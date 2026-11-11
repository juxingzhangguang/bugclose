# -*- coding: utf-8 -*-
"""汇总全部用例；用例编号唯一性在此校验。"""
from ._base import C, COLUMNS, COMMON_PRE, MODULE_ORDER  # noqa: F401
from . import (auth, project, requirement, testcase, bug, doc,  # noqa: F401
               user, role, upload, dashboard, permission, security)

_MODULES = [auth, project, requirement, testcase, bug, doc,
            user, role, upload, dashboard, permission, security]


def all_cases():
    cases = []
    for m in _MODULES:
        cases.extend(m.CASES)
        cases.extend(getattr(m, "MANUAL", []))   # 手工用例同样进文档，只是没有自动化节点
    ids = [c["用例编号"] for c in cases]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, "用例编号重复: {}".format(sorted(dup))
    order = {name: idx for idx, name in enumerate(MODULE_ORDER)}
    return sorted(cases, key=lambda c: (order[c["所属模块"]], c["用例编号"]))