# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "PoseToolsFeature" in locals():
    print("Reloading Pose Tools")
    import imp
    imp.reload(save_poses)
    imp.reload(mute)
    imp.reload(gaze)
    imp.reload(bake_fk)
    imp.reload(object_bones)
else:
    print("Loading Pose Tools")
    from . import save_poses
    from . import mute
    from . import gaze
    from . import bake_fk
    from . import object_bones
    PoseToolsFeature = True

#----------------------------------------------------------
#   Posing panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_RuntimeTab

class DAZ_PT_DazMhxRigify(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "MHX/Rigify"

    def draw(self, context):
        self.layout.operator("daz.bake_pose_to_fk_rig")
        self.layout.operator("daz.bake_shapekeys")
        self.layout.separator()
        self.layout.operator("daz.mute_control_rig")
        self.layout.operator("daz.unmute_control_rig")
        self.layout.operator("daz.toggle_control_rig")
        self.layout.separator()
        self.layout.operator("daz.transfer_to_gaze")
        self.layout.operator("daz.transfer_from_gaze")


class DAZ_PT_DazMorePoseTools(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "More Pose Tools"

    def draw(self, context):
        self.layout.operator("daz.object_pose_to_bones")
        self.layout.separator()
        self.layout.operator("daz.save_poses_to_file")
        self.layout.operator("daz.load_poses_from_file")
        self.layout.operator("daz.key_all_poses")


class DAZ_PT_DazMatrix(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "Matrix"

    def draw(self, context):
        def vecRow(layout, vec, text):
            row = layout.row()
            row.label(text=text)
            for n in range(3):
                row.label(text = "%.3f" % vec[n])

        from mathutils import Vector
        from ..utils import D, getSelectedArmatures
        for rig in getSelectedArmatures(context):
            for pb in rig.pose.bones:
                if P2B(pb).select:
                    box = self.layout.box()
                    box.label(text = "%s : %s" % (rig.name, pb.name))
                    mat = rig.matrix_world @ pb.matrix
                    loc,quat,scale = mat.decompose()
                    vecRow(box, loc/GS.scale, "Location")
                    vecRow(box, Vector(quat.to_euler())/D, "Rotation")
                    vecRow(box, Vector(mat.col[1][0:3])/D, "Y Axis")
                    #self.vecRow(box, scale, "Scale")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_DazMhxRigify,
    DAZ_PT_DazMorePoseTools,
    #DAZ_PT_DazMatrix,
]

def register():
    try:
        print("Register Pose Tools")
        for cls in classes:
            bpy.utils.register_class(cls)
        from . import save_poses, mute, gaze, bake_fk, object_bones
        save_poses.register()
        mute.register()
        gaze.register()
        bake_fk.register()
        object_bones.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        for cls in classes:
            bpy.utils.unregister_class(cls)
        from . import save_poses, mute, gaze, bake_fk, object_bones
        save_poses.unregister()
        mute.unregister()
        gaze.unregister()
        bake_fk.unregister()
        object_bones.unregister()
    except (RuntimeError, ValueError):
        pass
