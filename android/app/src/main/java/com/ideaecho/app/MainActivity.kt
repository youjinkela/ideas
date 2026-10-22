package com.ideaecho.app

import android.app.AlertDialog
import android.content.res.ColorStateList
import android.graphics.BitmapFactory
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.text.InputType
import android.view.View
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import com.ideaecho.app.data.*
import com.ideaecho.app.sync.*
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class MainActivity : ComponentActivity() {
    private val db by lazy { AppDatabase.get(this) }
    private val repository by lazy { CaptureRepository(db) }
    private val account by lazy { AccountStore(this) }
    private val sync by lazy { SyncRepository(this,db,account) }
    private lateinit var content: LinearLayout
    private lateinit var status: TextView
    private var input: EditText?=null
    private var imageStrip: LinearLayout?=null
    private var historyList: LinearLayout?=null
    private var screen="capture"
    private var text=""
    private var saveId=UUID.randomUUID().toString()
    private val images=mutableListOf<LocalAttachment>()
    private var rows=listOf<IdeaEntity>()
    private var ready=false
    private var saving=false
    private var draftJob: Job?=null
    private val draftScope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private val picker=registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        lifecycleScope.launch {
            for(uri in uris) {
                if(images.size>=20) { message("每条最多20张图片");break }
                try {
                    val image=withContext(Dispatchers.IO) { AttachmentStore(this@MainActivity).importImage(uri,images.size) }
                    images.add(image);persistDraft();renderImages()
                } catch(error: Exception) { message(error.message ?: "图片未保存，文字仍保留") }
            }
        }
    }
    private val exporter=registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        uri?.let { lifecycleScope.launch { try { withContext(Dispatchers.IO) { exportPending(it) };message("已导出未同步的图文") } catch(error: Exception) { message("导出未完成，请检查空间后重试") } } }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val outer=LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(245,246,239))
            setPadding(dp(20),dp(20),dp(20),dp(12))
            setOnApplyWindowInsetsListener { view,insets ->
                view.setPadding(dp(20),insets.systemWindowInsetTop+dp(12),dp(20),insets.systemWindowInsetBottom+dp(8));insets
            }
        }
        outer.addView(label("点子回声",24))
        status=label("正在读取本机记录…",12);outer.addView(status)
        val scroll=ScrollView(this)
        content=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }
        scroll.addView(content)
        outer.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        val nav=LinearLayout(this)
        listOf("随手记" to "capture","已记录" to "history","设置" to "settings").forEach { (name,value) ->
            nav.addView(button(name) { screen=value;render() },LinearLayout.LayoutParams(0,-2,1f))
        }
        outer.addView(nav);setContentView(outer)
        lifecycleScope.launch {
            val draft=withContext(Dispatchers.IO) { db.dao().draft() }
            if(draft!=null) { text=draft.text;saveId=draft.saveId;images.addAll(LocalAttachment.decode(draft.imagesJson)) }
            ready=true;render()
            db.dao().observeAll().collect { rows=it;refreshStatus();if(screen=="history")renderHistory() }
        }
    }
    override fun onResume() { super.onResume();account.accountId?.let { SyncWorker.enqueue(this,it) } }
    override fun onPause() { persistDraft();super.onPause() }

    private fun dp(value: Int)=(value*resources.displayMetrics.density).toInt()
    private fun label(value: String,size: Int=15)=TextView(this).apply { text=value;textSize=size.toFloat();setTextColor(Color.rgb(46,68,51));setPadding(0,dp(8),0,dp(8)) }
    private fun button(value: String,action: ()->Unit)=Button(this).apply { text=value;isAllCaps=false;backgroundTintList=ColorStateList.valueOf(Color.rgb(224,233,214));setTextColor(Color.rgb(43,72,46));setOnClickListener { action() } }
    private fun field(hintText: String,value: String="",password: Boolean=false)=EditText(this).apply { hint=hintText;setText(value);if(password)inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD }
    private fun message(value: String) { Toast.makeText(this,value,Toast.LENGTH_LONG).show() }
    private fun persistDraft() {
        if(!ready || saving)return
        val snapshot=text;val snapshotImages=images.toList();val id=saveId
        val previous=draftJob
        draftJob=draftScope.launch {
            previous?.join()
            try { repository.saveDraft(snapshot,snapshotImages,id) }
            catch(error: Exception) { withContext(Dispatchers.Main) { status.text="草稿尚未保存，请检查手机空间；不要关闭 App" } }
        }
    }
    private fun refreshStatus() {
        val pending=rows.count { it.revision>it.syncedRevision }
        val unowned=rows.count { it.owner==null }
        status.text=when {
            unowned>0 -> "$pending 条待同步 · $unowned 条尚未关联账号"
            pending>0 -> "$pending 条已存本机，等待同步"
            rows.isNotEmpty() -> "全部已同步 · 共 ${rows.size} 条"
            else -> "本机优先保存 · 断网也能记"
        }
    }
    private fun render() {
        if(!ready)return
        content.removeAllViews();input=null;imageStrip=null;historyList=null
        when(screen) { "capture"->renderCapture();"history"->renderHistory();else->renderSettings() }
    }
    private fun renderCapture() {
        content.addView(label("想到一句，就记一句。",22))
        content.addView(label("不用起标题，也不用先分类。",13))
        input=field("刚才想到……",text).apply {
            minLines=6;maxLines=16;gravity=android.view.Gravity.TOP
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            addTextChangedListener(object: TextWatcher {
                override fun beforeTextChanged(s: CharSequence?,start: Int,count: Int,after: Int) {}
                override fun onTextChanged(s: CharSequence?,start: Int,before: Int,count: Int) { this@MainActivity.text=s.toString();persistDraft() }
                override fun afterTextChanged(s: Editable?) {}
            })
        }
        content.addView(input)
        content.addView(button("＋ 添加照片或截图") { if(!saving)picker.launch(arrayOf("image/jpeg","image/png","image/webp")) })
        imageStrip=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL };content.addView(imageStrip);renderImages()
        content.addView(label("偶尔想说出来，可使用输入法的语音输入。",12))
        val save=button("保存点子") {}
        save.setOnClickListener {
            if(saving || !CaptureRules.canSave(text,images.size))return@setOnClickListener
            saving=true;save.isEnabled=false
            input?.isEnabled=false
            val snapshot=text;val selected=images.toList();val id=saveId
            val queuedDraft=draftJob
            lifecycleScope.launch {
                try {
                    queuedDraft?.join()
                    withContext(Dispatchers.IO) { repository.saveCapture(snapshot,selected,id,account.accountId) }
                    text="";images.clear();saveId=UUID.randomUUID().toString()
                    input?.setText("");renderImages();message("已存本机，可以继续记下一条")
                    account.accountId?.let { SyncWorker.enqueue(this@MainActivity,it) }
                } catch(error: Exception) { message(error.message ?: "保存未成功，内容仍然保留")
                } finally { saving=false;save.isEnabled=true;input?.isEnabled=true;persistDraft() }
            }
        }
        content.addView(save)
    }
    private fun renderImages() {
        imageStrip?.removeAllViews()
        images.forEachIndexed { index,image ->
            val row=LinearLayout(this)
            val thumbnail=ImageView(this).apply { scaleType=ImageView.ScaleType.CENTER_CROP;setOnClickListener { showImage(image.path) } }
            row.addView(thumbnail,LinearLayout.LayoutParams(dp(84),dp(84)))
            loadImage(thumbnail,image.path,256)
            row.addView(button("移除") { if(!saving) { images.removeAt(index);renumber();persistDraft();renderImages() } })
            if(index>0)row.addView(button("前移") { if(!saving) { val prior=images[index-1];images[index-1]=image;images[index]=prior;renumber();persistDraft();renderImages() } })
            imageStrip?.addView(row)
        }
    }
    private fun renumber() { images.indices.forEach { images[it]=images[it].copy(order=it) } }
    private fun loadImage(view: ImageView,path: String,size: Int) {
        lifecycleScope.launch {
            val bitmap=withContext(Dispatchers.IO) {
                val bounds=BitmapFactory.Options().apply { inJustDecodeBounds=true }
                BitmapFactory.decodeFile(path,bounds)
                var sample=1
                while(bounds.outWidth/sample>size || bounds.outHeight/sample>size)sample*=2
                BitmapFactory.decodeFile(path,BitmapFactory.Options().apply { inSampleSize=sample })
            }
            view.setImageBitmap(bitmap)
        }
    }
    private fun showImage(path: String) {
        val image=ImageView(this).apply { adjustViewBounds=true }
        loadImage(image,path,1600)
        AlertDialog.Builder(this).setView(image).setPositiveButton("关闭",null).show()
    }
    private fun renderHistory() {
        content.removeAllViews();content.addView(label("已记录",22))
        content.addView(button("立即重试同步") { account.accountId?.let { SyncWorker.enqueue(this,it);message("已安排同步") } ?: message("先到设置中连接服务器") })
        for(item in rows) {
            content.addView(label(CaptureRules.title(item.text,item.recordedAt),18))
            content.addView(label(item.text))
            val state=when {item.owner==null->"仅存本机，待关联账号";item.syncedRevision>=item.revision->"已同步";item.syncError.orEmpty().startsWith("conflict:")->"版本冲突，手机与云端内容都保留";else->item.syncError ?: "已存本机，待上传"}
            content.addView(label(state,12))
            val savedImages=LocalAttachment.decode(item.imagesJson).sortedBy { it.order }
            if(savedImages.isNotEmpty()) {
                val strip=LinearLayout(this)
                savedImages.forEach { image ->
                    val thumbnail=HistoryThumbnail(this).apply {
                        contentDescription="点子图片 ${image.order+1}，点击放大"
                        setOnClickListener { showImage(image.path) }
                    }
                    strip.addView(thumbnail)
                    loadImage(thumbnail,image.path,256)
                }
                content.addView(HorizontalScrollView(this).apply { addView(strip) })
            }
            content.addView(button("编辑原文") {
                val edit=field("原始点子",item.text).apply { minLines=4;inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE }
                AlertDialog.Builder(this).setTitle("修改后会重新同步").setView(edit).setNegativeButton("取消",null).setPositiveButton("保存") { _,_->
                    lifecycleScope.launch { try { repository.editCapture(item.id,edit.text.toString(),LocalAttachment.decode(item.imagesJson));account.accountId?.let { SyncWorker.enqueue(this@MainActivity,it) } } catch(error: Exception) { message(error.message ?: "保存未成功") } }
                }.show()
            })
            if(item.syncError.orEmpty().startsWith("conflict:"))content.addView(button("比较并处理冲突") {
                val remote=runCatching { JSONObject(item.syncError!!.removePrefix("conflict:")).getJSONObject("current").optString("text") }.getOrDefault("云端副本不可读取")
                val edit=field("编辑合并内容",item.text+"\n\n云端版本：\n"+remote).apply { minLines=5;inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE }
                AlertDialog.Builder(this).setTitle("你来决定保留什么").setView(edit).setNegativeButton("稍后",null).setPositiveButton("按此内容重新同步") { _,_->
                    lifecycleScope.launch { try { repository.editCapture(item.id,edit.text.toString(),LocalAttachment.decode(item.imagesJson));sync.keepLocalAfterConflict(item.id);account.accountId?.let { SyncWorker.enqueue(this@MainActivity,it) } } catch(error: Exception) { message(error.message ?: "处理未成功") } }
                }.show()
            })
            content.addView(View(this).apply { setBackgroundColor(Color.LTGRAY) },LinearLayout.LayoutParams(-1,dp(1)))
        }
        if(rows.isEmpty())content.addView(label("还没有点子，先记一句。"))
    }
    private fun renderSettings() {
        content.addView(label("连接你的私人收件箱",22))
        content.addView(label("不连接也可以离线记录。联网后登录，才会上传。",13))
        val server=field("服务器地址：https://…",account.server)
        val username=field("用户名")
        val password=field("密码",password=true)
        content.addView(server);content.addView(username);content.addView(password)
        val login=button("登录并连接") {}
        login.setOnClickListener {
            login.isEnabled=false
            lifecycleScope.launch {
                try {
                    val result=withContext(Dispatchers.IO) { IdeaApi(server.text.toString().trim()).request("POST","/v1/auth/login",JSONObject().put("username",username.text.toString()).put("password",password.text.toString())) }
                    account.save(server.text.toString().trim(),result.getString("account_id"),result.getString("token"));password.setText("")
                    val owner=account.accountId!!
                    val local=withContext(Dispatchers.IO) { db.dao().all().filter { it.owner==null }.map { it.id } }
                    if(local.isNotEmpty())AlertDialog.Builder(this@MainActivity).setTitle("上传此前的本机记录？").setMessage("将 ${local.size} 条未关联记录上传到这个账号。其他账号的记录不会上传。")
                        .setNegativeButton("暂不上传",null).setPositiveButton("确认上传") { _,_->lifecycleScope.launch { sync.claimLocalRecords(owner,local);SyncWorker.enqueue(this@MainActivity,owner) } }.show()
                    SyncWorker.enqueue(this@MainActivity,owner);message("已连接，登录密码不会保存在手机")
                } catch(error: Exception) { message(error.message ?: "连接失败，离线记录不受影响")
                } finally { login.isEnabled=true }
            }
        }
        content.addView(login)
        content.addView(button("退出登录（保留本机记录）") { account.logout();message("已退出，本机记录没有删除") })
        content.addView(button("导出未同步的图文") { exporter.launch("idea-echo-pending.zip") })
        content.addView(label("后台补传受系统调度影响。若长时间没有同步，请重新打开 App 或检查华为应用启动管理；不要清除应用数据。",13))
    }
    private suspend fun exportPending(uri: Uri) {
        val pending=db.dao().all().filter { it.syncedRevision<it.revision }
        val draft=db.dao().draft()
        val allImages=pending.flatMap { LocalAttachment.decode(it.imagesJson) }+(draft?.let { LocalAttachment.decode(it.imagesJson) } ?: emptyList())
        val records=JSONArray().apply { pending.forEach { item ->put(JSONObject().put("id",item.id).put("text",item.text).put("recorded_at",item.recordedAt).put("attachments",JSONArray().apply { LocalAttachment.decode(item.imagesJson).forEach { put(it.descriptor()) } })) } }
        contentResolver.openOutputStream(uri).use { stream ->
            requireNotNull(stream)
            ZipOutputStream(stream).use { zip ->
                zip.putNextEntry(ZipEntry("records.json"));zip.write(JSONObject().put("records",records).put("draft",draft?.let { JSONObject().put("text",it.text).put("attachments",JSONArray(it.imagesJson)) }).toString(2).toByteArray(Charsets.UTF_8));zip.closeEntry()
                allImages.distinctBy { it.id }.forEach { image ->zip.putNextEntry(ZipEntry("images/${image.id}"));File(image.path).inputStream().use { it.copyTo(zip) };zip.closeEntry() }
            }
        }
    }
}
