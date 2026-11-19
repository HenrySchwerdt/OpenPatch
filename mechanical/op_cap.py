"""End cap (separate cheap part, SLA for water, later PP) pressed onto the single press port of the frozen CNC reservoir.

The cap carries everything that may still change: fill septum (side, through a hole in the -Y shell wall), duckbill check valve pocket,
needle-hub guard tube, and all internal d0.7 channels.  The reservoir itself has only the d2.0 H7 port.

Channels (all d0.7): port -> +X at the port height to a jog at x_r1 + jog_x -> down to the needle-axis height -> junction;
junction -> +Y/-Y side branch to the septum chamber (fill/draw path, upstream of the valve);
junction -> duckbill valve (flow +X) -> needle hub bore.
"""
from __future__ import annotations

from op_cmds import Script


def cap_geometry(p: dict, L: dict) -> dict:
    dk, cp, D = p["dock"], p["dock"]["cap"], L["dock"]
    xr = L["x_r1"]
    return {"x_block": [xr, xr + dk["block_len"]], "y_block": [cp["block_y0"], D["y_c"] + cp["block_up_y"]],
            "z_block": [L["wall"], D["z_n"] + cp.get("block_up", dk["block_up"])], "x_jog": xr + cp["jog_x"], "x_sept": xr + cp["septum_x"],
            "valve_x": [xr + dk["valve_x0"], xr + dk["valve_x0"] + p["coax"]["valve_len"]], "z_port": L["z_axis"]}


def build_cap(s: Script, p: dict, L: dict) -> dict:
    nd, cn, dk, cp, D, cx = p["needle"], p["cannula"], p["dock"], p["dock"]["cap"], L["dock"], p["coax"]
    G = cap_geometry(p, L)
    xr, yc, zn, zp = L["x_r1"], D["y_c"], D["z_n"], G["z_port"]
    s.box("end_cap", tuple(G["x_block"]), tuple(G["y_block"]), tuple(G["z_block"]))
    j = [s.cyl("t_cap_spigot", "X", (0, yc, zp), cp["spigot_d"], xr - cp["spigot_len"], xr + 0.01),
         s.cyl("t_cap_shroud", "X", (0, yc, zn), cn["O_cyl_od"], xr + dk["block_len"] - 0.05, D["shroud_end"])]
    s.join("end_cap", j)
    d = nd["channel_d"]
    dp = cp.get("prime_d", d)                       # main path (port -> jog -> valve -> hub): short, smallest bore (prime volume)
    ya = yc - cp["lane_off"]                         # side branch lane (beside the valve pocket)
    df = cp["fill_d"]                                # fill branch bore (septum -> junction)
    sd = cp["septum_depth"]
    y0 = G["y_block"][0]
    cuts = [
        s.cyl("t_cap_p", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, G["x_jog"] + 0.2),       # port channel
        s.cyl("t_cap_d", "Z", (G["x_jog"], yc, 0), dp, zn - 0.2, zp + 0.2),                             # jog to the needle axis
        s.cyl("t_cap_e", "X", (0, yc, zn), dp, G["x_jog"] - 0.2, G["valve_x"][0] + 0.1),                # junction -> valve
        s.cyl("t_cap_c", "Y", (G["x_jog"], 0, zn), df, ya - 0.2, yc + 0.2),                             # junction -> side lane
        s.cyl("t_cap_b", "X", (0, ya, zn), df, G["x_jog"] - 0.2, G["x_sept"] + 0.2),                    # side lane -> septum x
        s.cyl("t_cap_a", "Y", (G["x_sept"], 0, zn), df, y0 + sd - 0.1, ya + 0.2),                       # septum cavity -> side lane
        s.cyl("t_cap_sb", "Y", (G["x_sept"], 0, zn), p["septum"]["d"] * (1.0 - cp["septum_compress"]), y0 - 0.1, y0 + sd),   # septum cavity: bore smaller than the disc
        s.cyl("t_cap_f", "X", (0, yc, zn), dp, G["valve_x"][1] - 0.1, D["x_h0"] + 0.1),                  # valve -> hub bore
        s.cyl("t_cap_hb", "X", (0, yc, zn), dk["hub_d"] - cp["hub_press"], D["x_h0"], D["shroud_end"] + 0.1),      # hub press fit
    ]
    s.cut("end_cap", cuts)
    og = cp["oring"]       # face O-ring groove around the spigot (seal against the reservoir end face)
    s.tube("t_cap_og", "X", (0, yc, zp), og["groove_inner_d"] + 2 * og["groove_w"], og["groove_inner_d"], xr - 0.1, xr + og["groove_depth"])
    s.cut("end_cap", ["t_cap_og"])
    s.cut("end_cap", [s.cyl("t_cap_vb", "X", (0, yc, zn), cx["valve_d"] - (p["bench"]["valve"]["bore_interference"] if "bench" in p else -0.05), G["valve_x"][0], G["valve_x"][1]),
                      s.box("t_cap_vs", tuple(G["valve_x"]), (yc - cx["valve_d"] / 2 - 0.02, yc + cx["valve_d"] / 2 + 0.02), (zn, G["z_block"][1] + 0.1))])
    return G


def build_valve_plug(s: Script, p: dict, L: dict) -> None:
    """Printed plug that closes the valve insertion slot to the pod interior (press fit, 0.04 mm interference per side)."""
    cx, bv = p["coax"], p["bench"]["valve"]
    G = cap_geometry(p, L)
    yc, zn = L["dock"]["y_c"], L["dock"]["z_n"]
    e = bv["plug_interference"]
    s.box("valve_plug", (G["valve_x"][0] - e, G["valve_x"][1] + e), (yc - cx["valve_d"] / 2 - 0.02 - e, yc + cx["valve_d"] / 2 + 0.02 + e),
          (zn + cx["valve_d"] / 2 + bv["plug_gap"], G["z_block"][1]))


def oring_squeeze(p: dict) -> dict:
    og = p["dock"]["cap"]["oring"]
    stretch = og["groove_inner_d"] / og["id"]
    cs_eff = og["cs"] * (1.0 / stretch) ** 0.5            # constant-volume ring: cross-section shrinks with stretch
    return {"stretch": stretch - 1.0, "cs_eff": cs_eff, "squeeze": (cs_eff - og["groove_depth"]) / cs_eff}


def build_oring(s: Script, p: dict, L: dict) -> None:
    """The cap's face O-ring in assembly state (axial squeeze overlaps the reservoir end face by design: interference exclude pair)."""
    og = p["dock"]["cap"]["oring"]
    G = cap_geometry(p, L)
    q = oring_squeeze(p)
    xr = G["x_block"][0]
    D = L["dock"]
    s.tube("cap_oring", "X", (0, D["y_c"], G["z_port"]), og["groove_inner_d"] + 2 * q["cs_eff"], og["groove_inner_d"], xr - (q["cs_eff"] - og["groove_depth"]), xr + og["groove_depth"])


def cap_interfaces(p: dict, L: dict) -> list[dict]:
    """Every sealing interface of the wetted cap path: gap (mm, > 0 clearance, 0 touching, < 0 interference) and the seal element that closes it (None = nothing)."""
    fz, cp, sp, dk = p["reservoir_frozen"], p["dock"]["cap"], p["septum"], p["dock"]
    og = cp.get("oring")
    q = oring_squeeze(p) if og else None
    seal_o = ("face O-ring %.1f x %.1f, axial squeeze %.0f %%" % (og["id"], og["cs"], 100 * q["squeeze"])) if og else None
    bv = p.get("bench", {}).get("valve", {})
    return [
        {"name": "cap spigot d%.2f in reservoir port d%.2f H7" % (cp["spigot_d"], fz["port_d"]), "gap": fz["port_d"] - cp["spigot_d"], "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "cap face on the reservoir end face", "gap": 0.0, "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "septum disc d%.1f in cap bore" % sp["d"], "gap": sp["d"] * (1.0 - cp.get("septum_compress", 0.0)) - sp["d"] if cp.get("septum_compress") else 0.1,
         "seal": "radial compression %.0f %%" % (100 * cp["septum_compress"]) if cp.get("septum_compress") else None, "squeeze": cp.get("septum_compress")},
        {"name": "needle hub in cap bore", "gap": -cp.get("hub_press", 0.0) / 2 if cp.get("hub_press") else dk["hub_clr"],
         "seal": "press fit %.2f per side" % (cp["hub_press"] / 2) if cp.get("hub_press") else None, "squeeze": None},
        {"name": "duckbill valve in its bore", "gap": -bv.get("bore_interference", 0.0), "seal": "interference %.2f" % bv.get("bore_interference", 0.0) if bv.get("bore_interference") else None, "squeeze": None},
        {"name": "valve insertion slot (plug)", "gap": -bv.get("plug_interference", 0.0), "seal": "press-fit plug %.2f" % bv.get("plug_interference", 0.0) if bv.get("plug_interference") else None, "squeeze": None},
    ]
