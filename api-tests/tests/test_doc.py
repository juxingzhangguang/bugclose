# -*- coding: utf-8 -*-
"""文档库接口测试：/api/docs（上传归档、版本管理、下载、元信息编辑、权限隔离）。"""
import pytest

import config
from core import data
from core.assertions import (created, error, forbidden, keys, no_content, ok,
                             rejected, unauthorized)
from core.client import body

pytestmark = pytest.mark.case("DOC")

VIEW_KEYS = ["id", "projectId", "projectName", "title", "category", "description",
             "latestVersionNo", "uploader", "createdAt", "updatedAt"]
LATEST_KEYS = ["latestVersionId", "latestFilename", "latestFileSize", "latestUploader"]
VERSION_KEYS = ["id", "documentId", "versionNo", "storedName", "originalFilename",
                "fileSize", "ext", "remark", "uploader", "createdAt"]
DOC_DIR = config.PROJECT_ROOT / "docs"
MB = 1024 * 1024


@pytest.fixture
def proj(factory):
    return factory.project()


def _ids(rows):
    return {r["id"] for r in rows}


def _post_doc(client, tracker, form, files):
    """发 multipart 并在成功时登记清理。

    直接调 admin.post 会绕过 factory 的清理登记，导致文档与物理文件残留，
    因此本模块所有上传都必须走这个包装。
    """
    resp = client.post("/api/docs", data=form, files=files)
    if resp.status_code == 201:
        oid = body(resp)["id"]
        tracker.add("doc", oid, lambda: client.delete("/api/docs/{}".format(oid)))
    return resp


def _upload(admin, proj_id, tracker, **kw):
    """构造标准表单后上传，便于精确控制单个字段。"""
    ext = kw.pop("ext", "txt")
    form = {"title": kw.pop("title", "AT文档_" + data.uniq()),
            "category": kw.pop("category", "TEST"),
            "description": kw.pop("description", "自动化测试文档"),
            "uploader": kw.pop("uploader", "at_bot")}
    if proj_id is not None:
        form["projectId"] = str(proj_id)
    form.update({k: str(v) for k, v in kw.items()})
    return _post_doc(admin, tracker, form, [data.doc_file(ext)])


# ===================================================================== 上传
@pytest.mark.case("DOC-001")
def test_upload_creates_v1(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], ext="pdf", filename="接口文档.pdf")
    keys(doc, VIEW_KEYS + LATEST_KEYS, "文档视图")
    assert doc["latestVersionNo"] == 1
    assert doc["latestFilename"] == "接口文档.pdf"
    assert doc["latestFileSize"] > 0
    assert doc["category"] == "TEST"
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    assert len(versions) == 1
    assert versions[0]["versionNo"] == 1
    assert versions[0]["remark"] == "首次上传", "首版备注固定为「首次上传」"


@pytest.mark.case("DOC-002")
@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
def test_upload_title_required(admin, proj, tracker, blank):
    error(_upload(admin, proj["id"], tracker, title=blank), 400, "文档名称不能为空")


@pytest.mark.case("DOC-003")
def test_upload_missing_title_param(admin, proj, tracker):
    resp = _post_doc(admin, tracker, {"projectId": str(proj["id"])}, [data.doc_file("txt")])
    rejected(resp, "缺少 title 表单字段")
    assert resp.status_code == 400


@pytest.mark.case("DOC-004")
def test_upload_trims_text_fields(admin, proj, tracker):
    obj = created(_upload(admin, proj["id"], tracker, title="  带空格文档  ",
                          description="  带空格说明  ", uploader="  上传人  "))
    assert obj["title"] == "带空格文档"
    assert obj["description"] == "带空格说明"
    assert obj["uploader"] == "上传人"
    assert obj["latestUploader"] == "上传人"


@pytest.mark.case("DOC-005")
def test_upload_category_defaults_to_other(admin, proj, tracker):
    resp = _post_doc(admin, tracker,
                     {"title": "无分类文档", "projectId": str(proj["id"])},
                     [data.doc_file("txt")])
    obj = created(resp)
    assert obj["category"] == "OTHER"


@pytest.mark.case("DOC-006")
@pytest.mark.parametrize("category", config.DOC_CATEGORY)
def test_upload_honours_category(admin, factory, proj, category):
    doc = factory.doc(admin, proj["id"], category=category)
    assert doc["category"] == category


@pytest.mark.case("DOC-007")
def test_admin_upload_without_project(admin, factory):
    doc = factory.doc(admin, None)
    assert doc["projectId"] is None
    assert doc["projectName"] is None


@pytest.mark.case("DOC-008")
def test_view_resolves_project_name(admin, factory, proj):
    doc = factory.doc(admin, proj["id"])
    assert doc["projectId"] == proj["id"]
    assert doc["projectName"] == proj["name"], "列表视图应回填项目名称"


@pytest.mark.case("DOC-009")
@pytest.mark.parametrize("ext", config.DOC_EXT)
def test_allowed_extensions(admin, factory, proj, ext):
    doc = factory.doc(admin, proj["id"], ext=ext)
    assert doc["latestFilename"].endswith("." + ext)
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    assert versions[0]["ext"] == ext


@pytest.mark.case("DOC-010")
def test_extension_case_insensitive(admin, proj, tracker):
    resp = _post_doc(admin, tracker,
                     {"title": "大写扩展名", "projectId": str(proj["id"])},
                     [data.doc_file("pdf", "大写文档.PDF")])
    obj = created(resp)
    assert obj["latestFilename"] == "大写文档.PDF", "原始文件名保留大小写"
    versions = ok(admin.get("/api/docs/{}/versions".format(obj["id"])))
    assert versions[0]["ext"] == "pdf", "扩展名归一化为小写后校验"


@pytest.mark.case("DOC-011")
@pytest.mark.parametrize("filename", ["malware.exe", "script.sh", "page.html", "data.json"])
def test_disallowed_extension_rejected(admin, proj, tracker, filename):
    resp = _post_doc(admin, tracker,
                     {"title": "非法格式", "projectId": str(proj["id"])},
                     [("file", (filename, data.TXT_BYTES, "application/octet-stream"))])
    error(resp, 400, "不支持的文件格式")


@pytest.mark.case("DOC-012")
def test_no_extension_rejected(admin, proj, tracker):
    resp = _post_doc(admin, tracker,
                     {"title": "无扩展名", "projectId": str(proj["id"])},
                     [("file", ("README", data.TXT_BYTES, "application/octet-stream"))])
    error(resp, 400, "不支持的文件格式")


@pytest.mark.case("DOC-013")
def test_empty_file_rejected(admin, proj, tracker):
    resp = _post_doc(admin, tracker,
                     {"title": "空文件", "projectId": str(proj["id"])},
                     [("file", ("empty.txt", b"", "application/octet-stream"))])
    error(resp, 400, "文件为空")


@pytest.mark.case("DOC-014")
@pytest.mark.xfail(reason="后端缺陷 D-03：缺少 file 分片时 @RequestParam 解析失败未被处理，"
                          "返回 500，应为 400", strict=True)
def test_missing_file_part(admin, proj):
    resp = admin.post("/api/docs", data={"title": "缺文件", "projectId": str(proj["id"])})
    error(resp, 400)


@pytest.mark.case("DOC-015")
@pytest.mark.slow
def test_oversize_file_rejected(admin, proj):
    """50MB+1 由 Spring multipart 上限拦截为 413 空体。

    服务层 DocService.validateFile 的「文件不能超过 50MB」分支被
    spring.servlet.multipart.max-file-size=50MB 抢先触发，HTTP 侧不可达。
    """
    resp = admin.post("/api/docs",
                      data={"title": "超限文件", "projectId": str(proj["id"])},
                      files=[data.doc_file("txt", "big.txt", size=50 * MB + 1)])
    assert resp.status_code == 413, "期望 413，实际 {}；响应 {}".format(
        resp.status_code, resp.text[:300])
    assert not resp.content, "413 由容器层直接返回，不带业务错误体"
    assert ok(admin.get("/api/docs", params={"projectId": proj["id"]})) == [], "超限文件不应落库"


@pytest.mark.case("DOC-016")
@pytest.mark.slow
def test_file_size_at_limit(admin, proj, tracker):
    resp = _post_doc(admin, tracker,
                     {"title": "边界文件", "projectId": str(proj["id"])},
                     [data.doc_file("txt", "edge.txt", size=50 * MB)])
    obj = created(resp, "恰好 50MB 应允许")
    assert obj["latestFileSize"] == 50 * MB
    no_content(admin.delete("/api/docs/{}".format(obj["id"])))
    tracker.forget("doc", obj["id"])


# ===================================================================== 查询
@pytest.fixture
def dataset(admin, factory, proj):
    rows = [
        factory.doc(admin, proj["id"], title="Alpha Design Doc", category="DESIGN",
                    description="架构设计说明"),
        factory.doc(admin, proj["id"], title="Beta Test Plan", category="TEST",
                    description="测试计划 alpha 关键字"),
        factory.doc(admin, proj["id"], title="Gamma Meeting Notes", category="MEETING",
                    description="会议纪要"),
    ]
    return {"project": proj, "rows": rows}


@pytest.mark.case("DOC-017")
def test_filter_by_project(admin, dataset):
    rows = ok(admin.get("/api/docs", params={"projectId": dataset["project"]["id"]}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("DOC-018")
@pytest.mark.parametrize("category,index", [("DESIGN", 0), ("TEST", 1), ("MEETING", 2)])
def test_filter_by_category(admin, dataset, category, index):
    rows = ok(admin.get("/api/docs", params={
        "projectId": dataset["project"]["id"], "category": category}))
    assert _ids(rows) == {dataset["rows"][index]["id"]}


@pytest.mark.case("DOC-019")
def test_keyword_matches_title_and_description(admin, dataset):
    pid = dataset["project"]["id"]
    by_title = ok(admin.get("/api/docs", params={"projectId": pid, "keyword": "Plan"}))
    assert _ids(by_title) == {dataset["rows"][1]["id"]}
    by_desc = ok(admin.get("/api/docs", params={"projectId": pid, "keyword": "架构设计"}))
    assert _ids(by_desc) == {dataset["rows"][0]["id"]}


@pytest.mark.case("DOC-020")
def test_keyword_case_insensitive(admin, dataset):
    pid = dataset["project"]["id"]
    lower = ok(admin.get("/api/docs", params={"projectId": pid, "keyword": "alpha"}))
    upper = ok(admin.get("/api/docs", params={"projectId": pid, "keyword": "ALPHA"}))
    assert _ids(lower) == _ids(upper) == {dataset["rows"][0]["id"], dataset["rows"][1]["id"]}


@pytest.mark.case("DOC-021")
def test_combined_filters(admin, dataset):
    rows = ok(admin.get("/api/docs", params={
        "projectId": dataset["project"]["id"], "category": "TEST", "keyword": "beta"}))
    assert _ids(rows) == {dataset["rows"][1]["id"]}


@pytest.mark.case("DOC-022")
def test_blank_keyword_ignored(admin, dataset):
    rows = ok(admin.get("/api/docs",
                        params={"projectId": dataset["project"]["id"], "keyword": "   "}))
    assert _ids(rows) == _ids(dataset["rows"])


@pytest.mark.case("DOC-023")
def test_list_sorted_by_updated_at_desc(admin, dataset):
    rows = ok(admin.get("/api/docs", params={"projectId": dataset["project"]["id"]}))
    stamps = [r["updatedAt"] for r in rows]
    assert stamps == sorted(stamps, reverse=True), "文档列表按更新时间倒序"


@pytest.mark.case("DOC-024")
def test_invalid_category_query_param(admin):
    resp = admin.get("/api/docs", params={"category": "NOT_A_CATEGORY"})
    rejected(resp, "非法分类枚举")
    assert resp.status_code == 400


@pytest.mark.case("DOC-025")
def test_foreign_project_filter_returns_empty(client1, dataset):
    rows = ok(client1.get("/api/docs", params={"projectId": dataset["project"]["id"]}))
    assert rows == []


# ===================================================================== 版本管理
@pytest.mark.case("DOC-026")
def test_add_version_increments(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], ext="txt")
    before = doc["updatedAt"]
    resp = admin.post("/api/docs/{}/versions".format(doc["id"]),
                      data={"remark": "  第二版修订  ", "uploader": "  李四  "},
                      files=[data.doc_file("pdf", "第二版.pdf")])
    obj = created(resp, "上传新版本")
    assert obj["latestVersionNo"] == 2
    assert obj["latestFilename"] == "第二版.pdf"
    assert obj["latestUploader"] == "李四"
    assert obj["updatedAt"] >= before, "新版本应刷新文档更新时间"
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    assert [v["versionNo"] for v in versions] == [2, 1]
    assert versions[0]["remark"] == "第二版修订", "版本备注应 trim"


@pytest.mark.case("DOC-027")
def test_add_multiple_versions(admin, factory, proj):
    doc = factory.doc(admin, proj["id"])
    for i in range(2, 5):
        obj = created(admin.post("/api/docs/{}/versions".format(doc["id"]),
                                 data={"remark": "第{}版".format(i)},
                                 files=[data.doc_file("txt", "v{}.txt".format(i))]))
        assert obj["latestVersionNo"] == i
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    assert [v["versionNo"] for v in versions] == [4, 3, 2, 1]
    assert len({v["storedName"] for v in versions}) == 4, "各版本物理文件名互不相同"


@pytest.mark.case("DOC-028")
def test_add_version_rejects_bad_file(admin, factory, proj):
    doc = factory.doc(admin, proj["id"])
    resp = admin.post("/api/docs/{}/versions".format(doc["id"]),
                      files=[("file", ("bad.exe", data.TXT_BYTES, "application/octet-stream"))])
    error(resp, 400, "不支持的文件格式")
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    assert len(versions) == 1, "校验失败不应新增版本"


@pytest.mark.case("DOC-029")
def test_add_version_doc_not_found(admin):
    resp = admin.post("/api/docs/99999999/versions", files=[data.doc_file("txt")])
    error(resp, 404, "文档不存在: id=99999999")


@pytest.mark.case("DOC-030")
def test_list_versions_fields(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], ext="pdf", filename="版本字段.pdf")
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    keys(versions[0], VERSION_KEYS, "版本记录")
    assert versions[0]["documentId"] == doc["id"]
    assert versions[0]["originalFilename"] == "版本字段.pdf"
    assert versions[0]["fileSize"] == doc["latestFileSize"]


@pytest.mark.case("DOC-031")
def test_list_versions_not_found(admin):
    error(admin.get("/api/docs/99999999/versions"), 404, "文档不存在: id=99999999")


# ===================================================================== 下载
@pytest.mark.case("DOC-032")
def test_download_returns_original_bytes(admin, factory, proj):
    content = b"%PDF-1.4\nAT download payload\n%%EOF\n"
    doc = factory.doc(admin, proj["id"], ext="pdf", filename="中文文件名.pdf", content=content)
    resp = admin.get("/api/docs/{}/versions/{}/download".format(doc["id"], doc["latestVersionId"]))
    assert resp.status_code == 200
    assert resp.content == content, "下载内容应与上传字节完全一致"
    assert resp.headers["Content-Type"] == "application/octet-stream"
    assert int(resp.headers["Content-Length"]) == len(content)
    disposition = resp.headers["Content-Disposition"]
    assert disposition.startswith("attachment"), "应为附件下载"
    assert "filename*=UTF-8''" in disposition, "中文文件名应走 RFC 5987 编码"
    assert "%E4%B8%AD%E6%96%87" in disposition, "「中文」应被百分号编码"


@pytest.mark.case("DOC-033")
def test_download_specific_old_version(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], ext="txt", content=b"v1-content")
    v1 = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))[0]
    created(admin.post("/api/docs/{}/versions".format(doc["id"]),
                       files=[data.doc_file("txt", "v2.txt", content=b"v2-content")]))
    resp = admin.get("/api/docs/{}/versions/{}/download".format(doc["id"], v1["id"]))
    assert resp.status_code == 200
    assert resp.content == b"v1-content", "应能下载历史版本而非最新版"


@pytest.mark.case("DOC-034")
def test_download_version_of_other_doc_rejected(admin, factory, proj):
    a = factory.doc(admin, proj["id"])
    b = factory.doc(admin, proj["id"])
    error(admin.get("/api/docs/{}/versions/{}/download".format(a["id"], b["latestVersionId"])),
          404, "版本不存在")


@pytest.mark.case("DOC-035")
def test_download_missing_version(admin, factory, proj):
    doc = factory.doc(admin, proj["id"])
    error(admin.get("/api/docs/{}/versions/99999999/download".format(doc["id"])),
          404, "版本不存在: id=99999999")


@pytest.mark.case("DOC-036")
def test_download_missing_doc(admin):
    error(admin.get("/api/docs/99999999/versions/1/download"), 404, "版本不存在")


# ===================================================================== 元信息编辑
@pytest.mark.case("DOC-037")
def test_update_metadata(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], title="原标题", description="原说明")
    obj = ok(admin.put("/api/docs/{}".format(doc["id"]),
                       json={"title": "  新标题  ", "category": "MANUAL",
                             "projectId": proj["id"], "description": "  新说明  "}), "编辑文档元信息")
    assert obj["title"] == "新标题"
    assert obj["category"] == "MANUAL"
    assert obj["description"] == "新说明"
    assert obj["latestVersionNo"] == doc["latestVersionNo"], "编辑元信息不影响版本"
    assert obj["latestVersionId"] == doc["latestVersionId"]


@pytest.mark.case("DOC-038")
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["null", "empty", "blank"])
def test_update_title_required(admin, factory, proj, blank):
    doc = factory.doc(admin, proj["id"])
    error(admin.put("/api/docs/{}".format(doc["id"]),
                    json={"title": blank, "projectId": proj["id"]}), 400, "文档名称不能为空")


@pytest.mark.case("DOC-039")
def test_update_keeps_category_when_null(admin, factory, proj):
    doc = factory.doc(admin, proj["id"], category="DESIGN")
    obj = ok(admin.put("/api/docs/{}".format(doc["id"]),
                       json={"title": "只改标题", "category": None, "projectId": proj["id"]}))
    assert obj["category"] == "DESIGN"
    assert obj["description"] is None, "description 传 null 应清空"


@pytest.mark.case("DOC-040")
def test_update_not_found(admin, proj):
    error(admin.put("/api/docs/99999999", json={"title": "x", "projectId": proj["id"]}),
          404, "文档不存在: id=99999999")


@pytest.mark.case("DOC-041")
def test_update_move_project(admin, factory, proj):
    target = factory.project()
    doc = factory.doc(admin, proj["id"])
    obj = ok(admin.put("/api/docs/{}".format(doc["id"]),
                       json={"title": doc["title"], "projectId": target["id"]}))
    assert obj["projectId"] == target["id"]
    assert obj["projectName"] == target["name"]


# ===================================================================== 删除
@pytest.mark.case("DOC-042")
def test_delete_removes_versions_and_files(admin, factory, proj):
    doc = factory.doc(admin, proj["id"])
    created(admin.post("/api/docs/{}/versions".format(doc["id"]),
                       files=[data.doc_file("txt", "v2.txt")]))
    versions = ok(admin.get("/api/docs/{}/versions".format(doc["id"])))
    stored = [DOC_DIR / v["storedName"] for v in versions]
    assert all(p.exists() for p in stored), "删除前物理文件应存在"
    no_content(admin.delete("/api/docs/{}".format(doc["id"])), "删除文档")
    error(admin.get("/api/docs/{}/versions".format(doc["id"])), 404, "文档不存在")
    assert not any(p.exists() for p in stored), "删除文档应连同物理文件一并清理"


@pytest.mark.case("DOC-043")
def test_delete_not_found(admin):
    error(admin.delete("/api/docs/99999999"), 404, "文档不存在: id=99999999")


# ===================================================================== 权限与数据隔离
@pytest.mark.case("DOC-044")
def test_user_cannot_read_foreign_versions(client1, admin, factory, project_b):
    doc = factory.doc(admin, project_b["id"])
    forbidden(client1.get("/api/docs/{}/versions".format(doc["id"])), "无权访问该资源")


@pytest.mark.case("DOC-045")
def test_user_cannot_download_foreign_doc(client1, admin, factory, project_b):
    doc = factory.doc(admin, project_b["id"])
    forbidden(client1.get("/api/docs/{}/versions/{}/download".format(
        doc["id"], doc["latestVersionId"])), "无权访问该资源")


@pytest.mark.case("DOC-046")
def test_user_cannot_upload_to_foreign_project(client1, project_b):
    resp = client1.post("/api/docs",
                        data={"title": "越权上传", "projectId": str(project_b["id"])},
                        files=[data.doc_file("txt")])
    forbidden(resp, "无权操作该项目的数据")


@pytest.mark.case("DOC-047")
def test_user_must_choose_project(client1):
    resp = client1.post("/api/docs", data={"title": "未选项目"}, files=[data.doc_file("txt")])
    error(resp, 400, "请选择所属项目")


@pytest.mark.case("DOC-048")
def test_user_cannot_update_or_delete_foreign(client1, admin, factory, project_b):
    doc = factory.doc(admin, project_b["id"])
    forbidden(client1.put("/api/docs/{}".format(doc["id"]),
                          json={"title": "越权改名", "projectId": project_b["id"]}),
              "无权访问该资源")
    forbidden(client1.delete("/api/docs/{}".format(doc["id"])), "无权访问该资源")
    forbidden(client1.post("/api/docs/{}/versions".format(doc["id"]),
                           files=[data.doc_file("txt")]), "无权访问该资源")


@pytest.mark.case("DOC-049")
def test_user_cannot_see_unassigned_doc(client1, admin, factory):
    doc = factory.doc(admin, None)
    forbidden(client1.get("/api/docs/{}/versions".format(doc["id"])), "无权访问该资源")
    assert doc["id"] not in _ids(ok(client1.get("/api/docs")))


@pytest.mark.case("DOC-050")
def test_user_list_only_bound_projects(client1, admin, factory, project_a, project_b):
    mine = factory.doc(admin, project_a["id"])
    foreign = factory.doc(admin, project_b["id"])
    rows = ok(client1.get("/api/docs"))
    assert mine["id"] in _ids(rows)
    assert foreign["id"] not in _ids(rows)
    assert all(r["projectId"] == project_a["id"] for r in rows)


@pytest.mark.case("DOC-051")
def test_user_full_flow_within_bound_project(client1, factory, project_a):
    doc = factory.doc(client1, project_a["id"], title="普通用户自建文档")
    created(client1.post("/api/docs/{}/versions".format(doc["id"]),
                         files=[data.doc_file("txt", "v2.txt")]))
    ok(client1.get("/api/docs/{}/versions".format(doc["id"])))
    resp = client1.get("/api/docs/{}/versions/{}/download".format(doc["id"], doc["latestVersionId"]))
    assert resp.status_code == 200
    ok(client1.put("/api/docs/{}".format(doc["id"]),
                   json={"title": "普通用户改名", "projectId": project_a["id"]}))
    no_content(client1.delete("/api/docs/{}".format(doc["id"])))


@pytest.mark.case("DOC-052")
def test_docs_require_auth(anon):
    unauthorized(anon.get("/api/docs"))
    unauthorized(anon.post("/api/docs", data={"title": "x"}, files=[data.doc_file("txt")]))
    unauthorized(anon.get("/api/docs/1/versions"))
    unauthorized(anon.get("/api/docs/1/versions/1/download"))