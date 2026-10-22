package com.ideaecho.app.sync

import com.ideaecho.app.BuildConfig
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.URI
import java.util.concurrent.TimeUnit

class LoginRequired : Exception("登录已过期，请重新登录；本机记录仍然保留")
class VersionConflict(val detail: JSONObject) : Exception("原文有两个版本，请在已记录中处理冲突")

class IdeaApi(val server: String,private val token: String="") {
    private val client=OkHttpClient.Builder().callTimeout(30,TimeUnit.SECONDS).followRedirects(false).followSslRedirects(false).build()
    init {
        val uri=URI(server)
        val host=uri.host ?: ""
        val numbers=host.split('.').mapNotNull { it.toIntOrNull() }
        val local=host=="localhost" || host=="127.0.0.1" || numbers.size==4 && numbers.all { it in 0..255 } && (numbers[0]==10 || numbers[0]==192 && numbers[1]==168 || numbers[0]==172 && numbers[1] in 16..31)
        require(uri.userInfo==null && uri.query==null && uri.fragment==null && uri.rawPath.orEmpty() in listOf("","/") && (uri.scheme=="https" && host.isNotEmpty() || BuildConfig.DEBUG && uri.scheme=="http" && local)) { "请输入 HTTPS 服务器根地址；调试版仅允许本机/局域网 HTTP" }
    }
    fun request(method: String,path: String,body: JSONObject?=null,file: File?=null): JSONObject {
        val requestBody=file?.asRequestBody("application/octet-stream".toMediaType()) ?: body?.toString()?.toRequestBody("application/json; charset=utf-8".toMediaType())
        val request=Request.Builder().url(server.trimEnd('/')+path).apply { if(token.isNotBlank())header("Authorization","Bearer $token") }.method(method,requestBody).build()
        client.newCall(request).execute().use { response ->
            val text=response.body?.string().orEmpty()
            val result=runCatching { JSONObject(text) }.getOrElse { JSONObject() }
            if(response.code==401)throw LoginRequired()
            if(response.code==409)throw VersionConflict(result.optJSONObject("detail") ?: JSONObject().put("message","版本冲突"))
            if(!response.isSuccessful)throw IOException("请求未完成（${response.code}），请检查网络/图片容量后重试")
            return result
        }
    }
}
