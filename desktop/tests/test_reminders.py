from datetime import datetime,date
import importlib
import pytest


@pytest.mark.parametrize("now,last,pending,want",[
    ("2026-10-22T18:59:00+08:00",None,2,False),
    ("2026-10-22T19:00:00+08:00",None,1,True),
    ("2026-10-22T20:00:00+08:00",None,2,True),
    ("2026-10-22T20:00:00+08:00","2026-10-22",2,False),
    ("2026-10-23T19:00:00+08:00","2026-10-22",1,True),
    ("2026-10-22T19:00:00+08:00",None,0,False),
    ("2026-10-22T11:00:00+00:00",None,1,True),
])
def test_daily_and_catchup_reminders(now,last,pending,want):
    try:module=importlib.import_module("idea_echo_desktop.reminders")
    except ImportError:pytest.fail("Daily reminders are not implemented")
    assert module.reminder_due(datetime.fromisoformat(now),date.fromisoformat(last) if last else None,pending) is want


def test_two_instances_claim_one_daily_notification(tmp_path):
    from idea_echo_desktop.cache import Cache
    module=importlib.import_module("idea_echo_desktop.reminders")
    assert hasattr(module,"claim_reminder")
    now=datetime.fromisoformat("2026-10-22T19:01:00+08:00")
    assert module.claim_reminder(Cache(tmp_path),now,1)
    assert not module.claim_reminder(Cache(tmp_path),now,1)
