#!/usr/bin/env python3
"""Fetch the WOD page and emit normalized entries, newest first.

UNTESTED against the live page from this environment (egress blocked until the
domain is allowed for cloud sessions). The selectors are proven from the
27.10 browser-pane extraction: CMS item = `.list_faq_list.w-dyn-item`,
date = `h3.is_acc`, body = `.w-richtext` (innerHTML, <br>/<p> as line breaks).

Usage: fetch.py [--html FILE]   (reads a saved page for offline testing)
Output: JSON [{date: "2026-10-29", text: "..."}], deduped by date.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sys
import urllib.request

URL = "https://www.12nullacht-crossfit.com/wod"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def fetch_html() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "wod-resolver/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&amp;", "&").replace("&nbsp;", " ").replace("&quot;", '"')
    html = html.replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
    return html


def parse_date(s: str) -> str | None:
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()


def extract(html: str) -> list[dict]:
    entries, seen = [], set()
    # CMS items: h3 (date) followed by the rich-text body.
    for m in re.finditer(
            r'<h3[^>]*class="[^"]*is_acc[^"]*"[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*class="[^"]*is_acc|$)',
            html, re.S):
        date = parse_date(strip_tags(m.group(1)))
        if not date or date in seen:
            continue
        body_html = re.search(r'class="[^"]*w-richtext[^"]*"[^>]*>(.*)', m.group(2), re.S)
        body = strip_tags(body_html.group(1) if body_html else m.group(2))
        lines = [re.sub(r"\s+", " ", l).strip() for l in body.splitlines()]
        text = "\n".join([l for l in lines if l])
        if text:
            seen.add(date)
            entries.append({"date": date, "text": text})
    return entries


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html")
    a = ap.parse_args()
    html = open(a.html, encoding="utf-8").read() if a.html else fetch_html()
    json.dump(extract(html), sys.stdout, indent=2, ensure_ascii=False)
    print()
