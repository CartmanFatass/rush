#!/usr/bin/env python3
"""离线重建：从已保存的 JSON + 旧 Markdown 里回收答案，重新渲染 题目+答案 版本。

不联网。用于源站不可用时修复排版 / 去掉解析。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from scrape import render_md  # noqa: E402

from parse import _clean as clean


def repair(t):
    """修复旧数据里被破坏的粗体标记（奇数个 ** 说明已被合并坏）。"""
    if not isinstance(t, str):
        return t
    if t.count('**') % 2:
        t = t.replace('\n', '').replace('**', '')
        t = '**' + t + '**'
    return clean(t)


def clean_data(d):
    for sec in d.get('sections', []):
        for it in sec.get('items', []):
            if 'text' in it:
                it['text'] = repair(it['text'])
            if 'stem' in it:
                it['stem'] = repair(it['stem'])
            for o in it.get('options', []):
                o['text'] = repair(o['text'])
    return d


def answers_from_md(path):
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding='utf-8').read()
    out, n = {}, None
    for line in txt.splitlines():
        m = re.match(r'^### (\d+)\.\s*$', line.strip())
        if m:
            n = int(m.group(1))
            continue
        m = re.match(r'^> \*\*答案：([A-D])\*\*', line.strip())
        if m and n is not None:
            out[n] = m.group(1)
    return out


def main():
    index = json.load(open(os.path.join(ROOT, 'index.json'), encoding='utf-8'))
    for rec in index:
        jp = os.path.join(ROOT, rec['markdown'].replace('.md', '.json'))
        blob = json.load(open(jp, encoding='utf-8'))
        d = blob['data']
        d.setdefault('style', 'quiz' if any(s.get('questions') for s in d['sections']) else 'prose')
        clean_data(d)

        md_path = os.path.join(ROOT, rec['markdown'])
        answers = blob.get('answer_key') or answers_from_md(md_path)
        answers = {int(k): v for k, v in answers.items()}

        md = render_md(d, answers, {}, rec['source'], rec['kind'])
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)

        blob['answer_key'] = answers
        blob['answers'] = len(answers)
        blob.pop('explanations', None)
        with open(jp, 'w', encoding='utf-8') as f:
            json.dump(blob, f, ensure_ascii=False, indent=1)

        rec['answers'] = len(answers)
        rec.pop('explanations', None)
        print(f"{rec['kind']} {rec['year']} q={rec['questions']} ans={len(answers)}  {rec['title'][:40]}")

    with open(os.path.join(ROOT, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('done', len(index))


if __name__ == '__main__':
    main()
