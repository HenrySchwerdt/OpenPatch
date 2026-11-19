"""Li-Po pouch cell with PCM (placeholder, docs/v010 size class) and the Accu-Chek Insight Flex cannula-head DUMMY (assumed dimensions).

battery_lipo_3x12x20 frame: X = length (20), Y = width (12), Z = thickness (3.0), z=0 is the bottom face; PCM end at +X.
cannula_head_dummy frame: dome centre on the Z axis, patch underside z=0, connector slides in along -X (septum faces +X).
"""
from cc import Part

# ---- Li-Po -----------------------------------------------------------------------------------------------------
L_ALL, W, T = 20.0, 12.0, 3.0


def battery() -> Part:
    p = Part("battery_lipo_3x12x20", "Li-Po pouch cell with PCM, 3.0 x 12 x 20 mm (placeholder, ~40 mAh class)")
    s = p.s
    s.box("cell", (0.0, 15.2), (0.0, W), (0.0, T))
    s.add("solid.fillet", edges=[[7.0, 0.0, T], [7.0, W, T], [7.0, 0.0, 0.0], [7.0, W, 0.0]], radius=0.5, body="cell", name="pouch rounding")
    # sealed top edge (folded flange)
    s.box("seal", (15.2, 17.4), (0.5, W - 0.5), (T / 2 - 0.2, T / 2 + 0.2))
    # tabs (Ni) out of the seal to the PCM
    s.box("tab_pos", (17.0, 18.6), (2.2, 4.2), (T / 2 - 0.05, T / 2 + 0.05))
    s.box("tab_neg", (17.0, 18.6), (W - 4.2, W - 2.2), (T / 2 - 0.05, T / 2 + 0.05))
    # PCM board on top of the seal + two small ICs (protection IC + dual MOSFET)
    s.box("pcm", (17.2, L_ALL), (0.8, W - 0.8), (T / 2 + 0.25, T / 2 + 0.25 + 0.45))
    s.box("pcm_ic1", (17.9, 19.4), (3.0, 5.6), (T / 2 + 0.7, T / 2 + 0.7 + 0.55))
    s.box("pcm_ic2", (17.9, 19.4), (6.4, 9.0), (T / 2 + 0.7, T / 2 + 0.7 + 0.55))
    # solder pads (B+, B-/P+, P-) at the board end
    pads = []
    for i, y in enumerate((2.2, 6.0, 9.8)):
        n = f"pcm_pad{i + 1}"
        s.box(n, (19.2, L_ALL), (y - 0.9, y + 0.9), (T / 2 + 0.7, T / 2 + 0.74))
        pads.append(n)
    p.look(["cell", "seal"], "pouch")
    p.look(["tab_pos", "tab_neg"], "nickel")
    p.look("pcm", "fr4_green")
    p.look(["pcm_ic1", "pcm_ic2"], "black_ic")
    p.look(pads, "gold")
    p.cfg.update(pitch=0.65, yaw=-0.6, zoom=1.0)
    return p


# ---- cannula head dummy -------------------------------------------------------------------------------------------
A, B, C = 10.0, 5.0, 3.0        # dome d, height, septum axis height (assumed, cannula-measurement.md / params.json cannula)
D, E = 3.6, 1.0                 # septum recess d, depth
J, K, Lt = 11.0, 11.0, 0.6      # patch footprint and thickness


def cannula() -> Part:
    p = Part("cannula_head_dummy", "Accu-Chek Insight Flex cannula head DUMMY (assumed dimensions, no cannula)")
    s = p.s
    s.rrect("patch", (-K / 2, K / 2), (-J / 2, J / 2), 2.5, (0.0, Lt))
    r = A / 2
    # dome: cylinder wall 1.5 + spherical-ish cap, revolved about Z (XZ sketch: z = -b)
    s.add("sketch.create", plane="XZ", offset=0)
    s.add("sketch.line", points=[[0, -Lt], [r, -Lt], [r, -1.6]])
    s.add("sketch.arc.three_point", start=[r, -1.6], end=[0, -B], through=[r * 0.74, -B * 0.80])
    s.add("sketch.line", points=[[0, -B], [0, -Lt]])
    s.add("sketch.finish")
    s.add("solid.revolve", axis="Z", angle=360, body_name="dome", name="dome")
    # septum recess on the +X side at height C, with the silicone septum sitting in it
    s.cyl("recess_tool", "X", (0, 0, C), D, r - E - 0.4, r + 1.0)
    s.cut("dome", ["recess_tool"])
    s.cyl("septum", "X", (0, 0, C), D - 0.2, r - E - 1.4, r - E - 0.4)
    # latch groove behind the dome equator (assumed notch, cannula.G_latch_dx / H_latch_depth)
    p.look("patch", "white_pa")
    p.look("dome", "dome", opacity=0.5)
    p.look("septum", "silicone", opacity=0.8)
    p.cfg.update(pitch=0.55, yaw=-0.9, zoom=1.0)
    return p


def build() -> list[Part]:
    return [battery(), cannula()]


META = {
    "battery_lipo_3x12x20": dict(
        title="Li-Po pouch cell with protection circuit (PCM), 3.0 x 12 x 20 mm placeholder (~40 mAh class)",
        material="aluminium-laminate pouch, Ni tabs, FR4 PCM", colour="silver / green",
        frame="X length 20 (PCM end at +X), Y width 12, Z thickness 3.0, z=0 bottom face",
        source="Task brief / docs/v010 placeholder 3.0 x 12 x 20 (Rev B target >= 40 mAh); spec/design-parameters.md 'flat Li-Po with PCM' (Rev A 3.2 x 11.2 x <=19.8). NOT a specific vendor cell",
        confidence="placeholder",
        notes="Cell/seal/tab/PCM split is generic. Rev A envelope in params.json battery is 3.2 x 11.2 x up to 19.8 mm; this part is 3.0 x 12 x 20 (does not fit that pocket: width 12 > 11.2). Replace with a sourced cell's drawing."),
    "cannula_head_dummy": dict(
        title="Accu-Chek Insight Flex cannula head (dome + patch + septum) DUMMY, assumed dimensions",
        material="PC/PETG dome, silicone septum, non-woven adhesive patch", colour="translucent clear / white",
        frame="dome centre on Z axis, patch underside z=0, slide direction -X (septum faces +X)",
        source="mechanical/cannula-measurement.md and params.json cannula (A 10.0, B 5.0, C 3.0, D 3.6, E 1.0, J=K=11, L 0.6): ALL TODO-MEASURE, scaled from two photos; Roche publishes no drawing",
        confidence="placeholder",
        notes="ASSUMED. No soft cannula or introducer needle is modelled (puncture hazard, nothing to fit-check). Latch notch not modelled yet (G, H, I letters). Use only for dock-fit layout until the real head is measured."),
}

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
