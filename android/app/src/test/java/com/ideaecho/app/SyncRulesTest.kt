package com.ideaecho.app
import com.ideaecho.app.sync.SyncRules
import org.junit.Assert.*
import org.junit.Test

class SyncRulesTest {
    @Test fun oldAckCannotClearNewRevisionOrPartialImages() {
        assertFalse(SyncRules.canMarkSynced(2,1,true))
        assertFalse(SyncRules.canMarkSynced(1,1,false))
        assertTrue(SyncRules.canMarkSynced(1,1,true))
    }
    @Test fun anonymousAndOtherAccountNeverUpload() {
        assertFalse(SyncRules.belongsTo(null,"alice"))
        assertFalse(SyncRules.belongsTo("bob","alice"))
        assertTrue(SyncRules.belongsTo("alice","alice"))
    }
}
