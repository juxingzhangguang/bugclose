# -*- coding: utf-8 -*-
"""缺陷管理接口测试：/api/bugs（增删改查、筛选搜索、状态流转、统计、并发序号）。"""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,
                             rejected, same_time, status, unauthorized)
from core.client import ApiClient, body

pytestmark = pytest.mark.case("BUG")

BUG_FIELDS = ["id", "projectId", "seq", "title", "description", "severity", "priority",
              "status", "assignee", "environment", "module", "reporter", "images",
              "createdAt", "updatedAt"]


@pytest.fixture
def proj(factory):
    """每个用例独享一个空项目，保证 seq 从 1 开始的断言不受其他用例影响。"""
    return factory.project()


# ===================================================================== 创建
@pytest.mark.case("BUG-001")
def test_create_defaults(admin, proj):
    payload = data.bug(proj["id"])
    payload.pop("severity"), payload.pop("priority"), payload.pop("assignee")
    obj = created(admin.post("/api/bugs", json=payload), "创建缺陷")
    keys(obj, BUG_FIELDS, "缺陷响应")
    assert obj["status"] == "NEW"
    assert obj["severity"] == "MEDIUM"
    assert obj["priority"] == "MEDIUM"
    assert obj["seq"] == 1, "项目内首条缺陷序号应为 1"
    assert obj["projectId"] == proj["id"]
    assert obj["createdAt"] and obj["updatedAt"]


@pytest.mark.case("BUG-002")
def test_seq_increments_within_project(admin, factory, proj):
    seqs = [factory.bug(admin, proj["id"])["seq"] for _ in range(3)]
    assert seqs == [1, 2, 3]


@pytest.mark.case("BUG-003")
def test_seq_independent_across_projects(admin, factory, proj):
    other = factory.project()
    assert factory.bug(admin, proj["id"])["seq"] == 1
    assert factory.bug(admin, proj["id"])["seq"] == 2
    assert factory.bug(admin, other["id"])["seq"] == 1, "不同项目各自独立编号"


@pytest.mark.case("BUG-004")
@pytest.mark.parametrize("field,message", [
    ("title", "标题不能为空"),
    ("environment", "影响环境不能为空"),
    ("module", "影响模块不能为空"),
])
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_required_fields(admin, proj, field, message, blank):
    payload = data.bug(proj["id"])
    payload[field] = blank
    error(admin.post("/api/bugs", json=payload), 400, message)


@pytest.mark.case("BUG-005")
def test_required_fields_trimmed(admin, proj):
    obj = created(admin.post("/api/bugs", json=data.bug(
        proj["id"], title="  带空格的标题  ", environment=" 测试环境 ", module=" 登录 ")))
    assert obj["title"] == "带空格的标题"
    assert obj["environment"] == "测试环境"
    assert obj["module"] == "登录"


@pytest.mark.case("BUG-006")
def test_create_honours_enums(admin, proj):
    obj = created(admin.post("/api/bugs", json=data.bug(
        proj["id"], severity="CRITICAL", priority="URGENT", status="CLOSED", assignee="张三")))
    assert (obj["severity"], obj["priority"], obj["status"]) == ("CRITICAL", "URGENT", "CLOSED")
    assert obj["assignee"] == "张三"


@pytest.mark.case("BUG-007")
def test_client_id_and_seq_ignored(admin, proj):
    obj = created(admin.post("/api/bugs", json=data.bug(proj["id"], id=999999, seq=88888)))
    assert obj["id"] != 999999
    assert obj["seq"] == 1, "序号由服务端分配，客户端传值应被忽略"


@pytest.mark.case("BUG-008")
def test_images_stored_as_json_string(admin, proj):
    images = json.dumps(["/uploads/a.png", "/uploads/b.png"], ensure_ascii=False)
    obj = created(admin.post("/api/bugs", json=data.bug(proj["id"], images=images)))
    assert obj["images"] == images
    assert json.loads(obj["images"]) == ["/uploads/a.png", "/uploads/b.png"]


@pytest.mark.case("BUG-009")
def test_title_length_boundary(admin, proj):
    obj = created(admin.post("/api/bugs", json=data.bug(proj["id"], title="T" * config.LEN["bug_title"])))
    assert len(obj["title"]) == config.LEN["bug_title"]


@pytest.mark.case("BUG-010")
@pytest.mark.xfail(reason="后端缺陷 D-01：标题超长未做长度校验，返回 500，应为 400", strict=True)
def test_title_over_length(admin, proj):
    error(admin.post("/api/bugs", json=data.bug(proj["id"], title="T" * (config.LEN["bug_title"] + 1))),
          400, "标题")


@pytest.mark.case("BUG-011")
@pytest.mark.xfail(reason="后端缺陷 D-02：显式 null 覆盖非空枚举字段，触发完整性异常返回 500，应为 400", strict=True)
def test_null_severity_rejected_with_400(admin, proj):
    error(admin.post("/api/bugs", json=data.bug(proj["id"], severity=None)), 400)


# ===================================================================== 查询
@pytest.fixture
def dataset(admin, factory, proj):
    """构造可预测的筛选数据集：3 条缺陷，字段各不相同。"""
    rows = [
        factory.bug(admin, proj["id"], title="Alpha Login Failure", description="无法登录系统",
                    severity="CRITICAL", priority="URGENT", status="NEW", assignee="张三"),
        factory.bug(admin, proj["id"], title="Beta Pay Timeout", description="支付超时 alpha",
                    severity="HIGH", priority="HIGH", status="IN_PROGRESS", assignee="李四"),
        factory.bug(admin, proj["id"], title="Gamma UI Typo", description="界面错别字",
                    severity="LOW", priority="LOW", status="CLOSED", assignee=None),
    ]
    return {"project": proj, "rows": rows}


def _ids(rows):
    return {r["id"] for r in rows}


@pytest.mark.case("BUG-012")
def test_filter_by_project(admin, dataset):
    rows = ok(admin.get("/api/bugs", params={"projectId": dataset["project"]["id"]}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("BUG-013")
@pytest.mark.parametrize("field,value,index", [
    ("status", "NEW", 0), ("status", "IN_PROGRESS", 1), ("status", "CLOSED", 2),
    ("severity", "CRITICAL", 0), ("severity", "LOW", 2),
    ("priority", "URGENT", 0), ("priority", "HIGH", 1),
])
def test_filter_by_enum(admin, dataset, field, value, index):
    rows = ok(admin.get("/api/bugs", params={"projectId": dataset["project"]["id"], field: value}))
    assert _ids(rows) == {dataset["rows"][index]["id"]}


@pytest.mark.case("BUG-014")
def test_filter_by_assignee_exact_and_trim(admin, dataset):
    rows = ok(admin.get("/api/bugs", params={"projectId": dataset["project"]["id"], "assignee": " 张三 "}))
    assert _ids(rows) == {dataset["rows"][0]["id"]}, "处理人为精确匹配且忽略首尾空格"
    partial = ok(admin.get("/api/bugs", params={"projectId": dataset["project"]["id"], "assignee": "张"}))
    assert partial == [], "处理人不做模糊匹配"


@pytest.mark.case("BUG-015")
def test_keyword_matches_title_and_description(admin, dataset):
    pid = dataset["project"]["id"]
    by_title = ok(admin.get("/api/bugs", params={"projectId": pid, "keyword": "Pay"}))
    assert _ids(by_title) == {dataset["rows"][1]["id"]}
    by_desc = ok(admin.get("/api/bugs", params={"projectId": pid, "keyword": "错别字"}))
    assert _ids(by_desc) == {dataset["rows"][2]["id"]}


@pytest.mark.case("BUG-016")
def test_keyword_case_insensitive(admin, dataset):
    pid = dataset["project"]["id"]
    lower = ok(admin.get("/api/bugs", params={"projectId": pid, "keyword": "alpha"}))
    upper = ok(admin.get("/api/bugs", params={"projectId": pid, "keyword": "ALPHA"}))
    assert _ids(lower) == _ids(upper) == {dataset["rows"][0]["id"], dataset["rows"][1]["id"]}


@pytest.mark.case("BUG-017")
def test_combined_filters(admin, dataset):
    rows = ok(admin.get("/api/bugs", params={
        "projectId": dataset["project"]["id"], "status": "IN_PROGRESS",
        "severity": "HIGH", "priority": "HIGH", "assignee": "李四", "keyword": "timeout"}))
    assert _ids(rows) == {dataset["rows"][1]["id"]}


@pytest.mark.case("BUG-018")
def test_blank_filters_ignored(admin, dataset):
    pid = dataset["project"]["id"]
    rows = ok(admin.get("/api/bugs", params={"projectId": pid, "keyword": "   ", "assignee": "  "}))
    assert _ids(rows) == _ids(dataset["rows"]), "空白关键字/处理人应被忽略"


@pytest.mark.case("BUG-019")
def test_list_sorted_by_created_at_desc(admin, dataset):
    rows = ok(admin.get("/api/bugs", params={"projectId": dataset["project"]["id"]}))
    stamps = [r["createdAt"] for r in rows]
    assert stamps == sorted(stamps, reverse=True), "列表应按创建时间倒序"


@pytest.mark.case("BUG-020")
def test_invalid_enum_query_param(admin):
    resp = admin.get("/api/bugs", params={"status": "NOT_A_STATUS"})
    rejected(resp, "非法枚举查询参数")
    assert resp.status_code == 400


@pytest.mark.case("BUG-021")
def test_foreign_project_filter_returns_empty(client1, dataset):
    rows = ok(client1.get("/api/bugs", params={"projectId": dataset["project"]["id"]}))
    assert rows == [], "普通用户按未绑定项目筛选返回空列表（交集过滤），不报错"


# ===================================================================== 详情
@pytest.mark.case("BUG-022")
def test_detail(admin, factory, proj):
    bug = factory.bug(admin, proj["id"], title="详情校验")
    obj = ok(admin.get("/api/bugs/{}".format(bug["id"])))
    keys(obj, BUG_FIELDS)
    assert obj["title"] == "详情校验"
    assert obj["id"] == bug["id"]


@pytest.mark.case("BUG-023")
def test_detail_not_found(admin):
    error(admin.get("/api/bugs/99999999"), 404, "Bug 不存在: id=99999999")


# ===================================================================== 编辑
@pytest.mark.case("BUG-024")
def test_update_fields(admin, factory, proj):
    bug = factory.bug(admin, proj["id"])
    payload = data.bug(proj["id"], title="改后标题", description="改后描述",
                       severity="HIGH", priority="LOW", assignee="王五",
                       environment="生产环境", module="支付模块", reporter="赵六")
    obj = ok(admin.put("/api/bugs/{}".format(bug["id"]), json=payload), "编辑缺陷")
    for field in ("title", "description", "severity", "priority", "assignee",
                  "environment", "module", "reporter"):
        assert obj[field] == payload[field], "字段 {} 未更新".format(field)
    assert obj["seq"] == bug["seq"], "同项目编辑不应改变序号"
    same_time(obj["createdAt"], bug["createdAt"], "创建时间不变")


@pytest.mark.case("BUG-025")
def test_update_cannot_change_status(admin, factory, proj):
    bug = factory.bug(admin, proj["id"], status="NEW")
    payload = data.bug(proj["id"], status="CLOSED")
    obj = ok(admin.put("/api/bugs/{}".format(bug["id"]), json=payload))
    assert obj["status"] == "NEW", "PUT 不修改状态，状态只能走 /status 流转接口"


@pytest.mark.case("BUG-026")
def test_update_move_project_reassigns_seq(admin, factory, proj):
    target = factory.project()
    factory.bug(admin, target["id"])
    bug = factory.bug(admin, proj["id"])
    obj = ok(admin.put("/api/bugs/{}".format(bug["id"]), json=data.bug(target["id"])))
    assert obj["projectId"] == target["id"]
    assert obj["seq"] == 2, "迁移项目后应取目标项目最大序号 +1"


@pytest.mark.case("BUG-027")
def test_update_required_validation(admin, factory, proj):
    bug = factory.bug(admin, proj["id"])
    payload = data.bug(proj["id"])
    payload["title"] = ""
    error(admin.put("/api/bugs/{}".format(bug["id"]), json=payload), 400, "标题不能为空")


@pytest.mark.case("BUG-028")
def test_update_clears_nullable_fields(admin, factory, proj):
    bug = factory.bug(admin, proj["id"], assignee="张三", description="原描述",
                      images=json.dumps(["/uploads/a.png"]))
    payload = data.bug(proj["id"], assignee=None, description=None, images=None)
    obj = ok(admin.put("/api/bugs/{}".format(bug["id"]), json=payload))
    assert obj["assignee"] is None and obj["description"] is None and obj["images"] is None


@pytest.mark.case("BUG-029")
def test_update_not_found(admin, proj):
    error(admin.put("/api/bugs/99999999", json=data.bug(proj["id"])), 404, "Bug 不存在")


# ===================================================================== 状态流转
TRANSITIONS = [
    ("NEW", "IN_PROGRESS", True), ("NEW", "CLOSED", True), ("NEW", "RESOLVED", False),
    ("IN_PROGRESS", "RESOLVED", True), ("IN_PROGRESS", "CLOSED", True), ("IN_PROGRESS", "NEW", False),
    ("RESOLVED", "CLOSED", True), ("RESOLVED", "IN_PROGRESS", True), ("RESOLVED", "NEW", False),
    ("CLOSED", "IN_PROGRESS", True), ("CLOSED", "RESOLVED", False), ("CLOSED", "NEW", False),
]


@pytest.mark.case("BUG-030")
@pytest.mark.parametrize("src,target,allowed", TRANSITIONS,
                         ids=["{}-{}".format(s, t) for s, t, _ in TRANSITIONS])
def test_state_machine(admin, factory, proj, src, target, allowed):
    bug = factory.bug(admin, proj["id"], status=src)
    resp = admin.put("/api/bugs/{}/status".format(bug["id"]), json={"status": target})
    if allowed:
        obj = ok(resp, "{} → {}".format(src, target))
        assert obj["status"] == target
    else:
        error(resp, 400, "不允许从 {} 流转到 {}".format(src, target))


@pytest.mark.case("BUG-031")
@pytest.mark.parametrize("src", config.BUG_STATUS)
def test_self_transition_rejected(admin, factory, proj, src):
    bug = factory.bug(admin, proj["id"], status=src)
    error(admin.put("/api/bugs/{}/status".format(bug["id"]), json={"status": src}),
          400, "不允许从 {} 流转到 {}".format(src, src))


@pytest.mark.case("BUG-032")
def test_transition_assigns_handler(admin, factory, proj):
    bug = factory.bug(admin, proj["id"], status="NEW", assignee=None)
    obj = ok(admin.put("/api/bugs/{}/status".format(bug["id"]),
                       json={"status": "IN_PROGRESS", "assignee": "  张三  "}))
    assert obj["status"] == "IN_PROGRESS"
    assert obj["assignee"] == "张三", "指派处理人应 trim"


@pytest.mark.case("BUG-033")
@pytest.mark.parametrize("assignee", [None, "", "   "], ids=["null", "empty", "blank"])
def test_transition_keeps_assignee_when_blank(admin, factory, proj, assignee):
    bug = factory.bug(admin, proj["id"], status="NEW", assignee="原处理人")
    obj = ok(admin.put("/api/bugs/{}/status".format(bug["id"]),
                       json={"status": "IN_PROGRESS", "assignee": assignee}))
    assert obj["assignee"] == "原处理人"


@pytest.mark.case("BUG-034")
@pytest.mark.parametrize("payload", [{}, {"status": None}], ids=["missing", "null"])
def test_transition_without_status(admin, factory, proj, payload):
    bug = factory.bug(admin, proj["id"], status="NEW")
    error(admin.put("/api/bugs/{}/status".format(bug["id"]), json=payload),
          400, "不允许从 NEW 流转到 null")


@pytest.mark.case("BUG-035")
def test_transition_invalid_enum(admin, factory, proj):
    bug = factory.bug(admin, proj["id"])
    resp = admin.put("/api/bugs/{}/status".format(bug["id"]), json={"status": "BAD"})
    rejected(resp, "非法状态枚举")
    assert resp.status_code == 400


@pytest.mark.case("BUG-036")
def test_transition_not_found(admin):
    error(admin.put("/api/bugs/99999999/status", json={"status": "CLOSED"}), 404, "Bug 不存在")


# ===================================================================== 删除
@pytest.mark.case("BUG-037")
def test_delete_bug(admin, factory, proj):
    bug = factory.bug(admin, proj["id"])
    no_content(admin.delete("/api/bugs/{}".format(bug["id"])), "删除缺陷")
    error(admin.get("/api/bugs/{}".format(bug["id"])), 404, "Bug 不存在")


@pytest.mark.case("BUG-038")
def test_delete_not_found(admin):
    error(admin.delete("/api/bugs/99999999"), 404, "Bug 不存在")


# ===================================================================== 统计
@pytest.mark.case("BUG-039")
def test_statistics_structure(admin):
    obj = ok(admin.get("/api/bugs/statistics"))
    keys(obj, ["total", "byStatus", "bySeverity", "byAssignee"], "缺陷统计")
    assert set(obj["byStatus"]) == set(config.BUG_STATUS), "状态维度应覆盖全部枚举"
    assert set(obj["bySeverity"]) == set(config.BUG_SEVERITY)
    assert list(obj["byStatus"]) == config.BUG_STATUS, "枚举按声明顺序输出"
    assert isinstance(obj["total"], int)


@pytest.mark.case("BUG-040")
def test_statistics_counts_and_unassigned(admin, factory, proj):
    factory.bug(admin, proj["id"], severity="CRITICAL", status="NEW", assignee=None)
    factory.bug(admin, proj["id"], severity="CRITICAL", status="NEW", assignee="  ")
    factory.bug(admin, proj["id"], severity="LOW", status="NEW", assignee="统计员")
    rows = ok(admin.get("/api/bugs", params={"projectId": proj["id"]}))
    stat = ok(admin.get("/api/bugs/statistics"))
    assert stat["total"] >= len(rows)
    assert stat["byStatus"]["NEW"] >= 3
    assert stat["bySeverity"]["CRITICAL"] >= 2
    assert stat["byAssignee"].get("未指派", 0) >= 2, "空/空白处理人应归入「未指派」"
    assert stat["byAssignee"].get("统计员", 0) >= 1


@pytest.mark.case("BUG-041")
def test_statistics_consistent_with_list(admin):
    stat = ok(admin.get("/api/bugs/statistics"))
    rows = ok(admin.get("/api/bugs"))
    assert stat["total"] == len(rows)
    assert sum(stat["byStatus"].values()) == len(rows)
    assert sum(stat["bySeverity"].values()) == len(rows)
    assert sum(stat["byAssignee"].values()) == len(rows)


@pytest.mark.case("BUG-042")
def test_statistics_scoped_for_user(client1, admin, factory, project_a, project_b):
    mine = factory.bug(admin, project_a["id"], title="可见缺陷")
    foreign = factory.bug(admin, project_b["id"], title="不可见缺陷")
    stat = ok(client1.get("/api/bugs/statistics"))
    rows = ok(client1.get("/api/bugs"))
    assert stat["total"] == len(rows)
    assert mine["id"] in _ids(rows)
    assert foreign["id"] not in _ids(rows)


# ===================================================================== 权限与数据隔离
@pytest.mark.case("BUG-043")
def test_user_cannot_read_foreign_bug(client1, admin, factory, project_b):
    bug = factory.bug(admin, project_b["id"])
    forbidden(client1.get("/api/bugs/{}".format(bug["id"])), "无权访问该资源")


@pytest.mark.case("BUG-044")
def test_user_cannot_write_foreign_project(client1, project_b):
    forbidden(client1.post("/api/bugs", json=data.bug(project_b["id"])), "无权操作该项目的数据")


@pytest.mark.case("BUG-045")
def test_user_cannot_update_or_delete_foreign_bug(client1, admin, factory, project_b):
    bug = factory.bug(admin, project_b["id"])
    forbidden(client1.put("/api/bugs/{}".format(bug["id"]), json=data.bug(project_b["id"])),
              "无权操作该项目的数据")
    forbidden(client1.delete("/api/bugs/{}".format(bug["id"])), "无权访问该资源")
    forbidden(client1.put("/api/bugs/{}/status".format(bug["id"]), json={"status": "CLOSED"}),
              "无权访问该资源")


@pytest.mark.case("BUG-046")
def test_user_must_choose_project(client1):
    error(client1.post("/api/bugs", json=data.bug(None)), 400, "请选择所属项目")


@pytest.mark.case("BUG-047")
def test_user_cannot_see_unassigned_bug(client1, admin, factory):
    bug = factory.bug(admin, None)
    forbidden(client1.get("/api/bugs/{}".format(bug["id"])), "无权访问该资源")
    rows = ok(client1.get("/api/bugs"))
    assert bug["id"] not in _ids(rows), "未关联项目的缺陷不应出现在普通用户列表"


@pytest.mark.case("BUG-048")
def test_user_list_only_bound_projects(client1, admin, factory, project_a, project_b):
    mine = factory.bug(admin, project_a["id"])
    foreign = factory.bug(admin, project_b["id"])
    rows = ok(client1.get("/api/bugs"))
    assert mine["id"] in _ids(rows)
    assert foreign["id"] not in _ids(rows)
    assert all(r["projectId"] == project_a["id"] for r in rows)


@pytest.mark.case("BUG-049")
def test_user_full_crud_within_bound_project(client1, factory, project_a):
    bug = factory.bug(client1, project_a["id"], title="普通用户自建缺陷")
    assert bug["seq"] >= 1
    ok(client1.put("/api/bugs/{}".format(bug["id"]),
                   json=data.bug(project_a["id"], title="普通用户改标题")))
    ok(client1.put("/api/bugs/{}/status".format(bug["id"]), json={"status": "IN_PROGRESS"}))
    ok(client1.get("/api/bugs/{}".format(bug["id"])))
    no_content(client1.delete("/api/bugs/{}".format(bug["id"])))


@pytest.mark.case("BUG-050")
def test_bugs_require_auth(anon):
    unauthorized(anon.get("/api/bugs"))
    unauthorized(anon.post("/api/bugs", json=data.bug(1)))


# ===================================================================== 并发
@pytest.mark.case("BUG-051")
@pytest.mark.slow
@pytest.mark.xfail(reason="后端缺陷 D-04：BugService.create 序号冲突重试上限仅 3 次，"
                          "并发下重试耗尽抛 DataIntegrityViolationException 返回 500",
                   strict=True)
def test_concurrent_create_seq_unique(admin, factory, ip_pool):
    """并发创建 12 条缺陷：唯一约束 + 独立事务重试应保证序号不重不漏。"""
    proj = factory.project()
    total = 12

    def create(i):
        client = ApiClient("concurrent-{}".format(i), token=admin.token, ip=ip_pool())
        return client.post("/api/bugs", json=data.bug(proj["id"], title="并发缺陷{}".format(i)))

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(create, range(total)))

    # 先登记清理，再断言：失败时已落库的缺陷也要能回收
    for r in responses:
        if r.status_code == 201:
            obj = body(r)
            factory.tracker.add("bug", obj["id"],
                                lambda oid=obj["id"]: admin.delete("/api/bugs/{}".format(oid)))

    codes = [r.status_code for r in responses]
    bad = [(r.status_code, (r.text or "")[:200]) for r in responses if r.status_code != 201]
    assert all(c == 201 for c in codes), "并发创建应全部成功，实际状态码 {}；失败响应 {}".format(codes, bad)
    seqs = sorted(body(r)["seq"] for r in responses if r.status_code == 201)
    assert seqs == list(range(1, total + 1)), "序号应为 1..{} 且无重复，实际 {}".format(total, seqs)