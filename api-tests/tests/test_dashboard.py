# -*- coding: utf-8 -*-
"""统计看板接口测试：/api/dashboard/statistics（四维度聚合、通过率口径、数据可见性）。

看板是全局聚合、无项目入参，因此断言一律采用「快照 → 操作 → 快照」的增量比对，
避免依赖库中既有业务数据的绝对值。
"""
import math

import pytest

import config
from core import data
from core.assertions import keys, ok, status, unauthorized

pytestmark = pytest.mark.case("DASH")

PATH = "/api/dashboard/statistics"
TOP_KEYS = ["bug", "testCase", "requirement", "doc"]
LISTS = {"bug": "/api/bugs", "testCase": "/api/testcases",
         "requirement": "/api/requirements", "doc": "/api/docs"}


def _stats(client):
    return ok(client.get(PATH), "看板统计")


def _count(client, path):
    return len(ok(client.get(path)))


def _java_round(x):
    """Java Math.round(double) = floor(x + 0.5)，与 Python 的银行家舍入不同。"""
    return math.floor(x + 0.5)


# ===================================================================== 结构与枚举
@pytest.mark.case("DASH-001")
def test_statistics_structure(admin):
    obj = _stats(admin)
    keys(obj, TOP_KEYS, "看板四维度")
    assert set(obj) == set(TOP_KEYS), "只应含 bug/testCase/requirement/doc，实际 {}".format(sorted(obj))
    keys(obj["bug"], ["total", "byStatus", "bySeverity", "byAssignee"], "缺陷维度")
    keys(obj["testCase"], ["total", "byStatus", "executed", "passRate"], "用例维度")
    keys(obj["requirement"], ["total", "byStatus"], "需求维度")
    keys(obj["doc"], ["total", "byCategory"], "文档维度")


@pytest.mark.case("DASH-002")
def test_bug_enum_buckets_complete(admin):
    bug = _stats(admin)["bug"]
    assert set(bug["byStatus"]) == set(config.BUG_STATUS), "状态桶应覆盖全部枚举（含 0 值）"
    assert set(bug["bySeverity"]) == set(config.BUG_SEVERITY), "严重度桶应覆盖全部枚举"
    assert all(isinstance(v, int) and v >= 0 for v in bug["byStatus"].values())
    assert sum(bug["byStatus"].values()) == bug["total"], "状态桶之和应等于 total"
    assert sum(bug["bySeverity"].values()) == bug["total"], "严重度桶之和应等于 total"


@pytest.mark.case("DASH-003")
def test_testcase_enum_buckets_complete(admin):
    tc = _stats(admin)["testCase"]
    assert set(tc["byStatus"]) == set(config.CASE_STATUS)
    assert sum(tc["byStatus"].values()) == tc["total"]


@pytest.mark.case("DASH-004")
def test_requirement_enum_buckets_complete(admin):
    req = _stats(admin)["requirement"]
    assert set(req["byStatus"]) == set(config.REQ_STATUS)
    assert sum(req["byStatus"].values()) == req["total"]


@pytest.mark.case("DASH-005")
def test_doc_enum_buckets_complete(admin):
    doc = _stats(admin)["doc"]
    assert set(doc["byCategory"]) == set(config.DOC_CATEGORY)
    assert sum(doc["byCategory"].values()) == doc["total"]


@pytest.mark.case("DASH-006")
def test_totals_match_list_endpoints(admin):
    obj = _stats(admin)
    for dim, path in LISTS.items():
        assert obj[dim]["total"] == _count(admin, path), \
            "{} 维度 total 应与列表接口条数一致".format(dim)


# ===================================================================== 缺陷维度增量
@pytest.mark.case("DASH-007")
def test_bug_total_and_status_increment(admin, factory, project_a):
    before = _stats(admin)["bug"]
    factory.bug(admin, project_a["id"], status="NEW")
    after = _stats(admin)["bug"]
    assert after["total"] == before["total"] + 1
    assert after["byStatus"]["NEW"] == before["byStatus"]["NEW"] + 1


@pytest.mark.case("DASH-008")
def test_bug_severity_increment(admin, factory, project_a):
    before = _stats(admin)["bug"]
    factory.bug(admin, project_a["id"], severity="CRITICAL")
    after = _stats(admin)["bug"]
    assert after["bySeverity"]["CRITICAL"] == before["bySeverity"]["CRITICAL"] + 1
    assert after["total"] == before["total"] + 1


@pytest.mark.case("DASH-009")
def test_bug_assignee_bucket(admin, factory, project_a):
    before = _stats(admin)["bug"]["byAssignee"]
    name = "AT负责人_" + data.uniq()
    factory.bug(admin, project_a["id"], assignee=None)
    factory.bug(admin, project_a["id"], assignee="   ")
    factory.bug(admin, project_a["id"], assignee=name)
    after = _stats(admin)["bug"]["byAssignee"]
    assert after.get("未指派", 0) == before.get("未指派", 0) + 2, \
        "assignee 为 null 或纯空格都归入「未指派」"
    assert after.get(name) == before.get(name, 0) + 1, "指名负责人应单独成桶"


@pytest.mark.case("DASH-010")
def test_bug_delete_decrements(admin, factory, project_a):
    before = _stats(admin)["bug"]
    bug = factory.bug(admin, project_a["id"], severity="LOW")
    assert _stats(admin)["bug"]["total"] == before["total"] + 1
    admin.delete("/api/bugs/{}".format(bug["id"]))
    factory.tracker.forget("bug", bug["id"])
    after = _stats(admin)["bug"]
    assert after["total"] == before["total"], "删除后统计应回落"
    assert after["bySeverity"]["LOW"] == before["bySeverity"]["LOW"]


# ===================================================================== 用例维度与通过率
@pytest.mark.case("DASH-011")
def test_executed_excludes_not_run(admin):
    tc = _stats(admin)["testCase"]
    assert tc["executed"] == tc["total"] - tc["byStatus"]["NOT_RUN"], \
        "executed = 总数 - 未执行数（PASS/FAIL/BLOCKED 都算已执行）"


@pytest.mark.case("DASH-012")
def test_pass_rate_formula(admin):
    """passRate = round(PASS × 1000 / executed) / 10，executed=0 时为 0。"""
    rows = ok(admin.get("/api/testcases"))
    total = len(rows)
    not_run = sum(1 for r in rows if r["status"] == "NOT_RUN")
    passed = sum(1 for r in rows if r["status"] == "PASS")
    executed = total - not_run
    expected = 0.0 if executed == 0 else _java_round(passed * 1000.0 / executed) / 10.0
    tc = _stats(admin)["testCase"]
    assert tc["total"] == total
    assert tc["executed"] == executed
    assert tc["passRate"] == pytest.approx(expected), \
        "通过率口径不符：期望 {}，实际 {}".format(expected, tc["passRate"])


@pytest.mark.case("DASH-013")
def test_execute_case_updates_pass_rate(admin, factory, project_a):
    before = _stats(admin)["testCase"]
    case = factory.testcase(admin, project_a["id"])
    mid = _stats(admin)["testCase"]
    assert mid["total"] == before["total"] + 1
    assert mid["byStatus"]["NOT_RUN"] == before["byStatus"]["NOT_RUN"] + 1
    assert mid["executed"] == before["executed"], "新建用例未执行，executed 不变"
    ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                 json={"status": "PASS", "actualResult": "通过", "executor": "at_bot"}))
    after = _stats(admin)["testCase"]
    assert after["byStatus"]["PASS"] == mid["byStatus"]["PASS"] + 1
    assert after["byStatus"]["NOT_RUN"] == mid["byStatus"]["NOT_RUN"] - 1
    assert after["executed"] == mid["executed"] + 1


@pytest.mark.case("DASH-014")
def test_fail_and_blocked_count_as_executed(admin, factory, project_a):
    before = _stats(admin)["testCase"]
    for st in ("FAIL", "BLOCKED"):
        case = factory.testcase(admin, project_a["id"])
        ok(admin.put("/api/testcases/{}/execute".format(case["id"]),
                     json={"status": st, "actualResult": st, "executor": "at_bot"}))
    after = _stats(admin)["testCase"]
    assert after["executed"] == before["executed"] + 2
    assert after["byStatus"]["FAIL"] == before["byStatus"]["FAIL"] + 1
    assert after["byStatus"]["BLOCKED"] == before["byStatus"]["BLOCKED"] + 1
    assert after["byStatus"]["PASS"] == before["byStatus"]["PASS"], "失败/阻塞不计入通过数"


# ===================================================================== 需求与文档维度
@pytest.mark.case("DASH-015")
def test_requirement_increment(admin, factory, project_a):
    before = _stats(admin)["requirement"]
    factory.requirement(admin, project_a["id"], status="APPROVED")
    after = _stats(admin)["requirement"]
    assert after["total"] == before["total"] + 1
    assert after["byStatus"]["APPROVED"] == before["byStatus"]["APPROVED"] + 1


@pytest.mark.case("DASH-016")
def test_doc_increment_by_category(admin, factory, project_a):
    before = _stats(admin)["doc"]
    factory.doc(admin, project_a["id"], category="DESIGN")
    after = _stats(admin)["doc"]
    assert after["total"] == before["total"] + 1
    assert after["byCategory"]["DESIGN"] == before["byCategory"]["DESIGN"] + 1


# ===================================================================== 数据可见性
@pytest.mark.case("DASH-017")
def test_zero_bound_user_sees_all_zero(client_empty):
    obj = _stats(client_empty)
    for dim in TOP_KEYS:
        assert obj[dim]["total"] == 0, "{} 维度应为 0".format(dim)
    assert obj["testCase"]["executed"] == 0
    assert obj["testCase"]["passRate"] == 0, "无已执行用例时通过率为 0，不得除零报错"
    assert obj["bug"]["byAssignee"] == {}


@pytest.mark.case("DASH-018")
def test_user_stats_match_own_visible_lists(client1):
    obj = _stats(client1)
    for dim, path in LISTS.items():
        assert obj[dim]["total"] == _count(client1, path), \
            "{} 维度应只统计该用户可见的数据".format(dim)


@pytest.mark.case("DASH-019")
def test_foreign_project_data_not_counted(admin, client1, factory, project_b):
    before = _stats(client1)
    before_admin = _stats(admin)
    factory.bug(admin, project_b["id"])
    factory.testcase(admin, project_b["id"])
    factory.requirement(admin, project_b["id"])
    after = _stats(client1)
    for dim in TOP_KEYS:
        assert after[dim]["total"] == before[dim]["total"], \
            "未绑定项目 B 的新增数据不应进入用户 1 的看板"
    after_admin = _stats(admin)
    assert after_admin["bug"]["total"] == before_admin["bug"]["total"] + 1, "管理员应能看到项目 B 的新增数据"
    assert after_admin["testCase"]["total"] == before_admin["testCase"]["total"] + 1
    assert after_admin["requirement"]["total"] == before_admin["requirement"]["total"] + 1


@pytest.mark.case("DASH-020")
def test_unassigned_data_invisible_to_user(admin, client1, factory):
    before_user = _stats(client1)
    before_admin = _stats(admin)
    factory.bug(admin, None)
    after_user = _stats(client1)
    after_admin = _stats(admin)
    assert after_admin["bug"]["total"] == before_admin["bug"]["total"] + 1, "管理员可见未关联项目的数据"
    assert after_user["bug"]["total"] == before_user["bug"]["total"], "普通用户不可见未关联项目的数据"


@pytest.mark.case("DASH-021")
def test_bound_project_data_counted_for_user(admin, client1, factory, project_a):
    before = _stats(client1)["bug"]
    factory.bug(admin, project_a["id"])
    after = _stats(client1)["bug"]
    assert after["total"] == before["total"] + 1, "绑定项目内的数据应计入用户看板"


# ===================================================================== 协议
@pytest.mark.case("DASH-022")
def test_dashboard_requires_auth(anon):
    unauthorized(anon.get(PATH))


@pytest.mark.case("DASH-023")
def test_dashboard_get_only(admin):
    status(admin.post(PATH, json={}), 405, "看板只支持 GET")
    status(admin.delete(PATH), 405)


@pytest.mark.case("DASH-024")
def test_dashboard_ignores_query_params(admin):
    base = _stats(admin)
    obj = ok(admin.get(PATH, params={"projectId": 99999999, "page": 2, "size": 1}))
    assert obj == base, "看板无项目/分页入参，附加查询参数应被忽略"