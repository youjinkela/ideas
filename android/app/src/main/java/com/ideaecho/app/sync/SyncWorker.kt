package com.ideaecho.app.sync

import android.content.Context
import androidx.work.*
import com.ideaecho.app.data.*
import java.util.concurrent.TimeUnit

class SyncWorker(context: Context,params: WorkerParameters) : CoroutineWorker(context,params) {
    override suspend fun doWork(): Result {
        val account=AccountStore(applicationContext)
        val owner=inputData.getString("owner") ?: return Result.success()
        if(account.accountId!=owner)return Result.success()
        return try {
            SyncRepository(applicationContext,AppDatabase.get(applicationContext),account).syncOnce(owner)
            Result.success()
        } catch(error: kotlinx.coroutines.CancellationException) { throw error
        } catch(error: LoginRequired) { Result.success()
        } catch(error: Exception) { if(runAttemptCount<8) Result.retry() else Result.failure() }
    }
    companion object {
        fun enqueue(context: Context,owner: String) {
            val constraints=Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
            val data=workDataOf("owner" to owner)
            val one=OneTimeWorkRequestBuilder<SyncWorker>().setInputData(data).setConstraints(constraints).setBackoffCriteria(BackoffPolicy.EXPONENTIAL,30,TimeUnit.SECONDS).build()
            val manager=WorkManager.getInstance(context)
            manager.enqueueUniqueWork("idea-sync-$owner",ExistingWorkPolicy.APPEND_OR_REPLACE,one)
            val periodic=PeriodicWorkRequestBuilder<SyncWorker>(15,TimeUnit.MINUTES).setInputData(data).setConstraints(constraints).build()
            manager.enqueueUniquePeriodicWork("idea-sync-periodic-$owner",ExistingPeriodicWorkPolicy.KEEP,periodic)
        }
    }
}
