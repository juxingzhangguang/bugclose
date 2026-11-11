# -*- coding: utf-8 -*-
"""BugClose 接口自动化测试全局配置。

所有配置均可用环境变量覆盖，便于切换被测环境：
    BUGCLOSE_BASE_URL          被测服务地址，默认 http://localhost:8080
    BUGCLOSE_ADMIN_USER        管理员用户名，默认 at_bot_admin（套件专用账号）
    BUGCLOSE_ADMIN_PASSWORD    管理员口令，默认 AtBot#2026Pwd
    BUGCLOSE_AUTO_BOOTSTRAP    管理员登录失败时是否自动建套件专用管理员，默认 1
    BUGCLOSE_DB_HOST/PORT/NAME/USER  数据库连接覆盖（口令始终取 application*.properties）
    BUGCLOSE_KEEP_DATA         1=保留本次测试数据不清理（排查用），默认 0
"""
import os
import re
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------- 路径
TESTS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_ROOT.parent
REPORT_DIR = TESTS_ROOT / "reports"
CASE_DIR = TESTS_ROOT / "cases"

# ---------------------------------------------------------------- 被测服务
BASE_URL = os.getenv("BUGCLOSE_BASE_URL", "http://localhost:8080").rstrip("/")
TIMEOUT = float(os.getenv("BUGCLOSE_TIMEOUT", "30"))

# ---------------------------------------------------------------- 管理员账号
# 默认使用套件专用管理员，避免依赖 / 修改真实 admin 的口令。
ADMIN_USERNAME = os.getenv("BUGCLOSE_ADMIN_USER", "at_bot_admin")
ADMIN_PASSWORD = os.getenv("BUGCLOSE_ADMIN_PASSWORD", "AtBot#2026Pwd")
AUTO_BOOTSTRAP = os.getenv("BUGCLOSE_AUTO_BOOTSTRAP", "1") != "0"

# ---------------------------------------------------------------- 数据保留策略
KEEP_DATA = os.getenv("BUGCLOSE_KEEP_DATA", "0") == "1"

# ---------------------------------------------------------------- 命名前缀（保留给本套件，勿用于业务数据）
RUN_ID = (time.strftime("%m%d%H%M") + uuid.uuid4().hex[:4]).upper()
PROJECT_PREFIX = "AT_"          # 项目名前缀
USER_PREFIX = "at_bot_"         # 用户名前缀
ROLE_PREFIX = "AT_"             # 角色编码前缀
TAG = "AT" + RUN_ID             # 短标签，用于项目编号 / 关键字检索

# 固定 X-Forwarded-For：限流按 用户名+IP 分桶，给每个身份分配独立 IP 可避免相互干扰
IP_ADMIN = "10.199.0.1"
IP_USER1 = "10.199.0.2"
IP_USER2 = "10.199.0.3"
IP_USER_EMPTY = "10.199.0.4"
IP_PROBE_BASE = "10.199.1"      # 负向登录用例按 10.199.1.N 递增取用

# ---------------------------------------------------------------- 业务常量（与后端枚举保持一致）
DEFAULT_ADMIN_PASSWORD = "admin123"   # DataSeeder.DEFAULT_ADMIN_PASSWORD
BUG_SEVERITY = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
BUG_PRIORITY = ["URGENT", "HIGH", "MEDIUM", "LOW"]
BUG_STATUS = ["NEW", "IN_PROGRESS", "RESOLVED", "CLOSED"]
REQ_PRIORITY = ["P0", "P1", "P2", "P3"]
REQ_STATUS = ["DRAFT", "REVIEWING", "APPROVED", "IN_PROGRESS", "COMPLETED", "REJECTED"]
CASE_PRIORITY = ["P0", "P1", "P2", "P3"]
CASE_STATUS = ["NOT_RUN", "PASS", "FAIL", "BLOCKED"]
DOC_CATEGORY = ["REQUIREMENT", "DESIGN", "TEST", "MANUAL", "MEETING", "OTHER"]

IMG_EXT = ["png", "jpg", "jpeg", "gif", "webp", "bmp"]
DOC_EXT = ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf", "txt", "md", "zip", "rar", "7z", "png", "jpg"]

# 字段长度上限（来自 JPA @Column(length=...)）
LEN = {
    "project_name": 100, "project_code": 20, "project_desc": 500,
    "bug_title": 200, "bug_desc": 4000, "bug_assignee": 50,
    "bug_env": 100, "bug_module": 100, "bug_reporter": 50,
    "req_title": 200, "req_period": 50, "req_module": 100,
    "case_title": 200, "case_module": 100, "case_precondition": 1000,
    "username": 50, "display_name": 50, "role_code": 20, "role_name": 50,
}


# ---------------------------------------------------------------- 数据库连接（仅用于建/删套件专用管理员与少量落库校验）
def _read_properties(path: Path) -> dict:
    props = {}
    if not path.exists():
        return props
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def db_settings() -> dict:
    """解析 spring.datasource.*；local profile 覆盖主配置。"""
    main = _read_properties(PROJECT_ROOT / "src/main/resources/application.properties")
    local = _read_properties(PROJECT_ROOT / "src/main/resources/application-local.properties")
    merged = {**main, **local}
    url = merged.get("spring.datasource.url", "")
    m = re.match(r"jdbc:mysql://([^:/]+):(\d+)/([^?]+)", url)
    host, port, name = (m.group(1), int(m.group(2)), m.group(3)) if m else ("127.0.0.1", 3306, "bugclose")
    password = merged.get("spring.datasource.password", "")
    # 仅当配置文件里是 ${ENV} 占位符时才回退到环境变量；
    # local profile 已给出明文口令时以文件为准（机器上可能残留过期的同名环境变量）。
    if password.startswith("${"):
        password = os.getenv(password[2:-1], "")
    return {
        "host": os.getenv("BUGCLOSE_DB_HOST", host),
        "port": int(os.getenv("BUGCLOSE_DB_PORT", str(port))),
        "database": os.getenv("BUGCLOSE_DB_NAME", name),
        "user": os.getenv("BUGCLOSE_DB_USER", merged.get("spring.datasource.username", "bugclose")),
        "password": password,
    }