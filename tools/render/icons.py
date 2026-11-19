"""Flat line icons for tools and actions (SVG, 100 x 100 viewBox) rendered with cairosvg.  Original drawings."""
from __future__ import annotations

import io

import cairosvg
from PIL import Image

S = 'fill="none" stroke="#1d1f23" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
F = 'fill="#1d1f23"'
G = 'fill="#c9ced4" stroke="#1d1f23" stroke-width="3" stroke-linejoin="round"'
A = 'fill="#e8a317" stroke="#1d1f23" stroke-width="3" stroke-linejoin="round"'

ICONS = {
    "calipers": f'<path {S} d="M12 78 H88 M20 78 V30 M20 30 H34 M44 78 V48 H70 V78"/><rect {G} x="40" y="40" width="34" height="16" rx="3"/><path {S} d="M28 70 v8 M36 70 v8 M52 70 v8 M60 70 v8"/>',
    "tweezers": f'<path {S} d="M16 86 L46 20 Q50 12 54 20 L84 86"/><path {S} d="M40 50 L60 50"/>',
    "cutters": f'<path {S} d="M20 86 L52 44 M80 86 L52 44"/><path {S} d="M52 44 L34 14 M52 44 L70 14"/><circle {G} cx="52" cy="44" r="5"/>',
    "screwdriver": f'<rect {A} x="14" y="10" width="22" height="46" rx="8"/><path {S} d="M25 56 V90"/><path {S} d="M20 90 H30"/>',
    "uv": f'<rect {G} x="22" y="50" width="56" height="30" rx="6"/><path {S} d="M32 40 v-14 M50 40 v-20 M68 40 v-14"/><circle {A} cx="50" cy="66" r="7"/>',
    "wheel": f'<circle {G} cx="46" cy="50" r="30"/><circle {F} cx="46" cy="50" r="5"/><path {S} d="M76 50 H94"/><path {S} d="M62 24 L74 14"/>',
    "pinvise": f'<rect {A} x="12" y="36" width="52" height="28" rx="10"/><path {S} d="M64 50 H92"/><path {S} d="M24 36 v-10 M40 36 v-10"/>',
    "file": f'<path {G} d="M20 80 L72 28 L82 38 L30 90 Z"/><path {S} d="M36 74 l6 6 M46 64 l6 6 M56 54 l6 6"/>',
    "loupe": f'<circle {S} cx="42" cy="42" r="24"/><path {S} d="M60 60 L86 86"/><path {S} d="M32 36 q6 -8 14 -6"/>',
    "lathe": f'<rect {G} x="10" y="56" width="80" height="14" rx="3"/><rect {A} x="14" y="30" width="22" height="26" rx="4"/><path {S} d="M36 43 H62"/><path {S} d="M62 38 L72 56"/>',
    "punch": f'<path {S} d="M40 14 H60 M50 14 V54"/><rect {G} x="38" y="54" width="24" height="26" rx="3"/><path {S} d="M20 88 H80"/>',
    "razor": f'<path {G} d="M14 60 L70 24 L86 44 L30 78 Z"/><path {S} d="M70 24 L86 44"/>',
    "feeler": f'<path {S} d="M16 70 L84 24 M20 80 L88 34 M24 88 L92 44"/><circle {G} cx="14" cy="74" r="7"/>',
    "multimeter": f'<rect {A} x="26" y="10" width="48" height="80" rx="8"/><rect {G} x="34" y="20" width="32" height="18" rx="2"/><circle {G} cx="50" cy="60" r="12"/><path {S} d="M50 60 L56 54"/>',
    "gauge": f'<circle {G} cx="50" cy="46" r="32"/><path {S} d="M50 46 L66 30"/><path {S} d="M34 82 h32"/><path {S} d="M50 78 v12"/>',
    "syringe": f'<rect {G} x="22" y="38" width="50" height="22" rx="3"/><path {S} d="M72 49 H92 M22 49 H8 M8 38 V60"/><path {S} d="M34 38 v10 M44 38 v10 M54 38 v10"/>',
    "balance": f'<path {G} d="M16 84 H84 L74 62 H26 Z"/><rect {G} x="32" y="40" width="36" height="8" rx="3"/><path {S} d="M50 40 V30"/><rect {F} x="40" y="14" width="20" height="14" rx="3"/>',
    "ipa": f'<path {G} d="M22 80 L16 40 H84 L78 80 Z"/><path {S} d="M16 40 Q50 52 84 40"/><path {S} d="M30 62 q8 -6 14 0 t14 0 t12 0"/>',
    "marker": f'<path {A} d="M24 80 L66 22 L80 32 L38 90 Z"/><path {S} d="M24 80 l-4 12 12 -4"/>',
    "compass": f'<circle {G} cx="50" cy="50" r="34"/><path d="M50 22 L58 50 L50 78 L42 50 Z" {A}/><circle {F} cx="50" cy="50" r="3"/>',
    "jig": f'<rect {G} x="14" y="40" width="72" height="30" rx="3"/><path {S} d="M14 55 H86"/><path {S} d="M70 40 V70"/>',
    "drop": f'<path {A} d="M50 12 Q74 44 74 62 A24 24 0 0 1 26 62 Q26 44 50 12 Z"/>',
    "glue": f'<rect {G} x="34" y="30" width="32" height="54" rx="6"/><path {S} d="M42 30 L50 12 L58 30"/><path {A} d="M50 90 Q58 100 50 100 Q42 100 50 90 Z"/>',
}

ACTIONS = {
    "wash": f'<path {G} d="M14 84 L8 36 H92 L86 84 Z"/><path {S} d="M24 60 q10 -8 18 0 t18 0 t16 0"/><path {S} d="M30 20 q6 -10 12 0 M58 20 q6 -10 12 0"/>',
    "uv": f'<circle {A} cx="50" cy="50" r="16"/><path {S} d="M50 14 v12 M50 74 v12 M14 50 h12 M74 50 h12 M24 24 l9 9 M67 67 l9 9 M76 24 l-9 9 M33 67 l-9 9"/>',
    "cut": f'<path {S} d="M16 86 L52 44 M84 86 L52 44 M52 44 L34 12 M52 44 L70 12"/>',
    "glue": f'<rect {G} x="34" y="26" width="32" height="50" rx="6"/><path {S} d="M42 26 L50 8 L58 26"/><path {A} d="M50 84 Q62 98 50 98 Q38 98 50 84 Z"/>',
    "oil": f'<path {A} d="M50 10 Q76 44 76 62 A26 26 0 0 1 24 62 Q24 44 50 10 Z"/><path {S} d="M36 64 q4 10 14 12"/>',
    "punch": f'<path {S} d="M36 10 H64 M50 10 V50"/><rect {G} x="36" y="50" width="28" height="26" rx="3"/><path {S} d="M14 88 H86"/>',
    "lock_open": f'<rect {G} x="22" y="46" width="56" height="36" rx="6"/><path {S} d="M34 46 V32 a16 16 0 0 1 30 -8"/>',
    "lock_close": f'<rect {G} x="22" y="46" width="56" height="36" rx="6"/><path {S} d="M34 46 V32 a16 16 0 0 1 32 0 V46"/>',
    "multimeter": ICONS["multimeter"], "feeler": ICONS["feeler"], "balance": ICONS["balance"],
    "tube": f'<path {S} d="M12 60 q20 -30 40 0 t36 0"/><path {S} d="M12 72 q20 -30 40 0 t36 0"/>',
    "fixture": f'<rect {G} x="12" y="34" width="76" height="34" rx="4"/><path {S} d="M12 51 H40"/><path {S} d="M56 34 V68"/>',
    "controller": f'<rect {G} x="14" y="24" width="72" height="52" rx="5"/><rect {A} x="24" y="34" width="22" height="16" rx="2"/><path {S} d="M60 36 H78 M60 46 H78 M24 62 H78"/>',
    "wheel": ICONS["wheel"], "valvetest": ICONS["syringe"], "slice": ICONS["razor"], "hubdrill": ICONS["pinvise"],
    "compass": ICONS["compass"],
    "lathe_a": ICONS["lathe"], "lathe_b": ICONS["lathe"],
    "rodmark": ICONS["marker"], "rodclamp": ICONS["pinvise"], "rodcut": ICONS["wheel"], "rodroll": ICONS["loupe"],
    "measure16": ICONS["calipers"], "measure84": ICONS["calipers"],
}


def _render(svg_body: str, size: int) -> Image.Image:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}">{svg_body}</svg>'
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def tool(name: str, size: int = 96) -> Image.Image:
    return _render(ICONS.get(name, ICONS["jig"]), size)


def action(name: str, size: int = 160) -> Image.Image | None:
    if name not in ACTIONS:
        return None
    return _render(ACTIONS[name], size)
