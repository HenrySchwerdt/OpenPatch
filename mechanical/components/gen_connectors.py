"""Connectors and cables: Hirose FH12-10S-0.5SH ZIF, 0.5 mm FFC ribbon, Molex PicoBlade 53261-0471 header,
PicoBlade 51021-0400 plug with 4-wire motor lead.

Frames (z = 0 at the PCB surface, +Z up) follow the KiCad footprints so the models drop onto the board:
  fh12_10s_0p5sh : footprint origin at the connector centre; FFC enters from -Y (lever side), solder tails / pads at +Y.
  picoblade_53261_0471 : footprint origin; cavity (mating face) toward -Y, solder tails toward +Y.
  ffc_05mm_10p_same_side : flat in XY, length along +Y from y=0, thickness 0.3 (z 0..0.3), contacts on the bottom face (z=0).
  lead_picoblade_plug : plug mated in the header's frame (it sits in the cavity), wires leave toward -Y.
"""
from cc import DENSITY, PAL, Part

PAL["pa_beige"] = ("#e8dcb5", 0.0, 0.5)
PAL["ffc_pet"] = ("#7fa6c0", 0.0, 0.4)
PAL["pb_natural"] = ("#efeee6", 0.0, 0.5)
DENSITY.update({"pa_beige": 1.15, "ffc_pet": 1.4, "pb_natural": 1.14})


def fh12() -> Part:
    p = Part("hirose_fh12_10s_0p5sh", "Hirose FH12-10S-0.5SH(55) 0.5 mm FFC/FPC ZIF connector, 10 pos, bottom contact")
    s = p.s
    B, C, H = 8.1, 9.1, 2.0           # Hirose catalogue table: B = 8.1 (housing width), C = 9.1 (incl. ground tabs), H = 2.0
    # housing (lower part) with the FFC slot; flip-lock actuator closed on top
    s.box("housing", (-B / 2, B / 2), (-2.8, 2.0), (0.0, 1.35))
    s.box("slot", (-3.05, 3.05), (-2.9, 0.4), (0.38, 0.72))      # slot for t=0.3 FFC, 6.1 wide
    s.cut("housing", ["slot"])
    s.box("lock", (-3.9, 3.9), (-3.1, 1.7), (1.35, H))
    # contacts: 10 tails on 0.5 pitch at the back (pad centres y=+1.85 in the model frame, 0.3 wide)
    tails = []
    for i in range(10):
        x = (i - 4.5) * 0.5
        n = f"tail{i + 1}"
        s.box(n, (x - 0.15, x + 0.15), (1.2, 2.5), (0.0, 0.12))
        tails.append(n)
    # ground / retention tabs
    tabs = []
    for sg, n in ((-1, "tab_l"), (1, "tab_r")):
        x0, x1 = (sg * (B / 2 - 0.1), sg * (C / 2)) if sg > 0 else (sg * (C / 2), sg * (B / 2 - 0.1))
        s.box(n, (x0, x1), (0.2, 2.5), (0.0, 0.15))
        tabs.append(n)
    p.look(["housing", "lock"], "pa_beige")
    p.look(tails + tabs, "gold")
    p.cfg.update(pitch=0.75, yaw=-0.6, zoom=0.95)
    return p


def ffc(length: float = 30.0) -> Part:
    p = Part("ffc_05mm_10p_same_side", f"0.5 mm pitch FFC ribbon, 10 conductors, same-side contacts, {length:g} mm")
    s = p.s
    W, T = 6.0, 0.30                 # width 6.0 (params ffc.cable_w), thickness 0.3 (Hirose FH12: t = 0.3 +-0.05)
    s.box("film", (-W / 2, W / 2), (0.0, length), (0.035, T))
    cond = []
    for end, (y0, y1) in enumerate(((0.0, 3.5), (length - 3.5, length))):
        for i in range(10):
            x = (i - 4.5) * 0.5
            n = f"c{end}_{i + 1}"
            s.box(n, (x - 0.15, x + 0.15), (y0, y1), (0.0, 0.035))
            cond.append(n)
    # stiffener pads over the contact ends (conductors face down)
    s.box("stiff_a", (-W / 2, W / 2), (0.0, 3.5), (T, T + 0.15))
    s.box("stiff_b", (-W / 2, W / 2), (length - 3.5, length), (T, T + 0.15))
    s.join("film", ["stiff_a", "stiff_b"])
    p.look("film", "ffc_pet", opacity=0.85)
    p.look(cond, "tin")
    p.cfg.update(pitch=0.9, yaw=-0.5, zoom=1.0)
    return p


def picoblade_header() -> Part:
    p = Part("molex_picoblade_53261_0471", "Molex PicoBlade 53261-0471 4-circuit right-angle SMT header, 1.25 mm")
    s = p.s
    s.box("housing", (-3.34, 3.34), (-2.6, 1.53), (0.0, 3.4))
    s.box("cavity", (-2.9, 2.9), (-2.7, -0.85), (0.55, 2.85))
    s.cut("housing", ["cavity"])
    parts_ = []
    for i in range(4):
        x = (i - 1.5) * 1.25
        s.box(f"tail{i + 1}", (x - 0.25, x + 0.25), (0.8, 2.6), (0.0, 0.2))      # SMT tail (pad y=+2.4)
        s.box(f"blade{i + 1}", (x - 0.15, x + 0.15), (-2.1, -0.8), (0.55, 1.0))   # contact blade in the cavity
        parts_ += [f"tail{i + 1}", f"blade{i + 1}"]
    for sg, n in ((-1, "tab_l"), (1, "tab_r")):
        x0, x1 = ((3.34, 5.08) if sg > 0 else (-5.08, -3.34))
        s.box(n, (x0, x1), (-2.2, 0.56), (0.0, 0.2))                               # solder tabs; footprint MP pads 2.1 x 3.0 at x=+-4.425
        parts_.append(n)
    p.look("housing", "pb_natural")
    p.look(parts_, "tin")
    p.cfg.update(pitch=0.75, yaw=-0.6, zoom=1.0)
    return p


def lead() -> Part:
    p = Part("lead_picoblade_plug", "PicoBlade 51021-0400 plug with 4-wire 30 AWG lead (NFP motor lead, 30 mm shown)")
    s = p.s
    s.box("plug", (-2.8, 2.8), (-4.6, -1.0), (0.85, 2.85))
    wires, ends = [], []
    cols = ["wire_blk", "wire_red", "wire_ylw", "wire_wht"]
    for i in range(4):
        x = (i - 1.5) * 1.25
        n = f"wire{i + 1}"
        s.cyl(n, "Y", (x, 0, 1.85), 0.45, -34.6, -4.5)          # 30 AWG insulated OD ~0.45; 30 mm exposed length modelled
        e = f"strip{i + 1}"
        s.cyl(e, "Y", (x, 0, 1.85), 0.25, -36.1, -34.6)         # 1.5 mm stripped, tinned conductor
        wires.append(n)
        ends.append(e)
        p.look(n, cols[i])
    p.look("plug", "pb_natural")
    p.look(ends, "tin")
    p.cfg.update(pitch=0.6, yaw=-0.7, zoom=1.0)
    return p


def build() -> list[Part]:
    return [fh12(), ffc(), picoblade_header(), lead()]


META = {
    "hirose_fh12_10s_0p5sh": dict(
        title="Hirose FH12-10S-0.5SH(55) FFC/FPC connector, 0.5 mm, 10 pos, flip-lock, bottom contact",
        material="LCP housing, phosphor-bronze gold-plated contacts, tin-plated tabs", colour="beige / gold",
        frame="footprint frame: origin at connector centre, PCB surface z=0, FFC enters from -Y, tails at +Y",
        source="Hirose FH12 catalogue (FH12_Series.pdf) 0.5mm bottom-contact table: A 4.5 / B 8.1 / C 9.1 / D 5.57 for 10 pos; "
               "'standard type connector height 2 mm'; KiCad stock footprint Hirose_FH12-10S-0.5SH_1x10-1MP (pad pitch 0.5, MP pads +-4.15) for tails/tabs",
        confidence="datasheet (B, C, H, pitch) / estimated (slot, lever detail)",
        notes="FH12 is 2.0 mm HIGH, but params.json bench.ffc.conn assumes 1.0 mm and spec s4a asks for <= 1.2 mm: the "
              "ZIF as locked does not meet that height budget (pod stack must allow 2.0 or switch to a lower connector). "
              "Lever shown closed; opening rotates it up (adds ~1.5 mm toward -Y)."),
    "ffc_05mm_10p_same_side": dict(
        title="0.5 mm pitch FFC ribbon, 10 conductors, same-side contacts, 30 mm (cut to length in practice)",
        material="PET film, Cu conductors tin-plated, PET stiffener at the ends", colour="translucent blue / tin",
        frame="flat in XY, length along +Y from y=0, z 0..0.3, contacts on the bottom face (z=0) at both ends",
        source="Hirose FH12 datasheet applicable FPC: t = 0.30 +-0.05, 0.5 mm pitch, 10 conductors -> width 6.0 (params.json bench.ffc.cable_w); conductor width 0.3 / thickness 0.035 typical (IPC-4203)",
        confidence="estimated", notes="Generic; actual stiffener thickness and conductor width vary per vendor (measured-sample TODO)."),
    "molex_picoblade_53261_0471": dict(
        title="Molex PicoBlade 53261-0471 header, 4 circuits, 1.25 mm, right-angle SMT",
        material="natural nylon housing, tin-plated tails", colour="off-white / tin",
        frame="footprint frame: origin at footprint centre, cavity toward -Y, tails toward +Y, PCB surface z=0",
        source="KiCad stock footprint/3D Molex_PicoBlade_53261-0471_1x04-1MP_P1.25mm_Horizontal (pad pitch 1.25, pads at y=2.4, MP pads x=+-4.425) -- outline "
               "(housing 6.7 x 4.1 x 3.4, tabs to +-5.08) read off that model; Molex drawing SD-53261-... NOT read (molex.com unreachable)",
        confidence="estimated (from KiCad library model of the Molex part)",
        notes="Cavity depth/width approximated. Verify against the Molex 2D drawing before freezing keep-outs. PARTS-LOCK #14: confirm PicoBlade vs JST-GH on the first motor."),
    "lead_picoblade_plug": dict(
        title="Molex PicoBlade 51021-0400 plug + 4-wire 30 AWG motor lead (30 mm shown; NFP supplies ~200 mm)",
        material="nylon plug, PVC-insulated 30 AWG wires, tinned ends", colour="off-white / black red yellow white",
        frame="mated frame of molex_picoblade_53261_0471: plug sits in the cavity, wires leave toward -Y at z=1.85",
        source="nfpshop.com product page ('JST 1.25 mm connector + 200 mm lead', 30 AWG per mechanical/parts.md); plug outline ESTIMATED to fit the 53261 cavity",
        confidence="estimated",
        notes="Product page says JST 1.25; project assumes the PicoBlade-compatible plug (PARTS-LOCK #14 LOCK-AFTER-SAMPLE). Wire colours and plug size are placeholders until a sample is in hand."),
}

if __name__ == "__main__":
    for pt in build():
        print(pt.pid, pt.build()["size"])
