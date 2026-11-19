# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Slide-on dock for the Insight Flex cannula head (dome with side septum), shared by both pod variants.

The pod is pushed FLAT along the skin onto the dome.  The dome enters a channel that is open at the +X end wall
(mouth); at the closed end a horizontal 30G needle (press-fit hub, inside a printed guard tube) pierces the septum
from the side.  Two snap arms (compliant PA12 cantilevers, moulded into the bottom shell) spread over the dome
equator and latch behind it in a notch (hook height / depth from the cannula.* letters).

All cannula.* values are TODO-MEASURE placeholders (see cannula-measurement.md).
"""
from __future__ import annotations

import math

from op_cmds import Script

PA12_E_MPA = 1700.0
PA12_STRAIN_LIMIT = 0.03          # repeated snap, conservative (yield strain of PA12 is much higher)


def dock_geometry(p: dict, xr: float, wall: float) -> dict:
    cn, dk = p["cannula"], p["dock"]
    R = cn["A_dome_d"] / 2
    x_h0 = xr + dk["hub_x0"]
    x_h1 = x_h0 + dk["hub_t"]
    x_tip = x_h1 + dk["needle_free"]
    x_face = x_tip - cn["F_needle_depth"]                 # septum face = recess floor
    x_f = x_face - cn["E_septum_recess_depth"]            # tangent point of the dome on the needle axis
    x_d = x_f + R                                         # dome centre (latched position)
    notch_half = math.sqrt(R * R - cn["G_latch_dx"] ** 2) - cn["H_latch_depth"]
    hook_in = notch_half + dk["hook_clr"]                 # hook inner half spacing (latched, relaxed)
    travel = R + dk["dome_clr"] - hook_in                 # arm tip travel while the dome equator passes
    arm_in = R + dk["arm_gap_clr"]                        # relaxed inner half spacing of the arms
    floor_half = arm_in + dk["arm_t"] + 0.1               # floor opening clears plate AND the arms (no fusing in MJF)
    mouth_half = max(cn["J_base_w"] / 2 + 0.3, R + 0.3)
    if "dock_interface_frozen" in p and p.get("mode") == "bench":
        mouth_half = p["dock_interface_frozen"]["mouth_half"]       # pod end-wall mouth is frozen; the insert adapts inside it
    x_arm0 = xr + dk["block_len"] + dk["root_len"]         # start of the free (flexing) length (behind the cap and the bridge)
    x_hook = x_d + cn["G_latch_dx"]
    flex_len = x_hook - x_arm0                            # free length root -> hook centre
    t = dk["arm_t"]
    strain = 1.5 * t * travel / (flex_len ** 2)
    stiff_N = 3 * PA12_E_MPA * (dk["arm_z"][1] - dk["arm_z"][0]) * t ** 3 / 12 * travel / flex_len ** 3
    return {
        "x_h0": x_h0, "x_h1": x_h1, "x_tip": x_tip, "x_face": x_face, "x_f": x_f, "x_d": x_d, "y_c": dk["y_c"],
        "z_n": cn["C_septum_axis_z"], "R": R, "notch_half": notch_half, "hook_in": hook_in, "travel": travel,
        "x_hook": x_hook, "flex_len": flex_len, "arm_strain": strain, "arm_tip_force_N": stiff_N,
        "arm_t": t, "arm_h": dk["arm_z"][1] - dk["arm_z"][0], "arm_x": [x_arm0, x_hook + dk["hook_w"] / 2 + 0.3],
        "shroud_end": x_f + cn["E_septum_recess_depth"] - 0.2,
        "mouth_half": mouth_half, "floor_half": floor_half, "arm_in": arm_in, "x_arm0": x_arm0,
        "strain_ok": strain <= PA12_STRAIN_LIMIT,
    }


def build_dock_joins(s: Script, p: dict, L: dict) -> list[str]:
    """Shell part of the dock: bridge bar behind the end cap + two snap arms with ramped hooks.
    (The cap with septum, needle guard is a separate part: op_cap.py.)"""
    cn, dk, D = p["cannula"], p["dock"], L["dock"]
    xr, yc, zn, wall = L["x_r1"], D["y_c"], D["z_n"], L["wall"]
    za, zb = dk["arm_z"]
    ai = D["arm_in"]
    bx0 = xr + dk["block_len"]
    bx1 = bx0 + dk["root_len"]
    out = [s.box("t_dbridge", (bx0, bx1), (yc - ai - dk["arm_t"], yc + ai + dk["arm_t"]), (wall - 0.1, zn + dk["block_up"]))]
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * ai, yc + sg * (ai + dk["arm_t"])))
        out.append(s.box(f"t_darm{k}", (bx1 - 0.3, D["arm_x"][1]), (y0, y1), (za, zb)))
        w2, rmp = dk["hook_w"] / 2, dk["hook_ramp"]
        ri, ra = D["hook_in"], ai + 0.1
        prof = [(-w2, ra), (-w2, ri + rmp), (-w2 + rmp, ri), (w2 - rmp, ri), (w2, ri + rmp), (w2, ra)]
        pts = [(D["x_hook"] + dx, yc + sg * r) for dx, r in prof]
        out.append(s.polyprism(f"t_dhook{k}", pts, (zn - cn["N_hook_h"] / 2, zn + cn["N_hook_h"] / 2)))
    return out


def build_dock_cuts(s: Script, p: dict, L: dict) -> list[str]:
    cn, dk, D = p["cannula"], p["dock"], L["dock"]
    xr, yc, zn = L["x_r1"], D["y_c"], D["z_n"]
    bx0 = xr + dk["block_len"]
    bx1 = bx0 + dk["root_len"]
    cuts = [s.cyl("t_kshr", "X", (0, yc, zn), cn["O_cyl_od"] + 0.2, bx0 - 0.1, bx1 + 0.1)]      # hole for the guard tube of the end cap
    # floor opening under the channel (dome + patch footprint) from the bridge to the mouth
    cuts.append(s.box("t_kfloor", (bx1, L["length"] + 0.1), (yc - D["floor_half"], yc + D["floor_half"]), (-0.1, dk["arm_z"][0])))
    return cuts


def build_mouth_cut(s: Script, p: dict, L: dict, name: str, top_part: bool = False) -> list[str]:
    """Opening of the +X end wall for the dome. Two tools (a single tall tool that pokes out through the rim step makes
    SMLib's planar regularization fail): the wall below the lap step, then the lap tongue / lid skirt."""
    dk, D = p["dock"], L["dock"]
    y0, y1 = D["y_c"] - D["mouth_half"], D["y_c"] + D["mouth_half"]
    ztop = p["cannula"]["B_dome_h"] + dk["mouth_over"]
    lap = p["shell"]["lap_low"]
    x0 = L["length"] - L["wall"] - 0.3
    if top_part:        # lid: skirt (z 5.01..) only
        return [s.box(name, (x0, L["length"] - 0.05), (y0, y1), (lap - 0.1, ztop))]
    return [s.box(name + "a", (x0, L["length"] + 0.1), (y0, y1), (-0.1, lap - 0.05)),
            s.box(name + "b", (x0, L["length"] - 0.05), (y0, y1), (lap - 0.1, ztop))]


def build_needle(s: Script, p: dict, L: dict) -> None:
    nd, D = p["needle"], L["dock"]
    s.cyl("needle", "X", (0, D["y_c"], D["z_n"]), nd["od"], D["x_h0"], D["x_tip"])
    s.tube("needle_hub", "X", (0, D["y_c"], D["z_n"]), nd["hub_d"], nd["od"], D["x_h0"], D["x_h1"])


def build_adapter(s: Script, p: dict, L: dict, name: str = "cannula_adapter", lug: bool = True) -> None:
    """Dummy cannula head (printed): base plate + dome, septum recess, latch notches, hose barb, magnet lug."""
    cn, dk, ad, D = p["cannula"], p["dock"], p["bench"]["adapter"], L["dock"]
    R, xd, yc, zn = D["R"], D["x_d"], D["y_c"], D["z_n"]
    bw, bl, bt = cn["J_base_w"], cn["K_base_l"], cn["L_base_t"]
    s.box(name, (xd - bl / 2, xd + bl / 2), (yc - bw / 2, yc + bw / 2), (0, bt))
    joins = [s.cyl("t_ad_dome", "Z", (xd, yc, 0), cn["A_dome_d"], 0, cn["B_dome_h"] - 0.0)]
    zl = ad["lug_top"]
    xm = xd + ad["magnet_dx"]
    if lug:
        joins.append(s.box("t_ad_lug", (xd + R - 1.0, xm + ad["lug_half_x"]), (yc - ad["lug_half_y"], yc + ad["lug_half_y"]), (0, zl)))
        joins.append(s.cyl("t_ad_barb", "X", (0, yc, ad["channel_z"]), ad["barb_d"], xm + ad["lug_half_x"] - 0.01, xm + ad["lug_half_x"] + ad["barb_len"]))
    s.join(name, joins)
    notch_in = D["notch_half"]
    cuts = []
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * notch_in, yc + sg * (R + 0.5)))
        cuts.append(s.box(f"t_ad_n{k}", (xd + cn["G_latch_dx"] - cn["I_latch_w"] / 2, xd + cn["G_latch_dx"] + cn["I_latch_w"] / 2),
                          (y0, y1), (dk["arm_z"][0] + 0.2, cn["B_dome_h"] + 0.1)))
    xf = D["x_f"]
    cuts.append(s.cyl("t_ad_rec", "X", (0, yc, zn), cn["D_septum_recess_d"], xf - 0.1, xf + cn["E_septum_recess_depth"]))
    cuts.append(s.cyl("t_ad_bore", "X", (0, yc, zn), ad["septum_bore_d"], xf + cn["E_septum_recess_depth"] - 0.01,
                      xf + cn["E_septum_recess_depth"] + cn["F_needle_depth"] + 0.7))
    if lug:
        xv = xf + cn["E_septum_recess_depth"] + cn["F_needle_depth"] + 0.35
        cuts.append(s.cyl("t_ad_vert", "Z", (xv, yc, 0), ad["channel_d"], ad["channel_z"] - ad["channel_d"] / 2, zn))
        cuts.append(s.cyl("t_ad_chan", "X", (0, yc, ad["channel_z"]), ad["channel_d"], xv - 0.3, xm + ad["lug_half_x"] + ad["barb_len"] + 0.1))
        cuts.append(s.cyl("t_ad_mag", "Z", (xm, yc, 0), ad["magnet_d"] + ad["magnet_clr"], zl - ad["magnet_t"] - 0.05, zl + 0.1))
    s.cut(name, cuts)


# ======================================================================================================
# Modular dock (spec 8a): frozen pod-side interface + swappable dock insert
# ======================================================================================================
SEG = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg", 6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg"}


def pod_interface_geometry(p: dict, L: dict) -> dict:
    F, dk = p["dock_interface_frozen"], p["dock"]
    xr, yc = L["x_r1"], L["dock"]["y_c"]
    return {"x0": xr + F["x0_u"], "x1": L["length"] + 0.1, "yc": yc, "win_half": F["win_half"], "pocket_half": F["pocket_half"],
            "ledge_top": F["ledge_z"][1], "x_det": xr + F["detent"]["x_u"]}


def build_pod_dock_interface(s: Script, p: dict, L: dict) -> tuple[list[str], list[str]]:
    """Pod side of the frozen interface (bottom shell): through window + flange pocket (cuts) and two detent bumps (joins)."""
    F, wall = p["dock_interface_frozen"], L["wall"]
    G = pod_interface_geometry(p, L)
    top = wall + F["insert_top_gap"]
    cuts = [s.box("t_dwin", (G["x0"], G["x1"]), (G["yc"] - G["win_half"], G["yc"] + G["win_half"]), (-0.1, top)),
            s.box("t_dpocket", (G["x0"], G["x1"]), (G["yc"] - G["pocket_half"], G["yc"] + G["pocket_half"]), (G["ledge_top"], top))]
    ym = (G["win_half"] + G["pocket_half"]) / 2
    bz = F["detent"]["z"]
    joins = [s.cyl(f"t_dbump{k}", "Z", (G["x_det"], G["yc"] + sg * ym, 0), F["detent"]["d_bump"], bz[0], bz[1])
             for k, sg in enumerate((-1, 1))]
    return joins, cuts


def build_insert(s: Script, p: dict, L: dict, name: str = "dock_insert", vid: int | None = None) -> None:
    """The swappable dock insert: tile (floor of the dock window) + T-slot flanges + root bridge + two snap arms with hooks
    + guard-tube bore; everything that depends on the cannula (cannula.* values) lives here."""
    cn, dk, D, F = p["cannula"], p["dock"], L["dock"], p["dock_interface_frozen"]
    xr, yc, zn, wall = L["x_r1"], D["y_c"], D["z_n"], L["wall"]
    za, zb = dk["arm_z"]
    ai = D["arm_in"]
    G = pod_interface_geometry(p, L)
    c, top = F["clr"], wall - F["insert_top_gap"]
    xa, xb = G["x0"] + c, L["length"] - 0.05
    bx1 = xr + dk["block_len"] + dk["root_len"]
    s.box(name, (xa, xb), (yc - G["win_half"] + c, yc + G["win_half"] - c), (0, top))
    joins = [s.box(f"t_ifl{k}", (xa, xb), tuple(sorted((yc + sg * (G["win_half"] - 0.3), yc + sg * (G["pocket_half"] - c)))),
                   (F["ledge_z"][1] + 0.05, top)) for k, sg in enumerate((-1, 1))]
    joins.append(s.box("t_ibridge", (xa, bx1), (yc - ai - dk["arm_t"], yc + ai + dk["arm_t"]), (top - 0.1, zn + dk["block_up"])))
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * ai, yc + sg * (ai + dk["arm_t"])))
        joins.append(s.box(f"t_iarm{k}", (bx1 - 0.3, D["arm_x"][1]), (y0, y1), (za, zb)))
        w2, rmp = dk["hook_w"] / 2, dk["hook_ramp"]
        ri, ra = D["hook_in"], ai + 0.1
        prof = [(-w2, ra), (-w2, ri + rmp), (-w2 + rmp, ri), (w2 - rmp, ri), (w2, ri + rmp), (w2, ra)]
        pts = [(D["x_hook"] + dx, yc + sg * r) for dx, r in prof]
        joins.append(s.polyprism(f"t_ihook{k}", pts, (zn - cn["N_hook_h"] / 2, zn + cn["N_hook_h"] / 2)))
    if vid is not None:             # raised ID digits (7 segments, reading along +X) on the outer face of the -Y snap arm
        digits = [int(ch) for ch in str(vid)]
        wd, ht, w, rz = 1.0, 2.0, 0.35, 0.3
        y_face = yc - ai - dk["arm_t"]
        zc_ = (za + zb) / 2
        x0d = D["x_arm0"] + 2.5
        for di, dg in enumerate(digits):
            cx = x0d + di * 1.6
            for sg_ in SEG[dg]:
                if sg_ in "adg":
                    zz = {"a": ht / 2 - w / 2, "g": 0.0, "d": -(ht / 2 - w / 2)}[sg_]
                    bx, bz = (cx - wd / 2, cx + wd / 2), (zc_ + zz - w / 2, zc_ + zz + w / 2)
                else:
                    xx = -(wd / 2 - w / 2) if sg_ in "fe" else (wd / 2 - w / 2)
                    zz = ht / 4 if sg_ in "fb" else -ht / 4
                    bx, bz = (cx + xx - w / 2, cx + xx + w / 2), (zc_ + zz - ht / 4 - w / 2 + 0.0, zc_ + zz + ht / 4 + w / 2 - 0.0)
                joins.append(s.box(f"t_id{di}{sg_}", bx, (y_face - rz, y_face + 0.05), bz))
    s.join(name, joins)
    cuts = [s.cyl("t_ishr", "X", (0, yc, zn), cn["O_cyl_od"] + 0.2, xa - 0.1, bx1 + 0.1),       # guard tube of the end cap
            s.box("t_ifloor", (bx1, L["length"] + 0.1), (yc - D["floor_half"], yc + D["floor_half"]), (-0.1, za))]
    ym = (G["win_half"] + G["pocket_half"]) / 2
    for k, sg in enumerate((-1, 1)):
        cuts.append(s.cyl(f"t_ihole{k}", "Z", (G["x_det"], yc + sg * ym, 0), F["detent"]["hole_d"], F["ledge_z"][1] + 0.01, top + 0.1))
    s.cut(name, cuts)
