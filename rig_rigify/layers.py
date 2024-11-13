#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.


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
