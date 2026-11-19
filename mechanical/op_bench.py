"""Bench pod (Rev A bench split, spec 4a): pod sensor board, hall sensors, motor contacts, FFC, cannula adapter.

Frames
  pod   : X = length, Y = width, Z = up (Z = 0 skin side), mm.  Same frame as the integrated variant.
  u, v  : pod X / Y relative to the wet end of the reservoir:  u = x - x_r1,  v = y   (identical for all sizes)
  board : bx = u - U0, by = v - V0 with U0 = u_left, V0 = leg_v0 (origin = lower-left corner of the board bounding box).
          Viewed from the TOP (lid side), X right, Y up (mathematical).  KiCad import: flip Y.
          F.Cu = top (+Z, lid side), B.Cu = bottom (-Z, floor side).

One board for all sizes: every board feature is expressed relative to x_r1 (the motor is wired by its factory lead
to the controller, not to this board), so the board file is identical; only the pod offset
x0 = x_r1 + u_left changes per size.
"""
from __future__ import annotations

import math

from hall_model import axial_disc_on_axis_mT, axial_trigger_distance_mm, bz_phase_amp, diametric_field_mT
from op_cmds import Script

SCHEMA = "openpatch-bench-layout/1"


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int) -> list[list[float]]:
    return [[round(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), 4),
             round(cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), 4)] for i in range(n + 1)]


def bench_geometry(p: dict, L: dict) -> dict:
    """Everything in pod coordinates (absolute) plus board coordinates; one dict, JSON-serialisable."""
    b, hl = p["bench"], p["hall"]
    xr, ys, zc = L["x_r1"], L["y_s"], L["z_axis"]
    t, z0 = b["board_t"], b["board_z0"]
    ztop = z0 + t
    U0, V0 = b["u_left"], b["leg_v0"]
    X0 = xr + U0
    u_right = L["x_end"] - b["right_gap"] - xr
    r = b["corner_r"]

    def pod(u: float, v: float) -> list[float]:
        return [round(xr + u, 4), round(v, 4)]

    def brd(u: float, v: float) -> list[float]:
        return [round(u - U0, 4), round(v - V0, 4)]

    # ---- outline (CCW, board coords) ------------------------------------------------------------
    wv, bv, lu, lobe = b["wing_v"], b["body_v"], b["leg_u"], b["lobe_u"]
    pts_uv = [(U0, wv[0]), (lobe, wv[0]), (lobe, bv[0]), (lu[0], bv[0]), (lu[0], b["leg_v0"]), (lu[1], b["leg_v0"]),
              (lu[1], bv[0]), (u_right, bv[0]), (u_right, bv[1] - r)]
    outline = [brd(*q) for q in pts_uv]
    outline += _arc(u_right - r - U0, bv[1] - r - V0, r, 0, 90, 12)[0:]
    outline += [brd(lobe, bv[1]), brd(lobe, wv[1]), brd(U0, wv[1])]
    # remove consecutive duplicates
    clean: list[list[float]] = []
    for q in outline:
        if not clean or q != clean[-1]:
            clean.append(q)
    width = u_right - U0
    height = bv[1] - V0

    # ---- magnet / sensors -----------------------------------------------------------------------
    mag_c = (xr + (L["mag_x"][0] - xr + L["mag_x"][1] - xr) / 2, ys, zc)
    mag_u = mag_c[0] - xr
    sensors = []
    tm = b["tmag"]
    tz_mid = z0 - tm["pkg"][2] / 2
    dx_t = tm["u"] - mag_u
    sensors.append({
        "id": "HALL_3D", "part": "TMAG5273A1QDBVR (SOT-23-6, LCSC C3716049)", "side": "bottom",
        "center_board_mm": brd(tm["u"], ys), "center_pod_mm": pod(tm["u"], ys),
        "body_xyz_mm": tm["pkg"], "rotation_note": "body length 2.9 along pod X, lead span 2.8 along pod Y",
        "z_body_pod": [round(z0 - tm["pkg"][2], 3), z0], "z_sensing_pod": round(tz_mid, 3),
        "sensing_axes": "3-axis. Package Z (out of the marking face) = -Z_pod because the part hangs under the board; "
                        "package X/Y lie in the board plane (pin row along pod Y).",
        "optional": False, "mandatory_reason": "per-pulse angle check (6.43 deg per tooth); the DRV pair is only a coarse second channel", "air_gap_to_magnet_end_face_mm": round(tm["u"] - tm["pkg"][0] / 2 - (L["mag_x"][1] - xr), 3),
        "dist_to_magnet_centre_mm": round(math.hypot(dx_t, tz_mid - zc), 3),
        "expected_field_mT": round(abs(diametric_field_mT((dx_t, 0.0, tz_mid - zc), 0.0)[2]), 1),
        "note": "On the spindle axis (end-of-shaft angle sensing): B rotates in the Y-Z plane with the magnet, "
                "amplitude about 12 mT (fits the A1 +-40 mT range).",
    })
    dr = b["drv_top"]
    zs = ztop + dr["pkg"][2] / 2
    for i, dvv in enumerate(dr["dvs"]):
        v = ys + dvv
        dxm, dym, dzm = dr["u"] - mag_u, dvv, zs - zc
        ph, amp = bz_phase_amp((dxm, dym, dzm))
        sensors.append({
            "id": f"HALL_{'AB'[i]}", "part": "DRV5032FADMR (X2SON-4 1.1x1.4, LCSC C2152496), omnipolar switch, "
                                           "alt. FADBZR SOT-23 C140921 does not fit the pitch", "side": "top",
            "center_board_mm": brd(dr["u"], v), "center_pod_mm": pod(dr["u"], v),
            "body_xyz_mm": [dr["pkg"][0], dr["pkg"][1], dr["pkg"][2]],
            "rotation_note": "package ROTATED 90 deg: its 1.4 mm side lies along pod X, its 1.1 mm side along pod Y "
                             "(A and B are 2.7 mm apart in Y, edge gap 1.6 mm)",
            "z_body_pod": [round(ztop, 3), round(ztop + dr["pkg"][2], 3)], "z_sensing_pod": round(zs, 3),
            "sensing_axis_pod": [0, 0, 1], "sensing_face": "package top (+Z_pod, away from the board)",
            "air_gap_to_magnet_end_face_mm": round(dr["u"] - dr["pkg"][0] / 2 - (L["mag_x"][1] - xr), 3),
            "dist_to_magnet_centre_mm": round(math.sqrt(dxm ** 2 + dym ** 2 + dzm ** 2), 3),
            "expected_Bz_amplitude_mT": round(amp, 1), "expected_Bz_phase_deg": round(ph, 0),
"note": "Above-and-beyond the magnet end. Bz(theta) phases of A and B differ by ~44 deg (mod 180): for OMNIPOLAR "
                    "switches (|B| > BOP, two edges per 180 deg) that is a true quadrature (A/B edges alternate, order gives direction). "
                    "Amplitude ~8 mT vs BOP 3.9 mT: ~2x margin. Model estimate +-20 %: verify on the bench.",
        })
    dk, ad, D = b["dock"], b["adapter"], L["dock"]
    x_dock = D["x_d"] + dk["dx_from_dome"]
    zdock = z0 - dk["pkg"][2] / 2
    mag_top = ad["lug_top"]
    gap_face = z0 - dk["pkg"][2] - mag_top
    dock_b = axial_disc_on_axis_mT(zdock - mag_top)
    sensors.append({
        "id": "HALL_DOCK", "part": "DRV5032FADMR (X2SON-4 1.1x1.4, LCSC C2152496), omnipolar switch", "side": "bottom",
        "center_board_mm": brd(x_dock - xr, D["y_c"]), "center_pod_mm": [round(x_dock, 4), round(D["y_c"], 4)],
        "body_xyz_mm": dk["pkg"], "rotation_note": "1.1 mm along pod X, 1.4 mm along pod Y",
        "z_body_pod": [round(z0 - dk["pkg"][2], 3), z0], "z_sensing_pod": round(zdock, 3),
        "sensing_axis_pod": [0, 0, 1], "sensing_face": "package top = -Z_pod (faces the magnet below)",
        "air_gap_to_magnet_face_mm": round(gap_face, 3),
        "dist_to_magnet_centre_mm": round(zdock - (mag_top - ad["magnet_t"] / 2), 3),
        "expected_field_mT": round(dock_b, 1),
        "trigger_distance_mm_at_3p9mT": round(axial_trigger_distance_mm(3.9), 2),
        "detection_window_note": "The magnet sits in the adapter's rear latch lug, directly below this sensor only when the dome is "
                                 "fully latched. With BOP 3.9 mT the sensor already switches ~4 mm of travel before full latch "
                                 "(sphere of radius ~5 mm); use a higher-threshold part/TMAG threshold (>= 20 mT -> +-3 mm) and rely on "
                                 "the needle depth mechanics for the final 1.9 mm.",
        "note": "On the underside of the leg, which overhangs the dock channel (dome top is 0.4 mm below the board). "
                "The dome and its latch lug slide underneath during docking.",
    })

    magnets = {
        "spindle": {"center_pod_mm": [round(mag_c[0], 4), ys, zc], "d_mm": p["drive"]["mag_d"], "t_mm": p["drive"]["mag_t"],
                    "axis": "X", "magnetisation": "diametric (rotates with the spindle)", "end_face_x_pod": round(L["mag_x"][1], 4),
                    "spindle_axis_yz_pod": [ys, zc]},
        "dock": {"center_pod_mm": [round(x_dock, 4), round(D["y_c"], 4), round(mag_top - ad["magnet_t"] / 2, 3)],
                 "d_mm": ad["magnet_d"], "t_mm": ad["magnet_t"], "axis": "Z", "magnetisation": "axial",
                 "top_face_z_pod": mag_top, "carrier": "cannula_adapter rear latch lug (bench part)"},
        "assumed_Br_T": 1.3,
    }

    # ---- motor (NFP, coaxial) and its factory lead -----------------------------------------------------------
    C = L["coax"]
    cx = p["coax"]
    if C:
        contacts = {
            "bench_variant": "COAXIAL layout (bench.drive_layout = coaxial). The NFP motor keeps its factory lead (4 x 30 AWG, JST 1.25); it runs along -X to a slot in the dry end wall.",
            "motor_pins_pod": {"x_pod": round(C["pin_x"], 3), "z_pod_B_Aminus_Bplus_A": [round(z, 3) for z in C["pin_z"]], "y_tip_pod": round(C["pin_tip_y"], 3),
                               "direction": "-Y", "pitch_mm": p["drive"]["term_pitch"]},
            "lead_exit_slot": {"wall": "dry end wall (x = 0)", "x_pod": [-0.1, L["wall"] + 0.1], "y_pod": [round(C["pin_tip_y"] - cx["slot_w"] / 2, 3), round(C["pin_tip_y"] + cx["slot_w"] / 2, 3)], "z_pod": cx["slot_z"]},
            "u_per_step": L["drive"]["u_per_step"]}
    else:
        n, ld, G = L["nfp_term"], b["lead"], L["gears"]
        contacts = {
            "bench_variant": "SIDE-BY-SIDE layout (bench.drive_layout = side_gears): NFP motor beside the leadscrew lane, gear pair GHW module 0.3 z%d (motor) : z%d (screw), centre %.2f mm. "
                             "The motor keeps its factory lead (4 x 30 AWG, JST 1.25); it leaves through a floor channel and a slot in the +X end wall, plugs into the bench controller board (not into this board)." % (G["z_motor"], G["z_screw"], G["centre"]),
            "gear_pair": {"z_motor": G["z_motor"], "z_screw": G["z_screw"], "ratio_motor_to_screw": G["ratio_motor_to_screw"], "centre_mm": G["centre"],
                          "u_per_step": L["drive"]["u_per_step"], "formula": "0.35 / (20 x 26.45 x ratio) x 74.63 / 10, ratio = z_screw / z_motor"},
            "motor_axis_pod": {"y": round(L["y_m"], 3), "z": L["z_axis"], "leadscrew_y": round(L["y_s"], 3)},
            "motor_pins_pod": {"x_pod": round(n["x_center"], 3), "y_pod_centres": n["pin_y_centres"], "direction": "-Z (down, bent/trimmed, see parts.md)", "pitch_mm": p["drive"]["term_pitch"]},
            "lead_channel": {"width_mm": ld["groove_w"], "centre_y_pod": ld["groove_y"], "floor_z_pod": ld["groove_floor"], "slot_x_pod": [round(L["length"] - L["wall"] - 0.1, 3), round(L["length"] + 0.1, 3)],
                             "slot_y_pod": [round(ld["groove_y"] - ld["slot_w"] / 2, 3), round(ld["groove_y"] + ld["slot_w"] / 2, 3)], "slot_z_pod": [ld["groove_floor"], ld["slot_z_top"]]}}

    # ---- FFC connector, cable and exit slot --------------------------------------------------------
    f = b["ffc"]
    cu, cv = f["u"], f["v"]
    conn_front_u = cu + f["conn"][0] / 2
    wall_in_x = L["x_end"]
    ffc = {
        "part": "Hirose FH12-10S-0.5SH(55) (LCSC C506791, 10 pos, 0.5 mm pitch, ~1.0 mm high, ZIF flip-lock)",
        "alt_part": "generic FPC-05F-10PH20 (XUNPU C2856798) is 2.0 mm high: too tall; keep Hirose",
        "pins": 10, "pitch_mm": 0.5, "side": "top",
        "contact_side_note": "bottom-contact vs top-contact: verify on the Hirose drawing; if it is the other type order the cable "
                             "with the matching contact side (type A same-side / D opposite-side)",
        "center_board_mm": brd(cu, cv), "center_pod_mm": pod(cu, cv),
        "body_mm": {"depth_along_cable_x": f["conn"][0], "width_y": f["conn"][1], "height_z": f["conn"][2],
                    "note": "envelope incl. latch tabs, +-0.4 mm (VERIFY with the vendor drawing)"},
        "z_body_pod": [round(ztop, 3), round(ztop + f["conn"][2], 3)],
        "cable_exit_direction": "+X (cable leaves toward the +X end wall)", "cable_entry_edge_board_x": round(conn_front_u - U0, 3),
        "pin1_end": "free choice (cable is custom length; pick the end that keeps routing short)",
        "cable": {"type": "FFC 10 P 0.5 mm, 0.3 mm thick", "width_mm": f["cable_w"], "centre_z_pod": round(ztop + f["cable_z"], 3),
                  "length_note": "300 mm typical"},
        "exit_slot": {"wall": "+X end wall (lid part)", "x_pod": [round(L["length"] - L["wall"] - 0.1, 3), round(L["length"] + 0.1, 3)],
                      "y_pod": [round(cv - f["slot_w"] / 2, 3), round(cv + f["slot_w"] / 2, 3)],
                      "z_pod": f["slot_z"], "centre_y_pod": round(cv, 3), "sealed": False},
        "inner_wall_x_pod": round(wall_in_x, 3),
    }

    # ---- mounting ----------------------------------------------------------------------------------
    m = b["mount"]
    mount = {
        "locating_pins": [{"id": f"PIN{i+1}", "center_board_mm": brd(*q), "center_pod_mm": pod(*q),
                           "pin_d_mm": m["pin_d"], "pin_top_z_pod": round(z0 + m["pin_h"] - 0.1, 3),
                           "board_hole_d_mm": m["hole_d"], "hole": "NPTH"} for i, q in enumerate(m["pins"])],
        "screw": {"type": "M1.2 x 4 self-tapping (pan or cheese head, head d 2.4)", "center_board_mm": brd(*m["screw"]),
                  "center_pod_mm": pod(*m["screw"]), "board_hole_d_mm": m["screw_hole_d"], "hole": "NPTH",
                  "top_keepout_d_mm": m["screw_head_keepout"], "boss": "post from the floor, pilot d 1.0 x 3.4 deep"},
        "support_posts": [{"id": f"POST{i+1}", "center_board_mm": brd(*q), "center_pod_mm": pod(*q), "d_mm": m["post_d"],
                           "bottom_keepout_d_mm": m["post_d"] + 0.6, "note": "touches the board underside, no hole"}
                          for i, q in enumerate(m["posts"])],
        "lid_hold_down_pads": [{"id": f"HD{i+1}", "center_board_mm": brd(*q), "center_pod_mm": pod(*q), "d_mm": m["hd_d"],
                                "top_keepout_d_mm": m["hd_d"] + 0.6} for i, q in enumerate(m["hd"])],
        "board_rests_on": "2 pin posts, 2 support posts and the screw boss, all with top at z=%.2f; the leg overhangs the dock channel" % z0,
    }

    # ---- keep-out heights (board coordinates; heights in mm from the board surface) -----------------
    top_free = L["z_top_inner"] - ztop
    keepouts = [
        {"region": "wing (spindle sensors)", "rect_board": [round(U0 - U0, 3), round(wv[0] - V0, 3), round(lobe - U0, 3), round(wv[1] - V0, 3)],
         "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 1.5,
         "note": "bottom: TMAG5273 1.45 mm hangs in free air (floor is 4.0 mm below)"},
        {"region": "body (connector, free area)", "rect_board": [round(lobe - U0, 3), round(bv[0] - V0, 3), round(u_right - U0, 3), round(bv[1] - V0, 3)],
         "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 1.0,
         "note": "bottom: free air (floor is 4.4 mm below); top: FFC connector 1.0 mm"},
        {"region": "leg over the dock channel", "rect_board": [round(lu[0] - U0, 3), round(b["leg_v0"] - V0, 3), round(lu[1] - U0, 3), round(bv[0] - V0, 3)],
         "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 0.4,
         "note": "bottom: ONLY HALL_DOCK (0.4 mm). The dome (top at z=%.1f) and the adapter lug (top z=%.1f) slide under this leg, board bottom z=%.1f" % (p["cannula"]["B_dome_h"], ad["lug_top"], z0)},
    ]
    excl_circles = ([{"what": "locating pin", "center_board_mm": q["center_board_mm"], "d_mm": 2.0, "layers": "top+bottom: no components, no exposed copper"}
                     for q in mount["locating_pins"]]
                    + [{"what": "screw boss (bottom) / head (top)", "center_board_mm": mount["screw"]["center_board_mm"], "d_mm": m["screw_head_keepout"], "layers": "top+bottom"}]
                    + [{"what": "support post", "center_board_mm": q["center_board_mm"], "d_mm": q["bottom_keepout_d_mm"], "layers": "bottom: no components/vias/exposed copper"}
                       for q in mount["support_posts"]]
                    + [{"what": "lid hold-down pad", "center_board_mm": q["center_board_mm"], "d_mm": q["top_keepout_d_mm"], "layers": "top: no components"}
                       for q in mount["lid_hold_down_pads"]])
    return {
        "xr": xr, "X0": X0, "V0": V0, "ztop": ztop, "z0": z0, "t": t, "u_right": u_right,
        "outline": clean, "width": width, "height": height, "sensors": sensors, "magnets": magnets, "contacts": contacts,
        "ffc": ffc, "mount": mount, "keepouts": keepouts, "excl_circles": excl_circles,
        "x_dock": x_dock,
        "motor_clearance_mm": {"board_vs_motor_axis_edge": round((ys + 0) * 0 + L["y_m"] - 3.0 - wv[1], 3),
                               "note": "wing top edge to motor body (Ø6, y_m-3), at x < motor end + 0.3"},
    }


def layout_json(p: dict, L: dict, B: dict) -> dict:
    """Public layout file for the PCB designer (out/bench/OP-xx.layout.json)."""
    b = p["bench"]
    return {
        "schema": SCHEMA, "variant": L["variant"], "kind": "pod_sensor_board", "drawing_no": "OP-100",
        "units": "mm", "status": "generated by mechanical/generate.py --variant bench; geometry is CAD-verified by check.py",
        "one_board_for_all_sizes": True,
        "one_board_note": ("All board-frame numbers below (outline, sensors, FFC, holes) are IDENTICAL for OP-70, OP-100 "
                           "and OP-200; only transform.board_origin_in_pod_mm differs. The motor is NOT on this board (factory lead to the controller)."),
        "frames": {
            "pod": "X length, Y width, Z up (Z=0 skin side); same as the integrated pod",
            "board": "bx,by = pod x,y minus board_origin_in_pod_mm, board viewed from the TOP (lid side), X right, Y up; KiCad: flip Y",
            "layers": "F.Cu = top/lid side (+Z), B.Cu = bottom/floor side (-Z)",
        },
        "transform": {"board_origin_in_pod_mm": [round(B["X0"], 4), round(B["V0"], 4)], "rotation_deg": 0, "mirror": False,
                      "board_to_pod": "x_pod = X0 + bx ; y_pod = V0 + by ; board top (F.Cu) faces +Z_pod",
                      "board_bottom_z_pod": B["z0"], "board_top_z_pod": round(B["ztop"], 3)},
        "board": {"thickness_mm": b["board_t"], "layers": 2, "copper_oz": 1, "finish": "ENIG not required, HASL ok (no fine pitch except FFC/X2SON)",
                  "outline_polygon_board_mm": B["outline"], "outline_note": "closed CCW polygon, last point connects to first; the arc at "
                  "(+X,+Y) corner is R%.1f flattened. Inside corners: add R0.5 for routing." % b["corner_r"],
                  "bbox_mm": [round(B["width"], 3), round(B["height"], 3)],
                  "edge_clearance_to_housing_mm": {"x_end_wall": b["right_gap"], "y_top_wall": round(L["yi1"] - 30.5, 2)}},
        "stack_z_pod": {"floor_z": L["wall"], "board_bottom": B["z0"], "board_top": round(B["ztop"], 3),
                        "lid_inner_z": L["z_top_inner"], "top_free_mm": round(L["z_top_inner"] - B["ztop"], 2),
                        "bottom_free_mm_over_open_floor": round(B["z0"] - L["wall"], 2)},
        "keepout_heights_mm": B["keepouts"], "keepout_circles": B["excl_circles"],
        "hall_sensors": B["sensors"], "magnets": B["magnets"],
        "motor": B["contacts"], "ffc_connector": B["ffc"],
        "mounting": B["mount"],
        "adapter": {"part": "cannula_adapter (dummy dome, printed)", "magnet_pocket": {"d_mm": b["adapter"]["magnet_d"] + b["adapter"]["magnet_clr"],
                                                                 "depth_mm": b["adapter"]["magnet_t"] + 0.05},
                    "magnet": "Ø2 x 1 mm axial NdFeB in the rear latch lug, top face z=%.2f" % b["adapter"]["lug_top"]},
        "dock": {"note": "slide-on dock: horizontal needle axis y=%.2f z=%.2f, dome centre x=%.2f when latched; all cannula.* values TODO-MEASURE"
                         % (L["dock"]["y_c"], L["dock"]["z_n"], L["dock"]["x_d"]),
                 "arm_strain_pct": round(L["dock"]["arm_strain"] * 100, 2)},
        "references": {"pod_layout_full": f"{L['variant']}.mech.json", "motor_end_x_pod": round(L["mot_end"], 3),
                       "x_r1": round(L["x_r1"], 4), "x_dome_centre": round(L["dock"]["x_d"], 3), "spindle_axis_pod_yz": [L["y_s"], L["z_axis"]]},
    }


# ======================================================================================================
# CAD
# ======================================================================================================
def build_bench_electronics(s: Script, p: dict, L: dict) -> None:
    b, hl = p["bench"], p["hall"]
    B = L["bench"]
    xr, ys = L["x_r1"], L["y_s"]
    z0, t, ztop = B["z0"], B["t"], B["ztop"]
    U0, V0 = b["u_left"], b["leg_v0"]
    wv, bv, lu, lobe = b["wing_v"], b["body_v"], b["leg_u"], b["lobe_u"]
    ur, r = B["u_right"], b["corner_r"]

    def X(u: float) -> float:
        return xr + u

    # ---- pod sensor board: wing + body + leg, rounded (+X,+Y) corner, holes ----------------------
    s.box("pod_board", (X(U0), X(lobe + 0.01)), (wv[0], wv[1]), (z0, ztop))
    s.box("t_pb_body", (X(lobe), X(ur)), (bv[0], bv[1]), (z0, ztop))
    s.box("t_pb_leg", (X(lu[0]), X(lu[1])), (b["leg_v0"], bv[0] + 0.01), (z0, ztop))
    s.join("pod_board", ["t_pb_body", "t_pb_leg"])
    cc = s.box("t_pb_corner", (X(ur - r), X(ur) + 0.01), (bv[1] - r, bv[1] + 0.01), (z0 - 0.1, ztop + 0.1))
    s.cyl("t_pb_ccyl", "Z", (X(ur - r), bv[1] - r, 0), 2 * r, z0 - 0.2, ztop + 0.2)
    s.cut(cc, ["t_pb_ccyl"])
    holes = []
    m = b["mount"]
    for i, q in enumerate(m["pins"]):
        holes.append(s.cyl(f"t_pb_pin{i}", "Z", (X(q[0]), q[1], 0), m["hole_d"], z0 - 0.1, ztop + 0.1))
    holes.append(s.cyl("t_pb_screw", "Z", (X(m["screw"][0]), m["screw"][1], 0), m["screw_hole_d"], z0 - 0.1, ztop + 0.1))
    s.cut("pod_board", [cc] + holes)

    # ---- hall sensors --------------------------------------------------------------------------------
    for sen in B["sensors"]:
        cx, cy = sen["center_pod_mm"]
        bx, by, bz = sen["body_xyz_mm"]
        zr = sen["z_body_pod"]
        name = {"HALL_3D": "hall_tmag", "HALL_A": "hall_drv0", "HALL_B": "hall_drv1", "HALL_DOCK": "hall_dock"}[sen["id"]]
        s.box(name, (cx - bx / 2, cx + bx / 2), (cy - by / 2, cy + by / 2), tuple(zr))

    # ---- FFC connector + cable ----------------------------------------------------------------------------
    f = b["ffc"]
    conn = B["ffc"]["center_pod_mm"]
    s.box("ffc_conn", (conn[0] - f["conn"][0] / 2, conn[0] + f["conn"][0] / 2), (conn[1] - f["conn"][1] / 2, conn[1] + f["conn"][1] / 2),
          (ztop, ztop + f["conn"][2]))
    front = conn[0] + f["conn"][0] / 2
    zc = ztop + f["cable_z"]
    s.box("ffc_cable", (front, L["length"] + f["cable_out"]), (conn[1] - f["cable_w"] / 2, conn[1] + f["cable_w"] / 2),
          (zc - f["cable_t"] / 2, zc + f["cable_t"] / 2))

    # ---- dock magnet + cannula adapter (dummy dome) ---------------------------------------------------------
    from op_dock import build_adapter
    ad = b["adapter"]
    s.cyl("dock_magnet", "Z", (L["dock"]["x_d"] + ad["magnet_dx"], L["dock"]["y_c"], 0), ad["magnet_d"], ad["lug_top"] - ad["magnet_t"], ad["lug_top"])
    build_adapter(s, p, L, name="cannula_adapter", lug=True)
