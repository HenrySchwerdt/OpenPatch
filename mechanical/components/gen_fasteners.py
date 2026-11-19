"""Fasteners: M1.6x0.35 stainless threaded rod (modelled thread), DIN 934 M1.6 brass nut, ISO 7045-style M1.2 pan-head screws.

Frames: rod Z axis, z = 0 at the free end where the thread starts, rod extends +Z to length L.
        nut Z axis, z = 0..1.3 (bore axis Z, hex flats parallel to X).
        screw Z axis, head underside at z = 0, head up (0..k), shank down (-L..0).
"""
from cc import Part

# --- M1.6 x 0.35 rod ---------------------------------------------------------------------------
M16_D, M16_P = 1.6, 0.35                  # ISO 261 coarse M1.6: pitch 0.35 (ISO 965 / DIN 13)
# --- DIN 934 M1.6 nut -----------------------------------------------------------------------------
NUT_AF, NUT_M, NUT_E = 3.2, 1.3, 3.41     # DIN 934 / ISO 4032 table: s 3.2, m 1.3 (max), e min 3.41
NUT_BORE = 1.3                            # modelled at minor diameter (D1 = 1.221..1.321); cosmetic M1.6x0.35 on the bore
# --- ISO 7045 M1.2 -------------------------------------------------------------------------------
M12_D, M12_P = 1.2, 0.25
M12_HEAD_D, M12_HEAD_K = 2.4, 0.9         # ESTIMATE: ISO 7045 starts at M1.6 (dk 3.2, k 1.3); M1.2 vendor lists dk 2.3-2.4, k 0.9-1.0


def rod(length: float) -> Part:
    p = Part(f"rod_m1p6_{length:g}", f"M1.6x0.35 A2 stainless threaded rod, L={length:g}")
    s = p.s
    s.cyl("rod", "Z", (0, 0, 0), M16_D, 0.0, length)
    s.add("solid.thread", faces=[{"body": "rod", "point": [M16_D / 2, 0, length / 2]}], designation="M1.6x0.35",
          modeled=True, tip="both", name="M1.6x0.35 thread")
    p.look("rod", "steel")
    p.cfg.update(pitch=0.35, yaw=-0.6, zoom=0.9)
    return p


def nut() -> Part:
    p = Part("nut_din934_m1p6_brass", "DIN 934 M1.6 hex nut, brass")
    s = p.s
    s.add("sketch.create", plane="XY", offset=0)
    # hex with flats parallel to X: circumscribed polygon of apothem AF/2, vertices on the Y axis -> angle 30 deg
    s.add("sketch.polygon.circumscribed", center=[0, 0], radius=NUT_AF / 2, sides=6, angle=0)
    s.add("sketch.finish")
    s.add("solid.extrude", distance=NUT_M, body_name="nut", name="hex")
    # 30 deg corner chamfer on both faces: intersect with a chamfered cylinder over the corners
    s.cyl("chamf", "Z", (0, 0, 0), NUT_E, 0, NUT_M)
    s.add("solid.chamfer", edges=[[NUT_E / 2, 0, 0], [NUT_E / 2, 0, NUT_M]], distance=0.28, distance2=0.16,
          body="chamf", name="corner chamfer")
    s.add("solid.combine", target="nut", tools=["chamf"], operation="intersect", name="chamfer nut")
    s.cyl("bore", "Z", (0, 0, 0), NUT_BORE, -0.1, NUT_M + 0.1)
    s.cut("nut", ["bore"])
    p.look("nut", "brass")
    p.cfg.update(pitch=0.8, yaw=-0.6)
    return p


def screw(length: float) -> Part:
    p = Part(f"screw_iso7045_m1p2x{length:g}", f"ISO 7045 M1.2x{length:g} pan head cross-recess screw, A2")
    s = p.s
    s.cyl("screw", "Z", (0, 0, 0), M12_D, -length, 0.0)
    s.add("solid.thread", faces=[{"body": "screw", "point": [M12_D / 2, 0, -length / 2]}], designation="M1.2x0.25",
          modeled=True, name="M1.2x0.25 thread")
    s.cyl("head", "Z", (0, 0, 0), M12_HEAD_D, 0.0, M12_HEAD_K)
    s.add("solid.fillet", edges=[[M12_HEAD_D / 2, 0, M12_HEAD_K]], radius=0.4, body="head", name="pan dome")
    # cross recess (Phillips-like): two slots + shallow cone dimple
    s.box("rec1", (-0.55, 0.55), (-0.1, 0.1), (M12_HEAD_K - 0.55, M12_HEAD_K + 0.1))
    s.box("rec2", (-0.1, 0.1), (-0.55, 0.55), (M12_HEAD_K - 0.55, M12_HEAD_K + 0.1))
    s.cut("head", ["rec1", "rec2"])
    s.join("screw", ["head"])
    p.look("screw", "steel")
    p.cfg.update(pitch=0.7, yaw=-0.6)
    return p


def build() -> list[Part]:
    return [rod(19.0), rod(22.0), rod(37.0), nut(), screw(3.0), screw(4.0)]


META = {}
for L in (19.0, 22.0, 37.0):
    META[f"rod_m1p6_{L:g}"] = dict(
        title=f"M1.6x0.35 A2/304 stainless threaded rod cut to {L:g} mm (project cut lengths 19/22/37)",
        material="stainless steel A2 (1.4301)", colour="steel grey",
        frame="Z axis, z=0 at one end, rod to +Z",
        source="ISO 261/965: M1.6 coarse pitch 0.35, major d 1.6; thread is a true helical modelled thread (SolidCraft solid.thread, 60 deg ISO profile). Stock 1 m rod is DIN 976-1 class",
        confidence="datasheet (standard)", notes="Standard thread, no vendor-specific geometry. Cut ends modelled square (real cut ends are burred).")
META["nut_din934_m1p6_brass"] = dict(
    title="DIN 934 M1.6 hex nut, brass (AF 3.2, m 1.3)", material="brass (CuZn, nickel plated optional)", colour="brass",
    frame="Z axis, z 0..1.3, flats parallel to X",
    source="DIN 934 / ISO 4032 table: s=3.2, m=1.3, e>=3.41; 30 deg chamfer both faces (chamfer size estimated 0.28 x 0.16)",
    confidence="datasheet (standard)",
    notes="Bore modelled plain at 1.3 (about thread minor D1 1.221-1.321 range); no helical internal thread (rod carries the helical thread).")
for L in (3.0, 4.0):
    META[f"screw_iso7045_m1p2x{L:g}"] = dict(
        title=f"ISO 7045-style M1.2x{L:g} pan head cross-recess screw, A2 stainless",
        material="stainless steel A2", colour="steel grey",
        frame="Z axis, head underside z=0, head up (0..0.9), shank to -L",
        source="ISO 7045 pan head form; M1.2 is below the standard's M1.6 start -> dk 2.4 / k 0.9 ESTIMATED from vendor listings (measured-sample TODO); thread M1.2x0.25 (ISO 261 coarse)",
        confidence="estimated", notes="Cross recess is a simplified two-slot cut, not the ISO 4757 H-recess profile.")

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
