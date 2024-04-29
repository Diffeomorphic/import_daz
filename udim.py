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

import bpy
import os
from .error import *
from .utils import *
from .fileutils import MultiFile, ImageFile
from .material import LocalTextureSaver
from .matedit import MaterialSelector
from .tree import getFromSocket, XSIZE, YSIZE, YSTEP

#----------------------------------------------------------
#   Tile Fixer
#----------------------------------------------------------

class TileFixer:
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
        cuvlayer = hum.data.uv_layers.active
        ucoord = []
        vcoord = []
        fmasked = [face.a for face in graft.data.DazMaskGroup]
        m = 0
        for fn,f in enumerate(hum.data.polygons):
            if fn in fmasked:
                for j,vn in enumerate(f.vertices):
                    uv = cuvlayer.data[m+j].uv
                    ucoord.append(uv[0])
                    vcoord.append(uv[1])
            m += len(f.vertices)
        tile,udim,vdim = self.getTile(ucoord, vcoord)
        print("Move %s UVs to tile %d" % (graft.name, tile))
        auvlayer = graft.data.uv_layers.active
        for data in auvlayer.data:
            uvs = data.uv
            uvs[0] += udim - int(uvs[0])
            uvs[1] += vdim - int(uvs[1])


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


def isShellNode(node):
    return (node.type == 'GROUP' and
            "Influence" in node.inputs.keys() and
            "UV" in node.inputs.keys())


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

#----------------------------------------------------------
#   Tiles From Graft
#----------------------------------------------------------

class DAZ_OT_TilesFromGraft(DazOperator, TileFixer, IsMesh):
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

class DAZ_OT_FixTextureTiles(DazOperator, LocalTextureSaver, TileFixer):
    bl_idname = "daz.fix_texture_tiles"
    bl_label = "Fix Texture Tiles"
    bl_description = "Copy textures to the right directory and correct tile numbers.\nTo fix incorrect Genesis 8.1 material names"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)

    def run(self, context):
        ob = context.object
        self.findMatTiles(ob)
        self.fixTextures(ob, ob.active_material.name)

#----------------------------------------------------------
#   Make UDIM materials
#----------------------------------------------------------

def getTargetMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]


class DAZ_OT_MakeUdimMaterials(DazPropsOperator, LocalTextureSaver, MaterialSelector, TileFixer):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    trgmat : EnumProperty(items=getTargetMaterial, name="Active")

    useSaveLocalTextures : BoolProperty(
        name = "Save Local Textures",
        description = "Save local textures if not already done",
        default = True)

    keepDirs = True

    useFixTextures : BoolProperty(
        name = "Fix Textures",
        description = (
            "Copy textures to the right directory and correct tile numbers.\n" +
            "For incorrect Genesis 8.1 material names,\n" +
            "or for textures without tile info"),
        default = True)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge materials and not only textures.\nThis may cause some information loss.\nIf not, Merge Materials can be called afterwards",
        default = False)

    useStackShells : BoolProperty(
        name = "Stack Shells",
        description = "Add shell groups to UDIM material",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useSaveLocalTextures")
        self.layout.prop(self, "useFixTextures")
        self.layout.prop(self, "useMergeMaterials")
        if self.useMergeMaterials:
            self.layout.prop(self, "useStackShells")
        self.layout.prop(self, "trgmat")
        self.layout.label(text="Materials To Merge")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def run(self, context):
        ob = context.object
        if not ob.DazLocalTextures:
            if self.useSaveLocalTextures:
                self.saveLocalTextures(context)
            else:
                raise DazError("Save local textures first")
        if self.useFixTextures:
            self.findMatTiles(ob)
            self.fixTextures(ob, self.trgmat)

        mats = []
        mnums = []
        actmat = None
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                mnums.append(mn)
                if actmat is None or mat.name == self.trgmat:
                    actmat = mat
                    amnum = mn
                    acttile = 1001 + mat.DazUDim

        if actmat is None:
            raise DazError("No materials selected")

        texnodes = {}
        hasmapping = False
        for mat in mats:
            nodes,hasmaps = self.getTextureNodes(mat)
            texnodes[mat.name] = nodes
            if mat == actmat:
                hasmapping = hasmaps

        if self.useMergeMaterials and self.useStackShells:
            shells0 = self.getShells(mats)
            actshells = self.getShells([actmat])
            shells = {}
            for tname,data in shells0.items():
                if tname not in actshells.keys():
                    shells[tname] = data

        for key,actnode in texnodes[actmat.name].items():
            actnode.image.source = "TILED"
            actnode.extension = "CLIP"
            if actnode.image:
                imgname = actnode.image.name
            else:
                imgname = actnode.name
            basename = "T_%s" % self.getBaseName(imgname, actmat.DazUDim)
            udims = {}
            for mat in mats:
                nodes = texnodes[mat.name]
                node = nodes.get(key)
                if node and node.image:
                    img = node.image
                    self.updateImage(img, basename, mat.DazUDim)
                    if mat.DazUDim not in udims.keys():
                        udims[mat.DazUDim] = mat.name
                    if mat == actmat:
                        img.name = self.makeImageName(basename, acttile, img)
                        node.label = basename
                        node.name = basename

            img = actnode.image
            if bpy.app.version >= (3, 1, 0):
                path2,ext2 = os.path.splitext(img.filepath)
                tile,base = getTileBase(path2)
                if base:
                    img.filepath = "%s_<UDIM>%s" % (base,ext2)
            tile0 = img.tiles[0]
            for udim,mname in udims.items():
                if udim == 0:
                    tile0.number = 1001
                    tile0.label = mname
                else:
                    img.tiles.new(tile_number=1001+udim, label=mname)

        for mat in mats:
            self.addSkipZeroUvs(mat)

        if self.useMergeMaterials:
            for f in ob.data.polygons:
                if f.material_index in mnums:
                    f.material_index = amnum

            mnums.reverse()
            for mn in mnums:
                if mn != amnum:
                    ob.data.materials.pop(index=mn)
            if self.useStackShells:
                self.addShells(actmat, shells)
        else:
            anodes = texnodes[actmat.name]
            for mat in mats:
                if mat != actmat:
                    nodes = texnodes[mat.name]
                    for key,node in nodes.items():
                        if key in anodes.keys():
                            actnode = anodes[key]
                            img = node.image = actnode.image
                            node.extension = "CLIP"
                            node.label = actnode.label
                            node.name = actnode.name


    def makeImageName(self, basename, tile, img):
        return "%s%s" % (basename, os.path.splitext(img.name)[1])


    def getTextureNodes(self, mat):
        def getChannel(node, links):
            for link in links:
                if link.from_node == node:
                    sname = link.to_socket.name
                    if link.to_node.type in ['MIX_RGB', 'MIX', 'MATH', 'GAMMA']:
                        return "%s:%s" % (getChannel(link.to_node, links), sname)
                    elif link.to_node.type == 'BSDF_PRINCIPLED':
                        return "PBR:%s" % sname
                    elif link.to_node.type == 'GROUP':
                        return "%s:%s" % (link.to_node.node_tree.name, sname)
                    else:
                        return "%s:%s" % (link.to_node.type, sname)
            return None

        texnodes = {}
        hasmaps = False
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                if node.image.source == "TILED":
                    raise DazError("Material %s is already an UDIM material" % mat.name)
                channel = getChannel(node, mat.node_tree.links)
                links = node.inputs["Vector"].links
                if links and links[0].from_node.type == 'MAPPING':
                    hasmaps = True
                elif channel in texnodes.keys():
                    print("Duplicate channel: %s" % channel)
                else:
                    texnodes[channel] = node
        return texnodes, hasmaps


    def getBaseName(self, path, udim):
        tile,base = getTileBase(os.path.splitext(path)[0])
        if tile == 1001+udim:
            return base
        return path


    def updateImage(self, img, basename, udim):
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        folder = os.path.dirname(src)
        fname,ext = os.path.splitext(bpy.path.basename(src))
        if fname[-6:] == '<UDIM>':
            src = os.path.join(folder, "%s%d%s" % (fname[:-6], 1001+udim, ext))
        trg = os.path.join(folder, "%s_%d%s" % (basename, 1001+udim, ext))
        self.changeImage(src, trg, img)


    def getShells(self, mats):
        from .tree import getFromNode
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


    def addShells(self, mat, shells):
        if not shells:
            return
        from .tree import findNodes, getFromSocket, XSIZE, YSIZE
        from .cycles import makeCyclesTree
        from .cgroup import SkipZeroUvGroup
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

#----------------------------------------------------------
#   Shift UVs
#----------------------------------------------------------

def getUVDims(tile):
    tile = tile - 1001
    vdim = tile//10
    udim = tile - 10*vdim
    return udim,vdim


def shiftUVs(mat, mn, ob, udim, vdim):
    ushift = udim - mat.DazUDim
    vshift = vdim - mat.DazVDim
    print(" Shift", mat.name, mn, ushift, vshift)
    if ushift == 0 and vshift == 0:
        return
    uvlayer = ob.data.uv_layers.active
    m = 0
    for fn,f in enumerate(ob.data.polygons):
        if f.material_index == mn:
            for n in range(len(f.vertices)):
                uv = uvlayer.data[m].uv
                uv[0] += ushift
                uv[1] += vshift
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
        from .material import addUdimTree
        ob = context.object
        udim,vdim = getUVDims(self.tile)
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                shiftUVs(mat, mn, ob, udim, vdim)
                addUdimTree(mat.node_tree, udim, vdim)
                mat.DazUDim = udim
                mat.DazVDim = vdim

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TilesFromGraft,
    DAZ_OT_FixTextureTiles,
    DAZ_OT_MakeUdimMaterials,
    DAZ_OT_SetUDims,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)



