# Copyright (c) 2016-2022, Thomas Larsson
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
from .tree import Tree, NodeGroup, XSIZE, YSIZE

# ---------------------------------------------------------------------
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(Tree, NodeGroup):
    def __init__(self):
        Tree.__init__(self, None)
        NodeGroup.__init__(self)
        self.type = 'GEO'
        self.nodeTreeType = "GeometryNodeTree"
        self.nodeGroupType = "GeometryNodeGroup"


    def create(self, name):
        NodeGroup.make(self, name, 5)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketFloat", "Geograft Edge")
        self.group.inputs.new("NodeSocketFloat", "Geograft Area")
        self.group.inputs.new("NodeSocketFloat", "Merge Distance")
        self.group.outputs.new("NodeSocketGeometry", "Geometry")
        self.group.outputs.new("NodeSocketInt", "Vertex Table")


    def addNodes(self, anatomies):
        VECTOR = 1
        VALUE = 2
        RGBA = 3
        BOOLEAN = 4
        INT = 5

        index = self.addNode("GeometryNodeInputIndex", 0)
        captureIndex = self.addNode("GeometryNodeCaptureAttribute", 1)
        captureIndex.data_type = 'INT'
        captureIndex.domain = 'POINT'
        self.links.new(self.inputs.outputs["Geometry"], captureIndex.inputs["Geometry"])
        self.links.new(index.outputs["Index"], captureIndex.inputs[INT])

        captureEdge = self.addNode("GeometryNodeCaptureAttribute", 1)
        captureEdge.data_type = 'FLOAT'
        captureEdge.domain = 'POINT'
        self.links.new(captureIndex.outputs["Geometry"], captureEdge.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Edge"], captureEdge.inputs[VALUE])
        union = captureEdge.outputs[VALUE]

        deleteMask = self.addNode("GeometryNodeDeleteGeometry", 2)
        self.links.new(captureEdge.outputs["Geometry"], deleteMask.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Area"], deleteMask.inputs["Selection"])

        joinGeo = self.addNode("GeometryNodeJoinGeometry", 3)
        joins = [deleteMask]
        for aob in anatomies:
            objinfo = self.addNode("GeometryNodeObjectInfo", 0)
            objinfo.inputs[0].default_value = aob

            captureAnatomy = self.addNode("GeometryNodeCaptureAttribute", 1)
            captureAnatomy.data_type = 'FLOAT'
            captureAnatomy.domain = 'POINT'
            self.links.new(objinfo.outputs["Geometry"], captureAnatomy.inputs["Geometry"])
            self.links.new(self.inputs.outputs["Geograft Edge"], captureAnatomy.inputs[VALUE])
            joins.append(captureAnatomy)

            node = self.addNode("FunctionNodeBooleanMath", 2)
            node.operation = 'OR'
            self.links.new(union, node.inputs[0])
            self.links.new(captureAnatomy.outputs[VALUE], node.inputs[1])
            union = node.outputs[0]
        joins.reverse()
        for node in joins:
            self.links.new(node.outputs["Geometry"], joinGeo.inputs["Geometry"])

        mergeDist = self.addNode("GeometryNodeMergeByDistance", 4)
        mergeDist.inputs["Distance"].default_value = 1e-4
        self.links.new(self.inputs.outputs["Merge Distance"], mergeDist.inputs["Distance"])
        self.links.new(joinGeo.outputs["Geometry"], mergeDist.inputs["Geometry"])
        self.links.new(union, mergeDist.inputs["Selection"])

        self.links.new(mergeDist.outputs["Geometry"], self.outputs.inputs["Geometry"])
        self.links.new(captureIndex.outputs[INT], self.outputs.inputs["Vertex Table"])


def makeGeograftGroup(anatomies):
    name = "Daz Geograft"
    if name in bpy.data.node_groups.keys():
        return bpy.data.node_groups[name]
    group = GeograftGroup()
    group.create(name)
    group.addNodes(anatomies)
    return group.group
