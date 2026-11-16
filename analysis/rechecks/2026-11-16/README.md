# 2026-11-16 统计复核证据

当前结论见[复核报告](../../REPORT.md)。本目录记录研究修正，不记录个人学习进度。

- `REPORT-v3-historical.md`：修正前报告原字节存档，结论已由当前报告逐项修订，不能作为现行教学依据。
- `baseline-manifest.json`：原Git版本及旧索引、报告等哈希。完整本地快照在本次工作目录 `work/rush-recheck-20261116/baseline/`，大索引不提交Git。
- `classification-baseline.json`、`source-reclassification.csv`：固定旧样本的分类对照，与当前增量语料分开。
- `statistics.json`：输入哈希、范围、分组密度、检索候选与限制。
- `exam-inventory.csv`、`question-inventory.csv`：逐卷逐题依据及题本哈希，不是官方评分答案。
- `political-appearances.csv`：124个题位及qid，去重74题，各卷型各62题，共用题保留出处。
- `nearest-pre-candidates.csv`：每则材料的考前相似候选，分数不代表出处真实性。
- `topics-by-year-and-paper.csv`：按年份和卷型统计的关键词命中，不能代替题意判断或分布预测。

复现命令见当前报告。重新采集会改变输入；旧结果需同一原文快照。原题、机构答案与原文摘录未改写。
