#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BugClose 测试数据创建脚本（Python 版，逻辑与 create-test-data.sh 一致，无 jq 依赖）。
走 REST API 创建：10 项目 + 10 Bug(含状态流转) + 10 测试用例(含执行状态) + 10 文档。
"""
import io
import json
import sys
import time
import urllib.error
import urllib.request

# Windows 控制台默认 GBK，强制 stdout/stderr 走 UTF-8，避免 emoji/中文报错
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8080"
TOKEN = None


def login(username="admin", password="admin123"):
    """登录获取 Bearer token（应用对 /api/** 强制鉴权）。"""
    global TOKEN
    url = BASE + "/api/auth/login"
    data = json.dumps({"username": username, "password": password}).encode("utf-8")
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(r, timeout=30) as resp:
        TOKEN = json.loads(resp.read().decode("utf-8"))["token"]
    print(f"  已登录：{username}")


def req(method, path, body=None, form=None):
    """发请求。body=JSON dict 走 JSON；form=dict 赘认 multipart 文本字段。"""
    url = BASE + path
    if form is not None:
        # 构建 multipart/form-data
        boundary = "----bugclose-boundary"
        parts = []
        for k, v in form.items():
            if k == "file":
                # v = (filename, content_bytes)
                fname, content = v
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'
                    f"Content-Type: text/plain\r\n\r\n".encode("utf-8")
                    + content
                    + b"\r\n"
                )
            else:
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                    f"{v}\r\n".encode("utf-8")
                )
        data = b"".join(parts) + f"--{boundary}--\r\n".encode("utf-8")
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}",
                   "Authorization": f"Bearer {TOKEN}"}
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
    else:
        r = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        print(f"  [ERR] {method} {path} -> {e.code}: {msg}")
        return {}
    except urllib.error.URLError as e:
        print(f"  [NET] {method} {path} -> {e}")
        return {}


def get(path):
    try:
        r = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {TOKEN}"})
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [NET] GET {path} -> {e}")
        return []


def main():
    print("==========================================")
    print("  BugClose 测试数据创建脚本 (Python)")
    print("==========================================")

    # 前置：登录获取 token
    print("\n[登录] ...")
    import os
    login(os.environ.get("BUGCLOSE_ADMIN_USER", "admin"),
          os.environ.get("BUGCLOSE_ADMIN_PASS", "admin123"))

    # 0. 清理遗留 projectId 为 null 的文档
    print("\n[0/7] 清理遗留数据...")
    docs = get("/api/docs")
    orphan = [d["id"] for d in docs if d.get("projectId") is None]
    for did in orphan:
        req("DELETE", f"/api/docs/{did}")
    print(f"  已清理 {len(orphan)} 条遗留文档")

    # 1. 创建 10 个项目
    print("\n[1/7] 创建 10 个项目...")
    projects = [
        ("支付中心", "PAY", "统一支付平台，支持多渠道支付接入"),
        ("客户关系管理", "CRM", "客户信息管理与跟进系统"),
        ("电商平台", "MALL", "B2C在线商城，支持商品浏览与下单"),
        ("办公自动化", "OA", "内部审批考勤与流程管理"),
        ("数据中台", "DATA", "数据采集、清洗与报表分析平台"),
        ("物流管理", "WMS", "仓储出入库与库存管理系统"),
        ("人力资源", "HRM", "招聘、薪酬与绩效管理平台"),
        ("在线教育", "EDU", "课程管理与直播授课平台"),
        ("社交媒体", "SNS", "动态发布、关注与评论系统"),
        ("预约挂号", "HOSP", "医院在线挂号与就诊管理"),
    ]
    pids = []
    existing = {p["name"]: p["id"] for p in get("/api/projects")}
    for name, code, desc in projects:
        if name in existing:
            pids.append(existing[name])
            continue
        r = req("POST", "/api/projects", {"name": name, "code": code, "description": desc})
        pids.append(r.get("id"))
    print(f"  项目ID: {pids}")
    if not pids[0]:
        print("  ❌ 项目创建失败"); return 1
    print("  ✅ 10 个项目创建成功")

    # 2. 创建 10 个 Bug
    print("\n[2/7] 创建 10 个 Bug...")
    def bug(pid, title, desc, sev, pri, assignee, env, module, reporter):
        return req("POST", "/api/bugs", {
            "projectId": pid, "title": title, "description": desc,
            "severity": sev, "priority": pri, "assignee": assignee,
            "environment": env, "module": module, "reporter": reporter,
        })
    bs = [
        bug(pids[0], "微信支付回调超时导致订单状态不一致", "用户完成微信支付后回调接口超时导致订单仍显示未支付", "CRITICAL", "URGENT", "张伟", "生产环境", "支付网关", "李明"),
        bug(pids[1], "客户导出Excel时中文乱码", "导出超过1000条客户数据时Excel中中文姓名出现乱码", "HIGH", "HIGH", "王芳", "测试环境", "客户管理", "赵强"),
        bug(pids[2], "购物车商品数量为0时仍可提交订单", "前端未校验数量为0场景后端也缺少拦截导致金额为0异常订单", "HIGH", "URGENT", "刘洋", "测试环境", "购物车", "陈静"),
        bug(pids[3], "审批流程中审批人离职后流程卡住", "审批流程中某审批人已离职流程无法自动跳过", "MEDIUM", "HIGH", "孙丽", "生产环境", "审批流程", "周杰"),
        bug(pids[4], "日报数据聚合时内存溢出", "数据量超过50万条时日报聚合任务OOM导致服务重启", "CRITICAL", "URGENT", "吴磊", "生产环境", "数据报表", "郑华"),
        bug(pids[5], "扫码入库时条码重复未提示", "条码已存在系统未提示直接覆盖原记录", "MEDIUM", "MEDIUM", "马超", "仓库环境", "入库管理", "黄涛"),
        bug(pids[6], "薪资计算未考虑社保基数年度调整", "7月社保基数调整后系统仍用旧基数计算", "HIGH", "HIGH", "林婷", "生产环境", "薪酬模块", "何敏"),
        bug(pids[7], "直播课程在Safari浏览器无法播放", "Safari 17上HLS直播流无法播放Chrome正常", "MEDIUM", "MEDIUM", "杨帆", "测试环境", "直播模块", "徐亮"),
        bug(pids[8], "动态评论数显示与实际不符", "帖子详情页评论数缓存未更新显示数量比实际多", "LOW", "LOW", "韩雪", "生产环境", "社区动态", "曹阳"),
        bug(pids[9], "挂号成功后短信通知延迟超过30分钟", "确认短信延迟严重部分超过30分钟", "LOW", "MEDIUM", "谢楠", "生产环境", "挂号服务", "冯娟"),
    ]
    bids = [b.get("id") for b in bs]
    print(f"  Bug ID: {bids}")

    # 3. 流转状态
    print("\n[3/7] 流转 Bug 状态...")
    def tr(bid, status, assignee):
        req("PUT", f"/api/bugs/{bid}/status", {"status": status, "assignee": assignee})
    tr(bids[1], "IN_PROGRESS", "王芳")
    tr(bids[3], "IN_PROGRESS", "孙丽")
    tr(bids[4], "IN_PROGRESS", "吴磊"); tr(bids[4], "RESOLVED", "吴磊")
    tr(bids[6], "CLOSED", "林婷")
    tr(bids[7], "IN_PROGRESS", "杨帆")
    tr(bids[8], "IN_PROGRESS", "韩雪"); tr(bids[8], "RESOLVED", "韩雪")
    print("  ✅ Bug 状态流转完成")

    # 4. 创建 10 个测试用例
    print("\n[4/7] 创建 10 个测试用例...")
    def tc(pid, title, module, pri, pre, steps, exp, designer):
        return req("POST", "/api/testcases", {
            "projectId": pid, "title": title, "module": module, "priority": pri,
            "precondition": pre, "steps": steps, "expectedResult": exp, "designer": designer,
        })
    tcs = [
        tc(pids[0], "验证支付宝支付成功后订单状态更新", "支付网关", "P0", "用户已登录且订单已创建", "1.选择支付宝支付 2.完成支付 3.查看订单状态", "订单状态变为已支付", "张伟"),
        tc(pids[1], "验证客户信息批量导入功能", "客户管理", "P1", "准备标准CSV模板文件", "1.进入客户导入页面 2.上传CSV文件 3.确认导入", "所有客户数据正确导入且无乱码", "王芳"),
        tc(pids[2], "验证购物车金额计算准确性", "购物车", "P0", "购物车中有多件不同价格商品", "1.添加3件商品 2.修改数量 3.查看总金额", "总金额等于单价乘数量之和精确到分", "刘洋"),
        tc(pids[3], "验证多级审批流程正常流转", "审批流程", "P0", "已配置三级审批流程", "1.提交请假申请 2.一级审批 3.二级审批 4.三级审批", "流程正常结束申请人收到通知", "孙丽"),
        tc(pids[4], "验证大数据量报表导出性能", "数据报表", "P1", "数据库中有100万条记录", "1.选择日报导出 2.选择日期范围 3.点击导出", "报表60秒内生成并下载完成", "吴磊"),
        tc(pids[5], "验证扫码入库重复条码拦截", "入库管理", "P1", "仓库中已有条码A001商品", "1.扫描条码A001 2.输入入库数量 3.确认入库", "系统提示条码已存在拒绝重复入库", "马超"),
        tc(pids[6], "验证薪资计算含社保公积金扣除", "薪酬模块", "P0", "员工薪资与社保基数已配置", "1.运行月度薪资计算 2.查看薪资明细", "应发减社保减公积金减个税等于实发", "林婷"),
        tc(pids[7], "验证直播课程浏览器兼容性", "直播模块", "P2", "直播课程已创建且未开始", "1.Chrome 2.Firefox 3.Safari打开直播", "三种浏览器均可正常播放音视频", "杨帆"),
        tc(pids[8], "验证动态评论实时计数准确性", "社区动态", "P2", "帖子已有5条评论", "1.新增评论 2.查看评论数 3.删除评论 4.再看评论数", "评论数实时增减与数据库一致", "韩雪"),
        tc(pids[9], "验证挂号成功后短信通知及时性", "挂号服务", "P1", "用户已完成挂号并绑定手机号", "1.完成挂号操作 2.等待短信通知", "30秒内收到挂号成功确认短信", "谢楠"),
    ]
    tids = [t.get("id") for t in tcs]
    print(f"  测试用例ID: {tids}")

    # 5. 设置测试用例执行状态
    print("\n[5/7] 设置测试用例执行状态...")
    def ex(tid, status, actual, executor):
        req("PUT", f"/api/testcases/{tid}/execute", {"status": status, "actualResult": actual, "executor": executor})
    ex(tids[0], "PASS", "符合预期，支付回调正常", "张伟")
    ex(tids[1], "PASS", "导入成功，数据完整", "王芳")
    ex(tids[2], "PASS", "金额计算正确，精确到分", "刘洋")
    ex(tids[3], "FAIL", "三级审批通过后页面白屏", "孙丽")
    ex(tids[5], "PASS", "重复条码正确拦截", "马超")
    ex(tids[6], "PASS", "薪资计算准确无误", "林婷")
    ex(tids[7], "BLOCKED", "Safari环境暂不可用", "杨帆")
    ex(tids[8], "PASS", "评论数实时更新正确", "韩雪")
    print("  ✅ 测试用例状态设置完成")

    # 6. 上传 10 个文档
    print("\n[6/7] 创建临时文件并上传 10 个文档...")
    docs_meta = [
        ("支付中心接口文档v2.0", "DESIGN", 0, "支付网关API接口设计说明文档", "张伟"),
        ("CRM需求规格说明书", "REQUIREMENT", 1, "客户关系管理系统完整需求文档", "王芳"),
        ("电商平台测试报告", "TEST", 2, "V3.0版本系统测试报告", "刘洋"),
        ("OA系统用户操作手册", "MANUAL", 3, "办公自动化系统使用指南", "孙丽"),
        ("数据中台技术方案评审纪要", "MEETING", 4, "2026年7月技术方案评审会议记录", "吴磊"),
        ("WMS仓储管理规范", "OTHER", 5, "仓库出入库操作规范与管理制度", "马超"),
        ("HRM薪酬模块设计文档", "DESIGN", 6, "薪酬计算模块详细设计说明", "林婷"),
        ("在线教育平台需求文档", "REQUIREMENT", 7, "课程管理与直播功能需求说明", "杨帆"),
        ("SNS社区运营测试用例集", "TEST", 8, "社交模块全量测试用例", "韩雪"),
        ("医院挂号系统操作手册", "MANUAL", 9, "挂号系统与就诊流程操作指南", "谢楠"),
    ]
    dids = []
    for i, (title, cat, pidx, desc, uploader) in enumerate(docs_meta, start=1):
        content = f"这是第{i}号测试文档的内容，用于BugClose系统文档管理模块测试。".encode("utf-8")
        r = req("POST", "/api/docs", form={
            "file": (f"test-doc-{i}.txt", content),
            "title": title, "category": cat, "projectId": str(pids[pidx]),
            "description": desc, "uploader": uploader,
        })
        dids.append(r.get("id"))
    print(f"  文档ID: {dids}")
    if dids and dids[0]:
        print("  ✅ 10 个文档上传成功")
    else:
        print("  ⚠️  部分文档可能上传失败")

    # 7. 验证
    print("\n[7/7] 验证数据...")
    pc = len(get("/api/projects"))
    bc = len(get("/api/bugs"))
    tcc = len(get("/api/testcases"))
    dc = len(get("/api/docs"))
    print("\n==========================================")
    print("  数据验证结果")
    print("==========================================")
    print(f"  项目:     {pc} 条")
    print(f"  Bug:      {bc} 条")
    print(f"  测试用例: {tcc} 条")
    print(f"  文档:     {dc} 条")
    print("==========================================")
    if pc >= 10 and bc >= 10 and tcc >= 10 and dc >= 10:
        print("  ✅ 测试数据创建完成！")
        return 0
    print("  ⚠️  数据条数不符合预期，请检查！")
    return 1


if __name__ == "__main__":
    sys.exit(main())
