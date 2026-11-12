# SPDX-License-Identifier: GPL-2.0-or-later

"""Volume-based translucency colour for Iray Uber skin (experimental, Global Settings > Materials).

The base colour keeps the importer's colour-effect split (DAZ Color Effect group): a diffuse share m with colour Dn, the
rest translucent. With the switch on, the diffuse share is 1 - Translucency Weight also when the weight has a map, and
Scatter & Transmit Intensity uses the group's intensity output. The translucency colour T then enters as T^2 x K instead of
T^3.5, where K is the per-channel diffuse reflectance of a 2 cm deep layer of the interior as the importer's volume build
describes it: scattering from SSS Amount (Mono) or the logarithm of SSS Color (Chromatic) over Scattering Measurement
Distance, anisotropy SSS Direction, and absorption from Transmitted Color over Transmitted Measurement Distance (the colour
light keeps after that distance, times the mean of its map, if any). Colour values are linear (the value set in DAZ Studio
raised to 2.2); distances are in centimetres. A Translucency Weight of 0 gives a plain diffuse base colour.

The depth, the weight-0 behaviour and the overall result were checked against DAZ Studio renders under the same light.
"""

import numpy
from .volume_reflectance import reflectanceRGB, logCoefficient

DEPTH = 0.02    # metres


def _linear(color):
    return [max(0.0, float(c)) ** 2.2 for c in color[:3]]


def _mapMean(mat, key):
    """Linear mean colour of the texture map on a channel, or None."""
    from .material import getImage
    channel = mat.getChannel([key])
    url = mat.getImageFile(channel) if channel else None
    if not url:
        return None
    img = getImage(url)
    if img is None:
        return None
    small = img.copy()
    try:
        small.scale(64, 64)
        px = numpy.array(small.pixels[:]).reshape(-1, 4)[:, :3]
        if not small.is_float and small.colorspace_settings.name != 'Non-Color':
            px = numpy.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
        return px.mean(axis=0)
    finally:
        import bpy
        bpy.data.images.remove(small)


def interiorK(mat):
    """K of an Iray Uber material that is not thin walled."""
    sigmaA = [0.0, 0.0, 0.0]
    dt = float(mat.getValue(["Transmitted Measurement Distance"], 0) or 0)
    if dt > 0:
        tc = numpy.array(_linear(mat.getValue(["Transmitted Color"], (1.0, 1.0, 1.0))))
        mean = _mapMean(mat, "Transmitted Color")
        if mean is not None:
            tc = tc * mean
        sigmaA = logCoefficient(tc, dt * 0.01, 1e-4)
    sigmaS = [0.0, 0.0, 0.0]
    ds = float(mat.getValue(["Scattering Measurement Distance"], 0) or 0)
    if ds > 0:
        if int(mat.getValue(["SSS Mode"], 0) or 0) == 1:     # Chromatic
            sigmaS = logCoefficient(_linear(mat.getValue(["SSS Color"], (1.0, 1.0, 1.0))), ds * 0.01, 1e-4)
        else:                                                 # Mono
            amount = float(mat.getValue(["SSS Amount"], 0) or 0)
            sigmaS = [amount / (ds * 0.01)] * 3
    return reflectanceRGB(sigmaA, sigmaS, float(mat.getValue(["SSS Direction"], 0) or 0), DEPTH)
