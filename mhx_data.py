# Copyright (c) 2016-2024, Thomas Larsson
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

from .layers import *
from mathutils import Vector

class MhxData:
    Fingers = ["thumb", "index", "middle", "ring", "pinky"]
    F_Fingers = ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]
    PalmNames = ["palm_thumb", "palm_index", "palm_index", "palm_middle", "palm_middle"]
    BackBones = ["spine", "spine-1", "chest", "chest-1"]
    NeckBones = ["neck", "neck-1", "head"]

    Skeleton = {
        "hip" : ("hip", L_MAIN),
        "pelvis" : ("pelvis", L_SPINE),
        "abdomen" : ("spine", L_SPINE),
        "abdomenLower" : ("spine", L_SPINE),
        "spine1" : ("spine", L_SPINE),
        "abdomen2" : ("spine-1", L_SPINE),
        "abdomenUpper" : ("spine-1", L_SPINE),
        "spine2" : ("spine-1", L_SPINE),
        "chest" : ("chest", L_SPINE),
        "chestLower" : ("chest", L_SPINE),
        "spine3" : ("chest", L_SPINE),
        "chestUpper" : ("chest-1", L_SPINE),
        "spine4" : ("chest-1", L_SPINE),
        "neck" : ("neck", L_SPINE),
        "neckLower" : ("neck", L_SPINE),
        "neck1" : ("neck", L_SPINE),
        "neckUpper" : ("neck-1", L_SPINE),
        "neck2" : ("neck-1", L_SPINE),
        "head" : ("head", L_SPINE),

        #"tongue00" : ("tounge01", L_MAIN),
        #"tongue02" : ("tongue02", L_MAIN),
        #"tongue04" : ("tongue03", L_MAIN),
        #"tongue06" : ("tongue04", L_MAIN),
        "lEye" : ("eye.L", L_HEAD),
        "rEye" : ("eye.R", L_HEAD),
        "leftEye" : ("eye.L", L_HEAD),
        "rightEye" : ("eye.R", L_HEAD),
        "l_eye" : ("eye.L", L_HEAD),
        "r_eye" : ("eye.R", L_HEAD),
        "lEar" : ("ear.L", L_HEAD),
        "rEar" : ("ear.R", L_HEAD),
        "l_ear" : ("ear.L", L_HEAD),
        "r_ear" : ("ear.R", L_HEAD),

        "lPectoral" : ("pectoral.L", L_TWEAK),
        "l_pectoral" : ("pectoral.L", L_TWEAK),
        "lCollar" : ("clavicle.L", L_LARMFK),
        "l_shoulder" : ("clavicle.L", L_LARMFK),
        "lShldr" : ("upper_arm.L", L_LARMFK),
        "lShldrBend" : ("upper_armBend.L", L_LARMFK),
        "lShldrTwist" : ("upper_armTwist.L", L_LARMFK),
        "l_upperarm" : ("upper_arm.L", L_LARMFK),
        "l_upperarmtwist1" : ("upper_arm.twist1.L", L_DEF),
        "l_upperarmtwist2" : ("upper_arm.twist2.L", L_DEF),
        "lForeArm" : ("forearm.L", L_LARMFK),
        "lForearmBend" : ("forearmBend.L", L_LARMFK),
        "lForearmTwist" : ("forearmTwist.L", L_LARMFK),
        "l_forearm" : ("forearm.L", L_LARMFK),
        "l_forearmtwist1" : ("forearm.twist1.L", L_DEF),
        "l_forearmtwist2" : ("forearm.twist2.L", L_DEF),
        "lHand" : ("hand.L", L_LARMFK),
        "l_hand" : ("hand.L", L_LARMFK),

        "rPectoral" : ("pectoral.R", L_TWEAK),
        "r_pectoral" : ("pectoral.R", L_TWEAK),
        "rCollar" : ("clavicle.R", L_RARMFK),
        "r_shoulder" : ("clavicle.R", L_RARMFK),
        "rShldr" : ("upper_arm.R", L_RARMFK),
        "rShldrBend" : ("upper_armBend.R", L_RARMFK),
        "rShldrTwist" : ("upper_armTwist.R", L_RARMFK),
        "r_upperarm" : ("upper_arm.R", L_RARMFK),
        "r_upperarmtwist1" : ("upper_arm.twist1.R", L_DEF),
        "r_upperarmtwist2" : ("upper_arm.twist2.R", L_DEF),
        "rForeArm" : ("forearm.R", L_RARMFK),
        "rForearmBend" : ("forearmBend.R", L_RARMFK),
        "rForearmTwist" : ("forearmTwist.R", L_RARMFK),
        "r_forearm" : ("forearm.R", L_RARMFK),
        "r_forearmtwist1" : ("forearm.twist1.R", L_DEF),
        "r_forearmtwist2" : ("forearm.twist2.R", L_DEF),
        "rHand" : ("hand.R", L_RARMFK),
        "r_hand" : ("hand.R", L_RARMFK),

        "lThigh" : ("thigh.L", L_LLEGFK),
        "lThighBend" : ("thighBend.L", L_LLEGFK),
        "lThighTwist" : ("thighTwist.L", L_LLEGFK),
        "l_thigh" : ("thigh.L", L_LLEGFK),
        "l_thightwist1" : ("thigh.twist1.L", L_DEF),
        "l_thightwist2" : ("thigh.twist2.L", L_DEF),
        "lShin" : ("shin.L", L_LLEGFK),
        "l_shin" : ("shin.L", L_LLEGFK),
        "lFoot" : ("foot.L", L_LLEGFK),
        "l_foot" : ("foot.L", L_LLEGFK),
        "lMetatarsals" : ("tarsal.L", L_TWEAK),
        "l_metatarsal" : ("tarsal.L", L_TWEAK),
        "lToe" : ("toe.L", L_LLEGFK),
        "l_toes" : ("toe.L", L_LLEGFK),
        "lHeel" : ("heel.L", L_LTOE),

        "rThigh" : ("thigh.R", L_RLEGFK),
        "rThighBend" : ("thighBend.R", L_RLEGFK),
        "rThighTwist" : ("thighTwist.R", L_RLEGFK),
        "r_thigh" : ("thigh.R", L_RLEGFK),
        "r_thightwist1" : ("thigh.twist1.R", L_DEF),
        "r_thightwist2" : ("thigh.twist2.R", L_DEF),
        "rShin" : ("shin.R", L_RLEGFK),
        "r_shin" : ("shin.R", L_RLEGFK),
        "rFoot" : ("foot.R", L_RLEGFK),
        "r_foot" : ("foot.R", L_RLEGFK),
        "rMetatarsals" : ("tarsal.R", L_TWEAK),
        "r_metatarsal" : ("tarsal.R", L_TWEAK),
        "rToe" : ("toe.R", L_RLEGFK),
        "r_toes" : ("toe.R", L_RLEGFK),
        "rHeel" : ("heel.R", L_RTOE),

        "lBigToe" : ("big_toe.01.L", L_LTOE),
        "lBigToe_2" : ("big_toe.02.L", L_LTOE),
        "lSmallToe1" : ("small_toe_1.01.L", L_LTOE),
        "lSmallToe1_2" : ("small_toe_1.02.L", L_LTOE),
        "lSmallToe2" : ("small_toe_2.01.L", L_LTOE),
        "lSmallToe2_2" : ("small_toe_2.02.L", L_LTOE),
        "lSmallToe3" : ("small_toe_3.01.L", L_LTOE),
        "lSmallToe3_2" : ("small_toe_3.02.L", L_LTOE),
        "lSmallToe4" : ("small_toe_4.01.L", L_LTOE),
        "lSmallToe4_2" : ("small_toe_4.02.L", L_LTOE),

        "rBigToe" : ("big_toe.01.R", L_RTOE),
        "rBigToe_2" : ("big_toe.02.R", L_RTOE),
        "rSmallToe1" : ("small_toe_1.01.R", L_RTOE),
        "rSmallToe1_2" : ("small_toe_1.02.R", L_RTOE),
        "rSmallToe2" : ("small_toe_2.01.R", L_RTOE),
        "rSmallToe2_2" : ("small_toe_2.02.R", L_RTOE),
        "rSmallToe3" : ("small_toe_3.01.R", L_RTOE),
        "rSmallToe3_2" : ("small_toe_3.02.R", L_RTOE),
        "rSmallToe4" : ("small_toe_4.01.R", L_RTOE),
        "rSmallToe4_2" : ("small_toe_4.02.R", L_RTOE),

        "l_bigtoe1" : ("big_toe.01.L", L_LTOE),
        "l_bigtoe2" : ("big_toe.02.L", L_LTOE),
        "l_indextoe1" : ("small_toe_1.01.L", L_LTOE),
        "l_indextoe2" : ("small_toe_1.02.L", L_LTOE),
        "l_midtoe1" : ("small_toe_2.01.L", L_LTOE),
        "l_midtoe2" : ("small_toe_2.02.L", L_LTOE),
        "l_ringtoe1" : ("small_toe_3.01.L", L_LTOE),
        "l_ringtoe2" : ("small_toe_3.02.L", L_LTOE),
        "l_pinkytoe1" : ("small_toe_4.01.L", L_LTOE),
        "l_pinkytoe2" : ("small_toe_4.02.L", L_LTOE),

        "r_bigtoe1" : ("big_toe.01.R", L_RTOE),
        "r_bigtoe2" : ("big_toe.02.R", L_RTOE),
        "r_indextoe1" : ("small_toe_1.01.R", L_RTOE),
        "r_indextoe2" : ("small_toe_1.02.R", L_RTOE),
        "r_midtoe1" : ("small_toe_2.01.R", L_RTOE),
        "r_midtoe2" : ("small_toe_2.02.R", L_RTOE),
        "r_ringtoe1" : ("small_toe_3.01.R", L_RTOE),
        "r_ringtoe2" : ("small_toe_3.02.R", L_RTOE),
        "r_pinkytoe1" : ("small_toe_4.01.R", L_RTOE),
        "r_pinkytoe2" : ("small_toe_4.02.R", L_RTOE),

        "lCarpal1" : ("palm_index.L", L_TWEAK),
        "lCarpal2" : ("palm_middle.L", L_TWEAK),
        "lCarpal3" : ("palm_ring.L", L_TWEAK),
        "lCarpal4" : ("palm_pinky.L", L_TWEAK),
        "l_indexmetacarpal" : ("palm_index.L", L_TWEAK),
        "l_midmetacarpal" : ("palm_middle.L", L_TWEAK),
        "l_ringmetacarpal" : ("palm_ring.L", L_TWEAK),
        "l_pinkymetacarpal" : ("palm_pinky.L", L_TWEAK),

        "rCarpal1" : ("palm_index.R", L_TWEAK),
        "rCarpal2" : ("palm_middle.R", L_TWEAK),
        "rCarpal3" : ("palm_ring.R", L_TWEAK),
        "rCarpal4" : ("palm_pinky.R", L_TWEAK),
        "r_indexmetacarpal" : ("palm_index.R", L_TWEAK),
        "r_midmetacarpal" : ("palm_middle.R", L_TWEAK),
        "r_ringmetacarpal" : ("palm_ring.R", L_TWEAK),
        "r_pinkymetacarpal" : ("palm_pinky.R", L_TWEAK),

        "lThumb1" : ("thumb.01.L", L_LFINGER),
        "lThumb2" : ("thumb.02.L", L_LFINGER),
        "lThumb3" : ("thumb.03.L", L_LFINGER),
        "lIndex1" : ("f_index.01.L", L_LFINGER),
        "lIndex2" : ("f_index.02.L", L_LFINGER),
        "lIndex3" : ("f_index.03.L", L_LFINGER),
        "lMid1" : ("f_middle.01.L", L_LFINGER),
        "lMid2" : ("f_middle.02.L", L_LFINGER),
        "lMid3" : ("f_middle.03.L", L_LFINGER),
        "lRing1" : ("f_ring.01.L", L_LFINGER),
        "lRing2" : ("f_ring.02.L", L_LFINGER),
        "lRing3" : ("f_ring.03.L", L_LFINGER),
        "lPinky1" : ("f_pinky.01.L", L_LFINGER),
        "lPinky2" : ("f_pinky.02.L", L_LFINGER),
        "lPinky3" : ("f_pinky.03.L", L_LFINGER),

        "l_thumb1" : ("thumb.01.L", L_LFINGER),
        "l_thumb2" : ("thumb.02.L", L_LFINGER),
        "l_thumb3" : ("thumb.03.L", L_LFINGER),
        "l_index1" : ("f_index.01.L", L_LFINGER),
        "l_index2" : ("f_index.02.L", L_LFINGER),
        "l_index3" : ("f_index.03.L", L_LFINGER),
        "l_mid1" : ("f_middle.01.L", L_LFINGER),
        "l_mid2" : ("f_middle.02.L", L_LFINGER),
        "l_mid3" : ("f_middle.03.L", L_LFINGER),
        "l_ring1" : ("f_ring.01.L", L_LFINGER),
        "l_ring2" : ("f_ring.02.L", L_LFINGER),
        "l_ring3" : ("f_ring.03.L", L_LFINGER),
        "l_pinky1" : ("f_pinky.01.L", L_LFINGER),
        "l_pinky2" : ("f_pinky.02.L", L_LFINGER),
        "l_pinky3" : ("f_pinky.03.L", L_LFINGER),

        "rThumb1" : ("thumb.01.R", L_RFINGER),
        "rThumb2" : ("thumb.02.R", L_RFINGER),
        "rThumb3" : ("thumb.03.R", L_RFINGER),
        "rIndex1" : ("f_index.01.R", L_RFINGER),
        "rIndex2" : ("f_index.02.R", L_RFINGER),
        "rIndex3" : ("f_index.03.R", L_RFINGER),
        "rMid1" : ("f_middle.01.R", L_RFINGER),
        "rMid2" : ("f_middle.02.R", L_RFINGER),
        "rMid3" : ("f_middle.03.R", L_RFINGER),
        "rRing1" : ("f_ring.01.R", L_RFINGER),
        "rRing2" : ("f_ring.02.R", L_RFINGER),
        "rRing3" : ("f_ring.03.R", L_RFINGER),
        "rPinky1" : ("f_pinky.01.R", L_RFINGER),
        "rPinky2" : ("f_pinky.02.R", L_RFINGER),
        "rPinky3" : ("f_pinky.03.R", L_RFINGER),

        "r_thumb1" : ("thumb.01.R", L_RFINGER),
        "r_thumb2" : ("thumb.02.R", L_RFINGER),
        "r_thumb3" : ("thumb.03.R", L_RFINGER),
        "r_index1" : ("f_index.01.R", L_RFINGER),
        "r_index2" : ("f_index.02.R", L_RFINGER),
        "r_index3" : ("f_index.03.R", L_RFINGER),
        "r_mid1" : ("f_middle.01.R", L_RFINGER),
        "r_mid2" : ("f_middle.02.R", L_RFINGER),
        "r_mid3" : ("f_middle.03.R", L_RFINGER),
        "r_ring1" : ("f_ring.01.R", L_RFINGER),
        "r_ring2" : ("f_ring.02.R", L_RFINGER),
        "r_ring3" : ("f_ring.03.R", L_RFINGER),
        "r_pinky1" : ("f_pinky.01.R", L_RFINGER),
        "r_pinky2" : ("f_pinky.02.R", L_RFINGER),
        "r_pinky3" : ("f_pinky.03.R", L_RFINGER)
    }


    BoneGroups = [
        ('Spine',    (1,1,0),   (L_MAIN, L_SPINE, L_SPINE2)),
        ('Left Arm FK',  (0.5,0,0), (L_LARMFK,)),
        ('Right Arm FK', (0,0,0.5), (L_RARMFK,)),
        ('Left Arm IK',  (1,0,0),   (L_LARMIK, L_LARM2IK)),
        ('Right Arm IK', (0,0,1),   (L_RARMIK, L_RARM2IK)),
        ('Left Hand',    (1,0,0),   (L_LHAND,)),
        ('Right Hand',   (0,0,1),   (L_RHAND,)),
        ('Left Fingers', (0.5,0,0), (L_LFINGER,)),
        ('Right Fingers',(0,0,0.5), (L_RFINGER,)),
        ('Left Leg FK',  (0.5,0,0), (L_LLEGFK,)),
        ('Right Leg FK', (0,0,0.5), (L_RLEGFK,)),
        ('Left Leg IK',  (1,0,0),   (L_LLEGIK, L_LLEG2IK)),
        ('Right Leg IK', (0,0,1),   (L_RLEGIK, L_RLEG2IK)),
        ('Left Toes',    (0.5,0,0), (L_LTOE,)),
        ('Right Toes',   (0,0,0.5), (L_RTOE,)),
        ('Face',     (0,1,0),   (L_HEAD, L_FACE)),
        ('Tweak',    (0,0.5,0), (L_TWEAK,)),
        ('Custom',       (1,0.5,0), (L_CUSTOM,)),
    ]

    BendTwistBones = [
        ("shin.L", "foot.L", "MhaLegStretch_L"),
        ("thigh.L", "shin.L", None),
        ("forearm.L", "hand.L", "MhaArmStretch_L"),
        ("upper_arm.L", "forearm.L", None),
        ("shin.R", "foot.R", "MhaLegStretch_R"),
        ("thigh.R", "shin.R", None),
        ("forearm.R", "hand.R", "MhaArmStretch_R"),
        ("upper_arm.R", "forearm.R", None),
    ]

    BendTwistGenesis38 = [
        ("thigh.L", "lThighBend", ["lThighTwist"]),
        ("upper_arm.L", "lShldrBend", ["lShldrTwist"]),
        ("forearm.L", "lForearmBend", ["lForearmTwist"]),
        ("thigh.R", "rThighBend", ["rThighTwist"]),
        ("upper_arm.R", "rShldrBend", ["rShldrTwist"]),
        ("forearm.R", "rForearmBend", ["rForearmTwist"]),
    ]

    BendTwistGenesis9 = [
        ("thigh.L", "l_thigh", ["l_thightwist1", "l_thightwist2"]),
        ("upper_arm.L", "l_upperarm", ["l_upperarmtwist1", "l_upperarmtwist2"]),
        ("forearm.L", "l_forearm", ["l_forearmtwist1", "l_forearmtwist2"]),
        ("thigh.R", "r_thigh", ["r_thightwist1", "r_thightwist2"]),
        ("upper_arm.R", "r_upperarm", ["r_upperarmtwist1", "r_upperarmtwist2"]),
        ("forearm.R", "r_forearm", ["r_forearmtwist1", "r_forearmtwist2"]),
    ]

    Knees = [
        ("thigh.L", "shin.L", Vector((0,-1,0))),
        ("thigh.R", "shin.R", Vector((0,-1,0))),
        ("upper_arm.L", "forearm.L", Vector((0,1,0))),
        ("upper_arm.R", "forearm.R", Vector((0,1,0))),
    ]

    ExtraRenames = [
        ("hand0.L", "hand.L"),
        ("hand0.R", "hand.R"),
    ]

    LimbBones = ["upper_arm", "forearm", "thigh", "shin"]

    BoneParents = {
        "ShldrBend" : "upper_arm.bend",
        "ShldrTwist" : "upper_arm.twist",
        "ForearmBend" : "forearm.bend",
        "ForearmTwist" : "forearm.twist",
        "ThighBend" : "thigh.bend",
        "ThighTwist" : "thigh.twist",
        "Shin" : "shin.twist",
    }

    BoneDrivers = {
        "upper_armBend.L" : "upper_arm.bend.L",
        "forearmBend.L" : "forearm.bend.L",
        "thighBend.L" : "thigh.bend.L",
        "upper_armBend.R" : "upper_arm.bend.R",
        "forearmBend.R" : "forearm.bend.R",
        "thighBend.R" : "thigh.bend.R",

        "lShldrBend(fin)" : "upper_arm.bend.L",
        "lForearmBend(fin)" : "forearm.bend.L",
        "lThighBend(fin)" : "thigh.bend.L",
        "rShldrBend(fin)" : "upper_arm.bend.R",
        "rForearmBend(fin)" : "forearm.bend.R",
        "rThighBend(fin)" : "thigh.bend.R",
    }

    DrivenParents = {
        "lowerFaceRig" :    "lowerJaw",
        "lowerTeeth(drv)" : "lowerJaw",
        "tongue01(drv)" :   "lowerTeeth",
    }

    ConnectBendTwist = [
        "lShldrTwist", "lForeArm", "lForearmBend", "lForearmTwist", "lHand",
        "rShldrTwist", "rForeArm", "rForearmBend", "rForearmTwist", "rHand",
        "lThighTwist", "lFoot", "lToe",
        "rThighTwist", "rFoot", "rToe",

        "l_forearm", "l_hand",
        "r_forearm", "r_hand",
        "l_foot", "l_toes",
        "r_foot", "r_toes",
    ]

    ConnectOther = [
        "abdomenUpper", "chestLower", "chestUpper", "neckLower", "neckUpper",
        "lThumb2", "lThumb3",
        "lIndex1", "lIndex2", "lIndex3",
        "lMid1", "lMid2", "lMid3",
        "lRing1", "lRing2", "lRing3",
        "lPinky1", "lPinky2", "lPinky3",
        "rThumb2", "rThumb3",
        "rIndex1", "rIndex2", "rIndex3",
        "rMid1", "rMid2", "rMid3",
        "rRing1", "rRing2", "rRing3",
        "rPinky1", "rPinky2", "rPinky3",

        "spine2", "spine3", "spine4", "neck1", "neck2",
        "l_thumb2", "l_thumb3",
        "l_index1", "l_index2", "l_index3",
        "l_mid1", "l_mid2", "l_mid3",
        "l_ring1", "l_ring2", "l_ring3",
        "l_pinky1", "l_pinky2", "l_pinky3",
        "r_thumb2", "r_thumb3",
        "r_index1", "r_index2", "r_index3",
        "r_mid1", "r_mid2", "r_mid3",
        "r_ring1", "r_ring2", "r_ring3",
        "r_pinky1", "r_pinky2", "r_pinky3",
    ]

    ConnectShin = ["lShin", "rShin", "l_shin", "r_shin"]


MHX = MhxData()
