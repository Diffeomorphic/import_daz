#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
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
from .error import *
from .utils import *

# ---------------------------------------------------------------------
#   Display face group
# ---------------------------------------------------------------------

class DisplayFaceGroup(DazPropsOperator):
    def draw(self, context):
        self.layout.prop(self, "group")

    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        setMode('EDIT')

    def run(self, context):
        ob = context.object
        pgs = getattr(ob.data, self.attr)
        gn = -1
        for gn,gname in enumerate(pgs.keys()):
            if gname == self.group:
                break
        if gn == -1:
            raise DazError("Group %s not found" % gname)
        print("Face group %d %s" % (gn, gname))
        setMode('EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        attr = ob.data.attributes[self.attr]
        for f in ob.data.polygons:
            f.select = (attr.data[f.index].value == gn)


def getMaterialGroups(scn, context):
    ob = context.object
    return [(gname, gname, gname) for gname in ob.data.DazMaterialGroup.keys()]


class DAZ_OT_DisplayMaterialGroup(DisplayFaceGroup, IsMesh):
    bl_idname = "daz.display_material_group"
    bl_label = "Display Material Group"

    attr = "DazMaterialGroup"

    group : EnumProperty(
        items = getMaterialGroups,
        name = "Group")


def getPolygonGroups(scn, context):
    ob = context.object
    return [(gname, gname, gname) for gname in ob.data.DazPolygonGroup.keys()]

class DAZ_OT_DisplayPolygonGroup(DisplayFaceGroup, IsMesh):
    bl_idname = "daz.display_polygon_group"
    bl_label = "Display Polygon Group"

    attr = "DazPolygonGroup"

    group : EnumProperty(
        items = getPolygonGroups,
        name = "Group")



# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_DisplayMaterialGroup,
    DAZ_OT_DisplayPolygonGroup,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Mesh.DazPolygonGroup = CollectionProperty(type = bpy.types.PropertyGroup)
    bpy.types.Mesh.DazMaterialGroup = CollectionProperty(type = bpy.types.PropertyGroup)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
