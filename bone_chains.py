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

#----------------------------------------------------------
#   Connect bone chains
#----------------------------------------------------------

class DAZ_OT_ConnectBoneChains(DazPropsOperator, BoneChains, IsArmature):
    bl_idname = "daz.connect_bone_chains"
    bl_label = "Connect Bone Chains"
    bl_description = "Connect all bones in chains to their parents"
    bl_options = {'UNDO'}

    useArms : BoolProperty(
        name = "Arms",
        description = "Connect arm bones",
        default = True)

    useLegs : BoolProperty(
        name = "Legs",
        description = "Connect leg bones",
        default = True)

    useSpine : BoolProperty(
        name = "Spine",
        description = "Connect spine bones",
        default = False)

    useNeck : BoolProperty(
        name = "Neck",
        description = "Connect neck bones",
        default = False)

    useFingers : BoolProperty(
        name = "Fingers",
        description = "Connect finger bones",
        default = True)

    useToes : BoolProperty(
        name = "Toes",
        description = "Connect toe bones",
        default = True)

    useTongue : BoolProperty(
        name = "Tongue",
        description = "Connect tongue bones",
        default = True)

    useSelected : BoolProperty(
        name = "Selected",
        description = "Connect selected bones",
        default = False)

    unlock : BoolProperty(
        name = "Unlock Last Bone",
        description = "Remove location locks of the last bone in each chain for use as Auto self target",
        default = True)

    location : EnumProperty(
        items = [('HEAD', "Child Head", "Connect at the head of the child bone"),
                 ('TAIL', "Parent Tail", "Connect at the tail of the parent bone"),
                 ('CENTER', "Center", "Connect at the midpoint between the parent tail and child head")],
        name = "Location",
        description = "Where to connect parent and child bones",
        default = 'HEAD')

    def draw(self, context):
        self.layout.prop(self, "useSelected")
        if not self.useSelected:
            self.layout.prop(self, "useArms")
            self.layout.prop(self, "useLegs")
            self.layout.prop(self, "useSpine")
            self.layout.prop(self, "useNeck")
            self.layout.prop(self, "useFingers")
            self.layout.prop(self, "useToes")
            self.layout.prop(self, "useTongue")
        self.layout.prop(self, "location")
        self.layout.prop(self, "unlock")


    def run(self, context):
        rig = context.object
        self.chains = []
        self.getBoneNames(rig)
        wmats = []
        for ob in rig.children:
            if ob.parent_type == 'BONE':
                wmats.append((ob, ob.matrix_world.copy()))
        setMode('EDIT')
        for chain in self.chains:
            parb = rig.data.edit_bones[chain[0]]
            for child in chain[1:]:
                eb = rig.data.edit_bones[child]
                if isDrvBone(eb.parent.name):
                    self.relocate(parb, eb)
                    self.relocate(parb, eb.parent)
                    eb.parent.use_connect = True
                else:
                    self.relocate(parb, eb)
                    eb.use_connect = True
                parb = eb
        if self.unlock:
            for chain in self.chains:
                pb = rig.pose.bones[chain[-1]]
                pb.lock_location = FFalse
        setMode('OBJECT')
        for ob,wmat in wmats:
            setWorldMatrix(ob, wmat)


    def relocate(self, parb, eb):
        if self.location == 'TAIL':
            eb.head = parb.tail
        elif self.location == 'HEAD':
            parb.tail = eb.head
        elif self.location == 'CENTER':
            center = (eb.head + parb.tail)/2
            parb.tail = eb.head = center


    def getBoneNames(self, rig):
        if self.useSelected:
            roots = []
            for bone in rig.data.bones:
                if bone.parent is None:
                    roots.append(bone)
            for root in roots:
                self.getChildNames(rig, root)
            return
        if self.useArms:
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Arm")
                self.chains.append(chain)
        if self.useLegs:
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Leg")
                self.chains.append(chain)
        if self.useFingers:
            for prefix in ["l", "r"]:
                for finger in ["Thumb", "Index", "Mid", "Ring", "Pinky"]:
                    chain = self.getLimbBoneNames(rig, prefix, finger)
                    self.chains.append(chain)
        if self.useToes:
            for prefix in ["l", "r"]:
                for toe in ["BigToe", "SmallToe1", "SmallToe2", "SmallToe3", "SmallToe4"]:
                    chain = self.getLimbBoneNames(rig, prefix, toe)
                    if chain:
                        self.chains.append(chain)
        if self.useTongue:
            chain = self.getLimbBoneNames(rig, "", "Tongue")
            self.chains.append(chain)
        if self.useSpine:
            chain = self.getLimbBoneNames(rig, "", "Spine")
            self.chains.append(chain)
        if self.useNeck:
            chain = self.getLimbBoneNames(rig, "", "Neck")
            self.chains.append(chain)
        return


    def getChildNames(self, rig, bone):
        if bone.select:
            chain = []
            self.getChainNames(rig, bone, chain)
            self.chains.append(chain)
        else:
            for child in bone.children:
                self.getChildNames(rig, child)


    def getChainNames(self, rig, bone, chain):
        if bone.select:
            chain.append(bone.name)
            for child in bone.children:
                self.getChainNames(rig, child, chain)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ConnectBoneChains)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ConnectBoneChains)

