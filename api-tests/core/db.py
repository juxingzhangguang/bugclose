# -*- coding: utf-8 -*-
"""数据库辅助：仅用于「建立/删除套件专用管理员」与少量落库校验。

业务断言一律走 HTTP 接口，这里的 SQL 只做只读校验或测试账号生命周期管理，
不会读写任何业务数据（bugs / requirements / test_cases / documents / projects）。
"""
import pymysql

import config


def connect():
    s = config.db_settings()
    return pymysql.connect(
        host=s["host"], port=s["port"], user=s["user"],
        password=s["password"], database=s["database"],
        charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def query(sql, args=None):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()


def scalar(sql, args=None):
    rows = query(sql, args)
    if not rows:
        return None
    return list(rows[0].values())[0]


# ------------------------------------------------------------------ 套件专用管理员
def hash_password(raw: str) -> str:
    import bcrypt
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(10)).decode("ascii")


def ensure_admin(username: str, password: str) -> str:
    """存在则重置口令，不存在则创建；返回动作描述。仅限套件专用账号。"""
    if not username.startswith(config.USER_PREFIX) and username != config.ADMIN_USERNAME:
        raise ValueError("拒绝操作非套件账号: " + username)
    row = query("SELECT id FROM users WHERE username=%s", (username,))
    digest = hash_password(password)
    if row:
        query("UPDATE users SET password=%s, enabled=1, role='ADMIN', must_change_password=0 WHERE id=%s",
              (digest, row[0]["id"]))
        return "reset"
    query(
        "INSERT INTO users(username, password, display_name, role, enabled, must_change_password, created_at, updated_at) "
        "VALUES(%s,%s,%s,'ADMIN',1,0,NOW(6),NOW(6))",
        (username, digest, "接口自动化管理员"),
    )
    return "created"


def remove_user(username: str) -> bool:
    if not username.startswith(config.USER_PREFIX) and username != config.ADMIN_USERNAME:
        raise ValueError("拒绝操作非套件账号: " + username)
    row = query("SELECT id FROM users WHERE username=%s", (username,))
    if not row:
        return False
    uid = row[0]["id"]
    query("DELETE FROM user_projects WHERE user_id=%s", (uid,))
    query("DELETE FROM users WHERE id=%s", (uid,))
    return True


# ------------------------------------------------------------------ 只读校验
def enabled_admin_count() -> int:
    return int(scalar("SELECT COUNT(*) FROM users WHERE role='ADMIN' AND enabled=1") or 0)


def index_exists(table: str, index: str) -> bool:
    return bool(scalar(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema=DATABASE() AND table_name=%s AND index_name=%s", (table, index)))


def password_is_bcrypt(username: str) -> bool:
    val = scalar("SELECT password FROM users WHERE username=%s", (username,))
    return isinstance(val, str) and val.startswith(("$2a$", "$2b$", "$2y$"))


def must_change_flag(username: str):
    return scalar("SELECT must_change_password+0 FROM users WHERE username=%s", (username,))


def count_rows(table: str, where: str = "", args=None) -> int:
    if table not in {"bugs", "requirements", "test_cases", "documents", "document_versions", "projects", "users", "roles"}:
        raise ValueError("不允许访问的表: " + table)
    sql = "SELECT COUNT(*) FROM " + table + ((" WHERE " + where) if where else "")
    return int(scalar(sql, args) or 0)