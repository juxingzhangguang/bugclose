# -*- coding: utf-8 -*-
"""断言助手：区分「业务错误体」与「框架默认错误体」。

后端业务异常统一返回 {"error": "..."}；
参数类型/缺失、JSON 解析失败等由 Spring Boot 默认错误处理返回
{"timestamp":..,"status":..,"error":"Bad Request","path":..}，两者形状不同。
"""
from core.client import body


def status(resp, expected, hint=""):
    actual = resp.status_code
    assert actual == expected, "{}期望 HTTP {}，实际 {}；响应={}".format(
        hint + " " if hint else "", expected, actual, _brief(resp))
    return body(resp)


def created(resp, hint=""):
    return status(resp, 201, hint)


def ok(resp, hint=""):
    return status(resp, 200, hint)


def no_content(resp, hint=""):
    assert resp.status_code == 204, "{}期望 204，实际 {}；响应={}".format(
        hint + " " if hint else "", resp.status_code, _brief(resp))
    assert not resp.content, "204 响应不应带响应体，实际 {} 字节".format(len(resp.content))


def error(resp, expected_status, contains=None, hint=""):
    """断言业务错误：状态码 + {"error": "..."} 中包含指定文案。"""
    data = status(resp, expected_status, hint)
    assert isinstance(data, dict) and "error" in data, \
        "期望业务错误体 {{'error': ...}}，实际 {}".format(_brief(resp))
    if contains is not None:
        msg = data["error"] or ""
        assert contains in msg, "期望错误信息包含「{}」，实际「{}」".format(contains, msg)
    return data["error"]


def rejected(resp, hint=""):
    """断言请求被拒绝（4xx/5xx 均可），用于框架层校验与未处理的完整性异常。"""
    assert resp.status_code >= 400, "{}期望请求被拒绝(>=400)，实际 {}；响应={}".format(
        hint + " " if hint else "", resp.status_code, _brief(resp))
    return resp.status_code


def unauthorized(resp, hint=""):
    data = status(resp, 401, hint)
    assert isinstance(data, dict) and "error" in data, "401 应返回 {'error': ...}"
    return data


def forbidden(resp, contains=None, hint=""):
    return error(resp, 403, contains, hint)


def keys(obj, required, hint=""):
    assert isinstance(obj, dict), "{}期望对象，实际 {}".format(hint, type(obj))
    missing = [k for k in required if k not in obj]
    assert not missing, "{}缺少字段 {}".format(hint + " " if hint else "", missing)


def no_keys(obj, forbidden_keys, hint=""):
    assert isinstance(obj, dict)
    leaked = [k for k in forbidden_keys if k in obj]
    assert not leaked, "{}不应返回敏感字段 {}".format(hint + " " if hint else "", leaked)


def same_time(a, b, hint=""):
    """比较两个 ISO 时间字符串到秒级。

    创建响应里的时间来自 Java LocalDateTime（纳秒），
    再次读库时 MySQL datetime(6) 会四舍五入到微秒，末位可能差 1，
    因此不能直接做字符串全等比较。
    """
    assert a and b, "{}时间字段为空: {} / {}".format(hint, a, b)
    assert a[:19] == b[:19], "{}期望时间 {}，实际 {}".format(hint + " " if hint else "", a, b)


def _brief(resp):
    try:
        text = resp.text
    except Exception:      # noqa: BLE001
        return "<unreadable>"
    return text[:400] if text else "<empty>"