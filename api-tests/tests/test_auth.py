# -*- coding: utf-8 -*-
"""认证模块接口测试：登录、当前用户、登出、修改密码、强制改密标记。

对应接口：POST /api/auth/login、GET /api/auth/me、POST /api/auth/logout、
          POST /api/auth/change-password
安全约束：本文件所有改密操作只针对套件临时账号，绝不修改真实 admin 口令。
"""
import re

import pytest

import config
from core import data
from core.assertions import error, keys, no_content, ok, status, unauthorized
from core.client import ApiClient

pytestmark = pytest.mark.case("AUTH")

LOGIN_FIELDS = ["token", "id", "username", "displayName", "role",
                "allProjects", "allowedProjectIds", "mustChangePassword"]


@pytest.fixture
def pwd_user(factory, ip_pool):
    """一次性改密账号：返回 (用户信息, 已登录客户端)。"""
    user = factory.user(password="At#Old123")
    client = ApiClient(user["username"], ip=ip_pool())
    status(client.login(user["username"], user["password"]), 200, "临时账号登录")
    return user, client


# --------------------------------------------------------------------- 登录
@pytest.mark.case("AUTH-001")
def test_login_success(user1, ip_pool):
    client = ApiClient("login-ok", ip=ip_pool())
    resp = client.login(user1["username"], user1["password"])
    body = ok(resp, "正常登录")
    assert re.fullmatch(r"[0-9a-f]{64}", body["token"]), "token 应为 64 位十六进制随机串"
    assert body["username"] == user1["username"]


@pytest.mark.case("AUTH-002")
def test_login_response_fields(user1, ip_pool):
    client = ApiClient("login-fields", ip=ip_pool())
    body = ok(client.login(user1["username"], user1["password"]))
    keys(body, LOGIN_FIELDS, "登录响应")
    assert isinstance(body["id"], int)
    assert isinstance(body["allProjects"], bool)
    assert isinstance(body["allowedProjectIds"], list)
    assert isinstance(body["mustChangePassword"], bool)


@pytest.mark.case("AUTH-003")
def test_admin_all_projects(admin):
    assert admin.me["role"] == "ADMIN"
    assert admin.me["allProjects"] is True
    assert admin.me["allowedProjectIds"] == [], "管理员不返回绑定项目集合"


@pytest.mark.case("AUTH-004")
def test_user_allowed_project_ids(client1, project_a):
    assert client1.me["allProjects"] is False
    assert set(client1.me["allowedProjectIds"]) == {project_a["id"]}


@pytest.mark.case("AUTH-005")
def test_login_unknown_username(ip_pool):
    client = ApiClient("login-unknown", ip=ip_pool())
    error(client.login("at_bot_nobody_" + data.uniq().lower(), "whatever"),
          400, "用户名或密码错误")


@pytest.mark.case("AUTH-006")
def test_login_wrong_password(user1, ip_pool):
    client = ApiClient("login-wrongpwd", ip=ip_pool())
    error(client.login(user1["username"], "WrongPwd#999"), 400, "用户名或密码错误")


@pytest.mark.case("AUTH-007")
@pytest.mark.parametrize("payload", [
    {"username": "", "password": "At#12345"},
    {"username": "at_bot_x", "password": ""},
    {"username": "", "password": ""},
    {"username": None, "password": None},
    {},
], ids=["empty-username", "empty-password", "both-empty", "null-fields", "no-fields"])
def test_login_blank_credentials(payload, ip_pool):
    client = ApiClient("login-blank", ip=ip_pool())
    error(client.post("/api/auth/login", json=payload), 400, "用户名或密码错误")


@pytest.mark.case("AUTH-008")
def test_login_disabled_account(admin, factory, ip_pool):
    user = factory.user(password="At#12345")
    payload = data.user(username=user["username"], password=None,
                        project_ids=[p["id"] for p in user["view"]["projects"]])
    payload["enabled"] = False
    status(admin.put("/api/users/{}".format(user["id"]), json=payload), 200, "禁用账号")
    client = ApiClient("login-disabled", ip=ip_pool())
    error(client.login(user["username"], user["password"]), 400, "账号已被禁用")


@pytest.mark.case("AUTH-009")
def test_login_without_body(ip_pool):
    client = ApiClient("login-nobody", ip=ip_pool())
    resp = client.post("/api/auth/login", data="", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400, "缺少请求体应返回 400，实际 {}".format(resp.status_code)


# --------------------------------------------------------------------- 当前用户 / 登出
@pytest.mark.case("AUTH-010")
def test_me_success(client1, user1):
    body = ok(client1.get("/api/auth/me"))
    keys(body, LOGIN_FIELDS, "/me 响应")
    assert body["token"] is None, "/me 不应下发 token"
    assert body["username"] == user1["username"]
    assert body["id"] == user1["id"]


@pytest.mark.case("AUTH-011")
def test_me_without_token(anon):
    unauthorized(anon.get("/api/auth/me"), "匿名访问 /me")


@pytest.mark.case("AUTH-012")
def test_me_invalid_token(anon):
    unauthorized(anon.get("/api/auth/me", token="f" * 64), "伪造 token")


@pytest.mark.case("AUTH-013")
def test_logout_invalidates_token(user1, ip_pool):
    session = ApiClient("logout-session", ip=ip_pool())
    ok(session.login(user1["username"], user1["password"]))
    token = session.token
    no_content(session.post("/api/auth/logout"), "登出")
    unauthorized(session.get("/api/auth/me", token=token), "登出后原 token 应立即失效")


@pytest.mark.case("AUTH-014")
def test_logout_without_token(anon):
    unauthorized(anon.post("/api/auth/logout"), "匿名登出")


@pytest.mark.case("AUTH-015")
def test_multi_session_independent(user1, ip_pool):
    a = ApiClient("session-a", ip=ip_pool())
    b = ApiClient("session-b", ip=ip_pool())
    ok(a.login(user1["username"], user1["password"]))
    ok(b.login(user1["username"], user1["password"]))
    assert a.token != b.token, "每次登录应签发不同 token"
    no_content(a.post("/api/auth/logout"))
    unauthorized(a.get("/api/auth/me"))
    ok(b.get("/api/auth/me"), "另一端会话仍有效")


# --------------------------------------------------------------------- 强制改密标记
@pytest.mark.case("AUTH-016")
def test_default_password_sets_must_change(factory, ip_pool):
    user = factory.user(password=config.DEFAULT_ADMIN_PASSWORD)
    client = ApiClient("must-change", ip=ip_pool())
    body = ok(client.login(user["username"], config.DEFAULT_ADMIN_PASSWORD))
    assert body["mustChangePassword"] is True, "使用内置默认口令登录必须要求改密"


@pytest.mark.case("AUTH-017")
def test_normal_password_no_must_change(client1):
    body = ok(client1.fetch_me())
    assert body["mustChangePassword"] is False


@pytest.mark.case("AUTH-025")
def test_must_change_cleared_after_change(factory, ip_pool):
    user = factory.user(password=config.DEFAULT_ADMIN_PASSWORD)
    client = ApiClient("clear-flag", ip=ip_pool())
    assert ok(client.login(user["username"], config.DEFAULT_ADMIN_PASSWORD))["mustChangePassword"] is True
    no_content(client.change_password(config.DEFAULT_ADMIN_PASSWORD, "At#New123"))
    again = ApiClient("clear-flag-2", ip=ip_pool())
    body = ok(again.login(user["username"], "At#New123"))
    assert body["mustChangePassword"] is False, "改成非默认口令后应解除强制改密标记"


# --------------------------------------------------------------------- 修改密码
@pytest.mark.case("AUTH-018")
def test_change_password_returns_204(pwd_user):
    _, client = pwd_user
    resp = client.change_password("At#Old123", "At#New123")
    no_content(resp, "修改密码")


@pytest.mark.case("AUTH-019")
def test_change_password_revokes_all_tokens(pwd_user, ip_pool):
    user, client = pwd_user
    second = ApiClient("second-session", ip=ip_pool())
    ok(second.login(user["username"], user["password"]))
    no_content(client.change_password("At#Old123", "At#New123"))
    unauthorized(client.get("/api/auth/me"), "改密后当前 token")
    unauthorized(second.get("/api/auth/me"), "改密后其他端 token")
    unauthorized(client.get("/api/bugs"), "改密后业务接口")


@pytest.mark.case("AUTH-020")
def test_relogin_with_new_password(pwd_user, ip_pool):
    user, client = pwd_user
    no_content(client.change_password("At#Old123", "At#New123"))
    fresh = ApiClient("relogin", ip=ip_pool())
    ok(fresh.login(user["username"], "At#New123"), "新密码可登录")
    bad = ApiClient("relogin-old", ip=ip_pool())
    error(bad.login(user["username"], "At#Old123"), 400, "用户名或密码错误", "旧密码登录")


@pytest.mark.case("AUTH-021")
def test_change_password_wrong_old(pwd_user):
    _, client = pwd_user
    error(client.change_password("NotTheOldPwd", "At#New123"), 400, "原密码错误")


@pytest.mark.case("AUTH-022")
@pytest.mark.parametrize("new", ["", "1", "12345", None], ids=["empty", "1char", "5chars", "null"])
def test_change_password_too_short(pwd_user, new):
    _, client = pwd_user
    error(client.change_password("At#Old123", new), 400, "新密码至少 6 位")


@pytest.mark.case("AUTH-023")
def test_change_password_same_as_old(pwd_user):
    _, client = pwd_user
    error(client.change_password("At#Old123", "At#Old123"), 400, "新密码不能与原密码相同")


@pytest.mark.case("AUTH-024")
def test_change_password_to_default_keeps_flag(pwd_user, ip_pool):
    user, client = pwd_user
    no_content(client.change_password("At#Old123", config.DEFAULT_ADMIN_PASSWORD))
    again = ApiClient("back-to-default", ip=ip_pool())
    body = ok(again.login(user["username"], config.DEFAULT_ADMIN_PASSWORD))
    assert body["mustChangePassword"] is True, "改回内置默认口令仍应强制改密"


@pytest.mark.case("AUTH-026")
def test_change_password_requires_auth(anon):
    unauthorized(anon.post("/api/auth/change-password",
                           json={"oldPassword": "x", "newPassword": "At#New123"}),
                 "匿名改密")