"""Bench pod drive: NFP-608-26.45-SGM geared stepper COAXIAL with the M1.6 leadscrew through a sleeve coupler.

Axial chain (X, all on the leadscrew axis y = y_s, z = z_axis), from the dry end wall:
  rear boss d2.6 | motor 8.0 | gearbox 8.1 | front boss d3.5 x 0.8 | shaft d2.0 (D-flat 1.5), free length shaft_free |
  coupler (D-bore on the shaft, M1.6 on the screw) | leadscrew | carriage (fixed nut) ... far bearing | magnet (TMAG target).
The reservoir lane starts behind the coupler (the pod is longer than the integrated one by the motor chain).
Motor pins (4, pitch 1.2, row along Z) point -Y (toward the empty area beside the motor); the factory lead (4 x 30 AWG, JST 1.25) runs along -X to a slot in the dry end wall.
One-way duckbill check valve in the outlet path before the needle (pocket in the dock end block).
"""
from __future__ import annotations

from op_cmds import Script


def coax_geometry(p: dict, wall: float, ys: float, zc: float) -> dict:
    dr, cx = p["drive"], p["coax"]
    x_rb0 = wall + cx["rear_gap"]
    x_m0 = x_rb0 + dr["motor_tail"]
    x_m1 = x_m0 + dr["motor_len"]
    x_g1 = x_m1 + dr["gearhead_len"]
    x_fb1 = x_g1 + dr["boss_front"]
    x_tip = x_fb1 + dr["shaft_free"]
    c0 = x_tip - cx["shaft_engage"]
    c1 = c0 + cx["len"]
    pin_x = x_g1 - dr["term_x"]
    bx, brow, bh = dr["term_block"]
    return {"x_rb0": x_rb0, "x_m0": x_m0, "x_m1": x_m1, "x_g1": x_g1, "x_fb0": x_g1, "x_fb1": x_fb1, "x_tip": x_tip,
            "c0": c0, "c1": c1, "screw_x0": x_tip + cx["screw_gap"], "x_carriage_min": c1 + cx["carriage_gap"],
            "pin_x": pin_x, "pin_z": [zc + k * dr["term_pitch"] for k in (1.5, 0.5, -0.5, -1.5)],
            "block_x": [pin_x - bx / 2, pin_x + bx / 2], "block_z": [zc - brow / 2, zc + brow / 2],
            "block_y": [ys - dr["motor_d"] / 2 - bh, ys - dr["motor_d"] / 2],
            "pin_tip_y": ys - dr["motor_d"] / 2 - bh - dr["pin_len"],
            "length_motor_chain": x_tip - x_rb0}


def build_coax_parts(s: Script, p: dict, L: dict) -> None:
    dr, cx, C = p["drive"], p["coax"], L["coax"]
    ys, zc = L["y_s"], L["z_axis"]
    s.cyl("motor_rear_boss", "X", (0, ys, zc), dr["rear_boss_d"], C["x_rb0"], C["x_m0"])
    s.cyl("motor", "X", (0, ys, zc), dr["motor_d"], C["x_m0"], C["x_m1"])
    s.cyl("gearhead", "X", (0, ys, zc), dr["motor_d"], C["x_m1"], C["x_g1"])
    s.cyl("motor_boss", "X", (0, ys, zc), dr["boss_d"], C["x_fb0"], C["x_fb1"])
    s.cyl("motor_shaft", "X", (0, ys, zc), dr["shaft_d"], C["x_fb1"], C["x_tip"])
    # terminal block (+Y side of the motor section) and the 4 pins (row along Z, pointing +Y)
    s.box("motor_term", tuple(C["block_x"]), tuple(C["block_y"]), tuple(C["block_z"]))
    pins = [s.box("motor_pins" if k == 0 else f"t_pin{k}", (C["pin_x"] - 0.15, C["pin_x"] + 0.15), (C["pin_tip_y"], C["block_y"][0]), (z - 0.15, z + 0.15))
            for k, z in enumerate(C["pin_z"])]
    s.join(pins[0], pins[1:])
    # sleeve coupler: D-bore on the shaft, M1.6 on the screw
    s.cyl("coupler", "X", (0, ys, zc), cx["od"], C["c0"], C["c1"])
    s.cyl("t_cp_a", "X", (0, ys, zc), dr["shaft_d"] + 0.04, C["c0"] - 0.1, C["screw_x0"])
    s.cut("coupler", ["t_cp_a"])
    s.cyl("t_cp_b", "X", (0, ys, zc), dr["screw_d"] + 0.04, C["screw_x0"] - 0.01, C["c1"] + 0.1)
    s.cut("coupler", ["t_cp_b"])
    s.cyl("leadscrew", "X", (0, ys, zc), dr["screw_d"], C["screw_x0"], L["screw_tip"])
    s.tube("bush_far", "X", (0, ys, zc), dr["bush_od"], dr["bush_id"], L["far_bush"][0], L["far_bush"][1])
    s.cyl("magnet", "X", (0, ys, zc), dr["mag_d"], L["mag_x"][0], L["mag_x"][1])
    # duckbill valve in its pocket (flow +X toward the needle)
    D, dk = L["dock"], p["dock"]
    s.cyl("duckbill_valve", "X", (0, D["y_c"], D["z_n"]), cx["valve_d"], L["x_r1"] + dk["valve_x0"], L["x_r1"] + dk["valve_x0"] + cx["valve_len"])


def build_coax_joins(s: Script, p: dict, L: dict) -> list[str]:
    """Printed structure: rear/front hard stops of the carriage, lead strain-relief posts."""
    C, cx, wall = L["coax"], p["coax"], L["wall"]
    ys = L["y_s"]
    out = []
    xr0 = L["xrear_full"]
    for k, sg in enumerate((-1, 1)):                # rear stop: two blocks beside the coupler, bear on the housing
        y0, y1 = sorted((ys + sg * 1.6, ys + sg * 2.15))
        out.append(s.box(f"t_rstop{k}", (xr0 - 0.7, xr0 - 0.02), (y0, y1), (wall - 0.1, 3.0)))
    # lead strain relief: two posts, the wires weave between them on their way to the wall slot
    px, y_tip = C["pin_x"], C["pin_tip_y"]
    out.append(s.cyl("t_zz0", "Z", (px - 1.2, y_tip + 0.45, 0), cx["post_d"], wall - 0.1, 5.0))
    out.append(s.cyl("t_zz1", "Z", (px - 2.4, y_tip - 0.45, 0), cx["post_d"], wall - 0.1, 5.0))
    return out


def build_coax_cuts(s: Script, p: dict, L: dict) -> list[str]:
    C, cx = L["coax"], p["coax"]
    y = C["pin_tip_y"]
    # lead slot through the dry end wall (x 0 .. wall), below the lap plane z = 5.0
    return [s.box("t_leadslot", (-0.1, L["wall"] + 0.1), (y - cx["slot_w"] / 2, y + cx["slot_w"] / 2), (cx["slot_z"][0], cx["slot_z"][1]))]


def build_valve_cut(s: Script, p: dict, L: dict) -> list[str]:
    D, dk, cx = L["dock"], p["dock"], p["coax"]
    xr = L["x_r1"]
    x0, x1 = xr + dk["valve_x0"], xr + dk["valve_x0"] + cx["valve_len"]
    # bore for the valve body + an open slot above it: the valve is dropped in from the top (before the board/lid), tweezers only
    return [s.cyl("t_valve", "X", (0, D["y_c"], D["z_n"]), cx["valve_d"] + 0.05, x0, x1),
            s.box("t_valve_slot", (x0, x1), (D["y_c"] - cx["valve_d"] / 2 - 0.02, D["y_c"] + cx["valve_d"] / 2 + 0.02), (D["z_n"], p["shell"]["height"] * 0 + 5.25))]
