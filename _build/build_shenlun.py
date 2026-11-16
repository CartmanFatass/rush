#!/usr/bin/env python3
"""把抓取到的申论真题/参考答案原文整理成可读的 Markdown 试卷。"""
import os
import re

SRC = '_build/shenlun_src'
OUT = '申论'
CN = '一二三四五'
YEARS = ('2022', '2023', '2024', '2025', '2026')
PAPERS = ('副省级', '地市级', '行政执法')

JUNK = re.compile(
    r'^(\$|if \(|}|type:|url:|success|data:|async|cache:|error:|var |//|/\*|\*/'
    r'|document\.|window\.|function|return |else)'
)
FIX = {'⾏': '行', '⾏政执法': '行政执法'}

# 2026 行政执法卷的源页缺少「材料N」小标题，按题干所引「给定资料N」的起始段切分
SPLIT_2026_ZF = [
    '2025年10月的一天，鲁师傅办公桌上的电脑屏幕弹出',
    '威山自然保护区森林覆盖面积达13800公顷',
    '2025年8月初，D市市场监管局接到多起投诉',
    '清晨6:30，A省B市政务云数据中心监控室里',
    'E市一家快餐配送点内',
]


def load(path):
    """读取原文，去掉导航、脚本与页脚，返回从标题行之后开始的正文行。"""
    lines = []
    started = False
    for raw in open(path, encoding='utf-8').read().split('\n'):
        line = raw.strip()
        if not started:
            if re.search(r'\d{4}年国家公务员考试《申论》', line):
                started = True
            continue
        if JUNK.match(line):
            continue
        if line.startswith(('发布者：', '浏览量：', '发布时间：')):
            continue
        if len(line) <= 1:
            continue
        for a, b in FIX.items():
            line = line.replace(a, b)
        lines.append(line)
    return lines


def split_materials(lines):
    """2026 行政执法卷补回材料分隔。"""
    out, k = [], 0
    for line in lines:
        if k < len(SPLIT_2026_ZF) and line.startswith(SPLIT_2026_ZF[k]):
            out.append(f'材料{k + 1}')
            k += 1
        out.append(line)
    return out


def is_question_line(lines, i):
    """`1、xxx` 既可能是题干，也可能是答案里的分点，用后面的「要求：」来区分。"""
    for nxt in lines[i + 1:i + 4]:
        if nxt.startswith('要求'):
            return True
        if nxt.strip():
            break
    return False


def build_paper(year, paper):
    body = load(f'{SRC}/{year}{paper}_题.txt')
    if (year, paper) == ('2026', '行政执法'):
        body = split_materials(body)

    buf = [f'# {year}年国家公务员考试《申论》（{paper}）\n',
           f'> 国考 {year} · {paper} · 考生回忆版 · 文末附参考答案\n']

    for i, line in enumerate(body):
        m = re.match(r'^([一二三四五])、(.+)$', line)
        if m and len(line) < 20:
            buf.append(f'\n## {m.group(1)}、{m.group(2)}\n')
            continue
        m = re.match(r'^材料\s*(\d+)\s*[.．。、]?\s*$', line)
        if m:
            buf.append(f'\n### 材料 {m.group(1)}\n')
            continue
        m = re.match(r'^第([一二三四五])题\s*$', line)
        if m:
            buf.append(f'\n### 第{m.group(1)}题\n')
            continue
        m = re.match(r'^([1-5])、(.+)$', line)
        if m and is_question_line(body, i):
            buf.append(f'\n### 第{CN[int(m.group(1)) - 1]}题\n{m.group(2)}\n')
            continue
        buf.append(line + '\n\n')

    buf.append('\n---\n\n## 参考答案\n')
    answers = load(f'{SRC}/{year}{paper}_答.txt')
    for i, line in enumerate(answers):
        m = re.match(r'^第([一二三四五])题\s*$', line)
        if m:
            buf.append(f'\n### 第{m.group(1)}题\n')
            continue
        m = re.match(r'^([1-5])、(.*)$', line)
        if m and is_question_line(answers, i):
            buf.append(f'\n### 第{CN[int(m.group(1)) - 1]}题\n{m.group(2)}\n')
            continue
        m = re.match(r'^【(.+)】$', line)
        if m:
            buf.append(f'\n**{line}**\n')
            continue
        buf.append(line + '\n\n')

    text = re.sub(r'\n{3,}', '\n\n', ''.join(buf))
    path = f'{OUT}/{year}国考申论（{paper}）.md'
    open(path, 'w', encoding='utf-8').write(text)
    return path, text


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for year in YEARS:
        for paper in PAPERS:
            path, text = build_paper(year, paper)
            mats = len(re.findall(r'^### 材料', text, re.M))
            qs = len(re.findall(r'^### 第[一二三四五]题', text, re.M))
            print(f'{os.path.basename(path):28s} 材料={mats} 题块={qs} {len(text) // 1000}K字符')
