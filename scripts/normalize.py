#!/usr/bin/env python3
"""Deterministic normalization — the GymSpellCheck layer, ported.

Runs BEFORE the model. Fixes SPELLING only, never meaning (Blood Rule).
Input: raw entry text (one day). Output: {date?, programs: [{name, text}]}.

Typo classes from the corpus audit (docs/wod-audit-2026-10-16.md and
COACH-GRAMMAR-AND-IR.md §2.1): structural typos that broke the old regex
parser silently. Every rule here is evidenced by a dated corpus line.
"""
from __future__ import annotations
import re
import sys
import json

# (pattern, replacement, evidence)
STRUCTURAL = [
    (r"\bwam up\b", "warm up", "Sep 19"),
    (r"\b(\d)\s*aets\b", r"\1 sets", "Aug 5 '3 aets'"),
    (r"\bssets\b", "sets", "Aug 31 HYROX"),
    (r"(\d)\s*sdec\b", r"\1sec", "Sep 14/7 '15sdec'"),
    (r"(\d)\s*aec\b", r"\1sec", "Jul 23 '30aec'"),
    (r"\(\s*(\d+)\s*min\s*=\s*\)", r"(\1min)", "Sep 19 'prehab (5min=)'"),
    (r"^(\w[\w /]*?)\s+8(\d)min\)\s*$", r"\1 (\2min)", "Aug 11 'prehab 85min)'"),
    (r"^(\w[\w /]*?)\s+(\d+)min\)\s*$", r"\1 (\2min)", "Aug 13 'strength/skill 16min)'"),
    (r"^(\w[\w /]*?)\s+\((\d+)min\s*$", r"\1 (\2min)", "Sep 7 'metcon (15min'"),
    (r"(\d+sec on)\s*/\s*(\d+)sec on\b", r"\1/\2sec off", "Jul 14 '45sec on/15sec on'"),
]

UNICODE = [
    ("´", "'"), ("’", "'"), ("„", '"'), ("“", '"'),
    ("”", '"'), ("‍", ""), (" ", " "),
]


def normalize_lines(text: str) -> list[str]:
    for a, b in UNICODE:
        text = text.replace(a, b)
    out = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        line = re.sub(r"^/\s*", "", line)  # stray leading slash
        for pat, rep, _why in STRUCTURAL:
            line = re.sub(pat, rep, line, flags=re.IGNORECASE)
        out.append(line)
    # drop leading/trailing empties, collapse doubles
    cleaned, prev_empty = [], True
    for l in out:
        if l == "" and prev_empty:
            continue
        cleaned.append(l)
        prev_empty = (l == "")
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return cleaned


def split_programs(lines: list[str]) -> list[dict]:
    """Split at the line == 'hyrox' (case-insensitive) into class + hyrox."""
    programs, cur, name = [], [], "class"
    for l in lines:
        if l.strip().lower() == "hyrox":
            if cur:
                programs.append({"name": name, "text": "\n".join(cur).strip()})
            cur, name = [], "hyrox"
            continue
        cur.append(l)
    if cur:
        programs.append({"name": name, "text": "\n".join(cur).strip()})
    return programs


def normalize_entry(text: str) -> dict:
    lines = normalize_lines(text)
    return {"programs": split_programs(lines)}


if __name__ == "__main__":
    text = sys.stdin.read()
    print(json.dumps(normalize_entry(text), indent=2, ensure_ascii=False))
