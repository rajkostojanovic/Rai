"""Development-only drawing and image-variant definitions for Rai.

This module holds the studio/backend surface that is intentionally kept
separate from the image-set-first performance workflow.
"""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

DEVELOPMENT_DRAW_TOOL_OPTIONS = (
    ("Select", "select"),
    ("Brush", "brush"),
    ("Line", "line"),
    ("Circle", "circle"),
    ("Rectangle", "rectangle"),
    ("Polygon", "polygon"),
)
DEVELOPMENT_DRAW_TOOL_VALUES = tuple(value for _, value in DEVELOPMENT_DRAW_TOOL_OPTIONS)

DEVELOPMENT_BRUSH_STYLE_OPTIONS = (
    ("Circle", "circle"),
    ("Square", "square"),
    ("Diagonal /", "diag_fwd"),
    ("Diagonal \\", "diag_back"),
    ("Cross", "cross"),
)
DEVELOPMENT_BRUSH_STYLE_VALUES = tuple(value for _, value in DEVELOPMENT_BRUSH_STYLE_OPTIONS)
DEVELOPMENT_BRUSH_STYLE_LABELS = {
    "circle": "Brush Circle",
    "square": "Brush Square",
    "diag_fwd": "Brush Diagonal /",
    "diag_back": "Brush Diagonal \\",
    "cross": "Brush Cross",
}

DEVELOPMENT_POLYGON_SIDE_OPTIONS = (3, 4, 5, 6, 8)

DEVELOPMENT_SHAPE_FILL_OPTIONS = (
    ("Empty", False),
    ("Filled", True),
)

DEVELOPMENT_SHAPE_TOOL_LABELS = {
    "line": "Line",
    "circle": "Circle",
    "rectangle": "Rectangle",
    "polygon": "Polygon",
}

IMAGE_VARIANT_PALETTE_OPTIONS = (
    ("Original", "original"),
    ("Warm", "warm"),
    ("Cool", "cool"),
    ("Neon", "neon"),
    ("Melancholic", "melancholic"),
)
IMAGE_VARIANT_PALETTE_VALUES = tuple(value for _, value in IMAGE_VARIANT_PALETTE_OPTIONS)

PERFORMANCE_WORKSPACE_NOTE = (
    "Performance workspace active: version 1 is image-set only. "
    "Rai is focused on Change > Photo Set and live timing/output controls."
)
DEVELOPMENT_WORKSPACE_NOTE = (
    "Further Development workspace active: studio/backend tools are available "
    "here for later drawing, stage authoring, shell design, palette work, and broader feature expansion."
)
PERFORMANCE_MODE_ACTIVE_NOTE = (
    "Performance mode is on. Version 1 is image-set only: Object studio tabs are hidden, "
    "stage editing is blocked, and the workspace is focused on Change > Photo Set."
)
PERFORMANCE_MODE_AVAILABLE_NOTE = (
    "Performance mode switches Rai into an image-set-only live workspace. "
    "Drawing, text, and stage-creation gestures are held back for later studio development."
)


def clean_image_variant_palette(value):
    mode = str(value).strip().lower()
    return mode if mode in IMAGE_VARIANT_PALETTE_VALUES else "original"


def default_image_variant_params(
    stroke_scale: float = 1.0,
    stroke_angle: float = 12.0,
    density: float = 0.55,
    shell_opacity: float = 0.50,
    palette_mode: str = "original",
    palette_mix: float = 0.72,
):
    try:
        stroke_scale = max(0.2, min(3.0, float(stroke_scale)))
    except Exception:
        stroke_scale = 1.0
    try:
        stroke_angle = max(-90.0, min(90.0, float(stroke_angle)))
    except Exception:
        stroke_angle = 12.0
    try:
        density = max(0.05, min(1.0, float(density)))
    except Exception:
        density = 0.55
    try:
        shell_opacity = max(0.0, min(1.0, float(shell_opacity)))
    except Exception:
        shell_opacity = 0.5
    try:
        palette_mix = max(0.0, min(1.0, float(palette_mix)))
    except Exception:
        palette_mix = 0.72

    return {
        "stroke_scale": stroke_scale,
        "stroke_angle": stroke_angle,
        "density": density,
        "shell_opacity": shell_opacity,
        "palette_mode": clean_image_variant_palette(palette_mode),
        "palette_mix": palette_mix,
    }


def normalize_image_variant_params(value):
    if not isinstance(value, dict):
        return default_image_variant_params()
    return default_image_variant_params(
        value.get("stroke_scale", 1.0),
        value.get("stroke_angle", 12.0),
        value.get("density", 0.55),
        value.get("shell_opacity", 0.50),
        value.get("palette_mode", "original"),
        value.get("palette_mix", 0.72),
    )


def default_image_variant_stage_presets():
    return [
        default_image_variant_params(1.55, 16.0, 0.58, 0.42, "warm", 0.72),
        default_image_variant_params(0.92, -26.0, 0.64, 0.54, "cool", 0.68),
        default_image_variant_params(1.24, 42.0, 0.82, 0.70, "neon", 0.88),
        default_image_variant_params(0.74, -48.0, 0.46, 0.48, "melancholic", 0.80),
    ]


def development_tool_is_brush(mode: str):
    return str(mode) == "brush"


def development_tool_is_polygon(mode: str):
    return str(mode) == "polygon"


def development_tool_is_shape(mode: str):
    return str(mode) in ("line", "circle", "rectangle", "polygon")


def is_development_brush_style(style: str):
    return str(style) in DEVELOPMENT_BRUSH_STYLE_VALUES


def is_development_polygon_side(value):
    try:
        return int(value) in DEVELOPMENT_POLYGON_SIDE_OPTIONS
    except Exception:
        return False


def development_draw_color(base_color: QColor, brightness: int, opacity: int, spray_alpha_scale: float = 1.0):
    base = QColor(base_color)
    h, s, v, _ = base.getHsv()
    if h < 0:
        h = 0
    v = int(max(0, min(255, round(v * (float(brightness) / 100.0)))))
    out = QColor.fromHsv(h, s, v)
    alpha = max(0, min(255, int(round(float(opacity) * float(spray_alpha_scale)))))
    out.setAlpha(alpha)
    return out


def development_stroke_size_from_pressure(base_size: int, pressure: float):
    pressure = max(0.0, min(1.0, float(pressure)))
    return max(1, int(int(base_size) * (0.25 + (1.75 * pressure))))


def development_spray_factor(spray: int):
    return max(0.0, min(1.0, float(spray) / 100.0))


def development_spray_spread(size: int, spray: int):
    return max(1.0, float(size) * math.sqrt(development_spray_factor(spray)))


def development_spray_step(size: int, spray: int):
    return max(1.0, development_spray_spread(size, spray) * 0.6)


def development_spray_color(color: QColor):
    out = QColor(color)
    out.setAlpha(max(1, int(out.alpha() * 0.2)))
    return out


def development_draw_spray_stamp(p: QPainter, center: QPointF, size: int, color: QColor, spray: int):
    spread = development_spray_spread(size, spray)
    count = max(2, min(240, int(math.pi * spread * spread * 0.03)))
    dot_size = max(1, int(size * 0.12))

    pen = QPen(development_spray_color(color), dot_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    for _ in range(count):
        angle = random.random() * math.tau
        radius = spread * (random.random() ** 0.5)
        x = center.x() + (math.cos(angle) * radius)
        y = center.y() + (math.sin(angle) * radius)
        p.drawPoint(QPointF(x, y))


def development_draw_spray_line(p: QPainter, a: QPointF, b: QPointF, size: int, color: QColor, spray: int):
    dx = b.x() - a.x()
    dy = b.y() - a.y()
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        development_draw_spray_stamp(p, a, size, color, spray)
        return

    step = development_spray_step(size, spray)
    samples = max(1, int(dist / step))
    for i in range(samples + 1):
        t = i / samples
        x = a.x() + (dx * t)
        y = a.y() + (dy * t)
        development_draw_spray_stamp(p, QPointF(x, y), size, color, spray)


def _development_midpoint(a: QPointF, b: QPointF):
    return QPointF((a.x() + b.x()) * 0.5, (a.y() + b.y()) * 0.5)


def _development_lerp_point(a: QPointF, b: QPointF, t: float):
    return QPointF(a.x() + ((b.x() - a.x()) * t), a.y() + ((b.y() - a.y()) * t))


def _development_quad_point(a: QPointF, control: QPointF, b: QPointF, t: float):
    omt = 1.0 - t
    x = (omt * omt * a.x()) + (2.0 * omt * t * control.x()) + (t * t * b.x())
    y = (omt * omt * a.y()) + (2.0 * omt * t * control.y()) + (t * t * b.y())
    return QPointF(x, y)


def _development_stroke_size_at(sizes, u: float, fallback_size: int):
    if not sizes:
        return max(1, int(fallback_size))

    if len(sizes) == 1:
        return max(1, int(sizes[0]))

    u = max(0.0, min(float(len(sizes) - 1), float(u)))
    lo = int(math.floor(u))
    hi = min(lo + 1, len(sizes) - 1)
    frac = u - lo
    size = sizes[lo] + ((sizes[hi] - sizes[lo]) * frac)
    return max(1, int(round(size)))


def _append_linear_stroke_samples(samples, a: QPointF, b: QPointF, ua: float, ub: float, sizes, fallback_size: int):
    dist = math.hypot(b.x() - a.x(), b.y() - a.y())
    avg_size = 0.5 * (
        _development_stroke_size_at(sizes, ua, fallback_size)
        + _development_stroke_size_at(sizes, ub, fallback_size)
    )
    step = max(1.0, avg_size * 0.16)
    count = max(1, int(math.ceil(dist / step)))
    for i in range(count + 1):
        if samples and i == 0:
            continue
        t = i / count
        pos = _development_lerp_point(a, b, t)
        u = ua + ((ub - ua) * t)
        samples.append((pos, _development_stroke_size_at(sizes, u, fallback_size)))


def _append_quadratic_stroke_samples(samples, a: QPointF, control: QPointF, b: QPointF, ua: float, ub: float, sizes, fallback_size: int):
    approx_len = (
        math.hypot(control.x() - a.x(), control.y() - a.y())
        + math.hypot(b.x() - control.x(), b.y() - control.y())
    )
    mid_u = 0.5 * (ua + ub)
    avg_size = (
        _development_stroke_size_at(sizes, ua, fallback_size)
        + _development_stroke_size_at(sizes, mid_u, fallback_size)
        + _development_stroke_size_at(sizes, ub, fallback_size)
    ) / 3.0
    step = max(1.0, avg_size * 0.16)
    count = max(1, int(math.ceil(approx_len / step)))
    for i in range(count + 1):
        if samples and i == 0:
            continue
        t = i / count
        pos = _development_quad_point(a, control, b, t)
        u = ua + ((ub - ua) * t)
        samples.append((pos, _development_stroke_size_at(sizes, u, fallback_size)))


def development_smoothed_stroke_samples(points, sizes, fallback_size: int):
    if not points:
        return []

    count = len(points)
    if not sizes:
        sizes = [fallback_size] * count
    else:
        sizes = [max(1, int(v)) for v in sizes[:count]]
        if len(sizes) < count:
            sizes.extend([sizes[-1]] * (count - len(sizes)))

    if count == 1:
        return [(QPointF(points[0]), max(1, int(sizes[0])))]

    samples = []
    if count == 2:
        _append_linear_stroke_samples(samples, points[0], points[1], 0.0, 1.0, sizes, fallback_size)
        return samples

    first_mid = _development_midpoint(points[0], points[1])
    _append_linear_stroke_samples(samples, points[0], first_mid, 0.0, 0.5, sizes, fallback_size)

    for i in range(1, count - 1):
        start = _development_midpoint(points[i - 1], points[i])
        end = _development_midpoint(points[i], points[i + 1])
        _append_quadratic_stroke_samples(samples, start, points[i], end, i - 0.5, i + 0.5, sizes, fallback_size)

    last_mid = _development_midpoint(points[-2], points[-1])
    _append_linear_stroke_samples(samples, last_mid, points[-1], count - 1.5, count - 1.0, sizes, fallback_size)
    return samples


def development_draw_brush_stamp(p: QPainter, pos: QPointF, size: int, color: QColor, style: str):
    if style == "circle":
        pen = QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.drawPoint(pos)
        return

    if style == "square":
        half = size / 2.0
        p.fillRect(QRectF(pos.x() - half, pos.y() - half, size, size), color)
        return

    pen_width = max(1, int(round(size * 0.18)))
    pen = QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    half = size / 2.0
    if style in ("diag_fwd", "cross"):
        p.drawLine(QPointF(pos.x() - half, pos.y() + half), QPointF(pos.x() + half, pos.y() - half))
    if style in ("diag_back", "cross"):
        p.drawLine(QPointF(pos.x() - half, pos.y() - half), QPointF(pos.x() + half, pos.y() + half))


def development_draw_brush_path(p: QPainter, a: QPointF, b: QPointF, size: int, color: QColor, style: str):
    dx = b.x() - a.x()
    dy = b.y() - a.y()
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        development_draw_brush_stamp(p, a, size, color, style)
        return

    step = max(1.0, size * 0.2)
    samples = max(1, int(dist / step))
    for i in range(samples + 1):
        t = i / samples
        x = a.x() + (dx * t)
        y = a.y() + (dy * t)
        development_draw_brush_stamp(p, QPointF(x, y), size, color, style)


def development_shape_pen(color: QColor, size: int, preview: bool = False):
    style = Qt.DashLine if preview else Qt.SolidLine
    return QPen(color, size, style, Qt.RoundCap, Qt.RoundJoin)


def development_regular_polygon(center: QPointF, vertex: QPointF, sides: int):
    dx = vertex.x() - center.x()
    dy = vertex.y() - center.y()
    radius = math.hypot(dx, dy)
    if radius < 1e-6:
        return QPolygonF([center])

    angle0 = math.atan2(dy, dx)
    step = (2.0 * math.pi) / max(3, int(sides))
    points = []
    for i in range(max(3, int(sides))):
        angle = angle0 + (i * step)
        x = center.x() + (radius * math.cos(angle))
        y = center.y() + (radius * math.sin(angle))
        points.append(QPointF(x, y))
    return QPolygonF(points)


def development_draw_shape_geometry(p: QPainter, tool: str, a: QPointF, b: QPointF, sides: int):
    if tool == "line":
        p.drawLine(a, b)
        return

    if tool == "circle":
        radius = math.hypot(b.x() - a.x(), b.y() - a.y())
        p.drawEllipse(a, radius, radius)
        return

    if tool == "rectangle":
        p.drawRect(QRectF(a, b).normalized())
        return

    if tool == "polygon":
        poly = development_regular_polygon(a, b, sides)
        if poly.count() >= 2:
            p.drawPolygon(poly)
        elif poly.count() == 1:
            p.drawPoint(poly.at(0))


def development_shape_segments(tool: str, a: QPointF, b: QPointF, size: int, spray: int, sides: int):
    if tool == "line":
        return [(QPointF(a), QPointF(b))]

    if tool == "circle":
        radius = math.hypot(b.x() - a.x(), b.y() - a.y())
        if radius < 1e-6:
            return [(QPointF(a), QPointF(a))]

        circumference = 2.0 * math.pi * radius
        point_count = max(24, min(2048, int(math.ceil(circumference / development_spray_step(size, spray)))))
        points = []
        for i in range(point_count):
            angle = (2.0 * math.pi * i) / point_count
            x = a.x() + (radius * math.cos(angle))
            y = a.y() + (radius * math.sin(angle))
            points.append(QPointF(x, y))
        return [(points[i], points[(i + 1) % point_count]) for i in range(point_count)]

    if tool == "rectangle":
        rect = QRectF(a, b).normalized()
        tl = rect.topLeft()
        tr = rect.topRight()
        br = rect.bottomRight()
        bl = rect.bottomLeft()
        return [(tl, tr), (tr, br), (br, bl), (bl, tl)]

    if tool == "polygon":
        poly = development_regular_polygon(a, b, sides)
        if poly.count() <= 0:
            return []
        if poly.count() == 1:
            pt = poly.at(0)
            return [(pt, pt)]
        return [(poly.at(i), poly.at((i + 1) % poly.count())) for i in range(poly.count())]

    return []


def development_draw_shape_spray(p: QPainter, tool: str, a: QPointF, b: QPointF, size: int, color: QColor, spray: int, sides: int):
    for start, end in development_shape_segments(tool, a, b, size, spray, sides):
        development_draw_spray_line(p, start, end, size, color, spray)


def development_lerp_color(start: QColor, end: QColor, t: float):
    mix = max(0.0, min(1.0, float(t)))
    return QColor(
        int(round(start.red() + ((end.red() - start.red()) * mix))),
        int(round(start.green() + ((end.green() - start.green()) * mix))),
        int(round(start.blue() + ((end.blue() - start.blue()) * mix))),
        int(round(start.alpha() + ((end.alpha() - start.alpha()) * mix))),
    )


def development_effective_image_variant_params(params, audio_low: float, audio_mid: float, audio_high: float, beat_pulse: float):
    variant = normalize_image_variant_params(params)
    low = max(0.0, min(1.0, float(audio_low)))
    mid = max(0.0, min(1.0, float(audio_mid)))
    high = max(0.0, min(1.0, float(audio_high)))
    pulse = max(0.0, min(1.0, float(beat_pulse)))
    return default_image_variant_params(
        stroke_scale=variant["stroke_scale"] * (1.0 + (0.85 * low) + (0.45 * pulse)),
        stroke_angle=variant["stroke_angle"] + ((high - 0.25) * 54.0),
        density=variant["density"] * (0.76 + (0.32 * low) + (0.48 * high)),
        shell_opacity=variant["shell_opacity"] * (0.72 + (0.40 * mid)),
        palette_mode=variant["palette_mode"],
        palette_mix=variant["palette_mix"] * (0.82 + (0.34 * mid)),
    )


def development_palette_shift_color(color: QColor, mode: str, mix: float):
    base = QColor(color)
    mix = max(0.0, min(1.0, float(mix)))
    if mode == "original" or mix <= 1e-6:
        return base

    h, s, v, a = base.getHsv()
    if h < 0:
        h = 0

    if mode == "warm":
        target = QColor.fromHsv(22, min(255, int((s * 0.85) + 85)), min(255, int((v * 1.05) + 18)), a)
    elif mode == "cool":
        target = QColor.fromHsv(205, min(255, int((s * 0.78) + 55)), min(255, int((v * 0.98) + 8)), a)
    elif mode == "neon":
        target = QColor.fromHsv((h + 138) % 360, min(255, int((s * 1.15) + 70)), min(255, int((v * 1.22) + 32)), a)
    elif mode == "melancholic":
        target = QColor.fromHsv(220, min(180, int((s * 0.42) + 20)), max(24, min(220, int((v * 0.78) + 6))), a)
    else:
        target = QColor(base)

    out = development_lerp_color(base, target, mix)
    out.setAlpha(base.alpha())
    return out


def development_draw_image_variant_object(
    p: QPainter,
    obj,
    audio_low: float,
    audio_mid: float,
    audio_high: float,
    beat_pulse: float,
):
    rect = QRectF(obj.get("rect", QRectF()))
    core_image = obj.get("core_image")
    samples = obj.get("variant_samples", [])
    if rect.isNull() or core_image is None or core_image.isNull():
        return

    object_alpha = QColor(obj.get("color", QColor(255, 255, 255))).alphaF()
    if object_alpha <= 1e-6:
        return

    variant_key = str(obj.get("variant_key", "")).strip()
    shell_images = obj.get("variant_shell_images", {})
    if isinstance(shell_images, dict) and variant_key in shell_images:
        shell_image = shell_images.get(variant_key)
        if shell_image is not None and not shell_image.isNull():
            p.save()
            p.setOpacity(object_alpha)
            p.drawImage(rect, shell_image)
            p.drawImage(rect, core_image)
            p.restore()
            return

    p.save()
    p.setOpacity(object_alpha)
    p.drawImage(rect, core_image)
    p.restore()

    if not samples:
        return

    params = development_effective_image_variant_params(
        obj.get("variant_params"),
        audio_low,
        audio_mid,
        audio_high,
        beat_pulse,
    )
    shell_opacity = max(0.0, min(1.0, params["shell_opacity"] * object_alpha))
    if shell_opacity <= 1e-6:
        return

    sample_count = max(1, int(round(len(samples) * params["density"])))
    sample_count = max(1, min(len(samples), sample_count))
    base_extent = max(1.0, min(rect.width(), rect.height()))
    stroke_mass = max(1.2, base_extent * 0.0115 * params["stroke_scale"])
    stroke_angle = math.radians(params["stroke_angle"])
    direction = QPointF(math.cos(stroke_angle), math.sin(stroke_angle))
    center = rect.center()

    for nx, ny, size_bias, rgba in samples[:sample_count]:
        pos = QPointF(center.x() + (nx * rect.width()), center.y() + (ny * rect.height()))
        source_color = QColor.fromRgba(int(rgba))
        shell_color = development_palette_shift_color(source_color, params["palette_mode"], params["palette_mix"])
        radial = min(1.0, math.hypot(nx * 1.15, ny * 1.15) * 1.35)
        local_alpha = shell_opacity * (0.22 + (0.78 * radial))
        shell_color.setAlpha(max(0, min(255, int(round(shell_color.alpha() * local_alpha)))))
        if shell_color.alpha() <= 0:
            continue

        stroke_length = stroke_mass * (1.25 + (0.70 * size_bias))
        pen_width = max(1.0, stroke_mass * (0.42 + (0.35 * size_bias)))
        start = QPointF(
            pos.x() - (direction.x() * stroke_length * 0.5),
            pos.y() - (direction.y() * stroke_length * 0.5),
        )
        end = QPointF(
            pos.x() + (direction.x() * stroke_length * 0.5),
            pos.y() + (direction.y() * stroke_length * 0.5),
        )
        p.setPen(QPen(shell_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(start, end)
