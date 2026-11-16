#!/usr/bin/env python3
"""校验素材库卡片里的引文：每条以 `>` 开头、以〔代号〕结尾的引文必须能在源文件里逐字找到。

卡片末尾的「## 来源」表给出 代号 → 本地路径（最后一列，反引号包住，相对语料根目录）。
代号形如 `真题2026` 的，对应本仓库该年度行测政治理论与申论真题。
引文里的 **加粗** 只是标记，不参与比对；`……` 表示省略，前后各段分别比对。

用法：python3 analysis/check_quotes.py [素材库/xx.md ...]   （不带参数则检查素材库下全部文件）

另一种写法：正文或表格里的「原文短语」〔代号〕也会校验；不跟代号的「短语」须能在来源表任一文件里找到。
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = Path("/home/fires/projects/Learn-to-Write/corpus/articles/cn")
WS = re.compile(r"[\s　*]+")
TAG = re.compile(r"〔([^〕]+)〕\s*$")
TERM = re.compile(r"「([^」]+)」(?:〔([^〕]+)〕)?")


def norm(s):
    return WS.sub("", s)


def exam_text(year):
    parts = [p.read_text(encoding="utf-8") for p in sorted((REPO / "_build" / "md").glob(f"01-政治理论__{year}年*.md"))]
    parts += [p.read_text(encoding="utf-8") for p in sorted((REPO / "申论").glob(f"{year}国考申论*.md"))]
    return norm("\n".join(parts))


def load_sources(text):
    src = {}
    if "## 来源" not in text:
        return src
    for line in text.split("## 来源", 1)[1].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.search(r"`([^`]+)`", cells[-1]) if len(cells) >= 2 else None
        if m:
            src[cells[0].strip("` ")] = m.group(1)
    return src


def check(path):
    text = path.read_text(encoding="utf-8")
    src = load_sources(text)
    cache, bad, n = {}, [], 0
    for no, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith(">"):
            continue
        body = line.lstrip()[1:].strip()
        m = TAG.search(body)
        if not m:
            if body:
                bad.append((no, "引文缺少〔代号〕", body[:40]))
            continue
        key, quote = m.group(1).strip(), body[: m.start()]
        n += 1
        if key not in cache:
            if key.startswith("真题"):
                cache[key] = exam_text(key[2:6])
            elif key in src and (CORPUS / src[key]).is_file():
                cache[key] = norm((CORPUS / src[key]).read_text(encoding="utf-8"))
            else:
                cache[key] = None
        if cache[key] is None:
            bad.append((no, f"代号〔{key}〕不在来源表或文件不存在", quote[:40]))
            continue
        for frag in re.split(r"…+", quote):
            f = norm(frag).strip("“”\"")
            if len(f) >= 4 and f not in cache[key]:
                bad.append((no, f"〔{key}〕里找不到", frag.strip()[:60]))
    # 第二种写法：表格或正文里的「原文短语」。后面紧跟〔代号〕的在该来源里找；
    # 没跟代号的，在本文件来源表列出的任一来源里找到即可。
    def load(key):
        if key not in cache:
            if key.startswith("真题"):
                cache[key] = exam_text(key[2:6])
            elif key in src and (CORPUS / src[key]).is_file():
                cache[key] = norm((CORPUS / src[key]).read_text(encoding="utf-8"))
            else:
                cache[key] = None
        return cache[key]
    body_text = text.split("## 来源", 1)[0]
    for no, line in enumerate(body_text.splitlines(), 1):
        if line.lstrip().startswith(">"):
            continue
        for m in TERM.finditer(line):
            phrase, key = m.group(1), (m.group(2) or "").strip()
            n += 1
            for frag in re.split(r"…+", phrase):
                f = norm(frag)
                if len(f) < 2:
                    continue
                if key:
                    hay = load(key)
                    if hay is None:
                        bad.append((no, f"代号〔{key}〕不在来源表或文件不存在", frag[:40]))
                    elif f not in hay:
                        bad.append((no, f"〔{key}〕里找不到", frag[:60]))
                elif not any((load(k) or "") and f in load(k) for k in src):
                    bad.append((no, "来源表各文件里都找不到", frag[:60]))
    return n, bad


def main():
    files = [Path(a) for a in sys.argv[1:]] or sorted(p for p in (REPO / "素材库").rglob("*.md") if p.name not in ("README.md", "整理规范.md"))
    fail = 0
    for p in files:
        n, bad = check(p)
        print(f"{p.name}: {n} 条引文或短语，{len(bad)} 处问题")
        for no, why, frag in bad:
            print(f"  L{no} {why}: {frag}")
        fail += len(bad)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
