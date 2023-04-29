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

from .utils import *

class RigifyData:
    def __init__(self, meta):
        def deleteChildren(eb, meta):
            for child in eb.children:
                deleteChildren(child, meta)
                meta.data.edit_bones.remove(child)

        def deleteBones(meta, bnames):
            ebones = meta.data.edit_bones
            rembones = [ebones[bname] for bname in bnames if bname in ebones.keys()]
            for eb in rembones:
                ebones.remove(eb)

        self.hips = "spine"
        spine = "spine.001"
        spine1 = "spine.002"
        chest = "spine.003"
        chest1 = "spine.004"
        neck = "spine.005"
        if meta.DazUseSplitNeck:
            neck1= "spine.006"
            self.head = "spine.007"
        else:
            self.head = "spine.006"
        meta.DazRigifyType = "rigify2"
        setMode('EDIT')
        eb = meta.data.edit_bones[self.head]
        deleteChildren(eb, meta)
        deleteBones(meta, ["breast.L", "breast.R"])
        setMode('OBJECT')

        self.MetaBones = {
            "spine" : self.hips,
            "spine-1" : spine1,
            "chest" : chest,
            "chest-1" : chest1,
            "chestUpper" : chest1,
            "neck" : neck,
            "head" : self.head,
        }

        self.RigifyParams = {
            ("spine", "neck_pos", 6),
            ("spine", "pivot_pos", 1),
        }

        self.DeformBones = {
            "abdomenLower" : "DEF-spine.001",
            "abdomenUpper" : "DEF-spine.002",
            "chestLower" : "DEF-spine.003",
            "chestUpper" : "DEF-spine.004",
            "neckLower" : "DEF-spine.005",
            "neckUpper" : "DEF-spine.006",
            "ShldrBend" : "DEF-upper_arm.%s",
            "ForearmBend" : "DEF-forearm.%s",
            "ThighBend" : "DEF-thigh.%s",
            "ShldrTwist" : "DEF-upper_arm.%s.001",
            "ForearmTwist" : "DEF-forearm.%s.001",
            "ThighTwist" : "DEF-thigh.%s.001",
            "Shin" : "DEF-shin.%s",
        }


        self.MetaDisconnect = [self.hips, neck]

        self.MetaParents = {
            "shoulder.L" : chest1,
            "shoulder.R" : chest1,
        }

        self.RigifyGenesis38 = {
            self.hips :         ("hip", ["hip", "pelvis"]),

            "thigh.L" :         "lThigh",
            "shin.L" :          "lShin",
            "foot.L" :          "lFoot",
            "toe.L" :           "lToe",

            "thigh.R" :         "rThigh",
            "shin.R" :          "rShin",
            "foot.R" :          "rFoot",
            "toe.R" :           "rToe",

            "abdomen" :         "abdomen",
            "chest" :           "chest",
            "neck" :            "neck",
            "head" :            "head",

            "shoulder.L" :      "lCollar",
            "upper_arm.L" :     "lShldr",
            "forearm.L" :       "lForeArm",
            "hand.L" :          "lHand",

            "shoulder.R" :      "rCollar",
            "upper_arm.R" :     "rShldr",
            "forearm.R" :       "rForeArm",
            "hand.R" :          "rHand",

            "thumb.01.L" :       "lThumb1",
            "thumb.02.L" :       "lThumb2",
            "thumb.03.L" :       "lThumb3",
            "f_index.01.L" :     "lIndex1",
            "f_index.02.L" :     "lIndex2",
            "f_index.03.L" :     "lIndex3",
            "f_middle.01.L" :    "lMid1",
            "f_middle.02.L" :    "lMid2",
            "f_middle.03.L" :    "lMid3",
            "f_ring.01.L" :      "lRing1",
            "f_ring.02.L" :      "lRing2",
            "f_ring.03.L" :      "lRing3",
            "f_pinky.01.L" :     "lPinky1",
            "f_pinky.02.L" :     "lPinky2",
            "f_pinky.03.L" :     "lPinky3",

            "thumb.01.R" :       "rThumb1",
            "thumb.02.R" :       "rThumb2",
            "thumb.03.R" :       "rThumb3",
            "f_index.01.R" :     "rIndex1",
            "f_index.02.R" :     "rIndex2",
            "f_index.03.R" :     "rIndex3",
            "f_middle.01.R" :    "rMid1",
            "f_middle.02.R" :    "rMid2",
            "f_middle.03.R" :    "rMid3",
            "f_ring.01.R" :      "rRing1",
            "f_ring.02.R" :      "rRing2",
            "f_ring.03.R" :      "rRing3",
            "f_pinky.01.R" :     "rPinky1",
            "f_pinky.02.R" :     "rPinky2",
            "f_pinky.03.R" :     "rPinky3",

            "palm.01.L" :       "lCarpal1",
            "palm.02.L" :       "lCarpal2",
            "palm.03.L" :       "lCarpal3",
            "palm.04.L" :       "lCarpal4",

            "palm.01.R" :       "rCarpal1",
            "palm.02.R" :       "rCarpal2",
            "palm.03.R" :       "rCarpal3",
            "palm.04.R" :       "rCarpal4",
        }

        self.RigifyGenesis9 = {
            self.hips :         ("hip", ["hip", "pelvis"]),

            "thigh.L" :         "l_thigh",
            "shin.L" :          "l_shin",
            "foot.L" :          "l_foot",
            "toe.L" :           "l_toes",

            "thigh.R" :         "r_thigh",
            "shin.R" :          "r_shin",
            "foot.R" :          "r_foot",
            "toe.R" :           "r_toes",

            "abdomen" :         "spine1",
            "abdomen2" :        "spine2",
            "chest" :           "spine3",
            "chestUpper" :      "spine4",
            "neck" :            "neck1",
            "head" :            "head",

            "shoulder.L" :      "l_shoulder",
            "upper_arm.L" :     "l_upperarm",
            "forearm.L" :       "l_forearm",
            "hand.L" :          "l_hand",

            "shoulder.R" :      "r_shoulder",
            "upper_arm.R" :     "r_upperarm",
            "forearm.R" :       "r_forearm",
            "hand.R" :          "r_hand",

            "thumb.01.L" :       "l_thumb1",
            "thumb.02.L" :       "l_thumb2",
            "thumb.03.L" :       "l_thumb3",
            "f_index.01.L" :     "l_index1",
            "f_index.02.L" :     "l_index2",
            "f_index.03.L" :     "l_index3",
            "f_middle.01.L" :    "l_mid1",
            "f_middle.02.L" :    "l_mid2",
            "f_middle.03.L" :    "l_mid3",
            "f_ring.01.L" :      "l_ring1",
            "f_ring.02.L" :      "l_ring2",
            "f_ring.03.L" :      "l_ring3",
            "f_pinky.01.L" :     "l_pinky1",
            "f_pinky.02.L" :     "l_pinky2",
            "f_pinky.03.L" :     "l_pinky3",

            "thumb.01.R" :       "r_thumb1",
            "thumb.02.R" :       "r_thumb2",
            "thumb.03.R" :       "r_thumb3",
            "f_index.01.R" :     "r_index1",
            "f_index.02.R" :     "r_index2",
            "f_index.03.R" :     "r_index3",
            "f_middle.01.R" :    "r_mid1",
            "f_middle.02.R" :    "r_mid2",
            "f_middle.03.R" :    "r_mid3",
            "f_ring.01.R" :      "r_ring1",
            "f_ring.02.R" :      "r_ring2",
            "f_ring.03.R" :      "r_ring3",
            "f_pinky.01.R" :     "r_pinky1",
            "f_pinky.02.R" :     "r_pinky2",
            "f_pinky.03.R" :     "r_pinky3",

            "palm.01.L" :       "l_indexmetacarpal",
            "palm.02.L" :       "l_midmetacarpal",
            "palm.03.L" :       "l_ringmetacarpal",
            "palm.04.L" :       "l_pinkymetacarpal",

            "palm.01.R" :       "r_indexmetacarpal",
            "palm.02.R" :       "r_midmetacarpal",
            "palm.03.R" :       "r_ringmetacarpal",
            "palm.04.R" :       "r_pinkymetacarpal",
        }

        self.GenesisSpine = {
            "abdomen" : (spine, self.hips),
            "abdomen2" : (spine1, spine),
            "chest" : (chest, spine1),
            "neck" : (neck, chest),
            "head" : (self.head, neck),
        }

        self.Genesis38Spine = {
            "abdomen" : (spine, self.hips),
            "abdomen2" : (spine1, spine),
            "chest" : (chest, spine1),
            "chestUpper" : (chest1, chest),
            "neck" : (neck, chest1),
        }

        self.Genesis9Spine = {
            "spine1" : (spine, self.hips),
            "spine2" : (spine1, spine),
            "spine3" : (chest, spine1),
            "spine4" : (chest1, chest),
            "neck1" : (neck, chest1),
        }

        if meta.DazUseSplitNeck:
            self.Genesis38Spine["neckUpper"] = (neck1, neck)
            self.Genesis38Spine["head"] = (self.head, neck1)
            self.Genesis9Spine["neck2"] = (neck1, neck)
            self.Genesis9Spine["head"] = (self.head, neck1)
        else:
            self.Genesis38Spine["head"] = (self.head, neck)
            self.Genesis9Spine["head"] = (self.head, neck)

        self.Genesis38Mergers = {
            "lShldrBend" : ["lShldrTwist"],
            "lForearmBend" : ["lForearmTwist"],
            "lThighBend" : ["lThighTwist"],
            #"lFoot" : ["lMetatarsals"],
            "rShldrBend" : ["rShldrTwist"],
            "rForearmBend" : ["rForearmTwist"],
            "rThighBend" : ["rThighTwist"],
            #"rFoot" : ["rMetatarsals"],
        }
        self.Genesis9Mergers = {
            "l_upperarm" : ["l_upperarmtwist1", "l_upperarmtwist2"],
            "l_forearm" : ["l_forearmtwist1", "l_forearmtwist2"],
            "l_thigh" : ["l_thightwist1", "l_thightwist2"],
            "r_upperarm" : ["r_upperarmtwist1", "r_upperarmtwist2"],
            "r_forearm" : ["r_forearmtwist1", "r_forearmtwist2"],
            "r_thigh" : ["r_thightwist1", "r_thightwist2"],
        }
        if not meta.DazUseSplitNeck:
            self.Genesis38Mergers["neckLower"] = ["neckUpper"]
            self.Genesis9Mergers["neck1"] = ["neck2"]

        self.Genesis38Parents = {
            "neckLower" : "chestUpper",
            "chestUpper" : "chestLower",
            "chestLower" : "abdomenUpper",
            "abdomenUpper" : "abdomenLower",
            "lForearmBend" : "lShldrBend",
            "lHand" : "lForearmBend",
            "lShin" : "lThighBend",
            "lToe" : "lFoot",
            "rForearmBend" : "rShldrBend",
            "rHand" : "rForearmBend",
            "rShin" : "rThighBend",
            "rToe" : "rFoot",
        }
        self.Genesis9Parents = {
            "neck1" : "spine4",
            "spine4" : "spine3",
            "spine3" : "spine2",
            "spine2" : "spine1",
            "l_forearm" : "l_upperarm",
            "l_hand" : "l_forearm",
            "l_shin" : "l_thigh",
            "l_toes" : "l_foot",
            "r_forearm" : "r_upperarm",
            "r_hand" : "r_forearm",
            "r_shin" : "r_thigh",
            "r_toes" : "r_foot",
        }
        if meta.DazUseSplitNeck:
            self.Genesis38Parents["head"] = "neckUpper"
            self.Genesis38Parents["neckUpper"] = "neckLower"
            self.Genesis9Parents["head"] = "neck2"
            self.Genesis9Parents["neck2"] = "neck1"
        else:
            self.Genesis38Parents["head"] = "neckLower"
            self.Genesis9Parents["head"] = "neck1"

        self.Genesis38Renames = {
            "abdomenLower" : "abdomen",
            "abdomenUpper" : "abdomen2",
            "chestLower" : "chest",
            "neckLower" : "neck",
            "lShldrBend" : "lShldr",
            "lForearmBend" : "lForeArm",
            "lThighBend" : "lThigh",
            "rShldrBend" : "rShldr",
            "rForearmBend" : "rForeArm",
            "rThighBend" : "rThigh",
        }

        self.Genesis9Removes = ["l_upperarm", "r_upperarm"]

        self.ExtraParents = {
            "lPectoral" : "DEF-spine.004",
            "rPectoral" : "DEF-spine.004",
            "l_pectoral" : "DEF-spine.004",
            "r_pectoral" : "DEF-spine.004",
        }
        self.ExtraParents = {}

        self.CustomShapeFixGenesis38 = [
            (["head", "spine_fk.007"], 4)
        ]

        self.CustomShapeFixGenesis9 = [
            (["head", "spine_fk.007"], 4),
            (["neck"], 0.6),
        ]

        self.Genesis1238Fingers = [
            ("Thumb", "thumb"),
            ("Index", "f_index"),
            ("Mid", "f_middle"),
            ("Ring", "f_ring"),
            ("Pinky", "f_pinky")
        ]

        self.Genesis9Fingers = [
            ("_thumb", "thumb"),
            ("_index", "f_index"),
            ("_mid", "f_middle"),
            ("_ring", "f_ring"),
            ("_pinky", "f_pinky")
        ]
