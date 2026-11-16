#!/usr/bin/env python3
"""地方党报数字报回填（方正 node_N.htm + content_*.htm 平台）。

探源结论（见 out/local_papers_probe.csv）：省级党报数字报在 2020 年前后大面积改版成
SPA/APP，2020 年存档仍可读的只有少数几家还在跑方正老平台。本脚本覆盖已确认的 4 家：

    河南日报  2020-01 起   https://newpaper.dahe.cn/hnrb
    青岛日报  2020-01 起   http://epaper.qingdaonews.com/qdrb
    太原日报  2021-01 起   http://epaper.tyrbw.com/tyrb
    湖南日报  2021-01 起   https://hnrb.voc.com.cn/hnrb_epaper

策略：按日取 node_1.htm 的版面导航，只抓「评论/理论/要闻/观察/深度/民生/社会」版面，
再抓这些版面里的文章正文。正文抽取复用 osint 的 extract_body（adapter_text 优先）。

用法：
    python3 crawl_local_papers.py 2023-05-01 2023-05-10 henandaily
    python3 crawl_local_papers.py 2020-01-01 2024-12-31 all
"""
import re
import sys
import time
import random
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "/home/fires")
from osint.collect.core.body_extract import extract_body  # noqa: E402

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OUT = Path("/home/fires/projects/Learn-to-Write/corpus/articles/cn/local-papers")

SOURCES = {
    "henandaily": {
        "name": "河南日报", "province": "河南",
        "base": "https://newpaper.dahe.cn/hnrb",
        "start": "2020-01-01",
        "art_re": r'content_\d+_\d+\.htm',
        "body_sel": ("ozoom", "content", "articleContent"),
    },
    "qingdaodaily": {
        "name": "青岛日报", "province": "山东",
        "base": "http://epaper.qingdaonews.com/qdrb",
        "start": "2020-01-01",
        "art_re": r'content_\d+_\d+\.htm',
        "body_sel": ("ozoom", "content", "articleContent"),
    },
    "taiyuandaily": {
        "name": "太原日报", "province": "山西",
        "base": "http://epaper.tyrbw.com/tyrb",
        "start": "2021-01-01",
        "art_re": r'content_\d+_\d+\.htm',
        "body_sel": ("ozoom", "content", "articleContent"),
    },
    "hunandaily": {
        "name": "湖南日报", "province": "湖南",
        "base": "https://hnrb.voc.com.cn/hnrb_epaper",
        "start": "2021-01-01",
        "art_re": r'content_\d+\.htm',
        "body_sel": ("ozoom", "content", "articleContent", "article"),
        "node_1_only": True,
    },
}

# 只抓这些版面（申论材料最相关的版面）
KEEP = re.compile(r"评论|理论|观察|深度|调查|视点|论坛|新论")
NAV_RE = re.compile(r'node_(\d+)\.htm[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,30})')


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": url.rsplit("/", 1)[0] + "/",
            })
            with urllib.request.urlopen(req, timeout=25) as r:
                enc = r.headers.get_content_charset() or "utf-8"
                return r.read().decode(enc, "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            time.sleep(1.2 * (i + 1))
        except Exception:
            time.sleep(1.2 * (i + 1))
    return None


def adapter_text(html, sels):
    for sel in sels:
        m = re.search(rf'id="{sel}"[^>]*>(.*?)</div>', html, re.S)
        if not m:
            m = re.search(rf'class="{sel}"[^>]*>(.*?)</div>', html, re.S)
        if m:
            t = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
            t = re.sub(r"<p[^>]*>", "\n", t)
            t = re.sub(r"<[^>]+>", "", t)
            t = t.replace("\u3000", " ").replace("&nbsp;", " ")
            t = re.sub(r"[ \t]+", " ", t)
            t = re.sub(r"\n{2,}", "\n", t).strip()
            if len(t) > 150:
                return t
    return None


def do_day(key, d):
    cfg = SOURCES[key]
    ds = d.strftime("%Y-%m/%d")
    base = f"{cfg['base']}/html/{ds}"
    saved = tried = 0
    idx = fetch(f"{base}/node_1.htm")
    if not idx:
        return 0, 0
    if cfg.get("node_1_only"):
        pages = [("1", "头版")]
    else:
        nav = NAV_RE.findall(idx)
        pages = [(n, t.strip()) for n, t in nav if KEEP.search(t)]
    # 去重（导航里同一 node 可能重复出现）
    seen, uniq = set(), []
    for n, t in pages:
        if n not in seen:
            seen.add(n)
            uniq.append((n, t))
    for node, title in uniq[:6]:
        ph = fetch(f"{base}/node_{node}.htm")
        if not ph:
            continue
        time.sleep(0.03 + random.random() * 0.06)
        art_pat = (r'<a[^>]+href=["\']?([^"\'>\s]*' + cfg["art_re"] +
                   r'[^"\'>\s]*)["\']?[^>]*>(.*?)</a>')
        arts = re.findall(art_pat, ph, re.S)
        if not arts:
            # 图片版（<Area href=...>）没有锚文本，先收链接，标题从文章页取
            hrefs = re.findall(r'href=["\']?([^"\'>\s]*' + cfg["art_re"] +
                               r'[^"\'>\s]*)', ph)
            arts = [(h, "") for h in dict.fromkeys(hrefs)]
        for href, atitle in arts:
            atitle = re.sub(r"<[^>]+>", "", atitle).strip().strip('"')
            if atitle and (len(atitle) < 4 or "版：" in atitle or "版:" in atitle):
                continue
            tried += 1
            safe = re.sub(r'[\\/:*?"<>|]', "_", atitle)[:60]
            path = OUT / key / f"{d.isoformat()}_{safe}.txt"
            if path.exists():
                saved += 1
                continue
            art = fetch(f"{base}/{href}")
            if not art:
                continue
            body = extract_body(art, adapter_text=adapter_text(art, cfg["body_sel"]),
                                min_chars=150, limit=20000).text
            if not body or len(body) < 150:
                continue
            if not atitle:
                mt = re.search(r"<title>(.*?)</title>", art, re.S)
                atitle = re.sub(r"<[^>]+>", "", mt.group(1)).strip() if mt else href
                atitle = re.sub(r"[-—]{2,}.*$", "", atitle)
                atitle = re.sub(r"数字报[刊]?$", "", atitle).strip() or href
                safe = re.sub(r'[\\/:*?"<>|]', "_", atitle)[:60]
                path = OUT / key / f"{d.isoformat()}_{safe}.txt"
                if path.exists():
                    saved += 1
                    continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"{atitle}\n{cfg['name']}·{title} · {d.isoformat()} · {base}/{href}\n\n{body}\n",
                encoding="utf-8")
            saved += 1
            time.sleep(0.03 + random.random() * 0.06)
    return saved, tried


def main():
    a = date.fromisoformat(sys.argv[1])
    b = date.fromisoformat(sys.argv[2])
    which = sys.argv[3] if len(sys.argv) > 3 else "all"
    keys = list(SOURCES) if which == "all" else [which]
    days = [a + timedelta(days=i) for i in range((b - a).days + 1)]
    print(f"{a} .. {b} ({len(days)} days) sources={keys}", flush=True)
    tot_s = tot_t = 0
    t0 = time.time()
    jobs = [(k, d) for k in keys for d in days
            if d.isoformat() >= SOURCES[k]["start"]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(do_day, k, d): (k, d) for k, d in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                s, t = f.result()
            except Exception as e:
                s, t = 0, 0
                print("ERR", futs[f], e, flush=True)
            tot_s += s
            tot_t += t
            if i % 100 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(jobs)} saved={tot_s} tried={tot_t} "
                      f"{el:.0f}s ({i/el*60:.0f} day/min)", flush=True)
    print(f"DONE saved={tot_s} tried={tot_t} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
