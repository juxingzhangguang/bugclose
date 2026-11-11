# -*- coding: utf-8 -*-
"""权限与数据隔离横切测试：跨模块越权矩阵、身份/绑定变更的即时生效、提权尝试。

各模块自身的权限用例已在 test_bug/requirement/testcase/doc/user/role/project 中覆盖，
本模块只做「同一断言在全部模块上的一致性」与「权限随身份变化即时生效」的横切验证。
"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, no_content, ok, status,
                             unauthorized)
from core.client import ApiClient

pytestmark = pytest.mark.case("PERM")

# 三个 JSON 业务模块：创建 payload 工厂 + 编辑 payload 工厂
JSON_MODULES = [
    ("bug", "/api/bugs", data.bug),
    ("requirement", "/api/requirements", data.requirement),
    ("testcase", "/api/testcases", data.testcase),
]
ALL_LISTS = ["/api/bugs", "/api/requirements", "/api/testcases", "/api/docs"]


def _foreign_objects(admin, factory, project_id):
    """在指定项目下各建一条数据，返回 [(名称, 列表路径, 对象)]。"""
    out = []
    for name, path, make in JSON_MODULES:
        obj = getattr(factory, name)(admin, project_id)
        out.append((name, path, obj))
    doc = factory.doc(admin, project_id)
    out.append(("doc", "/api/docs", doc))
    return out


def _update_payload(name, obj, project_id):
    if name == "doc":
        return {"title": obj["title"], "category": "TEST", "projectId": project_id}
    for n, _path, factory_fn in JSON_MODULES:
        if n == name:
            payload = factory_fn(project_id, title=obj["title"])
            if n == "bug":
                payload["severity"] = obj["severity"]
                payload["priority"] = obj["priority"]
            return payload
    raise AssertionError("未知模块 " + name)


def _login_as(account, ip):
    c = ApiClient(account["username"], ip=ip)
    resp = c.login(account["username"], account["password"])
    assert resp.status_code == 200, "测试账号登录失败: {}".format(resp.text[:200])
    return c


def _detail_get(name, path, obj):
    """文档模块没有 GET /api/docs/{id} 详情端点（只有列表），用版本历史做读权限断言。"""
    if name == "doc":
        return "{}/{}/versions".format(path, obj["id"])
    return "{}/{}".format(path, obj["id"])


def _row(admin, name, path, obj):
    if name == "doc":
        return next(r for r in ok(admin.get(path)) if r["id"] == obj["id"])
    return ok(admin.get("{}/{}".format(path, obj["id"])))


def _edit_user(username, **kw):
    """编辑用户但不改口令。

    UserService.update 只要 password 非空白就会 rehash 并 revokeByUser，
    带上默认口令会把被测账号的旧 token 全部吊销，权限断言就变成 401 而非 403。
    """
    payload = data.user(username=username, **kw)
    payload.pop("password")
    return payload


# ===================================================================== 越权矩阵
@pytest.mark.case("PERM-001")
def test_read_matrix(admin, client1, factory, project_b):
    """四个模块的详情接口对未绑定项目一律 403。"""
    for name, path, obj in _foreign_objects(admin, factory, project_b["id"]):
        forbidden(client1.get(_detail_get(name, path, obj)), "无权访问该资源",
                  name + " 详情越权")


@pytest.mark.case("PERM-002")
def test_create_matrix(client1, project_b):
    """四个模块在未绑定项目下创建一律 403。"""
    for name, path, make in JSON_MODULES:
        forbidden(client1.post(path, json=make(project_b["id"])),
                  "无权操作该项目的数据", name + " 创建越权")
    resp = client1.post("/api/docs",
                        data={"title": "AT越权文档", "projectId": str(project_b["id"])},
                        files=[data.doc_file("txt")])
    forbidden(resp, "无权操作该项目的数据", "doc 创建越权")


@pytest.mark.case("PERM-003")
def test_update_matrix(admin, client1, factory, project_b):
    for name, path, obj in _foreign_objects(admin, factory, project_b["id"]):
        payload = _update_payload(name, obj, project_b["id"])
        forbidden(client1.put("{}/{}".format(path, obj["id"]), json=payload),
                  "无权", name + " 编辑越权")


@pytest.mark.case("PERM-004")
def test_delete_matrix(admin, client1, factory, project_b):
    for name, path, obj in _foreign_objects(admin, factory, project_b["id"]):
        forbidden(client1.delete("{}/{}".format(path, obj["id"])),
                  "无权访问该资源", name + " 删除越权")
        assert _row(admin, name, path, obj)["id"] == obj["id"], name + " 未被删除"


@pytest.mark.case("PERM-005")
def test_list_isolation_matrix(admin, client1, factory, project_a, project_b):
    """四个模块的列表都只返回绑定项目内的数据。"""
    mine = _foreign_objects(admin, factory, project_a["id"])
    _foreign_objects(admin, factory, project_b["id"])
    for name, path, obj in mine:
        rows = ok(client1.get(path), name + " 列表")
        ids = {r["id"] for r in rows}
        assert obj["id"] in ids, name + " 应能看到自己项目内的数据"
        assert all(r["projectId"] == project_a["id"] for r in rows), \
            name + " 列表混入了未绑定项目的数据"


@pytest.mark.case("PERM-006")
def test_unassigned_invisible_matrix(admin, client1, factory):
    """projectId=null 的数据在四个模块中对普通用户都不可见。"""
    for name, path, make in JSON_MODULES:
        obj = getattr(factory, name)(admin, None)
        forbidden(client1.get("{}/{}".format(path, obj["id"])), "无权访问该资源", name)
        assert obj["id"] not in {r["id"] for r in ok(client1.get(path))}, name + " 列表泄露"
    doc = factory.doc(admin, None)
    forbidden(client1.get("/api/docs/{}/versions".format(doc["id"])), "无权访问该资源", "doc")
    assert doc["id"] not in {r["id"] for r in ok(client1.get("/api/docs"))}


@pytest.mark.case("PERM-007")
def test_write_requires_project_matrix(client1):
    """普通用户在四个模块下都必须选择项目（400 而非 403）。"""
    for name, path, make in JSON_MODULES:
        error(client1.post(path, json=make(None)), 400, "请选择所属项目", name)
    resp = client1.post("/api/docs", data={"title": "AT未选项目文档"},
                        files=[data.doc_file("txt")])
    error(resp, 400, "请选择所属项目", "doc")


@pytest.mark.case("PERM-008")
def test_admin_endpoints_matrix(client1, factory, project_a):
    """管理类写端点对普通用户一律 403。"""
    acct = factory.user()
    role = factory.role()
    cases = [
        ("POST", "/api/users", data.user()),
        ("PUT", "/api/users/{}".format(acct["id"]), data.user()),
        ("DELETE", "/api/users/{}".format(acct["id"]), None),
        ("POST", "/api/roles", data.role()),
        ("PUT", "/api/roles/{}".format(role["id"]), {"name": "越权改名"}),
        ("DELETE", "/api/roles/{}".format(role["id"]), None),
        ("POST", "/api/projects", data.project()),
        ("PUT", "/api/projects/{}".format(project_a["id"]), data.project()),
        ("DELETE", "/api/projects/{}".format(project_a["id"]), None),
    ]
    for method, path, payload in cases:
        resp = client1.request(method, path, json=payload)
        forbidden(resp, "需要管理员权限", "{} {}".format(method, path))


@pytest.mark.case("PERM-009")
def test_readonly_endpoints_open_to_user(client1):
    """只读端点登录即可访问，不限管理员。"""
    for path in ("/api/projects", "/api/roles", "/api/users", "/api/dashboard/statistics"):
        status(client1.get(path), 200, path + " 应对普通用户开放")


@pytest.mark.case("PERM-010")
def test_anonymous_matrix(anon):
    """全部业务与管理端点对匿名请求一律 401。"""
    paths = ["/api/auth/me", "/api/projects", "/api/bugs", "/api/requirements",
             "/api/testcases", "/api/docs", "/api/users", "/api/roles",
             "/api/dashboard/statistics", "/api/uploads"]
    for path in paths:
        unauthorized(anon.get(path), "GET " + path)
    for path in paths[1:]:
        unauthorized(anon.post(path, json={}), "POST " + path)


@pytest.mark.case("PERM-011")
def test_revoked_token_matrix(admin, factory, ip_pool):
    """账号被删除后，其旧 token 在所有端点上都失效。"""
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    token = c.token
    no_content(admin.delete("/api/users/{}".format(acct["id"])))
    factory.tracker.forget("user", acct["id"])
    stale = ApiClient("stale", token=token, ip=ip_pool())
    for path in ("/api/auth/me", "/api/projects", "/api/bugs", "/api/users",
                 "/api/roles", "/api/dashboard/statistics"):
        unauthorized(stale.get(path), "吊销后 GET " + path)


# ===================================================================== 权限即时生效
@pytest.mark.case("PERM-012")
def test_unbind_takes_effect_immediately(admin, factory, project_a, ip_pool):
    """解绑项目后无需重新登录，旧 token 立刻失去该项目数据权限。"""
    acct = factory.user(project_ids=[project_a["id"]])
    c = _login_as(acct, ip_pool())
    bug = factory.bug(admin, project_a["id"])
    ok(c.get("/api/bugs/{}".format(bug["id"])), "解绑前可读")
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=_edit_user(acct["username"], project_ids=[])))
    forbidden(c.get("/api/bugs/{}".format(bug["id"])), "无权访问该资源", "解绑后应立即不可读")
    assert ok(c.get("/api/bugs")) == [], "解绑后列表应为空"


@pytest.mark.case("PERM-013")
def test_new_binding_takes_effect_immediately(admin, factory, project_a, ip_pool):
    """新增绑定后无需重新登录，旧 token 立刻获得该项目数据权限。"""
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    bug = factory.bug(admin, project_a["id"])
    forbidden(c.get("/api/bugs/{}".format(bug["id"])), "无权访问该资源", "绑定前不可读")
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=_edit_user(acct["username"], project_ids=[project_a["id"]])))
    ok(c.get("/api/bugs/{}".format(bug["id"])), "绑定后应立即可读")


@pytest.mark.case("PERM-014")
def test_demotion_takes_effect_immediately(admin, factory, ip_pool):
    """管理员被降级后，旧 token 立刻失去管理权限与全量可见性。"""
    acct = factory.user(role="ADMIN")
    c = _login_as(acct, ip_pool())
    assert c.me["allProjects"] is True
    role = created(c.post("/api/roles", json=data.role()), "降级前可建角色")
    no_content(admin.delete("/api/roles/{}".format(role["id"])))
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=_edit_user(acct["username"], role="USER")))
    forbidden(c.post("/api/roles", json=data.role()), "需要管理员权限", "降级后不可建角色")
    me = ok(c.fetch_me())
    assert me["role"] == "USER" and me["allProjects"] is False


@pytest.mark.case("PERM-015")
def test_promotion_takes_effect_immediately(admin, factory, project_b, ip_pool):
    """普通用户被提升为管理员后，旧 token 立刻获得全量可见性。"""
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    bug = factory.bug(admin, project_b["id"])
    forbidden(c.get("/api/bugs/{}".format(bug["id"])), "无权访问该资源")
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=_edit_user(acct["username"], role="ADMIN")))
    ok(c.get("/api/bugs/{}".format(bug["id"])), "提升后应可见任意项目数据")
    role = created(c.post("/api/roles", json=data.role()), "提升后可建角色")
    no_content(admin.delete("/api/roles/{}".format(role["id"])))


@pytest.mark.case("PERM-016")
def test_disable_blocks_all_endpoints(admin, factory, project_a, ip_pool):
    acct = factory.user(project_ids=[project_a["id"]])
    c = _login_as(acct, ip_pool())
    bug = factory.bug(admin, project_a["id"])
    ok(c.get("/api/bugs/{}".format(bug["id"])))
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=_edit_user(acct["username"], enabled=False,
                                 project_ids=[project_a["id"]])))
    for path in ("/api/auth/me", "/api/projects", "/api/bugs", "/api/dashboard/statistics"):
        unauthorized(c.get(path), "禁用后 GET " + path)


# ===================================================================== 提权与迁移
@pytest.mark.case("PERM-017")
def test_user_cannot_self_promote(admin, factory, ip_pool):
    """普通用户不能通过用户编辑接口给自己提权。"""
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    forbidden(c.put("/api/users/{}".format(acct["id"]),
                    json=data.user(username=acct["username"], role="ADMIN")),
              "需要管理员权限")
    assert ok(admin.get("/api/users/{}".format(acct["id"])))["role"] == "USER", "角色未被篡改"


@pytest.mark.case("PERM-018")
def test_user_cannot_reset_others_password(admin, factory, ip_pool):
    peer = factory.user()
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    forbidden(c.put("/api/users/{}".format(peer["id"]),
                    json=data.user(username=peer["username"], password="Hacked#123")),
              "需要管理员权限")
    fresh = ApiClient(peer["username"], ip=ip_pool())
    assert fresh.login(peer["username"], peer["password"]).status_code == 200, "原口令仍有效"


@pytest.mark.case("PERM-019")
def test_change_password_only_self(admin, factory, ip_pool):
    """改密接口只作用于当前登录用户，无法借他人身份改密。"""
    peer = factory.user(password="Peer#Original1")   # 与 acct 口令不同，避免误判为「原密码正确」
    acct = factory.user()
    c = _login_as(acct, ip_pool())
    error(c.change_password(peer["password"], "Whatever#123"), 400, "原密码错误")
    fresh = ApiClient(peer["username"], ip=ip_pool())
    assert fresh.login(peer["username"], peer["password"]).status_code == 200


@pytest.mark.case("PERM-020")
@pytest.mark.parametrize("name,path", [(n, p) for n, p, _ in JSON_MODULES])
def test_not_found_before_forbidden(admin, client1, factory, project_b, name, path):
    """现状确认：先判存在再判权限，不存在的 id 返回 404、存在但越权返回 403。

    风险：可借状态码差异枚举出哪些 id 真实存在（存在性披露）。
    """
    obj = getattr(factory, name)(admin, project_b["id"])
    error(client1.get("{}/99999999".format(path)), 404, "不存在")
    forbidden(client1.get("{}/{}".format(path, obj["id"])), "无权访问该资源", "存在但越权")


@pytest.mark.case("PERM-021")
def test_cannot_move_foreign_data_into_own_project(admin, client1, factory, project_a, project_b):
    """不能把未绑定项目的数据「搬」进自己的项目来绕过隔离。"""
    for name, path, obj in _foreign_objects(admin, factory, project_b["id"]):
        payload = _update_payload(name, obj, project_a["id"])
        forbidden(client1.put("{}/{}".format(path, obj["id"]), json=payload),
                  "无权", name + " 跨项目搬迁")
        assert _row(admin, name, path, obj)["projectId"] == project_b["id"]


@pytest.mark.case("PERM-022")
def test_cannot_move_own_data_out(admin, client1, factory, project_a, project_b):
    """不能把自己项目的数据迁到未绑定项目（目标项目写权限校验）。"""
    for name, path, make in JSON_MODULES:
        obj = getattr(factory, name)(admin, project_a["id"])
        forbidden(client1.put("{}/{}".format(path, obj["id"]),
                              json=make(project_b["id"], title=obj["title"])),
                  "无权操作该项目的数据", name)
    doc = factory.doc(admin, project_a["id"])
    forbidden(client1.put("/api/docs/{}".format(doc["id"]),
                          json={"title": doc["title"], "projectId": project_b["id"]}),
              "无权操作该项目的数据", "doc")


@pytest.mark.case("PERM-023")
def test_subresource_endpoints_isolated(admin, client1, factory, project_b):
    """子资源端点（状态流转/用例执行/文档版本/下载）同样受数据隔离约束。"""
    bug = factory.bug(admin, project_b["id"])
    forbidden(client1.put("/api/bugs/{}/status".format(bug["id"]),
                        json={"status": "IN_PROGRESS"}), "无权访问该资源", "缺陷流转")
    case = factory.testcase(admin, project_b["id"])
    forbidden(client1.put("/api/testcases/{}/execute".format(case["id"]),
                        json={"status": "PASS"}), "无权访问该资源", "用例执行")
    doc = factory.doc(admin, project_b["id"])
    forbidden(client1.get("/api/docs/{}/versions".format(doc["id"])), "无权访问该资源", "版本历史")
    forbidden(client1.get("/api/docs/{}/versions/{}/download".format(doc["id"], doc["latestVersionId"])),
              "无权访问该资源", "版本下载")
    forbidden(client1.post("/api/docs/{}/versions".format(doc["id"]),
                           files=[data.doc_file("txt")]), "无权", "新增版本")


@pytest.mark.case("PERM-024")
def test_admin_sees_everything(admin, factory, project_a, project_b):
    """对照组：管理员不受项目隔离限制，且能看到未关联项目的数据。"""
    a = _foreign_objects(admin, factory, project_a["id"])
    b = _foreign_objects(admin, factory, project_b["id"])
    for name, path, obj in a + b:
        ok(admin.get(_detail_get(name, path, obj)), name + " 管理员应可读")
    orphan = factory.bug(admin, None)
    ok(admin.get("/api/bugs/{}".format(orphan["id"])), "管理员可读未关联项目的数据")