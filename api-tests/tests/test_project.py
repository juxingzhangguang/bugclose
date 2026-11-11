# -*- coding: utf-8 -*-
"""项目管理接口测试：/api/projects（增删改查为管理员专用，列表按可见范围过滤）。"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,  # noqa: F401
                             same_time, status, unauthorized)

pytestmark = pytest.mark.case("PROJ")


def _find(admin, project_id):
    rows = ok(admin.get("/api/projects"), "项目列表")
    for row in rows:
        if row["id"] == project_id:
            return row
    return None


# --------------------------------------------------------------------- 创建
@pytest.mark.case("PROJ-001")
def test_create_project(admin, tracker):
    payload = data.project()
    obj = created(admin.post("/api/projects", json=payload), "创建项目")
    tracker.add("project", obj["id"], lambda: admin.delete("/api/projects/{}".format(obj["id"])))
    keys(obj, ["id", "name", "code", "description", "createdAt"], "项目响应")
    assert obj["name"] == payload["name"]
    assert obj["code"] == payload["code"].upper()
    assert obj["createdAt"], "应返回创建时间"
    assert "bugCount" not in obj, "创建响应返回实体，不含 bugCount"


@pytest.mark.case("PROJ-002")
def test_code_normalized(admin, factory):
    obj = factory.project(code="  at_" + config.RUN_ID.lower() + "_n  ")
    assert obj["code"] == ("AT_" + config.RUN_ID + "_N"), "编号应去首尾空格并转大写"


@pytest.mark.case("PROJ-003")
@pytest.mark.parametrize("code", [None, "", "   "], ids=["null", "empty", "blank"])
def test_blank_code_becomes_null(admin, factory, code):
    obj = factory.project(code=code)
    assert obj["code"] is None, "空白编号应规范化为 null"


@pytest.mark.case("PROJ-004")
@pytest.mark.parametrize("name", [None, "", "   "], ids=["null", "empty", "blank"])
def test_create_blank_name(admin, name):
    payload = data.project()
    payload["name"] = name          # 显式覆盖，None 也要原样发出
    error(admin.post("/api/projects", json=payload), 400, "项目名称不能为空")


@pytest.mark.case("PROJ-005")
def test_create_duplicate_name(admin, factory):
    obj = factory.project()
    error(admin.post("/api/projects", json=data.project(name=obj["name"])), 400, "项目名称已存在")


@pytest.mark.case("PROJ-006")
def test_create_duplicate_code(admin, factory):
    obj = factory.project()
    error(admin.post("/api/projects", json=data.project(code=obj["code"].lower())),
          400, "项目编号已存在", "编号大小写不敏感")


@pytest.mark.case("PROJ-007")
def test_name_trimmed(admin, factory):
    raw = config.PROJECT_PREFIX + data.uniq("T")
    obj = factory.project(name="  " + raw + "  ")
    assert obj["name"] == raw


@pytest.mark.case("PROJ-027")
def test_name_length_boundary(admin, factory, tracker):
    ok_name = config.PROJECT_PREFIX + ("L" * (config.LEN["project_name"] - len(config.PROJECT_PREFIX)))
    obj = factory.project(name=ok_name, code=None)
    assert len(obj["name"]) == config.LEN["project_name"]


@pytest.mark.case("PROJ-028")
@pytest.mark.xfail(reason="后端缺陷 D-01：名称超长未做长度校验，落库触发完整性异常返回 500，应为 400", strict=True)
def test_name_over_length_rejected_with_400(admin):
    payload = data.project(name="N" * (config.LEN["project_name"] + 1), code=None)
    error(admin.post("/api/projects", json=payload), 400, "项目名称")


# --------------------------------------------------------------------- 列表
@pytest.mark.case("PROJ-008")
def test_bug_count_tracks_bugs(admin, factory):
    proj = factory.project()
    assert _find(admin, proj["id"])["bugCount"] == 0
    bug = factory.bug(admin, proj["id"])
    assert _find(admin, proj["id"])["bugCount"] == 1
    no_content(admin.delete("/api/bugs/{}".format(bug["id"])))
    assert _find(admin, proj["id"])["bugCount"] == 0


@pytest.mark.case("PROJ-009")
def test_list_sorted_by_created_at(admin, factory):
    factory.project()
    factory.project()
    rows = ok(admin.get("/api/projects"))
    stamps = [r["createdAt"] for r in rows]
    assert stamps == sorted(stamps), "项目列表应按创建时间升序"


@pytest.mark.case("PROJ-024")
def test_user_sees_only_bound_projects(client1, project_a, project_b):
    rows = ok(client1.get("/api/projects"), "普通用户项目列表")
    ids = {r["id"] for r in rows}
    assert project_a["id"] in ids
    assert project_b["id"] not in ids, "未绑定项目不应出现在列表中"


@pytest.mark.case("PROJ-025")
def test_list_requires_auth(anon):
    unauthorized(anon.get("/api/projects"))


@pytest.mark.case("PROJ-026")
def test_no_detail_endpoint(admin, project_a):
    resp = admin.get("/api/projects/{}".format(project_a["id"]))
    assert resp.status_code == 405, "未提供 GET /api/projects/{id}，应返回 405"


# --------------------------------------------------------------------- 编辑
@pytest.mark.case("PROJ-010")
def test_update_project(admin, factory):
    obj = factory.project()
    payload = data.project(name=config.PROJECT_PREFIX + data.uniq("U"), code=None, description="改后描述")
    body = ok(admin.put("/api/projects/{}".format(obj["id"]), json=payload), "编辑项目")
    assert body["name"] == payload["name"]
    assert body["description"] == "改后描述"
    assert body["code"] is None
    same_time(body["createdAt"], obj["createdAt"], "创建时间不应被修改")


@pytest.mark.case("PROJ-011")
def test_update_duplicate_name(admin, factory):
    a = factory.project()
    b = factory.project()
    error(admin.put("/api/projects/{}".format(b["id"]), json=data.project(name=a["name"])),
          400, "项目名称已存在")


@pytest.mark.case("PROJ-012")
def test_update_duplicate_code(admin, factory):
    a = factory.project()
    b = factory.project()
    error(admin.put("/api/projects/{}".format(b["id"]), json=data.project(code=a["code"])),
          400, "项目编号已存在")


@pytest.mark.case("PROJ-013")
def test_update_keep_own_name_and_code(admin, factory):
    obj = factory.project()
    body = ok(admin.put("/api/projects/{}".format(obj["id"]),
                        json={"name": obj["name"], "code": obj["code"], "description": "自身不冲突"}))
    assert body["name"] == obj["name"]
    assert body["code"] == obj["code"]


@pytest.mark.case("PROJ-014")
def test_update_missing_project(admin):
    error(admin.put("/api/projects/99999999", json=data.project()), 404, "项目不存在")


# --------------------------------------------------------------------- 删除与关联守卫
@pytest.mark.case("PROJ-015")
def test_delete_empty_project(admin, factory, tracker):
    obj = factory.project()
    no_content(admin.delete("/api/projects/{}".format(obj["id"])), "删除空项目")
    tracker.forget("project", obj["id"])
    assert _find(admin, obj["id"]) is None


@pytest.mark.case("PROJ-016")
def test_delete_with_bugs_rejected(admin, factory):
    proj = factory.project()
    factory.bug(admin, proj["id"])
    msg = error(admin.delete("/api/projects/{}".format(proj["id"])), 400, "个 Bug，请先处理后再删除")
    assert "1" in msg


@pytest.mark.case("PROJ-017")
def test_delete_with_requirements_rejected(admin, factory):
    proj = factory.project()
    factory.requirement(admin, proj["id"])
    error(admin.delete("/api/projects/{}".format(proj["id"])), 400, "个需求，请先处理后再删除")


@pytest.mark.case("PROJ-018")
def test_delete_with_testcases_rejected(admin, factory):
    proj = factory.project()
    factory.testcase(admin, proj["id"])
    error(admin.delete("/api/projects/{}".format(proj["id"])), 400, "个测试用例，请先处理后再删除")


@pytest.mark.case("PROJ-019")
def test_delete_with_docs_rejected(admin, factory):
    proj = factory.project()
    factory.doc(admin, proj["id"])
    error(admin.delete("/api/projects/{}".format(proj["id"])), 400, "个文档，请先处理后再删除")


@pytest.mark.case("PROJ-029")
def test_guard_order_bug_first(admin, factory):
    proj = factory.project()
    factory.bug(admin, proj["id"])
    factory.requirement(admin, proj["id"])
    factory.testcase(admin, proj["id"])
    error(admin.delete("/api/projects/{}".format(proj["id"])), 400, "个 Bug",
          "多类关联同时存在时按 Bug→需求→用例→文档 顺序提示")


@pytest.mark.case("PROJ-020")
def test_delete_missing_project(admin):
    error(admin.delete("/api/projects/99999999"), 404, "项目不存在")


# --------------------------------------------------------------------- 权限
@pytest.mark.case("PROJ-021")
def test_user_cannot_create(client1):
    forbidden(client1.post("/api/projects", json=data.project()), "需要管理员权限")


@pytest.mark.case("PROJ-022")
def test_user_cannot_update(client1, project_a):
    forbidden(client1.put("/api/projects/{}".format(project_a["id"]), json=data.project()),
              "需要管理员权限")


@pytest.mark.case("PROJ-023")
def test_user_cannot_delete(client1, project_a):
    forbidden(client1.delete("/api/projects/{}".format(project_a["id"])), "需要管理员权限")