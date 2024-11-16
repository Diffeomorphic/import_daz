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

import os
import json
import bpy
import bmesh
from mathutils import Matrix

from .utils import *
from .error import *
from .driver import DriverUser
from .fileutils import DF
from .geometry import getActiveUvLayer
from .figure import LockEnabler
from .udim import TileFixer

#-------------------------------------------------------------
#   Merge UV Layers
#-------------------------------------------------------------

class UVLayerMergerOptions:
    useMergeUvs : BoolProperty(
        name = "Merge UV Layers",
        description = "Merge active render UV layers of all meshes",
        default = True)

    allowOverlap : BoolProperty(
        name = "Allow Overlap",
        description = "Also merge overlapping UV layers.\nCan destroy UV assignment",
        default = False)


class UVLayerMerger:
    def drawUVLayer(self, layout):
        layout.prop(self, "useMergeUvs")
        if self.useMergeUvs:
            layout.prop(self, "allowOverlap")


    def getBackgroundUvLayer(self, ob):
        def getUvMap(socket, default):
            if socket:
                for link in socket.links:
                    node = link.from_node
                    if node.type == 'UVMAP':
                        return node.uv_map
                    elif node.type == 'ATTRIBUTE':
                        return node.attribute_name
                    elif node.type == 'TEX_COORD':
                        return default
                    elif "Vector" in node.inputs.keys():
                        return getUvMap(node.inputs.get("Vector"), default)
            return default

        from .matsel import isShellNode
        from .cycles import isTexImage
        active = getActiveUvLayer(ob)
        uvmaps = {}
        shellmaps = {}
        for mat in ob.data.materials:
            if not (mat and mat.node_tree):
                continue
            for node in mat.node_tree.nodes:
                if isTexImage(node):
                    uvname = getUvMap(node.inputs.get("Vector"), active.name)
                    uvmaps[uvname] = True
                elif isShellNode(node):
                    uvname = getUvMap(node.inputs.get("UV"), "**")
                    mat["DazShellMap"] = uvname
                    shellmaps[uvname] = True

        for uvname in uvmaps.keys():
            if uvname in shellmaps.keys():
                continue
            elif uvname in ob.data.uv_layers.keys():
                return uvname
        return None


    def initUvNames(self):
        self.auvnames = {}


    def storeUvName(self, ob):
        uvname = self.getBackgroundUvLayer(ob)
        if uvname is not None:
            self.auvnames[uvname] = True


    def mergeUvs(self, ob):
        active = getActiveUvLayer(ob)

        if not self.useMergeUvs:
            actname = ""
            msg = ""
            if active:
                actname = active.name
                for uvname in self.auvnames:
                    if uvname != actname:
                        msg += "\n  %s" % uvname
                if msg:
                    self.addWarning("UV layers should be merged to %s:%s" % (actname, msg))
            return

        idxs = []
        keepIdx = 0
        for idx,uvlayer in enumerate(ob.data.uv_layers):
            if uvlayer == active:
                keepIdx = idx
            elif uvlayer.name in self.auvnames:
                idxs.append(idx)
        if not idxs:
            print("No UV layers to merge")
            return
        idxs.reverse()
        for idx in idxs:
            mergeUvLayers(ob.data, keepIdx, idx, self.allowOverlap)
        uvname0 = ob.data.uv_layers[keepIdx].name
        print("UV layers %s merged to %s" % (list(self.auvnames), uvname0))

#-------------------------------------------------------------
#   Merge geografts
#-------------------------------------------------------------

class MergeGeograftOptions(UVLayerMergerOptions):

    keepOriginal : BoolProperty(
        name = "Keep Original Meshes",
        description = "Keep the original mesh and geografts in separate collections",
        default = False)

    useFixTiles : BoolProperty(
        name = "Fix UV Tiles",
        description = "Move geograft UVs to tile based on texture names",
        default = True)

    useSubDDisplacement : BoolProperty(
        name = "SubD Displacement",
        description = "Add SubD Displacement to the merge mesh if some geograft has it.\nMay slow down rendering",
        default = True)

    useGeoNodes: BoolProperty(
        name = "Geometry Nodes (Experimental)",
        description = "Merge geografts using geometry nodes",
        default = False)


class DAZ_OT_MergeGeografts(DazPropsOperator, MergeGeograftOptions, UVLayerMerger, TileFixer, DriverUser, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    def draw(self, context):
        if bpy.app.version >= (3,4,0):
            self.layout.prop(self, "useGeoNodes")
        if not self.useGeoNodes:
            self.layout.prop(self, "keepOriginal")
        self.layout.prop(self, "useSubDDisplacement")
        box = self.layout.box()
        box.label(text="UDIM Materials")
        box.prop(self, "useFixTiles")
        box.prop(self, "useLastUdimTile")
        self.drawUVLayer(box)


    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        safeTransformApply()
        from .finger import isGenesis
        hum = context.object
        selected_meshes = getSelectedMeshes(context)
        nhumverts = len(hum.data.vertices)
        humans = {nhumverts : hum}
        prio = {nhumverts : False}
        for ob in selected_meshes:
            ob.active_shape_key_index = 0
            nverts = len(ob.data.vertices)
            if nverts not in humans.keys() or isGenesis(ob):
                humans[nverts] = ob
                prio[nverts] = (not (not ob.data.DazGraftGroup))

        grafts = dict([(vert_count, []) for vert_count in humans.keys()])
        ngrafts = 0
        misses = []
        # Store geograft objects in grafts dictionary--lookup by number of vertices
        for ob in selected_meshes:
            if ob.data.DazGraftGroup:
                nhumverts = ob.data.DazVertexCount
                if nhumverts in grafts.keys():
                    grafts[nhumverts].append(ob)
                    ngrafts += 1
                else:
                    print("No matching mesh found for geograft %s" % ob.name)
                    misses.append(ob)
        if ngrafts == 0:
            if misses:
                msg = "No matching mesh found for these geografts:\n"
                for ob in misses:
                    msg += "    %s\n" % ob.name
                msg += "Has some mesh been edited?"
            else:
                msg = "No geograft selected"
            raise DazError(msg)

        for nhumverts, hum in humans.items():
            if prio[nhumverts]:
                self.mergeGeografts(context, nhumverts, hum, grafts[nhumverts])
        for nhumverts, hum in humans.items():
            if not prio[nhumverts]:
                self.mergeGeografts(context, nhumverts, hum, grafts[nhumverts])


    def duplicateMeshes(self, context, hum, grafts):
        from .finger import getFingerPrint
        dup = None
        if activateObject(context, hum):
            finger = getFingerPrint(hum)
            bpy.ops.object.duplicate()
            for ob in getSelectedMeshes(context):
                if getFingerPrint(ob) == finger and ob != hum:
                    dup = ob
        if dup is None:
            return
        cname = baseName(hum.name)
        basename = cname.rstrip("Mesh")
        hum.name = "%s Merged" % basename
        coll = getCollection(context, hum)
        dup.name = cname

        coll1 = bpy.data.collections.new("%sOriginal" % basename)
        coll.children.link(coll1)
        unlinkAll(dup, False)
        coll1.objects.link(dup)
        lcoll1 = getLayerCollection(context, coll1)
        lcoll1.exclude = True

        coll2 = bpy.data.collections.new("%sMerged" % basename)
        coll.children.link(coll2)
        unlinkAll(hum, False)
        coll2.objects.link(hum)

        activateObject(context, hum)


    def mergeGeografts(self, context, nverts, hum, grafts):
        if not grafts:
            return
        try:
            hum.data
        except ReferenceError:
            print("No ref")
            return

        if self.keepOriginal and not self.useGeoNodes:
            self.duplicateMeshes(context, hum, grafts)

        self.initUvNames()
        subDLevels = 0
        self.setActiveUvLayer(hum)
        influs = dict([(prop, value) for prop, value in hum.items() if prop[0:6] == "INFLU "])
        hum.active_shape_key_index = 0
        hum.show_only_shape_key = True
        for graft in grafts:
            graft.active_shape_key_index = 0
            graft.show_only_shape_key = True
            self.renameUvLayers(graft)
            self.storeUvName(graft)
            if self.useFixTiles:
                self.udimsFromGraft(graft, hum)
            self.copyBodyPart(graft, hum)
            self.fixFaceGroups(graft, hum)
            for prop, value in graft.items():
                if prop[0:6] == "INFLU " and prop not in influs.keys():
                    influs[prop] = value
            for mod in list(graft.modifiers):
                if mod.type == 'SURFACE_DEFORM':
                    graft.modifiers.remove(mod)
                elif self.useSubDDisplacement and mod.type == 'SUBSURF':
                    if mod.render_levels > subDLevels:
                        subDLevels = mod.render_levels

        # Select graft group for each anatomy
        cuvname = getActiveUvLayer(hum).name
        drivers = {}
        cvgrps = dict([(vgrp.index, vgrp.name) for vgrp in hum.vertex_groups])
        for graft in grafts:
            activateObject(context, graft)
            self.moveGraftVerts(graft, hum, cvgrps)
            self.getShapekeyDrivers(graft, drivers)
            self.replaceTexco(graft, cuvname, self.useGeoNodes)

        # For the body, setup mask groups
        activateObject(context, hum)
        for mod in hum.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        nverts = len(hum.data.vertices)
        self.vfaces = dict([(vn,[]) for vn in range(nverts)])
        for f in hum.data.polygons:
            for vn in f.vertices:
                self.vfaces[vn].append(f.index)

        nfaces = len(hum.data.polygons)
        self.fmasked = dict([(fn,False) for fn in range(nfaces)])
        for graft in grafts:
            for face in graft.data.DazMaskGroup:
                self.fmasked[face.a] = True

        # If hum is itself a geograft, make sure to keep tbe boundary
        if hum.data.DazGraftGroup:
            body_pair_a_verts = [pair.a for pair in hum.data.DazGraftGroup]
        else:
            body_pair_a_verts = []

        deselectAllVerts(hum)

        # Select body verts to delete
        self.vdeleted = dict([(vn,False) for vn in range(nverts)])
        self.hummasks = {}
        for graft in grafts:
            hummask = self.hummasks[graft.name] = dict([(vn, False) for vn in range(nverts)])
            graft_pair_b_verts = [pair.b for pair in graft.data.DazGraftGroup]
            for face in graft.data.DazMaskGroup:
                fverts = hum.data.polygons[face.a].vertices
                vdelete = []
                for vn in fverts:
                    # Don't delete if it's on the edge to be merged--these will be merged by distance later
                    if vn in body_pair_a_verts:
                        pass
                    elif vn not in graft_pair_b_verts:
                        vdelete.append(vn)
                    # Slate the vertex for deletion, as it's not one to be merged and is one of the body vertices that will be replaced by the graft
                    else:
                        mfaces = [fn for fn in self.vfaces[vn] if self.fmasked[fn]]
                        if len(mfaces) == len(self.vfaces[vn]):
                            vdelete.append(vn)
                for vn in vdelete:
                    hum.data.vertices[vn].select = True
                    self.vdeleted[vn] = True
                    hummask[vn] = True

        # Build association tables between new and old vertex numbers
        assoc = {}
        vn2 = 0
        for vn in range(nverts):
            if not self.vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        # Original vertex locations
        if not self.useGeoNodes:
            self.origlocs = [v.co.copy() for v in hum.data.vertices]

        # If hum is itself a geograft, store locations
        if hum.data.DazGraftGroup:
            verts = hum.data.vertices
            self.locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in hum.data.DazGraftGroup])

        # Delete the masked verts
        self.deleteSelectedVerts()

        # Select nothing
        for graft in grafts:
            deselectAllVerts(graft)
        deselectAllVerts(hum)

        # Select verts on common boundary
        self.humedges = {}
        self.graftedges = {}
        for graft in grafts:
            selectSet(graft, True)
            ngraftverts = len(graft.data.vertices)
            graftedge = self.graftedges[graft.name] = dict([(vn,False) for vn in range(ngraftverts)])
            humedge = self.humedges[graft.name] = dict([(vn,False) for vn in range(nverts)])
            pg = hum.data.DazMergedGeografts.add()
            pg.name = graft.name

            # Add custom attribute which will store the vertex to be paired, and accessible via geometry node
            # If this is the graft...
            attribute_name = "paired_body_vert_%s" % graft.name
            if not hasattr(graft.data, "attributes"):
                attribute = None
            elif not hasattr(graft.data.attributes, attribute_name):
                # print("Creating paired body vert attribute: %s" % attribute_name)
                attribute = graft.data.attributes.new(attribute_name, type="INT", domain="POINT")
            else:
                # print("%s already exists" % attribute_name)
                attribute = graft.data.attributes[attribute_name]

            # Create a dictionary, default all to -1, but values will be populated with the paired body vertex
            # To set in foreach_set method, needs to be the same length as the # of vertices
            paired_vert_list = dict()
            for idx, v in enumerate(graft.data.vertices):
                paired_vert_list[idx] = -1

            for pair in graft.data.DazGraftGroup:
                graft.data.vertices[pair.a].select = True
                if pair.b in assoc.keys():
                    # Set value to be added as attribute
                    paired_vert_list[pair.a] = pair.b
                    graftedge[pair.a] = True
                    hvn = assoc[pair.b]
                    hum.data.vertices[hvn].select = True
                    humedge[pair.b] = True

            # Set the attribute values for all the vertices
            if attribute:
                attribute.data.foreach_set("value", list(paired_vert_list.values()))

        # Also select hum graft group. These will not be removed.
        if hum.data.DazGraftGroup:
            for pair in hum.data.DazGraftGroup:
                hvn = assoc[pair.a]
                hum.data.vertices[hvn].select = True

        # Retarget shells
        self.retargetShellInfluence(hum, grafts, influs)
        if bpy.app.version < (3,1,0):
            self.mergeDestructively(context, hum, grafts, body_pair_a_verts)
        elif self.useGeoNodes:
            self.mergeWithGeoNodes(context, hum, grafts, body_pair_a_verts)
        else:
            self.retargetShellModifiers(hum, grafts)
            self.mergeDestructively(context, hum, grafts, body_pair_a_verts)

        self.copyShapeKeyDrivers(hum, drivers)
        updateDrivers(hum)
        hum.show_only_shape_key = False
        for mod in hum.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
            elif mod.type == 'SUBSURF':
                if subDLevels > mod.render_levels:
                    mod.render_levels = subDLevels
                subDLevels = 0


    def deleteSelectedVerts(self):
        if self.useGeoNodes and bpy.app.version >= (3,1,0):
            return
        setMode('EDIT')
        bpy.ops.mesh.delete(type='VERT')
        setMode('OBJECT')


    def fixFaceGroups(self, graft, hum):
        if BLENDER3 or "DazVertex" not in graft.data.attributes.keys():
            return

        def fixFaceGroup(aname, graft, hum):
            pgs = getattr(hum.data, aname)
            n0 = len(pgs)
            graftpgs = getattr(graft.data, aname)
            for gname in graftpgs.keys():
                pg = pgs.add()
                pg.name = gname
            attr = graft.data.attributes[aname]
            for data in attr.data.values():
                data.value += n0

        fixFaceGroup("DazPolygonGroup", graft, hum)
        fixFaceGroup("DazMaterialGroup", graft, hum)
        attr = graft.data.attributes["DazVertex"]
        for data in attr.data.values():
            data.value = -1


    def mergeDestructively(self, context, hum, grafts, body_pair_a_verts):
        # Join meshes and remove doubles
        names = [graft.name for graft in grafts]
        print("Merge %s to %s" % (names, hum.name))
        threshold = 0.001*hum.DazScale
        bpy.ops.object.join()
        setMode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        setMode('OBJECT')
        selected = dict([(v.index,v.co.copy()) for v in hum.data.vertices if v.select])
        deselectAllVerts(hum)

        # Create graft vertex group
        vgrp = hum.vertex_groups.new(name="Graft")
        for vn in selected.keys():
            vgrp.add([vn], 1.0, 'REPLACE')
        mod = getModifier(hum, 'MULTIRES')
        if mod:
            smod = hum.modifiers.new("Smooth Graft", 'SMOOTH')
            smod.factor = 1.0
            smod.iterations = 10
            smod.vertex_group = vgrp.name

        # Update hum graft group
        if hum.data.DazGraftGroup and selected:
            for pair in hum.data.DazGraftGroup:
                x = self.locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        # Merge UV layers
        from .tree import pruneMaterials
        self.mergeUvs(hum)
        #pruneMaterials(hum)

    #
    # Based on ideas of Midnight Arrow
    # https://bitbucket.org/Diffeomorphic/import_daz/issues/869/non-destructive-geografts
    # Modifications by GeneralProtectionFault
    # https://bitbucket.org/Diffeomorphic/import_daz/issues/2005/geometry-node-merge-geografts-geometry
    #
    def mergeWithGeoNodes(self, context, hum, grafts, cgrafts):
        def addVertexGroup(ob, vgname, struct):
            vgrp = ob.vertex_groups.get(vgname)
            if vgrp is None:
                vgrp = ob.vertex_groups.new(name=vgname)
                verts = [vn for vn,ok in struct.items() if ok]
                for vn in verts:
                    vgrp.add([vn], 1, 'REPLACE')
            return vgrp

        # Add vertex group of entire body in order to remove duplication when merging the grafts w/ geonodes
        # The name needs to include the mesh as well or it will break on nested grafts
        full_body_grp = hum.vertex_groups.new(name=f"FullBody_{hum.name}")
        full_body_grp.add([v.index for v in hum.data.vertices], 1.0, 'REPLACE')

        from .store import ModStore
        stores = []
        delmasks = []
        for mod in list(hum.modifiers):
            if mod.type == 'NODES':
                if mod.node_group.name == "DAZ Geograft":
                    if BLENDER3:
                        graft = mod["Input_1"]
                    else:
                        graft = mod["Socket_1"]
                    if graft:
                        delmasks.append(graft.name)
                    else:
                        hum.modifiers.remove(mod)
                else:
                    words = mod.node_group.name.split(":")
                    if words[0] == "Geograft" and baseName(words[-1]) == "END":
                        hum.modifiers.remove(mod)
            elif mod.type != 'ARMATURE':
                stores.append(ModStore(mod))
                hum.modifiers.remove(mod)

        cuvname = getActiveUvLayer(hum).name
        self.replaceTexco(hum, cuvname, True)

        from .geonodes import GeograftGroup
        from .tree import addNodeGroup

        for graft in grafts:
            maskname = "%s Mask" % graft.name
            edgename = "%s Edge" % graft.name
            hummask = addVertexGroup(hum, maskname, self.hummasks[graft.name])
            humedge = addVertexGroup(hum, edgename, self.humedges[graft.name])
            graftedge = addVertexGroup(graft, edgename, self.graftedges[graft.name])
            for vgrp in graft.vertex_groups:
                if vgrp.name not in list(hum.vertex_groups.keys()):
                    hum.vertex_groups.new(name=vgrp.name)
            for amod in list(graft.modifiers):
                if amod.type in ['SUBSURF']:
                    amod.show_viewport = amod.show_render = False
                    graft.modifiers.remove(amod)

        from .geonodes import GeograftsGroup
        graftgrp = GeograftsGroup()
        groupname = "Geografts:%s" % hum.name
        graftgrp.create(groupname)
        graftgrp.addGrafts(grafts, hum.name)

        # Create the modifier
        mod = hum.modifiers.new(groupname, 'NODES')
        mod.node_group = graftgrp.group

        # Handle all the inputs generated from the geografts - Placed below the inputs that apply to the entire geonode group
        graft_socket_count = 5  # Number of sockets per geograft
        socket_offset = 3 # Number of sockets before the geograft-specific sockets
        if BLENDER3:
            mod["Input_1"] = 0.01*GS.scale
            for i, graft in enumerate(grafts):
                mod["Input_%d" % (graft_socket_count*i+(socket_offset))] = graft
                mod["Input_%d" % (graft_socket_count*i+(socket_offset+1))] = "paired_body_vert_%s" % graft.name
                bpy.ops.object.geometry_nodes_input_attribute_toggle(
                    prop_path="Input_%d" % (graft_socket_count*i+(socket_offset+2)),
                    modifier_name=mod.name)
                mod["Input_%d_attribute_name" % (graft_socket_count*i+(socket_offset+2))] = "%s Mask" % graft.name
                mod["Input_%d" % (graft_socket_count*i+(socket_offset+3))] = True
                mod["Input_%d" % (graft_socket_count*i+(socket_offset+4))] = f"{graft.name} Edge"
                bpy.ops.object.geometry_nodes_input_attribute_toggle(
                    prop_path="Input_%d" % (graft_socket_count*i+(socket_offset+4)),
                    modifier_name=mod.name)
        else:
            mod["Socket_1"] = 0.01*GS.scale
            for i, graft in enumerate(grafts):
                mod["Socket_%d" % (graft_socket_count*i+(socket_offset))] = graft
                mod["Socket_%d" % (graft_socket_count*i+(socket_offset+1))] = "paired_body_vert_%s" % graft.name
                bpy.ops.object.geometry_nodes_input_attribute_toggle(
                    input_name="Socket_%d" % (graft_socket_count*i+(socket_offset+2)),
                    modifier_name=mod.name)
                mod["Socket_%d_attribute_name" % (graft_socket_count*i+(socket_offset+2))] = "%s Mask" % graft.name
                mod["Socket_%d" % (graft_socket_count*i+(socket_offset+3))] = True
                mod["Socket_%d" % (graft_socket_count*i+(socket_offset+4))] = f"{graft.name} Edge"
                bpy.ops.object.geometry_nodes_input_attribute_toggle(
                    input_name="Socket_%d" % (graft_socket_count*i+(socket_offset+4)),
                    modifier_name=mod.name)

        for graft in grafts:
            graft.hide_set(True)
            graft.hide_render = True
            graft.show_only_shape_key = False
            for mod in graft.modifiers:
                if mod.type == 'NODES':
                    mod.show_viewport = mod.show_render = True

        for store in stores:
            store.restore(hum)


    def retargetShellModifiers(self, hum, grafts):
        from .tree import findLinksFrom
        socket1 = ("Input_1" if BLENDER3 else "Socket_1")
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                for mod in ob.modifiers:
                    if mod.type == 'NODES':
                        graft = mod.get(socket1)
                        if graft and graft in grafts:
                            mod[socket1] = hum


    def retargetShellInfluence(self, hum, grafts, influs):
        for prop,value in influs.items():
            if prop not in hum.keys():
                hum[prop] = value
                setOverridable(hum, prop)
                hum.DazVisibilityDrivers = True
        for graft in grafts:
            for mat in graft.data.materials:
                if mat and mat.node_tree.animation_data:
                    for fcu in mat.node_tree.animation_data.drivers:
                        for var in fcu.driver.variables:
                            for trg in var.targets:
                                if trg.id_type == 'OBJECT' and getProp(trg.data_path) in influs.keys():
                                    trg.id = hum



    def replaceTexco(self, ob, cuvname, force):
        uvname = getActiveUvLayer(ob).name
        if (self.useMergeUvs or uvname == cuvname) and not force:
            return
        for mat in ob.data.materials:
            if mat is None:
                continue
            texco = None
            tree = mat.node_tree
            location = (0,0)
            for node in tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
                    location = texco.location
            uvmap = tree.nodes.new(type="ShaderNodeUVMap")
            uvmap.uv_map = uvname
            uvmap.label = uvname
            uvmap.hide = True
            uvmap.location = location
            if texco:
                for link in tree.links:
                    if link.from_node == texco:
                        mat.node_tree.links.new(uvmap.outputs["UV"], link.to_socket)
                mat.node_tree.nodes.remove(texco)
            for node in tree.nodes:
                socket = node.inputs.get("Vector")
                if socket and not socket.links:
                    tree.links.new(uvmap.outputs["UV"], socket)


    def setActiveUvLayer(self, ob):
        def findUvMap(node):
            socket = node.inputs.get("Vector")
            if socket and socket.links:
                return findUvMap(socket.links[0].from_node)
            return None

        from .cycles import isTexImage
        uvmaps = {}
        for mat in ob.data.materials:
            if mat is None:
                continue
            for node in mat.node_tree.nodes:
                if isTexImage(node):
                    uvmap = findUvMap(node)
                    if uvmap is None or uvmap.type == 'TEX_COORD':
                        return
                    elif uvmap.type == 'UVMAP':
                        uvmaps[uvmap.uv_map] = True
        if uvmaps:
            uvlayer = None
            for uvmap in uvmaps.keys():
                if uvlayer is None or uvmap.startswith("Base"):
                    uvlayer = ob.data.uv_layers.get(uvmap)
            if uvlayer:
                uvlayer.active_render = True
                uvlayer.active = True
                print('New active UV layer: "%s"' % uvlayer.name)


    def renameUvLayers(self, graft):
        def replaceUvMaps(tree):
            for node in tree.nodes:
                if node.type in ['NORMAL_MAP', 'UVMAP']:
                    if node.uv_map in renamed.keys():
                        node.uv_map = renamed[node.uv_map]
                elif node.type == 'GROUP':
                    replaceUvMaps(node.node_tree)

        renamed = {}
        for uvlayer in graft.data.uv_layers:
            if uvlayer.name.startswith(("Base", "Default")):
                newname = "%s:%s" % (uvlayer.name, graft.name)
                renamed[uvlayer.name] = newname
                uvlayer.name = newname
        if renamed:
            for mat in graft.data.materials:
                if mat:
                    replaceUvMaps(mat.node_tree)


    def copyBodyPart(self, graft, hum):
        apgs = graft.data.DazBodyPart
        cpgs = hum.data.DazBodyPart
        for sname,apg in apgs.items():
            if sname not in cpgs.keys():
                cpg = cpgs.add()
                cpg.name = sname
                cpg.s = apg.s


    def moveGraftVerts(self, graft, hum, cvgrps):
        from .modifier import addShapekey, getBasicShape
        cvgroups = dict([(vgrp.index, vgrp.name) for vgrp in hum.vertex_groups])
        averts = graft.data.vertices
        cverts = hum.data.vertices
        for pair in graft.data.DazGraftGroup:
            avert = averts[pair.a]
            cvert = cverts[pair.b]
            avert.co = cvert.co
            for cg in cvert.groups:
                vgname = cvgroups[cg.group]
                if vgname in graft.vertex_groups.keys():
                    avgrp = graft.vertex_groups[vgname]
                else:
                    avgrp = graft.vertex_groups.new(name=vgname)
                avgrp.add([pair.a], cg.weight, 'REPLACE')

        # Create empty shapekeys
        cskeys = hum.data.shape_keys
        if cskeys:
            abasic,askeys,new = getBasicShape(graft)
            for cskey in cskeys.key_blocks:
                if cskey.name not in askeys.key_blocks.keys():
                    graft.shape_key_add(name = cskey.name)

        # Move shapekey positions
        askeys = graft.data.shape_keys
        if askeys:
            for askey in askeys.key_blocks:
                if cskeys and askey.name in cskeys.key_blocks.keys():
                    cdata = cskeys.key_blocks[askey.name].data
                else:
                    cdata = cverts
                for pair in graft.data.DazGraftGroup:
                    askey.data[pair.a].co = cdata[pair.b].co

        # Copy vertex groups
        for pair in graft.data.DazGraftGroup:
            for agrp in graft.vertex_groups:
                agrp.remove([pair.a])
            cv = cverts[pair.b]
            for g in cv.groups:
                vname = cvgrps[g.group]
                if vname not in graft.vertex_groups.keys():
                    graft.vertex_groups.new(name=vname)
                agrp = graft.vertex_groups[vname]
                agrp.add([pair.a], g.weight, 'REPLACE')


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(me.uv_layers[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    me.uv_layers.remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def removeMultires(self, ob):
        for mod in ob.modifiers:
            if mod.type == 'MULTIRES':
                ob.modifiers.remove(mod)


def replaceNodeNames(mat, oldname, newname):
    texco = None
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_COORD':
            texco = node
            break

    uvmaps = []
    for node in mat.node_tree.nodes:
        if isinstance(node, bpy.types.ShaderNodeUVMap):
            if node.uv_map == oldname:
                node.uv_map = newname
                uvmaps.append(node)
        elif isinstance(node, bpy.types.ShaderNodeAttribute):
            if node.attribute_name == oldname:
                node.attribute_name = newname
        elif isinstance(node, bpy.types.ShaderNodeNormalMap):
            if node.uv_map == oldname:
                node.uv_map = newname

    if texco and uvmaps:
        fromsocket = texco.outputs["UV"]
        tosockets = []
        for link in mat.node_tree.links:
            if link.from_node in uvmaps:
                tosockets.append(link.to_socket)
        for tosocket in tosockets:
            mat.node_tree.links.new(fromsocket, tosocket)


def copyModifier(smod, tmod):
    for attr in dir(smod):
        if (attr[0] != "_" and
            attr not in ["bl_rna", "is_override_data", "rna_type", "type"]):
            value = getattr(smod, attr)
            if (isSimpleType(value) or
                isinstance(value, (bpy.types.Object, bpy.types.NodeTree))):
                try:
                    setattr(tmod, attr, getattr(smod, attr))
                except AttributeError:
                    pass

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
        ob = context.object
        if self.keepIdx < 0:
            raise DazError("No active UV layer found")
        mergeIdx = int(self.layer)
        mergeUvLayers(ob.data, self.keepIdx, mergeIdx, self.allowOverlap)
        deselectAllVerts(ob)


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


def mergeUvLayers(me, keepIdx, mergeIdx, allowOverlap):
    def checkLayersOverlap(keepLayer, mergeLayer):
        for keepData,mergeData in zip(keepLayer.data, mergeLayer.data):
            if (keepData.uv.length > 1e-6 and
                mergeData.uv.length > 1e-6):
                msg = 'UV layers overlap:\n"%s", "%s"' % (keepLayer.name, mergeLayer.name)
                reportError(msg)
                return True
        return False

    def replaceUVMapNodes(me, mergeLayer):
        from .tree import hideAllBut
        for mat in me.materials:
            if mat is None:
                continue
            texco = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
            deletes = {}
            for link in mat.node_tree.links:
                node = link.from_node
                if (node.type == 'UVMAP' and
                    node.uv_map == mergeLayer.name):
                    deletes[node.name] = node
                    if texco is None:
                        texco = mat.node_tree.nodes.new(type="ShaderNodeTexCoord")
                        texco.location = node.location
                        texco.hide = True
                        hideAllBut(texco, ["UV"])
                    mat.node_tree.links.new(texco.outputs["UV"], link.to_socket)
            for node in deletes.values():
                mat.node_tree.nodes.remove(node)

    if keepIdx == mergeIdx:
        raise DazError("UV layer is the same as the active render layer.")
    keepLayer = me.uv_layers[keepIdx]
    mergeLayer = me.uv_layers[mergeIdx]
    if not keepLayer.active_render:
        raise DazError("Only the active render layer may be the layer to keep")
    if not allowOverlap:
        if checkLayersOverlap(keepLayer, mergeLayer):
            return
    replaceUVMapNodes(me, mergeLayer)
    for n,data in enumerate(mergeLayer.data):
        if data.uv.length > 1e-6:
            keepLayer.data[n].uv = data.uv
    for mat in me.materials:
        if mat and mat.use_nodes:
            replaceNodeNames(mat, mergeLayer.name, keepLayer.name)
    me.uv_layers.active_index = keepIdx
    me.uv_layers.remove(mergeLayer)

#-------------------------------------------------------------
#   Get selected rigs
#-------------------------------------------------------------

def getSelectedRigs(context):
    rig = context.object
    if rig:
        setMode('OBJECT')
    subrigs = []
    for ob in getSelectedArmatures(context):
        if ob != rig:
            subrigs.append(ob)
    return rig, subrigs

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

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

def getDupName(subrig, bname):
    return "%s:%s" % (subrig.name, bname)


class BoneInfo:
    def __init__(self, bone, pb, parname, wmat):
        self.head = bone.head_local.copy()
        self.tail = bone.tail_local.copy()
        self.matrix_local = bone.matrix_local.copy()
        self.parent = parname
        self.use_deform = bone.use_deform
        self.pb = pb
        self.matrix = pb.matrix.copy()
        self.matrix_world = wmat


    def setEditBone(self, bname, ebones, subrig):
        eb = ebones.new(bname)
        eb.head = self.head
        eb.tail = self.tail
        if self.matrix_world:
            eb.matrix = self.matrix_world @ self.matrix_local
        else:
            eb.matrix = self.matrix_local
        self.use_deform = self.use_deform
        if self.parent is not None:
            if self.parent in ebones.keys():
                eb.parent = ebones[self.parent]
            else:
                dupname = getDupName(subrig, self.parent)
                eb.parent = ebones.get(dupname)


    def setPoseBone(self, pb, rig):
        from .figure import copyBoneInfo
        from .store import copyConstraints
        copyBoneInfo(self.pb, pb)
        copyConstraints(self.pb, pb, rig)
        if self.matrix_world:
            #pb.matrix = self.matrix_world @ self.matrix
            pb.matrix_basis = Matrix()
        else:
            pb.matrix = self.matrix
        pb.custom_shape = self.pb.custom_shape
        if hasattr(pb, "custom_shape_translation"):
            pb.custom_shape_scale_xyz = self.pb.custom_shape_scale_xyz
            pb.custom_shape_translation = self.pb.custom_shape_translation
            pb.custom_shape_rotation_euler = self.pb.custom_shape_rotation_euler


class MergeRigsOptions:
    duplicateDistance : FloatProperty(
        name = "Duplicate Distance (cm)",
        description = "Create separate bones if several bones with the same name are found,\nand they are at least this far apart (in centimeters)",
        min = 0.0,
        default = 1.0)

    useMergeNonConforming : EnumProperty(
        items = [('NEVER', "Never", "Don't merge non-conforming bones"),
                 ('CONTROLS', "Widget Controls", "Only merge known widget controls"),
                 ('ALWAYS', "Always", "Always merge non-conforming bones")],
        name = "Non-conforming Rigs",
        description = "Also merge non-conforming rigs.\n(Bone parented and with no bones in common with main rig)",
        default = 'CONTROLS')

    useConvertWidgets : BoolProperty(
        name = "Convert To Widgets",
        description = "Convert face controls to bone custom shapes",
        default = True)

    useHiddenRigs : BoolProperty(
        name = "Include Hidden Rigs",
        description = "Also merge bones from armatures that are hidden",
        default = False)


class DAZ_OT_MergeRigs(DazPropsOperator, MergeRigsOptions, DriverUser, IsArmature):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    useOnlySelected : BoolProperty(
        name = "Only Selected Rigs",
        description = "Only merge armatures that are children of selected armatures",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useOnlySelected")
        self.layout.prop(self, "useHiddenRigs")
        self.layout.prop(self, "duplicateDistance")
        self.layout.prop(self, "useMergeNonConforming")
        self.layout.prop(self, "useConvertWidgets")

    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        def findSelectedRoots(objects):
            roots = []
            for ob in objects:
                if ob.type == 'ARMATURE' and ob.select_get():
                    roots.append(ob)
                else:
                    roots += findSelectedRoots(ob.children)
            return roots

        roots = [ob for ob in context.view_layer.objects if ob.parent is None]
        if self.useOnlySelected:
            roots = findSelectedRoots(roots)
        excluded = findExcludedObjects(context, self.useHiddenRigs)
        if self.useMergeNonConforming == 'ALWAYS':
            rootmats = applyTransformToObjects(roots, excluded)
        else:
            rootmats = []
        deletes = []
        try:
            deletes = self.mergeRigs(context, roots, excluded)
        finally:
            restoreTransformsToObjects(rootmats)
        deleteObjects(context, deletes)


    def mergeRigs(self, context, roots, excluded):
        def getObjects(ob, parent, objects, infos, widgets, info):
            if ob in excluded:
                return
            if parent and parent.type == 'ARMATURE':
                objects.append((ob, parent, ob.matrix_world.copy(), ob.hide_viewport, ob.hide_get()))
                ob.hide_viewport = False
                ob.hide_set(False)
            wmat = None
            if ob.type == 'ARMATURE':
                rig = ob
                parentBone = None
                if rig.parent is None or rig.parent.type != 'ARMATURE':
                    conforms = False
                elif rig.parent_type == 'BONE':
                    conforms = False
                    if self.useMergeNonConforming == 'ALWAYS':
                        conforms = True
                    elif (self.useMergeNonConforming == 'CONTROLS' and
                          rig.DazUrl.lower() in DF.WidgetControls):
                        conforms = True
                        widgets.append(rig)
                    if conforms:
                        parentBone = rig.parent_bone
                        wmat = rig.matrix_world.copy()
                else:
                    conforms = True
                if not conforms:
                    parent = rig
                    info = []
                    infos.append(info)
                bones = {}
                for pb in rig.pose.bones:
                    bone = pb.bone
                    if bone.parent:
                        parname = bone.parent.name
                    else:
                        parname = parentBone
                    bones[bone.name] = BoneInfo(bone, pb, parname, wmat)
                meshes = [child for child in rig.children if child.type == 'MESH']
                info.append((rig, bones, meshes))
            else:
                parent = ob
            for child in ob.children:
                getObjects(child, parent, objects, infos, widgets, info)

        # Collect info about objects and bones
        objects = []
        infos = []
        widgets = []
        for root in roots:
            getObjects(root, root.parent, objects, infos, widgets, [])

        def addMergedProp(rig, subrig, idx):
            pg = rig.data.DazMergedRigs.add()
            pg.name = str(idx)
            pg.s = subrig.DazUrl
            pg.b = (subrig.parent_bone is not None)

        # Add info about merge rigs
        # Rename duplicate bones
        deletes = []
        dupss = []
        for info in infos:
            rig,bones,_meshes = info[0]
            heads = {}
            dups = {}
            dupss.append(dups)
            idx = 0
            addMergedProp(rig, rig, idx)
            for subrig,subbones,meshes in info[1:]:
                deletes.append(subrig)
                for bname,binfo in subbones.items():
                    if bname in bones.keys():
                        if binfo.use_deform:
                            bone = rig.data.bones[bname]
                            bone.use_deform = True
                    else:
                        head0 = heads.get(bname)
                        if head0 and (binfo.head-head0).length > self.duplicateDistance * GS.scale:
                            dups[bname] = True
                        else:
                            heads[bname] = binfo.head
                idx += 1
                addMergedProp(rig, subrig, idx)

        # Create the new editbones
        hasNew = False
        taken = []
        for info,dups in zip(infos, dupss):
            rig,bones,_meshes = info[0]
            activateObject(context, rig)
            setMode('EDIT')
            for subrig,subbones,_submeshes in info[1:]:
                for bname,binfo in subbones.items():
                    if bname not in bones.keys() and bname not in taken:
                        hasNew = True
                        if bname in dups.keys():
                            dupname = getDupName(subrig, bname)
                            binfo.setEditBone(dupname, rig.data.edit_bones, subrig)
                        else:
                            binfo.setEditBone(bname, rig.data.edit_bones, subrig)
                            taken.append(bname)
            setMode('OBJECT')
        if hasNew:
            enableRigNumLayer(rig, T_CUSTOM)

        from .driver import copyProp, retargetDrivers
        def copyProps(src, trg, ovr):
            for prop,value in src.items():
                if prop[0:3] != "Daz":
                    copyProp(prop, src, trg, ovr)

        # Copy rig, armature and posebone properties and drivers
        for info,dups in zip(infos, dupss):
            rig,bones,_meshes = info[0]
            for subrig,subbones,submeshes in info[1:]:
                for key,pg0 in subrig.data.DazBoneMap.items():
                    if key not in rig.data.DazBoneMap.keys():
                        pg = rig.data.DazBoneMap.add()
                        pg.name = pg0.name
                        pg.s = pg0.s

                copyProps(subrig, rig, True)
                copyProps(subrig.data, rig.data, False)
                assoc = dict([(bname, getDupName(subrig, bname)) for bname in dups.keys()])
                self.copyAssocDrivers(subrig.data, rig.data, subrig, rig, assoc)
                self.copyAssocDrivers(subrig, rig, subrig, rig, assoc)
                for submesh in submeshes:
                    skeys = submesh.data.shape_keys
                    if skeys:
                        retargetDrivers(skeys, subrig, rig)
                    for mat in submesh.data.materials:
                        if mat:
                            retargetDrivers(mat.node_tree, subrig, rig)

                for bname,binfo in subbones.items():
                    if bname in bones.keys():
                        continue
                    elif bname in dups.keys():
                        dupname = getDupName(subrig, bname)
                        for mesh in submeshes:
                            vgrp = mesh.vertex_groups.get(bname)
                            if vgrp:
                                vgrp.name = dupname
                        pb = rig.pose.bones.get(dupname)
                    else:
                        pb = rig.pose.bones.get(bname)
                    if pb:
                        binfo.setPoseBone(pb, rig)
                        enableBoneNumLayer(pb.bone, rig, T_CUSTOM)

        # Widgets
        if widgets:
            from .proxy import WidgetConverter
            wrig = widgets[0]
            rig = wrig.parent
            ob = getMeshChildren(wrig)[0]
            if rig and ob and rig.type == 'ARMATURE':
                print("Convert %s to widgets for %s" % (ob.name, rig.name))
                activateObject(context, ob)
                wc = WidgetConverter()
                wc.convertWidgets(context, rig, ob)
                enableRigNumLayer(rig, T_WIDGETS)

        # Restore all objects
        for ob,parent,wmat,hide1,hide2 in objects:
            ob.parent = parent
            setWorldMatrix(ob, wmat)
            ob.hide_viewport = hide1
            ob.hide_set(hide2)
            if ob.type == 'MESH':
                mod = getModifier(ob, 'ARMATURE')
                if mod:
                    mod.object = parent

        return deletes

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

class DAZ_OT_CopyPose(DazPropsOperator, LockEnabler, IsArmature):
    bl_idname = "daz.copy_pose"
    bl_label = "Copy Pose"
    bl_description = "Copy pose from active rig to selected rigs"
    bl_options = {'UNDO'}

    useDisableLocks : BoolProperty(
        name = "Disable Locks And Limits",
        description = "Disable locks and limits",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useDisableLocks")

    def setLocks(self, pb):
        pb.lock_location = pb.lock_rotation = FFalse


    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            raise DazError("No source armature")
        if not subrigs:
            raise DazError("No target armature")

        def snapBone(pb, gmats):
            M1 = gmats.get(pb.name)
            if M1 is None:
                return
            R1 = pb.bone.matrix_local
            if pb.parent:
                M0 = gmats.get(pb.parent.name)
                if M0 is None:
                    return
                R0 = pb.parent.bone.matrix_local
                pb.matrix_basis = R1.inverted() @ R0 @ M0.inverted() @ M1
            else:
                pb.matrix_basis = R1.inverted() @ M1

        gmats = dict([(pb.name, pb.matrix.copy()) for pb in rig.pose.bones])
        for subrig in subrigs:
            if self.useDisableLocks:
                self.enableLocksLimits(rig, False, 0.0)
            print("Copy bones to %s:" % subrig.name)
            setWorldMatrix(subrig, rig.matrix_world)
            for pb in subrig.pose.bones:
                if pb.name in rig.pose.bones.keys():
                    snapBone(pb, gmats)

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(CollectionShower, DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):
    children = []
    for child in rig.children:
        setRestPose(child, rig, context)
        if activateObject(context, child):
            children.append((child, child.parent_type, child.parent_bone))
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    if activateObject(context, rig):
        bpy.ops.object.transform_apply()
        setMode('POSE')
        bpy.ops.pose.armature_apply()
        setMode('OBJECT')
    for child,type,bone in children:
        wmat = child.matrix_world.copy()
        child.parent = rig
        child.parent_type = type
        child.parent_bone = bone
        setWorldMatrix(child, wmat)


def safeTransformApply(useLocRot=True):
    try:
        bpy.ops.object.transform_apply(location=useLocRot, rotation=useLocRot, scale=True)
    except RuntimeError as err:
        print("Cannot apply transforms")


def applyAllObjectTransforms(rigs):
    bpy.ops.object.select_all(action='DESELECT')
    for rig in rigs:
        selectSet(rig, True)
    safeTransformApply()
    bpy.ops.object.select_all(action='DESELECT')
    status = []
    try:
        for rig in rigs:
            for ob in rig.children:
                if ob.parent_type != 'BONE':
                    status.append((ob, ob.hide_get(), ob.hide_select))
                    ob.hide_set(False)
                    ob.hide_select = False
                    selectSet(ob, True)
        safeTransformApply()
        for ob,hide,select in status:
            ob.hide_set(hide)
            ob.hide_select = select
        return True
    except RuntimeError:
        print("Could not apply object transformations")
        return False


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type != 'OBJECT' or ob.type != 'MESH':
        return
    if len(ob.vertex_groups) == 0:
        print("Mesh with no vertex groups: %s" % ob.name)
        return
    try:
        applyArmatureModifier(ob)
        ok = True
    except RuntimeError:
        print("Could not apply armature to %s" % ob.name)
        ok = False
    if ok:
        from .modifier import newArmatureModifier
        newArmatureModifier(rig.name, ob, rig)


def applyArmatureModifier(ob):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE':
            mname = mod.name
            if ob.data.shape_keys:
                if bpy.app.version < (2,90,0):
                    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                else:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                bpy.ops.object.modifier_apply(modifier=mname)

#-------------------------------------------------------------
#   Apply transform to objects
#-------------------------------------------------------------

def findExcludedObjects(context, useHidden):
    def excludeHidden(objects, layer):
        if not (layer.exclude or layer.hide_viewport):
            for ob in layer.collection.objects:
                if useHidden or not (ob.hide_viewport or ob.hide_get()):
                    objects.append(ob)
            for child in layer.children:
                excludeHidden(objects, child)

    objects = []
    excludeHidden(objects, context.view_layer.layer_collection)
    objects = set(objects)
    excluded = []
    for ob in context.scene.objects:
        if ob not in objects:
            excluded.append(ob)
    return excluded


def applyTransformToObjects(objects, excluded=[]):
    bpy.ops.object.select_all(action='DESELECT')
    parents = []
    for ob in objects:
        for child in ob.children:
            if child in excluded:
                continue
            parents.append((child, ob, child.matrix_world.copy(), child.hide_viewport, child.hide_get(), child.hide_select))
            child.hide_viewport = False
            child.hide_set(False)
            child.hide_select = False
            child.select_set(True)
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

    wmats = []
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        wmat = ob.matrix_world.copy()
        wmats.append((ob, wmat, ob.hide_viewport, ob.hide_get(), ob.hide_select))
        ob.hide_viewport = False
        ob.hide_set(False)
        ob.hide_select = False
        ob.select_set(True)
    bpy.ops.object.transform_apply()

    for child,ob,wmat,hide1,hide2,hide3 in parents:
        child.parent = ob
        setWorldMatrix(child, wmat)
        child.hide_viewport = hide1
        child.hide_set(hide2)
        child.hide_select = hide3

    return wmats


def restoreTransformsToObjects(wmats):
    bpy.ops.object.select_all(action='DESELECT')
    for ob,wmat,hide1,hide2,hide3 in wmats:
        setWorldMatrix(ob, wmat.inverted())
        ob.select_set(True)
    bpy.ops.object.transform_apply()
    for ob,wmat,hide1,hide2,hide3 in wmats:
        setWorldMatrix(ob, wmat)
        ob.hide_viewport = hide1
        ob.hide_set(hide2)
        ob.hide_select = hide3

#-------------------------------------------------------------
#   Merge toes
#-------------------------------------------------------------

def mergeBones(rig, mergers, parents, context):
    from .driver import removeBoneSumDrivers

    deletes = []
    for bones in mergers.values():
        deletes += bones + [drvBone(bone) for bone in bones]
    activateObject(context, rig)
    removeBoneSumDrivers(rig, deletes)

    swapped = {}
    for key,bnames in mergers.items():
        for bname in bnames:
            swapped[bname] = key
    for ob in rig.children:
        if ob.parent_type == 'BONE' and ob.parent_bone in swapped.keys():
            wmat = ob.matrix_world.copy()
            ob.parent_bone = swapped[ob.parent_bone]
            setWorldMatrix(ob, wmat)

    setMode('EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    for eb in rig.data.edit_bones:
        if eb.name in deletes:
            rig.data.edit_bones.remove(eb)


def mergeVertexGroups(rig, mergers):
    setMode('OBJECT')
    for toe in mergers.keys():
        bone = rig.data.bones.get(toe)
        if bone:
            bone.use_deform = True

    for ob in getMeshChildren(rig):
        for toe,subtoes in mergers.items():
            subgrps = []
            for subtoe in subtoes:
                if subtoe in ob.vertex_groups.keys():
                    subgrps.append(ob.vertex_groups[subtoe])
            if toe in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[toe]
            elif subgrps:
                vgrp = ob.vertex_groups.new(name=toe)
            else:
                continue
            idxs = [vg.index for vg in subgrps]
            idxs.append(vgrp.index)
            weights = dict([(vn,0) for vn in range(len(ob.data.vertices))])
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group in idxs:
                         weights[v.index] += g.weight
            for subgrp in subgrps:
                ob.vertex_groups.remove(subgrp)
            for vn,w in weights.items():
                if w > 1e-3:
                    vgrp.add([vn], w, 'REPLACE')

    updateDrivers(rig)


class DAZ_OT_MergeToes(DazOperator, IsArmature):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge separate toes into a single toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        genesisToes = {
            "lFoot" : ["lMetatarsals"],
            "rFoot" : ["rMetatarsals"],
            "lToe" : ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
                      "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
            "rToe" : ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
                      "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
            "l_foot" : ["l_metatarsal"],
            "r_foot" : ["r_metatarsal"],
            "l_toes" : ["l_bigtoe1", "l_indextoe1", "l_midtoe1", "l_ringtoe1", "l_pinkytoe1",
                        "l_bigtoe2", "l_indextoe2", "l_midtoe2", "l_ringtoe2", "l_pinkytoe2"],
            "r_toes" : ["r_bigtoe1", "r_indextoe1", "r_midtoe1", "r_ringtoe1", "r_pinkytoe1",
                        "r_bigtoe2", "r_indextoe2", "r_midtoe2", "r_ringtoe2", "r_pinkytoe2"],
        }

        newParents = {
            "lToe" : "lFoot",
            "rToe" : "rFoot",
            "l_toes" : "l_foot",
            "r_toes" : "r_foot",
        }
        rig = context.object
        mergeBones(rig, genesisToes, newParents, context)
        mergeVertexGroups(rig, genesisToes)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeGeografts,
    DAZ_OT_MergeUvLayers,
    DAZ_OT_MergeMeshes,
    DAZ_OT_MergeRigs,
    DAZ_OT_EliminateEmpties,
    DAZ_OT_CopyPose,
    DAZ_OT_ApplyRestPoses,
    DAZ_OT_MergeToes,
]

def register():
    from .propgroups import DazStringBoolGroup
    bpy.types.Armature.DazMergedRigs = CollectionProperty(type = DazStringBoolGroup)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

