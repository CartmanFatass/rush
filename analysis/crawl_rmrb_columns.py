#!/usr/bin/env python3
"""人民日报数字报 2023-01 → 2024-11 版面栏目回填。

为什么需要这个脚本：`tools/collect/download_renmin_commentary.py` 走的是
opinion.people.com.cn 的栏目索引，覆盖 人民时评/人民论坛/评论员/社论/任仲平
等，但**不覆盖版面栏目**（深阅读、评论员观察、人民观点、记者调查…）；
`osint` 的 `parse_people_daily_layout` 只认新版 `/rmrb/pc/` 路径，而
2023-01 → 2024-11 只有旧版 `/rmrb/html/YYYY-MM/DD/` 路径。

所以这里只补两块上游没有的东西：旧版版面页的链接解析 + 按日循环。
正文抽取直接复用 osint 的 `extract_body`（adapter_text 优先的 R1 链），
不另写抽取器。

用法：
    python3 crawl_rmrb_columns.py 2023-01-01 2024-11-30
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
OUT = Path("/home/fires/projects/Learn-to-Write/corpus/articles/cn/renmin-ribao")
PAGES = ("04", "05", "06", "07", "09", "13")

# 版面栏目 -> 目录名（不含 opinion 频道已覆盖的人民时评/人民论坛/评论员/社论/任仲平）
COLUMNS = [
    ("深阅读", "deep-reading"),
    ("评论员观察", "pinglunyuan-guancha"),
    ("人民观点", "renminguandian"),
    ("现场评论", "xianchang"),
    ("暖闻热评", "nuanwen"),
    ("纵横", "zongheng"),
    ("微观", "weiguan"),
    ("大家谈", "dajiatan"),
    ("记者调查", "jizhediaocha"),
    ("人民要论", "renminyaolun"),
    ("思想纵横", "sixiangzongheng"),
    ("有的放矢", "youdifangshi"),
    ("新知新觉", "xinzhi"),
    ("来论", "lailun"),
    ("今日谈", "jinritan"),
    ("人民论坛", "renminluntan-ban"),   # 版面版，与 opinion 频道互补
]
COL_RE = re.compile("|".join(f"（[^）]*{re.escape(c)}[^）]*）" for c, _ in COLUMNS))
ART_RE = re.compile(r'href=["\']?(nw\.D110000renmrb_[\d_\-]+\.htm)["\']?[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,80})')
BODY_RE = re.compile(r'id="articleContent">(.*?)</div>', re.S)


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": "http://paper.people.com.cn/rmrb/paperindex.htm",
            })
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def col_of(title):
    m = COL_RE.search(title)
    if not m:
        return None
    tag = m.group(0)
    for c, d in COLUMNS:
        if c in tag:
            return d
    return None


def adapter_text(html):
    m = BODY_RE.search(html)
    if not m:
        return None
    t = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    t = re.sub(r"<p[^>]*>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("\u3000", " ").replace("&nbsp;", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def do_day(d: date):
    ds, saved, tried = d.strftime("%Y-%m/%d"), 0, 0
    base = f"http://paper.people.com.cn/rmrb/html/{ds}"
    idx = fetch(f"{base}/nbs.D110000renmrb_01.htm")
    if not idx:
        return 0, 0
    have = set(re.findall(r'nbs\.D110000renmrb_(\d+)\.htm', idx))
    for pg in PAGES:
        if pg not in have:
            continue
        ph = fetch(f"{base}/nbs.D110000renmrb_{pg}.htm")
        if not ph:
            continue
        time.sleep(0.05 + random.random() * 0.1)
        for href, title in ART_RE.findall(ph):
            title = re.sub(r"\s+", " ", title).strip()
            col = col_of(title)
            if not col:
                continue
            tried += 1
            safe = re.sub(r'[\\/:*?"<>|]', "_", title)[:60]
            path = OUT / col / f"{d.isoformat()}_{safe}.txt"
            if path.exists():
                saved += 1
                continue
            url = f"{base}/{href}"
            art = fetch(url)
            if not art:
                continue
            body = extract_body(art, adapter_text=adapter_text(art),
                                min_chars=200, limit=20000).text
            if not body or len(body) < 200:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{title}\n人民日报·{col} · {d.isoformat()} · {url}\n\n{body}\n",
                            encoding="utf-8")
            saved += 1
            time.sleep(0.05 + random.random() * 0.1)
    return saved, tried


def main():
    a = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2023, 1, 1)
    b = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2024, 11, 30)
    days = [a + timedelta(days=i) for i in range((b - a).days + 1)]
    print(f"{a} .. {b} ({len(days)} days)", flush=True)
    tot_s = tot_t = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(do_day, d): d for d in days}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                s, t = f.result()
            except Exception as e:
                s, t = 0, 0
                print("ERR", futs[f], e, flush=True)
            tot_s += s
            tot_t += t
            if i % 25 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(days)} saved={tot_s} tried={tot_t} "
                      f"{el:.0f}s ({i/el*60:.1f} day/min)", flush=True)
    print(f"DONE saved={tot_s} tried={tot_t} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
