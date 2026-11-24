#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Cart board outline for electronics: one common board for variants A and B (same chip set as the cup board, new outline).

Writes out/v010-cart/board/: cart_board_outline.kicad_pcb (Edge.Cuts + keep-outs / markers on User layers), cart_board_interface.json,
cart_board_outline.svg (kicad-cli export). Board frame: origin = west-south corner, +x = pump +X (toward the cartridge cap end),
+y = pump +Y (north edge = USB-C wall side), z up = pump +Z. TEST PROJECT, water only.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import op_cart
from op_layout import HERE, load_params

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def interface(p0: dict) -> dict:
    Ls = {v: op_cart.geometry(op_cart.prepare(p0, v)) for v in ("A", "B")}
    c = op_cart.prepare(p0, "A")["cart"]
    bd, usb, bt, bs = c["board"], c["usb"], c["button"], c["board_ledge_d"]
    l, w = bd["l"], bd["w"]
    pads = []
    for v, L in Ls.items():
        x0, y0 = L["board"]["x"][0], L["board"]["y"][0]
        pads.append({v: [[round(x - x0, 3), round(y - y0, 3), d] for x, y, d in op_cart.board_ledges(op_cart.prepare(p0, v), L)]})
    rx, ry = op_cart.board_lid_rib(Ls["A"])
    xa, ya = Ls["A"]["board"]["x"][0], Ls["A"]["board"]["y"][0]
    gap = c["board_wall_clr"]
    return {
        "_comment": "cart board (variants A and B share it). Frame: origin west-south corner, +x toward the cartridge cap end, +y = north edge (USB-C wall). "
                    "Same chip set as electronics/v010/cup (HJ-840, STM32C011, TPL5010, TPS2553, TPS61023, 2 x DRV8838, MCP73832, USB-C, RGB LED, sounder, side button, "
                    "TMAG5273 strip); no dock hall on the board (adapter-lock DRV5032 on a 3-wire pigtail). Interlock unchanged (INTERLOCK.md).",
        "outline_mm": [l, w], "thickness_mm": bd["t"], "layers_target": 4, "corner_r": 0.5,
        "parts_height_max_mm": {"top": bd["top_parts"], "bottom": bd["bottom_parts"]},
        "usb_c": {"part": "TYPE-C-31-M-14 mid-mount (C223907), as the cup board", "centre_x": round(l - usb["x_from_board_east"], 3), "edge": "north",
                  "mouth_beyond_edge": gap, "notch_outer": {"w": usb["open_w"], "depth": round(6.4 - gap, 3)}, "notch_inner": {"w": 6.6, "depth": round(7.05 - gap, 3)},
                  "note": "receptacle mouth flush with the housing wall inner face, which is board_wall_clr beyond the north edge (cup notch geometry kept relative to the mouth)"},
        "button_sw1": {"part": "SKSCLAE010 side switch (cup BOM) on the BOTTOM face", "x": round(l - bt["x_from_board_east"], 3), "edge": "north",
                       "actuator": "+y, tip at the north edge", "centre_below_pcb_bottom": bt["below_pcb"]},
        "support_pads_part_free_both_faces": {"d": round(bs + 0.6, 2), "xy_A": pads[0]["A"], "xy_B": pads[1]["B"]},
        "lid_rib_pad_top_face": {"x": [round(rx[0] - xa - 0.3, 3), round(rx[1] - xa + 0.3, 3)], "y": [round(ry[0] - ya - 0.3, 3), round(ry[1] - ya + 0.3, 3)]},
        "antenna_zone": {"x": [round(l - 3.0, 3), l], "y": [0, w], "rule": "HJ-840 antenna end at the EAST end, no copper on any layer, no parts (VERIFY against the HJ-840 footprint)"},
        "wire_pads_west_end": {"x": [0.3, 4.0], "note": "motor 4 + cell 2 + TMAG strip + lock-hall pigtail soldered at the west end (spec 1a exception, as the cup pod)"},
        "per_variant": {v: {"pump_frame_origin": [round(L["board"]["x"][0], 3), round(L["board"]["y"][0], 3), round(L["board"]["pcb_z"][0], 3)],
                            "east_edge_max_x": L["board_x1_max"], "under_board": "motor + pinion + TMAG strip (rear), cell (front)" if v == "B" else
                            "cell (front); motor / TMAG strip are beside the board (wired)"} for v, L in Ls.items()},
    }


def kicad_pcb(I: dict) -> str:
    l, w = I["outline_mm"]
    u = I["usb_c"]
    xo, wo, do_ = u["centre_x"], u["notch_outer"]["w"], u["notch_outer"]["depth"]
    wi, di = u["notch_inner"]["w"], u["notch_inner"]["depth"]
    # outline polygon (clockwise in KiCad's y-down frame: we write y_kicad = -y)
    pts = [(0, 0), (l, 0), (l, w), (xo + wo / 2, w), (xo + wo / 2, w - do_), (xo + wi / 2, w - do_), (xo + wi / 2, w - di), (xo - wi / 2, w - di),
           (xo - wi / 2, w - do_), (xo - wo / 2, w - do_), (xo - wo / 2, w), (0, w)]
    out = ['(kicad_pcb (version 20240108) (generator "openpatch_cart_board") (generator_version "1")',
           '  (general (thickness %.2f) (legacy_teardrops no))' % I["thickness_mm"], '  (paper "A4")',
           '  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen") (44 "Edge.Cuts" user) '
           '(46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard") (50 "User.1" user) (51 "User.2" user))']

    def P(x: float, y: float) -> str:
        return "(xy %.3f %.3f)" % (x + 100.0, -y + 100.0)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        out.append('  (gr_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))' % (a[0] + 100, -a[1] + 100, b[0] + 100, -b[1] + 100))
    for layer in ("F.CrtYd", "B.CrtYd"):
        for x, y, d in I["support_pads_part_free_both_faces"]["xy_A"] + I["support_pads_part_free_both_faces"]["xy_B"]:
            out.append('  (gr_circle (center %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "%s"))' % (x + 100, -y + 100, x + 100 + d / 2, -y + 100, layer))
    rp = I["lid_rib_pad_top_face"]
    out.append('  (gr_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))' % (rp["x"][0] + 100, -rp["y"][0] + 100, rp["x"][1] + 100, -rp["y"][1] + 100))
    az = I["antenna_zone"]
    out.append('  (gr_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "User.1"))' % (az["x"][0] + 100, 100, az["x"][1] + 100, -w + 100))
    sw = I["button_sw1"]
    out.append('  (gr_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "B.CrtYd"))' % (sw["x"] - 1.75 + 100, -w + 100, sw["x"] + 1.75 + 100, -(w - 2.9) + 100))
    wp = I["wire_pads_west_end"]
    out.append('  (gr_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "User.2"))' % (wp["x"][0] + 100, -0.5 + 100, wp["x"][1] + 100, -(w - 0.5) + 100))
    for txt, x, y, layer in (("USB-C", xo, w - 3.0, "User.2"), ("SW1 (bottom)", sw["x"], w - 4.2, "User.2"), ("ANT", l - 1.5, w / 2, "User.1"), ("wires", 2.1, w / 2, "User.2"),
                             ("cart board %.1f x %.1f, parts top <= %.2f / bottom <= %.2f" % (l, w, I["parts_height_max_mm"]["top"], I["parts_height_max_mm"]["bottom"]), l / 2, -2.0, "User.2")):
        out.append('  (gr_text "%s" (at %.3f %.3f) (layer "%s") (effects (font (size 0.8 0.8) (thickness 0.1))))' % (txt, x + 100, -y + 100, layer))
    out.append(")")
    return "\n".join(out) + "\n"


def main() -> None:
    p0 = load_params()
    out = HERE / "out" / "v010-cart" / "board"
    out.mkdir(parents=True, exist_ok=True)
    I = interface(p0)
    (out / "cart_board_interface.json").write_text(json.dumps(I, indent=1), encoding="utf-8")
    pcb = out / "cart_board_outline.kicad_pcb"
    pcb.write_text(kicad_pcb(I), encoding="utf-8")
    if Path(KICAD_CLI).exists():
        r = subprocess.run([KICAD_CLI, "pcb", "export", "svg", str(pcb), "-o", str(out / "cart_board_outline.svg"), "--layers", "Edge.Cuts,F.CrtYd,B.CrtYd,User.1,User.2",
                            "--page-size-mode", "2", "--exclude-drawing-sheet"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("kicad-cli failed: " + r.stdout + r.stderr)
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-b", "white", "-w", "1800", "-o", str(out / "cart_board_outline.png"), str(out / "cart_board_outline.svg")], check=True)
    print(f"cart board {I['outline_mm'][0]} x {I['outline_mm'][1]} -> {out}")


if __name__ == "__main__":
    main()
