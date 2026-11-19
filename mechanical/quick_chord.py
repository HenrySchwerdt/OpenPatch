import sys
from pathlib import Path

sys.path.insert(0, ".")
import check_assembly as CA

M = CA.Model(Path("out/v010"), "OP-100")
yr, zc = M.mech["y_r"], M.mech["z_axis"]
for x in (21.8, 22.1, 25.0):
    for dy in (0.0, 5.0, 9.0):
        for dz in (0.0, -1.0):
            for part, kw in (("plunger_core", "outer"), ("reservoir", "hole")):
                a = CA.chord(M.mesh[part], "X", [x, yr + dy, zc + dz], "Y", kw)
                b = CA.chord(M.mesh[part], "X", [x, yr + dy, zc + dz], "Z", kw)
                print(f"x {x} dy {dy} dz {dz} {part:13} Y-chord {a} Z-chord {b}")
