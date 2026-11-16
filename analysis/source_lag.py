#!/usr/bin/env python3
"""行测政治理论（副省+地市，2022–2026）每题的出题依据：来源类型 + 发布日期 → 距考试的月数。

来源类型与日期是对照官方解析逐题人工标注的（74 题，去重后）；本脚本只做统计。
输出 out/source_lag.csv（逐题）并打印按年汇总。
"""
import csv
import datetime as dt
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MD = HERE.parent / "_build" / "md"
OUT = HERE / "out"

# 笔试日期（2023 年度因疫情推迟到 2023-01）
EXAM = {2022: "2021-11-28", 2023: "2023-01-08", 2024: "2023-11-26",
        2025: "2024-12-01", 2026: "2025-11-30"}

TYPES = {
    "A": "党代会/全会文件",
    "B": "中央会议（通稿或会上讲话）",
    "C": "《求是》等署名文章",
    "D": "重要讲话（座谈会/集体学习/周年大会/外交）",
    "E": "地方考察/回信/贺词",
    "F": "政府文件/规划/党内法规/法律",
    "G": "基本原理/党史（无时效来源）",
}

# 序号 = parse() 去重后的顺序；(类型, 依据发布日, 依据名称)
LABELS = {
    0: ("D", "2021-07-01", "庆祝建党100周年大会讲话"),
    1: ("D", "2021-01-11", "省部级研讨班讲话（新发展阶段）"),
    2: ("E", "2021-04-27", "广西考察"),
    3: ("D", "2021-02-25", "全国脱贫攻坚总结表彰大会讲话"),
    4: ("E", "2020-12-08", "珠峰高程互致信函"),
    5: ("D", "2021-07-01", "庆祝建党100周年大会讲话"),
    6: ("D", "2021-01-11", "省部级研讨班讲话（扩大内需）"),
    7: ("B", "2020-11-16", "中央全面依法治国工作会议"),
    8: ("D", "2021-07-01", "庆祝建党100周年大会讲话"),
    9: ("G", "", "历次党代会排序"),
    10: ("A", "2022-10-16", "二十大报告"),
    11: ("A", "2022-10-16", "二十大报告"),
    12: ("A", "2022-10-16", "二十大报告"),
    13: ("A", "2022-10-16", "二十大报告"),
    14: ("F", "2022-06-20", "《习近平经济思想学习纲要》"),
    15: ("F", "2021-06-26", "《中国共产党党徽党旗条例》"),
    16: ("E", "2021-12-31", "二〇二二年新年贺词"),
    17: ("D", "2014-10-15", "文艺工作座谈会讲话"),
    18: ("A", "2022-10-16", "二十大报告"),
    19: ("B", "2021-08-17", "中央财经委第十次会议"),
    20: ("D", "2023-06-02", "文化传承发展座谈会讲话"),
    21: ("D", "2023-03-06", "看望政协民建工商联界委员讲话"),
    22: ("E", "2023-07-27", "内蒙古/四川考察（主题教育）"),
    23: ("E", "2023-05-17", "陕西考察"),
    24: ("D", "2023-06-28", "对党的建设和组织工作的指示"),
    25: ("B", "2023-07-18", "全国生态环境保护大会"),
    26: ("E", "2022-10-02", "给山东地矿六队的回信"),
    27: ("D", "2023-03-15", "中国共产党与世界政党高层对话会"),
    28: ("B", "2022-12-24", "中央农村工作会议（农业强国）"),
    29: ("C", "2022-12-19", "署名文章《谱写新时代中国宪法实践新篇章》"),
    30: ("B", "2023-07-18", "全国生态环境保护大会"),
    31: ("F", "2022-08-01", "《黑土地保护法》"),
    32: ("D", "2023-06-30", "政治局第六次集体学习"),
    33: ("G", "", "矛盾的普遍性"),
    34: ("G", "", "马克思主义政治经济学"),
    35: ("G", "", "真理与价值"),
    36: ("B", "2023-10-31", "中央金融工作会议"),
    37: ("B", "2023-12-20", "中央农村工作会议（粮食安全，兼国办大食物观意见）"),
    38: ("C", "2024-10-31", "《求是》：促进高质量充分就业"),
    39: ("B", "2024-01-08", "二十届中央纪委三次全会讲话"),
    40: ("A", "2024-07-18", "三中全会《决定》"),
    41: ("A", "2024-07-18", "三中全会《决定》"),
    42: ("D", "2023-09-07", "新时代推动东北全面振兴座谈会"),
    43: ("A", "2024-07-18", "三中全会《决定》"),
    44: ("B", "2023-10-08", "全国宣传思想文化工作会议"),
    45: ("A", "2024-07-18", "三中全会《决定》"),
    46: ("A", "2024-07-18", "三中全会《决定》"),
    47: ("A", "2024-07-18", "三中全会《决定》"),
    48: ("A", "2024-07-18", "三中全会《决定》"),
    49: ("F", "2023-12-27", "《中国共产党纪律处分条例》（修订）"),
    50: ("D", "2024-01-31", "政治局第十一次集体学习"),
    51: ("D", "2024-04-23", "新时代推动西部大开发座谈会"),
    52: ("F", "2024-03-05", "2024 年政府工作报告"),
    53: ("E", "2023-12-31", "二〇二四年新年贺词"),
    54: ("D", "2023-02-07", "多篇讲话综合（自信自立）"),
    55: ("C", "2025-06-16", "《求是》：用中长期规划指导经济社会发展"),
    56: ("C", "2025-04-16", "《求是》：加快建设文化强国"),
    57: ("F", "2025-04-07", "《加快建设农业强国规划（2024—2035年）》"),
    58: ("D", "2020-11-16", "多篇讲话综合（法治一体建设）"),
    59: ("B", "2025-07-15", "中央城市工作会议"),
    60: ("C", "2025-02-28", "《求是》：经济工作必须统筹好几对重要关系"),
    61: ("B", "2025-07-30", "中央政治局会议（经济形势）"),
    62: ("C", "2024-11-16", "《求是》：以人口高质量发展支撑中国式现代化"),
    63: ("A", "2025-10-23", "四中全会《建议》"),
    64: ("D", "2024-01-15", "多篇讲话综合（战略思维）"),
    65: ("C", "2025-06-01", "《求是》：加快建设教育强国"),
    66: ("D", "2024-11-18", "二十国集团峰会讲话"),
    67: ("B", "2024-06-24", "全国科技大会讲话"),
    68: ("D", "2024-12-27", "多篇讲话综合（党性）"),
    69: ("G", "", "问题导向"),
    70: ("G", "", "马克思主义科学态度"),
    71: ("G", "", "实践观"),
    72: ("E", "2025-07-08", "地方考察讲话对应（山西/山东/江苏/海南）"),
    73: ("C", "2025-09-01", "《求是》：弘扬伟大抗战精神"),
}

# 专题归类（人工）：M1–M11 是另一份方案的 11 个专题，X* 是它没有覆盖的
TOPIC_NAMES = {
    "M1": "十五五/高质量发展/现代化总论", "M2": "科技创新与新质生产力", "M3": "内需与经济体制改革",
    "M4": "金融强国", "M5": "金融风险与监管", "M6": "党的建设（从严治党/党史/政绩观）",
    "M7": "数字中国", "M8": "民生与人口（含教育）", "M9": "乡村与城乡融合", "M10": "生态绿色",
    "M11": "法治与开放", "X1": "文化建设（含纪念）", "X2": "原理与方法论", "X3": "区域协调/地方考察",
    "X4": "城市工作", "X5": "国家安全", "X6": "政治制度（民主/统战）", "X7": "其他常识",
}
TOPIC_OF = {
    "M1": [1, 10, 11, 18, 27, 55], "M2": [16, 40, 42, 67], "M3": [6, 14, 21, 48, 52, 60], "M4": [36],
    "M6": [0, 2, 5, 8, 9, 15, 22, 24, 39, 49, 50, 68], "M8": [3, 13, 19, 38, 41, 47, 61, 62, 65],
    "M9": [23, 28, 31, 37, 57], "M10": [25, 30, 46], "M11": [7, 29, 58, 43, 66],
    "X1": [17, 20, 44, 53, 56, 73], "X2": [32, 33, 34, 35, 54, 64, 69, 70, 71], "X3": [51, 72],
    "X4": [59], "X5": [63], "X6": [12, 45], "X7": [4, 26],
}
TOPIC = {i: k for k, v in TOPIC_OF.items() for i in v}

Q_RE = re.compile(r"^## 第 (\d+) 题　<sub>qid (\d+) · ([^<]*)</sub>", re.M)


def parse():
    qs, seen = [], set()
    for p in sorted(MD.glob("01-政治理论__202[2-6]年*.md")):
        year = int(re.search(r"(\d{4})年", p.name).group(1))
        paper = re.search(r"（(.+?)(网友回忆版)?）", p.name).group(1)
        if "行政" in paper:
            continue
        parts = Q_RE.split(p.read_text(encoding="utf-8"))
        for i in range(1, len(parts) - 3, 4):
            n, qid, tag, body = parts[i:i + 4]
            stem = re.split(r"\n-\s*\*\*A\*\*", body)[0].strip()
            key = (year, re.sub(r"\s", "", stem)[:60])
            if key in seen:
                continue
            seen.add(key)
            qs.append({"year": year, "paper": paper, "n": int(n), "tag": tag.strip(), "stem": stem})
    return qs


def months(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days / 30.44


def fmt(stem):
    if re.search(r"有几项|有（\s*）项", stem):
        return "几项"
    if re.search(r"不准确|不正确|错误|不恰当|不符合|不属于", stem):
        return "选错"
    if re.search(r"排序|对应", stem):
        return "排序/对应"
    return "选对"


def main():
    qs = parse()
    assert len(qs) == len(LABELS), (len(qs), len(LABELS))
    rows = []
    for i, q in enumerate(qs):
        t, d, name = LABELS[i]
        lag = round(months(d, EXAM[q["year"]]), 1) if d else ""
        rows.append({"idx": i, "exam": q["year"], "paper": q["paper"], "n": q["n"], "tag": q["tag"],
                     "type": t, "type_name": TYPES[t], "source": name, "source_date": d,
                     "lag_months": lag, "format": fmt(q["stem"]),
                     "topic": TOPIC[i], "topic_name": TOPIC_NAMES[TOPIC[i]],
                     "stem": q["stem"][:60].replace("\n", " ")})
    OUT.mkdir(exist_ok=True)
    with open(OUT / "source_lag.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["exam"]].append(r)
    print("题量与来源类型（题数）")
    print("年度  题数 " + " ".join(f"{k:>3s}" for k in TYPES))
    for y in sorted(by):
        c = Counter(r["type"] for r in by[y])
        print(f"{y}  {len(by[y]):3d}  " + " ".join(f"{c.get(k, 0):3d}" for k in TYPES))
    print()
    print("时效（只算有日期的题）：距考试月数")
    print("年度  有日期  中位  ≤6月  ≤12月  ≤18月  >24月  最近一条来源")
    for y in sorted(by):
        d = [r for r in by[y] if r["lag_months"] != ""]
        lags = [r["lag_months"] for r in d]
        near = min(d, key=lambda r: r["lag_months"])
        n = len(lags)
        print(f"{y}  {n:4d}  {st.median(lags):5.1f}  {sum(l <= 6 for l in lags)/n:4.0%}  "
              f"{sum(l <= 12 for l in lags)/n:5.0%}  {sum(l <= 18 for l in lags)/n:5.0%}  "
              f"{sum(l > 24 for l in lags)/n:4.0%}  {near['source']}（{near['lag_months']} 月）")
    print()
    print("题型")
    for y in sorted(by):
        c = Counter(r["format"] for r in by[y])
        print(f"{y}  " + "  ".join(f"{k} {v}" for k, v in c.most_common()))
    print()
    print("专题 × 年度（题数）")
    years = sorted(by)
    print(f"{'专题':<28s}" + " ".join(str(y) for y in years) + "  合计  近两年")
    for k, name in TOPIC_NAMES.items():
        c = Counter(r["exam"] for r in rows if r["topic"] == k)
        print(f"{k:>3s} {name:<22s}" + " ".join(f"{c.get(y, 0):4d}" for y in years)
              + f"  {sum(c.values()):4d}  {c.get(2025, 0) + c.get(2026, 0):4d}")
    cov = sum(1 for r in rows if r["topic"].startswith("M") and r["exam"] >= 2025)
    tot = sum(1 for r in rows if r["exam"] >= 2025)
    print(f"11 个专题覆盖近两年 {cov}/{tot} 题")
    print()
    print("被考两题以上的同一来源")
    c = Counter((r["exam"], r["source"]) for r in rows if r["source_date"])
    for (y, s), v in sorted(c.items()):
        if v > 1:
            print(f"  {y}  {s} × {v}")


if __name__ == "__main__":
    main()
