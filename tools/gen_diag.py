#!/usr/bin/env python3
"""OpenPatch diagnostic catalogue tool (docs/06-diagnostics.md WP-0).

Single source of truth: ``spec/diag-codes.csv``.  Generated from it:

* ``firmware-rs/openpatch-diag/src/catalogue.rs``   (Rust, no_std, sorted const table + code constants)
* ``ios/OpenPatchKit/OpenPatchCore/Sources/OpenPatchCore/DiagCatalogue.swift``
* ``docs/06-diagnostics-trace.md``                   (code <-> hazard <-> test tag report)

Modes::

    tools/gen_diag.py            regenerate all generated files
    tools/gen_diag.py --check    exit 1 when a generated file is stale, the CSV is invalid, or the
                                 section 4 tables of docs/06-diagnostics.md diverge from the CSV
    tools/gen_diag.py --extract  (re)build the CSV from the doc tables (one-off bootstrap; keeps the
                                 hand-maintained ``waiver`` column of an existing CSV)

TEST PROJECT: never worn, never used with insulin on a person.
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "spec", "diag-codes.csv")
DOC_PATH = os.path.join(ROOT, "docs", "06-diagnostics.md")
RUST_OUT = os.path.join(ROOT, "firmware-rs", "openpatch-diag", "src", "catalogue.rs")
SWIFT_OUT = os.path.join(ROOT, "ios", "OpenPatchKit", "OpenPatchCore", "Sources", "OpenPatchCore", "DiagCatalogue.swift")
TRACE_OUT = os.path.join(ROOT, "docs", "06-diagnostics-trace.md")

# Bump on EVERY catalogue change (reported to the app in DIAG_SUMMARY.schema).
SCHEMA_VERSION = 3

# ---- enumerations (docs/06-diagnostics.md 2.2, 2.3, 2.4) -------------------------------------
SEVERITIES = ["I", "W", "F", "L"]
SEV_RUST = {"I": "Info", "W": "Warning", "F": "Fault", "L": "Latched"}
SEV_SWIFT = {"I": "info", "W": "warning", "F": "fault", "L": "latched"}
ACTIONS = ["NONE", "RETRY", "ACK", "REFILL", "REDOCK", "RECABLE", "REPHONE", "CHECK_POWER", "REPLACE",
           "RESEAT", "SWAP_POD", "PRIME", "REPROVISION", "UPDATE_FW", "REPORT_BUG", "WAIT_COOL",
           "REPAIR", "UPDATE_APP", "CHECK_CANNULA", "ISOLATE"]
# The catalogue writes CHARGE for the battery codes; 2.3 has no such id, CHECK_POWER covers "or charge".
ACTION_ALIASES = {"CHARGE": "CHECK_POWER"}
FRUS = ["NONE", "CTRL", "PODB", "FFC", "MOTOR", "GEAR", "SCREW", "RESV", "SEAL", "CAP", "NEEDLE",
        "BATT", "APP", "MAGD", "MAGS", "USB", "CANN", "FW", "CHG"]
LEGACY_DEFAULT = 5  # INTERNAL
BY_VALUES = {"FW-HAL", "FW-core", "FW-boot", "PROTO", "APP"}
TEST_TAGS = {"C", "H", "P", "S", "D"}
MAX_TEXT = 90

FIELDS = ["code", "name", "detection", "by", "sev", "fru", "fru2", "action", "haz", "test", "text",
          "legacy_bit", "waiver"]
CODE_RE = re.compile(r"^([1-9AB])-([0-9A-F]{2})-([0-9A-F]{3})$")


class CatalogueError(Exception):
    pass


# ---- doc parsing -------------------------------------------------------------------------------
def parse_fru_action(cell):
    cell = cell.strip()
    if cell.startswith("by the spare"):
        # 9-91-005: the app shows the FRU/action of the spare pod's own record
        return "NONE", "", "NONE"
    m = re.match(r"^([A-Z]+)(?: \(([A-Z]+)\))?: ([A-Z_]+)$", cell)
    if not m:
        raise CatalogueError("cannot parse FRU/action cell: %r" % cell)
    return m.group(1), m.group(2) or "", ACTION_ALIASES.get(m.group(3), m.group(3))


def parse_doc_rows(text):
    """Rows of the section 4 catalogue tables (4.1 .. 4.7), in document order."""
    start = text.index("## 4. Catalogue")
    end = text.index("### 4.8 Counts")
    rows = []
    for line in text[start:end].splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) != 9:
            raise CatalogueError("table row with %d cells: %s" % (len(cells), line[:80]))
        code, name, det, by, sev, fa, haz, test, trio = cells
        fru, fru2, action = parse_fru_action(fa)
        rows.append({
            "code": code.strip("`"),
            "name": name,
            "detection": det,
            "by": by,
            "sev": sev,
            "fru": fru,
            "fru2": fru2,
            "action": action,
            "haz": " ".join(h.strip() for h in haz.split(",")),
            "test": " ".join(t.strip() for t in test.split(",")),
            "text": trio,
        })
    return rows


def parse_legacy_table(text):
    """{code: legacy bit} for the explicit rows of the 2.7 table."""
    start = text.index("### 2.7 Backward compatibility")
    end = text.index("### 2.8 Allocation")
    out = {}
    for line in text[start:end].splitlines():
        m = re.match(r"^\| (\d) \| [A-Z_]+ \| (.*) \|$", line)
        if not m:
            continue
        bit = int(m.group(1))
        for c in re.findall(r"`([1-9AB]-[0-9A-F]{2}-[0-9A-F]{3})`", m.group(2)):
            out[c] = bit
    return out


def default_legacy(row, explicit):
    if row["code"] in explicit:
        return str(explicit[row["code"]])
    return str(LEGACY_DEFAULT) if row["sev"] in ("F", "L") else ""


def extract():
    text = open(DOC_PATH, encoding="utf-8").read()
    rows = parse_doc_rows(text)
    explicit = parse_legacy_table(text)
    old = {}
    if os.path.exists(CSV_PATH):
        for r in read_csv():
            old[r["code"]] = r
    for r in rows:
        r["legacy_bit"] = default_legacy(r, explicit)
        r["waiver"] = old.get(r["code"], {}).get("waiver", "")
    write_csv(rows)
    return rows


# ---- CSV ---------------------------------------------------------------------------------------
def read_csv():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != FIELDS:
            raise CatalogueError("CSV header must be: " + ",".join(FIELDS))
        return [dict(r) for r in rd]


def write_csv(rows):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def code_value(code):
    m = CODE_RE.match(code)
    return (int(m.group(1), 16) << 28) | (int(m.group(2), 16) << 20) | (int(m.group(3), 16) << 8)


def haz_mask(haz):
    mask = 0
    for h in haz.split():
        m = re.match(r"^H(\d+)$", h)
        if not m or not 1 <= int(m.group(1)) <= 15:
            raise CatalogueError("bad hazard %r" % h)
        mask |= 1 << int(m.group(1))
    return mask


def validate(rows):
    errs = []
    seen, names = set(), set()
    for r in rows:
        c = r["code"]
        if not CODE_RE.match(c):
            errs.append("%s: malformed code" % c)
            continue
        if c in seen:
            errs.append("%s: duplicate code" % c)
        seen.add(c)
        if not re.match(r"^[A-Z][A-Z0-9_]*$", r["name"]):
            errs.append("%s: bad name %r" % (c, r["name"]))
        if r["name"] in names:
            errs.append("%s: duplicate name %s" % (c, r["name"]))
        names.add(r["name"])
        if r["sev"] not in SEVERITIES:
            errs.append("%s: bad severity %r" % (c, r["sev"]))
        if r["by"] not in BY_VALUES:
            errs.append("%s: bad 'by' %r" % (c, r["by"]))
        if r["fru"] not in FRUS:
            errs.append("%s: bad FRU %r" % (c, r["fru"]))
        if r["fru2"] and r["fru2"] not in FRUS:
            errs.append("%s: bad FRU2 %r" % (c, r["fru2"]))
        if r["action"] not in ACTIONS:
            errs.append("%s: bad action %r" % (c, r["action"]))
        if not r["text"] or len(r["text"]) > MAX_TEXT:
            errs.append("%s: text empty or longer than %d" % (c, MAX_TEXT))
        try:
            haz_mask(r["haz"])
        except CatalogueError as e:
            errs.append("%s: %s" % (c, e))
        if not r["haz"].strip():
            errs.append("%s: no hazard link" % c)
        tags = r["test"].split()
        if not tags and not r["waiver"].strip():
            errs.append("%s: no test tag and no waiver" % c)
        for t in tags:
            if t not in TEST_TAGS and not re.match(r"^B\d{2}$", t):
                errs.append("%s: bad test tag %r" % (c, t))
        lb = r["legacy_bit"].strip()
        if r["sev"] in ("F", "L") and lb == "":
            errs.append("%s: F/L code without legacy bit" % c)
        if r["sev"] in ("I", "W") and lb != "":
            errs.append("%s: I/W code must not set a legacy bit" % c)
        if lb != "" and not (lb.isdigit() and 0 <= int(lb) <= 7):
            errs.append("%s: bad legacy bit %r" % (c, lb))
    keys = [code_value(r["code"]) for r in rows if CODE_RE.match(r["code"])]
    if keys != sorted(keys):
        errs.append("CSV rows must be sorted by code")
    if errs:
        raise CatalogueError("\n".join(errs))


# ---- generators --------------------------------------------------------------------------------
HEADER = "// @generated by tools/gen_diag.py from spec/diag-codes.csv. DO NOT EDIT.\n"


def camel(name):
    parts = name.lower().split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def pascal(name):
    return "".join(p.capitalize() for p in name.lower().split("_"))


def swift_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def gen_rust(rows):
    o = [HEADER,
         "//! Generated diagnostic catalogue (docs/06-diagnostics.md section 4). Sorted by code identity.\n",
         "use crate::{Action, CodeInfo, DiagCode, Fru, Severity};\n",
         "/// Catalogue version, reported in `DIAG_SUMMARY.schema`.",
         "pub const SCHEMA_VERSION: u16 = %d;\n" % SCHEMA_VERSION,
         "/// All catalogue rows, sorted by `code.identity()` (binary search).",
         "pub static CATALOGUE: [CodeInfo; %d] = [" % len(rows)]
    for r in rows:
        lb = r["legacy_bit"].strip()
        o.append(
            "    CodeInfo { code: DiagCode(0x%08X), name: \"%s\", severity: Severity::%s, action: Action::%s, fru: Fru::%s, "
            "fru2: Fru::%s, legacy_bit: %s, hazards: 0x%04X },"
            % (code_value(r["code"]), r["name"], SEV_RUST[r["sev"]], pascal(r["action"]), pascal(r["fru"]),
               pascal(r["fru2"] or "NONE"), lb if lb else "0xFF", haz_mask(r["haz"])))
    o.append("];\n")
    o.append("/// One constant per catalogue row (instance 0).")
    o.append("pub mod codes {")
    o.append("    use crate::DiagCode;")
    for r in rows:
        o.append("    /// `%s`" % r["code"])
        o.append("    pub const %s: DiagCode = DiagCode(0x%08X);" % (r["name"], code_value(r["code"])))
    o.append("}")
    return "\n".join(o) + "\n"


def gen_swift(rows):
    o = [HEADER,
         "// Generated diagnostic catalogue (docs/06-diagnostics.md section 4), sorted by code identity.",
         "import Foundation\n",
         "public enum DiagCatalogueData {",
         "    /// Catalogue version (matches `DiagSummary.schema` of a pod with the same catalogue).",
         "    public static let schemaVersion: UInt16 = %d\n" % SCHEMA_VERSION,
         "    public static let entries: [DiagCatalogueEntry] = ["]
    for r in rows:
        lb = r["legacy_bit"].strip()
        o.append(
            "        DiagCatalogueEntry(code: DiagCode(raw: 0x%08X), name: %s, severity: .%s, action: .%s, fru: .%s, fru2: %s, "
            "legacyBit: %s, hazards: 0x%04X, text: %s),"
            % (code_value(r["code"]), swift_str(r["name"]), SEV_SWIFT[r["sev"]], camel(r["action"]), camel(r["fru"]),
               "." + camel(r["fru2"]) if r["fru2"] else "nil", lb if lb else "nil", haz_mask(r["haz"]), swift_str(r["text"])))
    o.append("    ]")
    o.append("}\n")
    o.append("extension DiagCode {")
    for r in rows:
        o.append("    /// `%s`" % r["code"])
        o.append("    public static let %s = DiagCode(raw: 0x%08X)" % (camel(r["name"]), code_value(r["code"])))
    o.append("}")
    return "\n".join(o) + "\n"


def gen_trace(rows):
    o = ["<!-- @generated by tools/gen_diag.py from spec/diag-codes.csv. DO NOT EDIT. -->",
         "# Diagnostics traceability (code, hazard, test tag)\n",
         "> Generated from `spec/diag-codes.csv` (%d codes, schema %d). Test tags: `C` core fault injection, `H` HAL logic, "
         "`P` protocol, `S` Swift, `D` differential, `Bnn` bench procedure (docs/06-diagnostics.md 6.1 and 6.3).\n" % (len(rows), SCHEMA_VERSION),
         "## Per code\n",
         "| Code | Name | Sev | Hazards | Tests | Waiver |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        o.append("| `%s` | %s | %s | %s | %s | %s |" % (r["code"], r["name"], r["sev"], r["haz"].replace(" ", ", "),
                                                        r["test"].replace(" ", ", ") or "-", r["waiver"] or ""))
    o.append("\n## Per hazard\n")
    o.append("| Hazard | Codes | Count |")
    o.append("|---|---|---|")
    hz = {}
    for r in rows:
        for h in r["haz"].split():
            hz.setdefault(int(h[1:]), []).append(r["code"])
    for h in sorted(hz):
        o.append("| H%d | %s | %d |" % (h, ", ".join("`%s`" % c for c in hz[h]), len(hz[h])))
    o.append("\n## Per test tag\n")
    o.append("| Tag | Codes | Count |")
    o.append("|---|---|---|")
    tg = {}
    for r in rows:
        for t in r["test"].split():
            tg.setdefault(t, []).append(r["code"])
    for t in sorted(tg):
        o.append("| %s | %s | %d |" % (t, ", ".join("`%s`" % c for c in tg[t]), len(tg[t])))
    no_tag = [r["code"] for r in rows if not r["test"].strip()]
    o.append("\n## Coverage gaps\n")
    o.append("Codes without any test tag: %s" % (", ".join("`%s`" % c for c in no_tag) if no_tag else "none"))
    sev = {s: sum(1 for r in rows if r["sev"] == s) for s in SEVERITIES}
    o.append("\nSeverity counts: " + ", ".join("%d %s" % (sev[s], s) for s in SEVERITIES) + ".")
    return "\n".join(o) + "\n"


# ---- drift check -------------------------------------------------------------------------------
DOC_FIELDS = ["code", "name", "detection", "by", "sev", "fru", "fru2", "action", "haz", "test", "text"]


def check_doc(rows):
    text = open(DOC_PATH, encoding="utf-8").read()
    doc = parse_doc_rows(text)
    errs = []
    if [r["code"] for r in doc] != [r["code"] for r in rows]:
        a, b = {r["code"] for r in doc}, {r["code"] for r in rows}
        errs.append("code set differs: only in doc %s, only in CSV %s" % (sorted(a - b), sorted(b - a)))
    else:
        for d, r in zip(doc, rows):
            for f in DOC_FIELDS:
                if d[f] != r[f]:
                    errs.append("%s.%s differs: doc=%r csv=%r" % (r["code"], f, d[f], r[f]))
    by_code = {r["code"]: r for r in rows}
    for c, bit in parse_legacy_table(text).items():
        row = by_code.get(c)
        if row is None or row["legacy_bit"] != str(bit):
            errs.append("%s: legacy bit differs from the 2.7 table of the doc" % c)
    if errs:
        raise CatalogueError("doc tables and spec/diag-codes.csv diverge:\n" + "\n".join(errs))


def outputs(rows):
    return {RUST_OUT: gen_rust(rows), SWIFT_OUT: gen_swift(rows), TRACE_OUT: gen_trace(rows)}


def main(argv):
    if "--extract" in argv:
        rows = extract()
        print("extracted %d rows to %s" % (len(rows), os.path.relpath(CSV_PATH, ROOT)))
        return 0
    check = "--check" in argv
    try:
        rows = read_csv()
        validate(rows)
        if check:
            check_doc(rows)
    except CatalogueError as e:
        print("diag catalogue error:\n%s" % e, file=sys.stderr)
        return 1
    outs = outputs(rows)
    if check:
        stale = []
        for path, content in outs.items():
            cur = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if cur != content:
                stale.append(os.path.relpath(path, ROOT))
        if stale:
            print("stale generated files (run tools/gen_diag.py): " + ", ".join(stale), file=sys.stderr)
            return 1
        print("diag catalogue ok: %d codes, schema %d" % (len(rows), SCHEMA_VERSION))
        return 0
    for path, content in outs.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print("wrote " + os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
