"""Electronic components used on the bench boards: ICs, passives and the Ebyte E73-2G4M08S1C module.

Common frame: package centred on XY origin, z = 0 at the seating plane (PCB top surface), +Z up.
Pin 1 is at (-x, +y) for SOT-23-x / QFN (marked with a dimple). Dimensions are JEDEC/vendor package numbers (see META).
"""
from __future__ import annotations

import re

from cc import HERE, Part

ROOT = HERE.parent.parent


# --- generic helpers ----------------------------------------------------------------------------------
def gull(p: Part, name: str, x: float, side: int, y_in: float, y_out: float, z_body: float, w: float, t: float = 0.15,
         foot: float = 0.45) -> str:
    """One gull-wing lead centred at x, on side = +1/-1 (Y), from the body face (|y| = y_in) to tip (|y| = y_out)."""
    yf = y_out - foot
    pts = [(y_in, z_body + t / 2), (yf + 0.15, z_body + t / 2), (yf + 0.05, t), (y_out, t), (y_out, 0.0), (yf - 0.05, 0.0),
           (yf - 0.20, z_body - t / 2), (y_in, z_body - t / 2)]
    pts = [(side * a, b) for a, b in pts]
    p.s.prism_yz(name, pts, x - w / 2, x + w / 2)
    return name


def dimple(p: Part, body: str, x: float, y: float, z_top: float, d: float = 0.35, depth: float = 0.05) -> None:
    p.s.cyl(f"dimple_{body}", "Z", (x, y, 0), d, z_top - depth, z_top + 0.1)
    p.s.cut(body, [f"dimple_{body}"])


def sot23_6(pid: str, title: str, top: float, standoff: float, body_x: float = 2.9, body_y: float = 1.6, span: float = 2.8) -> Part:
    p = Part(pid, title)
    s = p.s
    s.box("body", (-body_x / 2, body_x / 2), (-body_y / 2, body_y / 2), (standoff, top))
    dimple(p, "body", -body_x / 2 + 0.5, body_y / 2 - 0.4, top)
    leads = []
    zb = standoff + min(0.55, (top - standoff) * 0.45)
    for i, x in enumerate((-0.95, 0.0, 0.95)):
        leads.append(gull(p, f"lead{i + 1}", x, +1, body_y / 2, span / 2, zb, 0.40))    # pins 1-3 on +Y? (pin1 at -x,+y)
        leads.append(gull(p, f"lead{i + 4}", x, -1, body_y / 2, span / 2, zb, 0.40))
    p.look("body", "black_ic")
    p.look(leads, "tin")
    p.cfg.update(pitch=0.75, yaw=-0.6, zoom=0.95)
    return p


def sot23_3(pid: str, title: str, top: float = 1.1, standoff: float = 0.05) -> Part:
    p = Part(pid, title)
    s = p.s
    bx, by = 2.9, 1.3
    s.box("body", (-bx / 2, bx / 2), (-by / 2, by / 2), (standoff, top))
    dimple(p, "body", -bx / 2 + 0.5, by / 2 - 0.35, top)
    zb = standoff + 0.4
    leads = [gull(p, "lead1", -0.95, +1, by / 2, 1.2, zb, 0.40), gull(p, "lead2", 0.95, +1, by / 2, 1.2, zb, 0.40),
             gull(p, "lead3", 0.0, -1, by / 2, 1.2, zb, 0.40)]
    p.look("body", "black_ic")
    p.look(leads, "tin")
    p.cfg.update(pitch=0.75, yaw=-0.6, zoom=0.95)
    return p


def x2son4(pid: str, title: str) -> Part:
    p = Part(pid, title)
    s = p.s
    bx, by, h = 1.1, 1.4, 0.4
    s.box("body", (-bx / 2, bx / 2), (-by / 2, by / 2), (0.0, h))
    dimple(p, "body", -0.3, 0.55, h, d=0.2, depth=0.03)
    pads = []
    for i, (x, y) in enumerate([(-0.25, 0.7), (-0.25, -0.7), (0.25, -0.7), (0.25, 0.7)]):   # footprint DMR0004B pad centres
        n = f"pad{i + 1}"
        s.box(n, (x - 0.11, x + 0.11), ((0.3, 0.7) if y > 0 else (-0.7, -0.3)), (-0.005, 0.1))
        pads.append(n)
    s.box("thermal", (-0.4, 0.4), (-0.3, 0.3), (-0.005, 0.1))
    p.look("body", "black_ic")
    p.look(pads + ["thermal"], "tin")
    p.cfg.update(pitch=0.8, yaw=-0.6, zoom=0.95)
    return p


def vfqfpn16(pid: str, title: str) -> Part:
    p = Part(pid, title)
    s = p.s
    D, H = 3.0, 1.0
    s.box("body", (-D / 2, D / 2), (-D / 2, D / 2), (0.0, H))
    s.polyprism("chamfer_tool", [(-D / 2 - 0.1, D / 2 - 0.45), (-D / 2 + 0.45, D / 2 + 0.1), (-D / 2 - 0.1, D / 2 + 0.1)], (-0.1, H + 0.1))
    s.cut("body", ["chamfer_tool"])
    pads = []
    pitch, pw, pl = 0.5, 0.25, 0.4
    k = 0
    for side in range(4):
        for i in range(4):
            off = (i - 1.5) * pitch
            k += 1
            n = f"pad{k}"
            if side == 0:      # left, pin 1 at top
                s.box(n, (-D / 2 - 0.03, -D / 2 + pl), (-off - pw / 2, -off + pw / 2), (0, 0.3))
            elif side == 1:    # bottom
                s.box(n, (off - pw / 2, off + pw / 2), (-D / 2 - 0.03, -D / 2 + pl), (0, 0.3))
            elif side == 2:    # right
                s.box(n, (D / 2 - pl, D / 2 + 0.03), (off - pw / 2, off + pw / 2), (0, 0.3))
            else:              # top
                s.box(n, (-off - pw / 2, -off + pw / 2), (D / 2 - pl, D / 2 + 0.03), (0, 0.3))
            pads.append(n)
    s.box("exposed_pad", (-0.85, 0.85), (-0.85, 0.85), (-0.005, 0.1))
    dimple(p, "body", -D / 2 + 0.55, D / 2 - 0.55, H, d=0.3)
    p.look("body", "black_ic")
    p.look(pads + ["exposed_pad"], "tin")
    p.cfg.update(pitch=0.35, yaw=-0.6, zoom=1.0)
    return p


def chip(pid: str, title: str, L: float, W: float, H: float, term: float, kind: str) -> Part:
    p = Part(pid, title)
    s = p.s
    body_l = L - 2 * term
    if kind == "cap":
        s.box("body", (-body_l / 2, body_l / 2), (-W / 2, W / 2), (0.0, H))
        p.look("body", "cap_brown")
    else:
        s.box("body", (-body_l / 2, body_l / 2), (-W / 2, W / 2), (0.0, H))
        p.look("body", "res_black")
    terms = []
    for i, sg in enumerate((-1, 1)):
        x0, x1 = (sg * body_l / 2, sg * (body_l / 2 + term))
        n = f"term{i + 1}"
        s.box(n, (min(x0, x1) - 0.0, max(x0, x1)), (-W / 2 - 0.0, W / 2), (0.0, H))
        terms.append(n)
    # overlap the terminations slightly over the body ends
    p.look(terms, "tin")
    p.cfg.update(pitch=0.7, yaw=-0.6, zoom=0.95)
    return p


# --- Ebyte E73-2G4M08S1C ------------------------------------------------------------------------------------
E73_W, E73_L, E73_H = 13.0, 18.0, 2.2      # Ebyte data sheet: 13 x 18 x 2.2 mm (total height incl. shield)
E73_PCB_T = 0.8                            # ASSUMED PCB thickness
E73_SHIELD = (12.2, 12.6)                  # shield can footprint: ESTIMATE from photos; antenna keep-out end is free
E73_FP = HERE.parent.parent / "electronics/bench/footprints/Bench.pretty/Ebyte_E73-2G4M08S1C_13x18.kicad_mod"


def e73() -> Part:
    p = Part("ebyte_e73_2g4m08s1c", "Ebyte E73-2G4M08S1C nRF52840 module (shield can + ceramic antenna)")
    s = p.s
    hw, hl = E73_W / 2, E73_L / 2
    s.box("pcb", (-hw, hw), (-hl, hl), (0.0, E73_PCB_T))
    # shield can: sits toward +Y (pad rows 'top'), antenna end at -Y (footprint y>0 is flipped to -Y here)
    sy0, sy1 = 9.0 - E73_SHIELD[1] - 0.2, 9.0 - 0.2
    s.box("shield", (-E73_SHIELD[0] / 2, E73_SHIELD[0] / 2), (sy0, sy1), (E73_PCB_T, E73_H))
    # drawn-in recess panel on the can lid
    s.box("shield_lid", (-E73_SHIELD[0] / 2 + 0.3, E73_SHIELD[0] / 2 - 0.3), (sy0 + 0.3, sy1 - 0.3), (E73_H - 0.05, E73_H + 0.02))
    # ceramic chip antenna at the -Y end, 3.2 x 1.6 x 1.0 (typical 2.4 GHz chip ant. outline - ESTIMATE)
    ay = -hl + 2.2
    s.box("antenna", (-1.6, 1.6), (ay - 0.8, ay + 0.8), (E73_PCB_T, E73_PCB_T + 1.0))
    s.box("ant_feed", (-0.3, 0.3), (ay + 0.8, ay + 1.6), (E73_PCB_T, E73_PCB_T + 0.04))
    # castellated pads + bottom pads from the project footprint (kicad_mod, y flipped for this frame)
    pads = []
    txt = E73_FP.read_text() if E73_FP.exists() else ""
    k = 0
    for m in re.finditer(r'\(pad "(\d+)" smd rect \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+) ([\d.]+)\)', txt):
        num, x, y, sx, sy = m.group(1), float(m.group(2)), -float(m.group(3)), float(m.group(4)), float(m.group(5))
        k += 1
        n = f"pad{num}"
        if abs(abs(x) - 6.325) < 1e-3:       # side castellation: 1.0 deep, 0.8 wide, full PCB thickness
            s.box(n, (5.5, 6.5) if x > 0 else (-6.5, -5.5), (y - 0.4, y + 0.4), (0.0, E73_PCB_T))
        elif abs(abs(y) - 8.825) < 1e-3:     # end castellation
            s.box(n, (x - 0.4, x + 0.4), (8.0, 9.0) if y > 0 else (-9.0, -8.0), (0.0, E73_PCB_T))
        else:                                # inner ground pad, bottom side
            s.box(n, (x - sx / 2, x + sx / 2), (y - sy / 2, y + sy / 2), (-0.03, 0.0))
        pads.append(n)
    p.look("pcb", "fr4_black")
    p.look("shield", "tin")
    p.look("shield_lid", "nickel")
    p.look("antenna", "ceramic")
    p.look("ant_feed", "gold")
    p.look(pads, "gold")
    p.cfg.update(pitch=0.9, yaw=-0.6, zoom=0.95)
    return p


# --- catalogue ------------------------------------------------------------------------------------------------------
def build() -> list[Part]:
    return [
        sot23_6("ic_tmag5273_sot23_6", "TI TMAG5273 3-axis hall, SOT-23-6 (DBV)", top=1.45, standoff=0.1),
        sot23_6("ic_tpl5010_sot23_6", "TI TPL5010 nano-power timer, SOT-23-6 (DDC)", top=1.1, standoff=0.05),
        sot23_3("ic_drv5032_sot23", "TI DRV5032 hall switch, SOT-23-3 (DBZ)"),
        x2son4("ic_drv5032_x2son", "TI DRV5032 hall switch, X2SON-4 (DMR) 1.1x1.4x0.4"),
        vfqfpn16("ic_stspin220_vfqfpn16", "ST STSPIN220 stepper driver, VFQFPN-16 3x3x1.0"),
        chip("c_0402_100nf", "Capacitor 0402 (1.0x0.5), X7R 100 nF", 1.0, 0.5, 0.5, 0.25, "cap"),
        chip("r_0402", "Resistor 0402 (1.0x0.5x0.35)", 1.0, 0.5, 0.35, 0.25, "res"),
        chip("c_0603_10uf", "Capacitor 0603 (1.6x0.8) 10 uF", 1.6, 0.8, 0.8, 0.35, "cap"),
        chip("r_0603", "Resistor 0603 (1.6x0.8x0.45)", 1.6, 0.8, 0.45, 0.35, "res"),
        e73(),
    ]


def _m(title, material, colour, src, conf, notes, frame="package centred on origin, z=0 PCB surface, +Z up; pin 1 at (-x,+y)"):
    return dict(title=title, material=material, colour=colour, frame=frame, source=src, confidence=conf, notes=notes)


META = {
    "ic_tmag5273_sot23_6": _m("TI TMAG5273 3D hall sensor, SOT-23-6 (DBV)", "epoxy mould compound, tin leads", "black / tin",
        "TI TMAG5273 datasheet SBASA27, package DBV0006A: body 2.9 x 1.6, pitch 0.95, lead span 2.8, height 1.45 max; project params.json bench.tmag.pkg [2.9,2.8,1.45]",
        "datasheet", "Gull-wing lead shape simplified; standoff 0.1 assumed (JEDEC MO-178 0.00-0.15)."),
    "ic_tpl5010_sot23_6": _m("TI TPL5010 nano-power system timer, SOT-23-6 (DDC)", "epoxy, tin leads", "black / tin",
        "TI TPL5010 datasheet SNAS675, package DDC0006A (SOT-23-THIN): 2.9 x 1.6 body, pitch 0.95, height 1.1 max",
        "datasheet", "Lead profile simplified."),
    "ic_drv5032_sot23": _m("TI DRV5032 hall switch, SOT-23-3 (DBZ)", "epoxy, tin leads", "black / tin",
        "TI DRV5032 datasheet SLVSDJ0 (package DBZ0003A): body 2.9 x 1.3, height 1.1 max, pitch 0.95, lead span 2.4",
        "datasheet", "Two leads on +Y, one centred on -Y; not used on current boards (bench uses X2SON)."),
    "ic_drv5032_x2son": _m("TI DRV5032 hall switch, X2SON-4 (DMR0004B) 1.1 x 1.4 x 0.4", "epoxy, tin pads", "black / tin",
        "TI DRV5032 datasheet SLVSDJ0 package DMR0004B: 1.1 x 1.4 x 0.4 mm, 4 pads + thermal; pad centres from electronics/bench/footprints DRV5032_X2SON-4 (+-0.25, +-0.7)",
        "datasheet", "KiCad stock library has no X2SON-4 DMR model, so the boards export (below) lacks this part; use this one."),
    "ic_stspin220_vfqfpn16": _m("ST STSPIN220 low-voltage stepper driver, VFQFPN-16 3x3x1.0", "epoxy, tin pads", "black / tin",
        "ST STSPIN220 datasheet DS12078, VFQFPN 3x3x1.0 16L, pitch 0.5, lead width 0.25, exposed pad ~1.7 x 1.7 (project footprint EP 1.7)",
        "datasheet", "Exposed pad modelled 1.7 x 1.7 (the footprint's EP1.7); pin 1 chamfer at -x,+y."),
    "c_0402_100nf": _m("0402 ceramic capacitor (100 nF X7R)", "ceramic, tinned terminations", "brown / tin",
        "EIA 0402: L 1.0 x W 0.5, T 0.5, termination band 0.25 (typical MLCC series, e.g. Samsung CL05B104KO5NNNC)", "datasheet", "Typical; band width 0.15-0.35 across vendors.", frame="centred on origin, z=0 PCB surface; length along X"),
    "r_0402": _m("0402 thick-film resistor", "alumina, tinned terminations", "black / tin",
        "EIA 0402: 1.0 x 0.5, T 0.35, terminations 0.25 (typical, e.g. Uniroyal 0402WGF series)", "datasheet", "Typical.", frame="centred on origin, z=0 PCB surface; length along X"),
    "c_0603_10uf": _m("0603 ceramic capacitor (10 uF)", "ceramic, tinned terminations", "brown / tin",
        "EIA 0603: 1.6 x 0.8, T 0.8 (10 uF class is 0.8-0.95), termination 0.35", "datasheet", "Typical.", frame="centred on origin, z=0 PCB surface; length along X"),
    "r_0603": _m("0603 thick-film resistor", "alumina, tinned terminations", "black / tin",
        "EIA 0603: 1.6 x 0.8, T 0.45, terminations 0.35 (typical)", "datasheet", "Typical.", frame="centred on origin, z=0 PCB surface; length along X"),
    "ebyte_e73_2g4m08s1c": _m("Ebyte E73-2G4M08S1C nRF52840 module", "FR4 black soldermask, tinned steel can, ceramic chip antenna, ENIG castellations", "black / tin / ceramic / gold",
        "Ebyte E73-2G4M08S1C product data sheet: 13 x 18 x 2.2 mm, 43 castellated/ground pads at 1.27 pitch; pad geometry taken from the project footprint (electronics/bench/footprints/Bench.pretty/Ebyte_E73-2G4M08S1C_13x18.kicad_mod)",
        "datasheet (outline, pads) / estimated (shield, antenna, PCB thickness)",
        "Shield can outline 12.2 x 12.6 and chip antenna 3.2 x 1.6 x 1.0 are ESTIMATES (measured-sample TODO). NOTE repo "
        "parts.json says the '-C' lcsc variant has IPEX while the spec asks for the ceramic-antenna version: confirm which is ordered.",
        frame="module centred on origin, bottom (pads) at z=0, +Z up, antenna end toward -Y, pad row end toward +Y"),
}

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
