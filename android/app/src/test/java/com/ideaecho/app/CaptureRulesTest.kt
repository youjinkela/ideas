package com.ideaecho.app

import org.junit.Assert.*
import org.junit.Test
import com.ideaecho.app.data.CaptureRules

class CaptureRulesTest {
    @Test fun rejectsOnlyFullyEmptyCapture() {
        assertFalse(CaptureRules.canSave("  \n ", 0))
        assertTrue(CaptureRules.canSave("", 1))
        assertTrue(CaptureRules.canSave("一句点子", 0))
    }
    @Test fun titleDoesNotTruncateBodyOrLoseEmoji() {
        assertEquals("第一行💡", CaptureRules.title("\n第一行💡\n第二行", "fallback"))
        assertEquals("图片点子 10:30", CaptureRules.title("", "10:30"))
    }
}
