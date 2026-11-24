# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Dock of the cup pod: pocket open to the underside and the +X end face, 3.5 mm slide + two stainless L-springs + dock magnet/hall.  All cannula values TODO-MEASURE (photo estimate).

The head either slides in from the open +X end (like the Insight pump) or the pod is lowered over it with the dome `travel` mm further from the needle than its
latched position; the last `travel` mm toward the tank (= needle insertion) end when the two spring teeth drop into the dome side notches.  Needle axis: +Y at (x_n, z_n), leaving the tank front wall sideways.
A spring-loaded guard sleeve covers the needle tip while no head is docked.
"""
from __future__ import annotations

import math

from op_cmds import Script


def layout(p: dict, x_face_tank: float, y_c: float) -> dict:
    """Needle axis along +X leaving the tank front wall straight; pocket extends +X (right end of lane 1), centred on y_c."""
    d = p["cup"]["dock"]
    h, cl, g = d["head"], d["clip"], d["guard"]
    R = h["A_dome_d"] / 2
    x_bf = x_face_tank + 0.05
    x_f = x_bf + d["clr"]                       # dome -X tangent (septum side), latched
    x_d = x_f + R
    x_face = x_f + h["recess_depth"]            # septum face (recess floor)
    x_tip = x_face + h["needle_depth"]
    pocket_len = d["clr"] + h["A_dome_d"] + d["travel"] + d["clr"]
    x_far = x_bf + pocket_len
    return {"R": R, "x_bf": x_bf, "y_c": y_c, "z_n": h["septum_z"], "x_f": x_f, "x_d": x_d, "x_face": x_face, "x_tip": x_tip, "x_far": x_far, "pocket_len": pocket_len,
            "half": d["pocket_half"], "x_hub": [x_face_tank - 1.2, x_face_tank - 0.5], "guard_dock": [x_face_tank + 0.05, x_face], "guard_free": [x_face + 0.1, x_tip + g["tip_cover"]],
            "guard_free_end": x_tip + g["tip_cover"], "x_tooth": x_d, "arm_len": (x_far - 0.15) - x_d,
            "plate_x": [x_d - h["base_l"] / 2 - d["clr"], x_d + h["base_l"] / 2 + d["clr"] + d["travel"]], "x_d0": x_d + d["travel"], "slide": d["travel"], "clip": cl}


def clip_stress(p: dict, K: dict) -> dict:
    c, h, d = K["clip"], p["cup"]["dock"]["head"], p["cup"]["dock"]
    L, t, b, E = K["arm_len"], c["t"], c["b"], c["E_MPa"]
    need = h["notch_depth"] + 0.1
    I = b * t ** 3 / 12.0
    sig = lambda dl: 3 * E * t * dl / (2 * L * L)
    return {"arm_len": L, "need_travel": need, "sigma_need": sig(need), "sigma_1p8": sig(1.8), "travel_allow": 2 * c["allow_MPa"] * L * L / (3 * E * t),
            "F_need_N": 3 * E * I * need / L ** 3, "F_1p8_N": 3 * E * I * 1.8 / L ** 3, "short_arm_3p5_travel": 2 * c["allow_MPa"] * 3.5 ** 2 / (3 * E * t),
            "arm_for_1p8": math.sqrt(3 * E * t * 1.8 / (2 * c["allow_MPa"])), "I": I}


def hall_window(p: dict) -> dict:
    d, h = p["cup"]["dock"], p["cup"]["dock"]["head"]
    V = math.pi * (h["magnet_d"] / 2) ** 2 * h["magnet_t"]
    m = d["hall"]["Br_T"] * V * 1e-9 / (4e-7 * math.pi)
    z = d["hall"]["gap_z"] * 1e-3

    def Bz(r_mm: float) -> float:
        dd = math.hypot(z, r_mm * 1e-3)
        return 1e-7 * m * (3 * z * z / dd ** 2 - 1) / dd ** 3 * 1e3
    r = 0.0
    while r < 6.0 and Bz(r) >= d["hall"]["bop_mT"]:
        r += 0.02
    return {"B0_mT": round(Bz(0.0), 1), "bop_mT": d["hall"]["bop_mT"], "assert_radius_mm": round(r, 2), "slide_mm": d["travel"]}


def build_head(s: Script, p: dict, K: dict, name: str = "cannula_adapter", mag: str = "dock_magnet") -> None:
    """Dummy cannula head (test fixture, latched position): base plate + dome + septum recess facing the tank + 2 side notches + magnet."""
    h = p["cup"]["dock"]["head"]
    xd, yc, R, zn = K["x_d"], K["y_c"], K["R"], K["z_n"]
    s.box(name, (xd - h["base_l"] / 2, xd + h["base_l"] / 2), (yc - h["base_w"] / 2, yc + h["base_w"] / 2), (0, h["base_t"]))
    s.join(name, [s.cyl("t_ad_dome", "Z", (xd, yc, 0), h["A_dome_d"], h["base_t"] - 0.05, h["B_dome_h"])])
    cuts = [s.cyl("t_ad_rec", "X", (0, yc, zn), h["recess_d"], K["x_f"] - 0.1, K["x_face"]),
            s.cyl("t_ad_bore", "X", (0, yc, zn), 0.5, K["x_face"] - 0.01, K["x_face"] + h["needle_depth"] + 0.5),
            s.cyl("t_ad_mag", "Z", (xd, yc, 0), h["magnet_d"] + 0.1, h["B_dome_h"] - h["magnet_t"] - 0.05, h["B_dome_h"] + 0.1)]
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * (R - h["notch_depth"] - 0.1), yc + sg * (R + 0.3)))
        cuts.append(s.box(f"t_ad_n{k}", (xd - h["notch_w"] / 2, xd + h["notch_w"] / 2), (y0, y1), tuple(h["notch_z"])))
    s.cut(name, cuts)
    s.cyl(mag, "Z", (xd, yc, 0), h["magnet_d"], h["B_dome_h"] - h["magnet_t"], h["B_dome_h"])


def open_end_tools(s: Script, p: dict, K: dict, x_end: float, z_roof0: float, prefix: str = "t_oe") -> tuple[list[str], list[str]]:
    """Open-end pocket (owner 2026-11-24): anchor blocks on both side walls at the open +X end (arm root + tab slot), 45 deg lead-in on the end-face
    edges of the opening and chamfers on the two bottom edges of the pocket.  Returns (join tools, cut tools); join them after the pocket cut."""
    d, c, h = p["cup"]["dock"], K["clip"], p["cup"]["dock"]["head"]
    yc, half, R = K["y_c"], K["half"], K["R"]
    y_arm_out = R + c["arm_inner_clr"] + c["t"]                    # arm outer face = anchor block inner face
    x_root = K["x_far"] + c["slot_x0_rel"]                         # arm root (where the U-clip bridge used to be)
    joins, cuts = [], []
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * y_arm_out, yc + sg * (half + 0.01)))
        joins.append(s.box(f"{prefix}_blk{k}", (x_root, x_end), (y0, y1), (d["anchor_z0"], z_roof0 + 0.01)))
        # tab slot: 0.2 wide in x, from the arm face through the block into the side wall (0.1 skin left), open to the underside (tab pushed up from below)
        ys0, ys1 = sorted((yc + sg * (y_arm_out - 0.15), yc + sg * (half + d["pocket_wall"] - 0.1)))
        cuts.append(s.box(f"{prefix}_slot{k}", (x_root, x_root + c["slot_w"]), (ys0, ys1), (-0.1, c["z0"] + c["b"] + 0.1)))
        # lead-in on the vertical end-face edge: from the block face (x_end - lead_in) out to half + lead_in_to (x_end)
        li, lt = d["lead_in"], d["lead_in_to"]
        ya = yc + sg * (y_arm_out - 0.01)
        pts = [(x_end - li, ya), (x_end + 0.1, ya), (x_end + 0.1, yc + sg * (y_arm_out + lt * (li + 0.1) / li))]
        cuts.append(s.polyprism(f"{prefix}_li{k}", pts if sg > 0 else pts[::-1], (-0.1, z_roof0)))
        # bottom edge chamfer along the pocket (head lowered from below or slid in from the end finds the opening)
        ch = d["bottom_chamfer"]
        tri = [(yc + sg * (half - 0.01), -0.1), (yc + sg * (half + ch + 0.1), -0.1), (yc + sg * (half - 0.01), ch + 0.01)]
        cuts.append(s.prism_yz(f"{prefix}_bc{k}", tri if sg > 0 else tri[::-1], K["x_bf"], x_end + 0.1))
    return joins, cuts


def build_clip(s: Script, p: dict, K: dict) -> None:
    """Two L-springs (301 FH 0.1): arm along each side wall with the latch tooth at the dome notch, anchor tab bent 90 deg outward into the slot of the anchor block
    at the open end (owner 2026-11-24, the U-clip bridge would block the open end).  One body `dock_clip` for both springs."""
    c, h = K["clip"], p["cup"]["dock"]["head"]
    yc, R, xt = K["y_c"], K["R"], K["x_tooth"]
    t, z0, b = c["t"], c["z0"], c["b"]
    yin = R + c["arm_inner_clr"]
    x_tab = K["x_far"] + c["slot_x0_rel"] + (c["slot_w"] - t) / 2      # tab centred in its slot
    parts = []
    for k, sg in enumerate((-1, 1)):
        y0, y1 = sorted((yc + sg * yin, yc + sg * (yin + t)))
        nm = "dock_clip" if k == 0 else f"t_ca{k}"
        s.box(nm, (xt - c["tooth_w"] / 2, x_tab + t), (y0, y1), (z0, z0 + b))
        if k:
            parts.append(nm)
        ya0, ya1 = sorted((yc + sg * yin, yc + sg * (yin + c["tab_len"])))
        parts.append(s.box(f"t_ctab{k}", (x_tab, x_tab + t), (ya0, ya1), (z0, z0 + b)))
        yt0, yt1 = sorted((yc + sg * (R - h["notch_depth"]), yc + sg * (yin + 0.01)))
        parts.append(s.box(f"t_ct{k}", (xt - c["tooth_w"] / 2, xt + c["tooth_w"] / 2), (yt0, yt1), (h["notch_z"][0] + 0.2, h["notch_z"][1] - 0.2)))
    s.join("dock_clip", parts)


def build_needle(s: Script, p: dict, K: dict) -> None:
    nd, g, hb = p["needle"], p["cup"]["dock"]["guard"], p["cup"]["dock"]["hub"]
    yc, zn = K["y_c"], K["z_n"]
    s.cyl("needle", "X", (0, yc, zn), nd["od"], K["x_hub"][0], K["x_tip"])
    s.tube("needle_hub", "X", (0, yc, zn), hb["d"], hb["id"], *K["x_hub"])                          # brass tube 1.5 x 0.2 (ID 1.1); the 30G needle is bonded in with CA
    s.tube("needle_guard", "X", (0, yc, zn), g["od"], g["id"], *K["guard_dock"])


def dxf_u_clip(p: dict, K: dict, path) -> dict:
    """Flat pattern of the dock L-springs as ASCII DXF R12: layer CUT = outline, BEND = bend lines.  Each strip: anchor tab - bend - arm - tooth flap
    (bent in 45 deg, pointing toward the tank = barb).  Four strips = two pods (owner 2026-11-24: open-end pocket, no U bridge)."""
    c = K["clip"]
    ba = math.pi / 2 * (0.15 + 0.4 * c["t"])
    arm = K["arm_len"] + c["tooth_w"] / 2 + (c["slot_w"] - c["t"]) / 2 + 0.05
    tab = c["tab_len"] - c["t"]
    total = tab + ba + arm
    b, tw, tl = c["b"], c["tooth_w"], c["tooth_len"]
    ents: list[str] = []

    def ln(x0, y0, x1, y1, layer):
        ents.append(f"0\nLINE\n8\n{layer}\n10\n{x0:.4f}\n20\n{y0:.4f}\n30\n0\n11\n{x1:.4f}\n21\n{y1:.4f}\n31\n0")
    for i in range(4):
        oy = i * (b + 3.0)
        o = [(0, oy), (total, oy), (total, oy + (b - tw) / 2), (total + tl, oy + (b - tw) / 2), (total + tl, oy + (b + tw) / 2), (total, oy + (b + tw) / 2), (total, oy + b), (0, oy + b)]
        for a_, bb in zip(o, o[1:] + o[:1]):
            ln(a_[0], a_[1], bb[0], bb[1], "CUT")
        for xb in (tab + ba / 2, total):
            ln(xb, oy - 0.3, xb, oy + b + 0.3, "BEND")
    path.write_text("0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n" + "\n".join(ents) + "\n0\nENDSEC\n0\nEOF\n", encoding="ascii")
    return {"flat_length_mm": round(total, 2), "strip_width_mm": b, "thickness_mm": c["t"], "tooth_tab_mm": [tl, tw], "anchor_tab_mm": c["tab_len"], "strips_in_file": 4,
            "shape": "L-spring: tab 90 deg outward into the anchor slot, tooth flap bent in 45 deg toward the tank (barb)"}
