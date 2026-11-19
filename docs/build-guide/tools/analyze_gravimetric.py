#!/usr/bin/env python3
"""Analyse gravimetric water-delivery runs of the OpenPatch bench pod (build guide chapter 11.2).

TEST PROJECT: water only, bench only. Python 3 standard library only.

Input: a CSV in the format of templates/gravimetric_log.csv (one row per series). Output: a table per
run and a summary per dose class, as Markdown on stdout (use --csv-out to also write the per-run numbers).

    python3 analyze_gravimetric.py my_gravimetric_log.csv
    python3 analyze_gravimetric.py my_gravimetric_log.csv --u-per-step 0.003951 --resolution-mg 1.0 --csv-out result.csv

Definitions (U = model unit of the U100 convention: 1 U = 10 microlitres of water):
    density          = water density in mg/ul at the logged temperature (taken from the column, else from a table)
    corrected mass   = (m_after - m_before) - drift_mg_per_min * elapsed_min      [mg]; the drift is the
                       mass change per minute of the evaporation control (negative = loss), so a loss is added back
    delivered_ul     = corrected mass / density
    delivered_U      = delivered_ul / 10
    error_vs_cmd     = delivered_U / commanded_total_U - 1                         (what the user asks for)
    error_vs_steps   = delivered_U / (steps_total * u_per_step) - 1                (mechanical accuracy of one step)
    u_per_step_meas  = delivered_U / steps_total
    uncertainty      = sqrt(2) * resolution_mg / (expected mass of the series)     (two weighings)
A series whose uncertainty exceeds the tolerance (5 %) is reported INCONCLUSIVE, never PASS.
"""
import argparse
import csv
import math
import statistics
import sys

# water density in mg/ul (CRC, rounded), used only when the density column is empty
DENSITY = {15: 0.9991, 16: 0.9989, 17: 0.9988, 18: 0.9986, 19: 0.9984, 20: 0.9982, 21: 0.9980, 22: 0.9978,
           23: 0.9975, 24: 0.9973, 25: 0.9970, 26: 0.9968, 27: 0.9965, 28: 0.9962, 30: 0.9957}

SIM = {  # openpatch-sim REPORT.md 5.1 (Monte Carlo of 1000 pods; the model uses the 15:12 drive)
    1.0: "sim: mean -0.11 %, sd 2.47 %, 94.4 % within +-5 %",
    10.0: "sim: mean +0.02 %, sd 0.79 %, 100 % within +-5 %",
    0.05: "sim: single doses sd 50.7 %; judge the cumulative series",
}


def density_for(temp_c):
    t = round(temp_c)
    keys = sorted(DENSITY)
    t = min(keys, key=lambda k: abs(k - t))
    return DENSITY[t]


def num(row, key, default=None):
    v = (row.get(key) or "").strip()
    if v == "":
        return default
    try:
        return float(v)
    except ValueError:
        raise SystemExit(f"row {row.get('run_id', '?')}: column {key!r} is not a number: {v!r}")


def analyse_row(row, u_per_step, resolution_mg, tol_pct):
    n_doses = num(row, "n_doses")
    dose_u = num(row, "commanded_u_per_dose")
    total_cmd = num(row, "commanded_total_u")
    if total_cmd is None:
        total_cmd = n_doses * dose_u
    steps = num(row, "steps_total")
    dens = num(row, "water_density_mg_per_ul") or density_for(num(row, "ambient_c", 20.0))
    m0, m1 = num(row, "m_before_mg"), num(row, "m_after_mg")
    drift = num(row, "control_drift_mg_per_min", 0.0)
    elapsed = num(row, "elapsed_min", 0.0)
    corr = (m1 - m0) - drift * elapsed
    ul = corr / dens
    u = ul / 10.0
    out = {
        "run_id": row.get("run_id", ""), "dose_u": dose_u, "n_doses": n_doses, "commanded_total_u": total_cmd,
        "steps_total": steps, "corrected_mass_mg": corr, "delivered_u": u,
        "error_vs_cmd_pct": 100.0 * (u / total_cmd - 1.0) if total_cmd else float("nan"),
        "error_vs_steps_pct": (100.0 * (u / (steps * u_per_step) - 1.0)) if steps else float("nan"),
        "u_per_step_meas": (u / steps) if steps else float("nan"),
        "per_dose_u": u / n_doses if n_doses else float("nan"),
    }
    expected_mg = total_cmd * 10.0 * dens
    unc = 100.0 * math.sqrt(2.0) * resolution_mg / expected_mg if expected_mg else float("inf")
    out["uncertainty_pct"] = unc
    out["conclusive"] = unc <= tol_pct
    out["within_5"] = abs(out["error_vs_cmd_pct"]) <= tol_pct
    out["within_10"] = abs(out["error_vs_cmd_pct"]) <= 2 * tol_pct
    out["notes"] = row.get("notes", "")
    return out


def fmt(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="gravimetric log (templates/gravimetric_log.csv format)")
    ap.add_argument("--u-per-step", type=float, default=0.003951, help="nominal U per step of the 16:20 drive (default 0.003951)")
    ap.add_argument("--resolution-mg", type=float, default=1.0, help="balance reading uncertainty per weighing in mg (default 1.0)")
    ap.add_argument("--tol-pct", type=float, default=5.0, help="acceptance band in percent (default 5, docs/02-safety.md 3.1)")
    ap.add_argument("--csv-out", help="write the per-run results to this CSV")
    a = ap.parse_args()

    with open(a.csv, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("run_id") or "").strip() and not (r.get("run_id") or "").startswith("#")]
    if not rows:
        sys.exit("no data rows")
    res = [analyse_row(r, a.u_per_step, a.resolution_mg, a.tol_pct) for r in rows]

    print("# Gravimetric analysis (water only, bench only)\n")
    print(f"Nominal drive: {a.u_per_step} U/step; balance reading uncertainty {a.resolution_mg} mg per weighing; tolerance +-{a.tol_pct} %.\n")
    print("| run | dose U | n | cmd total U | steps | mass mg (corr.) | delivered U | err vs cmd % | err vs steps % | U/step | unc. % | verdict |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res:
        verdict = "INCONCLUSIVE" if not r["conclusive"] else ("PASS" if r["within_5"] else "FAIL")
        r["verdict"] = verdict
        print(f"| {r['run_id']} | {fmt(r['dose_u'], 3)} | {fmt(r['n_doses'], 0)} | {fmt(r['commanded_total_u'], 2)} | {fmt(r['steps_total'], 0)} | "
              f"{fmt(r['corrected_mass_mg'], 1)} | {fmt(r['delivered_u'], 3)} | {fmt(r['error_vs_cmd_pct'])} | {fmt(r['error_vs_steps_pct'])} | "
              f"{fmt(r['u_per_step_meas'], 6)} | {fmt(r['uncertainty_pct'])} | {verdict} |")

    classes = {}
    for r in res:
        classes.setdefault(round(r["dose_u"], 3), []).append(r)
    print("\n## Summary per dose class\n")
    print("| dose U | runs | mean err % | sd % | min % | max % | inside +-5 % | inside +-10 % | mean U/step | conclusive | prediction |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for dose in sorted(classes):
        g = classes[dose]
        e = [x["error_vs_cmd_pct"] for x in g]
        sd = statistics.stdev(e) if len(e) > 1 else float("nan")
        ups = [x["u_per_step_meas"] for x in g if not math.isnan(x["u_per_step_meas"])]
        conc = sum(1 for x in g if x["conclusive"])
        w5 = sum(1 for x in g if x["within_5"])
        w10 = sum(1 for x in g if x["within_10"])
        sim = SIM.get(dose, "")
        print(f"| {dose} | {len(g)} | {fmt(statistics.mean(e))} | {fmt(sd)} | {fmt(min(e))} | {fmt(max(e))} | {w5}/{len(g)} | {w10}/{len(g)} | "
              f"{fmt(statistics.mean(ups), 6) if ups else 'n/a'} | {conc}/{len(g)} | {sim} |")
    print("\nNotes: a single dose below 10 U cannot be verified with a 1 mg balance (see chapter 11.0): the table "
          "judges series. 'INCONCLUSIVE' means the weighing uncertainty exceeds the tolerance: weigh a longer series. "
          "The error vs steps column separates mechanical accuracy (does one step deliver the nominal volume) from "
          "the preset in the firmware; report both. This tool never changes a calibration.")

    if a.csv_out:
        keys = ["run_id", "dose_u", "n_doses", "commanded_total_u", "steps_total", "corrected_mass_mg", "delivered_u", "error_vs_cmd_pct",
                "error_vs_steps_pct", "u_per_step_meas", "per_dose_u", "uncertainty_pct", "verdict", "notes"]
        with open(a.csv_out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(res)


if __name__ == "__main__":
    main()
