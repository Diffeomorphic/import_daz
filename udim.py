# Copyright (c) 2016-2022, Thomas Larsson
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
from .matedit import MaterialSelector

#----------------------------------------------------------
#   Fix texture tiles
#----------------------------------------------------------

class TextureTileFixer:
    def findMatTiles(self, ob):
        ucoords = dict([(mn,[]) for mn in range(len(ob.data.materials))])
        vcoords = dict([(mn,[]) for mn in range(len(ob.data.materials))])
        uvloop = ob.data.uv_layers.active
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            mn = f.material_index
            ucoord = ucoords[mn]
            vcoord = vcoords[mn]
            for n in range(len(f.vertices)):
                uv = uvloop.data[m].uv
                ucoord.append(uv[0])
                vcoord.append(uv[1])
                m += 1
        self.mattiles = {}
        for mn,mat in enumerate(ob.data.materials):
            ucoord = ucoords[mn]
            vcoord = vcoords[mn]
            if ucoord and vcoord:
                umax = max(ucoord)
                umin = min(ucoord)
                vmax = max(vcoord)
                vmin = min(vcoord)
                udim = math.floor((umax+umin)/2)
                vdim = math.floor((vmax+vmin)/2)
                tile = 1001 + udim + 10*vdim
                mat.DazUDim = udim
                mat.DazVDim = vdim
                self.mattiles[mn] = tile
        print("Tile assignment:")
        for mn,mat in enumerate(ob.data.materials):
            print("  %s: %d" % (mat.name, self.mattiles[mn]))


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

        from shutil import copyfile
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
                    if len(fname) > 5 and fname[-4:].isdigit():
                        tile = int(fname[-4:])
                    else:
                        continue
                    if tile != mattile:
                        if inform:
                            print("Fix %s textures for tile %d" % (mat.name, mattile))
                            inform = False
                        newpath = os.path.join(folder, "%s%d%s" % (fname[:-4], mattile, ext))
                        src = bpy.path.abspath(path)
                        if src in images.keys():
                            img = images[src]
                        else:
                            trg = bpy.path.abspath(newpath)
                            print("Copy %s\n => %s" % (src, trg))
                            copyfile(src, trg)
                            img = bpy.data.images.load(trg)
                            img.filepath = bpy.path.relpath(trg)
                            node.label = "%s%d" % (node.label[:-4], mattile)
                            images[src] = img
                        node.image = img


class DAZ_OT_FixTextureTiles(DazOperator, TextureTileFixer):
    bl_idname = "daz.fix_texture_tiles"
    bl_label = "Fix Texture Tiles"
    bl_description = "Copy textures to the right directory and correct tile numbers.\nTo fix incorrect Genesis 8.1 material names"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.active_material)

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


class DAZ_OT_UdimizeMaterials(DazPropsOperator, MaterialSelector, TextureTileFixer):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    trgmat : EnumProperty(items=getTargetMaterial, name="Active")

    useFixTextures : BoolProperty(
        name = "Fix Textures",
        description = "Copy textures to the right directory and correct tile numbers.\nTo fix incorrect Genesis 8.1 material names",
        default = True)

    useOnlyFixTextures : BoolProperty(
        name = "Only Fix Textures",
        description = "Only fix textures, don't make UDIM material.\nFor debugging",
        default = False)

    useFixTiles : BoolProperty(
        name = "Fix UV Tiles",
        description =  "Move UV vertices to the right tile automatically",
        default = False)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge materials and not only textures.\nIf on, some info may be lost.\nIf off, Merge Materials must be called afterwards",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useFixTextures")
        self.layout.prop(self, "useFixTiles")
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "trgmat")
        self.layout.label(text="Materials To Merge")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        ob = context.object
        if not ob.DazLocalTextures:
            from .error import invokeErrorMessage
            invokeErrorMessage("Save local textures first")
            return {'CANCELLED'}
        self.setupMaterials(ob)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def run(self, context):
        from shutil import copyfile

        ob = context.object
        if self.useFixTextures:
            self.findMatTiles(ob)
            self.fixTextures(ob, self.trgmat)

        mats = []
        mnums = []
        amat = None
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                mnums.append(mn)
                if amat is None or mat.name == self.trgmat:
                    amat = mat
                    amnum = mn
                    atile = 1001 + mat.DazUDim

        if amat is None:
            raise DazError("No materials selected")

        self.nodes = {}
        for mat in mats:
            self.nodes[mat.name] = self.getChannels(mat)

        if self.useFixTiles:
            for mn,mat in zip(mnums, mats):
                self.fixTiles(mat, mn, ob)

        for key,anode in self.nodes[amat.name].items():
            if anode.image.source == "TILED":
                raise DazError("Material %s already UDIM  " % amat.name)
            anode.image.source = "TILED"
            anode.extension = "CLIP"
            if anode.image:
                imgname = anode.image.name
            else:
                imgname = anode.name
            basename = "T_%s" % self.getBaseName(imgname, amat.DazUDim)
            udims = {}
            for mat in mats:
                nodes = self.nodes[mat.name]
                if key in nodes.keys():
                    node = nodes[key]
                    img = node.image
                    self.updateImage(img, basename, mat.DazUDim)
                    if mat.DazUDim not in udims.keys():
                        udims[mat.DazUDim] = mat.name
                    if mat == amat:
                        img.name = self.makeImageName(basename, atile, img)
                        node.label = basename
                        node.name = basename

            img = anode.image
            if bpy.app.version >= (3, 1, 0):
                path2,ext2 = os.path.splitext(img.filepath)
                img.filepath = "%s%s%s" % (path2[:-4],'<UDIM>',ext2)
            tile0 = img.tiles[0]
            for udim,mname in udims.items():
                if udim == 0:
                    tile0.number = 1001
                    tile0.label = mname
                else:
                    img.tiles.new(tile_number=1001+udim, label=mname)

        if self.useMergeMaterials:
            for f in ob.data.polygons:
                if f.material_index in mnums:
                    f.material_index = amnum

            mnums.reverse()
            for mn in mnums:
                if mn != amnum:
                    ob.data.materials.pop(index=mn)
        else:
            anodes = self.nodes[amat.name]
            for mat in mats:
                if mat != amat:
                    nodes = self.nodes[mat.name]
                    for key,node in nodes.items():
                        if key in anodes.keys():
                            anode = anodes[key]
                            img = node.image = anode.image
                            node.extension = "CLIP"
                            node.label = anode.label
                            node.name = anode.name


    def makeImageName(self, basename, tile, img):
        return "%s%s" % (basename, os.path.splitext(img.name)[1])


    def fixTiles(self, mat, mn, ob):
        for f in ob.data.polygons:
            f.select = False
        for node in self.nodes[mat.name].values():
            if node.image:
                imgname = baseName(node.image.name)
                if imgname[-4:].isdigit():
                    tile = int(imgname[-4:])
                else:
                    continue
                udim,vdim = getUVDims(tile)
                shiftUVs(mat, mn, ob, udim, vdim)
                return


    def getChannels(self, mat):
        channels = {}
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                channel = self.getChannel(node, mat.node_tree.links)
                channels[channel] = node
        return channels


    def getChannel(self, node, links):
        for link in links:
            if link.from_node == node:
                if link.to_node.type in ["MIX_RGB", "MATH", "GAMMA"]:
                    return self.getChannel(link.to_node, links)
                elif link.to_node.type == "BSDF_PRINCIPLED":
                    return ("PBR_%s" % link.to_socket.name)
                elif link.to_node.type == 'GROUP':
                    return link.to_node.node_tree.name
                else:
                    return link.to_node.type
        return None


    def getBaseName(self, string, udim):
        du = str(1001 + udim)
        if string[-4:] == du:
            string = string[:-4]
            if string[-1] in ["_", "-"]:
                string = string[:-1]
        return string


    def updateImage(self, img, basename, udim):
        from shutil import copyfile
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        folder = os.path.dirname(src)
        fname,ext = os.path.splitext(bpy.path.basename(src))
        if fname[-6:] == '<UDIM>':
            src = os.path.join(folder, "%s_%d%s" % (fname[-6], 1001+udim, ext))
        trg = os.path.join(folder, "%s_%d%s" % (basename, 1001+udim, ext))
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)

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
    uvloop = ob.data.uv_layers.active
    m = 0
    for fn,f in enumerate(ob.data.polygons):
        if f.material_index == mn:
            for n in range(len(f.vertices)):
                uv = uvloop.data[m].uv
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
        self.setupMaterials(context.object)
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
    DAZ_OT_FixTextureTiles,
    DAZ_OT_UdimizeMaterials,
    DAZ_OT_SetUDims,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)



