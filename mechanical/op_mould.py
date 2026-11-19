"""Two-part silicone moulds for the plunger bead seals: ONE order, three variants (params.json -> seal.variants), independent of pump size.

Cavity = plunger-core envelope (wc + 2 core_clr, so the empty grooves are part of the cavity) + for every ring of the variant a trapezoidal BEAD cavity
(op_seal.bead_bodies: draft flanks + flat land) whose land is the free (cast) size w_in + variant.free_oversize.  The cast silicone fills cavity minus
core, i.e. the groove(s) plus the bead(s).  Split plane z = split_h; X = plunger axis.  The core is inserted pushed against the rear cavity wall.

Variant files (all bodies are built in one script at different y offsets):
  mould_lower / mould_upper             = variant S1 (primary; kept under the old names for check.py / fab.py)
  mould_s2_lower / mould_s2_upper       = variant S2
  mould_t_lower  / mould_t_upper        = variant T

Print orientation (see SEAL-AND-DEAD-VOLUME.md): each half standing on its short end (cavity axis X vertical) so that the layer steps run around the
bead instead of across it (steps across the land would be axial leak channels); 25-50 um layers, post-cure, wash, polish the cavity with a wet 1500 grit
swab, release agent (PVA / soap film) before the cast.
"""
from __future__ import annotations

from op_cmds import Script
from op_seal import bead_bodies, ring_range, variant

FILES = {"S1": "mould", "S2": "mould_s2", "T": "mould_t"}


def build_one(s: Script, p: dict, key: str, yo: float) -> dict:
    rs, sl, md = p["reservoir"], p["seal"], p["mould"]
    v = variant(p, key)
    pre = FILES[key]
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd, pl = sl["groove_depth"], rs["plunger_len"]
    m, sh = md["margin"], md["split_h"]
    cc = md["core_clr"]
    over = v["free_oversize"]
    bx = pl + 2 * m
    by = rs["w_in"] + over + 2 * m
    yc, zc = yo + by / 2, sh
    x0 = m                                           # core starts here
    lo, up = f"{pre}_lower", f"{pre}_upper"
    # core (for the fit check only; not exported): grooves, no sockets
    s.stadium(f"{pre}_core", (x0, x0 + pl), yc, zc, wc, hc)
    gr = []
    for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
        gr.append(s.stadium_ring(f"t_{pre}_gr{k}", (x0 + a, x0 + b), yc, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd))
    s.cut(f"{pre}_core", gr)
    s.box(lo, (0, bx), (yo, yo + by), (0, sh))
    s.box(up, (0, bx), (yo, yo + by), (sh, 2 * sh))
    for nm in (lo, up):
        t = [s.stadium(f"t_{nm}_core", (x0, x0 + pl), yc, zc, wc + 2 * cc, hc + 2 * cc)]
        for which in v["rings"]:
            a, b = ring_range(p, which)
            t += bead_bodies(s, f"t_{nm}_b{which}", x0 + a, x0 + b, yc, zc, wc + 2 * cc, hc + 2 * cc,
                             rs["w_in"] + over, rs["h_in"] + over, v["land"])
        s.cut(nm, t)
    # sprues (feed, 22G syringe) and vents in the upper half, one pair per ring
    cuts = []
    for which in v["rings"]:
        a, b = ring_range(p, which)
        xm = x0 + (a + b) / 2
        cuts.append(s.cyl(f"t_{pre}_sp{which}", "Z", (xm, yc + 6.5, 0), md["sprue_d"], sh + 0.5, 2 * sh + 0.1))
        cuts.append(s.cyl(f"t_{pre}_vt{which}", "Z", (xm, yc - 6.5, 0), md["vent_d"], sh + 0.5, 2 * sh + 0.1))
    # alignment pins (lower) and holes (upper)
    pins = []
    for i, (px, py) in enumerate(((2.5, yo + 2.5), (bx - 2.5, yo + 2.5), (2.5, yo + by - 2.5), (bx - 2.5, yo + by - 2.5))):
        pins.append(s.cyl(f"t_{pre}_pin{i}", "Z", (px, py, 0), md["pin_d"], sh - 0.1, sh + md["pin_h"]))
        cuts.append(s.cyl(f"t_{pre}_ph{i}", "Z", (px, py, 0), md["pin_d"] + 2 * md["pin_clr"], sh - 0.1, sh + md["pin_h"] + 0.2))
    s.cut(up, cuts)
    s.join(lo, pins)
    s.export_step(f"__OUT__/{lo}.step", [lo])
    s.export_step(f"__OUT__/{up}.step", [up])
    s.export_stl(f"__OUT__/{lo}.stl", [lo])
    s.export_stl(f"__OUT__/{up}.stl", [up])
    return {"key": key, "block": [bx, by, 2 * sh], "free_oversize": over, "rings": v["rings"]}


def build_mould(p: dict) -> tuple[Script, dict]:
    s = Script()
    info = {}
    yo = 0.0
    for key in FILES:
        r = build_one(s, p, key, yo)
        info[key] = r
        yo += r["block"][1] + 4.0
    return s, info
