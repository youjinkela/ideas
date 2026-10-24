package com.ideaecho.app.sync

import android.content.Context
import android.content.SharedPreferences
import java.security.MessageDigest

data class SyncSnapshot(val lastAttemptAt: Long=0,val lastSuccessAt: Long=0,val error: String="",val loginRequired: Boolean=false)

/** Only connection metadata: no note contents, credentials or raw exception text. */
class SyncStatusStore(context: Context) {
    private val preferences=context.getSharedPreferences("sync-status",Context.MODE_PRIVATE)
    private fun key(server: String,owner: String): String = MessageDigest.getInstance("SHA-256")
        .digest((server.trimEnd('/')+"\n"+owner).toByteArray()).joinToString("") { "%02x".format(it) }
    fun read(server: String,owner: String): SyncSnapshot {
        val key=key(server,owner)
        return SyncSnapshot(preferences.getLong("$key-attempt",0),preferences.getLong("$key-success",0),preferences.getString("$key-error","")!!,preferences.getBoolean("$key-login",false))
    }
    fun started(server: String,owner: String) {
        val key=key(server,owner)
        preferences.edit().putLong("$key-attempt",System.currentTimeMillis()).apply()
    }
    fun finished(server: String,owner: String,uploaded: Boolean) {
        val key=key(server,owner)
        preferences.edit().remove("$key-error").remove("$key-login").apply {
            if(uploaded)putLong("$key-success",System.currentTimeMillis())
        }.apply()
    }
    fun failed(server: String,owner: String,error: Throwable) {
        val key=key(server,owner)
        preferences.edit().putString("$key-error",SyncFeedback.error(error)).putBoolean("$key-login",error is LoginRequired).apply()
    }
    fun register(listener: SharedPreferences.OnSharedPreferenceChangeListener)=preferences.registerOnSharedPreferenceChangeListener(listener)
    fun unregister(listener: SharedPreferences.OnSharedPreferenceChangeListener)=preferences.unregisterOnSharedPreferenceChangeListener(listener)
}
