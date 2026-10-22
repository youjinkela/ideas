package com.ideaecho.app

import android.graphics.Bitmap
import android.widget.ImageView
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HistoryThumbnailTest {
    @Test fun savedHistoryUsesVisibleClickableImageThumbnail() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val type=runCatching { Class.forName("com.ideaecho.app.HistoryThumbnail") }.getOrNull()
        assertNotNull("Saved images need a thumbnail component, not only a text button",type)
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            val view=type!!.getConstructor(android.content.Context::class.java).newInstance(context) as ImageView
            view.setImageBitmap(Bitmap.createBitmap(8,8,Bitmap.Config.ARGB_8888))
            assertNotNull(view.drawable)
            assertTrue(view.layoutParams.width>0 && view.layoutParams.height>0)
            assertEquals(ImageView.ScaleType.CENTER_CROP,view.scaleType)
            assertTrue(view.isClickable)
        }
    }
}
