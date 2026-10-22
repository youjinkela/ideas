"""Ephemeral USB-forwarded test service; never uses the user's cloud data."""
from pathlib import Path
import tempfile
import uvicorn
from idea_echo.app import create_app
from idea_echo.auth import create_user
from idea_echo.settings import Settings

if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="idea-echo-phone-") as root:
        settings=Settings(data_dir=Path(root))
        create_user(settings,"device-test","device-test-only-password")
        uvicorn.run(create_app(settings),host="127.0.0.1",port=47841,access_log=False)
