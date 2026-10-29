#!/usr/bin/env python3
"""Deterministic validation — the model is never trusted blind.

Checks (WOD-RESOLVER-SERVICE.md §1 step 5):
  1. JSON schema (schema/ir.schema.json)
  2. every Block has >= 1 Segment (schema enforces) and carries raw text
  3. pair loads: m >= f, else ERROR (resolver should swap + issue)
  4. clock arithmetic vs block minutes (when minutes known, +60s grace):
       interval: rounds x (work+rest) <= minutes*60 + 60
       emom:     everySec x rounds    <= minutes*60 + 60
  5. rotate-station intervals/emoms: rounds %% station-slot count == 0
  6. COVERAGE: every non-empty input line appears in some raw/text field.
     The single best guard against silent drops ('*' lines, into, HYROX).
  7. confidence = 1 - weighted issues
Exit 0 = publishable; exit 1 = must not publish.
Usage: validate.py <day.json> <raw.txt>
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("pip install jsonschema --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "ir.schema.json").read_text())


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def walk(obj, key):
    """Yield every value of `key` anywhere in the tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                yield v
            else:
                yield from walk(v, key)
    elif isinstance(obj, list):
        for it in obj:
            yield from walk(it, key)


def movements(obj):
    if isinstance(obj, dict):
        if "qty" in obj and "load" in obj and "text" in obj:
            yield obj
        for v in obj.values():
            yield from movements(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from movements(it)


def station_slots(seg) -> int:
    """Rotation slot count: one slot per station occupancy (repeat multiplies;
    sub-stations a)/b) happen INSIDE one on-window — fixed work + max-in-
    remaining, the house station bundle — so they never multiply slots)."""
    slots = 0
    for st in seg.get("work", {}).get("stations", []) or []:
        slots += st.get("repeat", 1)
    return slots


def validate(day: dict, raw_text: str):
    errors, issues = [], list(day.get("resolver", {}).get("issues", []))

    # 1 - schema (newest validator this environment has)
    VCls = (getattr(jsonschema, "Draft202012Validator", None)
            or getattr(jsonschema, "Draft7Validator", None)
            or jsonschema.Draft4Validator)
    for e in VCls(SCHEMA).iter_errors(day):
        errors.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:120]}")

    # 3 - pair loads m >= f  (box heights in cm included: 60/50)
    for mv in movements(day):
        ld = mv.get("load", {})
        if ld.get("mode") == "pair" and ld.get("m") is not None and ld.get("f") is not None:
            if ld["m"] < ld["f"]:
                errors.append(f"load pair m<f on '{mv.get('text','?')}' — swap + issue")
    # qty without value is lawful ONLY under a segment scheme (21-15-9 family:
    # the scheme IS the row's value); anywhere else it is an issue.
    for prog in day.get("programs", []):
        for blk in prog.get("blocks", []):
            for seg in blk.get("segments", []):
                if seg.get("scheme"):
                    continue
                for mv in movements(seg):
                    q = mv.get("qty", {})
                    if q.get("mode") in ("reps", "cal", "m", "sec") and q.get("value") is None and not q.get("range"):
                        issues.append(f"qty mode {q.get('mode')} without value: '{mv.get('text','?')}'")

    # 4+5 - clock arithmetic per block
    for prog in day.get("programs", []):
        for blk in prog.get("blocks", []):
            budget = blk["minutes"] * 60 + 60 if blk.get("minutes") else None
            for seg in blk.get("segments", []):
                ck = seg.get("clock", {})
                t = ck.get("type")
                if t == "interval" and ck.get("rounds"):
                    span = ck["rounds"] * (ck["workSec"] + ck["restSec"])
                    if budget and span > budget:
                        errors.append(f"block {blk['ordinal']} interval {ck['rounds']}x({ck['workSec']}+{ck['restSec']})s = {span}s > {budget}s")
                    slots = station_slots(seg)
                    if ck.get("stationMode") == "rotate" and slots and ck["rounds"] % slots:
                        errors.append(f"block {blk['ordinal']} rotate: rounds {ck['rounds']} %% station slots {slots} != 0")
                if t == "emom" and ck.get("rounds"):
                    span = ck["everySec"] * ck["rounds"]
                    if budget and span > budget:
                        errors.append(f"block {blk['ordinal']} emom {ck['rounds']}x{ck['everySec']}s = {span}s > {budget}s")
                    slots = station_slots(seg)
                    if slots > 1 and ck["rounds"] % slots:
                        issues.append(f"block {blk['ordinal']} emom rounds {ck['rounds']} not divisible by {slots} stations")
                if t == "amrap" and budget and ck.get("sec", 0) > budget:
                    errors.append(f"block {blk['ordinal']} amrap {ck['sec']}s > {budget}s")

    # 6 - coverage
    covered = " \n ".join(
        list(walk(day, "raw")) + list(walk(day, "text")) + list(walk(day, "title"))
        + list(walk(day, "label")) + list(walk(day, "focus"))
        + [day.get("hashtag") or "", "rpe" + (day.get("rpe") or "")]
        + list(walk(day, "notes_joined"))
    )
    for blk_notes in walk(day, "note"):
        covered += " \n " + blk_notes
    for prog in day.get("programs", []):
        for blk in prog.get("blocks", []):
            covered += " \n " + " \n ".join(blk.get("notes", []))
            for sc in blk.get("scale", []):
                covered += " \n " + " ".join(sc.get("options", []))
    covered_n = norm(covered)
    for line in raw_text.splitlines():
        ln = norm(line)
        if not ln or ln == "hyrox":
            continue
        if ln not in covered_n:
            errors.append(f"coverage: input line not represented: '{line.strip()}'")

    # 7 - confidence
    confidence = max(0.0, 1.0 - 0.3 * len(errors) - 0.05 * len(issues))
    return errors, issues, round(confidence, 2)


def main():
    day = json.loads(Path(sys.argv[1]).read_text())
    raw = Path(sys.argv[2]).read_text()
    errors, issues, confidence = validate(day, raw)
    for e in errors:
        print(f"ERROR  {e}")
    for i in issues:
        print(f"issue  {i}")
    print(f"confidence {confidence}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
