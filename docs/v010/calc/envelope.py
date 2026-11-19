"""Envelope / free-board-area model for the v0.1.0 integrated pod (all electronics in the pod).

TEST PROJECT, NOT A MEDICAL DEVICE. Geometry is taken from mechanical/out/bench/OP-100.{mech,layout}.json (side-by-side motor,
GHW gear pair, slide-on dock). Model: the electronics sit in the block to the right of the reservoir end x_r1 ("u" axis, u = x - x_r1)
exactly as the bench pod sensor board does (one board for all sizes); only a TAIL of length Lt is added behind the dock.

Run:  python3 envelope.py            (prints tables, writes ../board-outline-proposal.json)
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# ---- fixed numbers from the bench CAD (OP-100 snapshot, z18:z18) ------------------------------------------------
H_OUT, WALL = 8.5, 0.9
Z_FLOOR, Z_LID_IN = 0.9, 7.6
Z_BOARD_BOT, T_BOARD = 5.3, 0.8                   # bench pod board: bottom 5.3 because the dome (top z 5.0) slides under it
TOP_FREE = Z_LID_IN - (Z_BOARD_BOT + T_BOARD)     # 1.5 mm (no Qi coil in v0.1.0)
BOT_FREE_AIR = Z_BOARD_BOT - Z_FLOOR              # 4.4 mm where neither battery nor dock is below
BLOCK_U0, BLOCK_U1 = 1.7, 19.0                    # interior block right of the screw lane: board starts u=1.7, interior ends u=19.0 (OP-100)
BOARD_Y0, BOARD_Y1 = 1.5, 30.5                    # 29.0 mm wide (old integrated board used the same)
DOCK = (13.2, 12.6)                               # dome/arm/latch-lug footprint x (u 4.8..18.0, magnet lug centre u 16.7) * y (5.2..17.8)
INSERT_RESERVE = (13.6, 13.6, 5.0)                # swappable dock insert envelope (x,y,z), spec 8a; = dock + 0.4/0.5 mm margin
BATT = (16.0, 11.0)                               # bay for a ~15x10 cell incl. clearance
KEEP_MOUNT = 8 * 6.0                              # 2 pins + screw + 2 posts + 3 hold-downs (layout.json) ~6 mm^2 each
KEEP_ANT = 10.5 * 5.0                             # copper-free antenna zone beyond the module edge (all layers) - from module datasheet class, VERIFY
FILL = {"4L": 0.60, "6L": 0.70}                   # usable fill fraction (placed area / board area) for an autorouter on this tech (rule of thumb, estimate)

SIZES = {"OP-70": 9.4, "OP-100": 13.4, "OP-200": 26.8}     # piston stroke mm
X_R1 = lambda stroke: 11.6 + stroke                          # reservoir end, side-by-side layout (OP-100 -> 25.0, OP-70 -> 21.0 as in the CAD)


def option(Lt, gear_centre=5.4):
    board_len = (BLOCK_U1 - 0.6 - BLOCK_U0) + Lt
    board_w = BOARD_Y1 - BOARD_Y0
    A = board_len * board_w
    block_len = BLOCK_U1 - 0.6 - BLOCK_U0
    A_block = block_len * board_w
    dock = DOCK[0] * DOCK[1]
    batt = BATT[0] * BATT[1]
    tail = Lt * board_w
    # usable area per side (mm^2): efficiency 0.8 for irregular leftover shapes
    top = A - KEEP_MOUNT - KEEP_ANT
    bot_free = 0.8 * (tail + max(A_block - dock - batt, 0) - 0.5 * KEEP_ANT)   # free-air bottom (tall parts allowed)
    bot_low = 0.6 * batt                                                         # over the battery: <= 0.8 mm parts only
    return dict(Lt=Lt, board_len=board_len, board_w=board_w, A=A, top=top, bot_free=bot_free, bot_low=bot_low)


def demand():
    d = {s: bom.area(s) for s in "TBLD"}
    # small bottom-free parts that could also live on top are the flexible ones; tall ones must stay bottom-free
    return d


def pod_dims(stroke, gear_centre):
    x_r1 = X_R1(stroke)
    return x_r1


def main():
    d = demand()
    print("demand (placed mm^2): top %.0f | bottom-free-air %.0f | bottom-low %.0f | dock-hall %.1f ; pads %d, parts cost %.2f USD" %
          (d["T"], d["B"], d["L"], d["D"], bom.pads(), bom.cost()))
    print("top free height %.1f mm; bottom free air %.1f mm; tallest bottom-free part %.1f mm (buzzer 3.0 / module 2.2 / PicoBlade 3.3) -> fits 4.4" %
          (TOP_FREE, BOT_FREE_AIR, max(x.h for x in bom.BOM if x.side == "B")))
    print("top-side tallest part %.2f mm vs free %.2f mm" % (max(x.h for x in bom.BOM if x.side == "T"), TOP_FREE))
    print()
    print("Rule (estimate): both sides together <= 0.60 fill (4-layer autoroute; calibration: failed integrated board ~0.9-1.1, routed bench controller ~0.5 (estimate)), top <= 0.85, free-air bottom <= 0.85 occupancy")
    print("Lt   board LxW      area  | top use/avail | botfree use/avail | botlow use/avail | both sides | verdict")
    best = None
    rows = []
    for Lt in (0, 4, 8, 10, 12, 16, 20):
        o = option(Lt)
        ft = d["T"] / max(o["top"], 1)
        fb = d["B"] / max(o["bot_free"], 1)
        fl = d["L"] / max(o["bot_low"], 1)
        tot = (d["T"] + d["B"] + d["L"]) / max(o["top"] + o["bot_free"] + o["bot_low"], 1)
        ok = tot <= FILL["4L"] and fb <= 0.85 and ft <= 0.85
        rows.append((Lt, o, ft, fb, fl, ok))
        print("%3d  %5.1f x %4.1f  %5.0f | %4.0f/%4.0f=%.2f | %4.0f/%4.0f=%.2f | %3.0f/%3.0f=%.2f | %.2f | %s" %
              (Lt, o["board_len"], o["board_w"], o["A"], d["T"], o["top"], ft, d["B"], o["bot_free"], fb, d["L"], o["bot_low"], fl, tot, "OK (4L)" if ok else "too dense"))
        if ok and best is None:
            best = Lt
    rec = (best or 0) + 2   # +2 mm margin: the passing row sits exactly on the limit
    print("\nsmallest tail that passes the 4-layer density rule: Lt = %s mm -> recommended Lt = %s mm (+2 mm margin)" % (best, rec))
    best = rec
    print("\nPod outline per size (width 32.0 as bench; length = x_r1 + 19.9 + Lt; 18:18 gear pair as in the CAD snapshot; a 15:12 pair would save 1.35 mm width but loses thrust/resolution, see ARCHITECTURE.md)")
    print("size    stroke  x_r1   bench(Lt=0)   v0.1.0 (Lt=%s)   volume cm3 (L*W*8.5)" % best)
    for s, st in SIZES.items():
        x1 = X_R1(st)
        L0 = x1 + 19.9
        L1 = L0 + (best or 0)
        print("%-7s %5.1f  %5.1f   %5.1f x 32.0   %5.1f x 32.0    %.1f" % (s, st, x1, L0, L1, L1 * 32 * 8.5 / 1000))
    print("(Omnipod DASH 52 x 39 x 14.5 = 29.4 cm3)")
    # ---- board outline proposal -----------------------------------------------------------------------
    Lt = best or 0
    o = option(Lt)
    outline = {
        "schema": "openpatch-v010-board-proposal/1",
        "status": "PROPOSAL from docs/v010/calc/envelope.py - the mechanical owner refines it (keepouts copied from mechanical/out/bench/OP-100.layout.json)",
        "units": "mm", "frame": "board frame as the bench pod board: x_pod = x_r1 + 1.7 + bx ; y_pod = 1.5 + by ; F.Cu = lid side",
        "one_board_for_all_sizes": True,
        "per_size": {s: {"x_r1": round(X_R1(st), 1), "board_origin_in_pod": [round(X_R1(st) + 1.7, 1), 1.5], "pod_length": round(X_R1(st) + 19.9 + Lt, 1), "pod_width": 32.0, "pod_height": H_OUT} for s, st in SIZES.items()},
        "board": {"thickness": T_BOARD, "layers": 4, "stackup": "JLC04081H-3313-class 0.8 mm", "bottom_z_pod": Z_BOARD_BOT, "top_z_pod": Z_BOARD_BOT + T_BOARD,
                  "outline_rect": [0, 0, round(o["board_len"], 2), round(o["board_w"], 2)], "corner_r": 2.5,
                  "note": "rectangle; notches for snap-arm roots / screw bosses to be copied from the bench polygon"},
        "zones_board_frame": {
            "dock_insert_reserve": {"rect": [3.1, 3.7, 16.3, 16.3], "bottom_max_height": 0.4, "note": "only the dock hall may be below the board here; insert envelope %sx%sx%s mm" % INSERT_RESERVE},
            "battery_bay": {"rect": [0.0, 17.6, 16.0, 28.6], "bottom_max_height": 0.8, "note": "cell ~15x10x3.2, spring contacts at the -x edge"},
            "tail_free_air": {"rect": [round(o["board_len"] - Lt, 2), 0, round(o["board_len"], 2), round(o["board_w"], 2)], "bottom_max_height": 4.2,
                              "note": "module, buzzer, PicoBlade, boost, bulk caps hang here"},
            "antenna_keepout": {"rect": [round(o["board_len"] - 5.0, 2), 17.0, round(o["board_len"], 2), 27.5], "all_layers_copper_free": True,
                                "note": "VERIFY against the MDBT50Q datasheet keep-out drawing; antenna at the +x end, away from the battery and the motor"},
        },
        "heights_mm": {"top_max": TOP_FREE, "bottom_over_dock": 0.4, "bottom_over_battery": 0.8, "bottom_free_air": 4.2},
        "keepout_circles_copied_from_bench": "see mechanical/out/bench/OP-100.layout.json keepout_circles (pins, screw, posts, hold-downs)",
        "frozen_interface_items": {
            "needle_exit": {"x_pod_OP100": 30.5, "u_from_x_r1": 5.5, "y_pod": 11.5, "z_pod": 3.0, "note": "axis +x; fixed in the pod (end cap), spec 8a"},
            "dock_hall": {"side": "bottom", "center_board_mm": [15.0, 6.9], "center_pod_mm_OP100": [41.7, 11.5], "u_from_x_r1": 16.7, "body_mm": [1.1, 1.4, 0.4], "z_body_pod": [4.9, 5.3], "note": "as bench HALL_DOCK; FIXED in the pod, the insert only carries the magnet",
                          "magnet_in_insert": {"d": 2.0, "t": 1.0, "axis": "Z", "top_face_z_pod": 4.3}},
            "insert_envelope_xyz": INSERT_RESERVE,
        },
    }
    with open(os.path.join(HERE, "..", "board-outline-proposal.json"), "w") as f:
        json.dump(outline, f, indent=1)
    print("\nwrote docs/v010/board-outline-proposal.json")


if __name__ == "__main__":
    main()
