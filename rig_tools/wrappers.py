# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..daz import DriverModeItems

#-------------------------------------------------------------
#   Optimize pose for IK
#   Function used by rigify
#-------------------------------------------------------------

class DAZ_OT_OptimizePose(DazPropsOperator, IsArmature):
    bl_idname = "daz.optimize_pose"
    bl_label = "Optimize Pose For IK"
    bl_description = "Optimize pose for IK.\nIncompatible with pose loading and body morphs"
    bl_options = {'UNDO'}

    useApplyRestPose : BoolProperty(
        name = "Apply Rest Pose",
        description = "Apply current pose as rest pose for all armatures",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useApplyRestPose")

    def run(self, context):
        from ..convert import optimizePose
        optimizePose(context, self.useApplyRestPose)


#----------------------------------------------------------
#   Set driver modes
#----------------------------------------------------------

class DAZ_OT_SetDriverModes(DazPropsOperator, IsArmature):
    bl_idname = "daz.set_driver_modes"
    bl_label = "Set Driver Modes"
    bl_description = "Change driver rotation modes.\nAvoids some popping during animation at the cost of JCMs accuracy"
    bl_options = {'UNDO'}

    rotMode : EnumProperty(
        items = DriverModeItems,
        name = "Rotation Mode",
        description = "Use this rotation mode",
        default = 'AUTO')

    useQuatsOnly : BoolProperty(
        name = "Only Quaternion Bones",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useQuatsOnly")
        self.layout.prop(self, "rotMode")

    def run(self, context):
        setDriverModes(context.object, self.rotMode, (not self.useQuatsOnly))


def setDriverModes(rig, rotmode, useAll):
    def setModes(rna):
        if rna.animation_data:
            for fcu in rna.animation_data.drivers:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        if useAll or trg.bone_target in quats:
                            trg.rotation_mode = rotmode

    if rotmode == 'NATIVE':
        return
    quats = [pb.name for pb in rig.pose.bones if pb.rotation_mode == 'QUATERNION']
    setModes(rig)
    setModes(rig.data)
    for ob in getShapeChildren(rig):
        setModes(ob.data.shape_keys)

#----------------------------------------------------------
#   Batch set custom shape
#----------------------------------------------------------

class DAZ_OT_BatchSetCustomShape(DazPropsOperator, IsArmature):
    bl_idname = "daz.batch_set_custom_shape"
    bl_label = "Batch Set Custom Shape"
    bl_description = "Set the selected mesh as the custom shape of all selected bones"
    bl_options = {'UNDO'}

    useClear : BoolProperty(
        name = "Clear custom shapes",
        default = False)

    scale : FloatVectorProperty(
        name = "Scale",
        size=3,
        default=(1,1,1))

    translation : FloatVectorProperty(
        name = "Translation",
        size=3,
        default=(0,0,0))

    rotation : FloatVectorProperty(
        name = "Rotation",
        size=3,
        default=(0,0,0))

    def draw(self, context):
        self.layout.prop(self, "useClear")
        if not self.useClear:
            self.layout.prop(self, "scale")
            self.layout.prop(self, "translation")
            self.layout.prop(self, "rotation")

    def run(self, context):
        rig = context.object
        if self.useClear:
            for pb in rig.pose.bones:
                if P2B(pb).select:
                    pb.custom_shape = None
        else:
            ob = None
            for ob1 in getSelectedObjects(context):
                if ob1 != rig:
                    ob = ob1
                    break
            if ob is None:
                raise DazError("No custom shape object selected")
            for pb in rig.pose.bones:
                if P2B(pb).select:
                    pb.custom_shape = ob
                    setCustomShapeTransform(pb, self.scale, self.translation, Vector(self.rotation)*D)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_OptimizePose,
    DAZ_OT_SetDriverModes,
    DAZ_OT_BatchSetCustomShape,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
