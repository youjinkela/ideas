package com.ideaecho.app

import android.content.Context
import android.graphics.Color
import android.widget.ImageView
import android.widget.LinearLayout

/** Actual image surface shared by every saved-history attachment. */
class HistoryThumbnail(context: Context) : ImageView(context) {
    init {
        val size=(96*resources.displayMetrics.density).toInt()
        val gap=(6*resources.displayMetrics.density).toInt()
        layoutParams=LinearLayout.LayoutParams(size,size).apply { setMargins(0,gap,gap,gap) }
        scaleType=ScaleType.CENTER_CROP
        setBackgroundColor(Color.rgb(224,233,214))
        isClickable=true
        isFocusable=true
        contentDescription="点子图片，点击放大"
    }
}
