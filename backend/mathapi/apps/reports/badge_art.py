"""
Badge medallion art, shared by pdf_engine.py and excel_engine.py.

Each badge icon (matching the `icon` field on gamification.models.Badge —
'flag', 'flame', 'star', etc.) is defined ONCE here as a small list of
normalized (0..1, y-up) vector primitives. Two renderers consume that same
recipe:

  - draw_badge_drawing()  -> a reportlab.graphics.shapes.Drawing (true vector,
    used directly in PDF flowables — crisp at any size, no rasterization).
  - badge_png_bytes()     -> a PNG (via Pillow, already a project dependency)
    for embedding as a real image in Excel workbooks, since openpyxl can only
    place raster images, not vector drawings.

Deliberately hand-drawn primitive glyphs (not a redistributed third-party
icon set) so there's exactly one small, dependency-free source of truth for
"what a badge looks like" everywhere in the platform's reports.
"""
import io
import math

from reportlab.graphics.shapes import Drawing, Circle, Polygon, Line, Group
from reportlab.lib import colors as rl_colors

from PIL import Image, ImageDraw

# ── Palette — one accent colour per icon family ─────────────────────────────
ICON_COLORS = {
    'flag':          '#2563eb',
    'flame':         '#f97316',
    'star':          '#f59e0b',
    'trending-up':   '#10b981',
    'award':         '#f59e0b',
    'shield':        '#3b82f6',
    'shield-check':  '#10b981',
    'swords':        '#e11d48',
    'crown':         '#d97706',
    'trophy':        '#d97706',
    'zap':           '#eab308',
    'sparkles':      '#8b5cf6',
}
DEFAULT_COLOR = '#6b7280'


def _star_points(cx, cy, r_outer, r_inner, n=5, rotation=-90):
    pts = []
    for i in range(n * 2):
        r = r_outer if i % 2 == 0 else r_inner
        angle = math.radians(rotation + i * (360 / (n * 2)))
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def _diamond_points(cx, cy, r):
    return [(cx, cy + r), (cx + r * 0.55, cy), (cx, cy - r), (cx - r * 0.55, cy)]


# ── Icon recipes — normalized to a 0..1 box, y-up ───────────────────────────
# Each part: ('polygon', points, tone) | ('circle', cx, cy, r, tone) | ('line', x1, y1, x2, y2, width, tone)
# tone: 'glyph' = drawn in white (over the coloured medallion); 'accent' = drawn in the medallion's own colour
def _icon_recipe(icon):
    if icon == 'flag':
        return [
            ('line', 0.28, 0.10, 0.28, 0.90, 0.09, 'glyph'),
            ('polygon', [(0.28, 0.88), (0.82, 0.72), (0.28, 0.56)], 'glyph'),
        ]
    if icon == 'flame':
        return [
            ('polygon', [
                (0.50, 0.98), (0.66, 0.80), (0.78, 0.58), (0.74, 0.36),
                (0.60, 0.46), (0.62, 0.20), (0.50, 0.02), (0.38, 0.20),
                (0.40, 0.46), (0.26, 0.36), (0.22, 0.58), (0.34, 0.80),
            ], 'glyph'),
        ]
    if icon in ('star', 'award'):
        return [('polygon', _star_points(0.5, 0.52, 0.46, 0.19), 'glyph')]
    if icon == 'trending-up':
        return [
            ('line', 0.08, 0.22, 0.35, 0.50, 0.08, 'glyph'),
            ('line', 0.35, 0.50, 0.55, 0.34, 0.08, 'glyph'),
            ('line', 0.55, 0.34, 0.92, 0.75, 0.08, 'glyph'),
            ('polygon', [(0.68, 0.80), (0.95, 0.86), (0.86, 0.60)], 'glyph'),
        ]
    if icon in ('shield', 'shield-check'):
        shield = ('polygon', [
            (0.5, 0.95), (0.85, 0.80), (0.85, 0.42),
            (0.5, 0.05), (0.15, 0.42), (0.15, 0.80),
        ], 'glyph')
        if icon == 'shield':
            return [shield]
        return [
            shield,
            ('line', 0.32, 0.50, 0.45, 0.34, 0.08, 'accent'),
            ('line', 0.45, 0.34, 0.72, 0.66, 0.08, 'accent'),
        ]
    if icon == 'swords':
        return [
            ('line', 0.15, 0.15, 0.85, 0.85, 0.10, 'glyph'),
            ('line', 0.15, 0.85, 0.85, 0.15, 0.10, 'glyph'),
            ('polygon', [(0.10, 0.10), (0.24, 0.10), (0.10, 0.24)], 'glyph'),
            ('polygon', [(0.90, 0.10), (0.90, 0.24), (0.76, 0.10)], 'glyph'),
            ('polygon', [(0.10, 0.90), (0.24, 0.90), (0.10, 0.76)], 'glyph'),
            ('polygon', [(0.90, 0.90), (0.76, 0.90), (0.90, 0.76)], 'glyph'),
        ]
    if icon == 'crown':
        return [
            ('polygon', [
                (0.15, 0.15), (0.85, 0.15), (0.85, 0.72),
                (0.68, 0.48), (0.5, 0.85), (0.32, 0.48), (0.15, 0.72),
            ], 'glyph'),
        ]
    if icon == 'trophy':
        return [
            ('polygon', [(0.30, 0.90), (0.70, 0.90), (0.58, 0.60), (0.42, 0.60)], 'glyph'),
            ('circle', 0.19, 0.78, 0.11, 'glyph'),
            ('circle', 0.19, 0.78, 0.065, 'accent'),
            ('circle', 0.81, 0.78, 0.11, 'glyph'),
            ('circle', 0.81, 0.78, 0.065, 'accent'),
            ('polygon', [(0.46, 0.35), (0.54, 0.35), (0.54, 0.60), (0.46, 0.60)], 'glyph'),
            ('polygon', [(0.32, 0.22), (0.68, 0.22), (0.68, 0.35), (0.32, 0.35)], 'glyph'),
        ]
    if icon == 'zap':
        return [
            ('polygon', [
                (0.58, 0.95), (0.25, 0.48), (0.45, 0.48),
                (0.35, 0.05), (0.75, 0.55), (0.52, 0.55),
            ], 'glyph'),
        ]
    if icon == 'sparkles':
        return [
            ('polygon', _diamond_points(0.5, 0.55, 0.30), 'glyph'),
            ('polygon', _diamond_points(0.80, 0.26, 0.13), 'glyph'),
            ('polygon', _diamond_points(0.20, 0.80, 0.11), 'glyph'),
        ]
    # Fallback: simple circle-in-circle
    return [('circle', 0.5, 0.5, 0.28, 'glyph')]


def icon_color(icon: str) -> str:
    return ICON_COLORS.get(icon, DEFAULT_COLOR)


# ── PDF renderer (reportlab vector Drawing) ─────────────────────────────────
def draw_badge_drawing(icon: str, size: float = 26, muted: bool = False) -> Drawing:
    """A self-contained square Drawing: coloured circular medallion + glyph.
    `muted` renders a greyed-out version for badges not yet earned."""
    hexc = DEFAULT_COLOR if muted else icon_color(icon)
    fill = rl_colors.HexColor(hexc)
    ring = rl_colors.HexColor(hexc).clone()
    ring.alpha = 0.55
    glyph_color = rl_colors.HexColor('#f4f4f5') if not muted else rl_colors.HexColor('#d1d5db')
    accent_color = fill

    d = Drawing(size, size)
    cx = cy = size / 2
    r = size / 2

    d.add(Circle(cx, cy, r, fillColor=fill, strokeColor=rl_colors.white, strokeWidth=max(1, size * 0.035)))
    d.add(Circle(cx, cy, r * 0.98, fillColor=None, strokeColor=ring, strokeWidth=max(0.6, size * 0.02)))

    glyph_box = r * 1.28  # icon coordinates scaled into most of the circle
    ox, oy = cx - glyph_box / 2, cy - glyph_box / 2

    for part in _icon_recipe(icon):
        kind = part[0]
        tone = part[-1]
        color = accent_color if tone == 'accent' else glyph_color
        if kind == 'polygon':
            pts = part[1]
            flat = []
            for (px, py) in pts:
                flat.extend([ox + px * glyph_box, oy + py * glyph_box])
            d.add(Polygon(flat, fillColor=color, strokeColor=None))
        elif kind == 'circle':
            _, px, py, pr, _ = part
            d.add(Circle(ox + px * glyph_box, oy + py * glyph_box, pr * glyph_box,
                          fillColor=color, strokeColor=None))
        elif kind == 'line':
            _, x1, y1, x2, y2, w, _ = part
            d.add(Line(ox + x1 * glyph_box, oy + y1 * glyph_box,
                        ox + x2 * glyph_box, oy + y2 * glyph_box,
                        strokeColor=color, strokeWidth=w * glyph_box, strokeLineCap=1))
    return d


# ── Excel renderer (Pillow raster PNG) ──────────────────────────────────────
def _hex_to_rgba(hexc, alpha=255):
    hexc = hexc.lstrip('#')
    return (int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16), alpha)


def draw_badge_image(icon: str, size: int = 96, muted: bool = False) -> Image.Image:
    """Same recipe as draw_badge_drawing(), rasterized with Pillow at `size`
    px square (supersampled 4x then downscaled for smooth edges — no extra
    dependency needed for anti-aliasing)."""
    ss = 4
    px = size * ss
    hexc = DEFAULT_COLOR if muted else icon_color(icon)
    fill = _hex_to_rgba(hexc)
    glyph_color = (244, 244, 245, 255) if not muted else (209, 213, 219, 255)
    accent_color = fill

    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = px / 2
    r = px / 2 - ss

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=(255, 255, 255, 255), width=max(1, int(px * 0.035)))

    glyph_box = r * 1.28
    ox, oy_top = cx - glyph_box / 2, cy - glyph_box / 2

    def to_px(nx, ny):
        # recipe y-up -> PIL y-down
        return (ox + nx * glyph_box, oy_top + (1 - ny) * glyph_box)

    for part in _icon_recipe(icon):
        kind = part[0]
        tone = part[-1]
        color = accent_color if tone == 'accent' else glyph_color
        if kind == 'polygon':
            pts = [to_px(px_, py_) for (px_, py_) in part[1]]
            draw.polygon(pts, fill=color)
        elif kind == 'circle':
            _, cxr, cyr, prr, _ = part
            x, y = to_px(cxr, cyr)
            rad = prr * glyph_box
            draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=color)
        elif kind == 'line':
            _, x1, y1, x2, y2, w, _ = part
            p1 = to_px(x1, y1)
            p2 = to_px(x2, y2)
            draw.line([p1, p2], fill=color, width=max(1, int(w * glyph_box)))

    img = img.resize((size, size), Image.LANCZOS)
    return img


def badge_png_bytes(icon: str, size: int = 96, muted: bool = False) -> bytes:
    img = draw_badge_image(icon, size=size, muted=muted)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
