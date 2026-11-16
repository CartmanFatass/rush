#!/usr/bin/env python3
"""探测省级/副省级党报数字报：可达性、URL 形态、存档深度。

对每家报纸试几套常见的方正/自研数字报路径模板，命中即记录：
  - 命中的 URL 模板
  - 版面页里的文章链接形态
  - 2020-01 / 2022-01 / 2023-01 / 2024-06 四个时间点的可达性（判断存档深度）

输出 analysis/out/local_papers_probe.csv
"""
import csv
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OUT = HERE / "out"
TIMEOUT = 15

# (name, host, path_prefix)  path_prefix 为空表示报纸就在根
PAPERS = [
    ("北京日报", "bjrb.bjd.com.cn", ""),
    ("解放日报", "newspaper.jfdaily.com", "/jfrb"),
    ("南方日报", "epaper.southcn.com", "/nfdaily"),
    ("浙江日报", "zjrb.zjol.com.cn", ""),
    ("新华日报", "xh.xhby.net", ""),
    ("大众日报", "paper.dzwww.com", "/dzrb"),
    ("河南日报", "newpaper.dahe.cn", "/hnrb"),
    ("湖北日报", "hbrb.cnhubei.com", ""),
    ("四川日报", "epaper.scdaily.cn", "/shtml/scrb"),
    ("湖南日报", "hnrb.voc.com.cn", "/hnrb_epaper"),
    ("安徽日报", "epaper.ahnews.com.cn", "/ahrb"),
    ("福建日报", "fjrb.fjdaily.com", ""),
    ("江西日报", "epaper.jxxw.com.cn", ""),
    ("陕西日报", "esb.sxdaily.com.cn", ""),
    ("辽宁日报", "epaper.lnd.com.cn", "/lnrbepaper"),
    ("河北日报", "hbrb.hebnews.cn", ""),
    ("山西日报", "epaper.sxrb.com", "/shtml/sxrb"),
    ("重庆日报", "epaper.cqrb.cn", "/html/cqrb"),
    ("贵州日报", "szb.gog.cn", "/epaper/gzrb"),
    ("云南日报", "yndaily.yunnan.cn", ""),
    ("甘肃日报", "szb.gansudaily.com.cn", "/gsrb"),
    ("天津日报", "epaper.tianjinwe.com", "/tjrb/tjrb"),
    ("广西日报", "gxrb.gxrb.com.cn", ""),
    ("黑龙江日报", "epaper.hljnews.cn", "/hljrb"),
    ("吉林日报", "jlrbszb.cnjiwang.com", "/pc/paper/c"),
    ("内蒙古日报", "szb.northnews.cn", "/nmgrb"),
    ("海南日报", "hnrb.hinews.cn", ""),
    ("宁夏日报", "szb.nxrb.com.cn", "/nxrb"),
    ("青海日报", "epaper.qhnews.com", "/qhrb"),
    ("新疆日报", "szb.xjdaily.com", "/xjrb"),
    ("西藏日报", "epaper.chinatibetnews.com", "/xzrb"),
    ("广州日报", "gzdaily.dayoo.com", ""),
    ("深圳特区报", "sztqb.sznews.com", "/PC"),
    ("长江日报", "cjrb.cjn.cn", ""),
    ("成都日报", "www.cdrb.com.cn", "/epaper/cdrbpc"),
    ("杭州日报", "hzdaily.hangzhou.com.cn", "/hzrb"),
    ("南京日报", "njrb.njdaily.cn", ""),
    ("郑州日报", "zzrb.zynews.cn", ""),
    ("济南日报", "jnrb.e23.cn", ""),
    ("青岛日报", "epaper.qingdaonews.com", "/qingdaoribao"),
    ("宁波日报", "daily.cnnb.com.cn", "/nbrb"),
    ("厦门日报", "epaper.xmnn.cn", "/xmrb"),
]

# 模板：{p}=path_prefix, {y}/{m}/{d}=日期分量
TEMPLATES = {
    "A_html_dash": "{p}/html/{Y}-{M}/{D}/node_01.htm",
    "B_pc_layout": "{p}/pc/layout/{Y}{M}/{D}/node_01.html",
    "C_nbs": "{p}/html/{Y}-{M}/{D}/nbs.D110000renmrb_01.htm",
    "D_flat": "{p}/{Y}{M}/{D}/node_01.html",
    "E_content": "{p}/content/{Y}{M}/{D}/node_01.html",
}

DATES = [("2020", "01", "06"), ("2022", "01", "06"),
         ("2023", "01", "06"), ("2024", "06", "06")]

ART_PATTERNS = [
    r'href=["\']?([\w.\-]*content_\d+\.html?)',
    r'href=["\']?([\w.\-]*\d{8}[\w\-]*\.html?)',
    r'href=["\']?(nw\.D110000[\w_\-]+\.htm)',
    r'href=["\']?([\w.\-]+\.htm)[^>]*>[^<]{6,40}</a>',
]


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            enc = r.headers.get_content_charset() or "utf-8"
            try:
                return r.status, raw.decode(enc, "replace")
            except LookupError:
                return r.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def probe(paper):
    name, host, prefix = paper
    res = {"paper": name, "host": host, "template": "", "status": 0,
           "depth_2020": "", "depth_2022": "", "depth_2023": "", "depth_2024": "",
           "art_pattern": "", "note": ""}
    for tname, tpl in TEMPLATES.items():
        url = "http://" + host + tpl.format(p=prefix, Y="2023", M="01", D="06")
        st, body = get(url)
        if st == 200 and len(body) > 2000:
            res["template"] = tname
            res["status"] = st
            # 存档深度
            for (Y, M, D) in DATES:
                u = "http://" + host + tpl.format(p=prefix, Y=Y, M=M, D=D)
                s2, b2 = get(u)
                res[f"depth_{Y}"] = "ok" if (s2 == 200 and len(b2) > 2000) else str(s2)
            # 文章链接形态
            for ap in ART_PATTERNS:
                m = re.findall(ap, body)
                if m:
                    res["art_pattern"] = ap[:28] + " -> " + m[0]
                    break
            return res
        res["status"] = st or res["status"]
    res["note"] = "no template matched"
    return res


def main():
    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(probe, p): p for p in PAPERS}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                r = f.result()
            except Exception as e:
                r = {"paper": futs[f][0], "host": futs[f][1], "template": "",
                     "status": 0, "depth_2020": "", "depth_2022": "",
                     "depth_2023": "", "depth_2024": "", "art_pattern": "",
                     "note": f"ERR {e}"}
            rows.append(r)
            print(f"[{i}/{len(PAPERS)}] {r['paper']:8s} {r['template'] or '-':12s} "
                  f"2020={r['depth_2020'] or '-':4s} 2022={r['depth_2022'] or '-':4s} "
                  f"2023={r['depth_2023'] or '-':4s} 2024={r['depth_2024'] or '-':4s} "
                  f"{r['art_pattern'][:40]}", flush=True)
    rows.sort(key=lambda r: (r["template"] == "", r["paper"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "local_papers_probe.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r["template"]]
    deep = [r for r in ok if r["depth_2020"] == "ok"]
    print(f"\n可达: {len(ok)}/{len(rows)}   2020 年可回溯: {len(deep)}")
    print("2020 可回溯:", "、".join(r["paper"] for r in deep))


if __name__ == "__main__":
    main()
