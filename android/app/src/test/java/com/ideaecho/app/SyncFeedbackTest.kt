package com.ideaecho.app

import com.ideaecho.app.sync.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.net.SocketException
import java.net.UnknownHostException

class SyncFeedbackTest {
    @Test fun networkErrorsAreActionableAndNeverExposeRawDetails() {
        val reset=SyncFeedback.error(SocketException("Connection reset: secret-token private-text"))
        assertTrue(reset.contains("连接被中断"))
        assertTrue(reset.contains("本机"))
        assertFalse(reset.contains("secret-token"))
        assertTrue(SyncFeedback.error(UnknownHostException("private-host")).contains("服务器地址"))
        assertFalse(SyncFeedback.error(IOException("private-text")).contains("private-text"))
    }
    @Test fun queuedAndOfflineWorkNeverLooksSuccessfullyUploaded() {
        assertTrue(SyncFeedback.summary(2,false,false,true,"",false).contains("等待联网"))
        assertTrue(SyncFeedback.summary(2,true,false,true,"",false).contains("等待系统执行"))
        assertTrue(SyncFeedback.summary(2,true,true,true,"",false).contains("正在上传"))
        assertFalse(SyncFeedback.summary(2,true,false,false,"连接被中断",false).contains("全部已同步"))
        assertTrue(SyncFeedback.summary(2,true,false,false,"",true).contains("重新登录"))
    }
}
