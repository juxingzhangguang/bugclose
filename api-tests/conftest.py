# -*- coding: utf-8 -*-
"""pytest 全局夹具：身份、项目、数据工厂与清理。

设计原则
--------
1. 不依赖真实 admin 口令：默认使用套件专用管理员 at_bot_admin，
   登录失败时按配置自动创建（会话结束后删除），全程不修改真实 admin。
2. 所有测试数据都带 AT_ / at_bot_ 保留前缀，会话开始前清扫历史遗留、
   结束后按「先子后父」顺序回收，不触碰任何业务数据。
3. 每个身份绑定独立 X-Forwarded-For，登录限流用例之间互不干扰。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                      # noqa: E402
from config import BASE_URL, RUN_ID  # noqa: E402  （钩子参数名会遮蔽模块名，故提前取出常量）
from core import data, db          # noqa: E402
from core.assertions import created, no_content, ok, status   # noqa: E402
from core.client import ApiClient  # noqa: E402
from core.tracker import Tracker, sweep_leftovers   # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "case(cid): 关联接口测试用例编号")
    config.addinivalue_line("markers", "slow: 耗时较长的用例")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:      # noqa: BLE001
            pass


# ====================================================================== 身份
@pytest.fixture(scope="session")
def admin():
    """套件管理员客户端（会话级，全程稳定，清理动作统一用它）。"""
    client = ApiClient("admin", ip=config.IP_ADMIN)
    resp = client.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
    bootstrapped = False
    if resp.status_code != 200 and config.AUTO_BOOTSTRAP:
        try:
            action = db.ensure_admin(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
            bootstrapped = True
            print("\n[bootstrap] suite admin {} {} via database".format(config.ADMIN_USERNAME, action))
        except Exception as exc:      # noqa: BLE001
            pytest.exit("无法创建套件专用管理员：{}\n"
                        "请设置 BUGCLOSE_ADMIN_USER / BUGCLOSE_ADMIN_PASSWORD 为可用管理员账号，"
                        "或检查数据库连接配置。".format(exc), returncode=3)
        resp = client.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
    if resp.status_code != 200:
        pytest.exit("管理员登录失败（HTTP {}）：{}\n"
                    "请确认服务已启动（{}），并通过 BUGCLOSE_ADMIN_USER / BUGCLOSE_ADMIN_PASSWORD "
                    "提供可用管理员账号。".format(resp.status_code, resp.text[:200], config.BASE_URL),
                    returncode=3)
    assert client.me["role"] == "ADMIN", "配置的账号不是管理员，无法执行全套用例"
    yield client
    if bootstrapped and not config.KEEP_DATA:
        try:
            db.remove_user(config.ADMIN_USERNAME)
            print("\n[bootstrap] suite admin {} removed".format(config.ADMIN_USERNAME))
        except Exception as exc:      # noqa: BLE001
            print("\n[bootstrap] remove admin failed: {}".format(exc))


@pytest.fixture(scope="session")
def anon():
    return ApiClient("anonymous", ip="10.199.0.99")


@pytest.fixture(scope="session")
def ip_pool():
    """为负向登录用例分配互不相同的来源 IP。

    后端限流按「用户名+IP」分桶，独立 IP 可确保用例之间不会相互锁定，
    也不会影响真实用户在浏览器里的登录。
    """
    import itertools
    counter = itertools.count(10)
    return lambda: "{}.{}".format(config.IP_PROBE_BASE, next(counter))


@pytest.fixture(scope="session")
def tracker(admin):
    t = Tracker()
    removed = sweep_leftovers(admin)
    if removed:
        print("\n[sweep] removed {} leftover test objects".format(len(removed)))
    yield t
    errors = t.cleanup()
    for e in errors:
        print("\n[cleanup] " + e)


# ====================================================================== 项目
def _make_project(admin, tracker, suffix):
    payload = data.project(name="{}{}_{}".format(config.PROJECT_PREFIX, config.RUN_ID, suffix),
                           code=(config.TAG + suffix)[:20])
    resp = admin.post("/api/projects", json=payload)
    obj = created(resp, "创建测试项目 " + suffix)
    tracker.add("project", obj["id"], lambda: admin.delete("/api/projects/{}".format(obj["id"])))
    return obj


@pytest.fixture(scope="session")
def project_a(admin, tracker):
    """主测试项目：绑定给 user1。"""
    return _make_project(admin, tracker, "A")


@pytest.fixture(scope="session")
def project_b(admin, tracker):
    """对照项目：只绑定给 user2，用于越权 / 数据隔离断言。"""
    return _make_project(admin, tracker, "B")


@pytest.fixture(scope="session")
def project_c(admin, tracker):
    """沙盒项目：并发、删除守卫等破坏性用例专用。"""
    return _make_project(admin, tracker, "C")


# ====================================================================== 普通用户
def _make_user(admin, tracker, suffix, project_ids, password="At#12345"):
    payload = data.user(username="{}{}_{}".format(config.USER_PREFIX, config.RUN_ID.lower(), suffix),
                        password=password, project_ids=project_ids)
    resp = admin.post("/api/users", json=payload)
    obj = created(resp, "创建测试用户 " + suffix)
    tracker.add("user", obj["id"], lambda: admin.delete("/api/users/{}".format(obj["id"])))
    return {"id": obj["id"], "username": payload["username"], "password": password, "view": obj}


@pytest.fixture(scope="session")
def user1(admin, tracker, project_a):
    return _make_user(admin, tracker, "u1", [project_a["id"]])


@pytest.fixture(scope="session")
def user2(admin, tracker, project_b):
    return _make_user(admin, tracker, "u2", [project_b["id"]])


@pytest.fixture(scope="session")
def user_empty(admin, tracker):
    return _make_user(admin, tracker, "u0", [])


def _login(user, ip):
    c = ApiClient(user["username"], ip=ip)
    resp = c.login(user["username"], user["password"])
    status(resp, 200, "测试用户登录 " + user["username"])
    return c


@pytest.fixture(scope="session")
def client1(user1):
    return _login(user1, config.IP_USER1)


@pytest.fixture(scope="session")
def client2(user2):
    return _login(user2, config.IP_USER2)


@pytest.fixture(scope="session")
def client_empty(user_empty):
    return _login(user_empty, config.IP_USER_EMPTY)


# ====================================================================== 数据工厂
class Factory:
    """创建即登记清理；创建用调用者身份，清理统一用管理员身份。"""

    def __init__(self, admin, tracker):
        self.admin = admin
        self.tracker = tracker

    def _reg(self, kind, path, obj):
        oid = obj["id"]
        self.tracker.add(kind, oid, lambda: self.admin.delete("{}/{}".format(path, oid)))
        return obj

    def bug(self, client, project_id, **kw):
        resp = client.post("/api/bugs", json=data.bug(project_id, **kw))
        return self._reg("bug", "/api/bugs", created(resp, "创建缺陷"))

    def requirement(self, client, project_id, **kw):
        resp = client.post("/api/requirements", json=data.requirement(project_id, **kw))
        return self._reg("requirement", "/api/requirements", created(resp, "创建需求"))

    def testcase(self, client, project_id, **kw):
        resp = client.post("/api/testcases", json=data.testcase(project_id, **kw))
        return self._reg("testcase", "/api/testcases", created(resp, "创建用例"))

    def doc(self, client, project_id, ext="txt", filename=None, **fields):
        content = fields.pop("content", None)
        size = fields.pop("size", None)
        form = {"title": fields.pop("title", "AT文档_" + data.uniq()),
                "category": fields.pop("category", "TEST"),
                "description": fields.pop("description", "自动化测试文档"),
                "uploader": fields.pop("uploader", "at_bot")}
        if project_id is not None:
            form["projectId"] = str(project_id)
        form.update({k: str(v) for k, v in fields.items()})
        resp = client.post("/api/docs", data=form,
                           files=[data.doc_file(ext, filename, size, content)])
        return self._reg("doc", "/api/docs", created(resp, "上传文档"))

    def project(self, client=None, **kw):
        c = client or self.admin
        resp = c.post("/api/projects", json=data.project(**kw))
        obj = self._reg("project", "/api/projects", created(resp, "创建项目"))
        # 项目删除有子资源守卫：先清空该项目下的业务数据，
        # 兜住「用例直接发请求创建、未走 factory 登记」的子资源。
        self.tracker.add("project", "purge-{}".format(obj["id"]),
                         lambda: self._purge(obj["id"]))
        return obj

    def _purge(self, project_id):
        for path in ("/api/bugs", "/api/requirements", "/api/testcases", "/api/docs"):
            listing = self.admin.get(path, params={"projectId": project_id})
            if listing.status_code != 200:
                continue
            for row in listing.json():
                self.admin.delete("{}/{}".format(path, row["id"]))

    def user(self, client=None, **kw):
        c = client or self.admin
        payload = data.user(**kw)
        resp = c.post("/api/users", json=payload)
        obj = self._reg("user", "/api/users", created(resp, "创建用户"))
        return {"id": obj["id"], "username": payload["username"],
                "password": payload["password"], "view": obj}

    def role(self, client=None, **kw):
        c = client or self.admin
        resp = c.post("/api/roles", json=data.role(**kw))
        return self._reg("role", "/api/roles", created(resp, "创建角色"))

    def upload(self, client, ext="png", filename=None, size=None):
        resp = client.post("/api/uploads", files=[data.image_file(ext, filename, size)])
        obj = ok(resp, "上传图片")
        url = obj["url"]
        local = config.PROJECT_ROOT / url.lstrip("/")
        self.tracker.add("file", url, lambda: local.unlink(missing_ok=True))
        return obj


@pytest.fixture(scope="session")
def factory(admin, tracker):
    return Factory(admin, tracker)


# ====================================================================== 失败现场
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        dumps = []
        for name in ("admin", "client1", "client2", "client_empty", "anon"):
            client = item.funcargs.get(name)
            if isinstance(client, ApiClient) and client.history:
                dumps.append("[{}]\n{}".format(name, client.dump_history(5)))
        if dumps:
            report.sections.append(("HTTP trace", "\n".join(dumps)))


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    tr = terminalreporter
    passed = len(tr.stats.get("passed", []))
    failed = len(tr.stats.get("failed", []))
    skipped = len(tr.stats.get("skipped", []))
    errors = len(tr.stats.get("error", []))
    total = passed + failed + skipped + errors
    rate = (passed / total * 100) if total else 0.0
    tr.write_sep("=", "BugClose API test summary")
    tr.write_line("total={} passed={} failed={} skipped={} error={} pass_rate={:.1f}%".format(
        total, passed, failed, skipped, errors, rate))
    tr.write_line("run_id={} base_url={}".format(RUN_ID, BASE_URL))