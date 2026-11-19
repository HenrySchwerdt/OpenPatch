"""NFP-608-26.45-SGM 6 mm planetary-gear stepper (nfpshop.com outline drawing, see README).

Local frame: Z = shaft axis, origin on the gearbox mounting (front) face, +Z toward the shaft tip, body toward -Z.
The terminal block sits on the -Y side ("down" in the drawing's end view); the pin row runs along X.
"""
from cc import Part

# --- dimensions (mm); sources in README.md -------------------------------------------------------
D_BODY, L_GEAR, L_MOTOR = 6.0, 8.1, 8.0          # drawing: d6 +-0.1, gearbox 8.1 +-0.1, motor 8.0 +-0.1
BOSS_D, BOSS_L = 3.5, 0.8                       # drawing: front boss d3.5 x 0.8
SHAFT_D, FLAT_W, FLAT_L = 2.0, 1.5, 2.5         # drawing: d2.0 (+0/-0.05), flat to 1.5, flat length 2.5
SHAFT_FREE = 5.3                                # beyond front boss; derived from drawing (11.7 - 8.1 + 2.5 = 6.1 from face)
REAR_BOSS_D, REAR_BOSS_L = 2.6, 0.7             # drawing d2.6; length 0.7 assumed
TERM_Z, TERM_BLOCK, PIN_LEN = 11.0, (4.6, 3.4, 0.65), 1.05   # block (x across, z along, y thick); pins 4 x 1.2 pitch
PIN_PITCH = 1.2


def build_part() -> Part:
    p = Part("nfp_608_26_45", "NFP-608-26.45-SGM geared stepper")
    s = p.s
    zt = BOSS_L + SHAFT_FREE                               # shaft tip z
    # gearbox + motor can (separate bodies so the crimp joint shows)
    s.cyl("gearbox", "Z", (0, 0, 0), D_BODY, -L_GEAR, 0)
    s.cyl("motor_can", "Z", (0, 0, 0), D_BODY, -(L_GEAR + L_MOTOR), -L_GEAR - 0.0)
    s.cyl("front_boss", "Z", (0, 0, 0), BOSS_D, 0, BOSS_L)
    s.cyl("shaft", "Z", (0, 0, 0), SHAFT_D, -0.5, zt)
    # D-flat: flat face at y = +0.5 so the width across flat is 1.5
    s.box("flat_tool", (-1.2, 1.2), (SHAFT_D / 2 - (SHAFT_D - FLAT_W), 1.2), (zt - FLAT_L, zt + 0.2))
    s.cut("shaft", ["flat_tool"])
    s.cyl("rear_boss", "Z", (0, 0, 0), REAR_BOSS_D, -(L_GEAR + L_MOTOR) - REAR_BOSS_L, -(L_GEAR + L_MOTOR))
    # terminal block on -Y side
    bx, bz, bt = TERM_BLOCK
    zc = -TERM_Z
    s.box("term_block", (-bx / 2, bx / 2), (-3.0 - bt, -1.9), (zc - bz / 2, zc + bz / 2))
    # solder pads / pins: 4 x 1.2 pitch, 0.3 mm square, 1.05 mm beyond the block
    names = []
    for i in range(4):
        x = (i - 1.5) * PIN_PITCH
        n = f"pin{i + 1}"
        s.box(n, (x - 0.15, x + 0.15), (-3.0 - bt - PIN_LEN, -3.0 - bt + 0.05), (zc - 0.15, zc + 0.15))
        names.append(n)
    p.look(["gearbox", "motor_can"], "nickel")
    p.look("front_boss", "brass")
    p.look("shaft", "steel")
    p.look("rear_boss", "brass")
    p.look("term_block", "black_pa")
    p.look(names, "tin")
    return p


META = {
    "nfp_608_26_45": dict(
        title="NFP-608-26.45-SGM 6 mm planetary-gear stepper (bare, no lead)",
        material="nickel-plated steel case, brass boss, stainless D-shaft, black PA terminal block, tinned pins",
        colour="nickel grey / brass / black",
        frame="Z = shaft axis, origin on gearbox mounting face, +Z toward shaft tip; terminal block on -Y",
        source="nfpshop.com NFP-608-26.45-SGM product page + outline drawing (stepper-gear-motor-spec-NFP-608-26.45-SGM.pdf); "
               "numbers as transcribed in mechanical/parts.md section 1.0 and params.json drive_presets.nfp_608_26",
        confidence="datasheet",
        notes="Body d6.0, gearbox 8.1, motor 8.0 (drawing). parts.md states total 15.1 but 8.1+8.0 = 16.1: model uses the "
              "sub-dimensions (TODO measure on sample). Rear boss length 0.7, terminal block 4.6x3.4x0.65, pin 0.3 sq x1.05 "
              "are DERIVED/assumed (measured-sample TODO). Product page says lead+JST plug; drawing shows 4 solder pins "
              "(conflict noted in motor-selection.md); see nfp_lead_picoblade.",
    )
}

def build() -> list[Part]:
    return [build_part()]


if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
