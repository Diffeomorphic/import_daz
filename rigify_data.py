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

        if meta.DazPre278:
            self.hips = "hips"
            spine = "spine"
            spine1 = "spine-1"
            chest = "chest"
            chest1 = "chest-1"
            neck = "neck"
            self.head = "head"
            meta.DazRigifyType = "rigify"

            self.MetaBones = {
                "spine" : spine,
                "spine-1" : spine1,
                "chest" : chest,
                "chest-1" : chest1,
                "chestUpper" : chest1,
                "neck" : neck,
                "head" : self.head,
            }

            self.RigifyParams = {}

            self.DeformBones = {
                "neckLower" : "DEF-neck",
                "neckUpper" : "DEF-neck",
                "ShldrBend" : "DEF-upper_arm.01.%s",
                "ForearmBend" : "DEF-forearm.01.%s",
                "ThighBend" : "DEF-thigh.01.%s",
                "ShldrTwist" : "DEF-upper_arm.02.%s",
                "ForearmTwist" : "DEF-forearm.02.%s",
                "ThighTwist" : "DEF-thigh.02.%s",
                "Shin" : "DEF-shin.02.%s",
            }

        else:
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
                "neckLower" : "DEF-spine.005",
                "neckUpper" : "DEF-spine.006",
                "ShldrBend" : "DEF-upper_arm.%s",
                "ForearmBend" : "DEF-forearm.%s",
                "ThighBend" : "DEF-thigh.%s",
                "ShldrTwist" : "DEF-upper_arm.%s.001",
                "ForearmTwist" : "DEF-forearm.%s.001",
                "ThighTwist" : "DEF-thigh.%s.001",
                "Shin" : "DEF-shin.%s.001",
            }


        self.MetaDisconnect = [self.hips, neck]

        self.MetaParents = {
            "shoulder.L" : chest1,
            "shoulder.R" : chest1,
        }

        self.RigifySkeleton = {
            self.hips :            ("hip", ["hip", "pelvis"]),

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

        self.GenesisCarpals = {
            "palm.01.L" :        (("lCarpal1", "lIndex1"), ["lCarpal1"]),
            "palm.02.L" :        (("lCarpal1", "lMid1"), []),
            "palm.03.L" :        (("lCarpal2", "lRing1"), ["lCarpal2"]),
            "palm.04.L" :        (("lCarpal2", "lPinky1"), []),

            "palm.01.R" :        (("rCarpal1", "rIndex1"), ["rCarpal1"]),
            "palm.02.R" :        (("rCarpal1", "rMid1"), []),
            "palm.03.R" :        (("rCarpal2", "rRing1"), ["rCarpal2"]),
            "palm.04.R" :        (("rCarpal2", "rPinky1"), []),
        }

        self.GenesisSpine = [
            ("abdomen", spine, self.hips),
            ("abdomen2", spine1, spine),
            ("chest", chest, spine1),
            ("neck", neck, chest),
            ("head", self.head, neck),
        ]

        self.Genesis3Spine = [
            ("abdomen", spine, self.hips),
            ("abdomen2", spine1, spine),
            ("chest", chest, spine1),
            ("chestUpper", chest1, chest),
            ("neck", neck, chest1),
        ]
        if meta.DazUseSplitNeck:
            self.Genesis3Spine += [
                ("neckUpper", neck1, neck),
                ("head", self.head, neck1)]
        else:
            self.Genesis3Spine.append(("head", self.head, neck))

        self.Genesis3Mergers = {
            "lShldrBend" : ["lShldrTwist"],
            "lForearmBend" : ["lForearmTwist"],
            "lThighBend" : ["lThighTwist"],
            #"lFoot" : ["lMetatarsals"],
            "rShldrBend" : ["rShldrTwist"],
            "rForearmBend" : ["rForearmTwist"],
            "rThighBend" : ["rThighTwist"],
            #"rFoot" : ["rMetatarsals"],
        }
        if not meta.DazUseSplitNeck:
            self.Genesis3Mergers["neckLower"] = ["neckUpper"]

        self.Genesis3Parents = {
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
        if meta.DazUseSplitNeck:
            self.Genesis3Parents["head"] = "neckUpper"
            self.Genesis3Parents["neckUpper"] = "neckLower"
        else:
            self.Genesis3Parents["head"] = "neckLower"

        self.Genesis3Renames = {
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
