# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Categories(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMorphs"
    bl_idname = "DAZ_PT_Categories"
    bl_label = "Categories"

    def draw(self, context):
        self.layout.operator("daz.add_shape_to_category")
        self.layout.operator("daz.remove_shape_from_category")
        self.layout.operator("daz.rename_category")
        self.layout.operator("daz.join_categories")
        self.layout.operator("daz.remove_categories")
        self.layout.operator("daz.remove_standard_morphs")


class DAZ_PT_Shapekeys(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMorphs"
    bl_idname = "DAZ_PT_Shapekeys"
    bl_label = "Shapekeys"

    def draw(self, context):
        self.layout.operator("daz.convert_morphs_to_shapekeys")
        self.layout.operator("daz.transfer_animation_to_shapekeys")
        self.layout.operator("daz.transfer_mesh_to_shape")
        self.layout.separator()
        self.layout.operator("daz.remove_shapekeys")
        self.layout.operator("daz.apply_all_shapekeys")
        self.layout.operator("daz.mix_shapekeys")
        self.layout.operator("daz.visualize_shapekey")
        self.layout.operator("daz.mute_shapekeys")
        self.layout.separator()
        self.layout.operator("daz.update_slider_limits")
        self.layout.operator("daz.update_morph_paths")


class DAZ_PT_Drivers(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMorphs"
    bl_idname = "DAZ_PT_Drivers"
    bl_label = "Drivers"

    def draw(self, context):
        self.layout.operator("daz.convert_morphs_to_action")
        self.layout.operator("daz.remove_all_drivers")
        self.layout.separator()
        self.layout.operator("daz.add_shapekey_drivers")
        self.layout.operator("daz.remove_shapekey_drivers")
        self.layout.operator("daz.copy_drivers")
        self.layout.operator("daz.bake_all_erc_drivers")
        self.layout.operator("daz.add_driven_value_nodes")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Categories,
    DAZ_PT_Shapekeys,
    DAZ_PT_Drivers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
