"""GHW-Modellbau brass spur gears, module 0.3, true involute teeth (parametric).

Local frame: Z = bore axis. Toothed section spans z = 0 .. width; a hub (if any) extends below, z = -hub_l .. 0
(GHW lists the hub length separately from the face width; hub taken as protruding beyond the tooth width - VERIFY on sample).
Tooth 0 is centred on +X; `phase` rotates the whole gear (rad) so a mating pair can be phased in the assembly.
"""
from __future__ import annotations

import math

from cc import Part, inv


def gear_profile(m: float, z: int, pa_deg: float = 20.0, n_flank: int = 7, phase: float = 0.0):
    rp = m * z / 2
    a = math.radians(pa_deg)
    rb = rp * math.cos(a)
    ra = rp + m          # GHW: da = m (z + 2)
    rf = rp - 1.25 * m   # standard root, dedendum 1.25 m
    r0 = max(rb, rf)

    def half(r):         # half tooth angle at radius r
        ar = math.acos(min(rb / r, 1.0))
        return math.pi / (2 * z) + inv(a) - inv(ar)

    rs = [r0 + (ra - r0) * (i / (n_flank - 1)) ** 1.0 for i in range(n_flank)]
    pts = []
    for i in range(z):
        psi = 2 * math.pi * i / z + phase
        R = [(r, psi - half(r)) for r in rs]                 # right flank, outward
        L = [(r, psi + half(r)) for r in reversed(rs)]       # left flank, inward
        seg = []
        if rf < rb:
            seg.append((rf, psi - half(r0)))                  # radial run-in from the root circle
        seg += R
        seg.append((ra, psi))                                 # tip mid-point
        seg += L
        if rf < rb:
            seg.append((rf, psi + half(r0)))
        # root arc to the next tooth
        nxt = 2 * math.pi * (i + 1) / z + phase - half(r0)
        cur = psi + half(r0)
        seg.append((rf, (cur + nxt) / 2))
        pts += seg
    xy = [(round(r * math.cos(t), 5), round(r * math.sin(t), 5)) for r, t in pts]
    return xy, dict(rp=rp, rb=rb, ra=ra, rf=rf)


def spur_gear(pid: str, title: str, m: float, z: int, bore: float, width: float,
              hub_d: float = 0.0, hub_l: float = 0.0, phase: float = 0.0) -> Part:
    p = Part(pid, title)
    s = p.s
    xy, g = gear_profile(m, z, phase=phase)
    s.polyprism("gear", xy, (0.0, width))
    if hub_d > 0 and hub_l > 0:
        s.cyl("hub", "Z", (0, 0, 0), hub_d, -hub_l, 0.0)
        s.join("gear", ["hub"])
    s.cyl("bore_tool", "Z", (0, 0, 0), bore, -hub_l - 0.1, width + 0.1)
    s.cut("gear", ["bore_tool"])
    p.look("gear", "brass")
    p.cfg["pitch"] = 0.9
    p.cfg["yaw"] = -0.5
    p.gear = g
    return p


# (id, title, z, bore, width, hub_d, hub_l, ghw article, row status)
GEARS = [
    ("gear_m03_z15_753015", "GHW 753015 spur gear m0.3 z15 bore 2.0, thin 1.4 mm with hub", 15, 2.0, 1.4, 4.0, 2.5, "753015"),
    ("gear_m03_z12_753012", "GHW 753012 spur gear m0.3 z12 bore 1.5, width 4", 12, 1.5, 4.0, 0.0, 0.0, "753012"),
    ("gear_m03_z16_390754", "GHW 390754 spur gear m0.3 z16 bore 2.0, width 5 (motor gear, final pair)", 16, 2.0, 5.0, 0.0, 0.0, "390754"),
    ("gear_m03_z20_753020", "GHW 753020 spur gear m0.3 z20 bore 2.0, thin 1.4 mm with hub (screw gear, final pair)", 20, 2.0, 1.4, 4.0, 2.5, "753020"),
    ("gear_m03_z18_390755", "GHW 390755 spur gear m0.3 z18 bore 2.0, width 5", 18, 2.0, 5.0, 0.0, 0.0, "390755"),
]


def build() -> list[Part]:
    parts = []
    for pid, title, z, bore, w, hd, hl, art in GEARS:
        pt = spur_gear(pid, title, 0.3, z, bore, w, hd, hl)
        parts.append(pt)
    return parts


def _meta(pid, z, bore, w, hd, hl, art):
    m = 0.3
    return dict(
        title=f"GHW-Modellbau brass spur gear module 0.3, z={z}, bore {bore}, width {w}"
              + (f", hub d{hd} x {hl}" if hd else ""),
        material="brass Ms58 (CW614N / 2.0401)", colour="brass",
        frame="Z = bore axis; teeth z 0..width, hub (if any) z -hub_l..0; tooth 0 centred on +X",
        source=f"ghw-modellbau.de page 'Spur gear Brass Module 0.3' (article {art}): z, bore, da={m*(z+2):.1f}, "
               f"d={m*z:.1f}, width, hub d/length as tabulated. Involute 20 deg PA, root 1.25 m computed (GHW publishes no profile drawing)",
        confidence="datasheet (catalogue table); tooth profile computed",
        notes="Tooth form is the standard 20 deg involute (profile not published by GHW: measured-sample TODO, esp. "
              "tip/root rounding and hub length convention).",
    )


META = {g_[0]: _meta(*g_[:1], g_[2], g_[3], g_[4], g_[5], g_[6], g_[7]) for g_ in GEARS}


if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
