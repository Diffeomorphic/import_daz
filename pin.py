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
from .error import *
from .utils import *

# ---------------------------------------------------------------------
#   Pinning
# ---------------------------------------------------------------------

class Pinner:
    fixedPin = True

    def __init__(self):
        self.nodeGroup = None
        self.curveMapping = None
        self.pinGroup = "HairPinning"

    def getCurveMapping(self):
        if self.nodeGroup is None:
            self.nodeGroup = bpy.data.node_groups.new('DazPinningData', 'ShaderNodeTree')
        if self.curveMapping is None:
            cn = self.nodeGroup.nodes.new('ShaderNodeRGBCurve')
            self.curveMapping = cn.name
        return self.nodeGroup.nodes[self.curveMapping]

    def invokePinner(self):
        self.simQuality = 1
        self.useCollision = False
        node = self.getCurveMapping()
        cu = node.mapping.curves[3]
        cu.points[0].location = (0,1)
        cu.points[-1].location = (1,0)

    def initMapping(self):
        node = self.getCurveMapping()
        self.mapping = node.mapping
        self.curve = node.mapping.curves[3]

    def addWeight(self, vgrp, vn, w):
        x = min(1.0, max(0.0, w))
        w = self.mapping.evaluate(self.curve, x)
        vgrp.add([vn], w, 'REPLACE')

    def invoke(self, context, event):
        self.invokePinner()
        return DazPropsOperator.invoke(self, context, event)

    def draw(self, context):
        self.drawMapping(context, self.layout)

    def drawMapping(self, context, layout):
        layout.template_curve_mapping(self.getCurveMapping(), "mapping")


    def addHairPinning(self, ob):
        self.initMapping()
        if self.pinGroup in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[self.pinGroup]
            ob.vertex_groups.remove(vgrp)
        vgrp = ob.vertex_groups.new(name=self.pinGroup)
        if "Root Distance" in ob.vertex_groups.keys():
            distgrp = ob.vertex_groups["Root Distance"]
            idx = distgrp.index
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == idx:
                        self.addWeight(vgrp, v.index, g.weight)
                        break
        elif ob.data.uv_layers:
            uvs = ob.data.uv_layers.active.data
            m = 0
            for f in ob.data.polygons:
                for n,vn in enumerate(f.vertices):
                    self.addWeight(vgrp, vn, 1-uvs[m+n].uv[1])
                m += len(f.vertices)
        else:
            raise DazError("Cannot determine root distance")

        mod = getModifier(ob, 'CLOTH')
        if mod and vgrp:
            mod.settings.vertex_group_mass = vgrp.name

# ---------------------------------------------------------------------
#   Add pinning to hair mesh
# ---------------------------------------------------------------------

class DAZ_OT_MeshAddPinning(Pinner, DazPropsOperator, IsMesh):
    bl_idname = "daz.mesh_add_pinning"
    bl_label = "Add Pinning Group"
    bl_description = "Add HairPin group to mesh hair"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        self.addHairPinning(ob)

# ---------------------------------------------------------------------
#   Modify vertex group
# ---------------------------------------------------------------------

class DAZ_OT_ModifyVertexGroup(Pinner, DazPropsOperator, IsMesh):
    bl_idname = "daz.modify_vertex_group"
    bl_label = "Modify Vertex Group"
    bl_description = "Modify the active vertex group"
    bl_options = {'UNDO'}

    direction : EnumProperty(
        items = [("+X", "+X", "+X"),
                 ("-X", "-X", "-X"),
                 ("+Y", "+Y", "+Y"),
                 ("-Y", "-Y", "-Y"),
                 ("+Z", "+Z", "+Z"),
                 ("-Z", "-Z", "-Z")],
        name = "Direction")


    def draw(self, context):
        Pinner.draw(self, context)
        ob = context.object
        vgrp = ob.vertex_groups.active
        box = self.layout.box()
        box.label(text="Vertex group: %s" % vgrp.name)
        self.layout.prop(self, "direction")


    def run(self, context):
        vectors = {
            "+X" : (1,0,0),
            "-X" : (-1,0,0),
            "+Y" : (0,1,0),
            "-Y" : (0,-1,0),
            "+Z" : (0,0,1),
            "-Z" : (0,0,-1)
        }
        ob = context.object
        vgrp = ob.vertex_groups.active
        self.initMapping()
        ez = Vector(vectors[self.direction])
        zs = [ez.dot(v.co) for v in ob.data.vertices]
        z0 = min(zs)
        z1 = max(zs)
        for v in ob.data.vertices:
            w = (ez.dot(v.co) - z0)/(z1 - z0)
            self.addWeight(vgrp, v.index, w)

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_MeshAddPinning,
    DAZ_OT_ModifyVertexGroup,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
