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
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_MeshAddPinning,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
