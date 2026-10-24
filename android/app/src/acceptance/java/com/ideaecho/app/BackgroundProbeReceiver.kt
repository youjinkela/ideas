package com.ideaecho.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import androidx.work.*
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit

/** Shell-only fixture setup, compiled exclusively into the isolated acceptance APK. */
class BackgroundProbeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context,intent: Intent) {
        check(context.packageName=="com.ideaecho.app.acceptance")
        val pending=goAsync()
        CoroutineScope(SupervisorJob()+Dispatchers.IO).launch {
            try {
                val phase=intent.getStringExtra("phase") ?: "long"
                require(phase in listOf("long","recovery"))
                val seconds=intent.getIntExtra("delaySeconds",900)
                require(seconds in 60..1800)
                val receipt=File(context.filesDir,"background-$phase.json")
                check(!receipt.exists()) { "Phase already prepared" }
                val login=IdeaApi("http://127.0.0.1:47841").request("POST","/v1/auth/login",JSONObject()
                    .put("username","device-test").put("password","device-test-only-password"))
                val owner=login.getString("account_id")
                AccountStore(context).save("http://127.0.0.1:47841",owner,login.getString("token"))
                val source=File(context.cacheDir,"background-fixture-${UUID.randomUUID()}.png")
                try {
                    val bitmap=Bitmap.createBitmap(12,8,Bitmap.Config.ARGB_8888)
                    source.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG,100,it) }
                    bitmap.recycle()
                    val images=(0..1).map { AttachmentStore(context).importImage(Uri.fromFile(source),it) }
                    val id=UUID.randomUUID().toString()
                    CaptureRepository(AppDatabase.get(context)).saveCapture("独立后台验收 $phase",images,id,owner)
                    val work=OneTimeWorkRequestBuilder<SyncWorker>().setInputData(workDataOf("owner" to owner))
                        .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                        .setInitialDelay(seconds.toLong(),TimeUnit.SECONDS)
                        .setBackoffCriteria(BackoffPolicy.EXPONENTIAL,30,TimeUnit.SECONDS).build()
                    val prepared=System.currentTimeMillis()
                    val state=JSONObject().put("phase",phase).put("idea_id",id).put("work_id",work.id.toString())
                        .put("prepared_at",prepared).put("not_before",prepared+seconds*1000L).put("delay_seconds",seconds)
                    receipt.writeText(state.toString())
                    WorkManager.getInstance(context).enqueueUniqueWork("background-acceptance-$phase",ExistingWorkPolicy.KEEP,work)
                        .result.get(10,TimeUnit.SECONDS)
                    pending.resultData=state.toString()
                    pending.resultCode=-1
                } finally { source.delete() }
            } catch(error: Exception) {
                pending.resultCode=1
                pending.resultData=JSONObject().put("error_type",error.javaClass.simpleName).toString()
            } finally { pending.finish() }
        }
    }
}
