#!/usr/bin/env python3
"""离线复算目录频次、实际笔试日前阅读清单和已核断言；只用标准库。

根目录运行：python3 资料研究/scripts/frequency_review.py
不联网、不运行旧研究脚本、不修改原始数据。输出仅在资料研究/统计。
标题命中、旧依据字段候选、经原文核对的断言分别计数，均不作得分预测。
"""
import argparse
import ast
import calendar
import csv
import datetime as dt
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '资料研究'
SOURCES = ROOT / '资料采集'
QPATH = SOURCES / '03-关系对与方法论/求是署名文章目录.jsonl'
SPATH = SOURCES / '03-关系对与方法论/政治局集体学习目录.jsonl'
PPATH = SOURCES / '09-省考时政溯源/省考时政题溯源.jsonl'
CPATH = SOURCES / '07-议程日历/年度政治日历.jsonl'
EPATH = BASE / '数据/时政命题示例.jsonl'
TPATH = Path(__file__).with_name('frequency_topics.json')
LABELPATH = ROOT / 'analysis/source_lag.py'
QRE = re.compile(r'^## 第 (\d+) 题　<sub>qid (\d+) · ([^<]*)</sub>', re.M)
INPUTS = set()


def read_text(path):
    INPUTS.add(path)
    return path.read_text(encoding='utf-8')


def read_jsonl(path):
    return [json.loads(line) for line in read_text(path).splitlines() if line.strip()]


def norm(text):
    return re.sub(r'\s+', '', text).translate(str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"}))


def title_norm(text):
    return re.sub(r'[^\w\u3400-\u9fff]', '', text)


def date(value):
    return dt.date.fromisoformat(value)


def before_months(day, n):
    month = day.year * 12 + day.month - 1 - n
    year, m = divmod(month, 12)
    return dt.date(year, m + 1, min(day.day, calendar.monthrange(year, m + 1)[1]))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def constants():
    # 只读字面量，避免导入旧脚本及触发其依赖或写操作。
    result = {}
    tree = ast.parse(read_text(LABELPATH))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('EXAM', 'LABELS'):
                result[name] = ast.literal_eval(node.value)
    return result


def parse_national(labels, exam_dates):
    records, by_id, legacy_order, legacy_seen = [], {}, [], set()
    paths = sorted((ROOT / '_build/md').glob('01-政治理论__202[2-6]年*.md'))
    paths = [p for p in paths if '国家' in p.name and '行政' not in p.name and ('地市级' in p.name or '副省级' in p.name)]
    if len(paths) != 10:
        raise ValueError(f'须有现有仓库10份市地/副省政治理论文件，实际{len(paths)}份')
    for path in paths:
        year = int(re.search(r'(\d{4})年', path.name).group(1))
        paper = '地市级' if '地市级' in path.name else '副省级'
        parts = QRE.split(read_text(path))
        for i in range(1, len(parts) - 3, 4):
            n, qid, tag, body = parts[i:i + 4]
            stem = re.split(r'\n-\s*\*\*A\*\*', body)[0].strip()
            key = (year, qid)
            if key not in by_id:
                row = {'year': year, 'qid': qid, 'stem': stem, 'body': body, 'appearances': [], 'exam_date': exam_dates[year]}
                by_id[key] = row
                records.append(row)
            by_id[key]['appearances'].append({'paper': paper, 'n': int(n), 'file': str(path.relative_to(ROOT))})
            old_key = (year, re.sub(r'\s', '', stem)[:60])
            if old_key not in legacy_seen:
                legacy_order.append(key)
                legacy_seen.add(old_key)
    if len(records) != 74 or len(legacy_order) != len(labels):
        raise ValueError('固定旧依据标注与74题清单不再对应；需人工重建映射，不能静默套序号')
    for idx, key in enumerate(legacy_order):
        category, old_date, name = labels[idx]
        by_id[key].update(legacy_index=idx, old_type=category, old_date=old_date, old_source=name)
    return records


def topic_hits(title, rules):
    return {topic: [term for term in terms if term in title] for topic, terms in rules.items() if any(term in title for term in terms)}


def documents(qiushi, study, rules):
    docs = []
    for row in qiushi:
        match = re.search(r'网页发布时间\s*(\d{4}-\d{2}-\d{2})', row.get('备注', ''))
        pub = match.group(1) if match else ''
        docs.append({'id': f"QS_{row['年份']}_{row['期次']:02d}", 'source': '求是署名文章', 'year': row['年份'], 'ordinal': row['期次'],
                     'title': row['标题'], 'period_date': row['出刊日期'], 'public_date': pub,
                     'date_basis': '目录备注的网页发布时间' if pub else '刊期代公开日期，未独立认证',
                     'usable_date': pub or row['出刊日期'], 'event_date': row.get('原讲话日期', ''),
                     'event_context': row.get('原场合与日期', ''), 'url': row['URL'], 'topics': topic_hits(row['标题'], rules)})
    for row in study:
        if not row.get('通稿URL'):
            continue  # 空记录在覆盖表中列出，不当“零主题”的有效文档。
        docs.append({'id': f"STUDY_{row['届次']}_{row['序次']}", 'source': '政治局集体学习', 'year': int(row['日期'][:4]), 'ordinal': row['序次'],
                     'title': row['主题'], 'period_date': row['日期'], 'public_date': row.get('通稿发表日期', ''),
                     'date_basis': '目录通稿发表日期', 'usable_date': row.get('通稿发表日期', ''), 'event_date': row['日期'],
                     'event_context': row.get('通稿标题', ''), 'url': row['通稿URL'], 'topics': topic_hits(row['主题'], rules)})
    return docs


def coverage(qiushi, study, calendar_rows, as_of):
    result = []
    for year in range(2019, as_of.year + 1):
        expected = 24 if year < as_of.year else (as_of.month - 1) * 2 + (1 if as_of.day < 16 else 2)
        rows = [q for q in qiushi if q['年份'] == year]
        seen = [q['期次'] for q in rows]
        result.append({'来源': '求是每期署名文章', '年份或届次': year, '应有序位': expected, '记录': len(rows), '实质条目': len(rows),
                       '缺号': sorted(set(range(1, expected + 1)) - set(seen)), '重复号': [k for k, v in Counter(seen).items() if v > 1],
                       '范围': f'{year}年1期至{expected}期', '统计性质': '期次连续；不代表求是全部文章或全部官方议程'})
    for term in dict.fromkeys(s['届次'] for s in study):
        rows = [s for s in study if s['届次'] == term]
        ordinals = [s['序次'] for s in rows]
        result.append({'来源': '政治局集体学习', '年份或届次': term, '应有序位': max(ordinals) - min(ordinals) + 1, '记录': len(rows),
                       '实质条目': sum(bool(s.get('通稿URL')) for s in rows), '缺号': sorted(set(range(min(ordinals), max(ordinals) + 1)) - set(ordinals)),
                       '空占位': [s['序次'] for s in rows if not s.get('通稿URL')], '范围': f'{min(ordinals)}—{max(ordinals)}次',
                       '统计性质': '仅此序次范围；空占位不当零频次，不据未检出断定没开会'})
    for year, n in sorted(Counter(c['年份'] for c in calendar_rows).items()):
        result.append({'来源': '年度政治日历', '年份或届次': year, '应有序位': '未知', '记录': n, '实质条目': n,
                       '范围': '现有采集条目', '统计性质': '已知缺重要会议；仅盘点数量，不排名议题'})
    return result


def frequency_rows(docs, rules, as_of):
    result = []
    for source in ('求是署名文章', '政治局集体学习'):
        years = sorted({d['year'] for d in docs if d['source'] == source})
        for year in years:
            for scope in ('现有全年/截至当前', f'同期01-01至{as_of:%m-%d}'):
                cutoff = dt.date(year, as_of.month, as_of.day) if scope.startswith('同期') else (as_of if year == as_of.year else dt.date(year, 12, 31))
                rows = [d for d in docs if d['source'] == source and d['year'] == year and date(d['period_date']) <= cutoff]
                counter = Counter(topic for d in rows for topic in d['topics'])
                for topic in list(rules) + ['未命中']:
                    n = sum(not d['topics'] for d in rows) if topic == '未命中' else counter[topic]
                    result.append({'来源': source, '年份': year, '窗口': scope, '截止日': cutoff.isoformat(), '可观察条目': len(rows), '标题标签': topic,
                                   '命中文档数': n, '命中占比': round(n / len(rows), 4) if rows else '',
                                   '范围说明': '非互斥标题词面；比例不可相加。' + ('2019仅10月起，2026仅至现有第27次；另有2空位，不作完整年度强调强度。' if source == '政治局集体学习' else '固定每期署名文章；以刊期对齐。')})
    return result


def source_candidates(name, body, old_date, docs):
    # 精确书名或旧依据字段包含文章全名/长前缀；仅是待核目录关联。
    named = [title_norm(x) for x in re.findall(r'《([^》]+)》', body)]
    short = title_norm(re.sub(r'^《求是》等?[:：]?', '', name))
    result = []
    for d in docs:
        title = title_norm(d['title'])
        how = ''
        if d['source'] == '求是署名文章':
            if title in named:
                how = '题库文本明示同名书名；仍须核对具体引文'
            elif '求是' in name and len(short) >= 8 and (short in title or title in short):
                how = '旧依据字段文章名或长前缀'
        elif '集体学习' in name and old_date and d['event_date'] == old_date:
            how = '旧依据字段集体学习日期'
        if how:
            result.append({'id': d['id'], 'title': d['title'], '公开或暂代日': d['usable_date'], '日期口径': d['date_basis'], '匹配规则': how})
    return result


def lag_row(name, rows, field, gfield):
    values = [float(r[field]) for r in rows if isinstance(r.get(field), (int, float))]
    return {'样本': name, '全部题数': len(rows), '无时效G类': sum(r.get(gfield) == 'G' for r in rows),
            '可计算时差题数': len(values), '未计算题数': len(rows) - len(values), '中位月数': round(statistics.median(values), 1) if values else '',
            '不超过6月': sum(v <= 6 for v in values), '不超过12月': sum(v <= 12 for v in values), '不超过18月': sum(v <= 18 for v in values),
            '超过24月': sum(v > 24 for v in values), '超过24月占有效日期题': round(sum(v > 24 for v in values) / len(values), 4) if values else '',
            '限定': '旧来源日期混有讲话、文件、刊发；复合题取最近日等问题仍在。不是命题提前量。'}


def recompute_province_dates(rows):
    checks = []
    for row in rows:
        original = row.get('依据发布日期', '')
        effective = original + '-15' if re.fullmatch(r'\d{4}-\d{2}', original) else original
        value = round((date(row['笔试日期']) - date(effective)).days / 30.4375, 1) if effective and row['依据类型'] != 'G' else ''
        row['重算距笔试月数'] = value
        previous = row.get('距笔试月数', '')
        checks.append({'编号': row['编号'], '实际笔试日': row['笔试日期'], '原依据日期': original, '计算日期': effective,
                       '日期精度': '月，按15日暂代' if effective != original else ('日' if effective else '无日期'),
                       '依据类型': row['依据类型'], '旧记录月数': previous, '独立重算月数': value, '数字一致': previous == value,
                       '限定': '核算术与日期格式；不认证日期所代表的原讲话/首次公开/重刊身份。'})
    return checks


def validate_examples(examples, national):
    by_id = {(r['year'], r['qid']): r for r in national}
    verified = []
    for row in examples:
        q = by_id[(row['年度'], row['qid'])]
        source_map = {s['id']: s for s in row['原文来源']}
        for i, item in enumerate(row['已核对断言'], 1):
            source = source_map[item['来源ID']]
            text = read_text(ROOT / source['文件'])
            if norm(item['官方原句']) not in norm(text):
                raise ValueError(f"引文不在所标原文：{row['id']}/{i}")
            quoted = item.get('真实设错摘录', item.get('真实正确项摘录', ''))
            if not quoted or norm(quoted) not in norm(q['body']):
                raise ValueError(f"设错/正确项不在原题：{row['id']}/{i}")
            if source['所核文本公开日期'] >= row['实际笔试日']:
                raise ValueError(f"所用文本未早于笔试：{row['id']}/{i}")
            verified.append({'id': row['id'] + '-' + str(i), 'year': row['年度'], 'qid': row['qid'], 'source_id': source['id'],
                             'public_date': source['所核文本公开日期'], 'papers': [a['paper'] for a in q['appearances']],
                             'action': item['辨析动作'], 'quote_verified': True, 'question_verified': True})
    return verified


def replay(docs, national, provincial, verified, exam_dates):
    plans, scores, province_scores, article_matches = [], [], [], []
    match_by_id = {}
    for row in national:
        matches = source_candidates(row['old_source'], row['body'], row['old_date'], docs)
        match_by_id[(row['year'], row['qid'])] = matches
        article_matches.append({'年度': row['year'], 'qid': row['qid'], '卷型与题号': row['appearances'], '实际笔试日': row['exam_date'],
                                '旧标注依据': row['old_source'], '旧日期': row['old_date'], '旧日期类型': '未统一，非首次公开认证',
                                '考前目录候选': [m for m in matches if m['公开或暂代日'] and m['公开或暂代日'] < row['exam_date']],
                                '考后或未知日期候选': [m for m in matches if not m['公开或暂代日'] or m['公开或暂代日'] >= row['exam_date']],
                                '解释': '关联不上也可能在两目录以外/名称不同；关联上不等于整题知识覆盖。'})

    def select(exam_day, capacity):
        lower = before_months(exam_day, 18)
        # 两类来源不混频；清单比较只在每期署名文章这一固定总体内进行。
        pool = [d for d in docs if d['source'] == '求是署名文章' and lower <= date(d['usable_date']) < exam_day]
        recent = sorted(pool, key=lambda d: (d['usable_date'], d['id']), reverse=True)
        counts = Counter(t for d in pool for t in d['topics'])
        ranked = sorted(pool, key=lambda d: (max((counts[t] for t in d['topics']), default=0), d['usable_date'], d['id']), reverse=True)
        keep = (capacity + 1) // 2
        mixed = recent[:keep]
        used = {d['id'] for d in mixed}
        mixed += [d for d in ranked if d['id'] not in used][:max(0, capacity - len(mixed))]
        return pool, {'近期优先': recent[:capacity], '近期一半加标题频次': mixed}

    for year, exam in sorted(exam_dates.items()):
        day = date(exam)
        for cap in (3, 6, 12):
            pool, choices = select(day, cap)
            for name, chosen in choices.items():
                ids = {d['id'] for d in chosen}
                plans.append({'用途': '历史补充阅读清单演示，非预测回测', '年度': year, '实际笔试日': exam, '窗口起点': before_months(day, 18).isoformat(),
                              '候选篇数': len(pool), '候选中刊期代公开日': sum(not d['public_date'] for d in pool), '补充阅读容量': cap, '方案': name,
                              '已选篇数': len(chosen), '篇目': [{'id': d['id'], 'title': d['title'], 'public_date': d['usable_date']} for d in chosen]})
                for paper in ('地市级', '副省级'):
                    questions = [r for r in national if r['year'] == year and any(a['paper'] == paper for a in r['appearances'])]
                    old_candidates = sum(any(m['id'] in ids for m in match_by_id[(r['year'], r['qid'])]) for r in questions)
                    points = [v for v in verified if v['year'] == year and paper in v['papers'] and v['source_id'].startswith('QS_')]
                    available_ids = {d['id'] for d in pool}
                    eligible = [v for v in points if v['source_id'] in available_ids]
                    scores.append({'年度': year, '卷型': paper, '补充阅读容量': cap, '方案': name, '原题题位': len(questions),
                                   '旧标注目录候选相交题数': old_candidates, '已核断言数_此卷型全部QS来源': len(points),
                                   '已核断言数_18月候选内': len(eligible), '清单包含已核断言来源数': sum(v['source_id'] in ids for v in eligible),
                                   '已核断言涉及独立篇目': len({v['source_id'] for v in eligible}),
                                   '清单包含这些独立篇目数': len({v['source_id'] for v in eligible if v['source_id'] in ids}),
                                   '解释': '共用核心文件不参与这组补充席位比较；不是整题知识覆盖/得分，样例事后选取且样本很小。'})

    # 省考保留各自实际笔试批次，独立输出；不混入国考调参或命题概率。
    province_match = {r['编号']: source_candidates(r['依据名称'], '', r.get('依据发布日期', ''), docs) for r in provincial}
    batches = defaultdict(list)
    for r in provincial:
        batches[r['笔试日期']].append(r)
    for exam, rows in sorted(batches.items()):
        for cap in (3, 6, 12):
            pool, choices = select(date(exam), cap)
            for name, chosen in choices.items():
                ids = {d['id'] for d in chosen}
                province_scores.append({'实际笔试日': exam, '该批题数': len(rows), '补充阅读容量': cap, '方案': name,
                                        '候选篇数': len(pool), '旧依据字段可关联的目录题数': sum(any(m['公开或暂代日'] and m['公开或暂代日'] < exam for m in province_match[r['编号']]) for r in rows),
                                        '与清单相交题数': sum(any(m['id'] in ids for m in province_match[r['编号']]) for r in rows),
                                        '解释': '仅未经全部语义验收的旧依据字段关联；不是必要知识覆盖或独立验证的预测效果。'})
    return plans, scores, province_scores, article_matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', default='2026-11-16', help='本版仅接受固定快照日2026-11-16，不是任意日期在线更新器')
    args = parser.parse_args()
    as_of = date(args.as_of)
    if as_of != date('2026-11-16'):
        parser.error('本版固定2026-11-16数据快照；更新日期须先补齐输入覆盖并调整核对说明。')
    out = BASE / '统计'
    out.mkdir(parents=True, exist_ok=True)
    qiushi, study, provincial, cal = map(read_jsonl, (QPATH, SPATH, PPATH, CPATH))
    rules = json.loads(read_text(TPATH))['规则']
    old = constants()
    national = parse_national(old['LABELS'], old['EXAM'])
    docs = documents(qiushi, study, rules)
    examples = read_jsonl(EPATH)
    verified = validate_examples(examples, national)
    province_dates = recompute_province_dates(provincial)
    write_csv(out / '省考日期逐题核对.csv', province_dates)
    write_csv(out / '序列覆盖.csv', coverage(qiushi, study, cal, as_of))
    write_csv(out / '标题主题频率.csv', frequency_rows(docs, rules, as_of))
    write_json(out / '目录逐条标注.json', docs)
    write_csv(out / '标题未命中.csv', [{'id': d['id'], '来源': d['source'], '标题': d['title'], '日期': d['period_date']} for d in docs if not d['topics']])
    repeated = defaultdict(list)
    for d in docs:
        if d['source'] == '求是署名文章' and re.fullmatch(r'\d{4}-\d{2}-\d{2}', d['event_date']):
            repeated[d['event_date']].append(d)
    write_csv(out / '原讲话同日刊发候选.csv', [{'原讲话日期': day, '期次数': len(items), '原场合文本': [d['event_context'] for d in items],
                                                  '篇目': [d['id'] + ' ' + d['title'] for d in items], '解释': '同日不自动等于同一次讲话；须核场合。不作为独立原发计数。'}
                                                 for day, items in sorted(repeated.items()) if len(items) > 1])
    lag_rows = [lag_row('省考全部：旧标注复算', provincial, '重算距笔试月数', '依据类型')]
    for year in sorted({r['年度'] for r in provincial}):
        lag_rows.append(lag_row(f'省考{year}：旧标注复算', [r for r in provincial if r['年度'] == year], '重算距笔试月数', '依据类型'))
    for r in national:
        r['legacy_lag'] = round((date(r['exam_date']) - date(r['old_date'])).days / 30.44, 1) if r['old_date'] else ''
    lag_rows.append(lag_row('国考74题：旧标注复算', national, 'legacy_lag', 'old_type'))
    for year in sorted(old['EXAM']):
        lag_rows.append(lag_row(f'国考{year}：旧标注复算', [r for r in national if r['year'] == year], 'legacy_lag', 'old_type'))
    write_csv(out / '时间窗复算.csv', lag_rows)
    plans, scores, province_scores, matched = replay(docs, national, provincial, verified, old['EXAM'])
    write_csv(out / '国考74题目录历史核对.csv', matched)
    write_csv(out / '历史补充阅读清单.csv', plans)
    write_csv(out / '国考等容量清单比较.csv', scores)
    write_csv(out / '省考独立对照.csv', province_scores)
    write_csv(out / '时政断言核验.csv', verified)
    summary = {'观察截止日': args.as_of, '数据起点commit': '9fa62caabe8bb48e20e2ecf71d2a0177491b32cd',
               '求是期数': len(qiushi), '求是备注有网页公开日': sum(bool(d['public_date']) for d in docs if d['source'] == '求是署名文章'),
               '集体学习记录': len(study), '集体学习实质条目': sum(bool(r.get('通稿URL')) for r in study),
               '集体学习空占位': [{'届次': r['届次'], '序次': r['序次']} for r in study if not r.get('通稿URL')],
               '年度日历记录': len(cal), '年度日历用于议题排名': False,
               '国考题位': sum(len(r['appearances']) for r in national), '国考同年qid去重题': len(national),
               '国考地市题位': sum(a['paper'] == '地市级' for r in national for a in r['appearances']),
               '国考副省题位': sum(a['paper'] == '副省级' for r in national for a in r['appearances']),
               '省考题': len(provincial), '省考G类': sum(r['依据类型'] == 'G' for r in provincial),
               '省考非G缺依据日期': sum(r['依据类型'] != 'G' and not r.get('依据发布日期') for r in provincial),
               '省考有依据URL': sum(bool(r.get('依据URL') or r.get('依据 URL')) for r in provincial),
               '省考空题干摘要': sum(not r.get('题干前60字') for r in provincial),
               '省考时差重算与旧值不一致': sum(not r['数字一致'] for r in province_dates),
               '示例真题': len(examples), '已核断言': len(verified), '已核断言独立来源': len({v['source_id'] for v in verified}),
               '历史比较容量': [3, 6, 12], '历史比较性质': '固定规则的事后清单演示；共用基础文件不纳入补充席位计数。不能确定预测权重。',
               '时间窗': lag_rows,
               '明确限制': ['标题标签不等于全文强调强度；标签非互斥。', '求是按期次计编辑再强调，不以同篇讲话重刊充作独立原讲话。',
                        '17条目录未记网页公开日时以刊期暂代；清单中逐条标明。', '旧依据名称可能只是解析引用，或多来源被压缩；74/419关联表不认证命题出处。',
                        '核验只覆盖10题的16条断言；全部选项、原始网页真实性、未来效果未全面验收。',
                        '国考各卷分别报告，共享题不在合计中重复计样本；省考是另表描述性对照。',
                        '不采用未考加分、已考减分或作文题眼重现推断。']}
    write_json(out / 'summary.json', summary)
    INPUTS.add(Path(__file__).resolve())
    write_json(out / '输入摘要.json', [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(INPUTS)])
    print(json.dumps({k: summary[k] for k in ('求是期数', '集体学习记录', '集体学习实质条目', '国考题位', '国考同年qid去重题', '省考题', '示例真题', '已核断言')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
