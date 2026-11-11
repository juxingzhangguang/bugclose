# -*- coding: utf-8 -*-
"""需求管理接口测试：/api/requirements（增删改查、筛选搜索、项目校验、权限隔离）。"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,
                             rejected, same_time, unauthorized)

pytestmark = pytest.mark.case("REQ")

REQ_FIELDS = ["id", "seq", "projectId", "title", "description", "period", "module",
              "priority", "status", "proposer", "assignee", "createdAt", "updatedAt"]


@pytest.fixture
def proj(factory):
    """每个用例独享一个空项目，保证 seq 从 1 起算。"""
    return factory.project()


# ===================================================================== 创建
@pytest.mark.case("REQ-001")
def test_create_defaults(admin, proj):
    payload = data.requirement(proj["id"])
    obj = created(admin.post("/api/requirements", json=payload), "创建需求")
    keys(obj, REQ_FIELDS, "需求响应")
    assert obj["priority"] == "P2", "未传优先级默认 P2"
    assert obj["status"] == "DRAFT", "未传状态默认 DRAFT"
    assert obj["seq"] == 1
    assert obj["projectId"] == proj["id"]
    assert obj["createdAt"] and obj["updatedAt"]


@pytest.mark.case("REQ-002")
def test_seq_increments_within_project(admin, factory, proj):
    seqs = [factory.requirement(admin, proj["id"])["seq"] for _ in range(3)]
    assert seqs == [1, 2, 3]


@pytest.mark.case("REQ-003")
def test_seq_independent_across_projects(admin, factory, proj):
    other = factory.project()
    assert factory.requirement(admin, proj["id"])["seq"] == 1
    assert factory.requirement(admin, proj["id"])["seq"] == 2
    assert factory.requirement(admin, other["id"])["seq"] == 1


@pytest.mark.case("REQ-004")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_title_required(admin, proj, blank):
    payload = data.requirement(proj["id"])
    payload["title"] = blank
    error(admin.post("/api/requirements", json=payload), 400, "需求标题不能为空")


@pytest.mark.case("REQ-005")
def test_title_trimmed(admin, proj):
    obj = created(admin.post("/api/requirements",
                             json=data.requirement(proj["id"], title="  带空格的需求  ")))
    assert obj["title"] == "带空格的需求"


@pytest.mark.case("REQ-006")
def test_create_honours_all_fields(admin, proj):
    payload = data.requirement(proj["id"], title="全字段需求", description="描述内容",
                               period="二期", module="支付模块", priority="P0",
                               status="APPROVED", proposer="提出人", assignee="负责人")
    obj = created(admin.post("/api/requirements", json=payload))
    for field in ("title", "description", "period", "module", "priority",
                  "status", "proposer", "assignee"):
        assert obj[field] == payload[field], "字段 {} 未按入参写入".format(field)


@pytest.mark.case("REQ-007")
def test_client_id_and_seq_ignored(admin, proj):
    obj = created(admin.post("/api/requirements",
                             json=data.requirement(proj["id"], id=999999, seq=88888)))
    assert obj["id"] != 999999
    assert obj["seq"] == 1


@pytest.mark.case("REQ-008")
def test_create_with_missing_project_rejected(admin):
    error(admin.post("/api/requirements", json=data.requirement(99999999)),
          400, "关联项目不存在")


@pytest.mark.case("REQ-009")
def test_admin_can_create_without_project(admin, factory):
    obj = factory.requirement(admin, None)
    assert obj["projectId"] is None
    assert obj["seq"] >= 1, "未关联项目的需求自成一套序号"


@pytest.mark.case("REQ-010")
def test_title_length_boundary(admin, proj):
    obj = created(admin.post("/api/requirements",
                             json=data.requirement(proj["id"], title="R" * config.LEN["req_title"])))
    assert len(obj["title"]) == config.LEN["req_title"]


@pytest.mark.case("REQ-011")
@pytest.mark.xfail(reason="后端缺陷 D-01：标题超长未做长度校验，返回 500，应为 400", strict=True)
def test_title_over_length(admin, proj):
    error(admin.post("/api/requirements",
                     json=data.requirement(proj["id"], title="R" * (config.LEN["req_title"] + 1))),
          400, "标题")


@pytest.mark.case("REQ-012")
@pytest.mark.parametrize("field,expected", [("priority", "P2"), ("status", "DRAFT")])
def test_explicit_null_enum_falls_back_to_default(admin, proj, field, expected):
    """与缺陷模块不同：需求创建对 null 枚举有兜底默认值，不会触发非空约束。"""
    payload = data.requirement(proj["id"])
    payload[field] = None
    obj = created(admin.post("/api/requirements", json=payload))
    assert obj[field] == expected


# ===================================================================== 查询
@pytest.fixture
def dataset(admin, factory, proj):
    rows = [
        factory.requirement(admin, proj["id"], title="Alpha Login Requirement",
                            description="描述里含 gamma 一词", period="一期", module="登录模块",
                            priority="P0", status="DRAFT"),
        factory.requirement(admin, proj["id"], title="Beta Pay Requirement",
                            description="支付需求描述", period="二期", module="支付模块",
                            priority="P1", status="APPROVED"),
        factory.requirement(admin, proj["id"], title="Gamma Report Requirement",
                            description="报表需求描述", period="一期", module="报表模块",
                            priority="P3", status="COMPLETED"),
    ]
    return {"project": proj, "rows": rows}


def _ids(rows):
    return {r["id"] for r in rows}


@pytest.mark.case("REQ-013")
def test_filter_by_project(admin, dataset):
    rows = ok(admin.get("/api/requirements", params={"projectId": dataset["project"]["id"]}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("REQ-014")
@pytest.mark.parametrize("value,index", [("DRAFT", 0), ("APPROVED", 1), ("COMPLETED", 2)])
def test_filter_by_status(admin, dataset, value, index):
    rows = ok(admin.get("/api/requirements",
                        params={"projectId": dataset["project"]["id"], "status": value}))
    assert _ids(rows) == {dataset["rows"][index]["id"]}


@pytest.mark.case("REQ-015")
@pytest.mark.parametrize("value,index", [("P0", 0), ("P1", 1), ("P3", 2)])
def test_filter_by_priority(admin, dataset, value, index):
    rows = ok(admin.get("/api/requirements",
                        params={"projectId": dataset["project"]["id"], "priority": value}))
    assert _ids(rows) == {dataset["rows"][index]["id"]}


@pytest.mark.case("REQ-016")
def test_filter_by_period_exact_and_trim(admin, dataset):
    pid = dataset["project"]["id"]
    rows = ok(admin.get("/api/requirements", params={"projectId": pid, "period": " 一期 "}))
    assert _ids(rows) == {dataset["rows"][0]["id"], dataset["rows"][2]["id"]}, "所属期精确匹配且 trim"
    partial = ok(admin.get("/api/requirements", params={"projectId": pid, "period": "一"}))
    assert partial == [], "所属期不做模糊匹配"


@pytest.mark.case("REQ-017")
def test_keyword_matches_title_and_module_only(admin, dataset):
    pid = dataset["project"]["id"]
    by_title = ok(admin.get("/api/requirements", params={"projectId": pid, "keyword": "Pay"}))
    assert _ids(by_title) == {dataset["rows"][1]["id"]}
    by_module = ok(admin.get("/api/requirements", params={"projectId": pid, "keyword": "报表"}))
    assert _ids(by_module) == {dataset["rows"][2]["id"]}
    by_desc = ok(admin.get("/api/requirements", params={"projectId": pid, "keyword": "支付需求描述"}))
    assert by_desc == [], "关键字不匹配描述字段（与缺陷模块不同）"


@pytest.mark.case("REQ-018")
def test_keyword_case_insensitive(admin, dataset):
    pid = dataset["project"]["id"]
    lower = ok(admin.get("/api/requirements", params={"projectId": pid, "keyword": "alpha"}))
    upper = ok(admin.get("/api/requirements", params={"projectId": pid, "keyword": "ALPHA"}))
    assert _ids(lower) == _ids(upper) == {dataset["rows"][0]["id"]}


@pytest.mark.case("REQ-019")
def test_combined_filters(admin, dataset):
    rows = ok(admin.get("/api/requirements", params={
        "projectId": dataset["project"]["id"], "status": "APPROVED",
        "priority": "P1", "period": "二期", "keyword": "beta"}))
    assert _ids(rows) == {dataset["rows"][1]["id"]}


@pytest.mark.case("REQ-020")
def test_blank_filters_ignored(admin, dataset):
    rows = ok(admin.get("/api/requirements", params={
        "projectId": dataset["project"]["id"], "keyword": "   ", "period": "  "}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("REQ-021")
def test_list_sorted_by_id_asc(admin, dataset):
    rows = ok(admin.get("/api/requirements", params={"projectId": dataset["project"]["id"]}))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids), "需求列表按 id 升序（与缺陷列表的时间倒序不同）"


@pytest.mark.case("REQ-022")
def test_invalid_enum_query_param(admin):
    resp = admin.get("/api/requirements", params={"status": "NOT_A_STATUS"})
    rejected(resp, "非法枚举查询参数")
    assert resp.status_code == 400


@pytest.mark.case("REQ-023")
def test_foreign_project_filter_returns_empty(client1, dataset):
    rows = ok(client1.get("/api/requirements", params={"projectId": dataset["project"]["id"]}))
    assert rows == [], "普通用户按未绑定项目筛选返回空列表，不报错"


# ===================================================================== 详情
@pytest.mark.case("REQ-024")
def test_detail(admin, factory, proj):
    req = factory.requirement(admin, proj["id"], title="详情校验")
    obj = ok(admin.get("/api/requirements/{}".format(req["id"])))
    keys(obj, REQ_FIELDS)
    assert obj["title"] == "详情校验"
    assert obj["id"] == req["id"]


@pytest.mark.case("REQ-025")
def test_detail_not_found(admin):
    error(admin.get("/api/requirements/99999999"), 404, "需求不存在: 99999999")


# ===================================================================== 编辑
@pytest.mark.case("REQ-026")
def test_update_fields(admin, factory, proj):
    req = factory.requirement(admin, proj["id"])
    payload = data.requirement(proj["id"], title="改后需求", description="改后描述",
                               period="三期", module="订单模块", priority="P0",
                               status="IN_PROGRESS", proposer="新提出人", assignee="新负责人")
    obj = ok(admin.put("/api/requirements/{}".format(req["id"]), json=payload), "编辑需求")
    for field in ("title", "description", "period", "module", "priority",
                  "status", "proposer", "assignee"):
        assert obj[field] == payload[field], "字段 {} 未更新".format(field)
    assert obj["seq"] == req["seq"], "同项目编辑不应改变序号"
    same_time(obj["createdAt"], req["createdAt"], "创建时间不变")


@pytest.mark.case("REQ-027")
def test_update_keeps_enum_when_null(admin, factory, proj):
    req = factory.requirement(admin, proj["id"], priority="P0", status="APPROVED")
    payload = data.requirement(proj["id"], title="只改标题")
    payload["priority"] = None
    payload["status"] = None
    obj = ok(admin.put("/api/requirements/{}".format(req["id"]), json=payload))
    assert obj["priority"] == "P0" and obj["status"] == "APPROVED", "枚举为 null 时保留原值"
    assert obj["title"] == "只改标题"


@pytest.mark.case("REQ-028")
def test_update_move_project_reassigns_seq(admin, factory, proj):
    target = factory.project()
    factory.requirement(admin, target["id"])
    req = factory.requirement(admin, proj["id"])
    obj = ok(admin.put("/api/requirements/{}".format(req["id"]),
                       json=data.requirement(target["id"])))
    assert obj["projectId"] == target["id"]
    assert obj["seq"] == 2, "迁移项目后取目标项目最大序号 +1"


@pytest.mark.case("REQ-029")
def test_update_required_validation(admin, factory, proj):
    req = factory.requirement(admin, proj["id"])
    payload = data.requirement(proj["id"])
    payload["title"] = ""
    error(admin.put("/api/requirements/{}".format(req["id"]), json=payload),
          400, "需求标题不能为空")


@pytest.mark.case("REQ-030")
def test_update_clears_nullable_fields(admin, factory, proj):
    req = factory.requirement(admin, proj["id"], description="原描述",
                              period="一期", assignee="张三")
    payload = data.requirement(proj["id"], description=None, period=None, assignee=None)
    obj = ok(admin.put("/api/requirements/{}".format(req["id"]), json=payload))
    assert obj["description"] is None and obj["period"] is None and obj["assignee"] is None


@pytest.mark.case("REQ-031")
def test_update_with_missing_project_rejected(admin, factory, proj):
    req = factory.requirement(admin, proj["id"])
    error(admin.put("/api/requirements/{}".format(req["id"]),
                    json=data.requirement(99999999)), 400, "关联项目不存在")


@pytest.mark.case("REQ-032")
def test_update_not_found(admin, proj):
    error(admin.put("/api/requirements/99999999", json=data.requirement(proj["id"])),
          404, "需求不存在: 99999999")


@pytest.mark.case("REQ-033")
@pytest.mark.parametrize("src,target", [("DRAFT", "COMPLETED"), ("COMPLETED", "DRAFT"),
                                        ("REJECTED", "APPROVED")])
def test_no_state_machine(admin, factory, proj, src, target):
    """需求状态无流转约束，任意跳转均允许（与缺陷状态机形成对照）。"""
    req = factory.requirement(admin, proj["id"], status=src)
    payload = data.requirement(proj["id"], status=target)
    obj = ok(admin.put("/api/requirements/{}".format(req["id"]), json=payload))
    assert obj["status"] == target


# ===================================================================== 删除
@pytest.mark.case("REQ-034")
def test_delete_requirement(admin, factory, proj):
    req = factory.requirement(admin, proj["id"])
    no_content(admin.delete("/api/requirements/{}".format(req["id"])), "删除需求")
    error(admin.get("/api/requirements/{}".format(req["id"])), 404, "需求不存在")


@pytest.mark.case("REQ-035")
def test_delete_not_found(admin):
    error(admin.delete("/api/requirements/99999999"), 404, "需求不存在: 99999999")


# ===================================================================== 权限与数据隔离
@pytest.mark.case("REQ-036")
def test_user_cannot_read_foreign(client1, admin, factory, project_b):
    req = factory.requirement(admin, project_b["id"])
    forbidden(client1.get("/api/requirements/{}".format(req["id"])), "无权访问该资源")


@pytest.mark.case("REQ-037")
def test_user_cannot_write_foreign_project(client1, project_b):
    forbidden(client1.post("/api/requirements", json=data.requirement(project_b["id"])),
              "无权操作该项目的数据")


@pytest.mark.case("REQ-038")
def test_user_cannot_update_or_delete_foreign(client1, admin, factory, project_b):
    req = factory.requirement(admin, project_b["id"])
    forbidden(client1.put("/api/requirements/{}".format(req["id"]),
                          json=data.requirement(project_b["id"])), "无权操作该项目的数据")
    forbidden(client1.delete("/api/requirements/{}".format(req["id"])), "无权访问该资源")


@pytest.mark.case("REQ-039")
def test_user_must_choose_project(client1):
    error(client1.post("/api/requirements", json=data.requirement(None)), 400, "请选择所属项目")


@pytest.mark.case("REQ-040")
def test_user_cannot_see_unassigned(client1, admin, factory):
    req = factory.requirement(admin, None)
    forbidden(client1.get("/api/requirements/{}".format(req["id"])), "无权访问该资源")
    rows = ok(client1.get("/api/requirements"))
    assert req["id"] not in _ids(rows)


@pytest.mark.case("REQ-041")
def test_user_list_only_bound_projects(client1, admin, factory, project_a, project_b):
    mine = factory.requirement(admin, project_a["id"])
    foreign = factory.requirement(admin, project_b["id"])
    rows = ok(client1.get("/api/requirements"))
    assert mine["id"] in _ids(rows)
    assert foreign["id"] not in _ids(rows)
    assert all(r["projectId"] == project_a["id"] for r in rows)


@pytest.mark.case("REQ-042")
def test_user_full_crud_within_bound_project(client1, factory, project_a):
    req = factory.requirement(client1, project_a["id"], title="普通用户自建需求")
    assert req["seq"] >= 1
    ok(client1.put("/api/requirements/{}".format(req["id"]),
                   json=data.requirement(project_a["id"], title="普通用户改标题", status="REVIEWING")))
    ok(client1.get("/api/requirements/{}".format(req["id"])))
    no_content(client1.delete("/api/requirements/{}".format(req["id"])))


@pytest.mark.case("REQ-043")
def test_requirements_require_auth(anon):
    unauthorized(anon.get("/api/requirements"))
    unauthorized(anon.post("/api/requirements", json=data.requirement(1)))


@pytest.mark.case("REQ-044")
@pytest.mark.xfail(reason="后端缺陷 D-05：RequirementService 只 trim 标题不 trim 所属期，"
                          "而查询侧对 period 做了 trim，带空格落库后按所属期筛选漏匹配",
                   strict=True)
def test_period_trimmed_on_create(admin, factory, proj):
    """所属期查询侧会 trim，创建侧也应 trim，否则带空格落库后按所属期筛选会漏匹配。"""
    req = factory.requirement(admin, proj["id"], period="  三期  ")
    assert req["period"] == "三期", "创建时所属期首尾空格应被裁剪"
    rows = ok(admin.get("/api/requirements",
                        params={"projectId": proj["id"], "period": "三期"}))
    assert req["id"] in _ids(rows), "落库带空格会导致按所属期筛选漏掉该需求"