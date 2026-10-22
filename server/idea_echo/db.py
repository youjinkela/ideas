from contextlib import contextmanager
from pathlib import Path
import sqlite3
from .settings import Settings


@contextmanager
def connect(settings: Settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    con = sqlite3.connect(settings.data_dir / "ideas.db", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    if con.execute("PRAGMA user_version").fetchone()[0] == 0:
        con.executescript((Path(__file__).parent / "migrations/001_initial.sql").read_text("utf-8"))
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()

