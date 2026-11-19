#!/usr/bin/env python3
"""Coverage of the diagnostic catalogue by tests (docs/06-diagnostics.md 6.1, WP-2 gate).

For every catalogue row tagged ``C`` (core fault injection test) it looks for a Rust test named
``diag_<L>_<CC>_<FFF>`` (e.g. ``diag_1_06_001_vmot_stuck_on``) under ``firmware-rs/``; rows tagged
``S`` are covered by the table-driven Swift tests (every row), ``P`` by the protocol tests, ``B nn``
and ``H`` by WP-3 (bench / simulated board).

    tools/diag_coverage.py            print the report, exit 0
    tools/diag_coverage.py --strict   exit 1 when a row tagged C has no diag_<code> test (WP-2 acceptance)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_diag  # noqa: E402

ROOT = gen_diag.ROOT


def tests_found():
    found = {}
    pat = re.compile(r"fn (diag_([0-9a-f])_([0-9a-f]{2})_([0-9a-f]{3}))\w*\s*\(")
    base = os.path.join(ROOT, "firmware-rs")
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in ("target", ".git")]
        for f in files:
            if not f.endswith(".rs"):
                continue
            text = open(os.path.join(dirpath, f), encoding="utf-8").read()
            for m in pat.finditer(text):
                code = "%s-%s-%s" % (m.group(2).upper(), m.group(3).upper(), m.group(4).upper())
                found.setdefault(code, []).append(os.path.relpath(os.path.join(dirpath, f), ROOT) + "::" + m.group(1))
    return found


def main(argv):
    rows = gen_diag.read_csv()
    found = tests_found()
    unknown = sorted(set(found) - {r["code"] for r in rows})
    c_rows = [r for r in rows if "C" in r["test"].split()]
    missing = [r for r in c_rows if r["code"] not in found]
    covered = [r for r in c_rows if r["code"] in found]
    print("catalogue rows: %d, tagged C: %d, with a diag_<code> test: %d, without: %d" % (len(rows), len(c_rows), len(covered), len(missing)))
    for tag, what in (("H", "HAL logic host test (WP-3)"), ("P", "protocol codec test"), ("S", "Swift table-driven test"), ("D", "differential parity")):
        print("tagged %s (%s): %d" % (tag, what, sum(1 for r in rows if tag in r["test"].split())))
    print("tagged with a bench procedure only (B nn, WP-8): %d" % sum(1 for r in rows if not (set(r["test"].split()) & {"C", "H", "P", "S", "D"})))
    if unknown:
        print("ERROR: tests named after codes that are not in the catalogue: %s" % ", ".join(unknown))
    if missing:
        print("\nRows tagged C without a diag_<code> test (%d):" % len(missing))
        for r in missing:
            print("  %s  %-34s %s  by %s" % (r["code"], r["name"], r["sev"], r["by"]))
    if unknown:
        return 1
    if "--strict" in argv and missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
