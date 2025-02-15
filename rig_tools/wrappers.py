# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..daz import DriverModeItems

#-------------------------------------------------------------
#   Improve IK
#-------------------------------------------------------------

class DAZ_OT_ImproveIK(DazOperator, IsArmature):
    bl_idname = "daz.improve_ik"
    bl_label = "Improve IK"
    bl_description = "Improve IK behaviour"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..rig_utils import improveIk
        improveIk(context.object)

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
        from ..fix import setDriverModes
        setDriverModes(context.object, self.rotMode, (not self.useQuatsOnly))


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
                if pb.bone.select:
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
                if pb.bone.select:
                    pb.custom_shape = ob
                    setCustomShapeTransform(pb, self.scale, self.translation, Vector(self.rotation)*D)

#----------------------------------------------------------
#   Remove Driven Bones
#----------------------------------------------------------

class DAZ_OT_RemoveDrivenBones(DazOperator, IsArmature):
    bl_idname = "daz.remove_driven_bones"
    bl_label = "Remove Driven Bones"
    bl_description = "Remove driven (drv) bones and drive the posable bones.\nThis undoes Make All Bones Posable"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..bone_data import BD
        rig = context.object
        if rig.animation_data:
            for fcu in list(rig.animation_data.drivers):
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname and isDrvBone(bname):
                    fcu.data_path = fcu.data_path.replace("(drv)", "")
        for pb in rig.pose.bones:
            for cns in list(pb.constraints):
                if (cns.type in ['COPY_TRANSFORMS', 'COPY_ROTATION'] and
                    isDrvBone(cns.subtarget)):
                    pb.constraints.remove(cns)
        setMode('EDIT')
        for eb in list(rig.data.edit_bones):
            if isDrvBone(eb.name):
                rig.data.edit_bones.remove(eb)
        setMode('OBJECT')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImproveIK,
    DAZ_OT_OptimizePose,
    DAZ_OT_SetDriverModes,
    DAZ_OT_BatchSetCustomShape,
    DAZ_OT_RemoveDrivenBones,

]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
