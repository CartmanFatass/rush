#!/usr/bin/env python3
"""读取 parse_repo.py 的输出，剔除国考/选调/名校优生/县级纪委卷，按题干去重（同年度内），输出 unique.jsonl。
用法: python3 -I build_unique.py <questions.jsonl> <unique.jsonl>
去重键: 年度 + 题干归一化(去标点空白)全文；之后对同年度内题干相似度>=0.85 的再合并（difflib，仅比较前120字）。
"""
import sys, json, re, collections, difflib
def norm(s): return re.sub(r'[\s\W_]+', '', s)
def excluded(p):
    # 四川省考与选调同卷同日, 保留; 其余选调/名校优生/县级纪委/国考排除
    if '四川省考' in p: return '国家公务员' in p
    return any(k in p for k in ('国家公务员', '选调', '名校优生', '县级纪委'))
qs = [json.loads(l) for l in open(sys.argv[1], encoding='utf8')]
qs = [q for q in qs if not excluded(q['paper'])]
groups = collections.OrderedDict()
for q in qs:
    groups.setdefault((q['year'], q['module'], norm(q['stem'])), []).append(q)
# 近似合并
keys = list(groups.keys())
merged = {}
byym = collections.defaultdict(list)
for k in keys: byym[(k[0], k[1])].append(k)
for ym, ks in byym.items():
    reps = []
    for k in ks:
        hit = None
        for r in reps:
            a, b = k[2][:120], r[2][:120]
            if a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
                hit = r; break
        if hit: merged[hit].extend(groups[k])
        else: reps.append(k); merged[k] = list(groups[k])
out = []
for i, (k, v) in enumerate(sorted(merged.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[1][0]['paper'], kv[1][0]['no'])), 1):
    first = v[0]
    out.append(dict(uid=f"{k[0]}-{'Z' if k[1]=='政治理论' else 'C'}-{i:04d}", year=k[0], module=k[1], tag=first['tag'],
        stem=first['stem'], options=first['options'], answer=first['answer'], explanation=first['explanation'],
        appear=[dict(paper=x['paper'], region=x['region'], no=x['no'], qid=x['qid']) for x in v]))
with open(sys.argv[2], 'w', encoding='utf8') as w:
    for o in out: w.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(out), collections.Counter((o['year'], o['module']) for o in out))
