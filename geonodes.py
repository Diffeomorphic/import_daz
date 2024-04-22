# Copyright (c) 2016-2024, Thomas Larsson
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
from .tree import Tree, NodeGroup, XSIZE, YSIZE, addNodeGroup
from .tree import addGroupInput, addGroupOutput, getGroupInput
from .selector import Selector

# ---------------------------------------------------------------------
#   Geometry nodes, tree
# ---------------------------------------------------------------------

class GeoTree(Tree, NodeGroup):
    def __init__(self):
        Tree.__init__(self, None)
        NodeGroup.__init__(self)
        self.type = 'GEONODES'
        self.nodeTreeType = "GeometryNodeTree"
        self.nodeGroupType = "GeometryNodeGroup"

# ---------------------------------------------------------------------
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 6)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Geograft")
        addGroupInput(self.group, "NodeSocketFloat", "Geograft Edge")
        addGroupInput(self.group, "NodeSocketFloat", "Geograft Area")
        addGroupInput(self.group, "NodeSocketFloat", "Merge Distance")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self):
        graft = self.addNode("GeometryNodeObjectInfo", 1)
        self.links.new(self.inputs.outputs["Geograft"], graft.inputs[0])

        captureEdge = self.addNode("GeometryNodeCaptureAttribute", 2)
        captureEdge.data_type = 'FLOAT'
        captureEdge.domain = 'POINT'
        self.links.new(self.inputs.outputs["Geometry"], captureEdge.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Edge"], captureEdge.inputs["Value"])
        union = captureEdge.outputs["Attribute"]

        deleteMask = self.addNode("GeometryNodeDeleteGeometry", 3)
        self.links.new(captureEdge.outputs["Geometry"], deleteMask.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Area"], deleteMask.inputs["Selection"])

        joinGeo = self.addNode("GeometryNodeJoinGeometry", 4)
        joins = []

        captureAnatomy = self.addNode("GeometryNodeCaptureAttribute", 2)
        captureAnatomy.data_type = 'FLOAT'
        captureAnatomy.domain = 'POINT'
        self.links.new(graft.outputs["Geometry"], captureAnatomy.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Edge"], captureAnatomy.inputs["Value"])
        joins.append(captureAnatomy)

        node = self.addNode("FunctionNodeBooleanMath", 3)
        node.operation = 'OR'
        self.links.new(union, node.inputs[0])
        self.links.new(captureAnatomy.outputs["Attribute"], node.inputs[1])
        union = node.outputs[0]
        joins.append(deleteMask)
        joins.reverse()
        for node in joins:
            self.links.new(node.outputs["Geometry"], joinGeo.inputs["Geometry"])

        mergeDist = self.addNode("GeometryNodeMergeByDistance", 5)
        mergeDist.inputs["Distance"].default_value = 1e-4
        self.links.new(self.inputs.outputs["Merge Distance"], mergeDist.inputs["Distance"])
        self.links.new(joinGeo.outputs["Geometry"], mergeDist.inputs["Geometry"])
        self.links.new(union, mergeDist.inputs["Selection"])

        self.links.new(mergeDist.outputs["Geometry"], self.outputs.inputs["Geometry"])

# ---------------------------------------------------------------------
#   Geoshell group
# ---------------------------------------------------------------------

class GeoshellGroup(GeoTree):
    def create(self, name, mnames):
        NodeGroup.make(self, name, 7)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Base Object")
        addGroupInput(self.group, "NodeSocketFloat", "Shell Offset")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, mnames, mats, shmats):
        # Geoshell
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        self.links.new(self.inputs.outputs["Base Object"], objinfo.inputs["Object"])
        normal = self.addNode("GeometryNodeInputNormal", 1)

        mult = self.addNode("ShaderNodeVectorMath", 2)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Shell Offset"], mult.inputs[0])
        self.links.new(normal.outputs["Normal"], mult.inputs[1])

        delgeo = self.addNode("GeometryNodeDeleteGeometry", 2)
        delgeo.domain = 'FACE'
        delgeo.mode = 'ALL'
        self.links.new(objinfo.outputs["Geometry"], delgeo.inputs["Geometry"])

        setpos = self.addNode("GeometryNodeSetPosition", 3)
        self.links.new(mult.outputs[0], setpos.inputs["Offset"])
        self.links.new(delgeo.outputs["Geometry"], setpos.inputs["Geometry"])
        active = setpos

        # Materials
        rest = None
        for mn,mname in enumerate(mnames):
            mat = mats[mn]
            shmat = shmats[mn]
            matsel = self.addNode("GeometryNodeMaterialSelection", 4)
            matsel.inputs["Material"].default_value = mat
            setmat = self.addNode("GeometryNodeSetMaterial", 6)
            self.links.new(active.outputs["Geometry"], setmat.inputs["Geometry"])
            self.links.new(matsel.outputs["Selection"], setmat.inputs["Selection"])
            setmat.inputs["Material"].default_value = shmat
            if rest is None:
                rest = matsel
            else:
                node = self.addNode("FunctionNodeBooleanMath", 5)
                node.operation = 'OR'
                self.links.new(rest.outputs[0], node.inputs[0])
                self.links.new(matsel.outputs["Selection"], node.inputs[1])
                rest = node
            active = setmat

        if rest:
            node = self.addNode("FunctionNodeBooleanMath", 1)
            node.operation = 'NOT'
            self.links.new(rest.outputs[0], node.inputs[0])
            self.links.new(node.outputs[0], delgeo.inputs["Selection"])

        self.links.new(active.outputs["Geometry"], self.outputs.inputs["Geometry"])


def makeShell(shname, shmats, ob):
    me = bpy.data.meshes.new(shname)
    for shmat in shmats:
        me.materials.append(shmat)
    shell = bpy.data.objects.new(shname, me)
    linkShell(shell)
    shell.parent = ob
    return shell


def linkShell(shell):
    coll = bpy.data.collections.new(shell.name)
    LS.collection.children.link(coll)
    coll.objects.link(shell)


def makeShellModifier(shell, ob, offset, mnames, mats, shmats):
    mod = getModifier(shell, 'NODES')
    if mod:
        shell = makeShell(shell.name, shmats, shell.parent)
    else:
        shmatlist = list(enumerate(shell.data.materials))
        shmatlist.reverse()
        for n,shmat in shmatlist:
            if shmat not in shmats:
                shell.data.materials.pop(index=n)
    shell.lock_location = shell.lock_rotation = shell.lock_scale = TTrue
    shell.visible_shadow = False
    mod = shell.modifiers.new(shell.name, 'NODES')
    group = GeoshellGroup()
    group.create(ob.name.rstrip(" Mesh"), mnames)
    group.addNodes(mnames, mats, shmats)
    mod.node_group = group.group
    if BLENDER3:
        mod["Input_1"] = ob
        mod["Input_2"] = offset
    else:
        mod["Socket_1"] = ob
        mod["Socket_2"] = offset

