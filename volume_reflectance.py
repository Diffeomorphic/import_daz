# SPDX-License-Identifier: GPL-2.0-or-later

"""Diffuse reflectance of a homogeneous scattering interior, per colour channel.

Light enters through the surface with a cosine-weighted direction (no refraction), scatters with a Henyey-Greenstein
phase function of anisotropy g, and counts when it leaves through the entry side. With a depth, light that leaves through
the far side is lost. A fixed-seed random walk, so a material always gets the same value; results are cached per input.
"""

import math
import numpy

_cache = {}


def _cosineDirections(n, rng):
    u1, u2 = rng.random(n), rng.random(n)
    r, phi = numpy.sqrt(u1), 2 * numpy.pi * u2
    return numpy.stack([r * numpy.cos(phi), r * numpy.sin(phi), numpy.sqrt(1 - u1)], axis=1)  # +z points inwards


def _scatter(d, g, rng):
    n = len(d)
    u = rng.random(n)
    if abs(g) < 1e-4:
        cost = 1 - 2 * u
    else:
        s = (1 - g * g) / (1 - g + 2 * g * u)
        cost = (1 + g * g - s * s) / (2 * g)
    sint = numpy.sqrt(numpy.clip(1 - cost ** 2, 0, 1))
    phi = 2 * numpy.pi * rng.random(n)
    a = numpy.where(numpy.abs(d[:, 2:3]) < 0.999, numpy.array([[0, 0, 1.0]]), numpy.array([[1.0, 0, 0]]))
    t1 = numpy.cross(a, d)
    t1 /= numpy.linalg.norm(t1, axis=1, keepdims=True)
    t2 = numpy.cross(d, t1)
    return sint[:, None] * (numpy.cos(phi)[:, None] * t1 + numpy.sin(phi)[:, None] * t2) + cost[:, None] * d


def reflectance(sigmaA, sigmaS, g, depth=None, paths=60000, seed=1):
    """Escaping energy fraction for one channel. sigmaA, sigmaS per metre, depth in metres (None = infinitely deep)."""
    key = (round(float(sigmaA), 6), round(float(sigmaS), 6), round(float(g), 6), depth, paths, seed)
    if key in _cache:
        return _cache[key]
    st = sigmaA + sigmaS
    if st <= 0:
        _cache[key] = 0.0
        return 0.0
    albedo = sigmaS / st
    rng = numpy.random.default_rng(seed)
    d = _cosineDirections(paths, rng)
    z = numpy.zeros(paths)
    w = numpy.ones(paths)
    out = 0.0
    alive = numpy.ones(paths, bool)
    for _ in range(5000):
        idx = numpy.nonzero(alive)[0]
        if len(idx) == 0:
            break
        step = -numpy.log(1 - rng.random(len(idx))) / st
        z[idx] += step * d[idx, 2]
        esc = z[idx] < 0
        out += w[idx[esc]].sum()
        if depth is not None:
            esc = esc | (z[idx] > depth)
        alive[idx[esc]] = False
        idx = idx[~esc]
        w[idx] *= albedo
        dead = w[idx] < 1e-4
        alive[idx[dead]] = False
        idx = idx[~dead]
        d[idx] = _scatter(d[idx], g, rng)
    value = float(out / paths)
    _cache[key] = value
    return value


def reflectanceRGB(sigmaA, sigmaS, g, depth=None):
    return tuple(reflectance(sigmaA[i], sigmaS[i], g, depth) for i in range(3))


def logCoefficient(color, distance, floor):
    """-ln(color) / distance per channel, the color clipped to [floor, 1]."""
    return [-math.log(min(max(float(c), floor), 1.0)) / distance for c in color[:3]]
