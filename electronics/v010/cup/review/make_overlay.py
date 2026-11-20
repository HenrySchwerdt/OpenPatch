#!/usr/bin/env python3
"""Board-vs-housing overlay for the cup-pod main board (independent review, 2026-11-20).

Inputs : board_snapshot.json (from dump_board.py, a copy of cup.kicad_pcb taken 2026-11-20 12:20) and the
         housing numbers of mechanical/out/v010-cup/OP-100.mech.json + op_cup.py / op_cup_asm.py (copied below
         as constants, verified against OP-100_bottom.stl / OP-100_top.stl with stl_probe.py).
Outputs: overlay_top.png, overlay_side.png (Pillow).  Pod frame: x = 0 rear (motor) end, +x toward the dock;
         y = 0 at the -Y (tank) wall; z = 0 skin side.  KiCad -> pod: x = kx - 100 + 7.45, y = 33.5 - (ky - 80).
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MECH = json.load(open(os.path.join(HERE, "..", "..", "..", "..", "mechanical", "out", "v010-cup", "OP-100.mech.json")))
SNAP = json.load(open(os.path.join(HERE, "board_snapshot.json")))

L, W, H, WALL = MECH["length"], MECH["width"], MECH["height"], MECH["wall"]
LID_IN, Z_BOT, Z_TOP = 7.6, 5.3, 6.1
POSTS = [(2.55, 2.55), (L - 2.55, 2.55), (L - 2.55, W - 2.55)]
POCKET = (35.16, 47.07, 6.45, 17.05)            # roof z 4.45..4.9 (STL)
MAGNET = (39.36, 11.75)
OUTLINE = [(7.45, 33.5), (43.4, 33.5), (43.4, 22.9), (42.0, 22.9), (42.0, 6.35), (44.2, 6.35), (44.2, 1.1), (35.4, 1.1), (35.4, 6.35),
           (36.0, 6.35), (36.0, 17.15), (35.4, 17.15), (35.4, 22.9), (7.45, 22.9)]
INTERFACE = {"U1", "JU1", "SW1", "J1", "BZ1", "LD1", "U4A", "SP1", "SP2", "TL1", "TL2", "TL3", "TL4"}
POCKET_HITS = {"C1", "C50", "R21", "R91", "R92"}

FONT = "/System/Library/Fonts/Helvetica.ttc"


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except OSError:
        return ImageFont.load_default()


def to_pod(kx, ky):
    return kx - 100 + 7.45, 33.5 - (ky - 80)


def parts():
    out = []
    for f in SNAP["fps"]:
        x0, y1 = to_pod(f["bb"][0], f["bb"][1])
        x1, y0 = to_pod(f["bb"][2], f["bb"][3])
        cx, cy = to_pod(f["x"], f["y"])
        out.append(dict(ref=f["ref"], side=f["side"], h=f["h"], bb=(x0, y0, x1, y1), c=(cx, cy), fp=f["fp"]))
    return out


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
    d.rectangle([P(7.87, 33.4), P(39.37, 22.8)], outline=(0, 140, 0), width=3)
    d.rectangle([P(7.7, W), P(17.0, W - WALL)], fill=(0, 160, 255))
    label(d, 12.35, W + 0.9, "USB-C wall opening x 7.7-17.0", 12, (0, 90, 180))
    # posts, ledges
    for (x, y) in POSTS:
        a, b = P(x - 1.0, y + 1.0), P(x + 1.0, y - 1.0)
        d.ellipse([a, b], fill=(60, 60, 60), outline="black")
    label(d, L - 2.55, 2.55 + 1.9, "M1.2 post", 10)
    for y in (24.3, 32.1):
        a, b = P(40.57 - 0.9, y + 0.9), P(40.57 + 0.9, y - 0.9)
        d.ellipse([a, b], outline=(120, 60, 0), width=2)
    label(d, 45.3, 25.7, "ledges top z 4.15", 10, (120, 60, 0))
    label(d, 45.3, 25.0, "(board at 5.3!)", 10, (120, 60, 0))
    # requested button flex zone (not in CAD)
    for i in range(0, 12):
        x = 38.3 + i * 0.25
        d.line([P(x, 0.0), P(x + 0.12, 0.9)], fill=(220, 0, 0), width=2)
    label(d, 37.6, -2.3, "button flex zone requested - NOT in CAD ->", 12, (200, 0, 0), "rm")
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
    issues = [(1, 12.5, 31.6), (2, 7.6, 30.7), (3, 40.0, 14.2), (4, 39.8, 4.7), (5, 31.5, 29.6), (6, 39.8, 1.6), (7, 40.57, 33.0), (8, 9.2, 25.2)]
    for n, x, y in issues:
        cx, cy = P(x, y)
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=(230, 0, 0), outline="white", width=2)
        d.text((cx, cy), str(n), font=font(15), fill="white", anchor="mm")
    # axes
    d.text((MX, 30), "OpenPatch cup pod OP-100 - TOP VIEW: housing + mechanics vs main board (cup.kicad_pcb, 2026-11-20 12:20)", font=font(20), fill="black")
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
           ((255, 150, 0, 110), (190, 90, 0), "part on BOTTOM side"), ((255, 255, 255, 0), (230, 0, 0), "part that collides / is wrong"),
           ((170, 210, 245, 200), (40, 90, 160), "tank"), ((150, 150, 150, 220), (0, 0, 0), "motor (axis along y)"),
           ((250, 200, 200, 120), (180, 60, 60), "dock pocket (roof z 4.45-4.9)"), ((255, 255, 255, 0), (0, 150, 0), "cell 301030 under the board (z 0.9-4.1)"), ((255, 0, 255, 60), (200, 0, 200), "antenna keep-out")]
    for i, (f, o, t) in enumerate(leg):
        y = ly + i * 30
        d.rectangle([lx, y, lx + 26, y + 18], fill=f, outline=o, width=3)
        d.text((lx + 36, y + 9), t, font=font(13), fill="black", anchor="lm")
    y = ly + len(leg) * 30 + 14
    notes = ["Numbered problems:",
             "1 USB-C proxy is top-mount: top z 9.36 > lid 7.6",
             "   (no notch in the outline for a mid-mount)",
             "2 lane-2 motor saddle enters the board",
             "   volume (x 7.45-7.68, z 5.3-5.85)",
             "3 C1 C50 R21 R91 R92 hit the pocket roof",
             "   (only 0.4 mm below the board there)",
             "4 J1 motor socket 32 mm from the motor",
             "5 SP1/SP2 cell pads mid-board, top side:",
             "   cell wires cannot reach them",
             "6 SW1 points at a solid wall (no flex zone)",
             "7 board ledges at z 4.15: board floats",
             "8 west end: motor pins + cell PCM + TMAG",
             "   strip + USB-C all want the same 10 mm"]
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
    box(7.87, 0.9, 39.37, 4.1, ox, oy, fill=(120, 200, 120), outline=(0, 110, 0))
    d.text(Q(20, 2.5, ox, oy), "CELL 301030 (z 0.9-4.1 incl. swell)", font=font(13), fill="black", anchor="mm")
    box(7.87, 4.2, 16.81, 7.46, ox, oy, outline=(0, 120, 255), width=3)
    d.text(Q(12.3, 4.6, ox, oy), "USB box (mech)", font=font(11), fill=(0, 90, 200), anchor="mm")
    box(7.14, Z_TOP, 17.87, Z_TOP + 3.26, ox, oy, fill=(230, 0, 0, 70), outline=(230, 0, 0), width=2)
    d.text(Q(12.5, 9.0, ox, oy), "JU1 as placed (top-mount) -> z 9.36", font=font(12), fill=(200, 0, 0), anchor="mm")
    box(7.45, Z_BOT, 43.4, Z_TOP, ox, oy, fill=(0, 140, 0), outline=(0, 90, 0))
    d.text(Q(44, 5.7, ox, oy), "board 0.8", font=font(11), fill=(0, 90, 0), anchor="lm")
    for y in (40.57,):
        box(y - 0.9, WALL, y + 0.9, 4.15, ox, oy, fill=(200, 140, 60))
    d.text(Q(40.6, 4.5, ox, oy), "ledge 4.15", font=font(10), fill=(120, 60, 0), anchor="mm")
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
    d.text(Q(1.0, -1.2, ox, oy), "red wedge = lane-2 motor saddle lip reaching x 7.68 at z 5.3 (board edge 7.45)", font=font(12), fill=(200, 0, 0))
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
    for (y0, y1) in ((1.1, 6.35), (6.35, 17.15), (17.15, 22.9), (22.9, 33.5)):
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
    d.text(Q(0.0, -1.3, ox, oy), "-Y wall (button side, solid: no flex zone)", font=font(12), fill=(200, 0, 0))
    d.text(Q(W, -1.3, ox, oy), "+Y wall", font=font(12), fill="black", anchor="rm")
    d.text(Q(11.75, 5.0 - 1.9, ox, oy), "", font=font(10))
    d.text(Q(0.5, -2.4, ox, oy), "red bars under the board above the pocket = C1, C50, R21, R91, R92 (0.5-0.6 mm tall) in a 0.4 mm gap; U4A hall (0.4) sits on the roof with 0.0 mm",
           font=font(12), fill=(200, 0, 0))
    img.save(os.path.join(HERE, "overlay_side.png"))


if __name__ == "__main__":
    top_view()
    side_view()
