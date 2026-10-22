package com.ideaecho.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class AccountStore(context: Context) {
    private val preferences=context.getSharedPreferences("account",Context.MODE_PRIVATE)
    val server: String get()=preferences.getString("server","")!!
    val accountId: String? get()=preferences.getString("owner",null)
    val token: String get() {
        val raw=preferences.getString("token",null) ?: return ""
        val bytes=Base64.decode(raw,Base64.NO_WRAP)
        return Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,bytes.copyOfRange(0,12)))
            doFinal(bytes.copyOfRange(12,bytes.size)).toString(Charsets.UTF_8)
        }
    }
    private fun key(): SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("idea-echo-token",null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder("idea-echo-token",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    fun save(server: String,owner: String,token: String) {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE,key()) }
        val encrypted=cipher.iv+cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        check(preferences.edit().putString("server",server.trimEnd('/')).putString("owner",owner).putString("token",Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit()) { "无法保存登录信息" }
    }
    fun logout() { preferences.edit().remove("owner").remove("token").commit() }
}
