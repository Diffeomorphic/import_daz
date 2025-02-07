# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(GeoTree):
    def create(self, node, name, parent):
        GeoTree.create(self, node, name, parent, 8)
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
        # joins = [self.inputs, graft]
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

    def addGrafts(self, grafts, hum_name = ""):
        join = self.addNode("GeometryNodeJoinGeometry", 3)
        self.links.new(self.inputs.outputs["Geometry"], join.inputs["Geometry"])
        last = join

        # Add named attribute (FullBody) for deleting duplicated body geometry after the merge
        temp_body_node = self.addNode("GeometryNodeInputNamedAttribute", 1)
        temp_body_node.data_type = 'INT'
        temp_body_node.inputs[0].default_value = f'FullBody_{hum_name}'

        merge = self.addNode("GeometryNodeMergeByDistance", 6)

        graft_count = len(grafts)
        add_edge_node_counter = 0
        add_edge_nodes = {}
        for node_counter, graft in enumerate(grafts, start=1):
            gname = graft.name
            addGroupInput(self.group, "NodeSocketObject", "Geograft %s" % gname)
            addGroupInput(self.group, "NodeSocketString", "Pairs %s" % gname)
            addGroupInput(self.group, "NodeSocketFloat", "Mask %s" % gname)
            addGroupInput(self.group, "NodeSocketBool", "Toggle %s" % gname)
            addGroupInput(self.group, "NodeSocketString", "Edge %s" % gname)

            node = self.addGroup(GeograftGroup, "DAZ Geograft", 1)
            self.links.new(self.inputs.outputs["Geometry"], node.inputs["Geometry"])
            self.links.new(self.inputs.outputs["Geograft %s" % gname], node.inputs["Geograft"])
            self.links.new(self.inputs.outputs["Pairs %s" % gname], node.inputs["Pairs"])
            self.links.new(self.inputs.outputs["Toggle %s" % gname], node.inputs["Toggle"])

            delete_temp_body = self.addNode("GeometryNodeDeleteGeometry", 2)
            self.links.new(temp_body_node.outputs["Attribute"], delete_temp_body.inputs["Selection"])
            self.links.new(node.outputs["Geometry"], delete_temp_body.inputs["Geometry"])
            self.links.new(delete_temp_body.outputs["Geometry"], join.inputs["Geometry"])

            toggle = self.addNode("GeometryNodeSwitch", 3)
            toggle.input_type = 'FLOAT'
            self.links.new(self.inputs.outputs["Toggle %s" % gname], toggle.inputs["Switch"])
            self.links.new(self.inputs.outputs["Mask %s" % gname], toggle.inputs["True"])

            # Limit selection to the geograft edges
            graft_edge_attr = self.addNode("GeometryNodeInputNamedAttribute", 3)
            graft_edge_attr.data_type = 'BOOLEAN'

            self.links.new(self.inputs.outputs["Edge %s" % gname], graft_edge_attr.inputs["Name"])

            # Connect the edge vertex group attribute to the merge by distance selection (name is the same on the graft & body object)
            if graft_count == 1:
                self.links.new(graft_edge_attr.outputs["Attribute"], merge.inputs["Selection"])
            # For multiple geografts, we need to add the edges together to feed to the merge by distance selection
            else:
                # Only add another add node if we're not on the last graft
                if node_counter != 2:
                    add_edge_node_counter += 1
                    # Add nodes to combine any edges from multiple grafts, which will then limit the merge-by-distance verts
                    add_edge_node = self.addNode("ShaderNodeMath", 5)
                    add_edge_node.operation = 'ADD'
                    add_edge_nodes[add_edge_node_counter] = add_edge_node
                    if add_edge_node_counter > 1:
                        prev_add_node = add_edge_nodes[add_edge_node_counter-1]

                # Depending on if we're on the first/middle/last/etc... add node, we have to connect the switch output
                # to the first or second value of the add node

                if node_counter % 2 != 0:
                    if node_counter == 1:
                        self.links.new(graft_edge_attr.outputs["Attribute"], add_edge_node.inputs[0])
                    else:
                        self.links.new(graft_edge_attr.outputs["Attribute"], add_edge_node.inputs[1])

                if 'prev_add_node' in locals():
                    self.links.new(prev_add_node.outputs["Value"], add_edge_node.inputs[0])
                if node_counter >= 2:
                    self.links.new(graft_edge_attr.outputs["Attribute"], add_edge_node.inputs[1])
                # elif 'prev_add_node' in locals():
                #     self.links.new(graft_edge_attr.outputs["Attribute"], prev_add_node.inputs[1])

                # On the last graft geograft offset
                if node_counter == graft_count:
                    self.links.new(add_edge_node.outputs["Value"], merge.inputs["Selection"])

            # Delete the geograft masks
            delete_mask = self.addNode("GeometryNodeDeleteGeometry", 4)
            self.links.new(last.outputs["Geometry"], delete_mask.inputs["Geometry"])
            self.links.new(toggle.outputs["Output"], delete_mask.inputs["Selection"])
            last = delete_mask

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

