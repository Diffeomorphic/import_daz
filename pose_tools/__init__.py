# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
else:
    print("Loading Pose Tools")
    from . import save_poses
    PoseToolsFeature = True


class DAZ_PT_DazKeyPoses(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "Key Poses"

    def draw(self, context):
        self.layout.operator("daz.save_poses_to_file")
        self.layout.operator("daz.load_poses_from_file")
        self.layout.operator("daz.key_all_poses")
        self.layout.operator("daz.hide_unused_links")


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
                if pb.bone.select:
                    box = self.layout.box()
                    box.label(text = "%s : %s" % (rig.name, pb.name))
                    mat = rig.matrix_world @ pb.matrix
                    loc,quat,scale = mat.decompose()
                    vecRow(box, loc/rig.DazScale, "Location")
                    vecRow(box, Vector(quat.to_euler())/D, "Rotation")
                    vecRow(box, Vector(mat.col[1][0:3])/D, "Y Axis")
                    #self.vecRow(box, scale, "Scale")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_DazKeyPoses,
    #DAZ_PT_DazMatrix,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

def register():
    print("Register Pose Tools")
    from . import save_poses
    save_poses.register()

def unregister():
    from . import save_poses
    save_poses.unregister()
