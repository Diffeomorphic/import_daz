# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab


class DAZ_PT_Mesh(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_Mesh"
    bl_label = "Mesh"

    def draw(self, context):
        self.layout.operator("daz.merge_meshes")
        self.layout.operator("daz.convert_tubes_curves")


class DAZ_PT_Lowpoly(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Mesh"
    bl_idname = "DAZ_PT_Lowpoly"
    bl_label = "Lowpoly"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.make_lowpoly")
        self.layout.operator("daz.add_push")


class DAZ_PT_UvMaps(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Mesh"
    bl_idname = "DAZ_PT_UvMaps"
    bl_label = "UV Maps"

    def draw(self, context):
        self.layout.operator("daz.merge_uv_layers")
        self.layout.operator("daz.find_seams")
        self.layout.operator("daz.load_uv")
        self.layout.operator("daz.collapse_udims")
        self.layout.operator("daz.restore_udims")
        self.layout.operator("daz.copy_uvs")


class DAZ_PT_Attributes(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Mesh"
    bl_idname = "DAZ_PT_Attributes"
    bl_label = "Attributes"

    def draw(self, context):
        self.layout.operator("daz.copy_attributes")
        self.layout.operator("daz.display_material_group")
        self.layout.operator("daz.display_polygon_group")
        self.layout.operator("daz.display_cond_graft_group")


class DAZ_PT_VertexGroups(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Mesh"
    bl_idname = "DAZ_PT_VertexGroups"
    bl_label = "Vertex Groups"

    def draw(self, context):
        self.layout.operator("daz.limit_vertex_groups")
        self.layout.operator("daz.prune_vertex_groups")
        self.layout.operator("daz.create_graft_groups")
        self.layout.operator("daz.transfer_vertex_groups")
        self.layout.operator("daz.transfer_uv_layers")
        self.layout.operator("daz.modify_vertex_group")


class DAZ_PT_Modifiers(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Mesh"
    bl_idname = "DAZ_PT_Modifiers"
    bl_label = "Modifiers"

    def draw(self, context):
        self.layout.operator("daz.apply_subsurf")
        self.layout.operator("daz.apply_multires")
        self.layout.operator("daz.apply_active_modifier")
        self.layout.operator("daz.copy_modifiers")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Mesh,
    DAZ_PT_Lowpoly,
    DAZ_PT_UvMaps,
    DAZ_PT_Attributes,
    DAZ_PT_Modifiers,
    DAZ_PT_VertexGroups,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
