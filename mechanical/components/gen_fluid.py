"""Fluid-path parts: 30G blunt dispensing needle with hub (Nordson EFD type), duckbill check valve (PLACEHOLDER),
fill septum disc.

Frames (all Z axis):
  needle_30g_efd  : z = 0 at the hub front face, needle tip at +Z (6.35), hub body toward -Z.
  duckbill_valve  : z = 0 at the sleeve (inlet) end, bills point to +Z (flow direction).
  septum_d4x2     : z = 0 .. 2.
"""
from cc import Part

# --- 30G needle (Nordson EFD catalogue: gauge 30, lavender, ID 0.15 / OD 0.31 mm, 1/4" = 6.35 mm) ------
NEEDLE_OD, NEEDLE_ID, NEEDLE_L = 0.31, 0.15, 6.35
# Hub: PP "SafetyLok" luer-lock hub. NOT published dimensionally -> ESTIMATED from a standard luer-lock hub
HUB_NOSE_D0, HUB_NOSE_D1, HUB_NOSE_L = 1.6, 4.2, 2.8     # conical nose at the needle side
HUB_BODY_D, HUB_BODY_L = 6.4, 4.4                        # cylindrical grip body
HUB_FLANGE_D, HUB_FLANGE_L = 8.0, 0.9                    # luer lock ears (two flats)
HUB_FLAT = 6.6


def needle_part() -> Part:
    p = Part("needle_30g_efd_14in", "Nordson EFD-type 30G blunt needle 1/4 in with PP hub (lavender)")
    s = p.s
    # nose cone: wide end at z=-HUB_NOSE_L, narrow end (d0) at z=0
    s.add("sketch.create", plane="XZ", offset=0)
    # XZ sketch: (a, b) -> x = a, z = -b ; build the revolve profile in (r, z') with z' = -z
    r0, r1 = HUB_NOSE_D0 / 2, HUB_NOSE_D1 / 2
    rb = HUB_BODY_D / 2
    L1 = HUB_NOSE_L
    L2 = L1 + HUB_BODY_L
    pts = [[0, 0], [r0, 0], [r1, L1], [rb, L1], [rb, L2], [HUB_FLANGE_D / 2, L2], [HUB_FLANGE_D / 2, L2 + HUB_FLANGE_L], [0, L2 + HUB_FLANGE_L]]
    s.add("sketch.line", points=pts, closed=True)
    s.add("sketch.finish")
    s.add("solid.revolve", axis="Z", angle=360, body_name="hub", name="hub")
    # luer-lock ears: flats on the flange (cut two boxes)
    f0 = -(L2 + HUB_FLANGE_L)
    s.box("flat_a", (HUB_FLAT / 2, 5), (-5, 5), (f0 - 0.1, -L2 + 0.0))
    s.box("flat_b", (-5, -HUB_FLAT / 2), (-5, 5), (f0 - 0.1, -L2 + 0.0))
    s.cut("hub", ["flat_a", "flat_b"])
    # needle tube (cannula): stainless, embedded 3 mm into the hub, bore through
    s.cyl("needle", "Z", (0, 0, 0), NEEDLE_OD, -3.0, NEEDLE_L)
    s.cyl("needle_bore", "Z", (0, 0, 0), NEEDLE_ID, -3.2, NEEDLE_L + 0.1)
    s.cut("needle", ["needle_bore"])
    p.look("hub", "lavender")
    p.look("needle", "steel")
    p.cfg.update(pitch=0.45, yaw=-0.6, zoom=0.95)
    return p


# --- duckbill valve (placeholder) ----------------------------------------------------------------------
DB_OD, DB_ID, DB_SLEEVE, DB_BILL = 3.0, 2.0, 2.0, 2.2     # OD <= 3 (PARTS-LOCK #16); rest generic


def duckbill() -> Part:
    p = Part("duckbill_valve_generic", "Miniature silicone duckbill check valve OD 3 (PLACEHOLDER)")
    s = p.s
    s.tube("sleeve", "Z", (0, 0, 0), DB_OD, DB_ID, 0.0, DB_SLEEVE)
    z0, z1 = DB_SLEEVE, DB_SLEEVE + DB_BILL
    R, r = DB_OD / 2, DB_ID / 2
    # two lips, each a wedge in XZ closing onto a slit at x = 0, extruded along Y (width = bore)
    for sgn, nm in ((-1, "bill_a"), (1, "bill_b")):
        pts = [(sgn * R, z0), (sgn * r, z0), (sgn * 0.04, z1), (sgn * 0.5, z1)]
        s.prism_xz(nm, pts, -r, r)
    s.join("sleeve", ["bill_a", "bill_b"])
    p.look("sleeve", "silicone", opacity=0.75)
    p.cfg.update(pitch=0.5, yaw=-0.6)
    return p


def septum() -> Part:
    p = Part("septum_d4x2", "Fill septum disc d4 x 2, platinum-cure silicone Shore A 40-50")
    s = p.s
    s.cyl("septum", "Z", (0, 0, 0), 4.0, 0.0, 2.0)
    p.look("septum", "silicone", opacity=0.75)
    p.cfg.update(pitch=0.6, yaw=-0.6)
    return p


def build() -> list[Part]:
    return [needle_part(), duckbill(), septum()]


META = {
    "needle_30g_efd_14in": dict(
        title="30G blunt dispensing needle 1/4 in with polypropylene luer-lock hub (Nordson EFD type)",
        material="needle: stainless steel; hub: polypropylene (lavender = 30G colour code)", colour="steel / lavender",
        frame="Z axis; hub front face z=0, needle tip z=+6.35, hub toward -Z",
        source="Needle: Nordson EFD General Purpose Dispense Tips catalogue (gauge 30, lavender, ID 0.15 mm / OD 0.31 mm, "
               "stainless straight blunt, 1/4 in = 6.35 mm, part 7018424). Hub: NOT dimensioned in the catalogue.",
        confidence="datasheet (needle) / estimated (hub)",
        notes="Hub geometry (nose cone d1.6-4.2, body d6.4 x 4.4, ears d8.0, flats 6.6) is an estimate of a generic luer-lock "
              "hub (measured-sample TODO). The project press-fits the needle via its own printed hub, so the real EFD hub is "
              "normally cut away: use the 'needle' body alone for the in-pod model."),
    "duckbill_valve_generic": dict(
        title="Miniature silicone duckbill check valve, OD 3 (PLACEHOLDER, no sourced listing yet)",
        material="silicone (translucent)", colour="translucent clear/blue-white",
        frame="Z axis; sleeve inlet z=0, bills (outlet) toward +Z",
        source="PARTS-LOCK #16 CANDIDATE: 'miniature silicone duckbill OD <= 3 mm, cracking 1-5 kPa'. Shape generic (Minivalve/Vernay "
               "style); no vendor drawing yet",
        confidence="placeholder",
        notes="Every dimension except OD<=3 is invented (sleeve ID 2.0 x 2.0 long, bills 2.2 long, slit closed to 0.08). "
              "Replace when a part is sourced."),
    "septum_d4x2": dict(
        title="Fill septum disc d4 x 2 (punched from platinum-cure silicone sheet)",
        material="silicone Shore A 40-50", colour="translucent",
        frame="Z axis, z 0..2", source="spec / params.json septum.d=4.0, len=2.0; PARTS-LOCK #18",
        confidence="datasheet (spec dimension; vendor sheet thickness TODO)",
        notes="Plain punched disc; real punched edge has a slight taper."),
}

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
