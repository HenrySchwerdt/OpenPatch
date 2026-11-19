# SPDX-License-Identifier: LicenseRef-OpenPatch
"""v0.1.0 ZERO-TAIL ("stack") layout (spec 2b): the pod keeps the bench footprint.  TEST PROJECT, water only.

* board + all low-profile parts lie ABOVE the dock tunnel (board bottom z 5.3: insert top 5.2, dome 5.0 -> only 2.3 mm of the lid-side stack remain: 0.8 board + parts <= 1.3 mm);
* the Li-Po cell lies in the full-height strip BESIDE the tunnel (y >= 19.5), 12.8 x 10.2 x 3.2 mm (301012 class);
* radio <= 1.3 mm on the lid side (8 x 8 x 1.0 body), piezo 9 x 9 x 1.0, tact switch, charge pads in a gasketed lid window, vent;
* motor: NFP motor with a short FPC tail (spec 1c) on a contact shelf behind the motor + 4 SMD spring contacts on the board tongue (no PicoBlade, no cable).
Everything is expressed in u = x - x_r1 (and absolute motor/shelf x from the computed layout) so it follows the bench drive layout.
"""
from __future__ import annotations

import math

from op_cmds import Script

NEW_BODIES = ["pod_board", "radio", "battery", "bat_foam", "bat_pad_p", "bat_pad_n", "spring_p", "spring_n", "mspring_1", "mspring_2", "mspring_3", "mspring_4",
              "motor_fpc", "piezo", "switch", "usb_conn", "usb_board", "usb_gasket", "usb_link_1", "usb_link_2"]
MFG_EXTRA = {"usb_gasket": ["usb_gasket"]}


def _arc(cx, cy, r, a0, a1, n=10):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def apply_overrides(p: dict) -> None:
    v, S = p["v010"], p["v010"]["stack"]
    p["bench"]["mount"] = {**p["bench"]["mount"], **S["mount"]}
    p["bench"]["lead"] = {**p["bench"]["lead"], "groove_w": S["motor"]["groove_w"], "groove_y": S["motor"]["groove_y"], "slot_w": S["motor"]["groove_w"],
                          "posts": S["lead"]["posts"], "post_x0": S["lead"]["post_x0"]}
    p["v010"]["extra_screws"] = S["extra_screws"]
    p["v010"]["vent"] = S["vent"]


def plan(p: dict, L0: dict) -> dict:
    S = p["v010"]["stack"]
    xr, B = L0["x_r1"], L0["bench"]
    tm = next(s for s in B["sensors"] if s["id"] == "HALL_3D")
    tmag_end_u = tm["center_pod_mm"][0] + tm["body_xyz_mm"][0] / 2 - xr
    cl = S["cell"]
    cell_u0 = tmag_end_u + cl["tmag_clear"]
    cell_u1 = cell_u0 + cl["l"]
    us = S["usb"]
    usb_tail = cell_u1 + us["gap_cell"] + us["board_len"] + us["d"] + us["gasket_t"] + us["end_gap"]      # USB-C receptacle at the +X end wall in the strip
    tail_len = max(p["bench"]["tail_len"], cell_u1 + 1.2, usb_tail)
    shelf_x0 = L0["mot_end"] + S["motor"]["shelf_dx"]
    return {"layout": "stack", "tmag_end_u": round(tmag_end_u, 3), "cell_u0": round(cell_u0, 3), "cell_u1": round(cell_u1, 3), "tail_len": round(tail_len, 3),
            "shelf_x0": round(shelf_x0, 3), "lead_end_u": round(shelf_x0 - xr, 3), "arms_end_u": round(L0["dock"]["arm_x"][1] - xr, 3),
            "y_lo_arms": round(p["dock"]["y_c"] + p["dock"]["arm_t"] + L0["dock"]["arm_in"] + 0.5, 3)}


def geometry(p: dict, L: dict) -> dict:
    S, pl = p["v010"]["stack"], p["v010_plan"]
    xr, B = L["x_r1"], L["bench"]
    z0, ztop, zi, zt, wall = B["z0"], B["ztop"], L["z_top_inner"], p["shell"]["height"], L["wall"]
    bd, cl, ra, pz, bn, mo = S["board"], S["cell"], S["radio"], S["piezo"], S["button"], S["motor"]
    U0, V0 = B["U0"], bd["y0"]

    def X(u):
        return xr + u

    # ---- board outline: tongue (motor contacts) + wing (spindle sensors) + full width over the tunnel ---------------------------
    u_r = pl["tail_len"] - bd["right_gap"]
    R = bd["corner_r"]
    x_t0 = pl["shelf_x0"] + 0.1                      # tongue starts just over the contact shelf
    pts = [(x_t0, bd["tongue_y0"]), (X(U0), bd["tongue_y0"]), (X(U0), bd["left_y0"]), (X(bd["full_from_u"]), bd["left_y0"]), (X(bd["full_from_u"]), bd["y0"]), (X(u_r - R), bd["y0"])]
    pts += [(X(a), b) for a, b in _arc(u_r - R, bd["y0"] + R, R, -90, 0)[1:]] + [(X(u_r), bd["y1"] - R)]
    pts += [(X(a), b) for a, b in _arc(u_r - R, bd["y1"] - R, R, 0, 90)[1:]]
    pts += [(x_t0 + 1.0, bd["y1"])] + [(x_t0 + a, b) for a, b in [(1.0 - 1.0 * math.cos(math.radians(t)), bd["y1"] - 1.0 + math.sin(math.radians(t))) for t in range(90, 181, 15)]][1:]
    outline_pod = [(round(x, 4), round(y, 4)) for x, y in pts]
    X0 = X(U0)
    outline_board = [[round(x - X0, 4), round(y - V0, 4)] for x, y in outline_pod]
    # ---- cell bay -----------------------------------------------------------------------------------------------------------------
    cell_z0 = wall + cl["foam_t"]
    cell_top = cell_z0 + cl["t"]
    cx0, cx1 = X(pl["cell_u0"]), X(pl["cell_u1"])
    cy0, cy1 = cl["y0"], cl["y0"] + cl["w"]
    cell = {"x": [round(cx0, 3), round(cx1, 3)], "y": [cy0, cy1], "z": [round(cell_z0, 3), round(cell_top, 3)]}
    yc = (cy0 + cy1) / 2
    pads = [{"center_pod": [round(X(pl["cell_u0"] + cl["pad_u"]), 3), round(yc + sg * cl["pad_dy"] / 2, 3)], "size": cl["pad"], "z": [round(cell_top, 3), round(cell_top + 0.05, 3)]} for sg in (-1, 1)]
    ribs = [{"id": "rib_ym", "x": [cx0 - 0.1, cx1 + 0.1], "y": [cy0 - 0.1 - cl["rib_t"], cy0 - 0.1], "h": cl["rib_h"]},
            {"id": "rib_yp", "x": [cx0 - 0.1, cx1 + 0.1], "y": [cy1 + 0.1, cy1 + 0.1 + cl["rib_t"]], "h": cl["rib_h"]}]
    # ---- motor contacts: shelf behind the motor, FPC, 4 SMD spring contacts -------------------------------------------------------
    n = L["nfp_term"]
    sx0 = pl["shelf_x0"]
    shelf = {"x": [sx0, round(sx0 + mo["shelf_len"], 3)], "y": mo["shelf_y"], "z_top": mo["shelf_top"]}
    ymc = n["pin_y_centres"]
    pad_top = mo["shelf_top"] + mo["fpc_t"]
    mpads = [{"center_pod": [round(sx0 + mo["shelf_len"] / 2, 3), round(sum(ymc) / 4 + (k - 1.5) * mo["pitch"], 3)], "z_top": round(pad_top, 3)} for k in range(4)]
    mspring_gap = z0 - pad_top
    # ---- top side -----------------------------------------------------------------------------------------------------------------
    radio = {"x": [round(X(ra["u"][0]), 3), round(X(ra["u"][1]), 3)], "y": ra["y"], "z": [ztop, ztop + ra["h"]]}
    pzx0 = X(pz["u0"])
    piezo = {"x": [round(pzx0, 3), round(pzx0 + pz["l"], 3)], "y": [pz["y0"], pz["y0"] + pz["w"]], "z": [ztop, ztop + pz["h"]], "port": [round(pzx0 + pz["l"] / 2, 3), pz["y0"] + pz["w"] / 2]}
    sw = {"center_pod": [round(X(bn["u"]), 3), bn["y"]], "size": bn["sw"], "z": [ztop, ztop + bn["sw"][2]]}
    us = S["usb"]
    x_in = xr + pl["tail_len"]                       # inner face of the +X end wall
    ycu = us["y_c"]
    bx1 = x_in - us["gasket_t"]
    bx0 = bx1 - us["d"]
    zc, hh = us["z_c"], us["h"]
    usb = {"x": [round(bx0, 3), round(bx1, 3)], "y": [round(ycu - us["w"] / 2, 3), round(ycu + us["w"] / 2, 3)], "z": [round(zc - hh / 2, 3), round(zc + hh / 2, 3)], "nose_x1": round(x_in + wall - 0.15, 3),
           "open_x": [round(x_in - us["gasket_t"] - 0.1, 3), round(x_in + wall + 0.1, 3)], "open_y": [round(ycu - us["open_w"] / 2, 3), round(ycu + us["open_w"] / 2, 3)],
           "open_z": [round(zc - us["open_h"] / 2, 3), round(zc + us["open_h"] / 2, 3)],
           "board": {"x": [round(bx0 - us["board_len"], 3), round(bx0, 3)], "y": [round(ycu - us["w"] / 2 - 0.3, 3), round(ycu + us["w"] / 2 + 0.3, 3)], "z": [round(zc - us["board_t"] / 2, 3), round(zc + us["board_t"] / 2, 3)]},
           "gasket": {"x": [round(bx1, 3), round(x_in, 3)], "outer_y": [round(ycu - us["open_w"] / 2 - us["gasket_w"], 3), round(ycu + us["open_w"] / 2 + us["gasket_w"], 3)],
                      "outer_z": [round(wall + 0.05, 3), 4.9]},
           "link_z": [round(zc + us["board_t"] / 2, 3), z0], "web_above_mm": round(5.0 - (zc + us["open_h"] / 2), 3)}
    vt = S["vent"]
    vent = {"center_pod": [round(X(vt["u"]), 3), vt["y"]], "hole_d": vt["hole_d"], "recess_d": vt["recess_d"], "recess_depth": vt["recess_depth"]}
    m = p["bench"]["mount"]
    holes = [{"what": "lid screw clearance", "center_pod": [s_["x"], s_["y"]], "d": bd["screw_hole_d"]} for s_ in L["screws"] if s_["x"] > X(bd["full_from_u"]) - 2 and s_["y"] > bd["y0"] - 2]
    holes += [{"what": "locating pin", "center_pod": [round(X(q[0]), 4), q[1]], "d": m["hole_d"]} for q in m["pins"]]
    holes += [{"what": "board screw M1.2", "center_pod": [round(X(m["screw"][0]), 4), m["screw"][1]], "d": m["screw_hole_d"]}]
    return {"layout": "stack", "U0": U0, "V0": V0, "X0": X0, "z0": z0, "ztop": ztop, "zi": zi, "zt": zt, "board_t": ztop - z0, "outline_pod": outline_pod, "outline_board": outline_board,
            "u_right": round(u_r, 3), "holes": holes, "cell": cell, "cell_yc": yc, "cell_pads": pads, "ribs": ribs, "spring_gap": round(z0 - (cell_top + 0.05), 3), "shelf": shelf, "motor_pads": mpads,
            "mspring_gap": round(mspring_gap, 3), "radio": radio, "piezo": piezo, "switch": sw, "usb": usb, "vent": vent, "plan": pl,
            "electronics_file": (p.get("v010_electronics") or {}).get("file"), "tongue_x0": round(x_t0, 3)}


def build(s: Script, p: dict, L: dict, G: dict) -> None:
    from op_dock import build_insert
    S = p["v010"]["stack"]
    xr, wall = L["x_r1"], L["wall"]
    z0, ztop, zi, zt = G["z0"], G["ztop"], G["zi"], G["zt"]
    cl, mo, bn = S["cell"], S["motor"], S["button"]
    s.add("solid.remove", bodies=["pod_board", "ffc_conn", "ffc_cable"])
    Lf = dict(L)
    Lf["length"] = xr + p["dock_interface_frozen"]["tail_u"]
    s.add("solid.remove", bodies=["dock_insert"])
    build_insert(s, p, Lf, "dock_insert")
    # board
    s.polyprism("pod_board", [tuple(q) for q in G["outline_pod"]], (z0, ztop))
    s.cut("pod_board", [s.cyl(f"t_bh{i}", "Z", (h["center_pod"][0], h["center_pod"][1], 0), h["d"], z0 - 0.1, ztop + 0.1) for i, h in enumerate(G["holes"])])
    # cell + foam + pads + springs
    c = G["cell"]
    s.box("bat_foam", tuple(c["x"]), tuple(c["y"]), (wall, c["z"][0]))
    s.box("battery", tuple(c["x"]), tuple(c["y"]), tuple(c["z"]))
    for nm, sp_, pd in (("p", "spring_p", G["cell_pads"][0]), ("n", "spring_n", G["cell_pads"][1])):
        px, py = pd["center_pod"]
        s.box(f"bat_pad_{nm}", (px - pd["size"][0] / 2, px + pd["size"][0] / 2), (py - pd["size"][1] / 2, py + pd["size"][1] / 2), tuple(pd["z"]))
        hs = cl["spring"][0] / 2
        s.box(sp_, (px - hs, px + hs), (py - hs, py + hs), (pd["z"][1], z0))
    # motor FPC: pin pads in the groove (z .4..0.5), vertical flex at the shelf edge, pad area on the shelf; 4 spring contacts
    n = L["nfp_term"]
    sh = G["shelf"]
    gfl = p["bench"]["lead"]["groove_floor"]
    t, w = mo["fpc_t"], mo["fpc_w"]
    ycn = sum(n["pin_y_centres"]) / 4
    s.box("motor_fpc", (n["x_center"] + 1.5, sh["x"][0]), (ycn - w / 2, ycn + w / 2), (gfl, gfl + t))
    s.box("t_fpc_v", (sh["x"][0] - t, sh["x"][0]), (ycn - w / 2, ycn + w / 2), (gfl, sh["z_top"] + t))
    s.box("t_fpc_s", (sh["x"][0] - t, sh["x"][1]), (ycn - mo["pad_w"] / 2, ycn + mo["pad_w"] / 2), (sh["z_top"], sh["z_top"] + t))
    s.join("motor_fpc", ["t_fpc_v", "t_fpc_s"])
    for k, mp in enumerate(G["motor_pads"]):
        px, py = mp["center_pod"]
        hs = mo["spring"][0] / 2
        s.box(f"mspring_{k + 1}", (px - hs, px + hs), (py - hs, py + hs), (mp["z_top"], z0))
    # top side parts
    s.box("radio", tuple(G["radio"]["x"]), tuple(G["radio"]["y"]), tuple(G["radio"]["z"]))
    s.box("piezo", tuple(G["piezo"]["x"]), tuple(G["piezo"]["y"]), tuple(G["piezo"]["z"]))
    sx, sy = G["switch"]["center_pod"]
    sw_ = G["switch"]["size"]
    s.box("switch", (sx - sw_[0] / 2, sx + sw_[0] / 2), (sy - sw_[1] / 2, sy + sw_[1] / 2), tuple(G["switch"]["z"]))
    # USB-C receptacle (mid-mount, nose through the end-wall opening), gasket frame, USB board, zebra/elastomer links to the main board
    u = G["usb"]
    s.box("usb_conn", tuple(u["x"]), tuple(u["y"]), tuple(u["z"]))
    s.box("t_usb_nose", (u["x"][1] - 0.01, u["nose_x1"]), tuple(u["y"]), tuple(u["z"]))
    s.join("usb_conn", ["t_usb_nose"])
    gk = u["gasket"]
    s.box("usb_gasket", tuple(gk["x"]), tuple(gk["outer_y"]), tuple(gk["outer_z"]))
    s.box("t_ug_in", (gk["x"][0] - 0.1, gk["x"][1] + 0.1), tuple(u["open_y"]), tuple(u["open_z"]))
    s.cut("usb_gasket", ["t_ug_in"])
    s.box("usb_board", tuple(u["board"]["x"]), tuple(u["board"]["y"]), tuple(u["board"]["z"]))
    lh = S["usb"]["link_h"]
    for k, sg in enumerate((-1, 1)):
        yy = (u["y"][0] + u["y"][1]) / 2 + sg * 2.6
        s.box(f"usb_link_{k + 1}", (u["board"]["x"][0] + 0.3, u["board"]["x"][0] + 1.7), (yy - 0.6, yy + 0.6), tuple(u["link_z"]))
    # housing: ribs, shelf, lid features
    joins = [s.box(f"t_{r['id']}", tuple(r["x"]), tuple(r["y"]), (wall - 0.1, wall + r["h"])) for r in G["ribs"]]
    joins.append(s.box("t_mshelf", tuple(sh["x"]), tuple(sh["y"]), (wall - 0.1, sh["z_top"])))
    ub = G["usb"]["board"]
    for k, dy in enumerate((4.2, -1.5)):         # away from the insert flange (y <= 18.75)
        joins.append(s.cyl(f"t_upost{k}", "Z", (ub["x"][0] + 0.5, (ub["y"][0] + ub["y"][1]) / 2 + dy, 0), 1.2, wall - 0.1, ub["z"][0]))
    s.join("bottom", joins)
    pt = p["port"]
    px, py = G["piezo"]["port"]
    bx, by = sx, sy
    s.join("top", [s.cyl("t_btnpost", "Z", (bx, by, 0), p["button"]["post_d"], ztop + bn["sw"][2] + 0.1, zi + 0.1)])
    vn = G["vent"]
    lc = [s.cyl("t_port", "Z", (px, py, 0), pt["hole_d"], zi - 0.1, zt + 0.1),
          s.cyl("t_prec", "Z", (px, py, 0), pt["recess_d"], zi - 0.1, zi + pt["recess_depth"]),
          s.cyl("t_vent", "Z", (vn["center_pod"][0], vn["center_pod"][1], 0), vn["hole_d"], zi - 0.1, zt + 0.1),
          s.cyl("t_vrec", "Z", (vn["center_pod"][0], vn["center_pod"][1], 0), vn["recess_d"], zi - 0.1, zi + vn["recess_depth"]),
          s.cyl("t_memb", "Z", (bx, by, 0), p["button"]["d_memb"], zt - (wall - p["button"]["memb_t"]), zt + 0.1),
          ]
    s.cut("top", lc)
    s.cut("bottom", [s.box("t_usbopen", tuple(G["usb"]["open_x"]), tuple(G["usb"]["open_y"]), tuple(G["usb"]["open_z"]))])


def project(p: dict, L: dict) -> dict:
    """Projected pod length for the coaxial drive study (coordinator): x_r1' = rear_stack + (res_len - stroke) + stroke', length' = x_r1' + frozen tail."""
    pr = p["v010"]["stack"]["projection"]
    k = pr["stroke_op100"] / p["variants"]["OP-100"]["stroke"]
    stroke2 = L["stroke"] * k
    xr2 = pr["rear_stack"] + (L["res_len"] - L["stroke"]) + stroke2
    tail = p["dock_interface_frozen"]["tail_u"]
    length2 = xr2 + max(tail, L["length"] - L["x_r1"])
    return {"stroke_now": L["stroke"], "stroke_proj": round(stroke2, 2), "x_r1_now": round(L["x_r1"], 2), "x_r1_proj": round(xr2, 2), "length_now": round(L["length"], 2), "length_proj": round(length2, 2)}
