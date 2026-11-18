# SPDX-License-Identifier: GPL-2.0-or-later

"""Volume-based translucency colour for PBR Skin (experimental, Global Settings > Materials).

Instead of the fixed power 3.5, the translucency colour T in the Extended Principled base colour mix becomes T^2 x K, where
K is the per-channel diffuse reflectance of the skin's interior: absorption from Transmitted Color over Transmitted
Measurement Distance, scattering from SSS Color over Scattering Measurement Distance (both -ln(colour) / distance, colour
values as set in DAZ Studio), Henyey-Greenstein anisotropy SSS Direction. Distances are in centimetres.
"""

from .volume_reflectance import reflectanceRGB, logCoefficient

# PBR Skin values a surface may leave unset
DEFAULTS = {
    "Translucency Enable": False,
    "Transmission Enable": False,
    "Transmitted Color": (0.0, 0.0, 0.0),
    "Transmitted Measurement Distance": 0.12,
    "Sub Surface Enable": False,
    "SSS Color": (0.976, 0.694, 0.761),
    "Scattering Measurement Distance": 0.015,
    "SSS Direction": 0.0,
}


def _value(mat, key):
    return mat.getValue([key], DEFAULTS[key])


def interiorK(mat):
    """K of a PBR Skin material; (1, 1, 1) when it has no interior (Translucency Enable off)."""
    if not _value(mat, "Translucency Enable"):
        return (1.0, 1.0, 1.0)
    sigmaA = [0.0, 0.0, 0.0]
    dt = float(_value(mat, "Transmitted Measurement Distance"))
    if _value(mat, "Transmission Enable") and dt > 0:
        sigmaA = logCoefficient(_value(mat, "Transmitted Color"), dt * 0.01, 1e-6)
    sigmaS = [0.0, 0.0, 0.0]
    ds = float(_value(mat, "Scattering Measurement Distance"))
    if _value(mat, "Sub Surface Enable") and ds > 0:
        sigmaS = logCoefficient(_value(mat, "SSS Color"), ds * 0.01, 1e-6)
    return reflectanceRGB(sigmaA, sigmaS, float(_value(mat, "SSS Direction")))


def bodyMaterial(mat):
    """The PBR Skin body material of the same figure, if any."""
    geonode = mat.geometry
    materials = getattr(geonode, "materials", None) or {}
    for name in ("body", "torso"):
        for key, other in materials.items():
            if key.lower() == name and other.shader == 'PBRSKIN':
                return other
    return None


def translucencyK(mat):
    """K for the translucency branch of `mat`, or None to keep the fixed power.

    PBR Skin surfaces use their own values. Other surfaces that get the same branch on a figure whose body is PBR Skin
    (add-on grafts, eye and mouth surfaces without PBR Skin values) use the body's values.
    """
    if mat.shader == 'PBRSKIN':
        return interiorK(mat)
    body = bodyMaterial(mat)
    return interiorK(body) if body is not None else None
