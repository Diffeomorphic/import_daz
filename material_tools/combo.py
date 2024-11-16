#  DAZ Materials - Tools for editing materials imported with the DAZ Importer
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
from ..utils import *
from ..error import *
from ..matsel import MaterialSelector
from ..material import NORMAL
from ..tree import TNode, getSocket, XSIZE, YSIZE, beautifyNodeTree

# ---------------------------------------------------------------------
#   Combo materials
# ---------------------------------------------------------------------

class DAZ_OT_MakeComboMaterials(MaterialSelector, DazPropsOperator):
    bl_idname = "daz.make_combo_material"
    bl_label = "Make Combo Material"
    bl_description = "Create a combo node group for selected materials"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawActive(context)
        MaterialSelector.draw(self, context)

    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)

    def run(self, context):
        ob = context.object
        tree = ob.active_material.node_tree
        self.useBump = False
        self.clearData()
        self.findOutputs(tree)
        for socket in self.outputs.values():
            self.selectNodes(socket, "")
        group,gname = self.makeGroup(ob)
        beautifyNodeTree(group)
        mats = []
        for mat in ob.data.materials:
            if (mat and
                self.useMaterial(mat) and
                mat.node_tree and
                mat != ob.active_material):
                mats.append(mat)
        mats.append(ob.active_material)
        for mat in mats:
            self.clearData()
            self.findOutputs(mat.node_tree)
            for socket in self.outputs.values():
                self.selectNodes(socket, "")
            self.replaceNodes(mat.node_tree, group, gname)
            beautifyNodeTree(mat.node_tree)


    def clearData(self):
        self.outputs = {}
        self.inputs = {}
        self.nodes = {}
        self.tnodes = {}
        self.links = []


    def findOutputs(self, tree):
        def skipShells(node, socket, slot):
            for link in socket.links:
                fromnode = link.from_node
                if (fromnode.type == 'GROUP' and
                    not fromnode.node_tree.name[0:4] == "DAZ " and
                    slot in fromnode.inputs.keys()):
                    return skipShells(fromnode, fromnode.inputs[slot], slot)
            return socket,node

        from ..tree import findNodes
        self.cycles = None
        for node in findNodes(tree, 'OUTPUT_MATERIAL'):
            self.outputs["BSDF"], self.cycles = skipShells(node, node.inputs["Surface"], "BSDF")
            self.outputs["Volume"],_ = skipShells(node, node.inputs["Volume"], "Volume")
            self.outputs["Displacement"],_ = skipShells(node, node.inputs["Displacement"], "Displacement")


    def selectNodes(self, socket, slot):
        def isMappingGroup(node):
            if node.type != 'GROUP' or node.node_tree.name[0:4] == "DAZ ":
                return False
            for node1 in node.node_tree.nodes:
                if node1.type == 'TEX_IMAGE':
                    return True
            return False

        from ..cycles import isGroupType
        for link in socket.links:
            node = link.to_node
            if node.type in ['MIX_RGB', 'MIX', 'MATH', 'GAMMA', 'INVERT']:
                pass
            elif isGroupType(node, ("DAZ Log Color", "DAZ Color Effect", "DAZ Tinted Effect")):
                pass
            elif node.type == 'GROUP':
                treename = node.node_tree.name
                if treename[0:4] == "DAZ ":
                    slot = "%s:%s" % (treename[4:], link.to_socket.name)
                elif treename.endswith("Combo"):
                    raise DazError("Combo group already exists")
            else:
                if node.type[0:5] == "BSDF_":
                    key = node.type[5:]
                else:
                    key = node.type
                slot = "%s:%s" % (key.capitalize(), link.to_socket.name)
            node = link.from_node
            if node.type == 'TEX_IMAGE' or isMappingGroup(node):
                if slot:
                    if slot not in self.inputs.keys():
                        self.inputs[slot] = []
                    self.inputs[slot].append(link)
            else:
                self.links.append(link)
                if node.name not in self.nodes.keys():
                    self.nodes[node.name] = node
                    self.tnodes[node.name] = TNode(node)
                if isGroupType(node, ("DAZ Color Effect", "DAZ Tinted Effect")):
                    if slot.endswith("Fac"):
                        self.selectNodes(node.inputs["Fac"], slot)
                    elif slot.endswith("Color"):
                        self.selectNodes(node.inputs["Color"], slot)
                else:
                    for socket in node.inputs:
                        self.selectNodes(socket, slot)
                if node.type == 'BUMP':
                    self.useBump = True


    def makeGroup(self, ob):
        from ..tree import addGroupInput, addGroupOutput
        gname = "%s:%s Combo" % (ob.name, ob.active_material.name)
        group = bpy.data.node_groups.new(gname, "ShaderNodeTree")
        xlocs = [node.location[0] for node in self.nodes.values()]
        innode = group.nodes.new("NodeGroupInput")
        innode.location = (min(xlocs) - XSIZE, 2*YSIZE)
        outnode = group.nodes.new("NodeGroupOutput")
        outnode.location = (max(xlocs) + XSIZE, 2*YSIZE)
        for key,links in self.inputs.items():
            if links and links[0].from_socket.type == 'VALUE':
                socket = addGroupInput(group, "NodeSocketFloat", key)
            else:
                socket = addGroupInput(group, "NodeSocketColor", key)
                if key.split(":",1)[0] == "Normal_map":
                    socket.default_value = NORMAL
        if self.useBump:
            addGroupInput(group, "NodeSocketFloat", "Bump Distance")
        addGroupOutput(group, "NodeSocketShader", "BSDF")
        addGroupOutput(group, "NodeSocketShader", "Volume")
        addGroupOutput(group, "NodeSocketVector", "Displacement")

        for tnode in self.tnodes.values():
            tnode.make(group)
        if self.useBump and "Bump" in self.tnodes.keys():
            bump = self.tnodes["Bump"].node
            group.links.new(innode.outputs["Bump Distance"], bump.inputs["Distance"])

        for link in self.links:
            if link.from_node.name in self.tnodes.keys():
                fromnode = self.tnodes[link.from_node.name].node
                fromsocket = getSocket(fromnode.outputs, link.from_socket.identifier)
                if link.to_node.name in self.tnodes.keys():
                    tonode = self.tnodes[link.to_node.name].node
                    tosocket = getSocket(tonode.inputs, link.to_socket.identifier)
                    group.links.new(fromsocket, tosocket)
                elif fromsocket.name in self.outputs.keys():
                    group.links.new(fromsocket, outnode.inputs[fromsocket.name])
                elif fromsocket.name == "BSDF":
                    group.links.new(fromsocket, outnode.inputs["BSDF"])
                else:
                    print("MISS", fromsocket.name, self.outputs.keys())
        for slot,links in self.inputs.items():
            self.linkInputs(group, links, innode.outputs.get(slot))
        return group, gname


    def linkInputs(self, group, links, fromsocket):
        if fromsocket is None:
            return
        for link in links:
            if link.to_node.name in self.tnodes.keys():
                tonode = self.tnodes[link.to_node.name].node
                tosocket = getSocket(tonode.inputs, link.to_socket.identifier)
                group.links.new(fromsocket, tosocket)


    def replaceNodes(self, tree, group, gname):
        skin = tree.nodes.new("ShaderNodeGroup")
        skin.name = gname
        skin.label = gname
        skin.node_tree = group
        skin.location = (self.cycles.location[0] - 1.5*XSIZE, 2*YSIZE)
        skin.width = 1.5*XSIZE
        for slot,links in self.inputs.items():
            if slot in skin.inputs.keys():
                for link in links:
                    tree.links.new(link.from_socket, skin.inputs[slot])
            else:
                print("Missing slot: %s" % slot)
        if (self.useBump and
            "Bump" in self.nodes.keys() and
            "Bump Distance" in skin.inputs.keys()):
            bump = self.nodes["Bump"]
            skin.inputs["Bump Distance"].default_value = bump.inputs["Distance"].default_value
        for slot,socket in self.outputs.items():
            tree.links.new(skin.outputs[slot], socket)
        for node in self.nodes.values():
            tree.nodes.remove(node)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeComboMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
