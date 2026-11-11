# -*- coding: utf-8 -*-
"""安全加固横切测试：登录限流、token 强度、注入/XSS、错误信息泄露、强制改密落地情况。

限流用例一律使用一次性账号 + 独立 X-Forwarded-For，
锁定只影响该账号与该 IP 的组合，不会波及真实用户或其他用例。
"""
import re

import pytest

import config
from core import data
from core.assertions import (created, error, keys, no_keys, ok, rejected, status,
                             unauthorized)
from core.client import ApiClient, body

pytestmark = pytest.mark.case("SEC")

TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_FAILURES = 5          # LoginRateLimiter.MAX_FAILURES
LOCK_HINT = "失败次数过多"


def _client(ip, token=None):
    return ApiClient("sec-probe", token=token, ip=ip)


def _fail(username, ip, times, password="WrongPass#1"):
    c = _client(ip)
    return [c.login(username, password) for _ in range(times)]


# ===================================================================== 登录限流
@pytest.mark.case("SEC-001")
def test_rate_limit_locks_after_threshold(factory, ip_pool):
    acct = factory.user()
    ip = ip_pool()
    responses = _fail(acct["username"], ip, MAX_FAILURES)
    assert all(r.status_code == 400 for r in responses), \
        "阈值内的失败应返回 400，实际 {}".format([r.status_code for r in responses])
    locked = _client(ip).login(acct["username"], "WrongPass#1")
    error(locked, 429, LOCK_HINT, "第 6 次应被锁定")


@pytest.mark.case("SEC-002")
def test_rate_limit_scoped_by_ip(factory, ip_pool):
    acct = factory.user()
    _fail(acct["username"], ip_pool(), MAX_FAILURES)
    fresh = _client(ip_pool())
    assert fresh.login(acct["username"], acct["password"]).status_code == 200, \
        "换来源 IP 后应可正常登录（限流按 用户名+IP 分桶）"


@pytest.mark.case("SEC-003")
def test_rate_limit_username_case_insensitive(factory, ip_pool):
    acct = factory.user()
    ip = ip_pool()
    _fail(acct["username"].lower(), ip, MAX_FAILURES)
    resp = _client(ip).login(acct["username"].upper(), acct["password"])
    error(resp, 429, LOCK_HINT, "用户名大小写应命中同一限流桶")


@pytest.mark.case("SEC-004")
def test_success_clears_failure_counter(factory, ip_pool):
    acct = factory.user()
    ip = ip_pool()
    _fail(acct["username"], ip, MAX_FAILURES - 1)
    assert _client(ip).login(acct["username"], acct["password"]).status_code == 200
    again = _client(ip).login(acct["username"], "WrongPass#1")
    status(again, 400, "成功登录应清空失败计数，重新从 1 开始")


@pytest.mark.case("SEC-005")
def test_locked_rejects_correct_password(factory, ip_pool):
    acct = factory.user()
    ip = ip_pool()
    _fail(acct["username"], ip, MAX_FAILURES)
    resp = _client(ip).login(acct["username"], acct["password"])
    error(resp, 429, LOCK_HINT, "锁定期间即使口令正确也拒绝")


@pytest.mark.case("SEC-006")
def test_xff_spoofing_bypasses_rate_limit(factory, ip_pool):
    """现状确认：X-Forwarded-For 被无条件信任，攻击者逐次伪造即可绕过限流。

    风险：限流形同虚设，仍可离线爆破口令。
    建议：只在可信代理后解析 XFF，或改用 remoteAddr + 代理层真实 IP 透传。
    """
    acct = factory.user()
    codes = []
    for _ in range(MAX_FAILURES * 2):
        c = _client(ip_pool())          # 每次换一个伪造 IP
        codes.append(c.login(acct["username"], "WrongPass#1").status_code)
    assert all(c == 400 for c in codes), "伪造 XFF 后 never 触发 429，实际 {}".format(codes)
    assert 429 not in codes


@pytest.mark.case("SEC-007")
def test_xff_first_value_used(factory, ip_pool):
    acct = factory.user()
    first = ip_pool()
    second = ip_pool()
    _fail(acct["username"], "{}, {}".format(first, second), MAX_FAILURES)
    error(_client(first).login(acct["username"], acct["password"]), 429, LOCK_HINT,
          "多值 XFF 取第一个，应与单值 first 命中同一桶")
    assert _client(second).login(acct["username"], acct["password"]).status_code == 200, \
        "第二个 IP 不在同一桶"


@pytest.mark.case("SEC-008")
def test_rate_limit_does_not_affect_other_account(factory, ip_pool):
    a = factory.user()
    b = factory.user()
    ip = ip_pool()
    _fail(a["username"], ip, MAX_FAILURES)
    assert _client(ip).login(b["username"], b["password"]).status_code == 200, \
        "同 IP 下其他账号不受影响"


# ===================================================================== token 强度
@pytest.mark.case("SEC-009")
def test_token_format_and_uniqueness(factory, ip_pool):
    acct = factory.user()
    t1 = _client(ip_pool()).login(acct["username"], acct["password"]).json()["token"]
    t2 = _client(ip_pool()).login(acct["username"], acct["password"]).json()["token"]
    assert TOKEN_RE.match(t1), "token 应为 64 位小写 hex（SecureRandom 32 字节）"
    assert TOKEN_RE.match(t2)
    assert t1 != t2, "两次登录应签发不同 token"


@pytest.mark.case("SEC-010")
@pytest.mark.parametrize("token", ["0" * 64, "f" * 64, "deadbeef", "", "x" * 64])
def test_forged_token_rejected(anon, token):
    unauthorized(anon.get("/api/auth/me", token=token), "伪造 token")


@pytest.mark.case("SEC-011")
@pytest.mark.parametrize("header", ["Token abc", "Bearer", "Basic YWRtaW46YWRtaW4=",
                                    "bearer abc", "ABC"])
def test_malformed_authorization_rejected(anon, admin, header):
    resp = anon.get("/api/auth/me", headers={"Authorization": header})
    unauthorized(resp, "非法 Authorization 头: " + header)


@pytest.mark.case("SEC-012")
def test_token_not_accepted_via_other_headers(anon, admin):
    for name in ("X-Auth-Token", "Token", "Auth", "Cookie"):
        unauthorized(anon.get("/api/auth/me", headers={name: admin.token}),
                     "token 只认 Authorization: Bearer，" + name + " 不应生效")


# ===================================================================== 注入与 XSS
@pytest.mark.case("SEC-013")
@pytest.mark.parametrize("payload", ["' OR '1'='1", "admin'--", "' UNION SELECT 1,2,3--",
                                     "'; DROP TABLE users;--"])
def test_login_sql_injection(ip_pool, payload):
    resp = _client(ip_pool()).login(payload, payload)
    error(resp, 400, "用户名或密码错误", "SQL 注入登录")
    assert "SQL" not in resp.text and "Exception" not in resp.text, "不得泄露数据库异常"


@pytest.mark.case("SEC-014")
def test_search_keyword_sql_injection(admin, project_a, factory):
    factory.bug(admin, project_a["id"], title="AT正常缺陷")
    for kw in ("' OR '1'='1", "%", "_", "'; DROP TABLE bugs;--"):
        rows = ok(admin.get("/api/bugs", params={"projectId": project_a["id"], "keyword": kw}),
                  "注入关键字 " + kw)
        assert isinstance(rows, list), "应正常返回列表而非报错"
    assert ok(admin.get("/api/bugs", params={"keyword": "' OR '1'='1"})) == [], \
        "注入串不应匹配到全部数据"


@pytest.mark.case("SEC-015")
def test_stored_xss_payload_not_executed_on_server(admin, factory, project_a):
    """现状确认：后端原样存储并返回 HTML/脚本片段，转义责任在前端。

    风险：若前端用 innerHTML 渲染标题/描述，会形成存储型 XSS。
    建议：前端统一文本节点渲染，或后端入库时做转义/白名单过滤。
    """
    payload = "<script>alert('xss')</script><img src=x onerror=alert(1)>"
    bug = factory.bug(admin, project_a["id"], title=payload, description=payload)
    assert bug["title"] == payload, "后端原样返回，未做转义"
    resp = admin.get("/api/bugs/{}".format(bug["id"]))
    got = ok(resp)
    assert got["description"] == payload
    assert "text/html" not in resp.headers.get("Content-Type", ""), \
        "响应 Content-Type 应为 JSON，避免被浏览器当 HTML 执行"


@pytest.mark.case("SEC-016")
def test_path_traversal_in_query(admin):
    for kw in ("../../application.properties", "..\\..\\windows\\win.ini", "/etc/passwd"):
        resp = admin.get("/api/bugs", params={"keyword": kw})
        assert resp.status_code == 200
        assert b"spring.datasource" not in resp.content, "不得读出配置文件"


# ===================================================================== 错误信息泄露
@pytest.mark.case("SEC-017")
def test_error_body_has_no_stacktrace(admin, client1, project_b, factory):
    bug = factory.bug(admin, project_b["id"])
    resp = client1.get("/api/bugs/{}".format(bug["id"]))
    text = resp.text
    for leak in ("Exception", "at com.bugclose", "java.", "SQL", "Hibernate", "stackTrace"):
        assert leak not in text, "错误响应泄露内部信息: " + leak


@pytest.mark.case("SEC-018")
def test_framework_error_body_shape(admin):
    """框架层错误（缺少 multipart 部分名）走 Boot 默认错误体，同样不得泄露堆栈。"""
    resp = admin.post("/api/uploads",
                      files=[("image", ("at_x.png", data.PNG_BYTES, "application/octet-stream"))])
    rejected(resp, "part 名不是 file")
    obj = body(resp)
    keys(obj, ["timestamp", "status", "error", "path"], "框架默认错误体")
    assert "trace" not in obj and "exception" not in obj, "不应返回堆栈/异常类名"
    # 业务层错误（非法枚举被 IllegalArgumentException 处理器接管）走 {"error": ...}
    biz = admin.get("/api/bugs", params={"status": "NOT_A_STATUS"})
    rejected(biz, "非法枚举")
    assert "trace" not in (body(biz) or {}), "业务错误体也不应返回堆栈"


@pytest.mark.case("SEC-019")
def test_sensitive_fields_never_returned(admin, factory):
    acct = factory.user()
    for resp in (admin.get("/api/users"), admin.get("/api/users/{}".format(acct["id"]))):
        rows = ok(resp)
        rows = rows if isinstance(rows, list) else [rows]
        for row in rows:
            no_keys(row, ["password", "mustChangePassword"], "用户视图")
    login = _client("10.199.0.77").login(acct["username"], acct["password"])
    no_keys(body(login), ["password"], "登录响应")


# ===================================================================== 强制改密落地
@pytest.mark.case("SEC-020")
def test_must_change_password_not_enforced_server_side(admin, factory, ip_pool, project_a):
    """现状确认：mustChangePassword 只是返回给前端的标记，服务端不拦截业务请求。

    风险：绕过前端直接调接口即可用默认口令长期操作数据。
    建议：AuthFilter 或拦截器对 mustChangePassword=true 的用户只放行
    /api/auth/me、/api/auth/change-password、/api/auth/logout。
    """
    acct = factory.user(password=config.DEFAULT_ADMIN_PASSWORD, project_ids=[project_a["id"]])
    c = _client(ip_pool())
    assert c.login(acct["username"], acct["password"]).status_code == 200
    assert c.me["mustChangePassword"] is True
    bug = created(c.post("/api/bugs", json=data.bug(project_a["id"])),
                  "未改密也能创建缺陷（服务端未强制）")
    factory.tracker.add("bug", bug["id"], lambda: admin.delete("/api/bugs/{}".format(bug["id"])))
    ok(c.get("/api/projects"), "未改密也能读取项目列表")


@pytest.mark.case("SEC-021")
def test_change_password_revokes_across_endpoints(admin, factory, ip_pool):
    acct = factory.user()
    c = _client(ip_pool())
    assert c.login(acct["username"], acct["password"]).status_code == 200
    old = c.token
    status(c.change_password(acct["password"], "Brand#NewPass1"), 204, "改密")
    stale = _client(ip_pool(), token=old)
    for path in ("/api/auth/me", "/api/projects", "/api/bugs", "/api/users",
                 "/api/roles", "/api/dashboard/statistics"):
        unauthorized(stale.get(path), "改密后旧 token 访问 " + path)


# ===================================================================== 协议健壮性
@pytest.mark.case("SEC-022")
def test_malformed_json_rejected(admin):
    resp = admin.post("/api/bugs", data="{not json",
                      headers={"Content-Type": "application/json"})
    rejected(resp, "畸形 JSON")
    assert resp.status_code == 400
    assert "Exception" not in resp.text


@pytest.mark.case("SEC-023")
def test_wrong_content_type_rejected(admin):
    resp = admin.post("/api/bugs", data="title=x",
                      headers={"Content-Type": "text/plain"})
    assert resp.status_code in (400, 415), "非 JSON Content-Type 应被拒绝，实际 {}".format(resp.status_code)


@pytest.mark.case("SEC-024")
def test_method_override_header_ignored(admin, factory):
    proj = factory.project()
    resp = admin.put("/api/projects/{}".format(proj["id"]),
                     json=data.project(name=proj["name"], code=proj["code"]),
                     headers={"X-HTTP-Method-Override": "DELETE"})
    assert resp.status_code != 204, "方法覆盖头不应把 PUT 变成 DELETE"
    assert proj["id"] in {p["id"] for p in ok(admin.get("/api/projects"))}, "项目未被删除"


@pytest.mark.case("SEC-025")
def test_logout_token_cannot_be_reused(factory, ip_pool):
    acct = factory.user()
    c = _client(ip_pool())
    assert c.login(acct["username"], acct["password"]).status_code == 200
    token = c.token
    status(c.logout(), 204, "登出")
    unauthorized(_client(ip_pool(), token=token).get("/api/auth/me"), "登出后复用 token")
    # 登出接口本身也在 AuthFilter 保护范围内：token 已吊销，重复登出返回 401 而非幂等 204
    unauthorized(_client(ip_pool(), token=token).logout(), "重复登出")