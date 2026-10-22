"""Headless browser fixture. Never points at user notes or credentials."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/"desktop"),str(Path(__file__).resolve().parents[1]/"server")]
import tempfile
import hashlib
from PIL import Image
import uvicorn
from idea_echo_desktop.app import create_desktop_app

with tempfile.TemporaryDirectory(prefix="idea-echo-browser-") as directory:
    root=Path(directory)
    vault=root/"test-vault";vault.mkdir();(vault/"学习").mkdir()
    (vault/"已有笔记.md").write_text("# 已有笔记\n用户原文\n",encoding="utf-8")
    app=create_desktop_app(root/"desktop","http://127.0.0.1:47831","e2e-bootstrap")
    app.state.settings.update(vault=str(vault))
    aid="33333333-3333-4333-8333-333333333333"
    images=app.state.cache.root/"attachments";images.mkdir()
    Image.new("RGB",(40,30),"#78926c").save(images/aid,format="PNG")
    data=(images/aid).read_bytes()
    events=[]
    for index,text in enumerate(("早晨的图文点子<script>window.__injected=1</script>","昨晚没有回顾的点子")):
        id=f"11111111-1111-4111-8111-{index+1:012d}"
        attachments=[{"id":aid,"order":0,"mime_type":"image/png","size_bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"content_ready":True}] if index==0 else [{"id":"44444444-4444-4444-8444-444444444444","order":0,"mime_type":"image/png","size_bytes":10,"sha256":"a"*64,"content_ready":False}]
        events.append({"seq":index+1,"kind":"record","entity_id":id,"payload":{"id":id,"text":text,"recorded_at":"2026-10-21T09:00:00+08:00","attachments":attachments,"raw_version":1}})
    app.state.cache.apply_events(events)
    uvicorn.run(app,host="127.0.0.1",port=47831,access_log=False,log_level="warning")
