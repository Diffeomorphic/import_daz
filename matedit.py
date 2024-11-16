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

import bpy
import os
import math
from mathutils import Vector

from .error import *
from .utils import *
from .material import WHITE, NORMAL, isWhite
from .cycles import isGroupType
from .pbr import PBR
from collections import OrderedDict
from .fileutils import SingleFile, ImageFile
from .tree import TNode, getSocket, XSIZE, YSIZE, YSTEP, MixRGB, colorOutput, beautifyNodeTree
from .propgroups import DazIntGroup, DazFloatGroup

#-------------------------------------------------------------
#   Material selector
#-------------------------------------------------------------

def getMaterialSelector():
    global theMaterialSelector
    return theMaterialSelector


def setMaterialSelector(selector):
    global theMaterialSelector
    theMaterialSelector = selector


class DazMaterialGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


class MaterialSelector:
    umats : CollectionProperty(type = DazMaterialGroup)
    useAllMaterials = False

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.active_material)


    def draw(self, context):
        row = self.layout.row()
        row.operator("daz.select_all_materials")
        row.operator("daz.select_no_material")
        row = self.layout.row()
        row.operator("daz.select_skin_materials")
        row.operator("daz.select_skin_red_materials")
        umats = self.umats
        while umats:
            row = self.layout.row()
            row.prop(umats[0], "bool", text=umats[0].name)
            if len(umats) > 1:
                row.prop(umats[1], "bool", text=umats[1].name)
                umats = umats[2:]
            else:
                umats = []


    def drawActive(self, context):
        ob = context.object
        box = self.layout.box()
        box.label(text="Active Material: %s" % ob.active_material.name)
        self.layout.separator()


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        return DazPropsOperator.invoke(self, context, event)


    def setupMaterialSelector(self, context):
        from .guess import getMaterialType
        global theMaterialEditor
        theMaterialEditor = self
        ob = context.object
        self.skinColor = WHITE
        for mat in ob.data.materials:
            if mat and getMaterialType(mat) == 'SKIN':
                self.skinColor = mat.diffuse_color[0:3]
                break
        self.umats.clear()
        for mat in ob.data.materials:
            if mat:
                item = self.umats.add()
                item.name = mat.name
                item.bool = self.isDefaultActive(mat, ob)
        setMaterialSelector(self)


    def isDefaultActive(self, mat, ob):
        return False


    def useMaterial(self, mat):
        if self.useAllMaterials:
            return True
        elif mat.name in self.umats.keys():
            item = self.umats[mat.name]
            return item.bool
        else:
            return False


    def selectAll(self, context):
        for item in self.umats.values():
            item.bool = True

    def selectNone(self, context):
        for item in self.umats.values():
            item.bool = False

    def selectSkin(self, context):
        ob = context.object
        for mat,item in zip(ob.data.materials, self.umats.values()):
            if mat.DazMaterialType:
                item.bool = (mat.DazMaterialType == 'SKIN')
            else:
                item.bool = (mat.diffuse_color[0:3] == self.skinColor)

    def selectSkinRed(self, context):
        ob = context.object
        for mat,item in zip(ob.data.materials, self.umats.values()):
            item.bool = self.isSkinRedMaterial(mat)

    def isSkinRedMaterial(self, mat):
        if mat.DazMaterialType:
            return (mat.DazMaterialType in ['SKIN', 'RED'])
        elif mat.diffuse_color[0:3] == self.skinColor:
            return True
        from .guess import getMaterialType
        return (getMaterialType(mat) == 'RED')

#-------------------------------------------------------------
#   Select all and none
#-------------------------------------------------------------

class DAZ_OT_SelectAllMaterials(bpy.types.Operator):
    bl_idname = "daz.select_all_materials"
    bl_label = "All"
    bl_description = "Select all materials"

    def execute(self, context):
        getMaterialSelector().selectAll(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectSkinMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_materials"
    bl_label = "Skin"
    bl_description = "Select skin materials"

    def execute(self, context):
        getMaterialSelector().selectSkin(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectSkinRedMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_red_materials"
    bl_label = "Skin-Lips-Nails"
    bl_description = "Select all skin or red materials"

    def execute(self, context):
        getMaterialSelector().selectSkinRed(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectNoMaterial(bpy.types.Operator):
    bl_idname = "daz.select_no_material"
    bl_label = "None"
    bl_description = "Select no material"

    def execute(self, context):
        getMaterialSelector().selectNone(context)
        return {'PASS_THROUGH'}

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

class EditSlotGroup(bpy.types.PropertyGroup):
    ncomps : IntProperty(default = 0)

    color : FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0, max = 1.0,
        default = (1,1,1,1)
    )

    vector : FloatVectorProperty(
        name = "Vector",
        size = 3,
        precision = 4,
        min = 0.0,
        default = (0,0,0)
    )

    number : FloatProperty(default = 0.0, precision=4)
    new : BoolProperty()


class ShowGroup(bpy.types.PropertyGroup):
    show : BoolProperty(default = False)


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
        from .cycles import isTexImage
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

#----------------------------------------------------------
#   Drive shell influence
#----------------------------------------------------------

class DAZ_OT_SetShellInfluence(DazOperator, IsMeshArmature):
    bl_idname = "daz.set_shell_influence"
    bl_label = "Set Shell Influence"

    value : FloatProperty()

    def run(self, context):
        props = getShellProps(context)
        for prop,ob in props:
            ob[prop] = self.value
        updateDrivers(ob)


def getShellProps(context):
    filter = context.scene.DazFilter.lower()
    rig = getRigFromContext(context)
    if rig:
        objects = [rig] + [ob for ob in rig.children if ob.DazVisibilityDrivers]
    else:
        objects = [context.object]
    props = {}
    for ob in objects:
        for prop in ob.keys():
            if (prop[0:6] == "INFLU " and
                filter in prop[6:].lower() and
                prop not in props.keys()):
                props[prop] = ob
    return list(props.items())


class DAZ_OT_ToggleShellInfluence(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_shell_influence"
    bl_label = "Toggle Shell Influence"

    prop : StringProperty()
    object : StringProperty()

    def run(self, context):
        ob = bpy.data.objects.get(self.object)
        if ob is None:
            return
        elif ob[self.prop] > 0:
            ob[self.prop] = 0.0
        else:
            ob[self.prop] = 1.0
        updateDrivers(ob)


def driveShellInfluence(ob):
    from .driver import setFloatProp, addDriver
    rig = ob
    if ob.parent and ob.parent.type == 'ARMATURE':
        rig = ob.parent
        rig.hide_viewport = False
    for mat in ob.data.materials:
        if mat and mat.node_tree:
            for node in mat.node_tree.nodes:
                if isShellNode(node):
                    prop = "INFLU %s" % node.label
                    setFloatProp(rig, prop, 1.0, 0.0, 10.0, True)
                    addDriver(node.inputs["Influence"], "default_value", rig, propRef(prop), "x")
                    ob.DazVisibilityDrivers = rig.DazVisibilityDrivers = True


ShellInputs = ["Influence", "BSDF", "UV", "Displacement"]
ShellOutputs = ["BSDF", "Displacement"]

def isShellNode(node):
    def hasSlots(data, slots):
        for slot in slots:
            if slot not in data:
                return False
        return True

    if isinstance(node, bpy.types.NodeTree):
        from .tree import getGroupInputs, getGroupOutputs
        inputs = getGroupInputs(node)
        outputs = getGroupOutputs(node)
    elif (node.type == 'GROUP' and
          not node.name.startswith("DAZ ")):
        inputs = node.inputs.keys()
        outputs = node.outputs.keys()
    else:
        return False
    return (hasSlots(inputs, ShellInputs) and
            hasSlots(outputs, ShellOutputs))

#----------------------------------------------------------
#   UV utilities
#----------------------------------------------------------

def findUvlayers(mat, uvlayers):
    for node in mat.node_tree.nodes.values():
        if node.type == 'ATTRIBUTE':
            uvlayers[node.attribute_name] = True
        elif node.type == 'UVMAP':
            uvlayers[node.uv_map] = True
        elif node.type == 'NORMAL_MAP':
            uvlayers[node.uv_map] = True


def fixMaterialUvs(mats, uvset):
    for mat in mats:
        tree = mat.node_tree
        if tree is None:
            continue
        texcos = []
        for node in tree.nodes:
            if node.type == 'NORMAL_MAP':
                node.uv_map = uvset
            elif node.type == 'UVMAP':
                node.uv_map = uvset
            elif node.type == 'ATTRIBUTE':
                node.attribute_name = uvset
            elif node.type == 'TEX_COORD':
                texcos.append(node)
                attr = tree.nodes.new("ShaderNodeAttribute")
                attr.location = node.location
                attr.attribute_name = uvset
                for socket in node.outputs:
                    for link in list(socket.links):
                        tree.links.new(attr.outputs["Vector"], link.to_socket)
        for texco in texcos:
            tree.nodes.remove(texco)


#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazMaterialGroup,
    EditSlotGroup,
    ShowGroup,
    DAZ_OT_SelectAllMaterials,
    DAZ_OT_SelectNoMaterial,
    DAZ_OT_SelectSkinMaterials,
    DAZ_OT_SelectSkinRedMaterials,
    DAZ_OT_SetShellInfluence,
    DAZ_OT_ToggleShellInfluence,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Material.DazSlots = CollectionProperty(type = EditSlotGroup)
    #bpy.types.Object.DazSlots = CollectionProperty(type = EditSlotGroup)
    bpy.types.Scene.DazFloats = CollectionProperty(type = DazFloatGroup)

    bpy.types.Scene.DazFilter = StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
    )


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
