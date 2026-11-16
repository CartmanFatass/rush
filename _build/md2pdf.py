#!/usr/bin/env python3
"""把合并后的 Markdown 试卷渲染成可打印的 A4 PDF（无 pandoc 依赖，走 Chrome headless）。"""
import html
import os
import re
import subprocess
import sys

CSS = """
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: "Droid Sans Fallback", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 10.5pt; line-height: 1.75; color: #111; margin: 0;
  text-align: justify; word-break: break-word;
}
h1 { font-size: 17pt; text-align: center; margin: 0 0 4pt; line-height: 1.4; }
h2 { font-size: 13pt; margin: 18pt 0 8pt; padding-bottom: 3pt;
     border-bottom: 1.2pt solid #333; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 6pt; page-break-after: avoid; }
h4 { font-size: 11pt; margin: 12pt 0 5pt; page-break-after: avoid; }
p { margin: 0 0 6pt; }
blockquote { margin: 0 0 10pt; padding: 6pt 10pt; background: #f4f4f4;
             border-left: 3pt solid #999; font-size: 9.5pt; color: #444; }
blockquote p { margin: 0; }
ul { margin: 0 0 6pt; padding-left: 1.6em; }
li { margin: 0 0 2pt; }
hr { border: 0; border-top: 0.6pt dashed #bbb; margin: 10pt 0; }
img { max-width: 100%; height: auto; vertical-align: middle; }
sub { font-size: 8pt; color: #666; font-weight: normal; }
strong { font-weight: 700; }
.paper { page-break-after: always; }
.paper:last-child { page-break-after: auto; }
"""


def inline(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<em>\1</em>', text)
    return text


def render(md):
    out, para, in_list = [], [], False

    def flush_para():
        nonlocal para
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>')
            para = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    for raw in md.split('\n'):
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_para()
            flush_list()
            continue

        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            out.append(f'<h{level}>{inline(m.group(2))}</h{level}>')
            continue

        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', stripped):
            flush_para()
            flush_list()
            out.append('<hr>')
            continue

        if stripped.startswith('>'):
            flush_para()
            flush_list()
            out.append('<blockquote><p>' + inline(stripped.lstrip('> ').strip()) + '</p></blockquote>')
            continue

        m = re.match(r'^[-*+]\s+(.*)$', stripped)
        if m:
            flush_para()
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append('<li>' + inline(m.group(1)) + '</li>')
            continue

        if stripped.startswith('<'):
            flush_para()
            flush_list()
            out.append(stripped)
            continue

        flush_list()
        para.append(stripped)

    flush_para()
    flush_list()
    return '\n'.join(out)


def build(md_path, pdf_path):
    md = open(md_path, encoding='utf-8').read()
    body = render(md)
    title = os.path.basename(md_path)[:-3]
    doc = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
           f'<title>{html.escape(title)}</title><style>{CSS}</style></head>'
           f'<body><div class="paper">{body}</div></body></html>')
    html_path = pdf_path[:-4] + '.html'
    open(html_path, 'w', encoding='utf-8').write(doc)
    subprocess.run([
        'google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
        '--allow-file-access-from-files', '--no-pdf-header-footer',
        '--virtual-time-budget=20000',
        f'--print-to-pdf={os.path.abspath(pdf_path)}',
        'file://' + os.path.abspath(html_path),
    ], capture_output=True)
    return pdf_path


if __name__ == '__main__':
    for md in sys.argv[1:]:
        pdf = os.path.splitext(md)[0] + '.pdf'
        build(md, pdf)
        size = os.path.getsize(pdf) if os.path.exists(pdf) else 0
        print(f'{os.path.basename(pdf)}  {size // 1024} KB')
