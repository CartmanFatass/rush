# 参考资料索引

语料本体在 `/home/fires/projects/Learn-to-Write/corpus/`，**不在本仓库**。本文件是它的索引，由 `analysis/corpus_manifest.py` 生成。它记录本机语料范围；复现历史结果还需要同一原文快照与分析代码。

合计 **29,195 个文件 / 167 MB**。
文件数包含版本快照，不等于去重文章数。层级按已识别的来源目录分类；采集工具前缀不代表发布者身份，目录分类也不认证每篇文章的权威性。

## 按层

| 层 | 文件 | 大小 |
|---|---:|---:|
| `A0_中央文件` | 75 | 2 MB |
| `A1_部委发布` | 355 | 1 MB |
| `B1_英文媒体` | 6,834 | 59 MB |
| `B_主流媒体` | 7,713 | 37 MB |
| `C1_地方党报` | 11,489 | 46 MB |
| `C_地方实践` | 472 | 1 MB |
| `D_学术智库` | 192 | 5 MB |
| `Z_其他` | 3 | 0 MB |
| `Z_登记库` | 2,062 | 14 MB |

## 按源

| 源 | 层 | 文件 | 大小 | 日期范围 | 已跟踪 |
|---|---|---:|---:|---|---:|
| `local-papers` | C1_地方党报 | 11,489 | 46.1 MB | 2020-07-01 → 2024-12-31 | 11,489/11,489 |
| `western` | B1_英文媒体 | 6,834 | 59.3 MB | 2025-08-06 → 2026-10-12 | 321/6,834 |
| `renmin-ribao` | B_主流媒体 | 4,932 | 20.9 MB | 2020-01-02 → 2026-11-16 | 4,932/4,932 |
| `reference` | Z_登记库 | 2,062 | 14.1 MB | — → — | 2,062/2,062 |
| `local-gov-leaders` | C_地方实践 | 472 | 1.4 MB | 2026-01-09 → 2026-07-20 | 472/472 |
| `huanqiu` | B_主流媒体 | 456 | 2.5 MB | 2026-01-04 → 2026-07-19 | 456/456 |
| `inbox` | B_主流媒体 | 382 | 1.8 MB | 2025-01-02 → 2026-09-17 | 382/382 |
| `guangming` | B_主流媒体 | 378 | 2.0 MB | 2021-10-26 → 2026-11-16 | 378/378 |
| `qiushi` | B_主流媒体 | 254 | 1.9 MB | 2024-11-16 → 2026-11-16 | 205/254 |
| `jingjiwang` | B_主流媒体 | 235 | 1.0 MB | 2025-06-23 → 2026-11-16 | 235/235 |
| `liaowang` | B_主流媒体 | 216 | 2.0 MB | 2024-09-18 → 2026-11-10 | 216/216 |
| `banyuetan` | B_主流媒体 | 199 | 0.7 MB | 2026-01-04 → 2026-11-16 | 199/199 |
| `osint-yicai_news` | B_主流媒体 | 156 | 1.1 MB | 2026-08-21 → 2026-10-02 | 0/156 |
| `aisixiang` | D_学术智库 | 131 | 3.9 MB | 2026-05-21 → 2026-07-20 | 131/131 |
| `osint-21jingji_news` | B_主流媒体 | 130 | 0.9 MB | 2026-08-20 → 2026-10-02 | 0/130 |
| `xuexi-shibao` | B_主流媒体 | 113 | 0.9 MB | 2026-05-31 → 2026-11-16 | 113/113 |
| `rss` | B_主流媒体 | 100 | 0.4 MB | 2025-05-24 → 2025-06-05 | 100/100 |
| `_primary-sources` | A0_中央文件 | 75 | 2.1 MB | 2020-05-29 → 2026-11-01 | 40/75 |
| `osint-stcn_news` | B_主流媒体 | 56 | 0.4 MB | 2026-08-21 → 2026-08-31 | 0/56 |
| `osint-ndrc_news` | A1_部委发布 | 49 | 0.1 MB | 2025-12-25 → 2026-08-28 | 0/49 |
| `_academic` | D_学术智库 | 47 | 0.9 MB | 2024-04-02 → 2026-10-06 | 47/47 |
| `osint-mofcom_news` | A1_部委发布 | 43 | 0.1 MB | 2026-07-04 → 2026-08-31 | 0/43 |
| `osint-safe_news` | A1_部委发布 | 40 | 0.2 MB | 2026-04-24 → 2026-08-28 | 0/40 |
| `osint-stats_nbs` | A1_部委发布 | 39 | 0.2 MB | 2026-05-15 → 2026-08-31 | 0/39 |
| `osint-nea_news` | A1_部委发布 | 35 | 0.1 MB | 2025-10-29 → 2026-08-28 | 0/35 |
| `osint-csrc_news` | A1_部委发布 | 30 | 0.1 MB | 2021-11-26 → 2026-08-28 | 0/30 |
| `osint-people_daily` | B_主流媒体 | 30 | 0.3 MB | 2026-08-21 → 2026-10-02 | 0/30 |
| `osint-cac_news` | A1_部委发布 | 27 | 0.2 MB | 2026-07-24 → 2026-08-29 | 0/27 |
| `osint-miit_news` | A1_部委发布 | 27 | 0.1 MB | 2025-03-21 → 2026-08-31 | 0/27 |
| `osint-gmw` | B_主流媒体 | 24 | 0.2 MB | 2026-08-21 → 2026-10-02 | 0/24 |
| `osint-economic_daily` | B_主流媒体 | 20 | 0.2 MB | 2026-08-19 → 2026-09-30 | 0/20 |
| `osint-mfa_presser` | A1_部委发布 | 20 | 0.1 MB | 2026-07-30 → 2026-08-28 | 0/20 |
| `osint-sasac_news` | A1_部委发布 | 20 | 0.1 MB | 2026-07-23 → 2026-09-29 | 0/20 |
| `osint-pbc_news` | A1_部委发布 | 18 | 0.1 MB | 2026-07-31 → 2026-08-28 | 0/18 |
| `wechat` | B_主流媒体 | 18 | 0.1 MB | 2017-05-24 → 2026-07-14 | 18/18 |
| `chao-news` | B_主流媒体 | 8 | 0.1 MB | 2026-09-15 → 2026-09-24 | 8/8 |
| `osint-cass_news` | D_学术智库 | 8 | 0.1 MB | 2026-07-29 → 2026-08-20 | 0/8 |
| `osint-mof_news` | A1_部委发布 | 7 | 0.1 MB | 2026-08-10 → 2026-08-28 | 0/7 |
| `osint-drc_news` | D_学术智库 | 6 | 0.1 MB | 2026-08-21 → 2026-08-31 | 0/6 |
| `_web` | Z_其他 | 3 | 0.0 MB | 2024-11-14 → 2026-10-10 | 0/3 |
| `bjnews` | B_主流媒体 | 3 | 0.0 MB | — → — | 3/3 |
| `thepaper-pinglun` | B_主流媒体 | 3 | 0.0 MB | 2026-10-11 → 2026-10-11 | 3/3 |

> `western` 大部分被 `.gitignore` 排除（Economist / New Yorker / Wired / Atlantic 为版权保护）；
> `reference` 目录里还有 `.json` / `.html` 快照，不计入上表的 `.txt` 计数。

## 重抓命令

在 `~/projects/Learn-to-Write` 下执行（`python -m` 是必须的，
直接跑脚本会让 `tools/collect/http.py` 遮蔽标准库 `http`）：

**地方党报（河南/青岛/太原/湖南）**

```bash
/home/fires/osint/.venv/bin/python ~/projects/rush/analysis/crawl_local_papers.py 2020-07-01 2024-12-31 all
```

**人民日报（评论 7 栏 + 版面栏目 16 个）**

```bash
python -m tools.collect.download_renmin_commentary renminshiping renminluntan pinglunyuan shelun renzhongping renping zhongyin --start-date 2020-01-01 --index-pages 45 --delay 0.3
/home/fires/osint/.venv/bin/python ~/projects/rush/analysis/crawl_rmrb_columns.py 2023-01-01 2024-11-30
```

**地方党政领导活动**

```bash
python -m tools.collect.download_local_gov_leaders
```

**环球时报**

```bash
python -m tools.collect.download_globaltimes_opinion
```

**光明日报**

```bash
python -m tools.collect.download_guangming_commentary lilun pinglun wenhua --start-date 2020-01-01
```

**求是**

```bash
python -m tools.collect.download_qiushi_theory qswp shelunpinglun liwenxuan --start-date 2020-01-01
```

**经济日报**

```bash
python -m tools.collect.download_jingjiwang_commentary ent --start-date 2020-01-01
```

**瞭望**

```bash
python -m tools.collect.download_liaowang_commentary sp2 dyxx zglzjs szcl rgc sz zcjm rdjx tbbd lwft --start-date 2020-01-01
```

**半月谈**

```bash
python -m tools.collect.download_banyuetan_articles --all-prefixes --start-date 2020-01-01
```

**yicai_news**

```bash
osint 采集器
```

**爱思想**

```bash
python -m tools.collect.download_aisixiang_essays
```

**21jingji_news**

```bash
osint 采集器
```

**学习时报**

```bash
python -m tools.collect.download_studytimes_commentary llwp llsd sxll whjy --start-date 2020-01-01
```

**RSS 聚合**

```bash
python -m tools.collect.download_rss_feeds
```

**中央文件（政府工作报告/五年规划/党代会报告/国务院文件）**

```bash
python -m tools.collect.download_primary_sources
```

**stcn_news**

```bash
osint 采集器
```

**ndrc_news**

```bash
osint 采集器
```

**mofcom_news**

```bash
osint 采集器
```

**safe_news**

```bash
osint 采集器
```

**stats_nbs**

```bash
osint 采集器
```

**nea_news**

```bash
osint 采集器
```

**csrc_news**

```bash
osint 采集器
```

**people_daily**

```bash
osint 采集器
```

**cac_news**

```bash
osint 采集器
```

**miit_news**

```bash
osint 采集器
```

**gmw**

```bash
osint 采集器
```

**economic_daily**

```bash
osint 采集器
```

**mfa_presser**

```bash
osint 采集器
```

**sasac_news**

```bash
osint 采集器
```

**pbc_news**

```bash
osint 采集器
```

**微信公众号**

```bash
python -m tools.collect.download_wechat_articles
```

**cass_news**

```bash
osint 采集器
```

**mof_news**

```bash
osint 采集器
```

**drc_news**

```bash
osint 采集器
```

