# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
        NodeGroup.make(self, name, 4)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Surface Geometry")
        addGroupInput(self.group, "NodeSocketString", "Surface UV Map")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, args):
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        objinfo.transform_space = 'ORIGINAL'
        self.links.new(self.inputs.outputs["Surface Geometry"], objinfo.inputs[0])

        attr = self.addNode("GeometryNodeInputNamedAttribute", 1)
        attr.data_type = 'FLOAT_VECTOR'
        self.links.new(self.inputs.outputs["Surface UV Map"], attr.inputs[0])

        ob = args[0]
        group = addHairNodeGroup(ob, "Hair Attachment Info")
        attach = self.addNode("GeometryNodeGroup", 2)
        attach.name = attach.label = group.name
        attach.node_tree = group
        self.links.new(objinfo.outputs["Geometry"], attach.inputs["Surface Geometry"])
        self.links.new(attr.outputs["Attribute"], attach.inputs["Surface UV Map"])

        sep = self.addNode("GeometryNodeSeparateGeometry", 3)
        sep.domain = 'CURVE'
        self.links.new(self.inputs.outputs["Geometry"], sep.inputs["Geometry"])
        self.links.new(attach.outputs["Attachment is Valid"], sep.inputs["Selection"])

        self.links.new(sep.outputs["Selection"], self.outputs.inputs["Geometry"])

#-------------------------------------------------------------
#   Add Hair Node Group
#-------------------------------------------------------------

def addHairNodeGroup(ob, name):
    group = bpy.data.node_groups.get(name)
    if group is None:
        aid = "geometry_nodes\\procedural_hair_node_assets.blend\\NodeTree\\%s" % name
        bpy.ops.object.modifier_add_node_group(
            asset_library_type = 'ESSENTIALS',
            asset_library_identifier = "",
            relative_asset_identifier = aid)
        mod = ob.modifiers[-1]
        group = mod.node_group
        ob.modifiers.remove(mod)
        print('Created node group "%s"' % group.name)
    return group





