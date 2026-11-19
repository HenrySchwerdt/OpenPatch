# exec'd by build_v3.py (globals: pcbnew, bl, Board, MM, T, ROOT, HERE, name, write_project)
W = float(os.environ.get("OP_W", 20.0)); H = float(os.environ.get("OP_H", 20.0))
LAYERS = 6
ISP_XY = (4.8, 4.6)                 # module centre; rotated 180 deg: antenna half (local +Y) points to the top edge
ANT_KEEPOUT = (0.0, 0.0, 9.7, 4.5)  # no copper on any layer (datasheet: antenna half of the module)
POWERNETS = ("VBAT", "3V3", "VMOT", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2")
OUTDIR = os.path.join(HERE, name); os.makedirs(OUTDIR, exist_ok=True)
PCB = os.path.join(OUTDIR, name + ".kicad_pcb")

# explicit placements: ref -> (x, y, rot, side)   (board frame, y down, viewed from the top)
FIXED = {
    "U1": (ISP_XY[0], ISP_XY[1], 180, "F"),
    "U30": (4.3, 12.4, 0, "F"), "U31": (8.6, 11.6, 0, "F"),
    "U7": (13.2, 13.0, 0, "F"), "U2": (6.6, 17.0, 0, "F"),
    "Q7": (10.6, 17.2, 0, "F"), "Q7B": (13.6, 17.2, 0, "F"),
    "SP1": (2.2, 7.6, 90, "B"), "SP2": (2.2, 11.8, 90, "B"),
    "MP1": (17.8, 2.6, 90, "B"), "MP2": (17.8, 6.8, 90, "B"), "MP3": (17.8, 11.0, 90, "B"), "MP4": (17.8, 15.2, 90, "B"),
    "J7": (10.0, 17.55, 0, "B"), "J3": (10.0, 13.6, 0, "B"),
}
# test / SWD pads on a grid in the top-right region
GRID = [(10.5 + 1.3 * c, 1.1 + 1.3 * r) for r in range(3) for c in range(7)]
SNAP = [  # (ref, anchor ref, anchor pad)
    ("C1", "U1", 26), ("C2", "U1", 26), ("R1", "U1", 13),
    ("C50", "U30", 4), ("C51", "U30", 4), ("R80", "U30", 6), ("R81", "U30", 11), ("C52", "U31", 5), ("R43", "U31", 1),
    ("R34", "U7", 4), ("R35", "U7", 9), ("C23", "U7", 6), ("C22", "U7", 6), ("C21", "U7", 6),
    ("C19", "U7", 11), ("R37", "U7", 11), ("R38", "U7", 11), ("R36", "U7", 12), ("R39", "U7", 14), ("R40", "U7", 13), ("C20", "U7", 13),
    ("C6", "U2", 3), ("C7", "U2", 2),
    ("R19", "Q7", 1), ("R20", "Q7B", 1), ("R21", "Q7", 3),
    ("R67", "U1", 41), ("R68", "U1", 39), ("R73", "U1", 37),
    ("LD1", "U1", 53), ("R74", "LD1", 2), ("R75", "LD1", 1),
]


def isp_fanout(b, fps):
    """via-in-pad (0.4/0.2, filled + capped) on every connected module pad that cannot escape on L1"""
    u1 = fps["U1"]; n = 0
    outer = {1, 7, 25, 31, 2, 4, 6, 26, 28, 30} | set(range(32, 49, 2))
    for pd in u1.Pads():
        num = int(pd.GetNumber())
        net = pd.GetNet()
        if not net or net.GetNetname() in ("", "RF_BRIDGE") or num in outer or num > 64:
            continue
        v = pcbnew.PCB_VIA(b.b)
        v.SetPosition(pd.GetPosition()); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(MM(0.40)); v.SetDrill(MM(0.20))
        b.b.Add(v); n += 1
    return n


def rf_bridge(b, fps):
    """copper bridge pad 20 - pad 22 of the module (datasheet: connect OUT_ANT to OUT_MOD for the internal antenna) over the 0.25 mm gap"""
    u1 = fps["U1"]
    p = {pd.GetNumber(): pd for pd in u1.Pads()}
    t = pcbnew.PCB_TRACK(b.b)
    t.SetStart(p["20"].GetPosition()); t.SetEnd(p["22"].GetPosition()); t.SetLayer(pcbnew.F_Cu); t.SetWidth(MM(0.30)); t.SetNet(b.net("RF_BRIDGE"))
    b.b.Add(t)


def main():
    parts = json.load(open(os.path.join(ROOT, "netlist_v3_main.json")))
    b = Board(name, W, H, layers=LAYERS, corner=1.0)
    b.b.GetDesignSettings().SetBoardThickness(MM(0.8))
    b.rounded_outline()
    gi = 0
    for p in parts:
        ref = p["ref"]
        side = p["side"]
        if ref in FIXED:
            x, y, rot, side = FIXED[ref]
        elif ref.startswith(("J1", "TP")) and p["group"] in ("swd", "tp"):
            x, y = GRID[gi]; gi += 1; rot = 0
        else:
            x, y, rot = W / 2, H / 2, 0
        b.add(ref, p["value"], tuple(p["fp"]), x, y, rot, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"], bom=p["bom"], note=p["note"], hide_ref=True)
        b.parts[ref]["dnp"] = p["dnp"]; b.parts[ref]["group"] = p["group"]; b.parts[ref]["board"] = "MAIN"
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    # keepout (all copper layers, tracks/vias/pours) for the antenna half
    a = ANT_KEEPOUT
    z = pcbnew.ZONE(b.b); z.SetIsRuleArea(True); z.SetZoneName("ANT_KEEPOUT")
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    ch = z.Outline(); ch.NewOutline()
    for x, y in ((a[0], a[1]), (a[2], a[1]), (a[2], a[3]), (a[0], a[3])):
        ch.Append(MM(bl.OX + x), MM(bl.OY + y))
    b.b.Add(z)
    bl.snap(b, SNAP, rmax=6.0, step=0.1, margin=0.10, edge=0.45, keepout=[[a[0], a[1], a[2] + 0.2, a[3] + 0.2]])
    print("fanout vias:", isp_fanout(b, fps))
    rf_bridge(b, fps)
    b.text("TEST ONLY - NOT FOR HUMAN USE", 10.2, 19.2, 0.5, thick=0.08)
    b.rules(power_nets=POWERNETS, power_w=0.25, track=0.12)
    d = b.b.GetDesignSettings()
    d.m_CopperEdgeClearance = MM(0.25); d.m_MinThroughDrill = MM(0.2); d.m_ViasMinSize = MM(0.4); d.m_HoleToHoleMin = MM(0.2); d.m_TrackMinWidth = MM(0.1)
    for f in b.b.GetFootprints():
        f.Reference().SetVisible(False)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(OUTDIR, "parts.json"), "w"), indent=1)
    write_project(os.path.join(OUTDIR, name + ".kicad_pro"), POWERNETS, 0.25, track=0.12, edge=0.25, clear=0.10)
    pj = os.path.join(OUTDIR, name + ".kicad_pro"); dd = json.load(open(pj)); r = dd["board"]["design_settings"]["rules"]
    r.update(min_through_hole_diameter=0.2, min_via_diameter=0.4, min_track_width=0.1, min_hole_to_hole=0.2, min_hole_clearance=0.2, min_via_annular_width=0.1)
    json.dump(dd, open(pj, "w"), indent=2)
    print(name, "written", len(b.parts), "parts", W, "x", H)


main()
