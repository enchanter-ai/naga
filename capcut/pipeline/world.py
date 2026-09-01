"""Procedural voxel world generation. Python 3.8+ stdlib only.

Deterministic: the same seed yields the same world on every machine, which
is what makes a render reproducible and a re-render diffable.
"""

import math

# --- block ids -------------------------------------------------------------
AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
COBBLE = 4
SAND = 5
WATER = 6
LOG = 7
LEAVES = 8
PLANK = 9
TORCH = 10
CLOUD = 11
GLOWSTONE = 12

# Per-block face palettes: (top, side, bottom) base RGB.
PALETTE = {
    GRASS:     ((106, 170, 80), (134, 96, 67), (134, 96, 67)),
    DIRT:      ((134, 96, 67), (134, 96, 67), (134, 96, 67)),
    STONE:     ((128, 128, 128), (122, 122, 122), (118, 118, 118)),
    COBBLE:    ((130, 130, 130), (124, 124, 124), (120, 120, 120)),
    SAND:      ((219, 207, 163), (214, 202, 158), (210, 198, 154)),
    WATER:     ((58, 108, 196), (52, 98, 182), (48, 92, 172)),
    LOG:       ((150, 120, 74), (102, 81, 50), (150, 120, 74)),
    LEAVES:    ((60, 143, 54), (54, 130, 48), (48, 118, 44)),
    PLANK:     ((162, 130, 78), (156, 124, 74), (150, 118, 70)),
    TORCH:     ((255, 214, 120), (196, 148, 74), (150, 110, 60)),
    CLOUD:     ((246, 248, 252), (232, 236, 244), (214, 220, 232)),
    GLOWSTONE: ((255, 214, 130), (243, 199, 112), (232, 186, 100)),
}

# Texel noise amplitude per block: how mottled a face reads up close.
ROUGHNESS = {
    GRASS: 14, DIRT: 16, STONE: 12, COBBLE: 22, SAND: 8, WATER: 6,
    LOG: 14, LEAVES: 26, PLANK: 10, TORCH: 10, CLOUD: 4, GLOWSTONE: 18,
}

# Blocks that do not occlude the face of the neighbour behind them.
TRANSPARENT = {AIR, WATER, LEAVES, TORCH, CLOUD}

# Blocks that emit their own light and so ignore face shading and fog tint.
EMISSIVE = {TORCH, GLOWSTONE}

# Non-unit block bounds as (x0, y0, z0, x1, y1, z1) in block-local space.
BOUNDS = {
    TORCH: (0.40, 0.0, 0.40, 0.60, 0.62, 0.60),
}


def _hash2(x, z, seed):
    h = (x * 374761393 + z * 668265263 + seed * 144665) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise(x, z, seed):
    xi, zi = math.floor(x), math.floor(z)
    xf, zf = x - xi, z - zi
    u, v = _smooth(xf), _smooth(zf)
    a = _hash2(xi, zi, seed)
    b = _hash2(xi + 1, zi, seed)
    c = _hash2(xi, zi + 1, seed)
    d = _hash2(xi + 1, zi + 1, seed)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def fbm(x, z, seed, octaves=4, lacunarity=2.0, gain=0.5):
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * _value_noise(x * freq, z * freq, seed + o * 101)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


class World:
    """A sparse voxel world plus its precomputed exposed-face list."""

    def __init__(self, seed=20260901, radius=44, sea_level=6):
        self.seed = seed
        self.radius = radius
        self.sea_level = sea_level
        self.blocks = {}
        self.heights = {}
        self._generate()
        self.faces = self._build_faces()

    # -- generation ---------------------------------------------------------
    def _height(self, x, z):
        base = fbm(x * 0.045, z * 0.045, self.seed, octaves=4)
        ridge = fbm(x * 0.012, z * 0.012, self.seed + 7, octaves=2)
        h = 2.0 + base * 12.0 + ridge * 7.0
        # Carve a basin through the middle so the lake has somewhere to sit.
        d = math.hypot(x - 4, z - 2)
        h -= max(0.0, 7.0 - d * 0.42) * 1.5
        return int(h)

    def _set(self, x, y, z, bid):
        self.blocks[(x, y, z)] = bid

    def _generate(self):
        r, sea = self.radius, self.sea_level
        for x in range(-r, r + 1):
            for z in range(-r, r + 1):
                h = self._height(x, z)
                self.heights[(x, z)] = h
                # Only the top few layers are ever visible; skip the rest so
                # the face pass stays cheap.
                for y in range(max(h - 2, -4), h + 1):
                    if y == h:
                        if h <= sea:
                            top = SAND
                        elif h <= sea + 1:
                            top = SAND
                        else:
                            top = GRASS
                    elif y >= h - 1:
                        top = DIRT
                    else:
                        top = STONE
                    self._set(x, y, z, top)
                for y in range(h + 1, sea + 1):
                    self._set(x, y, z, WATER)

        self._plant_trees()
        self._build_tower()
        self._make_clouds()

    def _plant_trees(self):
        r = self.radius
        for x in range(-r + 2, r - 1):
            for z in range(-r + 2, r - 1):
                if _hash2(x, z, self.seed + 991) > 0.976:
                    # Keep a clearing around the tower so the hero object is
                    # never swallowed by canopy on the orbit.
                    if math.hypot(x - 0, z + 14) < 10.0:
                        continue
                    h = self.heights.get((x, z))
                    if h is None or h <= self.sea_level + 1:
                        continue
                    if self.blocks.get((x, h, z)) != GRASS:
                        continue
                    self._tree(x, h + 1, z)

    def _tree(self, x, y, z):
        trunk = 4 + int(_hash2(x, z, self.seed + 13) * 3)
        for i in range(trunk):
            self._set(x, y + i, z, LOG)
        crown = y + trunk
        for dy in range(-2, 2):
            rad = 2 if dy < 0 else 1
            for dx in range(-rad, rad + 1):
                for dz in range(-rad, rad + 1):
                    if abs(dx) == rad and abs(dz) == rad and rad > 1:
                        continue
                    p = (x + dx, crown + dy, z + dz)
                    if self.blocks.get(p) in (None, AIR):
                        self._set(p[0], p[1], p[2], LEAVES)
        self._set(x, crown + 1, z, LEAVES)

    def _build_tower(self):
        """A small cobblestone tower with the scene's title torch on top."""
        cx, cz = 0, -14
        ground = self.heights.get((cx, cz), 8)
        base = max(ground, self.sea_level + 1)
        self.tower = (cx, cz, base)
        height = 9
        for y in range(base, base + height):
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    edge = abs(dx) == 2 or abs(dz) == 2
                    if not edge:
                        continue
                    if abs(dx) == 2 and abs(dz) == 2:
                        bid = COBBLE
                    else:
                        bid = COBBLE if (y + dx + dz) % 5 else STONE
                    self._set(cx + dx, y, cz + dz, bid)
        # Battlement floor and crenellations.
        top = base + height
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                self._set(cx + dx, top - 1, cz + dz, PLANK)
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                if (abs(dx) == 2 or abs(dz) == 2) and (dx + dz) % 2 == 0:
                    self._set(cx + dx, top, cz + dz, COBBLE)
        self._set(cx, top, cz, GLOWSTONE)
        self._set(cx, top + 1, cz, TORCH)
        self.torch_pos = (cx + 0.5, top + 1.35, cz + 0.5)

    def _make_clouds(self):
        """Cloud slabs live in their own list so they can drift per frame."""
        self.clouds = []
        for cx in range(-6, 7):
            for cz in range(-6, 7):
                if _hash2(cx, cz, self.seed + 555) > 0.70:
                    self.clouds.append((cx * 7, 41, cz * 7))

    # -- face extraction ----------------------------------------------------
    def _build_faces(self):
        """Return [(x, y, z, bid, mask)] for every block with an exposed face.

        mask bits: 1 +Y (top), 2 -Y, 4 +X, 8 -X, 16 +Z, 32 -Z.
        """
        out = []
        get = self.blocks.get
        for (x, y, z), bid in self.blocks.items():
            if bid == AIR:
                continue
            mask = 0
            for bit, (dx, dy, dz) in (
                (1, (0, 1, 0)), (2, (0, -1, 0)), (4, (1, 0, 0)),
                (8, (-1, 0, 0)), (16, (0, 0, 1)), (32, (0, 0, -1)),
            ):
                n = get((x + dx, y + dy, z + dz), AIR)
                if n == bid and bid in (WATER, LEAVES):
                    continue  # don't draw interior faces of a translucent mass
                if n in TRANSPARENT:
                    mask |= bit
            if mask:
                out.append((x, y, z, bid, mask))
        return out

    # -- camera helpers -----------------------------------------------------
    def surface_y(self, x, z):
        """Terrain height at a world column, sampled with bilinear smoothing
        so a moving camera rides the ground instead of stepping over it."""
        xi, zi = math.floor(x), math.floor(z)
        fx, fz = x - xi, z - zi
        h = self.heights
        r = self.radius

        def at(a, b):
            a = max(-r, min(r, a))
            b = max(-r, min(r, b))
            return h.get((a, b), self.sea_level)

        top = at(xi, zi) * (1 - fx) + at(xi + 1, zi) * fx
        bot = at(xi, zi + 1) * (1 - fx) + at(xi + 1, zi + 1) * fx
        return top * (1 - fz) + bot * fz

    def is_solid(self, x, y, z):
        b = self.blocks.get((math.floor(x), math.floor(y), math.floor(z)), AIR)
        return b != AIR and b not in (WATER,)

    def clear_camera(self, pos, margin=2.6, max_lift=9.0):
        """Lift a camera position out of terrain or foliage.

        Keyframes are authored by eye against a procedural world; without
        this, one bad seed puts the lens inside a hill.
        """
        x, y, z = pos
        floor_y = max(self.surface_y(x, z), self.sea_level) + margin
        if y < floor_y:
            y = floor_y
        lifted = 0.0
        while lifted < max_lift and (
                self.is_solid(x, y, z) or self.is_solid(x, y + 0.9, z)):
            y += 0.6
            lifted += 0.6
        return (x, y, z)
