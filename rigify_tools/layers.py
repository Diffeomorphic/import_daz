# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
BLENDER3 = (bpy.app.version < (4,0,0))

#-------------------------------------------------------------
#   Rigify Layers
#-------------------------------------------------------------

if BLENDER3:
    R_FACE = 1
    R_DETAIL = 2
    R_TORSO = 3
    R_TORSOTWEAK = 4
    R_ARMIK_L = 7
    R_ARMFK_L = 8
    R_ARMIK_R = 10
    R_ARMFK_R = 11
    R_LEGIK_L = 13
    R_LEGFK_L = 14
    R_LEGIK_R = 16
    R_LEGFK_R = 17
    R_CUSTOM = 19
    R_ROOT = 28
    R_DEF = 29
    R_HELP = 30
else:
    R_ROOT = "Root"
    R_FACE = "Face"
    R_DETAIL = "Face (Primary)"
    R_TORSO = "Torso"
    R_TORSOTWEAK = "Torso (Tweak)"
    R_ARMIK_L = "Arm.L (IK)"
    R_ARMIK_R = "Arm.R (IK)"
    R_LEGIK_L = "Leg.L (IK)"
    R_LEGIK_R = "Leg.R (IK)"
    R_ARMFK_L = "Arm.L (FK)"
    R_ARMFK_R = "Arm.R (FK)"
    R_LEGFK_L = "Leg.L (FK)"
    R_LEGFK_R = "Leg.R (FK)"
    R_CUSTOM = "Custom"
    R_HELP = "Help"
    R_DEF = "DEF"

RigifyLayers = {
    R_ROOT : "Root",
    R_TORSO : "Torso",
    R_TORSOTWEAK : "Torso (Tweak)",
    R_FACE : "Face",
    R_DETAIL : "Face (Primary)",
    R_ARMIK_L : "Arm.L (IK)",
    R_ARMIK_R : "Arm.R (IK)",
    R_LEGIK_L : "Leg.L (IK)",
    R_LEGIK_R : "Leg.R (IK)",
    R_CUSTOM : "Custom",
    R_HELP : "Help",
}
