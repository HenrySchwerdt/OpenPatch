# exec'd by build_v3.py (globals: pcbnew, bl, Board, MM, T, ROOT, HERE, name, write_project)
W = float(os.environ.get("OP_W", 22.0)); H = float(os.environ.get("OP_H", 26.0))
LAYERS = int(os.environ.get("OP_LAYERS", 4))
OUTDIR = os.path.join(HERE, name); os.makedirs(OUTDIR, exist_ok=True)
PCB = os.path.join(OUTDIR, name + ".kicad_pcb")
POWERNETS = ("VBAT", "3V3", "VMOT", "VMOT_RAW", "VMOT_A", "VMOT_PRE", "VBUS_P", "VBUS_R", "BST_SW")
FIXED = {"JU1": (11.0, 4.5, 0, "F"), "J7P": (11.0, 22.0, 0, "F"), "PZ1": (2.4, 13.0, 90, "F"), "PZ2": (19.6, 13.0, 90, "F"),
         "SW1": (11.0, 9.5, 0, "F"), "H1": (1.5, 1.5, 0, "F"), "H2": (20.5, 1.5, 0, "F"), "H3": (1.5, 24.5, 0, "F")}
CFG = dict(anchors={"usb": (11, 8), "pwr": (14, 17), "chg": (17, 11), "sense": (6, 17), "sw": (11, 15), "dock": (11, 14), "oc": (6, 11), "ui": (11, 17), "boost": (17, 17),
                    "tp": (11, 12), "b2b": (11, 22), "mech": (1, 1), "sup": (11, 12), "mot": (11, 12)})
Y = lambda by: H - by
exec(open(os.path.join(HERE, "placelib_v3.py")).read())


def main():
    parts = json.load(open(os.path.join(ROOT, "netlist_v3_power.json")))
    b = Board(name, W, H, layers=LAYERS, corner=1.5)
    b.b.GetDesignSettings().SetBoardThickness(MM(0.8))
    b.rounded_outline()
    for p in parts:
        ref = p["ref"]; side = p["side"]
        if ref in FIXED:
            x, y, rot, side = FIXED[ref]; y = Y(y)
        else:
            x, y = CFG["anchors"].get(p["group"], (W / 2, H / 2)); y = Y(y); rot = 0
        b.add(ref, p["value"], tuple(p["fp"]), x, y, rot, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"], bom=p["bom"], note=p["note"], hide_ref=True)
        b.parts[ref]["dnp"] = p["dnp"]; b.parts[ref]["group"] = p["group"]; b.parts[ref]["board"] = "POWER"
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    fixed = set(FIXED)
    # board-to-board rows must not be crowded: keep the pad-row courtyard free on the back side too
    quad_place(b, fps, parts, fixed)
    legalize2(b, fps, fixed, [])
    b.text("TEST ONLY - NOT FOR HUMAN USE", 1.0, Y(0.8), 0.6, thick=0.1)
    b.rules(power_nets=POWERNETS, power_w=0.3, track=0.15)
    d = b.b.GetDesignSettings()
    d.m_CopperEdgeClearance = MM(0.25); d.m_MinThroughDrill = MM(0.2); d.m_ViasMinSize = MM(0.4); d.m_HoleToHoleMin = MM(0.2); d.m_TrackMinWidth = MM(0.1)
    for f in b.b.GetFootprints():
        f.Reference().SetVisible(False)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(OUTDIR, "parts.json"), "w"), indent=1)
    write_project(os.path.join(OUTDIR, name + ".kicad_pro"), POWERNETS, 0.3, track=0.15, edge=0.25, clear=0.10)
    pj = os.path.join(OUTDIR, name + ".kicad_pro"); dd = json.load(open(pj)); r = dd["board"]["design_settings"]["rules"]
    r.update(min_through_hole_diameter=0.2, min_via_diameter=0.4, min_track_width=0.1, min_hole_to_hole=0.2, min_hole_clearance=0.2, min_via_annular_width=0.1)
    json.dump(dd, open(pj, "w"), indent=2)
    print(name, "written", len(b.parts), "parts", W, "x", H, "layers", LAYERS)


main()
