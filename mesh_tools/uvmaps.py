# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..fileutils import SingleFile, DufFile
from ..merge_uvs import UVLayerMergerOptions, UVLayerMerger
from ..geometry import *

#-------------------------------------------------------------
#   Find seams
#-------------------------------------------------------------

class DAZ_OT_FindSeams(DazOperator, IsMesh):
    bl_idname = "daz.find_seams"
    bl_label = "Find Seams"
    bl_description = "Create seams based on existing UVs"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..proxy import findSeams
        findSeams(context.object)

#-------------------------------------------------------------
#   Load UVs
#-------------------------------------------------------------

class DAZ_OT_LoadUV(DazOperator, DufFile, SingleFile, IsMesh):
    bl_idname = "daz.load_uv"
    bl_label = "Load UV Set"
    bl_description = "Load a UV set to the active mesh"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        from ..fileutils import getFoldersFromObject
        folders = getFoldersFromObject(context.object, ["UV Sets/"])
        if folders:
            self.properties.filepath = folders[0]
        return SingleFile.invoke(self, context, event)


    def run(self, context):
        from ..files import parseAssetFile
        from ..load_json import JL
        from ..geometry import makeNewUvLayer

        ob = context.object
        me = ob.data
        LS.forUV(ob)
        struct = JL.load(self.filepath)
        asset = parseAssetFile(struct)
        if asset is None or len(asset.uvsets) == 0:
            raise DazError ("Not an UV asset:\n  '%s'" % self.filepath)

        for uvset in asset.uvsets:
            polyverts = uvset.getPolyVerts(me)
            uvset.checkPolyverts(me, polyverts, True)
            uvlayer = makeNewUvLayer(me, uvset.getLabel(), False)
            vnmax = len(uvset.uvs)
            m = 0
            for fn,f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvlayer.data[m].uv = uv
                    m += 1

#-------------------------------------------------------------
#   Collaps UDims
#-------------------------------------------------------------

def addUdimsToUVs(ob, restore, udim, vdim):
    mat = ob.data.materials[0]
    for uvlayer in ob.data.uv_layers:
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            mat = ob.data.materials[f.material_index]
            if restore:
                ushift = dazRna(mat).DazUDim
                vshift = dazRna(mat).DazVDim
            else:
                ushift = udim - dazRna(mat).DazUDim
                vshift = vdim - dazRna(mat).DazVDim
            for n in range(len(f.vertices)):
                uvlayer.data[m].uv[0] += ushift
                uvlayer.data[m].uv[1] += vshift
                m += 1


class DAZ_OT_CollapseUDims(DazOperator):
    bl_idname = "daz.collapse_udims"
    bl_label = "Collapse UDIMs"
    bl_description = "Restrict UV coordinates to the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and not dazRna(ob).DazUDimsCollapsed)

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.collapseUDims(ob)

    def collapseUDims(self, ob):
        from ..material import addUdimTree
        if dazRna(ob).DazUDimsCollapsed:
            return
        dazRna(ob).DazUDimsCollapsed = True
        addUdimsToUVs(ob, False, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if dazRna(mat).DazUDimsCollapsed:
                continue
            dazRna(mat).DazUDimsCollapsed = True
            addUdimTree(mat.node_tree, -dazRna(mat).DazUDim, -dazRna(mat).DazVDim)


class DAZ_OT_RestoreUDims(DazOperator):
    bl_idname = "daz.restore_udims"
    bl_label = "Restore UDIMs"
    bl_description = "Restore original UV coordinates outside the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and dazRna(ob).DazUDimsCollapsed)

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.restoreUDims(ob)

    def restoreUDims(self, ob):
        from ..material import addUdimTree
        if not dazRna(ob).DazUDimsCollapsed:
            return
        dazRna(ob).DazUDimsCollapsed = False
        addUdimsToUVs(ob, True, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if not dazRna(mat).DazUDimsCollapsed:
                continue
            dazRna(mat).DazUDimsCollapsed = False
            addUdimTree(mat.node_tree, dazRna(mat).DazUDim, dazRna(mat).DazVDim)

#----------------------------------------------------------
#   Copy UV maps
#----------------------------------------------------------

def getUvMaps(scn, context):
        me = context.object.data
        return [(uvset.name, uvset.name, uvset.name) for uvset in me.uv_layers]

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
                copyUvLayers(context, src, trg, [self.uvset])

#-------------------------------------------------------------
#   Merge UV sets
#-------------------------------------------------------------

def getUvLayers(scn, context):
    ob = context.object
    enums = []
    for n,uv in enumerate(ob.data.uv_layers):
        ename = "%s (%d)" % (uv.name, n)
        enums.append((str(n), ename, ename))
    return enums

#-------------------------------------------------------------
#   Merge UV layers
#-------------------------------------------------------------

class DAZ_OT_MergeUvLayers(DazPropsOperator, IsMesh):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = ("Merge an UV layer to the active render layer.\n" +
                      "Merging the active render layer to itself replaces\n" +
                      "any UV map nodes with texture coordinate nodes")
    bl_options = {'UNDO'}

    layer : EnumProperty(
        items = getUvLayers,
        name = "Layer To Merge",
        description = "UV layer that is merged with the active render layer")

    allowOverlap : BoolProperty(
        name = "Allow Overlap",
        description = "Allow merging overlapping UV layers",
        default = False)

    def draw(self, context):
        self.layout.label(text="Active Layer: %s" % self.keepName)
        self.layout.prop(self, "layer")
        self.layout.prop(self, "allowOverlap")


    def invoke(self, context, event):
        ob = context.object
        self.keepIdx = -1
        self.keepName = "None"
        for idx,uvlayer in enumerate(ob.data.uv_layers):
            if uvlayer.active_render:
                self.keepIdx = idx
                self.keepName = uvlayer.name
                break
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        from ..merge_uvs import mergeUvLayers
        ob = context.object
        if self.keepIdx < 0:
            raise DazError("No active UV layer found")
        mergeIdx = int(self.layer)
        mergeUvLayers(ob.data, self.keepIdx, mergeIdx, self.allowOverlap)
        deselectAllVerts(ob)

#-------------------------------------------------------------
#   Merge Meshes
#-------------------------------------------------------------

class DAZ_OT_MergeMeshes(DazPropsOperator, UVLayerMergerOptions, UVLayerMerger, IsMesh):
    bl_idname = "daz.merge_meshes"
    bl_label = "Merge Meshes"
    bl_description = ("Merge selected meshes to active mesh")
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawUVLayer(self.layout)


    def run(self, context):
        hum = context.object
        self.initUvNames()
        for ob in getSelectedMeshes(context):
            if ob != hum:
                self.storeUvName(ob)
        for mod in hum.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        nlayers = len(hum.data.uv_layers)
        bpy.ops.object.join()
        self.mergeUvs(hum)
        deselectAllVerts(hum)
        for mod in hum.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        print("Meshes merged")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_FindSeams,
    DAZ_OT_LoadUV,
    DAZ_OT_CollapseUDims,
    DAZ_OT_RestoreUDims,
    DAZ_OT_CopyUvs,
    DAZ_OT_MergeUvLayers,
    DAZ_OT_MergeMeshes,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
