#!/usr/bin/env python3
"""索引外部参考资料：扫描 Learn-to-Write 语料，产出 corpus-manifest.json / .csv / CORPUS.md。

语料本体不在本仓库（`~/projects/Learn-to-Write/corpus/`），本仓库只保存
「有什么、在哪、多大、什么日期范围、怎么重抓」这份索引，保证分析可复现。

用法：
    python3 corpus_manifest.py            # 生成索引
    python3 corpus_manifest.py --check    # 只比对，不写文件（CI / 手动核对）
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CORPUS_REPO = Path("/home/fires/projects/Learn-to-Write")
CORPUS = CORPUS_REPO / "corpus"
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

# 目录 -> (层, 中文名, 重抓命令)
SOURCES = {
    "renmin-ribao": ("B_主流媒体", "人民日报（评论 7 栏 + 版面栏目 16 个）",
                     "python -m tools.collect.download_renmin_commentary renminshiping renminluntan "
                     "pinglunyuan shelun renzhongping renping zhongyin --start-date 2020-01-01 "
                     "--index-pages 45 --delay 0.3\n"
                     "/home/fires/osint/.venv/bin/python ~/projects/rush/analysis/crawl_rmrb_columns.py "
                     "2023-01-01 2024-11-30"),
    "local-papers": ("C1_地方党报", "地方党报（河南/青岛/太原/湖南）",
                     "/home/fires/osint/.venv/bin/python ~/projects/rush/analysis/crawl_local_papers.py "
                     "2020-07-01 2024-12-31 all"),
    "local-gov-leaders": ("C_地方实践", "地方党政领导活动", "python -m tools.collect.download_local_gov_leaders"),
    "liaowang": ("B_主流媒体", "瞭望", "python -m tools.collect.download_liaowang_commentary sp2 dyxx zglzjs "
                 "szcl rgc sz zcjm rdjx tbbd lwft --start-date 2020-01-01"),
    "guangming": ("B_主流媒体", "光明日报", "python -m tools.collect.download_guangming_commentary "
                  "lilun pinglun wenhua --start-date 2020-01-01"),
    "qiushi": ("B_主流媒体", "求是", "python -m tools.collect.download_qiushi_theory qswp shelunpinglun "
               "liwenxuan --start-date 2020-01-01"),
    "banyuetan": ("B_主流媒体", "半月谈", "python -m tools.collect.download_banyuetan_articles "
                  "--all-prefixes --start-date 2020-01-01"),
    "jingjiwang": ("B_主流媒体", "经济日报", "python -m tools.collect.download_jingjiwang_commentary "
                   "ent --start-date 2020-01-01"),
    "xuexi-shibao": ("B_主流媒体", "学习时报", "python -m tools.collect.download_studytimes_commentary "
                     "llwp llsd sxll whjy --start-date 2020-01-01"),
    "huanqiu": ("B_主流媒体", "环球时报", "python -m tools.collect.download_globaltimes_opinion"),
    "aisixiang": ("D_学术智库", "爱思想", "python -m tools.collect.download_aisixiang_essays"),
    "_primary-sources": ("A0_中央文件", "中央文件（政府工作报告/五年规划/党代会报告/国务院文件）",
                         "python -m tools.collect.download_primary_sources"),
    "_academic": ("D_学术智库", "学术期刊", "—"),
    "_web": ("A1_部委发布", "网页快照", "—"),
    "rss": ("B_主流媒体", "RSS 聚合", "python -m tools.collect.download_rss_feeds"),
    "wechat": ("B_主流媒体", "微信公众号", "python -m tools.collect.download_wechat_articles"),
    "chao-news": ("B_主流媒体", "潮新闻", "—"),
    "thepaper-pinglun": ("B_主流媒体", "澎湃评论", "—"),
    "bjnews": ("B_主流媒体", "新京报", "—"),
}


def git_status(paths):
    """返回 {相对路径: tracked|untracked|ignored}。"""
    out = {}
    if not paths:
        return out
    try:
        r = subprocess.run(["git", "-C", str(CORPUS_REPO), "ls-files", "-z"],
                           capture_output=True, timeout=120)
        tracked = {p.decode() for p in r.stdout.split(b"\0") if p}
    except Exception:
        tracked = set()
    for rel in paths:
        pre = rel.rstrip("/") + "/"
        out[rel] = sum(1 for t in tracked if t.startswith(pre) and t.endswith(".txt"))
    return out


def scan():
    rows = []
    cn = CORPUS / "articles/cn"
    if not cn.exists():
        sys.exit(f"语料目录不存在: {cn}")

    for d in sorted(cn.iterdir()):
        if not d.is_dir():
            continue
        files = sorted(d.rglob("*.txt"))
        if not files:
            continue
        dates, chars, n = [], 0, 0
        for f in files:
            m = DATE_RE.match(f.name)
            if m:
                dates.append(m.group(0))
            try:
                chars += f.stat().st_size
            except OSError:
                pass
            n += 1
        if d.name.startswith("osint-"):
            layer, name, fetch = "A1_部委发布", d.name[6:], "osint 采集器"
        else:
            layer, name, fetch = SOURCES.get(d.name, ("Z_其他", d.name, "—"))
        rows.append({
            "source": d.name, "name": name, "layer": layer,
            "path": str(d.relative_to(CORPUS_REPO)),
            "files": n, "bytes": chars,
            "date_min": min(dates) if dates else "",
            "date_max": max(dates) if dates else "",
            "fetch": fetch,
        })

    # 其他语料区（不细分源）
    for sub, layer, name in [("articles/western", "B1_英文媒体", "英文语料（Economist/New Yorker/…）"),
                             ("inbox", "B_主流媒体", "2025–2026 精选素材"),
                             ("reference", "Z_登记库", "shenlun-system 登记库（含不可变版本快照）")]:
        d = CORPUS / sub
        if not d.exists():
            continue
        files = list(d.rglob("*.txt"))
        dates = [m.group(0) for f in files if (m := DATE_RE.match(f.name))]
        rows.append({
            "source": sub.replace("articles/", ""), "name": name, "layer": layer,
            "path": str(d.relative_to(CORPUS_REPO)),
            "files": len(files),
            "bytes": sum(f.stat().st_size for f in files if f.exists()),
            "date_min": min(dates) if dates else "",
            "date_max": max(dates) if dates else "",
            "fetch": "—",
        })

    st = git_status([r["path"] for r in rows])
    for r in rows:
        r["tracked"] = st.get(r["path"], 0)
        r["untracked"] = r["files"] - r["tracked"]
    return rows


def write_md(rows, path):
    total_f = sum(r["files"] for r in rows)
    total_b = sum(r["bytes"] for r in rows)
    by_layer = defaultdict(lambda: [0, 0])
    for r in rows:
        by_layer[r["layer"]][0] += r["files"]
        by_layer[r["layer"]][1] += r["bytes"]
    lines = [
        "# 参考资料索引",
        "",
        f"语料本体在 `{CORPUS_REPO}/corpus/`，**不在本仓库**。本文件是它的索引，由 "
        "`analysis/corpus_manifest.py` 生成，保证分析可复现。",
        "",
        f"合计 **{total_f:,} 个文件 / {total_b / 1048576:.0f} MB**。",
        "",
        "## 按层",
        "",
        "| 层 | 文件 | 大小 |",
        "|---|---:|---:|",
    ]
    for k in sorted(by_layer):
        f, b = by_layer[k]
        lines.append(f"| `{k}` | {f:,} | {b / 1048576:.0f} MB |")
    lines += [
        "",
        "## 按源",
        "",
        "| 源 | 层 | 文件 | 大小 | 日期范围 | 已提交 |",
        "|---|---|---:|---:|---|---:|",
    ]
    for r in sorted(rows, key=lambda x: -x["files"]):
        lines.append(
            f"| `{r['source']}` | {r['layer']} | {r['files']:,} | "
            f"{r['bytes'] / 1048576:.1f} MB | {r['date_min'] or '—'} → {r['date_max'] or '—'} | "
            f"{r['tracked']:,}/{r['files']:,} |")
    lines += [
        "",
        "> `western` 大部分被 `.gitignore` 排除（Economist / New Yorker / Wired / Atlantic 为版权保护）；",
        "> `reference` 目录里还有 `.json` / `.html` 快照，不计入上表的 `.txt` 计数。",
        "",
        "## 重抓命令", "", "在 `~/projects/Learn-to-Write` 下执行（`python -m` 是必须的，",
              "直接跑脚本会让 `tools/collect/http.py` 遮蔽标准库 `http`）：", ""]
    for r in sorted(rows, key=lambda x: -x["files"]):
        if r["fetch"] and r["fetch"] != "—":
            lines += [f"**{r['name']}**", "", "```bash", r["fetch"], "```", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写文件")
    args = ap.parse_args()

    rows = scan()
    jpath = HERE / "corpus-manifest.json"
    cpath = HERE / "corpus-manifest.csv"
    mpath = REPO / "CORPUS.md"

    if args.check:
        if not jpath.exists():
            sys.exit("manifest 不存在，先跑一次不带 --check")
        old = json.loads(jpath.read_text(encoding="utf-8"))
        old_map = {r["source"]: r for r in old["sources"]}
        new_map = {r["source"]: r for r in rows}
        diffs = []
        for k in sorted(set(old_map) | set(new_map)):
            a, b = old_map.get(k), new_map.get(k)
            if a is None:
                diffs.append(f"+ {k} ({b['files']} 篇)")
            elif b is None:
                diffs.append(f"- {k}")
            elif a["files"] != b["files"]:
                diffs.append(f"~ {k}: {a['files']} → {b['files']}")
        print("无变化" if not diffs else "变化:\n  " + "\n  ".join(diffs))
        return

    payload = {
        "generated": date.today().isoformat(),
        "corpus_repo": str(CORPUS_REPO),
        "total_files": sum(r["files"] for r in rows),
        "total_bytes": sum(r["bytes"] for r in rows),
        "sources": rows,
    }
    jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(cpath, "w", encoding="utf-8") as f:
        cols = ["source", "name", "layer", "path", "files", "bytes",
                "date_min", "date_max", "tracked", "untracked"]
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join('"' + str(r[c]).replace('"', "'") + '"' for c in cols) + "\n")
    write_md(rows, mpath)
    print(f"{len(rows)} sources, {payload['total_files']:,} files, "
          f"{payload['total_bytes'] / 1048576:.0f} MB")
    print(f"  -> {jpath.name}, {cpath.name}, {mpath.relative_to(REPO)}")


if __name__ == "__main__":
    main()
