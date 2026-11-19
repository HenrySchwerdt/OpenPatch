"""Compose the step images of the build guide: main view + exploded inset + numbered callouts + legend (Pillow).

Raw renders come from render_steps.py (`sNN.png` assembled view 1200 x 800, `sNN_x.png` exploded view 900 x 600).
Callout coordinates are pixel positions in the 1200 x 800 main view: (target x, target y, label x, label y).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAMES = {
    "s00": "step00_exploded", "s03": "step03_plunger", "s04": "step04_carriage", "s05": "step05_reservoir",
    "s06": "step06_shell_reservoir", "s07": "step06_leadscrew_carriage", "s08": "step06_motor_gear",
    "s09": "step07_board_ffc", "s10": "step08_gasket_lid", "s11": "step09_dock",
}

# (n, target_x, target_y, label_x, label_y)
CALLOUTS = {
    "s00": [(1, 860, 60, 1000, 40), (2, 560, 372, 250, 400), (3, 780, 250, 1000, 150), (4, 1110, 230, 1130, 120), (5, 480, 170, 250, 120), (6, 435, 300, 250, 260), (7, 500, 450, 220, 520), (8, 745, 470, 700, 560), (9, 500, 590, 250, 650), (10, 950, 470, 1100, 420), (11, 950, 650, 1100, 700)],
    "s03": [(1, 885, 440, 1000, 480), (2, 835, 500, 930, 590), (3, 775, 480, 700, 620), (4, 650, 300, 560, 190), (5, 610, 420, 450, 480)],
    "s04": [(1, 620, 250, 780, 170), (2, 520, 430, 340, 400), (3, 690, 490, 800, 470), (4, 560, 590, 420, 640)],
    "s05": [(1, 420, 300, 300, 200), (2, 760, 430, 900, 480), (3, 800, 455, 1010, 470), (4, 730, 345, 760, 220), (5, 820, 327, 960, 260)],
    "s06": [(1, 480, 610, 480, 700), (2, 450, 430, 380, 360), (3, 690, 500, 760, 640), (4, 690, 583, 620, 720), (5, 880, 470, 1000, 420), (6, 380, 245, 300, 130)],
    "s07": [(1, 228, 300, 160, 220), (2, 262, 300, 300, 200), (3, 322, 285, 420, 190), (4, 622, 295, 640, 200), (5, 640, 300, 760, 240)],
    "s08": [(1, 330, 225, 330, 120), (2, 250, 222, 170, 140), (3, 262, 330, 130, 330), (4, 480, 215, 560, 120), (5, 648, 290, 760, 220)],
    "s09": [(1, 700, 270, 600, 150), (2, 930, 450, 1060, 420), (3, 810, 310, 800, 190), (4, 900, 300, 980, 190)],
    "s10": [(1, 590, 168, 480, 80), (2, 700, 150, 800, 80), (3, 240, 400, 130, 480), (4, 1100, 300, 1100, 200)],
    "s11": [(1, 560, 350, 380, 250), (2, 640, 330, 640, 180), (3, 760, 320, 860, 220), (4, 870, 340, 1000, 400), (5, 400, 445, 280, 520)],
}


def _font(size, bold=True):
    try:
        import matplotlib
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        return ImageFont.truetype(str(d / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)
    except Exception:
        return ImageFont.load_default()


def _callouts(img, items):
    d = ImageDraw.Draw(img)
    f = _font(20)
    for n, tx, ty, lx, ly in items:
        d.line([(lx, ly), (tx, ty)], fill=(31, 59, 99), width=3)
        d.ellipse([tx - 5, ty - 5, tx + 5, ty + 5], fill=(31, 59, 99))
        d.ellipse([lx - 16, ly - 16, lx + 16, ly + 16], fill=(255, 255, 255), outline=(31, 59, 99), width=3)
        w = d.textlength(str(n), font=f)
        d.text((lx - w / 2, ly - 12), str(n), font=f, fill=(31, 59, 99))


def compose_all(steps, raw, img, only=None):
    img.mkdir(parents=True, exist_ok=True)
    for st in steps:
        sid = st["id"]
        if only and sid not in only:
            continue
        name = NAMES[sid]
        if st.get("explode_only"):
            src = raw / f"{sid}_x.png"
            if not src.exists():
                continue
            im = Image.open(src).convert("RGB")
            im = im.resize((1200, int(im.height * 1200 / im.width)), Image.LANCZOS)
            _callouts(im, CALLOUTS.get(sid, []))
        else:
            main, ex = raw / f"{sid}.png", raw / f"{sid}_x.png"
            if not main.exists():
                continue
            im = Image.open(main).convert("RGB")
            if ex.exists():
                x = Image.open(ex).convert("RGB").resize((360, 240), Image.LANCZOS)
                d = ImageDraw.Draw(im)
                px, py = im.width - 360 - 16, im.height - 240 - 26 - 12
                d.rectangle([px - 3, py - 3, px + 363, py + 243 + 26], fill=(255, 255, 255), outline=(31, 59, 99), width=2)
                im.paste(x, (px, py))
                d.text((px + 6, py + 244), "exploded view", font=_font(16), fill=(31, 59, 99))
            _callouts(im, CALLOUTS.get(sid, []))
        # legend strip
        out = Image.new("RGB", (im.width, im.height + 34), (255, 255, 255))
        out.paste(im, (0, 0))
        d = ImageDraw.Draw(out)
        legend = ("OP-100 bench pod, all parts exploded (CAD render). Bench test only, water only." if st.get("explode_only") else
                  "OP-100 bench pod, CAD render. Coloured = new in this step, grey = built earlier. Bench test only, water only.")
        d.text((12, im.height + 8), legend, font=_font(15, bold=False), fill=(60, 60, 60))
        out.save(img / f"{name}.png", optimize=True)
        print("composed", name)


SECTION_CALLOUTS = [
    (1, 480, 210, 480, 90), (2, 295, 230, 170, 150), (3, 560, 320, 600, 410), (4, 370, 305, 160, 330), (5, 367, 385, 150, 470),
    (6, 370, 560, 150, 620), (7, 580, 560, 580, 700), (8, 790, 560, 740, 820), (9, 880, 546, 960, 640), (10, 1000, 412, 1000, 300),
    (11, 990, 520, 1080, 760), (12, 765, 322, 840, 220), (13, 293, 360, 135, 395),
]


def compose_section(raw, img):
    src = raw / "section_plan.png"
    if not src.exists():
        return
    im = Image.open(src).convert("RGB")
    _callouts(im, SECTION_CALLOUTS)
    out = Image.new("RGB", (im.width, im.height + 34), (255, 255, 255))
    out.paste(im, (0, 0))
    d = ImageDraw.Draw(out)
    d.text((12, im.height + 8), "OP-100 bench pod, plan section at the drive axis plane z = 4.2 mm (CAD render). Bench test only, water only.",
           font=_font(15, bold=False), fill=(60, 60, 60))
    out.save(img / "section_plan_z4.2.png", optimize=True)
    print("composed section_plan_z4.2")
