# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import math
from mathutils import Vector

from .error import *
from .utils import *
from .material import WHITE

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
#   Update
#-------------------------------------------------------------

class DAZ_OT_UpdateMaterials(bpy.types.Operator):
    bl_idname = "daz.update_materials"
    bl_label = "Update Materials"
    bl_description = "Update Materials"

    def execute(self, context):
        global theMaterialEditor
        theMaterialEditor.run(context)
        return {'PASS_THROUGH'}

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
        objects = [rig] + [ob for ob in rig.children if ob.get("DazVisibilityDrivers", False)]
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
                    ob["DazVisibilityDrivers"] = rig["DazVisibilityDrivers"] = True


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
#   Invisible and permanent materials
#----------------------------------------------------------

def getInvisibleMaterial(mname="Invisio", color=(0.8,0.8,0.8,0)):
    if mname in bpy.data.materials.keys():
        return bpy.data.materials[mname]
    mat = bpy.data.materials.new(mname)
    mat.blend_method = 'CLIP'
    mat.shadow_method = 'NONE'
    mat.diffuse_color = color
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    trans = tree.nodes.new(type = "ShaderNodeBsdfTransparent")
    trans.location = (0, 0)
    output = tree.nodes.new(type = "ShaderNodeOutputMaterial")
    output.location = (200, 0)
    output.target = 'ALL'
    tree.links.new(trans.outputs["BSDF"], output.inputs["Surface"])
    return mat


def makePermanentMaterial(ob, mname, color):
    perm = getInvisibleMaterial(mname, color)
    mnum = -1
    for mn,mat in enumerate(ob.data.materials):
        if mat == perm:
            mnum = mn
            break
    if mnum == -1:
        mnum = len(ob.data.materials)
        ob.data.materials.append(perm)
    for f in ob.data.polygons:
        if f.select:
            f.material_index = mnum

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazMaterialGroup,
    DAZ_OT_SelectAllMaterials,
    DAZ_OT_SelectNoMaterial,
    DAZ_OT_SelectSkinMaterials,
    DAZ_OT_SelectSkinRedMaterials,
    DAZ_OT_SetShellInfluence,
    DAZ_OT_ToggleShellInfluence,
    DAZ_OT_UpdateMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.DazFilter = StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
    )


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
