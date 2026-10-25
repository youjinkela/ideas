package com.ideaecho.app

import android.content.Context
import android.content.ContextWrapper
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.InetAddress
import java.util.UUID

/** Only synthetic records, a unique database/preferences/files directory, and loopback HTTP. */
@RunWith(AndroidJUnit4::class)
class SyncedDeletionTest {
    private class Fixture : AutoCloseable {
        val base=InstrumentationRegistry.getInstrumentation().targetContext
        val prefix="synced-deletion-${UUID.randomUUID()}"
        val folder=File(base.cacheDir,prefix).apply { mkdirs() }
        val context=object: ContextWrapper(base) {
            override fun getFilesDir()=folder
            override fun getSharedPreferences(name: String,mode: Int)=base.getSharedPreferences("$prefix-$name",mode)
        }
        val db=Room.databaseBuilder(base,AppDatabase::class.java,"$prefix.db").build()
        val server=MockWebServer().apply { start(InetAddress.getByName("127.0.0.1"),0) }
        // MockWebServer.url() reverse-resolves the bind address, often to localhost.
        // Set both hosts explicitly so a server-switch test cannot silently become a no-op.
        val address=server.url("/").newBuilder().host("127.0.0.1").build().toString().trimEnd('/')
        val alternateAddress=server.url("/").newBuilder().host("localhost").build().toString().trimEnd('/')
        val owner="fixture-owner"
        val account=AccountStore(context)
        val calls=java.util.Collections.synchronizedList(mutableListOf<RecordedRequest>())
        init { check(address!=alternateAddress) { "Fixture server addresses must differ" };login() }
        // No token or AndroidKeyStore is needed by this synthetic HTTP server.
        fun login(owner: String=this.owner,address: String=this.address) {
            check(context.getSharedPreferences("account",Context.MODE_PRIVATE).edit()
                .putString("owner",owner).putString("server",address).remove("token").commit())
        }
        fun respond(block: (RecordedRequest)->MockResponse) {
            server.dispatcher=object: Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse {
                    calls.add(request)
                    return block(request)
                }
            }
        }
        suspend fun sync()=SyncRepository(context,db,account).syncOnce(account.accountId!!)
        fun image(): LocalAttachment {
            val id=UUID.randomUUID().toString()
            val file=File(File(folder,"attachments").apply { mkdirs() },id).apply { writeText("synthetic image") }
            return LocalAttachment(id,file.absolutePath,"image/png",file.length(),"a".repeat(64),0)
        }
        suspend fun idea(images: List<LocalAttachment> = emptyList(),owner: String?=this.owner,pending: List<LocalAttachment>?=null,synced: Boolean=false): IdeaEntity {
            val id=UUID.randomUUID().toString()
            val request=pending?.let { JSONObject().put("mutation_id",UUID.randomUUID()).put("expected_version",0)
                .put("payload",JSONObject().put("text","lost acknowledgement fixture").put("recorded_at","2026-10-25T12:00:00Z")
                    .put("attachments",JSONArray().apply { it.forEach { image -> put(image.descriptor()) } })) }
            return IdeaEntity(id,"offline edited fixture","2026-10-25T12:00:00Z",LocalAttachment.encode(images),owner,
                revision=2,syncedRevision=if(synced)2 else 0,pendingPayload=request?.toString(),
                pendingMutation=request?.getString("mutation_id"),pendingRevision=if(request!=null)1 else null)
                .also { db.dao().insert(it) }
        }
        suspend fun receipt(image: LocalAttachment,owner: String=this.owner) { db.dao().markImageUploaded(UploadedImage(owner,image.id,image.sha256)) }
        override fun close() {
            server.shutdown();db.close();base.deleteDatabase("$prefix.db")
            listOf("account","sync-status","sync-changes").forEach { context.getSharedPreferences(it,Context.MODE_PRIVATE).edit().clear().commit() }
            folder.walkBottomUp().forEach { it.delete() }
        }
    }
    private fun event(seq: Long,id: String,images: List<LocalAttachment> = emptyList(),kind: String="delete")=JSONObject()
        .put("seq",seq).put("kind",kind).put("entity_id",id)
        .put("payload",JSONObject().put("id",id).put("attachment_ids",JSONArray(images.map { it.id })))
    private fun page(cursor: Long=0,more: Boolean=false,generation: String="fixture-generation",vararg events: JSONObject)=MockResponse().setBody(
        JSONObject().put("events",JSONArray(events.toList())).put("next_cursor",cursor).put("has_more",more).put("generation",generation).toString())
    private fun ack()=MockResponse().setBody("{\"accepted_version\":1}")
    private suspend fun failsWith(code: Int,block: suspend ()->Unit) {
        try { block();fail("Expected HTTP $code") } catch(error: HttpStatusFailure) { assertEquals(code,error.code) }
    }

    @Test fun offlineEditedAndLostAckCopiesAreDeletedBeforeAnyQueuedUpload() = runBlocking {
        Fixture().use { f ->
            val image=f.image();val oldImage=f.image()
            val deleted=f.idea(listOf(image),pending=listOf(oldImage));f.receipt(image);f.receipt(oldImage)
            val survivor=f.idea()
            f.respond { r -> if(r.method=="GET")page(1,false,"fixture-generation",event(1,deleted.id,listOf(oldImage))) else ack() }
            assertTrue(f.sync())
            assertNull(f.db.dao().find(deleted.id))
            assertNull(f.db.dao().uploaded(f.owner,image.id));assertNull(f.db.dao().uploaded(f.owner,oldImage.id))
            assertFalse(File(image.path).exists());assertFalse(File(oldImage.path).exists())
            assertEquals(2L,f.db.dao().find(survivor.id)!!.syncedRevision)
            assertEquals(listOf("GET","PUT"),f.calls.map { it.method })
            assertEquals("/v1/ideas/${survivor.id}/record",f.calls.last().path)
            assertEquals("100",f.calls.first().requestUrl!!.queryParameter("limit"))
            // A new repository instance must resume the persisted cursor, including ignored events.
            f.respond { page(2,false,"fixture-generation",event(2,survivor.id,kind="review")) }
            f.sync();f.respond { page(2) };f.sync()
            assertEquals("1",f.calls[2].requestUrl!!.queryParameter("after"))
            assertEquals("fixture-generation",f.calls[2].requestUrl!!.queryParameter("generation"))
            assertEquals("2",f.calls[3].requestUrl!!.queryParameter("after"))
        }
    }

    @Test fun deletesOnlyUnsharedCurrentAccountImagesAndProtectsDraftsAndPendingReferences() = runBlocking {
        Fixture().use { f ->
            val exclusive=f.image();val historical=f.image();val shared=f.image();val draft=f.image();val other=f.image();val pending=f.image();val foreignReceipt=f.image()
            val deleted=f.idea(listOf(exclusive,shared,draft,other,pending,foreignReceipt))
            val current=f.idea(listOf(shared),synced=true)
            val foreign=f.idea(listOf(other),owner="other-owner")
            val pendingOnly=f.idea(owner="other-owner",pending=listOf(pending))
            val unsaved=DraftEntity(text="unsaved fixture",imagesJson=LocalAttachment.encode(listOf(draft)),saveId=deleted.id)
            f.db.dao().setDraft(unsaved)
            listOf(exclusive,shared,draft,other,pending,foreignReceipt).forEach { f.receipt(it) }
            f.receipt(foreignReceipt,"other-owner")
            // Even historical payload IDs cannot erase another account's local receipt/file.
            val foreignOnly=f.image();f.receipt(foreignOnly,"other-owner")
            f.respond { page(1,false,"fixture-generation",event(1,deleted.id,listOf(exclusive,historical,foreignOnly))) }
            f.sync()
            assertNull(f.db.dao().find(deleted.id));assertFalse(File(exclusive.path).exists())
            assertNull(f.db.dao().uploaded(f.owner,exclusive.id))
            assertFalse("Historical server manifest images must also be cleaned",File(historical.path).exists())
            listOf(shared,draft,other,pending,foreignReceipt,foreignOnly).forEach { assertTrue(File(it.path).isFile) }
            assertEquals(unsaved,f.db.dao().draft())
            assertEquals(current,f.db.dao().find(current.id));assertEquals(foreign,f.db.dao().find(foreign.id))
            assertEquals(pendingOnly,f.db.dao().find(pendingOnly.id))
            assertNotNull(f.db.dao().uploaded("other-owner",foreignReceipt.id))
        }
    }

    @Test fun foreignAndUnownedIdeasCannotBeDeletedByCurrentFeed() = runBlocking {
        Fixture().use { f ->
            val image=f.image();val foreign=f.idea(listOf(image),owner="other-owner");val local=f.idea(owner=null)
            f.respond { page(2,false,"fixture-generation",event(1,foreign.id,listOf(image)),event(2,local.id)) }
            f.sync()
            assertEquals(foreign,f.db.dao().find(foreign.id));assertEquals(local,f.db.dao().find(local.id));assertTrue(File(image.path).isFile)
        }
    }

    private fun goneDuringUpload(replay: Boolean)=runBlocking {
        Fixture().use { f ->
            val image=f.image();val deleted=f.idea(listOf(image),pending=if(replay)listOf(image) else null);f.receipt(image)
            val shared=f.idea(listOf(image),owner="other-owner");val survivor=f.idea()
            f.respond { r -> when {
                r.method=="GET" -> page()
                r.path=="/v1/ideas/${deleted.id}/record" -> MockResponse().setResponseCode(410).setBody("{\"detail\":\"deleted\"}")
                else -> ack()
            } }
            f.sync()
            assertNull(f.db.dao().find(deleted.id));assertEquals(shared,f.db.dao().find(shared.id));assertTrue(File(image.path).isFile)
            assertEquals(2L,f.db.dao().find(survivor.id)!!.syncedRevision)
            assertFalse(f.calls.any { it.path!!.startsWith("/v1/attachments/") })
        }
    }
    @Test fun newUpload410ConsumesDeletionAndContinuesOtherRecords()=goneDuringUpload(false)
    @Test fun lostAcknowledgementReplay410AlsoConsumesDeletion()=goneDuringUpload(true)

    @Test fun upload410DeletesExclusiveImagesAndReceipts()=runBlocking {
        Fixture().use { f ->
            val image=f.image();val deleted=f.idea(listOf(image));f.receipt(image)
            f.respond { r -> if(r.method=="GET")page() else MockResponse().setResponseCode(410) }
            f.sync()
            assertNull(f.db.dao().find(deleted.id));assertFalse(File(image.path).exists())
            assertNull(f.db.dao().uploaded(f.owner,image.id))
        }
    }

    @Test fun accountSwitchDuringUpload410CannotDeletePreviousAccountCopy()=runBlocking {
        Fixture().use { f ->
            val image=f.image();val idea=f.idea(listOf(image),pending=listOf(image))
            f.respond { r -> if(r.method=="GET")page() else {
                f.login(owner="other-owner");MockResponse().setResponseCode(410)
            } }
            f.sync()
            assertEquals(idea,f.db.dao().find(idea.id));assertTrue(File(image.path).exists())
        }
    }

    @Test fun interruptedFileCleanupIsRetriedEvenAfterIdeaRowIsGone()=runBlocking {
        Fixture().use { f ->
            val image=f.image();val idea=f.idea(listOf(image))
            val path=File(image.path)
            assertTrue(path.delete());assertTrue(path.mkdir())
            val blocker=File(path,"synthetic-blocker").apply { writeText("fixture") }
            f.respond { page(1,false,"fixture-generation",event(1,idea.id)) }
            try { f.sync();fail("Incomplete file cleanup must retry") } catch(expected: java.io.IOException) { }
            assertNull(f.db.dao().find(idea.id))
            assertTrue(blocker.delete());assertTrue(path.delete());path.writeText("synthetic image")
            f.sync()
            assertFalse(path.exists())
            assertTrue("Failed page must not advance its cursor",f.calls.all { it.requestUrl!!.queryParameter("after")=="0" })
        }
    }

    @Test fun nonResetConflictDoesNotRewindCursorOrUpload()=runBlocking {
        Fixture().use { f ->
            val idea=f.idea()
            f.respond { MockResponse().setResponseCode(409).setBody("{\"detail\":{\"message\":\"fixture conflict\"}}") }
            try { f.sync();fail("Non-reset conflict must propagate") } catch(expected: VersionConflict) { }
            assertEquals(idea,f.db.dao().find(idea.id));assertEquals(1,f.calls.size)
        }
    }

    @Test fun pullFailureLeavesOfflineEditsQueuedWithoutUploading()=runBlocking {
        Fixture().use { f ->
            val idea=f.idea()
            f.respond { MockResponse().setResponseCode(503) }
            failsWith(503) { f.sync() }
            assertEquals(idea,f.db.dao().find(idea.id));assertEquals(listOf("GET"),f.calls.map { it.method })
        }
    }

    @Test fun failedLaterPageResumesAfterDurablyAppliedEarlierDeletion()=runBlocking {
        Fixture().use { f ->
            val deleted=f.idea();val survivor=f.idea()
            f.respond { r -> if(r.requestUrl!!.queryParameter("after")=="0")page(1,true,"fixture-generation",event(1,deleted.id)) else MockResponse().setResponseCode(503) }
            failsWith(503) { f.sync() }
            assertNull(f.db.dao().find(deleted.id));assertEquals(survivor,f.db.dao().find(survivor.id))
            f.respond { r -> if(r.method=="GET")page(1) else ack() }
            f.sync()
            assertEquals("1",f.calls[2].requestUrl!!.queryParameter("after"))
            assertEquals(2L,f.db.dao().find(survivor.id)!!.syncedRevision)
        }
    }

    @Test fun generationResetReplaysFromZeroBeforeUploads()=runBlocking {
        Fixture().use { f ->
            f.respond { page(7,false,"old",event(7,UUID.randomUUID().toString(),kind="status")) };f.sync()
            val deleted=f.idea()
            f.respond { r -> if(r.requestUrl!!.queryParameter("generation")=="old")
                MockResponse().setResponseCode(409).setBody("{\"detail\":{\"cursor_reset\":true,\"generation\":\"new\"}}")
                else page(1,false,"new",event(1,deleted.id)) }
            f.sync()
            assertEquals("7",f.calls[1].requestUrl!!.queryParameter("after"))
            assertEquals("0",f.calls[2].requestUrl!!.queryParameter("after"))
            assertEquals("new",f.calls[2].requestUrl!!.queryParameter("generation"))
            assertNull(f.db.dao().find(deleted.id));assertTrue(f.calls.all { it.method=="GET" })
        }
    }

    @Test fun cursorIsScopedByBothServerAndAccount()=runBlocking {
        Fixture().use { f ->
            f.respond { r -> if(r.requestUrl!!.queryParameter("after")=="0")page(5,false,"fixture-generation",event(5,UUID.randomUUID().toString(),kind="record")) else page(5) }
            f.sync();f.login(owner="other-owner");f.sync()
            f.login(address=f.alternateAddress);f.sync()
            f.login();f.sync()
            assertEquals(listOf("0","0","0","5"),f.calls.map { it.requestUrl!!.queryParameter("after") })
            assertEquals(listOf("127.0.0.1","127.0.0.1","localhost","127.0.0.1"),f.calls.map { it.getHeader("Host")!!.substringBefore(':') })
        }
    }

    @Test fun accountOrServerSwitchDuringPullCannotDeleteOldSessionSources()=runBlocking {
        Fixture().use { f ->
            val deleted=f.idea()
            f.respond { f.login(address=f.alternateAddress);page(1,false,"fixture-generation",event(1,deleted.id)) }
            f.sync();assertEquals(deleted,f.db.dao().find(deleted.id))
            f.login()
            f.respond { f.login(owner="other-owner");page(1,false,"fixture-generation",event(1,deleted.id)) }
            f.sync();assertEquals(deleted,f.db.dao().find(deleted.id))
            assertTrue(f.calls.all { it.requestUrl!!.queryParameter("after")=="0" })
        }
    }

    @Test fun malformedDeletePageCannotAdvanceCursorOrPartiallyDelete()=runBlocking {
        Fixture().use { f ->
            val deleted=f.idea()
            f.respond { page(2,false,"fixture-generation",event(1,deleted.id),event(2,"invalid-id")) }
            try { f.sync();fail("Malformed page must fail closed") } catch(expected: Exception) { /* retry the same page */ }
            assertEquals(deleted,f.db.dao().find(deleted.id))
            f.respond { page(1,false,"fixture-generation",event(1,deleted.id)) };f.sync()
            assertEquals("0",f.calls[1].requestUrl!!.queryParameter("after"));assertNull(f.db.dao().find(deleted.id))
        }
    }

    @Test fun unsafePayloadAttachmentIdCannotDeleteOutsideAttachmentDirectory()=runBlocking {
        Fixture().use { f ->
            val idea=f.idea();val outside=File(f.folder,"keep-fixture.txt").apply { writeText("fixture") }
            val malformed=event(1,idea.id).apply { getJSONObject("payload").put("attachment_ids",JSONArray().put("../keep-fixture.txt")) }
            f.respond { page(1,false,"fixture-generation",malformed) }
            try { f.sync();fail("Unsafe attachment IDs must reject the page") } catch(expected: Exception) { }
            assertTrue(outside.isFile);assertEquals(idea,f.db.dao().find(idea.id))
        }
    }

    @Test fun replayedIdOnlyDeletionCleansHistoricalFileWhenIdeaIsAlreadyAbsent()=runBlocking {
        Fixture().use { f ->
            val historical=f.image()
            f.respond { page(1,false,"fixture-generation",event(1,UUID.randomUUID().toString(),listOf(historical))) }
            f.sync();assertFalse(File(historical.path).exists())
        }
    }

    @Test fun endlessFeedIsBoundedAndDefersUploadsUntilCaughtUp()=runBlocking {
        Fixture().use { f ->
            val survivor=f.idea()
            f.respond { r ->
                val seq=r.requestUrl!!.queryParameter("after")!!.toLong()+1
                page(seq,true,"fixture-generation",event(seq,UUID.randomUUID().toString(),kind="review"))
            }
            try { f.sync();fail("An unfinished bounded pull must request retry") } catch(expected: java.io.IOException) { }
            assertTrue(f.calls.size in 1..20);assertTrue(f.calls.all { it.method=="GET" })
            assertEquals(survivor,f.db.dao().find(survivor.id))
            val checkpoint=f.calls.last().requestUrl!!.queryParameter("after")!!.toLong()+1
            f.respond { r -> if(r.method=="GET")page(checkpoint) else ack() };f.sync()
            assertEquals(2L,f.db.dao().find(survivor.id)!!.syncedRevision)
        }
    }

    @Test fun repeatedResetsAreBoundedAndDoNotUpload()=runBlocking {
        Fixture().use { f ->
            val survivor=f.idea()
            f.respond { MockResponse().setResponseCode(409).setBody("{\"detail\":{\"cursor_reset\":true,\"generation\":\"new\"}}") }
            try { f.sync();fail("Repeated reset must retry later") } catch(expected: Exception) { }
            assertTrue(f.calls.size in 1..3);assertEquals(survivor,f.db.dao().find(survivor.id))
        }
    }
}
