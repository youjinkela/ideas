package com.ideaecho.app.sync

import java.io.IOException
import java.net.ConnectException
import java.net.SocketException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException

object SyncFeedback {
    fun error(error: Throwable): String = when(error) {
        is LoginRequired -> "登录已过期，请到设置重新登录；本机记录仍然保留"
        is VersionConflict -> "版本冲突，请在已记录中处理；两份内容均已保留"
        is UnknownHostException -> "无法解析服务器地址，请检查地址和网络；记录已存本机"
        is SocketTimeoutException -> "连接超时，稍后可重试；记录已存本机"
        is ConnectException -> "无法连接服务器，请检查地址和网络；记录已存本机"
        is SocketException -> "连接被中断，请检查服务器和网络；记录已存本机"
        is SSLException -> "HTTPS 连接未建立，请检查服务器证书或网络；记录已存本机"
        is HttpStatusFailure -> "服务器返回 ${error.code}，请检查账号或服务端访问限制；记录已存本机"
        is IOException -> "网络请求未完成，请检查服务器和网络；记录已存本机"
        else -> "操作未完成，请检查设置和手机存储；本机记录仍然保留"
    }

    fun summary(pending: Int,online: Boolean,running: Boolean,queued: Boolean,error: String,loginRequired: Boolean): String = when {
        loginRequired -> "需要重新登录 · $error"
        running -> "正在上传 · $pending 条待确认"
        pending==0 -> if(error.isNotBlank())"上次同步未完成 · $error" else "没有待上传的记录"
        !online -> "等待联网 · $pending 条已存本机" + if(error.isNotBlank())"\n上次失败：$error" else ""
        error.isNotBlank() -> (if(queued)"等待重试" else "同步未完成")+" · $error"
        queued -> "等待系统执行 · $pending 条已存本机"
        else -> "有 $pending 条待上传，可点击立即重试"
    }
}
