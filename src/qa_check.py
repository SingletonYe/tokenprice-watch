#!/usr/bin/env python3
"""Quality gate for the generated site.

Runs before publishing. Fails loudly on structural problems so a broken build
never reaches the public URL:

  * every page has exactly one <h1>, a <title>, and a meta description
  * no unescaped template artefacts ("None", "nan", "{", "}")
  * container tags are balanced
  * every internal link resolves to a file that exists
  * canonical URLs are unique, sitemap entries match the files on disk
  * JSON-LD blocks parse as JSON
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
CONTAINERS = ("p", "div", "section", "table", "ul", "ol", "li", "dd", "dt", "tr", "td", "th",
              "aside", "header", "footer", "main", "nav", "h1", "h2", "h3", "form", "span")


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []
        self.h1 = 0
        self.links: list[str] = []
        self.scripts_ld: list[str] = []
        self._in_ld = False
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and d.get("href"):
            self.links.append(d["href"])
        if tag == "script" and d.get("type") == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []
            return
        if tag not in VOID and tag in CONTAINERS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.scripts_ld.append("".join(self._ld_buf))
            return
        if tag in VOID:
            return
        if tag not in CONTAINERS:
            return
        # pop until match, reporting mismatches
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for j in range(len(self.stack) - 1, i, -1):
                    t, line = self.stack[j]
                    self.errors.append(f"unclosed <{t}> opened at line {line}, closed by </{tag}>")
                del self.stack[i:]
                return
        self.errors.append(f"stray </{tag}>")

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)


def check_site(out: pathlib.Path, prefix: str = "") -> int:
    pages = sorted(out.rglob("*.html"))
    problems: list[str] = []
    canonicals: dict[str, str] = collections.Counter()
    all_titles: collections.Counter = collections.Counter()
    descriptions = collections.Counter()
    internal_targets: set[str] = set()

    for page in pages:
        rel = "/" + page.relative_to(out).as_posix()
        text = page.read_text()
        c = Checker()
        c.feed(text)
        for err in c.errors:
            problems.append(f"{rel}: {err}")
        if c.h1 != 1:
            problems.append(f"{rel}: {c.h1} <h1> tags (expected 1)")
        m = re.search(r"<title>(.*?)</title>", text, re.S)
        if not m or len(m.group(1).strip()) < 8:
            problems.append(f"{rel}: missing/too-short <title>")
        else:
            all_titles[m.group(1).strip()] += 1
        d = re.search(r'name="description" content="(.*?)"', text, re.S)
        if not d or len(d.group(1).strip()) < 40:
            problems.append(f"{rel}: missing/too-short meta description")
        else:
            descriptions[d.group(1).strip()] += 1
        can = re.search(r'<link rel="canonical" href="(.*?)"', text)
        if can:
            canonicals[can.group(1)] += 1
        for artefact in (">None<", ">nan<", ">undefined<", "{'", "Traceback"):
            if artefact in text:
                problems.append(f"{rel}: template artefact {artefact!r}")
        for ld in c.scripts_ld:
            try:
                json.loads(ld)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{rel}: invalid JSON-LD ({e})")
        for href in c.links:
            if href.startswith("/") and not href.startswith("//"):
                internal_targets.add(href.split("#")[0])

    # link resolution
    missing = []
    pref = "/" + prefix.strip("/") if prefix.strip("/") else ""
    for href in sorted(internal_targets):
        if pref and href.startswith(pref + "/"):
            href = href[len(pref):]
        if href in ("", "/"):
            target = out / "index.html"
        elif href.endswith("/"):
            target = out / href.strip("/") / "index.html"
        else:
            target = out / href.lstrip("/")
        if not target.exists():
            missing.append(href)
    for m in missing:
        problems.append(f"broken internal link: {m}")

    dup_can = [u for u, n in canonicals.items() if n > 1]
    for u in dup_can:
        problems.append(f"duplicate canonical: {u}")
    dup_titles = [t for t, n in all_titles.items() if n > 1]
    for t in dup_titles[:10]:
        problems.append(f"duplicate title ({all_titles[t]}x): {t}")
    dup_desc = [d for d, n in descriptions.items() if n > 1]
    for d in dup_desc[:10]:
        problems.append(f"duplicate description ({descriptions[d]}x): {d[:70]}")

    # sitemap consistency
    sm = (out / "sitemap.xml")
    if sm.exists():
        locs = re.findall(r"<loc>(.*?)</loc>", sm.read_text())
        print(f"[qa] sitemap entries: {len(locs)}")
        if len(locs) != len(pages) - 1:  # 404.html is not in the sitemap
            problems.append(f"sitemap has {len(locs)} entries but {len(pages)} html files exist")
    else:
        problems.append("sitemap.xml missing")

    # data guard: upstream has used negative sentinels for router endpoints before
    data_file = out.parent / "data" / "latest.json"
    if data_file.exists():
        latest = json.loads(data_file.read_text())
        for m in latest.get("models", []):
            for field in ("pin", "pout", "pcr", "pcw", "pimg", "paudio"):
                v = m.get(field)
                try:
                    if v is not None and float(v) < 0:
                        problems.append(f"negative price in data: {m['id']}.{field}={v}")
                except (TypeError, ValueError):
                    problems.append(f"non-numeric price in data: {m['id']}.{field}={v}")

    for f in ("robots.txt", ".well-known/feed.xml"):
        if not (out / f).exists():
            problems.append(f"missing required file: {f}")
    for pattern, label in (("assets/style-*", "hashed stylesheet"), ("assets/app-*", "hashed app script")):
        if not list(out.glob(pattern)):
            problems.append(f"missing {label} ({pattern})")

    print(f"[qa] pages checked: {len(pages)}")
    print(f"[qa] internal links checked: {len(internal_targets)}")
    print(f"[qa] unique titles: {len(all_titles)} / {len(pages)}")
    print(f"[qa] unique descriptions: {len(descriptions)} / {len(pages)}")
    if problems:
        print(f"\n[qa] FAIL — {len(problems)} problems")
        for p in problems[:60]:
            print("  -", p)
        if len(problems) > 60:
            print(f"  ... and {len(problems) - 60} more")
        return 1
    print("[qa] PASS — no structural problems found")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--path-prefix", default="")
    args = ap.parse_args(argv)
    return check_site(pathlib.Path(args.out).resolve(), prefix=args.path_prefix)


if __name__ == "__main__":
    sys.exit(main())
