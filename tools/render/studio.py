"""Studio compositing helpers: seamless background, soft contact shadow, arrows, badges, text.  Pillow only."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path("/usr/share/fonts/opentype/inter")


def font(size, weight="Regular"):
    for f in (FONT_DIR / f"Inter-{weight}.otf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if f.exists():
            return ImageFont.truetype(str(f), size)
    return ImageFont.load_default()


THEMES = {
    "light": dict(bg_top=(241, 242, 245), bg_bot=(219, 222, 227), ink=(24, 26, 30), mute=(98, 104, 112), panel=(255, 255, 255),
                  line=(212, 216, 221), shadow=(40, 44, 52), shadow_a=0.30),
    "dark": dict(bg_top=(34, 37, 43), bg_bot=(14, 15, 18), ink=(240, 242, 245), mute=(150, 156, 165), panel=(30, 33, 38),
                 line=(62, 66, 74), shadow=(0, 0, 0), shadow_a=0.55),
}
GREEN = (36, 150, 84)
RED = (205, 50, 50)
AMBER = (232, 163, 23)


def backdrop(w, h, variant="light", floor=True):
    t = THEMES[variant]
    a = Image.new("RGB", (1, 2))
    a.putpixel((0, 0), t["bg_top"])
    a.putpixel((0, 1), t["bg_bot"])
    im = a.resize((w, h), Image.BILINEAR)
    return im.convert("RGBA")


def with_shadow(canvas, sprite, pos, variant="light", drop=0.05, blur=0.012, squash=None):
    """Paste an RGBA sprite on canvas at pos with a soft drop shadow (from its alpha) on the table below it."""
    t = THEMES[variant]
    w, h = sprite.size
    m = int(max(w, h) * 0.12)
    big = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    big.alpha_composite(sprite, (m, m))
    alpha = big.getchannel("A")
    if not alpha.getbbox():
        return canvas
    soft = alpha.filter(ImageFilter.GaussianBlur(max(3, w * blur * 2.0)))
    tight = alpha.filter(ImageFilter.GaussianBlur(max(2, w * blur * 0.6)))
    soft = ImageChops.offset(soft, int(w * 0.012), int(h * drop))
    tight = ImageChops.offset(tight, int(w * 0.004), int(h * drop * 0.35))
    shadow = ImageChops.lighter(soft.point(lambda v: int(v * 0.55)), tight.point(lambda v: int(v * 0.8)))
    layer = Image.new("RGBA", big.size, t["shadow"] + (0,))
    layer.putalpha(shadow.point(lambda v: int(v * t["shadow_a"])))
    pos2 = (pos[0] - m, pos[1] - m)
    # composite onto a cropped, padded copy so shadow margins outside the canvas are clipped safely
    canvas.alpha_composite(layer, (max(0, pos2[0]), max(0, pos2[1])), (max(0, -pos2[0]), max(0, -pos2[1])))
    canvas.alpha_composite(sprite, pos) if pos[0] >= 0 and pos[1] >= 0 else canvas.paste(sprite, pos, sprite)
    return canvas


def trim(sprite, pad=0):
    bb = sprite.getchannel("A").getbbox()
    if not bb:
        return sprite
    return sprite.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(sprite.width, bb[2] + pad), min(sprite.height, bb[3] + pad)))


def rounded(draw, box, r, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def arrow(canvas, p0, p1, color=(24, 26, 30), width=14, halo=(255, 255, 255), head=1.9):
    """Straight block arrow from p0 to p1 (pixels), supersampled, with a light halo for contrast."""
    S = 3
    w, h = canvas.size
    layer = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = [v * S for v in (*p0, *p1)]
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 4:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    wd = width * S / 2
    hl = min(L * 0.55, width * S * head * 1.6)
    hw = wd * 2.1
    bx, by = x1 - ux * hl, y1 - uy * hl

    def poly(grow):
        g = grow * S
        return [(x0 + nx * (wd + g), y0 + ny * (wd + g)), (bx + nx * (wd + g), by + ny * (wd + g)), (bx + nx * (hw + g), by + ny * (hw + g)),
                (x1 + ux * g * 1.6, y1 + uy * g * 1.6), (bx - nx * (hw + g), by - ny * (hw + g)), (bx - nx * (wd + g), by - ny * (wd + g)),
                (x0 - nx * (wd + g), y0 - ny * (wd + g))]

    d.polygon(poly(4), fill=halo + (235,))
    d.polygon(poly(0), fill=color + (255,))
    canvas.alpha_composite(layer.resize((w, h), Image.LANCZOS))


def curved_arrow(canvas, center, radius, start=200, end=500, color=(24, 26, 30), width=10):
    """Circular rotation arrow (degrees, screen space) around center."""
    S = 3
    w, h = canvas.size
    layer = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = center[0] * S, center[1] * S, radius * S
    box = [cx - r, cy - r * 0.55, cx + r, cy + r * 0.55]
    for col, wd in (((255, 255, 255, 235), width + 8), (color + (255,), width)):
        d.arc(box, start, end, fill=col, width=wd * S)
    a = math.radians(end)
    ex, ey = cx + r * math.cos(a), cy + r * 0.55 * math.sin(a)
    ta = a + math.pi / 2
    tip = (ex + math.cos(ta) * width * 2.4 * S, ey + math.sin(ta) * width * 2.4 * S * 0.55)
    l1 = (ex + math.cos(a) * width * 1.8 * S, ey + math.sin(a) * width * 1.8 * S * 0.55)
    l2 = (ex - math.cos(a) * width * 1.8 * S, ey - math.sin(a) * width * 1.8 * S * 0.55)
    d.polygon([l1, tip, l2], fill=color + (255,))
    canvas.alpha_composite(layer.resize((w, h), Image.LANCZOS))


def text_lines(draw, xy, lines, size, fill, weight="Regular", gap=1.25, maxw=None):
    f = font(size, weight)
    x, y = xy
    for ln in lines:
        if maxw:
            ln = fit(ln, f, maxw, draw)
        draw.text((x, y), ln, font=f, fill=fill)
        y += int(size * gap)
    return y


def wrap(text, f, maxw, draw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit(text, f, maxw, draw):
    while draw.textlength(text, font=f) > maxw and len(text) > 4:
        text = text[:-2]
    return text


def badge(draw, center, r, label, fill=(24, 26, 30), fg=(255, 255, 255), size=None):
    x, y = center
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)
    f = font(size or int(r * 1.1), "Bold")
    tw = draw.textlength(label, font=f)
    draw.text((x - tw / 2, y - (size or int(r * 1.1)) * 0.62), label, font=f, fill=fg)


def frame_inset(canvas, img, box, color, symbol, caption=None, variant="light", cap_size=20):
    """Paste img (RGB/RGBA) scaled into box with a colour frame and a corner symbol."""
    t = THEMES[variant]
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    d = ImageDraw.Draw(canvas)
    rounded(d, (x0 - 6, y0 - 6, x1 + 6, y1 + (cap_size * 2.4 if caption else 6)), 18, fill=t["panel"], outline=color, width=5)
    bgp = backdrop(w, h, variant)
    s = img.copy()
    s.thumbnail((w, h), Image.LANCZOS)
    bgp.alpha_composite(s, ((w - s.width) // 2, (h - s.height) // 2))
    canvas.alpha_composite(bgp, (x0, y0))
    d = ImageDraw.Draw(canvas)
    badge(d, (x0 + 4, y0 + 4), 26, symbol, fill=color, size=34)
    if caption:
        f = font(cap_size, "Medium")
        y = y1 + 8
        for ln in wrap(caption, f, w, d)[:2]:
            d.text((x0 + 4, y), ln, font=f, fill=t["ink"])
            y += int(cap_size * 1.2)
    return canvas
