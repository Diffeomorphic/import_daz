# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Matrix
from ..utils import *
from ..error import *
from ..animation import FrameRange

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
        if self.auto:
            wmats = {}
            parmats = {}
            chmats = {}
            for frame in range(self.startFrame, self.endFrame+1):
                scn.frame_current = frame
                updateScene(context)
                wmats[frame] = rig.matrix_world.copy()
                parmats[frame] = [pb.matrix.copy() for pb in parents]
                chmats[frame] = [pb.matrix.copy() for pb in children]
            for frame in range(self.startFrame, self.endFrame+1):
                scn.frame_current = frame
                rig.matrix_basis = Matrix()
                insertKeys(rig, False, frame)
                updateScene(context)
                wmat = wmats[frame]
                for pb,mat in zip(parents, parmats[frame]):
                    if self.useSkipRoots:
                        pb.matrix = Matrix()
                    else:
                        pb.matrix = wmat @ mat
                    insertKeys(pb, True, frame)
                updateScene(context)
                if self.useSkipRoots:
                    for pb,mat in zip(children, chmats[frame]):
                        pb.matrix = wmat @ mat
                        insertKeys(pb, True, frame)
        else:
            wmat = rig.matrix_world.copy()
            parmats = [pb.matrix.copy() for pb in parents]
            chmats = [pb.matrix.copy() for pb in children]
            rig.matrix_basis = Matrix()
            updateScene(context)
            for pb,mat in zip(parents, parmats):
                if self.useSkipRoots:
                    pb.matrix = Matrix()
                else:
                    pb.matrix = wmat @ mat
            updateScene(context)
            if self.useSkipRoots:
                for pb,mat in zip(children, chmats):
                    pb.matrix = wmat @ mat

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ObjectPoseToBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
