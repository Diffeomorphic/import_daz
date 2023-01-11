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
import os
from .utils import *

NCOLUMNS = 20
XSIZE = 300
YSIZE = 250
YSTEP = 25


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


    def addNode(self, stype, col=None, size=10, label=None, parent=None):
        if col is None:
            col = self.column
        col = max(0, min(col, NCOLUMNS-1))
        node = self.nodes.new(type = stype)
        self.setLocation(node, col, size)
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node

    if bpy.app.version < (3,4,0):
        MixColor1 = 1
        MixColor2 = 2
        MixColorOut = 0
    else:
        MixColor1 = 6
        MixColor2 = 7
        MixColorOut = 2


    def addMixRgbNode(self, blendtype, col=None, parent=None):
        if bpy.app.version < (3,4,0):
            node = self.addNode("ShaderNodeMixRGB", col, size=10, parent=parent)
        else:
            node = self.addNode("ShaderNodeMix", col, size=12, parent=parent)
            node.data_type = 'RGBA'
        node.blend_type = blendtype
        a = node.inputs[self.MixColor1]
        b = node.inputs[self.MixColor2]
        out = node.outputs[self.MixColorOut]
        return node,a,b,out


    def colorOutput(self, node):
        if "Color" in node.outputs.keys():
            return node.outputs["Color"]
        elif node.type == 'MIX':
            return node.outputs[2]
        else:
            return node.outputs[0]


    def addColumn(self):
        self.column += 1
        if self.column >= NCOLUMNS:
            print("Material has too many columns: %s" % self.owner.name)
            self.column = NCOLUMNS-10


    def setLocation(self, node, col, size):
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= size*YSTEP


    def moveTex(self, tex, node):
        return
        if tex is None:
            return
        x,y = node.location
        x1,y1 = tex.location
        if x == x1:
            self.setLocation(tex, self.column-1, 2)


    def addGroup(self, classdef, name, col=None, size=10, args=[], force=False):
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


    def hideAllBut(self, node, sockets):
        for socket in node.outputs:
            if socket.name not in sockets:
                socket.hide = True

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


def getFromNode(socket):
    for link in socket.links:
        return link.from_node
    return None


def getFromSocket(socket):
    for link in socket.links:
        return link.from_socket
    return None

#-------------------------------------------------------------
#   Prune node tree
#-------------------------------------------------------------

def pruneNodeTree(tree, active=None, useDeleteUnusedNodes=True, useHideTexNodes=False, usePruneTexco=False, useHideOutputs=False):
    marked = {}
    if not tree:
        return marked

    for node in tree.nodes:
        if node.type == 'GROUP' and not node.name.startswith("DAZ "):
            pruneNodeTree(node.node_tree, None, useDeleteUnusedNodes, useHideTexNodes, usePruneTexco, useHideOutputs)

    if usePruneTexco:
        texcos = []
        links = []
        for node in tree.nodes:
            if (node.type == 'TEX_COORD' or
                (active and node.type == 'UVMAP' and node.uv_map == active.name) or
                (active and node.type == 'ATTRIBUTE' and node.attribute_name == active.name)):
                ok = True
                for link in node.outputs["UV"].links:
                    if link.to_node.type in ['TEX_IMAGE']:
                        links.append(link)
                    else:
                        ok = False
                if ok:
                    texcos.append(node)
        for link in links:
            tree.links.remove(link)
        for node in texcos:
            tree.nodes.remove(node)

    for node in tree.nodes:
        for socket in node.outputs:
            if not socket.links:
                socket.hide = useHideOutputs

    for node in tree.nodes:
        if node.type in ['TEX_IMAGE']:
           node.hide = useHideTexNodes

    if useDeleteUnusedNodes:
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

class TreeSaver:
    def __init__(self, type, useRelativePaths):
        self.type = type
        if type == "material_nodetree":
            self.entrykey = "materials"
            self.libkey = "material_library"
        self.useRelativePaths = useRelativePaths
        self.taken = []
        self.nodetrees = {}
        self.textures = {}
        self.channels = {}
        self.nodegroups = {}
        self.entries = []


    def addEntry(self, name):
        self.entry = { "name" : name }
        self.entries.append(self.entry)
        return self.entry


    def saveFile(self, filepath):
        from .load_json import saveJson
        struct = {
            "type" : self.type,
            "blender" : bpy.app.version,
            "textures" : self.textures,
            "nodetrees" : self.nodetrees,
            self.entrykey : self.entries
        }
        saveJson(struct, filepath)


    def getImage(self, name, img):
        struct = {}
        if img.filepath:
            if self.useRelativePaths:
                filepath = GS.getRelativePath(img.filepath)
            else:
                filepath = img.filepath.replace("\\", "/")
        struct["filepath"] = filepath
        include = ["alpha_mode"]
        for attr in include:
            if hasattr(img, attr):
                struct[attr] = getattr(img, attr)
        channels = self.channels.get(filepath, [])
        if channels:
            struct["channel"] = self.getMatch(name, channels)
        return struct


    def getMatch(self, name, channels):
        for channel in channels:
            if name == channel.split(":",1)[0]:
                return channel
        return channels[0]


    def saveSingleTree(self, name, tree, struct):
        name = stripName(name)
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
                    nodestruct[attr.identifier] = self.getImage(name, data)
                elif isinstance(data, bpy.types.ShaderNodeTree):
                    nodestruct[attr.identifier] = data.name
                    self.nodegroups[data.name] = data
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


    def setTextures(self, textures):
        self.textures = textures
        self.channels = {}
        for channel,imgfile in textures.items():
            if imgfile not in self.channels.keys():
                self.channels[imgfile] = []
            self.channels[imgfile].append(channel)


    def saveTree(self, name, tree):
        self.saveSingleTree(name, tree, self.entry)
        n = 5
        found = True
        while found and n > 0:
            n -= 1
            found = False
            for gname,group in list(self.nodegroups.items()):
                if gname not in self.taken:
                    found = True
                    self.taken.append(gname)
                    gstruct = {"name" : gname}
                    self.nodetrees[gname] = gstruct
                    self.saveSingleTree(gname, group, gstruct)

#-------------------------------------------------------------
#   Load node trees
#-------------------------------------------------------------

class TreeLoader:
    def __init__(self, type, reuseNodegroups):
        self.type = type
        if type == "material_nodetree":
            self.treetype = "ShaderNodeTree"
            self.grptype = "ShaderNodeGroup"
            self.entrykey = "materials"
        else:
            raise DazError("Not yet imlemented: %s" % type)
        self.reuseNodegroups = reuseNodegroups
        self.nodetrees = []
        self.textures = {}
        self.entries = []
        self.dummy = None
        self.x = 0
        self.taken = {}
        self.missing = {}


    def loadFile(self, filepath):
        from .load_json import loadJson
        struct = loadJson(filepath)
        if struct.get("type") != self.type:
            raise DazError("File does not contain a %s" % treetype)
        if struct["blender"] != list(bpy.app.version):
            print("Warning: Wrong Blender version")
        self.nodetrees = struct["nodetrees"]
        self.entries = struct[self.entrykey]


    def loadNodeGroups(self, tree):
        self.dummy = tree
        for grpname,grpstruct in self.nodetrees.items():
            self.loadNodeGroup(grpname)


    def loadNodeGroup(self, gname):
        if gname in self.taken.keys():
            return self.taken[gname]
        if self.reuseNodegroups:
            group = bpy.data.node_groups.get(gname)
            if group:
                print("Reuse node group: %s" % group.name)
                self.taken[gname] = group
                return group
        gstruct = self.nodetrees[gname]
        group = bpy.data.node_groups.new(gname, self.treetype)
        print("Define node group: %s" % gname)
        self.loadInterface(gstruct, group)
        self.loadSingleTree(gstruct, group)
        node = self.dummy.nodes.new(self.grptype)
        node.location = (self.x, -600)
        self.x += 200
        node.node_tree = group
        self.taken[gname] = group
        return group


    SocketTypes = {
        "VALUE" : "NodeSocketFloat",
        "SHADER" : "NodeSocketShader",
        "RGBA" : "NodeSocketColor",
        "VECTOR" : "NodeSocketVector",
    }


    def loadInterface(self, struct, tree):
        interface = []
        for nodestruct in struct["nodes"]:
            rna_type = nodestruct["rna_type"]
            data = {}
            if rna_type == "NodeGroupOutput":
                data = nodestruct.get("inputs", {})
            elif rna_type == "NodeGroupInput":
                data = nodestruct.get("outputs", {})
            if data:
                for id,info in data.items():
                    words = id.split("_",1)
                    if len(words) == 2 and words[1].isdigit():
                        interface.append((int(words[1]), id, info))
        interface.sort()
        for n,id,info in interface:
            socket = None
            stype = self.SocketTypes.get(info["type"])
            if not stype:
                continue
            elif id.startswith("Input"):
                socket = tree.inputs.new(stype, info["name"])
            elif id.startswith("Output"):
                socket = tree.outputs.new(stype, info["name"])
            if "default_value" in info.keys():
                socket.default_value = info["default_value"]


    def getFilepath(self, data):
        channel = data.get("channel")
        path = self.textures.get(channel)
        if path:
            filepath = GS.getAbsPath(path)
            if os.path.exists(filepath):
                return filepath

        path = data.get("filepath")
        if not path:
            return ""
        elif path[0:2] == "//":
            filepath = path
        elif path[0] == "/":
            filepath = GS.getAbsPath(path)
        else:
            filepath = path
        if os.path.exists(filepath):
            return filepath
        else:
            self.missing[path] = filepath
            return ""


    def getSocket(self, sockets, id):
        for socket in sockets:
            if socket.identifier == id:
               return socket
        return None


    def loadSingleTree(self, struct, tree):
        tree.nodes.clear()
        x = 0
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
                    if rna_type != "NodeGroupOutput":
                        for socket in node.inputs:
                           info = data.get(socket.identifier)
                           if info and "default_value" in info.keys():
                               socket.default_value = info["default_value"]
                elif key == "outputs":
                    if rna_type != "NodeGroupInput":
                        for socket in node.outputs:
                            info = data.get(socket.identifier)
                            if info and "default_value" in info.keys():
                                socket.default_value = info["default_value"]
                elif key == "image":
                    filepath = self.getFilepath(data)
                    if filepath:
                        img = node.image = bpy.data.images.load(filepath)
                        for key,value in data.items():
                            if key not in ["filepath", "channel"]:
                                setattr(img, key, value)
                elif key == "node_tree":
                    group = bpy.data.node_groups.get(data)
                    if group is None and data not in self.taken:
                        group = self.loadNodeGroup(data)
                    node.node_tree = group
                else:
                    try:
                        setattr(node, key, data)
                    except AttributeError:
                        print("WRONG", key)

        for linkstruct in struct["links"]:
            from_node = nodes.get(linkstruct["from_node"])
            to_node = nodes.get(linkstruct["to_node"])
            if from_node and to_node:
                from_socket = self.getSocket(from_node.outputs, linkstruct["from_socket"])
                to_socket = self.getSocket(to_node.inputs, linkstruct["to_socket"])
                if from_socket and to_socket:
                    tree.links.new(from_socket, to_socket)
                else:
                    print("NN", from_node, to_node)
                    print("FF", linkstruct["from_socket"], from_socket)
                    print("TT", linkstruct["to_socket"], to_socket)
                    print("SS", [socket.identifier for socket in from_node.outputs])
                    print("RR", [socket.identifier for socket in to_node.inputs])
                    halt

