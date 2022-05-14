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
from .error import *
from .utils import *
from .tree import Tree, NodeGroup, XSIZE, YSIZE

VECTOR = 1
VALUE = 2
RGBA = 3
BOOLEAN = 4
INT = 5

# ---------------------------------------------------------------------
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(Tree, NodeGroup):
    def __init__(self):
        Tree.__init__(self, None)
        NodeGroup.__init__(self)
        self.type = 'GEONODE'
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

# ---------------------------------------------------------------------
#   Geoshell group
# ---------------------------------------------------------------------

class GeoshellGroup(Tree, NodeGroup):
    def __init__(self):
        Tree.__init__(self, None)
        NodeGroup.__init__(self)
        self.type = 'GEOSHELL'
        self.nodeTreeType = "GeometryNodeTree"
        self.nodeGroupType = "GeometryNodeGroup"


    def create(self, name, mnames):
        NodeGroup.make(self, name, 4)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketObject", "Figure")
        self.group.inputs.new("NodeSocketFloat", "Shell Offset")
        for mname in mnames:
            self.group.inputs.new("NodeSocketMaterial", mname)
        self.group.outputs.new("NodeSocketGeometry", "Geometry")


    def addNodes(self, mnames, mats):
        # Geoshell
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        self.links.new(self.inputs.outputs["Figure"], objinfo.inputs["Object"])
        normal = self.addNode("GeometryNodeInputNormal", 1)

        mult = self.addNode("ShaderNodeVectorMath", 2)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Shell Offset"], mult.inputs[0])
        self.links.new(normal.outputs["Normal"], mult.inputs[1])

        setpos = self.addNode("GeometryNodeSetPosition", 3)
        self.links.new(mult.outputs[0], setpos.inputs["Offset"])
        self.links.new(objinfo.outputs["Geometry"], setpos.inputs["Geometry"])

        # Materials
        for mname,mat in zip(mnames,mats):
            matsel = self.addNode("GeometryNodeMaterialSelection", 2)
            matsel.inputs["Material"].default_value = mat
            setmat = self.addNode("GeometryNodeSetMaterial", 3)
            self.links.new(setpos.outputs["Geometry"], setmat.inputs["Geometry"])
            self.links.new(matsel.outputs["Selection"], setmat.inputs["Selection"])
            self.links.new(self.inputs.outputs[mname], setmat.inputs["Material"])
            setpos = setmat

        #joinGeo = self.addNode("GeometryNodeJoinGeometry", 6)
        #self.links.new(objinfo.outputs["Geometry"], joinGeo.inputs["Geometry"])
        #self.links.new(setpos.outputs["Geometry"], joinGeo.inputs["Geometry"])
        self.links.new(setpos.outputs["Geometry"], self.outputs.inputs["Geometry"])

#----------------------------------------------------------
#   Add shells
#----------------------------------------------------------

class DAZ_OT_AddShell(DazOperator):
    bl_idname = "daz.add_shell"
    bl_label = "Add Shell"
    bl_description = "Add active shell to selected mesh"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.data.vertices) == 0)

    def run(self, context):
        shell = context.object
        for ob in getSelectedMeshes(context):
            if ob.data.vertices:
                mnames = [mat.name for mat in ob.data.materials]
                makeShellModifier(shell, ob, mnames, ob.data.materials, shell.data.materials)
                return
        raise DazError("No matching mesh selected")


def makeShellModifier(shell, ob, mnames, mats, shmats):
    mod = shell.modifiers.new(shell.name, 'NODES')
    group = GeoshellGroup()
    group.create(ob.name, mnames)
    group.addNodes(mnames, mats)
    mod.node_group = group.group
    mod["Input_1"] = ob
    mod["Input_2"] = 0.1 * ob.DazScale
    for n,shmat in enumerate(shmats):
        mod["Input_%d" % (n+3)] = shmat

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddShell,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
