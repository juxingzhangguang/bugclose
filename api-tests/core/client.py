# -*- coding: utf-8 -*-
"""HTTP 客户端封装：统一注入 Bearer / X-Forwarded-For，记录调用轨迹便于失败定位。"""
import json as _json

import requests

import config


class ApiClient:
    """一个 ApiClient 代表一个「登录身份 + 来源 IP」。

    - token 为空时不注入 Authorization（用于匿名 / 越权用例）
    - ip 会写入 X-Forwarded-For，后端限流按 用户名+IP 分桶，
      因此不同身份使用不同 IP 可彻底避免用例之间相互锁定。
    """

    def __init__(self, name="anonymous", token=None, ip=None, base_url=None):
        self.name = name
        self.token = token
        self.ip = ip
        self.base_url = (base_url or config.BASE_URL).rstrip("/")
        self.session = requests.Session()
        self.history = []
        self.me = None          # 登录成功后缓存的用户信息
        self.user_id = None

    # ------------------------------------------------------------------ 底层
    def request(self, method, path, *, params=None, json=None, data=None, files=None,
                headers=None, token="__default__", timeout=None, allow_redirects=False):
        url = path if path.startswith("http") else self.base_url + path
        h = {"Accept": "application/json"}
        if self.ip:
            h["X-Forwarded-For"] = self.ip
        use_token = self.token if token == "__default__" else token
        if use_token:
            h["Authorization"] = "Bearer " + use_token
        if headers:
            h.update(headers)
        resp = self.session.request(
            method.upper(), url, params=params, json=json, data=data, files=files,
            headers=h, timeout=timeout or config.TIMEOUT, allow_redirects=allow_redirects,
        )
        self.history.append({
            "method": method.upper(), "url": url, "status": resp.status_code,
            "request": json if json is not None else data, "response": _safe_text(resp),
        })
        if len(self.history) > 400:
            del self.history[:200]
        return resp

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def patch(self, path, **kw):
        return self.request("PATCH", path, **kw)

    # ------------------------------------------------------------------ 业务快捷方法
    def login(self, username, password, ip=None):
        old_ip = self.ip
        if ip:
            self.ip = ip
        resp = self.post("/api/auth/login", json={"username": username, "password": password})
        self.ip = old_ip
        if resp.status_code == 200:
            body = resp.json()
            self.token = body["token"]
            self.me = body
            self.user_id = body["id"]
            self.name = username
        return resp

    def logout(self):
        resp = self.post("/api/auth/logout")
        self.token = None
        return resp

    def change_password(self, old, new):
        return self.post("/api/auth/change-password", json={"oldPassword": old, "newPassword": new})

    def fetch_me(self):
        resp = self.get("/api/auth/me")
        if resp.status_code == 200:
            self.me = resp.json()
            self.user_id = self.me["id"]
        return resp

    def clone(self, name=None, token="__default__", ip=None):
        """复制一个同身份客户端（用于多端会话 / 对照实验）。"""
        return ApiClient(name or (self.name + "-clone"),
                         self.token if token == "__default__" else token,
                         ip if ip is not None else self.ip, self.base_url)

    def dump_history(self, limit=8):
        lines = []
        for item in self.history[-limit:]:
            lines.append("  {} {} -> {}".format(item["method"], item["url"], item["status"]))
            if item["request"] is not None:
                lines.append("    req: " + str(item["request"])[:300])
            lines.append("    res: " + str(item["response"])[:300])
        return "\n".join(lines)


def _safe_text(resp):
    try:
        if not resp.content:
            return "<empty>"
        ctype = resp.headers.get("Content-Type", "")
        if "json" in ctype:
            return _json.dumps(resp.json(), ensure_ascii=False)
        if ctype.startswith("text/") or "javascript" in ctype:
            return resp.text[:500]
        return "<binary {} bytes>".format(len(resp.content))
    except Exception as exc:      # noqa: BLE001
        return "<unreadable: {}>".format(exc)


def body(resp):
    """安全取 JSON；空响应体返回 None（204 场景）。"""
    if not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return None