# -*- coding: utf-8 -*-
"""图片上传接口测试：/api/uploads 与 /uploads/** 静态资源。

覆盖格式白名单、大小边界、存储命名安全、静态资源鉴权（含 ?token= 通道）。
"""
import re

import pytest

import config
from core import data
from core.assertions import (error, keys, ok, rejected, status, unauthorized)
from core.client import ApiClient, body

pytestmark = pytest.mark.case("UP")

UPLOAD_DIR = config.PROJECT_ROOT / "uploads"
MB = 1024 * 1024
MAX_IMG = 5 * MB
UUID_NAME = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[a-z]+$")


def _local(url):
    return config.PROJECT_ROOT / url.lstrip("/")


def _post_img(client, tracker, files):
    """发 multipart 并在成功时登记物理文件清理。

    直接调 client.post 会绕过 factory 的登记，导致 uploads/ 目录残留文件。
    """
    resp = client.post("/api/uploads", files=files)
    if resp.status_code == 200:
        url = body(resp)["url"]
        tracker.add("file", url, lambda: _local(url).unlink(missing_ok=True))
    return resp


def _stale(token):
    """持旧 token 的独立客户端（登出/吊销后验证失效）。"""
    return ApiClient("stale-token", token=token, ip="10.199.0.98")


def _assert_stored(obj, ext):
    keys(obj, ["url"], "上传响应")
    assert set(obj) == {"url"}, "上传响应只应含 url 字段，实际 {}".format(sorted(obj))
    url = obj["url"]
    assert url.startswith("/uploads/"), "url 应为 /uploads/ 前缀，实际 " + url
    name = url.rsplit("/", 1)[-1]
    assert UUID_NAME.match(name), "存储名应为 UUID.扩展名，实际 " + name
    assert name.endswith("." + ext), "扩展名应保留为小写 " + ext
    local = _local(url)
    assert local.is_file(), "文件应落盘到 uploads/：" + str(local)
    return local


# ===================================================================== 上传成功
@pytest.mark.case("UP-001")
def test_upload_png(admin, factory):
    obj = factory.upload(admin, ext="png")
    local = _assert_stored(obj, "png")
    assert local.read_bytes() == data.PNG_BYTES, "落盘内容应与上传字节完全一致"
    resp = admin.get(obj["url"])
    status(resp, 200, "读取已上传图片")
    assert resp.content == data.PNG_BYTES
    assert resp.headers["Content-Type"] == "image/png"


@pytest.mark.case("UP-002")
@pytest.mark.parametrize("ext", config.IMG_EXT)
def test_all_image_formats(admin, factory, ext):
    obj = factory.upload(admin, ext=ext)
    local = _assert_stored(obj, ext)
    assert local.read_bytes() == data.IMAGE_MAGIC[ext]


@pytest.mark.case("UP-003")
def test_extension_case_insensitive(admin, factory):
    obj = factory.upload(admin, ext="png", filename="AT_UPPER.PNG")
    _assert_stored(obj, "png")


@pytest.mark.case("UP-013")
def test_chinese_filename(admin, factory):
    obj = factory.upload(admin, ext="png", filename="中文图片 测试.png")
    local = _assert_stored(obj, "png")
    assert "中文" not in local.name, "原始文件名不参与存储命名"


@pytest.mark.case("UP-014")
def test_very_long_filename(admin, factory):
    obj = factory.upload(admin, ext="png", filename="a" * 256 + ".png")
    _assert_stored(obj, "png")


@pytest.mark.case("UP-016")
def test_same_filename_gets_unique_url(admin, factory):
    name = "at_same_name.png"
    first = factory.upload(admin, ext="png", filename=name)
    second = factory.upload(admin, ext="png", filename=name)
    assert first["url"] != second["url"], "同名文件两次上传应得到不同存储名，不互相覆盖"
    assert _local(first["url"]).is_file() and _local(second["url"]).is_file()


# ===================================================================== 上传校验
@pytest.mark.case("UP-004")
def test_empty_file_rejected(admin):
    resp = admin.post("/api/uploads",
                      files=[("file", ("at_empty.png", b"", "application/octet-stream"))])
    error(resp, 400, "文件为空")


@pytest.mark.case("UP-005")
def test_over_size_rejected(admin):
    before = {p.name for p in UPLOAD_DIR.glob("*")}
    resp = admin.post("/api/uploads", files=[data.image_file("png", size=MAX_IMG + 1)])
    error(resp, 400, "图片不能超过 5MB")
    assert {p.name for p in UPLOAD_DIR.glob("*")} == before, "超限请求不应落盘"


@pytest.mark.case("UP-006")
@pytest.mark.slow
def test_size_boundary_exact_5mb(admin, factory):
    before = {p.name for p in UPLOAD_DIR.glob("*")}
    obj = factory.upload(admin, ext="png", size=MAX_IMG)
    local = _assert_stored(obj, "png")
    assert local.stat().st_size == MAX_IMG, "恰好 5MB 应放行（校验为 > 而非 >=）"
    local.unlink()
    factory.tracker.forget("file", obj["url"])
    assert {p.name for p in UPLOAD_DIR.glob("*")} == before


@pytest.mark.case("UP-007")
@pytest.mark.parametrize("ext", ["txt", "pdf", "zip", "exe", "html", "svg", "jsp"])
def test_non_image_extension_rejected(admin, ext):
    resp = admin.post("/api/uploads", files=[data.image_file(ext, "at_sample." + ext)])
    msg = error(resp, 400, "仅支持图片格式")
    # ALLOWED_EXT 是 Set.of(...)，迭代顺序由 JVM 随机化，只断言前缀不断言括号内列表
    assert "[" in msg and "]" in msg


@pytest.mark.case("UP-008")
def test_no_extension_rejected(admin):
    resp = admin.post("/api/uploads",
                      files=[("file", ("at_noext", data.PNG_BYTES, "application/octet-stream"))])
    error(resp, 400, "仅支持图片格式")


@pytest.mark.case("UP-009")
def test_double_extension_rejected(admin):
    resp = admin.post("/api/uploads",
                      files=[("file", ("at_shell.png.exe", data.PNG_BYTES, "application/octet-stream"))])
    error(resp, 400, "仅支持图片格式")


@pytest.mark.case("UP-010")
@pytest.mark.xfail(reason="后端缺陷 D-03：缺少 multipart file 部分时抛 "
                          "MissingServletRequestPartException，未被全局异常处理器覆盖，返回 500",
                   strict=True)
def test_missing_file_part(admin):
    resp = admin.post("/api/uploads", data={"note": "no file part"})
    rejected(resp, "缺少 file 部分")
    assert resp.status_code == 400, "缺少必填上传部分应为 400，实际 {}".format(resp.status_code)


@pytest.mark.case("UP-011")
def test_wrong_part_name_rejected(admin):
    resp = admin.post("/api/uploads",
                      files=[("image", ("at_x.png", data.PNG_BYTES, "application/octet-stream"))])
    rejected(resp, "part 名不是 file")
    assert resp.status_code == 400
    assert body(resp).get("status") == 400, "框架默认错误体应含 status 字段"


@pytest.mark.case("UP-017")
def test_get_uploads_not_allowed(admin):
    status(admin.get("/api/uploads"), 405, "上传接口只支持 POST")


# ===================================================================== 存储命名安全
@pytest.mark.case("UP-012")
def test_traversal_filename_neutralized(admin, factory):
    obj = factory.upload(admin, ext="png", filename="../../at_evil.png")
    local = _assert_stored(obj, "png")
    assert local.parent.resolve() == UPLOAD_DIR.resolve(), "文件必须落在 uploads/ 内"
    assert not (config.PROJECT_ROOT / "at_evil.png").exists(), "不得写出到项目根目录"
    assert not (config.PROJECT_ROOT.parent / "at_evil.png").exists(), "不得写出到上级目录"


@pytest.mark.case("UP-015")
def test_content_not_validated_only_extension(admin, factory):
    """现状确认：只按扩展名白名单放行，不校验文件魔数/真实类型。

    纯文本改名为 .png 也能上传成功，且静态资源按扩展名返回 image/png。
    风险：可上传伪装成图片的任意内容（如 HTML/脚本），
    若未来放宽扩展名或浏览器发生 MIME 嗅探，可能形成存储型 XSS。
    """
    payload = b"<html><script>alert(1)</script></html>"
    resp = _post_img(admin, factory.tracker,
                     [("file", ("at_fake.png", payload, "application/octet-stream"))])
    obj = ok(resp, "伪装图片上传")
    local = _assert_stored(obj, "png")
    assert local.read_bytes() == payload
    got = admin.get(obj["url"])
    status(got, 200, "读取伪装图片")
    assert got.headers["Content-Type"] == "image/png", "Content-Type 由扩展名推断，与内容无关"


# ===================================================================== 上传权限
@pytest.mark.case("UP-018")
def test_upload_requires_auth(anon):
    unauthorized(anon.post("/api/uploads", files=[data.image_file("png")]), "匿名上传")


@pytest.mark.case("UP-019")
def test_normal_user_can_upload(client1, factory):
    obj = factory.upload(client1, ext="png")
    _assert_stored(obj, "png")


# ===================================================================== 静态资源鉴权
@pytest.mark.case("UP-020")
def test_static_requires_auth(anon, factory, admin):
    obj = factory.upload(admin, ext="png")
    unauthorized(anon.get(obj["url"]), "匿名读取上传图片")


@pytest.mark.case("UP-021")
def test_static_with_bearer(admin, factory):
    obj = factory.upload(admin, ext="png")
    resp = admin.get(obj["url"])
    status(resp, 200, "Bearer 读取图片")
    assert resp.content == data.PNG_BYTES
    assert resp.headers["Content-Type"] == "image/png"


@pytest.mark.case("UP-022")
def test_static_with_query_token(anon, admin, factory):
    """<img src> 无法带 Authorization 头，/uploads/ 允许 ?token= 通道。"""
    obj = factory.upload(admin, ext="png")
    resp = anon.get(obj["url"], params={"token": admin.token})
    status(resp, 200, "查询参数 token")
    assert resp.content == data.PNG_BYTES


@pytest.mark.case("UP-023")
def test_static_with_invalid_query_token(anon, admin, factory):
    obj = factory.upload(admin, ext="png")
    unauthorized(anon.get(obj["url"], params={"token": "0" * 64}), "伪造 token")
    unauthorized(anon.get(obj["url"], params={"token": ""}), "空 token")


@pytest.mark.case("UP-024")
def test_query_token_not_accepted_on_api(anon, admin):
    """?token= 只对 /uploads/ 生效，API 仍必须走 Authorization 头，避免 token 进 URL 日志。"""
    unauthorized(anon.get("/api/auth/me", params={"token": admin.token}), "API 查询参数 token")
    unauthorized(anon.get("/api/projects", params={"token": admin.token}))


@pytest.mark.case("UP-025")
def test_static_after_logout(factory, admin, ip_pool):
    acct = factory.user()
    c = ApiClient(acct["username"], ip=ip_pool())
    assert c.login(acct["username"], acct["password"]).status_code == 200
    obj = factory.upload(c, ext="png")
    token = c.token
    ok(c.get(obj["url"]), "登出前可读")
    c.logout()
    unauthorized(_stale(token).get(obj["url"]), "登出后旧 token 应立即失效")


@pytest.mark.case("UP-026")
def test_static_missing_file(admin):
    status(admin.get("/uploads/at_does_not_exist_9999.png"), 404, "不存在的图片")


@pytest.mark.case("UP-027")
@pytest.mark.parametrize("path", ["/uploads/../application.properties",
                                  "/uploads/%2e%2e/application.properties",
                                  "/uploads/..%2fapplication.properties"],
                         ids=["dotdot", "encoded", "mixed"])
def test_static_path_traversal(admin, path):
    resp = admin.get(path)
    assert resp.status_code in (400, 404), "路径穿越应被拒绝，实际 {}".format(resp.status_code)
    assert b"spring.datasource" not in resp.content, "不得泄露配置文件内容"


@pytest.mark.case("UP-028")
def test_static_no_per_project_authorization(admin, client1, client2, factory):
    """现状确认：/uploads/** 只校验登录态，不校验图片归属项目。

    client2 未绑定 client1 的项目，仍能读取对方上传的图片。
    风险：缺陷截图可能含敏感信息，URL 一旦泄露即可被任意登录用户读取。
    """
    obj = factory.upload(client1, ext="png")
    resp = client2.get(obj["url"])
    status(resp, 200, "跨项目读取他人图片")
    assert resp.content == data.PNG_BYTES