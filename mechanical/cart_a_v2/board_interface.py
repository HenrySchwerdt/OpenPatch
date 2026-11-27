#!/usr/bin/env python3
"""Cart pump A v2: mechanical interface of the main board for the electronics flow. TEST ONLY - water only, never on a person.

Writes ../out/cart_a_v2/board_A_interface.json from package.py / shells.py (the single sources). All numbers in pump coordinates (mm):
x = length (rear 0 -> head 65.26), y = width (0 near / cartridge side -> far wall 38.0 at the board, USB-C side), z = height.
The electronics side converts to its board frame. Run: ../../.venv/bin/python board_interface.py
"""
from __future__ import annotations

import json

import numpy as np

import package as pk


def far_inner(x: float) -> float:
    """Inner face of the far wall at height z 8.74 (flat wall part)."""
    return pk.extents(x)[0] - pk.WALL


def main() -> None:
    bx, by = pk.BOARD["x"], pk.BOARD["y"]
    pz0, pz1 = pk.BOARD["pcb_z"]
    tx, ty = pk.TONGUE["x"], pk.TONGUE["y"]
    # antenna wing: the board may grow toward the far wall where the body flares (x 52 .. tongue), 0.4 mm short of the inner wall
    wing = [[round(x, 2), round(far_inner(x) - 0.4, 2)] for x in np.arange(52.0, tx[0] + 0.01, 0.5)]
    iface = {
        "_note": "cart pump A v2 main board (mechanical/CART-A-V2-BRIEF.md). Pump coordinates, mm. TEST ONLY, water only.",
        "thickness_mm": round(pz1 - pz0, 2),
        "pcb_z": [pz0, pz1],
        "seam_z": pk.SEAM_Z,
        "outline": {
            "main_rect": {"x": list(bx), "y": list(by)},
            "notch": {"x": list(pk.BOARD_NOTCH["x"]), "y": [pk.BOARD_NOTCH["y"][0], by[1]],
                      "purpose": "board absent: clears the 4 mm pinion end (x 32.66) on the motor axis"},
            "tongue": {"x": list(tx), "y": list(ty), "purpose": "carries the lock detector switch on its UNDERSIDE"},
            "antenna_wing_max": {"far_edge_y_by_x": wing, "purpose": "optional: the board may extend between y 36.3 and this edge "
                                 "for the HJ-840 antenna end (>= 3 mm from the cell, away from water and motor)"},
            "corner_r_max": 0.5,
        },
        "part_free_strips_both_faces": {
            "near": {"y": [by[0], 20.35], "x": [bx[0], bx[1]], "why": "bottom ledge (partition side) + top clamp 19.35-20.1"},
            "far": {"y": [35.3, by[1]], "x": [[33.0, 35.0], [45.0, 58.0 + pk.XS]],
                    "why": "bottom ledge + top clamp (not at the USB-C, x 35-45)"},
            "rear_stop": {"note": "the rear edge bears on a stop at x 31.97-32.5 (bottom half) for y 18.84-21.0"},
            "front_stop": {"x": [bx[1] + 0.1, bx[1] + 1.2], "y": [18.84, 22.0], "note": "front edge stop block, y 18.84-22.0"},
        },
        "height_limits": {
            "top_mm": round(pk.CELL["z"][0] - 0.5 - pz1, 2),
            "top_why": "cell above (z 11.1) on a 0.5 foam pad",
            "bottom_mm": round(pz0 - pk.WALL - 0.3, 2),
            "bottom_why": "floor at z 1.2; except over the bottom head boss (x >= 62.86, y 19.46-23.46, top z 5.24): 2.8 mm",
            "bottom_boss_zone": {"x": [61.86 + pk.XS, 66.0], "y": [19.46, 23.46], "max_mm": 2.8},
        },
        "fixed_parts": {
            "usb_c": {"centre_x": pk.USB_X, "front_face_y": 36.8, "centre_z": pk.USB_Z, "type": "mid-mount 16p (TYPE-C-31-M-14 class), "
                      "receptacle centred on the PCB mid-plane = the housing seam; opening in the far wall: stadium 9.44 x 3.76"},
            "sw1": {"x": pk.BUTTON_XY[0], "y": pk.BUTTON_XY[1], "face": "top", "type": "top-actuated tactile <= 3.5 x 3.5 x 1.5, "
                    "pressed by a printed plunger from the top face"},
            "led": {"x": pk.LED_XY[0], "y": pk.LED_XY[1], "face": "top", "type": "RGB, top-emitting, under a d2 light pipe"},
            "tmag5273": {"x": list(pk.TMAG_X), "y": [pk.YM - 1.0, pk.YM + 1.0], "face": "top", "why": "beside the angle magnet in the "
                         "4 mm pinion's front bore (x 31.66-32.66, y 33.435, z 8.74)"},
            "lock_switch": {"x": [59.76 + pk.XS, 63.26 + pk.XS], "y": [35.71, 39.21], "face": "bottom (tongue underside)",
                            "actuator": "toward +x, tip at x 64.26 locked / 64.63 free, line y 37.46, z 7.07 (d2 pin from the head)"},
            "sounder": {"x": 56.0 + pk.XS, "y": 26.0, "face": "bottom", "max_h": 2.5, "port": "3 slots in the floor below"},
        },
        "connectors_no_soldering": {
            "motor": {"face": "bottom", "near": [34.0, 33.5], "why": "motor leads run along the floor (notches z 1-5.2 in the motor "
                      "saddles, the rear bulkhead and rib_f, y 34-37.5) and arrive under the board's rear-far corner"},
            "cell": {"face": "bottom", "near": [61.5, 29.0], "why": "the cell lies above the board (x 33.3-64.8, y 24.3-34.9, z 11.1-14.3) "
                     "with its lead at the FRONT end; the lead drops past the board's front edge (free gap x 62.9-65.2, y 22-34.5)"},
            "type": "JST-SH 2 pin on the BOTTOM face (2.9-4.3 mm tall does not fit on top: 1.45 mm)",
        },
        "keepouts_top": [
            {"what": "button plunger d3 + collar d4.2", "x": pk.BUTTON_XY[0], "y": pk.BUTTON_XY[1], "d": 4.4},
            {"what": "light pipe d2", "x": pk.LED_XY[0], "y": pk.LED_XY[1], "d": 2.4},
        ],
        "radio": "HJ-840: antenna end at a board edge with >= 3 mm to the cell pouch (metal laminate: y <= 34.9 above the board), "
                 "> 15 mm to the cartridge water (y <= 17) and to the motor (x <= 27.9); best spot: the antenna wing in the flare",
    }
    out = pk.OUT / "board_A_interface.json"
    out.write_text(json.dumps(iface, indent=1))
    print(out)


if __name__ == "__main__":
    main()
