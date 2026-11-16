#!/usr/bin/env python3
"""Check this package's readable links and structured records, without network calls.

Run in a full checkout, or pass --source-manifest for a connector materialization.
This validates file integrity and coverage, not the truth of semantic judgments.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


MIN_RECORDS = {
    "作文题任务索引.jsonl": 10,
    "关系索引.jsonl": 121,
    "作文推荐.jsonl": 6,
    "表达校准.jsonl": 24,
    "小题任务对照.jsonl": 8,
    "时政命题示例.jsonl": 6,
    "词表校准记录.jsonl": 19,
    "提法校准记录.jsonl": 3,
    "时政辨析卡.jsonl": 24,
    "市场样本.jsonl": 5,
    "市场逐项对照.jsonl": 63,
}
REQUIRED_DOCS = [
    "SPEC.md", "PLAN.md", "README.md", "执行报告.md",
    "作文元主题与素材推荐.md", "小题材料与表达.md", "频率与时间窗.md",
    "时政辨析材料.md", "市场资料对照.md",
]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")


def check_v2(records: dict[str, list[dict]], errors: list[str], package: Path) -> dict:
    """Validate usable-record structure and comparison denominators, not semantics."""
    def filled(value: object) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            # Optional evidence fields may explicitly remain unknown.
            # Required children are checked by their own schema below.
            return bool(value)
        if isinstance(value, list):
            return bool(value) and all(filled(v) for v in value)
        return value is not None

    def require(row: dict, fields: list[str], owner: str) -> None:
        for field in fields:
            if field not in row or not filled(row[field]):
                errors.append(f"{owner} 缺少或空白字段：{field}")

    essays = records.get("作文推荐.jsonl", [])
    expressions = records.get("表达校准.jsonl", [])
    tasks = records.get("小题任务对照.jsonl", [])
    cards = records.get("时政辨析卡.jsonl", [])
    samples = records.get("市场样本.jsonl", [])
    comparisons = records.get("市场逐项对照.jsonl", [])
    task_ids = {r.get("id") for r in tasks}
    essay_task_ids = {r.get("ID") for r in records.get("作文题任务索引.jsonl", [])}
    essay_doc = (package / "作文元主题与素材推荐.md").read_text(encoding="utf-8") if (package / "作文元主题与素材推荐.md").exists() else ""
    expression_doc = (package / "小题材料与表达.md").read_text(encoding="utf-8") if (package / "小题材料与表达.md").exists() else ""
    political_doc = (package / "时政辨析材料.md").read_text(encoding="utf-8") if (package / "时政辨析材料.md").exists() else ""
    expected_ids = {
        "作文推荐.jsonl": {f"W{i:02}" for i in range(1, 9)},
        "表达校准.jsonl": {f"EX{i:02}" for i in range(1, 33)},
        "时政辨析卡.jsonl": {f"P{i:02}" for i in range(1, 25)},
        "市场样本.jsonl": {f"M{i:02}" for i in range(1, 6)},
    }
    for name, expected in expected_ids.items():
        actual = {r.get("ID", r.get("id")) for r in records.get(name, [])}
        if actual != expected:
            errors.append(f"{name} 与v2固定范围不符：缺{sorted(expected - actual)}；多{sorted(str(x) for x in actual - expected)}")
    for row in essays:
        owner = row.get("ID", "作文推荐")
        require(row, ["论证使用", "题眼重合", "调用边界", "推荐性质", "排序含义"], owner)
        use = row.get("论证使用", {})
        if not isinstance(use, dict):
            errors.append(f"{owner} 论证使用必须为对象")
            continue
        require(use, ["可展开判断", "必要条件", "条件性质", "事实依据", "整理者推理", "证据能支持的范围", "论证示范"], owner)
        material_ids = {x.get("素材ID") for x in row.get("素材", [])}
        for fact in use.get("事实依据", []):
            require(fact, ["素材ID", "证据性质", "有出处的概括"], owner)
            if fact.get("素材ID") not in material_ids:
                errors.append(f"{owner} 事实依据引用不存在的素材：{fact.get('素材ID')}")
        demo = use.get("论证示范", {})
        require(demo, ["文本", "字数", "计数口径", "性质", "依据素材"], owner)
        demo_text = demo.get("文本", "")
        if demo_text and (len(demo_text) != demo.get("字数") or not 80 <= len(demo_text) <= 140):
            errors.append(f"{owner} 示范字数应与文本一致且在80—140字符内")
        if demo_text and demo_text not in essay_doc:
            errors.append(f"{owner} JSON示范未逐字出现在说明文中")
        for mid in demo.get("依据素材", []):
            if mid not in material_ids:
                errors.append(f"{owner} 示范引用不存在的素材：{mid}")
        for history in row.get("历史任务参照", []):
            require(history, ["ID", "重合层级", "相同点", "具体差别", "作用"], owner)
            if history.get("ID") not in essay_task_ids:
                errors.append(f"{owner} 引用不存在的历史作文任务")
            if history.get("重合层级") not in {"核心命题", "论证机制", "仅领域"}:
                errors.append(f"{owner} 历史重合未按三层口径记录")
    contrast_count = 0
    for row in expressions:
        require(row, ["成立条件", "不可据此推出", "主客体与范围", "证据不足时写法"], row.get("id", "表达校准"))
        require(row.get("主客体与范围", {}), ["主体", "对象", "范围限定"], row.get("id", "表达校准"))
        for task in row.get("对应任务", []):
            if task not in task_ids:
                errors.append(f"{row.get('id')} 引用不存在的小题任务：{task}")
        if row.get("整理者改写对照"):
            contrast_count += 1
            contrast = row["整理者改写对照"]
            require(contrast, ["性质", "适用任务", "示范用途", "材料支持的写法", "越界写法", "为什么越界"], row.get("id", "表达校准"))
            for task in contrast.get("适用任务", []):
                if task not in task_ids:
                    errors.append(f"{row.get('id')} 改写对照引用不存在的任务")
            for field in ("材料支持的写法", "越界写法", "为什么越界"):
                if contrast.get(field) and contrast[field] not in expression_doc:
                    errors.append(f"{row.get('id')} {field}未逐字出现在说明文中")
    if contrast_count < 8:
        errors.append(f"小题整理者改写对照仅{contrast_count}组，要求至少8组")
    for row in cards:
        owner = row.get("id", "时政卡")
        require(row, ["id", "source_id", "截至日期", "来源", "命题原论述日期", "正确命题", "正确命题身份", "主体", "对象", "范围", "条件", "易错改写", "依据定位", "为何错", "已能判断", "整题可解限制", "核验"], owner)
        source = row.get("来源", {})
        require(source, ["id", "标题", "发布主体", "文件类型", "知识层", "原文URL", "核读URL", "版本层", "状态说明", "正文核验方式"], owner)
        if source.get("id") != row.get("source_id"):
            errors.append(f"{owner} 来源ID与source_id不一致")
        mistake = row.get("易错改写", {})
        require(mistake, ["性质", "文本", "改错位置", "类型"], owner)
        if mistake.get("是真题") is not False or mistake.get("是预测题") is not False:
            errors.append(f"{owner} 自编改写须明确不是真题或预测题")
        require(row.get("依据定位", {}), ["章节或段落", "短原文锚点", "使用说明"], owner)
        require(row.get("核验", {}), ["日期", "方式", "结果", "覆盖范围"], owner)
        for label, value in (("正确命题", row.get("正确命题")), ("易错改写", mistake.get("文本"))):
            if value and value not in political_doc:
                errors.append(f"{owner} {label}未逐字出现在说明文中")
        dated = {key: source.get(key) for key in ("原事件日期", "所核原站网页公开日", "核读网页公开日", "名义期次日期")}
        dated.update({"命题原论述日期": row.get("命题原论述日期"), "核验日期": row.get("核验", {}).get("日期")})
        try:
            cutoff = date.fromisoformat(row["截至日期"])
            for label, value in dated.items():
                if value is not None and date.fromisoformat(value) > cutoff:
                    errors.append(f"{owner} {label}晚于资料截止日")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{owner} 日级日期须使用有效YYYY-MM-DD格式")
    source_counts = Counter(r.get("source_id") for r in cards)
    if len(source_counts) != 8 or any(n != 3 for n in source_counts.values()):
        errors.append(f"时政辨析卡应8份依据各3条，实际：{dict(source_counts)}")

    sample_map = {r.get("id"): r for r in samples}
    comparison_counts = Counter(r.get("样本ID") for r in comparisons)
    full_total = partial_total = 0
    for row in comparisons:
        require(row, ["id", "样本ID", "原始序号", "方向摘要", "URL", "可用性及边界", "整题答题充分性", "纳入范围"], row.get("id", "市场条目"))
        if row.get("样本ID") not in sample_map:
            errors.append(f"{row.get('id')} 引用不存在的市场样本")
    for sid, sample in sample_map.items():
        require(sample, ["URL", "页面日期", "范围", "分母类别", "日期证据", "答案状态"], sid)
        visible = sample.get("本次可见项数", 0)
        actual = comparison_counts[sid]
        if visible != actual:
            errors.append(f"{sid} 公开项数{visible}与对照记录数{actual}不符")
        positions = sorted(r.get("原始序号", 0) for r in comparisons if r.get("样本ID") == sid)
        if positions != list(range(1, visible + 1)):
            errors.append(f"{sid} 原始序号未覆盖全部可见位置或重复")
        if sample.get("分母类别") == "完整公开集合":
            full_total += actual
        elif sample.get("分母类别") == "部分公开，仅观察":
            partial_total += actual
        else:
            errors.append(f"{sid} 未说明完整或部分公开范围")
    if (full_total, partial_total) != (58, 5):
        errors.append(f"市场完整/部分集合分母应为58/5，实际{full_total}/{partial_total}")
    return {
        "作文使用规则组数": sum(bool(r.get("论证使用")) for r in essays),
        "小题证据门槛条数": len(expressions),
        "小题正反改写对照组数": contrast_count,
        "时政辨析卡数": len(cards),
        "时政依据及卡数": dict(source_counts),
        "市场公开样本数": len(samples),
        "市场完整集合条目数": full_total,
        "市场部分公开条目数": partial_total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repo.resolve()
    package = root / "资料研究"
    output = args.output or package / "统计" / "包校验.json"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    known = set()
    if args.source_manifest:
        manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
        known = {x["path"] for x in manifest["tree"]}
    errors: list[str] = []
    counts: dict[str, int] = {}
    records: dict[str, list[dict]] = {}
    checked_links = 0
    checked_source_paths = 0

    def check_sources(value: object, owner: str) -> None:
        nonlocal checked_source_paths
        if isinstance(value, list):
            for item in value:
                check_sources(item, owner)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"文件", "来源文件", "原文文件", "路径", "树中可定位原文路径", "仓库raw路径", "source_file", "source_path"} and isinstance(item, str):
                    if not urlsplit(item).scheme and re.search(r"\.(md|txt|jsonl|json|csv|pdf)$", item) and "/" in item:
                        checked_source_paths += 1
                        path = (root / item).resolve()
                        try:
                            rel = path.relative_to(root).as_posix()
                        except ValueError:
                            errors.append(f"{owner} 来源路径越出仓库：{item}")
                            continue
                        if not path.exists() and rel not in known:
                            errors.append(f"{owner} 来源文件不存在：{item}")
                check_sources(item, owner)
    for name in REQUIRED_DOCS:
        if not (package / name).is_file():
            errors.append(f"缺少文档：{name}")
    for name, minimum in MIN_RECORDS.items():
        file = package / "数据" / name
        if not file.is_file():
            errors.append(f"缺少数据：{name}")
            continue
        rows = []
        for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{name}:{line_no} JSON错误：{exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"{name}:{line_no} 记录必须为对象")
                continue
            check_sources(row, f"{name}:{line_no}")
            rows.append(row)
        counts[name] = len(rows)
        records[name] = rows
        if len(rows) < minimum:
            errors.append(f"{name}仅{len(rows)}条，要求至少{minimum}条")
        # A field is checked as an ID only when every row supplies it.
        for field in ("id", "ID", "编号", "索引编号"):
            if rows and all(isinstance(x, dict) and field in x for x in rows):
                ids = [str(x[field]) for x in rows]
                if len(set(ids)) != len(ids):
                    errors.append(f"{name}字段{field}重复")
                break
    v2 = check_v2(records, errors, package)
    for file in package.rglob("*.md"):
        # Exclude fenced examples from link checks.
        body = re.sub(r"```.*?```", "", file.read_text(encoding="utf-8"), flags=re.S)
        for match in LINK.finditer(body):
            target = match.group(1).strip("<>")
            split = urlsplit(target)
            if split.scheme or split.netloc or not split.path:
                continue
            checked_links += 1
            path = (file.parent / unquote(split.path)).resolve()
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                errors.append(f"{file.relative_to(root)} 链接越出仓库：{target}")
                continue
            # This report is produced by the current run, including on its first run.
            if not path.exists() and relative not in known and path != output:
                errors.append(f"{file.relative_to(root)} 缺失链接：{target}")
    report = {
        "通过": not errors,
        "数据条数": counts,
        "相对链接检查数": checked_links,
        "结构化来源路径检查数": checked_source_paths,
        "v2使用规则与分母检查": v2,
        "模式": "本地文件与已读远端树清单" if known else "完整工作副本",
        "检查范围": "JSON结构、必要交付物、记录数量、标识唯一性、Markdown相对路径、结构化来源路径、v2使用字段及任务引用、市场完整与部分公开分母",
        "不认证": ["外部网页持续可达", "引文及其语义真实", "全部原型归属", "预测效果", "学习效果"],
        "错误": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
