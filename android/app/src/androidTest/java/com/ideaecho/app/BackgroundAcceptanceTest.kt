package com.ideaecho.app

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.*
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit

/** Preparation is performed by the acceptance-only receiver, not by instrumentation. */
@RunWith(AndroidJUnit4::class)
class BackgroundAcceptanceTest {
    private fun context(): Context {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        // Never seed, change accounts, force-stop, or inspect the user's everyday app.
        assumeTrue("Requires isolated acceptance application ID",context.packageName=="com.ideaecho.app.acceptance")
        assumeTrue("Explicit background acceptance invocation required",InstrumentationRegistry.getArguments().getString("backgroundAcceptance")=="true")
        return context
    }
    private fun phase(): String {
        val phase=requireNotNull(InstrumentationRegistry.getArguments().getString("phase"))
        require(phase in listOf("long","recovery"))
        return phase
    }
    private fun receipt(context: Context)=File(context.filesDir,"background-${phase()}.json")

    @Test fun verifyBackgroundUpload() = runBlocking {
        val context=context()
        val state=JSONObject(receipt(context).readText())
        val observedAt=requireNotNull(InstrumentationRegistry.getArguments().getString("completionObservedAt")).toLong()
        require(observedAt<System.currentTimeMillis()) { "Completion must be observed before starting verification" }
        val account=AccountStore(context)
        assertEquals("Only the fixture endpoint may be contacted","http://127.0.0.1:47841",account.server)
        val fixture=IdeaApi("http://127.0.0.1:47841").request("POST","/v1/auth/login",JSONObject()
            .put("username","device-test").put("password","device-test-only-password"))
        assertEquals("Only the fixture owner may be inspected",fixture.getString("account_id"),account.accountId)
        val work=WorkManager.getInstance(context).getWorkInfoById(UUID.fromString(state.getString("work_id")))
            .get(10,TimeUnit.SECONDS)!!
        assertEquals("Background upload must finish without the preparation runner",WorkInfo.State.SUCCEEDED,work.state)
        val record=AppDatabase.get(context).dao().find(state.getString("idea_id"))!!
        assertEquals(record.revision,record.syncedRevision)
        assertNull(record.syncError)
        val status=SyncStatusStore(context).read(account.server,account.accountId!!)
        // A regular periodic job may legitimately upload before the delayed probe runs.
        assertTrue(status.lastSuccessAt>=state.getLong("prepared_at"))
        assertTrue("Upload must predate the external completion observation",status.lastSuccessAt<=observedAt)
        assertEquals("",status.error)
        val api=IdeaApi(account.server,account.token)
        val events=api.request("GET","/v1/changes?after=0").getJSONArray("events")
        assertEquals(1,(0 until events.length()).count {
            val event=events.getJSONObject(it)
            event.getString("kind")=="record" && event.getString("entity_id")==record.id
        })
        LocalAttachment.decode(record.imagesJson).forEach { image ->
            val remote=api.request("GET","/v1/attachments/${image.id}")
            assertTrue(remote.getBoolean("content_ready"))
            assertEquals(image.sha256,remote.getString("sha256"))
        }
    }
}
