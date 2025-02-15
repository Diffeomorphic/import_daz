# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
BLENDER3 = (bpy.app.version < (4,0,0))

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
    S_TWEAK = 2
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
    S_TWEAK = "Tweak"
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
    S_TWEAK : "Tweak",
    S_SPECIAL : "Special",
    S_HIDDEN : "Hidden"
}
