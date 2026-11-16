#!/usr/bin/env python3
"""Build a unified document index from the three repos.

Sources
-------
A. 官方文件层  : corpus/reference/shenlun-system/manifest.json (channel=policy)
                + corpus/articles/cn/osint-*  (部委/官网发布)
B. 主流媒体层  : corpus/articles/cn/{renmin-ribao,guangming,banyuetan,...}
C. 地方实践层  : corpus/articles/cn/local-gov-leaders
D. 学术/智库层 : corpus/articles/cn/{_academic,aisixiang,osint-cass_news,osint-drc_news,...}

Output: analysis/out/index.jsonl
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROOT = Path("/home/fires/projects/Learn-to-Write")
OUT = HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

# ---- layer classification -------------------------------------------------
MINISTRY = {
    "osint-ndrc_news", "osint-mof_news", "osint-miit_news", "osint-pbc_news",
    "osint-cac_news", "osint-sasac_news", "osint-stats_nbs", "osint-csrc_news",
    "osint-mofcom_news", "osint-mfa_presser", "osint-nea_news", "osint-safe_news",
    "osint-drc_news", "osint-cass_news", "osint-stcn_news", "osint-people_daily",
    "osint-gmw", "osint-economic_daily", "osint-21jingji_news", "osint-yicai_news",
    "_primary-sources", "_web",
}
MEDIA = {
    "renmin-ribao", "guangming", "banyuetan", "liaowang", "jingjiwang",
    "huanqiu", "qiushi", "xuexi-shibao", "chao-news", "rss", "wechat",
    "thepaper-pinglun", "bjnews", "qiushi-english-edition",
}
LOCAL = {"local-gov-leaders", "local-papers"}
ACADEMIC = {"_academic", "aisixiang"}


def sublayer_of(src: str, path: str) -> str:
    if "_primary-sources" in path:
        return "A0_中央文件"
    if src.startswith("osint-") or src in {"_web"}:
        return "A1_部委发布"
    if src == "local-papers":
        return "C1_地方党报"
    if src in LOCAL:
        return "C_地方实践"
    if src in ACADEMIC:
        return "D_学术智库"
    if src in MEDIA:
        return "B_主流媒体"
    return "Z_其他"


def layer_of(src: str) -> str:
    if src in MINISTRY:
        return "A_官方发布"
    if src in MEDIA:
        return "B_主流媒体"
    if src == "local-papers":
        return "C1_地方党报"
    if src in LOCAL:
        return "C_地方实践"
    if src in ACADEMIC:
        return "D_学术智库"
    return "Z_其他"


def read_text(p: Path, limit: int = 20000) -> str:
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return t[:limit]


def parse_header(text: str):
    """Return (title, outlet, date) from the 3-line header used by the corpus."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else ""
    outlet, date = "", ""
    for l in lines[:4]:
        if "·" in l:
            parts = [x.strip() for x in l.split("·")]
            if len(parts) >= 2:
                outlet = parts[0]
                m = DATE_RE.search(l)
                if m:
                    date = m.group(0)
            break
    return title, outlet, date


def main():
    rows = []
    seen = set()

    # ---- A/B/C/D: corpus/articles/cn --------------------------------------
    cn = ROOT / "corpus/articles/cn"
    for p in sorted(cn.rglob("*.txt")):
        rel = p.relative_to(cn)
        src = rel.parts[0]
        text = read_text(p)
        if not text.strip():
            continue
        title, outlet, hdate = parse_header(text)
        m = DATE_RE.match(p.name)
        date = m.group(0) if m else hdate
        if not date:
            continue
        rows.append({
            "id": f"cn:{rel}",
            "corpus": "learn-to-write/cn",
            "layer": layer_of(src),
            "sublayer": sublayer_of(src, str(p)),
            "source": src,
            "outlet": outlet or src,
            "date": date,
            "title": title[:120],
            "path": str(p.relative_to(ROOT)),
            "chars": len(text),
            "text": text,
        })
        seen.add(p.name)

    # ---- corpus/inbox/2025-2026 -------------------------------------------
    inbox = ROOT / "corpus/inbox/2025-2026"
    for p in sorted(inbox.rglob("*.txt")):
        rel = p.relative_to(inbox)
        src = rel.parts[1] if len(rel.parts) > 1 else rel.parts[0]
        text = read_text(p)
        if not text.strip():
            continue
        title, outlet, hdate = parse_header(text)
        m = DATE_RE.match(p.name)
        date = m.group(0) if m else hdate
        if not date:
            continue
        rows.append({
            "id": f"inbox:{rel}",
            "corpus": "learn-to-write/inbox",
            "layer": layer_of(src),
            "sublayer": sublayer_of(src, str(p)),
            "source": src,
            "outlet": outlet or src,
            "date": date,
            "title": title[:120],
            "path": str(p.relative_to(ROOT)),
            "chars": len(text),
            "text": text,
        })

    # ---- registered reference resources (policy / theory / commentary) -----
    man = ROOT / "corpus/reference/shenlun-system/manifest.json"
    if man.exists():
        docs = json.loads(man.read_text())["documents"]
        for d in docs:
            path = d.get("path") or ""
            # only the 15 reference nodes; the other 2048 already came from cn/
            if not path.startswith("corpus/reference/"):
                continue
            p = ROOT / path
            if not p.exists():
                continue
            text = read_text(p, limit=80000)
            ch = d.get("channel") or "unknown"
            layer = {"policy": "A_官方发布", "theory": "D_学术智库",
                     "commentary": "B_主流媒体", "reporting": "B_主流媒体"}.get(ch, "Z_其他")
            rows.append({
                "id": f"ref:{d.get('resource_id')}",
                "corpus": "learn-to-write/reference",
                "layer": layer,
                "sublayer": "A0_中央文件" if ch == "policy" else layer,
                "source": f"ref-{ch}",
                "outlet": d.get("capture_source_label") or ch,
                "date": d.get("date") or d.get("publication_date") or "",
                "title": (d.get("title") or d.get("title_or_first_line") or "")[:120],
                "path": path,
                "chars": len(text),
                "text": text,
            })

    # ---- write -------------------------------------------------------------
    with open(OUT / "index.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # summary
    from collections import Counter
    print(f"indexed {len(rows)} docs -> {OUT/'index.jsonl'}")
    for k in ("layer", "source"):
        c = Counter(r[k] for r in rows)
        print(f"  by {k}:")
        for name, n in c.most_common():
            print(f"    {name:24s} {n:5d}")
    dated = [r["date"] for r in rows if r["date"]]
    print(f"  dated {len(dated)}  {min(dated)} .. {max(dated)}")
    bym = Counter(d[:7] for d in dated)
    print("  by month:", " ".join(f"{k}:{v}" for k, v in sorted(bym.items())))


if __name__ == "__main__":
    main()
