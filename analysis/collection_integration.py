#!/usr/bin/env python3
"""Recount existing collection records and date coverage; no source discovery.

Prototype coverage describes annotations, not independently proven provenance.
Run from either working-directory location; paths follow this script's repository.
"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COLLECT = ROOT / "资料采集"
OUT = HERE / "rechecks" / "2026-11-16" / "collection-integration"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def relation_quotes(inputs):
    """Recheck the corrected relation record against its own stored source.

    Match the previous review's 4-character minimum. Normalization ignores
    whitespace, quote typography and boundary punctuation; it is not byte equality.
    """
    directory = COLLECT / "03-关系对与方法论"
    path = directory / "关系对库.jsonl"
    inputs[str(path.relative_to(ROOT))] = sha(path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    checked, skipped, exceptions = 0, 0, []

    def norm(text):
        return re.sub(r"\s+", "", text).translate(str.maketrans("“”‘’", "\"\"''"))

    for number, row in enumerate(rows, 1):
        # Some records append a parenthesized inventory location after the filename.
        raw = (directory / row["原文文件"].split("（", 1)[0].strip()).resolve()
        if not raw.is_relative_to((directory / "raw").resolve()):
            raise ValueError(f"unexpected source path for relation {number}")
        inputs[str(raw.relative_to(ROOT))] = sha(raw)
        original = norm(raw.read_text(encoding="utf-8"))
        for field in ("各项原文", "展开句"):
            for quote in row.get(field, []):
                value = norm(quote).strip("\"'。；，")
                if len(value) < 4:
                    skipped += 1
                    continue
                checked += 1
                if value not in original:
                    exceptions.append({"record": number, "field": field, "text": quote,
                                       "noted_as_paraphrase": "拆写" in row.get("备注", "")})
    return {
        "normalization": "去空白、统一引号、去引句边界标点，至少4字符；仅在各条自己标注的raw文件中查找",
        "checked": checked, "matched": checked - len(exceptions),
        "short_fields_not_checked": skipped, "exceptions": exceptions,
        "record75_own_source_matched": not any(r["record"] == 75 for r in exceptions),
        "limits": "字符串核对不认证来源网页真实性、关系类型、历史首次发表日期或教学结论",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    articles, material_records, inputs = [], defaultdict(list), {}
    for path in sorted((COLLECT / "01-材料溯源").glob("*.jsonl")):
        inputs[str(path.relative_to(ROOT))] = sha(path)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "材料号" not in row:
                continue
            key = (row["年度"], row["卷"], row["材料号"])
            material_records[key].append((line_no, row))
            for report_no, report in enumerate(row.get("原报道", []), 1):
                articles.append({
                    "record_id": f"{path.stem}:{line_no}:{report_no}",
                    "year": row["年度"], "paper": row["卷"], "material": row["材料号"],
                    "source_file": str(path.relative_to(ROOT)), "line": line_no,
                    "outlet_as_recorded": report["媒体"], "title": report["标题"],
                    "date_as_recorded": report["发表日"], "url": report["URL"],
                    "evidence_as_recorded": report.get("判断依据", ""),
                })
    inventory = []
    for (year, paper, material), rows in sorted(material_records.items()):
        # This deliberately reproduces the collection's provisional distinction:
        # a same-topic report beside "未找到" is not counted as a found prototype.
        has_candidate = any(r.get("原报道") and
                            not str(r.get("真实原型", "")).startswith("未找到")
                            for _, r in rows)
        inventory.append({
            "year": year, "paper": paper, "material": material,
            "annotation_rows": len(rows),
            "has_annotated_prototype_candidate": has_candidate,
            "report_mentions": sum(len(r.get("原报道", [])) for _, r in rows),
            "source_lines": ",".join(str(n) for n, _ in rows),
            "annotation_confidences": ";".join(sorted({r.get("置信度", "") for _, r in rows})),
            "interpretation": "采集记录中的原型候选，含推断；不等于已证明命题来源",
        })
    counts = Counter(a["url"] for a in articles)
    index = HERE / "out" / "index.jsonl"
    inputs[str(index.relative_to(ROOT))] = sha(index)
    ministry = []
    with index.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("sublayer") == "A1_部委发布":
                ministry.append(row)
    monthly = Counter(str(r.get("date", ""))[:7] for r in ministry)
    valid_dates = []
    for row in ministry:
        try:
            value = str(row.get("date", ""))
            if len(value) != 10:
                raise ValueError(value)
            valid_dates.append(date.fromisoformat(value))
        except ValueError:
            pass
    exam_path = HERE / "rechecks" / "2026-11-16" / "exam-inventory.csv"
    inputs[str(exam_path.relative_to(ROOT))] = sha(exam_path)
    with exam_path.open(encoding="utf-8") as f:
        exams = list(csv.DictReader(f))
    date_coverage = [{
        "year": e["year"], "paper": e["paper"], "exam_date": e["exam_date"],
        "ministry_records": len(ministry),
        "strictly_pre_exam": sum(d < date.fromisoformat(e["exam_date"]) for d in valid_dates),
        "unknown_or_non_day_dates": len(ministry) - len(valid_dates),
    } for e in exams]
    result = {
        "scope": "2022–2026 市地为主、副省为辅；既有资料的有限对接复核",
        "input_sha256": inputs,
        "materials": len(inventory),
        "annotated_prototype_candidates": sum(r["has_annotated_prototype_candidate"] for r in inventory),
        "by_year": {year: {
            "materials": sum(r["year"] == year for r in inventory),
            "annotated_candidates": sum(r["year"] == year and r["has_annotated_prototype_candidate"] for r in inventory),
        } for year in sorted({r["year"] for r in inventory})},
        "report_mentions": len(articles), "distinct_report_urls": len(counts),
        "repeated_urls": {url: n for url, n in counts.items() if n > 1},
        "media_distribution": "未认证；媒体字段混合原作者、机构和转载平台，不采用46/12结论",
        "ministry_records": len(ministry), "ministry_months": dict(sorted(monthly.items())),
        "ministry_from_2025_12": sum(d >= date(2025, 12, 1) for d in valid_dates),
        "ministry_date_coverage": date_coverage,
        "relation_quotes": relation_quotes(inputs),
        "limits": [
            "原型覆盖复现采集标注，不是对全部原型和改写关系的独立语义验收",
            "URL去重不是独立稿件去重；同稿异址、转载和片段仍需逐篇判断",
            "未重新抓网页；未认证各媒体首发身份或全部存档的完整性",
            "部委日期来自当前索引，仍须区分首发、转载、采集日期",
            "程序测试通过只说明切分、过滤等机制符合测试条件",
        ],
    }
    write_csv("report-mentions.csv", articles)
    write_csv("material-candidates.csv", inventory)
    write_csv("ministry-months.csv", [{"month": month, "records": n} for month, n in sorted(monthly.items())])
    write_csv("ministry-exam-date-coverage.csv", date_coverage)
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["materials", "annotated_prototype_candidates", "report_mentions", "distinct_report_urls", "ministry_records", "ministry_from_2025_12"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
