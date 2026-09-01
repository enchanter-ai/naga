"""Minimal PNG writer and RGB frame buffer. Python 3.8+ stdlib only.

Brand invariant: zero external runtime deps. PNG is emitted by hand from
zlib + struct rather than pulling in Pillow.
"""

import struct
import zlib


class Frame:
    """Flat RGB byte buffer, row-major, 3 bytes per pixel."""

    __slots__ = ("w", "h", "buf")

    def __init__(self, w, h, fill=(0, 0, 0)):
        self.w = w
        self.h = h
        self.buf = bytearray(bytes(fill) * (w * h))

    def clone(self):
        f = Frame.__new__(Frame)
        f.w, f.h = self.w, self.h
        f.buf = bytearray(self.buf)
        return f

    def px(self, x, y, r, g, b):
        i = (y * self.w + x) * 3
        self.buf[i] = r
        self.buf[i + 1] = g
        self.buf[i + 2] = b

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return self.buf[i], self.buf[i + 1], self.buf[i + 2]

    def blend_px(self, x, y, r, g, b, a):
        """Alpha-composite a single pixel. `a` in [0,1]."""
        if a <= 0.0:
            return
        i = (y * self.w + x) * 3
        if a >= 1.0:
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b
            return
        ia = 1.0 - a
        self.buf[i] = int(self.buf[i] * ia + r * a)
        self.buf[i + 1] = int(self.buf[i + 1] * ia + g * a)
        self.buf[i + 2] = int(self.buf[i + 2] * ia + b * a)

    def scale_nearest(self, factor):
        """Nearest-neighbour upscale. Preserves the hard pixel edges that
        make the voxel look read as Minecraft rather than as blur."""
        if factor == 1:
            return self
        w, h, src = self.w, self.h, self.buf
        out = Frame(w * factor, h * factor)
        dst = out.buf
        dw3 = w * factor * 3
        for y in range(h):
            row = bytearray(dw3)
            base = y * w * 3
            o = 0
            for x in range(w):
                s = base + x * 3
                trip = src[s:s + 3]
                for _ in range(factor):
                    row[o:o + 3] = trip
                    o += 3
            top = y * factor
            for k in range(factor):
                start = (top + k) * dw3
                dst[start:start + dw3] = row
        return out


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path, frame, level=6):
    """Write `frame` as a non-interlaced 8-bit RGB PNG."""
    raw = bytearray()
    stride = frame.w * 3
    buf = frame.buf
    for y in range(frame.h):
        raw.append(0)  # filter type 0 (None)
        raw += buf[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", frame.w, frame.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), level))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
