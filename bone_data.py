# Copyright (c) 2016-2022, Thomas Larsson
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

#-------------------------------------------------------------
#   bone.py
#-------------------------------------------------------------

RollCorrection = {
    "lCollar" : 180,
    "lShldr" : -90,
    "lShldrBend" : -90,
    "lShldrTwist" : -90,
    "lHand" : -90,
    "lThumb1" : 180,
    "lThumb2" : 180,
    "lThumb3" : 180,

    "rCollar" : 180,
    "rShldr" : 90,
    "rShldrBend" : 90,
    "rShldrTwist" : 90,
    "rHand" : 90,
    "rThumb1" : 180,
    "rThumb2" : 180,
    "rThumb3" : 180,

    "l_shoulder" : 180,
    "l_upperarm" : -90,
    "l_upperarmtwist1" : -90,
    "l_upperarmtwist2" : -90,
    "l_hand" : -90,
    "l_thumb1" : 180,
    "l_thumb2" : 180,
    "l_thumb3" : 180,

    "r_shoulder" : 180,
    "r_upperarm" : 90,
    "r_upperarmtwist1" : 90,
    "r_upperarmtwist2" : 90,
    "r_hand" : 90,
    "r_thumb1" : 180,
    "r_thumb2" : 180,
    "r_thumb3" : 180,

    "lEar" : -90,
    "rEar" : 90,
    "l_ear" : -90,
    "r_ear" : 90,
}

RollCorrectionG12 = {
    "lEye" : 180,
    "rEye" : 180,
}

SocketBones = [
    "lShldr", "lShldrBend", "l_upperarm",
    "rShldr", "rShldrBend", "r_upperarm",
    "lThigh", "lThighBend", "l_thigh",
    "rThigh", "rThighBend", "r_thigh",
]

RotationModes = {
    "lShldr" : ("YXZ", False),
    "lShldrBend" : ("YXZ", False),
    "lShldrTwist" : ("YXZ", False),
    "lForearmTwist" : ("YZX", False),
    "lHand" : ("YXZ", False),

    "rShldr" : ("YXZ", True),
    "rShldrBend" : ("YXZ", True),
    "rShldrTwist" : ("YXZ", True),
    "rForearmTwist" : ("YZX", True),
    "rHand" : ("YXZ", True),

    "l_upperarm" : ("YXZ", False),
    "l_upperarmtwist1" : ("YXZ", False),
    "l_upperarmtwist2" : ("YXZ", False),
    "l_forearmtwist1" : ("YZX", False),
    "l_forearmtwist2" : ("YZX", False),
    "l_hand" : ("YXZ", False),

    "r_upperarm" : ("YXZ", True),
    "r_upperarmtwist1" : ("YXZ", True),
    "r_upperarmtwist2" : ("YXZ", True),
    "r_forearmtwist1" : ("YZX", True),
    "r_forearmtwist2" : ("YZX", True),
    "r_hand" : ("YXZ", True),
}

#-------------------------------------------------------------
#   Alternative bone names
#-------------------------------------------------------------

BoneMap = {
        "abdomen" : "abdomenLower",
        "abdomen2" : "abdomenUpper",
        "chest" : "chestLower",
        "chest_2" : "chestUpper",
        "neck" : "neckLower",
        "neck_2" : "neckUpper",

        "lShldr" : "lShldrBend",
        "lForeArm" : "lForearmBend",
        "lWrist" : "lForearmTwist",
        "lCarpal2-1" : "lCarpal2",
        "lCarpal2" : "lCarpal4",

        "rShldr" : "rShldrBend",
        "rForeArm" : "rForearmBend",
        "rWrist" : "rForearmTwist",
        "rCarpal2-1" : "rCarpal2",
        "rCarpal2" : "rCarpal4",

        "upperJaw" : "upperTeeth",
        "tongueBase" : "tongue01",
        "tongue01" : "tongue02",
        "tongue02" : "tongue03",
        "tongue03" : "tongue04",
        "MidBrowUpper" : "CenterBrow",

        "lLipCorver" : "lLipCorner",
        "lCheekLowerInner" : "lCheekLower",
        "lCheekUpperInner" : "lCheekUpper",
        "lEyelidTop" : "lEyelidUpper",
        "lEyelidLower_2" : "lEyelidLowerInner",
        "lNoseBirdge" : "lNasolabialUpper",

        "rCheekLowerInner" : "rCheekLower",
        "rCheekUpperInner" : "rCheekUpper",

        "lThigh" : "lThighBend",
        "lBigToe2" : "lBigToe_2",

        "rThigh" : "rThighBend",
        "rBigToe2" : "rBigToe_2",

        "Shaft 1" : "shaft1",
        "Shaft 2" : "shaft2",
        "Shaft 3" : "shaft3",
        "Shaft 4" : "shaft4",
        "Shaft 5" : "shaft5",
        "Shaft5" : "shaft5",
        "Shaft 6" : "shaft6",
        "Shaft 7" : "shaft7",
        "Left Testicle" : "lTesticle",
        "Right Testicle" : "rTesticle",
        "Scortum" : "scrotum",
        "Legs Crease" : "legsCrease",
        "Rectum" : "rectum1",
        "Rectum 1" : "rectum1",
        "Rectum 2" : "rectum2",
        "Colon" : "colon",
        "Root" : "shaftRoot",
        "root" : "shaftRoot",
}

#-------------------------------------------------------------
#   animation.py
#-------------------------------------------------------------

TwistDxs = {
    "lShldrTwist" : 0,
    "lForearmTwist" : 0,
    "lThighTwist" : 1,
    "rShldrTwist" : 0,
    "rForearmTwist" : 0,
    "rThighTwist" : 1,

    "l_upperarmtwist1" : 0,
    "l_forearmtwist1" : 0,
    "l_thightwist1" : 1,
    "r_upperarmtwist1" : 0,
    "r_forearmtwist1" : 0,
    "r_thightwist1" : 1,
}
