# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *

#----------------------------------------------------------
#   Copy Attributes
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
            attrs.append(("DazGraft", 'INT', 'POINT'))
        if self.useMaterial:
            attrs.append(("DazMaterialGroup", 'INT', 'FACE'))
        if self.usePolygon:
            attrs.append(("DazPolygonGroup", 'INT', 'FACE'))
        for ob in getSelectedMeshes(context):
            fing = getFingerPrint(ob)
            if ob != src and fing == srcFing:
                print("Copy attributes %s => %s" % (src.name, ob.name))
                dazRna(ob.data).DazFingerPrint = dazRna(src.data).DazFingerPrint
                for aname, atype, domain in attrs:
                    self.copyAttributes(src, ob, aname, atype, domain)

    def copyAttributes(self, src, trg, aname, atype, domain):
        srcattr = src.data.attributes.get(aname)
        if srcattr is None:
            raise DazError("%s has no %s attribute" % (src.name, aname))
        if aname in ["DazVertex", "DazGraft"]:
            ndata = len(src.data.vertices)
        else:
            ndata = len(src.data.polygons)
            srcpgs = getattr(dazRna(src.data), aname)
            trgpgs = getattr(dazRna(trg.data), aname)
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

# ---------------------------------------------------------------------
#   Getters
# ---------------------------------------------------------------------

def getMaterialGroups(scn, context):
    ob = context.object
    return [(gname, gname, gname) for gname in dazRna(ob.data).DazMaterialGroup.keys()]


def getPolygonGroups(scn, context):
    ob = context.object
    return [(gname, gname, gname) for gname in dazRna(ob.data).DazPolygonGroup.keys()]

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
        setMode('EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        ob = context.object
        pgs = getattr(dazRna(ob.data), self.attr)
        pg = pgs.get(self.group)
        if pg is None:
            raise DazError("No face group data")
        print("Face group %d %s" % (pg.a, pg.name))
        attr = ob.data.attributes.get(self.attr)
        if attr is None:
            raise DazError("Object %s missing attribute %s" % (ob.name, self.attr))
        for f in ob.data.polygons:
            f.select = (attr.data[f.index].value == pg.a)


class DAZ_OT_DisplayMaterialGroup(DisplayFaceGroup, IsMesh):
    bl_idname = "daz.display_material_group"
    bl_label = "Display Material Group"

    attr = "DazMaterialGroup"

    group : EnumProperty(
        items = getMaterialGroups,
        name = "Group")


class DAZ_OT_DisplayPolygonGroup(DisplayFaceGroup, IsMesh):
    bl_idname = "daz.display_polygon_group"
    bl_label = "Display Polygon Group"

    attr = "DazPolygonGroup"

    group : EnumProperty(
        items = getPolygonGroups,
        name = "Group")

# ---------------------------------------------------------------------
#   Mask face group
# ---------------------------------------------------------------------

class MaskFaceGroup(DazPropsOperator):
    def draw(self, context):
        self.layout.prop(self, "group")

    def run(self, context):
        from ..geonodes import addMaskFaceModifier
        ob = context.object
        pgs = getattr(dazRna(ob.data), self.attr)
        pg = pgs.get(self.group)
        if pg is None:
            raise DazError("No face group data")
        print("Face group %d %s" % (pg.a, pg.name))
        addMaskFaceModifier(ob, self.attr, pg.name)


class DAZ_OT_MaskMaterialGroup(MaskFaceGroup, IsMesh):
    bl_idname = "daz.mask_material_group"
    bl_label = "Mask Material Group"

    attr = "DazMaterialGroup"

    group : EnumProperty(
        items = getMaterialGroups,
        name = "Group")


class DAZ_OT_MaskPolygonGroup(MaskFaceGroup, IsMesh):
    bl_idname = "daz.mask_polygon_group"
    bl_label = "Mask Polygon Group"

    attr = "DazPolygonGroup"

    group : EnumProperty(
        items = getPolygonGroups,
        name = "Group")

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_CopyAttributes,
    DAZ_OT_DisplayMaterialGroup,
    DAZ_OT_DisplayPolygonGroup,
    DAZ_OT_MaskMaterialGroup,
    DAZ_OT_MaskPolygonGroup,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
