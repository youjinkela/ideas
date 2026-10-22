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
            val sync=SyncRepository(context,db,account)
            sync.claimLocalRecords(owner,listOf(id,imageOnly))
            try { sync.syncOnce(owner);fail("Offline endpoint should fail") } catch (_: java.io.IOException) { }
            assertEquals(0L,db.dao().find(id)!!.syncedRevision)
            assertTrue(db.dao().all().any { it.pendingPayload!=null })
            account.save("http://127.0.0.1:47841",owner,token)
            sync.syncOnce(owner)
            assertTrue(db.dao().all().all { it.revision==it.syncedRevision && it.syncError==null })
            sync.syncOnce(owner)
            val api=IdeaApi(account.server,account.token)
            val events=api.request("GET","/v1/changes?after=0").getJSONArray("events")
            assertEquals(2,(0 until events.length()).count { events.getJSONObject(it).getString("kind")=="record" })
            images.forEach { assertTrue(api.request("GET","/v1/attachments/${it.id}").getBoolean("content_ready")) }
            account.logout()
            assertEquals("",account.token)
            assertEquals(2,db.dao().all().size)
        } finally {
            db.close();base.deleteDatabase(databaseName)
            context.getSharedPreferences("account",Context.MODE_PRIVATE).edit().clear().commit()
            folder.walkBottomUp().forEach { it.delete() }
        }
    }
}
