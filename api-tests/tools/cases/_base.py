# -*- coding: utf-8 -*-
"""用例登记基础设施：用例文档与自动化脚本共用的唯一数据源。"""

COLUMNS = ["用例编号", "所属模块", "用例标题", "优先级", "用例类型",
           "前置条件", "测试步骤", "预期结果", "自动化脚本", "执行结果", "备注"]

MODULE_ORDER = ["认证", "项目管理", "需求管理", "测试用例", "缺陷管理", "文档库",
                "用户管理", "角色管理", "图片上传", "统计看板", "权限与数据隔离", "安全加固"]


def C(cid, module, title, pre, steps, exp, pri="P1", kind="正常", auto="", note=""):
    """登记一条接口测试用例。

    cid    用例编号，如 AUTH-001
    module 所属模块（见 MODULE_ORDER）
    pre    前置条件
    steps  测试步骤（含接口方法/路径/关键参数）
    exp    预期结果（含状态码与关键字段/文案）
    pri    P0 冒烟 / P1 核心 / P2 一般 / P3 边缘
    kind   正常 / 异常 / 边界 / 权限 / 安全 / 并发 / 手工
    auto   对应自动化脚本节点（相对 api-tests 目录），空表示手工执行
    """
    assert module in MODULE_ORDER, "未知模块: " + module
    return {
        "用例编号": cid, "所属模块": module, "用例标题": title,
        "优先级": pri, "用例类型": kind, "前置条件": pre,
        "测试步骤": steps, "预期结果": exp, "自动化脚本": auto,
        "执行结果": "", "备注": note,
    }


COMMON_PRE = "服务已启动（http://localhost:8080）；套件管理员已登录；测试项目 A/B/C 与测试账号已就绪"