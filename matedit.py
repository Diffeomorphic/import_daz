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
from mathutils import Vector

from .error import *
from .utils import *
from .material import WHITE, isWhite
from .cycles import XSIZE, YSIZE
from collections import OrderedDict
from .fileutils import SingleFile, ImageFile

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


    def setupMaterials(self, ob):
        from .guess import getMaterialType
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
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1, None)),
    ("Bump Distance", ("BUMP", "Distance", 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1, None)),

    ("Diffuse", None),
    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", 4)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", 1)),

    ("Glossy", None),
    ("Glossy Color", ("DAZ Glossy", "Color", 4)),
    ("Glossy Roughness", ("DAZ Glossy", "Roughness", 1)),
    ("Glossy Strength", ("DAZ Glossy", "Fac", 1)),

    ("Fresnel", None),
    ("Fresnel IOR", ("DAZ Fresnel 2", "IOR", 1)),
    ("Fresnel Roughness", ("DAZ Fresnel 2", "Roughness", 1)),

    ("Dual Lobe Uber", None),
    ("Dual Lobe Uber Weight", ("DAZ Dual Lobe Uber", "Weight", 1)),
    ("Dual Lobe Uber IOR", ("DAZ Dual Lobe Uber", "IOR", 1)),
    ("Dual Lobe Uber Roughness 1", ("DAZ Dual Lobe Uber", "Roughness 1", 1)),
    ("Dual Lobe Uber Roughness 2", ("DAZ Dual Lobe Uber", "Roughness 2", 1)),
    ("Dual Lobe Uber Strength", ("DAZ Dual Lobe Uber", "Fac", 1)),

    ("Dual Lobe PBR", None),
    ("Dual Lobe PBR Weight", ("DAZ Dual Lobe PBR", "Weight", 1)),
    ("Dual Lobe PBR IOR", ("DAZ Dual Lobe PBR", "IOR", 1)),
    ("Dual Lobe PBR Roughness 1", ("DAZ Dual Lobe PBR", "Roughness 1", 1)),
    ("Dual Lobe PBR Roughness 2", ("DAZ Dual Lobe PBR", "Roughness 2", 1)),
    ("Dual Lobe PBR Strength", ("DAZ Dual Lobe PBR", "Fac", 1)),

    ("Translucency", None),
    ("Translucency Color", ("DAZ Translucent", "Color", 4)),
    ("Translucency Gamma", ("DAZ Translucent", "Gamma", 1)),
    ("Translucency Strength", ("DAZ Translucent", "Fac", 1)),
    ("Translucency Scale", ("DAZ Translucent", "Scale", 1)),
    ("Translucency Radius", ("DAZ Translucent", "Radius", 3)),
    ("Translucency Cycles Mix Factor", ("DAZ Translucent", "Cycles Mix Factor", 1)),
    ("Translucency Eevee Mix Factor", ("DAZ Translucent", "Eevee Mix Factor", 1)),

    ("Principled", None),
    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", 4)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", 1)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", 3)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", 4)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", 1)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", 1)),
    ("Principled Specular Tint", ("BSDF_PRINCIPLED", "Specular Tint", 1)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", 1)),
    ("Principled Anisotropic", ("BSDF_PRINCIPLED", "Anisotropic", 1)),
    ("Principled Anisotropic Rotation", ("BSDF_PRINCIPLED", "Anisotropic Rotation", 1)),
    ("Principled Sheen", ("BSDF_PRINCIPLED", "Sheen", 1)),
    ("Principled Sheen Tint", ("BSDF_PRINCIPLED", "Sheen Tint", 1)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", 1)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", 1)),
    ("Principled IOR", ("BSDF_PRINCIPLED", "IOR", 1)),
    ("Principled Transmission", ("BSDF_PRINCIPLED", "Transmission", 1)),
    ("Principled Transmission Roughness", ("BSDF_PRINCIPLED", "Transmission Roughness", 1)),
    ("Principled Emission", ("BSDF_PRINCIPLED", "Emission", 4)),
    ("Principled Emission Strength", ("BSDF_PRINCIPLED", "Emission Strength", 1)),
    ("Principled Alpha", ("BSDF_PRINCIPLED", "Alpha", 1)),

    ("Top Coat", None),
    ("Top Coat Color", ("DAZ Top Coat", "Color", 4)),
    ("Top Coat Roughness", ("DAZ Top Coat", "Roughness", 1)),
    ("Top Coat Bump", ("DAZ Top Coat", "Bump", 1)),
    ("Top Coat Distance", ("DAZ Top Coat", "Distance", 1)),

    ("Overlay", None),
    ("Overlay Color", ("DAZ Overlay", "Color", 4)),
    ("Overlay Roughness", ("DAZ Overlay", "Roughness", 1)),
    ("Overlay Strength", ("DAZ Overlay", "Fac", 1)),

    ("Metal Uber", None),
    ("Metallicity", ("DAZ Metal Uber", "Fac", 1)),

    ("Metal PBR", None),
    ("Metallicity", ("DAZ Metal PBR", "Fac", 1)),

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
    ("Emission Strength", ("DAZ Emission", "Strength", 1)),
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
    if len(data) == 6:
        return data
    else:
        nodeType, slot, ncomps = data
        return (nodeType, slot, None, None, ncomps, None)


class ChannelSetter:
    useChangedOnly = False
    origSlots : CollectionProperty(type = EditSlotGroup)
    matSlots : CollectionProperty(type = EditSlotGroup)

    def setChannelCycles(self, mat, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = getTweakableChannel(item.name)
        if self.useChangedOnly:
            value = self.getItemValue(ncomps, item)
            origItem = self.origSlots[item.name]
            origValue = self.getItemValue(ncomps, origItem)
            if value == origValue:
                return

        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat, fromType):
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, mat, item.name)
                socket.default_value = self.getItemValue(ncomps, item)
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type in "MIX_RGB":
                        self.ensureColor(ncomps, item)
                        fromnode.inputs[1].default_value = self.getItemValue(4, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        fromnode.inputs[0].default_value = self.getItemValue(1, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY_ADD':
                        fromnode.inputs[1].default_value = self.getItemValue(1, item)
                    elif fromnode.type in ["TEX_IMAGE", "GAMMA"]:
                        self.multiplyTex(node, fromsocket, socket, mat.node_tree, item)


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
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = getTweakableChannel(key)
        mat = ob.active_material
        if not mat.use_nodes:
            return None,0
        for node in mat.node_tree.nodes.values():
            if (self.matchingNode(node, nodeType, mat, fromType) and
                slot in node.inputs.keys()):
                socket = node.inputs[slot]
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        return fromnode.inputs[1].default_value, ncomps
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "GAMMA":
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "TEX_IMAGE":
                        return WHITE, ncomps
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


    def matchingNode(self, node, nodeType, mat, fromType):
        if node.type == nodeType:
            if fromType is None:
                return True
            for link in mat.node_tree.links.values():
                if link.to_node == node and link.from_node.type == fromType:
                    return True
            return False
        elif (node.type == "GROUP" and
            nodeType in bpy.data.node_groups.keys()):
            return (node.node_tree == bpy.data.node_groups[nodeType])
        return False

# ---------------------------------------------------------------------
#   Launch button
# ---------------------------------------------------------------------

class DAZ_OT_LaunchEditor(DazPropsOperator, MaterialSelector, ChannelSetter, IsMesh):
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
        ob = context.object
        self.layout.label(text="Active Material: %s" % ob.active_material.name)
        self.layout.separator()
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
        global theMaterialEditor
        theMaterialEditor = self
        ob = context.object
        self.setupMaterials(ob)
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


    def getObjectSlot(self, mat, key):
        for item in mat.DazSlots:
            if item.name == key:
                return item
        item = mat.DazSlots.add()
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
            mix = tree.nodes.new(type = "ShaderNodeMixRGB")
            mix.location = (x-XSIZE+50,y-YSIZE-50)
            mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            mix.inputs[1].default_value = item.color
            tree.links.new(fromsocket, mix.inputs[2])
            tree.links.new(mix.outputs[0], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type = "ShaderNodeMath")
            mult.location = (x-XSIZE+50,y-YSIZE-50)
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.links.new(fromsocket, mult.inputs[1])
            tree.links.new(mult.outputs[0], tosocket)
            return mult


class DAZ_OT_UpdateMaterials(bpy.types.Operator):
    bl_idname = "daz.update_materials"
    bl_label = "Update Materials"
    bl_description = "Update Materials"

    def execute(self, context):
        global theMaterialEditor
        theMaterialEditor.run(context)
        return {'PASS_THROUGH'}

# ---------------------------------------------------------------------
#   Make Decal
# ---------------------------------------------------------------------

def getEmptyName(scn, context):
    ob = context.object
    enums = [('NONE', "None", "None")]
    for child in ob.children:
        if child.type == 'EMPTY':
            enums.append((child.name, child.name, child.name))
    return enums


class DAZ_OT_MakeDecal(DazOperator, ImageFile, SingleFile, MaterialSelector, IsMesh):
    bl_idname = "daz.make_decal"
    bl_label = "Make Decal"
    bl_description = "Add a decal to the active material"
    bl_options = {'UNDO'}

    channel : EnumProperty(
        items = [("Diffuse", "Diffuse Color", "Diffuse Color"),
                 ("Glossy", "Glossy Color", "Glossy Color"),
                 ("Translucency", "Translucency Color", "Translucency Color"),
                 ("SSS", "Subsurface Color", "Subsurface Color"),
                 ("PBase", "Principled Base Color", "Principled Base Color"),
                 ("PSSS", "Principled Subsurface Color", "Principled Subsurface Color"),
                 ("Bump", "Bump", "Bump"),
                ],
        name = "Channel",
        description = "Add decal to this channel",
        default = "Diffuse")

    slots = {
        "Diffuse" : ("BSDF_DIFFUSE", "Color"),
        "Glossy" : ("DAZ Glossy", "Color"),
        "Translucency" : ("DAZ Translucent", "Color"),
        "SSS" : ("DAZ SSS", "Color"),
        "PBase" : ("BSDF_PRINCIPLED", "Base Color"),
        "PSSS" : ("BSDF_PRINCIPLED", "Subsurface Color"),
        "Bump" : ("BUMP", "Height"),
    }

    reuseEmpty : BoolProperty(
        name = "Reuse Empty",
        description = "Reuse an existing empty instead of creating a new one",
        default = False)

    emptyName : EnumProperty(
        items = getEmptyName,
        name = "Empty",
        description = "Empty to reuse")

    useMask : BoolProperty(
        name = "Use Mask",
        description = "Use a separate texture to mask the decal",
        default = False)

    decalMask : StringProperty(
        name = "Decal Mask",
        description = "Path to decal mask texture",
        default = "")

    blendType : EnumProperty(
        items = [('MIX', "Mix", "Mix"),
                 ('MULTIPLY', "Multiply", "Multiply")],
        name = "Blend Type",
        description = "Type of blending decal with skin",
        default = 'MIX')

    def draw(self, context):
        MaterialSelector.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "channel")
        self.layout.prop(self, "reuseEmpty")
        if self.reuseEmpty:
            self.layout.prop(self, "emptyName")
        self.layout.prop(self, "useMask")
        if self.useMask:
            self.layout.prop(self, "decalMask")
        self.layout.prop(self, "blendType")


    def invoke(self, context, event):
        global theMaterialEditor
        theMaterialEditor = self
        self.setupMaterials(context.object)
        self.decalMask = context.scene.DazDecalMask
        return SingleFile.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return (ob.active_material == mat)


    def run(self, context):
        img = bpy.data.images.load(self.filepath)
        if img is None:
            raise DazError("Unable to load file %s" % self.filepath)
        img.colorspace_settings.name = "sRGB"

        mask = None
        if self.useMask:
            maskname = os.path.basename(self.decalMask)
            if maskname in bpy.data.images.keys():
                mask = bpy.data.images[maskname]
            else:
                mask = bpy.data.images.load(self.decalMask)
            if mask is None:
                raise DazError("Unable to load mask file %s" % self.decalMask)
            mask.colorspace_settings.name = "Non-Color"

        ob = context.object
        ob.DazVisibilityDrivers = True
        fname = os.path.splitext(os.path.basename(self.filepath))[0]
        if self.reuseEmpty and self.emptyName != 'NONE':
            empty = bpy.data.objects[self.emptyName]
        else:
            empty = bpy.data.objects.new(fname, None)
            empty.parent = ob
            empty.rotation_euler = (0, 0, 0)
            empty.scale = (1, 0.2, 1)
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 0.25
            coll = getCollection(ob)
            coll.objects.link(empty)
        self.force = True
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.loadDecal(mat, img, empty, mask, fname)


    def loadDecal(self, mat, img, empty, mask, fname):
        def getFromToSockets(tree, nodeType, slot):
            from .tree import findNodes
            for link in tree.links.values():
                node = link.to_node
                if node:
                    if (node.type == nodeType or
                        (node.type == 'GROUP' and node.node_tree.name == nodeType)):
                        if link.to_socket == node.inputs[slot]:
                            return link.from_socket, link.to_socket, node.location
            nodes = findNodes(tree, nodeType)
            if nodes:
                node = nodes[0]
                return None, node.inputs[slot], node.location
            return None, None, None

        from .cgroup import DecalGroup
        from .cycles import findTree
        tree = findTree(mat)
        nodeType,slot = self.slots[self.channel]
        fromSocket, toSocket, loc = getFromToSockets(tree, nodeType, slot)
        if toSocket is None:
            raise DazError("Channel %s not found (%s)" % (self.channel, nodeType))
        nname = "%s_%s" % (fname, self.channel)
        node = tree.addGroup(DecalGroup, nname, args=[empty, img, mask, self.blendType], force=self.force)
        node.label = empty.name
        self.force = False
        node.location = (loc[0]-XSIZE, 3*YSIZE)
        node.inputs["Influence"].default_value = 1.0
        if fromSocket:
            tree.links.new(fromSocket, node.inputs["Color"])
        else:
            rgb = tree.addNode("ShaderNodeRGB")
            rgb.location = (loc[0]-2*XSIZE, 3*YSIZE)
            rgb.outputs["Color"].default_value = toSocket.default_value
            tree.links.new(rgb.outputs["Color"], node.inputs["Color"])
        tree.links.new(node.outputs["Combined"], toSocket)

# ---------------------------------------------------------------------
#   Reset button
# ---------------------------------------------------------------------

class DAZ_OT_ResetMaterial(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.resetObject(ob)


    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                for item in mat.DazSlots:
                    self.setChannelCycles(mat, item)
                    item.new = True
                mat.DazSlots.clear()


    def setOriginal(self, socket, ncomps, item, key):
        pass

    def useMaterial(self, mat):
        return True

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        pass

# ---------------------------------------------------------------------
#   Set Shell Visibility
# ---------------------------------------------------------------------

class DAZ_OT_SetShellVisibility(DazPropsOperator, IsMesh):
    bl_idname = "daz.set_shell_visibility"
    bl_label = "Set Shell Visibility"
    bl_description = "Control the visility of geometry shells"
    bl_options = {'UNDO'}

    useInsertKey : BoolProperty(
        name = "Insert Keys",
        description = "Insert keys at the current frame",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useInsertKey")
        for item in context.scene.DazFloats:
            self.layout.prop(item, "f", text=item.name)

    def run(self, context):
        scn = context.scene
        for item in scn.DazFloats:
            for node in self.shells[item.name]:
                node.inputs["Influence"].default_value = item.f
                if self.useInsertKey:
                    node.inputs["Influence"].keyframe_insert("default_value")

    def invoke(self, context, event):
        self.shells = {}
        scn = context.scene
        scn.DazFloats.clear()
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    for node in mat.node_tree.nodes:
                        if (node.type == 'GROUP' and
                            "Influence" in node.inputs.keys()):
                            key = node.label
                            if key not in self.shells.keys():
                               self.shells[key] = []
                               item = scn.DazFloats.add()
                               item.name = key
                               item.f = node.inputs["Influence"].default_value
                            self.shells[key].append(node)
        return DazPropsOperator.invoke(self, context, event)

# ---------------------------------------------------------------------
#   Remove shells from materials
# ---------------------------------------------------------------------

from .morphing import Selector

class ShellRemover:
    def getShells(self, context):
        ob = context.object
        self.shells = {}
        for mat in ob.data.materials:
            if mat:
                for node in mat.node_tree.nodes:
                    if (node.type == 'GROUP' and
                        "Influence" in node.inputs.keys()):
                        self.addShell(mat, node, node.node_tree)


    def addShell(self, mat, shell, tree):
        data = (mat,shell)
        if tree.name in self.shells.keys():
            struct = self.shells[tree.name]
            if mat.name in struct.keys():
                struct[mat.name].append(data)
            else:
                struct[mat.name] = [data]
        else:
            self.shells[tree.name] = {mat.name : [data]}


    def deleteNodes(self, mat, shell):
        print("Delete shell '%s' from material '%s'" % (shell.name, mat.name))
        linkFrom = {}
        linkTo = {}
        tree = mat.node_tree
        for link in tree.links:
            if link.to_node == shell:
                linkFrom[link.to_socket.name] = link.from_socket
            if link.from_node == shell:
                linkTo[link.from_socket.name] = link.to_socket
        for key in linkFrom.keys():
            if key in linkTo.keys():
                tree.links.new(linkFrom[key], linkTo[key])
        tree.nodes.remove(shell)


class DAZ_OT_RemoveShells(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.remove_shells"
    bl_label = "Remove Shells"
    bl_description = "Remove selected shells from active object"
    bl_options = {'UNDO'}

    columnWidth = 350

    def run(self, context):
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat,node in data:
                    self.deleteNodes(mat, node)


    def invoke(self, context, event):
        self.getShells(context)
        self.selection.clear()
        for name,nodes in self.shells.items():
                item = self.selection.add()
                item.name = name
                item.text = name
                item.select = False
        return self.invokeDialog(context)


class DAZ_OT_ReplaceShells(DazPropsOperator, ShellRemover, IsMesh):
    bl_idname = "daz.replace_shells"
    bl_label = "Replace Shells"
    bl_description = "Display shell node groups so they can be displaced."
    bl_options = {'UNDO'}

    dialogWidth = 800

    def draw(self, context):
        rows = []
        n = 0
        for tname,struct in self.shells.items():
            for mname,data in struct.items():
                for mat,node in data:
                    rows.append((node.name, n, node))
                    n += 1
        rows.sort()
        for nname,n,node in rows:
            row = self.layout.row()
            row.label(text=nname)
            row.prop(node, "node_tree")


    def run(self, context):
        pass


    def invoke(self, context, event):
        self.getShells(context)
        return DazPropsOperator.invoke(self, context, event)

#-------------------------------------------------------------
#   Change unit scale
#-------------------------------------------------------------

class DAZ_OT_ChangeUnitScale(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.change_unit_scale"
    bl_label = "Change Unit Scale"
    bl_description = "Safely change the unit scale of selected object and children"
    bl_options = {'UNDO'}

    unit : FloatProperty(
        name = "New Unit Scale",
        description = "Scale used to convert between DAZ and Blender units. Default unit meters",
        default = 0.01,
        precision = 3,
        min = 0.001, max = 100.0)

    def draw(self, context):
        self.layout.prop(self, "unit")

    def invoke(self, context, event):
        if context.object:
            self.unit = context.object.DazScale
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        ob = context.object
        while ob.parent:
            ob = ob.parent
        self.meshes = []
        self.rigs = []
        self.parents = {}
        self.addObjects(ob)
        for ob in self.meshes:
            self.applyScale(context, ob)
            self.fixMesh(ob)
        for rig in self.rigs:
            self.applyScale(context, rig)
            self.fixRig(rig)
        for rig in self.rigs:
            self.restoreParent(context, rig)
        for ob in self.meshes:
            self.restoreParent(context, ob)


    def addObjects(self, ob):
        if ob.type == 'MESH':
            if ob not in self.meshes:
                self.meshes.append(ob)
        elif ob.type == 'ARMATURE':
            if ob not in self.rigs:
                self.rigs.append(ob)
        for child in ob.children:
            self.addObjects(child)


    def applyScale(self, context, ob):
        scale = self.unit / ob.DazScale
        if activateObject(context, ob):
            self.parents[ob.name] = (ob.parent, ob.parent_type, ob.parent_bone)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            lock = list(ob.lock_scale)
            ob.lock_scale = (False,False,False)
            ob.scale *= scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


    def fixRig(self, rig):
        scale = self.unit / rig.DazScale
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'STRETCH_TO':
                    cns.rest_length *= scale


    def fixMesh(self, ob):
        scale = self.unit / ob.DazScale
        for mat in ob.data.materials:
            if mat:
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP':
                        self.fixNode(node, node.node_tree.name, scale)
                    else:
                        self.fixNode(node, node.type, scale)


    NodeScale = {
        "BUMP" : ["Distance"],
        "PRINCIPLED" : ["Subsurface Radius"],
        "DAZ Translucent" : ["Radius"],
        "DAZ Top Coat" : ["Distance"],
    }

    def fixNode(self, node, nodetype, scale):
        if nodetype in self.NodeScale.keys():
            for sname in self.NodeScale[nodetype]:
                socket = node.inputs[sname]
                if isinstance(socket.default_value, float):
                    socket.default_value *= scale
                else:
                    socket.default_value = scale*Vector(socket.default_value)


    def restoreParent(self, context, ob):
        ob.DazScale = self.unit
        if ob.name in self.parents.keys():
            wmat = ob.matrix_world.copy()
            (ob.parent, ob.parent_type, ob.parent_bone) = self.parents[ob.name]
            setWorldMatrix(ob, wmat)

#-------------------------------------------------------------
#   Make Material set
#-------------------------------------------------------------

class DAZ_OT_MakePalette(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_palette"
    bl_label = "Make Palette"
    bl_description = "Create a palette for use with the asset browser"
    bl_options = {'UNDO'}

    useMarkAsAsset : BoolProperty(
        name = "Mark As Asset",
        description = "Mark the palette for the asset browser and make all materials unique",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useMarkAsAsset")

    def run(self, context):
        ob = context.object
        nmat = len(ob.data.materials)
        bpy.ops.mesh.primitive_cone_add(vertices=nmat, radius1=0.5, depth=0.1, end_fill_type='NOTHING')
        cone = context.object
        cone.name = "%s Palette" % ob.name
        for mat,f in zip(ob.data.materials, cone.data.polygons):
            cone.data.materials.append(mat)
            f.material_index = f.index
        if not self.useMarkAsAsset:
            return
        bpy.ops.file.make_paths_absolute()
        bpy.ops.object.make_single_user(object=False, obdata=False, material=True, animation=False, obdata_animation=False)
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=False)
        for mat in cone.data.materials:
            if len(mat.name) > 4 and mat.name[-4] == "." and mat.name[-3:].isdigit():
                mat.name = mat.name[:-4]
        bpy.ops.asset.mark()

#-------------------------------------------------------------
#   Replace material node tree
#-------------------------------------------------------------

def getAllMaterials(scn, context):
    return [(mat.name, mat.name, mat.name) for mat in bpy.data.materials]


class DAZ_OT_ReplaceNodeTrees(DazPropsOperator, MaterialSelector, IsMesh):
    bl_idname = "daz.replace_node_trees"
    bl_label = "Replace Node Trees"
    bl_description = "Replace the node trees of selected materials.\nFor copying geograft base materials"
    bl_options = {'UNDO'}

    material : EnumProperty(
        items = getAllMaterials,
        name = "Material",
        description = "Use node tree from this material")

    def draw(self, context):
        MaterialSelector.draw(self, context)
        self.layout.prop(self, "material")

    def invoke(self, context, event):
        global theMaterialEditor
        theMaterialEditor = self
        ob = context.object
        self.setupMaterials(ob)
        return DazPropsOperator.invoke(self, context, event)

    def isDefaultActive(self, mat, ob):
        return True

    def run(self, context):
        from .tree import copyNodeTree
        ob = context.object
        src = bpy.data.materials[self.material]
        for mat in ob.data.materials:
            if self.useMaterial(mat):
                copyNodeTree(src.node_tree, mat.node_tree)
                copyMaterialAttributes(src, mat)


def copyMaterialAttributes(src, trg):
    attributes = [
        'blend_method', 'shadow_method', 'alpha_threshold', 'show_transparent_back', 'use_backface_culling',
        'use_screen_refraction', 'use_sss_translucency', 'refraction_depth',
        'diffuse_color', 'specular_color', 'roughness', 'specular_intensity', 'metallic',
    ]
    for attr in attributes:
        setattr(trg, attr, getattr(src, attr))

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
    DAZ_OT_LaunchEditor,
    DAZ_OT_UpdateMaterials,
    DAZ_OT_ResetMaterial,
    DAZ_OT_MakeDecal,
    DAZ_OT_SetShellVisibility,
    DAZ_OT_RemoveShells,
    DAZ_OT_ReplaceShells,
    DAZ_OT_ChangeUnitScale,
    DAZ_OT_MakePalette,
    DAZ_OT_ReplaceNodeTrees,
]

def register():
    from .propgroups import DazFloatGroup
    from .morphing import DazActiveGroup

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.DazDecalMask = StringProperty(
        name = "Decal Mask",
        description = "Path to decal mask texture",
        subtype = 'FILE_PATH',
        default = "")

    bpy.types.Material.DazSlots = CollectionProperty(type = EditSlotGroup)
    #bpy.types.Object.DazSlots = CollectionProperty(type = EditSlotGroup)
    bpy.types.Scene.DazFloats = CollectionProperty(type = DazFloatGroup)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
