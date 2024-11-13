#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
import math
from mathutils import *
from .utils import *
from .error import *

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
        from .animation import insertKeys
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
        from .animation import imposeLocks
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

#-------------------------------------------------------------
#   Improve IK
#-------------------------------------------------------------

class DAZ_OT_ImproveIK(DazOperator, IsArmature):
    bl_idname = "daz.improve_ik"
    bl_label = "Improve IK"
    bl_description = "Improve IK behaviour"
    bl_options = {'UNDO'}

    def run(self, context):
        improveIk(context.object)


def improveIk(rig, exclude=[]):
    ikconstraints = []
    for pb in rig.pose.bones:
        if pb.name in exclude:
            continue
        for cns in pb.constraints:
            if cns.type == 'IK':
                ikconstraints.append((pb, cns, cns.mute))
                cns.mute = True
                pb.rotation_euler[0] = 30*D
                pb.lock_rotation[0] = True
    for pb,cns,mute in ikconstraints:
        pb.lock_rotation = TTrue
        pb.lock_location = TTrue
        cns.mute = mute
        pb.use_ik_limit_y = pb.use_ik_limit_z = False
        pb.lock_ik_y = pb.lock_ik_z = True
        pb.use_ik_limit_x = True
        pb.ik_min_x = -15*D
        pb.ik_max_x = 160*D

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
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ImproveIK,
    DAZ_OT_BatchSetCustomShape,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
