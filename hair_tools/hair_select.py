# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..proxy import Proxifier
from ..selector import Selector

#-------------------------------------------------------------
#   Select random strands
#-------------------------------------------------------------

class DAZ_OT_SelectRandomStrands(DazPropsOperator, IsMesh):
    bl_idname = "daz.select_random_strands"
    bl_label = "Select Random Strands"
    bl_description = ("Select random subset of strands selected in UV space.\n" +
                      "Useful for reducing the number of strands before making particle hair")
    bl_options = {'UNDO'}

    fraction : FloatProperty(
        name = "Fraction",
        description = "Fraction of strands to select",
        min = 0.0, max = 1.0,
        default = 0.5)

    seed : IntProperty(
        name = "Seed",
        description = "Seed for the random number generator",
        default = 0)

    def draw(self, context):
        self.layout.prop(self, "fraction")
        self.layout.prop(self, "seed")


    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.selectRandom(context, ob)


    def selectRandom(self, context, ob):
        import random
        if not (ob.data.polygons or ob.data.edges):
            return
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, context)
        random.seed(self.seed)
        for comp in comps.values():
            if random.random() < self.fraction:
                prox.selectComp(comp, ob)


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#-------------------------------------------------------------
#   Select strands by width
#-------------------------------------------------------------

class DAZ_OT_SelectStrandsByWidth(DazPropsOperator, IsMesh):
    bl_idname = "daz.select_strands_by_width"
    bl_label = "Select Strands By Width"
    bl_description = "Select strands not wider than threshold"
    bl_options = {'UNDO'}

    width : FloatProperty(
        name = "Width",
        description = "Max allowed width (mm)",
        min = 0.1, max = 10,
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "width")


    def run(self, context):
        ob = context.object
        if not ob.data.polygons:
            raise DazError("Mesh has no polygons")
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, context)
        maxwidth = 0.1 * self.width * GS.scale
        verts = ob.data.vertices
        faces = ob.data.polygons
        for comp in comps.values():
            if self.withinWidth(verts, faces, comp, maxwidth):
                prox.selectComp(comp, ob)


    def withinWidth(self, verts, faces, comp, maxwidth):
        for fn in comp:
            sizes = [(verts[vn1].co - verts[vn2].co).length
                      for vn1,vn2 in faces[fn].edge_keys]
            sizes.sort()
            if sizes[-3] > maxwidth:
                return False
        return True


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#-------------------------------------------------------------
#   Select largest strands
#-------------------------------------------------------------

class DAZ_OT_SelectStrandsBySize(DazOperator, IsMesh, Selector):
    bl_idname = "daz.select_strands_by_size"
    bl_label = "Select Strands By Size"
    bl_description = ("Select strands based on the number of faces.\n" +
                      "Useful for reducing the number of strands before making particle hair")
    bl_options = {'UNDO'}

    def draw(self, context):
        Selector.draw(self, context)

    def run(self, context):
        ob = context.object
        if not (ob.data.polygons or ob.data.edges):
            return
        prox = Proxifier(ob)
        for item in self.getSelectedItems():
            for comp in self.groups[int(item.name)]:
                prox.selectComp(comp, ob)


    def getKeys(self, rig, ob):
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, bpy.context)
        self.groups = dict([(len(comp),[]) for comp in comps.values()])
        for comp in comps.values():
            self.groups[len(comp)].append(comp)
        sizes = list(self.groups.keys())
        sizes.sort()
        keys = [(str(size), str(size), "All") for size in sizes]
        return keys


    def invoke(self, context, event):
        return Selector.invoke(self, context, event)


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SelectRandomStrands,
    DAZ_OT_SelectStrandsByWidth,
    DAZ_OT_SelectStrandsBySize,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


