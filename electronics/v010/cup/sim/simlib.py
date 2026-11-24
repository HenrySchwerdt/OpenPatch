"""Shared helpers for the cup-board SPICE runs: ngspice runner, wrdata reader, board blocks (netlist text).

All circuit values come from electronics/v010/netlist_v4_cup.json (the 45-part cup board); every assumed value is labelled ASSUMPTION.
Repo-relative paths only; decks are written to results/ (gitignored for .csv/.raw, .cir/.log kept small).
"""
import os
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
LIB = os.path.join(HERE, "lib")
MODELS = os.path.join(HERE, "models")
os.makedirs(RES, exist_ok=True)

# ---- component values (netlist_v4_cup.json) and assumptions -----------------------------------------------------------------
# ASSUMPTION cell: Ampul 301030 90 mAh (60 mAh realistic) + its protection circuit + soldered leads. The listing gives no ESR.
#   A 60..90 mAh Li-Po pouch cell has about 0.4..0.7 ohm at 1 kHz at 25 C, 50 % SOC; protection FETs + leads add about 0.15 ohm
#   -> 0.8 ohm is used as the nominal value, 0.5 / 1.2 / 1.6 ohm as sweep (warm full cell / cold or aged / cold + aged + low SOC).
RINT_NOM = 0.8
C5_EFF = 6e-6        # C5 10 uF 10 V 0603 X5R, ~55 % left at 3.7 V (ASSUMPTION)
CB1_EFF = 8e-6       # CB1 22 uF 10 V 0805 X5R: 8 uF = conservative figure of the netlist note (10 V part keeps ~11 uF at 5 V); case 1 sweeps 2..30 uF
C21_EFF = 8e-6       # C21, same part, on VMOT (driver VM bulk)
C60 = 0.1e-6
L1 = 1e-6            # WPN252012E1R0MT
R_ILIM = 47e3
R_COIL = 26.5        # NFP-608-26.45-SGM, per phase
L_COIL = 5e-3        # ASSUMPTION: no datasheet value in the repo; 6 mm PM stepper class 3..10 mH, swept 2..15 mH in case 4
R_BRIDGE = 0.28      # DRV8838 HS+LS on resistance (TI SLVSBA4F typ 280 mOhm, max 330; DRV8835 before: 0.305)
I_NRF = 5e-3         # ASSUMPTION: nRF52840 + supervisor etc. on VBAT through REG0 (INTERLOCK I.7 estimate 4..7 mA)


def ngspice(deck_text, name, mode="std", timeout=600):
    """Run a deck. mode 'ps' = ngspice PSpice compatibility (needed for the vendor TPS2553 model). Returns (stdout, csv path)."""
    deck = deck_text.replace("@LIB@", LIB).replace("@MODELS@", MODELS).replace("@RES@", RES)
    cir = os.path.join(RES, name + ".cir")
    with open(cir, "w") as f:
        f.write(deck)
    cwd = tempfile.mkdtemp(prefix="ngs_")     # own cwd so that .spiceinit selects the compat mode per run
    with open(os.path.join(cwd, ".spiceinit"), "w") as f:
        f.write("set ngbehavior=%s\nset noaskquit\n" % ("psa" if mode == "ps" else "all"))
    r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, cwd=cwd, timeout=timeout)
    out = r.stdout + r.stderr
    with open(os.path.join(RES, name + ".log"), "w") as f:
        f.write(out[-20000:])
    return out


class Wave:
    """wrdata output: first column time, then (x, y) pairs per vector."""

    def __init__(self, path, names):
        d = np.loadtxt(path)
        self.t = d[:, 0]
        self.v = {n: d[:, 1 + 2 * i] for i, n in enumerate(names)}

    def __getitem__(self, n):
        return self.v[n]

    def at(self, n, t):
        return float(np.interp(t, self.t, self.v[n]))

    def window(self, n, t0, t1):
        m = (self.t >= t0) & (self.t <= t1)
        return self.v[n][m]

    def first_cross(self, n, level, t0=0.0, rising=True):
        y = self.v[n]
        for i in range(1, len(self.t)):
            if self.t[i] < t0:
                continue
            if rising and y[i - 1] < level <= y[i] or (not rising) and y[i - 1] > level >= y[i]:
                a = (level - y[i - 1]) / (y[i] - y[i - 1] + 1e-30)
                return float(self.t[i - 1] + a * (self.t[i] - self.t[i - 1]))
        return None


# ---- circuit snippets (node names follow netlist_v4_cup.json) ------------------------------------------------------------------
def snip_cell(ocv, rint=RINT_NOM, extra=""):
    return ("* cell: OCV source + internal resistance (ASSUMPTION, see simlib.RINT_NOM)\nVcell vc 0 %s\nRint vc vbat %g\nC5 vbat 0 %g\n"
            "Inrf vbat 0 %g\n%s\n" % (ocv, rint, C5_EFF, I_NRF, extra))


def snip_boost(en_node="sup_permit", cb=CB1_EFF, model="TPS61023_BEH", extra_params=""):
    return ("* TPS61023 boost, 5 V (FB 220k/30k -> 4.96 V)\nL1 vbat sw %g\nXU8 %s fb 0 sw vbat vmot_pre %s %s\nR55 vmot_pre fb 220k\nR56 fb 0 30k\n"
            "CB1 vmot_pre 0 %g\nC60 vmot_pre 0 %g\n" % (L1, en_node, model, extra_params, cb, C60))


def snip_switch(en_node="mot_allow", c21=C21_EFF, rilim=R_ILIM):
    # PWPD (thermal pad pin of the model) tied to GND as on the board (DBV-6 has none)
    return ("* TPS2553 load switch (TI PSpice model) + ILIM + FAULT pull-up + VM bulk + sense divider/bleeder\n"
            "XU20 vmot_pre 0 %s 0 oc_ok ilim vmot TPS2553_TRANS\nR91 ilim 0 %g\nR92 v3v3 oc_ok 100k\nC21 vmot 0 %g\nR57 vmot vsense 10k\nR58 vsense 0 10k\n"
            % (en_node, rilim, c21))


def snip_motor_res(rscale=1.0, short_t=None, short_r=0.5, rbridge=R_BRIDGE):
    """both windings energised (full step hold or stall): 2 x (R_coil + bridge) in parallel with an optional bridge/winding short."""
    r = (R_COIL * rscale + rbridge)
    s = "* motor, both phases on, resistance-limited (no chopper): 2 x %.2f ohm\nRm1 vmot m1 %g\nLm1 m1 0 %g\nRm2 vmot m2 %g\nLm2 m2 0 %g\n" % (r, r, L_COIL, r, L_COIL)
    if short_t is not None:
        s += "Bshort vmot 0 I = (time > %g) ? v(vmot) / %g : 0\n" % (short_t, short_r)
    return s


SPICE_OPTS = ".options method=gear reltol=0.003 gmin=1e-12 abstol=1e-10\n"


def run_wave(deck_text, name, names, mode="std"):
    """deck must end its .control block with `wrdata @RES@/<name>.csv <vectors>`; returns (Wave or None, log)."""
    path = os.path.join(RES, name + ".csv")
    if os.path.exists(path):
        os.remove(path)
    out = ngspice(deck_text, name, mode)
    if not os.path.exists(path):
        return None, out
    w = Wave(path, names)
    w.aborted = "aborted" in out        # a run that stops (timestep too small) keeps the data up to that point
    return w, out
