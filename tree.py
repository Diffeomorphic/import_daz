# Copyright (c) 2016-2022, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
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
from .utils import *

NCOLUMNS = 20
XSIZE = 300
YSIZE = 250


class Tree:
    def __init__(self, owner):
        self.type = 'TREE'
        self.owner = owner
        self.column = 1
        self.ycoords = NCOLUMNS*[2*YSIZE]
        self.nodes = None
        self.links = None
        self.groups = {}

    def __repr__(self):
        return ("<%s %s %s %s>" % (self.type, self.owner.rna, self.nodes, self.links))

    def getValue(self, channel, default):
        return self.owner.getValue(channel, default)


    def addNode(self, stype, col=None, size=0, label=None, parent=None):
        if col is None:
            col = self.column
        col = max(0, min(col, NCOLUMNS-1))
        node = self.nodes.new(type = stype)
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= (YSIZE + size)
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node


    def addColumn(self):
        self.column += 1
        if self.column >= NCOLUMNS:
            print("Material has too many columns: %s" % self.owner.name)
            self.column = NCOLUMNS-10


    def addGroup(self, classdef, name, col=None, size=0, args=[], force=False):
        if col is None:
            col = self.column
        node = self.addNode(self.nodeGroupType, col, size=size)
        node.name = node.label = name
        group = classdef()
        if name in bpy.data.node_groups.keys() and not force:
            tree = bpy.data.node_groups[name]
            if group.checkSockets(tree):
                node.node_tree = tree
                return node
        group.create(node, name, self)
        group.addNodes(args)
        node.node_tree.name = name
        return node


def addNodeGroup(classdef, name):
    if name in bpy.data.node_groups.keys():
        return bpy.data.node_groups[name]
    group = classdef()
    group.create(name)
    group.addNodes()
    return group.group

# ---------------------------------------------------------------------
#   NodeGroup
# ---------------------------------------------------------------------

class NodeGroup:
    def __init__(self):
        self.insockets = []
        self.outsockets = []

    def __repr__(self):
        return ("<Group %s %s>" % (self.nodeTreeType, self.nodeGroupType))

    def make(self, name, ncols):
        self.group = bpy.data.node_groups.new(name, self.nodeTreeType)
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode("NodeGroupInput", 0)
        self.outputs = self.addNode("NodeGroupOutput", ncols)
        self.ncols = ncols

    def create(self, node, name, parent, ncols):
        self.make(name, ncols)
        node.name = name
        node.node_tree = self.group
        self.parent = parent

    def checkSockets(self, tree):
        for socket in self.insockets:
            if socket not in tree.inputs.keys():
                print("Missing insocket: %s" % socket)
                return False
        for socket in self.outsockets:
            if socket not in tree.outputs.keys():
                print("Missing outsocket: %s" % socket)
                return False
        return True

    def hideSlot(self, slot):
        if bpy.app.version >= (2,90,0):
            self.group.inputs[slot].hide_value = True

    def setMinMax(self, slot, default, min, max):
        self.group.inputs[slot].default_value = default
        self.group.inputs[slot].min_value = min
        self.group.inputs[slot].max_value = max

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def findNodes(tree, nodeType):
    nodes = []
    for node in tree.nodes.values():
        if node.type == nodeType:
            nodes.append(node)
    return nodes


def findNode(tree, ntypes):
    if isinstance(ntypes, list):
        for ntype in ntypes:
            node = findNode(tree, ntype)
            if node:
                return node
    for node in tree.nodes:
        if node.type == ntypes:
            return node
    return None


def findLinksFrom(tree, ntype):
    links = []
    for link in tree.links:
        if link.from_node.type == ntype:
            links.append(link)
    return links


def findLinksTo(tree, ntype):
    links = []
    for link in tree.links:
        if link.to_node.type == ntype:
            links.append(link)
    return links


def getLinkFrom(tree, node, slot):
    for link in tree.links:
        if (link.from_node == node and
            link.from_socket.name == slot):
            return link
    return None


def getLinkTo(tree, node, slot):
    for link in tree.links:
        if (link.to_node == node and
            link.to_socket.name == slot):
            return link
    return None


def getSocket(sockets, id):
    for socket in sockets:
        if socket.identifier == id:
            return socket
    return None

#-------------------------------------------------------------
#   Prune node tree
#-------------------------------------------------------------

def pruneNodeTree(tree):
    marked = {}
    output = False
    for node in tree.nodes:
        marked[node.name] = False
        if "Output" in node.name:
            marked[node.name] = True
            output = True
    if not output:
        print("No output node")
        return marked
    nmarked = 0
    n = 1
    while n > nmarked:
        nmarked = n
        n = 1
        for link in tree.links:
            if marked[link.to_node.name]:
                marked[link.from_node.name] = True
                n += 1

    for node in tree.nodes:
        node.select = False
        if not marked[node.name]:
            tree.nodes.remove(node)
    return marked

# ---------------------------------------------------------------------
#   TNode and TLink
# ---------------------------------------------------------------------

class TNode:
    def __init__(self, node):
        self.orig = node
        self.node = None
        ignore = ( "rna_type", "type", "dimensions", "inputs", "outputs", "internal_links", "select", "interface" )
        self.attributes = {}
        for attr in node.bl_rna.properties:
            if not attr.identifier in ignore and not attr.identifier.split("_")[0] == "bl":
                self.attributes[attr.identifier] = getattr(node, attr.identifier)


    def make(self, tree):
        self.node = tree.nodes.new(self.orig.bl_idname)
        self.node.name = self.orig.name
        self.node.location = self.orig.location
        self.node.width = self.orig.width
        if self.orig.type == 'GROUP' and self.orig.name in bpy.data.node_groups.keys():
            self.node.node_tree = bpy.data.node_groups[self.orig.name]
        for key,value in self.attributes.items():
            try:
                setattr(self.node, key, value)
            except AttributeError:
                print("Cannot set attribute %s: %s = %s" % (self.node.name, key, value))
                pass
        self.setValues(self.node.inputs, self.orig.inputs)
        self.setValues(self.node.outputs, self.orig.outputs)


    def setValues(self, sockets1, sockets2):
        for socket1,socket2 in zip(sockets1, sockets2):
            try:
                socket1.default_value = socket2.default_value
            except AttributeError:
                pass

#-------------------------------------------------------------
#   Copy node tree
#-------------------------------------------------------------

def copyNodeTree(src, trg):
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

    def copy_nodes(src, trg):
        input_attributes = ( "default_value", "name" )
        output_attributes = ( "default_value", "name" )
        for node in src.nodes:
            new_node = trg.nodes.new( node.bl_idname )
            node_attributes = get_node_attributes( node )
            copy_attributes( node_attributes, node, new_node )
            for i, inp in enumerate(node.inputs):
                copy_attributes( input_attributes, inp, new_node.inputs[i] )
            for i, out in enumerate(node.outputs):
                copy_attributes( output_attributes, out, new_node.outputs[i] )

    def copy_links(src, trg):
        for node in src.nodes:
            new_node = trg.nodes[ node.name ]
            for i, inp in enumerate( node.inputs ):
                for link in inp.links:
                    connected_node = trg.nodes[ link.from_node.name ]
                    trg.links.new( connected_node.outputs[ link.from_socket.name ], new_node.inputs[i] )

    trg.nodes.clear()
    copy_nodes( src, trg )
    copy_links( src, trg )

#-------------------------------------------------------------
#   Save node trees
#-------------------------------------------------------------

def saveTree(tree, struct, treelist, taken):
    def getImage(img):
        struct = {}
        if img.filepath:
            struct["filepath"] = img.filepath.replace("\\", "/")
        include = ["alpha_mode"]
        for attr in include:
            if hasattr(img, attr):
                struct[attr] = getattr(img, attr)
        return struct

    def saveSingleTree(tree, struct, nodegroups):
        nodelist = []
        struct["nodes"] = nodelist
        ignore = ( "inputs", "outputs", "rna_type", "internal_links", "interface", "texture_mapping", "color_mapping", "image_user")
        for node in tree.nodes:
            nodestruct = {}
            nodelist.append(nodestruct)
            words = str(node.rna_type).split('"')
            nodestruct["rna_type"] = words[1]
            for attr in node.bl_rna.properties:
                data = getattr(node, attr.identifier)
                if (attr.identifier in ignore or
                    attr.identifier.split("_")[0] == "bl"):
                    pass
                elif isinstance(data, bpy.types.Image):
                    nodestruct[attr.identifier] = getImage(data)
                elif isinstance(data, bpy.types.ShaderNodeTree):
                    nodestruct[attr.identifier] = data.name
                    nodegroups[data.name] = data
                else:
                    nodestruct[attr.identifier] = data

            inattrs = ["name", "type", "default_value"]
            instruct = {}
            nodestruct["inputs"] = instruct
            for socket in node.inputs:
                sockstruct = {}
                instruct[socket.identifier] = sockstruct
                for attr in inattrs:
                    try:
                        sockstruct[attr] = getattr(socket, attr)
                    except AttributeError:
                        pass

            outattrs = ["name", "type", "default_value"]
            outstruct = {}
            nodestruct["outputs"] = outstruct
            for socket in node.outputs:
                sockstruct = {}
                outstruct[socket.identifier] = sockstruct
                for attr in outattrs:
                    try:
                        sockstruct[attr] = getattr(socket, attr)
                    except AttributeError:
                        pass

        linklist = []
        struct["links"] = linklist
        for link in tree.links:
            linkstruct = {}
            linklist.append(linkstruct)
            linkstruct["from_node"] = link.from_node.name
            linkstruct["to_node"] = link.to_node.name
            linkstruct["from_socket"] = link.from_socket.identifier
            linkstruct["to_socket"] = link.to_socket.identifier

    nodegroups = {}
    saveSingleTree(tree, struct, nodegroups)
    n = 5
    while n > 0:
        n -= 1
        nodetrees = {}
        for gname,group in list(nodegroups.items()):
            if gname not in taken:
                taken.append(gname)
                gstruct = {"name" : gname}
                nodetrees[gname] = gstruct
                saveSingleTree(group, gstruct, nodegroups)
        if nodetrees:
            treelist.append(nodetrees)
        else:
            return

#-------------------------------------------------------------
#   Load node trees
#-------------------------------------------------------------

def loadTree(struct, tree):
    def getShaderGroup(gname):
        from .cgroup import ShaderGroups
        for key,data in ShaderGroups.items():
            if gname == data[1]:
                return key
        return None

    socketTypes = {
        "VALUE" : "NodeSocketFloat",
        "SHADER" : "NodeSocketShader",
        "RGBA" : "NodeSocketColor",
        "VECTOR" : "NodeSocketVector",
    }

    tree.nodes.clear()
    nodes = {}
    ignore = ["rna_type", "type", "dimensions"]
    for nodestruct in struct["nodes"]:
        rna_type = nodestruct["rna_type"]
        node = tree.nodes.new(rna_type)
        nodes[nodestruct["name"]] = node
        for key,data in nodestruct.items():
            if key in ignore:
                pass
            elif key == "inputs":
                if rna_type == "NodeGroupOutput":
                    for id,info in data.items():
                        stype = socketTypes.get(info["type"])
                        if stype:
                            socket = node.inputs.new(stype, id)
                            socket.name = info["name"]
                    continue
                for socket in node.inputs:
                    info = data.get(socket.identifier)
                    if info and "default_value" in info.keys():
                        socket.default_value = info["default_value"]
            elif key == "outputs":
                if rna_type == "NodeGroupInput":
                    for id,info in data.items():
                        stype = socketTypes.get(info["type"])
                        if stype:
                            socket = node.outputs.new(stype, id)
                            socket.name = info["name"]
                            print("ADD", socket.identifier, socket.name)
                    for socket in node.outputs:
                        print("AA", socket.identifier, socket.name)
                    print("NN", node)
                    continue
                for socket in node.outputs:
                    info = data.get(socket.identifier)
                    if info and "default_value" in info.keys():
                        socket.default_value = info["default_value"]
            elif key == "image":
                filepath = data.get("filepath")
                img = node.image = bpy.data.images.load(filepath)
                if img:
                    for key,value in data.items():
                        setattr(img, key, value)
            elif key == "node_tree":
                group = bpy.data.node_groups.get(data)
                if group:
                    node.node_tree = group
                elif data[0:3] == "DAZ":
                    use = getShaderGroup(data)
                    oper = "bpy.ops.daz.make_shader_groups(%s=True)" % use
                    print(oper)
                    # Yes, I know using eval is bad, but how else to change keyword dynamically?
                    eval(oper)
                    group = bpy.data.node_groups.get(data)
                    if group:
                        node.node_tree = group
            else:
                try:
                    setattr(node, key, data)
                except AttributeError:
                    print("WRONG", key)

    def getSocket(sockets, id):
        for socket in sockets:
            if socket.identifier == id:
                return socket
        return None

    #return
    for linkstruct in struct["links"]:
        from_node = nodes.get(linkstruct["from_node"])
        to_node = nodes.get(linkstruct["to_node"])
        if from_node and to_node:
            from_socket = getSocket(from_node.outputs, linkstruct["from_socket"])
            to_socket = getSocket(to_node.inputs, linkstruct["to_socket"])
            if from_socket and to_socket:
                tree.links.new(from_socket, to_socket)
            else:
                continue
                print("NN", from_node, to_node)
                print("FF", linkstruct["from_socket"], from_socket)
                print("TT", linkstruct["to_socket"], to_socket)
                for socket in from_node.outputs:
                    print("SS", socket.identifier, socket.name)
                halt


def loadNodeTrees(treelist, tree, type):
    treelist.reverse()
    x = 0
    for nodetrees in treelist:
        for gname,gstruct in nodetrees.items():
            group = bpy.data.node_groups.get(gname)
            if True or group is None:
                group = bpy.data.node_groups.new(gname, type)
                print("DEF", gname, group.name)
                node = tree.nodes.new("ShaderNodeGroup")
                node.location = (x, 0)
                x += 200
                loadTree(gstruct, group)
                node.node_tree = group
