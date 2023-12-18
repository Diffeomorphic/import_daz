# Copyright (c) 2016-2023, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

import bpy
BLENDER3 = (bpy.app.version < (4,0,0))

#-------------------------------------------------------------
#   MHX Layers
#-------------------------------------------------------------

if BLENDER3:
    L_MAIN =    0
    L_SPINE =   1

    L_LARMIK =  2
    L_LARMFK =  3
    L_LLEGIK =  4
    L_LLEGFK =  5
    L_LHAND =   6
    L_LFINGER = 7
    L_LEXTRA =  12
    L_LTOE =    13

    L_RARMIK =  18
    L_RARMFK =  19
    L_RLEGIK =  20
    L_RLEGFK =  21
    L_RHAND =   22
    L_RFINGER = 23
    L_REXTRA =  28
    L_RTOE =    29

    L_FACE =    8
    L_TWEAK =   9
    L_HEAD =    10
    L_UNUSED =  11
    L_CUSTOM =  16
    L_CUSTOM2 = 17

    L_HELP =    14
    L_HELP2 =   15
    L_HIDDEN =  30
    L_DEF =     31
else:
    L_MAIN =    "Root"
    L_SPINE =   "Spine"

    L_LARMIK =  "IK Arm Left"
    L_LARMFK =  "FK Arm Left"
    L_LLEGIK =  "IK Leg Left"
    L_LLEGFK =  "FK Leg Left"
    L_LHAND =   "Hand Left"
    L_LFINGER = "Fingers Left"
    L_LEXTRA =  "Extra Left"
    L_LTOE =    "Toes Left"

    L_RARMIK =  "IK Arm Right"
    L_RARMFK =  "FK Arm Right"
    L_RLEGIK =  "IK Leg Right"
    L_RLEGFK =  "FK Leg Right"
    L_RHAND =   "Hand Right"
    L_RFINGER = "Fingers Right"
    L_REXTRA =  "Extra Right"
    L_RTOE =    "Toes Right"

    L_FACE =    "Face"
    L_TWEAK =   "Tweak"
    L_HEAD =    "Head"
    L_UNUSED =  "Unused"
    L_CUSTOM =  "Custom"
    L_CUSTOM2 = "Custom 2"

    L_HELP =    "Help"
    L_HELP2 =   "Help 2"
    L_HIDDEN =   "Hidden"
    L_DEF =     "Deform"


MhxLayers = {
    L_MAIN :    "Root",
    L_SPINE :   "Spine",

    L_LARMIK :  "IK Arm Left",
    L_LARMFK :  "FK Arm Left",
    L_LLEGIK :  "IK Leg Left",
    L_LLEGFK :  "FK Leg Left",
    L_LHAND :   "Hand Left",
    L_LFINGER : "Fingers Left",
    L_LEXTRA :  "Extra Left",
    L_LTOE :    "Toes Left",

    L_RARMIK :  "IK Arm Right",
    L_RARMFK :  "FK Arm Right",
    L_RLEGIK :  "IK Leg Right",
    L_RLEGFK :  "FK Leg Right",
    L_RHAND :   "Hand Right",
    L_RFINGER : "Fingers Right",
    L_REXTRA :  "Extra Right",
    L_RTOE :    "Toes Right",

    L_FACE :    "Face",
    L_TWEAK :   "Tweak",
    L_HEAD :    "Head",
    L_UNUSED :  "Unused",
    L_CUSTOM :  "Custom",
    L_CUSTOM2 : "Custom 2",

    L_HELP :    "Help",
    L_HELP2 :   "Help 2",
    L_DEF :     "Deform",
}

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


MhxRigifyLayer = {
    L_HELP : R_HELP,
    L_HELP2 : R_HELP,
    L_FACE : R_DETAIL,
    L_HEAD : R_FACE,
    L_CUSTOM : R_CUSTOM,
    L_TWEAK : R_CUSTOM,
    L_DEF : R_DEF,
}

#-------------------------------------------------------------
#   Simple layers
#-------------------------------------------------------------

if BLENDER3:
    S_SPINE = 16
    S_FACE = 17
    S_LARMFK = 18
    S_RARMFK = 19
    S_LLEGFK = 20
    S_RLEGFK = 21
    S_LHAND = 22
    S_RHAND = 23
    S_LFOOT = 24
    S_RFOOT = 25
    S_LARMIK = 26
    S_RARMIK = 27
    S_LLEGIK = 28
    S_RLEGIK = 29
    S_SPECIAL = 30
    S_HIDDEN = 31
else:
    S_SPINE = "Spine"
    S_FACE = "Face"
    S_LARMFK = "FK Arm Left"
    S_RARMFK = "FK Arm Right"
    S_LLEGFK = "FK Leg Left"
    S_RLEGFK = "FK Leg Right"
    S_LHAND = "Hand Left"
    S_RHAND = "Hand Right"
    S_LFOOT = "Foot Left"
    S_RFOOT = "Foot Right"
    S_LARMIK = "IK Arm Left"
    S_RARMIK = "IK Arm Right"
    S_LLEGIK = "IK Leg Left"
    S_RLEGIK = "IK Leg Right"
    S_SPECIAL = "Special"
    S_HIDDEN = "Hidden"


SimpleLayers = {
    S_SPINE : "Spine",
    S_FACE : "Face",
    S_LARMFK : "FK Arm Left",
    S_RARMFK : "FK Arm Right",
    S_LLEGFK : "FK Leg Left",
    S_RLEGFK : "FK Leg Right",
    S_LHAND : "Hand Left",
    S_RHAND : "Hand Right",
    S_LFOOT : "Foot Left",
    S_RFOOT : "Foot Right",
    S_LARMIK : "IK Arm Left",
    S_RARMIK : "IK Arm Right",
    S_LLEGIK : "IK Leg Left",
    S_RLEGIK : "IK Leg Right",
    S_SPECIAL : "Special",
    S_HIDDEN : "Hidden"
}

#-------------------------------------------------------------
#   Mha features
#-------------------------------------------------------------

F_TONGUE = 1
F_FINGER = 2
F_IDPROPS = 4
F_SPINE = 8
F_SHAFT = 16
F_NECK = 32