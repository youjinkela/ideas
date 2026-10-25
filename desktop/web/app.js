'use strict';
const $=id=>document.getElementById(id);
let csrf='',ideas=[],current=null,preview=null,saveTimer,noticeTimer,saveTail=Promise.resolve();
const drafts=new Map();
let captureId=null,captureScope=null,captureBusy=false,capturePhotos=[],captureLimits={max_images:20,max_image_bytes:20*1024*1024,max_total_bytes:200*1024*1024};
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},...(body===undefined?{}:{body:JSON.stringify(body)})});
  return responseData(response);
}
async function responseData(response){
  let data;
  try{data=await response.json();}
  catch{const error=new Error('服务返回异常响应（HTTP '+response.status+'），请稍后重试；不要关闭未保存的编辑页面');error.httpStatus=response.status;throw error;}
  if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:data.detail?.message||'操作没有完成，请检查设置后重试');error.httpStatus=response.status;error.captureExists=data.detail?.capture_exists;if(response.status===410)error.deletedId=data.detail?.deleted_id;throw error;}
  return data;
}
function notice(text){$('notice').textContent=text;$('notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').hidden=true,5000);}
function guarded(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(e=>notice(e.message));}
function title(idea){return idea.text.split('\n').find(s=>s.trim())?.trim().slice(0,60)||'图片点子';}
function queueDraft(){if(!current)return;const old=drafts.get(current.id);drafts.set(current.id,{text:$('reflection').value,version:old?.version??current.review_version??0,revision:old?.revision??current.edit_revision??0});current.reflection=$('reflection').value;$('saveStatus').textContent='正在保存到本机…';clearTimeout(saveTimer);saveTimer=setTimeout(()=>flush().catch(e=>notice(e.message)),500);}
function flush(){
  clearTimeout(saveTimer);
  saveTail=saveTail.catch(()=>{}).then(async()=>{
    for(const [id,draft] of [...drafts]){
      try{const saved=await api('/local/reflection',{id,reflection:draft.text,expected_version:draft.version,expected_edit_revision:draft.revision});if(drafts.get(id)===draft)drafts.delete(id);else if(drafts.has(id)){drafts.get(id).version=saved.review_version;drafts.get(id).revision=saved.edit_revision;}if(current?.id===id){current.review_version=saved.review_version;current.edit_revision=saved.edit_revision;}}
      catch(error){
        if(error.deletedId===id){
          drafts.delete(id);
          if(current?.id===id){current=null;$('saveStatus').textContent='该点子已删除；未保存文字仅留在此页面，请先复制再切换';notice('点子已在其他设备删除，当前未保存文字可先复制保留');}
          continue;
        }
        $('saveStatus').textContent='尚未保存成功，请保留此页面后重试';throw error;
      }
    }
    if(current)$('saveStatus').textContent='已保存到本机';
  });
  return saveTail;
}
window.addEventListener('beforeunload',e=>{if(drafts.size||captureDirty()){e.preventDefault();e.returnValue='';}});
function renderList(){
  $('count').textContent=ideas.filter(x=>['pending','later'].includes(x.status||'pending')).length+' 个待回顾';
  $('ideaList').replaceChildren(...ideas.map(idea=>{
    const b=document.createElement('button');b.className='idea'+(current?.id===idea.id?' active':'');
    const strong=document.createElement('strong');strong.textContent=title(idea);
    const small=document.createElement('small');small.className='idea-meta';
    const date=document.createElement('span');date.textContent=new Date(idea.recorded_at).toLocaleString('zh-CN');
    const status=idea.status||'pending';
    const badge=document.createElement('span');badge.className='review-status status-'+status;
    badge.textContent=({pending:'未回顾',later:'留待下次',reviewed:'已回顾',archived:'已归档'}[status])||'未回顾';
    small.append(date,badge);
    b.append(strong,small);b.onclick=guarded(()=>select(idea.id));return b;
  }));
  if(!ideas.length){const p=document.createElement('p');p.textContent='暂无记录，或当前点子已回顾。';$('ideaList').append(p);}
}
async function load(){
  const result=await api('/local/ideas?view='+$('view').value);ideas=result.ideas;
  for(const idea of ideas)if(drafts.has(idea.id))idea.reflection=drafts.get(idea.id).text;
  if(current){const found=ideas.find(x=>x.id===current.id);if(found&&!drafts.has(current.id))current=found;else if(!found)current=null;}
  $('appStatus').textContent=result.sync_error?'本机编辑可用 · 同步待重试':'已连接本机 · '+result.pending_uploads+' 项待同步';
  renderList();
  if(!current&&ideas.length)await select(ideas[0].id);
  else if(current&&!drafts.has(current.id))await select(current.id);
  else if(!current){$('workspace').hidden=true;$('empty').hidden=false;}
}
async function select(id){
  await flush();current=ideas.find(x=>x.id===id);if(!current)return;
  $('workspace').hidden=false;$('empty').hidden=true;
  $('recordedAt').textContent=new Date(current.recorded_at).toLocaleString('zh-CN');$('ideaTitle').textContent=title(current);$('raw').textContent=current.text;
  $('reflection').value=drafts.has(id)?drafts.get(id).text:current.reflection||'';
  $('saveStatus').textContent='编辑自动保存到本机';$('ideaImages').replaceChildren();
  for(const image of current.attachments||[]){
    if(image.local_ready){const img=document.createElement('img');img.src='/local/images/'+encodeURIComponent(image.id);img.alt='点子图片 '+(image.order+1);img.onclick=()=>{$('largeImage').src=img.src;$('imageDialog').showModal();};$('ideaImages').append(img);}
    else{const p=document.createElement('div');p.className='pendingImage';p.textContent='图片待上传 / 待同步';$('ideaImages').append(p);}
  }
  $('conflicts').replaceChildren();
  for(const [kind,detail] of Object.entries(current.conflicts||{})){
    const box=document.createElement('div');box.className='conflict';const text=document.createElement('p');text.textContent='这项内容有两个版本，云端版本：'+JSON.stringify(detail.current||detail);box.append(text);
    for(const [label,keep] of [['保留我的版本',true],['采用云端版本',false]]){const b=document.createElement('button');b.textContent=label;b.onclick=guarded(async()=>{await api('/local/conflict',{id,kind,keep_local:keep});await load();await select(id);});box.append(b);}
    $('conflicts').append(box);
  }
  renderList();
}
$('reflection').addEventListener('input',queueDraft);
$('view').onchange=guarded(async()=>{await flush();current=null;await load();});
$('sync').onclick=guarded(async()=>{await flush();$('sync').disabled=true;try{const result=await api('/local/sync',{});notice(result.setup_required?'先在设置里连接服务器':result.error||'同步完成');await load();}finally{$('sync').disabled=false;}});
async function setStatus(value){if(!current)return;await flush();await api('/local/status',{id:current.id,value});await load();}
$('later').onclick=guarded(()=>setStatus('later'));$('reviewed').onclick=guarded(()=>setStatus('reviewed'));
$('discard').onclick=guarded(async()=>{
  if(!current||!confirm('删除这条点子及其图片？电脑立即删除，云端和手机在联网同步后删除；已导出的 Obsidian 笔记保留。'))return;
  const id=current.id;const button=$('discard');button.disabled=true;$('reflection').disabled=true;
  try{await flush();await api('/local/delete',{id});drafts.delete(id);current=null;await load();notice('已删除，其他设备将在联网同步后删除');}
  finally{button.disabled=false;$('reflection').disabled=false;}
});
async function settings(){const s=await api('/local/settings');$('cloudUrl').value=s.cloud_url||'';$('vaultPath').textContent=s.vault||'尚未选择';$('settingsDialog').showModal();}
$('settingsOpen').onclick=$('emptySettings').onclick=guarded(settings);
$('chooseVault').onclick=guarded(async()=>{const s=await api('/local/vault/select',{});$('vaultPath').textContent=s.vault||'尚未选择';});
$('saveSettings').onclick=guarded(async()=>{
  const button=$('saveSettings');button.disabled=true;
  try{await flush();await api('/local/settings',{cloud_url:$('cloudUrl').value.trim(),username:$('cloudUser').value.trim(),password:$('cloudPassword').value});$('cloudPassword').value='';$('settingsDialog').close();current=null;await load();notice('连接设置已保存');}finally{button.disabled=false;}
});
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
function captureDirty(){return !!$('captureText').value.trim()||capturePhotos.length>0;}
function captureMatches(idea,text,attachments){
  const manifest=images=>images.map(image=>({id:image.id,order:image.order,mime_type:image.mime_type,size_bytes:image.size_bytes,sha256:image.sha256})).sort((a,b)=>a.order-b.order);
  return idea.text===text.trim()&&JSON.stringify(manifest(idea.attachments||[]))===JSON.stringify(manifest(attachments));
}
function renderCapturePhotos(){
  $('captureImages').replaceChildren(...capturePhotos.map((photo,index)=>{
    const item=document.createElement('div');item.className='capture-photo';
    const image=document.createElement('img');image.src=photo.url;image.alt='点子配图 '+(index+1);
    const remove=document.createElement('button');remove.type='button';remove.textContent='移除';remove.setAttribute('aria-label','移除图片 '+(index+1));
    remove.onclick=()=>{if(captureBusy)return;URL.revokeObjectURL(photo.url);capturePhotos=capturePhotos.filter(p=>p!==photo);renderCapturePhotos();};
    item.append(image,remove);return item;
  }));
}
function resetCapture(){capturePhotos.forEach(photo=>URL.revokeObjectURL(photo.url));capturePhotos=[];captureId=null;captureScope=null;$('captureText').value='';$('captureFiles').value='';$('captureNewCopy').hidden=true;renderCapturePhotos();}
$('addIdea').onclick=guarded(async()=>{
  await flush();const config=await api('/local/capture/config');
  if(!config.ready){notice('首次使用请先登录账号，之后断网也能记录');await settings();return;}
  if(captureScope&&captureScope!==config.scope&&captureDirty()){
    if(!confirm('连接账号已变化，是否将当前草稿添加到现在的账号？'))return;
    captureId=null;capturePhotos.forEach(photo=>photo.id=crypto.randomUUID());
  }
  captureScope=config.scope;captureLimits=config;captureId=captureId||crypto.randomUUID();
  $('captureFeedback').textContent='先保存到电脑，联网后上传云端。';$('captureDialog').showModal();$('captureText').focus();
});
$('captureAddImage').onclick=()=>$('captureFiles').click();
$('captureFiles').onchange=()=>{
  for(const file of $('captureFiles').files){
    if(capturePhotos.length>=captureLimits.max_images){notice('每条最多20张图片');break;}
    if(file.type&&!['image/jpeg','image/png','image/webp'].includes(file.type)){notice('仅支持JPEG、PNG和WebP图片');continue;}
    if(file.size>captureLimits.max_image_bytes){notice('单张图片不能超过20MiB');continue;}
    if(capturePhotos.reduce((sum,p)=>sum+p.file.size,0)+file.size>captureLimits.max_total_bytes){notice('图片合计不能超过200MiB');continue;}
    capturePhotos.push({id:crypto.randomUUID(),file,url:URL.createObjectURL(file)});
  }
  $('captureFiles').value='';renderCapturePhotos();
};
$('captureDialog').addEventListener('cancel',event=>{if(captureBusy)event.preventDefault();});
document.querySelectorAll('[data-close="captureDialog"]').forEach(button=>button.onclick=()=>{if(!captureBusy)$('captureDialog').close();});
$('captureNewCopy').onclick=()=>{captureId=crypto.randomUUID();$('captureNewCopy').hidden=true;$('captureFeedback').textContent='将按一条新点子保存，之前的记录会保留。';};
$('saveCapture').onclick=guarded(async()=>{
  if(captureBusy)return;
  const text=$('captureText').value;
  if(!text.trim()&&!capturePhotos.length){$('captureFeedback').textContent='请写一点内容或添加图片。';$('captureText').focus();return;}
  captureBusy=true;$('captureFields').disabled=true;$('saveCapture').disabled=true;$('captureNewCopy').disabled=true;
  document.querySelectorAll('[data-close="captureDialog"]').forEach(button=>button.disabled=true);
  let saved;
  try{
    const attachments=[];
    for(const [index,photo] of capturePhotos.entries()){
      $('captureFeedback').textContent='正在保存图片 '+(index+1)+' / '+capturePhotos.length+'…';
      const response=await fetch('/local/capture/'+captureId+'/images/'+photo.id,{method:'PUT',headers:{'X-CSRF-Token':csrf,'X-Capture-Scope':captureScope},body:photo.file});
      attachments.push({...await responseData(response),order:index});
    }
    $('captureFeedback').textContent='正在保存点子…';
    try{saved=await api('/local/ideas',{id:captureId,scope:captureScope,text,attachments});}
    catch(error){
      if(error.httpStatus===undefined||error.httpStatus>=500||error.httpStatus===200){
        try{
          const receipt=await responseData(await fetch('/local/capture/'+captureId+'/receipt',{headers:{'X-Capture-Scope':captureScope}}));
          if(captureMatches(receipt.idea,text,attachments))saved=receipt;
          else{error.captureExists=true;error.httpStatus=409;error.message='之前的内容已保存，当前修改仍保留，请另存为新点子。';}
        }catch{}
      }
      if(!saved)throw error;
    }
  }catch(error){
    $('captureFeedback').textContent=(error.httpStatus?error.message:'保存结果尚未确认，内容仍保留，请重试。');
    if(error.captureExists||error.httpStatus===410)$('captureNewCopy').hidden=false;
    return;
  }finally{
    captureBusy=false;$('captureFields').disabled=false;$('saveCapture').disabled=false;$('captureNewCopy').disabled=false;
    document.querySelectorAll('[data-close="captureDialog"]').forEach(button=>button.disabled=false);
  }
  const id=saved.idea.id;$('captureDialog').close();resetCapture();$('view').value=['pending','later'].includes(saved.idea.status||'pending')?'pending':'all';current=null;
  try{await load();await select(id);notice('已保存到电脑，联网后会同步到云端');}
  catch{notice('点子已保存，列表暂未刷新，请刷新页面查看');}
});
$('imageDialog').addEventListener('click',event=>{
  if(event.target===event.currentTarget)event.currentTarget.close();
});
function invalidatePreview(){preview=null;$('commitArchive').disabled=true;$('archivePreview').textContent='';$('archiveDestination').textContent='';}
async function searchNotes(){const result=await api('/local/vault/notes?q='+encodeURIComponent($('noteSearch').value));$('targetNote').replaceChildren(...result.notes.map(path=>new Option(path,path)));invalidatePreview();}
let searchTimer;
$('noteSearch').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>searchNotes().catch(e=>notice(e.message)),150);};
$('archiveMode').onchange=guarded(async()=>{const append=$('archiveMode').value==='append';$('appendFields').hidden=!append;$('newFields').hidden=append;invalidatePreview();if(append)await searchNotes();});
for(const id of ['folder','noteTitle','targetNote'])$(id).addEventListener('input',invalidatePreview);
$('archive').onclick=guarded(async()=>{
  if(!current)return;await flush();
  const result=await api('/local/vault/folders');$('folder').replaceChildren(...result.folders.map(path=>new Option(path||'笔记库根目录',path)));
  $('archiveMode').value='new';$('newFields').hidden=false;$('appendFields').hidden=true;$('noteTitle').value=title(current);$('noteSearch').value='';invalidatePreview();$('archiveDialog').showModal();
});
$('previewArchive').onclick=guarded(async()=>{
  if(!current)return;await flush();
  preview=await api('/local/archive/preview',{id:current.id,mode:$('archiveMode').value,folder:$('folder').value,title:$('noteTitle').value,target:$('targetNote').value});
  if(preview.resumed)notice('已恢复此前未确认的归档操作；将沿用原目标和正文，避免重复写入');
  $('archivePreview').textContent=preview.content;$('archiveDestination').textContent='保存到：'+preview.path+(preview.attachments.length?' · '+preview.attachments.length+' 张本地附件':'');$('commitArchive').disabled=false;
});
$('commitArchive').onclick=guarded(async()=>{
  if(!preview)return;$('commitArchive').disabled=true;
  try{const result=await api('/local/archive/commit',{operation_id:preview.operation_id});await api('/local/archive/ack',{operation_id:preview.operation_id});$('archiveDialog').close();notice('已保存到 '+result.path);preview=null;await load();}catch(e){$('commitArchive').disabled=false;throw e;}
});
(async()=>{
  try{const bootstrap=location.hash.slice(1);history.replaceState(null,'',location.pathname);const session=await api('/local/session',bootstrap?{bootstrap}:undefined);csrf=session.csrf;await load();}
  catch(e){$('appStatus').textContent='请从本机启动程序打开';notice(e.message);}
})();
