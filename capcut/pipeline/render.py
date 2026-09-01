"""Voxel rasteriser. Python 3.8+ stdlib only, no numpy.

Approach: every voxel face is an axis-aligned rectangle, so instead of
interpolating a polygon we project the face's corners to get a screen
bounding box and then solve the exact ray/plane intersection per pixel.
That yields exact depth and exact texel coordinates for free, and keeps
the inner loop to a handful of float ops.

Shading is deferred: the raster pass fills a G-buffer (block id, face,
texel u/v, depth) and a single resolve pass lights it, so overdrawn
pixels are never shaded twice.
"""

import math

from .pngio import Frame
from .world import (BOUNDS, EMISSIVE, PALETTE, ROUGHNESS, CLOUD, WATER,
                    LEAVES, TORCH, GLOWSTONE)

# Face indices and their outward normals.
FACE_TOP, FACE_BOTTOM, FACE_PX, FACE_NX, FACE_PZ, FACE_NZ = range(6)
_FACE_BITS = (1, 2, 4, 8, 16, 32)
_FACE_AXIS = (1, 1, 0, 0, 2, 2)          # constant axis per face
_FACE_SIGN = (1, -1, 1, -1, 1, -1)       # which side of the box
# Directional face brightness: the classic Minecraft "sides are darker" cue.
_FACE_SHADE = (1.0, 0.45, 0.66, 0.66, 0.84, 0.84)

NEAR = 0.05


def _norm(v):
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp3(a, b, t):
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


class TimeOfDay:
    """Lighting preset. Blend two of these to move the sun across a shot."""

    def __init__(self, sky_top, sky_horizon, sun_color, sun_dir, ambient,
                 fog_density, sun_size=0.9982, star_density=0.0):
        self.sky_top = sky_top
        self.sky_horizon = sky_horizon
        self.sun_color = sun_color
        self.sun_dir = _norm(sun_dir)
        self.ambient = ambient
        self.fog_density = fog_density
        self.sun_size = sun_size
        self.star_density = star_density


PRESETS = {
    "dawn": TimeOfDay((44, 62, 122), (240, 150, 96), (255, 196, 120),
                      (0.62, 0.16, -0.77), 0.52, 0.0130, 0.9975),
    "day": TimeOfDay((92, 156, 232), (176, 210, 244), (255, 246, 214),
                     (0.42, 0.78, -0.46), 0.72, 0.0072, 0.9990),
    "dusk": TimeOfDay((34, 42, 96), (232, 116, 74), (255, 152, 88),
                      (-0.68, 0.12, 0.72), 0.44, 0.0155, 0.9972),
    "night": TimeOfDay((9, 12, 32), (26, 34, 70), (150, 172, 224),
                       (-0.40, 0.62, 0.68), 0.24, 0.0180, 0.9994, 0.00055),
}


def blend_tod(a, b, t):
    """Interpolate two lighting presets, so a shot can cross sunset."""
    return TimeOfDay(
        _lerp3(a.sky_top, b.sky_top, t),
        _lerp3(a.sky_horizon, b.sky_horizon, t),
        _lerp3(a.sun_color, b.sun_color, t),
        _lerp3(a.sun_dir, b.sun_dir, t),
        _lerp(a.ambient, b.ambient, t),
        _lerp(a.fog_density, b.fog_density, t),
        _lerp(a.sun_size, b.sun_size, t),
        _lerp(a.star_density, b.star_density, t),
    )


def resolve_tod(spec, t):
    """`spec` is a name, or [name_a, name_b] to cross-fade across the shot."""
    if isinstance(spec, str):
        return PRESETS[spec]
    a, b = PRESETS[spec[0]], PRESETS[spec[1]]
    return blend_tod(a, b, t)


def _texel_hash(x, y, z, face, u, v):
    h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ (face * 2654435761)
    h ^= (u * 6971) ^ (v * 40499)
    h &= 0xFFFFFFFF
    h = (h ^ (h >> 15)) * 2246822519 & 0xFFFFFFFF
    return ((h ^ (h >> 13)) & 0xFFFF) / 65535.0


def build_static_boxes(world):
    """Convert the world's exposed-face list into renderable boxes once."""
    boxes = []
    for x, y, z, bid, mask in world.faces:
        b = BOUNDS.get(bid)
        if b:
            boxes.append((x + b[0], y + b[1], z + b[2],
                          x + b[3], y + b[4], z + b[5], bid, 63, x, y, z))
        else:
            boxes.append((x, y, z, x + 1.0, y + 1.0, z + 1.0, bid, mask, x, y, z))
    return boxes


def cloud_boxes(world, t):
    """Cloud slabs, drifting on the wind. Rebuilt per frame."""
    drift = t * 0.42
    out = []
    for i, (cx, cy, cz) in enumerate(world.clouds):
        x = cx + drift
        w = 5.0 + (i % 4)
        d = 4.0 + (i % 3)
        out.append((x, cy, cz, x + w, cy + 1.0, cz + d, CLOUD, 63,
                    int(cx), cy, int(cz)))
    return out


class Camera:
    def __init__(self, pos, yaw, pitch, fov=70.0):
        self.pos = pos
        self.yaw = yaw
        self.pitch = pitch
        self.fov = fov

    def basis(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        fwd = (sy * cp, sp, -cy * cp)
        right = (cy, 0.0, sy)
        up = (-sy * sp, cp, cp and cy * sp)
        # Recompute up as right x fwd to stay orthonormal at every pitch.
        up = (right[1] * fwd[2] - right[2] * fwd[1],
              right[2] * fwd[0] - right[0] * fwd[2],
              right[0] * fwd[1] - right[1] * fwd[0])
        return _norm(fwd), _norm(right), _norm(up)


def render_frame(world, static_boxes, cam, tod, width, height, t=0.0,
                 far=170.0, flicker=1.0):
    """Rasterise one frame and return a `Frame` at the internal resolution."""
    fwd, right, up = cam.basis()
    aspect = width / float(height)
    tan_h = math.tan(math.radians(cam.fov) * 0.5)
    ox, oy, oz = cam.pos

    # Per-pixel screen offsets, hoisted out of the face loop.
    sx_of = [((px + 0.5) / width * 2.0 - 1.0) * tan_h * aspect
             for px in range(width)]
    sy_of = [(1.0 - (py + 0.5) / height * 2.0) * tan_h for py in range(height)]
    # Ray direction components, separable per axis: d[a] = f[a] + r[a]*sx + u[a]*sy
    dxs = [right[0] * s for s in sx_of]
    dys = [right[1] * s for s in sx_of]
    dzs = [right[2] * s for s in sx_of]
    uxs = [up[0] * s for s in sy_of]
    uys = [up[1] * s for s in sy_of]
    uzs = [up[2] * s for s in sy_of]

    n = width * height
    zbuf = [far] * n
    g_bid = [0] * n
    g_face = [0] * n
    g_u = [0] * n
    g_v = [0] * n
    g_key = [0] * n

    boxes = static_boxes + cloud_boxes(world, t)
    fx, fy, fz = fwd

    # Cull, then sort front-to-back so the depth test rejects early.
    visible = []
    cos_cull = math.cos(math.radians(cam.fov) * 0.5 * aspect) - 0.55
    for bx0, by0, bz0, bx1, by1, bz1, bid, mask, wx, wy, wz in boxes:
        cxx = (bx0 + bx1) * 0.5 - ox
        cyy = (by0 + by1) * 0.5 - oy
        czz = (bz0 + bz1) * 0.5 - oz
        d2 = cxx * cxx + cyy * cyy + czz * czz
        if d2 > far * far:
            continue
        vf = cxx * fx + cyy * fy + czz * fz
        if vf < -2.0:
            continue
        dist = math.sqrt(d2) or 1e-6
        if dist > 3.0 and vf / dist < cos_cull:
            continue
        visible.append((vf, bx0, by0, bz0, bx1, by1, bz1, bid, mask,
                        wx, wy, wz, cxx, cyy, czz))
    visible.sort(key=lambda b: b[0])

    cam_c = (ox, oy, oz)
    fwd_c, right_c, up_c = fwd, right, up
    ax_offsets = (dxs, dys, dzs)
    ax_ups = (uxs, uys, uzs)

    for (_vf, bx0, by0, bz0, bx1, by1, bz1, bid, mask,
         wx, wy, wz, cxx, cyy, czz) in visible:
        lo = (bx0, by0, bz0)
        hi = (bx1, by1, bz1)
        rel = (cxx, cyy, czz)
        key = (wx * 73856093) ^ (wy * 19349663) ^ (wz * 83492791)
        for face in range(6):
            if not (mask & _FACE_BITS[face]):
                continue
            a = _FACE_AXIS[face]
            sign = _FACE_SIGN[face]
            # Backface: skip faces whose outward normal points away.
            if rel[a] * sign > 0.0:
                continue
            plane = hi[a] if sign > 0 else lo[a]
            b_ax = (a + 1) % 3
            c_ax = (a + 2) % 3
            b0, b1 = lo[b_ax], hi[b_ax]
            c0, c1 = lo[c_ax], hi[c_ax]

            # Screen bbox from the face's four corners.
            minx = miny = 1 << 30
            maxx = maxy = -(1 << 30)
            behind = False
            for pb in (b0, b1):
                for pc in (c0, c1):
                    p = [0.0, 0.0, 0.0]
                    p[a] = plane
                    p[b_ax] = pb
                    p[c_ax] = pc
                    vx = p[0] - cam_c[0]
                    vy = p[1] - cam_c[1]
                    vz = p[2] - cam_c[2]
                    vf2 = vx * fwd_c[0] + vy * fwd_c[1] + vz * fwd_c[2]
                    if vf2 <= NEAR:
                        behind = True
                        continue
                    vr = vx * right_c[0] + vy * right_c[1] + vz * right_c[2]
                    vu = vx * up_c[0] + vy * up_c[1] + vz * up_c[2]
                    px = int((vr / vf2 / (tan_h * aspect) + 1.0) * 0.5 * width)
                    py = int((1.0 - vu / vf2 / tan_h) * 0.5 * height)
                    if px < minx:
                        minx = px
                    if px > maxx:
                        maxx = px
                    if py < miny:
                        miny = py
                    if py > maxy:
                        maxy = py
            if behind:
                # Very near face: fall back to the full viewport; the exact
                # world-bounds test below still clips it correctly.
                minx, miny, maxx, maxy = 0, 0, width - 1, height - 1
            elif maxx < 0 or maxy < 0 or minx >= width or miny >= height:
                continue
            else:
                minx = 0 if minx < 0 else minx
                miny = 0 if miny < 0 else miny
                maxx = width - 1 if maxx >= width else maxx
                maxy = height - 1 if maxy >= height else maxy

            f_a, r_a, u_a = fwd_c[a], None, None
            da_row = ax_offsets[a]
            ua_col = ax_ups[a]
            db_row, ub_col = ax_offsets[b_ax], ax_ups[b_ax]
            dc_row, uc_col = ax_offsets[c_ax], ax_ups[c_ax]
            f_b, f_c = fwd_c[b_ax], fwd_c[c_ax]
            o_a, o_b, o_c = cam_c[a], cam_c[b_ax], cam_c[c_ax]
            plane_rel = plane - o_a
            span_b = b1 - b0
            span_c = c1 - c0
            inv_b = 16.0 / span_b if span_b else 0.0
            inv_c = 16.0 / span_c if span_c else 0.0

            for py in range(miny, maxy + 1):
                base_a = f_a + ua_col[py]
                base_b = f_b + ub_col[py]
                base_c = f_c + uc_col[py]
                row = py * width
                for px in range(minx, maxx + 1):
                    da = base_a + da_row[px]
                    if da == 0.0:
                        continue
                    tt = plane_rel / da
                    if tt <= NEAR:
                        continue
                    idx = row + px
                    if tt >= zbuf[idx]:
                        continue
                    pb = o_b + tt * (base_b + db_row[px])
                    if pb < b0 or pb > b1:
                        continue
                    pc = o_c + tt * (base_c + dc_row[px])
                    if pc < c0 or pc > c1:
                        continue
                    zbuf[idx] = tt
                    g_bid[idx] = bid
                    g_face[idx] = face
                    u = int((pb - b0) * inv_b)
                    v = int((pc - c0) * inv_c)
                    g_u[idx] = u if u < 16 else 15
                    g_v[idx] = v if v < 16 else 15
                    g_key[idx] = key

    return _resolve(world, zbuf, g_bid, g_face, g_u, g_v, g_key, width,
                    height, tod, fwd, right, up, tan_h, aspect, t, far, flicker)


def _resolve(world, zbuf, g_bid, g_face, g_u, g_v, g_key, width, height,
             tod, fwd, right, up, tan_h, aspect, t, far, flicker=1.0):
    """Light the G-buffer and paint the sky behind it."""
    frame = Frame(width, height)
    buf = frame.buf
    sun = tod.sun_dir
    amb = tod.ambient
    fogd = tod.fog_density
    sky_top, sky_hz = tod.sky_top, tod.sky_horizon
    sunc = tod.sun_color
    fog_r, fog_g, fog_b = sky_hz

    for py in range(height):
        sy = (1.0 - (py + 0.5) / height * 2.0) * tan_h
        row = py * width
        for px in range(width):
            idx = row + px
            i3 = idx * 3
            bid = g_bid[idx]
            if not bid:
                sx = ((px + 0.5) / width * 2.0 - 1.0) * tan_h * aspect
                dx = fwd[0] + right[0] * sx + up[0] * sy
                dy = fwd[1] + right[1] * sx + up[1] * sy
                dz = fwd[2] + right[2] * sx + up[2] * sy
                m = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                dx, dy, dz = dx / m, dy / m, dz / m
                k = dy * 0.5 + 0.5
                k = k * k
                r = sky_hz[0] + (sky_top[0] - sky_hz[0]) * k
                g = sky_hz[1] + (sky_top[1] - sky_hz[1]) * k
                b = sky_hz[2] + (sky_top[2] - sky_hz[2]) * k
                sd = dx * sun[0] + dy * sun[1] + dz * sun[2]
                if sd > tod.sun_size:
                    r, g, b = sunc
                elif sd > 0.90:
                    glow = ((sd - 0.90) / (tod.sun_size - 0.90)) ** 2 * 0.85
                    r += (sunc[0] - r) * glow
                    g += (sunc[1] - g) * glow
                    b += (sunc[2] - b) * glow
                if tod.star_density and dy > 0.02:
                    if _texel_hash(int(dx * 900), int(dy * 900),
                                   int(dz * 900), 5, 3, 7) < tod.star_density:
                        r, g, b = 236, 240, 255
                buf[i3] = 255 if r > 255 else (0 if r < 0 else int(r))
                buf[i3 + 1] = 255 if g > 255 else (0 if g < 0 else int(g))
                buf[i3 + 2] = 255 if b > 255 else (0 if b < 0 else int(b))
                continue

            face = g_face[idx]
            pal = PALETTE[bid]
            base = pal[0] if face == FACE_TOP else (
                pal[2] if face == FACE_BOTTOM else pal[1])
            shade = _FACE_SHADE[face]
            u, v = g_u[idx], g_v[idx]
            jitter = _texel_hash(g_key[idx], bid, face, face, u, v)
            rough = ROUGHNESS.get(bid, 10)
            off = (jitter - 0.5) * 2.0 * rough
            # Darken the outermost texel ring so block edges stay legible —
            # the grid is most of what reads as "Minecraft" at a distance.
            if u == 0 or u == 15 or v == 0 or v == 15:
                off -= 13.0

            if bid == WATER and face == FACE_TOP:
                # Shimmer: the lake is flat, so the motion lives in the colour.
                off += math.sin(t * 2.1 + g_key[idx] * 0.0007 + u * 0.55
                                + v * 0.31) * 11.0

            if bid in EMISSIVE:
                light = flicker
                fog = 0.0
            elif bid == CLOUD:
                # Clouds are lit ambiently; directional shading makes their
                # undersides read as grey slabs rather than cloud.
                light = 0.90 if face != FACE_BOTTOM else 0.80
                fog = 1.0 - math.exp(-zbuf[idx] * fogd * 0.35)
            else:
                nrm = _face_normal(face)
                ndl = nrm[0] * sun[0] + nrm[1] * sun[1] + nrm[2] * sun[2]
                if ndl < 0.0:
                    ndl = 0.0
                light = shade * (amb + (1.0 - amb) * ndl)
                fog = 1.0 - math.exp(-zbuf[idx] * fogd)
                if fog > 1.0:
                    fog = 1.0

            r = (base[0] + off) * light
            g = (base[1] + off) * light
            b = (base[2] + off) * light
            if fog:
                inv = 1.0 - fog
                r = r * inv + fog_r * fog
                g = g * inv + fog_g * fog
                b = b * inv + fog_b * fog
            buf[i3] = 255 if r > 255 else (0 if r < 0 else int(r))
            buf[i3 + 1] = 255 if g > 255 else (0 if g < 0 else int(g))
            buf[i3 + 2] = 255 if b > 255 else (0 if b < 0 else int(b))
    return frame


_NORMALS = ((0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))


def _face_normal(face):
    return _NORMALS[face]


def torch_flicker(t):
    """Emissive multiplier for the torch. Two detuned sines plus a hashed
    jitter, so the flame never settles into a visible loop."""
    a = math.sin(t * 11.3) * 0.5 + math.sin(t * 6.7 + 1.9) * 0.5
    j = _texel_hash(int(t * 90.0), 7, 3, 1, 5, 2)
    return 0.86 + 0.10 * a + 0.06 * j
