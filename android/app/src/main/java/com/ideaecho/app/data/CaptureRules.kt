package com.ideaecho.app.data

object CaptureRules {
    fun canSave(text: String, imageCount: Int): Boolean = text.isNotBlank() || imageCount > 0
    fun title(text: String, fallbackTime: String): String = text.lineSequence().firstOrNull { it.isNotBlank() }?.trim()?.take(60) ?: "图片点子 $fallbackTime"
}
