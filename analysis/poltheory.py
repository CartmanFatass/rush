#!/usr/bin/env python3
"""行测「政治理论」模块 vs 申论 vs 官方文件：同一套政策语汇的三个考试面。

解析 2018–2026 的 23 份政治理论真题，统计：
1. 每题的政策短语命中（复用 relate.PHRASES）；
2. 短语在 政治理论 / 申论 / 语料各层 的出现分布；
3. 短语首次进入政治理论 vs 首次进入语料的时间差。
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

from relate import PHRASES, parse_exams, topic_hits, TOPICS

MD = HERE.parent / "_build" / "md"
OUT = HERE / "out"
# 理论语汇（政治理论模块的语言），与 relate.PHRASES 的政策语汇对照
THEORY = [
    "中国式现代化", "全过程人民民主", "两个确立", "四个自信", "四个意识", "两个维护",
    "新发展理念", "新发展格局", "高质量发展", "人民至上", "自我革命", "人类命运共同体",
    "共同富裕", "物质文明和精神文明", "系统观念", "底线思维", "问题导向", "守正创新",
    "六个必须坚持", "十个明确", "十四个坚持", "五个必由之路", "三个务必", "以人民为中心",
    "江山就是人民", "自信自立", "独立自主", "胸怀天下", "斗争精神", "历史主动",
    "马克思主义中国化时代化", "两个结合", "伟大建党精神", "党的自我革命", "社会革命",
    "全体人民共同富裕", "人与自然和谐共生", "走和平发展道路", "创造人类文明新形态",
    "全面深化改革", "国家治理体系和治理能力现代化", "依法治国", "全面从严治党",
]
Q_RE = re.compile(r"^## 第 (\d+) 题　<sub>qid (\d+) · ([^>]*)</sub>", re.M)
ANS_RE = re.compile(r"\*\*答案\*\*：([A-D]+)")


def parse_poltheory():
    qs = []
    for p in sorted(MD.glob("01-政治理论__*.md")):
        m = re.match(r"01-政治理论__(\d{4})年.*?（(.+?)）", p.name)
        if not m:
            continue
        year, paper = int(m.group(1)), m.group(2)
        text = p.read_text(encoding="utf-8")
        parts = Q_RE.split(text)
        # parts: [pre, n, qid, tag, body, n, qid, tag, body, ...]
        for i in range(1, len(parts) - 3, 4):
            n, qid, tag, body = parts[i], parts[i + 1], parts[i + 2], parts[i + 3]
            stem = re.split(r"\n-\s*\*\*A\*\*", body)[0]
            ans = ANS_RE.search(body)
            qs.append({
                "year": year, "paper": paper, "n": int(n), "qid": qid,
                "tag": tag.strip(), "stem": stem.strip(),
                "answer": ans.group(1) if ans else "",
                "chars": len(stem),
            })
    return qs


def main():
    qs = parse_poltheory()
    print(f"政治理论: {len(qs)} 题, 年份 {min(q['year'] for q in qs)}–{max(q['year'] for q in qs)}")
    print("  按年:", dict(sorted(Counter(q["year"] for q in qs).items())))
    print("  按标签:", Counter(q["tag"] for q in qs).most_common(12))

    # ---- 短语命中 ----
    ph = list(dict.fromkeys(PHRASES))
    rows = []
    for phrase in ph:
        pt = [q for q in qs if phrase in q["stem"]]
        if not pt:
            continue
        rows.append({
            "phrase": phrase,
            "n_pt": len(pt),
            "pt_years": "/".join(str(y) for y in sorted({q["year"] for q in pt})),
            "pt_tags": "/".join(sorted({q["tag"] for q in pt}))[:40],
        })
    rows.sort(key=lambda r: -r["n_pt"])

    # 申论侧
    ex = parse_exams()
    sl = defaultdict(list)
    for e in ex:
        for m in e["materials"]:
            for phrase in ph:
                if phrase in m["text"]:
                    sl[phrase].append(e["year"])
    for r in rows:
        yrs = sorted(set(sl.get(r["phrase"], [])))
        r["n_sl"] = len(sl.get(r["phrase"], []))
        r["sl_years"] = "/".join(str(y) for y in yrs)

    # 语料侧
    docs = [json.loads(l) for l in open(OUT / "index.jsonl", encoding="utf-8")]
    docs = [d for d in docs if d["source"] not in ("ref-assignment", "ref-craft")]
    for r in rows:
        hits = [d for d in docs if r["phrase"] in d["text"]]
        r["n_corpus"] = len(hits)
        sub = Counter(d["sublayer"] for d in hits)
        r["A0"] = sub.get("A0_中央文件", 0)
        r["A1"] = sub.get("A1_部委发布", 0)
        r["B"] = sub.get("B_主流媒体", 0)
        r["C"] = sub.get("C_地方实践", 0)
        ds = sorted(d["date"] for d in hits if d["date"])
        r["first_corpus"] = ds[0] if ds else ""

    with open(OUT / "poltheory_phrases.csv", "w", encoding="utf-8") as f:
        cols = list(rows[0].keys())
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join('"' + str(r[c]).replace('"', "'") + '"' for c in cols) + "\n")

    print(f"\n政治理论命中的政策短语: {len(rows)} 个")
    print(f"{'短语':16s} {'政治理论':>6s} {'申论':>4s} {'语料':>5s}  政治理论年份 / 申论年份")
    for r in rows[:30]:
        print(f"{r['phrase']:16s} {r['n_pt']:>6d} {r['n_sl']:>4d} {r['n_corpus']:>5d}  "
              f"{r['pt_years']:22s} / {r['sl_years'] or '-'}")

    # ---- 只有政治理论用、申论不用的短语（公文语言 vs 叙事语言）----
    only_pt = [r for r in rows if r["n_sl"] == 0]
    print(f"\n只出现在政治理论、从未进申论: {len(only_pt)} 个")
    print("  " + "、".join(r["phrase"] for r in only_pt[:30]))

    # ---- 理论语汇 vs 政策语汇：三个考试面的分工 ----
    print("\n理论语汇 / 政策语汇 在三个考试面的命中率")
    print(f"  {'语汇':20s} {'政治理论':>7s} {'申论材料':>7s} {'中央文件':>7s} {'主流媒体':>7s}")
    def rate(items, key):
        return sum(1 for x in items if any(p in x for p in key)) / max(len(items), 1)
    pt_stems = [q["stem"] for q in qs]
    sl_texts = [m["text"] for e in ex for m in e["materials"]]
    a0 = [d["text"] for d in docs if d["sublayer"] == "A0_中央文件"]
    bb = [d["text"] for d in docs if d["sublayer"] == "B_主流媒体"]
    for label, key in (("理论语汇", THEORY), ("政策语汇", ph)):
        print(f"  {label:20s} {rate(pt_stems,key):7.3f} {rate(sl_texts,key):7.3f} "
              f"{rate(a0,key):7.3f} {rate(bb,key):7.3f}")
    print("\n  单个理论语汇:")
    for t in THEORY:
        a = sum(1 for x in pt_stems if t in x)
        b = sum(1 for x in sl_texts if t in x)
        c = sum(1 for x in a0 if t in x)
        if a or b:
            print(f"    {t:24s} 政治理论 {a:3d}  申论 {b:3d}  中央文件 {c:3d}")

    # ---- 主题覆盖对比 ----
    print("\n主题覆盖对比（命中率）:")
    print(f"  {'主题':14s} {'政治理论':>8s} {'申论材料':>8s}")
    for t in TOPICS:
        a = sum(1 for q in qs if t in topic_hits(q["stem"])) / len(qs)
        b = sum(1 for e in ex for m in e["materials"] if t in topic_hits(m["text"]))
        b /= sum(len(e["materials"]) for e in ex)
        if a > 0.02 or b > 0.05:
            print(f"  {t:14s} {a:8.3f} {b:8.3f}")

    # ---- 每年题目长度 / 引用密度 ----
    print("\n按年: 题量 / 平均题干字数 / 命中政策短语题数")
    for y in sorted({q["year"] for q in qs}):
        sub = [q for q in qs if q["year"] == y]
        hit = sum(1 for q in sub if any(p in q["stem"] for p in ph))
        print(f"  {y}  {len(sub):3d} 题  {sum(q['chars'] for q in sub)/len(sub):6.0f} 字  "
              f"{hit:3d} 题含政策短语 ({hit/len(sub):.0%})")


if __name__ == "__main__":
    main()
