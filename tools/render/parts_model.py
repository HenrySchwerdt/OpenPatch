"""Real-component placements and realistic materials for the OP-100 bench pod scene.

The bench CAD (mechanical/out/bench/OP-*.sc) still holds envelope bodies for most bought parts.  The render
pipeline hides those envelopes and inserts the vendor-accurate component models of mechanical/components/ at the
same place.  Frames of the component models are documented in mechanical/components/catalog.json ("frame").

Pod frame: X along the length (dry end x=0, dock mouth +X), Y across, Z up from the floor.
A placement is (rotation columns of the local axes in pod coordinates, translation).  `P(...)` builds the
row-major 3x4 matrix that file.insert_step takes.
"""
from __future__ import annotations

import math

# ----- matrix helpers (no numpy needed) -------------------------------------------------------------------


def mat(cols, t):
    """cols = images of local X, Y, Z in pod coordinates; returns the flat row-major 3x4 matrix."""
    (xx, xy, xz), (yx, yy, yz), (zx, zy, zz) = cols
    return [xx, yx, zx, t[0], xy, yy, zy, t[1], xz, yz, zz, t[2]]


def rot_local_z(cols, phi):
    """Turn a placement about its own local Z by phi (rad)."""
    c, s = math.cos(phi), math.sin(phi)
    X, Y, Z = cols
    nx = tuple(c * X[i] + s * Y[i] for i in range(3))
    ny = tuple(-s * X[i] + c * Y[i] for i in range(3))
    return (nx, ny, Z)


# local Z -> pod +X, local X -> pod +Y, local Y -> pod +Z (cyclic, proper rotation): drive-axis parts
AX_X = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
# local Z -> pod -X (motor: shaft toward the dry end), terminal block (-Y local) toward the floor (-Z)
AX_MX = ((0, -1, 0), (0, 0, 1), (-1, 0, 0))
# local Z stays Z (parts lying flat)
AX_Z = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
# local Z -> pod +Y (septum: thickness along Y)
AX_Y = ((1, 0, 0), (0, 0, -1), (0, 1, 0))

Y_S, Z_S = 22.5, 4.2      # leadscrew axis
Y_M = 28.0                # motor axis
Y_R, Z_R = 11.2, 3.0      # reservoir / needle axis

# id -> dict(file, name, matrix, hide=[envelope bodies replaced], clip=(axis,lo,hi) optional, look=body-name->look key)
# `bodies` are the names SolidCraft gives the inserted solids (filled in by scene.discover()).
REAL = {
    "rod": dict(file="rod_m1p6_25", cols=AX_X, t=(1.0, Y_S, Z_S), replaces=["leadscrew"], look="steel"),
    "gearb": dict(file="gear_z20_turned", cols=AX_X, t=(2.6, Y_S, Z_S), replaces=["gear_b"], look="brass"),
    "sleeve": dict(file="sleeve_d2x1p6", cols=AX_X, t=(1.9, Y_S, Z_S), replaces=[], look="brass_dark"),
    "geara": dict(file="gear_z16_skimmed", cols=rot_local_z(AX_X, math.pi / 16), t=(2.6, Y_M, Z_S), replaces=["gear_a"], look="brass"),
    "motor": dict(file="nfp_608_26_45", cols=AX_MX, t=(4.9, Y_M, Z_S),
                  replaces=["motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins"], look=None),
    "nut": dict(file="nut_din934_m1p6_brass", cols=AX_X, t=(5.15, Y_S, Z_S), replaces=["nut"], look="brass"),
    "magnet": dict(file="magnet_d3x1p5_diametric", cols=AX_X, t=(25.95, Y_S, Z_S), replaces=["magnet"], look="ndfeb"),
    "needle": dict(file="needle_30g_efd_14in", cols=AX_X, t=(36.1 - 6.35, Y_R, Z_R), replaces=["needle"], look=None),
    "septum": dict(file="septum_d4x2", cols=AX_Y, t=(28.0, 1.05, Z_R), replaces=["septum"], look="silicone"),
    "duckbill": dict(file="duckbill_valve_generic", cols=AX_X, t=(26.4, Y_R, Z_R), replaces=["duckbill_valve"], look="silicone"),
    "dockmag": dict(file="magnet_d2x1_axial", cols=AX_Z, t=(43.8, 11.2, 3.3), replaces=["dock_magnet"], look="ndfeb"),
    "bush_dry": dict(file="bush_ptfe", cols=AX_X, t=(0.9, Y_S, Z_S), replaces=["bush_dry"], look="ptfe"),
    "bush_far": dict(file="bush_ptfe", cols=AX_X, t=(24.6, Y_S, Z_S), replaces=["bush_far"], look="ptfe"),
}

# FFC + connector: connector footprint frame (FFC enters from -Y local -> pod +X), PCB surface z=5.9
FH12 = dict(file="hirose_fh12_10s_0p5sh", cols=((0, 1, 0), (-1, 0, 0), (0, 0, 1)), t=(41.6, 18.5, 5.9))
FFC = dict(file="ffc_05mm_10p_same_side", cols=((0, -1, 0), (1, 0, 0), (0, 0, 1)), t=(40.4, 18.5, 6.0))
