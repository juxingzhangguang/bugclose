# -*- coding: utf-8 -*-
"""测试资源登记与清理：保证用例产生的数据全部回收，不污染业务库。

清理顺序（先子后父）：用户 → 业务数据(缺陷/需求/用例/文档) → 角色 → 项目 → 上传文件。
同类资源按登记的逆序删除；删除失败（如已被用例删掉）只记录不抛错。
"""
import config

PRIORITY = {"user": 0, "bug": 1, "requirement": 1, "testcase": 1, "doc": 1,
            "role": 2, "project": 3, "file": 4}


class Tracker:
    def __init__(self):
        self.items = []       # (priority, seq, kind, label, callable)
        self.errors = []
        self._seq = 0

    def add(self, kind, label, deleter):
        self._seq += 1
        self.items.append((PRIORITY.get(kind, 1), self._seq, kind, label, deleter))

    def forget(self, kind, label):
        """资源已被用例自身删除时调用，避免重复清理。"""
        self.items = [i for i in self.items if not (i[2] == kind and i[3] == label)]

    def cleanup(self):
        if config.KEEP_DATA:
            return ["KEEP_DATA=1，保留 {} 项测试数据".format(len(self.items))]
        for _, _, kind, label, deleter in sorted(self.items, key=lambda x: (x[0], -x[1])):
            try:
                deleter()
            except Exception as exc:      # noqa: BLE001
                self.errors.append("{} {} 清理失败: {}".format(kind, label, exc))
        self.items.clear()
        return self.errors


def sweep_leftovers(admin):
    """清理历史遗留的套件数据（按保留前缀识别），使重复运行不受上次崩溃影响。

    只匹配 AT_ / at_bot_ 前缀，绝不触碰业务数据。
    """
    removed = []
    # 1) 用户
    resp = admin.get("/api/users")
    if resp.status_code == 200:
        for u in resp.json():
            if u["username"].startswith(config.USER_PREFIX) and u["username"] != config.ADMIN_USERNAME:
                if admin.delete("/api/users/{}".format(u["id"])).status_code in (204, 404):
                    removed.append("user:" + u["username"])
    # 2) 角色（非内置）
    resp = admin.get("/api/roles")
    if resp.status_code == 200:
        for r in resp.json():
            if r["code"].startswith(config.ROLE_PREFIX) and not r["builtin"]:
                if admin.delete("/api/roles/{}".format(r["id"])).status_code in (204, 404):
                    removed.append("role:" + r["code"])
    # 3) 项目及其子资源
    resp = admin.get("/api/projects")
    if resp.status_code == 200:
        for p in resp.json():
            if not p["name"].startswith(config.PROJECT_PREFIX):
                continue
            pid = p["id"]
            for path in ("/api/bugs", "/api/requirements", "/api/testcases", "/api/docs"):
                listing = admin.get(path, params={"projectId": pid})
                if listing.status_code != 200:
                    continue
                for row in listing.json():
                    admin.delete("{}/{}".format(path, row["id"]))
            if admin.delete("/api/projects/{}".format(pid)).status_code in (204, 404):
                removed.append("project:" + p["name"])
    # 4) 未关联项目的孤儿数据（管理员可创建 projectId=null 的业务数据，
    #    这类数据不挂在任何 AT_ 项目下，必须按标题前缀单独识别）
    for path in ("/api/bugs", "/api/requirements", "/api/testcases", "/api/docs"):
        listing = admin.get(path)
        if listing.status_code != 200:
            continue
        for row in listing.json():
            if row.get("projectId") is None and (row.get("title") or "").startswith("AT"):
                if admin.delete("{}/{}".format(path, row["id"])).status_code in (204, 404):
                    removed.append("orphan:{}".format(row["title"]))
    return removed