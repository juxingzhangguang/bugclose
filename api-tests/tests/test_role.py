# -*- coding: utf-8 -*-
"""角色管理接口测试：/api/roles（编码规范、内置角色保护、引用计数、权限）。"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,
                             rejected, same_time, unauthorized)

pytestmark = pytest.mark.case("ROLE")

ROLE_KEYS = ["id", "code", "name", "description", "builtin", "userCount", "createdAt"]


def _find(admin, role_id):
    rows = ok(admin.get("/api/roles"))
    return next(r for r in rows if r["id"] == role_id)


def _builtin(admin, code):
    rows = ok(admin.get("/api/roles"))
    return next(r for r in rows if r["code"] == code)


# ===================================================================== 创建
@pytest.mark.case("ROLE-001")
def test_create_role(admin, factory):
    role = factory.role(name="测试角色", description="角色描述")
    keys(role, ROLE_KEYS, "角色视图")
    assert role["builtin"] is False
    assert role["userCount"] == 0
    assert role["name"] == "测试角色"
    assert role["createdAt"]


@pytest.mark.case("ROLE-002")
def test_code_normalized(admin, factory):
    raw = data.short_code("R").lower()
    role = factory.role(code="  " + raw + "  ")
    assert role["code"] == raw.upper(), "编码应去首尾空格并转大写"


@pytest.mark.case("ROLE-003")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_code_required(admin, blank):
    payload = data.role()
    payload["code"] = blank
    error(admin.post("/api/roles", json=payload), 400, "角色编码不能为空")


@pytest.mark.case("ROLE-004")
@pytest.mark.parametrize("code", ["1ABC", "_ABC", "A-B", "A B", "A.B", "角色", "A" * 21])
def test_code_pattern_rejected(admin, code):
    error(admin.post("/api/roles", json=data.role(code=code)),
          400, "角色编码须为 1-20 位大写字母/数字/下划线，且以字母开头")


@pytest.mark.case("ROLE-005")
@pytest.mark.parametrize("code", ["A", "A1", "A_B", "A" * 20, "A1_2B"])
def test_code_pattern_accepted(admin, code):
    payload = data.role(code=code)
    resp = admin.post("/api/roles", json=payload)
    obj = created(resp, "合法编码 " + code)
    assert obj["code"] == code
    no_content(admin.delete("/api/roles/{}".format(obj["id"])))


@pytest.mark.case("ROLE-006")
def test_code_duplicate_case_insensitive(admin, factory):
    role = factory.role()
    error(admin.post("/api/roles", json=data.role(code=role["code"].lower())),
          400, "角色编码已存在: " + role["code"])


@pytest.mark.case("ROLE-007")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_name_required(admin, blank):
    payload = data.role()
    payload["name"] = blank
    error(admin.post("/api/roles", json=payload), 400, "角色名称不能为空")


@pytest.mark.case("ROLE-008")
def test_text_fields_trimmed(admin, factory):
    role = factory.role(name="  带空格角色  ", description="  带空格描述  ")
    assert role["name"] == "带空格角色"
    assert role["description"] == "带空格描述"


@pytest.mark.case("ROLE-009")
def test_description_optional(admin, factory):
    role = factory.role(description=None)
    assert role["description"] is None


@pytest.mark.case("ROLE-010")
def test_create_user_count_hardcoded_zero(admin, factory):
    """现状确认：创建响应的 userCount 恒为 0（服务层写死），列表接口才返回真实引用数。"""
    role = factory.role()
    assert role["userCount"] == 0
    assert _find(admin, role["id"])["userCount"] == 0


# ===================================================================== 列表
@pytest.mark.case("ROLE-011")
def test_list_contains_builtin_and_sorted(admin, factory):
    role = factory.role()
    rows = ok(admin.get("/api/roles"))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids), "角色列表按 id 升序"
    codes = {r["code"] for r in rows}
    assert {"ADMIN", "USER"} <= codes, "内置角色必须存在"
    assert role["code"] in codes
    for r in rows:
        keys(r, ROLE_KEYS)
    assert _builtin(admin, "ADMIN")["builtin"] is True
    assert _builtin(admin, "USER")["builtin"] is True


@pytest.mark.case("ROLE-012")
def test_list_user_count_tracks_references(admin, factory):
    role = factory.role()
    assert _find(admin, role["id"])["userCount"] == 0
    acct = factory.user(role=role["code"])
    assert _find(admin, role["id"])["userCount"] == 1, "被用户引用后计数应加 1"
    no_content(admin.delete("/api/users/{}".format(acct["id"])))
    factory.tracker.forget("user", acct["id"])
    assert _find(admin, role["id"])["userCount"] == 0, "用户删除后计数应回落"


@pytest.mark.case("ROLE-013")
def test_list_visible_to_normal_user(client1):
    rows = ok(client1.get("/api/roles"))
    assert {"ADMIN", "USER"} <= {r["code"] for r in rows}, "角色列表登录即可见，不限管理员"


# ===================================================================== 编辑
@pytest.mark.case("ROLE-014")
def test_update_name_and_description(admin, factory):
    role = factory.role()
    obj = ok(admin.put("/api/roles/{}".format(role["id"]),
                       json={"name": "  新角色名  ", "description": "  新描述  "}), "编辑角色")
    assert obj["name"] == "新角色名"
    assert obj["description"] == "新描述"
    assert obj["code"] == role["code"]
    same_time(obj["createdAt"], role["createdAt"], "创建时间不变")


@pytest.mark.case("ROLE-015")
def test_update_cannot_change_code(admin, factory):
    role = factory.role()
    obj = ok(admin.put("/api/roles/{}".format(role["id"]),
                       json={"code": "IGNORED_CODE", "name": role["name"]}))
    assert obj["code"] == role["code"], "编辑接口忽略 code，编码不可变更"


@pytest.mark.case("ROLE-016")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_update_name_required(admin, factory, blank):
    role = factory.role()
    error(admin.put("/api/roles/{}".format(role["id"]), json={"name": blank}),
          400, "角色名称不能为空")


@pytest.mark.case("ROLE-017")
def test_update_description_null_clears(admin, factory):
    role = factory.role(description="原描述")
    obj = ok(admin.put("/api/roles/{}".format(role["id"]),
                       json={"name": role["name"], "description": None}))
    assert obj["description"] is None


@pytest.mark.case("ROLE-018")
def test_update_builtin_role_not_rejected(admin):
    """内置角色允许改名（服务层无 builtin 守卫）。

    为避免污染真实数据，这里用「原值回写」做无副作用验证。
    """
    role = _builtin(admin, "USER")
    obj = ok(admin.put("/api/roles/{}".format(role["id"]),
                       json={"name": role["name"], "description": role["description"]}))
    assert obj["name"] == role["name"] and obj["builtin"] is True


@pytest.mark.case("ROLE-019")
def test_update_not_found(admin):
    error(admin.put("/api/roles/99999999", json={"name": "x"}), 404, "角色不存在: id=99999999")


# ===================================================================== 删除
@pytest.mark.case("ROLE-020")
def test_delete_unused_role(admin, factory):
    role = factory.role()
    no_content(admin.delete("/api/roles/{}".format(role["id"])), "删除角色")
    assert role["id"] not in {r["id"] for r in ok(admin.get("/api/roles"))}
    factory.tracker.forget("role", role["id"])


@pytest.mark.case("ROLE-021")
@pytest.mark.parametrize("code", ["ADMIN", "USER"])
def test_delete_builtin_rejected(admin, code):
    role = _builtin(admin, code)
    error(admin.delete("/api/roles/{}".format(role["id"])), 400, "内置角色不可删除")
    assert _builtin(admin, code)["id"] == role["id"], "内置角色未被删除"


@pytest.mark.case("ROLE-022")
def test_delete_referenced_role_rejected(admin, factory):
    role = factory.role()
    acct = factory.user(role=role["code"])
    error(admin.delete("/api/roles/{}".format(role["id"])),
          400, "该角色已被 1 个用户使用，无法删除")
    no_content(admin.delete("/api/users/{}".format(acct["id"])))
    factory.tracker.forget("user", acct["id"])


@pytest.mark.case("ROLE-023")
def test_delete_after_unbinding(admin, factory):
    role = factory.role()
    acct = factory.user(role=role["code"])
    ok(admin.put("/api/users/{}".format(acct["id"]),
                 json=data.user(username=acct["username"], role="USER")))
    no_content(admin.delete("/api/roles/{}".format(role["id"])), "解绑后应可删除")
    factory.tracker.forget("role", role["id"])


@pytest.mark.case("ROLE-024")
def test_delete_not_found(admin):
    error(admin.delete("/api/roles/99999999"), 404, "角色不存在: id=99999999")


@pytest.mark.case("ROLE-025")
def test_user_role_free_text_not_validated(admin, factory):
    """现状确认：用户.role 是自由字符串，不校验是否存在于角色表。"""
    acct = factory.user(role="AT_NOT_A_ROLE")
    assert acct["view"]["role"] == "AT_NOT_A_ROLE"
    assert "AT_NOT_A_ROLE" not in {r["code"] for r in ok(admin.get("/api/roles"))}


# ===================================================================== 权限
@pytest.mark.case("ROLE-026")
def test_user_cannot_create(client1):
    forbidden(client1.post("/api/roles", json=data.role()), "需要管理员权限")


@pytest.mark.case("ROLE-027")
def test_user_cannot_update(client1, factory):
    role = factory.role()
    forbidden(client1.put("/api/roles/{}".format(role["id"]), json={"name": "越权改名"}),
              "需要管理员权限")


@pytest.mark.case("ROLE-028")
def test_user_cannot_delete(client1, factory):
    role = factory.role()
    forbidden(client1.delete("/api/roles/{}".format(role["id"])), "需要管理员权限")


@pytest.mark.case("ROLE-029")
def test_roles_require_auth(anon):
    unauthorized(anon.get("/api/roles"))
    unauthorized(anon.post("/api/roles", json=data.role()))


@pytest.mark.case("ROLE-030")
def test_name_length_boundary(admin):
    payload = data.role(name="角" * config.LEN["role_name"])
    obj = created(admin.post("/api/roles", json=payload))
    assert len(obj["name"]) == config.LEN["role_name"]
    no_content(admin.delete("/api/roles/{}".format(obj["id"])))


@pytest.mark.case("ROLE-031")
@pytest.mark.xfail(reason="后端缺陷 D-01：角色名称超长未做长度校验，返回 500，应为 400", strict=True)
def test_name_over_length(admin):
    payload = data.role(name="角" * (config.LEN["role_name"] + 1))
    resp = admin.post("/api/roles", json=payload)
    rejected(resp, "超长名称")
    assert resp.status_code == 400