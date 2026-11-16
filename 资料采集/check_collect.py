#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 资料采集/ 下各任务目录的 JSONL：能否解析、日期和 URL 的格式、逐字状态，
以及 A 级引文能否在该目录 raw/ 的原文里逐字找到。

用法：python3 资料采集/check_collect.py [目录 ...]   不带参数时检查 资料采集/ 下全部任务目录。
只报问题，不改文件。
"""
import json, re, sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
SKIP = {'prompts', '00-本地挖掘'}
DATE_OK = re.compile(r'^\d{4}(-\d{2}){0,2}$')
DATE_KEYS = {'日期', '发表日', '出刊日期', '首次发表日期', '通报日期', '笔试日期', '旧日期', '新日期',
             '审议日期', '公开印发日期', '依据发布日期', '发布日期', '文件日期'}
QUOTE_KEYS = {'原句', '官方原句', '各项原文', '展开句', '做法小标题', '每条做法的首句', '定性句', '启示句',
              '官方概括的要义', '旧提法原文', '新提法原文', '核心要求', '定性用语', '整改要求用语',
              '官方概括摘录', '成效表述', '问题标题', '官方强调的边界'}
EMPTY = {'', '不详', '未找到', '无'}

def norm(s):
    s = re.sub(r'\s+', '', s)
    return s.translate(str.maketrans('“”‘’「」『』', '""\'\'""""'))

def walk(o, key=''):
    """逐个产出 (键, 值)；数组里的字符串沿用数组的键。"""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, key)
    else:
        yield key, o

def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)

def check_dir(d):
    raw = ''
    rawdir = d / 'raw'
    if rawdir.is_dir():
        raw = norm(''.join(p.read_text(encoding='utf-8', errors='ignore') for p in sorted(rawdir.rglob('*.txt'))))
    problems = 0
    for f in sorted(d.rglob('*.jsonl')):
        rows, bad = 0, []
        status = Counter()
        no_url = 0
        for n, line in enumerate(f.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                bad.append(f'第{n}行不是合法 JSON：{e}')
                continue
            rows += 1
            has_url = False
            for k, v in walk(rec):
                if not isinstance(v, str):
                    continue
                if 'URL' in k:
                    if v.startswith('http'):
                        has_url = True
                    elif v not in EMPTY:
                        bad.append(f'第{n}行 {k} 不是网址：{v[:40]}')
                elif k in DATE_KEYS and v not in EMPTY and not DATE_OK.match(v.split('（')[0].strip()):
                    bad.append(f'第{n}行 {k} 日期格式不对：{v[:30]}')
            if not has_url:
                no_url += 1
            st = rec.get('逐字状态', '')
            if isinstance(st, str):
                st = st.strip()[:1]
                status[st or '空'] += 1
                if st and st not in 'ABC':
                    bad.append(f'第{n}行 逐字状态应为 A/B/C：{rec.get("逐字状态")}')
                if st == 'A':
                    if not raw:
                        bad.append(f'第{n}行 标了 A，但 {d.name}/raw/ 里没有原文')
                    else:
                        for k in QUOTE_KEYS & set(rec):
                            for q in strings(rec[k]):
                                q2 = norm(q).strip('"\'。；，')
                                if len(q2) >= 6 and q2 not in raw:
                                    bad.append(f'第{n}行 {k} 在 raw/ 里找不到：{q[:30]}…')
        print(f'{f.relative_to(HERE)}：{rows} 条；逐字状态 {dict(status)}；没有任何网址的记录 {no_url} 条；问题 {len(bad)} 处')
        for b in bad[:30]:
            print('   -', b)
        if len(bad) > 30:
            print(f'   ……还有 {len(bad) - 30} 处')
        problems += len(bad)
    return problems

def main():
    dirs = [Path(a) for a in sys.argv[1:]] or [p for p in sorted(HERE.iterdir()) if p.is_dir() and p.name not in SKIP]
    total = sum(check_dir(d.resolve()) for d in dirs)
    print(f'\n合计 {total} 处问题')
    sys.exit(1 if total else 0)

if __name__ == '__main__':
    main()
