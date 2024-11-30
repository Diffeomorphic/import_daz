# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Matrix
from ..utils import *
from ..error import *
from ..animation import FrameRange

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

class DAZ_OT_ObjectPoseToBones(FrameRange, IsArmature):
    bl_idname = "daz.object_pose_to_bones"
    bl_label = "Object Pose To Bones"
    bl_description = "Clear object transform and transfer pose to unparented bones"
    bl_options = {'UNDO'}

    useSkipRoots: BoolProperty(
        name = "Skip Root Bones",
        description = "Clear unparented bones and transfer pose to its children",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useSkipRoots")
        FrameRange.draw(self, context)


    def run(self, context):
        from ..animation import insertKeys
        rig = context.object
        scn = context.scene
        parents = [pb for pb in rig.pose.bones if pb.parent is None]
        children = [pb for pb in rig.pose.bones if pb.parent in parents]

        def poseToChildren():
            mats = [pb.matrix.copy() for pb in children]
            for pb in parents:
                pb.matrix_basis = Matrix()
                if self.auto:
                    insertKeys(pb, True, frame)
            updateObject(context, rig)
            for pb,mat in zip(children, mats):
                pb.matrix = mat
                if self.auto:
                    insertKeys(pb, True, frame)

        def objectToBones():
            mats = [pb.matrix.copy() for pb in parents]
            wmat = rig.matrix_world.copy()
            rig.matrix_basis = Matrix()
            for pb,mat in zip(parents, mats):
                pb.matrix = wmat @ mat

        if self.auto:
            for frame in range(self.startFrame, self.endFrame+1):
                scn.frame_current = frame
                updateScene(context)
                objectToBones()
                insertKeys(rig, False, frame)
                for pb in parents:
                    insertKeys(pb, True, frame)
            if self.useSkipRoots:
                for frame in range(self.startFrame, self.endFrame+1):
                    scn.frame_current = frame
                    updateScene(context)
                    poseToChildren()
        else:
            objectToBones()
            if self.useSkipRoots:
                poseToChildren()

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ObjectPoseToBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
