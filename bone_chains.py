# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *

class BoneChains:

    G38Arm = ["ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Hand"]
    G38Leg = ["ThighBend", "ThighTwist", "Shin", "Foot"]
    G38Spine = ["abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G38Neck = ["neckLower", "neckUpper", "head"]
    G38Thumb = ["Thumb1", "Thumb2", "Thumb3"]
    G38Index = ["Index1", "Index2", "Index3"]
    G38Mid = ["Mid1", "Mid2", "Mid3"]
    G38Ring = ["Ring1", "Ring2", "Ring3"]
    G38Pinky = ["Pinky1", "Pinky2", "Pinky3"]
    G38BigToe = ["BigToe", "BigToe_2"]
    G38SmallToe1 = ["SmallToe1", "SmallToe1_2"]
    G38SmallToe2 = ["SmallToe2", "SmallToe2_2"]
    G38SmallToe3 = ["SmallToe3", "SmallToe3_2"]
    G38SmallToe4 = ["SmallToe4", "SmallToe4_2"]
    G38Tongue = ["tongue01", "tongue02", "tongue03", "tongue04"]

    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["abdomen", "abdomen2", "spine", "chest"]
    G12Neck = ["neck", "head"]
    G12Thumb = G38Thumb
    G12Index = G38Index
    G12Mid = G38Mid
    G12Ring = G38Ring
    G12Pinky = G38Pinky
    G12BigToe = G12SmallToe1 = G12SmallToe2 = G12SmallToe3 = G12SmallToe4 = []
    G12Tongue = ["tongueBase", "tongue01", "tongue02", "tongue03", "tongue04", "tongue05", "tongueTip"]

    G9Arm = ["_upperarm", "_forearm", "_hand"]
    G9Leg = ["_thigh", "_shin", "_foot"]
    G9Spine = ["spine1", "spine2", "spine3", "spine4"]
    G9Neck = ["neck1", "neck2", "head"]
    G9Thumb = ["_thumb1", "_thumb2", "_thumb3"]
    G9Index = ["_index1", "_index2", "_index3"]
    G9Mid = ["_mid1", "_mid2", "_mid3"]
    G9Ring = ["_ring1", "_ring2", "_ring3"]
    G9Pinky = ["_pinky1", "_pinky2", "_pinky3"]
    G9BigToe = ["_bigtoe1", "_bigtoe2"]
    G9SmallToe1 = ["_indextoe1", "_indextoe2"]
    G9SmallToe2 = ["_midtoe1", "_midtoe2"]
    G9SmallToe3 = ["_ringtoe1", "_ringtoe2"]
    G9SmallToe4 = ["_pinkytoe1", "_pinkytoe2"]
    G9Tongue = ["tongue01", "tongue02", "tongue03", "tongue04", "tongue05"]


    def getGenesisType(self, rig):
        def hasAllBones(rig, bnames, prefix):
            from .fix import getSuffixName
            bnames = [prefix+bname for bname in bnames]
            for bname in bnames:
                if bname not in rig.data.bones.keys():
                    sufname = getSuffixName(bname, True)
                    if sufname not in rig.data.bones.keys():
                        return False
            return True

        if (hasAllBones(rig, self.G38Arm+self.G38Leg, "l") and
            hasAllBones(rig, self.G38Arm+self.G38Leg, "r") and
            hasAllBones(rig, self.G38Spine, "")):
            return "G38"
        if (hasAllBones(rig, self.G12Arm+self.G12Leg, "l") and
            hasAllBones(rig, self.G12Arm+self.G12Leg, "r")):
            return "G12"
        if (hasAllBones(rig, self.G9Arm+self.G9Leg, "l") and
            hasAllBones(rig, self.G9Arm+self.G9Leg, "r") and
            hasAllBones(rig, self.G9Spine, "")):
            return "G9"
        raise DazError("%s is not a Genesis armature" % rig.name)
        return None


    def getLimbBoneNames(self, rig, prefix, type):
        self.genesis = self.getGenesisType(rig)
        if not self.genesis:
            return []
        from .fix import getPreSufName
        table = getattr(self, self.genesis+type)
        prenames = []
        for bname in table:
            prename = "%s%s" % (prefix, bname)
            if getPreSufName(prename, rig):
                prenames.append(prename)
        return prenames
