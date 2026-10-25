package com.ideaecho.app.sync

import android.content.Context
import androidx.room.withTransaction
import com.ideaecho.app.data.AccountStore
import com.ideaecho.app.data.AppDatabase
import com.ideaecho.app.data.IdeaEntity
import com.ideaecho.app.data.LocalAttachment
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.URLEncoder
import java.security.MessageDigest
import java.util.UUID

/** A session switch stops the old sync without recording an error against either account. */
internal class SyncSessionChanged : Exception()

private data class FeedPosition(val cursor: Long,val generation: String?)
private data class SourceDeletion(val id: String,val attachmentIds: Set<String>)

/** Connection metadata and an ID-only cleanup journal; never stores record/review contents. */
private class DeletionCheckpoint(context: Context,server: String,owner: String) {
    private val preferences=context.getSharedPreferences("sync-changes",Context.MODE_PRIVATE)
    private val key=MessageDigest.getInstance("SHA-256").digest((server.trimEnd('/')+"\n"+owner).toByteArray())
        .joinToString("") { "%02x".format(it) }
    fun position()=FeedPosition(preferences.getLong("$key-cursor",0),preferences.getString("$key-generation",null))
    fun save(position: FeedPosition) {
        if(!preferences.edit().putLong("$key-cursor",position.cursor).putString("$key-generation",position.generation).commit())
            throw IOException("Cannot persist deletion cursor")
    }
    fun pending(): Set<String> = preferences.getStringSet("$key-cleanup",emptySet())!!.toSet()
    fun queue(ids: Set<String>) {
        if(!preferences.edit().putStringSet("$key-cleanup",ids.toSet()).commit())
            throw IOException("Cannot persist attachment cleanup")
    }
}

/** Pulls a bounded batch completely before allowing any queued record mutations. */
internal class SyncedDeletionConsumer(
    private val context: Context,private val db: AppDatabase,private val account: AccountStore,
    private val server: String,private val owner: String,private val api: IdeaApi
) {
    private val checkpoint=DeletionCheckpoint(context,server,owner)

    fun ensureCurrent() {
        if(account.accountId!=owner || account.server!=server)throw SyncSessionChanged()
    }

    suspend fun pull() {
        ensureCurrent()
        cleanupPending()
        var position=checkpoint.position()
        var reset=false
        // Ten HTTP requests maximum, including a possible generation reset. A retry resumes
        // from the last durable page; uploads remain blocked while has_more is true.
        repeat(10) {
            ensureCurrent()
            val generation=position.generation?.let { "&generation="+URLEncoder.encode(it,"UTF-8") }.orEmpty()
            val page=try {
                api.request("GET","/v1/changes?after=${position.cursor}&limit=100$generation")
            } catch(error: VersionConflict) {
                ensureCurrent()
                if(!error.detail.optBoolean("cursor_reset") || reset)throw error
                val nextGeneration=validGeneration(error.detail.getString("generation"))
                position=FeedPosition(0,nextGeneration)
                checkpoint.save(position)
                reset=true
                return@repeat
            }
            ensureCurrent()
            val events=page.getJSONArray("events")
            require(events.length()<=100) { "Oversized changes page" }
            val next=page.getLong("next_cursor")
            val more=page.getBoolean("has_more")
            val nextGeneration=validGeneration(page.getString("generation"))
            require(position.generation==null || position.generation==nextGeneration) { "Unexpected feed generation" }
            var sequence=position.cursor
            val deletions=mutableListOf<SourceDeletion>()
            // Validate the whole page before deleting anything or moving its cursor.
            for(index in 0 until events.length()) {
                val event=events.getJSONObject(index)
                val seq=event.getLong("seq")
                require(seq>sequence) { "Changes feed did not advance" }
                sequence=seq
                if(event.getString("kind")!="delete")continue
                val id=validId(event.getString("entity_id"))
                val payload=event.getJSONObject("payload")
                require(payload.getString("id")==id) { "Mismatched deletion ID" }
                val images=payload.getJSONArray("attachment_ids")
                val ids=(0 until images.length()).map { validId(images.getString(it)) }.toSet()
                deletions.add(SourceDeletion(id,ids))
            }
            require(next==sequence && (!more || next>position.cursor)) { "Invalid changes cursor" }
            applyDeletions(deletions)
            ensureCurrent()
            position=FeedPosition(next,nextGeneration)
            // Room commits and file cleanup finish first. A crash before this commit replays
            // the page safely; a crash after deleting a row resumes the ID-only cleanup journal.
            checkpoint.save(position)
            if(!more)return
        }
        throw IOException("Deletion feed has more pages; retry before uploading")
    }

    suspend fun consumeGone(id: String) {
        ensureCurrent()
        applyDeletions(listOf(SourceDeletion(validId(id),emptySet())))
    }

    private suspend fun applyDeletions(deletions: List<SourceDeletion>) {
        db.withTransaction {
            ensureCurrent()
            val candidates=checkpoint.pending().toMutableSet()
            val owned=mutableListOf<String>()
            for(deletion in deletions) {
                val idea=db.dao().find(deletion.id)
                // A foreign or anonymous local row is never claimed by the logged-in feed.
                if(idea!=null && idea.owner!=owner)continue
                candidates.addAll(deletion.attachmentIds)
                if(idea!=null) {
                    candidates.addAll(imageIds(idea))
                    owned.add(idea.id)
                }
            }
            // Persist cleanup intent BEFORE removing the only local manifest. Payload IDs also
            // cover historical manifests, even if their source row or upload receipt is gone.
            if(candidates.isNotEmpty())checkpoint.queue(candidates)
            for(id in owned) {
                ensureCurrent()
                db.dao().deleteOwnedIdea(owner,id)
            }
        }
        cleanupPending()
    }

    private suspend fun cleanupPending() {
        ensureCurrent()
        val pending=checkpoint.pending()
        if(pending.isEmpty())return
        db.withTransaction {
            ensureCurrent()
            val remaining=db.dao().all()
            val referenced=remaining.flatMap { imageIds(it) }.toMutableSet()
            val localImages=remaining.flatMap { LocalAttachment.decode(it.imagesJson) }.toMutableList()
            db.dao().draft()?.let { localImages.addAll(LocalAttachment.decode(it.imagesJson)) }
            referenced.addAll(localImages.map { it.id })
            val paths=localImages.map { File(it.path).canonicalPath }.toSet()
            val directory=File(context.filesDir,"attachments").canonicalFile
            for(id in pending) {
                ensureCurrent()
                validId(id)
                val file=File(directory,id)
                if(id in referenced || file.canonicalPath in paths || db.dao().imageHasOtherOwner(owner,id))continue
                // Only UUID leaf files inside this app's attachment directory are eligible.
                // Never follow manifest paths or recursively remove a directory.
                if(file.canonicalFile.parentFile!=directory)throw IOException("Unsafe attachment path")
                if(file.exists() && (!file.isFile || !file.delete()))throw IOException("Attachment cleanup incomplete")
                db.dao().deleteImageReceipt(owner,id)
            }
        }
        ensureCurrent()
        checkpoint.queue(emptySet())
    }

    private fun imageIds(idea: IdeaEntity): Set<String> {
        val ids=LocalAttachment.decode(idea.imagesJson).map { validId(it.id) }.toMutableSet()
        idea.pendingPayload?.let {
            val images=JSONObject(it).getJSONObject("payload").getJSONArray("attachments")
            for(index in 0 until images.length())ids.add(validId(images.getJSONObject(index).getString("id")))
        }
        return ids
    }

    private fun validId(id: String): String {
        require(UUID.fromString(id).toString().equals(id,ignoreCase=true)) { "Invalid UUID" }
        return id
    }
    private fun validGeneration(generation: String): String {
        require(generation.isNotBlank() && generation.length<=80) { "Invalid feed generation" }
        return generation
    }
}
