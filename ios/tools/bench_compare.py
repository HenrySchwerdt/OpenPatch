#!/usr/bin/env python3
"""Compare insulin units Trio reports against grams of water on a lab balance.

OpenPatch is a TEST PROJECT. It is not a medical device and is only ever run
with WATER into a vial on a balance. This tool only does arithmetic on two CSV
files; it never talks to a pump.

Inputs
  trio_doses.csv  timestamp_iso8601,kind,units,duration_min,rate_u_per_h
                  kind in {bolus, smb, temp_basal, suspend, resume}
  balance.csv     timestamp_iso8601,mass_g

Conversion: U100, 1 U = 10 ul. Delivered volume (ul) = mass / density.
Run with:  python3 -I bench_compare.py --doses D.csv --balance B.csv

Exit codes: 0 PASS, 1 FAIL, 2 input/usage error, 3 INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import re
import sys
from datetime import datetime, timezone

UL_PER_UNIT = 10.0  # U100 insulin: 1 U = 10 mm^3 = 10 ul
DEFAULT_DENSITY_G_PER_ML = 0.9982  # water at 20 C
KINDS = ("bolus", "smb", "temp_basal", "suspend", "resume")
BOLUS_KINDS = ("bolus", "smb")
STEP_FRACTION = 0.25  # a bolus shows a "clear step" if >= 25 % of reported units
EXIT_PASS, EXIT_FAIL, EXIT_ERROR, EXIT_INCONCLUSIVE = 0, 1, 2, 3


class CsvError(Exception):
    """Raised for unreadable or malformed input files."""


# --------------------------------------------------------------------------
# Physics helpers
# --------------------------------------------------------------------------

def water_density_g_per_ml(temp_c: float) -> float:
    """Kell (1975) formula for air-free water at 1 atm, valid 0..150 C."""
    t = temp_c
    kg_m3 = (
        999.83952 + 16.945176 * t - 7.9870401e-3 * t ** 2
        - 46.170461e-6 * t ** 3 + 105.56302e-9 * t ** 4
        - 280.54253e-12 * t ** 5
    ) / (1 + 16.879850e-3 * t)
    return kg_m3 / 1000.0


def units_per_gram(density_g_per_ml: float) -> float:
    """U per gram of water: grams -> ml -> ul -> U."""
    return 1000.0 / density_g_per_ml / UL_PER_UNIT


# --------------------------------------------------------------------------
# CSV parsing
# --------------------------------------------------------------------------

_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?"
    r"(Z|z|[+-]\d{2}(?::?\d{2})?)?$"
)


def parse_timestamp(text: str) -> float:
    """ISO 8601 to epoch seconds. A timestamp without offset is taken as UTC."""
    m = _TS_RE.match(text.strip())
    if not m:
        raise ValueError(f"not an ISO 8601 timestamp: {text!r}")
    date, clock, frac, tz = m.groups()
    frac = (frac or "0")[:6].ljust(6, "0")
    if tz is None or tz in ("Z", "z"):
        tz = "+00:00"
    else:
        digits = tz[1:].replace(":", "")
        tz = f"{tz[0]}{digits[:2]}:{digits[2:4] or '00'}"
    try:
        return datetime.fromisoformat(f"{date}T{clock}.{frac}{tz}").timestamp()
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {text!r}: {exc}") from exc


def format_timestamp(epoch: float) -> str:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_rows(path: str, required: tuple):
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            lines = [ln for ln in handle if ln.strip() and not ln.lstrip().startswith("#")]
    except FileNotFoundError:
        raise CsvError(f"file not found: {path}") from None
    except OSError as exc:
        raise CsvError(f"cannot read {path}: {exc.strerror or exc}") from None
    except UnicodeDecodeError:
        raise CsvError(f"{path}: not valid UTF-8 text") from None
    if not lines:
        raise CsvError(f"{path}: file is empty")
    reader = csv.reader(lines)
    header = [h.strip().lower() for h in next(reader)]
    missing = [c for c in required if c not in header]
    if missing:
        raise CsvError(
            f"{path}: missing column(s) {', '.join(missing)}; found: {', '.join(header)}"
        )
    rows = []
    for number, cells in enumerate(reader, start=2):
        record = {name: (cells[i].strip() if i < len(cells) else "") for i, name in enumerate(header)}
        rows.append((number, record))
    return rows


def _number(path: str, line: int, column: str, text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise CsvError(f"{path} line {line}: column {column} is not a number: {text!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise CsvError(f"{path} line {line}: column {column} is not finite: {text!r}")
    return value


def load_balance(path: str) -> list:
    """Return [(epoch_s, mass_g)] sorted by time."""
    rows = []
    for line, rec in _read_rows(path, ("timestamp_iso8601", "mass_g")):
        try:
            t = parse_timestamp(rec["timestamp_iso8601"])
        except ValueError as exc:
            raise CsvError(f"{path} line {line}: {exc}") from None
        rows.append((t, _number(path, line, "mass_g", rec["mass_g"])))
    if len(rows) < 2:
        raise CsvError(f"{path}: need at least 2 balance readings, found {len(rows)}")
    return sorted(rows, key=lambda r: r[0])


def load_doses(path: str) -> list:
    """Return [dict(t, kind, units, duration_min, rate)] in file order, sorted by time (stable)."""
    doses = []
    for line, rec in _read_rows(path, ("timestamp_iso8601", "kind")):
        where = f"{path} line {line}"
        try:
            t = parse_timestamp(rec["timestamp_iso8601"])
        except ValueError as exc:
            raise CsvError(f"{where}: {exc}") from None
        kind = rec["kind"].lower()
        if kind not in KINDS:
            raise CsvError(f"{where}: unknown kind {rec['kind']!r}; expected one of {', '.join(KINDS)}")
        entry = {"t": t, "kind": kind, "units": 0.0, "duration_min": 0.0, "rate": 0.0}
        if kind in BOLUS_KINDS:
            if rec.get("units", "") == "":
                raise CsvError(f"{where}: {kind} needs a value in column units")
            entry["units"] = _number(path, line, "units", rec["units"])
            if entry["units"] < 0:
                raise CsvError(f"{where}: units must not be negative")
        elif kind == "temp_basal":
            if rec.get("duration_min", "") == "":
                raise CsvError(f"{where}: temp_basal needs a value in column duration_min")
            entry["duration_min"] = _number(path, line, "duration_min", rec["duration_min"])
            if entry["duration_min"] < 0:
                raise CsvError(f"{where}: duration_min must not be negative")
            if rec.get("rate_u_per_h", "") != "":
                entry["rate"] = _number(path, line, "rate_u_per_h", rec["rate_u_per_h"])
            elif rec.get("units", "") != "" and entry["duration_min"] > 0:
                entry["rate"] = _number(path, line, "units", rec["units"]) / (entry["duration_min"] / 60.0)
            else:
                raise CsvError(f"{where}: temp_basal needs rate_u_per_h (or units plus duration_min)")
            if entry["rate"] < 0:
                raise CsvError(f"{where}: rate_u_per_h must not be negative")
        doses.append(entry)
    if not doses:
        raise CsvError(f"{path}: no dose rows")
    return sorted(doses, key=lambda d: d["t"])


# --------------------------------------------------------------------------
# Core computation
# --------------------------------------------------------------------------

def build_series(balance, density, tare_mass, evaporation_mg_per_min):
    """Cumulative delivered units over time from balance readings.

    Evaporation loss is added back: corrected = mass - tare + loss(t).
    """
    t0 = balance[0][0]
    tare = balance[0][1] if tare_mass is None else tare_mass
    upg = units_per_gram(density)
    times, units, grams = [], [], []
    for t, mass in balance:
        g = mass - tare + evaporation_mg_per_min / 1000.0 * (t - t0) / 60.0
        times.append(t)
        grams.append(g)
        units.append(g * upg)
    return times, units, grams


def interpolate(times, values, t):
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = bisect.bisect_right(times, t)
    t_a, t_b = times[i - 1], times[i]
    if t_b == t_a:
        return values[i]
    frac = (t - t_a) / (t_b - t_a)
    return values[i - 1] + frac * (values[i] - values[i - 1])


def integrate_doses(doses, t_start, t_end):
    """Turn Trio events into point doses and constant-rate intervals.

    A temp basal runs for its duration but is clipped to the next temp_basal or
    suspend event and to the run end. Suspend cancels the running temp basal;
    resume does not restart it. Doses while suspended or outside the run are
    dropped with a warning.
    """
    points, intervals, warnings = [], [], []
    suspended = False
    for i, d in enumerate(doses):
        kind, t = d["kind"], d["t"]
        if kind == "suspend":
            suspended = True
        elif kind == "resume":
            suspended = False
        elif kind in BOLUS_KINDS:
            if suspended:
                warnings.append(f"{kind} {d['units']:g} U at {format_timestamp(t)} ignored: pump suspended")
            elif t < t_start or t > t_end:
                warnings.append(f"{kind} {d['units']:g} U at {format_timestamp(t)} ignored: outside balance run")
            else:
                points.append({"t": t, "kind": kind, "units": d["units"]})
        else:  # temp_basal
            if suspended:
                warnings.append(f"temp_basal at {format_timestamp(t)} ignored: pump suspended")
                continue
            end = t + d["duration_min"] * 60.0
            for later in doses[i + 1:]:
                if later["kind"] in ("temp_basal", "suspend") and later["t"] >= t:
                    end = min(end, later["t"])
                    break
            start = max(t, t_start)
            end = min(end, t_end)
            if end > start:
                intervals.append({"start": start, "end": end, "rate_u_per_s": d["rate"] / 3600.0})
    return points, intervals, warnings


def reported_in(points, intervals, a, b, include_points=True):
    """Units Trio reports in (a, b]; boluses at their timestamp, basal prorated."""
    total = 0.0
    if include_points:
        total += sum(p["units"] for p in points if a < p["t"] <= b)
    for iv in intervals:
        overlap = min(iv["end"], b) - max(iv["start"], a)
        if overlap > 0:
            total += overlap * iv["rate_u_per_s"]
    return total


def pct(diff, ref):
    return None if abs(ref) < 1e-9 else diff / ref * 100.0


def compare_windows(times, units, points, intervals, t_start, t_end, window_min):
    rows = []
    step = window_min * 60.0
    a = t_start
    while a < t_end - 1e-9:
        b = min(a + step, t_end)
        rep = reported_in(points, intervals, a - 1e-9 if a == t_start else a, b)
        meas = interpolate(times, units, b) - interpolate(times, units, a)
        rows.append({
            "start": format_timestamp(a), "end": format_timestamp(b),
            "minutes": round((b - a) / 60.0, 2),
            "reported_u": rep, "measured_u": meas,
            "diff_u": meas - rep, "diff_pct": pct(meas - rep, rep),
        })
        a = b
    return rows


def compare_boluses(times, units, points, intervals, window_s):
    rows = []
    for p in points:
        t = p["t"]
        others = [q for q in points if q is not p and t < q["t"] <= t + window_s]
        in_window = [i for i, ts in enumerate(times) if t < ts <= t + window_s]
        row = {"timestamp": format_timestamp(t), "kind": p["kind"], "reported_u": p["units"],
               "measured_u": None, "error_pct": None, "status": "ok"}
        if others:
            row["status"] = "skipped: another bolus within window"
        elif not in_window:
            row["status"] = "skipped: no balance reading in window"
        else:
            t_after = times[in_window[-1]]
            basal = reported_in(points, intervals, t, t_after, include_points=False)
            measured = interpolate(times, units, t_after) - interpolate(times, units, t) - basal
            row["measured_u"] = measured
            row["error_pct"] = pct(measured - p["units"], p["units"])
            if p["units"] > 0 and measured < STEP_FRACTION * p["units"]:
                row["status"] = "NO CLEAR STEP"
        rows.append(row)
    return rows


def compare(balance, doses, density=DEFAULT_DENSITY_G_PER_ML, tare_mass=None,
            evaporation_mg_per_min=0.0, window_min=30.0, tolerance_pct=5.0,
            min_units=2.0, bolus_window_s=120.0):
    """Full comparison; returns a JSON-serialisable dict."""
    times, units, grams = build_series(balance, density, tare_mass, evaporation_mg_per_min)
    t_start, t_end = times[0], times[-1]
    points, intervals, warnings = integrate_doses(doses, t_start, t_end)
    reported = reported_in(points, intervals, t_start - 1e-9, t_end)
    measured = units[-1]
    diff = measured - reported
    diff_pct = pct(diff, reported)

    if reported < min_units:
        result = "INCONCLUSIVE"
        reason = (f"reported {reported:.3f} U is below min-units {min_units:g} U; "
                  "balance resolution dominates the error")
    elif diff_pct is not None and abs(diff_pct) <= tolerance_pct:
        result = "PASS"
        reason = f"abs error {abs(diff_pct):.2f} % <= {tolerance_pct:g} %"
    else:
        result = "FAIL"
        reason = f"abs error {abs(diff_pct):.2f} % > {tolerance_pct:g} %"

    return {
        "params": {"density_g_per_ml": density, "units_per_gram": units_per_gram(density),
                   "tare_mass_g": balance[0][1] if tare_mass is None else tare_mass,
                   "evaporation_mg_per_min": evaporation_mg_per_min, "window_min": window_min,
                   "tolerance_pct": tolerance_pct, "min_units": min_units,
                   "bolus_window_s": bolus_window_s},
        "run": {"start": format_timestamp(t_start), "end": format_timestamp(t_end),
                "duration_min": round((t_end - t_start) / 60.0, 2), "balance_readings": len(times)},
        "totals": {"reported_u": reported, "measured_u": measured, "measured_g": grams[-1],
                   "diff_u": diff, "diff_pct": diff_pct},
        "windows": compare_windows(times, units, points, intervals, t_start, t_end, window_min),
        "boluses": compare_boluses(times, units, points, intervals, bolus_window_s),
        "verdict": {"result": result, "reason": reason, "tolerance_pct": tolerance_pct,
                    "min_units": min_units},
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _p(value, spec="+.2f", suffix=" %"):
    return "n/a" if value is None else f"{value:{spec}}{suffix}"


def format_report(r) -> str:
    p, run, tot = r["params"], r["run"], r["totals"]
    out = [
        "OpenPatch bench compare (WATER ONLY, test project)",
        f"Run        : {run['start']} .. {run['end']} ({run['duration_min']} min, "
        f"{run['balance_readings']} balance readings)",
        f"Conversion : density {p['density_g_per_ml']:.5f} g/ml -> {p['units_per_gram']:.2f} U/g "
        f"(1 U = {UL_PER_UNIT:g} ul = {UL_PER_UNIT * p['density_g_per_ml']:.3f} mg)",
        f"Tare       : {p['tare_mass_g']:.4f} g, evaporation correction "
        f"{p['evaporation_mg_per_min']:g} mg/min",
        "",
        "Totals",
        f"  Trio reported : {tot['reported_u']:9.3f} U",
        f"  Balance       : {tot['measured_u']:9.3f} U  ({tot['measured_g']:.4f} g)",
        f"  Difference    : {tot['diff_u']:+9.3f} U  ({_p(tot['diff_pct'])})",
        "",
        f"Windows ({p['window_min']:g} min)",
        "  start                 min   reported U  measured U     diff U    diff %",
    ]
    for w in r["windows"]:
        out.append(f"  {w['start']}  {w['minutes']:5.1f}  {w['reported_u']:10.3f}  "
                   f"{w['measured_u']:10.3f}  {w['diff_u']:+9.3f}  {_p(w['diff_pct'], '+8.2f', '')}")
    out += ["", f"Boluses (step within {p['bolus_window_s']:g} s)"]
    if r["boluses"]:
        out.append("  time                  kind   reported U  measured U   error %  status")
        for b in r["boluses"]:
            meas = "n/a" if b["measured_u"] is None else f"{b['measured_u']:.3f}"
            out.append(f"  {b['timestamp']}  {b['kind']:<5} {b['reported_u']:10.3f}  "
                       f"{meas:>10}  {_p(b['error_pct'], '+8.2f', '')}  {b['status']}")
    else:
        out.append("  none")
    for w in r["warnings"]:
        out.append(f"WARNING: {w}")
    v = r["verdict"]
    out += ["", f"Verdict: {v['result']} ({v['reason']}; tolerance {v['tolerance_pct']:g} %, "
            f"min {v['min_units']:g} U)"]
    return "\n".join(out)


def build_parser():
    ap = argparse.ArgumentParser(
        prog="bench_compare.py",
        description="Compare Trio-reported units with grams of water on a balance (OpenPatch bench, water only).")
    ap.add_argument("--doses", required=True, help="trio_doses.csv")
    ap.add_argument("--balance", required=True, help="balance.csv")
    ap.add_argument("--density", type=float, help="water density in g/ml (default 0.9982, i.e. 20 C)")
    ap.add_argument("--temp-c", type=float, help="water temperature in C; derives density (Kell) unless --density is given")
    ap.add_argument("--tare-mass", type=float, help="tare mass in g (default: first balance reading; tare after the prime)")
    ap.add_argument("--evaporation-mg-per-min", type=float, default=0.0,
                    help="measured evaporation loss, added back to the balance (default 0)")
    ap.add_argument("--window-min", type=float, default=30.0, help="window length in minutes (default 30)")
    ap.add_argument("--tolerance-pct", type=float, default=5.0, help="PASS tolerance for totals in %% (default 5)")
    ap.add_argument("--min-units", type=float, default=2.0,
                    help="below this many reported U the verdict is INCONCLUSIVE (default 2.0)")
    ap.add_argument("--bolus-window-s", type=float, default=120.0,
                    help="seconds after a bolus in which its step is measured (default 120)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.density is not None:
        density = args.density
    elif args.temp_c is not None:
        density = water_density_g_per_ml(args.temp_c)
    else:
        density = DEFAULT_DENSITY_G_PER_ML
    if not 0.5 < density < 1.5:
        print(f"error: implausible density {density} g/ml", file=sys.stderr)
        return EXIT_ERROR
    if args.window_min <= 0 or args.bolus_window_s <= 0:
        print("error: --window-min and --bolus-window-s must be positive", file=sys.stderr)
        return EXIT_ERROR
    try:
        balance = load_balance(args.balance)
        doses = load_doses(args.doses)
    except CsvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    result = compare(balance, doses, density=density, tare_mass=args.tare_mass,
                     evaporation_mg_per_min=args.evaporation_mg_per_min, window_min=args.window_min,
                     tolerance_pct=args.tolerance_pct, min_units=args.min_units,
                     bolus_window_s=args.bolus_window_s)
    print(json.dumps(result, indent=2) if args.json else format_report(result))
    return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL}.get(result["verdict"]["result"], EXIT_INCONCLUSIVE)


if __name__ == "__main__":
    sys.exit(main())
