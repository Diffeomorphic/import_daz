# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..figure import ExtraBones


class DAZ_OT_SetAddExtraFaceBones(DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.add_extra_face_bones"
    bl_label = "Add Extra Face Bones"
    bl_description = "Add an extra layer of face bones, which can be both driven and posed"
    bl_options = {'UNDO'}

    type =  "face"
    attr = "DazExtraFaceBones"
    button = "Add Extra Face Bones"

    def getBoneNames(self, rig):
        def getAnchoredBoneNames(rig, anchors):
            bnames = []
            keys = rig.pose.bones.keys()
            for anchor in anchors:
                if anchor in keys:
                    for pb in rig.pose.bones:
                        if (not isDrvBone(pb.name) and
                            drvBone(pb.name) not in keys and
                            pb.parent and
                            pb.parent.name == anchor):
                            bnames.append(pb.name)
            return bnames

        inface = [
            "lEye", "rEye", "eye.L", "eye.R",
            "lowerJaw", "upperTeeth", "lowerTeeth", "lowerFaceRig",
            "tongue01", "tongue02", "tongue03", "tongue04",
            "tongue05", "tongue06", "tongueBase", "tongueTip",
        ]
        keys = rig.pose.bones.keys()
        bnames = [bname for bname in inface
                  if bname in keys and
                    drvBone(bname) not in keys]
        bnames += getAnchoredBoneNames(rig, ["upperFaceRig", "lowerFaceRig"])
        return bnames

    def checkAllowed(self, rig):
        return True

    def changeLayer(self, eb, rig):
        if dazRna(rig).DazRig == "mhx":
            from ..mhx_tools import L_FACE
            enableBoneNumLayer(eb, rig, L_FACE)
        elif dazRna(rig).DazRig.startswith("rigify"):
            from ..rigify_tools import R_DETAIL
            enableBoneNumLayer(eb, rig, R_DETAIL)

    def hasBoneDriver(self, bname, drivers):
        return True

#-------------------------------------------------------------
#   Fix legacy posable bones
#-------------------------------------------------------------

class DAZ_OT_FixLegacyPosable(DazOperator, ExtraBones, IsArmature):
    bl_idname = "daz.fix_legacy_posable"
    bl_label = "Fix Legacy Posable Bones"
    bl_description = "Convert legacy posable bones to modern ones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        if isFinal(trg.bone_target):
                            trg.bone_target = baseBone(trg.bone_target)
        parents = {}
        setMode('EDIT')
        for eb in list(rig.data.edit_bones):
            par = eb.parent
            if par and isDrvBone(par.name):
                eb.parent = par.parent
                parents[eb.name] = par.name
            if isFinal(eb.name):
                rig.data.edit_bones.remove(eb)
        setMode('OBJECT')
        for bname in parents.keys():
            self.addCopyConstraint(rig, bname, [], [])


    def hasBoneDriver(self, bname, drivers):
        return True

#-------------------------------------------------------------
#   Rotate bones
#-------------------------------------------------------------

class DAZ_OT_RotateBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.rotate_bones"
    bl_label = "Rotate Bones"
    bl_description = "Rotate selected bones the same angle"
    bl_options = {'UNDO'}

    X : FloatProperty(name = "X")
    Y : FloatProperty(name = "Y")
    Z : FloatProperty(name = "Z")

    def draw(self, context):
        self.layout.prop(self, "X")
        self.layout.prop(self, "Y")
        self.layout.prop(self, "Z")

    def run(self, context):
        rig = context.object
        rot = Vector((self.X, self.Y, self.Z))*D
        quat = Euler(rot).to_quaternion()
        for pb in rig.pose.bones:
            if pb.bone.select:
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_quaternion = quat
                else:
                    pb.rotation_euler = rot

#-------------------------------------------------------------
#   Fix limit rotation constraints
#-------------------------------------------------------------

class DAZ_OT_FixLimitRotConstraints(DazOperator, IsArmature):
    bl_idname = "daz.fix_limit_rot_constraints"
    bl_label = "Fix Limit Rotation Constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..bone_data import BD
        rig = context.object
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'LIMIT_ROTATION':
                    setEulerOrder(cns, BD.getDefaultMode(pb))

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SetAddExtraFaceBones,
    DAZ_OT_FixLegacyPosable,
    DAZ_OT_RotateBones,
    DAZ_OT_FixLimitRotConstraints,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
