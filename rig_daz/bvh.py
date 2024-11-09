#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
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
import os
from ..figure import *
from ..fileutils import SingleFile, JsonFile, ensureExt
from ..load_json import saveJson


def checkBvhEnabled(rig):
    pb = list(rig.pose.bones)[0]
    if not hasattr(pb, "McpBone"):
        raise DazError("BVH Retargeter not enabled")

#-------------------------------------------------------------
#   Add IK goals
#-------------------------------------------------------------


class DAZ_OT_SetTPose(DazPropsOperator, IsArmature):
    bl_idname = "daz.set_tpose"
    bl_label = "Set T-Pose"
    bl_description = "Set T-pose"
    bl_options = {'UNDO'}


    def run(self, context):
        rig = context.object
        checkBvhEnabled(rig)
        from retarget_bvh.t_pose import putInRestPose, TPose
        putInRestPose(context, rig, False)
        for pb in rig.pose.bones:
            untwist = (not pb.bone.select)
            if pb.McpBone == "hips":
                euler = Euler((90*D, 0, 0))
            elif pb.McpBone in ["spine", "spine-1", "chest", "chest-1", "neck", "head"]:
                euler = Euler((90*D, 0, 0))
            elif pb.McpBone in ["foot.L", "foot.R"]:
                euler = Euler((-150*D, 0, 0))
            elif pb.McpBone in ["toe.L", "toe.R"]:
                euler = Euler((180*D, 0, 0))
            elif pb.McpBone in TPose.keys():
                euler = Euler(TPose[pb.McpBone])
            else:
                continue
            pb.matrix = euler.to_matrix().to_4x4()
            updateScene(context)
            euler = pb.matrix_basis.to_euler('YZX')
            if untwist:
                euler.y = 0
            pb.matrix_basis = euler.to_matrix().to_4x4()

#-------------------------------------------------------------
#   Save T-pose
#-------------------------------------------------------------

class DAZ_OT_SaveTPose(DazOperator, SingleFile, JsonFile, IsArmature):
    bl_idname = "daz.save_tpose"
    bl_label = "Save T-Pose"
    bl_description = "Save T-pose"

    def run(self, context):
        rig = context.object
        checkBvhEnabled(rig)
        fname = os.path.splitext(os.path.basename(self.filepath))[0]
        struct = {}
        struct["name"] = fname.capitalize()
        tstruct = struct["t-pose"] = {}
        for pb in rig.pose.bones:
            if pb.McpBone:
                if pb.rotation_mode == 'QUATERNION':
                    quat = pb.rotation_quaternion
                else:
                    quat = pb.rotation_euler.to_quaternion()
                v = Vector(quat.to_euler())/D
                tstruct[pb.name] = (int(v[0]), int(v[1]), int(v[2]))
        filepath = ensureExt(bpy.path.abspath(self.filepath), ".json")
        saveJson(struct, filepath, binary=False, strict=False)
        print("T-pose file %s saved" % filepath)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SetTPose,
    DAZ_OT_SaveTPose,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
