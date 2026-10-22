from test_archive import manager,idea


def test_reopen_operation_after_lost_ack_is_idempotent(tmp_path):
    m,v,_=manager(tmp_path)
    (v/"note.md").write_text("原文\r\n",encoding="utf-8",newline="")
    op=m.preview(idea(),"只出现一次",mode="append",target="note.md")
    receipt=m.commit(op["operation_id"])
    reopened,_,_=manager(tmp_path)
    assert reopened.commit(op["operation_id"])==receipt
    assert (v/"note.md").read_text("utf-8").count("只出现一次")==1
