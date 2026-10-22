from datetime import datetime,date
from zoneinfo import ZoneInfo

SHANGHAI=ZoneInfo("Asia/Shanghai")


def reminder_due(now: datetime,last_sent_day: date | None,pending_count: int) -> bool:
    if now.tzinfo is None:raise ValueError("提醒时间必须带时区")
    local=now.astimezone(SHANGHAI)
    return pending_count>0 and local.hour>=19 and last_sent_day!=local.date()


def send_reminder(review_url: str) -> bool:
    try:
        from winotify import Notification
        toast=Notification(app_id="点子回声",title="留几分钟，回顾今天的点子",msg="打开回顾页，挑一个值得继续想的点子。",launch=review_url)
        toast.show()
        return True
    except (ImportError,OSError,RuntimeError):
        return False
