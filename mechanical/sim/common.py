"""Shared context for the OpenPatch bench-pod simulations.

Everything geometric is read from ../params.json (and, where present, ../out/bench/OP-xx.mech.json written by
generate.py), so `python3 run_all.py` re-evaluates the design after every CAD change.  Material / process
assumptions live in CONST below, each with a source or an explicit ASSUMPTION tag.

TEST PROJECT, bench use only (WATER ONLY, never insulin or any drug), never on a person.
"""
from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass, field

HERE = pathlib.Path(__file__).resolve().parent
MECH = HERE.parent
GF_CM = 0.0980665          # 1 gf*cm in N*mm
PI = math.pi

# ----------------------------------------------------------------------------------------------------------
# Constants.  (lo, nominal, hi) tuples are used for sensitivity / Monte Carlo.  Tag: [DS] datasheet / vendor
# page, [LIT] textbook or literature (order of magnitude), [ASM] assumption to be settled on the bench.
# ----------------------------------------------------------------------------------------------------------
CONST = {
    # motor NFP-608-26.45-SGM
    "T_pullout_gfcm": 1.6,            # [DS] nfpshop listing: pull-out 1.6 gf*cm @ 500 pps (rated 4.8 V)
    "pullout_pps": 500.0,             # [DS]
    "motor_V": 4.8, "motor_R": 26.5,  # [DS]
    "I_set_mA": 105.0,                # firmware-rs limits.rs + electronics/bench/pin-assignment.md: VREF 0.105 V / 1.0 ohm
    "pullout_droop_exp": 0.5,         # [ASM] only one point of the curve is published: T ~ (500/f)^0.5 above 500 pps
    "hold_over_pullout": 1.3,         # [ASM] stall/holding torque vs pull-out torque (typical micro stepper 1.2-1.6)
    "gh_eff": (0.50, 0.64, 0.81),     # [LIT/ASM] 2-stage planetary: 0.8 per stage nominal (spec 4 uses 0.64)
    "pair_eff": (0.90, 0.95, 0.98),   # [LIT] small brass spur pair, dry
    "mu_thread": (0.15, 0.22, 0.35),  # [LIT] steel/stainless on brass nut, dry..lubed (task range 0.15-0.35)
    "mu_collar": (0.10, 0.18, 0.30),  # [ASM] brass gear / bush end face on printed PA12 or PTFE
    "thread_half_angle_deg": 30.0,    # ISO metric
    # seal (platinum-cure silicone lip rings in a PP bore)
    "shore_A": (30.0, 40.0, 50.0),    # parts list: Shore A 40
    "mu_seal": (0.15, 0.40, 0.90),    # [ASM/LIT] lubed .. wetted .. dry silicone on PP
    "mu_seal_design": (0.12, 0.22, 0.40),   # [LIT/ASM] PDMS bead on PP with a 350 cSt silicone-oil film, boundary regime at < 0.2 mm/s (syringe glide data 0.1-0.3)
    "mu_guide": (0.06, 0.10, 0.20),   # [ASM] design condition: core flange guide bands wrapped with 0.1 mm PTFE tape (PTFE on PP ~0.1) + oil film
    "mu_guide_bare": (0.08, 0.15, 0.30),   # [ASM] bare resin flange vs PP bore, oil-wetted (dry resin on PP: 0.3-0.4 -> jams, see seal_model.cocking_factor)
    "mould_tol_diam": 0.05,           # [ASM] +-0.05 mm on the printed cavity diameter (SLA)
    "shrink_range": (0.001, 0.002, 0.003),  # [LIT] platinum PDMS linear cast shrinkage
    "shore_scatter": 4.0,             # [ASM] Shore A +- from mixing ratio / cure
    "valve_void_frac": 0.12,          # [ASM] internal cavity of a micro duckbill as a fraction of its envelope
    "breakaway": (1.2, 1.5, 2.5),     # [ASM] static/kinetic friction ratio incl. dwell
    "silicone_shrink": 0.002,         # [LIT] platinum-cure linear cast shrinkage ~0.1-0.3 %
    # materials
    "PA12_MJF": {"E": 1700.0, "eps_allow_snap": 0.030, "eps_yield": 0.045, "sigma_flex": 45.0, "tol": 0.10},   # [DS] HP PA12 / ASM
    "SLA_tough": {"E": 1500.0, "eps_allow_snap": 0.020, "eps_yield": 0.027, "sigma_flex": 40.0, "tol": 0.05},  # [ASM] Tough/Durable class resin
    "SLA_std": {"E": 2600.0, "eps_allow_snap": 0.012, "eps_yield": 0.015, "sigma_flex": 60.0, "tol": 0.05},    # [ASM] standard (brittle) resin
    "steel_E": 193000.0,              # [LIT] A2 stainless
    "brass_sigma_bend": 110.0,        # [LIT] CuZn39Pb3 fatigue bending allowable (Ms58)
    "PP_E": 1500.0, "PP_nu": 0.42, "PP_yield": 30.0, "PP_alpha": 1.5e-4,   # [LIT]
    # fluids
    "mu_insulin": (0.9e-3, 1.1e-3, 1.6e-3),   # Pa*s water-like U100 at 25 C .. 10 C
    "P_atm_kPa": 101.3,
    # needle gauges: (OD, ID) mm, typical stainless regular-wall tube [LIT: ISO 9626 / gauge charts, +-0.01]
    "needles": {"27G": (0.413, 0.210), "28G": (0.361, 0.184), "29G": (0.337, 0.184), "30G": (0.311, 0.159), "31G": (0.261, 0.133)},
    # print / machining tolerance (symmetric, +- per feature position), task statement
    "tol_MJF": 0.10, "tol_SLA": 0.05,
    # gears DIN 58405 quality 8d [ASM]
    "gear_j0": (0.015, 0.03, 0.045),  # minimum normal-plane backlash of the pair at exact centre distance (mm)
    "pressure_angle": 20.0,
}


def area_stadium(w: float, h: float) -> float:
    return h * (w - h) + PI * h * h / 4.0


def perim_stadium(w: float, h: float) -> float:
    return 2.0 * (w - h) + PI * h


def lewis_Y(z: int) -> float:
    """Lewis form factor (Y, 20 deg full depth), Shigley table, linear interpolation."""
    t = {10: 0.201, 12: 0.245, 13: 0.261, 14: 0.277, 15: 0.290, 16: 0.296, 17: 0.303, 18: 0.309, 19: 0.314, 20: 0.322, 21: 0.328,
         22: 0.331, 24: 0.337, 26: 0.346, 28: 0.353, 30: 0.359}
    ks = sorted(t)
    if z <= ks[0]:
        return t[ks[0]]
    for a, b in zip(ks, ks[1:]):
        if a <= z <= b:
            return t[a] + (t[b] - t[a]) * (z - a) / (b - a)
    return t[ks[-1]]


@dataclass
class Row:
    id: str
    area: str
    requirement: str
    value: str
    margin: str
    status: str            # PASS / WARN / FAIL / INFO
    note: str = ""


@dataclass
class Result:
    name: str
    rows: list = field(default_factory=list)
    md: str = ""


def status(ok: bool, warn: bool = False) -> str:
    return "PASS" if ok else ("WARN" if warn else "FAIL")


class Ctx:
    def __init__(self, size_filter=None):
        self.P = json.loads((MECH / "params.json").read_text())
        P = self.P
        self.sizes = [s for s in P["variants"] if (size_filter is None or s in size_filter)]
        self.mech = {}
        self.layout = {}
        for s in self.sizes:
            f = MECH / "out" / "bench" / f"{s}.mech.json"
            if f.exists():
                self.mech[s] = json.loads(f.read_text())
            f = MECH / "out" / "bench" / f"{s}.layout.json"
            if f.exists():
                self.layout[s] = json.loads(f.read_text())
        dr = P["drive"]
        fz = P["reservoir_frozen"]
        self.w_in, self.h_in = fz["bore_w"], fz["bore_h"]
        self.A = area_stadium(self.w_in, self.h_in)
        self.perim = perim_stadium(self.w_in, self.h_in)
        self.pitch = dr["screw_pitch"]
        self.spr = dr["steps_per_rev"]
        preset = P["drive_presets"][dr["active_preset"]]
        self.preset = preset
        self.gh = preset["gh_ratio"]
        g = P["bench"]["gears"]
        self.module = g["module"]
        self.min_centre = g["min_centre"]
        self.active = (g["z_motor"], g["z_screw"])
        self.layout_kind = P["bench"].get("drive_layout", "side_gears")
        self.shared: dict = {}
        self.pngdir = HERE / "plots"
        self.pngdir.mkdir(exist_ok=True)

    def gear_options(self):
        """The CAD's active pair first, then the spec pair and step-down alternatives (all module 0.3)."""
        opts = [("%d:%d (CAD)" % self.active, *self.active)]
        for zm, zs in ((15, 12), (15, 15), (18, 18), (16, 20), (15, 21), (12, 15)):
            if (zm, zs) != self.active:
                opts.append(("%d:%d" % (zm, zs), zm, zs))
        return opts

    def centre(self, zm, zs):
        return self.module * (zm + zs) / 2.0

    def u_per_step(self, zm, zs, A=None):
        """U per full motor step (U100: 10 mm3 = 1 U)."""
        return self.pitch * (zm / zs) / (self.spr * self.gh) * (A or self.A) / 10.0

    def stroke(self, size):
        return self.P["variants"][size]["stroke"]

    def screw_span(self, size):
        """Free screw length dry-end collar -> nut with the carriage at the front (full delivery) [mm].
        Rear carriage position and collar are taken from the OP-100 / OP-70 mech.json (side-gear layout); the OP-200 json of the
        old coaxial snapshot is not used, only the stroke differs between sizes."""
        ref = None
        for s in ("OP-100", "OP-70"):
            if s in self.mech and self.mech[s].get("drive_layout", "side_gears") == "side_gears" and self.mech[s]["x_r0"] < 10:
                ref = self.mech[s]
                break
        xrear = ref["xrear_full"] if ref else 4.3
        collar = ref["dry_bush"][1] if ref else 1.9
        return xrear + self.stroke(size) - collar

    def save(self, fig, name):
        p = self.pngdir / name
        fig.savefig(p, dpi=120, bbox_inches="tight")
        return f"plots/{name}"


def fmt(x, n=3):
    if isinstance(x, str):
        return x
    if x != 0 and (abs(x) >= 1e4 or abs(x) < 10 ** -(n)):
        return f"{x:.{n-1}e}"
    return f"{x:.{n}g}"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out) + "\n"


PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#555555"]
