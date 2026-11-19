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
    x_arm0 = xr + dk["root_len"]                          # start of the free (flexing) length
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
    """Solid dock structure of the bottom shell: end block, guard tube, two snap arms with hooks."""
    cn, dk, D = p["cannula"], p["dock"], L["dock"]
    xr, yc, zn, wall = L["x_r1"], D["y_c"], D["z_n"], L["wall"]
    out = [s.box("t_dblock", (xr, xr + dk["block_len"]), (yc - dk["block_half_y"], yc + dk["block_half_y"]),
                 (wall - 0.1, zn + dk["block_up"]))]
    out.append(s.cyl("t_dshroud", "X", (0, yc, zn), cn["O_cyl_od"], xr + dk["block_len"] - 0.05, D["shroud_end"]))
    za, zb = dk["arm_z"]
    ai = D["arm_in"]
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * ai, yc + sg * (ai + dk["arm_t"])))
        out.append(s.box(f"t_darm{k}", (xr + dk["root_len"] - 0.3, D["arm_x"][1]), (y0, y1), (za, zb)))
        out.append(s.box(f"t_droot{k}", (xr, xr + dk["root_len"]),
                         tuple(sorted((yc + sg * (dk["block_half_y"] - 0.1), yc + sg * (ai + dk["arm_t"])))), (wall - 0.1, zb)))
        w2, rmp = dk["hook_w"] / 2, dk["hook_ramp"]
        ri, ra = D["hook_in"], ai + 0.1
        prof = [(-w2, ra), (-w2, ri + rmp), (-w2 + rmp, ri), (w2 - rmp, ri), (w2, ri + rmp), (w2, ra)]
        pts = [(D["x_hook"] + dx, yc + sg * r) for dx, r in prof]
        out.append(s.polyprism(f"t_dhook{k}", pts, (zn - cn["N_hook_h"] / 2, zn + cn["N_hook_h"] / 2)))
    return out


def build_dock_cuts(s: Script, p: dict, L: dict) -> list[str]:
    cn, dk, D, nd = p["cannula"], p["dock"], L["dock"], p["needle"]
    xr, yc, zn = L["x_r1"], D["y_c"], D["z_n"]
    cuts = [s.cyl("t_kbore", "X", (0, yc, zn), dk["hub_d"] + dk["hub_clr"], D["x_h0"], D["shroud_end"] + 0.1),
            s.cyl("t_kchan", "X", (0, yc, zn), nd["channel_d"], xr - 0.5, D["x_h0"] + 0.1)]
    # floor opening under the channel (the dome + patch footprint) from the block face to the mouth
    cuts.append(s.box("t_kfloor", (xr + dk["block_len"], L["length"] + 0.1), (yc - D["floor_half"], yc + D["floor_half"]),
                      (-0.1, dk["arm_z"][0])))
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
