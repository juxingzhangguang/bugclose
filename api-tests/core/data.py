# -*- coding: utf-8 -*-
"""测试数据构造：最小化文件样例 + 各模块 payload 工厂。

文件样例遵循「扩展名 + 魔数」的最小构造原则，不生成真实容器内容，
既能通过后端扩展名/大小校验，又保持体积极小、可重复。
"""
import base64
import itertools
import threading
import uuid

import config

# 1x1 透明 PNG（真实魔数，89 字节）
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 16 + b"\xff\xd9"
GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"
WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00" + b"\x00" * 14
BMP_BYTES = b"BM\x3a\x00\x00\x00\x00\x00\x00\x00\x36\x00\x00\x00" + b"\x00" * 40
PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
ZIP_BYTES = b"PK\x05\x00" + b"\x00" * 18
TXT_BYTES = "接口自动化测试样例文件\n".encode("utf-8")

IMAGE_MAGIC = {
    "png": PNG_BYTES, "jpg": JPEG_BYTES, "jpeg": JPEG_BYTES,
    "gif": GIF_BYTES, "webp": WEBP_BYTES, "bmp": BMP_BYTES,
}
DOC_MAGIC = {
    "pdf": PDF_BYTES, "zip": ZIP_BYTES, "rar": b"Rar!\x1a\x07\x00" + b"\x00" * 16,
    "7z": b"7z\xbc\xaf\x27\x1c" + b"\x00" * 16,
    "doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 24,
    "docx": ZIP_BYTES, "xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 24,
    "xlsx": ZIP_BYTES, "ppt": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 24,
    "pptx": ZIP_BYTES, "txt": TXT_BYTES, "md": b"# AT sample\n",
    "png": PNG_BYTES, "jpg": JPEG_BYTES,
}


def uniq(suffix=""):
    return config.TAG + ("_" + suffix if suffix else "") + "_" + uuid.uuid4().hex[:6]


def image_file(ext="png", filename=None, size=None):
    """返回 requests 的 files 参数元组。size 指定时补足到该字节数（用于超限用例）。"""
    content = IMAGE_MAGIC.get(ext.lower(), PNG_BYTES)
    if size is not None:
        content = content + b"\x00" * max(0, size - len(content))
    name = filename or ("at_" + uuid.uuid4().hex[:8] + "." + ext)
    return ("file", (name, content, "application/octet-stream"))


def doc_file(ext="txt", filename=None, size=None, content=None):
    data = content if content is not None else DOC_MAGIC.get(ext.lower(), TXT_BYTES)
    if size is not None:
        data = data + b"\x00" * max(0, size - len(data))
    name = filename or ("at_" + uuid.uuid4().hex[:8] + "." + ext)
    return ("file", (name, data, "application/octet-stream"))


# ------------------------------------------------------------------ payload 工厂
_UNSET = object()


def _default(value, fallback):
    """只有 None 才取默认值；空串/纯空格必须原样传出，用于空值校验用例。"""
    return fallback() if value is None else value


_CODE_SEQ = itertools.count(1)
_CODE_LOCK = threading.Lock()


def short_code(suffix="C"):
    """项目/角色编号上限 20 位。

    TAG(14) + 用途后缀(1) + 进程内递增序号(5) = 20 位，
    同一次运行内绝不重复（纯随机 4 位 hex 在几十个项目的规模下会按生日悖论撞号），
    跨运行由 TAG 中的时间戳 + uuid 区分。
    """
    with _CODE_LOCK:
        n = next(_CODE_SEQ)
    return (config.TAG + suffix + "{:05d}".format(n))[:20]


def project(name=None, code=_UNSET, description="接口自动化测试项目"):
    return {
        "name": _default(name, lambda: config.PROJECT_PREFIX + uniq("P")),
        "code": short_code("C") if code is _UNSET else code,
        "description": description,
    }


def bug(project_id, title=None, **kw):
    payload = {
        "projectId": project_id,
        "title": _default(title, lambda: "AT缺陷_" + uniq()),
        "description": "自动化测试生成的缺陷描述",
        "severity": "MEDIUM",
        "priority": "MEDIUM",
        "environment": "测试环境",
        "module": "登录模块",
        "reporter": "at_bot",
        "assignee": None,
    }
    payload.update(kw)
    return payload


def requirement(project_id, title=None, **kw):
    payload = {
        "projectId": project_id,
        "title": _default(title, lambda: "AT需求_" + uniq()),
        "description": "自动化测试生成的需求描述",
        "period": "一期",
        "module": "登录模块",
        "proposer": "at_bot",
        "assignee": None,
    }
    payload.update(kw)
    return payload


def testcase(project_id, title=None, **kw):
    payload = {
        "projectId": project_id,
        "title": _default(title, lambda: "AT用例_" + uniq()),
        "module": "登录模块",
        "precondition": "已打开登录页",
        "steps": "1. 输入用户名\n2. 输入密码\n3. 点击登录",
        "expectedResult": "登录成功并跳转首页",
        "designer": "at_bot",
    }
    payload.update(kw)
    return payload


def user(username=None, password="At#12345", role="USER", project_ids=None, **kw):
    payload = {
        "username": _default(username, lambda: config.USER_PREFIX + uniq("u").lower()),
        "password": password,
        "displayName": "自动化测试账号",
        "role": role,
        "enabled": True,
        "projectIds": list(project_ids) if project_ids else [],
    }
    payload.update(kw)
    return payload


def role(code=None, name=None, description="接口自动化测试角色"):
    return {
        "code": _default(code, lambda: short_code("R")),
        "name": _default(name, lambda: "AT角色_" + uniq()),
        "description": description,
    }