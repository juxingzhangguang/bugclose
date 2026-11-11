# -*- coding: utf-8 -*-
"""校验用例文档与自动化脚本一一对应。

检查三件事：
  1. 登记表里每条自动化用例的编号，都能在对应脚本里找到 @pytest.mark.case("编号")
  2. 脚本里每个 @pytest.mark.case("编号") 都在登记表里存在（无孤儿脚本）
  3. 登记表「自动化脚本」指向的 tests/xxx.py::test_yyy 节点真实存在

用法（在 api-tests 目录下）：
    python tools/check_coverage.py
退出码 0 = 全部对齐，1 = 存在缺口。
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from tools.cases import all_cases  # noqa: E402

CASE_MARK = re.compile(r'pytest\.mark\.case\(\s*"([A-Z]+-\d+)"\s*\)')
FUNC_DEF = re.compile(r"^def (test_\w+)\(", re.M)


def scan_scripts():
    """返回 {用例编号: [(文件, 函数)]}、{文件: {函数名}}、模块级标记文件列表。"""
    marks = defaultdict(list)
    funcs = {}
    module_level = []
    for path in sorted((config.TESTS_ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        rel = "tests/" + path.name
        funcs[rel] = set(FUNC_DEF.findall(text))
        if re.search(r'^pytestmark\s*=.*pytest\.mark\.case\(', text, re.M):
            module_level.append(rel)
        # 标记写在函数上方：从标记行往下找第一个 def test_xxx 即为归属函数
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            for cid in CASE_MARK.findall(line):
                for nxt in lines[idx + 1:]:
                    m = re.match(r"def (test_\w+)\(", nxt)
                    if m:
                        marks[cid].append((rel, m.group(1)))
                        break
                    if re.match(r"(class |def |@pytest\.fixture)", nxt):
                        break
    return marks, funcs, module_level


def main():
    cases = all_cases()
    marks, funcs, module_level = scan_scripts()
    auto = {c["用例编号"]: c for c in cases if c["自动化脚本"]}
    manual = [c["用例编号"] for c in cases if not c["自动化脚本"]]

    problems = []

    # 1 + 3：登记表 -> 脚本
    for cid, c in auto.items():
        node = c["自动化脚本"]
        if cid not in marks:
            problems.append("[缺标记] {} 在脚本里没有 @pytest.mark.case(\"{}\")".format(cid, cid))
        if "::" not in node:
            problems.append("[节点格式] {} 自动化脚本应为 tests/xxx.py::test_yyy，实际 {}".format(cid, node))
            continue
        file, func = node.split("::", 1)
        if file not in funcs:
            problems.append("[缺文件] {} 指向不存在的脚本 {}".format(cid, file))
        elif func not in funcs[file]:
            problems.append("[缺函数] {} 指向 {} 中不存在的 {}".format(cid, node, func))
        elif marks.get(cid) and (file, func) not in marks[cid]:
            problems.append("[标记错位] {} 标记打在 {}，登记表写的是 {}".format(
                cid, marks[cid], node))

    # 2：脚本 -> 登记表
    known = set(c["用例编号"] for c in cases)
    for cid, where in sorted(marks.items()):
        if cid not in known:
            problems.append("[孤儿脚本] {} 有标记但登记表里没有该用例（{}）".format(cid, where))

    print("用例总数 {}：自动化 {}，手工 {}".format(len(cases), len(auto), len(manual)))
    print("脚本标记 {} 个，覆盖 {} 个用例编号".format(
        sum(len(v) for v in marks.values()), len(marks)))
    if manual:
        print("手工用例（无自动化节点，属预期）：{}".format(", ".join(manual)))
    if module_level:
        print("模块级 case 标记（仅分组用，不参与编号校验）：{}".format(", ".join(module_level)))
    if problems:
        print("\n发现 {} 处不一致：".format(len(problems)))
        for p in problems:
            print("  " + p)
        return 1
    print("\n[ok] 用例文档与自动化脚本完全对齐")
    return 0


if __name__ == "__main__":
    sys.exit(main())