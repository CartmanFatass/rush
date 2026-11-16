#!/usr/bin/env python3
"""用法: python3 -I make_stats.py <省考jsonl> <source_lag.csv> <输出统计.md>"""
import sys, json, csv, statistics, collections, re
jl, csvp, out = sys.argv[1:4]
D = [json.loads(l) for l in open(jl, encoding='utf8')]
C = list(csv.DictReader(open(csvp, encoding='utf8')))
TOPMAP = {'M1':'现代化总论与高质量发展','M2':'科技创新','M3':'内需与经济体制改革','M4':'金融','M6':'党的建设','M8':'民生与人口','M9':'乡村与城乡融合','M10':'生态绿色','M11':'法治与开放','X1':'文化建设','X2':'原理与方法论','X5':'国家安全','X6':'政治制度','X3':'其他','X4':'其他','X7':'其他'}
TYPES = ['A','B','C','D','E','F','G']
TNAME = {'A':'党代会/全会文件','B':'中央会议通稿或会上讲话','C':'《求是》等署名文章','D':'重要讲话','E':'地方考察/回信/贺词','F':'政府文件/规划/党内法规/法律','G':'基本原理/党史等无时效来源'}
TOPICS = ['现代化总论与高质量发展','科技创新','内需与经济体制改革','金融','党的建设','民生与人口','乡村与城乡融合','生态绿色','法治与开放','文化建设','原理与方法论','国家安全','政治制度','其他']
QT = ['选对','选错','几项','排序对应','其他']
def fmt_q(x):  # 国考csv题型 -> 省考题型
    return '排序对应' if x == '排序/对应' else x
def pct(n, d): return f'{100*n/d:.0f}%' if d else '-'
def lagstats(lags):
    if not lags: return None
    n = len(lags)
    return dict(n=n, med=statistics.median(lags), le6=sum(l<=6 for l in lags), le12=sum(l<=12 for l in lags), le18=sum(l<=18 for l in lags), gt24=sum(l>24 for l in lags))
def lagrow(name, st):
    if not st: return f'| {name} | 0 | - | - | - | - | - |'
    n = st['n']
    return f"| {name} | {n} | {st['med']:.1f} | {pct(st['le6'],n)} ({st['le6']}) | {pct(st['le12'],n)} ({st['le12']}) | {pct(st['le18'],n)} ({st['le18']}) | {pct(st['gt24'],n)} ({st['gt24']}) |"
LAGHDR = '| 分组 | 有效题数 | 中位数(月) | ≤6月 | ≤12月 | ≤18月 | >24月 |\n|---|---|---|---|---|---|---|'
def lags_of(rows):
    return [r['距笔试月数'] for r in rows if r['依据类型'] != 'G' and isinstance(r.get('距笔试月数'), (int, float))]
L = []
w = L.append
w('# 省考时政题溯源统计(2024-2026招录年度)\n')
w('数据: 省考时政题溯源.jsonl,按题干去重后的题目,共 %d 题。口径与限制见 说明.md。距笔试月数 = (笔试日期-依据发布日期)天数/30.4375,保留一位小数。\n' % len(D))
w('## 1 去重题数(分年度、分模块)\n')
w('| 年度 | 政治理论 | 常识判断(仅时政类) | 合计 |\n|---|---|---|---|')
tot = [0,0]
for y in (2024, 2025, 2026):
    a = sum(1 for r in D if r['年度']==y and r['模块']=='政治理论'); b = sum(1 for r in D if r['年度']==y and r['模块']=='常识判断')
    tot[0]+=a; tot[1]+=b; w(f'| {y} | {a} | {b} | {a+b} |')
w(f'| 合计 | {tot[0]} | {tot[1]} | {sum(tot)} |\n')
w('按考试类别:\n')
w('| 年度 | 多省联考 | 单省(自主命题) |\n|---|---|---|')
for y in (2024, 2025, 2026):
    a = sum(1 for r in D if r['年度']==y and r['考试']=='多省联考'); b = sum(1 for r in D if r['年度']==y and r['考试']!='多省联考')
    w(f'| {y} | {a} | {b} |')
w('\n单省题目中,同题出现在多省(如江苏A/B/C卷、浙江A/B/C卷)的只计一次。\n')

w('## 2 依据类型分布\n')
w('| 类型 | 说明 | 2024 | 2025 | 2026 | 合计 | 占比 |\n|---|---|---|---|---|---|---|')
for t in TYPES:
    cs = [sum(1 for r in D if r['年度']==y and r['依据类型']==t) for y in (2024,2025,2026)]
    w(f'| {t} | {TNAME[t]} | {cs[0]} | {cs[1]} | {cs[2]} | {sum(cs)} | {pct(sum(cs),len(D))} |')
w('\n## 3 距笔试月数(排除G类与日期缺失的题)\n')
nolag = [r for r in D if r['依据类型']!='G' and not isinstance(r.get('距笔试月数'),(int,float))]
nodate_exam = [r for r in nolag if not r['笔试日期']]
nodate_src = [r for r in nolag if r['笔试日期']]
w(f'全部 {len(D)} 题中:G类 {sum(1 for r in D if r["依据类型"]=="G")} 题不计;非G类但无法计算 {len(nolag)} 题(其中笔试日期未核实 {len(nodate_exam)} 题,依据发布日期缺失 {len(nodate_src)} 题)。\n')
w(LAGHDR)
allL = lags_of(D)
w(lagrow('全部', lagstats(allL)))
for y in (2024, 2025, 2026):
    w(lagrow(f'{y}年度', lagstats(lags_of([r for r in D if r['年度']==y]))))
w(lagrow('政治理论', lagstats(lags_of([r for r in D if r['模块']=='政治理论']))))
w(lagrow('常识判断', lagstats(lags_of([r for r in D if r['模块']=='常识判断']))))
w(lagrow('多省联考', lagstats(lags_of([r for r in D if r['考试']=='多省联考']))))
w(lagrow('单省', lagstats(lags_of([r for r in D if r['考试']!='多省联考']))))
w('')
w('按笔试批次(3月联考/12月单省):\n')
w(LAGHDR)
for key in sorted({r['笔试日期'] for r in D if r['笔试日期']}):
    w(lagrow(key, lagstats(lags_of([r for r in D if r['笔试日期']==key]))))
w('')
w('按依据类型:\n')
w(LAGHDR)
for t in TYPES[:-1]:
    w(lagrow(t+' '+TNAME[t], lagstats(lags_of([r for r in D if r['依据类型']==t]))))
mo = [r for r in D if r['依据类型']!='G' and isinstance(r.get('距笔试月数'),(int,float)) and len(r['依据发布日期'])==7]
w(f'\n其中 {len(mo)} 题的依据发布日期只到月,按当月15日估算,误差约±0.5月。\n')

w('## 4 同一依据被2道及以上题使用\n')
grp = collections.defaultdict(list)
for r in D:
    if r['依据类型']=='G' or not r['依据发布日期'] or len(r['依据发布日期'])!=10: continue
    grp[r['依据发布日期']].append(r)
multi = sorted([(k,v) for k,v in grp.items() if len(v)>=2], key=lambda kv: (-len(kv[1]), kv[0]))
w('分组口径(判断): 以完整依据发布日期归并,同日的不同文件会被并入同组,故逐组列出依据名称变体供核对;只到月的日期、G类、无日期的不参与归并。\n')
w(f'共 {len(multi)} 组,涉及 {sum(len(v) for _,v in multi)} 题。\n')
w('| 依据发布日期 | 题数 | 年度分布 | 依据名称(出现次数) | 编号 |\n|---|---|---|---|---|')
for k,v in multi:
    names = collections.Counter(r['依据名称'] for r in v)
    nm = ';'.join(f'{n}({c})' if c>1 else n for n,c in names.most_common())
    yc = collections.Counter(r['年度'] for r in v)
    w(f"| {k} | {len(v)} | {' '.join(f'{y}:{c}' for y,c in sorted(yc.items()))} | {nm} | {', '.join(r['编号'] for r in v)} |")
w('')

w('## 5 题型分布\n')
w('| 题型 | 2024 | 2025 | 2026 | 合计 | 占比 |\n|---|---|---|---|---|---|')
for q in QT:
    cs = [sum(1 for r in D if r['年度']==y and r['题型']==q) for y in (2024,2025,2026)]
    w(f'| {q} | {cs[0]} | {cs[1]} | {cs[2]} | {sum(cs)} | {pct(sum(cs),len(D))} |')
oth = collections.Counter(r['备注'] for r in D if r['题型']=='其他')
w('\n"其他"含判断对错题与多选题。题型由程序按题干/解析规则判定后抽检,个别可能有误(判断)。\n')

w('## 6 专题分布\n')
w('| 专题 | 2024 | 2025 | 2026 | 合计 | 占比 |\n|---|---|---|---|---|---|')
for t in TOPICS:
    cs = [sum(1 for r in D if r['年度']==y and r['专题']==t) for y in (2024,2025,2026)]
    w(f'| {t} | {cs[0]} | {cs[1]} | {cs[2]} | {sum(cs)} | {pct(sum(cs),len(D))} |')
w('\n专题为人工按题干主旨标注(判断),一题只归一类。\n')

w('## 7 与国考对照(同年度)\n')
w('国考数据: source_lag.csv 中 exam 为 2024/2025/2026 的副省级+地市级题(2024:12题, 2025:22题, 2026:20题,共54题;2026年仅副省级)。国考的G类题无日期,处理同省考(不计入月数统计)。\n')
CG = [r for r in C if r['exam'] in ('2024','2025','2026')]
def crow(r):
    return dict(年度=int(r['exam']), 依据类型=r['type'], 距笔试月数=float(r['lag_months']) if r['lag_months'] else None, 题型=fmt_q(r['format']), 专题=TOPMAP.get(r['topic'],'其他'))
CR = [crow(r) for r in CG]
w('### 7.1 依据类型(占比)\n')
w('| 类型 | 国考2024 | 国考2025 | 国考2026 | 国考合计 | 省考2024 | 省考2025 | 省考2026 | 省考合计 |\n|---|---|---|---|---|---|---|---|---|')
def cnt(rows, y, key, val):
    s = [r for r in rows if y is None or r['年度']==y]
    return sum(1 for r in s if r[key]==val), len(s)
for t in TYPES:
    cells = []
    for rows in (CR, D):
        for y in (2024,2025,2026,None):
            c,n = cnt(rows,y,'依据类型',t); cells.append(f'{pct(c,n)} ({c}/{n})')
    w(f'| {t} | ' + ' | '.join(cells) + ' |')
w('\n### 7.2 距笔试月数(排除G类与无日期)\n')
w(LAGHDR)
for y in (2024,2025,2026):
    w(lagrow(f'国考{y}', lagstats(lags_of([r for r in CR if r['年度']==y]))))
w(lagrow('国考合计', lagstats(lags_of(CR))))
for y in (2024,2025,2026):
    w(lagrow(f'省考{y}', lagstats(lags_of([r for r in D if r['年度']==y]))))
w(lagrow('省考合计', lagstats(allL)))
w('\n注: 国考月数口径沿用 source_lag.csv(一位小数);省考按30.4375天/月换算,两者口径相近但非逐字相同(判断)。国考与省考的笔试日期不同,同"年度"不等于同一时段。\n')
w('### 7.3 题型(占比)\n')
w('| 题型 | 国考合计 | 省考合计 |\n|---|---|---|')
for q in QT:
    c1,n1 = cnt(CR,None,'题型',q); c2,n2 = cnt(D,None,'题型',q)
    w(f'| {q} | {pct(c1,n1)} ({c1}/{n1}) | {pct(c2,n2)} ({c2}/{n2}) |')
w('\n### 7.4 专题(占比)\n')
w('| 专题 | 国考合计 | 省考合计 |\n|---|---|---|')
for t in TOPICS:
    c1,n1 = cnt(CR,None,'专题',t); c2,n2 = cnt(D,None,'专题',t)
    w(f'| {t} | {pct(c1,n1)} ({c1}/{n1}) | {pct(c2,n2)} ({c2}/{n2}) |')
w('\n国考专题由 source_lag.csv 的 M/X 代码映射而来(M1→现代化总论与高质量发展等;X3/X4/X7→其他),映射表见 scripts/make_stats.py。\n')
open(out,'w',encoding='utf8').write('\n'.join(L))
print('ok', len(L))
