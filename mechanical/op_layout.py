"""Layout-Berechnung (alle Koordinaten in mm).

X = Länge, Y = Breite, Z = Höhe (Z=0 = Hautseite / Klettfläche).
Nur die Reservoirlänge hängt von der Variante ab (Kolbenhub 'stroke').
Rev A: echter Antrieb (Faulhaber ADM0620 + 06/1), Lager, Kolbenführung, Hall-Geber, RF-Modul.
"""
from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_cli() -> str:
    """solidcraft-cli: env SOLIDCRAFT_CLI, then PATH, then the macOS app bundle."""
    return (os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli")
            or "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli")


def load_params(path: Path | None = None) -> dict:
    with open(path or HERE / "params.json", encoding="utf-8") as fh:
        return json.load(fh)


def merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], val)
        else:
            out[key] = val
    return out


def stadium_area(w: float, h: float) -> float:
    return h * (w - h) + math.pi * (h / 2) ** 2


def u_per_step(p: dict, ratio: float) -> float:
    rs, dr = p["reservoir"], p["drive"]
    area = stadium_area(rs["w_in"], rs["h_in"])
    mm_step = dr["screw_pitch"] / (dr["steps_per_rev"] * ratio)
    return mm_step * area / 10.0          # 1 mm3 = 1 ul; U100: 10 ul = 1 U


def compute_layout(p: dict, variant: str) -> dict:
    sh, rs, sp, nd, dr = p["shell"], p["reservoir"], p["septum"], p["needle"], p["drive"]
    bt, pc, co, bz, cn, fit = p["battery"], p["pcb"], p["coil"], p["buzzer"], p["cannula"], p["fit"]
    rf, hl, sc, ct = p["rf"], p["hall"], p["screws"], p["contacts"]
    stroke = p["variants"][variant]["stroke"]
    wall, W = sh["wall"], sh["width"]
    yi0, yi1 = wall, W - wall

    res_h_out = rs["h_in"] + 2 * rs["wall"]
    res_w_out = rs["w_in"] + 2 * rs["wall"]
    lin = rs["dead"] + stroke + rs["plunger_len"] + rs["plunger_gap"]
    bench0 = p.get("mode") == "bench"
    end_wall = p["reservoir_frozen"]["end_wall"] if bench0 else rs["wall"]
    res_len = lin + rs["wall"] + end_wall
    z_axis = wall + res_h_out / 2
    bench = p.get("mode") == "bench"
    # gear plane: bench side_gears uses bench.gears.x0 (the gear tips must clear the R4 rear corner, see params comment)
    gear_x0 = p["bench"]["gears"].get("x0", dr["gear_x0"]) if bench and p["bench"]["drive_layout"] == "side_gears" else dr["gear_x0"]
    gear_x1 = gear_x0 + dr["gear_t"]
    y_r0 = yi0 + (p["bench"]["gap_y"] if bench else sp["gap_y"])
    y_r = y_r0 + res_w_out / 2
    y_s = y_r0 + res_w_out + dr["lane_clr"] + dr["screw_lane_w"] / 2
    coax = None
    layout = p["bench"]["drive_layout"] if bench else "side_gears"
    if bench and layout == "coaxial":           # NFP motor coaxial with the leadscrew: the reservoir lane starts behind the coupler
        from op_coax import coax_geometry
        coax = coax_geometry(p, wall, y_s, z_axis)
        x_r0 = coax["x_carriage_min"] - rs["plunger_gap"] - rs["wall"]
    else:
        x_r0 = gear_x1 + fit["clr_small"]
    x_r1 = x_r0 + res_len
    x_in0, x_in1 = x_r0 + rs["wall"], x_r1 - end_wall
    gz = p["bench"]["gears"] if (bench and layout == "side_gears") else {"z_motor": dr["gear_z"], "z_screw": dr["gear_z"], "module": dr["gear_module"]}
    gear_center_th = gz["module"] * (gz["z_motor"] + gz["z_screw"]) / 2
    gear_center = gear_center_th + gz.get("centre_add", 0.0)
    gears = {"z_motor": gz["z_motor"], "z_screw": gz["z_screw"], "module": gz["module"], "centre": gear_center, "centre_theoretical": gear_center_th,
             "root_motor": gz["module"] * (gz["z_motor"] - 2.5), "root_screw": gz["module"] * (gz["z_screw"] - 2.5),
             "tip_motor": gz["module"] * (gz["z_motor"] + 2), "tip_screw": gz["module"] * (gz["z_screw"] + 2),
             "x0": gear_x0, "x1": gear_x1,
             "ratio_motor_to_screw": gz["z_screw"] / gz["z_motor"]}
    y_m = y_s + gear_center

    xrear_full = x_in0 + rs["plunger_gap"]
    xrear = xrear_full + stroke * (1.0 - rs["fill_fraction"])
    xrear_empty = xrear_full + stroke

    mx0 = gear_x1 + fit["clr_small"] + dr.get("boss_front", 0.0)      # body front face (after the front boss)
    gh_x = (mx0, mx0 + dr["gearhead_len"])
    mo_x = (gh_x[1], gh_x[1] + dr["motor_len"])
    mot_end = mo_x[1] + dr["motor_tail"]

    x_end = x_r1 + (p["bench"]["tail_len"] if bench else co["d"] + 2 * co["gap_x"])
    length = x_end + wall
    from op_dock import dock_geometry
    D = dock_geometry(p, x_r1, wall)
    tower_x = x_end - x_r1                       # compat: dock region length
    x_p, y_p, x_n, y_n, z_tip, pocket_h = D["x_d"], D["y_c"], D["x_h1"], D["y_c"], D["z_n"], cn["B_dome_h"]
    x_s = x_in1 - 0.6

    bl = dr["bush_len"]
    far_bush = (x_r1 - 0.2 - bl, x_r1 - 0.2)
    far_block = (x_r1 - 0.3 - bl, x_r1 - 0.1)
    dry_bush = (wall, wall + bl)
    tc = p["bench"]["thrust"] if (bench and layout == "side_gears") else None
    screw_tip = (far_bush[1] + tc["collar_gap"] + tc["collar_len"]) if tc else x_r1 + 0.15
    thrust = None
    if tc:
        thrust = {"sleeve": [dry_bush[1] + tc["sleeve_gap"], gear_x1], "sleeve_od": tc["sleeve_od"],
                  "collar": [far_bush[1] + tc["collar_gap"], screw_tip], "collar_od": tc["collar_od"],
                  "rod_len": tc["rod_len"][variant], "rod_x": [screw_tip - tc["rod_len"][variant], screw_tip]}
    mag_x = (screw_tip, screw_tip + dr["mag_t"])
    pcb_z0 = pc["z0"]
    hall_x = mag_x[1] + hl["gap_x"] + hl["pkg_x"] / 2
    hall = {"x": hall_x, "y": y_s, "z_top": pcb_z0, "side": "bottom",
            "pkg": [hl["pkg_x"], hl["pkg_y"], hl["pkg_z"]]}
    drv = [{"x": hall_x, "y": y_s - hl["drv_dy"], "z_top": pcb_z0, "side": "bottom"},
           {"x": hall_x, "y": y_s + hl["drv_dy"], "z_top": pcb_z0, "side": "bottom"}]

    c_x = x_r1 + sc["c_dx"]
    dry_y = sc["dry_y"] if layout == "coaxial" else p["screws"].get("dry_y_side", [4.2, 11.7, 19.0])
    screws = [{"x": sc["dry_x"], "y": y} for y in dry_y] + [{"x": c_x, "y": sc["c_y"]}]
    if bench and layout == "coaxial":           # long pod: two more lid screws beside the motor (free area y < 19)
        screws += [{"x": 14.0, "y": 4.2}, {"x": 14.0, "y": 16.5}]

    bat_x0 = max(x_r1 + bt["margin"], mot_end + 0.3, c_x + sc["boss_d"] / 2 + 0.3, mag_x[1] + 0.3)
    bat_x1 = x_end - bt["margin"]
    bat_x = min(bt["x_max"], bat_x1 - bat_x0)
    bat_y0 = bt["y0"]

    pm = pc["margin"]
    pcb_x0, pcb_x1 = x_r1 + co["gap_x"], x_end - pm
    pcb_y0, pcb_y1 = wall + pm, yi1 - pm
    mod_x1, mod_y1 = pcb_x1 - 0.8, pcb_y1 - 0.8
    mod_x0, mod_y0 = mod_x1 - rf["module_x"], mod_y1 - rf["module_y"]
    shelf_x0 = mot_end + ct["shelf_dx"]
    shelf = {"x": [shelf_x0, shelf_x0 + ct["shelf_len"]], "y": ct["shelf_y"], "z_top": ct["shelf_top"]}
    rf_keep = [mod_x0 - 0.5, mod_x1 + 0.1, ct["shelf_y"][1] + 0.1, yi1]
    tab_x = bat_x0 + ct["tab_dx"]
    top_bat = p["fit"]["bat_gap"] + wall + bt["t"]
    contacts = {
        "spring_h_max": ct["spring_h_max"],
        "pcb_bottom_z": pcb_z0,
        "battery_tabs": [{"x": tab_x, "y": bat_y0 + dy, "z_pad_top": top_bat + 0.1, "pad": ct["tab_pad"]} for dy in ct["tab_dy"]],
        "motor_fpc": [{"x": shelf_x0 + 0.6 + i * ct["fpc_pitch"], "y": ct["fpc_y"], "z_pad_top": ct["shelf_top"] + ct["fpc_t"],
                       "pin": i + 1} for i in range(ct["fpc_n"])],
        "motor_shelf": shelf,
        "hold_down_pads": [{"x": tab_x, "y": bat_y0 + sum(ct["tab_dy"]) / 2, "d": ct["pad_d"], "z0": pcb_z0 + pc["t"] + ct["pad_gap"]},
                           {"x": shelf_x0 + 0.6 + (ct["fpc_n"] - 1) * ct["fpc_pitch"] / 2, "y": ct["fpc_y"], "d": ct["pad_d"],
                            "z0": pcb_z0 + pc["t"] + rf["module_z"] + ct["pad_gap"]}],   # drückt über das RF-Modul auf die Platine
        "note": "Federkontakte (<=1.2 mm) auf PCB-Unterseite; Deckelpads (z 5.55..7.6) halten die Platine nieder (Vorspannung).",
    }
    cut_mt = None
    if mot_end + 0.2 > pcb_x0:
        cut_mt = [pcb_x0 - 0.1, mot_end + 0.2, y_m - dr["motor_d"] / 2 - 0.2, pcb_y1 + 0.1]
    cutouts = {
        "magnet": [pcb_x0 - 0.1, hall_x - hl["pkg_x"] / 2 - 0.2, y_s - 1.4, y_s + 1.4],
        "tower_notch": [pcb_x0 - 0.1, x_r1 + pc["notch_x"] + sp["boss_d"] / 2 - 0.6, pcb_y0 - 0.1, wall + pc["notch_y"] + 0.4],
        "screw_c": [c_x - 1.4, c_x + 1.4, sc["c_y"] - 1.4, sc["c_y"] + 1.4],
    }
    cutouts["dock_channel"] = [pcb_x0 - 0.1, x_end + 0.1, D["y_c"] - 5.9, D["y_c"] + 5.9]
    if cut_mt:
        cutouts["motor_tail"] = cut_mt

    btn = p["button"]
    strip_x0 = max(hall_x + 1.0, c_x + sc["boss_d"] / 2 + 0.4, pcb_x0 + 0.2, bat_x0 + ct["tab_dx"] + 0.6 + ct["pad_d"] / 2 + 0.3)
    strip_x1 = pcb_x1 - 0.2
    sw_w = btn["sw_x"] + 0.6
    btn_x = strip_x1 - sw_w / 2
    bz_x1 = btn_x - sw_w / 2 - 0.5
    bz_x0 = max(strip_x0, bz_x1 - bz["x"])
    bz_y0 = bz["y0"]
    bz_y1 = rf_keep[2] - 0.0
    bz_y1 = min(bz_y0 + bz["y"], mod_y0 - 0.2)          # unterhalb des RF-Moduls
    buzzer = {"x0": bz_x0, "x1": bz_x1, "y0": bz_y0, "y1": bz_y1,
              "fits_9x9": (bz_x1 - bz_x0) >= bz["x"] - 1e-9 and (bz_y1 - bz_y0) >= bz["y"] - 1e-9,
              "z0": pcb_z0 + pc["t"], "z1": pcb_z0 + pc["t"] + bz["z"]}
    for hp in contacts["hold_down_pads"]:
        on_mod = mod_x0 - 0.3 <= hp["x"] <= mod_x1 + 0.3 and mod_y0 - 0.3 <= hp["y"] <= mod_y1 + 0.3
        hp["z0"] = pcb_z0 + pc["t"] + (rf["module_z"] if on_mod else 0.0) + ct["pad_gap"]
        hp["on_module"] = on_mod
    btn_pos = {"x": btn_x, "y": bz_y0 + (bz_y1 - bz_y0) / 2}

    nfp_term = None
    if "boss_front" in dr:
        xt = mx0 + dr["term_x"]
        bx, by, bz = dr["term_block"]
        zb = z_axis - dr["motor_d"] / 2 - bz
        nfp_term = {"x_center": xt, "block_x": [xt - bx / 2, xt + bx / 2], "block_y": [y_m - by / 2, y_m + by / 2],
                    "block_z": [zb, zb + bz],
                    "pins_x": [xt, xt + dr["pin_tab_len"]], "pins_y": [y_m - 1.5 * dr["term_pitch"] - 0.15, y_m + 1.5 * dr["term_pitch"] + 0.15],
                    "pins_z": [zb - dr["pin_tab_t"], zb],
                    "pin_y_centres": [round(y_m + k * dr["term_pitch"], 3) for k in (1.5, 0.5, -0.5, -1.5)],
                    "pin_order_drawing_left_to_right": ["B", "A-", "B+", "A"],
                    "pins_as_supplied_tip_z": round(zb - dr["pin_len"], 3)}
    out = {
        "nfp_term": nfp_term, "coax": coax, "gears": gears, "drive_layout": layout,
        "mode": p.get("mode", "integrated"), "nfp": "boss_front" in dr, "mx0": mx0,
        "dock": D, "variant": variant, "stroke": stroke, "length": length, "width": W,
        "height": sh["height"], "wall": wall, "xi0": wall, "yi0": yi0, "yi1": yi1,
        "x_end": x_end, "res_len": res_len, "res_h_out": res_h_out, "res_w_out": res_w_out,
        "z_axis": z_axis, "x_r0": x_r0, "x_r1": x_r1, "x_in0": x_in0, "x_in1": x_in1,
        "y_r0": y_r0, "y_r": y_r, "y_s": y_s, "y_m": y_m, "lin": lin,
        "xrear": xrear, "xrear_full": xrear_full, "xrear_empty": xrear_empty,
        "tower_x": tower_x, "x_p": x_p, "y_p": y_p, "x_n": x_n, "y_n": y_n, "z_tip": z_tip,
        "pocket_h": pocket_h, "x_s": x_s, "z_top_inner": sh["height"] - wall,
        "coil_cx": x_r1 + co["gap_x"] + co["d"] / 2, "coil_cy": yi0 + 0.2 + co["d"] / 2,
        "bat_x": bat_x, "bat_x0": bat_x0, "bat_y0": bat_y0, "bat_y1": bat_y0 + bt["y"], "contacts": contacts,
        "bat_vol_mm3": bat_x * bt["y"] * bt["t"],
        "gear_x0": gear_x0, "gear_x1": gear_x1, "gh_x": list(gh_x), "mo_x": list(mo_x), "mot_end": mot_end,
        "far_bush": list(far_bush), "far_block": list(far_block), "dry_bush": list(dry_bush),
        "screw_tip": screw_tip, "thrust": thrust, "mag_x": list(mag_x), "hall": hall, "drv5032": drv,
        "screws": screws, "c_x": c_x,
        "pcb": {"x": [pcb_x0, pcb_x1], "y": [pcb_y0, pcb_y1], "z": [pcb_z0, pcb_z0 + pc["t"]], "cutouts": cutouts},
        "rf_module": {"x": [mod_x0, mod_x1], "y": [mod_y0, mod_y1],
                      "z": [pcb_z0 + pc["t"], pcb_z0 + pc["t"] + rf["module_z"]],
                      "antenna_end": "+Y", "keepout_xy": rf_keep, "keepout_r": rf["keepout_r"]},
        "buzzer": buzzer, "button": btn_pos,
        "topside_height_under_coil": co["z0"] - (pcb_z0 + pc["t"]),
        "coil": {"cx": x_r1 + co["gap_x"] + co["d"] / 2, "cy": yi0 + 0.2 + co["d"] / 2, "d": co["d"],
                 "z": [co["z0"], co["z0"] + co["t"]]},
        "drive": {"gh_ratio_nominal": dr["gh_ratio"], "u_per_step": u_per_step(p, dr["gh_ratio"] * (gears["ratio_motor_to_screw"] if layout == "side_gears" else 1.0)),
                  "gear_ratio_motor_to_screw": gears["ratio_motor_to_screw"]},
    }
    if p.get("drive_mode") in ("inline", "coaxial"):          # optional sealed on-axis drive (op_inline.py); default pod untouched
        from op_inline import inline_layout
        out["inline"] = inline_layout(p, out)
    if out["mode"] == "bench":
        from op_bench import bench_geometry          # lazy: op_bench needs only the finished layout dict
        out["bench"] = bench_geometry(p, out)
    return out


def lap_dims(p: dict) -> dict:
    return {k: p["shell"][k] for k in ("lap_low", "lap_high", "rim_inset", "lid_ring_inset")}
