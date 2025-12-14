# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab

class DAZ_PT_EditMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_EditMaterials"
    bl_label = "Edit Materials"

    def draw(self, context):
        self.layout.operator("daz.make_udim_materials")
        self.layout.separator()
        self.layout.operator("daz.launch_editor")
        self.layout.operator("daz.reset_materials")
        self.layout.separator()
        self.layout.operator("daz.make_combo_material")
        self.layout.separator()
        self.layout.operator("daz.make_palette")
        self.layout.separator()
        self.layout.operator("daz.make_decal")
        self.layout.prop(context.scene, "DazDecalMask")


class DAZ_PT_MoreMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_MoreMaterials"
    bl_label = "More Material Tools"

    def draw(self, context):
        self.layout.operator("daz.change_skin_color")
        self.layout.operator("daz.sort_materials_by_name")
        self.layout.operator("daz.strip_material_names")
        self.layout.operator("daz.copy_materials")
        self.layout.separator()
        self.layout.operator("daz.find_missing_textures")
        self.layout.operator("daz.activate_diffuse")
        self.layout.separator()
        self.layout.operator("daz.change_resolution")


class DAZ_PT_DebugMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_DebugMaterials"
    bl_label = "Debug Materials"

    def draw(self, context):
        self.layout.operator("daz.update_render_settings")
        self.layout.separator()
        self.layout.operator("daz.tiles_from_geograft")
        self.layout.operator("daz.fix_texture_tiles")
        self.layout.operator("daz.set_udims")
        self.layout.separator()
        self.layout.operator("daz.prune_node_trees")
        self.layout.operator("daz.prune_uv_maps")
        self.layout.separator()
        self.layout.operator("daz.make_shader_groups")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_EditMaterials,
    DAZ_PT_MoreMaterials,
    DAZ_PT_DebugMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
