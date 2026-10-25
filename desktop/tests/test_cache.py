import importlib
import pytest


def cache_at(path):
    try:
        module=importlib.import_module("idea_echo_desktop.cache")
    except ImportError:
        pytest.fail("Desktop cache is not implemented")
    return module.Cache(path)


def raw_event(seq=1):
    return {"seq":seq,"kind":"record","entity_id":"11111111-1111-4111-8111-111111111111","payload":{"id":"11111111-1111-4111-8111-111111111111","text":"手机点子<script>bad()</script>","recorded_at":"2000-01-01T00:00:00Z","attachments":[],"raw_version":1}}


def test_offline_reflection_survives_restart_and_old_remote_event(tmp_path):
    cache=cache_at(tmp_path)
    cache.apply_events([raw_event()])
    cache.save_reflection(raw_event()["entity_id"],"我的补充",0)
    reopened=cache_at(tmp_path)
    assert reopened.list_ideas()[0]["reflection"]=="我的补充"
    assert reopened.pending()[0]["kind"]=="review"
    reopened.apply_events([{"seq":2,"kind":"review","entity_id":raw_event()["entity_id"],"payload":{"id":raw_event()["entity_id"],"reflection":"旧云端副本","review_version":1}}])
    assert reopened.list_ideas()[0]["reflection"]=="我的补充"


def test_old_ack_never_discards_newer_edit(tmp_path):
    cache=cache_at(tmp_path)
    id=raw_event()["entity_id"]
    cache.apply_events([raw_event()])
    cache.save_reflection(id,"第一版",0)
    old=cache.pending()[0]
    cache.save_reflection(id,"第二版",0)
    cache.acknowledge(old,{"accepted_version":1})
    assert cache.pending()[0]["payload"]["reflection"]=="第二版"
    assert cache.pending()[0]["expected_version"]==1


def test_change_cursor_is_server_sequence_not_recording_date(tmp_path):
    cache=cache_at(tmp_path)
    cache.apply_events([raw_event(10)])
    assert cache.cursor()==10
    assert len(cache.list_ideas("pending"))==1
    cache.set_status(raw_event()["entity_id"],"reviewed")
    assert cache.list_ideas("pending")==[]
    assert len(cache.list_ideas("all"))==1


def test_local_delete_survives_restart_and_cloud_replay_without_losing_other_ideas(tmp_path):
    cache=cache_at(tmp_path)
    event=raw_event();id=event["entity_id"]
    other=raw_event(2);other["entity_id"]="22222222-2222-4222-8222-222222222222"
    other["payload"]=dict(other["payload"],id=other["entity_id"])
    cache.apply_events([event,other])
    cache.save_reflection(id,"准备舍弃的补充",0)
    cache.delete_idea(id)
    reopened=cache_at(tmp_path)
    reopened.delete_idea(id)
    reopened.apply_events([raw_event(3),{"seq":4,"kind":"review","entity_id":id,"payload":{"reflection":"云端补充","review_version":1}}])
    assert [idea["id"] for idea in reopened.list_ideas("all")]==[other["entity_id"]]
    assert [operation['kind'] for operation in reopened.pending()]==['delete']
    assert reopened.cursor()==4
    with pytest.raises(KeyError):reopened.get(id)
    with pytest.raises(KeyError):reopened.delete_idea("33333333-3333-4333-8333-333333333333")
