# SPDX-License-Identifier: LicenseRef-OpenPatch
"""To-scale size comparison (top view + front view) of the cart pump against the Accu-Chek Insight, YpsoPump, Omnipod and the cup pod."""
from __future__ import annotations

from pathlib import Path

# (name, L, W, H, source / status)
REFERENCE = [
    ("Accu-Chek Insight (with adapter)", 84.0, 52.0, 19.0, "user manual App. A, VERIFIED"),
    ("mylife YpsoPump", 78.0, 46.0, 16.0, "mylife product page (search excerpt)"),
    ("Omnipod DASH / 5 pod", 52.0, 39.0, 14.5, "Insulet chart, VERIFIED"),
    ("OpenPatch cup pod OP-100", 47.96, 36.6, 8.5, "V010-CUP.md (CAD)"),
]
COLS = ["#9aa4ae", "#b9a37a", "#8fb0d8", "#7fbf7f", "#e0803a"]


def draw(L: dict, path: Path) -> None:
    rows = REFERENCE + [("OpenPatch cart pump (body / with adapter)", L["length_with_adapter"], L["width"], L["height"], f"this CAD, body {L['length']:.1f} long")]
    s = 4.0                                    # px per mm
    x0, y0, gap = 40, 80, 28
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="{h}">', '<rect width="100%" height="100%" fill="#fff"/>',
           '<text x="40" y="40" font-family="Helvetica,Arial,sans-serif" font-size="24" font-weight="bold">Size comparison to scale (top view left, end view right; 4 px = 1 mm)</text>']
    y = y0
    for k, (nm, l, w, h, src) in enumerate(rows):
        col = COLS[k]
        out.append(f'<rect x="{x0}" y="{y}" width="{l * s:.1f}" height="{w * s:.1f}" rx="12" fill="{col}" fill-opacity="0.55" stroke="#333"/>')
        if k == len(rows) - 1:
            out.append(f'<rect x="{x0}" y="{y}" width="{L["length"] * s:.1f}" height="{w * s:.1f}" rx="12" fill="{col}" fill-opacity="0.8" stroke="#000" stroke-width="2"/>')
        xe = x0 + 90 * s
        out.append(f'<rect x="{xe}" y="{y}" width="{w * s:.1f}" height="{h * s:.1f}" rx="8" fill="{col}" fill-opacity="0.7" stroke="#333"/>')
        xt = xe + 56 * s
        vol = l * w * h / 1000.0
        out.append(f'<text x="{xt}" y="{y + 22}" font-family="Helvetica,Arial,sans-serif" font-size="20" font-weight="bold">{nm}</text>')
        out.append(f'<text x="{xt}" y="{y + 48}" font-family="Helvetica,Arial,sans-serif" font-size="18">{l:.1f} x {w:.1f} x {h:.1f} mm, box {vol:.0f} ml</text>')
        out.append(f'<text x="{xt}" y="{y + 72}" font-family="Helvetica,Arial,sans-serif" font-size="15" fill="#555">{src}</text>')
        y += max(w, 22) * s + gap
    out[0] = out[0].format(h=int(y + 20))
    out.append("</svg>")
    path.write_text("\n".join(out), encoding="utf-8")
