# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..tree import NodeGroup
from ..tree import addGroupInput, addGroupOutput, getGroupInput
from ..geonodes import GeoTree

# ---------------------------------------------------------------------
#   Follow proxy group
# ---------------------------------------------------------------------

class FollowProxyGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 4)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Object")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, args):
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        objinfo.transform_space = 'RELATIVE'
        self.links.new(self.inputs.outputs["Object"], objinfo.inputs[0])
        position = self.addNode("GeometryNodeInputPosition", 1)
        index = self.addNode("GeometryNodeInputIndex", 1)

        sample = self.addNode("GeometryNodeSampleIndex", 2)
        if hasattr(sample, "data_type"):
            sample.data_type = 'FLOAT_VECTOR'
        sample.domain = 'POINT'
        self.links.new(objinfo.outputs["Geometry"], sample.inputs["Geometry"])
        self.links.new(position.outputs["Position"], sample.inputs["Value"])
        self.links.new(index.outputs["Index"], sample.inputs["Index"])

        setPosition = self.addNode("GeometryNodeSetPosition", 3)
        self.links.new(self.inputs.outputs["Geometry"], setPosition.inputs["Geometry"])
        self.links.new(sample.outputs["Value"], setPosition.inputs["Position"])

        self.links.new(setPosition.outputs["Geometry"], self.outputs.inputs["Geometry"])

# ---------------------------------------------------------------------
#   Deform curves group
# ---------------------------------------------------------------------

class DeformCurvesGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 2)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, args):
        node =  self.addNode("GeometryNodeDeformCurvesOnSurface", 1)
        self.links.new(self.inputs.outputs["Geometry"], node.inputs["Curves"])
        self.links.new(node.outputs["Curves"], self.outputs.inputs["Geometry"])

# ---------------------------------------------------------------------
#   Delete invalid curves
# ---------------------------------------------------------------------

class DeleteInvalidGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 5)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Surface Geometry")
        addGroupInput(self.group, "NodeSocketString", "Surface UV Map")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, args):
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        objinfo.transform_space = 'ORIGINAL'
        self.links.new(self.inputs.outputs["Surface Geometry"], objinfo.inputs[0])

        normal = self.addNode("GeometryNodeInputNormal", 1)

        capture = self.addNode("GeometryNodeCaptureAttribute", 2)
        capture.domain = 'POINT'
        self.links.new(objinfo.outputs["Geometry"], capture.inputs[0])
        self.captureInput(capture, "Value", 'FLOAT_VECTOR', normal.outputs["Normal"])

        attr1 = self.addNode("GeometryNodeInputNamedAttribute", 2)
        attr1.data_type = 'FLOAT_VECTOR'
        self.links.new(self.inputs.outputs["Surface UV Map"], attr1.inputs[0])

        attr2 = self.addNode("GeometryNodeInputNamedAttribute", 2)
        attr2.data_type = 'FLOAT_VECTOR'
        attr2.inputs[0].default_value = "surface_uv_coordinate"

        sample = self.addNode("GeometryNodeSampleUVSurface", 3)
        self.links.new(capture.outputs[0], sample.inputs["Mesh"])
        self.links.new(capture.outputs[1], sample.inputs["Value"])
        self.links.new(attr1.outputs["Attribute"], sample.inputs["UV Map"])
        self.links.new(attr2.outputs["Attribute"], sample.inputs["Sample UV"])

        sep = self.addNode("GeometryNodeSeparateGeometry", 4)
        sep.domain = 'CURVE'
        self.links.new(self.inputs.outputs["Geometry"], sep.inputs["Geometry"])
        self.links.new(sample.outputs["Is Valid"], sep.inputs["Selection"])

        self.links.new(sep.outputs["Selection"], self.outputs.inputs["Geometry"])

#-------------------------------------------------------------
#   Add Hair Node Group
#-------------------------------------------------------------

def addHairNodeGroup(ob, name):
    group = bpy.data.node_groups.get(name)
    if group is None:
        if BLENDER4:
            aid = "geometry_nodes/procedural_hair_node_assets.blend/NodeTree/%s" % name
        else:
            aid = "nodes/procedural_hair_node_assets.blend/NodeTree/%s" % name
        bpy.ops.object.modifier_add_node_group(
            asset_library_type = 'ESSENTIALS',
            asset_library_identifier = "",
            relative_asset_identifier = aid)
        if ob.modifiers:
            mod = ob.modifiers[-1]
            group = mod.node_group
            ob.modifiers.remove(mod)
            print('Created node group "%s"' % group.name)
        else:
            print('Unable to create node group "%s"' % group.name)
    return group





