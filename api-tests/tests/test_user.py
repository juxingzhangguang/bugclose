# -*- coding: utf-8 -*-
"""用户管理接口测试：/api/users（账号生命周期、项目绑定、口令重置、token 吊销、协作可见性）。"""
import pytest

import config
from core import data, db
from core.assertions import (created, error, forbidden, keys, no_content, no_keys,
                             ok, same_time, unauthorized)
from core.client import ApiClient

pytestmark = pytest.mark.case("USER")

VIEW_KEYS = ["id", "username", "displayName", "role", "enabled", "createdAt", "projects"]
SECRET_KEYS = ["password", "mustChangePassword", "updatedAt"]


@pytest.fixture
def account(factory):
    """一次性账号：默认口令 At#12345，用完即删。"""
    return factory.user()


def _login(account, ip):
    c = ApiClient(account["username"], ip=ip)
    resp = c.login(account["username"], account["password"])
    assert resp.status_code == 200, "测试账号登录失败: {}".format(resp.text[:200])
    return c


def _project_ids(view):
    return {p["id"] for p in view["projects"]}


# ===================================================================== 创建
@pytest.mark.case("USER-001")
def test_create_defaults(admin):
    payload = data.user()
    payload.pop("displayName"), payload.pop("role"), payload.pop("projectIds")
    obj = created(admin.post("/api/users", json=payload), "创建用户")
    keys(obj, VIEW_KEYS, "用户视图")
    no_keys(obj, SECRET_KEYS, "用户视图不应泄露口令")
    assert obj["role"] == "USER", "未传角色默认 USER"
    assert obj["enabled"] is True
    assert obj["displayName"] == payload["username"], "未传显示名回落为用户名"
    assert obj["projects"] == []
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-002")
def test_create_with_bindings(admin, factory, project_a, project_b):
    acct = factory.user(displayName="  张三  ", role="USER",
                        project_ids=[project_a["id"], project_b["id"]])
    view = acct["view"]
    assert view["displayName"] == "张三", "显示名应 trim"
    assert _project_ids(view) == {project_a["id"], project_b["id"]}
    assert all(set(p) == {"id", "name"} for p in view["projects"]), "绑定项目只暴露 id/name"
    names = {p["id"]: p["name"] for p in view["projects"]}
    assert names[project_a["id"]] == project_a["name"]


@pytest.mark.case("USER-003")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_username_required(admin, blank):
    payload = data.user()
    payload["username"] = blank
    error(admin.post("/api/users", json=payload), 400, "用户名不能为空")


@pytest.mark.case("USER-004")
def test_username_trimmed(admin, factory):
    raw = config.USER_PREFIX + data.uniq("t").lower()
    acct = factory.user(username="  " + raw + "  ")
    assert acct["view"]["username"] == raw


@pytest.mark.case("USER-005")
def test_username_duplicate(admin, account):
    payload = data.user(username=account["username"])
    error(admin.post("/api/users", json=payload), 400, "用户名已存在: " + account["username"])


@pytest.mark.case("USER-006")
@pytest.mark.parametrize("password,ok_expected", [
    (None, False), ("", False), ("123", False), ("1234", True),
], ids=["null", "empty", "3-chars", "4-chars"])
def test_password_min_length(admin, password, ok_expected):
    payload = data.user(password=password)
    resp = admin.post("/api/users", json=payload)
    if ok_expected:
        obj = created(resp, "4 位口令应允许")
        admin.delete("/api/users/{}".format(obj["id"]))
    else:
        error(resp, 400, "密码不能为空且至少 4 位")


@pytest.mark.case("USER-007")
def test_password_stored_hashed(admin, account):
    assert db.password_is_bcrypt(account["username"]), "口令必须以 bcrypt 摘要落库"
    digest = db.scalar("SELECT password FROM users WHERE username=%s", (account["username"],))
    assert account["password"] not in digest


@pytest.mark.case("USER-008")
@pytest.mark.parametrize("display", [None, "", "   "], ids=["null", "empty", "blank"])
def test_display_name_falls_back_to_username(admin, display):
    payload = data.user(displayName=display)
    obj = created(admin.post("/api/users", json=payload))
    assert obj["displayName"] == payload["username"]
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-009")
def test_role_null_defaults_to_user(admin):
    payload = data.user(role=None)
    obj = created(admin.post("/api/users", json=payload))
    assert obj["role"] == "USER"
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-010")
def test_create_forces_enabled(admin):
    """现状确认：创建接口忽略 enabled=false，新账号一律启用。"""
    payload = data.user(enabled=False)
    obj = created(admin.post("/api/users", json=payload))
    assert obj["enabled"] is True, "创建时 enabled 被强制为 true"
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-011")
def test_create_admin_role(admin, factory):
    acct = factory.user(role="ADMIN")
    assert acct["view"]["role"] == "ADMIN"


@pytest.mark.case("USER-012")
def test_default_password_sets_must_change(admin, factory, ip_pool):
    acct = factory.user(password=config.DEFAULT_ADMIN_PASSWORD)
    assert db.must_change_flag(acct["username"]) == 1, "初始口令为内置默认值时应打强制改密标记"
    c = _login(acct, ip_pool())
    assert c.me["mustChangePassword"] is True


@pytest.mark.case("USER-013")
def test_normal_password_no_must_change(admin, factory, ip_pool):
    acct = factory.user()
    assert db.must_change_flag(acct["username"]) == 0
    c = _login(acct, ip_pool())
    assert c.me["mustChangePassword"] is False


@pytest.mark.case("USER-014")
def test_unknown_project_ids_ignored(admin, project_a):
    payload = data.user(project_ids=[project_a["id"], 99999999])
    obj = created(admin.post("/api/users", json=payload))
    assert _project_ids(obj) == {project_a["id"]}, "不存在的项目 id 被静默忽略"
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-015")
def test_username_length_boundary(admin):
    payload = data.user(username=(config.USER_PREFIX + "x" * 60)[:config.LEN["username"]])
    obj = created(admin.post("/api/users", json=payload))
    assert len(obj["username"]) == config.LEN["username"]
    admin.delete("/api/users/{}".format(obj["id"]))


@pytest.mark.case("USER-016")
@pytest.mark.xfail(reason="后端缺陷 D-01：用户名超长未做长度校验，返回 500，应为 400", strict=True)
def test_username_over_length(admin):
    payload = data.user(username=(config.USER_PREFIX + "x" * 60)[:config.LEN["username"] + 1])
    error(admin.post("/api/users", json=payload), 400)


# ===================================================================== 列表与详情
@pytest.mark.case("USER-017")
def test_list_admin_sees_all_sorted(admin, account):
    rows = ok(admin.get("/api/users"))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids), "用户列表按 id 升序"
    assert account["id"] in ids
    assert all(no_keys(r, SECRET_KEYS) is None for r in rows)


@pytest.mark.case("USER-018")
def test_list_user_sees_only_collaborators(client1, admin, factory, project_a, project_b):
    peer = factory.user(project_ids=[project_a["id"]])       # 同项目协作成员
    stranger = factory.user(project_ids=[project_b["id"]])   # 不同项目
    rows = ok(client1.get("/api/users"))
    ids = {r["id"] for r in rows}
    assert peer["id"] in ids, "共用项目的非管理员应可见"
    assert stranger["id"] not in ids
    assert all(r["role"] != "ADMIN" for r in rows), "普通用户看不到管理员"
    assert client1.user_id in ids, "协作列表包含自己"


@pytest.mark.case("USER-019")
def test_list_zero_bound_user_empty(client_empty):
    assert ok(client_empty.get("/api/users")) == [], "未绑定任何项目的用户看不到任何成员"


@pytest.mark.case("USER-020")
def test_detail_admin(admin, account):
    obj = ok(admin.get("/api/users/{}".format(account["id"])))
    keys(obj, VIEW_KEYS)
    no_keys(obj, SECRET_KEYS)
    assert obj["username"] == account["username"]


@pytest.mark.case("USER-021")
def test_detail_user_cannot_see_admin(client1, admin):
    error(client1.get("/api/users/{}".format(admin.user_id)), 404, "用户不存在")


@pytest.mark.case("USER-022")
def test_detail_user_cannot_see_stranger(client1, factory, project_b):
    stranger = factory.user(project_ids=[project_b["id"]])
    error(client1.get("/api/users/{}".format(stranger["id"])), 404, "用户不存在")


@pytest.mark.case("USER-023")
def test_detail_user_can_see_collaborator(client1, factory, project_a):
    peer = factory.user(project_ids=[project_a["id"]])
    obj = ok(client1.get("/api/users/{}".format(peer["id"])))
    assert obj["id"] == peer["id"]


@pytest.mark.case("USER-024")
def test_detail_not_found(admin):
    error(admin.get("/api/users/99999999"), 404, "用户不存在: id=99999999")


# ===================================================================== 编辑
@pytest.mark.case("USER-025")
def test_update_fields(admin, account, project_a):
    payload = data.user(username=account["username"], displayName="  新显示名  ",
                        role="USER", project_ids=[project_a["id"]])
    obj = ok(admin.put("/api/users/{}".format(account["id"]), json=payload), "编辑用户")
    assert obj["displayName"] == "新显示名"
    assert _project_ids(obj) == {project_a["id"]}
    same_time(obj["createdAt"], account["view"]["createdAt"], "创建时间不变")


@pytest.mark.case("USER-026")
def test_update_username_duplicate(admin, account, factory):
    other = factory.user()
    payload = data.user(username=other["username"])
    error(admin.put("/api/users/{}".format(account["id"]), json=payload),
          400, "用户名已存在: " + other["username"])


@pytest.mark.case("USER-027")
def test_update_keep_own_username(admin, account):
    payload = data.user(username=account["username"], displayName="保持用户名")
    obj = ok(admin.put("/api/users/{}".format(account["id"]), json=payload))
    assert obj["username"] == account["username"]


@pytest.mark.case("USER-028")
@pytest.mark.parametrize("display", [None, "", "   "], ids=["null", "empty", "blank"])
def test_update_display_name_falls_back(admin, account, display):
    payload = data.user(username=account["username"], displayName=display)
    obj = ok(admin.put("/api/users/{}".format(account["id"]), json=payload))
    assert obj["displayName"] == account["username"]


@pytest.mark.case("USER-029")
def test_update_role_null_keeps_old(admin, factory):
    acct = factory.user(role="ADMIN")
    payload = data.user(username=acct["username"], role=None)
    obj = ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert obj["role"] == "ADMIN", "角色为 null 时保留原值"


@pytest.mark.case("USER-030")
def test_update_enabled_null_means_true(admin, factory):
    """现状确认：enabled 为 Boolean，缺省/null 一律按 true 处理，无法靠省略字段禁用账号。"""
    acct = factory.user()
    payload = data.user(username=acct["username"])
    payload.pop("enabled")
    obj = ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert obj["enabled"] is True


@pytest.mark.case("USER-031")
def test_update_password_revokes_tokens(admin, factory, ip_pool):
    acct = factory.user()
    c = _login(acct, ip_pool())
    old_token = c.token
    payload = data.user(username=acct["username"], password="At#NewPass99")
    ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    unauthorized(c.get("/api/auth/me", token=old_token), "重置口令后旧 token 应立即失效")
    assert db.must_change_flag(acct["username"]) == 0
    fresh = ApiClient(acct["username"], ip=ip_pool())
    assert fresh.login(acct["username"], "At#NewPass99").status_code == 200, "新口令可登录"
    error(fresh.login(acct["username"], acct["password"]), 400, "用户名或密码错误")


@pytest.mark.case("USER-032")
def test_update_password_to_default_sets_flag(admin, factory):
    acct = factory.user()
    payload = data.user(username=acct["username"], password=config.DEFAULT_ADMIN_PASSWORD)
    ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert db.must_change_flag(acct["username"]) == 1, "重置为内置默认口令应重新打强制改密标记"


@pytest.mark.case("USER-033")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_update_blank_password_keeps_old(admin, factory, ip_pool, blank):
    acct = factory.user()
    payload = data.user(username=acct["username"], password=blank)
    ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    c = ApiClient(acct["username"], ip=ip_pool())
    assert c.login(acct["username"], acct["password"]).status_code == 200, "空白口令不应修改原口令"


@pytest.mark.case("USER-034")
def test_update_short_password_rejected(admin, account):
    payload = data.user(username=account["username"], password="123")
    error(admin.put("/api/users/{}".format(account["id"]), json=payload), 400, "密码至少 4 位")


@pytest.mark.case("USER-035")
def test_update_projects_replaces_not_merges(admin, factory, project_a, project_b):
    acct = factory.user(project_ids=[project_a["id"]])
    payload = data.user(username=acct["username"], project_ids=[project_b["id"]])
    obj = ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert _project_ids(obj) == {project_b["id"]}, "绑定关系整体替换而非追加"


@pytest.mark.case("USER-036")
def test_update_without_projects_wipes_bindings(admin, factory, project_a):
    """现状确认：projectIds 缺省即清空全部绑定，前端编辑表单必须回传完整列表。"""
    acct = factory.user(project_ids=[project_a["id"]])
    payload = data.user(username=acct["username"])
    payload.pop("projectIds")
    obj = ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert obj["projects"] == [], "缺省 projectIds 会清空绑定"


@pytest.mark.case("USER-037")
def test_update_disable_revokes_tokens(admin, factory, ip_pool):
    acct = factory.user()
    c = _login(acct, ip_pool())
    old_token = c.token
    payload = data.user(username=acct["username"], enabled=False)
    obj = ok(admin.put("/api/users/{}".format(acct["id"]), json=payload))
    assert obj["enabled"] is False
    unauthorized(c.get("/api/auth/me", token=old_token), "禁用后旧 token 应立即失效")
    error(c.login(acct["username"], acct["password"]), 400, "账号已被禁用")


@pytest.mark.case("USER-038")
def test_update_not_found(admin):
    error(admin.put("/api/users/99999999", json=data.user()), 404, "用户不存在: id=99999999")


# ===================================================================== 删除
@pytest.mark.case("USER-039")
def test_delete_revokes_tokens(admin, factory, ip_pool):
    acct = factory.user()
    c = _login(acct, ip_pool())
    old_token = c.token
    no_content(admin.delete("/api/users/{}".format(acct["id"])), "删除用户")
    unauthorized(c.get("/api/auth/me", token=old_token), "删除后旧 token 应立即失效")
    error(admin.get("/api/users/{}".format(acct["id"])), 404, "用户不存在")
    factory.tracker.forget("user", acct["id"])


@pytest.mark.case("USER-040")
def test_delete_self_rejected(admin):
    error(admin.delete("/api/users/{}".format(admin.user_id)), 400, "不能删除当前登录用户")


@pytest.mark.case("USER-041")
def test_delete_not_found(admin):
    error(admin.delete("/api/users/99999999"), 404, "用户不存在: id=99999999")


@pytest.mark.case("USER-042")
def test_delete_removes_bindings(admin, factory, project_a):
    acct = factory.user(project_ids=[project_a["id"]])
    uid = acct["id"]
    no_content(admin.delete("/api/users/{}".format(uid)))
    assert db.scalar("SELECT COUNT(*) FROM user_projects WHERE user_id=%s", (uid,)) == 0, \
        "删除用户应级联清理项目绑定"
    factory.tracker.forget("user", uid)


# ===================================================================== 权限
@pytest.mark.case("USER-043")
def test_user_cannot_create(client1):
    forbidden(client1.post("/api/users", json=data.user()), "需要管理员权限")


@pytest.mark.case("USER-044")
def test_user_cannot_update(client1, account):
    forbidden(client1.put("/api/users/{}".format(account["id"]), json=data.user()),
              "需要管理员权限")


@pytest.mark.case("USER-045")
def test_user_cannot_delete(client1, account):
    forbidden(client1.delete("/api/users/{}".format(account["id"])), "需要管理员权限")


@pytest.mark.case("USER-046")
def test_users_require_auth(anon):
    unauthorized(anon.get("/api/users"))
    unauthorized(anon.post("/api/users", json=data.user()))
    unauthorized(anon.get("/api/users/1"))