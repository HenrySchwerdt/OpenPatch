#!/usr/bin/env python3
"""Route the board: project rules -> DSN -> Freerouting -> SES import -> pours -> save.

usage: python3 route.py prep|import   (run with KiCad's python3; `route.sh` wraps all steps)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "openpatch-op100.kicad_pcb")
PRO = os.path.join(HERE, "openpatch-op100.kicad_pro")
DSN = os.path.join(HERE, "route", "op100.dsn")
SES = os.path.join(HERE, "route", "op100_224.ses")
FROM = pcbnew.FromMM

# JLCPCB 4-layer capability (research.md): 0.09 mm track/space min, via 0.2/0.4 (epoxy-filled+capped for via-in-pad)
TRACK, CLEAR, VIA_D, VIA_H = 0.1, 0.1, 0.4, 0.2


def write_project() -> None:
    pro = {
        "meta": {"filename": "openpatch-op100.kicad_pro", "version": 3},
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.1, "silk_line_width": 0.1,
                         "silk_text_size_h": 0.6, "silk_text_size_v": 0.6, "silk_text_thickness": 0.1},
            "rules": {"min_clearance": CLEAR, "min_copper_edge_clearance": 0.2, "min_hole_clearance": 0.15,
                      "min_hole_to_hole": 0.25, "min_through_hole_diameter": VIA_H, "min_track_width": TRACK,
                      "min_via_annular_width": 0.1, "min_via_diameter": VIA_D - 0.05,
                      "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                      "min_silk_clearance": 0.0, "min_text_height": 0.5, "min_text_thickness": 0.08,
                      "min_connection_width": 0.1, "min_resolved_spokes": 2, "min_splitting_width": 0.1,
                      "solder_mask_min_width": 0.1, "solder_mask_to_copper_clearance": 0.0},
            "rule_severities": {"silk_over_copper": "ignore", "silk_overlap": "ignore", "silk_edge_clearance": "ignore",
                                "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                                "footprint_symbol_mismatch": "ignore", "solder_mask_bridge": "warning",
                                "courtyards_overlap": "warning"},
        }},
        "net_settings": {"classes": [{"name": "Default", "clearance": CLEAR, "track_width": TRACK,
                                      "via_diameter": VIA_D, "via_drill": VIA_H, "microvia_diameter": 0.3,
                                      "microvia_drill": 0.1, "diff_pair_width": 0.1, "diff_pair_gap": 0.1,
                                      "diff_pair_via_gap": 0.25, "priority": 2147483647, "pcb_color": "rgba(0,0,0,0.000)",
                                      "schematic_color": "rgba(0,0,0,0.000)", "wire_width": 6, "bus_width": 12,
                                      "line_style": 0}],
                         "meta": {"version": 4}, "net_colors": None, "netclass_assignments": None,
                         "netclass_patterns": []},
    }
    json.dump(pro, open(PRO, "w"), indent=2)


def add_plane(board, name: str, layer: int, net: str, inset: float = 0.15) -> None:
    sys.path.insert(0, HERE)
    import build_board as bb
    pts = bb.outline_pts()
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    z.SetZoneName(name)
    z.SetMinThickness(FROM(0.1))
    z.SetLocalClearance(FROM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FROM(0.15)); z.SetThermalReliefSpokeWidth(FROM(0.15))
    ch = z.Outline(); ch.NewOutline()
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    for x, y in pts:
        ch.Append(FROM(x), FROM(-y))
    z.SetIsFilled(False)
    board.Add(z)


def prep() -> None:
    os.makedirs(os.path.join(HERE, "route"), exist_ok=True)
    write_project()
    board = pcbnew.LoadBoard(PCB)
    for z in list(board.Zones()):
        if not z.GetIsRuleArea():
            board.Remove(z)
    add_plane(board, "GND_L2", pcbnew.In1_Cu, "GND")
    pcbnew.SaveBoard(PCB, board)
    pcbnew.ExportSpecctraDSN(board, DSN)
    print("DSN written", DSN)


def import_ses() -> None:
    board = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ImportSpecctraSES(board, SES)
    print("SES import", ok)
    pcbnew.SaveBoard(PCB, board)


def finish() -> None:
    """GND pours on F.Cu/B.Cu/In2.Cu (fill around routing), fill all zones, save."""
    board = pcbnew.LoadBoard(PCB)
    for name, layer in (("GND_F", pcbnew.F_Cu), ("GND_B", pcbnew.B_Cu), ("GND_L3", pcbnew.In2_Cu)):
        add_plane(board, name, layer, "GND")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("zones filled")


if __name__ == "__main__":
    {"prep": prep, "import": import_ses, "finish": finish}[sys.argv[1]]()
