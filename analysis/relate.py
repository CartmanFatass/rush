#!/usr/bin/env python3
"""Relate 申论题目 <-> 官方文件 <-> 主流媒体报道.

Stages
------
1. parse_exams  : 2022–2026 city papers (primary) and provincial papers (auxiliary)
2. tfidf_match  : char-bigram TF-IDF cosine, nearest corpus docs per 材料
3. topics       : topic taxonomy -> exam matrix + corpus monthly heat
4. phrases      : policy-phrase transmission (first appearance -> exam usage)

Outputs land in analysis/out/.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent

BASE = HERE
OUT = BASE / "out"
OUT.mkdir(parents=True, exist_ok=True)
EXAM_DIR = HERE.parent / "申论"

# 国考申论笔试日期（公共科目），label 年份 = 招录年度
EXAM_DATE = {
    2022: "2021-11-28",
    2023: "2023-01-08",   # 原定 2022-12-03/04，疫情延期
    2024: "2023-11-26",
    2025: "2024-12-01",
    2026: "2025-11-30",
}
PAPERS = ("地市级", "副省级")
YEARS = tuple(range(2022, 2027))


def normalize_paper(paper):
    if "地市" in paper or "市地" in paper:
        return "地市级"
    if "副省" in paper:
        return "副省级"
    return "行政执法" if "行政" in paper else paper


def pre_exam(doc_date, exam_date):
    """Only known, valid dates strictly before the actual exam qualify."""
    try:
        return date.fromisoformat(doc_date) < date.fromisoformat(exam_date)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- 1. exams
def parse_exams(*, exam_dir=EXAM_DIR, years=YEARS, papers=PAPERS):
    exams = []
    for p in sorted(Path(exam_dir).glob("*.md")):
        m = re.match(r"(\d{4})国考申论（(.+?)）", p.name)
        if not m:
            continue
        year, paper = int(m.group(1)), m.group(2)
        if year not in years or paper not in papers:
            continue
        text = p.read_text(encoding="utf-8")
        # stop at 参考答案
        body = text.split("## 参考答案")[0]
        # Some recalled papers omit the level-2 作答要求 heading. In either
        # form stop at the first question; never index instructions as material.
        boundary = re.search(r"^##\s+[^\n]*作答要求[^\n]*$|^###\s+第一题\s*$", body, re.M)
        material_body = body[:boundary.start()] if boundary else body
        mats = re.split(r"^### 材料\s*(\d+)\s*$", material_body, flags=re.M)
        materials = []
        for i in range(1, len(mats) - 1, 2):
            idx, chunk = int(mats[i]), mats[i + 1]
            chunk = re.sub(r"^---\s*$", "", chunk, flags=re.M).strip()
            if not chunk:
                continue
            materials.append({"n": idx, "text": chunk, "chars": len(chunk)})
        # 作答要求
        qs_src = body[boundary.start():] if boundary else ""
        questions = re.findall(r"### 第[一二三四五六]题\s*\n(.+?)(?=\n### |\Z)",
                               qs_src, flags=re.S)
        questions = [re.sub(r"\s+", " ", x).strip() for x in questions]
        exams.append({
            "year": year, "paper": paper,
            "role": "primary" if paper == "地市级" else "auxiliary",
            "exam_date": EXAM_DATE.get(year, ""),
            "file": p.name,
            "materials": materials,
            "questions": questions[:6],
        })
    return sorted(exams, key=lambda e: (e["year"], list(papers).index(e["paper"])))


def first_answers(text):
    """One clearly delimited institutional answer per question; no repeated prompt.

    Original alternatives remain in the source files. This projection is for
    descriptive statistics, never an official marking key.
    """
    if "## 参考答案" not in text:
        return []
    appendix = text.split("## 参考答案", 1)[1]
    parts = re.split(r"^### 第([一二三四五六])题\s*$", appendix, flags=re.M)
    answers = []
    for i in range(1, len(parts) - 1, 2):
        markers = list(re.finditer(r"\*\*【参考答案[一二三四]?】\*\*", parts[i + 1]))
        if not markers:
            raise ValueError(f"question {parts[i]} has no explicit answer boundary")
        block = parts[i + 1][markers[0].end():markers[1].start() if len(markers) > 1 else None]
        block = re.split(r"(?m)^参考答案说明[：:]|^\*\*【(?:解析|参考解析)】\*\*", block, maxsplit=1)[0]
        answers.append({"question": parts[i], "text": block.strip()})
    return answers


# ---------------------------------------------------------------- text prep
PUNCT = re.compile(r"[\s\u3000-\u303f\uff00-\uffef0-9A-Za-z_.,;:!?\"'()\[\]{}<>/\\|@#$%^&*+=~`-]+")


def clean(t: str) -> str:
    return PUNCT.sub("", t)


def bigrams(t: str) -> Counter:
    t = clean(t)
    return Counter(t[i:i + 2] for i in range(len(t) - 1))


# ---------------------------------------------------------------- 2. tfidf
class Tfidf:
    def __init__(self, docs, top_terms=600, min_df=3, max_df_ratio=0.35):
        n = len(docs)
        df = Counter()
        raw = []
        for d in docs:
            bg = bigrams(d["text"][:9000])
            raw.append(bg)
            df.update(bg.keys())
        max_df = max_df_ratio * n
        self.vocab = {g for g, c in df.items() if min_df <= c <= max_df}
        self.idf = {g: math.log((n + 1) / (df[g] + 1)) + 1 for g in self.vocab}
        self.vecs = []
        for bg in raw:
            v = {g: c * self.idf[g] for g, c in bg.items() if g in self.vocab}
            if len(v) > top_terms:
                v = dict(sorted(v.items(), key=lambda kv: -kv[1])[:top_terms])
            norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            self.vecs.append({g: x / norm for g, x in v.items()})
        self.n = n

    def query(self, text, top_terms=1200):
        bg = bigrams(text[:9000])
        v = {g: c * self.idf[g] for g, c in bg.items() if g in self.vocab}
        if len(v) > top_terms:
            v = dict(sorted(v.items(), key=lambda kv: -kv[1])[:top_terms])
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    def top(self, qv, k=8, allowed_indices=None):
        out = []
        for i, dv in enumerate(self.vecs):
            if allowed_indices is not None and i not in allowed_indices:
                continue
            # iterate the smaller dict
            a, b = (qv, dv) if len(qv) <= len(dv) else (dv, qv)
            s = 0.0
            for g, x in a.items():
                y = b.get(g)
                if y:
                    s += x * y
            if s > 0:
                out.append((s, i))
        out.sort(reverse=True)
        return out[:k]


def month_delta(d1: str, d2: str) -> int | None:
    try:
        y1, m1 = int(d1[:4]), int(d1[5:7])
        y2, m2 = int(d2[:4]), int(d2[5:7])
    except Exception:
        return None
    return (y1 - y2) * 12 + (m1 - m2)


# ---------------------------------------------------------------- 3. topics
TOPICS = {
    "城市治理": ["城市治理", "城市更新", "老旧小区", "背街小巷", "精细化管理", "城市管理", "城管",
                 "城市体检", "完整社区", "便民生活圈", "城市运行"],
    "基层治理": ["基层治理", "社区治理", "网格化", "枫桥经验", "村两委", "村民自治", "接诉即办",
                 "基层减负", "乡镇", "街道办", "矛盾纠纷"],
    "科技创新": ["科技创新", "新质生产力", "关键核心技术", "研发投入", "专精特新", "科技成果转化",
                 "创新联合体", "中试", "科技自立自强", "基础研究"],
    "人工智能与数据": ["人工智能", "大模型", "算力", "数据要素", "数据标注", "数字政府", "智能体",
                       "算法", "数据集", "数字化转"],
    "制造业转型": ["制造业", "转型升级", "老字号", "传统工艺", "技术改造", "产业链", "单项冠军",
                   "隐形冠军", "智能制造", "工业互联网"],
    "乡村振兴": ["乡村振兴", "和美乡村", "驻村", "农产品", "县域经济", "农业农村", "土地流转",
                 "村集体", "千万工程"],
    "生态文明": ["生态文明", "双碳", "绿色低碳", "生态产品价值", "GEP", "污染防治", "碳汇",
                 "美丽中国", "绿水青山", "排污"],
    "能源电力": ["光伏", "新能源", "储能", "电网", "电力", "风电", "氢能", "核电", "充电桩"],
    "文旅非遗": ["文旅", "非遗", "文化遗产", "博物馆", "传统村落", "旅游", "历史文化名城",
                 "考古", "文创", "民宿"],
    "教育": ["义务教育", "职业教育", "高等教育", "乡村教育", "教育资源", "双减", "五育",
             "教师队伍", "家校", "课后服务", "县中", "学位"],
    "养老托育": ["养老", "银发", "托育", "适老化", "老年", "失能", "居家养老", "长期护理"],
    "就业与青年": ["就业", "毕业生", "灵活就业", "新就业形态", "技能人才", "零工", "返乡",
                   "青年", "劳动者权益", "职业培训"],
    "营商环境": ["营商环境", "民营经济", "中小企业", "融资难", "涉企", "民间投资", "清欠",
                 "减税降费", "惠企"],
    "政务服务": ["一网通办", "放管服", "政务服务", "高效办成一件事", "跨省通办", "免申即享",
                 "窗口", "办事", "数据共享"],
    "法治与执法": ["行政执法", "法治政府", "执法", "行政处罚", "行政复议", "普法", "依法治理",
                   "监管执法", "柔性执法"],
    "对外开放": ["对外开放", "自贸", "一带一路", "外资", "外贸", "跨境电商", "制度型开放",
                 "出海", "海外仓", "免签"],
    "消费与内需": ["消费", "以旧换新", "服务消费", "首发经济", "夜间经济", "文旅消费", "内需",
                   "促消费", "消费券"],
    "改革与市场": ["全国统一大市场", "要素市场化", "市场准入", "公平竞争审查", "深化改革",
                   "体制机制创新", "营商环境改革", "综合改革试点"],
    "安全应急": ["安全生产", "应急管理", "防灾减灾", "食品药品安全", "防汛", "消防",
                 "风险隐患", "事故", "应急预案"],
    "网络治理": ["网络暴力", "个人信息保护", "算法推荐", "网络谣言", "直播带货", "平台治理",
                 "数据安全", "网络安全", "清朗", "网络生态", "自媒体"],
    "文化自信": ["文化自信", "精神文明", "全民阅读", "书香", "中华优秀传统", "文化传承", "文脉",
                 "价值引领", "文明"],
    "医疗卫生": ["医疗", "卫生", "医院", "分级诊疗", "基层卫生", "医保", "药品", "健康"],
    "交通物流": ["物流", "铁路", "公路", "港口", "快递", "冷链", "枢纽", "多式联运", "交通运输",
                 "货运", "客运"],
    "区域协调": ["区域协调", "京津冀", "长三角", "粤港澳", "成渝", "都市圈", "城市群", "对口支援"],
    "海洋低空": ["海洋经济", "低空经济", "深海", "蓝色", "通用航空", "无人机", "临港"],
    "人才": ["人才", "引才", "人才政策", "技能大师", "工程师", "招才", "人才评价"],
    "干部作风": ["政绩观", "干部作风", "形式主义", "官僚主义", "基层干部", "为民服务",
                 "群众路线", "减负", "容错纠错", "督查检查"],
    "科普科研": ["科普", "科学素养", "科学家精神", "科研", "科研人员", "科技馆", "公众参与科学"],
    "传统产业与技艺": ["手工艺", "匠人", "技艺", "传承人", "工坊", "刺绣", "陶瓷", "丝绸",
                       "榫卯", "老手艺"],
    "数字经济业态": ["无人经济", "平台经济", "共享经济", "直播带货", "电商", "即时零售", "新业态"],
}
TOPIC_RE = {k: re.compile("|".join(map(re.escape, v))) for k, v in TOPICS.items()}


def topic_hits(text: str) -> set:
    return {k for k, r in TOPIC_RE.items() if r.search(text)}


# ---------------------------------------------------------------- 4. phrases
PHRASES = [
    "新质生产力", "全国统一大市场", "高效办成一件事", "放管服", "一网通办", "接诉即办",
    "枫桥经验", "千万工程", "以旧换新", "首发经济", "银发经济", "低空经济", "海洋经济",
    "未来产业", "场景培育", "耐心资本", "数据要素", "人工智能+", "新型城镇化", "城市更新",
    "完整社区", "城市体检", "一刻钟便民生活圈", "生态产品价值实现", "GEP核算", "碳汇",
    "林票", "零工市场", "新就业形态", "专精特新", "单项冠军", "灯塔工厂", "服务消费",
    "民间投资", "现代化产业体系", "投资于人", "民生为大", "十五五", "共同缔造", "共享村落",
    "元科普", "光污染", "暗夜", "家庭式养老", "医养结合", "县域医共体", "综合行政执法",
    "行政执法监督", "柔性执法", "免罚清单", "信用监管", "数字政府", "智慧城市", "数字乡村",
    "非遗工坊", "文化数字化", "全民阅读", "书香社会", "体教融合", "五育并举", "双减",
    "职普融通", "大国工匠", "技能社会", "共同富裕", "乡村振兴", "和美乡村", "耕地保护",
    "高标准农田", "种业振兴", "蓝色粮仓", "海洋牧场", "绿色转型", "新型能源体系", "沙戈荒",
    "虚拟电厂", "车网互动", "零碳园区", "碳足迹", "ESG", "绿色金融", "转型金融",
    "科技金融", "普惠金融", "养老金融", "数字金融", "耐心资本", "投早投小",
    "中试平台", "概念验证", "创新联合体", "揭榜挂帅", "赛马制", "科技特派员", "科技小院",
    "以工代赈", "公益性岗位", "社会救助", "分层分类救助", "儿童友好", "青年发展型城市",
    "生育支持", "托幼一体", "长期护理保险", "安宁疗护", "殡葬改革", "婚俗改革",
    "基层医疗卫生", "家庭医生", "分级诊疗", "紧密型县域医共体", "药品集采",
    "城市运行管理服务平台", "城市生命线", "韧性城市", "海绵城市", "地下管网",
    "综合交通枢纽", "多式联运", "冷链物流", "县域商业体系", "即时零售", "平台经济",
    "算法治理", "个人信息保护", "网络暴力", "AI生成内容", "深度合成", "数据跨境",
    "自贸试验区", "跨境电商综试区", "海外仓", "中间品贸易", "服务贸易", "制度型开放",
    "免签政策", "China Travel", "入境游", "文旅融合", "演艺经济", "微短剧",
    "政务APP", "指尖上的形式主义", "基层报表", "督查检查考核", "容错纠错", "三个区分开来",
    "正确政绩观", "功成不必在我", "接诉即办", "民呼我为", "共同缔造", "参与式治理",
]


def main():
    docs = [json.loads(l) for l in open(OUT / "index.jsonl", encoding="utf-8")]
    # drop the exam 题本 / 模型批注 themselves — they are the query, not a source
    docs = [d for d in docs if d["source"] not in ("ref-assignment", "ref-craft")]
    exams = parse_exams()
    print(f"docs={len(docs)} exams={len(exams)} "
          f"materials={sum(len(e['materials']) for e in exams)}")

    tf = Tfidf(docs)

    # ---------------- nearest corpus docs per 材料 ----------------
    matches, best_pre = [], []
    for e in exams:
        for m in e["materials"]:
            qv = tf.query(m["text"])
            # Filter by exact date before taking top-k, otherwise newer texts
            # can crowd all valid historical candidates out of the shortlist.
            eligible = {i for i, d in enumerate(docs) if pre_exam(d["date"], e["exam_date"])}
            got = []
            for rank, (score, i) in enumerate(tf.top(qv, k=12, allowed_indices=eligible), 1):
                d = docs[i]
                rec = {
                    "exam_year": e["year"], "paper": e["paper"],
                    "exam_date": e["exam_date"], "material": m["n"],
                    "rank": rank, "score": round(score, 4),
                    "doc_date": d["date"], "sublayer": d["sublayer"],
                    "source": d["source"], "outlet": d["outlet"],
                    "title": d["title"], "path": d["path"],
                    "lead_months": month_delta(e["exam_date"], d["date"]),
                }
                matches.append(rec)
                got.append(rec)
            if got:
                b = dict(got[0])
                b["n_pre"] = len(got)
                best_pre.append(b)

    def dump(rows, name):
        with open(OUT / name, "w", encoding="utf-8") as f:
            cols = list(rows[0].keys())
            f.write(",".join(cols) + "\n")
            for r in rows:
                f.write(",".join('"' + str(r[c]).replace('"', "'") + '"' for c in cols) + "\n")
        print(f"  -> {name} ({len(rows)} rows)")

    dump(matches, "matches.csv")
    dump(best_pre, "best_pre.csv")

    # ---------------- topic matrix: exams ----------------
    exam_topics = []
    for e in exams:
        for m in e["materials"]:
            for t in sorted(topic_hits(m["text"])):
                exam_topics.append({"year": e["year"], "paper": e["paper"],
                                    "material": m["n"], "topic": t})
    with open(OUT / "exam_topics.csv", "w", encoding="utf-8") as f:
        f.write("year,paper,material,topic\n")
        for r in exam_topics:
            f.write(f"{r['year']},{r['paper']},{r['material']},{r['topic']}\n")

    # ---------------- topic heat: corpus by month x sublayer ----------------
    heat = defaultdict(Counter)
    totals = defaultdict(Counter)
    for d in docs:
        if not d["date"]:
            continue
        mon = d["date"][:7]
        totals[mon][d["sublayer"]] += 1
        for t in topic_hits(d["text"]):
            heat[(t, mon)][d["sublayer"]] += 1
    with open(OUT / "topic_heat.csv", "w", encoding="utf-8") as f:
        f.write("topic,month,sublayer,n_docs,n_total,share\n")
        for (t, mon), c in sorted(heat.items()):
            for sl, n in c.items():
                tot = totals[mon][sl]
                f.write(f"{t},{mon},{sl},{n},{tot},{n/tot:.4f}\n")

    # ---------------- 2026 heat ranking (leading indicator) ----------------
    # window: 2026-01 .. 2026-10  (pre-2027 国考 material window)
    win = [d for d in docs if "2026-01-01" <= d["date"] < "2026-11-01"]
    recent = [d for d in win if "2026-05-01" <= d["date"] < "2026-11-01"]
    exam_hist = defaultdict(set)
    for r in exam_topics:
        exam_hist[r["topic"]].add(r["year"])
    rank_rows = []
    for t in TOPICS:
        n_all = sum(1 for d in win if t in topic_hits(d["text"]))
        n_rec = sum(1 for d in recent if t in topic_hits(d["text"]))
        yrs = sorted(exam_hist.get(t, []))
        rank_rows.append({
            "topic": t,
            "docs_2026": n_all,
            "share_2026": round(n_all / max(len(win), 1), 4),
            "docs_2026H2": n_rec,
            "share_2026H2": round(n_rec / max(len(recent), 1), 4),
            "exam_years": len(yrs),
            "exam_where": "/".join(str(y) for y in yrs),
            "last_exam": max(yrs) if yrs else 0,
        })
    rank_rows.sort(key=lambda r: -r["share_2026H2"])
    with open(OUT / "topic_rank_2026.csv", "w", encoding="utf-8") as f:
        cols = list(rank_rows[0].keys())
        f.write(",".join(cols) + "\n")
        for r in rank_rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")

    # ---------------- phrase transmission ----------------
    ph_rows = []
    for ph in dict.fromkeys(PHRASES):
        hits = [d for d in docs if ph in d["text"]]
        if not hits:
            continue
        dates = sorted(d["date"] for d in hits if d["date"])
        sub = Counter(d["sublayer"] for d in hits)
        exam_hits = []
        for e in exams:
            for m in e["materials"]:
                if ph in m["text"]:
                    exam_hits.append(f"{e['year']}{e['paper'][:2]}/材{m['n']}")
        ph_rows.append({
            "phrase": ph, "n_docs": len(hits),
            "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
            "A0": sub.get("A0_中央文件", 0), "A1": sub.get("A1_部委发布", 0),
            "B": sub.get("B_主流媒体", 0), "C": sub.get("C_地方实践", 0),
            "D": sub.get("D_学术智库", 0),
            "exams": len(exam_hits), "exam_where": ";".join(exam_hits[:6]),
        })
    ph_rows.sort(key=lambda r: (-r["exams"], -r["n_docs"]))
    dump(ph_rows, "phrases.csv")

    # ---------------- console summary ----------------
    print("\n== exam topic frequency (top 20) ==")
    for t, n in Counter(r["topic"] for r in exam_topics).most_common(20):
        print(f"  {t:14s} {n}")

    print("\n== pre-exam best-match lead (months) by sublayer ==")
    by = defaultdict(list)
    for r in best_pre:
        if r["score"] >= 0.10:
            by[r["sublayer"]].append(r["lead_months"])
    for k, v in sorted(by.items()):
        v.sort()
        print(f"  {k:14s} n={len(v):3d} median={v[len(v)//2]:4d} "
              f"range=[{v[0]},{v[-1]}]")

    print("\n== 2026H2 topic heat (top 18) ==")
    for r in rank_rows[:18]:
        print(f"  {r['topic']:14s} 2026={r['docs_2026']:4d} "
              f"H2={r['docs_2026H2']:4d} share={r['share_2026H2']:.3f} "
              f"exams={r['exam_where'] or '-'}")

    print("\n== phrases by exam usage (top 20) ==")
    for r in ph_rows[:20]:
        print(f"  {r['phrase']:14s} docs={r['n_docs']:4d} first={r['first']} "
              f"A0={r['A0']:2d} A1={r['A1']:3d} B={r['B']:4d} C={r['C']:3d} "
              f"exams={r['exams']} {r['exam_where']}")


if __name__ == "__main__":
    main()
