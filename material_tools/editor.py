# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from collections import OrderedDict
from ..utils import *
from ..error import *
from ..propgroups import EditSlotGroup
from ..matsel import MaterialSelector
from ..tree import XSIZE, YSIZE, YSTEP, MixRGB, colorOutput, beautifyNodeTree
from ..material import WHITE, isWhite
from ..cycles import isGroupType
from ..pbr import PBR

# ---------------------------------------------------------------------
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, # components, comes from)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump And Normal", None),
    ("Bump Strength", ("BUMP", "Strength", 1)),
    ("Bump Distance", ("BUMP", "Distance", 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", 1)),

    ("Diffuse", None),
    ("Diffuse Color", ("DAZ Diffuse", "Color", 4)),
    ("Diffuse Roughness", ("DAZ Diffuse", "Roughness", 1)),
    ("Diffuse Strength", ("DAZ Diffuse", "Fac", 1)),

    ("Glossy", None),
    ("Glossy Color", ("DAZ Glossy", "Color", 4)),
    ("Glossy Roughness", ("DAZ Glossy", "Roughness", 1)),
    ("Glossy Strength", ("DAZ Glossy", "Fac", 1)),

    ("Fresnel", None),
    ("Fresnel IOR", ("DAZ Fresnel", "IOR", 1)),
    ("Fresnel Roughness", ("DAZ Fresnel", "Roughness", 1)),

    ("Dual Lobe", None),
    ("Dual Lobe Ratio", ("DAZ Dual Lobe", "Ratio", 1)),
    ("Dual Lobe IOR", ("DAZ Dual Lobe", "IOR", 1)),
    ("Dual Lobe Roughness 1", ("DAZ Dual Lobe", "Roughness 1", 1)),
    ("Dual Lobe Roughness 2", ("DAZ Dual Lobe", "Roughness 2", 1)),
    ("Dual Lobe Strength", ("DAZ Dual Lobe", "Fac", 1)),

    ("Dual Lobe PBR", None),
    ("Dual Lobe PBR Ratio", ("DAZ Dual Lobe PBR", "Ratio", 1)),
    ("Dual Lobe PBR IOR", ("DAZ Dual Lobe PBR", "IOR", 1)),
    ("Dual Lobe PBR Roughness 1", ("DAZ Dual Lobe PBR", "Roughness 1", 1)),
    ("Dual Lobe PBR Roughness 2", ("DAZ Dual Lobe PBR", "Roughness 2", 1)),
    ("Dual Lobe PBR Strength", ("DAZ Dual Lobe PBR", "Fac", 1)),

    ("Alt SSS", None),
    ("Alt SSS SSS Amount", ("DAZ Alt SSS", "SSS Amount", 1)),
    ("Alt SSS Diffuse Color", ("DAZ Alt SSS", "Diffuse Color", 4)),
    ("Alt SSS Translucent Color", ("DAZ Alt SSS", "Translucent Color", 4)),
    ("Alt SSS Translucency Weight", ("DAZ Alt SSS", "Translucency Weight", 1)),

    ("Subsurface", None),
    ("Subsurface Strength", ("DAZ Subsurface", "Fac", 1)),
    ("Subsurface Color", ("DAZ Subsurface", "Color", 4)),
    ("Subsurface Scale", ("DAZ Subsurface", "Scale", 1)),
    ("Subsurface Radius", ("DAZ Subsurface", "Radius", 3)),
    ("Subsurface IOR", ("DAZ Subsurface", "IOR", 1)),
    ("Subsurface Anisotropy", ("DAZ Subsurface", "Anisotropy", 1)),

    ("Translucency", None),
    ("Translucency Strength", ("DAZ Translucent", "Fac", 1)),
    ("Translucency Color", ("DAZ Translucent", "Color", 4)),

    ("Principled", None),
    ("Principled Base Color", ('BSDF_PRINCIPLED', "Base Color", 4)),
    ("Principled %s" % PBR.SubsurfWeight, ('BSDF_PRINCIPLED', PBR.SubsurfWeight, 1)),
    ("Principled Subsurface Radius", ('BSDF_PRINCIPLED', "Subsurface Radius", 3)),
    ("Principled Subsurface Scale", ('BSDF_PRINCIPLED', "Subsurface Scale", 1)),
    ("Principled Subsurface Color", ('BSDF_PRINCIPLED', "Subsurface Color", 4)),
    ("Principled Metallic", ('BSDF_PRINCIPLED', "Metallic", 1)),
    ("Principled %s" % PBR.Specular, ('BSDF_PRINCIPLED', PBR.Specular, 1)),
    ("Principled Specular Tint", ('BSDF_PRINCIPLED', "Specular Tint", PBR.TintComponents)),
    ("Principled Roughness", ('BSDF_PRINCIPLED', "Roughness", 1)),
    ("Principled Anisotropic", ('BSDF_PRINCIPLED', "Anisotropic", 1)),
    ("Principled Anisotropic Rotation", ('BSDF_PRINCIPLED', "Anisotropic Rotation", 1)),
    ("Principled %s" % PBR.SheenWeight, ('BSDF_PRINCIPLED', PBR.SheenWeight, 1)),
    ("Principled Sheen Tint", ('BSDF_PRINCIPLED', "Sheen Tint", PBR.TintComponents)),
    ("Principled %s" % PBR.CoatWeight, ('BSDF_PRINCIPLED', PBR.CoatWeight, 1)),
    ("Principled %s" % PBR.CoatRoughness, ('BSDF_PRINCIPLED', PBR.CoatRoughness, 1)),
    ("Principled Coat Tint", ('BSDF_PRINCIPLED', "Coat Tint", PBR.TintComponents)),
    ("Principled IOR", ('BSDF_PRINCIPLED', "IOR", 1)),
    ("Principled %s" % PBR.TransmitWeight, ('BSDF_PRINCIPLED', PBR.TransmitWeight, 1)),
    ("Principled Transmission Roughness", ('BSDF_PRINCIPLED', "Transmission Roughness", 1)),
    ("Principled %s" % PBR.EmitColor, ('BSDF_PRINCIPLED', PBR.EmitColor, 4)),
    ("Principled Emission Strength", ('BSDF_PRINCIPLED', "Emission Strength", 1)),
    ("Principled Alpha", ('BSDF_PRINCIPLED', "Alpha", 1)),

    ("Top Coat", None),
    ("Top Coat Color", ("DAZ Top Coat", "Color", 4)),
    ("Top Coat Roughness", ("DAZ Top Coat", "Roughness", 1)),
    ("Top Coat Anisotropy", ("DAZ Top Coat", "Anisotropy", 1)),
    ("Top Coat Rotation", ("DAZ Top Coat", "Rotation", 1)),
    ("Top Coat Strength", ("DAZ Top Coat", "Fac", 1)),

    ("Overlay", None),
    ("Overlay Color", ("DAZ Overlay", "Color", 4)),
    ("Overlay Roughness", ("DAZ Overlay", "Roughness", 1)),
    ("Overlay Strength", ("DAZ Overlay", "Fac", 1)),

    ("Metal Uber", None),
    ("Metal Uber Metallicity", ("DAZ Metal", "Fac", 1)),

    ("Metal PBR", None),
    ("Metal PBR Metallicity", ("DAZ Metal PBR", "Fac", 1)),

    ("Refraction", None),
    ("Refraction Color", ("DAZ Refraction", "Refraction Color", 4)),
    ("Refraction Roughness", ("DAZ Refraction", "Refraction Roughness", 1)),
    ("Refraction IOR", ("DAZ Refraction", "Refraction IOR", 1)),
    ("Refraction Fresnel IOR", ("DAZ Refraction", "Fresnel IOR", 1)),
    ("Refraction Glossy Color", ("DAZ Refraction", "Glossy Color", 4)),
    ("Refraction Glossy Roughness", ("DAZ Refraction", "Glossy Roughness", 1)),
    ("Refraction Strength", ("DAZ Refraction", "Fac", 1)),

    ("Transparent", None),
    ("Transparent Color", ("DAZ Transparent", "Color", 4)),
    ("Transparent Strength", ("DAZ Transparent", "Fac", 1)),

    ("Emission", None),
    ("Emission Color", ("DAZ Emission", "Color", 4)),
    ("Emission Strength", ("DAZ Emission", "Fac", 1)),

    ("Volume", None),
    ("Volume Absorption Color", ("DAZ Volume", "Absorbtion Color", 4)),
    ("Volume Absorption Density", ("DAZ Volume", "Absorbtion Density", 1)),
    ("Volume Scatter Color", ("DAZ Volume", "Scatter Color", 4)),
    ("Volume Scatter Density", ("DAZ Volume", "Scatter Density", 1)),
    ("Volume Scatter Anisotropy", ("DAZ Volume", "Scatter Anisotropy", 1)),

])

# ---------------------------------------------------------------------
#   Mini material editor
# ---------------------------------------------------------------------

def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))

# ---------------------------------------------------------------------
#   Channel setter
# ---------------------------------------------------------------------

def getTweakableChannel(cname):
    data = TweakableChannels[cname]
    if len(data) != 3:
        print("ERR", cname)
        halt
    return data


class ChannelSetter:
    useChangedOnly = False
    origSlots : CollectionProperty(type = EditSlotGroup)
    matSlots : CollectionProperty(type = EditSlotGroup)
    dirty = {}

    def setChannelCycles(self, mat, item):
        nodeType, slot, ncomps = getTweakableChannel(item.name)
        if self.useChangedOnly:
            value = self.getItemValue(ncomps, item)
            origItem = self.origSlots[item.name]
            origValue = self.getItemValue(ncomps, origItem)
            if value == origValue and not self.dirty.get(item.name):
                return
            self.dirty[item.name] = True

        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat):
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, mat, item.name)
                socket.default_value = self.getItemValue(ncomps, item)
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if not fromnode:
                    pass
                elif self.setNodeValue(node, fromnode, fromsocket, socket, mat, ncomps, item):
                    pass
                elif isGroupType(fromnode, "DAZ Log Color"):
                    self.ensureColor(ncomps, item)
                    fromnode.inputs["Color"].default_value = self.getItemValue(4, item)
                elif isGroupType(fromnode, ("DAZ Color Effect", "DAZ Tinted Effect")):
                    if slot == "Fac":
                        socket = fromnode.inputs["Fac"]
                        socket.default_value = self.getItemValue(1, item)
                    elif slot == "Color":
                        self.ensureColor(ncomps, item)
                        socket = fromnode.inputs["Color"]
                        socket.default_value = self.getItemValue(4, item)
                    for link in socket.links:
                        texnode = link.from_node
                        self.setNodeValue(fromnode, texnode, colorOutput(texnode), socket, mat, ncomps, item)


    def setNodeValue(self, node, fromnode, fromsocket, socket, mat, ncomps, item):
        if fromnode.type == 'MIX_RGB':
            self.ensureColor(ncomps, item)
            fromnode.inputs[MixRGB.LegacyColor1].default_value = self.getItemValue(4, item)
        elif fromnode.type == 'MIX':
            self.ensureColor(ncomps, item)
            fromnode.inputs[MixRGB.Color1].default_value = self.getItemValue(4, item)
        elif fromnode.type == 'MATH' and fromnode.operation == 'MULTIPLY':
            fromnode.inputs[0].default_value = self.getItemValue(1, item)
        elif fromnode.type == 'MATH' and fromnode.operation == 'MULTIPLY_ADD':
            fromnode.inputs[1].default_value = self.getItemValue(1, item)
        elif fromnode.type in ['TEX_IMAGE', 'GAMMA']:
            self.multiplyTex(node, fromsocket, socket, mat.node_tree, item)
        else:
            return False
        return True


    def ensureColor(self, ncomps, item):
        if ncomps == 1:
            ncomps = 4
            num = item.number
            item.color = (num,num,num,1)


    def addSlots(self, context):
        ob = context.object
        self.matSlots.clear()
        self.origSlots.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                continue
            value,ncomps = self.getEditChannel(ob, key)
            if ncomps == 0:
                continue
            item = self.matSlots.add()
            item.name = key
            item.ncomps = ncomps
            self.setItemValue(ncomps, item, value)
            item = self.origSlots.add()
            item.name = key
            item.ncomps = ncomps
            self.setItemValue(ncomps, item, value)


    def getItemValue(self, ncomps, item):
        if item.ncomps == 1:
            return self.getValue(item.number, ncomps)
        elif item.ncomps == 3:
            return self.getValue(item.vector, ncomps)
        elif item.ncomps == 4:
            return list(self.getValue(item.color, ncomps))


    def setItemValue(self, ncomps, item, value):
        if ncomps == 1:
            item.number = self.getValue(value, 1)
        elif ncomps == 3:
            item.vector = self.getValue(value, 3)
        elif ncomps == 4:
            item.color = self.getValue(value, 4)


    def getEditChannel(self, ob, key):
        from ..cycles import isTexImage
        nodeType, slot, ncomps = getTweakableChannel(key)
        mat = ob.active_material
        if not mat.use_nodes:
            return None,0
        for node in mat.node_tree.nodes.values():
            if (self.matchingNode(node, nodeType, mat) and
                slot in node.inputs.keys()):
                socket = node.inputs[slot]
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == 'MIX_RGB':
                        return fromnode.inputs[MixRGB.LegacyColor1].default_value, ncomps
                    elif fromnode.type == 'MIX':
                        return fromnode.inputs[MixRGB.Color1].default_value, ncomps
                    elif fromnode.type == 'MATH' and fromnode.operation == 'MULTIPLY':
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == 'GAMMA':
                        return fromnode.inputs[0].default_value, ncomps
                    elif isTexImage(fromnode):
                        return WHITE, ncomps
                    elif isGroupType(fromnode, "DAZ Log Color"):
                        return fromnode.inputs["Color"].default_value, ncomps
                    elif isGroupType(fromnode, ("DAZ Color Effect", "DAZ Tinted Effect")):
                        if slot.endswith("Color"):
                            slot = "Color"
                        return fromnode.inputs[slot].default_value, ncomps
                else:
                    return socket.default_value, ncomps
        return None,0


    def getValue(self, value, ncomps):
        if ncomps == 1:
            if isinstance(value, float):
                return value
            else:
                return value[0]
        elif ncomps == 3:
            if isinstance(value, float):
                return (value,value,value)
            elif len(value) == 3:
                return value
            elif len(value) == 4:
                return value[0:3]
        elif ncomps == 4:
            if isinstance(value, float):
                return (value,value,value,1)
            elif len(value) == 3:
                return (value[0],value[1],value[2],1)
            elif len(value) == 4:
                return value


    def inputDiffers(self, node, slot, value):
        if slot in node.inputs.keys():
            if node.inputs[slot].default_value != value:
                return True
        return False


    def getFromNode(self, mat, node, socket):
        for link in mat.node_tree.links.values():
            if link.to_node == node and link.to_socket == socket:
                return (link.from_node, link.from_socket)
        return None,None


    def matchingNode(self, node, nodeType, mat):
        if node.type == nodeType:
            return True
        elif (node.type == "GROUP" and
              nodeType in bpy.data.node_groups.keys()):
            return (node.node_tree == bpy.data.node_groups[nodeType])
        return False

# ---------------------------------------------------------------------
#   Launch button
# ---------------------------------------------------------------------

class ShowGroup(bpy.types.PropertyGroup):
    show : BoolProperty(default = False)


class DAZ_OT_LaunchEditor(MaterialSelector, DazPropsOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}

    shows : CollectionProperty(type = ShowGroup)

    useAllMaterials : BoolProperty(
        name = "All Materials",
        description = "Affect all materials of all selected meshes",
        default = False)

    useChangedOnly : BoolProperty(
        name = "Only Modified Channels",
        description = "Only update channels that have been modified by the material editor",
        default = True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "useAllMaterials")
        row.prop(self, "useChangedOnly")
        if not self.useAllMaterials:
            MaterialSelector.draw(self, context)
        self.drawActive(context)
        group = None
        items = []
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                if group:
                    self.drawGroup(group)
                items = []
                group = (key, items)
            elif key in self.matSlots.keys():
                items.append( (key, self.matSlots[key]) )
        if group:
            self.drawGroup(group)
        self.layout.operator("daz.update_materials")


    def drawGroup(self, group):
        section,items = group
        if not items:
            return
        elif not self.shows[section].show:
            self.layout.prop(self.shows[section], "show", icon="RIGHTARROW", emboss=False, text=section)
            return
        self.layout.prop(self.shows[section], "show", icon="DOWNARROW_HLT", emboss=False, text=section)
        nchars = len(section)
        for key,item in items:
            row = self.layout.row()
            if key[0:nchars] == section:
                text = item.name[nchars+1:]
            else:
                text = item.name
            row.label(text=text)
            if item.ncomps == 4:
                row.prop(item, "color", text="")
            elif item.ncomps == 1:
                row.prop(item, "number", text="")
            elif item.ncomps == 3:
                row.prop(item, "vector", text="")
            else:
                print("WAHT")


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        self.shows.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                item = self.shows.add()
                item.name = key
                item.show = False
                continue
        self.addSlots(context)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def run(self, context):
        ob = context.object
        for ob1 in getSelectedMeshes(context):
            for item in self.matSlots:
                self.setEditChannel(ob1, item)


    def setEditChannel(self, ob, item):
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.setChannelCycles(mat, item)
                beautifyNodeTree(mat.node_tree)


    def getObjectSlot(self, mat, key):
        for item in dazRna(mat).DazSlots:
            if item.name == key:
                return item
        item = dazRna(mat).DazSlots.add()
        item.name = key
        item.new = True
        return item


    def setOriginal(self, socket, ncomps, mat, key):
        item = self.getObjectSlot(mat, key)
        if item.new:
            value = socket.default_value
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            item.new = False


    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        x,y = node.location
        if item.ncomps == 4 and not isWhite(item.color):
            mix = tree.nodes.new(type = MixRGB.Nodetype)
            mix.location = (x-XSIZE+50,y-12*YSTEP)
            mix.blend_type = 'MULTIPLY'
            if bpy.app.version >= (3,4,0):
                mix.data_type = 'RGBA'
            mix.inputs[0].default_value = 1.0
            mix.inputs[MixRGB.Color1].default_value = item.color
            tree.links.new(fromsocket, mix.inputs[MixRGB.Color2])
            tree.links.new(mix.outputs[MixRGB.ColorOut], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type = "ShaderNodeMath")
            mult.location = (x-XSIZE+50,y-12*YSTEP)
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.links.new(fromsocket, mult.inputs[1])
            tree.links.new(mult.outputs[0], tosocket)
            return mult

# ---------------------------------------------------------------------
#   Reset button
# ---------------------------------------------------------------------

class DAZ_OT_ResetMaterials(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_materials"
    bl_label = "Reset Materials"
    bl_description = "Reset materials to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.resetObject(ob)


    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                for item in dazRna(mat).DazSlots:
                    self.setChannelCycles(mat, item)
                    item.new = True
                dazRna(mat).DazSlots.clear()


    def setOriginal(self, socket, ncomps, item, key):
        pass

    def useMaterial(self, mat):
        return True

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        pass

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    ShowGroup,
    DAZ_OT_LaunchEditor,
    DAZ_OT_ResetMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
