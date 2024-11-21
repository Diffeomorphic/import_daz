# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Matrix
from ..utils import *
from ..error import *

#----------------------------------------------------------
#   Copy Absolute Pose
#----------------------------------------------------------

class DAZ_OT_CopyAbsolutePose(DazOperator, IsArmature):
    bl_idname = "daz.copy_absolute_pose"
    bl_label = "Copy Absolute Pose"
    bl_description = (
        "Copy pose in world space from active to selected armatures.\n" +
        "Only works properly if both armatures have the same bone names")
    bl_options = {'UNDO'}

    def run(self, context):
        from ..animation import insertKeys
        src = context.object
        scn = context.scene
        auto = scn.tool_settings.use_keyframe_insert_auto
        roots = [pb for pb in src.pose.bones if pb.parent is None]
        for trg in getSelectedArmatures(context):
            if trg != src:
                for root in roots:
                    self.copyPose(root, trg)
                if auto:
                    for pb in trg.pose.bones:
                        insertKeys(pb, True, scn.frame_current)


    def copyPose(self, pb, trg):
        from ..animation import imposeLocks
        trgpb = trg.pose.bones.get(pb.name)
        if trgpb:
            loc = trgpb.location.copy()
            trgpb.matrix = pb.matrix.copy()
            updatePose()
            if trgpb.parent:
                trgpb.location = loc
            imposeLocks(trgpb)
            for child in pb.children:
                self.copyPose(child, trg)

#----------------------------------------------------------
#   Object pose to bones
#----------------------------------------------------------

class DAZ_OT_ObjectPoseToBones(DazOperator, IsArmature):
    bl_idname = "daz.object_pose_to_bones"
    bl_label = "Object Pose To Bones"
    bl_description = "Clear object transform and transfer pose to unparented bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        mats = []
        for pb in rig.pose.bones:
            if pb.parent is None:
                mat = pb.matrix.copy()
                mats.append((pb, mat))
        wmat = rig.matrix_world.copy()
        rig.matrix_basis = Matrix()
        for pb,mat in mats:
            pb.matrix = wmat @ mat

#----------------------------------------------------------
#   Pose to children
#----------------------------------------------------------

class DAZ_OT_PoseToChildren(DazOperator, IsArmature):
    bl_idname = "daz.pose_to_children"
    bl_label = "Pose To Children"
    bl_description = "Clear selected bones and transfer pose to children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        pbones = [pb for pb in rig.pose.bones if pb.bone.select]
        mats = []
        for pb in rig.pose.bones:
            if pb.parent in pbones:
                mat = pb.matrix.copy()
                mats.append((pb, mat))
        for pb in pbones:
            pb.matrix_basis = Matrix()
        updateObject(context, rig)
        for pb,mat in mats:
            pb.matrix = mat

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ObjectPoseToBones,
    DAZ_OT_PoseToChildren,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
