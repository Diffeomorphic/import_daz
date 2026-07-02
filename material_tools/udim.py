# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import numpy as np
from ..error import *
from ..utils import *
from ..fileutils import MultiFile, ImageFile
from ..localtex import LocalTextureUser, normPath
from ..matsel import MaterialSelector
from ..tree import getFromSocket, XSIZE, YSIZE, YSTEP
from ..merge_uvs import TileFixer

#----------------------------------------------------------
#   Tiles From Graft
#----------------------------------------------------------

class DAZ_OT_TilesFromGraft(DazPropsOperator, TileFixer, IsMesh):
    bl_idname = "daz.tiles_from_geograft"
    bl_label = "Tiles From Geograft"
    bl_description = "Move geograft UV coordinates to same tile as body UVs"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        for graft in getSelectedMeshes(context):
            if graft != hum:
                self.udimsFromGraft(graft, hum)

#----------------------------------------------------------
#   Fix Texture Tiles
#----------------------------------------------------------

class DAZ_OT_FixTextureTiles(DazPropsOperator, LocalTextureUser, TileFixer):
    bl_idname = "daz.fix_texture_tiles"
    bl_label = "Fix Texture Tiles"
    bl_description = "Copy textures to the right directory and correct tile numbers.\nTo fix incorrect Genesis 8.1 material names"
    bl_options = {'UNDO'}

    def draw(self, context):
        LocalTextureUser.draw(self, context)
        TileFixer.draw(self, context)

    def run(self, context):
        ob = context.object
        self.initLocalImages()
        self.saveLocalTextures(context)
        mattiles = self.findMatTiles(ob)
        self.fixTextures(ob, ob.active_material.name, mattiles)

#----------------------------------------------------------
#   Add Genesis tiles
#----------------------------------------------------------

class GenesisTiles:
    def addGenesisTiles(self, ob):
        if dazRna(ob).DazUrl.lower() in [
                "/data/daz 3d/genesis/base/genesis.dsf#geometry",
                "/data/daz 3d/genesis 2/female/genesis2female.dsf#genesisfemale-1",
                "/data/daz 3d/genesis 2/male/genesis2male.dsf#genesis2male"]:
            uvlayer = ob.data.uv_layers.active
            if uvlayer is None:
                return
            nuvs = uv_length(uvlayer)
            array = np.zeros(2*nuvs, dtype=float)
            foreach_get_uv(uvlayer, array)
            uvmin = np.min(array)
            uvmax = np.max(array)
            if uvmin < 0 or uvmax > 1:
                print("%s already has tiles" % ob.name)
                return
            array = array.reshape((nuvs, 2))

            tiles = {
                "face" : 0,
                "nostrils" : 0,
                "lips" : 0,

                "head" : 1,
                "ears" : 1,
                "neck" : 1,
                "hips" : 1,
                "torso" : 1,
                "nipples" : 1,

                "shoulders" : 2,
                "toenails" : 2,
                "hands" : 2,
                "fingernails" : 2,
                "legs" : 2,
                "forearms" : 2,
                "feet" : 2,

                "gums" : 3,
                "teeth" : 3,
                "tongue" : 3,
                "innermouth" : 3,

                "irises" : 4,
                "lacrimals" : 4,
                "pupils" : 4,
                "cornea" : 4,
                "sclera" : 4,

                "eyereflection" : 5,
                "tear" : 5,

                "eyelashes" : 6,
            }

            nfaces = len(ob.data.polygons)
            for mn,mat in enumerate(ob.data.materials):
                if mat and mat.node_tree:
                    key = mat.name.lower().split("-", 1)[0]
                    words = key.split("_", 1)
                    if len(words) == 2 and words[0].isdigit():
                        tile = int(words[0]) - 1
                    else:
                        tile = tiles.get(key)
                    if tile is None:
                        print("Material has no tile: %s" % mat.name)
                    else:
                        loops = [f.loop_indices for f in ob.data.polygons if f.material_index == mn]
                        loops = flatten(loops)
                        array[loops,0] += tile
            foreach_set_uv(uvlayer, array.ravel())


class DAZ_OT_AddGenesisTiles(DazOperator, GenesisTiles):
    bl_idname = "daz.add_genesis_tiles"
    bl_label = "Add Genesis Tiles"
    bl_description = "Add UDIM tiles to Genesis and Genesis 2 characters"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        self.addGenesisTiles(ob)

#----------------------------------------------------------
#   Overwrite materials
#----------------------------------------------------------

class Overwriter:
    def getMaterials(self, ob, mattiles):
        mats = []
        mnums = []
        usedtiles = set()
        actmat = None
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                if umat.bool:
                    mnums.append(mn)
                if mn in mattiles.keys():
                    usedtiles.add(mattiles[mn]-1001)
                if actmat is None or mat.name == ob.active_material.name:
                    actmat = mat
                    actmnum = mn
                    acttile = 1001 + dazRna(mat).DazUDim
        if actmat is None:
            raise DazError("No materials selected")
        return actmat, actmnum, acttile, mats, mnums, usedtiles


    def getShells(self, mats):
        from ..tree import getFromNode
        from ..matsel import isShellNode
        nodes = {}
        for mat in mats:
            if mat.node_tree:
                n = len(mat.name)
                for node in mat.node_tree.nodes:
                    if isShellNode(node):
                        tree = node.node_tree
                        if tree.name[-n:] == mat.name:
                            shname = tree.name[:-n-1]
                            uvmap = getFromNode(node.inputs["UV"])
                            if uvmap:
                                nodes[shname] = (node, uvmap.uv_map)
        return nodes


    def getAllShells(self, actmat, mats):
        shells0 = self.getShells(mats)
        actshells = self.getShells([actmat])
        shells = {}
        for tname,data in shells0.items():
            if tname not in actshells.keys():
                shells[tname] = data
        return actshells, shells


    def overwrite(self, ob, actmnum, mnums):
        for f in ob.data.polygons:
            if f.material_index in mnums:
                f.material_index = actmnum
        mnums.reverse()
        for mn in mnums:
            if mn != actmnum:
                ob.data.materials.pop(index=mn)


    def addShells(self, mat, shells):
        if not shells:
            return
        from ..cycles import makeCyclesTree
        from ..cgroup import SkipZeroUvGroup
        from ..tree import findNodes
        ctree = makeCyclesTree(mat)
        for outp in findNodes(mat.node_tree, 'OUTPUT_MATERIAL'):
            x,y = outp.location
            outp.location = (x+2*XSIZE, y)
            ssocket = getFromSocket(outp.inputs["Surface"])
            dsocket = getFromSocket(outp.inputs["Displacement"])
            for tname,data in shells.items():
                template,uvname = data
                uvmap = ctree.addNode("ShaderNodeUVMap")
                uvmap.uv_map = uvname
                uvmap.label = uvname
                uvmap.hide = True
                uvmap.location = (x,y-6*YSTEP)
                skip = ctree.addGroup(SkipZeroUvGroup, "DAZ Skip Zero UVs")
                skip.location = (x,y)
                ctree.links.new(uvmap.outputs["UV"], skip.inputs["UV"])
                shell = ctree.addNode("ShaderNodeGroup")
                shell.location = (x+XSIZE, y)
                shell.node_tree = template.node_tree
                shell.label = template.label
                ctree.links.new(skip.outputs["Influence"], shell.inputs["Influence"])
                ctree.links.new(uvmap.outputs["UV"], shell.inputs["UV"])
                if ssocket:
                    ctree.links.new(ssocket, shell.inputs["BSDF"])
                if dsocket:
                    ctree.links.new(dsocket, shell.inputs["Displacement"])
                ssocket = shell.outputs["BSDF"]
                dsocket = shell.outputs["Displacement"]
                y -= YSIZE
            if ssocket:
               ctree.links.new(ssocket, outp.inputs["Surface"])
            if dsocket:
                ctree.links.new(dsocket, outp.inputs["Displacement"])


class DAZ_OT_OverwriteMaterials(DazPropsOperator, MaterialSelector, Overwriter):
    bl_idname = "daz.overwrite_materials"
    bl_label = "Overwrite Materials"
    bl_description = "Overwrite selected materials with the active material"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawActive(context)
        MaterialSelector.draw(self, context)

    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return DazPropsOperator.invoke(self, context, event)

    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)

    def run(self, context):
        ob = context.object
        actmat, actmnum, acttile, mats, mnums, usedtiles = self.getMaterials(ob, {})
        actshells, shells = self.getAllShells(actmat, mats)
        self.overwrite(ob, actmnum, mnums)
        self.addShells(actmat, shells)

#----------------------------------------------------------
#   Make UDIM materials
#----------------------------------------------------------

class DAZ_OT_MakeUdimTextures(DazPropsOperator, LocalTextureUser, MaterialSelector, TileFixer, GenesisTiles, Overwriter):
    bl_idname = "daz.make_udim_textures"
    bl_label = "Make UDIM Textures"
    bl_description = "Combine textures of selected mesh into tiled textures"
    bl_options = {'UNDO'}

    subdir = "/textures/UDIM"

    useFixTextures = True
    useGenesisTiles = True
    useOverwrite = False

    useGuessMissing : BoolProperty(
        name = "Guess Missing Textures",
        description = "Search for UDIM textures that almost match location in node tree",
        default = True)

    imageSize : IntProperty(
        name = "Image Size",
        description = "Size of generated images",
        min = 1, max = 8196,
        default = 64)

    def draw(self, context):
        self.drawActive(context)
        LocalTextureUser.draw(self, context)
        self.layout.prop(self, "imageSize")
        self.layout.prop(self, "useGuessMissing")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def run(self, context):
        self.initLocalImages()
        ob = context.object
        if ob.active_material is None:
            raise DazError("No active material")
        if self.useGenesisTiles:
            self.addGenesisTiles(ob)
        self.saveLocalTextures(context)
        mattiles = self.findMatTiles(ob)
        if self.useFixTextures:
            self.fixTextures(ob, ob.active_material.name, mattiles)

        actmat, actmnum, acttile, mats, mnums, usedtiles = self.getMaterials(ob, mattiles)

        texnodes = {}
        hasmapping = False
        for mat in mats:
            nodes,hasmaps = self.getTextureNodes(mat)
            texnodes[mat.name] = nodes
            if mat == actmat:
                hasmapping = hasmaps

        if self.useOverwrite:
            actshells, shells = self.getAllShells(actmat, mats)

        basenames = {}
        keytiles = {}
        origpaths = {}
        self.updatedImages = {}
        acttile = dazRna(actmat).DazUDim
        tiledImages = set()
        for key,actnode in texnodes[actmat.name].items():
            if key is None:
                continue
            img = actnode.image
            filepath = str(img.filepath)
            imgname = os.path.splitext(img.name)[0]
            tile,basename = self.getTileBase(imgname)
            #basename = self.getBaseName(imgname, dazRna(mat).DazUDim)
            if not basename.startswith("T_"):
                basename = "T_%s" % basename
            img = self.updateImage(img, basename, acttile)
            width, height = img.size
            actimg = bpy.data.images.new(basename, width, height)
            actimg.source = "TILED"
            actimg.filepath_raw = filepath
            actimg.colorspace_settings.name = img.colorspace_settings.name
            tiledImages.add(actimg)
            actnode.image = actimg
            actnode.extension = "CLIP"
            udims = {}
            for mat in mats:
                nodes = texnodes[mat.name]
                node = nodes.get(key)
                found = True
                if node is None and self.useGuessMissing:
                    if key.endswith((":A", ":B")):
                        node = nodes.get(key[:-2])
                        found = False
                        if node and node.image:
                            basenames[node.image.filepath] = basename
                if node and node.image:
                    img = node.image
                    tile = dazRna(mat).DazUDim
                    if found:
                        self.updateImage(img, basename, tile)
                    if tile not in udims.keys():
                        udims[tile] = mat.name
                    if mat == actmat:
                        img.name = self.makeImageName(basename, acttile, img)
                        node.label = basename
                        node.name = basename

            img = actnode.image
            keytiles[key] = list(udims.keys())
            if bpy.app.version >= (3, 1, 0):
                path2,ext2 = os.path.splitext(img.filepath)
                tile,base = self.getTileBase(path2)
                if base:
                    udimpath = "%s_<UDIM>%s" % (base,ext2)
                    origpaths[udimpath] = str(img.filepath)
                    img.filepath = udimpath
            tile0 = img.tiles[0]
            for udim,mname in udims.items():
                if udim == 0:
                    tile0.number = 1001
                    tile0.label = mname
                else:
                    img.tiles.new(tile_number=1001+udim, label=mname)

        if len(usedtiles) > 1:
            for key,tiles in keytiles.items():
                node = texnodes[actmat.name][key]
                if len(tiles) == 1 and tiles[0] == 0:
                    img = node.image
                    udimpath = origpaths.get(img.filepath, img.filepath)
                    origpath = self.updatedImages.get(udimpath, udimpath)
                    self.changeImage(udimpath, origpath, img)
                    img.source = "FILE"
                    node.extension = "CLIP"
                    img.filepath = origpath
                    img.name = node.label = node.label[2:]
                    print("Texture %s only on tile 1001" % origpath)
                elif len(tiles) < len(usedtiles):
                    for tile in usedtiles:
                        if tile not in tiles:
                            self.addImage(node.image, tile, key)

        for mat in mats:
            self.addSkipZeroUvs(mat)

        if self.useOverwrite:
            self.overwrite(ob, actmnum, mnums)
            self.addShells(actmat, shells)
        else:
            actnodes = texnodes[actmat.name]
            for mat in mats:
                if mat != actmat:
                    nodes = texnodes[mat.name]
                    for key,node in nodes.items():
                        actnode = actnodes.get(key)
                        if actnode is None and node.image and self.useGuessMissing:
                            actnode = self.findBestMatch(key, node.image, mat, actnodes, basenames)
                        if actnode:
                            img = node.image = actnode.image
                            node.extension = "CLIP"
                            node.label = actnode.label
                            node.name = actnode.name
        self.printLocalImages()
        useSaveGenerated = self.useSaveGenerated
        self.useSaveGenerated = True
        self.saveLocalImages()
        for img in tiledImages:
            img.reload()
        if not useSaveGenerated:
            self.useSaveGenerated = False
            self.saveLocalImages()
            for img in tiledImages:
                img.pack()
            self.deleteCopiedImages()
        dazRna(ob.data).DazTexLevel = 3


    def makeImageName(self, basename, tile, img):
        return "%s%s" % (basename, os.path.splitext(img.name)[1])


    def addImage(self, actimg, tile, key):
        from ..material import setColorSpaceNone
        #basename = self.getBaseName(actimg.name, tile)
        _,basename = self.getTileBase(actimg.name)
        if key.endswith(("Factor:Value", "Fac")):
            color = (1,1,1,1)
        elif key.startswith("NORMAL_MAP:Color"):
            color = (0.5, 0.5, 1.0, 1)
        elif key.endswith(("Color:A", "Color:B", "Color")):
            color = (1,1,1,1)
        elif key.startswith(("BUMP:Height")):
            color = (0.5, 0.5, 0.5, 1)
        elif key.startswith(("PBR:Base Color", "DAZ Dual Lobe:IOR")):
            color = (1,1,1,1)
        elif "Roughness" in key:
            color = (1,1,1,1)
        else:
            print("Unknown key when adding UDIM image:", key)
            color = (0,0,0,1)

        imgname = self.makeImageName(basename, tile, actimg)
        src,trg = self.getTargetPath(actimg, basename, tile)
        img = bpy.data.images.new(imgname, self.imageSize, self.imageSize)
        img.generated_color = color
        setColorSpaceNone(img)
        img.filepath_raw = trg
        self.saveImage(img, True)
        udim = 1001+tile
        actimg.tiles.new(tile_number=udim, label=str(udim))


    def getTextureNodes(self, mat):
        def getChannel(node, links, grpname):
            for link in links:
                if link.from_node == node:
                    sname = link.to_socket.name
                    tonode = link.to_node
                    if tonode.type in ['MIX_RGB', 'MIX', 'MATH', 'GAMMA']:
                        return "%s:%s" % (getChannel(tonode, links, grpname), sname)
                    elif (tonode.type == 'GROUP' and
                          tonode.name in ["DAZ Color Effect"]):
                        return "%s:%s" % (getChannel(tonode, links, grpname), sname)
                    elif tonode.type == 'BSDF_PRINCIPLED':
                        return "PBR:%s" % sname
                    elif tonode.type == 'GROUP' and tonode.node_tree.name.startswith("DAZ "):
                        return "%s:%s" % (tonode.node_tree.name, sname)
                    elif tonode.type == 'GROUP':
                        return "%s:%s" % (tonode.node_tree.name, sname)
                    elif tonode.type == 'GROUP_OUTPUT' and grpname:
                        return "%s:%s" % (grpname, sname)
                    else:
                        return "%s:%s" % (tonode.type, sname)
            return None

        def addTexNodes(tree, mat, texnodes, grpname):
            hasmaps = False
            for node in tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    if node.image.source == "TILED":
                        raise DazError("Material %s is already an UDIM material" % mat.name)
                    channel = getChannel(node, tree.links, grpname)
                    links = node.inputs["Vector"].links
                    if links and links[0].from_node.type == 'MAPPING':
                        hasmaps = True
                    elif channel in texnodes.keys():
                        print("Duplicate channel: %s" % channel)
                    else:
                        texnodes[channel] = node
                elif (node.type == 'GROUP' and
                      not node.name.startswith("DAZ ") and
                      node.node_tree.name.startswith(("LIE", "DIMG"))):
                        channel = getChannel(node, tree.links, grpname)
                        hasgrp = addTexNodes(node.node_tree, mat, texnodes, channel)
                        hasmaps = (hasmaps or hasgrp)
            return hasmaps

        texnodes = {}
        hasmaps = addTexNodes(mat.node_tree, mat, texnodes, None)
        return texnodes, hasmaps


    def getTileBase(self, path):
        from ..merge_uvs import getTileBase
        return getTileBase(os.path.splitext(path)[0])


    def updateImage(self, img, basename, udim):
        src,trg = self.getTargetPath(img, basename, udim)
        trg = self.getLocalPath(trg)
        self.updatedImages[trg] = src
        return self.changeImage(src, trg, img, strict=False)


    def getTargetPath(self, img, basename, udim):
        src = normPath(img.filepath)
        folder = os.path.dirname(src)
        fname,ext = os.path.splitext(bpy.path.basename(src))
        if fname[-6:] == '<UDIM>':
            src = os.path.join(folder, "%s%d%s" % (fname[:-6], 1001+udim, ext))
        trg = os.path.join(folder, "%s_%d%s" % (basename, 1001+udim, ext))
        return src, trg


    def findBestMatch(self, key, img, mat, actnodes, basenames):
        for ext in ["A", "B"]:
            actnode = actnodes.get("%s:%s" % (key, ext))
            if actnode and actnode.image:
                folder1 = os.path.dirname(img.filepath)
                folder2 = os.path.dirname(actnode.image.filepath)
                if folder1 == folder2:
                    basename = basenames.get(img.filepath)
                    if basename:
                        self.updateImage(img, basename, dazRna(mat).DazUDim)
                    return actnode
        lpath = img.filepath.lower()
        udim = str(1001 + dazRna(mat).DazUDim)
        for actnode in actnodes.values():
            actimg = actnode.image
            if actimg:
                actpath = actimg.filepath.replace("<UDIM>", udim).lower()
                if actpath == lpath:
                    return actnode
        return None

#----------------------------------------------------------
#   Shift UVs
#----------------------------------------------------------

def getUVDims(tile):
    tile = tile - 1001
    vdim = tile//10
    udim = tile - 10*vdim
    return udim,vdim


def shiftUVs(mat, mn, ob, udim, vdim):
    uvshift = Vector((udim - dazRna(mat).DazUDim, vdim - dazRna(mat).DazVDim))
    print(" Shift", mat.name, mn, uvshift)
    if uvshift.length == 0:
        return
    uvlayer = ob.data.uv_layers.active
    m = 0
    for fn,f in enumerate(ob.data.polygons):
        if f.material_index == mn:
            for n in range(len(f.vertices)):
                uv = get_uv(uvlayer, m)
                uv += uvshift
                m += 1
        else:
            m += len(f.vertices)

#----------------------------------------------------------
#   Set Udims to given tile
#----------------------------------------------------------

class DAZ_OT_SetUDims(DazPropsOperator, MaterialSelector):
    bl_idname = "daz.set_udims"
    bl_label = "Set UDIM Tile"
    bl_description = "Move all UV coordinates of selected materials to specified UV tile"
    bl_options = {'UNDO'}

    tile : IntProperty(name="Tile", min=1001, max=1100, default=1001)

    def draw(self, context):
        self.layout.prop(self, "tile")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return False


    def run(self, context):
        from ..material import addUdimTree
        ob = context.object
        udim,vdim = getUVDims(self.tile)
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                shiftUVs(mat, mn, ob, udim, vdim)
                addUdimTree(mat.node_tree, udim, vdim)
                dazRna(mat).DazUDim = udim
                dazRna(mat).DazVDim = vdim

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TilesFromGraft,
    DAZ_OT_FixTextureTiles,
    DAZ_OT_AddGenesisTiles,
    DAZ_OT_MakeUdimTextures,
    DAZ_OT_OverwriteMaterials,
    DAZ_OT_SetUDims,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)



