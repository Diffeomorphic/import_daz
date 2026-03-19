# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .utils import *
from .error import *
from .driver import DriverUser
from .merge_uvs import UVLayerMergerOptions, UVLayerMerger, TileFixer

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

    useBakeGrafts: BoolProperty(
        name = "Bake Grafts",
        description = "Add a bake node to the geometry node tree.\nThis must be baked in rest pose before posing",
        default = False)


class DAZ_OT_MergeGeografts(DazPropsOperator, MergeGeograftOptions, UVLayerMerger, TileFixer, DriverUser, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    def draw(self, context):
        if bpy.app.version >= (3,4,0):
            self.layout.prop(self, "useGeoNodes")
        if self.useGeoNodes and bpy.app.version >= (4,4,0):
            self.layout.prop(self, "useBakeGrafts")
        else:
            self.layout.prop(self, "keepOriginal")
        self.layout.prop(self, "useSubDDisplacement")
        box = self.layout.box()
        box.label(text="UDIM Materials")
        box.prop(self, "useFixTiles")
        box.prop(self, "useLastUdimTile")
        self.drawUVLayer(box)


    def run(self, context):
        from .apply import safeTransformApply
        from .finger import isGenesis
        self.initTmp()
        safeTransformApply()
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
                prio[nverts] = (not (not dazRna(ob.data).DazGraftGroup))

        grafts = dict([(vert_count, []) for vert_count in humans.keys()])
        ngrafts = 0
        misses = []
        # Store geograft objects in grafts dictionary--lookup by number of vertices
        for ob in selected_meshes:
            if dazRna(ob.data).DazGraftGroup:
                nhumverts = dazRna(ob.data).DazVertexCount
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
        self.outlineMat = None
        self.removeOutlineMat(hum)
        for gn,graft in enumerate(grafts):
            graft.active_shape_key_index = 0
            graft.show_only_shape_key = True
            self.renameUvLayers(graft)
            self.storeUvName(graft)
            self.removeOutlineMat(graft)
            if self.useFixTiles:
                self.udimsFromGraft(graft, hum)
            self.copyBodyPart(graft, hum)
            self.fixFaceGroups(gn+1, graft, hum)
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
        from .geometry import getActiveUvLayer
        cuvlayer = getActiveUvLayer(hum)
        drivers = {}
        cvgrps = dict([(vgrp.index, vgrp.name) for vgrp in hum.vertex_groups])
        for graft in grafts:
            activateObject(context, graft)
            self.moveGraftVerts(graft, hum, cvgrps)
            self.getShapekeyDrivers(graft, drivers)
            if cuvlayer:
                self.replaceTexco(graft, cuvlayer.name, self.useGeoNodes)

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
            for face in dazRna(graft.data).DazMaskGroup:
                self.fmasked[face.a] = True

        # If hum is itself a geograft, make sure to keep tbe boundary
        if dazRna(hum.data).DazGraftGroup:
            body_pair_a_verts = [pair.a for pair in dazRna(hum.data).DazGraftGroup]
        else:
            body_pair_a_verts = []

        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')

        # Select body verts to delete
        self.vdeleted = dict([(vn,False) for vn in range(nverts)])
        self.hummasks = {}
        for graft in grafts:
            hummask = self.hummasks[graft.name] = dict([(vn, False) for vn in range(nverts)])
            graft_pair_b_verts = [pair.b for pair in dazRna(graft.data).DazGraftGroup]
            for face in dazRna(graft.data).DazMaskGroup:
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
        if dazRna(hum.data).DazGraftGroup:
            verts = hum.data.vertices
            self.locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in dazRna(hum.data).DazGraftGroup])

        # Delete the masked verts
        self.deleteSelectedVerts()

        # Select all grafts
        for graft in grafts:
            graft.select_set(True)
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')

        # Select verts on common boundary
        self.humedges = {}
        self.graftedges = {}
        for graft in grafts:
            ngraftverts = len(graft.data.vertices)
            graftedge = self.graftedges[graft.name] = dict([(vn,False) for vn in range(ngraftverts)])
            humedge = self.humedges[graft.name] = dict([(vn,False) for vn in range(nverts)])
            pg = dazRna(hum.data).DazMergedGeografts.add()
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

            for pair in dazRna(graft.data).DazGraftGroup:
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
                try:
                    attribute.data.foreach_set("value", list(paired_vert_list.values()))
                except (TypeError, RuntimeError):
                    print("Attribute mismatch:", graft.name, attribute.name)

        # Also select hum graft group. These will not be removed.
        if dazRna(hum.data).DazGraftGroup:
            for pair in dazRna(hum.data).DazGraftGroup:
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
        self.restoreOutlineMat(hum)
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


    def fixFaceGroups(self, gn, graft, hum):
        if BLENDER3 or "DazVertex" not in graft.data.attributes.keys():
            return

        def fixFaceGroup(aname, graft, hum):
            pgs = getattr(dazRna(hum.data), aname)
            n0 = len(pgs)
            graftpgs = getattr(dazRna(graft.data), aname)
            for gname in graftpgs.keys():
                pg = pgs.add()
                pg.name = gname
            attr = graft.data.attributes.get(aname)
            if attr:
                for data in attr.data.values():
                    data.value += n0

        fixFaceGroup("DazPolygonGroup", graft, hum)
        fixFaceGroup("DazMaterialGroup", graft, hum)
        fixFaceGroup("DazCondGraftGroup", graft, hum)
        if "DazGraft" in graft.data.attributes.keys():
            gattr = graft.data.attributes.get("DazGraft")
            for gdata in gattr.data.values():
                gdata.value = gn
            pgs = dazRna(hum.data).DazGraftData
            gpg = dazRna(graft.data).DazGraftData[0]
            pg = pgs.add()
            pg.name = gpg.name
            pg.s = gpg.s
            pg.i = gpg.i


    def removeOutlineMat(self, ob):
        mat = ob.data.materials[-1]
        if mat and mat.name == "DAZ Toon Outline":
            ob.data.materials.pop()
            if self.outlineMat is None:
                self.outlineMat = mat


    def restoreOutlineMat(self, hum):
        if self.outlineMat:
            hum.data.materials.append(self.outlineMat)


    def mergeDestructively(self, context, hum, grafts, body_pair_a_verts):
        # Join meshes
        names = [graft.name for graft in grafts]
        print("Merge %s to %s" % (names, hum.name))
        threshold = 0.001*GS.scale
        bpy.ops.object.join()

        # Create graft vertex group
        selected = [v.index for v in hum.data.vertices if v.select]
        vgrp = hum.vertex_groups.new(name="Graft")
        for vn in selected:
            vgrp.add([vn], 1.0, 'REPLACE')

        # Remove doubles
        setMode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        vglocs = [[(v.index,v.co.copy()) for g in v.groups if g.group == vgrp.index]
                    for v in hum.data.vertices]
        sellocs = dict(flatten(vglocs))

        mod = getModifier(hum, 'MULTIRES')
        if mod:
            smod = hum.modifiers.new("Smooth Graft", 'SMOOTH')
            smod.factor = 1.0
            smod.iterations = 10
            smod.vertex_group = vgrp.name

        # Update hum graft group
        if dazRna(hum.data).DazGraftGroup and sellocs:
            for pair in dazRna(hum.data).DazGraftGroup:
                x = self.locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in sellocs.items()]
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

        from .geometry import getActiveUvLayer
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

        cuvlayer = getActiveUvLayer(hum)
        if cuvlayer:
            self.replaceTexco(hum, cuvlayer.name, True)

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
        graftgrp.addGrafts(grafts, hum.name, self.useBakeGrafts)

        # Create the modifier
        from .store import addModifierFirst
        mod = addModifierFirst(hum, groupname, 'NODES', second=(not self.useBakeGrafts))
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
        from .merge_rigs import retargetMeshDrivers
        for prop,value in influs.items():
            if prop not in hum.keys():
                hum[prop] = value
                setOverridable(hum, prop)
                dazRna(hum).DazVisibilityDrivers = True
        for graft in grafts:
            retargetMeshDrivers(grafts, graft, hum)


    def replaceTexco(self, ob, cuvname, force):
        from .geometry import getActiveUvLayer
        from .tree import XSIZE
        uvlayer = getActiveUvLayer(ob)
        if uvlayer is None:
            return
        uvname = uvlayer.name
        if (self.useMergeUvs or uvname == cuvname) and not force:
            return
        for mat in ob.data.materials:
            if mat is None:
                continue
            texco = None
            tree = mat.node_tree
            x,y = (0,0)
            for node in tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
                    x,y = texco.location
                    break
                elif node.type == 'TEX_IMAGE':
                    x1,y1 = node.location
                    if x1 <= x:
                        x = x1-XSIZE
            uvmap = tree.nodes.new(type="ShaderNodeUVMap")
            uvmap.uv_map = uvname
            uvmap.label = uvname
            uvmap.hide = True
            uvmap.location = (x,y)
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
        apgs = dazRna(graft.data).DazBodyPart
        cpgs = dazRna(hum.data).DazBodyPart
        for sname,apg in apgs.items():
            if sname not in cpgs.keys():
                cpg = cpgs.add()
                cpg.name = sname
                cpg.s = apg.s


    def moveGraftVerts(self, graft, hum, cvgrps):
        from .modifier import getBasisShape
        from .transfer import addShapekey
        cvgroups = dict([(vgrp.index, vgrp.name) for vgrp in hum.vertex_groups])
        averts = graft.data.vertices
        cverts = hum.data.vertices
        for pair in dazRna(graft.data).DazGraftGroup:
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
            abasis,askeys,new = getBasisShape(graft)
            for cskey in cskeys.key_blocks:
                if cskey.name not in askeys.key_blocks.keys():
                    addShapekey(graft, cskey)

        # Move shapekey positions
        askeys = graft.data.shape_keys
        if askeys:
            for askey in askeys.key_blocks:
                if cskeys and askey.name in cskeys.key_blocks.keys():
                    cdata = cskeys.key_blocks[askey.name].data
                else:
                    cdata = cverts
                for pair in dazRna(graft.data).DazGraftGroup:
                    askey.data[pair.a].co = cdata[pair.b].co

        # Copy vertex groups
        for pair in dazRna(graft.data).DazGraftGroup:
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


#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_MergeGeografts)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_MergeGeografts)

