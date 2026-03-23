# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import bpy
from ..error import *
from ..utils import *
from ..fileutils import MultiFile, ImageFile, theImageExtensions
from ..material import setColorSpaceNone
from ..matsel import MaterialSelector

#-------------------------------------------------------------
#   Node tree layout
#-------------------------------------------------------------

class Layouter:
    loadedImages = {}

    usePrune : BoolProperty(
        name = "Prune Node Tree",
        description = "Prune the node tree",
        default = True)

    useCompact : BoolProperty(
        name = "Compact Layout",
        description = "Compact",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useCompact")
        self.layout.prop(self, "usePrune")

    def getImage(self, filepath):
        if filepath in self.loadedImages.keys():
            return self.loadedImages[filepath]
        else:
            img = bpy.data.images.load(filepath)
            img.name = os.path.splitext(os.path.basename(filepath))[0]
            setColorSpaceNone(img)
            self.loadedImages[filepath] = img
            return img

#-------------------------------------------------------------
#   Load Maps
#-------------------------------------------------------------

class LoadMaps(MultiFile, ImageFile, Layouter, MaterialSelector):
    useDriver : BoolProperty(
        name = "Use Drivers",
        description = "Drive maps with armature properties",
        default = True)

    useSmartTiles : BoolProperty(
        name = "Smart Tiles",
        description = "Identify tiles from materials",
        default = True)

    tile : IntProperty(
        name = "Tile",
        description = "Load textures in this tile.\nSelected materials should match the tile",
        min = 1001, max = 1009,
        default = 1001)

    def draw(self, context):
        self.layout.prop(self, "useDriver")
        self.layout.prop(self, "useSmartTiles")
        if not self.useSmartTiles:
            self.layout.prop(self, "tile")
        Layouter.draw(self, context)
        self.layout.label(text="Add Maps To Materials:")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return MultiFile.invoke(self, context, event)

    def getMaterials(self, ob):
        return [mat for mat in ob.data.materials if self.useMaterial(mat)]

    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def getArgs(self, ob):
        self.loadedImages = {}
        rig = ob.parent
        amt = None
        if rig and rig.type == 'ARMATURE':
            amt = rig.data
        filepaths = self.getMultiFiles(theImageExtensions)
        if not self.useSmartTiles:
            filepaths = [path for path in filepaths
                         if os.path.splitext(path)[0].endswith(str(self.tile))]
        self.props = {}
        for item in dazRna(ob.data).DazDhdmFiles:
            key = os.path.splitext(os.path.basename(item.s))[0].lower()
            self.props[key] = item.name
        args = []
        if self.useDriver and amt:
            for filepath in filepaths:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                final = self.getFinal(fname, rig, amt)
                args.append((ob, amt, fname, final, filepath))
        else:
            for filepath in filepaths:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                args.append((ob, amt, fname, None, filepath))
        for _,_,prop,_,_ in args:
            print(" *", prop)
        if not args:
            raise DazError("No file selected")
        return args


    def getFinal(self, fname, rig, amt):
        for key,prop in self.props.items():
            if fname.lower().startswith(key):
                if prop not in rig.keys():
                    rig[prop] = 0.0
                final = finalProp(prop)
                if final not in amt.keys():
                    amt[final] = 0.0
                return final
        return None


    def useFileInTile(self, fname, mat):
        tile = getTile(fname)
        if self.useSmartTiles:
            mattile = getMaterialTile(mat)
            return (mattile is None or tile == mattile)
        else:
            return (tile == self.tile)


    def checkTileUsed(self, mat, args):
        for ob,amt,fname,prop,filepath in args:
            if (os.path.exists(filepath) and
                self.useFileInTile(fname, mat)):
                return True
        return False


def getMaterialTile(mat):
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            tile = getTile(node.image.name)
            if tile:
                return tile
    return None


def getTile(string):
    string = baseName(string)
    if len(string) > 5 and string[-5] == "_" and string[-4:].isdigit():
        tile = int(string[-4:])
        if tile >= 1001 and tile <= 1100:
            return tile
    return None

#-------------------------------------------------------------
#   Scalar and Vector Displacement groups
#-------------------------------------------------------------

class DispAdder:
    shaderNode = "ShaderNodeDisplacement"
    heightInput = "Height"

    scale : FloatProperty(
        name = "Scale",
        description = "Scale value for displacement node",
        min = 0.0, max = 10.0,
        default = 0.01)

    midlevel : FloatProperty(
        name = "Midlevel",
        description = "Midlevel value for displacement node",
        min = 0.0, max = 1.0,
        default = 0.5)

    def draw(self, context):
        self.layout.prop(self, "scale")
        self.layout.prop(self, "midlevel")

    def loadDispMaps(self, mat, args):
        from ..tree import findNodes, pruneNodeTree, XSIZE
        from ..cycles import findTree
        from ..driver import makePropDriver
        if not self.checkTileUsed(mat, args):
            return
        if self.useCompact:
            size = 2
        else:
            size = 8
        tree = findTree(mat)
        outputs = findNodes(tree, 'OUTPUT_MATERIAL')
        last = None
        frame = None
        dy = 0
        if outputs:
            for link in outputs[0].inputs["Displacement"].links:
                last = link.from_node
                frame = last.parent
                dy = tree.below(last, size)
        if frame is None:
            frame = tree.nodes.new("NodeFrame")
            frame.label = "Displacement Maps"
        nodes = []
        for ob,amt,sname,prop,filepath in args:
            if not self.useFileInTile(sname, mat):
                continue
            img = self.getImage(filepath)
            tex = tree.addTextureNode(0, img, sname, size)
            tex.parent = frame
            nodes.append(tex)
            disp = tree.addNode(self.shaderNode, col=1, label=sname, size=size)
            disp.parent = frame
            nodes.append(disp)
            tree.links.new(tex.outputs["Color"], disp.inputs[self.heightInput])
            disp.inputs["Midlevel"].default_value = self.midlevel
            disp.inputs["Scale"].default_value = self.scale
            if amt and prop:
                makePropDriver(propRef(prop), disp.inputs["Scale"], "default_value", amt, "%g*x" % GS.scale)
            if self.useCompact:
                disp.hide = True
            if last is None:
                last = disp
                tree.skipSteps(2, size)
            else:
                add = tree.addNode("ShaderNodeVectorMath", col=2, size=size)
                add.parent = frame
                nodes.append(add)
                if self.useCompact:
                    add.hide = True
                add.operation = 'ADD'
                tree.links.new(last.outputs[0], add.inputs[0])
                tree.links.new(disp.outputs[0], add.inputs[1])
                last = add
        if last:
            for node in outputs:
                tree.links.new(last.outputs[0], node.inputs["Displacement"])
        tree.shiftNodes(nodes, -XSIZE, dy)
        if self.usePrune:
            pruneNodeTree(tree)


class DAZ_OT_LoadScalarDisp(DazOperator, LoadMaps, DispAdder):
    bl_idname = "daz.load_scalar_disp"
    bl_label = "Load Scalar Disp Maps"
    bl_description = "Load scalar displacement map to selected materials"
    bl_options = {'UNDO'}

    type = "DISP"

    def draw(self, context):
        DispAdder.draw(self, context)
        LoadMaps.draw(self, context)

    def run(self, context):
        ob = context.object
        args = self.getArgs(ob)
        LS.__init__()
        for mat in self.getMaterials(ob):
            self.loadDispMaps(mat, args)


class DAZ_OT_LoadVectorDisp(DazOperator, LoadMaps, DispAdder):
    bl_idname = "daz.load_vector_disp"
    bl_label = "Load Vector Disp Maps"
    bl_description = "Load vector displacement map to selected materials"
    bl_options = {'UNDO'}

    type = "VDISP"
    shaderNode = "ShaderNodeVectorDisplacement"
    heightInput = "Vector"

    def draw(self, context):
        DispAdder.draw(self, context)
        LoadMaps.draw(self, context)

    def run(self, context):
        ob = context.object
        args = self.getArgs(ob)
        LS.__init__()
        for mat in self.getMaterials(ob):
            self.loadDispMaps(mat, args)

#-------------------------------------------------------------
#   Load HD Normal Map
#-------------------------------------------------------------

class NormalAdder:
    def loadNormalMaps(self, mat, args, row):
        from ..driver import makePropDriver
        from ..tree import findNode, findLinksTo, XSIZE, pruneNodeTree
        from ..cycles import findTree
        from ..material import NORMAL

        if not self.checkTileUsed(mat, args) or not GS.useNormalMap:
            return
        tree = findTree(mat)
        if self.useCompact:
            size = 2
        else:
            size = 10
        dy = 0
        normal = findNode(tree, "NORMAL_MAP")
        socket = None
        frame = None
        if normal is None:
            tree.skipSteps(2, size)
            normal = tree.addNode("ShaderNodeNormalMap", col=2)
        else:
            links = findLinksTo(tree, "NORMAL_MAP")
            for link in links:
                socket = link.from_socket
                node = link.from_node
                dy = tree.below(node, size)
                frame = node.parent
        if frame is None:
            frame = tree.nodes.new("NodeFrame")
            frame.label = "Normal Maps"

        bump = findNode(tree, "BUMP")
        if bump:
            tree.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
        else:
            for node in tree.nodes:
                if "Normal" in node.inputs.keys():
                    tree.links.new(normal.outputs["Normal"], node.inputs["Normal"])

        nodes = []
        for ob,amt,fname,prop,filepath in args:
            if not os.path.exists(filepath):
                print("No such file: %s" % filepath)
                continue
            if not self.useFileInTile(fname, mat):
                continue
            img = self.getImage(filepath)
            tex = tree.addTextureNode(0, img, fname, size)
            tex.parent = frame
            nodes.append(tex)
            mix,a,b,out = tree.addMixRgbNode('OVERLAY', 1, size=size)
            mix.parent = frame
            nodes.append(mix)
            if self.useCompact:
                mix.hide = True
            mix.inputs[0].default_value = 1
            a.default_value = NORMAL
            if socket:
                tree.links.new(socket, a)
            tree.links.new(tex.outputs["Color"], b)
            if amt and prop:
                makePropDriver(propRef(prop), mix.inputs[0], "default_value", amt, "x")
            socket = out
        if socket:
            tree.links.new(socket, normal.inputs["Color"])
        else:
            print("No link to normal map node")
        tree.shiftNodes(nodes, -XSIZE, dy)
        if self.usePrune:
            pruneNodeTree(tree)


class DAZ_OT_LoadNormalMap(DazOperator, LoadMaps, NormalAdder):
    bl_idname = "daz.load_normal_map"
    bl_label = "Load Normal Maps"
    bl_description = "Load normal maps to selected materials"
    bl_options = {'UNDO'}

    type = "mrNM"

    def run(self, context):
        ob = context.object
        args = self.getArgs(ob)
        LS.__init__()
        for mat in self.getMaterials(ob):
            self.loadNormalMaps(mat, args, 1)

#----------------------------------------------------------
#   Baking
#----------------------------------------------------------

class Baker:
    if BLENDER4:
        enums = [('NORMALS', "Normals", "Bake normal maps"),
                 ('DISPLACEMENT', "Displacement", "Bake scalar displacement maps")]
    else:
        enums = [('NORMALS', "Normals", "Bake normal maps"),
                 ('DISPLACEMENT', "Displacement", "Bake scalar displacement maps"),
                 ('VECTOR_DISPLACEMENT', "Vector Displacement", "Bake vector displacement maps"),
                 ]

    bakeType : EnumProperty(
        items = enums,
        name = "Bake Type",
        description = "Bake Type",
        default = 'NORMALS')

    imageSize : EnumProperty(
        items = [("512", "512", "512 x 512 pixels"),
                 ("1024", "1024", "1024 x 1024 pixels"),
                 ("2048", "2048", "2048 x 2048 pixels"),
                 ("4096", "4096", "4096 x 4096 pixels"),
                ],
        name = "Image Size",
        default = "2048")

    subfolder : StringProperty(
        name = "Subfolder",
        description = "Subfolder for normal/displace maps",
        default = "")

    basename : StringProperty(
        name = "Base Name",
        description = "Name used to construct file names",
        default = "")

    def draw(self, context):
        self.layout.prop(self, "bakeType")
        self.layout.prop(self, "imageSize")
        self.layout.prop(self, "subfolder")
        self.layout.prop(self, "basename")


    storedFolder : StringProperty(default = "")
    storedName : StringProperty(default = "")

    def setDefaultNames(self, context):
        if self.storedName:
            self.basename = self.storedName
        else:
            self.basename = ""
            self.basename = self.getBaseName(context.object)
        if self.storedFolder:
            self.subfolder = self.storedFolder
        else:
            self.subfolder = self.basename


    def storeDefaultNames(self, context):
        if not self.subfolder:
            self.subfolder = self.getBaseName(context.object)
        self.storedFolder = self.subfolder
        self.storedName = self.basename


    def getBaseName(self, ob):
        if self.basename:
            return self.basename
        obname = noMeshName(ob.name)
        return bpy.path.clean_name(obname.lower())


    def getImageName(self, basename, tile):
        if self.bakeType == 'NORMALS':
            return ("%s_NM_%s_%d.png" % (basename, self.imageSize, tile))
        elif self.bakeType == 'DISPLACEMENT':
            return ("%s_DISP_%s_%d.png" % (basename, self.imageSize, tile))
        elif self.bakeType == 'VECTOR_DISPLACEMENT':
            return ("%s_VDISP_%s_%d.png" % (basename, self.imageSize, tile))


    def getImagePath(self, imgname, create):
        folder = os.path.dirname(bpy.data.filepath)
        dirpath = os.path.join(folder, "textures", self.bakeType.lower(), self.subfolder)
        if not os.path.exists(dirpath):
            if create:
                os.makedirs(dirpath)
            else:
                return None
        return os.path.join(dirpath, imgname)


    def getTiles(self, ob):
        tiles = {}
        uvloop = ob.data.uv_layers[0]
        m = 0
        for f in ob.data.polygons:
            n = len(f.vertices)
            rx = sum([get_uv(uvloop, k)[0] for k in f.loop_indices])/n
            ry = sum([get_uv(uvloop, k)[1] for k in f.loop_indices])/n
            i = max(0, int(round(rx-0.5)))
            j = max(0, int(round(ry-0.5)))
            tile = 1001 + 10*j + i
            if tile not in tiles.keys():
                tiles[tile] = []
            tiles[tile].append(f.index)
            m += n
        return tiles

#----------------------------------------------------------
#   Bake maps
#----------------------------------------------------------

class DAZ_OT_BakeMaps(DazPropsOperator, Baker):
    bl_idname = "daz.bake_maps"
    bl_label = "Bake Maps"
    bl_description = "Bake normal/displacement maps for the selected HD meshes"
    bl_options = {'UNDO'}

    useSingleTile : BoolProperty(
        name = "Single Tile",
        description = "Only bake map for a single tile",
        default = False)

    tile : IntProperty(
        name = "Tile",
        description = "Single tile to bake",
        min = 1001, max = 1100,
        default = 1001)

    def draw(self, context):
        Baker.draw(self, context)
        self.layout.prop(self, "useSingleTile")
        if self.useSingleTile:
            self.layout.prop(self, "tile")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and ob and getModifier(ob, 'MULTIRES'))


    def storeState(self, context):
        scn = context.scene
        self.engine = scn.render.engine
        scn.render.engine = 'CYCLES'
        if hasattr(scn.render, "bake_type"):
            self.bake_type = scn.render.bake_type
            self.use_bake_multires = scn.render.use_bake_multires
        else:
            self.bake_type = scn.render.bake.type
            self.use_multires = scn.render.bake.use_multires
        self.samples = scn.cycles.samples
        self.simplify = scn.render.use_simplify
        if hasattr(scn.render, "bake_type"):
            scn.render.bake_type = self.bakeType
            scn.render.use_bake_multires = True
            scn.render.bake_margin = 2
        else:
            scn.render.bake.type = self.bakeType
            scn.render.bake.use_multires = True
            scn.render.bake.margin = 2
        scn.cycles.samples = 512
        scn.render.use_simplify = False
        self.object = context.view_layer.objects.active


    def restoreState(self, context):
        scn = context.scene
        if hasattr(scn.render, "bake_type"):
            scn.render.use_bake_multires = self.use_bake_multires
            scn.render.bake_type = self.bake_type
        else:
            scn.render.bake.use_multires = self.use_multires
            scn.render.bake.type = self.bake_type
        scn.render.engine = self.engine
        scn.cycles.samples = self.samples
        scn.render.use_simplify = self.simplify
        context.view_layer.objects.active = self.object


    def invoke(self, context, event):
        self.setDefaultNames(context)
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        self.storeDefaultNames(context)
        LS.__init__()
        objects = [ob for ob in getSelectedMeshes(context) if getModifier(ob, 'MULTIRES')]
        for ob in objects:
            activateObject(context, ob)
            try:
                self.storeMaterials(ob)
                self.bakeObject(context, ob)
            finally:
                self.restoreMaterials(ob)


    def storeMaterials(self, ob):
        self.mnums = [f.material_index for f in ob.data.polygons]
        self.materials = list(ob.data.materials)
        for mat in self.materials:
            ob.data.materials.pop()


    def restoreMaterials(self, ob):
        for mat in list(ob.data.materials):
            ob.data.materials.pop()
        for mat in self.materials:
            ob.data.materials.append(mat)
        for fn,mn in enumerate(self.mnums):
            f = ob.data.polygons[fn]
            f.material_index = mn


    def bakeObject(self, context, ob):
        setMode('OBJECT')
        mod = getModifier(ob, 'MULTIRES')
        if mod is None:
            print("Object %s has no multires modifier" % ob.name)
            return
        levels = mod.levels
        mod.levels = 0
        tiles = self.getTiles(ob)
        ntiles = len(tiles)
        startProgress("Baking %s" % ob.name)
        for n,data in enumerate(tiles.items()):
            tile,fnums = data
            if self.useSingleTile and tile != self.tile:
                continue
            showProgress(n, ntiles)
            img = self.makeImage(ob, tile)
            mat = self.makeMaterial(ob, img)
            self.translateTile(ob, fnums, tile, -1)
            self.selectFaces(ob, fnums, tile)
            bpy.ops.object.bake_image()
            img.save()
            print("Saved %s" % img.filepath)
            self.translateTile(ob, fnums, tile, 1)
            ob.data.materials.pop()
        showProgress(ntiles, ntiles)
        endProgress()
        mod.levels = levels


    def makeImage(self, ob, tile):
        basename = self.getBaseName(ob)
        imgname = self.getImageName(basename, tile)
        size = int(self.imageSize)
        img = bpy.data.images.new(imgname, size, size)
        setColorSpaceNone(img)
        img.filepath = self.getImagePath(imgname, True)
        return img


    def makeMaterial(self, ob, img):
        from ..tree import hideAllBut
        mat = bpy.data.materials.new(img.name)
        setModernProps(mat)
        ob.data.materials.append(mat)
        ob.active_material = mat
        if BLENDER5:
            mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        texco = tree.nodes.new(type = "ShaderNodeTexCoord")
        texco.location = (0, 0)
        texco.hide = True
        hideAllBut(texco, ["UV"])
        node = tree.nodes.new(type = "ShaderNodeTexImage")
        node.location = (200,0)
        node.image = img
        node.interpolation = GS.imageInterpolation
        node.extension = 'CLIP'
        node.select = True
        tree.nodes.active = node
        tree.links.new(texco.outputs["UV"], node.inputs["Vector"])
        return mat


    def selectFaces(self, ob, fnums, tile):
        setMode('EDIT')
        bpy.ops.uv.select_all(action='DESELECT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        for fn in fnums:
            f = ob.data.polygons[fn]
            f.select = True
        setMode('EDIT')
        bpy.ops.uv.select_all(action='SELECT')
        setMode('OBJECT')


    def translateTile(self, ob, fnums, tile, sign):
        setMode('OBJECT')
        j = (tile-1001)//10
        i = (tile-1001-10*j)%10
        dx = sign*i
        dy = sign*j
        uvloop = ob.data.uv_layers[0]
        for f in ob.data.polygons:
            for n in f.loop_indices:
                get_uv(uvloop, n)[0] += dx
                get_uv(uvloop, n)[1] += dy

#----------------------------------------------------------
#   Load normal/displacement maps
#----------------------------------------------------------

class DAZ_OT_LoadBakedMaps(DazPropsOperator, Baker, NormalAdder, DispAdder, Layouter, IsMesh):
    bl_idname = "daz.load_baked_maps"
    bl_label = "Load Baked Maps"
    bl_description = "Load baked normal/displacement maps for the selected meshes"
    bl_options = {'UNDO'}

    dispScale : FloatProperty(
        name = "Displacement Scale",
        description = "Displacement scale",
        min = 0.001, max = 10,
        default = 0.01)

    def draw(self, context):
        Baker.draw(self, context)
        if self.bakeType in ['DISPLACEMENT', 'VECTOR_DISPLACEMENT']:
            self.layout.prop(self, "dispScale")
        Layouter.draw(self, context)

    def invoke(self, context, event):
        self.setDefaultNames(context)
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        self.storeDefaultNames(context)
        LS.__init__()
        for ob in getSelectedMeshes(context):
            activateObject(context, ob)
            self.loadObjectMaps(ob)

    def useFileInTile(self, fname, mat):
        return True

    def checkTileUsed(self, mat, args):
        return True

    def loadObjectMaps(self, ob):
        self.loadedImages = {}
        mod = getModifier(ob, 'MULTIRES')
        if mod:
            mod.show_viewport = mod.show_render = False
        tiles = self.getTiles(ob)
        mattiles = dict([(mn,None) for mn in range(len(ob.data.materials))])
        for tile,fnums in tiles.items():
            for fn in fnums:
                f = ob.data.polygons[fn]
                mattiles[f.material_index] = tile
        for mn,mat in enumerate(ob.data.materials):
            tile = mattiles[mn]
            if tile is None:
                print("No matching tile for material %s" % mat.name)
            else:
                self.loadMap(ob, mat, tile)


    def loadMap(self, ob, mat, tile):
        basename = self.getBaseName(ob)
        imgname = self.getImageName(basename, tile)
        filepath = self.getImagePath(imgname, False)
        args = [(ob, None, imgname, None, filepath)]
        if filepath is None:
            print("Texture not found: %s" % imgname)
        elif self.bakeType == 'NORMALS':
            self.loadNormalMaps(mat, args, 0)
        elif self.bakeType == 'DISPLACEMENT':
            self.shaderNode = "ShaderNodeDisplacement"
            self.heightInput = "Height"
            self.loadDispMaps(mat, args)
        elif self.bakeType == 'VECTOR_DISPLACEMENT':
            self.shaderNode = "ShaderNodeVectorDisplacement"
            self.heightInput = "Vector"
            self.loadDispMaps(mat, args)


#----------------------------------------------------------
#
#----------------------------------------------------------

class DAZ_OT_CopyGraftGroups(DazOperator, IsMesh):
    bl_idname = "daz.copy_grafts_groups"
    bl_label = "Copy Grafts Groups"
    bl_description = "Copy vertex groups from selected geografts to HD mesh.\nThe base mesh must also be selected"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..geometry import isGeograft
        from ..hd_data import copyGraftGroups
        hdob = context.object
        baseob = None
        grafts = []
        for ob in getSelectedMeshes(context):
            if isGeograft(ob):
                grafts.append(ob)
            elif ob != hdob:
                baseob = ob
        if len(grafts) == 0:
            raise DazError("No grafts selected")
        elif baseob is None:
            raise DazError("No base object selected")
        copyGraftGroups(context, hdob, baseob, grafts)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_LoadScalarDisp,
    DAZ_OT_LoadVectorDisp,
    DAZ_OT_LoadNormalMap,
    DAZ_OT_BakeMaps,
    DAZ_OT_LoadBakedMaps,
    DAZ_OT_CopyGraftGroups,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)