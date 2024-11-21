# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *
from .tree import getFromSocket, XSIZE, YSIZE, YSTEP

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
        from .geometry import getActiveUvLayer
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
        from .geometry import getActiveUvLayer
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

#----------------------------------------------------------
#   Tile Fixer
#----------------------------------------------------------

class TileFixer:
    useLastUdimTile : BoolProperty(
        name = "Last UDIM Tile",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useLastUdimTile")


    def findMatTiles(self, ob):
        ucoords = dict([(mn,[]) for mn in range(len(ob.data.materials))])
        vcoords = dict([(mn,[]) for mn in range(len(ob.data.materials))])
        uvlayer = ob.data.uv_layers.active
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            mn = f.material_index
            ucoord = ucoords[mn]
            vcoord = vcoords[mn]
            for n in range(len(f.vertices)):
                uv = uvlayer.data[m].uv
                ucoord.append(uv[0])
                vcoord.append(uv[1])
                m += 1
        self.mattiles = {}
        for mn,mat in enumerate(ob.data.materials):
            if mat:
                tile,udim,vdim = self.getTile(ucoords[mn], vcoords[mn])
                mat.DazUDim = udim
                mat.DazVDim = vdim
                self.mattiles[mn] = tile
        print("Tile assignment:")
        for mn,mat in enumerate(ob.data.materials):
            print("  %s: %d" % (mat.name, self.mattiles[mn]))


    def getTile(self, ucoord, vcoord):
        umax = max(ucoord)
        umin = min(ucoord)
        vmax = max(vcoord)
        vmin = min(vcoord)
        udim = math.floor((umax+umin)/2)
        vdim = math.floor((vmax+vmin)/2)
        tile = 1001 + udim + 10*vdim
        return tile, udim, vdim


    def fixTextures(self, ob, matname):
        def getFolder(ob, matname):
            for mat in ob.data.materials:
                if mat.name == matname:
                    if mat.node_tree:
                        for node in mat.node_tree.nodes:
                            if node.type == 'TEX_IMAGE' and node.image:
                                path = bpy.path.abspath(node.image.filepath)
                                return os.path.dirname(path)
            return None

        folder = getFolder(ob, matname)
        images = {}
        for mn,mat in enumerate(ob.data.materials):
            tree = mat.node_tree
            if tree is None:
                continue
            mattile = self.mattiles.get(mn)
            if mattile is None:
                continue
            inform = True
            for node in tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    path = bpy.path.abspath(node.image.filepath)
                    file = os.path.basename(path)
                    fname,ext = os.path.splitext(file)
                    tile,base = getTileBase(node.image.name)
                    if not base:
                        continue
                    if tile != mattile:
                        if inform:
                            print("Fix %s textures for tile %d" % (mat.name, mattile))
                            inform = False
                        newpath = os.path.join(folder, "%s_%d%s" % (base, mattile, ext))
                        src = bpy.path.abspath(path)
                        if src in images.keys():
                            img = images[src]
                        else:
                            trg = bpy.path.abspath(newpath)
                            img = self.changeImage(src, trg, None)
                            img.colorspace_settings.name = node.image.colorspace_settings.name
                            images[src] = img
                        node.image = img
                        node.label = "%s_%d" % (base, mattile)


    def udimsFromGraft(self, graft, hum):
        def getUVcoords(mn):
            m = 0
            ucoord = []
            vcoord = []
            for fn,f in enumerate(hum.data.polygons):
                if fn in fmasked and f.material_index == mn:
                    for j,vn in enumerate(f.vertices):
                        uv = cuvlayer.data[m+j].uv
                        ucoord.append(uv[0])
                        vcoord.append(uv[1])
                m += len(f.vertices)
            return ucoord, vcoord

        cuvlayer = hum.data.uv_layers.active
        fmasked = [face.a for face in graft.data.DazMaskGroup]
        tiles = {}
        udims = {}
        vdims = {}
        for mn,mat in enumerate(hum.data.materials):
            if mat:
                ucoord,vcoord = getUVcoords(mn)
                if ucoord:
                    mname = stripName(mat.name)
                    tiles[mname], udims[mname], vdims[mname] = self.getTile(ucoord, vcoord)

        if len(tiles) == 0:
            print("No UVs to shift")
            return
        if self.useLastUdimTile:
            ucoord = [data.uv[0] for data in cuvlayer.data]
            vcoord = [data.uv[1] for data in cuvlayer.data]
            tile, udefault, vdefault = self.getTile([max(ucoord)-0.01], [max(vcoord)-0.01])
            tiledefault = tile+1
            udefault += 1
        else:
            tiledefault = list(tiles.values())[0]
            udefault = list(udims.values())[0]
            vdefault = list(vdims.values())[0]
        auvlayer = graft.data.uv_layers.active

        def moveUVs(mn, udim, vdim):
            m = 0
            for f in graft.data.polygons:
                if f.material_index == mn:
                    for j in range(len(f.vertices)):
                        uvs = auvlayer.data[m+j].uv
                        uvs[0] += udim - int(uvs[0])
                        uvs[1] += vdim - int(uvs[1])
                m += len(f.vertices)

        for mn,mat in enumerate(graft.data.materials):
            if mat:
                mname = stripName(mat.name)
                if mname in tiles.keys() and not self.useLastUdimTile:
                    tile = tiles[mname]
                    udim = udims[mname]
                    vdim = vdims[mname]
                else:
                    tile = tiledefault
                    udim = udefault
                    vdim = vdefault
            print("Move %s:%s UVs to tile %d" % (graft.name, mname, tile))
            moveUVs(mn, udim, vdim)
        return


    def getKnownTiles(self, ob):
        from .fileutils import DF
        char = ob.DazMesh.split("-",1)[0].lower()
        if char == "genesis8":
            for mat in ob.data.materials:
                if mat.name.startswith("Body"):
                    char = "genesis81"
                    break
                elif mat.name.startswith("Torso"):
                    break
        entry = DF.loadEntry(char, "tiles", strict=False)
        if entry:
            return entry["tiles"]
        else:
            return {}


    def addSkipZeroUvs(self, mat):
        from .cycles import makeCyclesTree
        from .cgroup import SkipZeroUvGroup
        from .matsel import isShellNode
        ctree = makeCyclesTree(mat)
        for node in list(ctree.nodes):
            if isShellNode(node):
                skip = ctree.addGroup(SkipZeroUvGroup, "DAZ Skip Zero UVs")
                x,y = node.location
                skip.location = (x-XSIZE, y+YSIZE)
                socket = getFromSocket(node.inputs["UV"])
                if socket:
                    ctree.links.new(socket, skip.inputs["UV"])
                ctree.links.new(skip.outputs["Influence"], node.inputs["Influence"])


def getTileBase(string):
    def getTileBaseFromList(words):
        words.reverse()
        for n,word in enumerate(words[0:2]):
            if len(word) == 4 and word.isdigit():
                tile = int(word)
                if tile >= 1001 and tile <= 1100:
                    rest = words[0:n] + words[n+1:]
                    rest.reverse()
                    return tile, "_".join(rest)
        return None, ""

    words = string.split("_")
    tile,base = getTileBaseFromList(words)
    if tile:
        return tile, base
    words = string.split("-")
    tile,base = getTileBaseFromList(words)
    if tile:
        return tile, base
    return None, string

#-------------------------------------------------------------
#   Replace node names
#-------------------------------------------------------------

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

#-------------------------------------------------------------
#   Merge UV layers
#-------------------------------------------------------------

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
