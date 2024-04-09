# Copyright (c) 2016-2024, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import os
import json
import bpy
from mathutils import Matrix

from .utils import *
from .error import *
from .driver import DriverUser
from .fileutils import DF
from .geometry import getActiveUvLayer

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

        from .udim import isShellNode
        active = getActiveUvLayer(ob)
        uvmaps = {}
        shellmaps = {}
        for mat in ob.data.materials:
            if not (mat and mat.node_tree):
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    uvname = getUvMap(node.inputs.get("Vector"), active.name)
                    uvmaps[uvname] = True
                elif False and isShellNode(node):
                    uvname = getUvMap(node.inputs.get("UV"), "**")
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
    useVertexTable : BoolProperty(
        name = "Add Vertex Table",
        description = (
            "Add a table with vertex numbers before and after merge.\n"+
            "Makes it possible to add morphs after merge,\n"+
            "but affects viewport performance"),
        default = False)

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


class DAZ_OT_MergeGeografts(DazPropsOperator, MergeGeograftOptions, UVLayerMerger, DriverUser, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    def draw(self, context):
        if bpy.app.version >= (3,4,0):
            self.layout.prop(self, "useGeoNodes")
        if not self.useGeoNodes:
            self.layout.prop(self, "keepOriginal")
            self.layout.prop(self, "useVertexTable")
        self.layout.prop(self, "useSubDDisplacement")
        box = self.layout.box()
        box.label(text="UDIM Materials")
        box.prop(self, "useFixTiles")
        self.drawUVLayer(box)


    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        safeTransformApply()
        from .finger import isGenesis
        cob = context.object
        meshes = getSelectedMeshes(context)
        ncverts = len(cob.data.vertices)
        chars = {ncverts : cob}
        prio = {ncverts : False}
        for ob in meshes:
            ob.active_shape_key_index = 0
            nverts = len(ob.data.vertices)
            if nverts not in chars.keys() or isGenesis(ob):
                chars[nverts] = ob
                prio[nverts] = (not (not ob.data.DazGraftGroup))

        grafts = dict([(ncverts, []) for ncverts in chars.keys()])
        ngrafts = 0
        misses = []
        for aob in meshes:
            if aob.data.DazGraftGroup:
                ncverts = aob.data.DazVertexCount
                if ncverts in grafts.keys():
                    grafts[ncverts].append(aob)
                    ngrafts += 1
                else:
                    print("No matching mesh found for geograft %s" % aob.name)
                    misses.append(aob)
        if ngrafts == 0:
            if misses:
                msg = "No matching mesh found for these geografts:\n"
                for aob in misses:
                    msg += "    %s\n" % aob.name
                msg += "Has some mesh been edited?"
            else:
                msg = "No geograft selected"
            raise DazError(msg)

        for ncverts,cob in chars.items():
            if prio[ncverts]:
                self.mergeGeografts(context, ncverts, cob, grafts[ncverts])
        for ncverts,cob in chars.items():
            if not prio[ncverts]:
                self.mergeGeografts(context, ncverts, cob, grafts[ncverts])


    def duplicateMeshes(self, context, cob, anatomies):
        from .finger import getFingerPrint
        dob = None
        danatomies = []
        if activateObject(context, cob):
            finger = getFingerPrint(cob)
            for aob in anatomies:
                aob.select_set(True)
            bpy.ops.object.duplicate()
            for ob in getSelectedMeshes(context):
                if getFingerPrint(ob) == finger:
                    if ob != cob:
                        dob = ob
                elif ob not in anatomies:
                    danatomies.append(ob)
        if dob is None:
            return
        cname = baseName(cob.name)
        basename = cname.rstrip("Mesh")
        cob.name = "%s Merged" % basename
        coll = getCollection(context, cob)
        dob.name = cname

        coll1 = bpy.data.collections.new("%sOriginal" % basename)
        coll.children.link(coll1)
        unlinkAll(dob, False)
        coll1.objects.link(dob)
        lcoll1 = getLayerCollection(context, coll1)
        lcoll1.exclude = True

        coll2 = bpy.data.collections.new("%sMerged" % basename)
        coll.children.link(coll2)
        unlinkAll(cob, False)
        coll2.objects.link(cob)

        coll3 = bpy.data.collections.new("%sGeografts" % basename)
        coll.children.link(coll3)
        for aob in danatomies:
            unlinkAll(aob, False)
            coll3.objects.link(aob)
            aob.name = baseName(aob.name)
        lcoll3 = getLayerCollection(context, coll3)
        lcoll3.exclude = True
        activateObject(context, cob)


    def mergeGeografts(self, context, ncverts, cob, anatomies):
        if not anatomies:
            return
        try:
            cob.data
        except ReferenceError:
            print("No ref")
            return

        if self.keepOriginal and not self.useGeoNodes:
            self.duplicateMeshes(context, cob, anatomies)
        self.initUvNames()
        subDLevels = 0
        self.setActiveUvLayer(cob)
        influs = dict([(prop, value) for prop,value in cob.items() if prop[0:6] == "INFLU "])
        for aob in anatomies:
            self.renameUvLayers(aob)
            self.storeUvName(aob)
            if self.useFixTiles:
                from .udim import TileFixer
                fixer = TileFixer()
                fixer.udimsFromGraft(aob, cob)
            self.copyBodyPart(aob, cob)
            for prop,value in aob.items():
                if prop[0:6] == "INFLU " and prop not in influs.keys():
                    influs[prop] = value
            for mod in list(aob.modifiers):
                if mod.type == 'SURFACE_DEFORM':
                    aob.modifiers.remove(mod)
                elif self.useSubDDisplacement and mod.type == 'SUBSURF':
                    if mod.render_levels > subDLevels:
                        subDLevels = mod.render_levels

        # Select graft group for each anatomy
        cuvname = getActiveUvLayer(cob).name
        drivers = {}
        cvgrps = dict([(vgrp.index, vgrp.name) for vgrp in cob.vertex_groups])
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob, cvgrps)
            self.getShapekeyDrivers(aob, drivers)
            self.replaceTexco(aob, cuvname, self.useGeoNodes)

        # For the body, setup mask groups
        activateObject(context, cob)
        for mod in cob.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        nverts = len(cob.data.vertices)
        self.vfaces = dict([(vn,[]) for vn in range(nverts)])
        for f in cob.data.polygons:
            for vn in f.vertices:
                self.vfaces[vn].append(f.index)

        nfaces = len(cob.data.polygons)
        self.fmasked = dict([(fn,False) for fn in range(nfaces)])
        for aob in anatomies:
            for face in aob.data.DazMaskGroup:
                self.fmasked[face.a] = True

        # If cob is itself a geograft, make sure to keep tbe boundary
        if cob.data.DazGraftGroup:
            cgrafts = [pair.a for pair in cob.data.DazGraftGroup]
        else:
            cgrafts = []

        deselectAllVerts(cob)

        # Select body verts to delete
        self.vdeleted = dict([(vn,False) for vn in range(nverts)])
        self.cmasks = {}
        for aob in anatomies:
            cmask = self.cmasks[aob.name] = dict([(vn,False) for vn in range(nverts)])
            paired = [pair.b for pair in aob.data.DazGraftGroup]
            for face in aob.data.DazMaskGroup:
                fverts = cob.data.polygons[face.a].vertices
                vdelete = []
                for vn in fverts:
                    if vn in cgrafts:
                        pass
                    elif vn not in paired:
                        vdelete.append(vn)
                    else:
                        mfaces = [fn for fn in self.vfaces[vn] if self.fmasked[fn]]
                        if len(mfaces) == len(self.vfaces[vn]):
                            vdelete.append(vn)
                for vn in vdelete:
                    cob.data.vertices[vn].select = True
                    self.vdeleted[vn] = True
                    cmask[vn] = True

        # Build association tables between new and old vertex numbers
        assoc = {}
        vn2 = 0
        for vn in range(nverts):
            if not self.vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        # Original vertex locations
        if self.useVertexTable and not self.useGeoNodes:
            self.origlocs = [v.co.copy() for v in cob.data.vertices]

        # If cob is itself a geograft, store locations
        if cob.data.DazGraftGroup:
            verts = cob.data.vertices
            self.locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in cob.data.DazGraftGroup])

        # Delete the masked verts
        self.deleteSelectedVerts()

        # Select nothing
        for aob in anatomies:
            deselectAllVerts(aob)
        deselectAllVerts(cob)

        # Select verts on common boundary
        self.cedges = {}
        self.aedges = {}
        for aob in anatomies:
            selectSet(aob, True)
            naverts = len(aob.data.vertices)
            aedge = self.aedges[aob.name] = dict([(vn,False) for vn in range(naverts)])
            cedge = self.cedges[aob.name] = dict([(vn,False) for vn in range(nverts)])
            pg = cob.data.DazMergedGeografts.add()
            pg.name = aob.name
            for pair in aob.data.DazGraftGroup:
                aob.data.vertices[pair.a].select = True
                if pair.b in assoc.keys():
                    aedge[pair.a] = True
                    cvn = assoc[pair.b]
                    cob.data.vertices[cvn].select = True
                    cedge[pair.b] = True

        # Also select cob graft group. These will not be removed.
        if cob.data.DazGraftGroup:
            for pair in cob.data.DazGraftGroup:
                cvn = assoc[pair.a]
                cob.data.vertices[cvn].select = True

        # Retarget shells
        self.retargetShellInfluence(cob, anatomies, influs)
        if bpy.app.version < (3,1,0):
            self.mergeDestructively(context, cob, anatomies, cgrafts)
        elif self.useGeoNodes:
            self.mergeWithGeoNodes(context, cob, anatomies, cgrafts)
        else:
            self.retargetShellModifiers(cob, anatomies)
            self.mergeDestructively(context, cob, anatomies, cgrafts)

        self.copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)
        for mod in cob.modifiers:
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


    def mergeDestructively(self, context, cob, anatomies, cgrafts):
        # Join meshes and remove doubles
        names = [aob.name for aob in anatomies]
        print("Merge %s to %s" % (names, cob.name))
        threshold = 0.001*cob.DazScale
        bpy.ops.object.join()
        setMode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        setMode('OBJECT')
        selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])
        deselectAllVerts(cob)

        # Create graft vertex group
        vgrp = cob.vertex_groups.new(name="Graft")
        for vn in selected.keys():
            vgrp.add([vn], 1.0, 'REPLACE')
        mod = getModifier(cob, 'MULTIRES')
        if mod:
            smod = cob.modifiers.new("Smooth Graft", 'SMOOTH')
            smod.factor = 1.0
            smod.iterations = 10
            smod.vertex_group = vgrp.name

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = self.locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        # Create a vertex table
        if self.useVertexTable and not self.useGeoNodes:
            vn = 0
            eps = 1e-3*cob.DazScale
            for vn0,r in enumerate(self.origlocs):
                item = cob.data.DazOrigVerts.add()
                item.name = str(vn0)
                v = cob.data.vertices[vn]
                if (v.co - r).length > eps:
                    item.a = -1
                else:
                    item.a = vn
                    vn += 1
        else:
            cob.data.DazFingerPrint = ""

        # Merge UV layers
        from .tree import pruneMaterials
        self.mergeUvs(cob)
        #pruneMaterials(cob)


    def mergeWithGeoNodes(self, context, cob, anatomies, cgrafts):
        from .dforce import ModStore
        stores = []
        showmods = []
        geogroup = None
        grpname = "Geografts %s" % cob.name
        for mod in list(cob.modifiers):
            if (mod.type == 'NODES' and
                mod.node_group.name.startswith("Geograft")):
                showmods.append((mod, mod.show_viewport))
                mod.show_viewport = False
                if mod.node_group.name == grpname:
                    geogroup = mod.node_group
            elif mod.type != 'ARMATURE':
                stores.append(ModStore(mod))
                cob.modifiers.remove(mod)
        if geogroup is None:
            from .geonodes import GeograftGroup
            group = GeograftGroup()
            group.create(grpname)
            group.addNodes()
            geogroup = group.group

        cuvname = getActiveUvLayer(cob).name
        self.replaceTexco(cob, cuvname, True)

        def addVertexGroup(ob, vgname, struct):
            vgrp = ob.vertex_groups.get(vgname)
            if vgrp is None:
                vgrp = ob.vertex_groups.new(name=vgname)
                verts = [vn for vn,ok in struct.items() if ok]
                for vn in verts:
                    vgrp.add([vn], 1, 'REPLACE')
            return vgrp

        for aob in anatomies:
            maskname = "%s Mask" % aob.name
            edgename = "%s Edge" % aob.name
            cmask = addVertexGroup(cob, maskname, self.cmasks[aob.name])
            cedge = addVertexGroup(cob, edgename, self.cedges[aob.name])
            aedge = addVertexGroup(aob, edgename, self.aedges[aob.name])
            for vgrp in aob.vertex_groups:
                if vgrp.name not in list(cob.vertex_groups.keys()):
                    cob.vertex_groups.new(name=vgrp.name)
            for amod in list(aob.modifiers):
                if amod.type in ['SUBSURF']:
                    amod.show_viewport = amod.show_render = False
                    aob.modifiers.remove(amod)

            mod = cob.modifiers.new("Geograft %s" % aob.name, 'NODES')
            mod.node_group = geogroup
            if BLENDER3:
                bpy.ops.object.geometry_nodes_input_attribute_toggle(prop_path=propRef("Input_2_use_attribute"), modifier_name=mod.name)
                bpy.ops.object.geometry_nodes_input_attribute_toggle(prop_path=propRef("Input_3_use_attribute"), modifier_name=mod.name)
                mod["Input_1"] = aob
                mod["Input_2_attribute_name"] = edgename
                mod["Input_3_attribute_name"] = maskname
                mod["Input_4"] = 0.01*cob.DazScale
            else:
                bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name=mod.name)
                bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_3", modifier_name=mod.name)
                mod["Socket_1"] = aob
                mod["Socket_2_attribute_name"] = edgename
                mod["Socket_3_attribute_name"] = maskname
                mod["Socket_4"] = 0.01*cob.DazScale
            aob.hide_set(True)
            aob.hide_render = True
            for mod in aob.modifiers:
                if mod.type == 'NODES':
                    mod.show_viewport = mod.show_render = True
        for mod,show in showmods:
            mod.show_viewport = show
        for store in stores:
            store.restore(cob)


    def retargetShellModifiers(self, cob, anatomies):
        from .tree import findLinksFrom
        socket1 = ("Input_1" if BLENDER3 else "Socket_1")
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                for mod in ob.modifiers:
                    if mod.type == 'NODES':
                        aob = mod.get(socket1)
                        if aob and aob in anatomies:
                            mod[socket1] = cob


    def retargetShellInfluence(self, cob, anatomies, influs):
        for prop,value in influs.items():
            if prop not in cob.keys():
                cob[prop] = value
                setOverridable(cob, prop)
                cob.DazVisibilityDrivers = True
        for aob in anatomies:
            for mat in aob.data.materials:
                if mat and mat.node_tree.animation_data:
                    for fcu in mat.node_tree.animation_data.drivers:
                        for var in fcu.driver.variables:
                            for trg in var.targets:
                                if trg.id_type == 'OBJECT' and getProp(trg.data_path) in influs.keys():
                                    trg.id = cob



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

        uvmaps = {}
        for mat in ob.data.materials:
            if mat is None:
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
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


    def renameUvLayers(self, aob):
        def replaceUvMaps(tree):
            for node in tree.nodes:
                if node.type in ['NORMAL_MAP', 'UVMAP']:
                    if node.uv_map in renamed.keys():
                        node.uv_map = renamed[node.uv_map]
                elif node.type == 'GROUP':
                    replaceUvMaps(node.node_tree)

        renamed = {}
        for uvlayer in aob.data.uv_layers:
            if uvlayer.name.startswith(("Base", "Default")):
                newname = "%s:%s" % (uvlayer.name, aob.name)
                renamed[uvlayer.name] = newname
                uvlayer.name = newname
        if renamed:
            for mat in aob.data.materials:
                if mat:
                    replaceUvMaps(mat.node_tree)


    def copyBodyPart(self, aob, cob):
        apgs = aob.data.DazBodyPart
        cpgs = cob.data.DazBodyPart
        for sname,apg in apgs.items():
            if sname not in cpgs.keys():
                cpg = cpgs.add()
                cpg.name = sname
                cpg.s = apg.s


    def moveGraftVerts(self, aob, cob, cvgrps):
        from .modifier import addShapekey, getBasicShape
        cvgroups = dict([(vgrp.index, vgrp.name) for vgrp in cob.vertex_groups])
        averts = aob.data.vertices
        cverts = cob.data.vertices
        for pair in aob.data.DazGraftGroup:
            avert = averts[pair.a]
            cvert = cverts[pair.b]
            avert.co = cvert.co
            for cg in cvert.groups:
                vgname = cvgroups[cg.group]
                if vgname in aob.vertex_groups.keys():
                    avgrp = aob.vertex_groups[vgname]
                else:
                    avgrp = aob.vertex_groups.new(name=vgname)
                avgrp.add([pair.a], cg.weight, 'REPLACE')

        # Create empty shapekeys
        cskeys = cob.data.shape_keys
        if cskeys:
            abasic,askeys,new = getBasicShape(aob)
            for cskey in cskeys.key_blocks:
                if cskey.name not in askeys.key_blocks.keys():
                    aob.shape_key_add(name = cskey.name)

        # Move shapekey positions
        askeys = aob.data.shape_keys
        if askeys:
            for askey in askeys.key_blocks:
                if cskeys and askey.name in cskeys.key_blocks.keys():
                    cdata = cskeys.key_blocks[askey.name].data
                else:
                    cdata = cverts
                for pair in aob.data.DazGraftGroup:
                    askey.data[pair.a].co = cdata[pair.b].co

        # Copy vertex groups
        for pair in aob.data.DazGraftGroup:
            for agrp in aob.vertex_groups:
                agrp.remove([pair.a])
            cv = cverts[pair.b]
            for g in cv.groups:
                vname = cvgrps[g.group]
                if vname not in aob.vertex_groups.keys():
                    aob.vertex_groups.new(name=vname)
                agrp = aob.vertex_groups[vname]
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
            try:
                setattr(tmod, attr, getattr(smod, attr))
            except AttributeError:
                print(attr)

#-------------------------------------------------------------
#   Create graft and mask vertex groups
#-------------------------------------------------------------

class DAZ_OT_CreateGraftGroups(DazOperator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.DazGraftGroup)

    def run(self, context):
        aob = context.object
        objects = []
        for ob in getSelectedMeshes(context):
            if ob != aob:
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        cob = objects[0]
        gname = "Graft_" + aob.data.name
        mname = "Mask_" + aob.data.name
        self.createVertexGroup(aob, gname, [pair.a for pair in aob.data.DazGraftGroup])
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        self.createVertexGroup(cob, gname, graft)
        mask = {}
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    mask[vn] = True
        self.createVertexGroup(cob, mname, mask.keys())


    def createVertexGroup(self, ob, gname, vnums):
        vgrp = ob.vertex_groups.new(name=gname)
        for vn in vnums:
            vgrp.add([vn], 1, 'REPLACE')
        return vgrp

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
        cob = context.object
        self.initUvNames()
        for aob in getSelectedMeshes(context):
            if aob != cob:
                self.storeUvName(aob)
        for mod in cob.modifiers:
            if mod.type == 'SURFACE_DEFORM':
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        nlayers = len(cob.data.uv_layers)
        bpy.ops.object.join()
        self.mergeUvs(cob)
        deselectAllVerts(cob)
        for mod in cob.modifiers:
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


    def eliminateEmpties(self, ob, context, sub, coll):
        deletes = []
        elim = self.doEliminate(ob)
        if elim:
            if coll:
                subcoll = bpy.data.collections.new(ob.name)
                coll.children.link(subcoll)
                sub = True
                coll = subcoll
        elif sub and coll:
            if ob.name not in coll.objects:
                unlinkAll(ob, False)
                coll.objects.link(ob)
        for child in ob.children:
            self.eliminateEmpties(child, context, sub, coll)
        if elim and ob.type == 'EMPTY' and ob.parent:
            for child in ob.children:
                wmat = child.matrix_world.copy()
                if ob.parent_type == 'OBJECT':
                    child.parent = ob.parent
                    child.parent_type = 'OBJECT'
                    setWorldMatrix(child, wmat)
                    deletes.append(ob)
                elif ob.parent_type == 'BONE':
                    child.parent = ob.parent
                    child.parent_type = 'BONE'
                    child.parent_bone = ob.parent_bone
                    setWorldMatrix(child, wmat)
                    deletes.append(ob)
                elif ob.parent_type in ['VERTEX', 'VERTEX_3', 'VERTEX_TRI']:
                    activateObject(context, ob.parent)
                    deselectAllVerts(ob.parent)
                    for vn in ob.parent_vertices:
                        ob.parent.data.vertices[vn].select = True
                    child.select_set(True)
                    partypes = {
                        'VERTEX' : 'VERTEX',
                        'VERTEX_3' : 'VERTEX_TRI',
                        'VERTEX_TRI' : 'VERTEX_TRI',
                    }
                    partype = partypes[ob.parent_type]
                    bpy.ops.object.parent_set(type=partype)
                    print("%s parent: %s > %s" % (ob.parent_type, ob.parent.name, child.name))
                    deletes.append(ob)
                else:
                    raise DazError("Unknown parent type: %s %s" % (child.name, ob.parent_type))
        for empty in deletes:
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

class RigInfo:
    def __init__(self, rig, conforms, btn):
        self.name = rig.name
        self.rig = rig
        if len(rig.name) < 64:
            self.hash = rig.name
        else:
            self.hash = str(hash(rig.name))
        self.button = btn
        self.objects = []
        self.deletes = []
        self.addObjects(rig)
        self.conforms = conforms
        self.foundControl = None
        if rig.parent and rig.parent_type == 'BONE':
            self.parbone = rig.parent_bone
        else:
            self.parbone = None
        self.matrix = rig.matrix_world.copy()
        self.editbones = {}
        self.posebones = {}
        self.bones = {}


    def getBoneKey(self, bname):
        if self.button.useCreateDuplicates:
            return "%s:%s" % (self.hash, bname)
        else:
            return bname


    def addObjects(self, ob):
        for child in ob.children:
            if (getHideViewport(child) or
                child.parent_type in ['VERTEX', 'VERTEX_3', 'VERTEX_TRI']):
                continue
            elif child.type != 'ARMATURE':
                partype = child.parent_type
                parbone = child.parent_bone
                self.objects.append((child, (partype, parbone)))
                self.addObjects(child)


    def getEditBones(self, mainbones, extrabones):
        setMode('EDIT')
        for eb in self.rig.data.edit_bones:
            if eb.name not in mainbones:
                if eb.parent:
                    parent = eb.parent.name
                else:
                    parent = None
                key = self.getBoneKey(eb.name)
                self.editbones[key] = (eb.head.copy(), eb.tail.copy(), eb.roll, parent)
        setMode('OBJECT')
        for pb in self.rig.pose.bones:
            if pb.name in mainbones:
                key = pb.name
            else:
                key = self.getBoneKey(pb.name)
                extrabones.append(pb.name)
                self.posebones[key] = (pb, pb.matrix.copy())
                if not self.button.useCreateDuplicates:
                    mainbones.append(pb.name)
            self.bones[key] = pb.bone.use_deform


    def addEditBones(self, rig, idx, layer):
        setMode('EDIT')
        ebones = rig.data.edit_bones
        for bname,data in self.editbones.items():
            eb = ebones.new(bname)
            parent = data[3]
            eb = ebones[bname]
            if parent:
                self.setParent(eb, parent, ebones)
            elif self.parbone:
                self.setParent(eb, self.parbone, ebones)
            eb.head, eb.tail, eb.roll, parent = data
            enableBoneNumLayer(eb, rig, layer)
        setMode('OBJECT')
        for bname in self.editbones.keys():
            bone = rig.data.bones[bname]
            bone["DazRigIndex"] = idx


    def setParent(self, eb, parent, ebones):
        parkey = self.getBoneKey(parent)
        if parent in ebones.keys():
            eb.parent = ebones[parent]
        elif parkey in ebones.keys():
            eb.parent = ebones[parkey]
        else:
            print("Parent not found", eb.name, parent)


    def copyPose(self, context, rig):
        from .figure import copyBoneInfo
        from .fix import copyConstraints
        for key,pg0 in self.rig.data.DazBoneMap.items():
            if key not in rig.data.DazBoneMap.keys():
                pg = rig.data.DazBoneMap.add()
                pg.name = pg0.name
                pg.s = pg0.s
        self.copyProps(self.rig, rig, True)
        self.copyProps(self.rig.data, rig.data, False)
        self.button.copyDrivers(self.rig.data, rig.data, self.rig, rig)
        self.button.copyDrivers(self.rig, rig, self.rig, rig)   # causes warnings
        setActiveObject(context, rig)
        wmat = rig.matrix_world.inverted() @ self.matrix
        for bname,data in self.posebones.items():
            pb = rig.pose.bones[bname]
            subpb, pb.matrix = data
            copyBoneInfo(subpb, pb)
            copyConstraints(subpb, pb, rig)
        for bname,deform in self.bones.items():
            pb = rig.pose.bones[bname]
            if deform:
                pb.bone.use_deform = True


    def copyProps(self, src, trg, ovr):
        from .driver import copyProp
        for prop,value in src.items():
            if prop[0:3] != "Daz":
                copyProp(prop, src, trg, ovr)


    def reParent(self, rig):
        subrig = self.rig
        wmat = subrig.matrix_world.copy()
        subrig.parent = rig
        if self.parbone:
            subrig.parent_type = 'BONE'
            subrig.parent_bone = self.parbone
        else:
            subrig.parent_type = 'OBJECT'
        setWorldMatrix(subrig, wmat)


    def renameVertexGroups(self, ob):
        for key in self.editbones.keys():
            if self.button.useCreateDuplicates:
                _,bname = key.split(":", 1)
            else:
                bname = key
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = key


class MergeRigsOptions:
    useCreateDuplicates : BoolProperty(
        name = "Create Duplicate Bones",
        description = "Create separate bones if several bones with the same name are found",
        default = True)

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


class DAZ_OT_MergeRigs(DazPropsOperator, MergeRigsOptions, DriverUser, IsArmature):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    separateCharacters : BoolProperty(
        name = "Separate Characters",
        description = "Don't merge armature that belong to different characters",
        default = False)

    useSubrigsOnly : BoolProperty(
        name = "Only Child Rigs",
        description = "Only merge armatures that are children of the active armature",
        default = False)

    if BLENDER3:
        createMeshCollection : BoolProperty(
            name = "Create Mesh Collection",
            description = "Create a new collection and move all meshes to it",
            default = True)
    else:
        createMeshCollection = False

    def draw(self, context):
        self.layout.prop(self, "separateCharacters")
        if not self.separateCharacters:
            self.layout.prop(self, "useSubrigsOnly")
        self.layout.prop(self, "useCreateDuplicates")
        self.layout.prop(self, "useMergeNonConforming")
        self.layout.prop(self, "useConvertWidgets")
        if BLENDER3:
            self.layout.prop(self, "createMeshCollection")

    def __init__(self):
        DriverUser.__init__(self)


    def storeState(self, context):
        DazPropsOperator.storeState(self, context)
        self.rig = context.object
        self.storeRig(self.rig)


    def restoreState(self, context):
        self.restoreRig(self.rig)
        DazPropsOperator.restoreState(self, context)


    def run(self, context):
        if not self.separateCharacters:
            if self.useSubrigsOnly:
                rig = context.object
                subrigs = self.getSubRigs(rig)
            else:
                rig,subrigs = getSelectedRigs(context)
            locmat = rig.matrix_local.copy()
            rig.matrix_local = Matrix()
            info,subinfos,repars = self.getRigInfos(context, rig, subrigs)
            self.mergeRigs(context, info, subinfos, repars)
            rig.matrix_local = locmat
        else:
            rigs = []
            for rig in getSelectedArmatures(context):
                if rig.parent is None:
                    rigs.append(rig)
            rgroups = []
            locmats = []
            for rig in rigs:
                subrigs = self.getSubRigs(rig)
                rgroups.append((rig,subrigs))
                locmat = rig.matrix_local.copy()
                rig.matrix_local = Matrix()
                locmats.append(locmat)
            igroups = []
            for rig,subrigs in rgroups:
                igroup = self.getRigInfos(context, rig, subrigs)
                igroups.append(igroup)
            for info,subinfos,repars in igroups:
                activateObject(context, info.rig)
                self.mergeRigs(context, info, subinfos, repars)
            for rig,locmat in zip(rigs, locmats):
                rig.matrix_local = locmat


    def getRigInfos(self, context, rig, subrigs):
        def findSubObjects(rig, subobs):
            for child in rig.children:
                subobs.append(child)
                findSubObjects(child, subobs)

        subobs = []
        findSubObjects(rig, subobs)
        repars = []
        for ob in subobs:
            if ob.parent and ob.parent_type == 'BONE':
                if ob.parent in subrigs:
                    wmat = ob.matrix_world.copy()
                    repars.append((ob, wmat))

        subinfos = []
        conforming = []
        info = RigInfo(rig, True, self)
        for subrig in subrigs:
            if subrig.parent is None:
                conforms = (self.useMergeNonConforming == 'ALWAYS')
            elif subrig.parent == rig:
                conforms = self.isConforming(subrig, rig, info)
            elif subrig.parent in repars:
                continue
            else:
                conforms = True
            if conforms:
                conforming.append(subrig)
            subinfo = RigInfo(subrig, conforms, self)
            subinfos.append(subinfo)

        bpy.ops.object.select_all(action='DESELECT')
        for subinfo in subinfos:
            selectSet(subinfo.rig, True)
            for ob,_ in subinfo.objects:
                selectSet(ob, True)
        for ob in repars:
            selectSet(ob, True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.ops.object.select_all(action='DESELECT')
        for subrig in conforming:
            selectSet(subrig, True)
        safeTransformApply()
        return info, subinfos, repars


    def isConforming(self, subrig, rig, info):
        if self.useMergeNonConforming == 'ALWAYS':
            return True
        elif self.useMergeNonConforming == 'CONTROLS':
            if subrig.DazUrl.lower() in DF.WidgetControls:
                if info.foundControl:
                    subrig.hide_viewport = True
                    for child in subrig.children:
                        child.hide_viewport = True
                    return False
                info.foundControl = list(subrig.children)
                return True
        elif subrig.parent is None or subrig.parent_type == 'BONE':
            return False
        for bname in subrig.data.bones.keys():
            if bname in rig.data.bones.keys():
                return True
        return False


    def applyTransforms(self, info, subinfos):
        bpy.ops.object.select_all(action='DESELECT')
        selectSet(info.rig, True)
        for subinfo in subinfos:
            if subinfo.conforms:
                selectSet(subinfo.rig, True)
                for ob,data in subinfo.objects:
                    partype,parbone = data
                    if partype != 'BONE' and ob.type in ['MESH', 'ARMATURE']:
                        selectSet(ob, True)
        safeTransformApply()


    def getSubRigs(self, rig):
        subrigs = []
        for ob in rig.children:
            if ob.type == 'ARMATURE' and ob.select_get():
                subrigs.append(ob)
                subrigs += self.getSubRigs(ob)
        return subrigs


    def mergeRigs(self, context, info, subinfos, repars):
        rig = info.rig
        LS.forAnimation(None, rig)
        if rig is None:
            raise DazError("No rigs to merge")
        oldvis = getRigLayers(rig)
        enableAllRigLayers(rig)
        locmat = rig.matrix_local.copy()
        success = False
        try:
            self.mergeRigs1(context, info, subinfos, repars)
            success = True
        finally:
            rig.matrix_local = locmat
            setRigLayers(rig, oldvis)
            if success:
                enableRigNumLayer(rig, T_CUSTOM)
            if info.foundControl:
                enableRigNumLayer(rig, T_WIDGETS)
            setActiveObject(context, rig)
            updateDrivers(rig)
            updateDrivers(rig.data)


    def mergeRigs1(self, context, info, subinfos, repars):
        from .node import clearParent
        scn = context.scene
        rig = info.rig

        if not ES.easy:
            print("Merge infos to %s:" % rig.name)
        #self.applyTransforms(info, subinfos)
        mainbones = list(rig.pose.bones.keys())
        extrabones = []
        for subinfo in subinfos:
            subinfo.getEditBones(mainbones, extrabones)
        adds, hdadds, removes = self.createNewCollections(rig)

        activateObject(context, rig)
        nmerged = len(rig.data.DazMergedRigs)
        if nmerged == 0:
            pg = rig.data.DazMergedRigs.add()
            pg.name = "0"
            pg.s = rig.DazUrl
            pg.b = False
            nmerged = 1
        for idx,subinfo in enumerate(subinfos):
            if subinfo.conforms:
                subinfo.addEditBones(rig, idx+nmerged, T_CUSTOM)
        for bone in rig.data.bones:
            if bone.name in extrabones:
                bone["DazExtraBone"] = True
        self.reparentObjects(info, rig, adds, hdadds, removes)
        for idx,subinfo in enumerate(subinfos):
            if subinfo.conforms:
                subinfo.copyPose(context, rig)
                for ob,_ in subinfo.objects:
                    if ob.type == 'MESH':
                        self.changeArmatureModifier(ob, rig)
                        subinfo.renameVertexGroups(ob)
                self.reparentObjects(subinfo, rig, adds, hdadds, removes)
                pg = rig.data.DazMergedRigs.add()
                pg.name = str(idx+nmerged)
                pg.s = subinfo.rig.DazUrl
                pg.b = (subinfo.parbone is not None)
                subinfo.rig.parent = None
                deleteObjects(context, [subinfo.rig])
                for ob,_ in subinfo.objects:
                    if ob.type == 'MESH' and ob.name[-5:] == " Mesh":
                        ob.name = ob.name[:-5]
            else:
                subinfo.reParent(rig)
                self.reparentObjects(subinfo, subinfo.rig, adds, hdadds, removes)
            deleteObjects(context, subinfo.deletes)
        activateObject(context, rig)
        self.cleanVertexGroups(rig)
        setMode('OBJECT')
        if self.useConvertWidgets and info.foundControl:
            from .proxy import WidgetConverter
            ob = info.foundControl[0]
            print("Convert %s to widgets for %s" % (ob.name, rig.name))
            wc = WidgetConverter()
            wc.convertWidgets(context, rig, ob)
            enableRigNumLayer(rig, T_WIDGETS)


    def reparentObjects(self, info, rig, adds, hdadds, removes):
        from .driver import retargetDrivers
        if info.rig and info.rig != rig:
            retargetDrivers(rig, info.rig, rig)
            retargetDrivers(rig.data, info.rig, rig)

        for ob,data in info.objects:
            partype, parbone = data
            if partype in ['VERTEX', 'VERTEX_3', 'VERTEX_TRI']:
                continue
            wmat = ob.matrix_world.copy()
            ob.parent = rig
            ob.parent_type = partype
            if parbone is None:
                pass
            elif parbone in rig.data.bones.keys():
                ob.parent_bone = parbone
            else:
                ob.parent_bone = info.getBoneKey(parbone)
            setWorldMatrix(ob, wmat)
            self.addToCollections(ob, adds, hdadds, removes)
            if info.rig and info.rig != rig:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    retargetDrivers(ob.data.shape_keys, info.rig, rig)


    def createNewCollections(self, rig):
        adds = []
        hdadds = []
        removes = []
        if not self.createMeshCollection:
            return adds, hdadds, removes

        mcoll = hdcoll = None
        for coll in bpy.data.collections:
            if rig in coll.objects.values():
                if coll.name.endswith("HD"):
                    if hdcoll is None:
                        hdcoll = bpy.data.collections.new(name= rig.name + " Meshes_HD")
                        hdadds = [hdcoll]
                    coll.children.link(hdcoll)
                else:
                    if mcoll is None:
                        mcoll = bpy.data.collections.new(name= rig.name + " Meshes")
                        adds = [mcoll]
                    coll.children.link(mcoll)
                removes.append(coll)
        return adds, hdadds, removes


    def changeVertexGroupNames(self, ob, storage):
        for bname in storage.keys():
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = storage[bname].realname


    def addToCollections(self, ob, adds, hdadds, removes):
        if not self.createMeshCollection:
            return
        if ob.name.endswith("HD"):
            adders = hdadds
        else:
            adders = adds
        for grp in adders:
            if ob.name not in grp.objects:
                grp.objects.link(ob)
        for grp in removes:
            if ob.name in grp.objects:
                grp.objects.unlink(ob)


    def changeArmatureModifier(self, ob, rig):
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            mod.name = "Armature %s" % rig.name
            mod.object = rig
            return
        if len(ob.vertex_groups) == 0:
            print("Mesh with no vertex groups: %s" % ob.name)
        else:
            mod = ob.modifiers.new("Armature %s" % rig.name, "ARMATURE")
            mod.object = rig
            mod.use_deform_preserve_volume = True


    def cleanVertexGroups(self, rig):
        def unkey(bname):
            return bname.split(":",1)[-1]

        bones = dict([(unkey(bname),[]) for bname in rig.data.bones.keys()])
        for bone in rig.data.bones:
            bones[unkey(bone.name)].append(bone)
        for bname,dbones in bones.items():
            if len(dbones) == 1:
                bone = dbones[0]
                if bone.name != bname:
                    bone.name = bname

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

class DAZ_OT_CopyPose(DazOperator, IsArmature):
    bl_idname = "daz.copy_pose"
    bl_label = "Copy Pose"
    bl_description = "Copy pose from active rig to selected rigs"
    bl_options = {'UNDO'}

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
            print("Copy bones to %s:" % subrig.name)
            setWorldMatrix(subrig, rig.matrix_world)
            for pb in subrig.pose.bones:
                if pb.name in rig.pose.bones.keys():
                    snapBone(pb, gmats)

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):

    def applyLimitConstraints(rig):
        constraints = []
        for pb in rig.pose.bones:
            if pb.rotation_mode != 'QUATERNION':
                x,y,z = pb.rotation_euler
                for cns in pb.constraints:
                    if cns.type == 'LIMIT_ROTATION':
                        constraints.append((cns,cns.mute))
                        cns.mute = True
                        applyLimitComp("min_x", "max_x", "use_limit_x", 0, cns, pb)
                        applyLimitComp("min_y", "max_y", "use_limit_y", 1, cns, pb)
                        applyLimitComp("min_z", "max_z", "use_limit_z", 2, cns, pb)
        return constraints

    def applyLimitComp(min, max, use, idx, cns, pb):
        x = pb.rotation_euler[idx]
        if getattr(cns, use):
            xmax = getattr(cns, max)
            if x > xmax:
                x = pb.rotation_euler[idx] = xmax
            xmax -= x
            if abs(xmax) < 1e-4:
                xmax = 0
            setattr(cns, max, xmax)

            xmin = getattr(cns, min)
            if x < xmin:
                x = pb.rotation_euler[idx] = xmin
            xmin -= x
            if abs(xmin) < 1e-4:
                xmin = 0
            setattr(cns, min, xmin)

    def setRestRotation(rig):
        for pb in rig.pose.bones:
            if pb.rotation_mode == 'QUATERNION':
                rot = pb.rotation_quaternion.to_euler()
            else:
                rot = pb.rotation_euler
            if nonzero(rot):
                fvec = Vector((0,0,0))
                for idx in range(3):
                    idx2 = pb.DazAxes[idx]
                    fvec[idx] = pb.DazFlips[idx2] * rot[idx2]
                pb.DazRestRotation = Vector(pb.DazRestRotation) + fvec/D

    LS.forAnimation(None, rig)
    rigs = [rig] + subrigs
    applyAllObjectTransforms(rigs)
    for subrig in rigs:
        setRestRotation(subrig)
        for ob in getMeshChildren(subrig):
            if not ob.parent_type == 'BONE':
                setRestPose(ob, subrig, context)
        if not setActiveObject(context, subrig):
            continue
        constraints = applyLimitConstraints(subrig)
        setMode('POSE')
        bpy.ops.pose.armature_apply()
        for cns,mute in constraints:
            cns.mute = mute
    setActiveObject(context, rig)


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
            for ob in getMeshChildren(rig):
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
        print("Could not apply object transformations to meshes")
        return False


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if LS.fitFile:
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            mod.object = rig
    elif len(ob.vertex_groups) == 0:
        print("Mesh with no vertex groups: %s" % ob.name)
    else:
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
    DAZ_OT_CreateGraftGroups,
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

