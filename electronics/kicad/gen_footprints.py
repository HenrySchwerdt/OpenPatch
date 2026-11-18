#!/usr/bin/env python3
"""Generate OpenPatch.pretty custom footprints (run with KiCad's bundled python3).

ISP1807: exact pad geometry from the Insight SiP official Eagle library
(datasheets/isp/eagle/ISP1807LR_Int.lbr, ISP1807-LR package) cross-checked with
the datasheet drawing (isp_ble_DS1807 R19, sec. 4.1: 0.4x0.4 pads, 0.8x0.8 corner pads).
Everything else derived from KiCad library footprints or provisional (flagged).
"""
import os, re, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "OpenPatch.pretty")
EAGLE = os.path.join(HERE, "..", "datasheets", "isp", "eagle", "ISP1807LR_Int.lbr")
os.makedirs(OUT, exist_ok=True)


def hdr(name, descr, tags="openpatch"):
    return (f'(footprint "{name}"\n\t(version 20260206)\n\t(generator "openpatch-gen")\n'
            f'\t(layer "F.Cu")\n\t(descr "{descr}")\n\t(tags "{tags}")\n'
            f'\t(property "Reference" "REF**" (at 0 -5.2 0) (layer "F.SilkS") '
            f'(effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            f'\t(property "Value" "{name}" (at 0 5.2 0) (layer "F.Fab") '
            f'(effects (font (size 0.8 0.8) (thickness 0.12))))\n\t(attr smd)\n')


def pad(num, x, y, w, h, shape="rect", layers='"F.Cu" "F.Mask" "F.Paste"', extra=""):
    return (f'\t(pad "{num}" smd {shape} (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f}) '
            f'(layers {layers}){extra})\n')


def rect(x0, y0, x1, y1, layer, w=0.05):
    return (f'\t(fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
            f'(stroke (width {w}) (type solid)) (fill no) (layer "{layer}"))\n')


def isp1807():
    root = ET.parse(EAGLE).getroot()
    pkg = [p for p in root.iter("package") if p.get("name") == "ISP1807-LR"][0]
    s = hdr("ISP1807",
            "Insight SiP ISP1807-LR LGA-78 8x8x1.0 mm. Pads from official Insight Eagle lib "
            "(DS1807 R19 4.1). Antenna half = +Y local (pads 65-78 NC are mechanical). "
            "Antenna keep-out added at board level.", "isp1807 lga module")
    pads = []
    for e in pkg.iter("smd"):
        n = e.get("name"); x = float(e.get("x")) - 4.0; y = -float(e.get("y")) - 4.0
        w = float(e.get("dx")); h = float(e.get("dy"))
        pads.append((int(n), x, y, round(w, 3), round(h, 3)))
    assert len(pads) == 78, len(pads)
    for n, x, y, w, h in sorted(pads):
        s += pad(n, x, y, w, h)
    s += rect(-4, -4, 4, 4, "F.Fab", 0.1)
    s += rect(-4.1, -4.1, 4.1, 4.1, "F.SilkS", 0.12)
    s += '\t(fp_circle (center -3.4 -3.4) (end -3.2 -3.4) (stroke (width 0.1) (type solid)) (fill yes) (layer "F.SilkS"))\n'
    s += rect(-4.25, -4.25, 4.25, 4.25, "F.CrtYd")
    s += ")\n"
    open(os.path.join(OUT, "ISP1807.kicad_mod"), "w").write(s)
    return len(pads)


def pad_pair(name, descr, pads, courtyard):
    s = hdr(name, descr)
    for n, x, y, w, h in pads:
        s += pad(n, x, y, w, h, extra=" (solder_mask_margin 0.0)")
    x0, y0, x1, y1 = courtyard
    s += rect(x0, y0, x1, y1, "F.CrtYd") + ")\n"
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(s)


def fh12_4s():
    """Derive FH12-4S-0.5SH from the KiCad FH12-10S footprint (same family).
    Signal pads re-centred, mounting-tab pads moved inwards by (10-4)*0.25 mm."""
    src = ("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Connector_FFC-FPC.pretty/"
           "Hirose_FH12-10S-0.5SH_1x10-1MP_P0.50mm_Horizontal.kicad_mod")
    t = open(src).read()
    t = t.replace("Hirose_FH12-10S-0.5SH_1x10-1MP_P0.50mm_Horizontal", "Hirose_FH12-4S-0.5SH_derived")
    t = t.replace("(layer \"F.Cu\")", "(layer \"F.Cu\")", 1)
    # drop pads 5..10 and shift pads 1..4 / MP
    out, i = [], 0
    blocks = re.split(r"(?=\n\t\(pad )", t)
    head = blocks[0]; rest = blocks[1:]
    new = [head]
    for b in rest:
        m = re.match(r"\n\t\(pad \"([^\"]*)\"", b)
        num = m.group(1)
        tail = ""
        # pad block ends where next top-level element starts; keep as is
        if num.isdigit():
            k = int(num)
            if k > 4:
                # keep any trailing non-pad content after the pad block
                tail = re.split(r"\n\t\)\n", b, maxsplit=1)
                continue_tail = tail[1] if len(tail) > 1 else ""
                new.append("\n" + continue_tail if continue_tail.strip() else "")
                continue
            # shift x by +2.25 so that pads 1..4 are centred (orig centre of 1..10 is 0)
            b = re.sub(r"\(at (-?[\d.]+) (-?[\d.]+)", lambda mm: f"(at {float(mm.group(1)) + 1.5:.3f} {mm.group(2)}", b, count=1)
        else:  # mounting tab pads
            def shift(mm):
                x = float(mm.group(1)); x = x - 1.5 if x > 0 else x + 1.5
                return f"(at {x:.3f} {mm.group(2)}"
            b = re.sub(r"\(at (-?[\d.]+) (-?[\d.]+)", shift, b, count=1)
        new.append(b)
    open(os.path.join(OUT, "Hirose_FH12-4S-0.5SH_derived.kicad_mod"), "w").write("".join(new))


if __name__ == "__main__":
    print("ISP1807 pads:", isp1807())
    # Battery spring-contact lands (positions from mechanical layout.json contacts.battery_tabs; pad 1.5x1.2).
    pad_pair("Contact_Pads_Battery_2x_1.5x1.2",
             "2 ENIG lands for SMD spring contacts pressing on cell tabs; pitch 1.9 mm. PROVISIONAL: contact part not selected.",
             [(1, 0, -0.95, 1.5, 1.2), (2, 0, 0.95, 1.5, 1.2)], (-1.1, -1.8, 1.1, 1.8))
    pad_pair("Contact_Pads_Coil_2x_1.5x1.2",
             "2 ENIG lands for coil spring contacts (coil is a separate part above the PCB). PROVISIONAL.",
             [(1, -1.2, 0, 1.5, 1.2), (2, 1.2, 0, 1.5, 1.2)], (-2.1, -0.9, 2.1, 0.9))
    fh12_4s()
    print("done")
