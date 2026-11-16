#!/usr/bin/env python3
"""Descriptive phrase/register statistics and a reading list, not exam prediction."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

from relate import (TOPICS, TOPIC_RE, PHRASES, EXAM_DIR, EXAM_DATE,
                    parse_exams, topic_hits, first_answers)

BASE = HERE
OUT = BASE / "out"


def load_docs():
    docs = [json.loads(l) for l in open(OUT / "index.jsonl", encoding="utf-8")]
    return [d for d in docs if d["source"] not in ("ref-assignment", "ref-craft")]


def quarter(d: str) -> str:
    try:
        return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"
    except Exception:
        return ""


# ---------------------------------------------------------------- 1. lifecycle
def lifecycle(docs):
    rows = []
    for ph in dict.fromkeys(PHRASES):
        hits = [d for d in docs if ph in d["text"] and d["date"]]
        if len(hits) < 12:
            continue
        first = {}
        for d in hits:
            sl = d["sublayer"]
            if sl not in first or d["date"] < first[sl]:
                first[sl] = d["date"]
        # who spoke first: 中央/部委 (policy) vs 媒体 (B) vs 地方 (C)
        pol = min([v for k, v in first.items() if k.startswith("A")], default="")
        med = first.get("B_主流媒体", "")
        loc = first.get("C_地方实践", "")
        lead = None
        if pol and med:
            lead = (int(med[:4]) - int(pol[:4])) * 12 + (int(med[5:7]) - int(pol[5:7]))
        rows.append({
            "phrase": ph, "n": len(hits),
            "first_all": min(first.values()),
            "first_policy": pol, "first_media": med, "first_local": loc,
            "policy_leads_media_months": lead,
            "n_A0": sum(1 for d in hits if d["sublayer"] == "A0_中央文件"),
            "n_A1": sum(1 for d in hits if d["sublayer"] == "A1_部委发布"),
            "n_B": sum(1 for d in hits if d["sublayer"] == "B_主流媒体"),
            "n_C": sum(1 for d in hits if d["sublayer"] == "C_地方实践"),
            "n_D": sum(1 for d in hits if d["sublayer"] == "D_学术智库"),
        })
    rows.sort(key=lambda r: -r["n"])
    with open(OUT / "phrase_lifecycle.csv", "w", encoding="utf-8") as f:
        cols = list(rows[0].keys())
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join('"' + str(r[c]) + '"' for c in cols) + "\n")

    leads = [r["policy_leads_media_months"] for r in rows
             if r["policy_leads_media_months"] is not None]
    leads.sort()
    print(f"phrase_lifecycle: {len(rows)} phrases, "
          f"{len(leads)} with both policy+media first-dates")
    if leads:
        print(f"  policy-leads-media months: median={leads[len(leads)//2]} "
              f"p25={leads[len(leads)//4]} p75={leads[3*len(leads)//4]} "
              f"neg={sum(1 for x in leads if x < 0)}/{len(leads)}")
    return rows


# ---------------------------------------------------------------- 2. register
NARRATIVE = ["他说", "表示", "告诉记者", "村民", "居民", "负责人", "老", "说：",
             "回忆", "去年", "前年", "走进", "看到", "现场", "一位", "几位"]
POLICY = ["坚持", "推动", "加快", "深化", "完善", "健全", "统筹", "着力", "扎实",
          "全面", "落实", "机制", "体系", "格局", "高质量", "进一步", "不断", "切实"]
INSTRUCTION = ["请根据", "请结合", "拟写", "起草", "谈谈", "概括", "梳理", "分析",
               "提出", "不超过", "要求：", "假如你是", "撰写"]


def density(text: str, words) -> float:
    n = max(len(text), 1)
    return sum(text.count(w) for w in words) / n * 1000


def register(exams):
    groups = defaultdict(list)
    for e in exams:
        for m in e["materials"]:
            groups["申论材料"].append(m["text"])
        groups["题干"].extend(e["questions"])
        groups["参考答案"].extend(e.get("answer_texts", []))
    return groups


def register_table(docs, exams):
    groups = register(exams)
    # 行测「政治理论」题干：第三个考试面
    try:
        from poltheory import parse_poltheory
        groups["政治理论题干"] = [q["stem"] for q in parse_poltheory()]
    except Exception as e:
        print("poltheory skip:", e)
    for d in docs:
        groups[d["sublayer"]].append(d["text"])
    rows = []
    for k, texts in groups.items():
        if not texts:
            continue
        joined = "\n".join(texts)
        rows.append({
            "group": k, "docs": len(texts), "chars": len(joined),
            "叙事/千字": round(density(joined, NARRATIVE), 2),
            "政策/千字": round(density(joined, POLICY), 2),
            "指令/千字": round(density(joined, INSTRUCTION), 2),
        })
    order = {"申论材料": 0, "题干": 1, "政治理论题干": 2, "参考答案": 3, "A0_中央文件": 4,
             "A1_部委发布": 5, "B_主流媒体": 6, "C_地方实践": 7, "D_学术智库": 8}
    rows.sort(key=lambda r: order.get(r["group"], 9))
    with open(OUT / "register.csv", "w", encoding="utf-8") as f:
        cols = list(rows[0].keys())
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")
    print("\n== register profile (per 1000 chars) ==")
    print(f"  {'group':14s} {'docs':>5s} {'叙事':>6s} {'政策':>6s} {'指令':>6s}")
    for r in rows:
        print(f"  {r['group']:14s} {r['docs']:5d} {r['叙事/千字']:6.2f} "
              f"{r['政策/千字']:6.2f} {r['指令/千字']:6.2f}")
    return rows


# ---------------------------------------------------------------- 3. quarterly heat
def quarterly(docs):
    tot = defaultdict(Counter)
    hit = defaultdict(Counter)
    for d in docs:
        q = quarter(d["date"])
        if not q:
            continue
        tot[q][d["sublayer"]] += 1
        for t in topic_hits(d["text"]):
            hit[(t, q)][d["sublayer"]] += 1
    rows = []
    for (t, q), c in sorted(hit.items()):
        for sl in ("B_主流媒体", "A1_部委发布", "C_地方实践", "A0_中央文件"):
            n, N = c.get(sl, 0), tot[q][sl]
            if N >= 15:
                rows.append({"topic": t, "quarter": q, "sublayer": sl,
                             "n": n, "N": N, "share": round(n / N, 4)})
    with open(OUT / "topic_quarter.csv", "w", encoding="utf-8") as f:
        f.write("topic,quarter,sublayer,n,N,share\n")
        for r in rows:
            f.write(f"{r['topic']},{r['quarter']},{r['sublayer']},{r['n']},{r['N']},{r['share']}\n")
    return rows


# ---------------------------------------------------------------- 4. 2027 candidates
def candidates(docs, exams):
    used = defaultdict(set)
    for e in exams:
        for m in e["materials"]:
            for t in topic_hits(m["text"]):
                used[t].add(e["year"])
    win = [d for d in docs if "2026-04-01" <= d["date"] < "2026-11-01"]
    rows = []
    for t in TOPICS:
        hits = [d for d in win if t in topic_hits(d["text"])]
        if not hits:
            continue
        yrs = used.get(t, set())
        # 官方文件层是否已表态（政策势能）
        pol = sum(1 for d in hits if d["sublayer"] in ("A0_中央文件", "A1_部委发布"))
        med = sum(1 for d in hits if d["sublayer"] == "B_主流媒体")
        loc = sum(1 for d in hits if d["sublayer"] == "C_地方实践")
        rows.append({
            "topic": t, "docs": len(hits),
            "share": round(len(hits) / len(win), 4),
            "policy": pol, "media": med, "local": loc,
            "exam_years": "/".join(str(y) for y in sorted(yrs)) or "-",
            "n_exam_years": len(yrs),
            "last_exam": max(yrs) if yrs else 0,
            "use": "reading_inventory_not_exam_probability",
        })
    rows.sort(key=lambda r: (-r["docs"], r["topic"]))
    with open(OUT / "candidates_2027.csv", "w", encoding="utf-8") as f:
        cols = list(rows[0].keys())
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")
    print("\n== 2027 reading inventory (corpus frequency only; not prediction) ==")
    for r in rows[:16]:
        print(f"  {r['topic']:14s} share={r['share']:.3f} pol={r['policy']:3d} "
              f"med={r['media']:4d} loc={r['local']:3d} exams={r['exam_years']:24s} "
              "not an exam score")
    return rows


def main():
    docs = load_docs()
    exams = parse_exams()
    # pull 参考答案 out of the exam files
    for e in exams:
        t = (EXAM_DIR / e["file"]).read_text(encoding="utf-8")
        e["answer_texts"] = [a["text"] for a in first_answers(t)]
    lifecycle(docs)
    register_table(docs, exams)
    quarterly(docs)
    candidates(docs, exams)


if __name__ == "__main__":
    main()
