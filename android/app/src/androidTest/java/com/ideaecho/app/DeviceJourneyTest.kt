package com.ideaecho.app

import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.net.Uri
import androidx.room.Room
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class DeviceJourneyTest {
    @Test fun offlineImagesDraftKeystoreAndRetryUseRealDevice() = runBlocking {
        val base=InstrumentationRegistry.getInstrumentation().targetContext
        val prefix="test-${UUID.randomUUID()}"
        val folder=File(base.cacheDir,prefix).apply { mkdirs() }
        val context=object: ContextWrapper(base) {
            override fun getFilesDir()=folder
            override fun getSharedPreferences(name: String,mode: Int)=base.getSharedPreferences("$prefix-$name",mode)
        }
        val databaseName="$prefix.db"
        var db=Room.databaseBuilder(base,AppDatabase::class.java,databaseName).build()
        try {
            val source=File(folder,"fixture.png")
            source.outputStream().use { Bitmap.createBitmap(12,8,Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.PNG,100,it) }
            val imageStore=AttachmentStore(context)
            val images=listOf(imageStore.importImage(Uri.fromFile(source),0),imageStore.importImage(Uri.fromFile(source),1))
            source.delete()
            assertTrue(images.all { File(it.path).isFile })
            val capture=CaptureRepository(db)
            val id=UUID.randomUUID().toString()
            capture.saveDraft("未提交草稿",images,id)
            db.close()
            db=Room.databaseBuilder(base,AppDatabase::class.java,databaseName).build()
            assertEquals("未提交草稿",db.dao().draft()!!.text)
            CaptureRepository(db).saveCapture("离线文字加两图",images,id)
            CaptureRepository(db).saveCapture("离线文字加两图",images,id)
            val imageOnly=UUID.randomUUID().toString()
            CaptureRepository(db).saveCapture("",listOf(images[0]),imageOnly)
            assertEquals(2,db.dao().all().size)
            assertNull(db.dao().draft())
            val login=IdeaApi("http://127.0.0.1:47841").request("POST","/v1/auth/login",JSONObject().put("username","device-test").put("password","device-test-only-password"))
            val owner=login.getString("account_id");val token=login.getString("token")
            val account=AccountStore(context)
            account.save("http://127.0.0.1:47842",owner,token)
            assertEquals(token,AccountStore(context).token)
            assertFalse(context.getSharedPreferences("account",Context.MODE_PRIVATE).getString("token","")!!.contains(token))
            var sync=SyncRepository(context,db,account)
            val statusType=runCatching { Class.forName("com.ideaecho.app.sync.SyncStatusStore") }.getOrNull()
            assertNotNull("Sync attempts must expose durable status without note contents",statusType)
            sync.claimLocalRecords(owner,listOf(id,imageOnly))
            val queuedBeforeOffline=db.dao().all().associateBy { it.id }
            val imageBytes=images.associate { it.id to File(it.path).readBytes() }
            try { sync.syncOnce(owner);fail("Offline endpoint should fail") } catch (_: java.io.IOException) { }
            val failedStatus=SyncStatusStore(context).read(account.server,owner)
            assertTrue(failedStatus.lastAttemptAt>0)
            assertEquals(0L,failedStatus.lastSuccessAt)
            assertTrue(failedStatus.error.contains("本机"))
            // Deletion pull fails before preparing an upload: every field, including the
            // unfrozen pending payload and unsynced revision, must remain unchanged on disk.
            assertEquals("Offline pull must preserve both queued records",queuedBeforeOffline,db.dao().all().associateBy { it.id })
            db.close()
            db=Room.databaseBuilder(base,AppDatabase::class.java,databaseName).build()
            assertEquals("The complete offline queue must survive reopening",queuedBeforeOffline,db.dao().all().associateBy { it.id })
            images.forEach { assertArrayEquals("Offline image bytes must survive",imageBytes.getValue(it.id),File(it.path).readBytes()) }
            assertNull(db.dao().draft())
            sync=SyncRepository(context,db,account)
            account.save("http://127.0.0.1:47841",owner,token)
            sync.syncOnce(owner)
            assertTrue(db.dao().all().all { it.revision==it.syncedRevision && it.syncError==null })
            val successStatus=SyncStatusStore(context).read(account.server,owner)
            assertTrue(successStatus.lastSuccessAt>0)
            assertEquals("",successStatus.error)
            assertEquals(0L,SyncStatusStore(context).read(account.server,"other-owner").lastSuccessAt)
            sync.syncOnce(owner)
            assertEquals("An empty local queue is not a fresh server receipt",successStatus.lastSuccessAt,SyncStatusStore(context).read(account.server,owner).lastSuccessAt)
            val api=IdeaApi(account.server,account.token)
            val events=api.request("GET","/v1/changes?after=0").getJSONArray("events")
            assertEquals(2,(0 until events.length()).count { events.getJSONObject(it).getString("kind")=="record" })
            images.forEach { assertTrue(api.request("GET","/v1/attachments/${it.id}").getBoolean("content_ready")) }

            fun deleteSource(sourceId: String) {
                api.request("PUT","/v1/ideas/$sourceId/delete",JSONObject()
                    .put("mutation_id",UUID.randomUUID().toString()).put("expected_version",0).put("payload",JSONObject()))
            }
            fun assertCloudImageGone(image: LocalAttachment) {
                try { api.request("GET","/v1/attachments/${image.id}");fail("Deleted image metadata must be absent") }
                catch(error: HttpStatusFailure) { assertEquals(404,error.code) }
            }
            deleteSource(id)
            sync.syncOnce(owner)
            assertEquals(listOf(imageOnly),db.dao().all().map { it.id })
            assertTrue("The surviving image-only idea still owns the shared file",File(images[0].path).isFile)
            assertArrayEquals(imageBytes.getValue(images[0].id),File(images[0].path).readBytes())
            assertFalse("The deleted idea's unique image must be removed",File(images[1].path).exists())
            assertNotNull(db.dao().uploaded(owner,images[0].id))
            assertNull(db.dao().uploaded(owner,images[1].id))
            assertTrue(api.request("GET","/v1/attachments/${images[0].id}").getBoolean("content_ready"))
            assertCloudImageGone(images[1])

            deleteSource(imageOnly)
            sync.syncOnce(owner)
            assertTrue(db.dao().all().isEmpty())
            images.forEach {
                assertFalse("No source still references this local attachment",File(it.path).exists())
                assertNull(db.dao().uploaded(owner,it.id))
                assertCloudImageGone(it)
            }
            val deletions=api.request("GET","/v1/changes?after=0").getJSONArray("events")
            assertEquals("Cloud history must contain only the two tombstones",2,deletions.length())
            assertEquals(setOf(id,imageOnly),(0 until deletions.length()).map { index ->
                val event=deletions.getJSONObject(index)
                assertEquals("delete",event.getString("kind"))
                val payload=event.getJSONObject("payload")
                assertEquals(setOf("id","attachment_ids"),payload.keys().asSequence().toSet())
                assertEquals(event.getString("entity_id"),payload.getString("id"))
                event.getString("entity_id")
            }.toSet())
            assertFalse(deletions.toString().contains("离线文字加两图"))
            assertFalse(deletions.toString().contains("未提交草稿"))
            account.logout()
            assertEquals("",account.token)
            assertEquals(0,db.dao().all().size)
        } finally {
            db.close();base.deleteDatabase(databaseName)
            context.getSharedPreferences("account",Context.MODE_PRIVATE).edit().clear().commit()
            context.getSharedPreferences("sync-status",Context.MODE_PRIVATE).edit().clear().commit()
            context.getSharedPreferences("sync-changes",Context.MODE_PRIVATE).edit().clear().commit()
            folder.walkBottomUp().forEach { it.delete() }
        }
    }
}
