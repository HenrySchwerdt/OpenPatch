"""NdFeB disc magnets with pole colouring (N red, S blue).

Frames: Z axis. Axial magnets: S half z 0..t/2 (bottom), N half t/2..t (top) -> field points +Z.
        Diametric magnets: axis Z, z 0..t, N half at +X, S half at -X -> magnetisation along +X (S->N inside the magnet).
Colouring only (two bodies per magnet); the physical magnet is one NiCuNi-coated NdFeB piece.
"""
from cc import Part

# id, diameter, thickness, kind, grade
MAGS = [
    ("magnet_d2x1_diametric", 2.0, 1.0, "diametric", "N52"),   # spindle magnet (PARTS-LOCK #7)
    ("magnet_d2x1_axial", 2.0, 1.0, "axial", "N52"),           # dock magnet (PARTS-LOCK #8)
    ("magnet_d3x1p5_diametric", 3.0, 1.5, "diametric", "N52"),  # FINAL spindle magnet chosen by the mechanical owner
    ("magnet_d4x1_diametric", 4.0, 1.0, "diametric", "N52"),   # option
]


def mag(pid, d, t, kind, grade) -> Part:
    p = Part(pid, f"NdFeB {grade} disc {d:g}x{t:g}, {kind}")
    s = p.s
    if kind == "axial":
        s.cyl("S_half", "Z", (0, 0, 0), d, 0, t / 2)
        s.cyl("N_half", "Z", (0, 0, 0), d, t / 2, t)
    else:
        s.cyl("S_half", "Z", (0, 0, 0), d, 0, t)
        s.cyl("N_half", "Z", (0, 0, 0), d, 0, t)
        s.box("cut_s", (-0.0, d), (-d, d), (-0.5, t + 0.5))      # remove x>0 from S
        s.cut("S_half", ["cut_s"])
        s.box("cut_n", (-d, 0.0), (-d, d), (-0.5, t + 0.5))      # remove x<0 from N
        s.cut("N_half", ["cut_n"])
    p.look("S_half", "mag_s")
    p.look("N_half", "mag_n")
    p.cfg.update(pitch=0.6, yaw=-0.6, zoom=1.0)
    return p


def build() -> list[Part]:
    return [mag(*m) for m in MAGS]


META = {}
for pid, d, t, kind, grade in MAGS:
    lock = {"magnet_d2x1_diametric": "docs/PARTS-LOCK.md #7 (superseded: spindle magnet is now d3 x 1.5)", "magnet_d3x1p5_diametric": "final spindle magnet (mechanical owner decision): d3 x 1.5 diametric",
            "magnet_d2x1_axial": "docs/PARTS-LOCK.md #8 (LOCKED, standard item)"}.get(pid, "option size, not locked")
    META[pid] = dict(
        title=f"NdFeB {grade} disc magnet d{d:g} x {t:g}, {kind} magnetisation",
        material=f"NdFeB {grade}, NiCuNi coating", colour="N pole red / S pole blue (visual marker only)",
        frame="Z axis; axial: N on +Z face; diametric: N half at +X (magnetisation +X)",
        source=f"{lock}; dimensions from the project spec (mechanical/parts.md 1.5, params.json drive.mag_d/mag_t). "
               "Catalogue tolerance typically +-0.05 mm (supermagnete.de / AliExpress listing)",
        confidence="datasheet" if pid != "magnet_d4x1_diametric" else "estimated",
        notes="Pole colouring is two half-bodies (STEP/glTF keep them separate). d3/d4 option thicknesses assumed 1 mm "
              "(measured-sample TODO)." if "d2x1" not in pid else "Pole halves are coloured bodies; physical part is one piece.",
    )

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
