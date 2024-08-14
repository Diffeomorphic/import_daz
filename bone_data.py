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


#-------------------------------------------------------------
#   bone.py
#-------------------------------------------------------------

class BoneData:
    RollCorrection = {
        "lCollar" : 180,
        "lPectoral" : 180,
        "lShldr" : -90,
        "lShldrBend" : -90,
        "lShldrTwist" : -90,
        "lHand" : -90,
        "lThumb1" : 180,
        "lThumb2" : 180,
        "lThumb3" : 180,

        "rCollar" : 180,
        "rPectoral" : 180,
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
        "lCollar" : "YZX",
        "lShldr" : "YXZ",
        "lShldrBend" : "YXZ",
        "lShldrTwist" : "YXZ",
        "lHand" : "YXZ",

        "rCollar" : "YZX",
        "rShldr" : "YXZ",
        "rShldrBend" : "YXZ",
        "rShldrTwist" : "YXZ",
        "rHand" : "YXZ",

        "l_shoulder" : "YZX",
        "l_upperarm" : "YXZ",
        "l_upperarmtwist1" : "YXZ",
        "l_upperarmtwist2" : "YXZ",
        "l_hand" : "YXZ",

        "r_upperarm" : "YXZ",
        "r_upperarmtwist1" : "YXZ",
        "r_upperarmtwist2" : "YXZ",
        "r_forearm" : "YZX",
        "r_forearmtwist1" : "YZX",
        "r_forearmtwist2" : "YZX",
        "r_hand" : "YXZ",
        "r_thumb1" : "YZX",
        "r_thumb2" : "YZX",
        "r_thumb3" : "YZX",

        "upper_arm.fk.L" : "YXZ",
        "upper_arm.fk.R" : "YXZ",
    }

    UnFlips = [
        ("lCollar", "lPectoral", "lShldr", "lForearm", "lHand",
         "lThumb", "lIndex", "lMid", "lRing", "lPinky",
         "l_shoulder", "l_pectoral", "l_upperarm", "l_forearm", "l_hand",
         "l_thumb", "l_index", "l_mid", "l_ring", "l_pinky",
        ),
        ("l_forearmtwist1", "l_forearmtwist2",
         "l_thightwist1", "l_thightwist2",
         "r_thightwist1", "r_thightwist2",
         ),
        ("l_upperarmtwist1", "l_upperarmtwist2",
        ),
        ]

    UnFlipsSharp = [
        [],
        ["Eyes", "l_Eye", "r_Eye",],
        [],
        ]

    Flips = [
        ("rCollar", "rPectoral", "rShldr", "rForearm", "rHand",
         "rThumb", "rIndex", "rMid", "rRing", "rPinky",
         "r_shoulder", "r_pectoral", "r_upperarm", "r_forearm", "r_hand",
         "r_thumb", "r_index", "r_mid", "r_ring", "r_pinky",
        ),
        "___",
        "___"
        ]

    FlipsSharp = [
        [],
        [],
        [],
        ]

    #-------------------------------------------------------------
    #   Bone twist info
    #-------------------------------------------------------------

    BoneTwistInfo = {
        "upper_arm.fk.L" : (0, 1),
        "upper_arm.fk.R" : (0, -1),
        "forearm.fk.L" : (0, 1),
        "forearm.fk.R" : (0, -1),
        "thigh.fk.L" : (1, -1),
        "thigh.fk.R" : (1, -1),

        "upper_arm_fk.L" : (0, 1),
        "upper_arm_fk.R" : (0, -1),
        "forearm_fk.L" : (0, 1),
        "forearm_fk.R" : (0, -1),
        "thigh_fk.L" : (1, -1),
        "thigh_fk.R" : (1, -1),

        "l_upperarm" : (0, 1),
        "r_upperarm" : (0, -1),
        "l_forearm" : (0, 1),
        "r_forearm" : (0, -1),
        "l_thigh" : (1, -1),
        "r_thigh" : (1, -1),

        "neck" : (1, 1),
    }

    FaceRigs = [
        "upperFaceRig", "lowerFaceRig",
        "upperfacerig", "lowerfacerig",
    ]

    Teeth = [
        "upperTeeth", "lowerTeeth",
        "upperteeth", "lowerteeth",
    ]

    HeadBones = [
        "upperJaw", "lowerJaw",
        "upperjaw", "lowerjaw",
    ]

    Tongue = [
        "tongue01", "tongue02", "tongue03", "tongue04",
        "tongue05", "tongue06", "tongueBase", "tongueTip",
    ]

    #-------------------------------------------------------------
    #   Alternative bone names
    #-------------------------------------------------------------

    BoneMap = {
        "Genesis9" : "RIG",

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

    def getDefaultMode(self, pb):
        return self.RotationModes.get(pb.name, 'YZX')


BD = BoneData()
