package com.ideaecho.app

import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.net.Uri
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.InetAddress
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class PartialBatchStatusTest {
    private fun scenario(firstRecordSucceeds: Boolean) = runBlocking {
        val base=InstrumentationRegistry.getInstrumentation().targetContext
        val prefix="partial-batch-${UUID.randomUUID()}"
        val folder=File(base.cacheDir,prefix).apply { mkdirs() }
        val context=object: ContextWrapper(base) {
            override fun getFilesDir()=folder
            override fun getSharedPreferences(name: String,mode: Int)=base.getSharedPreferences("$prefix-$name",mode)
        }
        val databaseName="$prefix.db"
        val db=Room.databaseBuilder(base,AppDatabase::class.java,databaseName).build()
        val server=MockWebServer()
        try {
            server.start(InetAddress.getByName("127.0.0.1"),0)
            val address=server.url("/").toString().trimEnd('/')
            val account=AccountStore(context).apply { save(address,"fixture-owner","fixture-token") }
            val source=File(folder,"source.png")
            val bitmap=Bitmap.createBitmap(8,8,Bitmap.Config.ARGB_8888)
            source.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG,100,it) }
            bitmap.recycle()
            val images=(0..1).map { AttachmentStore(context).importImage(Uri.fromFile(source),it) }
            val capture=CaptureRepository(db)
            val first=UUID.randomUUID().toString()
            val second=UUID.randomUUID().toString()
            if(firstRecordSucceeds) {
                capture.saveCapture("first fixture",listOf(images[0]),first,account.accountId)
                db.dao().find(first)!!.let { db.dao().update(it.copy(recordedAt="2026-10-25T12:00:00+08:00")) }
                server.enqueue(MockResponse().setBody("{\"accepted_version\":1}"))
                server.enqueue(MockResponse().setBody("{\"content_ready\":false}"))
                server.enqueue(MockResponse().setBody("{\"content_ready\":true}"))
            }
            capture.saveCapture("second fixture",listOf(images[1]),second,account.accountId)
            db.dao().find(second)!!.let { db.dao().update(it.copy(recordedAt="2026-10-24T12:00:00+08:00")) }
            server.enqueue(MockResponse().setBody("{\"accepted_version\":1}"))
            server.enqueue(MockResponse().setBody("{\"content_ready\":false}"))
            server.enqueue(MockResponse().setResponseCode(503).setBody("{\"detail\":\"fixture unavailable\"}"))
            try {
                SyncRepository(context,db,account).syncOnce(account.accountId!!)
                fail("The second image must remain pending after its failed HTTP upload")
            } catch(error: HttpStatusFailure) { assertEquals(503,error.code) }
            assertEquals(0L,db.dao().find(second)!!.syncedRevision)
            assertNotNull(db.dao().find(second)!!.pendingPayload)
            assertTrue(images.all { File(it.path).isFile })
            val status=SyncStatusStore(context).read(address,account.accountId!!)
            assertTrue(status.error.contains("503"))
            assertFalse(status.loginRequired)
            if(firstRecordSucceeds) {
                assertEquals(1L,db.dao().find(first)!!.syncedRevision)
                assertEquals(6,server.requestCount)
                assertTrue("A completed record and image receipt must survive a later failure",status.lastSuccessAt>0)
            } else {
                assertEquals(3,server.requestCount)
                assertEquals("A record acknowledgement alone must not count before its image succeeds",0L,status.lastSuccessAt)
            }
            assertEquals(0L,SyncStatusStore(context).read(address,"another-owner").lastSuccessAt)
        } finally {
            server.shutdown()
            db.close()
            base.deleteDatabase(databaseName)
            context.getSharedPreferences("account",Context.MODE_PRIVATE).edit().clear().commit()
            context.getSharedPreferences("sync-status",Context.MODE_PRIVATE).edit().clear().commit()
            folder.walkBottomUp().forEach { it.delete() }
        }
    }

    @Test fun completedUploadTimeSurvivesLaterImageFailure() = scenario(true)
    @Test fun incompleteFirstImageNeverSetsSuccessfulUploadTime() = scenario(false)
}
