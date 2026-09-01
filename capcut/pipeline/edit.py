"""The edit: transitions, fades, titles, captions and the end card.

Everything here operates on the raw render buffers before upscale, except
type, which is drawn at output resolution so glyph edges stay sharp.
"""

import math

from .font import draw_text, text_width, GLYPH_H
from .pngio import Frame


def load_raw(path, w, h):
    f = Frame.__new__(Frame)
    f.w, f.h = w, h
    with open(path, "rb") as fh:
        f.buf = bytearray(fh.read())
    return f


def save_raw(path, frame):
    with open(path, "wb") as fh:
        fh.write(frame.buf)


def dissolve(a, b, t):
    """Cross-fade two frames. `t` 0 -> a, 1 -> b."""
    out = Frame(a.w, a.h)
    ab, bb, ob = a.buf, b.buf, out.buf
    inv = 1.0 - t
    for i in range(len(ab)):
        ob[i] = int(ab[i] * inv + bb[i] * t)
    return out


def fade_to(frame, t, color=(0, 0, 0)):
    """Fade `frame` toward `color`. `t` 0 -> unchanged, 1 -> solid colour."""
    if t <= 0.0:
        return frame
    buf = frame.buf
    inv = 1.0 - t
    cr, cg, cb = color
    tr, tg, tb = cr * t, cg * t, cb * t
    for i in range(0, len(buf), 3):
        buf[i] = int(buf[i] * inv + tr)
        buf[i + 1] = int(buf[i + 1] * inv + tg)
        buf[i + 2] = int(buf[i + 2] * inv + tb)
    return frame


def scrim(frame, y0, y1, strength=0.55, feather=16):
    """Darken a horizontal band so text over bright sky stays readable."""
    w = frame.w
    buf = frame.buf
    y0 = max(0, y0)
    y1 = min(frame.h, y1)
    inv = 1.0 - strength
    for y in range(y0, y1):
        # Feather the top and bottom few rows of the band.
        d = min(y - y0, y1 - 1 - y)
        s = strength * min(1.0, d / float(feather)) if d < feather else strength
        k = 1.0 - s
        base = y * w * 3
        for i in range(base, base + w * 3):
            buf[i] = int(buf[i] * k)
    return frame


def envelope(i, n, fps, hold_in=0.4, hold_out=0.4, delay=0.5, life=None):
    """Opacity ramp for a timed overlay within an n-frame shot."""
    t = i / float(fps)
    dur = n / float(fps)
    life = life if life is not None else dur - delay - 0.3
    if t < delay:
        return 0.0
    e = t - delay
    if e > life:
        return 0.0
    a = min(1.0, e / hold_in) if hold_in > 0 else 1.0
    b = min(1.0, (life - e) / hold_out) if hold_out > 0 else 1.0
    return max(0.0, min(a, b))


def draw_title(frame, title, subtitle, alpha):
    """Centred main title with a rule and a subtitle beneath it."""
    if alpha <= 0.0:
        return
    W, H = frame.w, frame.h
    scale = max(3, W // 210)
    sub_scale = max(1, scale // 2)
    tw = text_width(title, scale)
    ty = int(H * 0.40)
    scrim(frame, ty - scale * 7, ty + GLYPH_H * scale + scale * 12,
          0.42 * alpha, feather=scale * 5)
    draw_text(frame, title, (W - tw) // 2, ty, scale=scale,
              color=(255, 248, 232), shadow=(12, 10, 8), alpha=alpha)
    rule_y = ty + GLYPH_H * scale + scale * 5
    rule_w = int(tw * 0.55)
    for x in range((W - rule_w) // 2, (W + rule_w) // 2):
        for dy in range(max(1, scale // 3)):
            frame.blend_px(x, rule_y + dy, 255, 190, 90, alpha)
    if subtitle:
        sw = text_width(subtitle, sub_scale)
        draw_text(frame, subtitle, (W - sw) // 2,
                  rule_y + scale * 4, scale=sub_scale,
                  color=(236, 206, 150), shadow=(12, 10, 8), alpha=alpha)


def draw_caption(frame, text, alpha):
    """Lower-third caption on a feathered scrim."""
    if alpha <= 0.0:
        return
    W, H = frame.w, frame.h
    scale = max(2, W // 400)
    tw = text_width(text, scale)
    y = int(H * 0.84)
    scrim(frame, y - scale * 6, y + GLYPH_H * scale + scale * 6,
          0.50 * alpha, feather=scale * 5)
    draw_text(frame, text, (W - tw) // 2, y, scale=scale,
              color=(246, 246, 240), shadow=(10, 10, 12), alpha=alpha)


def end_card(width, height, line1, line2, alpha):
    """Standalone black end card."""
    f = Frame(width, height, (0, 0, 0))
    s1 = max(3, width // 240)
    s2 = max(1, s1 // 3)
    w1 = text_width(line1, s1)
    y1 = int(height * 0.44)
    draw_text(f, line1, (width - w1) // 2, y1, scale=s1,
              color=(255, 214, 120), shadow=None, alpha=alpha)
    rule_w = int(w1 * 0.7)
    for x in range((width - rule_w) // 2, (width + rule_w) // 2):
        f.blend_px(x, y1 + GLYPH_H * s1 + s1 * 2, 120, 96, 54, alpha)
    if line2:
        w2 = text_width(line2, s2)
        draw_text(f, line2, (width - w2) // 2,
                  y1 + GLYPH_H * s1 + s1 * 5, scale=s2,
                  color=(180, 178, 172), shadow=None, alpha=alpha)
    return f
