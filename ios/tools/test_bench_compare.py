"""Tests for bench_compare.py. Run from ios/tools: python3 -I -m unittest"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_compare as bc  # noqa: E402

T0 = bc.parse_timestamp("2026-11-19T10:00:00Z")
G_PER_U = 1.0 / bc.units_per_gram(bc.DEFAULT_DENSITY_G_PER_ML)  # 0.009982 g


def iso(offset_s):
    return bc.format_timestamp(T0 + offset_s)


def synth_balance(delivery, minutes=40, step_s=30, tare=25.0, scale=1.0, evap_mg_per_min=0.0):
    """delivery(t_s) -> cumulative units. Returns CSV text."""
    lines = ["timestamp_iso8601,mass_g"]
    for k in range(0, minutes * 60 // step_s + 1):
        t = k * step_s
        mass = tare + delivery(t) * scale * G_PER_U - evap_mg_per_min / 1000.0 * t / 60.0
        lines.append(f"{iso(t)},{mass:.5f}")
    return "\n".join(lines) + "\n"


def bolus_curve(events, rate_u_per_s=1.5 / 60):
    """events [(t_s, units)] delivered linearly at 1.5 U/min."""
    def cum(t):
        total = 0.0
        for t_e, u in events:
            total += min(u, max(0.0, (t - t_e) * rate_u_per_s))
        return total
    return cum


DOSES_HEADER = "timestamp_iso8601,kind,units,duration_min,rate_u_per_h\n"


class BenchCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_compare(self, balance_text, doses_text, **kwargs):
        bal = bc.load_balance(self.write("balance.csv", balance_text))
        dos = bc.load_doses(self.write("doses.csv", doses_text))
        return bc.compare(bal, dos, **kwargs)

    BOLUSES = DOSES_HEADER + (
        "2026-11-19T10:05:00Z,bolus,1.0,,\n"
        "2026-11-19T10:15:00Z,smb,0.5,,\n"
        "2026-11-19T10:25:00Z,bolus,2.0,,\n"
    )
    EVENTS = [(300, 1.0), (900, 0.5), (1500, 2.0)]

    def test_perfect_match_passes(self):
        r = self.run_compare(synth_balance(bolus_curve(self.EVENTS)), self.BOLUSES)
        self.assertAlmostEqual(r["totals"]["reported_u"], 3.5)
        self.assertAlmostEqual(r["totals"]["measured_u"], 3.5, places=3)
        self.assertEqual(r["verdict"]["result"], "PASS")
        self.assertEqual(len(r["boluses"]), 3)
        for b in r["boluses"]:
            self.assertEqual(b["status"], "ok")
            self.assertLess(abs(b["error_pct"]), 1.0)

    def test_three_percent_under_delivery(self):
        text = synth_balance(bolus_curve(self.EVENTS), scale=0.97)
        r = self.run_compare(text, self.BOLUSES)
        self.assertAlmostEqual(r["totals"]["diff_pct"], -3.0, places=1)
        self.assertEqual(r["verdict"]["result"], "PASS")
        r2 = self.run_compare(text, self.BOLUSES, tolerance_pct=2.0)
        self.assertEqual(r2["verdict"]["result"], "FAIL")

    def test_ten_percent_under_delivery_fails(self):
        r = self.run_compare(synth_balance(bolus_curve(self.EVENTS), scale=0.90), self.BOLUSES)
        self.assertEqual(r["verdict"]["result"], "FAIL")

    def test_below_min_units_is_inconclusive(self):
        doses = DOSES_HEADER + "2026-11-19T10:05:00Z,bolus,0.5,,\n"
        r = self.run_compare(synth_balance(bolus_curve([(300, 0.5)])), doses)
        self.assertEqual(r["verdict"]["result"], "INCONCLUSIVE")

    def test_evaporation_drift_correction(self):
        text = synth_balance(bolus_curve(self.EVENTS), evap_mg_per_min=1.0)
        uncorrected = self.run_compare(text, self.BOLUSES)
        corrected = self.run_compare(text, self.BOLUSES, evaporation_mg_per_min=1.0)
        self.assertEqual(uncorrected["verdict"]["result"], "FAIL")  # 40 mg lost = 4 U
        self.assertAlmostEqual(corrected["totals"]["measured_u"], 3.5, places=2)
        self.assertEqual(corrected["verdict"]["result"], "PASS")

    def test_temp_basal_clipped_to_next_temp_and_run_end(self):
        doses = DOSES_HEADER + (
            "2026-11-19T10:00:00Z,temp_basal,,30,2.4\n"   # clipped at 10:10 -> 0.4 U
            "2026-11-19T10:10:00Z,temp_basal,,60,1.2\n"   # clipped at 10:40 (run end) -> 0.6 U
        )
        r = self.run_compare(synth_balance(lambda t: 0.0), doses)
        self.assertAlmostEqual(r["totals"]["reported_u"], 1.0, places=6)

    def test_suspend_gates_temp_basal_and_boluses(self):
        doses = DOSES_HEADER + (
            "2026-11-19T10:00:00Z,temp_basal,,30,2.4\n"   # runs 10 min before suspend -> 0.4 U
            "2026-11-19T10:10:00Z,suspend,,,\n"
            "2026-11-19T10:15:00Z,bolus,1.0,,\n"          # dropped, suspended
            "2026-11-19T10:20:00Z,temp_basal,,30,3.0\n"   # dropped, suspended
            "2026-11-19T10:30:00Z,resume,,,\n"
            "2026-11-19T10:31:00Z,bolus,1.0,,\n"          # counted
        )
        r = self.run_compare(synth_balance(lambda t: 0.0), doses)
        self.assertAlmostEqual(r["totals"]["reported_u"], 1.4, places=6)
        self.assertEqual(len(r["warnings"]), 2)

    def test_doses_outside_run_are_ignored(self):
        doses = DOSES_HEADER + "2026-11-19T09:00:00Z,bolus,1.0,,\n2026-11-19T11:00:00Z,smb,1.0,,\n"
        r = self.run_compare(synth_balance(lambda t: 0.0), doses)
        self.assertEqual(r["totals"]["reported_u"], 0.0)
        self.assertEqual(len(r["warnings"]), 2)

    def test_windows_sum_to_total(self):
        r = self.run_compare(synth_balance(bolus_curve(self.EVENTS)), self.BOLUSES, window_min=15)
        self.assertEqual(len(r["windows"]), 3)
        self.assertAlmostEqual(sum(w["reported_u"] for w in r["windows"]), 3.5, places=6)
        self.assertAlmostEqual(sum(w["measured_u"] for w in r["windows"]), 3.5, places=3)

    def test_bolus_without_step_is_flagged(self):
        r = self.run_compare(synth_balance(lambda t: 0.0), self.BOLUSES)
        self.assertTrue(all(b["status"] == "NO CLEAR STEP" for b in r["boluses"]))

    def test_density_from_temperature(self):
        self.assertAlmostEqual(bc.water_density_g_per_ml(20.0), 0.99821, places=4)
        self.assertAlmostEqual(bc.units_per_gram(0.9982), 100.18, places=2)

    def test_missing_file_error(self):
        with self.assertRaises(bc.CsvError) as ctx:
            bc.load_balance(os.path.join(self.tmp.name, "nope.csv"))
        self.assertIn("file not found", str(ctx.exception))

    def test_malformed_inputs_give_clear_errors(self):
        with self.assertRaisesRegex(bc.CsvError, "missing column"):
            bc.load_balance(self.write("a.csv", "time,grams\n1,2\n"))
        bad = "timestamp_iso8601,mass_g\n2026-11-19T10:00:00Z,1\n2026-11-19T10:00:30Z,x\n"
        with self.assertRaisesRegex(bc.CsvError, "line 3.*not a number"):
            bc.load_balance(self.write("b.csv", bad))
        with self.assertRaisesRegex(bc.CsvError, "ISO 8601"):
            bc.load_balance(self.write("c.csv", "timestamp_iso8601,mass_g\nyesterday,1\n"))
        with self.assertRaisesRegex(bc.CsvError, "unknown kind"):
            bc.load_doses(self.write("d.csv", DOSES_HEADER + "2026-11-19T10:00:00Z,pizza,1,,\n"))
        with self.assertRaisesRegex(bc.CsvError, "needs a value in column units"):
            bc.load_doses(self.write("e.csv", DOSES_HEADER + "2026-11-19T10:00:00Z,bolus,,,\n"))
        with self.assertRaisesRegex(bc.CsvError, "empty"):
            bc.load_doses(self.write("f.csv", ""))

    def test_timestamp_offsets(self):
        self.assertEqual(bc.parse_timestamp("2026-11-19T11:00:00+01:00"), T0)
        self.assertEqual(bc.parse_timestamp("2026-11-19 10:00:00.5"), T0 + 0.5)

    def test_cli_exit_codes_and_json(self):
        bal = self.write("balance.csv", synth_balance(bolus_curve(self.EVENTS)))
        dos = self.write("doses.csv", self.BOLUSES)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = bc.main(["--doses", dos, "--balance", bal, "--json"])
        self.assertEqual(code, bc.EXIT_PASS)
        self.assertEqual(json.loads(out.getvalue())["verdict"]["result"], "PASS")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = bc.main(["--doses", dos, "--balance", os.path.join(self.tmp.name, "missing.csv")])
        self.assertEqual(code, bc.EXIT_ERROR)
        self.assertIn("error: file not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
