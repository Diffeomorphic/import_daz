#  Shell Editor - Tools for manipulating shells and layered images from DAZ Importer
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
from ..geometry import *

#----------------------------------------------------------
#   Copy UV maps
#----------------------------------------------------------

def getUvMaps(scn, context):
        me = context.object.data
        return [(uvset.name, uvset.name, uvset.name) for uvset in me.uv_layers
                if uvset != me.uv_layers.active]

class DAZ_OT_CopyUvs(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_uvs"
    bl_label = "Copy UVs"
    bl_description = "Copy UV map from active mesh to selected meshes"
    bl_options = {'UNDO'}

    uvset : EnumProperty(
        items = getUvMaps,
        name = "UV Set",
        description = "UV set to copy")

    def draw(self, context):
        self.layout.prop(self, "uvset")

    def run(self, context):
        from ..finger import getFingerPrint
        src = context.object
        sfinger = getFingerPrint(src)
        for trg in getSelectedMeshes(context):
            if trg != src:
                if getFingerPrint(trg) != sfinger:
                    raise DazError("Can not copy UVs between meshes with different topology")
                copyUvLayers(src, trg, [self.uvset])

#----------------------------------------------------------
#   Copy verts
#----------------------------------------------------------

class DAZ_OT_CopyAttributes(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_attributes"
    bl_label = "Copy Attributes"
    bl_description = "Copy attributes from active to selected"
    bl_options = {'UNDO'}

    useVertex : BoolProperty(
        name = "Vertex",
        default = True)

    useMaterial : BoolProperty(
        name = "Material Groups",
        default = False)

    usePolygon : BoolProperty(
        name = "Polygon Groups",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useVertex")
        self.layout.prop(self, "useMaterial")
        self.layout.prop(self, "usePolygon")

    def run(self, context):
        from ..finger import getFingerPrint
        src = context.object
        srcFing = getFingerPrint(src)
        attrs = []
        if self.useVertex:
            attrs.append(("DazVertex", 'INT', 'POINT'))
        if self.useMaterial:
            attrs.append(("DazMaterialGroup", 'INT', 'FACE'))
        if self.usePolygon:
            attrs.append(("DazPolygonGroup", 'INT', 'FACE'))
        for ob in getSelectedMeshes(context):
            fing = getFingerPrint(ob)
            if ob != src and fing == srcFing:
                print("Copy attributes %s => %s" % (src.name, ob.name))
                ob.data.DazFingerPrint = src.data.DazFingerPrint
                for aname, atype, domain in attrs:
                    self.copyAttributes(src, ob, aname, atype, domain)

    def copyAttributes(self, src, trg, aname, atype, domain):
        srcattr = src.data.attributes.get(aname)
        if srcattr is None:
            raise DazError("%s has no %s attribute" % (src.name, aname))
        if aname == "DazVertex":
            ndata = len(src.data.vertices)
        else:
            ndata = len(src.data.polygons)
            srcpgs = getattr(src.data, aname)
            trgpgs = getattr(trg.data, aname)
            trgpgs.clear()
            for key in srcpgs.keys():
                pg = trgpgs.add()
                pg.name = key
        attr = trg.data.attributes.get(aname)
        if attr:
            trg.data.attributes.remove(attr)
        trgattr = trg.data.attributes.new(aname, atype, domain)
        for idx in range(ndata):
            trgattr.data[idx].value = srcattr.data[idx].value

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyUvs,
    DAZ_OT_CopyAttributes,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
