#!/usr/bin/env python3
"""Convert the TI PSpice transient models (downloaded by fetch_models.sh) to something ngspice-42 reads.

Only syntax is changed, never a value:
  * .MODEL x VSWITCH Roff= Ron= Voff= Von=   ->  .model x SW vt= vh= ron= roff=      (vt = mean of Von/Voff, vh = half the span)
  * nested braces  {{...{X}...}}              ->  {...(X)...}
  * the converted file is written next to the original as <name>_ng.lib (gitignored with models/).
"""
import re
import sys


def to_float(s):
    s = s.strip().lower()
    m = re.match(r"^([0-9.]+(?:e[+-]?\d+)?)(meg|mil|[tgkmunpf])?", s)
    num = float(m.group(1))
    suf = m.group(2) or ""
    mult = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15, "": 1, "mil": 25.4e-6}[suf]
    return num * mult


def fix_braces(expr):
    """strip every brace inside an outermost {...}; keep the outer pair."""
    out, depth = [], 0
    for ch in expr:
        if ch == "{":
            depth += 1
            out.append("{" if depth == 1 else "(")
        elif ch == "}":
            out.append("}" if depth == 1 else ")")
            depth -= 1
        else:
            out.append(ch)
    return "".join(out)


def convert(text):
    # join continuation lines first so that expressions are on one line
    lines = []
    for raw in text.splitlines():
        if raw.startswith("+") and lines:
            lines[-1] += " " + raw[1:].strip()
        else:
            lines.append(raw.rstrip())
    res = []
    for ln in lines:
        low = ln.lower()
        if low.startswith(".model") and "vswitch" in low:
            name = ln.split()[1]
            kv = dict((k.lower(), to_float(v)) for k, v in re.findall(r"(\w+)\s*=\s*([0-9.eE+\-]+[a-zA-Z]*)", ln))
            vt = (kv["von"] + kv["voff"]) / 2
            vh = (kv["von"] - kv["voff"]) / 2
            ln = ".model %s SW vt=%g vh=%g ron=%g roff=%g" % (name, vt, vh, kv["ron"], kv["roff"])
        elif "{" in ln:
            # do the brace fix on every top-level brace group of the line
            ln = re.sub(r"\{\{.*\}\}", lambda m: fix_braces(m.group(0)[1:-1]), ln)   # {{...}} -> {...}
            ln = re.sub(r"\{\{(\w+)\}\*([0-9.]+)\}", r"{\1*\2}", ln)
        # logical operators: ngspice gives & | ^ a different precedence than PSpice, so parenthesise every comparison
        ln = re.sub(r"(V\([A-Za-z0-9_]+\))\s*>\s*(\(VTHRESH\))", r"(\1 > \2)", ln)
        if ln.upper().startswith("E_ABMGATE") and "^" in ln:      # XNOR gate: PSpice ^ = XOR
            ln = re.sub(r"IF\((.*?)\s*\^\s*(.*?),\(VSS\),\(VDD\)\)", r"IF(\1 == \2,(VDD),(VSS))", ln)
        res.append(ln)
    return "\n".join(res) + "\n"


def patch_tps61023(text):
    """The vendor model ties VOUT to its internal node VOUT_INT with four n=0.01 diodes and a 10 A loop current source
    (an 'ideal wire' trick). ngspice cannot converge on that diode (exp(V/0.26 mV)). Structure-only replacement: a 1 mohm resistor."""
    out = []
    for ln in text.splitlines():
        if re.match(r"^(D_D5|D_D6|D_D7|D_D8|I_I1)\s", ln):
            continue
        out.append(ln)
        if ln.upper().startswith(".SUBCKT TPS61023_SCHEMATIC"):
            out.append("R_VSHORT VOUT VOUT_INT 1m")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    txt = convert(open(src, errors="replace").read())
    if "TPS61023" in src.upper():
        txt = patch_tps61023(txt)
    open(dst, "w").write(txt)
