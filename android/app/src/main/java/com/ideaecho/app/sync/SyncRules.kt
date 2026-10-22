package com.ideaecho.app.sync
object SyncRules {
    fun canMarkSynced(currentRevision: Long,sentRevision: Long,imagesReady: Boolean): Boolean = currentRevision == sentRevision && imagesReady
    fun belongsTo(owner: String?,currentAccount: String): Boolean = owner != null && owner == currentAccount
}
