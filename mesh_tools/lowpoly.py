# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *

#-------------------------------------------------------------
#   Make Low-poly
#-------------------------------------------------------------

class DAZ_OT_MakeLowPoly(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_lowpoly"
    bl_label = "Make Low Poly"
    bl_description = "Replace all selected meshes by low-poly versions"
    bl_options = {'UNDO'}

    keepUvIslands : BoolProperty(
        name = "Keep UV Islands",
        description = "Keep UV islands",
        default = True)

    iterations : IntProperty(
        name = "Iterations",
        description = "Number of times to unsubdivide",
        default = 2)

    useQuads : BoolProperty(
        name = "Quads",
        description = "Convert as many triangles to quads as possible",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "iterations")
        self.layout.prop(self, "keepUvIslands")
        self.layout.prop(self, "useQuads")

    def run(self, context):
        for ob in getSelectedMeshes(context):
            if activateObject(context, ob):
                setMode('EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                if self.keepUvIslands:
                    bpy.ops.uv.select_all(action='SELECT')
                    bpy.ops.uv.seams_from_islands()
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    setMode('OBJECT')
                    for e in ob.data.edges:
                        if e.use_seam:
                            e.select = True
                    setMode('EDIT')
                    bpy.ops.mesh.select_more()
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                    bpy.ops.mesh.select_all(action='INVERT')
                bpy.ops.mesh.unsubdivide(iterations = self.iterations)
                bpy.ops.mesh.select_all(action='SELECT')
                if self.useQuads:
                    setMode('OBJECT')
                    setMode('EDIT')
                    bpy.ops.mesh.tris_convert_to_quads(face_threshold=pi, shape_threshold=pi, seam=True)
                setMode('OBJECT')
        return

#-------------------------------------------------------------
#   Add push
#-------------------------------------------------------------

class DAZ_OT_AddPush(DazOperator, IsMesh):
    bl_idname = "daz.add_push"
    bl_label = "Add Push"
    bl_description = "Add a push shapekey"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..modifier import getBasisShape
        for ob in getSelectedMeshes(context):
            basis,skeys,new = getBasisShape(ob)
            skey = ob.shape_key_add(name="Push")
            scale = GS.scale
            for n,v in enumerate(ob.data.vertices):
                skey.data[n].co += v.normal*scale

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeLowPoly,
    DAZ_OT_AddPush,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
