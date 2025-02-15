# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..matsel import findUvlayers

#-------------------------------------------------------------
#   Make Material set
#-------------------------------------------------------------

class DAZ_OT_MakePalette(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_palette"
    bl_label = "Make Palette"
    bl_description = "Create a palette for use with the asset browser"
    bl_options = {'UNDO'}

    useMarkAsAsset : BoolProperty(
        name = "Mark As Asset",
        description = "Mark the palette for the asset browser and make all materials unique",
        default = False)

    paletteShape : EnumProperty(
        items = [('PLANE', "Plane", "Plane"),
                 ('CONE', "Cone", "Cone")],
        name = "Palette Shape",
        description = "Palette shape",
        default = 'PLANE')

    def draw(self, context):
        self.layout.prop(self, "paletteShape")
        self.layout.prop(self, "useMarkAsAsset")

    def run(self, context):
        ob = context.object
        if self.paletteShape == 'PLANE':
            palette = self.makePlane(context, ob)
        elif self.paletteShape == 'CONE':
            palette = self.makeCone(context, ob)

        # Add materials
        me = palette.data
        for mat,f in zip(ob.data.materials, me.polygons):
            me.materials.append(mat)
            f.material_index = f.index

        # Add UVs
        uvlayers = {}
        for mat in ob.data.materials:
            findUvlayers(mat, uvlayers)
        if not uvlayers:
            uvlayers["UVMap"] = True
        if self.paletteShape == 'PLANE':
            self.fixPlaneUvs(palette.data, uvlayers)
        elif self.paletteShape == 'CONE':
            self.fixConeUvs(palette.data, uvlayers)

        activateObject(context, palette)
        if not self.useMarkAsAsset:
            return
        bpy.ops.file.make_paths_absolute()
        bpy.ops.object.make_single_user(object=False, obdata=False, material=True, animation=False, obdata_animation=False)
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=False)
        for mat in palette.data.materials:
            mat.name = stripName(mat.name)
        bpy.ops.asset.mark()


    def makePlane(self, context, ob):
        scn = context.scene
        nmats = len(ob.data.materials)
        n = int(math.floor(math.sqrt(nmats-0.01)))+1
        n1 = n+1
        jmax = nmats//n + 1
        imax = nmats - n*(jmax-1)
        verts = [(i,j,0) for j in range(jmax) for i in range(n1)]
        verts += [(i,jmax,0) for i in range(imax+1)]
        faces = [[(i+j*n1), (i+1+j*n1), (i+1+(j+1)*n1), (i+(j+1)*n1)]
            for j in range(jmax-1) for i in range(n)]
        faces += [[(i+(jmax-1)*n1), (i+1+(jmax-1)*n1), (i+1+jmax*n1), (i+jmax*n1)]
            for i in range(imax)]
        nfaces = len(faces)
        name = "%s Palette" % ob.name
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        plane = bpy.data.objects.new(name, me)
        scn.collection.objects.link(plane)
        return plane


    def fixPlaneUvs(self, me, uvlayers):
        nfaces = len(me.polygons)
        for uvname in uvlayers.keys():
            uvlayer = me.uv_layers.new(name=uvname)
            for fn in range(nfaces):
                uvlayer.data[fn*4].uv = (0,0)
                uvlayer.data[fn*4+1].uv = (1,0)
                uvlayer.data[fn*4+2].uv = (1,1)
                uvlayer.data[fn*4+3].uv = (0,1)


    def makeCone(self, context, ob):
        nmat = len(ob.data.materials)
        bpy.ops.mesh.primitive_cone_add(vertices=nmat, radius1=0.5, depth=0.1, end_fill_type='NOTHING')
        cone = context.object
        cone.name = "%s Palette" % ob.name
        return cone


    def fixConeUvs(self, me, uvlayers):
        uvlayer = me.uv_layers[0]
        me.uv_layers.remove(uvlayer)
        nfaces = len(me.polygons)
        for uvname in uvlayers.keys():
            uvlayer = me.uv_layers.new(name=uvname)
            for fn in range(nfaces):
                uvlayer.data[fn*3].uv = (0,0)
                uvlayer.data[fn*3+1].uv = (1,0)
                uvlayer.data[fn*3+2].uv = (0.5,1)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakePalette,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
