#!/usr/bin/env python3
"""Board-vs-housing overlay for the cup-pod main board (independent review, 2026-11-20).

Inputs : board_snapshot.json (from dump_board.py: cup.kicad_pcb after the pin check, 54 fitted parts + pads) and the
         housing numbers of mechanical/out/v010-cup/OP-100.mech.json + op_cup.py / op_cup_asm.py (copied below
         as constants, verified against OP-100_bottom.stl / OP-100_top.stl with stl_probe.py).
Outputs: overlay_top.png, overlay_side.png (Pillow).  Pod frame: x = 0 rear (motor) end, +x toward the dock;
         y = 0 at the -Y (tank) wall; z = 0 skin side.  KiCad -> pod: x = kx - 100 + 7.45, y = 33.5 - (ky - 80).
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import cupgeom as G
MECH = json.load(open(os.path.join(HERE, "..", "..", "..", "..", "mechanical", "out", "v010-cup", "OP-100.mech.json")))
SNAP = json.load(open(os.path.join(HERE, "board_snapshot.json")))

L, W, H, WALL = MECH["length"], MECH["width"], MECH["height"], MECH["wall"]
LID_IN, Z_BOT, Z_TOP = 7.6, 5.3, 6.1
POSTS = [(2.55, 2.55), (L - 2.55, 2.55), (L - 2.55, W - 2.55)]
POCKET = (35.16, 47.07, 6.45, 17.05)            # roof z 4.45..4.9 (STL)
MAGNET = (39.36, 11.75)
OUTLINE = list(G.OUTLINE_POD)
INTERFACE = {"U1", "JU1", "SW1", "BZ1", "LD1", "U4A", "SP1", "SP2", "MP1", "MP2", "MP3", "MP4", "TL1", "TL2", "TL3", "TL4", "H1", "H2"}
POCKET_HITS = set()          # filled in by hits() below: bottom parts taller than 0.4 mm over the dock-pocket roof

FONT = next((f for f in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf") if os.path.exists(f)), "x")


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except OSError:
        return ImageFont.load_default()


def to_pod(kx, ky):
    return kx - 100 + G.X0, G.Y1 - (ky - 80)


def parts():
    out = []
    for f in SNAP["fps"]:
        x0, y1 = to_pod(f["bb"][0], f["bb"][1])
        x1, y0 = to_pod(f["bb"][2], f["bb"][3])
        cx, cy = to_pod(f["x"], f["y"])
        out.append(dict(ref=f["ref"], side=f["side"], h=f["h"], bb=(x0, y0, x1, y1), c=(cx, cy), fp=f["fp"]))
    return out


from check_items import ITEM_STATUS


def hits():
    """bottom-side parts taller than the 0.4 mm gap above the dock-pocket roof"""
    out = set()
    for p in parts():
        x0, y0, x1, y1 = p["bb"]
        if p["side"] == "B" and p["h"] > 0.4 and not (x1 < 35.26 or x0 > 46.97 or y1 < 6.55 or y0 > 16.95):
            out.add(p["ref"])
    return out


POCKET_HITS.update(hits())


# ------------------------------------------------------------------ top view
S, MX, MY = 22, 70, 110          # px per mm, margins


def P(x, y):
    return (MX + x * S, MY + (W - y) * S)


def rect(d, x0, y0, x1, y1, **kw):
    a, b = P(x0, y1), P(x1, y0)
    d.rectangle([a, b], **kw)


def label(d, x, y, txt, sz=13, fill="black", anchor="mm"):
    d.text(P(x, y), txt, font=font(sz), fill=fill, anchor=anchor)


def top_view():
    img = Image.new("RGB", (int(MX * 2 + L * S + 430), int(MY + W * S + 90)), "white")
    d = ImageDraw.Draw(img, "RGBA")
    # housing
    d.rounded_rectangle([P(0, W), P(L, 0)], radius=4.8 * S, fill=(235, 235, 235), outline=(90, 90, 90), width=3)
    d.rounded_rectangle([P(WALL, W - WALL), P(L - WALL, WALL)], radius=3.1 * S, fill="white", outline=(120, 120, 120), width=2)
    # lane-1 mechanics
    rect(d, MECH["x_dry"], 0.9, MECH["x_t0"], 22.6, fill=(170, 210, 245, 200), outline=(40, 90, 160), width=2)
    label(d, 22.6, 11.75, "TANK (full height z 0.9-7.6)", 15, (20, 60, 120))
    gy0, gy1 = MECH["gearhead_y"][0], MECH["y_motor_end"]
    rect(d, 1.47, gy0, 7.47, gy1, fill=(150, 150, 150, 220), outline="black", width=2)
    label(d, 4.47, 20.0, "MOTOR", 14, "white")
    label(d, 4.47, 18.6, "NFP-608", 11, "white")
    rect(d, 2.17, 25.35, 6.77, 28.75, fill=(255, 220, 0, 230), outline="black")
    label(d, 4.47, 27.05, "pins", 11)
    label(d, 4.47, 26.0, "(under can)", 10)
    rect(d, 4.47 - 3.37, 29.95, 7.84, 31.45, outline=(200, 0, 0), width=2)
    rect(d, 1.77, MECH["gear_a_y"][0], 7.17, MECH["gear_a_y"][1], fill=(200, 160, 60, 220), outline="black")
    rect(d, MECH["gear_b"][0], 9.05, MECH["gear_b"][1], 14.45, fill=(200, 160, 60, 220), outline="black")
    label(d, 6.8, 8.3, "gears", 11)
    rect(d, MECH["tmag"][0], 7.45, MECH["tmag"][1], 10.25, fill=(120, 200, 120, 230), outline="black")
    label(d, 4.1, 6.6, "TMAG", 11)
    # dock pocket
    rect(d, POCKET[0], POCKET[2], POCKET[1], POCKET[3], fill=(250, 200, 200, 120), outline=(180, 60, 60), width=2)
    label(d, 45.3, 15.9, "DOCK POCKET", 11, (150, 30, 30))
    label(d, 45.3, 15.1, "roof z 4.9", 11, (150, 30, 30))
    mx, my = P(*MAGNET)
    d.ellipse([mx - 9, my - 9, mx + 9, my + 9], fill=(200, 0, 0), outline="black")
    label(d, 45.3, 11.0, "dock magnet", 11, (150, 30, 30))
    # lane 2: cell + USB opening
    d.rectangle([P(9.37, 33.4), P(40.87, 22.8)], outline=(0, 140, 0), width=3)
    d.rectangle([P(18.8, W), P(28.2, W - WALL)], fill=(0, 160, 255))
    label(d, 23.5, W + 0.9, "USB-C wall opening x 18.8-28.2", 12, (0, 90, 180))
    rect(d, 19.03, 26.35, 27.97, 33.7, outline=(0, 90, 200), width=2)
    # posts, ledges
    for (x, y) in POSTS:
        a, b = P(x - 1.0, y + 1.0), P(x + 1.0, y - 1.0)
        d.ellipse([a, b], fill=(60, 60, 60), outline="black")
    label(d, L - 2.55, 2.55 + 1.9, "M1.2 post", 10)
    for y in (24.3, 32.1):
        a, b = P(41.5 - 0.8, y + 0.8), P(41.5 + 0.8, y - 0.8)
        d.ellipse([a, b], outline=(120, 60, 0), width=2)
    for sx, sy in G.SCREWS:
        a, b = P(sx - 1.4, sy + 1.4), P(sx + 1.4, sy - 1.4)
        d.ellipse([a, b], outline=(200, 0, 200), width=2)
        label(d, sx, sy, "screw", 9, (150, 0, 150))
    label(d, 45.3, 25.7, "support pads z 5.3", 10, (120, 60, 0))
    label(d, 45.3, 25.0, "+ lid ribs above", 10, (120, 60, 0))
    # requested button flex zone (not in CAD)
    for i in range(0, 9):
        x = 31.9 + i * 0.25
        d.line([P(x, W), P(x + 0.12, W - 0.9)], fill=(220, 0, 0), width=2)
    label(d, 33.0, W + 1.9, "button flex window x 29.4-31.5 in the CAD: move to x 31.9-34.1 (SKSCLAE010, request)", 11, (200, 0, 0))
    # board
    pts = [P(x, y) for x, y in OUTLINE]
    d.polygon(pts, fill=(60, 170, 60, 45))
    d.line(pts + [pts[0]], fill=(0, 110, 0), width=4)
    a, b = P(42.0, 33.6), P(43.3, 22.9)
    d.rectangle([a, b], fill=(255, 0, 255, 60), outline=(200, 0, 200), width=2)
    label(d, 42.65, 34.25, "antenna", 10, (160, 0, 160))
    # cell outline again on top of the board fill
    for i in range(0, int((39.37 - 7.87) / 0.8)):
        x = 7.87 + i * 0.8
        d.line([P(x, 22.8), P(min(x + 0.4, 39.37), 22.8)], fill=(0, 150, 0), width=4)
        d.line([P(x, 33.4), P(min(x + 0.4, 39.37), 33.4)], fill=(0, 150, 0), width=4)
    d.line([P(39.37, 22.8), P(39.37, 33.4)], fill=(0, 150, 0), width=4)
    d.line([P(7.87, 22.8), P(7.87, 33.4)], fill=(0, 150, 0), width=4)
    # parts
    for p in parts():
        x0, y0, x1, y1 = p["bb"]
        bad = p["ref"] in POCKET_HITS or p["ref"] in ("JU1", "J1")
        if p["side"] == "F":
            col = (40, 80, 220, 110)
            ol = (20, 40, 160)
        else:
            col = (255, 150, 0, 110)
            ol = (190, 90, 0)
        if bad:
            ol = (230, 0, 0)
        d.rectangle([P(x0, y1), P(x1, y0)], fill=col, outline=ol, width=3 if bad or p["ref"] in INTERFACE else 1)
        if p["ref"] in INTERFACE or bad:
            if p["ref"] in ("TL2", "TL3", "TL4"):
                continue
            txt = "TL1-4" if p["ref"] == "TL1" else p["ref"]
            lx_ = 10.4 if p["ref"] == "TL1" else (x0 + x1) / 2
            label(d, lx_, (y0 + y1) / 2, txt, 13 if p["ref"] in INTERFACE else 11, "black")
    # issue markers
    status = ITEM_STATUS
    issues = [(1, 23.5, 30.5), (2, 38.0, 13.5), (3, 10.6, 26.1), (4, 7.8, 31.0), (5, 41.5, 28.2), (6, 33.0, 32.4), (7, 41.0, 20.4), (8, 36.5, 12.6)]
    for n, x, y in issues:
        cx, cy = P(x, y)
        col = (0, 150, 60) if status.get(n, (False, ""))[0] else (230, 0, 0)
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=col, outline="white", width=2)
        d.text((cx, cy), str(n), font=font(15), fill="white", anchor="mm")
    # axes
    d.text((MX, 30), "OpenPatch cup pod OP-100 - TOP VIEW: housing + mechanics vs main board (cup.kicad_pcb after the pin check; green = review item resolved)", font=font(20), fill="black")
    d.text((MX, 58), "x = 0 at the motor end (left), dock at the right; y = 0 at the tank-side wall (bottom). Scale: 1 mm = 22 px. Mechanics from OP-100.mech.json / STL.", font=font(13), fill=(60, 60, 60))
    for x in range(0, 50, 5):
        d.line([P(x, 0)[0], MY + W * S + 8, P(x, 0)[0], MY + W * S + 16], fill="black")
        d.text((P(x, 0)[0], MY + W * S + 26), str(x), font=font(12), fill="black", anchor="mm")
    for y in range(0, 36, 5):
        d.line([MX - 16, P(0, y)[1], MX - 8, P(0, y)[1]], fill="black")
        d.text((MX - 30, P(0, y)[1]), str(y), font=font(12), fill="black", anchor="mm")
    # legend
    lx = MX + L * S + 40
    ly = MY
    leg = [((60, 170, 60, 90), (0, 110, 0), "main board outline (z 5.3-6.1)"), ((40, 80, 220, 110), (20, 40, 160), "part on TOP side"),
           ((255, 150, 0, 110), (190, 90, 0), "part on BOTTOM side"), ((255, 255, 255, 0), (230, 0, 0), "part that collides / is wrong (red)"),
           ((170, 210, 245, 200), (40, 90, 160), "tank"), ((150, 150, 150, 220), (0, 0, 0), "motor (axis along y)"),
           ((250, 200, 200, 120), (180, 60, 60), "dock pocket (roof z 4.45-4.9)"), ((255, 255, 255, 0), (0, 150, 0), "cell 301030 under the board (z 0.9-4.1)"), ((255, 0, 255, 60), (200, 0, 200), "antenna keep-out")]
    for i, (f, o, t) in enumerate(leg):
        y = ly + i * 30
        d.rectangle([lx, y, lx + 26, y + 18], fill=f, outline=o, width=3)
        d.text((lx + 36, y + 9), t, font=font(13), fill="black", anchor="lm")
    y = ly + len(leg) * 30 + 14
    notes = ["Review items (green = resolved):"]
    for n in range(1, 9):
        ok, txt = ITEM_STATUS.get(n, (False, "not checked"))
        notes.append("%d %s %s" % (n, "OK" if ok else "OPEN", txt[:46]))
        if len(txt) > 46:
            notes.append("     " + txt[46:92])
    for i, t in enumerate(notes):
        d.text((lx, y + i * 22), t, font=font(14 if i == 0 else 13), fill=(200, 0, 0) if i == 0 else "black")
    img.save(os.path.join(HERE, "overlay_top.png"))


# ------------------------------------------------------------------ side views
def side_view():
    S2 = 22
    img = Image.new("RGB", (1300, 900), "white")
    d = ImageDraw.Draw(img, "RGBA")

    def Q(x, z, ox, oy):
        return (ox + x * S2, oy - z * S2)

    def box(x0, z0, x1, z1, ox, oy, **kw):
        d.rectangle([Q(x0, z1, ox, oy), Q(x1, z0, ox, oy)], **kw)

    d.text((40, 20), "SIDE SECTIONS (z = height above the skin side, 1 mm = 22 px)", font=font(20), fill="black")
    # ---------- panel A: lane 2 along x, all lane-2 parts projected
    ox, oy = 60, 330
    d.text((ox, 60), "A) Lane 2 seen from the +Y wall (all parts with y > 22.9 projected)", font=font(15), fill="black")
    box(0, 0, L, WALL, ox, oy, fill=(200, 200, 200))
    box(0, H - WALL, L, H, ox, oy, fill=(200, 230, 255, 160), outline=(90, 140, 200))
    d.text(Q(1, H + 0.6, ox, oy), "clear lid (inner face z 7.6)", font=font(12), fill=(40, 90, 160))
    cx, cz = Q(4.47, 4.25, ox, oy)
    d.ellipse([cx - 3 * S2, cz - 3 * S2, cx + 3 * S2, cz + 3 * S2], fill=(150, 150, 150), outline="black", width=2)
    d.text((cx, cz), "motor d6", font=font(12), fill="white", anchor="mm")
    d.pieslice([cx - 3.37 * S2, cz - 3.37 * S2, cx + 3.37 * S2, cz + 3.37 * S2], start=-29, end=0, fill=(230, 0, 0, 160))
    box(9.37, 0.9, 40.87, 4.1, ox, oy, fill=(120, 200, 120), outline=(0, 110, 0))
    d.text(Q(20, 2.5, ox, oy), "CELL 301030 (z 0.9-4.1 incl. swell)", font=font(13), fill="black", anchor="mm")
    box(19.03, 4.12, 27.97, 7.33, ox, oy, outline=(0, 120, 255), width=3)
    d.text(Q(23.5, 7.9, ox, oy), "USB-C receptacle keep-out (mech): sink-board part, board passes through its body", font=font(11), fill=(0, 90, 200), anchor="mm")
    box(7.8, Z_BOT, 43.4, Z_TOP, ox, oy, fill=(0, 140, 0), outline=(0, 90, 0))
    d.text(Q(44, 5.7, ox, oy), "board 0.8", font=font(11), fill=(0, 90, 0), anchor="lm")
    for y in (41.5,):
        box(y - 0.5, WALL, y + 0.5, 5.3, ox, oy, fill=(200, 140, 60))
    d.text(Q(41.5, 5.6, ox, oy), "ledge 5.3", font=font(10), fill=(120, 60, 0), anchor="mm")
    box(L - 2.55 - 1.0, WALL, L - 2.55 + 1.0, 7.55, ox, oy, fill=(90, 90, 90))
    for p in parts():
        x0, y0, x1, y1 = p["bb"]
        if y1 < 22.9 or p["ref"] == "JU1" or p["h"] <= 0:
            continue
        if p["side"] == "F":
            box(x0, Z_TOP, x1, Z_TOP + p["h"], ox, oy, fill=(40, 80, 220, 70), outline=(20, 40, 160))
        else:
            box(x0, Z_BOT - p["h"], x1, Z_BOT, ox, oy, fill=(255, 150, 0, 90), outline=(190, 90, 0))
    for z, t in ((LID_IN, "lid inner 7.6"), (Z_TOP, "board top 6.1"), (Z_BOT, "board bottom 5.3"), (4.1, "cell top 4.1")):
        d.line([Q(0, z, ox, oy), Q(L, z, ox, oy)], fill=(120, 120, 120), width=1)
        d.text(Q(L + 0.5, z, ox, oy), t, font=font(11), fill=(80, 80, 80), anchor="lm")
    d.text(Q(1.0, -1.2, ox, oy), "red wedge = lane-2 motor saddle lip (x 7.7 at z 5.2; board edge now x 7.8)", font=font(12), fill=(200, 0, 0))
    # ---------- panel B: cross section through the leg at x ~ 36-44 (y along horizontal)
    ox, oy = 60, 790
    d.text((ox, 450), "B) Cross-section through the board leg / dock (x 35.4-44.2), seen from the dock end; all leg parts projected", font=font(15), fill="black")
    box(0, 0, W, WALL, ox, oy, fill=(200, 200, 200))
    box(0, 0, WALL, H, ox, oy, fill=(200, 200, 200))
    box(W - WALL, 0, W, H, ox, oy, fill=(200, 200, 200))
    box(0, H - WALL, W, H, ox, oy, fill=(200, 230, 255, 160), outline=(90, 140, 200))
    box(6.45, 4.45, 17.05, 4.9, ox, oy, fill=(180, 60, 60))
    box(6.45, WALL, 6.85, 4.9, ox, oy, fill=(180, 60, 60))
    box(16.65, WALL, 17.05, 4.9, ox, oy, fill=(180, 60, 60))
    d.text(Q(11.75, 2.6, ox, oy), "dock pocket (cannula head inside)", font=font(12), fill=(150, 30, 30), anchor="mm")
    mx, mz = Q(11.75, 3.9, ox, oy)
    d.ellipse([mx - 8, mz - 5, mx + 8, mz + 5], fill=(200, 0, 0))
    box(22.8, 0.9, 33.4, 4.1, ox, oy, fill=(120, 200, 120), outline=(0, 110, 0))
    d.text(Q(28.1, 2.5, ox, oy), "cell", font=font(12), fill="black", anchor="mm")
    for (y0, y1) in ((10.4, 17.15), (17.15, 22.9), (22.9, 33.5)):
        box(y0, Z_BOT, y1, Z_TOP, ox, oy, fill=(0, 140, 0), outline=(0, 90, 0))
    for p in parts():
        x0, y0, x1, y1 = p["bb"]
        if x1 < 35.4 or p["h"] <= 0:
            continue
        bad = p["ref"] in POCKET_HITS
        if p["side"] == "F":
            box(y0, Z_TOP, y1, Z_TOP + p["h"], ox, oy, fill=(40, 80, 220, 70), outline=(20, 40, 160))
        else:
            box(y0, Z_BOT - p["h"], y1, Z_BOT, ox, oy, fill=(230, 0, 0, 140) if bad else (255, 150, 0, 90), outline=(230, 0, 0) if bad else (190, 90, 0), width=2 if bad else 1)
        if p["ref"] in INTERFACE:
            zz = Z_TOP + p["h"] + 0.35 if p["side"] == "F" else Z_BOT - p["h"] - 0.35
            d.text(Q((y0 + y1) / 2, zz, ox, oy), p["ref"], font=font(11), fill="black", anchor="mm")
    for z, t in ((LID_IN, "lid 7.6"), (Z_TOP, "6.1"), (Z_BOT, "5.3"), (4.9, "roof 4.9")):
        d.line([Q(0, z, ox, oy), Q(W, z, ox, oy)], fill=(120, 120, 120))
        d.text(Q(W + 0.5, z, ox, oy), t, font=font(11), fill=(80, 80, 80), anchor="lm")
    d.text(Q(0.0, -1.3, ox, oy), "-Y wall (tank side)", font=font(12), fill=(200, 0, 0))
    d.text(Q(W, -1.3, ox, oy), "+Y wall (button flex window)", font=font(12), fill="black", anchor="rm")
    d.text(Q(11.75, 5.0 - 1.9, ox, oy), "", font=font(10))
    d.text(Q(0.5, -2.4, ox, oy), "bottom parts over the dock-pocket roof: " + (", ".join(sorted(POCKET_HITS)) or "none taller than 0.4 mm"), font=font(12), fill=(200, 0, 0))
    img.save(os.path.join(HERE, "overlay_side.png"))


if __name__ == "__main__":
    top_view()
    side_view()
