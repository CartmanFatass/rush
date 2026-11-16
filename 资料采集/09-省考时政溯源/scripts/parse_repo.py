#!/usr/bin/env python3
"""解析 xingcezhenti 仓库中 2024-2026 年的 01-政治理论 / 02-常识判断 单文件，输出 questions.jsonl。
用法: python3 -I parse_repo.py <repo目录> <输出jsonl>
"""
import sys, re, os, glob, json

def strip_html(s):
    s = re.sub(r'<img[^>]*>', '[图]', s)
    s = re.sub(r'</p>\s*<p>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return s.replace('　', ' ').strip()

def parse_file(path, module):
    t = open(path, encoding='utf8').read()
    m = re.match(r'---\n(.*?)\n---\n', t, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip().strip('"')
    body = t[m.end():] if m else t
    parts = re.split(r'\n#{2,3} 第 (\d+) 题\s*<sub>qid (\d+) · ([^<]*)</sub>\n', body)
    out = []
    # parts[0] = preamble (可能含材料)
    pre = parts[0]
    for i in range(1, len(parts), 4):
        no, qid, tag, txt = parts[i], parts[i+1], parts[i+2], parts[i+3]
        txt = re.split(r'\n## 材料', txt)[0]
        ans = re.search(r'\*\*答案\*\*：(.*)', txt)
        expl = ''
        if '**官方解析**' in txt:
            expl = txt.split('**官方解析**', 1)[1].strip()
            expl = re.sub(r'\n---\s*$', '', expl).strip()
        head = txt.split('**答案**')[0]
        opts = re.findall(r'^- \*\*([A-H])\*\*\. (.*)$', head, re.M)
        stem = re.split(r'\n- \*\*A\*\*\.|\n- （选项）', head)[0]
        out.append(dict(file=os.path.basename(path), paper=meta.get('试卷', ''), region=meta.get('地区', ''),
                        year=meta.get('年份', ''), module=module, no=int(no), qid=qid, tag=tag.strip(),
                        stem=strip_html(stem), options=[f'{a}.{strip_html(b)}' for a, b in opts],
                        answer=(ans.group(1).strip() if ans else ''), explanation=strip_html(expl)))
    return out

def main():
    repo, outp = sys.argv[1], sys.argv[2]
    n = 0
    with open(outp, 'w', encoding='utf8') as w:
        for mod_dir, module in (('01-政治理论', '政治理论'), ('02-常识判断', '常识判断')):
            for f in sorted(glob.glob(os.path.join(repo, mod_dir, '202[456]年*.md'))):
                for q in parse_file(f, module):
                    w.write(json.dumps(q, ensure_ascii=False) + '\n'); n += 1
    print('questions', n)
main()
