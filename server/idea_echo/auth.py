import argparse
import getpass
import hashlib
import secrets
import time
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from .db import connect
from .settings import Settings

PASSWORDS = PasswordHasher()
DUMMY_HASH = PASSWORDS.hash(secrets.token_hex(24))


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


def create_user(settings: Settings, username: str, password: str) -> str:
    if not username.strip() or len(password) < 12:
        raise ValueError("用户名不能为空，密码至少12个字符")
    owner = str(uuid4())
    with connect(settings) as con:
        con.execute("INSERT INTO users VALUES(?,?,?)", (owner, username.strip(), PASSWORDS.hash(password)))
    return owner


def login(settings: Settings, body: Login, ip: str) -> dict:
    now = time.time()
    with connect(settings) as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM login_attempts WHERE at<?", (now-60,))
        failures = con.execute("SELECT count(*) FROM login_attempts WHERE ip=?", (ip,)).fetchone()[0]
        if failures >= 5:
            raise HTTPException(429, "登录尝试过多，请稍后重试")
        user = con.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
        try:
            ok = PASSWORDS.verify(user["password_hash"] if user else DUMMY_HASH, body.password) and user is not None
        except VerificationError:
            ok = False
        if not ok:
            con.execute("INSERT INTO login_attempts VALUES(?,?)", (ip,now))
            con.commit()  # The failed-attempt counter must survive the 401 exception.
            raise HTTPException(401, "用户名或密码不正确")
        token = secrets.token_urlsafe(48)
        con.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], now+settings.token_days*86400))
        return {"token":token, "account_id":user["id"], "expires_in":settings.token_days*86400}


def require_owner(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "请登录")
    digest = hashlib.sha256(header[7:].encode()).hexdigest()
    with connect(request.app.state.settings) as con:
        row = con.execute("SELECT owner FROM sessions WHERE digest=? AND expires>?", (digest,time.time())).fetchone()
    if not row:
        raise HTTPException(401, "登录已过期，请重新登录；本机记录不会清除")
    return row["owner"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init-user"])
    parser.add_argument("--username", required=True)
    parser.add_argument("--data-dir", type=Path, default=Settings().data_dir)
    args = parser.parse_args()
    password = getpass.getpass("新密码（至少12位）: ")
    if password != getpass.getpass("确认密码: "):
        raise SystemExit("两次密码不同")
    create_user(Settings(data_dir=args.data_dir), args.username, password)
    print("账号已建立")


if __name__ == "__main__":
    main()

