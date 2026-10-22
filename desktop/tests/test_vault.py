import pytest
from test_archive import manager,idea


@pytest.mark.parametrize("folder",["../outside","/outside",".obsidian","正常/../../outside","C:\\Windows","normal/.git"])
def test_refuses_escape_and_hidden_directories(tmp_path,folder):
    m,_,_=manager(tmp_path)
    with pytest.raises(ValueError):m.preview(idea(),"",mode="new",folder=folder,title="test")


def test_lists_folders_and_searches_notes(tmp_path):
    m,v,_=manager(tmp_path)
    (v/"学习").mkdir();(v/".obsidian").mkdir()
    (v/"学习"/"点子.md").write_text("笔记",encoding="utf-8")
    assert "学习" in m.folders()
    assert ".obsidian" not in m.folders()
    assert m.search("点子")==["学习/点子.md"]

