# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..bone_chains import BoneChains

#-------------------------------------------------------------
#   Select chain roots
#-------------------------------------------------------------

class DAZ_OT_SelectChains(DazPropsOperator, IsArmature):
    bl_idname = "daz.select_chains"
    bl_label = "Select Chains"
    bl_description = "Select bones in chains"
    bl_options = {'UNDO'}

    useRootsOnly : BoolProperty(
        name = "Only Chain Roots",
        description = "Only select chain roots",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useRootsOnly")


    def run(self, context):
        def selectSubRoots(bone):
            if len(bone.children) > 1:
                for child in bone.children:
                    if self.useRootsOnly:
                        child.select = True
                    else:
                        selectChain(child)
            elif len(bone.children) == 1:
                selectSubRoots(bone.children[0])

        def selectChain(bone):
            bone.select = True
            if len(bone.children) == 1:
                selectChain(bone.children[0])

        rig = context.object
        for bone in rig.data.bones:
            bone.select = False
        roots = [bone for bone in rig.data.bones if bone.parent is None]
        for root in roots:
            selectSubRoots(root)

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

    useAlignLast : BoolProperty(
        name = "Align Last Bone",
        description = "Make last bone in each chain parallel to the second last one",
        default = False)

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
        self.layout.prop(self, "useAlignLast")


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
        if self.useAlignLast:
            for chain in self.chains:
                eb = rig.data.edit_bones[chain[-1]]
                parb = eb.parent
                vec = (parb.tail - parb.head).normalized()
                eb.tail = eb.head + eb.length*vec
        setMode('OBJECT')
        if self.unlock:
            for chain in self.chains:
                pb = rig.pose.bones[chain[-1]]
                pb.lock_location = FFalse
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
            roots = [bone for bone in rig.data.bones if bone.parent is None]
            for root in roots:
                self.getChildNames(root)
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


    def getChildNames(self, bone):
        if bone.select:
            chain = []
            self.getChainNames(bone, chain)
            self.chains.append(chain)
        else:
            for child in bone.children:
                self.getChildNames(child)


    def getChainNames(self, bone, chain):
        if bone.select:
            chain.append(bone.name)
            for child in bone.children:
                self.getChainNames(child, chain)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SelectChains,
    DAZ_OT_ConnectBoneChains,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
