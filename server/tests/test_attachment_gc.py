import importlib
import time
from test_attachments import register
from idea_echo.db import connect


def test_gc_keeps_referenced_pending_images(setup_api):
    c,a,_,settings=setup_api
    aid,_=register(c,a)
    module=importlib.import_module("idea_echo.attachments")
    assert module.collect_unreferenced(settings,time.time()+1)==0
    with connect(settings) as con:
        con.execute("DELETE FROM attachment_refs WHERE attachment_id=?",(aid,))
    assert module.collect_unreferenced(settings,time.time()+1)==1
