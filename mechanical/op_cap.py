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
            "z_block": [L["wall"], D["z_n"] + dk["block_up"]], "x_jog": xr + cp["jog_x"], "x_sept": xr + cp["septum_x"],
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
    ya = yc - 2.0                                   # side branch lane (beside the valve pocket)
    cuts = [
        s.cyl("t_cap_p", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, G["x_jog"] + 0.2),       # port channel
        s.cyl("t_cap_d", "Z", (G["x_jog"], yc, 0), dp, zn - 0.2, zp + 0.2),                             # jog to the needle axis
        s.cyl("t_cap_e", "X", (0, yc, zn), dp, G["x_jog"] - 0.2, G["valve_x"][0] + 0.1),                # junction -> valve
        s.cyl("t_cap_c", "Y", (G["x_jog"], 0, zn), d, ya - 0.2, yc + 0.2),                             # junction -> side lane
        s.cyl("t_cap_b", "X", (0, ya, zn), d, G["x_jog"] - 0.2, G["x_sept"] + 0.2),                    # side lane -> septum x
        s.cyl("t_cap_a", "Y", (G["x_sept"], 0, zn), d, G["y_block"][0] + 3.5, ya + 0.2),               # septum chamber -> side lane
        s.cyl("t_cap_ch", "Y", (G["x_sept"], 0, zn), 1.0, G["y_block"][0] + 3.0, G["y_block"][0] + 3.8),
        s.cyl("t_cap_sb", "Y", (G["x_sept"], 0, zn), p["septum"]["d"] + 2 * p["septum"]["bore_clr"], G["y_block"][0] - 0.1, G["y_block"][0] + 3.1),
        s.cyl("t_cap_f", "X", (0, yc, zn), dp, G["valve_x"][1] - 0.1, D["x_h0"] + 0.1),                  # valve -> hub bore
        s.cyl("t_cap_hb", "X", (0, yc, zn), dk["hub_d"] + dk["hub_clr"], D["x_h0"], D["shroud_end"] + 0.1),
    ]
    s.cut("end_cap", cuts)
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
