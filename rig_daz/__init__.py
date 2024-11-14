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

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "bpy" in locals():
    print("Reloading DAZ Rigging")
    import imp
    imp.reload(mute)
    imp.reload(ikgoals)
    imp.reload(store)
    imp.reload(bvh)
    imp.reload(mannequin)
    imp.reload(unreal)
else:
    print("Loading DAZ Rigging")
    from . import mute
    from . import ikgoals
    from . import store
    from . import bvh
    from . import mannequin
    from . import unreal

#----------------------------------------------------------
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab

class DAZ_PT_DazRigBuild(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_label = "More Rigging Tools"

    def draw(self, context):
        self.layout.operator("daz.add_mannequin")
        self.layout.operator("daz.categorize_objects")
        self.layout.separator()
        self.layout.operator("daz.select_matching_bones")
        self.layout.operator("daz.add_ik_goals")
        self.layout.operator("daz.add_winders")
        self.layout.operator("daz.add_tails")
        self.layout.operator("daz.move_graft_bones")
        self.layout.separator()
        self.layout.operator("daz.make_eulers")
        self.layout.operator("daz.lock_channels")
        self.layout.operator("daz.clear_center")
        return
        self.layout.separator()
        self.layout.operator("daz.set_tpose")
        self.layout.operator("daz.save_tpose")


class DAZ_PT_DazRigPose(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "More Posing"

    def draw(self, context):
        self.layout.operator("daz.save_poses_to_file")
        self.layout.operator("daz.load_poses_from_file")
        self.layout.operator("daz.key_all_poses")
        self.layout.operator("daz.hide_unused_links")
        return
        self.layout.separator()
        self.layout.operator("daz.make_unreal")
        self.layout.operator("daz.export_unreal")


class DAZ_PT_DazMatrix(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Matrix"

    def draw(self, context):
        from mathutils import Vector
        from ..utils import D, getSelectedArmatures
        for rig in getSelectedArmatures(context):
            for pb in rig.pose.bones:
                if pb.bone.select:
                    box = self.layout.box()
                    box.label(text = "%s : %s" % (rig.name, pb.name))
                    mat = rig.matrix_world @ pb.matrix
                    loc,quat,scale = mat.decompose()
                    self.vecRow(box, loc/rig.DazScale, "Location")
                    self.vecRow(box, Vector(quat.to_euler())/D, "Rotation")
                    self.vecRow(box, Vector(mat.col[1][0:3])/D, "Y Axis")
                    #self.vecRow(box, scale, "Scale")

    def vecRow(self, layout, vec, text):
        row = layout.row()
        row.label(text=text)
        for n in range(3):
            row.label(text = "%.3f" % vec[n])

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_DazRigBuild,
    DAZ_PT_DazRigPose,
    DAZ_PT_DazMatrix
]

def register():
    print("Register DAZ Rigging")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import mute, ikgoals, store, bvh, mannequin, unreal
    mute.register()
    ikgoals.register()
    store.register()
    bvh.register()
    mannequin.register()
    #unreal.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    from . import mute, ikgoals, store, bvh, mannequin, unreal
    #unreal.unregister()
    mannequin.unregister()
    bvh.unregister()
    store.unregister()
    ikgoals.unregister()
    mute.unregister()
