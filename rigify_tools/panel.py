# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Rigging panel
#----------------------------------------------------------

import bpy
from ..utils import *
from ..panel import DAZ_PT_SetupTab
class DAZ_PT_DazRigifyBuild(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_label = "Rigify"

    def draw(self, context):
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")

#------------------------------------------------------------------------
#   DAZ Rigify props panels
#------------------------------------------------------------------------

class DAZ_PT_DazRigifyProps(bpy.types.Panel):
    bl_label = "DAZ Rigify Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and dazRna(ob).DazRig.startswith("rigify"))

    def draw(self, context):
        rig = context.object
        self.layout.prop(rig, "MhaGazeFollowsHead", text="Gaze Follows Head")
        row = self.layout.row()
        row.prop(rig, "MhaGaze_L", text="Left Gaze")
        row.prop(rig, "MhaGaze_R", text="Right Gaze")
        from ..fix import F_TONGUE
        if rig.data.MhaFeatures & F_TONGUE:
            self.layout.prop(rig, "MhaTongueIk", text="Tongue IK")
        self.layout.separator()
        row = self.layout.row()
        row.operator("daz.rigify_set_fk_all")
        row.operator("daz.rigify_set_ik_all")
        row = self.layout.row()
        row.operator("daz.rigify_snap_fk_all")
        row.operator("daz.rigify_snap_ik_all")
        row = self.layout.row()
        row.operator("daz.rigify_fk_layers")
        row.operator("daz.rigify_ik_layers")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_DazRigifyBuild,
    DAZ_PT_DazRigifyProps,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
