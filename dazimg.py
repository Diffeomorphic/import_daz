# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Vector, Color
from .error import DazError
from .utils import *

#-------------------------------------------------------------
#   Copy node tree
#-------------------------------------------------------------

def copyNode(node, trg):
    def copy_attributes(attributes, old_prop, new_prop):
        for attr in attributes:
            if hasattr( new_prop, attr ):
                try:
                    setattr( new_prop, attr, getattr( old_prop, attr ) )
                except AttributeError:
                    pass

    def get_node_attributes(node):
        ignore_attributes = ( "rna_type", "type", "dimensions", "inputs", "outputs", "internal_links", "select")
        attributes = []
        for attr in node.bl_rna.properties:
            if not attr.identifier in ignore_attributes and not attr.identifier.split("_")[0] == "bl":
                attributes.append(attr.identifier)
        return attributes

    input_attributes = ( "default_value", "name" )
    output_attributes = ( "default_value", "name" )
    new_node = trg.nodes.new( node.bl_idname )
    node_attributes = get_node_attributes( node )
    copy_attributes( node_attributes, node, new_node )
    for i, inp in enumerate(node.inputs):
        copy_attributes( input_attributes, inp, new_node.inputs[i] )
    for i, out in enumerate(node.outputs):
        copy_attributes( output_attributes, out, new_node.outputs[i] )
    return new_node


def copyLinks(src, trg):
    for node in src.nodes:
        new_node = trg.nodes[ node.name ]
        for i, inp in enumerate( node.inputs ):
            for link in inp.links:
                connected_node = trg.nodes[ link.from_node.name ]
                trg.links.new( connected_node.outputs[ link.from_socket.name ], new_node.inputs[i] )


def copyNodeTree(src, trg):
    trg.nodes.clear()
    for node in src.nodes:
        copyNode(node, trg)
    copyLinks( src, trg )

#-------------------------------------------------------------
#   CtreeInfo
#-------------------------------------------------------------

class CtreeInfo:
    def __init__(self, node, tex, after, before):
        self.name = node.name
        self.image = tex.image
        self.after = [self.getStruct(node) for node in after]
        self.before = [self.getStruct(node) for node in before]

    def getStruct(self, node):
        struct = {}
        struct["type"] = node.type
        for key,socket in node.inputs.items():
            value = socket.default_value
            if isinstance(value, (int, float, str)):
                struct[key] = value
            elif isinstance(value, (Vector, Color)):
                struct[key] = tuple(value)
        return struct

    def matchNode(self, node, other):
        struct = self.getStruct(node)
        for key,value in struct.items():
            if value != other.get(key):
                if GS.verbosity >= 3:
                    print("DIMG mismatch: %s %s:\n  %s != %s" % (self.name, key, value, other.get(key)))
                return False
        return True

    def match(self, tex, after, before):
        if (self.image != tex.image or
            len(after) != len(self.after) or
            len(before) != len(self.before)):
            return False
        for node,other in zip(after, self.after):
            if not self.matchNode(node, other):
                return False
        for node,other in zip(before, self.before):
            if not self.matchNode(node, other):
                return False
        return True

    def __repr__(self):
        string = "TEX %s\n" % self.image
        for struct in self.before:
            string += "BF %s\n" % struct.items()
        for struct in self.after:
            string += "AF %s\n" % struct.items()
        return string

#-------------------------------------------------------------
#   makeDazImages
#-------------------------------------------------------------

def makeDazImages(tree, ctrees):
    from .cgroup import CyclesGroup
    from .tree import addGroupInput, addGroupOutput, beautifyNodeTree

    def getVectorSocket(sockets):
        socket = sockets.get("Vector")
        if socket:
            return socket
        else:
            return sockets.get("UV")

    def getBefore(node):
        socket = getVectorSocket(node.inputs)
        if socket:
            for link in socket.links:
                fromnode = link.from_node
                if (fromnode.type in ['VECT_MATH', 'MAPPING'] and
                    len(fromnode.outputs["Vector"].links) == 1):
                    before.append(fromnode)
                    getBefore(fromnode)

    def getAfter(node):
        if node.type == 'GAMMA':
            gamma = node.inputs["Gamma"].default_value
            if abs(gamma - 1/2.2) < 1e-4:
                linear.append(node)
        socket = node.outputs["Color"]
        if len(socket.links) == 1:
            for link in socket.links:
                if link.to_node.type in ['GAMMA', 'INVERT']:
                    after.append(link.to_node)
                    getAfter(link.to_node)

    dazimgs = []
    if GS.useDazImages:
        for node in tree.nodes:
            if node.type == 'TEX_IMAGE':
                before = []
                after = []
                linear = []
                getBefore(node)
                getAfter(node)
                if (before or
                    len(after) > 1 or
                    (after and len(linear) == 0)):
                    dazimgs.append((node, after, before))

    def makeCtree(grpnode, tex, after, before):
        ctree = CyclesGroup()
        name = "DIMG %s" % tex.label
        ctree.create(grpnode, name, None, len(before) + len(after))
        addGroupInput(ctree.group, "NodeSocketVector", "Vector")
        ctree.hideSlot("Vector")
        addGroupOutput(ctree.group, "NodeSocketColor", "Color")
        addGroupOutput(ctree.group, "NodeSocketFloat", "Alpha")
        return ctree

    def getCtree(ctrees, tex, after, before):
        for ctree,info in ctrees:
            if info.match(tex, after, before):
                return ctree

    deletes = []
    for tex,after,before in dazimgs:
        after.reverse()
        before.reverse()

        grpnode = tree.nodes.new("ShaderNodeGroup")
        grpnode.location = tex.location
        grpnode.width = 290
        ctree = getCtree(ctrees, tex, after, before)
        if ctree:
            grpnode.node_tree = ctree.group
            if GS.verbosity >= 3:
                print("DIMG match: %s" % grpnode.node_tree.name)
        else:
            ctree = makeCtree(grpnode, tex, after, before)
            info = CtreeInfo(grpnode, tex, after, before)
            ctrees.append((ctree, info))

        first = (before[0] if before else tex)
        insocket = getVectorSocket(first.inputs)
        if insocket is None:
            continue
        for link in list(insocket.links):
            tree.links.new(link.from_socket, grpnode.inputs["Vector"])
        outsocket = ctree.inputs.outputs["Vector"]
        for node in before:
            cnode = copyNode(node, ctree)
            cnode.hide = False
            insocket = getVectorSocket(cnode.inputs)
            ctree.links.new(outsocket, insocket)
            outsocket = getVectorSocket(cnode.outputs)
        ctex = copyNode(tex, ctree)
        ctex.hide = False
        ctex.extension = 'REPEAT'
        ctree.links.new(outsocket, getVectorSocket(ctex.inputs))

        last = (after[0] if after else tex)
        for link in list(last.outputs["Color"].links):
            tree.links.new(grpnode.outputs["Color"], link.to_socket)
        for link in list(tex.outputs["Alpha"].links):
            tree.links.new(grpnode.outputs["Alpha"], link.to_socket)
        insocket = ctree.outputs.inputs["Color"]
        for node in after:
            cnode = copyNode(node, ctree)
            cnode.hide = False
            ctree.links.new(cnode.outputs["Color"], insocket)
            insocket = cnode.inputs["Color"]
        ctree.links.new(ctex.outputs["Color"], insocket)
        ctree.links.new(ctex.outputs["Alpha"], ctree.outputs.inputs["Alpha"])
        beautifyNodeTree(ctree)
        for node in after + before + [tex]:
            deletes.append(node)

    for node in set(deletes):
        tree.nodes.remove(node)
