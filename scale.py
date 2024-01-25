# Copyright (c) 2016-2023, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
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
from bpy.types import EnumProperty, FloatProperty
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Set unit scale
#-------------------------------------------------------------

class UnitsOperator(DazPropsOperator):
    units : EnumProperty(
        items = [("100", "Meters", "Meters"),
                 ("1", "Centimeters", "Centimeters (DAZ native)"),
                 ("0.1", "Millimeters", "Millimeters"),
                 ("30.48", "Feet", "Feet"),
                 ("2.54", "Inches", "Inches"),
                 ("Manual", "Manual", "Set the unit scale manually")],
        name = "Units",
        description = "Set global unit scale")

    scale : FloatProperty(
        name = "Scale",
        description = "Scale used to convert between DAZ and Blender units.\nDefault unit meters",
        default = 0.01,
        precision = 4,
        min = 1e-6)

    def draw(self, context):
        self.layout.prop(self, "units")
        self.layout.prop(self, "scale")

    def invoke(self, context, event):
        self.scale = GS.scale
        return DazPropsOperator.invoke(self, context, event)

    def setUnitScale(self):
        if self.units != "Manual":
            self.scale = 1/float(self.units)


class DAZ_OT_SetUnits(UnitsOperator):
    bl_idname = "daz.set_units"
    bl_label = "Set Units"
    bl_description = "Set global unit scale"
    bl_options = {'UNDO'}

    def run(self, context):
        self.setUnitScale()
        GS.scale = self.scale

#-------------------------------------------------------------
#   Scale materials
#-------------------------------------------------------------

class MaterialScaler(UnitsOperator):
    objectScale : FloatProperty(
        name = "Object Scale",
        description = "Scale of the active object",
        default = 0.01,
        precision = 4,
        min = 1e-6)

    useUpdate : BoolProperty(
        name = "Update Unit Scale",
        description = "Update global unit scale",
        default = True)

    def draw(self, context):
        UnitsOperator.draw(self, context)
        if context.object:
            self.layout.label(text = "Object Scale: %.4f" % self.objectScale)
        self.layout.prop(self, "useUpdate")
        self.layout.prop(context.scene.tool_settings, "use_keyframe_insert_auto")

    def invoke(self, context, event):
        if context.object:
            self.objectScale = context.object.DazScale
        return UnitsOperator.invoke(self, context, event)

    def scaleMaterials(self, ob):
        for mat in ob.data.materials:
            if mat:
                if mat.DazScale == 0:
                    mat.DazScale = ob.DazScale
                scale = self.scale / mat.DazScale
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP':
                        self.fixNode(node, node.node_tree.name, scale)
                    else:
                        self.fixNode(node, node.type, scale)
                mat.DazScale = self.scale
                if self.auto:
                    mat.keyframe_insert("DazScale")

    if BLENDER3:
        NodeScale = {
            "BUMP" : ["Distance"],
            "BSDF_PRINCIPLED" : ["Subsurface Radius"],
            "DAZ Translucent" : ["Radius"],
            "DAZ Subsurface" : ["Radius"],
            "DAZ Top Coat" : ["Distance"],
            "DAZ Displacement" : ["Max", "Min"],
        }
    else:
        NodeScale = {
            "BUMP" : ["Distance"],
            "BSDF_PRINCIPLED" : ["Subsurface Scale"],
            "DAZ Translucent" : ["Radius"],
            "DAZ Subsurface" : ["Scale"],
            "DAZ Top Coat" : ["Distance"],
            "DAZ Displacement" : ["Max", "Min"],
        }


    def fixNode(self, node, nodetype, scale):
        if nodetype in self.NodeScale.keys():
            for sname in self.NodeScale[nodetype]:
                socket = node.inputs.get(sname)
                if socket is None:
                    continue
                elif isinstance(socket.default_value, float):
                    socket.default_value *= scale
                else:
                    socket.default_value = scale*Vector(socket.default_value)
                if self.auto:
                    socket.keyframe_insert("default_value")


class DAZ_OT_ScaleMaterials(MaterialScaler, IsMesh):
    bl_idname = "daz.scale_materials"
    bl_label = "Scale Materials"
    bl_description = "Scale material properties with dimension of length\n(bump distance, subsurface radius, etc.)"
    bl_options = {'UNDO'}

    def run(self, context):
        self.setUnitScale()
        self.auto = context.scene.tool_settings.use_keyframe_insert_auto
        for ob in getSelectedMeshes(context):
            self.scaleMaterials(ob)
        if self.useUpdate:
            GS.scale = self.scale

#-------------------------------------------------------------
#   Change object scale
#-------------------------------------------------------------

class DAZ_OT_ScaleObjects(MaterialScaler, DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.scale_objects"
    bl_label = "Scale Objects"
    bl_description = "Safely change the unit scale of selected object and children"
    bl_options = {'UNDO'}

    def run(self, context):
        self.setUnitScale()
        self.auto = context.scene.tool_settings.use_keyframe_insert_auto
        ob = context.object
        while ob.parent:
            ob = ob.parent
        self.meshes = []
        self.rigs = []
        self.parents = {}
        self.addObjects(ob)
        for ob in self.meshes:
            self.applyScale(context, ob)
            self.scaleMaterials(ob)
        for rig in self.rigs:
            self.applyScale(context, rig)
            self.fixRig(rig)
        for rig in self.rigs:
            self.restoreParent(context, rig)
        for ob in self.meshes:
            self.restoreParent(context, ob)
        if self.useUpdate:
            GS.scale = self.scale


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
        scale = self.scale / ob.DazScale
        if ob.type in ['MESH', 'ARMATURE'] and activateObject(context, ob):
            self.parents[ob.name] = (ob.parent, ob.parent_type, ob.parent_bone)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            lock = list(ob.lock_scale)
            ob.lock_scale = (False,False,False)
            ob.scale *= scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


    def fixRig(self, rig):
        scale = self.scale / rig.DazScale
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'STRETCH_TO':
                    cns.rest_length *= scale


    def restoreParent(self, context, ob):
        ob.DazScale = self.scale
        if ob.name in self.parents.keys():
            wmat = ob.matrix_world.copy()
            (ob.parent, ob.parent_type, ob.parent_bone) = self.parents[ob.name]
            setWorldMatrix(ob, wmat)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SetUnits,
    DAZ_OT_ScaleMaterials,
    DAZ_OT_ScaleObjects,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
