package com.ideaecho.app

import androidx.room.Room
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.ideaecho.app.data.*
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class CapturePersistenceTest {
    @Test fun doubleSaveWithSameIdCreatesOneIdeaAndSurvivesReopen() = runBlocking<Unit> {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "test-${UUID.randomUUID()}.db"
        val id = UUID.randomUUID().toString()
        var db = Room.databaseBuilder(context, AppDatabase::class.java, name).build()
        val repository = CaptureRepository(db)
        repository.saveCapture("离线想法", emptyList(), id)
        repository.saveCapture("离线想法", emptyList(), id)
        db.close()
        db = Room.databaseBuilder(context, AppDatabase::class.java, name).build()
        assertEquals(1, db.dao().all().size)
        assertEquals("离线想法", db.dao().all().single().text)
        db.close()
        context.deleteDatabase(name)
    }
}
