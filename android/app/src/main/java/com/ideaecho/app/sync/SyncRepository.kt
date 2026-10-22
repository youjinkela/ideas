package com.ideaecho.app.sync

import android.content.Context
import androidx.room.withTransaction
import com.ideaecho.app.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

class SyncRepository(private val context: Context,private val db: AppDatabase,private val account: AccountStore) {
    companion object { private val mutex=Mutex() }
    suspend fun claimLocalRecords(accountId: String,ids: List<String>) {
        require(account.accountId==accountId)
        db.withTransaction {
            ids.forEach { id -> db.dao().find(id)?.let { if(it.owner==null)db.dao().update(it.copy(owner=accountId)) } }
        }
    }
    suspend fun syncOnce(accountId: String): Boolean = withContext(Dispatchers.IO) { mutex.withLock {
        if(account.accountId!=accountId)return@withLock true
        val api=IdeaApi(account.server,account.token)
        repeat(3) {
            val items=db.dao().all().filter { SyncRules.belongsTo(it.owner,accountId) && it.syncedRevision<it.revision && !it.syncError.orEmpty().startsWith("conflict:") }
            for (initial in items) {
                if(account.accountId!=accountId)return@withLock true
                try {
                    val item=db.withTransaction {
                        val latest=requireNotNull(db.dao().find(initial.id))
                        if(latest.pendingPayload!=null)latest else {
                            val images=JSONArray().apply { LocalAttachment.decode(latest.imagesJson).forEach { put(it.descriptor()) } }
                            val request=JSONObject().put("mutation_id",UUID.randomUUID().toString()).put("expected_version",latest.rawVersion)
                                .put("payload",JSONObject().put("text",latest.text).put("recorded_at",latest.recordedAt).put("attachments",images))
                            latest.copy(pendingMutation=request.getString("mutation_id"),pendingPayload=request.toString(),pendingRevision=latest.revision).also { db.dao().update(it) }
                        }
                    }
                    val request=JSONObject(item.pendingPayload!!)
                    val ack=api.request("PUT","/v1/ideas/${item.id}/record",request)
                    val images=request.getJSONObject("payload").getJSONArray("attachments")
                    for (index in 0 until images.length()) {
                        val image=images.getJSONObject(index)
                        val id=image.getString("id")
                        // A past local upload receipt is not proof the server still has the file.
                        val remote=api.request("GET","/v1/attachments/$id")
                        if(remote.optBoolean("content_ready") && remote.optString("sha256")==image.getString("sha256"))continue
                        val file=File(File(context.filesDir,"attachments"),id)
                        check(file.isFile) { "本机图片缺失，请从原图重新添加；文字仍然保留" }
                        api.request("PUT","/v1/attachments/$id/content",file=file)
                        db.dao().markImageUploaded(UploadedImage(accountId,id,image.getString("sha256")))
                    }
                    db.withTransaction {
                        val latest=requireNotNull(db.dao().find(item.id))
                        val sent=item.pendingRevision!!
                        db.dao().update(latest.copy(rawVersion=ack.getInt("accepted_version"),syncedRevision=if(SyncRules.canMarkSynced(latest.revision,sent,true))sent else latest.syncedRevision,pendingMutation=null,pendingPayload=null,pendingRevision=null,syncError=null))
                    }
                } catch(error: Exception) {
                    if(error is kotlinx.coroutines.CancellationException)throw error
                    db.withTransaction {
                        db.dao().find(initial.id)?.let { latest ->
                            db.dao().update(latest.copy(syncError=if(error is VersionConflict)"conflict:${error.detail}" else error.message ?: "同步未完成"))
                        }
                    }
                    if(error !is VersionConflict)throw error
                }
            }
        }
        true
    } }

    suspend fun keepLocalAfterConflict(id: String) {
        db.withTransaction {
            val item=requireNotNull(db.dao().find(id))
            val detail=JSONObject(item.syncError.orEmpty().removePrefix("conflict:"))
            require(detail.has("version")) { "请先重新登录或检查服务器" }
            db.dao().update(item.copy(rawVersion=detail.getInt("version"),revision=item.revision+1,pendingMutation=null,pendingPayload=null,pendingRevision=null,syncError=null))
        }
    }
}
