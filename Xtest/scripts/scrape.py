#!/usr/bin/env python3
"""抓取 gwy.gkzhenti.cn（公开真题库）国考行测 / 申论真题（近 5 年）。

输出:
  Xtest/行测/<年份>/<试卷名>.md / .json
  Xtest/申论/<年份>/<试卷名>.md / .json
  Xtest/assets/<试卷ID>/<图片>
  Xtest/README.md, Xtest/index.json
"""
import json
import os
import re
import sys
import time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from parse import parse_paper, parse_answers  # noqa: E402

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

BASE = 'https://gwy.gkzhenti.cn'
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, 'assets')
YEARS = {2022, 2023, 2024, 2025, 2026}

SESSION = requests.Session()
SESSION.headers['User-Agent'] = UA


def api_list(cls, province='国考'):
    r = SESSION.get(f'{BASE}/api/json', params={'cls': cls, 'province': province}, timeout=30)
    r.raise_for_status()
    return r.json()


def year_of(title):
    m = re.match(r'\s*(\d{4})\s*年', title)
    return int(m.group(1)) if m else None


def paper_kind(title):
    """卷种：副省级 / 地市级 / 行政执法 / 其他。"""
    if '行政执法' in title:
        return '行政执法'
    if '副省' in title:
        return '副省级'
    if '地市' in title:
        return '地市级'
    if '公安' in title:
        return '公安'
    return re.sub(r'[（(].*?[）)]', '', title)


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', s)
    s = re.sub(r'\s+', '', s)
    return s[:110]


def download_images(html, pid, md_dir):
    """Download every image referenced in html; return {url: relative path}."""
    urls = set()
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', html):
        u = m.group(1).strip()
        if 'icon.png' in u:
            continue
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('/'):
            u = BASE + u
        if 'gkzhenti.cn' not in u:
            continue
        urls.add(u)
    out = {}
    if not urls:
        return out
    d = os.path.join(ASSETS, pid)
    os.makedirs(d, exist_ok=True)
    for u in sorted(urls):
        name = u.rsplit('/', 1)[-1]
        path = os.path.join(d, name)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            try:
                r = SESSION.get(u, timeout=30)
                if r.status_code == 200 and r.content:
                    with open(path, 'wb') as f:
                        f.write(r.content)
                else:
                    continue
            except Exception as e:
                print('    ! img fail', u, e)
                continue
        out[u] = os.path.relpath(path, md_dir).replace(os.sep, '/')
    return out


def get_retry(url, tries=5):
    last = None
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=40)
            if r.status_code == 200:
                return r
            last = r
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    if isinstance(last, Exception):
        raise last
    last.raise_for_status()
    return last


def fetch_paper(pid, md_dir):
    r = get_retry(f'{BASE}/paper/{pid}')
    html = r.text
    img_map = download_images(html, pid, md_dir)
    data = parse_paper(html, img_map)
    if data is None:
        raise RuntimeError('parse failed')
    return data, img_map


def fetch_answers(pid):
    try:
        r = SESSION.get(f'{BASE}/answer/{pid}', timeout=40)
        if r.status_code != 200:
            return {}
        return parse_answers(r.text)
    except Exception:
        return {}


def render_md(data, answers, explains, source_url, kind):
    lines = []
    title = data['title']
    lines.append(f'# {title}\n')
    meta = data.get('meta') or {}
    lines.append(f"- 分类：{meta.get('分类', kind + '/国考')}")
    if meta.get('来源'):
        lines.append(f"- 来源：{meta['来源']}")
    qs = [q for s in data['sections'] for q in s['questions']]
    if qs:
        lines.append(f'- 题目数：{len(qs)}')
    if answers:
        lines.append(f'- 答案：{len(answers)} 题')
    if explains:
        lines.append(f'- 解析：{len(explains)} 题（免费试读部分，其余需会员）')
    lines.append(f'- 原始链接：{source_url}')
    lines.append('')

    prose = data.get('style') == 'prose'
    for sec in data['sections']:
        if sec.get('title'):
            lines.append(f"\n## {sec['title']}\n")
        for item in sec.get('items', []):
            if item['type'] == 'material':
                if prose:
                    lines.append(item['text'] + '\n')
                elif item.get('label'):
                    lines.append(f"\n### 材料 {item['label']}\n")
                    lines.append(item['text'] + '\n')
                else:
                    lines.append(item['text'] + '\n')
            else:
                lines.append(f"\n### {item['number']}.\n")
                lines.append(item['stem'] + '\n')
                for o in item['options']:
                    lines.append(f"- **{o['label']}**、{o['text']}")
                n = int(item['number']) if str(item['number']).isdigit() else None
                ans = answers.get(n) if n else None
                exp = explains.get(n) if n else None
                if ans:
                    lines.append(f"\n> **答案：{ans}**\n")
                if exp:
                    body = '\n'.join('> ' + l if l.strip() else '>' for l in exp.split('\n'))
                    lines.append(f"\n> **解析：**\n>\n{body}\n")

    if answers:
        lines.append('\n## 参考答案速查\n')
        nums = sorted(answers)
        row = []
        for n in nums:
            row.append(f'{n}.{answers[n]}')
        for i in range(0, len(row), 10):
            lines.append('- ' + '　'.join(row[i:i + 10]))
        lines.append('')
    return '\n'.join(lines)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    index = []
    for kind, cls in (('行测', '行测'), ('申论', '申论')):
        papers = api_list(cls)
        best = {}
        for p in papers:
            y = year_of(p['Title'])
            if y not in YEARS:
                continue
            if '公安院校联考' in p['Title']:
                continue
            key = (y, paper_kind(p['Title']))
            score = 0
            if '站友提供版' in p['Title']:
                score -= 5
            if '网友回忆版' in p['Title']:
                score += 2
            if key not in best or score > best[key][0]:
                best[key] = (score, p)
        picked = [(y, p) for (y, _k), (_s, p) in best.items()]
        picked.sort(key=lambda x: (-x[0], paper_kind(x[1]['Title'])))
        print(f'== {kind}: {len(picked)} papers')
        for y, p in picked:
            pid = p['No'].rstrip('/').split('/')[-1]
            name = safe_name(p['Title'])
            out_dir = os.path.join(ROOT, kind, str(y))
            os.makedirs(out_dir, exist_ok=True)
            md_path = os.path.join(out_dir, name + '.md')
            print(f'  - {y} {p["Title"]} ({pid})')
            try:
                data, _ = fetch_paper(pid, out_dir)
            except Exception as e:
                print('    ! paper fail', e)
                continue
            answers = fetch_answers(pid) if kind == '行测' else {}
            explains = {}
            md = render_md(data, answers, explains, f'{BASE}/paper/{pid}', kind)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md)
            rec = {
                'kind': kind, 'year': y, 'title': data['title'],
                'paper_id': pid, 'source': f'{BASE}/paper/{pid}',
                'questions': len([q for s in data['sections'] for q in s['questions']]),
                'answers': len(answers), 'answer_key': answers,
                'markdown': os.path.relpath(md_path, ROOT).replace(os.sep, '/'),
                'data': data,
            }
            with open(os.path.join(out_dir, name + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
            index.append({k: v for k, v in rec.items() if k != 'data'})
            time.sleep(0.4)

    with open(os.path.join(ROOT, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('total', len(index))


if __name__ == '__main__':
    main()
