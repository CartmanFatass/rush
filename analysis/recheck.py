#!/usr/bin/env python3
"""Recompute the bounded 2022–2026 city/province research report.

Run after build_index.py, relate.py, dynamics.py and poltheory.py. The optional
baseline index isolates classification changes from newly collected documents.
No downloads, model calls, corpus writes or learner-score updates occur here.
"""
import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from dynamics import density, NARRATIVE, POLICY, INSTRUCTION
from poltheory import parse_poltheory
from relate import parse_exams, first_answers, EXAM_DIR, PAPERS, topic_hits, TOPICS, pre_exam
from source_layers import sublayer_of

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
EVIDENCE = HERE / "rechecks" / "2026-11-16"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_index(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def source_docs(rows):
    return [r for r in rows if r["source"] not in ("ref-assignment", "ref-craft")]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"empty evidence: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def profile(texts):
    joined = "\n".join(texts)
    return {"units": len(texts), "chars": len(joined),
            "narrative": round(density(joined, NARRATIVE), 3),
            "policy": round(density(joined, POLICY), 3),
            "instruction": round(density(joined, INSTRUCTION), 3)}


def freeze_classification_baseline(path):
    all_rows = read_index(path)
    rows = source_docs(all_rows)
    changes = Counter()
    before, after = defaultdict(list), defaultdict(list)
    for row in rows:
        old = row["sublayer"]
        new = old if row["source"].startswith("ref-") else sublayer_of(row["source"], row["path"])
        before[old].append(row["text"])
        after[new].append(row["text"])
        if old != new:
            changes[(row["source"], old, new)] += 1
    result = {
        "index_sha256": digest(path), "index_records": len(all_rows),
        "source_records": len(rows),
        "before": {k: profile(v) for k, v in sorted(before.items())},
        "after_classification_only": {k: profile(v) for k, v in sorted(after.items())},
        "changes": [{"source": s, "old": a, "new": b, "records": n}
                    for (s, a, b), n in sorted(changes.items())],
    }
    write_json(EVIDENCE / "classification-baseline.json", result)
    write_csv(EVIDENCE / "source-reclassification.csv", result["changes"])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-index", type=Path)
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    baseline = (freeze_classification_baseline(args.baseline_index) if args.baseline_index else
                json.loads((EVIDENCE / "classification-baseline.json").read_text()))
    write_csv(EVIDENCE / "source-reclassification.csv", baseline["changes"])
    all_docs = read_index(OUT / "index.jsonl")
    docs = source_docs(all_docs)
    exams = parse_exams()
    questions = parse_poltheory()
    appearances = parse_poltheory(deduplicate=False)
    inventory, groups, samples, question_inventory = [], defaultdict(list), {}, []
    for paper in PAPERS:
        selected = [e for e in exams if e["paper"] == paper]
        material_texts = [m["text"] for e in selected for m in e["materials"]]
        question_texts = [q for e in selected for q in e["questions"]]
        answer_texts = []
        for exam in selected:
            source_path = EXAM_DIR / exam["file"]
            answers = first_answers(source_path.read_text())
            if len(answers) != len(exam["questions"]) or len(answers) != 5:
                raise ValueError(f"incomplete answer extraction: {source_path}")
            answer_texts.extend(a["text"] for a in answers)
            inventory.append({"year": exam["year"], "paper": paper, "role": exam["role"],
                              "file": exam["file"], "sha256": digest(source_path),
                              "materials": len(exam["materials"]), "questions": len(exam["questions"]),
                              "first_answers": len(answers), "exam_date": exam["exam_date"]})
            for i, text in enumerate(exam["questions"], 1):
                question_inventory.append({"year": exam["year"], "paper": paper, "question": i,
                                           "prompt": text, "answer_chars_no_whitespace":
                                           len("".join(answers[i - 1]["text"].split()))})
        groups[paper + "材料"] = material_texts
        groups[paper + "题干"] = question_texts
        groups[paper + "参考答案"] = answer_texts
        political = parse_poltheory(papers=(paper,))
        samples[paper] = {"papers": len(selected), "materials": len(material_texts),
                          "questions": len(question_texts), "first_answers": len(answer_texts),
                          "political_unique": len(political)}
        groups[paper + "政治理论题干"] = [q["stem"] for q in political]
    groups["合并材料"] = [m["text"] for e in exams for m in e["materials"]]
    groups["合并参考答案"] = groups["地市级参考答案"] + groups["副省级参考答案"]
    for doc in docs:
        groups[doc["sublayer"]].append(doc["text"])
        if "/deep-reading/" in doc["path"]:
            groups["深阅读栏目样本"].append(doc["text"])
    profiles = {name: profile(texts) for name, texts in groups.items()}
    write_csv(EVIDENCE / "exam-inventory.csv", inventory)
    write_csv(EVIDENCE / "question-inventory.csv", question_inventory)
    write_csv(EVIDENCE / "political-appearances.csv", [
        {k: q[k] for k in ("year", "paper", "n", "qid", "file")} for q in appearances])

    with (OUT / "best_pre.csv").open() as stream:
        best = list(csv.DictReader(stream))
    expected = {(str(e["year"]), e["paper"], str(m["n"])) for e in exams for m in e["materials"]}
    keys = {(r["exam_year"], r["paper"], r["material"]) for r in best}
    if len(keys) != len(best) or not keys <= expected:
        raise ValueError("nearest candidate scope or uniqueness mismatch; rerun relate.py")
    for row in best:
        if not pre_exam(row["doc_date"], row["exam_date"]):
            raise ValueError("nonhistorical nearest candidate")
    nearest = {}
    for paper in PAPERS:
        selected = [r for r in best if r["paper"] == paper]
        nearest[paper] = {
            "materials": samples[paper]["materials"], "positive_similarity_candidates": len(selected),
            "threshold_counts": {str(t): sum(float(r["score"]) >= t for r in selected)
                                 for t in (0.10, 0.15, 0.20)},
            "median_lead_months": statistics.median(int(r["lead_months"]) for r in selected) if selected else None,
            "top_source_groups": dict(Counter(r["sublayer"] for r in selected)),
        }
    write_csv(EVIDENCE / "nearest-pre-candidates.csv", best)

    topic_rows = []
    for paper in PAPERS:
        for year in range(2022, 2027):
            selected = [e for e in exams if e["paper"] == paper and e["year"] == year]
            mats = [m for e in selected for m in e["materials"]]
            for topic in TOPICS:
                topic_rows.append({"year": year, "paper": paper, "topic": topic,
                                   "matched_materials": sum(topic in topic_hits(m["text"]) for m in mats),
                                   "total_materials": len(mats)})
    write_csv(EVIDENCE / "topics-by-year-and-paper.csv", topic_rows)
    inputs = ["build_index.py", "source_layers.py", "relate.py", "dynamics.py", "poltheory.py", "recheck.py"]
    result = {
        "as_of": "2026-11-16", "scope": "2022–2026; city primary, province auxiliary; no prediction weights",
        "index_records": len(all_docs), "source_records": len(docs),
        "source_group_counts": dict(sorted(Counter(d["sublayer"] for d in docs).items())),
        "samples": samples, "political_unique": len(questions), "political_appearances": len(appearances),
        "profiles": profiles, "nearest": nearest,
        "input_sha256": {"out/index.jsonl": digest(OUT / "index.jsonl"),
                         "out/best_pre.csv": digest(OUT / "best_pre.csv"),
                         **{name: digest(HERE / name) for name in inputs}},
        "limitations": ["Source groups classify capture directories, not every article's verified publisher.",
                        "Corpus records include reposts and versions; not independent article counts.",
                        "Original index truncation remains: article input 20000 chars, retrieval 9000 chars; bilingual texts affect character-based denominators.",
                        "Similarity is not source attribution, confidence, propagation or exam probability.",
                        "Handbook phrase/essay judgements were not independently reannotated in this pass.",
                        "No human learning outcome or official marking calibration is asserted."],
    }
    write_json(EVIDENCE / "statistics.json", result)

    lines = ["# 真题、政策文件与媒体材料：复核报告（v4）", "",
             "核对日期：2026-11-16。当前学习口径为 **2022—2026 市地级为主、副省级为辅**；两组分别报告，不以篇数自动加权。行政执法及更早真题保留原件，不进入本轮主统计。",
             "", "## 本轮结论", "",
             "现有资料足以开展时政选择题与申论各题型教学。统计用于检查材料覆盖、定位相似阅读素材和发现待解释的差异，不提供命题出处、押题概率或阅卷规则。",
             "", "## 1. 同一旧样本上的来源分类修正", "",
             f"固定旧索引 {baseline['index_records']:,} 条，其中排除题本和教学派生后的语料记录 {baseline['source_records']:,} 条；只改分类，不混入后来新增文章。旧索引 SHA-256：`{baseline['index_sha256']}`。",
             "", "| 采集来源 | 原分组 | 修正分组 | 记录数 |", "|---|---|---|---:|"]
    for row in baseline["changes"]:
        lines.append(f"| {row['source']} | {row['old']} | {row['new']} | {row['records']} |")
    before = baseline["before"]["A1_部委发布"]
    after = baseline["after_classification_only"]["A1_部委发布"]
    lines += ["", f"原“部委发布” {before['units']} 条修正为 {after['units']} 条。同一旧样本的政策标记词密度从 {before['policy']:.3f} 变为 {after['policy']:.3f} 次/千字符。旧报告据混合分组作出的部委/媒体对比不再沿用。",
              "", "分组依据是来源目录的已识别机构，不能自动认证文章本身的发布身份；转载文章仍需查原始发布者。未知采集源及普通网页快照进入待核组。",
              "", "## 2. 当前样本与边界", "",
              f"重建索引 {len(all_docs):,} 条；分析语料 {len(docs):,} 条。均为记录数，包含转载或版本，不能等同于独立文章数。",
              "", "| 卷型 | 用途 | 套卷 | 材料 | 题目 | 第一份机构参考答案 | 政治理论去重题 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for paper, sample in samples.items():
        lines.append(f"| {paper} | {'主线' if paper == '地市级' else '辅助'} | {sample['papers']} | {sample['materials']} | {sample['questions']} | {sample['first_answers']} | {sample['political_unique']} |")
    lines += ["", f"两卷型政治理论合计 {len(appearances)} 个题位、按同年 qid 去重为 {len(questions)} 道；全部出处保留，市地/副省共享题不能重复充当新样本。",
              "2025 两类及 2026 副省各有四则材料，其余主线题本各五则，合计 47 则。已逐卷核对标题；不能为了凑足五则补造材料。",
              "", "解析修正：材料在作答要求或第一题标题前截断；机构答案只取每题第一份明确标记的正文，排除重复题干、其他答案版本和“参考答案说明”。原题与所有参考版本不改写。",
              "", "## 3. 重新计算的词表描述", "",
              "下表是预定义词表的命中次数/千字符，包含标点与空白。它只是操作性指标，不能用几项均值相近证明两种文体相同，不能用词频证明认知难度、学习效果或实际来源。",
              "", "| 文本组 | 单元数 | 叙事标记 | 政策标记 | 指令标记 |", "|---|---:|---:|---:|---:|"]
    wanted = ["地市级材料", "副省级材料", "地市级题干", "副省级题干", "地市级参考答案", "副省级参考答案",
              "地市级政治理论题干", "副省级政治理论题干", "A0_中央文件", "A1_部委发布", "B_主流媒体", "C1_地方党报", "D_学术智库", "深阅读栏目样本"]
    for name in wanted:
        if name in profiles:
            p = profiles[name]
            lines.append(f"| {name} | {p['units']} | {p['narrative']:.3f} | {p['policy']:.3f} | {p['instruction']:.3f} |")
    lines += ["", "这些新数同时包含分组、材料边界、答案边界和样本范围修正，不能把与 v3 的全部差异归因于某一项修改。第一节才是固定样本的分类单因素对照。",
              "", "## 4. 相似候选与时间", "",
              "先按真实笔试日筛选发布日期严格早于考试的文档，再选相似候选；不再先取全库前 12 名后剔除考后文章，也不再把同月考后文章当成考前。未知或非法日期不准入。同日因没有时分信息保守排除。",
              "", "| 卷型 | 材料数 | 有正相似候选 | ≥0.10 | ≥0.15 | ≥0.20 | 候选领先月数中位 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for paper, n in nearest.items():
        c = n["threshold_counts"]
        lines.append(f"| {paper} | {n['materials']} | {n['positive_similarity_candidates']} | {c['0.1']} | {c['0.15']} | {c['0.2']} | {n['median_lead_months']} |")
    lines += ["", "0.10/0.15/0.20 仅作阈值敏感性展示，未经出处人工校准，不称“高置信来源”。月份差只描述选中候选与考试之间的年月距离，不是命题提前量。词典/逆文档频率仍基于全库，本分析不是历史预测回测。",
              "“地方党报→人民日报→申论”的传播路径：本轮相似检索方法不能识别传播链，撤回旧报告的肯定或否定结论。须有同一事实、关键表述、首发/转载关系等证据才能进一步研究。",
              "", "## 5. 结论处置与教学边界", "",
              "| 旧说法 | 本轮处置 |", "|---|---|",
              "| 深阅读与申论密度相近，因而文体相同 | 改为词表描述；可用来筛选阅读样本，文体/论证作用仍逐文判断 |",
              "| 参考答案更像部委落实语 | 原分组及答案边界不可靠；保留重算描述，撤回来源与得分推断 |",
              "| 政治理论只考理论、申论只考政策 | 撤回绝对化分工；两者均可能涉及理论与政策，要求和证据用途不同 |",
              "| 多年未考/媒体热度意味着今年更可能考 | 删除“热度×距上次出题年数”分数；候选表只作现有阅读材料目录 |",
              "| 月度波动方向可信、幅度不可信 | 改为来源构成变化时方向和幅度都未获验证，需稳定来源样本对照 |",
              "| 网页抓不到证明存档消失 | 改为当次访问方法未取到；不推断资料不存在或必须付费获取 |",
              "| 原词占比高意味着摘抄即可 | 保留旧样本记录；归类、取舍、因果和限定条件仍须推理 |",
              "| 每百字九短语、固定条数/三分论点/逐段外部例子 | 均改为可选练习支架；具体要求由题干、材料和论证任务决定 |",
              "| 近两年参考答案变化就是命题迁移 | 按年份、卷型和机构版本区分；单年题数少且机构不同，保留为待检验观察 |",
              "", "小题手册的 885/668 短语分类及作文手册的 31 篇范文判断是历史人工/模型研究。其逐短语审定底表未完整附在仓库，本轮不宣称重新认证这些数或全部判断。已保留历史、收紧教学结论，并将“全面保留传统工艺”标为参考答案过度推断的实例。",
              "", "## 6. 复现与证据", "",
              "```bash", "python3 analysis/build_index.py", "python3 analysis/corpus_manifest.py",
              "python3 analysis/relate.py", "python3 analysis/dynamics.py", "python3 analysis/poltheory.py",
              "python3 analysis/recheck.py", "PYTHONPATH=analysis python3 -m unittest discover -s analysis -p 'test_recheck.py' -v", "```", "",
              "证据在 `analysis/rechecks/2026-11-16/`：`statistics.json`（输入哈希与统计）、`classification-baseline.json`（固定旧样本单因素对照）、`source-reclassification.csv`、`exam-inventory.csv`、`question-inventory.csv`、`political-appearances.csv`、`nearest-pre-candidates.csv`、`topics-by-year-and-paper.csv`。旧报告见同目录 `REPORT-v3-historical.md`，仅供历史对照，不作为当前教学依据。",
              "", "外部原文位于 Learn-to-Write，未改写。当前索引保留旧有截断上限：一般文章 20,000 字符、检索使用前 9,000 字符；中英对照文本也会改变字符分母。长政策全文质量与事实正确性未因本轮通过程序检查而获得认证。",
              "来源文章量不等于学习覆盖；独立学习效果仍需真实作答。课程按 `学习计划.md` 审阅稿执行范围准备，个人状态仅记仓库根 `进度.md`。", ""]
    (HERE / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"samples": samples, "source_records": len(docs), "nearest": nearest,
                      "old_A1": before, "corrected_old_A1": after}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
