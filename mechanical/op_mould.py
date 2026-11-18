"""Two-part silicone mould for the plunger lip seals (independent of pump size).

Cavity = core envelope (plunger core, 15.6 x 4.6) + two ring slabs at the free (cast) size
(bore + seal.free_oversize).  The cast silicone fills cavity minus core, i.e. the two grooves.
Split plane z = split_h; X = plunger axis.
"""
from __future__ import annotations

from op_cmds import Script


def build_mould(p: dict) -> tuple[Script, dict]:
    rs, sl, md = p["reservoir"], p["seal"], p["mould"]
    s = Script()
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd, pl = sl["groove_depth"], rs["plunger_len"]
    m, sh = md["margin"], md["split_h"]
    bx = pl + 2 * m
    by = rs["w_in"] + sl["free_oversize"] + 2 * m
    yc, zc = by / 2, sh
    x0 = m                                           # core starts here
    # core (for the fit check; not exported)
    s.stadium("plunger_core", (x0, x0 + pl), yc, zc, wc, hc)
    s.stadium_ring("t_gr0", (x0 + sl["ring_a"][0], x0 + sl["ring_a"][1]), yc, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
    s.stadium_ring("t_gr1", (x0 + sl["ring_b"][0], x0 + sl["ring_b"][1]), yc, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
    s.cut("plunger_core", ["t_gr0", "t_gr1"])
    # lower / upper blocks
    s.box("mould_lower", (0, bx), (0, by), (0, sh))
    s.box("mould_upper", (0, bx), (0, by), (sh, 2 * sh))
    cc = md["core_clr"]
    for nm in ("mould_lower", "mould_upper"):
        t = [s.stadium(f"t_{nm}_core", (x0 - 0.0, x0 + pl), yc, zc, wc + 2 * cc, hc + 2 * cc)]
        for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
            t.append(s.stadium(f"t_{nm}_r{k}", (x0 + a, x0 + b), yc, zc, rs["w_in"] + sl["free_oversize"],
                               rs["h_in"] + sl["free_oversize"]))
        s.cut(nm, t)
    # sprues (feed, 22G syringe) and vents in the upper half, one pair per ring
    cuts = []
    for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
        xm = x0 + (a + b) / 2
        cuts.append(s.cyl(f"t_sp{k}", "Z", (xm, yc + 6.5, 0), md["sprue_d"], sh + 0.5, 2 * sh + 0.1))
        cuts.append(s.cyl(f"t_vt{k}", "Z", (xm, yc - 6.5, 0), md["vent_d"], sh + 0.5, 2 * sh + 0.1))
    # alignment pins (lower) and holes (upper)
    pins = []
    for i, (px, py) in enumerate(((2.5, 2.5), (bx - 2.5, 2.5), (2.5, by - 2.5), (bx - 2.5, by - 2.5))):
        pins.append(s.cyl(f"t_pin{i}", "Z", (px, py, 0), md["pin_d"], sh - 0.1, sh + md["pin_h"]))
        cuts.append(s.cyl(f"t_ph{i}", "Z", (px, py, 0), md["pin_d"] + 2 * md["pin_clr"], sh - 0.1, sh + md["pin_h"] + 0.2))
    s.cut("mould_upper", cuts)
    s.join("mould_lower", pins)
    s.export_step("__OUT__/mould_lower.step", ["mould_lower"])
    s.export_step("__OUT__/mould_upper.step", ["mould_upper"])
    s.export_stl("__OUT__/mould_lower.stl", ["mould_lower"])
    s.export_stl("__OUT__/mould_upper.stl", ["mould_upper"])
    return s, {"block": [bx, by, 2 * sh], "cast_volume_note": "cavity minus core"}
