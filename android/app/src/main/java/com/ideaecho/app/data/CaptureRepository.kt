package com.ideaecho.app.data

import androidx.room.withTransaction
import java.io.File
import java.time.OffsetDateTime
import java.util.UUID

class CaptureRepository(private val db: AppDatabase) {
    suspend fun saveCapture(text: String,attachments: List<LocalAttachment>,saveId: String,owner: String?=null): String {
        require(CaptureRules.canSave(text,attachments.size)) { "请写一句点子或添加图片" }
        require(attachments.size<=20 && attachments.sumOf { it.sizeBytes }<=200L*1024*1024) { "单条最多20张图片，合计200MB" }
        attachments.forEach { require(File(it.path).isFile) { "图片尚未保存，请重新选择" } }
        db.withTransaction {
            db.dao().insert(IdeaEntity(saveId,text.trim(),OffsetDateTime.now().toString(),LocalAttachment.encode(attachments),owner))
            db.dao().clearDraft(saveId)
        }
        return saveId
    }
    suspend fun saveDraft(text: String,attachments: List<LocalAttachment>,saveId: String) {
        db.dao().setDraft(DraftEntity(text=text,imagesJson=LocalAttachment.encode(attachments),saveId=saveId))
    }
    fun observeDraft() = db.dao().observeDraft()
    suspend fun editCapture(id: String,text: String,images: List<LocalAttachment>) {
        require(CaptureRules.canSave(text,images.size))
        db.withTransaction {
            val old=requireNotNull(db.dao().find(id))
            db.dao().update(old.copy(text=text.trim(),imagesJson=LocalAttachment.encode(images),revision=old.revision+1,syncError=null))
        }
    }
}
