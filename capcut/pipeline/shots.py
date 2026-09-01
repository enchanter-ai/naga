"""Shot definitions and camera rigging.

A shot is a list of camera keyframes plus a lighting spec. Keyframes are
interpolated with an ease curve so moves start and stop softly rather than
snapping, which is the difference between a camera move and a slideshow.
"""

import json
import math
import os

from .render import Camera, resolve_tod


def ease_in_out(t):
    return t * t * (3.0 - 2.0 * t)


def ease_out(t):
    return 1.0 - (1.0 - t) ** 2.4


def ease_in(t):
    return t ** 2.2


def linear(t):
    return t


EASES = {"in_out": ease_in_out, "out": ease_out, "in": ease_in,
         "linear": linear}


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


class Shot:
    def __init__(self, spec, world):
        self.id = spec["id"]
        self.duration = float(spec["duration"])
        self.tod = spec["light"]
        self.fov = spec.get("fov", [70.0, 70.0])
        if not isinstance(self.fov, list):
            self.fov = [self.fov, self.fov]
        self.ease = EASES[spec.get("ease", "in_out")]
        self.caption = spec.get("caption")
        self.title = spec.get("title")
        self.subtitle = spec.get("subtitle")
        self.fade_in = float(spec.get("fade_in", 0.0))
        self.fade_out = float(spec.get("fade_out", 0.0))
        self.note = spec.get("note", "")
        self.world = world
        self.clamp = spec.get("ground_clamp", 2.6)
        self.orbit = spec.get("orbit")
        self.keys = spec.get("keys")

    def frames(self, fps):
        return max(1, int(round(self.duration * fps)))

    def camera(self, u):
        """Camera at normalised shot time `u` in [0, 1]."""
        e = self.ease(min(1.0, max(0.0, u)))
        fov = self.fov[0] + (self.fov[1] - self.fov[0]) * e
        if self.orbit:
            o = self.orbit
            cx, cy, cz = o["center"]
            ang = math.radians(o["start_deg"] + o["sweep_deg"] * e)
            rad = o["radius"][0] + (o["radius"][1] - o["radius"][0]) * e
            hgt = o["height"][0] + (o["height"][1] - o["height"][0]) * e
            pos = (cx + math.sin(ang) * rad, cy + hgt, cz + math.cos(ang) * rad)
            target = o.get("target", o["center"])
        else:
            k = self.keys
            n = len(k) - 1
            f = e * n
            i = min(int(f), n - 1)
            local = f - i
            pos = _lerp3(k[i]["pos"], k[i + 1]["pos"], local)
            target = _lerp3(k[i]["look"], k[i + 1]["look"], local)
        if self.clamp:
            pos = self.world.clear_camera(pos, margin=self.clamp)
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        dz = target[2] - pos[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        yaw = math.atan2(dx, -dz)
        pitch = math.asin(max(-1.0, min(1.0, dy / dist)))
        return Camera(pos, yaw, pitch, fov)

    def light(self, u):
        return resolve_tod(self.tod, self.ease(min(1.0, max(0.0, u))))


class Scene:
    def __init__(self, path, world):
        with open(path) as fh:
            spec = json.load(fh)
        self.spec = spec
        self.title = spec["title"]
        self.logline = spec.get("logline", "")
        self.fps = int(spec.get("fps", 24))
        self.width = int(spec.get("render_width", 640))
        self.height = int(spec.get("render_height", 360))
        self.upscale = int(spec.get("upscale", 2))
        self.seed = int(spec.get("seed", 20260901))
        self.transitions = spec.get("transitions", [])
        self.shots = [Shot(s, world) for s in spec["shots"]]

    @property
    def out_width(self):
        return self.width * self.upscale

    @property
    def out_height(self):
        return self.height * self.upscale

    def transition_after(self, index):
        for tr in self.transitions:
            if tr["after"] == self.shots[index].id:
                return tr
        return None
