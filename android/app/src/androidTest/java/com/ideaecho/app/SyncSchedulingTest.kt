package com.ideaecho.app

import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.*
import com.ideaecho.app.sync.SyncWorker
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class SyncSchedulingTest {
    @Test fun manualRetryDoesNotWaitBehindAnExistingDelayedJob() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val manager=WorkManager.getInstance(context)
        // A nonexistent account ensures these test jobs never read a token or upload user data.
        val owner="scheduling-test-${UUID.randomUUID()}"
        val background="idea-sync-$owner"
        val manual="idea-sync-manual-$owner"
        val periodic="idea-sync-periodic-$owner"
        try {
            val delayed=OneTimeWorkRequestBuilder<SyncWorker>().setInputData(workDataOf("owner" to owner))
                .setInitialDelay(1,TimeUnit.HOURS).build()
            manager.enqueueUniqueWork(background,ExistingWorkPolicy.KEEP,delayed).result.get(10,TimeUnit.SECONDS)
            SyncWorker.enqueue(context,owner).result.get(10,TimeUnit.SECONDS)
            assertEquals(listOf(delayed.id),manager.getWorkInfosForUniqueWork(background).get(10,TimeUnit.SECONDS).map { it.id })
            SyncWorker.enqueue(context,owner,manual=true).result.get(10,TimeUnit.SECONDS)
            val manualWork=manager.getWorkInfosForUniqueWork(manual).get(10,TimeUnit.SECONDS)
            assertEquals(1,manualWork.size)
            assertNotEquals(WorkInfo.State.BLOCKED,manualWork.single().state)
            assertEquals(0L,manualWork.single().initialDelayMillis)
            assertEquals(WorkInfo.State.ENQUEUED,requireNotNull(manager.getWorkInfoById(delayed.id).get(10,TimeUnit.SECONDS)).state)
        } finally {
            listOf(background,manual,periodic).forEach { manager.cancelUniqueWork(it).result.get(10,TimeUnit.SECONDS) }
        }
    }
}
