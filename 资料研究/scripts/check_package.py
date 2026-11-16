#!/usr/bin/env python3
"""Check this package's readable links and structured records, without network calls.

Run in a full checkout, or pass --source-manifest for a connector materialization.
This validates file integrity and coverage, not the truth of semantic judgments.
"""
from __future__ import annotations

import argparse
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
}
REQUIRED_DOCS = [
    "SPEC.md", "PLAN.md", "README.md", "执行报告.md",
    "作文元主题与素材推荐.md", "小题材料与表达.md", "频率与时间窗.md",
]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")


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
    checked_links = 0
    checked_source_paths = 0

    def check_sources(value: object, owner: str) -> None:
        nonlocal checked_source_paths
        if isinstance(value, list):
            for item in value:
                check_sources(item, owner)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"文件", "来源文件", "原文文件", "路径", "树中可定位原文路径", "source_file", "source_path"} and isinstance(item, str):
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
            check_sources(row, f"{name}:{line_no}")
            rows.append(row)
        counts[name] = len(rows)
        if len(rows) < minimum:
            errors.append(f"{name}仅{len(rows)}条，要求至少{minimum}条")
        # A field is checked as an ID only when every row supplies it.
        for field in ("id", "ID", "编号", "索引编号"):
            if rows and all(isinstance(x, dict) and field in x for x in rows):
                ids = [str(x[field]) for x in rows]
                if len(set(ids)) != len(ids):
                    errors.append(f"{name}字段{field}重复")
                break
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
        "模式": "本地文件与已读远端树清单" if known else "完整工作副本",
        "检查范围": "JSON结构、必要交付物、记录数量、存在的记录标识唯一性、Markdown相对路径、结构化来源路径",
        "不认证": ["外部网页持续可达", "引文及其语义真实", "全部原型归属", "预测效果", "学习效果"],
        "错误": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
