# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab

class DAZ_PT_Figures(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_id = "DAZ_PT_Figures"
    bl_label = "Figures"

    def draw(self, context):
        self.layout.operator("daz.change_prefix_to_suffix")
        self.layout.operator("daz.change_suffix_to_prefix")
        self.layout.separator()
        self.layout.operator("daz.lock_channels")
        self.layout.operator("daz.clear_center")
        self.layout.operator("daz.optimize_pose")
        self.layout.operator("daz.improve_ik")
        self.layout.operator("daz.set_driver_modes")


class DAZ_PT_Chains(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_id = "DAZ_PT_Chains"
    bl_label = "Chains"

    def draw(self, context):
        self.layout.operator("daz.select_matching_bones")
        self.layout.operator("daz.add_ik_goals")
        self.layout.operator("daz.add_winders")
        self.layout.operator("daz.add_tails")
        self.layout.operator("daz.move_graft_bones")


class DAZ_PT_MoreRigging(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_id = "DAZ_PT_MoreRigging"
    bl_label = "More Rigging Tools"

    def draw(self, context):
        self.layout.operator("daz.add_extra_face_bones")
        self.layout.operator("daz.batch_set_custom_shape")
        self.layout.operator("daz.make_eulers")
        self.layout.separator()
        self.layout.operator("daz.remove_driven_bones")
        self.layout.operator("daz.fix_limit_rot_constraints")
        self.layout.operator("daz.fix_legacy_posable")
        self.layout.operator("daz.rotate_bones")
        return

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Figures,
    DAZ_PT_Chains,
    DAZ_PT_MoreRigging,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
