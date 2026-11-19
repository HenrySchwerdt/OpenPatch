#!/usr/bin/env python3
"""Writes assembly_sequence_v010.json: the build order of the v0.1.0 integrated pod as data for check_assembly.py (documented in ASSEMBLY.md, section v0.1.0).

  python3 mechanical/make_assembly_sequence_v010.py     (edit the step list HERE, then regenerate; the checker reads the JSON)

Conventions as in assembly_sequence.json (bench): `path` = straight segments in assembly order ending at the CAD pose, `engages` = intended overlaps, `present_offsets` = parked poses.
Design decisions that make the order feasible (all found with the checker, see V010.md):
  * the reservoir sub-assembly (reservoir + plunger + fluid module) is lowered and slid 1.2 mm toward -X over the nut of the nut gear (the nut protrudes 0.8 mm into the bore opening);
  * the drive screw (the only rod) is inserted LAST of the drive parts from the REAR through a d2.4 hole in the rear wall (it is longer than the rear zone), turned through the nut with a pin vise
    until the slot meets the plunger tab, then the hole is closed with a silicone stopper;
  * the spine FPC goes in before the reservoir (it lies under it), the dock insert before the main board (the dock hall chip hangs below the board).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
bench = json.loads((HERE / "assembly_sequence.json").read_text())


def st(id_, ctx, title, parts, path, tool, access=None, engages=None, guide="ASSEMBLY.md", **kw):
    d = {"id": id_, "context": ctx, "title": title, "guide": guide, "parts": parts, "path": [{"dir": d_, "dist": n} for d_, n in path], "tool": tool}
    if access:
        d["access"] = access
    if engages:
        d["engages"] = engages
    d.update(kw)
    return d


def pr(a, b, zone=99):
    return {"pair": [a, b], "kind": "press", "zone": zone}


FL = lambda a, b: {"pair": [a, b], "kind": "flexible"}       # noqa: E731
X, Y, Z = [1, 0, 0], [0, 1, 0], [0, 0, 1]
mX, mZ = [-1, 0, 0], [0, 0, -1]
steps = [
    st("P1", "plunger", "Front seal bead ring B (cast silicone) stretched over the core into the front groove", ["seal_b"], [(mX, 4.5)], "hand (stretch over the core)", None,
       [{"pair": ["seal_b", "plunger_core"], "kind": "stretch"}]),
    st("C1", "capsub", "O-ring 2.0 x 0.7 stretched over the spigot into the face groove of the end cap", ["cap_oring"], [(X, 3.0)], "tweezers", "tweezers",
       [pr("cap_oring", "end_cap")]),
    st("C2", "capsub", "Silicone sheet gasket laid into the 0.4 mm recess of the end cap", ["cap_gasket"], [(mZ, 3.0)], "tweezers", "tweezers", [pr("cap_gasket", "end_cap"), pr("cap_gasket", "cap_oring")]),
    st("C3", "capsub", "Septum disc d3.2 x 2 dropped into the septum pocket (open top)", ["septum"], [(mZ, 6.0)], "tweezers", "tweezers", [pr("septum", "end_cap")]),
    st("C4", "capsub", "End cap lid lowered on the lands (clamp screws follow once the module sits in the pod)", ["end_cap_lid"], [(mZ, 8.0)], "finger", None,
       [pr("end_cap_lid", "end_cap"), pr("end_cap_lid", "cap_gasket"), pr("end_cap_lid", "septum"), pr("end_cap_lid", "cap_oring")]),
    st("R1", "res_sub", "Plunger (core + front bead) pushed into the reservoir from the open dry end", ["@plunger"], [(X, 8.0)], "finger", None, [pr("seal_b", "reservoir")]),
    st("R2", "res_sub", "Fluid module (cap sandwich with O-ring) pressed onto the reservoir end: spigot into the port, O-ring on the end face", ["@capsub"], [(mX, 5.0)], "finger", None,
       [pr("end_cap", "reservoir", 2.2), pr("end_cap_lid", "reservoir", 2.2), pr("cap_oring", "reservoir")]),
    st("M1", "main", "Dry bush pressed into the bearing-block bore (reamed d3.05)", ["bush_dry2"], [(mX, 6.0)], "tweezers", "tweezers", [pr("bush_dry2", "bottom", 1.2)]),
    st("M2", "main", "FPC spine laid into the floor channel (it passes UNDER the reservoir; riser at the contact shelf)", ["spine_fpc"], [(mZ, 6.0)], "tweezers", "tweezers", [FL("spine_fpc", "bottom")]),
    st("M3", "main", "Motor (rear boss, motor, gearbox, front boss, shaft, terminal block + pins) laid into the three saddles, terminal pins facing +Y",
       ["motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins"], [(mZ, 10.0)], "tweezers", "tweezers"),
    st("M4", "main", "Gear A (z16) slid onto the motor shaft from the front and glued", ["gear_a"], [(mX, 2.0)], "tweezers", "tweezers", [pr("gear_a", "motor_shaft")]),
    st("G1", "gearpack", "Thrust sleeve (brass tube) glued into the nut gear", ["thrust_sleeve2"], [(mX, 4.0)], "tweezers", "tweezers", [pr("thrust_sleeve2", "gear_d")]),
    st("G2", "gearpack", "Diametric ring magnet pushed over the rear end of the sleeve and glued (pole direction marked)", ["ring_magnet"], [(X, 3.0)], "tweezers", "tweezers", [pr("ring_magnet", "thrust_sleeve2")]),
    st("G3", "gearpack", "M1.6 nut glued (Loctite 638) on the front face of the nut gear", ["nut"], [(mX, 3.0)], "tweezers", "tweezers", [pr("nut", "gear_d")]),
    st("M5", "main", "Nut-gear pack lowered into the bearing block, meshing with gear A", ["@gearpack"], [(mZ, 10.0)], "tweezers", "tweezers", [pr("gear_a", "gear_d")]),
    st("M6", "main", "Reservoir sub-assembly lowered and slid 1.2 mm toward -X over the nut (the nut protrudes into the bore opening)", ["@res_sub"], [(mZ, 12.0), (mX, 1.2)], "finger"),
    st("M7", "main", "Needle + hub pressed into the guard tube from the dock mouth", ["needle_hub", "needle"], [(mX, 25.0)], "tweezers", "tweezers", [pr("needle_hub", "end_cap", 0.8), pr("needle", "end_cap")]),
    st("M8", "main", "Drive screw (the only rod) inserted from the REAR through the rear-wall hole, turned through the nut with a pin vise until the slot meets the plunger tab", ["drive_screw"], [(X, 40.0)],
       "pin vise", None, [pr("drive_screw", "nut"), pr("drive_screw", "plunger_core")]),
    st("M9", "main", "Silicone stopper pressed into the rear-wall hole", ["rear_plug"], [(X, 3.0)], "tweezers", "tweezers"),
    st("M10", "main", "USB-C gasket frame laid against the inside of the rear wall", ["usb_gasket"], [(mX, 3.0)], "tweezers", "tweezers"),
    st("M11", "main", "Waterproof USB-C receptacle pushed to the rear wall (nose through the opening, flange on the gasket)", ["usb_conn"], [(mZ, 6.0), (mX, 1.0)], "finger", None, [pr("usb_conn", "usb_gasket")]),
    st("M12", "main", "USB board dropped behind the receptacle", ["usb_board"], [(mZ, 5.0)], "tweezers", "tweezers"),
    st("M13", "main", "SENSOR board with the TMAG5273 lowered onto three posts / pins beside the ring magnet", ["sensor_board", "hall_tmag"], [(mZ, 10.0)], "tweezers", "tweezers"),
    st("M14", "main", "Motor contact card (4 SMD spring contacts) lowered into its slot, springs wipe onto the motor pin tips", ["motor_card", "mspring_1", "mspring_2", "mspring_3", "mspring_4"], [(mZ, 8.0)],
       "tweezers", "tweezers", [FL("mspring_1", "motor_pins"), FL("mspring_2", "motor_pins"), FL("mspring_3", "motor_pins"), FL("mspring_4", "motor_pins")]),
    st("M15", "main", "Li-Po cell on 0.6 mm foam tape, tabs up, between the two bay ribs", ["bat_foam", "battery", "bat_pad_p", "bat_pad_n"], [(mZ, 8.0)], "tweezers", "tweezers"),
    st("M16", "main", "Dock insert slid into the dock window from the +X mouth until the detents click (before the board: the dock hall chip hangs below it)", ["dock_insert"], [(mX, 20.0)], "finger", None,
       [pr("dock_insert", "bottom", 1.5), FL("dock_insert", "bottom")]),
    st("M17", "main", "MAIN board (radio, button, dock hall, 2 cell springs, 8 spine springs) lowered onto the pins", ["pod_board", "radio", "switch", "hall_dock", "spring_p", "spring_n", "spine_springs"], [(mZ, 10.0)],
       "tweezers", "tweezers"),
    st("M18", "main", "Main gasket laid on the wall top", ["gasket"], [(mZ, 6.0)], "tweezers", "tweezers"),
    st("L1", "lidpack", "Piezo glued to the lid inner face (ePTFE vent disc and PU film glued into their recesses)", ["piezo"], [(Z, 6.0)], "tweezers", "tweezers"),
    st("M19", "main", "Clear lid with piezo lowered straight down", ["@lidpack"], [(mZ, 10.0)], "finger"),
    st("A1", "adapter", "Dock magnet d2 x 1 glued into the rear lug pocket of the dummy head", ["dock_magnet"], [(mZ, 5.0)], "tweezers", "tweezers"),
    st("D1", "main", "Dock: dummy head pushed into the pod mouth, snap arms spread and latch behind the dome", ["@adapter"], [(mX, 16.0)], "finger", None,
       [{"pair": ["cannula_adapter", "dock_insert"], "kind": "snap", "flex": {"axis": "Y", "centre": "L['dock']['y_c']"}, "material": "SLA_TOUGH"}, pr("needle", "cannula_adapter")]),
]


def fit(id_, name, kind, step, hole_proc, shaft_proc, at, hole, shaft, rx, **kw):
    d = {"id": id_, "name": name, "kind": kind, "step": step, "hole_proc": hole_proc, "shaft_proc": shaft_proc, "at": at, "hole": hole, "shaft": shaft, "guide_regex": rx}
    d.update(kw)
    return d


def F(p, a, f):
    return f"F('{p}','{a}',{f})"


ctr = lambda p: [F(p, "X", 0.5), F(p, "Y", 0.5), F(p, "Z", 0.5)]      # noqa: E731
fits = [
    {"_comment": "Mating pairs of the v0.1.0 pod, measured on the CAD mesh and run through the vendor tolerance scenarios (JLC3DP SLA +-0.2, MJF +-0.3, holes shrink). A pair that fails as printed needs a documented post-process (guide_regex = text in mechanical/ASSEMBLY.md)."},
    fit("F01", "dry bush OD3.0 in the bearing-block bore (printed, MJF)", "transition", "M1", "MJF", "purchased:bush_od", ctr("bush_dry2"),
        {"part": "bottom", "normal": "X", "dir": "Z"}, {"part": "bush_dry2", "normal": "X", "dir": "Z", "expect": "outer"}, "ream the bush bore.{0,60}3\\.05",
        post_tight="ream the bore with a 3.05 mm drill by hand", post_loose="one drop of CA on the bush OD"),
    fit("F02", "plunger core height 4.5 in the CNC PP bore 4.7 (sliding)", "float", "R1", "CNC_PP", "SLA", [F("plunger_core", "X", 0.55), "L['y_r']", "L['z_axis']"],
        {"part": "reservoir", "normal": "X", "dir": "Z"}, {"part": "plunger_core", "normal": "X", "dir": "Z", "expect": "outer"}, "sand the plunger core.{0,80}1500",
        post_tight="sand the core flanges with 1500 grit on a flat stick"),
    fit("F03", "plunger core width 25.5 in the CNC PP bore 25.7 (sliding)", "float", "R1", "CNC_PP", "SLA", [F("plunger_core", "X", 0.55), "L['y_r']", "L['z_axis']"],
        {"part": "reservoir", "normal": "X", "dir": "Y"}, {"part": "plunger_core", "normal": "X", "dir": "Y", "expect": "outer"}, "sand the plunger core.{0,80}1500",
        post_tight="sand the core flanges with 1500 grit on a flat stick"),
    fit("F04", "end-cap spigot d1.98 in the CNC port d2.0 H7 (locating, transition)", "transition", "R2", "CNC_PP", "SLA", ["L['x_r1']-0.9", "L['port_y']", "L['z_axis']-0.4"],
        {"part": "reservoir", "normal": "X", "dir": "Y"}, {"part": "end_cap", "normal": "X", "dir": "Y", "expect": "outer"}, "sand the spigot.{0,80}1\\.95",
        post_tight="sand the spigot to d1.95 (1500 grit, rotate in a drill)", post_loose="the O-ring seals; a drop of UV adhesive locates the cap", ds_override=1.98, dh_override=2.0),
    fit("F05", "needle hub d2.0 (PTFE) in the cap hub seat d2.0 (press)", "press", "M7", "SLA", "purchased:ptfe", ctr("needle_hub"),
        {"part": "end_cap", "normal": "X", "dir": "Y"}, {"part": "needle_hub", "normal": "X", "dir": "Y", "expect": "outer"}, "ream the hub seat.{0,60}2\\.0",
        window=[-0.12, -0.01], post_tight="ream the seat with a 2.0 mm drill", post_loose="UV adhesive drop (water test only)"),
    fit("F06", "thrust sleeve OD2.0 (brass) in the nut-gear bore 2.04 (glued)", "glued", "G1", "purchased:gear_bore", "purchased:brass_tube", ["F('gear_d','X',0.5)", "L['y_r']", "L['z_axis']"],
        {"part": "gear_d", "normal": "X", "dir": "Y"}, {"part": "thrust_sleeve2", "normal": "X", "dir": "Y", "expect": "outer"}, "Loctite 638", window=[-0.02, 0.15]),
    fit("F07", "gear A bore 2.04 on the motor shaft d2.0 (glued)", "glued", "M4", "purchased:gear_bore", "purchased:steel_rod", ["F('gear_a','X',0.5)", "F('motor_shaft','Y',0.5)", "F('motor_shaft','Z',0.5)"],
        {"part": "gear_a", "normal": "X", "dir": "Y"}, {"part": "motor_shaft", "normal": "X", "dir": "Y", "expect": "outer"}, "Loctite 638", window=[-0.02, 0.15]),
    fit("F08", "M1.6 screw in the brass thrust sleeve ID 1.7 (running)", "running", "M8", "purchased:brass_tube", "purchased:steel_rod", ctr("thrust_sleeve2"),
        {"part": "thrust_sleeve2", "normal": "X", "dir": "Y"}, {"part": "drive_screw", "normal": "X", "dir": "Y", "expect": "outer"}, "brass tube"),
    fit("F09", "M1.6 screw in the dry bush ID 1.7 (running)", "running", "M8", "purchased:ptfe", "purchased:steel_rod", ctr("bush_dry2"),
        {"part": "bush_dry2", "normal": "X", "dir": "Y"}, {"part": "drive_screw", "normal": "X", "dir": "Y", "expect": "outer"}, "brass tube"),
    fit("F10", "ring magnet ID 2.0 on the sleeve OD 2.0 (glued)", "glued", "G2", "purchased:magnet", "purchased:brass_tube", ctr("ring_magnet"),
        {"part": "ring_magnet", "normal": "X", "dir": "Y"}, {"part": "thrust_sleeve2", "normal": "X", "dir": "Y", "expect": "outer"}, "Loctite 638", window=[-0.02, 0.15]),
    fit("F11", "dock magnet d2.0 in the adapter lug pocket d2.1 (glued)", "glued", "A1", "SLA", "purchased:magnet", ctr("dock_magnet"),
        {"part": "cannula_adapter", "normal": "Z", "dir": "X"}, {"part": "dock_magnet", "normal": "Z", "dir": "X", "expect": "outer"}, "open the magnet pocket.{0,60}2\\.1",
        window=[0.0, 0.2], post_tight="open the pocket with a 2.1 mm drill", post_loose="CA drop"),
    fit("F12", "M1.2 lid screw in the lid clearance hole d1.4 (clear SLA)", "clearance", "M19", "SLA", "fixed:0.04", ["L['screws'][0]['x']", "L['screws'][0]['y']", "7.0"],
        {"part": "top", "normal": "Z", "dir": "X"}, {"d": 1.2}, "drill the lid screw holes.{0,60}1\\.4", window=[0.10, 0.60], post_tight="drill d1.4 by hand"),
    fit("F13", "M1.2 thread-forming screw pilot d1.0 in the bottom dome (MJF)", "pilot", "M19", "MJF", None, ["L['screws'][0]['x']", "L['screws'][0]['y']", "3"],
        {"part": "bottom"}, None, "drill the pilots.{0,60}1\\.0", z_scan=[2, 3, 4, 5], post_tight="drill d1.0 by hand", post_loose="use a drop of CA in the pilot"),
    fit("F14", "MAIN board locating pin d1.0 (printed, MJF) in the PCB hole d1.2", "running", "M17", "fixed:0.1", "MJF", ["L['x_r1']+L['geo']['board_holes_u'][0][0]", "L['geo']['board_holes_u'][0][1]", "L['geo']['z0']+0.3"],
        {"part": "pod_board", "normal": "Z", "dir": "X"}, {"part": "bottom", "normal": "Z", "dir": "X"}, "file the pins", post_tight="file the pin / drill the PCB hole 1.2"),
]
for f in fits:           # fits without a shaft part (pilot) keep None
    if "id" not in f:
        continue
    if f.get("shaft") is None:
        f.pop("shaft", None)
    if f.get("shaft_proc") is None:
        f.pop("shaft_proc", None)

lid_screws = [{"id": f"S-lid-{i + 1}", "after": "M19", "kind": "M1.2", "source": "mech", "index": i, "title": f"lid screw {i + 1}"} for i in range(6)]
cap_screws = [{"id": f"S-cap-{k + 1}", "after": "M16", "kind": "M1.2", "source": "xy", "xy": [f"L['x_r1']+P['dock']['cap']['sandwich']['screws']['pos'][{k}][0]", f"L['dock']['y_c']+P['dock']['cap']['sandwich']['screws']['pos'][{k}][1]"],
              "title": f"fluid sandwich clamp screw {k + 1}"} for k in range(1)]

doc = {
    "_comment": "Assembly order of the v0.1.0 integrated pod (water only, never on a person) as data, GENERATED by make_assembly_sequence_v010.py (see its docstring) from the ASSEMBLY.md v0.1.0 build order. Read by check_assembly.py (out/v010).",
    "tools": bench["tools"],
    "contexts": {"main": {"base": ["bottom"]}, "plunger": {"base": ["plunger_core"]}, "res_sub": {"base": ["reservoir"]}, "capsub": {"base": ["end_cap"]}, "gearpack": {"base": ["gear_d"]},
                 "lidpack": {"base": ["top"]}, "adapter": {"base": ["cannula_adapter"]}},
    "steps": steps,
    "fits": fits,
    "proposals": [],
    "fix_hints": {},
    "fix_general": [
        "**Vendor tolerances.** Every printed fit is judged with JLC3DP's numbers (SLA +-0.2 mm, MJF +-0.3 mm, holes shrink). Fits that cannot be held as printed are post-processed (reamed / drilled / sanded) and the step is written into ASSEMBLY.md."],
    "screws": cap_screws + lid_screws,
}
(HERE / "assembly_sequence_v010.json").write_text(json.dumps(doc, indent=1))
print("assembly_sequence_v010.json:", len(steps), "steps,", len(fits) - 1, "fits,", len(doc["screws"]), "screw positions")
