# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..fileutils import DF
from ..dforce import Collision

#-------------------------------------------------------------
#   Make deflection
#-------------------------------------------------------------

class DAZ_OT_MakeDeflection(DazPropsOperator, Collision, IsMesh):
    bl_idname = "daz.make_deflection"
    bl_label = "Make Deflection"
    bl_description = "Make a low-poly deflection mesh for the active mesh"
    bl_options = {'UNDO'}

    offset : FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 5.0)

    useQuads : BoolProperty(
        name = "Quads",
        description = "Convert the deflector into a majority-quad mesh",
        default = True)

    useSubsurf : BoolProperty(
        name = "Subsurf",
        description = "Smooth the deflection mesh with a subsurf modifier",
        default = True)

    useShrinkwrap : BoolProperty(
        name = "Shrinkwrap",
        description = "Shrinkwrap the deflection mesh to the original mesh",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "offset")
        self.layout.prop(self, "useQuads")
        self.layout.prop(self, "useSubsurf")
        self.layout.prop(self, "useShrinkwrap")

    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False

    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def run(self, context):
        ob = context.object
        fac = self.offset*0.1*ob.DazScale
        char = ob.DazMesh.lower()
        struct = DF.loadEntry(char, "lowpoly")
        vnums = struct["vertices"]
        verts = ob.data.vertices
        coords = [(verts[vn].co + fac*verts[vn].normal) for vn in vnums]
        #faces = struct["faces"]
        faces = ([(f[0],f[1],f[2]) for f in struct["faces"]] +
                 [(f[0],f[2],f[3]) for f in struct["faces"] if len(f) > 3])
        me = bpy.data.meshes.new(ob.data.name+"Deflect")
        me.from_pydata(coords, [], faces)
        nob = bpy.data.objects.new(ob.name+"Deflect", me)
        ncoll = bpy.data.collections.new(name=ob.name+"Deflect")
        ncoll.objects.link(nob)
        for coll in bpy.data.collections:
            if ob in coll.objects.values():
                coll.children.link(ncoll)
        nob.hide_render = True
        nob.show_wire = True
        nob.show_all_edges = True
        nob.parent = ob.parent

        vgrps = dict([(vgrp.index, vgrp) for vgrp in ob.vertex_groups])
        ngrps = {}
        for vgrp in ob.vertex_groups:
            ngrp = nob.vertex_groups.new(name=vgrp.name)
            ngrps[ngrp.index] = ngrp
        for nv in nob.data.vertices:
            v = ob.data.vertices[vnums[nv.index]]
            for g in v.groups:
                ngrp = ngrps[g.group]
                ngrp.add([nv.index], g.weight, 'REPLACE')

        mod = getModifier(ob, 'ARMATURE')
        if mod:
            nmod = nob.modifiers.new("Armature %s" % mod.name, 'ARMATURE')
            nmod.object = mod.object
            nmod.use_deform_preserve_volume = mod.use_deform_preserve_volume

        setActiveObject(context, nob)
        if self.useQuads:
            setMode('EDIT')
            bpy.ops.mesh.tris_convert_to_quads()
            setMode('OBJECT')
        if self.useSubsurf:
            mod = nob.modifiers.new("Subsurf", 'SUBSURF')
            mod.levels = 1
            bpy.ops.object.modifier_apply(modifier="Subsurf")
        if self.useShrinkwrap:
            mod = nob.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
            mod.wrap_method = 'NEAREST_SURFACEPOINT'
            mod.wrap_mode = 'ON_SURFACE'
            mod.target = ob
            bpy.ops.object.modifier_apply(modifier="Shrinkwrap")

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeDeflection,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)