package com.ideaecho.app

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.SystemClock
import android.view.InputDevice
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.viewpager2.widget.ViewPager2
import com.ideaecho.app.data.AccountStore
import com.ideaecho.app.data.AppDatabase
import com.ideaecho.app.data.DraftEntity
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/** Synthetic fixtures only; never launch or access the daily application's database. */
@RunWith(AndroidJUnit4::class)
class SwipePagesTest {
    private val instrumentation get()=InstrumentationRegistry.getInstrumentation()

    @Test fun swipesPreserveCaptureDraftAndSettingsFields() {
        assumeTrue("Only the disposable acceptance app may run this test",BuildConfig.APPLICATION_ID.endsWith(".acceptance"))
        val context=instrumentation.targetContext
        assumeTrue(context.packageName==BuildConfig.APPLICATION_ID && context.packageName.endsWith(".acceptance"))
        assumeTrue("Acceptance UI fixture must be logged out",AccountStore(context).accountId==null)
        val db=AppDatabase.get(context)
        db.clearAllTables()
        val text="synthetic swipe draft ${UUID.randomUUID()}"
        runBlocking { db.dao().setDraft(DraftEntity(text="synthetic seeded draft",imagesJson="[]",saveId=UUID.randomUUID().toString())) }
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val view=activity.findViewById<View>(R.id.idea_pager)
                assertNotNull("MainActivity must expose idea_pager for real horizontal swipes",view)
                assertTrue("idea_pager must be a ViewPager2",view is ViewPager2)
                assertEquals("Capture must be the default left page",0,(view as ViewPager2).currentItem)
            }
            awaitUi(scenario,"Capture draft must load") {
                it.findViewById<EditText>(R.id.capture_input)?.text?.toString()=="synthetic seeded draft"
            }
            scenario.onActivity { it.findViewById<EditText>(R.id.capture_input).setText(text) }
            await("Edited capture draft must reach disk") { runBlocking { db.dao().draft()?.text==text } }
            swipe(scenario,left=true);assertPage(scenario,1)
            swipe(scenario,left=true);assertPage(scenario,2)
            scenario.onActivity { settingsField(it).setText("https://swipe-fixture.invalid") }
            swipe(scenario,left=false);assertPage(scenario,1)
            swipe(scenario,left=false);assertPage(scenario,0)
            scenario.onActivity { assertEquals(text,it.findViewById<EditText>(R.id.capture_input).text.toString()) }
            swipe(scenario,left=true);assertPage(scenario,1)
            swipe(scenario,left=true);assertPage(scenario,2)
            scenario.onActivity { assertEquals("https://swipe-fixture.invalid",settingsField(it).text.toString()) }
            swipe(scenario,left=false);assertPage(scenario,1)
            swipe(scenario,left=false);assertPage(scenario,0)
            assertEquals(text,runBlocking { db.dao().draft() }!!.text)
            assertTrue("Swiping must not save a record",runBlocking { db.dao().all().isEmpty() })
            scenario.onActivity { activity ->
                val editor=activity.findViewById<EditText>(R.id.capture_input)
                editor.requestFocus()
                activity.getSystemService(InputMethodManager::class.java).showSoftInput(editor,InputMethodManager.SHOW_IMPLICIT)
            }
            awaitUi(scenario,"Soft keyboard must open on the capture page") {
                ViewCompat.getRootWindowInsets(it.window.decorView)?.isVisible(WindowInsetsCompat.Type.ime())==true
            }
            var keyboardTop=0
            scenario.onActivity { activity ->
                val decor=activity.window.decorView
                val location=IntArray(2);decor.getLocationOnScreen(location)
                val ime=ViewCompat.getRootWindowInsets(decor)!!.getInsets(WindowInsetsCompat.Type.ime())
                keyboardTop=location[1]+decor.height-ime.bottom
                for(id in listOf(R.id.add_image,R.id.save_idea)) {
                    val action=activity.findViewById<View>(id)
                    val rect=Rect()
                    assertTrue("Capture action must be visible above the keyboard",action.getGlobalVisibleRect(rect))
                    assertEquals(action.height,rect.height())
                    assertTrue("Keyboard must not cover a capture action",rect.bottom<=keyboardTop)
                }
            }
            instrumentation.uiAutomation.takeScreenshot()?.let { screenshot ->
                val cropped=Bitmap.createBitmap(screenshot,0,0,screenshot.width,keyboardTop.coerceIn(1,screenshot.height))
                java.io.File(context.getExternalFilesDir(null),"swipe-pages-keyboard.png").outputStream().use { cropped.compress(Bitmap.CompressFormat.PNG,100,it) }
                if(cropped!==screenshot)cropped.recycle()
                screenshot.recycle()
            }
            val pickerFilter=IntentFilter(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE);addDataType("*/*") }
            val picker=instrumentation.addMonitor(pickerFilter,Instrumentation.ActivityResult(Activity.RESULT_CANCELED,null),true)
            try {
                scenario.onActivity { it.findViewById<View>(R.id.add_image).performClick() }
                await("Image action must open the document picker") { picker.hits>0 }
            } finally { instrumentation.removeMonitor(picker) }
            scenario.onActivity {
                assertEquals("Canceling the picker must retain the idea",text,it.findViewById<EditText>(R.id.capture_input).text.toString())
                val save=it.findViewById<View>(R.id.save_idea)
                save.performClick();save.performClick()
            }
            await("Repeated save must create one durable record") { runBlocking { db.dao().all().count { it.text==text }==1 } }
            awaitUi(scenario,"A saved idea must leave a fresh input") { it.findViewById<EditText>(R.id.capture_input).text.isEmpty() }
            assertEquals(1,runBlocking { db.dao().all().size })
            swipe(scenario,left=true);assertPage(scenario,1)
            scenario.recreate();assertPage(scenario,1)
            awaitUi(scenario,"Capture must reload after recreation") { it.findViewById<EditText>(R.id.capture_input)!=null }
            swipe(scenario,left=false);assertPage(scenario,0)
            scenario.onActivity { assertTrue(it.findViewById<EditText>(R.id.capture_input).text.isEmpty()) }
        }
    }

    private fun settingsField(activity: MainActivity): EditText = descendants(activity.window.decorView)
        .filterIsInstance<EditText>().first { it.hint?.toString()?.contains("服务器地址")==true }

    private fun descendants(view: View): List<View> = listOf(view)+(if(view is ViewGroup)
        (0 until view.childCount).flatMap { descendants(view.getChildAt(it)) } else emptyList())

    private fun assertPage(scenario: ActivityScenario<MainActivity>,index: Int)=awaitUi(scenario,"Real swipe must settle on page $index") {
        val pager=it.findViewById<ViewPager2>(R.id.idea_pager)
        pager.currentItem==index && pager.scrollState==ViewPager2.SCROLL_STATE_IDLE
    }

    private fun swipe(scenario: ActivityScenario<MainActivity>,left: Boolean) {
        val rect=Rect()
        scenario.onActivity { assertTrue(it.findViewById<View>(R.id.idea_pager).getGlobalVisibleRect(rect)) }
        val start=rect.left+rect.width()*(if(left)0.82f else 0.18f)
        val end=rect.left+rect.width()*(if(left)0.18f else 0.82f)
        val y=rect.top+rect.height()*0.50f
        val down=SystemClock.uptimeMillis()
        for(step in 0..18) {
            val action=when(step) { 0->MotionEvent.ACTION_DOWN;18->MotionEvent.ACTION_UP;else->MotionEvent.ACTION_MOVE }
            val event=MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,start+(end-start)*step/18f,y,0)
            event.source=InputDevice.SOURCE_TOUCHSCREEN
            try { assertTrue("Pointer event must reach the real UI",instrumentation.uiAutomation.injectInputEvent(event,true)) }
            finally { event.recycle() }
            if(step<18)SystemClock.sleep(12) // Physical gesture duration, not an async UI wait.
        }
    }

    private fun awaitUi(scenario: ActivityScenario<MainActivity>,message: String,condition: (MainActivity)->Boolean)=await(message) {
        var matched=false
        scenario.onActivity { matched=condition(it) }
        matched
    }

    private fun await(message: String,condition: ()->Boolean) {
        val deadline=SystemClock.uptimeMillis()+5000
        do { if(condition())return;SystemClock.sleep(40) } while(SystemClock.uptimeMillis()<deadline)
        assertTrue(message,condition())
    }
}
