"""Shared geometry of the CUP board (pod frame -> board frame).  Pod frame: top view, +X right, +Y up (mechanical/out/v010-cup/OP-100.mech.json).
Board frame: bx = x - X0, by = Y1 - y  (so the board seen from the top side looks like the top view of the pod; KiCad y points down).

All numbers come from OP-100.mech.json (commit a12ff14) and the CAD bodies of `solidcraft-cli eval` (ko_* boxes):
  lane 2        y 22.8 .. 33.6, cell x 7.87..39.37 (z 0.9..4.1), USB-C ko x 7.87..16.81 y 26.35..33.7 z 4.2..7.46, ko_board x 17.11..39.37, ko_aux x 39.67..44.36
  side_b        x 35.16..46.76, y 17.15..22.5, z 1..7.5   |  side_a x 35.16..44.16, y 1..6.35, z 1..7.5   |  dock_board x 36.36..42.36, y 8.75..14.75, z 5.3..5.9
  dock hall     x 38.81..39.91, y 11.05..12.45 (hangs below the board, z 4.9..5.3)  |  dock magnet centre (39.36, 11.75)
  tank (reservoir bbox) x 10.17..35.11, y 0.9..22.6;  motor x 1.47..7.47;  cannula adapter x 34.86..43.86 y 7.25..16.25 z 0..4.2
"""
X0, Y1 = 7.45, 33.5
BOARD_T = 0.8
Z_BOT = 5.3                 # board underside (matches ko_dock_board z 5.3 and the hall below it)
Z_TOP = Z_BOT + BOARD_T     # 6.1
LID_INNER = 7.6

# outline in the pod frame (CCW seen from the top)
OUTLINE_POD = [(7.45, 33.5), (43.2, 33.5), (43.2, 22.9), (42.0, 22.9), (42.0, 6.35), (44.2, 6.35), (44.2, 1.1), (35.4, 1.1), (35.4, 6.35),
               (36.0, 6.35), (36.0, 17.15), (35.4, 17.15), (35.4, 22.9), (7.45, 22.9)]
ANT_POD = (42.4, 22.9, 43.3, 33.6)          # antenna half of the module: no copper / parts east of x 42.4 (board edge overhang)


def b(x, y):
    return (x - X0, Y1 - y)


def p(bx, by):
    return (bx + X0, Y1 - by)


OUTLINE = [b(*q) for q in OUTLINE_POD]


def rect_b(x0, y0, x1, y1):
    """pod-frame rectangle -> board-frame [bx0, by0, bx1, by1]"""
    a, c = b(x0, y1), b(x1, y0)
    return [a[0], a[1], c[0], c[1]]


ANT = rect_b(*ANT_POD)
# zones with a limited underside height (mm below the board): over the cell and over the cannula adapter (z top 4.2)
LOW_ZONES = [rect_b(7.45, 22.8, 39.4, 33.6), rect_b(34.8, 7.2, 44.0, 16.3)]
BOT_LIMIT = Z_BOT - 4.2          # 1.1 mm (cell top 4.1 + 0.1)
