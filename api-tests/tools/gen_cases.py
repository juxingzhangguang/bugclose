# -*- coding: utf-8 -*-
"""从用例登记表生成接口测试用例文档（Excel + Markdown）。

用例的唯一数据源是 tools/cases/ 下各模块的 CASES/MANUAL 列表，
本脚本只做渲染，不改内容；改用例请改登记表后重新生成。

用法（在 api-tests 目录下）：
    python tools/gen_cases.py                 # 生成 xlsx + md
    python tools/gen_cases.py --results       # 额外回填 reports/junit.xml 的执行结果
    python tools/gen_cases.py --md-only       # 只生成 Markdown
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from tools.cases import MODULE_ORDER, all_cases  # noqa: E402

XLSX_NAME = "接口测试用例.xlsx"
MD_NAME = "接口测试用例.md"

# 列宽（字符数），与 _base.COLUMNS 一一对应
WIDTHS = [12, 16, 34, 8, 10, 40, 56, 56, 46, 14, 40]


# ---------------------------------------------------------------- 执行结果回填
def load_results(junit_path: Path) -> dict:
    """解析 junit.xml，把结果按「用例编号」聚合。

    junit 里的 classname=tests.test_bug、name=test_x[param]，
    与登记表的「自动化脚本」= tests/test_bug.py::test_x 对应（忽略参数化后缀）。
    同一用例多个参数：只要有一条失败即判失败，全为 xfail 判「预期失败」。
    """
    if not junit_path.exists():
        return {}
    raw = {}
    for tc in ET.parse(junit_path).getroot().iter("testcase"):
        cls = (tc.get("classname") or "").replace(".", "/")
        name = (tc.get("name") or "").split("[")[0]
        key = "{}/{}.py::{}".format(cls.split("/")[0], cls.split("/")[-1], name) if cls else name
        if tc.find("failure") is not None or tc.find("error") is not None:
            outcome = "失败"
        elif tc.find("skipped") is not None:
            skipped = tc.find("skipped")
            outcome = "预期失败" if "xfail" in (skipped.get("type") or "") else "跳过"
        else:
            outcome = "通过"
        raw.setdefault(key, []).append(outcome)

    rank = {"失败": 0, "跳过": 1, "预期失败": 2, "通过": 3}
    return {k: min(v, key=lambda o: rank[o]) for k, v in raw.items()}


# ---------------------------------------------------------------- Excel
def write_xlsx(cases: list, path: Path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from tools.cases._base import COLUMNS

    head_fill = PatternFill("solid", fgColor="1F4E79")
    head_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(vertical="top", wrap_text=True)
    center = Alignment(horizontal="center", vertical="top", wrap_text=True)
    pri_fill = {"P0": "FFC7CE", "P1": "FFEB9C", "P2": "DDEBF7", "P3": "F2F2F2"}
    res_font = {"通过": "006100", "失败": "9C0006", "预期失败": "9C5700", "跳过": "808080"}

    wb = Workbook()
    summary = wb.active
    summary.title = "汇总"

    by_module = OrderedDict((m, []) for m in MODULE_ORDER)
    for c in cases:
        by_module[c["所属模块"]].append(c)

    # ---- 汇总表
    summary.append(["BugClose 接口测试用例汇总"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append([])
    summary.append(["所属模块", "用例数", "P0", "P1", "P2", "P3", "自动化", "手工",
                    "通过", "失败", "预期失败", "未执行"])
    for cell in summary[3]:
        cell.fill, cell.font, cell.border = head_fill, head_font, border
        cell.alignment = center
    for module, rows in by_module.items():
        pri = Counter(r["优先级"] for r in rows)
        res = Counter(r["执行结果"] or "未执行" for r in rows)
        auto = sum(1 for r in rows if r["自动化脚本"])
        summary.append([module, len(rows), pri["P0"], pri["P1"], pri["P2"], pri["P3"],
                        auto, len(rows) - auto, res["通过"], res["失败"],
                        res["预期失败"], res["未执行"]])
    total = summary.max_row + 1
    summary.append(["合计", len(cases)] + [
        sum(summary.cell(row=r, column=col).value or 0 for r in range(4, total))
        for col in range(3, 13)])
    for row in summary.iter_rows(min_row=4, max_row=summary.max_row):
        for cell in row:
            cell.border = border
            cell.alignment = center if cell.column > 1 else wrap
    for cell in summary[summary.max_row]:
        cell.font = Font(bold=True)
    for i, w in enumerate([22, 10, 8, 8, 8, 8, 10, 8, 8, 8, 10, 10], start=1):
        summary.column_dimensions[get_column_letter(i)].width = w
    summary.freeze_panes = "B4"

    # ---- 每模块一张明细表
    for module, rows in by_module.items():
        if not rows:
            continue
        ws = wb.create_sheet(module[:31])
        ws.append(COLUMNS)
        for cell in ws[1]:
            cell.fill, cell.font, cell.border = head_fill, head_font, border
            cell.alignment = center
        for r in rows:
            ws.append([r.get(col, "") for col in COLUMNS])
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                cell.border = border
                cell.alignment = center if cell.column in (1, 4, 5, 10) else wrap
            row[3].fill = PatternFill("solid", fgColor=pri_fill.get(row[3].value, "FFFFFF"))
            if row[9].value in res_font:
                row[9].font = Font(color=res_font[row[9].value], bold=True)
        for i, w in enumerate(WIDTHS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = "A1:{}{}".format(get_column_letter(len(COLUMNS)), ws.max_row)
        ws.sheet_view.zoomScale = 90

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ---------------------------------------------------------------- Markdown
def write_md(cases: list, path: Path):
    has_result = any(r["执行结果"] for r in cases)
    lines = ["# BugClose 接口测试用例", ""]
    lines += ["- 被测服务：`{}`".format(config.BASE_URL),
              "- 用例总数：**{}**（自动化 {} / 手工 {}）".format(
                  len(cases), sum(1 for c in cases if c["自动化脚本"]),
                  sum(1 for c in cases if not c["自动化脚本"])),
              "- 数据源：`api-tests/tools/cases/`，本文档由 `python tools/gen_cases.py` 生成，请勿直接编辑",
              "- 优先级：P0 冒烟 / P1 核心 / P2 一般 / P3 边缘",
              "- 「预期失败」= 已确认的后端缺陷，脚本用 `xfail(strict=True)` 固化，详见 [缺陷与风险清单](缺陷与风险清单.md)",
              ""]
    if has_result:
        res = Counter(r["执行结果"] or "未执行" for r in cases)
        lines += ["- 最近一次执行结果：通过 **{}** / 预期失败 **{}** / 失败 **{}** / 跳过 {} / 未执行 {} / 手工待执行 {}".format(
            res["通过"], res["预期失败"], res["失败"], res["跳过"], res["未执行"], res["手工待执行"]), ""]

    by_module = OrderedDict((m, []) for m in MODULE_ORDER)
    for c in cases:
        by_module[c["所属模块"]].append(c)

    lines += ["## 模块汇总", "", "| 所属模块 | 用例数 | P0 | P1 | P2 | P3 | 自动化 | 手工 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for module, rows in by_module.items():
        pri = Counter(r["优先级"] for r in rows)
        auto = sum(1 for r in rows if r["自动化脚本"])
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            module, len(rows), pri["P0"], pri["P1"], pri["P2"], pri["P3"], auto, len(rows) - auto))
    lines.append("")

    cols = ["优先级", "用例类型", "前置条件", "测试步骤", "预期结果", "自动化脚本"]
    if has_result:
        cols.append("执行结果")
    cols.append("备注")

    for module, rows in by_module.items():
        if not rows:
            continue
        lines += ["## {}".format(module), ""]
        for r in rows:
            lines += ["### {} {}".format(r["用例编号"], r["用例标题"]), "",
                      "| 项 | 内容 |", "| --- | --- |"]
            for col in cols:
                val = str(r.get(col) or "—").replace("|", "\\|").replace("\n", "<br>")
                if col == "自动化脚本" and r.get(col):
                    val = "`{}`".format(val)
                lines.append("| {} | {} |".format(col, val))
            lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="生成接口测试用例文档")
    ap.add_argument("--results", action="store_true", help="回填 reports/junit.xml 的执行结果")
    ap.add_argument("--md-only", action="store_true", help="只生成 Markdown")
    args = ap.parse_args()

    cases = all_cases()
    if args.results:
        results = load_results(config.REPORT_DIR / "junit.xml")
        if not results:
            print("[warn] 未找到 reports/junit.xml，执行结果留空")
        for c in cases:
            auto = c["自动化脚本"]
            c["执行结果"] = results.get(auto, "") if auto else "手工待执行"
        matched = sum(1 for c in cases if c["执行结果"] and c["执行结果"] != "手工待执行")
        print("[info] junit 回填 {}/{} 条自动化用例".format(matched, sum(1 for c in cases if c["自动化脚本"])))

    config.CASE_DIR.mkdir(parents=True, exist_ok=True)
    md = config.CASE_DIR / MD_NAME
    write_md(cases, md)
    print("[ok] {} （{} 条）".format(md, len(cases)))
    if not args.md_only:
        xlsx = config.CASE_DIR / XLSX_NAME
        write_xlsx(cases, xlsx)
        print("[ok] {}".format(xlsx))


if __name__ == "__main__":
    main()