package com.ideaecho.app.data

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

data class LocalAttachment(val id: String,val path: String,val mimeType: String,val sizeBytes: Long,val sha256: String,val order: Int) {
    fun descriptor(): JSONObject = JSONObject().put("id",id).put("order",order).put("mime_type",mimeType).put("size_bytes",sizeBytes).put("sha256",sha256)
    fun localJson(): JSONObject = descriptor().put("path",path)
    companion object {
        fun encode(images: List<LocalAttachment>): String = JSONArray().apply { images.forEach { put(it.localJson()) } }.toString()
        fun decode(text: String): List<LocalAttachment> {
            val array=JSONArray(text)
            return (0 until array.length()).map { index ->
                val a=array.getJSONObject(index)
                LocalAttachment(a.getString("id"),a.getString("path"),a.getString("mime_type"),a.getLong("size_bytes"),a.getString("sha256"),a.getInt("order"))
            }
        }
    }
}

class AttachmentStore(private val context: Context) {
    fun importImage(uri: Uri,order: Int): LocalAttachment {
        val folder=File(context.filesDir,"attachments").apply { mkdirs() }
        val id=UUID.randomUUID().toString()
        val target=File(folder,id)
        val temp=File(folder,"$id.part")
        try {
            var count=0L
            val digest=MessageDigest.getInstance("SHA-256")
            context.contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input) { "无法读取这张图片" }
                temp.outputStream().use { output ->
                    val buffer=ByteArray(65536)
                    while (true) {
                        val length=input.read(buffer)
                        if (length<0) break
                        count+=length
                        require(count<=20L*1024*1024) { "单张图片不能超过20MB" }
                        digest.update(buffer,0,length);output.write(buffer,0,length)
                    }
                    output.flush();output.fd.sync()
                }
            }
            val bounds=BitmapFactory.Options().apply { inJustDecodeBounds=true }
            BitmapFactory.decodeFile(temp.absolutePath,bounds)
            require(bounds.outMimeType in listOf("image/png","image/jpeg","image/webp") && bounds.outWidth>0 && bounds.outHeight>0) { "请选择 JPEG、PNG 或 WebP 图片" }
            require(bounds.outWidth.toLong()*bounds.outHeight<=100_000_000) { "图片分辨率过大" }
            require(temp.renameTo(target)) { "手机空间不足，图片没有保存" }
            return LocalAttachment(id,target.absolutePath,bounds.outMimeType,count,digest.digest().joinToString("") { "%02x".format(it) },order)
        } finally { temp.delete() }
    }
}
