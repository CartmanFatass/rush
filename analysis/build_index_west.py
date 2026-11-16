#!/usr/bin/env python3
"""Index the English corpus (corpus/articles/western) -> out/index_west.jsonl.

Same schema as build_index.py so relate.py can consume it. English docs are kept
in a separate index because the char-bigram tokenizer is CJK-oriented.
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROOT = Path("/home/fires/projects/Learn-to-Write")
OUT = HERE / "out"
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

# outlet dir -> (layer, sublayer)
GROUPS = {
    "economist": ("B_主流媒体", "B1_英文媒体"),
    "new-yorker": ("B_主流媒体", "B1_英文媒体"),
    "atlantic": ("B_主流媒体", "B1_英文媒体"),
    "wired": ("B_主流媒体", "B1_英文媒体"),
    "magazine": ("B_主流媒体", "B1_英文媒体"),
    "rss": ("B_主流媒体", "B1_英文媒体"),
    "think-tank": ("D_学术智库", "D1_英文智库"),
    "academic": ("D_学术智库", "D1_英文智库"),
}


def sublayer_of(src: str) -> tuple:
    if src in GROUPS:
        return GROUPS[src]
    if src.startswith("osint-"):
        if any(k in src for k in ("fed", "ecb", "boe", "bis", "ustr", "whitehouse", "eia")):
            return ("A1_部委发布", "A2_英文官方")
        if any(k in src for k in ("ecfr", "piie", "warontherocks", "thediplomat")):
            return ("D_学术智库", "D1_英文智库")
        if any(k in src for k in ("semiengineering", "theregister", "tomshardware")):
            return ("B_主流媒体", "B1_英文媒体")
    return ("Z_其他", "Z_其他")


def main():
    west = ROOT / "corpus/articles/western"
    rows = []
    for p in sorted(west.rglob("*.txt")):
        rel = p.relative_to(west)
        src = rel.parts[0]
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:20000]
        except Exception:
            continue
        if len(text) < 200:
            continue
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        title = lines[0] if lines else ""
        outlet = src
        for l in lines[:4]:
            if "·" in l:
                outlet = l.split("·")[0].strip()
                break
        m = DATE_RE.match(p.name)
        hd = DATE_RE.search("\n".join(lines[:4]))
        date = m.group(0) if m else (hd.group(0) if hd else "")
        if not date:
            continue
        layer, sub = sublayer_of(src)
        rows.append({
            "id": f"west:{rel}", "corpus": "learn-to-write/western",
            "layer": layer, "sublayer": sub, "source": src,
            "outlet": outlet, "date": date, "title": title[:120],
            "path": str(p.relative_to(ROOT)), "chars": len(text), "text": text,
        })
    with open(OUT / "index_west.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"indexed {len(rows)} English docs -> {OUT/'index_west.jsonl'}")
    print("  by source:", Counter(r["source"] for r in rows).most_common(12))
    print("  by sublayer:", Counter(r["sublayer"] for r in rows).most_common())
    d = [r["date"] for r in rows]
    print(f"  dated {len(d)}  {min(d)} .. {max(d)}")


if __name__ == "__main__":
    main()
