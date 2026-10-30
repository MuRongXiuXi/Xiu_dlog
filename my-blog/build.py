#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py -- 零依赖（仅 Python 标准库）静态博客生成器。

用法:
    python build.py                # 构建到 public/
    python build.py --serve        # 构建 + 本地预览 http://127.0.0.1:8000
    python build.py --clean        # 先清空 public/ 再构建
    python build.py --drafts       # 连 draft: true 的文章一起构建
    python build.py --new "标题"   # 新建一篇草稿到 posts/
"""
from __future__ import annotations

import html as html_lib
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
PAGES_DIR = ROOT / "pages"
STATIC_DIR = ROOT / "static"
OUT_DIR = ROOT / "public"
CONFIG_FILE = ROOT / "site.json"

DEFAULT_NAV = [
    {"name": "首页", "path": "index.html"},
    {"name": "归档", "path": "archive.html"},
    {"name": "标签", "path": "tags/index.html"},
    {"name": "搜索", "path": "search.html"},
    {"name": "关于", "path": "about.html"},
]

DEFAULT_CONFIG = {
    "title": "我的博客",
    "author": "站长",
    "description": "",
    "url": "",
    "lang": "zh-CN",
    "footer": "",
    "base_path": "",
    "nav": DEFAULT_NAV,
}


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def esc(text: str) -> str:
    """HTML 转义（不处理引号，保留正文里的 " 可读性）。"""
    return html_lib.escape(str(text), quote=False)


def attr(text: str) -> str:
    """属性值转义（处理引号）。"""
    return html_lib.escape(str(text), quote=True)


def slugify(text: str) -> str:
    """生成 URL / 锚点用的 slug，保留中日韩字符。"""
    text = str(text).strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/\\.,:+":
            out.append("-")
    s = re.sub(r"-+", "-", "".join(out)).strip("-")
    return s or "section"


def parse_date(value):
    if not value:
        return None
    value = str(value).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def as_list(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in re.split(r"[,，、]", str(value)) if x.strip()]


def _scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        return [x.strip().strip("\"'") for x in value[1:-1].split(",") if x.strip()]
    return value


def parse_front_matter(text: str):
    """解析 --- 包裹的极简 front matter（key: value）。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    meta = {}
    body = text
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", text, re.S)
    if m:
        body = text[m.end():]
        for raw in m.group(1).split("\n"):
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = _scalar(val)
    return meta, body


def strip_markdown(text: str) -> str:
    """粗粒度去掉 Markdown 标记，用于摘要、搜索索引和字数统计。"""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s{0,3}>\s?", "", t, flags=re.M)
    t = re.sub(r"[*_~]{1,3}(?=\S)(.+?)(?<=\S)[*_~]{1,3}", r"\1", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"^\s*\|.*\|\s*$", " ", t, flags=re.M)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*\d+[.)]\s+", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n")):
        b = block.strip()
        if not b or b.startswith("#") or b.startswith("```") or b.startswith("|") or b.startswith(">"):
            continue
        return strip_markdown(b)
    return strip_markdown(body)


def reading_minutes(body: str) -> int:
    plain = strip_markdown(body)
    cjk = sum(1 for ch in plain if "\u4e00" <= ch <= "\u9fff")
    words = len(re.findall(r"[A-Za-z0-9]+", plain))
    minutes = cjk / 400.0 + words / 220.0
    return max(1, int(round(minutes)))
# --------------------------------------------------------------------------
# 极简 Markdown 渲染器（块级 + 行内）
# --------------------------------------------------------------------------

FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^\s`~]*)\s*$")
HEADING_RE = re.compile(r"^(\s{0,3})(#{1,6})\s+(.+?)\s*#*\s*$")
HR_RE = re.compile(r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
OL_RE = re.compile(r"^(\s*)(\d{1,9})[.)]\s+(.*)$")
SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
TASK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$", re.S)

CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
AUTOLINK = re.compile(r"<((?:https?://|mailto:)[^\s<>]+)>")
RAW_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"([^\"]*)\")?\s*\)")
LINK_RE = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(\s*([^)\s]+)(?:\s+\"([^\"]*)\")?\s*\)")
STRONG_STAR = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
STRONG_UND = re.compile(r"__(?=\S)(.+?)(?<=\S)__", re.S)
STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
TRIPLE_STAR = re.compile(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*", re.S)
TRIPLE_UND = re.compile(r"___(?=\S)(.+?)(?<=\S)___", re.S)
MARK_RE = re.compile(r"==(?=\S)(.+?)(?<=\S)==", re.S)
EM_STAR = re.compile(r"(?<![\*\w])\*(?=\S)(.+?)(?<=\S)\*(?![\*\w])", re.S)
EM_UND = re.compile(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", re.S)

PH = "\x00%d\x00"
HARD_BREAK = "\x01"


def _safe_url(url: str) -> str:
    url = url.strip().replace('"', "%22").replace("<", "%3C").replace(">", "%3E")
    low = url.lower()
    if low.startswith(("javascript:", "data:text/html", "vbscript:")):
        return "#"
    return url


def unique_id(base: str, used: set) -> str:
    cand = base
    n = 1
    while cand in used:
        cand = "%s-%d" % (base, n)
        n += 1
    used.add(cand)
    return cand


def render_inline(text: str, ctx=None) -> str:
    """行内语法：代码、链接、图片、加粗、斜体、删除线、高亮。"""
    stash = []

    def put(fragment: str) -> str:
        stash.append(fragment)
        return PH % (len(stash) - 1)

    def code_sub(m):
        return put("<code>%s</code>" % esc(m.group(2).strip()))

    def auto_sub(m):
        url = _safe_url(m.group(1))
        return put('<a href="%s" rel="noopener" target="_blank">%s</a>' % (attr(url), esc(m.group(1))))

    text = CODE_SPAN.sub(code_sub, text)
    text = AUTOLINK.sub(auto_sub, text)
    text = RAW_TAG.sub(lambda m: put(m.group(0)), text)

    text = text.replace("  \n", HARD_BREAK + "\n")
    text = esc(text)

    def img_sub(m):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        t = ' title="%s"' % attr(title) if title else ""
        return put('<img src="%s" alt="%s"%s loading="lazy">' % (attr(_safe_url(src)), attr(alt), t))

    def link_sub(m):
        label, href, title = m.group(1), m.group(2), m.group(3)
        t = ' title="%s"' % attr(title) if title else ""
        external = href.startswith(("http://", "https://"))
        rel = ' rel="noopener"' if external else ""
        return put('<a href="%s"%s%s>%s</a>' % (attr(_safe_url(href)), t, rel, label))

    text = IMG_RE.sub(img_sub, text)
    text = LINK_RE.sub(link_sub, text)
    text = TRIPLE_STAR.sub(r"<strong><em>\1</em></strong>", text)
    text = TRIPLE_UND.sub(r"<strong><em>\1</em></strong>", text)
    text = STRONG_STAR.sub(r"<strong>\1</strong>", text)
    text = STRONG_UND.sub(r"<strong>\1</strong>", text)
    text = STRIKE_RE.sub(r"<del>\1</del>", text)
    text = MARK_RE.sub(r"<mark>\1</mark>", text)
    text = EM_STAR.sub(r"<em>\1</em>", text)
    text = EM_UND.sub(r"<em>\1</em>", text)
    text = text.replace(HARD_BREAK, "<br>")

    while PH.strip("\x00") and "\x00" in text:
        replaced = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
        if replaced == text:
            break
        text = replaced
    return text


def _split_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def render_table(header: str, sep: str, rows, ctx) -> str:
    aligns = []
    for cell in _split_row(sep):
        if cell.startswith(":") and cell.endswith(":"):
            aligns.append("center")
        elif cell.endswith(":"):
            aligns.append("right")
        elif cell.startswith(":"):
            aligns.append("left")
        else:
            aligns.append("")

    def cell_html(tag, cell, idx):
        al = aligns[idx] if idx < len(aligns) else ""
        style = ' style="text-align:%s"' % al if al else ""
        return "<%s%s>%s</%s>" % (tag, style, render_inline(cell, ctx), tag)

    head = "".join(cell_html("th", c, i) for i, c in enumerate(_split_row(header)))
    body_rows = []
    for row in rows:
        cells = _split_row(row)
        body_rows.append("".join(cell_html("td", c, i) for i, c in enumerate(cells)))
    out = ["<div class=\"table-wrap\"><table><thead><tr>" + head + "</tr></thead><tbody>"]
    for r in body_rows:
        out.append("<tr>" + r + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _build_list(entries, i, base, ctx):
    tag = "ol" if entries[i][1] else "ul"
    start = entries[i][2]
    attrs = ' start="%d"' % start if tag == "ol" and start != 1 else ""
    parts = ["<%s%s>" % (tag, attrs)]
    while i < len(entries) and entries[i][0] >= base:
        if entries[i][0] > base:
            break
        _indent, _ordered, _num, raw_lines = entries[i]
        raw = "\n".join(raw_lines).strip()
        box = ""
        m = TASK_RE.match(raw)
        if m:
            checked = " checked" if m.group(1).lower() == "x" else ""
            box = '<input type="checkbox" disabled%s> ' % checked
            raw = m.group(2)
        item = "<li>" + box + render_inline(raw, ctx)
        i += 1
        if i < len(entries) and entries[i][0] > base:
            nested, i = _build_list(entries, i, entries[i][0], ctx)
            item += nested
        parts.append(item + "</li>")
    parts.append("</%s>" % tag)
    return "".join(parts), i


def render_blocks(lines, ctx=None) -> str:
    ctx = ctx if ctx is not None else {}
    ctx.setdefault("headings", [])
    ctx.setdefault("ids", set())

    out = []
    i, n = 0, len(lines)

    def is_blank(s):
        return not s.strip()

    while i < n:
        line = lines[i]
        if is_blank(line):
            i += 1
            continue

        # 分隔线（必须先于列表判断，避免 --- 被当列表）
        if HR_RE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # 围栏代码块
        m = FENCE_OPEN.match(line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            fence, lang = m.group(2), m.group(3)
            close_re = re.compile(r"^\s*" + re.escape(fence[0]) + "{%d,}\\s*$" % len(fence))
            buf = []
            i += 1
            while i < n and not close_re.match(lines[i]):
                ln = lines[i]
                if indent and ln[:indent].strip() == "":
                    ln = ln[indent:]
                buf.append(ln)
                i += 1
            i += 1
            cls = ' class="language-%s"' % attr(lang) if lang else ""
            code = esc("\n".join(buf))
            out.append('<div class="code-block"><pre><code%s>%s</code></pre></div>' % (cls, code))
            continue

        # 标题
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(2))
            raw_text = m.group(3)
            hid = unique_id(slugify(strip_markdown(raw_text)), ctx["ids"])
            ctx["headings"].append({"level": level, "text": strip_markdown(raw_text), "id": hid})
            out.append('<h%d id="%s">%s</h%d>' % (level, hid, render_inline(raw_text, ctx), level))
            i += 1
            continue

        # 引用块
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = render_blocks(buf, ctx)
            out.append("<blockquote>" + inner + "</blockquote>")
            continue

        # 表格
        if "|" in line and i + 1 < n and "|" in lines[i + 1] and SEP_RE.match(lines[i + 1]):
            header = line
            sep = lines[i + 1]
            i += 2
            rows = []
            while i < n and not is_blank(lines[i]) and "|" in lines[i]:
                rows.append(lines[i])
                i += 1
            out.append(render_table(header, sep, rows, ctx))
            continue

        # 列表
        if UL_RE.match(line) or OL_RE.match(line):
            entries = []
            while i < n:
                cur = lines[i]
                mu = UL_RE.match(cur)
                mo = None if mu else OL_RE.match(cur)
                if mu:
                    entries.append([len(mu.group(1).expandtabs(4)), False, 1, [mu.group(2)]])
                elif mo:
                    entries.append([len(mo.group(1).expandtabs(4)), True,
                                    int(mo.group(2)), [mo.group(3)]])
                elif is_blank(cur):
                    if i + 1 < n and (UL_RE.match(lines[i + 1]) or OL_RE.match(lines[i + 1])):
                        i += 1
                        continue
                    break
                elif entries and (cur.startswith("  ") or cur.startswith("\t")):
                    entries[-1][3].append(cur.strip())
                else:
                    break
                i += 1
            html, _ = _build_list(entries, 0, entries[0][0], ctx)
            out.append(html)
            continue

        # 原始 HTML 块
        if line.lstrip().startswith("<") and RAW_TAG.match(line.lstrip()):
            buf = []
            while i < n and not is_blank(lines[i]):
                buf.append(lines[i])
                i += 1
            out.append("\n".join(buf))
            continue

        # 段落
        buf = []
        while i < n and not is_blank(lines[i]):
            cur = lines[i]
            if buf and (FENCE_OPEN.match(cur) or HEADING_RE.match(cur) or HR_RE.match(cur)
                        or cur.lstrip().startswith(">") or UL_RE.match(cur) or OL_RE.match(cur)):
                break
            if buf and "|" in cur and i + 1 < n and SEP_RE.match(lines[i + 1]):
                break
            buf.append(cur)
            i += 1
        out.append("<p>" + render_inline("\n".join(buf), ctx) + "</p>")

    return "\n".join(out)


def render_markdown(text: str):
    """返回 (html, headings)。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    ctx = {"headings": [], "ids": set()}
    body = render_blocks(text.split("\n"), ctx)
    return body, ctx["headings"]
# --------------------------------------------------------------------------
# 站点装配
# --------------------------------------------------------------------------

HEAD_SCRIPT = ('<script>(function(){try{var t=localStorage.getItem("theme");'
               'if(!t){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}'
               'document.documentElement.dataset.theme=t;}catch(e){}})();</script>')

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

LAYOUT = """<!DOCTYPE html>
<html lang="%(lang)s" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
%(canonical)s
<meta property="og:type" content="%(ogtype)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1115" media="(prefers-color-scheme: dark)">
<link rel="stylesheet" href="%(root)sstyle.css">
<link rel="alternate" type="application/rss+xml" title="%(sitename)s" href="%(root)sfeed.xml">
%(headscript)s
</head>
<body>
<a class="skip" href="#main">跳到正文</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="%(root)sindex.html">%(sitename)s</a>
    <nav class="nav">%(nav)s</nav>
    <button class="theme-toggle" id="theme-toggle" type="button" aria-label="切换深浅色">
      <svg class="icon-sun" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1"/></svg>
      <svg class="icon-moon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>
    </button>
  </div>
</header>
<main id="main" class="wrap">
%(content)s
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>&copy; %(year)s %(author)s%(footer)s</p>
    <p class="footer-links"><a href="%(root)sfeed.xml">RSS</a><span>·</span><a href="%(root)sarchive.html">归档</a><span>·</span><a href="%(root)ssitemap.xml">站点地图</a></p>
  </div>
</footer>
<script src="%(root)sapp.js" defer></script>
</body>
</html>
"""


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        except Exception as exc:  # noqa: BLE001
            print("! site.json 解析失败，已使用默认配置:", exc)
    if not cfg.get("nav"):
        cfg["nav"] = DEFAULT_NAV
    return cfg


def load_posts(cfg, include_drafts=False):
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for path in sorted(POSTS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        draft = str(meta.get("draft", "")).lower() in ("true", "1", "yes", "on")
        if draft and not include_drafts:
            continue
        stem = path.stem
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
        date = parse_date(meta.get("date"))
        if date is None and m:
            try:
                date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                date = None
        if date is None:
            date = datetime.fromtimestamp(path.stat().st_mtime)
        slug_source = meta.get("slug") or (m.group(4) if m else stem)
        slug = slugify(slug_source)
        body_html, headings = render_markdown(body)
        summary = str(meta.get("summary") or "").strip() or first_paragraph(body)
        summary = summary[:160]
        posts.append({
            "slug": slug,
            "title": str(meta.get("title") or slug_source).strip(),
            "date": date,
            "tags": as_list(meta.get("tags")),
            "summary": summary,
            "draft": draft,
            "html": body_html,
            "headings": headings,
            "minutes": reading_minutes(body),
            "text": strip_markdown(body),
            "source": path.name,
        })
    posts.sort(key=lambda p: (p["date"], p["title"]), reverse=True)
    return posts


def tag_slug(name: str) -> str:
    return slugify(name)


def render_nav(cfg, root, active):
    items = []
    for item in cfg["nav"]:
        path = str(item.get("path", "#"))
        cls = ' class="active"' if path == active else ""
        items.append('<a href="%s%s"%s>%s</a>' % (root, attr(path), cls, esc(item.get("name", path))))
    return "".join(items)


def layout(cfg, root, title, content, description=None, canonical="", ogtype="website", active=""):
    sitename = cfg["title"]
    full_title = title if title == sitename else ("%s | %s" % (title, sitename))
    desc = description if description is not None else cfg["description"]
    canon = '    <link rel="canonical" href="%s">\n' % attr(canonical) if canonical else ""
    return LAYOUT % {
        "lang": attr(cfg["lang"]),
        "title": esc(full_title),
        "description": attr(desc),
        "canonical": canon,
        "ogtype": ogtype,
        "root": root,
        "sitename": esc(sitename),
        "nav": render_nav(cfg, root, active),
        "content": content,
        "year": datetime.now().year,
        "author": esc(cfg["author"]),
        "footer": " " + esc(cfg["footer"]) if cfg["footer"] else "",
        "headscript": HEAD_SCRIPT,
    }


def date_str(dt):
    return dt.strftime("%Y-%m-%d")


def rfc822(dt, tz="+0800"):
    return "%s, %02d %s %04d %02d:%02d:%02d %s" % (
        DAYS[dt.weekday()], dt.day, MONTHS[dt.month - 1], dt.year,
        dt.hour, dt.minute, dt.second, tz)


def tag_chips(tags, root):
    if not tags:
        return ""
    chips = "".join('<a class="chip" href="%stags/%s.html">%s</a>'
                    % (root, attr(tag_slug(t)), esc(t)) for t in tags)
    return '<div class="chips">%s</div>' % chips


def post_meta_line(post, root):
    return ('<div class="post-meta"><time datetime="%s">%s</time><span>·</span>'
            '<span>约 %d 分钟</span>%s</div>'
            % (date_str(post["date"]), date_str(post["date"]), post["minutes"],
               tag_chips(post["tags"], root)))


def render_toc(headings):
    nodes = [h for h in headings if h["level"] in (2, 3)]
    if len(nodes) < 2:
        return ""
    items = []
    for h in nodes:
        cls = ' class="toc-h3"' if h["level"] == 3 else ""
        items.append('<li%s><a href="#%s">%s</a></li>' % (cls, attr(h["id"]), esc(h["text"])))
    return ('<details class="toc" open><summary>目录</summary><ul>%s</ul></details>'
            % "".join(items))


def build_index(cfg, root, posts):
    items = []
    for p in posts:
        items.append(
            '<li class="post-item">'
            '<a class="post-link" href="%sposts/%s.html"><h2>%s</h2></a>'
            '%s<p class="summary">%s</p></li>'
            % (root, attr(p["slug"]), esc(p["title"]), post_meta_line(p, root), esc(p["summary"])))
    hero = ('<section class="hero"><h1>%s</h1>%s</section>'
            % (esc(cfg["title"]),
               '<p class="hero-desc">%s</p>' % esc(cfg["description"]) if cfg["description"] else ""))
    if not items:
        list_html = '<p class="empty">还没有文章。在 <code>posts/</code> 里放一个 <code>*.md</code> 文件，然后运行 <code>python build.py</code>。</p>'
    else:
        list_html = '<ul class="post-list">%s</ul>' % "".join(items)
    return layout(cfg, root, cfg["title"], hero + list_html, active="index.html")


def build_post(cfg, post, prev_post, next_post, posts_by_slug):
    root = "../"
    toc = render_toc(post["headings"])
    body = ('<article class="post">'
            '<header class="post-header"><h1>%s</h1>%s</header>'
            '%s<div class="post-body">%s</div></article>'
            % (esc(post["title"]), post_meta_line(post, root), toc, post["html"]))
    navs = []
    if prev_post:
        navs.append('<a class="pn prev" href="%sposts/%s.html"><span>上一篇</span>%s</a>'
                    % (root, attr(prev_post["slug"]), esc(prev_post["title"])))
    if next_post:
        navs.append('<a class="pn next" href="%sposts/%s.html"><span>下一篇</span>%s</a>'
                    % (root, attr(next_post["slug"]), esc(next_post["title"])))
    body += '<nav class="post-nav">%s</nav>' % "".join(navs)
    canonical = ""
    if cfg.get("url"):
        canonical = cfg["url"].rstrip("/") + "/posts/" + quote(post["slug"]) + ".html"
    return layout(cfg, root, post["title"], body, description=post["summary"],
                  canonical=canonical, ogtype="article")


def build_archive(cfg, posts):
    if not posts:
        return layout(cfg, "", "归档", '<h1>归档</h1><p class="empty">暂无文章。</p>', active="archive.html")
    groups = {}
    for p in posts:
        groups.setdefault(p["date"].year, []).append(p)
    sections = []
    for year in sorted(groups, reverse=True):
        rows = []
        for p in groups[year]:
            rows.append('<li><time datetime="%s">%s</time><a href="posts/%s.html">%s</a></li>'
                        % (date_str(p["date"]), p["date"].strftime("%m-%d"),
                           attr(p["slug"]), esc(p["title"])))
        sections.append('<section class="year-group"><h2>%d <span class="count">%d 篇</span></h2><ul>%s</ul></section>'
                        % (year, len(groups[year]), "".join(rows)))
    content = '<h1>归档</h1>' + "".join(sections)
    return layout(cfg, "", "归档", content, active="archive.html")


def build_tags_index(cfg, posts):
    counts = {}
    for p in posts:
        for t in p["tags"]:
            counts[t] = counts.get(t, 0) + 1
    if not counts:
        content = '<h1>标签</h1><p class="empty">还没有标签。在文章 front matter 里加 <code>tags: 随笔, 技术</code>。</p>'
    else:
        cloud = "".join('<a class="chip chip-lg" href="tags/%s.html">%s<span class="n">%d</span></a>'
                        % (attr(tag_slug(t)), esc(t), n)
                        for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        content = '<h1>标签</h1><div class="tag-cloud">%s</div>' % cloud
    return layout(cfg, "", "标签", content, active="tags/index.html")


def build_tag_page(cfg, tag, posts):
    root = "../"
    items = "".join('<li class="post-item"><a class="post-link" href="%sposts/%s.html"><h2>%s</h2></a>%s</li>'
                    % (root, attr(p["slug"]), esc(p["title"]),
                       '<div class="post-meta"><time>%s</time><span>·</span><span>约 %d 分钟</span></div>'
                       % (date_str(p["date"]), p["minutes"]))
                    for p in posts)
    content = ('<h1>标签：%s</h1><p class="hub-back"><a href="%sindex.html">全部标签</a></p><ul class="post-list">%s</ul>'
               % (esc(tag), root, items))
    return layout(cfg, root, "标签：" + tag, content, active="tags/index.html")


def build_search(cfg):
    content = """<h1>搜索</h1>
<form class="search-form" role="search" onsubmit="return false">
  <input id="search-input" type="search" placeholder="输入关键词，回车或直接输入即可筛选…" autocomplete="off" autofocus>
</form>
<p class="search-hint" id="search-hint"></p>
<ul class="post-list" id="search-results"></ul>"""
    return layout(cfg, "", "搜索", content, active="search.html")


def build_about(cfg):
    path = PAGES_DIR / "about.md"
    if path.exists():
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        html, _ = render_markdown(body)
        title = str(meta.get("title") or "关于")
        content = '<article class="post"><div class="post-body">%s</div></article>' % html
        return layout(cfg, "", title, content, active="about.html")
    content = '<h1>关于</h1><p class="empty">把 <code>pages/about.md</code> 填上你的自我介绍。</p>'
    return layout(cfg, "", "关于", content, active="about.html")


def build_404(cfg):
    content = ('<div class="notfound"><h1>404</h1><p>这个页面不存在。</p>'
               '<p><a class="btn" href="index.html">回到首页</a></p></div>')
    return layout(cfg, "", "页面不存在", content)


def build_feed(cfg, posts, limit=20):
    site = cfg.get("url", "").rstrip("/")
    tz = cfg.get("timezone", "+0800")
    items = []
    for p in posts[:limit]:
        link = "%s/posts/%s.html" % (site, quote(p["slug"])) if site else "posts/%s.html" % p["slug"]
        items.append(
            "<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>"
            "<pubDate>%s</pubDate><description>%s</description></item>"
            % (esc(p["title"]), esc(link), esc(link), rfc822(p["date"], tz), esc(p["summary"])))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0"><channel>'
           "<title>%s</title><link>%s</link><description>%s</description>"
           "<language>%s</language><lastBuildDate>%s</lastBuildDate>%s</channel></rss>"
           % (esc(cfg["title"]), esc(site or ""), esc(cfg["description"]),
              attr(cfg["lang"]), rfc822(datetime.now(), tz), "".join(items)))
    return xml


def build_sitemap(cfg, posts):
    site = cfg.get("url", "").rstrip("/")
    if not site:
        return None
    urls = ["", "/archive.html", "/tags/index.html", "/search.html", "/about.html"]
    entries = ['<url><loc>%s%s</loc></url>' % (esc(site), p) for p in urls]
    for p in posts:
        entries.append('<url><loc>%s/posts/%s.html</loc><lastmod>%s</lastmod></url>'
                       % (esc(site), quote(p["slug"]), date_str(p["date"])))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>'
            % "".join(entries))


def build_search_index(posts):
    data = []
    for p in posts:
        data.append({
            "title": p["title"],
            "url": "posts/%s.html" % p["slug"],
            "date": date_str(p["date"]),
            "tags": p["tags"],
            "text": p["text"][:3000],
        })
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


ABS_ATTR = re.compile(r'(\b(?:href|src)=")/(?!/)')


def apply_base(markup: str, base: str) -> str:
    """把根绝对路径 /x 前置 base_path，适配 username.github.io/repo/ 这类子路径部署。"""
    base = (base or "").rstrip("/")
    if not base:
        return markup
    return ABS_ATTR.sub(lambda m: m.group(1) + base + "/", markup)


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def build(include_drafts=False, clean=False):
    started = time.time()
    cfg = load_config()
    if clean and OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    posts = load_posts(cfg, include_drafts)

    write(OUT_DIR / "index.html", build_index(cfg, "", posts))
    for idx, p in enumerate(posts):
        prev_post = posts[idx + 1] if idx + 1 < len(posts) else None
        next_post = posts[idx - 1] if idx > 0 else None
        write(OUT_DIR / "posts" / (p["slug"] + ".html"),
              build_post(cfg, p, prev_post, next_post, None))
    write(OUT_DIR / "archive.html", build_archive(cfg, posts))
    write(OUT_DIR / "tags" / "index.html", build_tags_index(cfg, posts))
    tag_map = {}
    for p in posts:
        for t in p["tags"]:
            tag_map.setdefault(t, []).append(p)
    for tag, group in tag_map.items():
        write(OUT_DIR / "tags" / (tag_slug(tag) + ".html"), build_tag_page(cfg, tag, group))
    write(OUT_DIR / "search.html", build_search(cfg))
    write(OUT_DIR / "about.html", build_about(cfg))
    write(OUT_DIR / "404.html", build_404(cfg))
    write(OUT_DIR / "feed.xml", build_feed(cfg, posts))
    write(OUT_DIR / "search.json", build_search_index(posts))
    sitemap = build_sitemap(cfg, posts)
    if sitemap:
        write(OUT_DIR / "sitemap.xml", sitemap)
    write(OUT_DIR / ".nojekyll", "")

    if STATIC_DIR.exists():
        for item in STATIC_DIR.iterdir():
            target = OUT_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    base = cfg.get("base_path", "")
    if base:
        for html_file in OUT_DIR.rglob("*.html"):
            text = html_file.read_text(encoding="utf-8")
            html_file.write_text(apply_base(text, base), encoding="utf-8", newline="\n")

    elapsed = time.time() - started
    print("构建完成: %d 篇文章, %d 个标签, 用时 %.2fs -> %s"
          % (len(posts), len(tag_map), elapsed, OUT_DIR))
    if not cfg.get("url"):
        print("提示: site.json 里的 url 还没填，RSS/sitemap/绝对链接会缺失。上线后填上域名再构建一次。")
    return posts


def new_post(title):
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    slug = slugify(title) or "untitled"
    path = POSTS_DIR / ("%s-%s.md" % (now.strftime("%Y-%m-%d"), slug))
    if path.exists():
        print("已存在:", path)
        return None
    body = ("---\n"
            "title: %s\n"
            "date: %s\n"
            "tags: 随笔\n"
            "summary: \n"
            "draft: true\n"
            "---\n\n"
            "在这里开始写正文。\n\n"
            "## 小标题\n\n"
            "写完把 front matter 里的 `draft: true` 删掉（或改成 false），再运行 `python build.py`。\n"
            % (title, now.strftime("%Y-%m-%d %H:%M")))
    path.write_text(body, encoding="utf-8", newline="\n")
    print("已创建:", path)
    return path


def serve(port=8000):
    import http.server
    import socketserver
    import webbrowser

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(OUT_DIR), **kw)

        def log_message(self, fmt, *args):
            pass

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = "http://127.0.0.1:%d/" % port
        print("本地预览: %s  (Ctrl+C 退出)" % url)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")


def main(argv):
    args = [a for a in argv[1:]]
    if "--new" in args:
        idx = args.index("--new")
        title = args[idx + 1] if idx + 1 < len(args) else "无标题"
        new_post(title)
        return 0
    clean = "--clean" in args
    include_drafts = "--drafts" in args
    build(include_drafts=include_drafts, clean=clean)
    if "--serve" in args:
        port = 8000
        for i, a in enumerate(args):
            if a == "--port" and i + 1 < len(args):
                port = int(args[i + 1])
        serve(port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))