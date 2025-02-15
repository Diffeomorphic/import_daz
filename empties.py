# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import bmesh
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Eliminate Empties
#-------------------------------------------------------------

class DAZ_OT_EliminateEmpties(DazPropsOperator):
    bl_idname = "daz.eliminate_empties"
    bl_label = "Eliminate Empties"
    bl_description = "Delete empties, parenting its children to its parent instead"
    bl_options = {'UNDO'}

    useAllEmpties : BoolProperty(
        name = "Eliminate All Empties",
        description = "Eliminate all empties in the scene,\nnot only those associated with selected objects",
        default = True)

    useCollections : BoolProperty(
        name = "Create Collections",
        description = "Replace empties with collections",
        default = False)

    useHidden : BoolProperty(
        name = "Delete Hidden Empties",
        description = "Also delete empties that are hidden",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useAllEmpties")
        self.layout.prop(self, "useHidden")
        self.layout.prop(self, "useCollections")


    def run(self, context):
        roots = []
        if self.useAllEmpties:
            objects = getVisibleObjects(context)
        else:
            objects = getSelectedObjects(context)
        for ob in objects:
            if ob.parent is None:
                roots.append(ob)
        for root in roots:
            if self.useCollections:
                coll = getCollection(context, root)
            else:
                coll = None
            self.eliminateEmpties(root, context, False, coll)


    def eliminateEmpties(self, empty, context, sub, coll):
        deletes = []
        elim = self.doEliminate(empty)
        if elim:
            if coll:
                subcoll = bpy.data.collections.new(empty.name)
                coll.children.link(subcoll)
                sub = True
                coll = subcoll
        elif sub and coll:
            if empty.name not in coll.objects:
                unlinkAll(empty, False)
                coll.objects.link(empty)
        for child in empty.children:
            self.eliminateEmpties(child, context, sub, coll)
        par = empty.parent
        if elim and empty.type == 'EMPTY':
            if par is None or not empty.children:
                deletes.append(empty)
            elif empty.parent_type == 'OBJECT':
                deletes.append(empty)
                for child in empty.children:
                    wmat = child.matrix_world.copy()
                    child.parent = par
                    child.parent_type = 'OBJECT'
                    setWorldMatrix(child, wmat)
            elif empty.parent_type == 'BONE':
                deletes.append(empty)
                for child in empty.children:
                    wmat = child.matrix_world.copy()
                    child.parent = par
                    child.parent_type = 'BONE'
                    child.parent_bone = empty.parent_bone
                    setWorldMatrix(child, wmat)
            elif empty.parent_type.startswith('VERTEX'):
                if activateObject(context, empty.children[0]):
                    deletes.append(empty)
                    for child in empty.children:
                        child.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    par.select_set(True)
                    context.view_layer.objects.active = par
                    if len(set(empty.parent_vertices)) == 3:
                        parverts = empty.parent_vertices
                    else:
                        parverts = [empty.parent_vertices[0]]
                    setMode('EDIT')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bm = bmesh.from_edit_mesh(par.data)
                    bm.verts.ensure_lookup_table()
                    for vn in parverts:
                        bm.verts[vn].select = True
                    bmesh.update_edit_mesh(par.data)
                    bm.free()
                    bpy.ops.object.vertex_parent_set()
                    setMode('OBJECT')
            else:
                raise DazError("Unknown parent type: %s %s" % (child.name, empty.parent_type))
        for empty in set(deletes):
            deleteObjects(context, [empty])


    def doEliminate(self, ob):
        if (ob.type != 'EMPTY' or
            ob.instance_type != 'NONE'):
            return False
        if getHideViewport(ob):
            if self.useHidden:
                ob.hide_set(False)
                ob.hide_viewport = ob.hide_render = False
                return True
            else:
                return False
        return True

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_EliminateEmpties)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_EliminateEmpties)

