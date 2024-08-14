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
from .tree import Tree, NodeGroup, XSIZE, YSIZE
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

    if bpy.app.version < (4,2,0):
        def captureInput(self, node, slot, datatype, fromsocket):
            node.data_type = datatype
            self.links.new(fromsocket, node.inputs[slot])

        def captureOutput(self, node, slot, tosocket):
            self.links.new(node.outputs[slot], tosocket)
    else:
        def captureInput(self, node, slot, datatype, fromsocket):
            for idx,item in enumerate(node.capture_items):
                if slot == item.name:
                    self.links.new(fromsocket, node.inputs[idx])
                    return
            socktype = ('VECTOR' if datatype == 'FLOAT_VECTOR' else datatype)
            item = node.capture_items.new(socktype, slot)
            self.links.new(fromsocket, node.inputs[-2])

        def captureOutput(self, node, slot, tosocket):
            self.links.new(node.outputs[1], tosocket)

# ---------------------------------------------------------------------
#   Follow proxy group
# ---------------------------------------------------------------------

class FollowProxyGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 4)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Object")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self):
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
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(GeoTree):
    def create(self, node, name, parent):
        GeoTree.create(self, node, name, parent, 7)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketObject", "Geograft")
        addGroupInput(self.group, "NodeSocketString", "Pairs")
        addGroupInput(self.group, "NodeSocketBool", "Toggle")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addNodes(self, args):
        # Object node for the geograft
        graft = self.addNode("GeometryNodeObjectInfo", 1)
        # Connect the Group Input-Geograft socket to this input
        self.links.new(self.inputs.outputs["Geograft"], graft.inputs[0])

        # Join the geograft & body objects into 1 mesh (to the end of having 1 list of vertices)\
        joinGeo = self.addNode("GeometryNodeJoinGeometry", 2)
        joins = [self.inputs, graft]
        joins.reverse()
        # Connect all objets to be joined to the Join Geometry node, which is to say....2
        for node in joins:
            self.links.new(node.outputs["Geometry"], joinGeo.inputs["Geometry"])

        # Retrieve the body vertex indices we stored in the attribute
        paired_verts_node = self.addNode("GeometryNodeInputNamedAttribute", 2)
        # ONLY FLOAT, INT, FLOAT_VECTOR, FLOAT_COLOR, BOOLEAN, QUATERNION
        paired_verts_node.data_type = 'INT'
        self.links.new(self.inputs.outputs["Pairs"], paired_verts_node.inputs["Name"])

        captureNamedAttribute = self.addNode("GeometryNodeCaptureAttribute", 3)
        captureNamedAttribute.domain = 'POINT'
        self.links.new(joinGeo.outputs["Geometry"], captureNamedAttribute.inputs["Geometry"])
        self.captureInput(captureNamedAttribute, "Value", 'INT', paired_verts_node.outputs["Attribute"])

        position_node = self.addNode("GeometryNodeInputPosition", 2)

        captureBodyPosition = self.addNode("GeometryNodeCaptureAttribute", 3)
        captureBodyPosition.domain = 'POINT'
        self.links.new(captureNamedAttribute.outputs["Geometry"], captureBodyPosition.inputs["Geometry"])
        self.captureInput(captureBodyPosition, "Value", 'FLOAT_VECTOR', position_node.outputs["Position"])

        # union = captureBodyPosition.outputs["Attribute"]

        # Evaluate At Index node for getting the POSITION at whatever index is referenced by the Named Attribute
        # (paired_body_vertex)
        evaluateIndex = self.addNode("GeometryNodeFieldAtIndex", 4)
        evaluateIndex.data_type = 'FLOAT_VECTOR'
        evaluateIndex.domain = 'POINT'
        self.captureOutput(captureNamedAttribute, "Attribute", evaluateIndex.inputs["Index"])
        self.links.new(position_node.outputs["Position"], evaluateIndex.inputs["Value"])

        # Switch node to determine which vertices stay put, and which snap to their paired body vertex
        switchNode = self.addNode("GeometryNodeSwitch", 5)
        switchNode.input_type = 'VECTOR'

        greaterThan = self.addNode("FunctionNodeCompare", 4)
        greaterThan.data_type = 'INT'
        greaterThan.operation = 'GREATER_THAN'
        self.captureOutput(captureNamedAttribute, "Attribute", greaterThan.inputs["A"])

        self.links.new(greaterThan.outputs["Result"], switchNode.inputs["Switch"])
        self.links.new(evaluateIndex.outputs["Value"], switchNode.inputs["True"])
        self.captureOutput(captureBodyPosition, "Attribute", switchNode.inputs["False"])

        # Set Position node will do the actual vertex "snapping" - just on the vertices of the graft edge to the body
        setPosition = self.addNode("GeometryNodeSetPosition", 5)
        self.links.new(captureBodyPosition.outputs["Geometry"], setPosition.inputs["Geometry"])
        self.links.new(switchNode.outputs["Output"], setPosition.inputs["Position"])

        toggle = self.addNode("GeometryNodeSwitch", 6)
        toggle.input_type = 'GEOMETRY'
        self.links.new(self.inputs.outputs["Toggle"], toggle.inputs["Switch"])
        self.links.new(self.inputs.outputs["Geometry"], toggle.inputs["False"])
        self.links.new(setPosition.outputs["Geometry"], toggle.inputs["True"])

        self.links.new(toggle.outputs["Output"], self.outputs.inputs["Geometry"])

# ---------------------------------------------------------------------
#   GeograftsGroup
# ---------------------------------------------------------------------

class GeograftsGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 7)
        addGroupInput(self.group, "NodeSocketGeometry", "Geometry")
        addGroupInput(self.group, "NodeSocketFloat", "Distance")
        addGroupOutput(self.group, "NodeSocketGeometry", "Geometry")


    def addGrafts(self, grafts):
        join = self.addNode("GeometryNodeJoinGeometry", 2)
        self.links.new(self.inputs.outputs["Geometry"], join.inputs["Geometry"])
        last = join

        for graft in grafts:
            gname = graft.name
            addGroupInput(self.group, "NodeSocketObject", "Geograft %s" % gname)
            addGroupInput(self.group, "NodeSocketString", "Pairs %s" % gname)
            addGroupInput(self.group, "NodeSocketFloat", "Mask %s" % gname)
            addGroupInput(self.group, "NodeSocketBool", "Toggle %s" % gname)

            node = self.addGroup(GeograftGroup, "DAZ Geograft", 1)
            self.links.new(self.inputs.outputs["Geometry"], node.inputs["Geometry"])
            self.links.new(self.inputs.outputs["Geograft %s" % gname], node.inputs["Geograft"])
            self.links.new(self.inputs.outputs["Pairs %s" % gname], node.inputs["Pairs"])
            self.links.new(self.inputs.outputs["Toggle %s" % gname], node.inputs["Toggle"])
            self.links.new(node.outputs["Geometry"], join.inputs["Geometry"])

            toggle = self.addNode("GeometryNodeSwitch", 3)
            toggle.input_type = 'FLOAT'
            self.links.new(self.inputs.outputs["Toggle %s" % gname], toggle.inputs["Switch"])
            self.links.new(self.inputs.outputs["Mask %s" % gname], toggle.inputs["True"])

            delete = self.addNode("GeometryNodeDeleteGeometry", 4)
            self.links.new(last.outputs["Geometry"], delete.inputs["Geometry"])
            self.links.new(toggle.outputs["Output"], delete.inputs["Selection"])
            last = delete

        merge = self.addNode("GeometryNodeMergeByDistance", 4)
        self.links.new(self.inputs.outputs["Distance"], merge.inputs["Distance"])
        self.links.new(last.outputs["Geometry"], merge.inputs["Geometry"])
        self.links.new(merge.outputs["Geometry"], self.outputs.inputs["Geometry"])

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

# ---------------------------------------------------------------------
#   Shell functions
# ---------------------------------------------------------------------

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
    shell.lock_location = shell.lock_rotation = shell.lock_scale = (True, True, True)
    shell.visible_shadow = False
    mod = shell.modifiers.new(shell.name, 'NODES')
    group = GeoshellGroup()
    group.create(noMeshName(ob.name), mnames)
    group.addNodes(mnames, mats, shmats)
    mod.node_group = group.group
    if BLENDER3:
        mod["Input_1"] = ob
        mod["Input_2"] = offset
    else:
        mod["Socket_1"] = ob
        mod["Socket_2"] = offset

