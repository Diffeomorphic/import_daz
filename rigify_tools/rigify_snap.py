# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from .layers import *

class RigifyOperator(DazOperator):
    useReport = False

    @classmethod
    def poll(self, context):
        rig = context.object
        return (rig and "rig_id" in rig.data.keys())

#----------------------------------------------------------
#   Snap IK
#----------------------------------------------------------

class DAZ_OT_RigifySnapIkAll(RigifyOperator):
    bl_idname = "daz.rigify_snap_ik_all"
    bl_label = "Snap IK"
    bl_description = "Snap all IK bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        rig_id = rig.data["rig_id"]
        op = getattr(bpy.ops.pose, "rigify_limb_ik2fk_%s" % rig_id)

        op(prop_bone = "upper_arm_parent.L",
           fk_bones = '["upper_arm_fk.L", "forearm_fk.L", "hand_fk.L"]',
           ik_bones = '["upper_arm_ik.L", "MCH-forearm_ik.L", "MCH-upper_arm_ik_target.L"]',
           ctrl_bones = '["upper_arm_ik.L", "upper_arm_ik_target.L", "hand_ik.L"]',
           tail_bones = '[]',
           extra_ctrls = '[]')

        op(prop_bone = "upper_arm_parent.R",
           fk_bones = '["upper_arm_fk.R", "forearm_fk.R", "hand_fk.R"]',
           ik_bones = '["upper_arm_ik.R", "MCH-forearm_ik.R", "MCH-upper_arm_ik_target.R"]',
           ctrl_bones = '["upper_arm_ik.R", "upper_arm_ik_target.R", "hand_ik.R"]',
           tail_bones = '[]',
           extra_ctrls = '[]')

        op(prop_bone = "thigh_parent.L",
           fk_bones = '["thigh_fk.L", "shin_fk.L", "foot_fk.L", "toe_fk.L"]',
           ik_bones = '["thigh_ik.L", "MCH-shin_ik.L", "MCH-thigh_ik_target.L"]',
           ctrl_bones = '["thigh_ik.L", "thigh_ik_target.L", "foot_ik.L"]',
           tail_bones = '["toe_ik.L"]',
           extra_ctrls = '["foot_heel_ik.L", "foot_spin_ik.L"]')

        op(prop_bone = "thigh_parent.R",
           fk_bones = '["thigh_fk.R", "shin_fk.R", "foot_fk.R", "toe_fk.R"]',
           ik_bones = '["thigh_ik.R", "MCH-shin_ik.R", "MCH-thigh_ik_target.R"]',
           ctrl_bones = '["thigh_ik.R", "thigh_ik_target.R", "foot_ik.R"]',
           tail_bones = '["toe_ik.R"]',
           extra_ctrls = '["foot_heel_ik.R", "foot_spin_ik.R"]')

#----------------------------------------------------------
#   Snap FK
#----------------------------------------------------------

class DAZ_OT_RigifySnapFkAll(RigifyOperator):
    bl_idname = "daz.rigify_snap_fk_all"
    bl_label = "Snap FK"
    bl_description = "Snap all FK bones"
    bl_options = {'UNDO'}

    useReport = False

    @classmethod
    def poll(self, context):
        rig = context.object
        return (rig and "rig_id" in rig.data.keys())

    def run(self, context):
        rig = context.object
        rig_id = rig.data["rig_id"]
        op = getattr(bpy.ops.pose, "rigify_generic_snap_%s" % rig_id)

        op(input_bones = '["upper_arm_ik.L", "MCH-forearm_ik.L", "MCH-upper_arm_ik_target.L"]',
           output_bones = '["upper_arm_fk.L", "forearm_fk.L", "hand_fk.L"]',
           ctrl_bones = '["upper_arm_ik.L", "upper_arm_ik_target.L", "hand_ik.L"]')

        op(input_bones = '["upper_arm_ik.R", "MCH-forearm_ik.R", "MCH-upper_arm_ik_target.R"]',
           output_bones = '["upper_arm_fk.R", "forearm_fk.R", "hand_fk.R"]',
           ctrl_bones = '["upper_arm_ik.R", "upper_arm_ik_target.R", "hand_ik.R"]')

        op(input_bones = '["thigh_ik.L", "MCH-shin_ik.L", "MCH-thigh_ik_target.L", "toe_ik.L"]',
           output_bones = '["thigh_fk.L", "shin_fk.L", "foot_fk.L", "toe_fk.L"]',
           ctrl_bones = '["thigh_ik.L", "thigh_ik_target.L", "foot_ik.L", "toe_ik.L", "foot_heel_ik.L", "foot_spin_ik.L"]')

        op(input_bones = '["thigh_ik.R", "MCH-shin_ik.R", "MCH-thigh_ik_target.R", "toe_ik.R"]',
           output_bones = '["thigh_fk.R", "shin_fk.R", "foot_fk.R", "toe_fk.R"]',
           ctrl_bones = '["thigh_ik.R", "thigh_ik_target.R", "foot_ik.R", "toe_ik.R", "foot_heel_ik.R", "foot_spin_ik.R"]')

#-------------------------------------------------------------
#   Set rigify to IK or FK
#-------------------------------------------------------------

class DAZ_OT_RigifySetFkAll(RigifyOperator):
    bl_idname = "daz.rigify_set_fk_all"
    bl_label = "Set FK"
    bl_description = "Set all limb bones to FK"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        scn = context.scene
        auto = scn.tool_settings.use_keyframe_insert_auto
        setRigifyFkIk(rig, 1.0, auto, scn.frame_current)


class DAZ_OT_RigifySetIkAll(RigifyOperator):
    bl_idname = "daz.rigify_set_ik_all"
    bl_label = "Set IK"
    bl_description = "Set all limb bones to IK"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        scn = context.scene
        auto = scn.tool_settings.use_keyframe_insert_auto
        setRigifyFkIk(rig, 0.0, auto, scn.frame_current)

#-------------------------------------------------------------
#   Set rigify to IK or FK
#-------------------------------------------------------------

class DAZ_OT_RigifyFkLayers(RigifyOperator):
    bl_idname = "daz.rigify_fk_layers"
    bl_label = "FK Layers"
    bl_description = "Show FK layers and hide IK layers"
    bl_options = {'UNDO'}

    def run(self, context):
        enable = [R_ARMFK_L, R_ARMFK_R, R_LEGFK_L, R_LEGFK_R]
        disable = [R_ARMIK_L, R_ARMIK_R, R_LEGIK_L, R_LEGIK_R]
        rig = context.object
        for layer in enable:
            enableRigNumLayer(rig, layer, True)
        for layer in disable:
            enableRigNumLayer(rig, layer, False)


class DAZ_OT_RigifyIkLayers(RigifyOperator):
    bl_idname = "daz.rigify_ik_layers"
    bl_label = "IK Layers"
    bl_description = "Show IK layers and hide FK layers"
    bl_options = {'UNDO'}

    def run(self, context):
        disable = [R_ARMFK_L, R_ARMFK_R, R_LEGFK_L, R_LEGFK_R]
        enable = [R_ARMIK_L, R_ARMIK_R, R_LEGIK_L, R_LEGIK_R]
        rig = context.object
        for layer in enable:
            enableRigNumLayer(rig, layer, True)
        for layer in disable:
            enableRigNumLayer(rig, layer, False)

#-------------------------------------------------------------
#   Set rigify to FK. For load pose.
#-------------------------------------------------------------

def setRigifyFkIk(rig, fk, useInsertKeys, frame):
    for bname in ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]:
        pb = rig.pose.bones[bname]
        pb["IK_FK"] = fk
        if useInsertKeys:
            pb.keyframe_insert(propRef("IK_FK"), frame=frame)


def setRigifyLayers(rig, fk, layers):
    if fk:
        enable = [R_ARMFK_L, R_ARMFK_R, R_LEGFK_L, R_LEGFK_R]
        disable = [R_ARMIK_L, R_ARMIK_R, R_LEGIK_L, R_LEGIK_R]
    else:
        disable = [R_ARMFK_L, R_ARMFK_R, R_LEGFK_L, R_LEGFK_R]
        enable = [R_ARMIK_L, R_ARMIK_R, R_LEGIK_L, R_LEGIK_R]
    if BLENDER3:
        for n in enable:
            layers[n] = True
        for n in disable:
            layers[n] = False
    else:
        for cname in enable:
            layers[cname] = rig.data.collections.get(cname)
        for cname in disable:
            if cname in layers.keys():
                del layers[cname]
    return layers


def clearOtherRigify(rig, useInsertKeys, frame):
    if "torso" in rig.pose.bones.keys():
        pb = rig.pose.bones["torso"]
        pb["neck_follow"] = 1.0
        pb["head_follow"] = 1.0
        if useInsertKeys:
            pb.keyframe_insert(propRef("neck_follow"), frame=frame)
            pb.keyframe_insert(propRef("head_follow"), frame=frame)
    for suffix in ["L", "R"]:
        for fing in ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]:
            pb = rig.pose.bones.get("%s.01_ik.%s" % (fing, suffix))
            if pb:
                pb["FK_IK"] = 0.0
                if useInsertKeys:
                    pb.keyframe_insert(propRef("FK_IK"), frame=frame)
    for pname in ["MhaTongueIk"]:
        if pname in rig.keys():
            rig[pname] = 0.0
            if useInsertKeys:
                rig.keyframe_insert(propRef(pname), frame=frame)
        if pname in rig.data.keys():
            rig.data[pname] = 0.0
            if useInsertKeys:
                rig.data.keyframe_insert(propRef(pname), frame=frame)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_RigifySnapFkAll,
    DAZ_OT_RigifySnapIkAll,
    DAZ_OT_RigifySetFkAll,
    DAZ_OT_RigifySetIkAll,
    DAZ_OT_RigifyFkLayers,
    DAZ_OT_RigifyIkLayers
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
