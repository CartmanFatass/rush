#!/usr/bin/env python3
"""把 build_unique.py 的去重结果 + 人工标注文件(annotations/*.txt) 合成 省考时政题溯源.jsonl。
用法: python3 -I compile_dataset.py <uniq.jsonl> <annotations目录> <输出jsonl>
标注行格式: 后缀|依据类型|依据名称|依据发布日期(YYYY-MM-DD或YYYY-MM)|专题码|备注
"""
import sys, json, re, glob, os, datetime, collections

TOPICS = {'1': '现代化总论与高质量发展', '2': '科技创新', '3': '内需与经济体制改革', '4': '金融', '5': '党的建设',
          '6': '民生与人口', '7': '乡村与城乡融合', '8': '生态绿色', '9': '法治与开放', '10': '文化建设',
          '11': '原理与方法论', '12': '国家安全', '13': '政治制度', '14': '其他'}

# ---- 笔试(行测)日期表: (年度, 组) -> (日期, 来源) ----
SRC = {
 ('2026', 'lk'): ('2026-03-14', '中新网3月14日电(转载于川观新闻/中国日报网2026-03-14):重庆、吉林、山西、河南等20余省份当日举行2026年度公务员招录公共科目笔试;上岸鸭汇总表(m.gwy.com/dfgwy/392850.html)列联考省份3月14日-15日;广西页面标题"3月14日开考"'),
 ('2026', 'dec'): ('2025-12-07', '上岸鸭汇总表(m.gwy.com/dfgwy/392850.html):北京/山东/天津/浙江/上海/江苏12月6日-7日,四川/广东12月7日;中新网称四川、上海、浙江、山东等12月举行。公共科目取12月7日,区间首日可能为专业科目,误差不超过1天'),
 ('2025', 'lk'): ('2025-03-15', '第一财经2025-03-16、界面新闻2025-03-17报道:23/24省区市3月15日同日举行2025年公务员联考笔试(点名广东、河南、湖北、湖南、陕西、河北、山西等)'),
 ('2025', 'dec'): ('2024-12-08', '凤凰网(news.ifeng.com/c/8eP999hezJo,2024-11-10)报道:四川、上海、浙江、山东、天津、江苏6省同日12月8日举行公共科目笔试'),
 ('2024', 'lk'): ('2024-03-16', '中新网2024-04-10:3月16日25个省份同日举行2024年度公务员招录考试;上岸鸭2024-02-28汇总表(m.gwy.com/gjgwy/350451.html)列19省区3月16日-17日'),
}
# 区域 -> 组 (None 表示日期未查实)
GROUP = {
 '2026': {**{r: 'lk' for r in ['云南','内蒙古','吉林','安徽','山西','广西','新疆','江西','河北','河南','海南','湖北','湖南','甘肃','福建','贵州','辽宁','重庆','陕西','青海','黑龙江']},
          **{r: 'dec' for r in ['上海','四川','天津','广东','浙江']}},
 '2025': {**{r: 'lk' for r in ['云南','内蒙古','宁夏','安徽','山西','广东','广西','新疆','新疆兵团','江西','河北','河南','海南','湖北','湖南','甘肃','福建','贵州','辽宁','重庆','陕西','青海','黑龙江']},
          **{r: 'dec' for r in ['上海','四川','天津','山东','江苏','浙江']}, '深圳市考': None},
 '2024': {**{r: 'lk' for r in ['云南','吉林','天津','宁夏','安徽','山西','广东','广西','新疆','新疆兵团','江西','河北','河南','海南','湖北','湖南','甘肃','福建','贵州','辽宁','重庆','陕西','青海','黑龙江']},
          **{r: None for r in ['四川','山东','江苏','浙江','深圳市考']}},
}
def region_of(a):
    return '新疆兵团' if '兵团' in a['paper'] else a['region']
def paper_label(a):
    p = a['paper']
    m = re.search(r'（([ABC])类）', p)
    if m: return m.group(1) + '类'
    return ''

QTYPE_OVERRIDE = {'2025-Z-0436': ('选对',''), '2026-Z-0817': ('选对','')}  # 人工核对:题干含"不是/而不是"但并非选错题

def qtype(u):
    if u.get('uid') in QTYPE_OVERRIDE: return QTYPE_OVERRIDE[u['uid']]
    """题型判定顺序: 无选项=判断对错(其他) > 几项 > 排序(先后/顺序) > 解析含"选非题"=选错 > 对应/匹配=排序对应 > 多选(其他) > 题干末尾含否定词=选错 > 选对"""
    stem = u['stem']; ans = u['answer']; opts = u['options']; expl = u['explanation']
    head = stem.split('①')[0] if '①' in stem else stem
    tail = head[-45:].replace('颠覆性错误', '')
    if not opts:
        return '其他', '判断对错题'
    if re.search(r'几项|几个|几处|多少项|有几|几种', stem) or all(re.fullmatch(r'[A-D]\.\s*[一二三四五六七八九0-9]+\s*(项|个|处)', o.replace('✅','').strip()) for o in opts):
        return '几项', ''
    if re.search(r'先后顺序|排序|排列|时间顺序|时间先后|按.{0,8}顺序', head):
        return '排序对应', ''
    if '选非题' in expl:
        return '选错', ''
    if len(ans) > 1 and re.fullmatch(r'[A-H]+', ans):
        return '其他', '多选题'
    if re.search(r'对应|匹配|相对应', head):
        return '排序对应', ''
    if re.search(r'(错误|不正确|有误|不准确|不恰当|不符合|不属于|不是|没有体现|不相符|不当|不合理|无关|不包括|不涉及|不同的是)', tail):
        return '选错', ''
    return '选对', ''

def months_between(pub, exam):
    d1 = datetime.date.fromisoformat(pub if len(pub) == 10 else pub + '-15')
    d2 = datetime.date.fromisoformat(exam)
    return round((d2 - d1).days / 30.4375, 1), len(pub) != 10

def main():
    uniq = [json.loads(l) for l in open(sys.argv[1], encoding='utf8')]
    ann = {}
    for f in sorted(glob.glob(os.path.join(sys.argv[2], '*.txt'))):
        for l in open(f, encoding='utf8'):
            l = l.rstrip('\n')
            if not l.strip() or l.startswith('#'): continue
            parts = l.split('|')
            assert len(parts) >= 6, l
            ann[parts[0]] = parts
    # 论文所属组件(是否多省共卷)
    comp = {}
    for y in ('2024', '2025', '2026'):
        par = {}
        def find(x):
            par.setdefault(x, x)
            while par[x] != x:
                par[x] = par[par[x]]; x = par[x]
            return x
        for u in uniq:
            if u['year'] != y: continue
            ps = [a['paper'] for a in u['appear']]
            find(ps[0])
            for p in ps[1:]: par[find(p)] = find(ps[0])
        sizes = collections.Counter(find(p) for p in list(par))
        for p in list(par): comp[(y, p)] = sizes[find(p)]
    out = []; missing = []
    for u in uniq:
        suffix = u['uid'].split('-', 1)[1]
        key = suffix if suffix in ann else None
        if key is None: continue   # 不在应标范围(非时政的常识判断题)
        _, typ, basis, pub, topic, note = ann[key][:6]
        y = u['year']
        regs = sorted({region_of(a) for a in u['appear']})
        groups = {GROUP[y].get(r) for r in regs}
        g = None if None in groups else (groups.pop() if len(groups) == 1 else 'mixed')
        exam_date, src = ('', '该卷笔试日期未查实') if g in (None,) else SRC[(y, g)] if g != 'mixed' else ('', 'MIXED')
        shared = max(comp[(y, a['paper'])] for a in u['appear']) >= 2
        if g == 'lk' and shared: kao = '多省联考'
        elif g == 'lk': kao = regs[0] + '(与联考同日,自主命题卷)'
        else: kao = '、'.join(regs)
        labels = sorted({paper_label(a) for a in u['appear']} - {''})
        juan = '/'.join(labels) if labels else ('联考卷' if kao == '多省联考' else '单独命题卷')
        qt, qnote = qtype(u)
        stem60 = re.sub(r'\s+', ' ', u['stem']).strip()[:60]
        lag = ''; notes = []
        if qnote: notes.append(qnote)
        if note and note != qnote: notes.append(note)
        notes = list(dict.fromkeys(sum([n.split(';') for n in notes], [])))
        if pub and exam_date:
            lag, monthonly = months_between(pub, exam_date)
            if monthonly: notes.append('距笔试月数按当月15日估算')
            if lag < 0: notes.append('依据日期晚于笔试日期,请核对')
        elif pub and not exam_date:
            notes.append('笔试日期未查实,未算距笔试月数')
        if len(u['appear']) > 1: notes.append(f"同题在{len(u['appear'])}份卷中出现")
        out.append({
            '编号': u['uid'], '年度': int(y), '考试': kao, '卷别': juan, '出现省份': regs,
            '笔试日期': exam_date, '笔试日期来源': src, '模块': u['module'], '题干前60字': stem60,
            '题型': qt, '依据名称': basis, '依据类型': typ, '依据发布日期': pub, '距笔试月数': lag,
            '专题': TOPICS[topic], '备注': ';'.join(n for n in notes if n)})
    with open(sys.argv[3], 'w', encoding='utf8') as w:
        for o in out: w.write(json.dumps(o, ensure_ascii=False) + '\n')
    print('written', len(out), 'annotated lines', len(ann))
main()
