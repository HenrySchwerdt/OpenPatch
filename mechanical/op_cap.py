"""Minimal fluid module (spec 3c, pressure fill, NO check valve): reservoir port -> septum chamber -> outlet needle.

Clamped two-part sandwich (microfluidic-manifold style), split on the reservoir-port plane z = z_port:
  end_cap       lower half (printed): locating spigot half-pin, O-ring half groove, gasket recess, septum pocket (axis Z, open from the top), fill-needle hole
                down through the base and the pod floor, via + needle bore on the needle axis, shroud tube + hub bore
  cap_gasket    0.5 mm silicone sheet in a 0.4 mm recess (20 % squeeze on hard lands): the port path is one slot in the sheet (open while the module is open)
  end_cap_lid   upper half: flat underside on the lands, septum chamber recess + short spur groove, O-ring half groove, spigot half pin, 2 x M1.2 clamp screws
Soft parts are DROPPED into open pockets: O-ring (face seal to the reservoir port), septum disc (compressed axially 15 % between the pocket floor and the lid face, set
by the lands), gasket.  The needle is UV-glued into the hub seat with a printed jig.  The fill septum is on the UNDERSIDE: the fill needle enters through a hole in the pod
floor (accessible when undocked).
Path: spigot half-grooves d prime_d -> gasket port slot (y = y_c) -> via d via_d down to the needle axis -> needle bore d prime_d -> hub / needle;
the septum chamber (lid recess over the disc) hangs on the junction through a short lid groove (spur).  Parametric: septum d / len (a bought septum or port), needle mount.
"""
from __future__ import annotations

from op_cmds import Script


def cap_geometry(p: dict, L: dict) -> dict:
    dk, cp, D = p["dock"], p["dock"]["cap"], L["dock"]
    xr = L["x_r1"]
    sw = cp["sandwich"]
    zs = L["z_axis"]
    yc = D["y_c"]
    return {"x_block": [xr, xr + dk["block_len"]], "y_block": [yc + sw["block_y_rel"][0], yc + sw["block_y_rel"][1]],
            "z_block": [L["wall"], D["z_n"] + cp.get("block_up", dk["block_up"])], "z_split": zs,
            "x_sept": xr + cp["septum_x"], "y_sept": yc - cp["septum_dy"], "z_port": zs, "sandwich": sw}


def oring_squeeze(p: dict) -> dict:
    og = p["dock"]["cap"]["oring"]
    stretch = og["groove_inner_d"] / og["id"]
    cs_eff = og["cs"] * (1.0 / stretch) ** 0.5            # constant-volume ring: cross-section shrinks with stretch
    return {"stretch": stretch - 1.0, "cs_eff": cs_eff, "squeeze": (cs_eff - og["groove_depth"]) / cs_eff}


def _half(s: Script, name: str, cyl_args: tuple, xlim: tuple, ylim: tuple, zlim: tuple) -> str:
    """Cylinder ∩ box (lower or upper half of a pin)."""
    s.cyl(name, *cyl_args)
    s.box(name + "_hb", xlim, ylim, zlim)
    s.add("solid.combine", target=name, tools=[name + "_hb"], operation="intersect", name=f"half {name}")
    return name


def build_cap(s: Script, p: dict, L: dict) -> dict:
    cn, dk, cp, D = p["cannula"], p["dock"], p["dock"]["cap"], L["dock"]
    sw = cp["sandwich"]
    G = cap_geometry(p, L)
    xr, yc, zn, zp = L["x_r1"], D["y_c"], D["z_n"], G["z_port"]
    zs = G["z_split"]
    x0, x1 = G["x_block"]
    y0, y1 = G["y_block"]
    z0, zt = G["z_block"]
    ws, gt, rec = sw["slot_w"], sw["gasket"]["t"], sw["gasket"]["recess"]
    gx0, gx1, gm = sw["gasket"]["x"][0], sw["gasket"]["x"][1], sw["gasket"]["y_margin"]
    og = cp["oring"]
    dp = cp["prime_d"]
    xd, yd = G["x_sept"], G["y_sept"]
    sdia, slen = p["septum"]["d"], p["septum"]["len"]
    scomp, sfl = sw["septum"]["compress"], sw["septum"]["float"]
    zf = zs - slen * (1.0 - scomp)                        # septum pocket floor: the disc is compressed to slen*(1-c) between it and the lid face
    gy1 = yc + sw["gasket"]["y_max_rel"]
    nsh = 2.8
    # ------------------------------------------------------------------ base
    s.box("end_cap", (x0, x1), (y0, y1), (z0, zs))
    j = [_half(s, "t_spg_l", ("X", (0, yc, zp), cp["spigot_d"], xr - cp["spigot_len"], xr + 0.01), (xr - cp["spigot_len"] - 0.1, xr + 0.1), (yc - 0.8, yc + 0.8), (zp - 2, zs)),
         s.cyl("t_cap_shroud", "X", (0, yc, zn), cn["O_cyl_od"], x1 - 0.05, D["shroud_end"])]
    s.join("end_cap", j)
    s.tube("t_og_b", "X", (0, yc, zp), og["groove_inner_d"] + 2 * og["groove_w"], og["groove_inner_d"], xr - 0.1, xr + og["groove_depth"])
    cuts = [
        "t_og_b",
        s.box("t_g_rec", (xr + gx0, xr + gx1), (y0 + gm, gy1), (zs - rec, zs + 0.1)),                                  # gasket recess (0.4 deep)
        s.cyl("t_cap_p", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, xr + gx0 + 0.1),                          # port channel (half groove in the spigot)
        s.cyl("t_cap_via", "Z", (xd, yc, 0), sw["via_d"], zn - 0.3, zs - rec + 0.1),                                  # via: slot layer -> needle axis
        s.cyl("t_cap_nb", "X", (0, yc, zn), cp.get("bore_d", dp), xd + (0.1 if "bore_d" in cp else -0.3), D["x_h0"] + (0.02 if "bore_d" in cp else 0.1)),                                           # needle bore: junction -> hub
        s.cyl("t_cap_hb", "X", (0, yc, zn), dk["hub_d"] - cp["hub_press"], D["x_h0"], D["shroud_end"] + 0.1),         # hub seat (needle UV-glued, jig)
        s.cyl("t_cap_sp", "Z", (xd, yd, 0), sdia + sfl, zf, zs + 0.05),                                                # septum pocket (axis Z, open top)
        s.cyl("t_cap_fh", "Z", (xd, yd, 0), cp["fill_hole_d"], z0 - 0.1, zf + 0.1),                                    # fill-needle hole down to the pod floor hole
    ]
    for k, (sx, sy) in enumerate(sw["screws"]["pos"]):
        cuts.append(s.cyl(f"t_cap_pil{k}", "Z", (xr + sx, yc + sy, 0), sw["screws"]["pilot"], zs - nsh, zs + 0.1))
    s.cut("end_cap", cuts)
    # ------------------------------------------------------------------ lid
    s.box("end_cap_lid", (x0, x1), (y0, y1), (zs, zt))
    s.join("end_cap_lid", [_half(s, "t_spg_u", ("X", (0, yc, zp), cp["spigot_d"], xr - cp["spigot_len"], xr + 0.01), (xr - cp["spigot_len"] - 0.1, xr + 0.1), (yc - 0.8, yc + 0.8), (zs, zp + 2))])
    s.tube("t_og_u", "X", (0, yc, zp), og["groove_inner_d"] + 2 * og["groove_w"], og["groove_inner_d"], xr - 0.1, xr + og["groove_depth"])
    lcuts = [
        "t_og_u",
        s.cyl("t_cap_pu", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, xr + gx0 + 0.1),
        s.cyl("t_cap_ch", "Z", (xd, yd, 0), sw["chamber_d"], zs - 0.05, zs + sw["chamber_h"]),                         # septum chamber over the disc
        s.box("t_cap_spur", (xd - sw["spur_w"] / 2, xd + sw["spur_w"] / 2), (yd, yc + 0.3), (zs - 0.05, zs + sw["spur_depth"])),   # spur groove chamber -> junction
    ]
    sc = sw["screws"]
    for k, (sx, sy) in enumerate(sc["pos"]):
        lcuts.append(s.cyl(f"t_cap_cl{k}", "Z", (xr + sx, yc + sy, 0), sc["clear"], zs - 0.1, zt + 0.1))
        if sc["head_depth"] > 0:           # v0.1.0: no counterbore (the head sits on the lid top, 0.9 mm high, under the pod lid)
            lcuts.append(s.cyl(f"t_cap_hd{k}", "Z", (xr + sx, yc + sy, 0), sc["head_d"], zt - sc["head_depth"], zt + 0.1))
    s.cut("end_cap_lid", lcuts)
    # ------------------------------------------------------------------ gasket (silicone sheet, the port path = one slot)
    s.box("cap_gasket", (xr + gx0, xr + gx1), (y0 + gm, gy1), (zs - rec, zs - rec + gt))
    gc = [
        s.box("t_gs_p", (xr + gx0 - 0.1, xd + ws / 2), (yc - ws / 2, yc + ws / 2), (zs - 1, zs + 1)),                  # port slot
        s.cyl("t_gs_s", "Z", (xd, yd, 0), sdia + sfl, zs - 1, zs + 1),                                                 # septum pocket opening
    ]
    for k, (sx, sy) in enumerate(sw["screws"]["pos"]):         # clamp screw passes through the sheet
        gc.append(s.cyl(f"t_gs_sc{k}", "Z", (xr + sx, yc + sy, 0), sw["screws"]["clear"], zs - 1, zs + 1))
    s.cut("cap_gasket", gc)
    return G


def build_oring(s: Script, p: dict, L: dict) -> None:
    """The face O-ring in assembly state (axial squeeze overlaps the reservoir end face by design: interference exclude pair)."""
    og = p["dock"]["cap"]["oring"]
    G = cap_geometry(p, L)
    q = oring_squeeze(p)
    xr = G["x_block"][0]
    D = L["dock"]
    s.tube("cap_oring", "X", (0, D["y_c"], G["z_port"]), og["groove_inner_d"] + 2 * q["cs_eff"], og["groove_inner_d"], xr - (q["cs_eff"] - og["groove_depth"]), xr + og["groove_depth"])


def build_septum(s: Script, p: dict, L: dict) -> None:
    """Septum disc in assembly state: compressed height slen*(1-c), between the pocket floor and the lid face (axis Z)."""
    G = cap_geometry(p, L)
    sw = G["sandwich"]
    zs = G["z_split"]
    h = p["septum"]["len"] * (1.0 - sw["septum"]["compress"])
    s.cyl("septum", "Z", (G["x_sept"], G["y_sept"], 0), p["septum"]["d"], zs - h, zs)


def cap_interfaces(p: dict, L: dict) -> list[dict]:
    """Every sealing interface of the wetted module: gap (mm, > 0 clearance, 0 touching, < 0 interference / compression) and the seal element that closes it."""
    fz, cp, sp, dk = p["reservoir_frozen"], p["dock"]["cap"], p["septum"], p["dock"]
    sw = cp["sandwich"]
    og = cp.get("oring")
    q = oring_squeeze(p) if og else None
    seal_o = ("face O-ring %.1f x %.1f in the clamped halves, axial squeeze %.0f %%" % (og["id"], og["cs"], 100 * q["squeeze"])) if og else None
    gk = sw["gasket"]
    gsq = (gk["t"] - gk["recess"]) / gk["t"]
    return [
        {"name": "cap spigot d%.2f in reservoir port d%.2f H7 (locating only)" % (cp["spigot_d"], fz["port_d"]), "gap": fz["port_d"] - cp["spigot_d"], "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "module rear face on the reservoir end face", "gap": 0.0, "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "base / lid split plane (port slot)", "gap": 0.0, "seal": "silicone sheet gasket %.1f mm, %.0f %% squeeze on hard lands" % (gk["t"], 100 * gsq), "squeeze": gsq},
        {"name": "septum disc d%.1f x %.1f (axial)" % (sp["d"], sp["len"]), "gap": -sp["len"] * sw["septum"]["compress"], "seal": "%.0f %% axial compression between pocket floor and lid face (lands)" % (100 * sw["septum"]["compress"]), "squeeze": sw["septum"]["compress"]},
        {"name": "needle in hub seat", "gap": -cp.get("hub_press", 0.0) / 2 if cp.get("hub_press") else dk["hub_clr"],
         "seal": "UV-resin bond in a printed jig + press fit %.2f per side" % (cp["hub_press"] / 2) if cp.get("hub_press") else None, "squeeze": None},
    ]
