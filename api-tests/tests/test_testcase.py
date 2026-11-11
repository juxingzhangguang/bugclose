# -*- coding: utf-8 -*-
"""测试用例接口测试：/api/testcases（增删改查、执行记录、批量导入、权限隔离）。"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,
                             rejected, same_time, unauthorized)
from core.client import body

pytestmark = pytest.mark.case("TC")

TC_FIELDS = ["id", "seq", "projectId", "title", "module", "priority", "precondition",
             "steps", "expectedResult", "status", "actualResult", "executor",
             "executedAt", "designer", "createdAt", "updatedAt"]


@pytest.fixture
def proj(factory):
    return factory.project()


def _ids(rows):
    return {r["id"] for r in rows}


def _purge_project(admin, tracker, project_id):
    """批量导入只返回计数不返回 id，按项目清理整批用例。"""
    def deleter():
        rows = ok(admin.get("/api/testcases", params={"projectId": project_id}))
        for r in rows:
            admin.delete("/api/testcases/{}".format(r["id"]))
    tracker.add("testcase", "batch-{}".format(project_id), deleter)


# ===================================================================== 创建
@pytest.mark.case("TC-001")
def test_create_defaults(admin, proj):
    obj = created(admin.post("/api/testcases", json=data.testcase(proj["id"])), "创建用例")
    keys(obj, TC_FIELDS, "用例响应")
    assert obj["priority"] == "P2"
    assert obj["status"] == "NOT_RUN"
    assert obj["seq"] == 1
    assert obj["actualResult"] is None and obj["executor"] is None and obj["executedAt"] is None
    assert obj["createdAt"] and obj["updatedAt"]


@pytest.mark.case("TC-002")
@pytest.mark.parametrize("given", ["PASS", "FAIL", "BLOCKED"])
def test_create_forces_not_run(admin, proj, given):
    obj = created(admin.post("/api/testcases", json=data.testcase(proj["id"], status=given)))
    assert obj["status"] == "NOT_RUN", "创建接口强制 NOT_RUN，执行结果只能走 /execute"


@pytest.mark.case("TC-003")
def test_seq_increments_within_project(admin, factory, proj):
    assert [factory.testcase(admin, proj["id"])["seq"] for _ in range(3)] == [1, 2, 3]


@pytest.mark.case("TC-004")
def test_seq_independent_across_projects(admin, factory, proj):
    other = factory.project()
    assert factory.testcase(admin, proj["id"])["seq"] == 1
    assert factory.testcase(admin, proj["id"])["seq"] == 2
    assert factory.testcase(admin, other["id"])["seq"] == 1


@pytest.mark.case("TC-005")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_title_required(admin, proj, blank):
    payload = data.testcase(proj["id"])
    payload["title"] = blank
    error(admin.post("/api/testcases", json=payload), 400, "用例标题不能为空")


@pytest.mark.case("TC-006")
def test_title_trimmed(admin, proj):
    obj = created(admin.post("/api/testcases", json=data.testcase(proj["id"], title="  带空格的用例  ")))
    assert obj["title"] == "带空格的用例"


@pytest.mark.case("TC-007")
def test_create_honours_all_fields(admin, proj):
    payload = data.testcase(proj["id"], title="全字段用例", module="支付模块", priority="P0",
                            precondition="前置条件", steps="步骤内容",
                            expectedResult="预期内容", designer="设计人")
    obj = created(admin.post("/api/testcases", json=payload))
    for field in ("title", "module", "priority", "precondition", "steps",
                  "expectedResult", "designer"):
        assert obj[field] == payload[field], "字段 {} 未按入参写入".format(field)


@pytest.mark.case("TC-008")
def test_client_id_and_seq_ignored(admin, proj):
    obj = created(admin.post("/api/testcases", json=data.testcase(proj["id"], id=999999, seq=88888)))
    assert obj["id"] != 999999
    assert obj["seq"] == 1


@pytest.mark.case("TC-009")
def test_create_does_not_validate_project_existence(admin):
    """现状确认：用例创建不校验项目是否存在（需求模块会校验），可产生孤儿数据。"""
    obj = created(admin.post("/api/testcases", json=data.testcase(99999999)))
    assert obj["projectId"] == 99999999
    no_content(admin.delete("/api/testcases/{}".format(obj["id"])))


@pytest.mark.case("TC-010")
def test_title_length_boundary(admin, proj):
    obj = created(admin.post("/api/testcases",
                             json=data.testcase(proj["id"], title="C" * config.LEN["case_title"])))
    assert len(obj["title"]) == config.LEN["case_title"]


@pytest.mark.case("TC-011")
@pytest.mark.xfail(reason="后端缺陷 D-01：标题超长未做长度校验，返回 500，应为 400", strict=True)
def test_title_over_length(admin, proj):
    error(admin.post("/api/testcases",
                     json=data.testcase(proj["id"], title="C" * (config.LEN["case_title"] + 1))),
          400, "标题")


@pytest.mark.case("TC-012")
def test_precondition_length_boundary(admin, proj):
    obj = created(admin.post("/api/testcases", json=data.testcase(
        proj["id"], precondition="前" * config.LEN["case_precondition"])))
    assert len(obj["precondition"]) == config.LEN["case_precondition"]


# ===================================================================== 查询
@pytest.fixture
def dataset(admin, factory, proj):
    rows = [
        factory.testcase(admin, proj["id"], title="Alpha Login Case", module="登录模块", priority="P0"),
        factory.testcase(admin, proj["id"], title="Beta Pay Case", module="支付模块", priority="P1"),
        factory.testcase(admin, proj["id"], title="Gamma Report Case", module="报表模块", priority="P3"),
    ]
    ok(admin.put("/api/testcases/{}/execute".format(rows[1]["id"]),
                 json={"status": "PASS", "executor": "执行员"}))
    ok(admin.put("/api/testcases/{}/execute".format(rows[2]["id"]),
                 json={"status": "FAIL", "executor": "执行员"}))
    return {"project": proj, "rows": rows}


@pytest.mark.case("TC-013")
def test_filter_by_project(admin, dataset):
    rows = ok(admin.get("/api/testcases", params={"projectId": dataset["project"]["id"]}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("TC-014")
@pytest.mark.parametrize("value,count", [("NOT_RUN", 1), ("PASS", 1), ("FAIL", 1), ("BLOCKED", 0)])
def test_filter_by_status(admin, dataset, value, count):
    rows = ok(admin.get("/api/testcases",
                        params={"projectId": dataset["project"]["id"], "status": value}))
    assert len(rows) == count


@pytest.mark.case("TC-015")
@pytest.mark.parametrize("value,index", [("P0", 0), ("P1", 1), ("P3", 2)])
def test_filter_by_priority(admin, dataset, value, index):
    rows = ok(admin.get("/api/testcases",
                        params={"projectId": dataset["project"]["id"], "priority": value}))
    assert _ids(rows) == {dataset["rows"][index]["id"]}


@pytest.mark.case("TC-016")
def test_keyword_matches_title_and_module_only(admin, dataset):
    pid = dataset["project"]["id"]
    by_title = ok(admin.get("/api/testcases", params={"projectId": pid, "keyword": "Pay"}))
    assert _ids(by_title) == {dataset["rows"][1]["id"]}
    by_module = ok(admin.get("/api/testcases", params={"projectId": pid, "keyword": "报表"}))
    assert _ids(by_module) == {dataset["rows"][2]["id"]}


@pytest.mark.case("TC-017")
def test_keyword_case_insensitive(admin, dataset):
    pid = dataset["project"]["id"]
    lower = ok(admin.get("/api/testcases", params={"projectId": pid, "keyword": "alpha"}))
    upper = ok(admin.get("/api/testcases", params={"projectId": pid, "keyword": "ALPHA"}))
    assert _ids(lower) == _ids(upper) == {dataset["rows"][0]["id"]}


@pytest.mark.case("TC-018")
def test_combined_filters(admin, dataset):
    rows = ok(admin.get("/api/testcases", params={
        "projectId": dataset["project"]["id"], "status": "PASS",
        "priority": "P1", "keyword": "beta"}))
    assert _ids(rows) == {dataset["rows"][1]["id"]}


@pytest.mark.case("TC-019")
def test_blank_keyword_ignored(admin, dataset):
    rows = ok(admin.get("/api/testcases",
                        params={"projectId": dataset["project"]["id"], "keyword": "   "}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("TC-020")
def test_list_sorted_by_id_asc(admin, dataset):
    rows = ok(admin.get("/api/testcases", params={"projectId": dataset["project"]["id"]}))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids)


@pytest.mark.case("TC-021")
def test_invalid_enum_query_param(admin):
    resp = admin.get("/api/testcases", params={"status": "NOT_A_STATUS"})
    rejected(resp, "非法枚举查询参数")
    assert resp.status_code == 400


@pytest.mark.case("TC-022")
def test_foreign_project_filter_returns_empty(client1, dataset):
    rows = ok(client1.get("/api/testcases", params={"projectId": dataset["project"]["id"]}))
    assert rows == []


# ===================================================================== 详情
@pytest.mark.case("TC-023")
def test_detail(admin, factory, proj):
    case = factory.testcase(admin, proj["id"], title="详情校验")
    obj = ok(admin.get("/api/testcases/{}".format(case["id"])))
    keys(obj, TC_FIELDS)
    assert obj["title"] == "详情校验"


@pytest.mark.case("TC-024")
def test_detail_not_found(admin):
    error(admin.get("/api/testcases/99999999"), 404, "测试用例不存在: 99999999")


# ===================================================================== 编辑
@pytest.mark.case("TC-025")
def test_update_fields(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    payload = data.testcase(proj["id"], title="改后用例", module="订单模块", priority="P0",
                            precondition="新前置", steps="新步骤",
                            expectedResult="新预期", designer="新设计人")
    obj = ok(admin.put("/api/testcases/{}".format(case["id"]), json=payload), "编辑用例")
    for field in ("title", "module", "priority", "precondition", "steps",
                  "expectedResult", "designer"):
        assert obj[field] == payload[field], "字段 {} 未更新".format(field)
    assert obj["seq"] == case["seq"]
    same_time(obj["createdAt"], case["createdAt"], "创建时间不变")


@pytest.mark.case("TC-026")
def test_update_cannot_change_status(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    obj = ok(admin.put("/api/testcases/{}".format(case["id"]),
                       json=data.testcase(proj["id"], status="PASS")))
    assert obj["status"] == "NOT_RUN", "PUT 不修改执行状态，只能走 /execute"


@pytest.mark.case("TC-027")
def test_update_keeps_priority_when_null(admin, factory, proj):
    case = factory.testcase(admin, proj["id"], priority="P0")
    payload = data.testcase(proj["id"], title="只改标题")
    payload["priority"] = None
    obj = ok(admin.put("/api/testcases/{}".format(case["id"]), json=payload))
    assert obj["priority"] == "P0"
    assert obj["title"] == "只改标题"


@pytest.mark.case("TC-028")
def test_update_move_project_reassigns_seq(admin, factory, proj):
    target = factory.project()
    factory.testcase(admin, target["id"])
    case = factory.testcase(admin, proj["id"])
    obj = ok(admin.put("/api/testcases/{}".format(case["id"]), json=data.testcase(target["id"])))
    assert obj["projectId"] == target["id"]
    assert obj["seq"] == 2


@pytest.mark.case("TC-029")
def test_update_required_validation(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    payload = data.testcase(proj["id"])
    payload["title"] = ""
    error(admin.put("/api/testcases/{}".format(case["id"]), json=payload), 400, "用例标题不能为空")


@pytest.mark.case("TC-030")
def test_update_clears_nullable_fields(admin, factory, proj):
    case = factory.testcase(admin, proj["id"], precondition="原前置", designer="原设计人")
    payload = data.testcase(proj["id"], precondition=None, designer=None, module=None)
    obj = ok(admin.put("/api/testcases/{}".format(case["id"]), json=payload))
    assert obj["precondition"] is None and obj["designer"] is None and obj["module"] is None


@pytest.mark.case("TC-031")
def test_update_not_found(admin, proj):
    error(admin.put("/api/testcases/99999999", json=data.testcase(proj["id"])),
          404, "测试用例不存在: 99999999")


# ===================================================================== 执行记录
@pytest.mark.case("TC-032")
def test_execute_records_result(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    obj = ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                       json={"status": "PASS", "actualResult": "  实际通过  ", "executor": "  张三  "}),
             "记录执行结果")
    assert obj["status"] == "PASS"
    assert obj["actualResult"] == "实际通过", "实际结果应 trim"
    assert obj["executor"] == "张三", "执行人应 trim"
    assert obj["executedAt"], "执行时间应被写入"


@pytest.mark.case("TC-033")
@pytest.mark.parametrize("target", config.CASE_STATUS)
def test_execute_no_state_machine(admin, factory, proj, target):
    """执行状态无流转约束，任意状态可反复覆盖（含回到 NOT_RUN）。"""
    case = factory.testcase(admin, proj["id"])
    ok(admin.put("/api/testcases/{}/execute".format(case["id"]), json={"status": "FAIL"}))
    obj = ok(admin.put("/api/testcases/{}/execute".format(case["id"]), json={"status": target}))
    assert obj["status"] == target


@pytest.mark.case("TC-034")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_execute_blank_actual_result_becomes_null(admin, factory, proj, blank):
    case = factory.testcase(admin, proj["id"])
    ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                 json={"status": "FAIL", "actualResult": "原实际结果"}))
    obj = ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                       json={"status": "PASS", "actualResult": blank}))
    assert obj["actualResult"] is None, "空白实际结果应清空为 null"


@pytest.mark.case("TC-035")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_execute_blank_executor_keeps_old(admin, factory, proj, blank):
    case = factory.testcase(admin, proj["id"])
    ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                 json={"status": "FAIL", "executor": "原执行人"}))
    obj = ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                       json={"status": "PASS", "executor": blank}))
    assert obj["executor"] == "原执行人", "空白执行人保留原值（与实际结果语义相反）"


@pytest.mark.case("TC-036")
@pytest.mark.parametrize("payload", [{}, {"status": None}], ids=["missing", "null"])
def test_execute_requires_status(admin, factory, proj, payload):
    case = factory.testcase(admin, proj["id"])
    error(admin.put("/api/testcases/{}/execute".format(case["id"]), json=payload),
          400, "执行状态不能为空")


@pytest.mark.case("TC-037")
def test_execute_invalid_enum(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    resp = admin.put("/api/testcases/{}/execute".format(case["id"]), json={"status": "BAD"})
    rejected(resp, "非法执行状态枚举")
    assert resp.status_code == 400


@pytest.mark.case("TC-038")
def test_execute_not_found(admin):
    error(admin.put("/api/testcases/99999999/execute", json={"status": "PASS"}),
          404, "测试用例不存在: 99999999")


# ===================================================================== 批量导入
@pytest.mark.case("TC-039")
def test_import_all_success(admin, proj, tracker):
    _purge_project(admin, tracker, proj["id"])
    rows = [data.testcase(proj["id"], title="导入用例{}".format(i)) for i in range(3)]
    obj = ok(admin.post("/api/testcases/import", json=rows), "批量导入")
    keys(obj, ["total", "success", "failures"])
    assert (obj["total"], obj["success"], obj["failures"]) == (3, 3, [])
    listed = ok(admin.get("/api/testcases", params={"projectId": proj["id"]}))
    assert len(listed) == 3
    assert all(r["status"] == "NOT_RUN" for r in listed), "导入同样强制 NOT_RUN"


@pytest.mark.case("TC-040")
def test_import_empty_rejected(admin):
    error(admin.post("/api/testcases/import", json=[]), 400, "导入数据不能为空")


@pytest.mark.case("TC-041")
@pytest.mark.parametrize("kind", ["absent", "null"], ids=["no-body", "literal-null"])
def test_import_missing_body_rejected(admin, kind):
    """@RequestBody 默认 required=true：不带体与字面量 null 都由框架层拦截为 400。

    服务层 importBatch 里的 testCases==null 分支属于防御性代码，HTTP 侧不可达。
    """
    if kind == "absent":
        resp = admin.post("/api/testcases/import")
    else:
        # requests 的 json=None 不会发送请求体，这里必须显式发字面量 null
        resp = admin.post("/api/testcases/import", data="null",
                          headers={"Content-Type": "application/json"})
    rejected(resp, "导入缺少请求体")
    assert resp.status_code == 400
    assert body(resp).get("status") == 400, "框架默认错误体应含 status 字段"


@pytest.mark.case("TC-042")
def test_import_over_limit_rejected(admin, proj):
    rows = [data.testcase(proj["id"], title="超限{}".format(i)) for i in range(501)]
    error(admin.post("/api/testcases/import", json=rows), 400, "单次最多导入 500 条")
    assert ok(admin.get("/api/testcases", params={"projectId": proj["id"]})) == [], "超限时整批不落库"


@pytest.mark.case("TC-043")
@pytest.mark.slow
def test_import_at_limit(admin, proj, tracker):
    _purge_project(admin, tracker, proj["id"])
    rows = [data.testcase(proj["id"], title="边界导入{}".format(i)) for i in range(500)]
    obj = ok(admin.post("/api/testcases/import", json=rows), "导入 500 条")
    assert (obj["total"], obj["success"], obj["failures"]) == (500, 500, [])
    listed = ok(admin.get("/api/testcases", params={"projectId": proj["id"]}))
    assert len(listed) == 500
    assert sorted(r["seq"] for r in listed) == list(range(1, 501)), "导入序号应连续无重复"


@pytest.mark.case("TC-044")
def test_import_collects_row_failures(admin, proj, tracker):
    _purge_project(admin, tracker, proj["id"])
    bad1 = data.testcase(proj["id"])
    bad1["title"] = ""
    bad2 = data.testcase(proj["id"])
    bad2["title"] = "   "
    rows = [data.testcase(proj["id"], title="合法行1"), bad1,
            data.testcase(proj["id"], title="合法行3"), bad2]
    obj = ok(admin.post("/api/testcases/import", json=rows), "部分失败导入")
    assert obj["total"] == 4 and obj["success"] == 2, "失败行不影响其他行，HTTP 仍为 200"
    assert [f["row"] for f in obj["failures"]] == [2, 4], "行号从 1 开始"
    assert all("用例标题不能为空" in f["error"] for f in obj["failures"])


@pytest.mark.case("TC-045")
def test_import_respects_permission(client1, project_b, tracker, admin):
    _purge_project(admin, tracker, project_b["id"])
    rows = [data.testcase(project_b["id"], title="越权导入{}".format(i)) for i in range(2)]
    obj = ok(client1.post("/api/testcases/import", json=rows), "越权批量导入")
    assert obj["success"] == 0
    assert len(obj["failures"]) == 2
    assert all("无权操作该项目的数据" in f["error"] for f in obj["failures"])


# ===================================================================== 删除
@pytest.mark.case("TC-046")
def test_delete_case(admin, factory, proj):
    case = factory.testcase(admin, proj["id"])
    no_content(admin.delete("/api/testcases/{}".format(case["id"])), "删除用例")
    error(admin.get("/api/testcases/{}".format(case["id"])), 404, "测试用例不存在")


@pytest.mark.case("TC-047")
def test_delete_not_found(admin):
    error(admin.delete("/api/testcases/99999999"), 404, "测试用例不存在: 99999999")


# ===================================================================== 权限与数据隔离
@pytest.mark.case("TC-048")
def test_user_cannot_read_foreign(client1, admin, factory, project_b):
    case = factory.testcase(admin, project_b["id"])
    forbidden(client1.get("/api/testcases/{}".format(case["id"])), "无权访问该资源")


@pytest.mark.case("TC-049")
def test_user_cannot_write_foreign_project(client1, project_b):
    forbidden(client1.post("/api/testcases", json=data.testcase(project_b["id"])),
              "无权操作该项目的数据")


@pytest.mark.case("TC-050")
def test_user_cannot_update_delete_execute_foreign(client1, admin, factory, project_b):
    case = factory.testcase(admin, project_b["id"])
    forbidden(client1.put("/api/testcases/{}".format(case["id"]),
                          json=data.testcase(project_b["id"])), "无权操作该项目的数据")
    forbidden(client1.put("/api/testcases/{}/execute".format(case["id"]),
                          json={"status": "PASS"}), "无权访问该资源")
    forbidden(client1.delete("/api/testcases/{}".format(case["id"])), "无权访问该资源")


@pytest.mark.case("TC-051")
def test_user_must_choose_project(client1):
    error(client1.post("/api/testcases", json=data.testcase(None)), 400, "请选择所属项目")


@pytest.mark.case("TC-052")
def test_user_cannot_see_unassigned(client1, admin, factory):
    case = factory.testcase(admin, None)
    forbidden(client1.get("/api/testcases/{}".format(case["id"])), "无权访问该资源")
    assert case["id"] not in _ids(ok(client1.get("/api/testcases")))


@pytest.mark.case("TC-053")
def test_user_list_only_bound_projects(client1, admin, factory, project_a, project_b):
    mine = factory.testcase(admin, project_a["id"])
    foreign = factory.testcase(admin, project_b["id"])
    rows = ok(client1.get("/api/testcases"))
    assert mine["id"] in _ids(rows)
    assert foreign["id"] not in _ids(rows)
    assert all(r["projectId"] == project_a["id"] for r in rows)


@pytest.mark.case("TC-054")
def test_user_full_crud_within_bound_project(client1, factory, project_a):
    case = factory.testcase(client1, project_a["id"], title="普通用户自建用例")
    ok(client1.put("/api/testcases/{}".format(case["id"]),
                   json=data.testcase(project_a["id"], title="普通用户改标题")))
    ok(client1.put("/api/testcases/{}/execute".format(case["id"]),
                   json={"status": "PASS", "executor": "普通用户"}))
    ok(client1.get("/api/testcases/{}".format(case["id"])))
    no_content(client1.delete("/api/testcases/{}".format(case["id"])))


@pytest.mark.case("TC-055")
def test_testcases_require_auth(anon):
    unauthorized(anon.get("/api/testcases"))
    unauthorized(anon.post("/api/testcases", json=data.testcase(1)))
    unauthorized(anon.post("/api/testcases/import", json=[data.testcase(1)]))