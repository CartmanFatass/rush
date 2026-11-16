#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""考察脚本（2026-11-16）：三类题与官方文件、官媒报道、规范用语的关系。

只读已有数据，不联网。输出写到 analysis/out/kaocha/。
数据来源：
  analysis/out/source_lag.csv   国考 2022–2026 政治理论 74 题的出题依据（此前会话对照机构解析的人工标注）
  analysis/out/pt.json          同 74 题的题干、选项、解析
  申论/*.md                      10 套卷（地市级、副省级）材料、题目、机构参考答案
  资料采集/01、03、04、09、10     本轮采集（采集者标注，验收只核了引文是否存在）
本脚本里属于"判断"的只有一处：JUDGE（2025、2026 两年 42 道题靠什么能做对），逐题写在下面，可逐题复核。
"""
import csv, json, re, glob, collections, datetime as dt, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out" / "kaocha"
OUT.mkdir(parents=True, exist_ok=True)
EXAM = {2022: "2021-11-28", 2023: "2023-01-08", 2024: "2023-11-26", 2025: "2024-12-01", 2026: "2025-11-30"}
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
S = {}  # 汇总


def D(s):
    m = re.match(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", str(s or "").strip())
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 15)) if m else None


def han(s):
    return "".join(re.findall(r"[一-鿿]", s))


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def wcsv(name, header, rows):
    with open(OUT / name, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


# ---------------------------------------------------------------- A 时政
# 2025、2026 两年逐题判断：做对这道题主要靠什么。
#  Y 元概念或政策方向即可判断（错项违背基本概念或方向，如把"市场"换成"政府"、把"质"换成"量"）
#  J 要记住原文措辞、成组对应、首次、数字（错项在逻辑上说得通）
#  M 混合：一部分错项可用概念排除，最后一步仍要记原文
#  L 马克思主义基本原理知识
#  G 要知道某项内容归在文件的哪一部分、哪一类
#  C 人文常识
JUDGE = {
    2025: dict(zip(range(1, 23), "Y L L L Y Y Y Y Y Y Y Y J G Y Y G G Y Y Y C".split())),
    2026: dict(zip(range(1, 21), "J J Y M J Y Y Y Y Y Y M Y Y J Y L L J J".split())),
}


def part_a():
    rows = list(csv.DictReader(open(HERE / "out" / "source_lag.csv", encoding="utf-8-sig")))
    a = {"题数": len(rows)}
    a["各年题数"] = dict(sorted(collections.Counter(r["exam"] for r in rows).items()))
    a["依据类型"] = dict(collections.Counter(r["type_name"] for r in rows).most_common())
    a["问法"] = dict(collections.Counter(r["format"] for r in rows).most_common())
    lag = [(int(r["exam"]), float(r["lag_months"])) for r in rows if r["lag_months"]]
    v = [x for _, x in lag]
    a["有日期题数"] = len(v); a["无时效来源题数"] = sum(r["type"] == "G" for r in rows)
    a["距笔试月数_中位"] = round(st.median(v), 1)
    a["12个月内"] = sum(x <= 12 for x in v); a["6个月内"] = sum(x <= 6 for x in v); a["超过24个月"] = sum(x > 24 for x in v)
    a["分年"] = {}
    for y in sorted(EXAM):
        vv = [x for yy, x in lag if yy == y]
        a["分年"][y] = dict(有日期=len(vv), 中位=round(st.median(vv), 1), 十二个月内=sum(x <= 12 for x in vv), 超过24个月=sum(x > 24 for x in vv))
    core = {2023: "二十大报告", 2025: "三中全会", 2026: "四中全会"}
    a["当年核心文件出题数"] = {y: f"{sum(k in r['source'] for r in rows if int(r['exam']) == y)}/{sum(int(r['exam']) == y for r in rows)}（{k}）" for y, k in core.items()}
    a["求是文章出题数_分年"] = dict(sorted(collections.Counter(r["exam"] for r in rows if r["type"] == "C").items()))
    # 逐题判断
    pt = json.load(open(HERE / "out" / "pt.json", encoding="utf-8"))
    tab = []; cnt = collections.Counter(); by = collections.defaultdict(collections.Counter)
    for x in pt:
        if x["year"] in JUDGE and x["n"] in JUDGE[x["year"]]:
            c = JUDGE[x["year"]][x["n"]]; cnt[c] += 1; by[x["year"]][c] += 1
            tab.append((x["year"], x["n"], c, re.sub(r"\s+", "", x["stem"])[:70]))
    seen = set(); tab2 = []
    for t in tab:
        if (t[0], t[1]) not in seen: seen.add((t[0], t[1])); tab2.append(t)
    cnt = collections.Counter(t[2] for t in tab2)
    a["2025至2026逐题判断"] = dict(题数=len(tab2), 合计=dict(cnt.most_common()),
                             分年={y: dict(collections.Counter(t[2] for t in tab2 if t[0] == y).most_common()) for y in JUDGE})
    wcsv("shizheng_2025_2026_judgement.csv", ["年度", "题号", "判断", "题干前70字"], tab2)
    # 求是首篇被考到的情况
    qs = jl(ROOT / "资料采集/03-关系对与方法论/求是署名文章目录.jsonl")
    for r in qs: r["d"] = D(r["出刊日期"])
    sk, seen = [], set()
    for r in jl(ROOT / "资料采集/09-省考时政溯源/省考时政题溯源.jsonl"):
        if r["题干前60字"] not in seen: seen.add(r["题干前60字"]); sk.append(r)
    hits = collections.defaultdict(list); nC = nM = 0

    def match(date, tag):
        # 只用写到"日"的依据日期去配期次；只到月的不配，避免把同月别的文章算成首篇
        d = D(date) if re.match(r"\d{4}-\d{1,2}-\d{1,2}", str(date or "")) else None
        if not d: return False
        b = [r for r in qs if r["d"] and abs((r["d"] - d).days) <= 3]
        if b: hits[(b[-1]["年份"], b[-1]["期次"])].append(tag)
        return bool(b)
    for r in sk:
        if r.get("依据类型") == "C": nC += 1; nM += match(r.get("依据发布日期"), f"省考{r['年度']}")
    for r in rows:
        if r["type"] == "C": nC += 1; nM += match(r["source_date"], f"国考{r['exam']}")
    a["求是首篇"] = dict(署名文章类题数=nC, 能配到期次=nM, 省考去重题数=len(sk),
                     各年24期中被考到的期数={y: sum((y, r["期次"]) in hits for r in qs if r["年份"] == y) for y in (2022, 2023, 2024, 2025)})
    wcsv("qiushi_hits.csv", ["年份", "期次", "出刊日期", "标题", "类型", "被哪些考试考到", "题数"],
         [(r["年份"], r["期次"], r["出刊日期"], r["标题"], r["类型"], "、".join(sorted(set(hits.get((r["年份"], r["期次"]), [])))), len(hits.get((r["年份"], r["期次"]), []))) for r in qs if r["年份"] >= 2022])
    # 选项里的标记词与真假：只取"选对""选错"两种问法里四个选项各是一句陈述的题
    lab = {(int(r["exam"]), int(r["n"]), r["paper"]): r["format"] for r in rows}
    stm = []
    for x in pt:
        fmt = lab.get((x["year"], x["n"], x["paper"]))
        opts = re.findall(r"- \*\*([A-D])\*\*\. (.*)", x["body"]); ans = re.search(r"\*\*答案\*\*：(\w)", x["body"])
        if not ans or len(opts) != 4 or fmt not in ("选对", "选错"): continue
        texts = [(o, re.sub(r"　?✅", "", t).strip()) for o, t in opts]
        if any(re.fullmatch(r"[①②③④⑤、\d项]+", t) for _, t in texts): continue
        for o, t in texts: stm.append((t, (o != ans.group(1)) if fmt == "选对" else (o == ans.group(1))))
    groups = {"收缩否定词（取代、限制、弱化、降低、缩减、禁止、取消）": r"取代|限制|弱化|降低|缩减|严禁|禁止|放弃|取消",
              "转变方向句（转向、转变、转型）": r"转向|转变|转型",
              "定位词（首位、首要、根本、关键、基础、核心、决定性、主体、重点、前提）": r"首位|第一位|首要|根本|关键|基础|核心|决定性|主体|重点|前提",
              "绝对化词（全面、一律、完全、所有、唯一、彻底、必然）": r"全面|一律|完全|所有|唯一|彻底|必然"}
    a["选项标记词"] = {"陈述句数": len(stm), "其中错误": sum(f for _, f in stm)}
    for g, pat in groups.items():
        sub = [f for t, f in stm if re.search(pat, t)]
        a["选项标记词"][g] = f"{sum(sub)}/{len(sub)} 为错误项"
    # 年度政治日历里的会议、文件，有多少被国考或省考考到：日期相差三天以内，且名称对得上
    TOK = ["三中全会", "四中全会", "一号文件", "政府工作报告", "经济工作会议", "农村工作会议", "城市工作会议", "科技大会", "教育大会", "民营企业座谈会", "政治局会议"]

    def norm(s):
        s = re.sub(r"\s+", "", s)
        return s.replace("第三次全体会议", "三中全会").replace("第四次全体会议", "四中全会")

    def lcs(x, y):
        best = 0; prev = [0] * (len(y) + 1)
        for cx in x:
            cur = [0] * (len(y) + 1)
            for j, cy in enumerate(y, 1):
                if cx == cy: cur[j] = prev[j - 1] + 1; best = max(best, cur[j])
            prev = cur
        return best

    def same_event(cname, qname):
        cname, qname = norm(cname), norm(qname)
        return any(t in cname and t in qname for t in TOK) or lcs(han(cname), han(qname)) >= 6
    full = lambda s: bool(re.match(r"\d{4}-\d{1,2}-\d{1,2}", str(s or "")))
    QQ = [(D(r["依据发布日期"]), f"省考{r['年度']}", r["依据名称"]) for r in sk if full(r.get("依据发布日期"))]
    QQ += [(D(r["source_date"]), f"国考{r['exam']}", r["source"]) for r in rows if full(r["source_date"])]
    cal = jl(ROOT / "资料采集/07-议程日历/年度政治日历.jsonl"); crow = []; tot = collections.Counter(); got = collections.Counter()
    for r in cal:
        d = D(r["日期"])
        if not d or r["年份"] not in (2023, 2024, 2025): continue
        name = r["名称"] + ("中央一号文件" if r["类别"] == "中央一号文件" else "")
        m = [q for q in QQ if abs((q[0] - d).days) <= 3 and same_event(name, q[2])]
        tot[r["年份"]] += 1; got[r["年份"]] += bool(m)
        crow.append((r["年份"], r["日期"], r["类别"], r["名称"], len(m), "、".join(sorted({q[1] for q in m}))))
    wcsv("calendar_hits.csv", ["年份", "日期", "类别", "名称", "对上的题数", "被哪些考试考到"], crow)
    a["年度政治日历条目被考到"] = {y: f"{got[y]}/{tot[y]}" for y in sorted(tot)}
    S["A_时政"] = a


# ---------------------------------------------------------------- B 材料
CENTRAL = ["经济日报", "新华社", "新华网", "人民日报", "人民网", "民生周刊", "光明", "求是", "工人日报", "中国教育报", "中国青年报", "农民日报",
           "中国新闻网", "中国经济导报", "中国经济新闻网", "中国质量", "健康报", "中国改革报", "科技日报", "中央广电总台", "央视", "央广"]
ORGAN = ["中央纪委国家监委", "水利部", "中国铁路"]
LOCAL = ["解放日报", "澎湃", "新京报", "四川在线", "湖南日报", "丽水日报", "中山日报", "新华日报", "河北日报", "浙江在线", "浙江日报"]
FIRM = ["卡车网", "松粮集团", "八号桥", "凤凰网"]


def outlet_class(s):
    """按原发媒体归类：'X（Y转载）'取X；'X（转Y）'取Y。"""
    m = re.search(r"（转(?!载)([^）]+)）", s)
    name = m.group(1) if m else re.split(r"[（(]", s)[0]
    for lab, keys in (("中央媒体", CENTRAL), ("中央机关与央企自有渠道", ORGAN), ("地方党报党媒", LOCAL), ("企业稿与商业媒体", FIRM)):
        if any(k in name for k in keys): return lab
    return "地方政府、高校、协会等机构"


def part_b():
    recs = []
    for f in sorted(glob.glob(str(ROOT / "资料采集/01-材料溯源/20*.jsonl"))): recs += jl(f)
    mats = [r for r in recs if "题眼句" not in r]
    key = lambda r: (r["年度"], r["卷"], str(r["材料号"]))
    b = {"材料记录数": len(mats), "材料数": len({key(r) for r in mats})}
    cites = []
    for r in mats:
        ex = D(EXAM[int(r["年度"])])
        for x in (r.get("原报道") or []):
            s = re.sub(r"\s+", "", str(x.get("媒体", ""))); d = D(x.get("发表日"))
            cites.append(dict(k=key(r), 媒体=s, 类=outlet_class(s), 日=str(x.get("发表日", "")), lag=(ex - d).days / 30.44 if d else None,
                              逐字="逐字" in str(x.get("判断依据", ""))))
    b["报道引用数"] = len(cites); b["有报道的材料数"] = len({c["k"] for c in cites})
    b["媒体归类"] = dict(collections.Counter(c["类"] for c in cites).most_common())
    b["经济日报引用数"] = sum("经济日报" in c["媒体"].split("（")[0] for c in cites)
    b["至少一篇中央媒体报道的材料数"] = len({c["k"] for c in cites if c["类"] == "中央媒体"})
    b["判断依据写明逐字重合的引用数"] = sum(c["逐字"] for c in cites)
    pre = [c for c in cites if c["lag"] is not None and c["lag"] >= 0]
    v = sorted(c["lag"] for c in pre)
    b["考前报道引用"] = dict(n=len(v), 中位月=round(st.median(v), 1), 一年内=sum(x <= 12 for x in v), 两年内=sum(x <= 24 for x in v), 三年以上=sum(x > 36 for x in v))
    best = {}
    for c in pre: best[c["k"]] = min(best.get(c["k"], 999), c["lag"])
    bv = sorted(best.values())
    b["每则材料最近一篇考前报道"] = dict(材料数=len(bv), 中位月=round(st.median(bv), 1), 半年内=sum(x <= 6 for x in bv), 一年内=sum(x <= 12 for x in bv), 两年内=sum(x <= 24 for x in bv), 两年以上=sum(x > 24 for x in bv))
    named = []
    for r in mats:
        ex = D(EXAM[int(r["年度"])])
        for x in (r.get("政策背景") or []):
            if str(x.get("点名或判断", "")).startswith("材料"):
                d = D(x.get("日期")); named.append((key(r), (ex - d).days / 30.44 if d else None))
    nv = sorted(x for _, x in named if x is not None)
    b["材料点名的政策文件"] = dict(次数=len(named), 涉及材料数=len({k for k, _ in named}), 有日期=len(nv), 距笔试中位月=round(st.median(nv), 1), 最短=round(nv[0]), 最长=round(nv[-1]))
    lj = collections.defaultdict(set)
    for r in mats: lj[key(r)].add(str(r.get("立纠"))[:1])
    only_li = sum(v == {"立"} for v in lj.values())
    b["立纠"] = dict(只写正面做法=only_li, 含问题或教训=len(lj) - only_li)
    b["原型进过官方名单或通报的材料数"] = len({key(r) for r in mats if r.get("官方案例名单")})
    tr = [str(r.get("改写痕迹") or "") for r in mats]
    b["改写痕迹"] = dict(有记录=sum(bool(t.strip()) for t in tr), 改名或隐去=sum(bool(re.search(r"→|←|改为|化名|隐去", t)) for t in tr),
                     删去内容=sum("删" in t for t in tr), 新增内容=sum(bool(re.search(r"新增|增加|加了", t)) for t in tr),
                     删去后续处理=sum(("删" in t) and bool(re.search(r"后续|立案|查处|问责|罚款|整改", t)) for t in tr))
    wcsv("material_reports.csv", ["年度", "卷", "材料号", "媒体原字段", "归类", "发表日", "距笔试月数", "判断依据含逐字重合"],
         [(*c["k"], c["媒体"], c["类"], c["日"], None if c["lag"] is None else round(c["lag"], 1), int(c["逐字"])) for c in cites])
    S["B_材料"] = b


# ---------------------------------------------------------------- C、D 申论题目与答案
APP = ["编者按", "宣传材料", "案例摘要", "短评", "《关于", "汇报", "实施意见", "提案", "展板", "发布词"]


def load(year, paper):
    t = (ROOT / "申论" / f"{year}国考申论（{paper}）.md").read_text(encoding="utf-8")
    ms = re.search(r"## 二、给定材料(.*?)## 三、作答要求", t, re.S).group(1)
    p = re.split(r"### 材料\s*(\d+)", ms)[1:]
    mats = {int(p[i]): p[i + 1].strip() for i in range(0, len(p), 2)}
    req = re.search(r"## 三、作答要求(.*?)## 参考答案", t, re.S).group(1)
    qp = re.split(r"### 第(.)题", req)[1:]
    qs = {CN[qp[i]]: re.sub(r"\s+", "", qp[i + 1]).rstrip("-") for i in range(0, len(qp), 2)}
    ap = re.split(r"### 第(.)题", t.split("## 参考答案", 1)[1])[1:]
    out = []
    for i in range(0, len(ap), 2):
        n = CN[ap[i]]; q = qs[n]
        vers = [re.split(r"参考答案说明", x)[0].strip() for x in re.split(r"\*\*【参考答案[一二三四]?】\*\*", ap[i + 1])[1:]] or [ap[i + 1].strip()]
        refs = sorted({int(x) if x.isdigit() else CN[x] for x in re.findall(r"给定(?:资料|材料)\s*([0-9一二三四五])", q)})
        if "1000" in q or "自拟题目" in q or "为题目" in q: typ = "大作文"
        elif any(k in q for k in APP): typ = "应用文"
        elif "建议" in q or "对策" in q: typ = "对策"
        else: typ = "概括分析"
        out.append(dict(year=year, paper=paper, n=n, q=q, refs=refs, typ=typ, ans=vers[0], allans=vers))
    return mats, out


def grams(s, n):
    s = han(s); return [s[i:i + n] for i in range(len(s) - n + 1)]


def part_cd():
    rows = []; A = collections.Counter(); M = collections.Counter(); na = nm = 0
    small = collections.defaultdict(str); mat_all = ""; essays = []
    for y in range(2022, 2027):
        for p in ("地市级", "副省级"):
            mats, qs = load(y, p); allm = "".join(mats.values()); mat_all += allm
            for g in grams(allm, 2): M[g] += 1
            nm += len(han(allm))
            for q in qs:
                if q["typ"] == "大作文": essays += [(y, p, a) for a in q["allans"]]; continue
                ref = "".join(mats[r] for r in q["refs"] if r in mats) or allm
                a = re.sub(r"[一二三四五六七八九十]、|[（(][一二三四五六七八九十\d][)）]|\d[\.．、]", "", q["ans"])
                g3 = grams(a, 3); R = set(grams(ref, 3))
                rows.append((y, p, q["n"], q["typ"], round(sum(g in R for g in g3) / max(1, len(g3)), 3), len(han(a))))
                for g in grams(a, 2): A[g] += 1
                na += len(han(a)); small[q["typ"]] += a
    c = {"小题数": len(rows), "题型数": dict(collections.Counter(r[3] for r in rows).most_common()), "答案汉字数": na, "材料汉字数": nm}
    c["答案三字片段见于指定材料的比例"] = {t: dict(题数=len(v), 平均=round(st.mean(v), 3), 中位=round(st.median(v), 3), 最低=min(v), 最高=max(v))
                                 for t in ("概括分析", "应用文", "对策") for v in [[r[4] for r in rows if r[3] == t]]}
    wcsv("xiaoti_coverage.csv", ["年度", "卷", "题号", "题型", "答案三字片段见于指定材料的比例", "答案汉字数"], rows)
    over = sorted(((cnt, g, round(cnt / na * 1e4, 1), round(M.get(g, 0) / nm * 1e4, 1)) for g, cnt in A.items()
                   if cnt >= 9 and (cnt / na * 1e4) / (M.get(g, 0) / nm * 1e4 + 0.15) >= 2.5), reverse=True)
    wcsv("answer_overrep_bigrams.csv", ["二字片段", "答案中次数", "答案每万字", "材料每万字"], [(g, cnt, ra, rm) for cnt, g, ra, rm in over])
    c["答案中远多于材料的二字片段_前30"] = [f"{g}{cnt}" for cnt, g, _, _ in over[:30]]
    sm = "".join(small.values())
    for name, f in (("通报定性词", "问题定性词表.jsonl"), ("通报整改手段词", "整改手段词表.jsonl")):
        ws = [w["词"] for w in jl(ROOT / "资料采集/04-官方案例与通报" / f)]
        hit = sorted(((sm.count(w), w) for w in ws if sm.count(w)), reverse=True)
        c[name] = dict(词表词数=len(ws), 在小题答案中出现的词数=len(hit), 在对策题答案中出现的词数=sum(1 for w in ws if small["对策"].count(w)), 出现最多的=[f"{w}{n}" for n, w in hit[:10]])
    slog = ["以人民为中心", "新质生产力", "中国式现代化", "新发展理念", "系统观念", "高质量发展", "习近平", "总书记", "党的二十大"]
    essay_all = "".join(e[2] for e in essays)
    c["口号与称谓出现次数_依次为材料_小题答案_卷内范文"] = {w: [mat_all.count(w), sm.count(w), essay_all.count(w)] for w in slog}
    S["C_小题"] = c
    # D 作文
    names = []
    for f, k in (("定名经验.jsonl", "名称"), ("人物典型.jsonl", "人物"), ("新事例.jsonl", "事例")):
        names += [r[k] for r in jl(ROOT / "资料采集/10-典型事例口径" / f)]
    # 事例名拆成可检索的词；泛指词不算（否则"新时代""经验"这类词会误中）
    STOP = {"新时代", "经验", "精神", "制度", "外贸", "北京", "杭州", "城市", "综合治理", "精准扶贫", "冰雪旅游", "产业投资", "从政起步地",
            "千村示范", "万村整治", "电动载人汽车", "锂电池", "太阳能电池", "江苏省城市足球联赛", "国际商贸城"}
    hit = collections.Counter()
    for n in names:
        toks = set(re.findall(r"[一-鿿A-Za-z0-9]{2,}", re.sub(r"[“”\"《》（）()、与及含·：:]", " ", n)))
        toks |= {t[:-2] for t in toks if t[-2:] in ("制度", "经验", "精神") and len(t) >= 5}
        for k in toks - STOP:
            ce = sum(1 for e in essays if k in e[2])
            if ce: hit[n] = max(hit[n], ce)
    d = dict(卷内范文篇数=len(essays), 范文总汉字=sum(len(han(e[2])) for e in essays), 典型事例名单条数=len(names), 在范文中出现的典型事例及篇数=dict(hit),
             提到习近平或总书记的范文篇数=sum(1 for e in essays if "习近平" in e[2] or "总书记" in e[2]))
    S["D_作文"] = d


def part_e():
    """本地语料索引各年的记录数：用来说明现有语料不能直接比年度出现次数。"""
    p = HERE / "out" / "index.jsonl"
    if not p.exists(): return
    c = collections.Counter()
    with open(p, encoding="utf-8") as f:
        for l in f:
            try: c[str(json.loads(l).get("date") or "")[:4]] += 1
            except Exception: pass
    S["E_本地语料各年记录数"] = dict(sorted(c.items()))


if __name__ == "__main__":
    part_a(); part_b(); part_cd(); part_e()
    json.dump(S, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(S, ensure_ascii=False, indent=1))
