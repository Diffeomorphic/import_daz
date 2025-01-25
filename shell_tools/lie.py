# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..tree import *
from ..material import isWhite, isBlack, getImage
from ..main import *
from ..cgroup import *
from ..matsel import MaterialSelector
from ..selector import Selector
from .shell import ShellRemover

def isNumber(x):
    return isinstance(x, (int, float))

#------------------------------------------------------------------
#   Import Layered Images
#------------------------------------------------------------------

Channels = {
    "Diffuse Color" : (
        [("DAZ Diffuse", "Color"), ("BSDF_PRINCIPLED", "Base Color")],
        "sRGB", "Color"),
    "Diffuse Roughness" : (
        [("DAZ Diffuse", "Roughness"), ("BSDF_PRINCIPLED", "Roughness")],
        "Non-Color", "Value"),
    "Translucency Color" : (
        [("DAZ Translucent", "Color"), ("DAZ Subsurface", "Color")],
        "sRGB", "Color"),
    "Glossy Layered Weight" : (
        [("DAZ Glossy", "Fac"), ("BSDF_PRINCIPLED", "Specular IOR Level")],
        "Non-Color", "Value"),
    "Glossy Color" : (
        [("DAZ Glossy", "Color"), ("BSDF_PRINCIPLED", "Specular Tint")],
        "sRGB", "Color"),
    "Glossy Roughness" : (
        [("DAZ Glossy", "Roughness"), ("DAZ Dual Lobe", "Roughness 1"), ("BSDF_PRINCIPLED", "Roughness")],
        "Non-Color", "Value"),
    "Bump Strength" : (
        [("BUMP", "Height")],
        "Non-Color", "Value"),
    "Normal Map" : (
        [("NORMAL_MAP", "Color")],
        "Non-Color", "Color"),
    "Top Coat Weight" : (
        [("DAZ Top Coat", "Fac"), ("BSDF_PRINCIPLED", "Coat Weight")],
        "Non-Color", "Value"),
    "Top Coat Color" : (
        [("DAZ Top Coat", "Color"), ("BSDF_PRINCIPLED", "Coat Tint")],
        "sRGB", "Color"),
    "Top Coat Roughness" : (
        [("DAZ Top Coat", "Roughness"), ("BSDF_PRINCIPLED", "Coat Roughness")],
        "Non-Color", "Value"),
}

SlotTypes = {
    "Color" : ["Color", "A", "B"],
    "Value" : ["Value"],
}

IrayChannels = {
    "diffuse" : "Diffuse Color",
    "specular" : "Glossy Color",
    "Specular Color" : "Glossy Color",
    "specular_strength" : "Glossy Layered Weight",
    "bump" : "Bump Strength",
    "normal" : "Normal Map",
    "displacement" : "Displacement",
    "opacity" : "Cutout Opacity",
}

GeograftMaterials = {
    "Torso" : ["Nipples",
               "Gen",
               "GP_Torso", "GP_Torso_Back",
               "Torso_Front", "Torso_Back", "Torso_Middle",
               "Torso_FenderBlender_G8F_FTL",
               "Torso_Upper_Left", "Torso_Upper_Right",
               "Torso_Medium_Left", "Torso_Medium_Right",
               "Torso_Lower_Left", "Torso_Lower_Right",
               ],
}

Geografts = [
    "AdvancedPussy_Redux__2253",
    "HeadLight_L_608",
    "HeadLight_R_608",
    "GoldenPalace_2254",
    "GoldenPalace_G9_9694",
    "Dicktator_Genitalia_G8M",
    "G9Dicktator_8666",
    "Futalicious_Genitalia_G8F",
    "RoastyFullBBQ_2117",
    "new_gens_V8_1840",
    "Breastacular_A2_2453",
    "FenderBlender_G8F_FTL_1107",
    "Multibreast_7332",
    "M_L_Tongue_1050",
    "TailGeom_Core_826",
    "dbxxx-XX",
]

theImages = {}

def getTargetMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]

class DAZ_OT_ImportShellsAsImages(DazOperator, MaterialLoader, DazImageFile, MultiFile, IsMesh):
    bl_idname = "daz.import_shells_as_images"
    bl_label = "Import Shells As Images"
    bl_description = "Load shells as layered images to selected meshes"
    bl_options = {'UNDO'}

    fitMeshes = 'SHARED'

    useDriveInfluence : BoolProperty(
        name = "Drive Influence",
        description = "Create drivers for shell influence",
        default = True)

    useGeografts : BoolProperty(
        name = "Geografts",
        description = "Target meshes are geografts",
        default = False)

    useAutoMaterial : BoolProperty(
        name = "Automatic Target Materials",
        default = True)

    useHSV : BoolProperty(
        name = "HSV Correction",
        default = False)

    targetMaterial : EnumProperty(
        items = getTargetMaterial,
        name = "Target Material",
        description = "Add images to this material")

    '''
    useExtend : BoolProperty(
        name = "Extend To Geografts",
        default = False)

    useOtherChannels : BoolProperty(
        name = "Other Channels",
        description = "Replace other channels with layered images too",
        default = False)
    '''
    useExtend = False
    useOtherChannels = False

    midLevel : BoolProperty(
        name = "Mid Level Opacity",
        description = "Grey mask is zero opacity",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useAutoMaterial")
        if not self.useAutoMaterial:
            self.layout.prop(self, "targetMaterial")
        self.layout.prop(self, "useDriveInfluence")
        self.layout.prop(self, "useGeografts")
        #self.layout.prop(self, "useExtend")
        #self.layout.prop(self, "useOtherChannels")
        self.layout.prop(self, "midLevel")
        self.layout.prop(self, "useHSV")

    def run(self, context):
        def materialBaseName(mname):
            basename = stripName(mname)
            if self.useGeografts:
                changed = True
                while changed:
                    changed = False
                    for gname in Geografts:
                        if basename.startswith(gname):
                            basename = basename[(len(gname)+1):]
                            changed = True
                            break
            return basename

        def getMaterials(ob, mname):
            if not self.useAutoMaterial:
                return [ob.data.materials[self.targetMaterial]]
            mats = []
            for mat in ob.data.materials:
                if mat and materialBaseName(mat.name) == mname:
                    if not self.useGeografts or dazRna(mat).DazShellMap:
                        mats.append(mat)
            return mats

        def getExistingShells(ob, existing):
            from ..matsel import isShellNode
            for mat in ob.data.materials:
                if mat and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if isShellNode(node):
                            key = node.node_tree.name
                            string = "_%s" % mat.name
                            n = len(string)
                            if key[-n:] == string:
                                key = key[:-n]
                            existing[key] = node

        def setupShells(main):
            def setupShell(inst):
                mnames = []
                invis = []
                n = len("material_group_")
                for key,channel in inst.channels.items():
                    if key[0:n] == "material_group_":
                        words = key[n:].rsplit("_",1)
                        if words[-1] == "vis":
                            mname = materialBaseName(words[0])
                            vis = channel.get("current_value", True)
                            if vis:
                                mnames.append(mname)
                            else:
                                invis.append(mname)
                return mnames, invis

            def addShell(asset, inst, shells, defaults):
                if asset.type == "node":
                    for extra in inst.extra:
                        type = extra.get("type")
                        if type == "studio/node/shell":
                            if asset.name in self.existing.keys():
                                return
                            mnames,invis = setupShell(inst)
                            if mnames:
                                defaults[asset.url] = (mnames, invis)
                            elif asset.url in defaults.keys():
                                mnames,invis = defaults[asset.url]
                            if mnames:
                                for geonode in inst.geometries:
                                    shells[geonode.id] = (inst.label, mnames, invis)
                            print("Shell: %s %d %d\nURL: %s" % (inst.label, len(mnames), len(invis), asset.url))

            shells = {}
            defaults = {}
            for asset,inst in main.nodes:
                addShell(asset, inst, shells, defaults)
            return shells

        global theImages
        theImages = { "sRGB" : {}, "Non-Color" : {}}
        meshes = getSelectedMeshes(context)
        self.existing = {}
        for ob in meshes:
            getExistingShells(ob, self.existing)

        GS.checkAbsPaths()
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        LS.forImport(self)
        for filepath in filepaths:
            self.replacedTexs = {}
            self.replacedLies = {}
            for ob in meshes:
                for mat in ob.data.materials:
                    self.replacedTexs[mat.name] = {}
                    self.replacedLies[mat.name] = {}

            main = self.loadDazFile(filepath, context)
            shells = setupShells(main)
            for dmat in main.materials:
                if dmat.geometry and dmat.geometry.id in shells.keys():
                    label,mnames,invis = shells.get(dmat.geometry.id)
                    mname = materialBaseName(dmat.name)
                    if mname not in mnames:
                        if not self.useExtend or mname in invis:
                            continue
                    for ob in meshes:
                        for mat in getMaterials(ob, mname):
                            if mat:
                                self.addToMaterial(dmat, mat, ob, label)
                                beautifyNodeTree(mat.node_tree)
                        if not self.useGeografts:
                            for xname in GeograftMaterials.get(mname, []):
                                for mat in getMaterials(ob, xname):
                                    if mat:
                                        self.addToMaterial(dmat, mat, ob, label)
                                        beautifyNodeTree(mat.node_tree)

            self.groups = {}
            for ob in meshes:
                for mat in ob.data.materials:
                    if mat is None:
                        continue
                    if self.useOtherChannels:
                        self.replaceUnfixedNodes(mat)
                    self.replaceGroups(mat)


    def addToMaterial(self, dmat, mat, ob, label):
        def getNode(tree, type):
            for node in mat.node_tree.nodes:
                if node.type == type:
                    return node
                elif node.type == 'GROUP' and node.node_tree.name == type:
                    return node

        def getTexNode(socket, slots):
            for link in socket.links:
                fromnode = link.from_node
                if fromnode.type == 'TEX_IMAGE':
                    return fromnode
                elif fromnode.type == 'GROUP':
                    if fromnode.node_tree.name.startswith(("SLIE", "SLie", "LIE")):
                        return fromnode
                for slot in slots:
                    socket = fromnode.inputs.get(slot)
                    if socket:
                        return getTexNode(socket, slots)

        def findTexNode(mat, channel):
            key = channel["id"]
            key = IrayChannels.get(key, key)
            if key in Channels.keys():
                ntypes,colorspace,stype = Channels[key]
                slots = SlotTypes[stype]
                for ntype,slot in ntypes:
                    node = getNode(mat.node_tree, ntype)
                    if node:
                        socket = node.inputs[slot]
                        texnode = getTexNode(socket, slots)
                        return key, texnode
            return key, None


        def replaceTexNode(tree, texnode, label, key, value, img, mask, uvset1, uvsets):
            node = tree.nodes.new("ShaderNodeGroup")
            x,y = node.location = texnode.location
            uvmap0,uvset0 = findUvmapNode(tree, uvsets[0], [], (x-100,y))
            if len(uvsets) > 1:
                if uvset1 is None:
                    uvset1 = uvsets[-1]
                uvmap1,uvset1 = findUvmapNode(tree, uvset1, uvsets[1:],(x-100,y-100))
            else:
                uvmap1,uvset1 = uvmap0,uvset0
            group = ShellLieGroup(None, key, self.midLevel)
            group.create(node, texnode, "SLIE %s %s" % (label, key), mat, uvset0)
            group.addImage(label, value, img, mask, uvset1, self.useHSV)
            tree.links.new(uvmap0.outputs[0], node.inputs[uvset0])
            tree.links.new(uvmap1.outputs[0], node.inputs[uvset1])
            if key == "Diffuse Color":
                tree.nodes.active = node
                node.select = True
            for idx,socket in enumerate(texnode.inputs):
                for link in socket.links:
                    tree.links.new(link.from_socket, node.inputs[idx])
            for idx,socket in enumerate(texnode.outputs):
                for link in socket.links:
                    tree.links.new(node.outputs[idx], link.to_socket)
            tree.nodes.remove(texnode)
            return node


        def replaceGroupNode(tree, grpnode, label, key, value, img, mask, uvsets):
            if label in grpnode.inputs.keys():
                #print("Already added to %s: %s" % (grpnode.label, label))
                return
            group = ShellLieGroup(tree, key, self.midLevel)
            group.recreate(grpnode, mat)
            if len(uvsets) > 1:
                uvset0 = uvsets[-1]
                uvsets0 = uvsets[1:]
            else:
                uvset0 = uvsets[0]
                uvsets0 = []
            uvmap1,uvset1 = findUvmapNode(tree, uvset0, uvsets0, (0,0))
            group.addImage(label, value, img, mask, uvset1, self.useHSV)
            tree.links.new(uvmap1.outputs[0], node.inputs[uvset1])

        def findUvmapNode(tree, uvset, uvsets, location):
            for node in tree.nodes:
                if node.type == "UVMAP" and node.uv_map in uvsets:
                    return node,node.uv_map
            node = tree.nodes.new("ShaderNodeUVMap")
            node.label = uvset
            node.uv_map = uvset
            node.location = location
            node.hide = True
            return node,uvset

        def fixNode(mat, node, label, key, value, img, mask, uvsets):
            uvset1 = dazRna(mat).DazShellMap
            if node is None:
                pass
            elif node.type == 'TEX_IMAGE':
                if node.image:
                    rkey = node.image.name
                    snode = replaceTexNode(mat.node_tree, node, label, key, value, img, mask, uvset1, uvsets)
                    self.replacedTexs[mat.name][rkey] = snode
                    self.addSocketDriver(snode, label, rig)
            elif isLayeredNode(node):
                rkey = node.node_tree.name
                snode = replaceTexNode(mat.node_tree, node, label, key, value, img, mask, uvset1, uvsets)
                self.replacedLies[mat.name][rkey] = snode
                self.addSocketDriver(snode, label, rig)
            elif isShellImageNode(node):
                replaceGroupNode(mat.node_tree, node, label, key, value, img, mask, uvsets)
                self.addSocketDriver(node, label, rig)

        rig = ob
        if ob.parent and ob.parent.type == 'ARMATURE':
            rig = ob.parent

        # Find UV sets
        active = ob.data.uv_layers.active.name
        uvsets = [active]
        if self.useGeografts:
            uvsets += [uvlayer.name for uvlayer in ob.data.uv_layers if uvlayer.name != active]

        # Find mask
        mask = None
        channel = dmat.channels.get("Cutout Opacity")
        if channel is None:
            channel = dmat.channels.get("opacity")
        if channel:
            url = channel.get("image_file")
            if url:
                mask = getImage(url)
        for key,channel in dmat.channels.items():
            if key in ("Cutout Opacity", "opacity"):
                continue
            key,node = findTexNode(mat, channel)
            if node is None:
                continue
            value = channel.get("current_value")
            if channel.get("image"):
                texs,maps = dmat.getTextures(channel)
                for tex,map in zip(texs,maps):
                    if map.operation == "alpha_blend":
                        tex.buildImage("COLOR")
                        if tex.image is None:
                            continue
                        fixNode(mat, node, label, key, value, tex.image, tex.image, uvsets)
            elif channel.get("image_file"):
                img = getImage(channel["image_file"])
                fixNode(mat, node, label, key, value, img, mask, uvsets)
            elif isNumber(value):
                if value != 1.0 and mask:
                    fixNode(mat, node, label, key, value, None, mask, uvsets)
            elif value and not isWhite(value) and mask:
                fixNode(mat, node, label, key, value, None, mask, uvsets)


    def addSocketDriver(self, node, label, rig):
        from ..driver import setFloatProp, addDriver
        prop = "INFLU %s" % label
        rig.hide_viewport = False
        if self.useDriveInfluence:
            setFloatProp(rig, prop, 1.0, 0.0, 10.0, True, False)
            addDriver(node.inputs[label], "default_value", rig, propRef(prop), "x")
            dazRna(rig).DazVisibilityDrivers = True
        else:
            node.inputs[label].default_value = 1.0
            if prop in rig.keys():
                del rig[prop]


    def replaceUnfixedNodes(self, mat):
        def replaceNode(tree, node, snode):
            for idx,socket in enumerate(node.outputs):
                for link in socket.links:
                    tree.links.new(snode.outputs[idx], link.to_socket)
            tree.nodes.remove(node)

        def heuristicMatch(nname, sname):
            return (nname[:20] == sname[:20] and nname[-20:] == sname[-20:])

        if not self.replacedTexs[mat.name] and not self.replacedLies[mat.name]:
            return
        texs = self.replacedTexs[mat.name]
        lies = self.replacedLies[mat.name]
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                if node.image.name in texs.keys():
                    replaceNode(mat.node_tree, node, texs[node.image.name])
            elif node.type == 'GROUP' and node.node_tree:
                nname = node.node_tree.name
                for sname,snode in lies.items():
                    if heuristicMatch(nname, sname):
                        replaceNode(mat.node_tree, node, snode)
                        break


    def replaceGroups(self, mat):
        for node in list(mat.node_tree.nodes):
            if isShellImageNode(node):
                inputs = [socket.name for socket in node.inputs]
                texnode,name = getShellTexNode(node)
                key = "%s:%s:%s" % (baseName(node.node_tree.name), name, ":".join(inputs))
                group = self.groups.get(key)
                if group:
                    node.node_tree = group
                else:
                    self.groups[key] = node.node_tree

# ---------------------------------------------------------------------
#   Shell LIE Group
# ---------------------------------------------------------------------

class ShellLieGroup(NodeGroup, CyclesTree):
    def __init__(self, tree, key, midLevel):
        CyclesGroup.__init__(self)
        if tree:
            self.node_tree = tree
        if key == "Normal Map":
            self.mixmode = 'OVERLAY'
        else:
            self.mixmode = 'MIX'
        self.colorspace = Channels[key][1]
        self.midLevel = midLevel
        self.useHSV = (key == "Diffuse Color")


    def create(self, node, texnode, name, mat, uvset):
        CyclesTree.__init__(self, mat.node_tree)
        NodeGroup.create(self, node, name, mat, 8)
        addGroupInput(self.group, "NodeSocketVector", uvset)
        if self.useHSV:
            addGroupInput(self.group, "NodeSocketFloat", "Saturation")
            self.setMinMax("Saturation", 1.0, 0.0, 2.0)
            addGroupInput(self.group, "NodeSocketFloat", "Value")
            self.setMinMax("Value", 1.0, 0.0, 2.0)
            addGroupInput(self.group, "NodeSocketFloat", "Factor")
            self.setMinMax("Factor", 1.0, 0.0, 1.0)
        addGroupOutput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketFloat", "Alpha")

        if texnode.type == 'TEX_IMAGE':
            tex = self.addNode("ShaderNodeTexImage", 1)
            tex.image = texnode.image
            tex.interpolation = texnode.interpolation
            tex.extension = texnode.extension
        else:
            tex = self.addNode("ShaderNodeGroup", 1)
            tex.node_tree = texnode.node_tree
        self.links.new(self.inputs.outputs[uvset], tex.inputs["Vector"])
        self.links.new(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.links.new(tex.outputs["Alpha"], self.outputs.inputs["Alpha"])
        if self.useHSV:
            node.inputs["Saturation"].default_value = 1.0
            node.inputs["Value"].default_value = 1.0
            node.inputs["Factor"].default_value = 1.0
        self.nodes.active = tex
        tex.select = True


    def recreate(self, grpnode, mat):
        CyclesTree.__init__(self, mat.node_tree)
        NodeGroup.remake(self, grpnode.node_tree, mat)


    def addImage(self, label, value, img, mask, uvset, useHSV):
        if not getGroupInput(self.group, uvset):
            addGroupInput(self.group, "NodeSocketVector", uvset)
        socket = addGroupInput(self.group, "NodeSocketFloat", label)
        self.setMinMax(label, 1.0, 0.0, 10)
        link = self.outputs.inputs["Color"].links[0]
        prev = link.from_node
        y = prev.location[1]-300
        texs = [node for node in self.nodes
                if node.type == 'TEX_IMAGE' or isLayeredNode(node)]
        tex0 = texs[0]

        if img:
            tex = self.addNode("ShaderNodeTexImage", 1)
            tex.location[1] = y
            img0 = theImages[self.colorspace].get(img.name)
            if img0:
                tex.image = img0
            else:
                img.colorspace_settings.name = self.colorspace
                theImages[self.colorspace] = img
            tex.image = img
            if tex0 and tex0.type == 'TEX_IMAGE':
                tex.interpolation = tex0.interpolation
                tex.extension = tex0.extension
            self.links.new(self.inputs.outputs[uvset], tex.inputs["Vector"])
            out = tex.outputs["Color"]
            if self.mixmode != 'MIX':
                pass
            elif isNumber(value):
                if value != 1.0:
                    mult = self.addNode("ShaderNodeMath", 2)
                    mult.location[1] = y
                    mult.operation = 'MULTIPLY'
                    self.links.new(tex.outputs["Color"], mult.inputs[0])
                    mult.inputs[1].default_value = value
                    out = mult.outputs[0]
            elif not isWhite(value):
                mult,a,b,out = self.addMixRgbNode('MULTIPLY', 2)
                mult.location[1] = y
                mult.inputs[0].default_value = 1.0
                self.links.new(tex.outputs["Color"], a)
                b.default_value[0:3] = value
        elif isNumber(value):
            node = self.addNode("ShaderNodeValue", 2)
            node.location[1] = y
            node.outputs[0].default_value = value
            out = node.outputs[0]
        else:
            rgb = self.addNode("ShaderNodeRGB", 2)
            rgb.location[1] = y
            rgb.outputs["Color"].default_value[0:3] = value
            out = rgb.outputs["Color"]

        if self.useHSV and useHSV:
            hsv = self.addNode("ShaderNodeHueSaturation", 3)
            hsv.location[1] = y
            self.links.new(out, hsv.inputs["Color"])
            self.links.new(self.inputs.outputs["Saturation"], hsv.inputs["Saturation"])
            self.links.new(self.inputs.outputs["Value"], hsv.inputs["Value"])
            self.links.new(self.inputs.outputs["Factor"], hsv.inputs["Fac"])
            out = hsv.outputs["Color"]

        if mask == img:
            if img:
                alpha = tex.outputs["Alpha"]
            else:
                alpha = None
        elif mask:
            masktex = self.addNode("ShaderNodeTexImage", 4)
            masktex.location[1] = y
            masktex.image = mask
            mask.colorspace_settings.name = "Non-Color"
            self.links.new(self.inputs.outputs[uvset], masktex.inputs["Vector"])
            alpha = masktex.outputs["Color"]
        else:
            alpha = None

        if alpha:
            if self.midLevel:
                sub = self.addNode("ShaderNodeMath", 5)
                sub.location[1] = y
                sub.operation = 'MULTIPLY_ADD'
                self.links.new(alpha, sub.inputs[0])
                sub.inputs[1].default_value = 2
                sub.inputs[2].default_value = -0.5
                alpha = sub.outputs[0]
            mult = self.addNode("ShaderNodeMath", 6)
            mult.location[1] = y
            mult.operation = 'MULTIPLY'
            self.links.new(self.inputs.outputs[label], mult.inputs[0])
            self.links.new(alpha, mult.inputs[1])
            factor = mult.outputs[0]
        else:
            factor = self.inputs.outputs[label]

        mix,a,b,mixout = self.addMixRgbNode(self.mixmode, 7)
        mix.location[1] = y
        mix.inputs[0].default_value = 1.0
        self.links.new(factor, mix.inputs[0])
        self.links.new(colorOutput(prev), a)
        self.links.new(out, b)
        self.links.new(mixout, self.outputs.inputs["Color"])

#----------------------------------------------------------
#   Remove Shell Images
#----------------------------------------------------------

class DAZ_OT_RemoveShellImages(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.remove_shell_images"
    bl_label = "Remove Shell Images"
    bl_description = "Remove selected shell images from selected objects"
    bl_options = {'UNDO'}

    columnWidth = 350

    useDeleteProperties : BoolProperty(
        name = "Delete Properties",
        description = "Delete driving properties",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useDeleteProperties")
        Selector.draw(self, context)

    def run(self, context):
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat,node in data:
                    self.replaceNodes(mat, node)
            if self.useDeleteProperties:
                print("II", item.name, item.text)


    def invoke(self, context, event):
        self.getShells(context)
        self.addItems()
        return self.invokeDialog(context)


    def isShellNode(self, node):
        return isShellImageNode(node)


    def replaceNodes(self, mat, shell):
        print("Replace shell image '%s' from material '%s'" % (shell.name, mat.name))
        tree = mat.node_tree
        texnode,name = getShellTexNode(shell)
        if texnode:
            if texnode.type == 'TEX_IMAGE':
                node = tree.nodes.new("ShaderNodeTexImage")
                node.image = texnode.image
                node.interpolation = texnode.interpolation
                node.hide = True
            else:
                node = tree.nodes.new("ShaderNodeGroup")
                node.node_tree = texnode.node_tree
        else:
            return
        node.label = texnode.label
        node.location = shell.location

        if shell.inputs:
            socket = shell.inputs[0]
            for link in socket.links:
                tree.links.new(link.from_socket, node.inputs["Vector"])
        for socket in shell.outputs:
            for link in socket.links:
                tree.links.new(node.outputs[socket.name], link.to_socket)
        tree.nodes.remove(shell)

#----------------------------------------------------------
#   Disable/Enable Shell Drivers
#----------------------------------------------------------

class ShellDisabler:
    columnWidth = 350

    def addItems(self, context):
        self.selection.clear()
        rig = getRigFromContext(context)
        for prop in rig.keys():
            if prop[0:6] == "INFLU ":
                item = self.selection.add()
                item.name = prop
                item.text = prop[6:]
                item.select = False


    def invoke(self, context, event):
        self.addItems(context)
        return self.invokeDialog(context)


    def run(self, context):
        rig = getRigFromContext(context)
        targets = {}
        for item in self.selection:
            if item.select:
                targets[propRef(item.name)] = rig[item.name]
        for ob in getMeshChildren(rig):
            self.setMesh(ob, rig, targets)


    def setMesh(self, ob, rig, targets):
        for mat in ob.data.materials:
            if mat and mat.node_tree and mat.node_tree.animation_data:
                for fcu in mat.node_tree.animation_data.drivers:
                    for var in fcu.driver.variables:
                        for trg in var.targets:
                            if trg.id == rig and trg.data_path in targets.keys():
                                self.setExpression(fcu, var, targets[trg.data_path])


class DAZ_OT_DisableShellDrivers(DazOperator, ShellDisabler, Selector, IsMeshArmature):
    bl_idname = "daz.disable_shell_drivers"
    bl_label = "Disable Shell Drivers"
    bl_description = "Disable drivers from selected shell from selected figures"
    bl_options = {'UNDO'}

    def setExpression(self, fcu, var, value):
        fcu.driver.expression = str(value)


class DAZ_OT_EnableShellDrivers(DazOperator, ShellDisabler, Selector, IsMeshArmature):
    bl_idname = "daz.enable_shell_drivers"
    bl_label = "Enable Shell Drivers"
    bl_description = "Enable drivers from selected shell from selected objects"
    bl_options = {'UNDO'}

    def setExpression(self, fcu, var, value):
        fcu.driver.expression = var.name

#----------------------------------------------------------
#   Remove All Influence
#----------------------------------------------------------

class DAZ_OT_RemoveAllInflus(DazOperator, IsArmature):
    bl_idname = "daz.remove_all_influs"
    bl_label = "Remove All Influence"
    bl_description = "Remove all influence properties"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        props = [key for key in rig.keys() if key.startswith("INFLU")]
        for ob in getMeshChildren(rig):
            for mat in ob.data.materials:
                if mat and mat.node_tree and mat.node_tree.animation_data:
                    drivers = mat.node_tree.animation_data.drivers
                    for fcu in list(drivers):
                        for var in fcu.driver.variables:
                            for trg in var.targets:
                                if trg.data_path.startswith('["INFLU '):
                                    drivers.remove(fcu)
        for prop in props:
            del rig[prop]

#----------------------------------------------------------
#   Update shell drivers
#----------------------------------------------------------

class DAZ_OT_UpdateShellDrivers(DazOperator, IsMesh):
    bl_idname = "daz.update_shell_drivers"
    bl_label = "Update Shell Drivers"
    bl_description = "Update drivers if problems"

    def run(self, context):
        updateShellDrivers(context)


def updateShellDrivers(context):
    from .driver import forceDriverUpdate
    ob = context.object
    rig = ob.parent
    if rig:
        rig.hide_viewport = False
    for mat in ob.data.materials:
        if mat:
            forceDriverUpdate(mat.node_tree)

#----------------------------------------------------------
#   Disable Normal Groups
#----------------------------------------------------------

class DAZ_OT_FixNormalGroups(DazPropsOperator, IsMesh):
    bl_idname = "daz.fix_normal_groups"
    bl_label = "Fix Normal Groups"
    bl_description = "Fix or disable normal groups from selected objects"
    bl_options = {'UNDO'}

    useDisable : BoolProperty(
        name = "Disable",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useDisable")

    def run(self, context):
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree.name.startswith("SLie Normal"):
                            self.fixNormalGroups(node.node_tree)

    def fixNormalGroups(self, tree):
        output = None
        for node in tree.nodes:
            if node.type == 'GROUP_OUTPUT':
                output = node
            elif node.type == 'TEX_IMAGE' and node.image:
                node.image.colorspace_settings.name = "Non-Color"
        if self.useDisable and output:
            tex = None
            for link in output.inputs["Alpha"].links:
                tex = link.from_node
                if tex and output:
                    tree.links.new(tex.outputs["Color"], output.inputs["Color"])

#----------------------------------------------------------
#   Set HSV
#----------------------------------------------------------

class DAZ_OT_SetHSV(MaterialSelector, DazPropsOperator):
    bl_idname = "daz.set_hsv"
    bl_label = "Set HSV"
    bl_description = "Set HSV values for shell image groups"
    bl_options = {'UNDO'}

    saturation : FloatProperty(
        name = "Saturation",
        min = 0.0, max = 2.0,
        default = 1.0)

    value : FloatProperty(
        name = "Value",
        min = 0.0, max = 2.0,
        default = 1.0)

    factor : FloatProperty(
        name = "Factor",
        min = 0.0, max = 2.0,
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "saturation")
        self.layout.prop(self, "value")
        self.layout.prop(self, "factor")
        MaterialSelector.draw(self, context)
        self.layout.operator("daz.update_materials")

    def run(self, context):
        ob = context.object
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                for node in mat.node_tree.nodes:
                    if (node.type == 'GROUP' and
                        "Saturation" in node.inputs.keys()):
                        node.inputs["Saturation"].default_value = self.saturation
                        node.inputs["Value"].default_value = self.value
                        node.inputs["Factor"].default_value = self.factor

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def isLayeredNode(node):
    return (node.type == 'GROUP' and
            node.node_tree.name.startswith("LIE"))

def isShellImageNode(node):
    return (node.type == 'GROUP' and
            node.node_tree.name.startswith(("SLIE", "SLie")))

def getShellTexNode(shell):
    for node in shell.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            return node, node.image.name
        elif isLayeredNode(node):
            return node, node.node_tree.name
    return None, None

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportShellsAsImages,
    DAZ_OT_RemoveShellImages,
    DAZ_OT_DisableShellDrivers,
    DAZ_OT_EnableShellDrivers,
    DAZ_OT_UpdateShellDrivers,
    DAZ_OT_FixNormalGroups,
    DAZ_OT_RemoveAllInflus,
    DAZ_OT_SetHSV,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
