"""HTML parsers for gwy.gkzhenti.cn paper / answer / explain pages."""
import re
from bs4 import BeautifulSoup, NavigableString, Tag

OPT_RE = re.compile(r'^\s*([A-D])\s*[、．.:：]\s*(.*)$', re.S)


def _clean(s):
    s = s.replace('\u00a0', ' ').replace('\u3000', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = _merge_bold(s)
    # 去掉只包含标点的粗体标记，如 **”** -> ”
    s = re.sub(r'\*\*([^\w\u4e00-\u9fff\s]{1,3})\*\*', r'\1', s)
    s = s.replace('****', '')
    return s.strip()


_BOLD_GAP = re.compile(r'\*\*((?:[^*]|\*(?!\*))*?)\*\*([^\s*]{1,2})\*\*')


def _merge_bold(s):
    """把被短文本隔开的相邻粗体段合并：**A**1**B** -> **A1B**。"""
    prev = None
    while prev != s:
        prev = s
        s = _BOLD_GAP.sub(r'**\1\2', s)
    return s


def _img_md(img, img_map):
    src = img.get('src') or img.get('data-src') or ''
    if not src:
        return ''
    src = src.strip()
    if src.startswith('//'):
        src = 'https:' + src
    elif src.startswith('/'):
        src = 'https://gwy.gkzhenti.cn' + src
    local = img_map.get(src)
    alt = img.get('alt') or '图'
    if local:
        return f'![{alt}]({local})'
    return f'![{alt}]({src})'


def node_to_text(node, img_map):
    """Render a tag's inner content to markdown-ish text, keeping <img>."""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
        elif isinstance(child, Tag):
            if child.name == 'img':
                out.append(_img_md(child, img_map))
            elif child.name == 'br':
                out.append('\n')
            elif child.name in ('b', 'strong'):
                inner = node_to_text(child, img_map).strip()
                out.append('**' + inner + '**' if inner else '')
            elif child.name == 'u':
                inner = node_to_text(child, img_map).strip()
                out.append(f'<u>{inner}</u>' if inner else '')
            elif child.name in ('em', 'i', 'span', 'a', 'font', 'sup', 'sub'):
                out.append(node_to_text(child, img_map))
            else:
                out.append('\n' + node_to_text(child, img_map) + '\n')
    return _clean(''.join(out))


def parse_paper(html, img_map=None):
    img_map = img_map or {}
    soup = BeautifulSoup(html, 'lxml')
    root = soup.find(id='printcontent')
    if root is None:
        return None

    title_tag = root.find('h3')
    title = _clean(title_tag.get_text()) if title_tag else ''

    meta = {}
    for p in root.find_all('p', attrs={'align': 'center'}):
        t = _clean(p.get_text())
        for k, v in re.findall(r'(分类|来源)\s*[：:]\s*([^\s]+)', t):
            meta[k] = v.strip()
        break

    sections = []
    cur = None
    for row in root.find_all('div', class_='row'):
        sub = row.find('div', class_=lambda c: c and 'subtitle' in c)
        if sub is not None:
            cur = {'title': _clean(sub.get_text()), 'items': []}
            sections.append(cur)
            continue
        left = row.find('div', class_=lambda c: c and 'left' in c)
        right = row.find('div', class_=lambda c: c and 'right' in c)
        if cur is None:
            cur = {'title': '', 'items': []}
            sections.append(cur)
        if right is None:
            # 资料分析材料块 / 分组标题
            label = ''
            for d in row.find_all('div', recursive=False):
                cls = ' '.join(d.get('class') or [])
                if 'sub2title' in cls:
                    label = _clean(d.get_text())
            parts = []
            for d in row.find_all('div', recursive=False):
                cls = ' '.join(d.get('class') or [])
                if 'sub2title' in cls:
                    continue
                parts.extend(_block_parts(d, img_map))
            if parts:
                cur['items'].append({'type': 'material', 'label': label,
                                     'text': '\n\n'.join(parts)})
            continue
        num = _clean(left.get_text()) if left is not None else ''
        q = _parse_question(num, right, img_map)
        if q['number']:
            cur['items'].append({'type': 'question', **q})
        elif q['stem']:
            cur['items'].append({'type': 'material', 'label': '',
                                 'text': q['stem']})

    for s in sections:
        s['questions'] = [i for i in s['items'] if i['type'] == 'question']
        s['materials'] = [i['text'] for i in s['items'] if i['type'] == 'material']

    # 申论-style documents: <h2> sections with plain <p>
    if not sections:
        sections = _parse_prose(root, img_map)
        for s in sections:
            s['questions'] = []
            s['items'] = [{'type': 'material', 'label': '',
                           'text': b if isinstance(b, str) else _table_md(b['table'])}
                          for b in s['blocks']]
        return {'title': title, 'meta': meta, 'sections': sections, 'style': 'prose'}

    return {'title': title, 'meta': meta, 'sections': sections, 'style': 'quiz'}


def _table_md(rows):
    if not rows:
        return ''
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |',
           '| ' + ' | '.join(['---'] * width) + ' |']
    for r in rows[1:]:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out)


def _block_parts(node, img_map):
    parts = []
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        if child.name == 'p':
            t = node_to_text(child, img_map)
            if t:
                parts.append(t)
        elif child.name == 'table':
            rows = []
            for tr in child.find_all('tr'):
                rows.append([_clean(td.get_text()) for td in tr.find_all(['td', 'th'])])
            if rows:
                parts.append(_table_md(rows))
        elif child.name == 'img':
            parts.append(_img_md(child, img_map))
        else:
            t = node_to_text(child, img_map)
            if t:
                parts.append(t)
    return parts


def _parse_question(num, right, img_map):
    stem_parts, options = [], []
    for child in right.children:
        if not isinstance(child, Tag):
            continue
        cls = ' '.join(child.get('class') or [])
        if child.name == 'p':
            txt = node_to_text(child, img_map)
            m = OPT_RE.match(txt)
            if m and len(options) < 4 and not child.find('img'):
                options.append({'label': m.group(1), 'text': m.group(2).strip()})
            elif txt:
                stem_parts.append(txt)
        elif 'col-xs-' in cls:
            txt = node_to_text(child, img_map)
            m = OPT_RE.match(txt)
            if m:
                options.append({'label': m.group(1), 'text': m.group(2).strip()})
            elif txt:
                stem_parts.append(txt)
        elif child.name == 'img':
            stem_parts.append(_img_md(child, img_map))
        else:
            txt = node_to_text(child, img_map)
            if txt:
                stem_parts.append(txt)
    return {'number': num, 'stem': '\n\n'.join(stem_parts), 'options': options}


def _parse_prose(root, img_map):
    """申论: <h2>一、注意事项</h2> blocks of <p>."""
    sections = []
    cur = {'title': '正文', 'blocks': []}
    sections.append(cur)
    wrapper = root.find('div') or root
    for el in wrapper.find_all(['h2', 'h3', 'p', 'table', 'div'], recursive=True):
        if el.name == 'h2':
            cur = {'title': _clean(el.get_text()), 'blocks': []}
            sections.append(cur)
        elif el.name == 'p':
            if el.find_parent('table'):
                continue
            txt = node_to_text(el, img_map)
            if txt:
                cur['blocks'].append(txt)
        elif el.name == 'table':
            rows = []
            for tr in el.find_all('tr'):
                cells = [_clean(td.get_text()) for td in tr.find_all(['td', 'th'])]
                rows.append(cells)
            if rows:
                cur['blocks'].append({'table': rows})
    return [s for s in sections if s['blocks']]


def parse_answers(html):
    soup = BeautifulSoup(html, 'lxml')
    root = soup.find(id='printcontent') or soup
    text = root.get_text(' ', strip=True)
    pairs = re.findall(r'(\d{1,3})\s*[、.．]\s*([A-D])', text)
    out = {}
    for n, a in pairs:
        out[int(n)] = a
    return out


def parse_explain(html, img_map=None):
    img_map = img_map or {}
    soup = BeautifulSoup(html, 'lxml')
    root = soup.find(id='printcontent')
    if root is None:
        return {}
    out = {}
    for row in root.find_all('div', class_='row'):
        left = row.find('div', class_=lambda c: c and 'left' in c)
        right = row.find('div', class_=lambda c: c and 'right' in c)
        if right is None or left is None:
            continue
        num = _clean(left.get_text())
        if not num.isdigit():
            continue
        parts = []
        for p in right.find_all('p'):
            t = node_to_text(p, img_map)
            if t:
                parts.append(t)
        for img in right.find_all('img'):
            parts.append(_img_md(img, img_map))
        out[int(num)] = '\n\n'.join(parts)
    return out
