# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from .utils import *

NCOLUMNS = 20
XSIZE = 300
YSIZE = 250
YSTEP = 25

#-------------------------------------------------------------
#   Group input and output
#-------------------------------------------------------------

if BLENDER3:
    def addGroupInput(group, type, slot):
        return group.inputs.new(type, slot)

    def addGroupOutput(group, type, slot):
        return group.outputs.new(type, slot)

    def getGroupInput(group, slot):
        return group.inputs[slot]

    def getGroupInputs(group):
        return group.inputs.keys()

    def getGroupOutputs(group):
        return group.outputs.keys()
else:
    def addGroupInput(group, type, slot):
        return group.interface.new_socket(slot, socket_type=type, in_out='INPUT')

    def addGroupOutput(group, type, slot):
        return group.interface.new_socket(slot, socket_type=type, in_out='OUTPUT')

    def getGroupInput(group, slot):
        for item in group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == slot:
                return item

    def getGroupInputs(group):
        return [item.name for item in group.interface.items_tree
                if item.item_type == 'SOCKET' and item.in_out == 'INPUT']

    def getGroupOutputs(group):
        return [item.name for item in group.interface.items_tree
                if item.item_type == 'SOCKET' and item.in_out == 'OUTPUT']

#-------------------------------------------------------------
#   Mix RGB
#-------------------------------------------------------------

class MixRGB:
    if bpy.app.version < (3,4,0):
        Nodetype = "ShaderNodeMixRGB"
        Color1 = 1
        Color2 = 2
        ColorOut = 0
    else:
        Nodetype = "ShaderNodeMix"
        Color1 = 6
        Color2 = 7
        ColorOut = 2
    LegacyColor1 = 1
    LegacyColor2 = 2
    LegacyColorOut = 0


def colorOutput(node):
    if "Color" in node.outputs.keys():
        return node.outputs["Color"]
    elif node.type == 'MIX':
        return node.outputs[2]
    else:
        return node.outputs[0]

#-------------------------------------------------------------
#   Tree base class
#-------------------------------------------------------------

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

    def addNode(self, stype, col=None, size=None, label=None, parent=None):
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

    def skipSteps(self, col, size):
        self.ycoords[col] -= size*YSTEP

    def below(self, node, size):
        return node.location[1] - 2*YSIZE - size*YSTEP

    def shiftNodes(self, nodes, dx, dy):
        for node in nodes:
            x,y = node.location
            node.location = (x+dx, y+dy)


    def addMixRgbNode(self, blendtype, col=None, parent=None, size=12):
        node = self.addNode(MixRGB.Nodetype, col, size=size, parent=parent)
        if bpy.app.version >= (3,4,0):
            node.data_type = 'RGBA'
        node.blend_type = blendtype
        a = node.inputs[MixRGB.Color1]
        b = node.inputs[MixRGB.Color2]
        out = node.outputs[MixRGB.ColorOut]
        return node,a,b,out


    def addColumn(self):
        self.column += 1
        if self.column >= NCOLUMNS:
            print("Material has too many columns: %s" % self.owner.name)
            self.column = NCOLUMNS-10


    def setLocation(self, node, col, size):
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        if size is None:
            size = NodeSize.get(node.type, 0)
            if size == 0:
                print("Missing NodeSize", node.type)
        self.ycoords[col] -= size*YSTEP


    def moveTex(self, tex, node):
        return
        if tex is None:
            return
        x,y = node.location
        x1,y1 = tex.location
        if x == x1:
            self.setLocation(tex, self.column-1, 2)


    def addGroup(self, classdef, name, col=None, args=[], force=False):
        if col is None:
            col = self.column
        group = classdef()
        size = GroupSize.get(name, 10)
        node = self.addNode(self.nodeGroupType, col, size=size)
        node.name = node.label = name
        tree = bpy.data.node_groups.get(name)
        if tree and not force:
            node.node_tree = tree
            return node
        group.create(node, name, self)
        group.addNodes(args)
        tree = node.node_tree
        tree.name = name
        if tree.name != name:
            tree0 = bpy.data.node_groups[name]
            tree0.name = "%s.001" % name
            tree.name = name
        return node


def addNodeGroup(classdef, name, args=[]):
    if name in bpy.data.node_groups.keys():
        return bpy.data.node_groups[name]
    group = classdef()
    group.create(name)
    group.addNodes(args)
    return group.group

# ---------------------------------------------------------------------
#   NodeGroup
# ---------------------------------------------------------------------

class NodeGroup:
    def __init__(self):
        self.insockets = []
        self.outsockets = []
        self.nodeTreeType = "ShaderNodeTree"
        self.nodeGroupType = "ShaderNodeGroup"

    def __repr__(self):
        return ("<Group %s %s>" % (self.nodeTreeType, self.nodeGroupType))


    def make(self, name, ncols):
        self.group = bpy.data.node_groups.new(name, self.nodeTreeType)
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode("NodeGroupInput", 0)
        self.outputs = self.addNode("NodeGroupOutput", ncols)
        self.ncols = ncols


    def remake(self, group, parent):
        self.group = group
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.parent = parent
        for node in group.nodes:
            if node.type == 'GROUP_INPUT':
                self.inputs = node
            elif node.type == 'GROUP_OUTPUT':
                self.outputs = node


    def create(self, node, name, parent, ncols):
        self.make(name, ncols)
        node.name = name
        node.node_tree = self.group
        self.parent = parent


    def checkSockets(self, tree):
        inputs = getGroupInputs(tree)
        outputs = getGroupOutputs(tree)
        for socket in self.insockets:
            if socket not in inputs:
                print("Missing insocket: %s" % socket)
                return False
        for socket in self.outsockets:
            if socket not in outputs:
                print("Missing outsocket: %s" % socket)
                return False
        return True


    def hideSlot(self, slot):
        socket = getGroupInput(self.group, slot)
        socket.hide_value = True


    def setMinMax(self, slot, default, min, max):
        socket = getGroupInput(self.group, slot)
        socket.default_value = default
        socket.min_value = min
        socket.max_value = max

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

if BLENDER3:
    PRINCIPLE_SIZE = 26
else:
    PRINCIPLE_SIZE = 14

NodeSize = {
    "BSDF_PRINCIPLED" : PRINCIPLE_SIZE,
    "BSDF_TRANSPARENT" : 5,
    "BSDF_BLACKBODY" : 5,
    "BSDF_TRANSLUCENT" : 10,
    "BSDF_ANISOTROPIC" : 7,
    "BSDF_DIFFUSE" : 7,
    "BSDF_GLOSSY" : 7,
    "BSDF_REFRACTION" : 7,
    "BSDF_HAIR" : 10,
    "SUBSURFACE_SCATTERING" : 10,
    "RGB" : 10,
    "VALUE" : 5,
    "INVERT" : 5,
    "GAMMA" : 6,
    "SEPRGB" : 7,
    "COMBRGB" : 7,
    "SEPARATE_COLOR" : 7,
    "COMBINE_COLOR" : 7,
    "SEPXYZ" : 7,
    "COMBXYZ" : 7,
    "RGBTOBW" : 7,
    "VALTORGB" : 10,
    "CLAMP" : 8,
    "MIX_RGB" : 8,
    "SHADERTORGB" : 8,
    "MIX" : 12,
    "MATH" : 8,
    "VECT_MATH" : 6,
    "TEX_IMAGE" : 12,
    "TEX_COORD" : 10,
    "TEX_ENVIRONMENT" : 10,
    "TEX_NOISE" : 8,
    "TEX_GRADIENT" : 8,
    "BACKGROUND" : 7,
    "GROUP" : 15,
    "GROUP_INPUT" : 15,
    "GROUP_OUTPUT" : 15,
    "ATTRIBUTE" : 2,
    "UVMAP" : 2,
    "FRESNEL" : 6,
    "MAPPING" : 15,
    "BEVEL" : 7,
    "NORMAL_MAP" : 7,
    "BUMP" : 8,
    "NEW_GEOMETRY" : 7,
    "HUE_SAT" : 7,
    "OUTPUT_MATERIAL" : 7,
    "OUTPUT_WORLD" : 7,
    "HAIR" : 7,
    "HAIR_INFO" : 7,
    "MAP_RANGE" : 7,
    "MIX_SHADER" : 6,
    "ADD_SHADER" : 6,
    "VOLUME_ABSORPTION" : 7,
    "VOLUME_SCATTER" : 7,
    "DISPLACEMENT" : 10,
    "VECTOR_DISPLACEMENT" : 10,
    "LIGHT_PATH" : 10,

    "BLACKBODY" : 5,
    "EMISSION" : 6,
    "OUTPUT_LIGHT" : 5,

    "OBJECT_INFO" : 10,
    "INPUT_NORMAL" : 3,
    "DELETE_GEOMETRY" : 6,
    "JOIN_GEOMETRY" : 6,
    "SET_POSITION" : 8,
    "MATERIAL_SELECTION" : 4,
    "SET_MATERIAL" : 6,
    "BOOLEAN_MATH" : 6,
    "CAPTURE_ATTRIBUTE" : 10,
    "MERGE_BY_DISTANCE" : 8,

    "INPUT_ATTRIBUTE" : 5,
    "POSITION" : 3,
    "FIELD_AT_INDEX" : 7,
    "COMPARE" : 6,
    "SWITCH" : 9,

    "FRAME" : 20,
}

GroupSize = {
    "DAZ Diffuse" : 9,
    "DAZ Log Color" : 6,
    "DAZ Weighted" : 4,
    "DAZ Color Effect" : 8,
    "DAZ Fresnel" : 10,
    "DAZ Schlick" : 10,
    "DAZ Emission" : 10,
    "DAZ One-Sided" : 6,
    "DAZ Overlay" : 9,
    "DAZ Glossy" : 12,
    "DAZ Top Coat" : 14,
    "DAZ Refraction" : 15,
    "DAZ Thin Wall" : 15,
    "DAZ Fake Caustics" : 10,
    "DAZ Transparent" : 7,
    "DAZ Invert NMap" : 10,
    "DAZ Translucent" : 8,
    "DAZ Subsurface" : 14,
    "DAZ Flakes" : 12,
    "DAZ Ray Clip" : 10,
    "DAZ Dual Lobe" : 10,
    "DAZ Dual Lobe PBR" : 10,
    "DAZ Metal" : 10,
    "DAZ Metal PBR" : 10,
    "DAZ Makeup" : 10,
    "DAZ Volume" : 10,
    "DAZ Normal" : 10,
    "DAZ Displacement" : 10,
    "DAZ Decal" : 10,
    "DAZ Principled" : 25,
    "DAZ Background" : 6,
}

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def hideAllBut(node, sockets):
    for socket in node.outputs:
        if socket.name not in sockets:
            socket.hide = True


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

def pruneNodeTree(tree,
                  active = None,
                  useDeleteUnusedNodes = True,
                  useHideTexNodes = True,
                  usePruneTexco = True,
                  useHideOutputs = True,
                  keepUnusedTextures = True,
                  useFixColorSpace = True,
                  useDazImages = True,
                  useBeautify = True,
                  useGroups = True,
                  ):
    marked = {}
    if not tree:
        return marked

    for node in tree.nodes:
        if (node.type == 'GROUP' and
            not node.name.startswith("DAZ ") and
            useGroups and
            node.outputs and
            node.node_tree not in LS.protectedGroups):
            isLie = node.node_tree.name.startswith("LIE")
            pruneNodeTree(node.node_tree,
                          None,
                          useDeleteUnusedNodes,
                          useHideTexNodes,
                          usePruneTexco,
                          useHideOutputs,
                          keepUnusedTextures,
                          useFixColorSpace,
                          (useDazImages and not isLie),
                          useBeautify,
                          useGroups)
            LS.protectedGroups.add(node.node_tree)

    def isUvPrunable(node, active):
        if node.type == 'TEX_COORD':
            for key,socket in node.outputs.items():
                if key != "UV" and len(socket.links) > 0:
                    return False
            return True
        elif active is None:
            return False
        else:
            return ((node.type == 'UVMAP' and node.uv_map == active.name) or
                    (node.type == 'ATTRIBUTE' and node.attribute_name == active.name))

    if usePruneTexco:
        removes = []
        replaces = []
        links = []
        for node in tree.nodes:
            if isUvPrunable(node, active):
                useRemove = True
                replaceLinks = []
                key = ("Vector" if node.type == 'ATTRIBUTE' else "UV")
                for link in node.outputs[key].links:
                    if link.to_node.type in ['TEX_IMAGE']:
                        links.append(link)
                    elif (node.type != 'TEX_COORD' and
                          link.to_node.type in ['VECT_MATH', 'MAPPING']):
                        replaceLinks.append(link)
                        useRemove = False
                    else:
                        useRemove = False
                if replaceLinks:
                    replaces.append((node, replaceLinks))
                elif useRemove:
                    removes.append(node)
        for link in links:
            tree.links.remove(link)
        for node,links in replaces:
            texco = tree.nodes.new("ShaderNodeTexCoord")
            texco.hide = True
            hideAllBut(texco, ["UV"])
            texco.location = node.location
            for link in links:
                tree.links.new(texco.outputs["UV"], link.to_socket)
            tree.nodes.remove(node)
        for node in removes:
            tree.nodes.remove(node)

    for node in tree.nodes:
        for socket in node.outputs:
            if not socket.links:
                socket.hide = useHideOutputs

    from .material import setColorSpaceNone, setColorSpaceSRGB, isSRGBImage
    def protectImage(node, img, links):
        if isSRGBImage(img):
            LS.protectedImages[img.name] = img
        else:
            for link in links:
                if (link.to_node.type in ['NORMAL_MAP'] or
                    link.to_socket.type == 'VALUE'):
                    return
            img2 = LS.protectedImages.get(img.name)
            if img2 is None:
                img2 = img.copy()
                setColorSpaceSRGB(img2)
                LS.protectedImages[img.name] = img2
            try:
                node.image = img2
            except ReferenceError:
                print("Image has been removed", img)
                node.image = img

    for node in list(tree.nodes):
        if node.type == 'TEX_IMAGE':
            links = node.outputs["Color"].links
            img = node.image
            if len(links) == 1 and img:
                gamma = links[0].to_node
                if (gamma.label == "Linear" and
                    gamma.type == 'GAMMA'):
                    if isSRGBImage(img) and img.name in LS.protectedImages.keys():
                        if GS.verbosity >= 3:
                            print("Protected image: %s" % img.name)
                    else:
                        setColorSpaceNone(img)
                        for link in gamma.outputs["Color"].links:
                            tree.links.new(node.outputs["Color"], link.to_socket)
                else:
                    protectImage(node, img, links)
            elif img:
                protectImage(node, img, links)
            node.hide = useHideTexNodes

    if useDeleteUnusedNodes:
        outputs = []
        for node in tree.nodes:
            marked[node.name] = False
            if not node.outputs:
                if (keepUnusedTextures or
                    not node.name.startswith("Unused Textures")):
                    marked[node.name] = True
                    outputs.append(node)
        if not outputs:
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

    if useDazImages:
        makeDazImages(tree)
    if useBeautify:
        beautifyNodeTree(tree)
    return marked

#-------------------------------------------------------------
#   Beautify NodeTree
#-------------------------------------------------------------

def beautifyNodeTree(tree):
    def findColumn(node, col, level):
        if level < 0:
            print("Infinite recursion")
            return
        col1 = columns.get(node.name, -1)
        if col1 < col:
            if node.width > XSIZE-50:
                col += 1
            columns[node.name] = col
            nodes[node.name] = node
            for socket in node.inputs:
                for link in socket.links:
                    findColumn(link.from_node, col+1, level-1)

    if tree is None:
        return
    outputs = []
    for node in tree.nodes:
        if not node.outputs:
            outputs.append(node)
    columns = {}
    nodes = {}
    for node in outputs:
        findColumn(node, 0, 100)
    for key,col in list(columns.items()):
        if col > 20:
            columns[key] = 10 + col%10
    rows = {}
    for name,node in nodes.items():
        col = columns[name]
        row = rows.get(col, 0)
        node.location = (-XSIZE*col, -YSTEP*row)
        if node.hide:
            size = 2
        elif node.type == "GROUP":
            grpname = node.name.split(".",1)[0]
            if grpname.startswith(("LIE", "DIMG")):
                size = 6
            elif grpname.endswith("Combo"):
                size = 30
            else:
                size = GroupSize.get(grpname, 10)
                if (False and
                    grpname not in GroupSize.keys() and
                    "shell" not in grpname.lower() and
                    not ES.easy):
                    print("Missing GroupSize", grpname)
        else:
            size = NodeSize.get(node.type, 10)
            if node.type not in NodeSize.keys() and not ES.easy:
                print("Missing NodeSize", node.type)
        rows[col] = row + size

#-------------------------------------------------------------
#   Prune materials
#-------------------------------------------------------------

def pruneMaterials(ob,
                   useDeleteUnusedNodes=True,
                   useHideTexNodes=True,
                   usePruneTexco=True,
                   useHideOutputs=True,
                   keepUnusedTextures=True,
                   useFixColorSpace=True,
                   useDazImages=True,
                   useBeautify=False):
    from .geometry import getActiveUvLayer
    LS.__init__()
    active = getActiveUvLayer(ob)
    for mat in ob.data.materials:
        if mat:
            pruneNodeTree(mat.node_tree, active,
                          useDeleteUnusedNodes,
                          useHideTexNodes,
                          usePruneTexco,
                          useHideOutputs,
                          keepUnusedTextures,
                          useFixColorSpace,
                          useDazImages,
                          useBeautify)


def getVectorSocket(sockets):
    socket = sockets.get("Vector")
    if socket:
        return socket
    else:
        return sockets.get("UV")


def makeDazImages(tree):
    from .cgroup import CyclesGroup
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

    deletes = []
    for tex,after,before in dazimgs:
        after.reverse()
        before.reverse()

        grpnode = tree.nodes.new("ShaderNodeGroup")
        grpnode.location = tex.location
        ctree = CyclesGroup()
        name = "DIMG %s" % tex.label
        ctree.create(grpnode, name, None, len(before) + len(after))
        addGroupInput(ctree.group, "NodeSocketVector", "Vector")
        ctree.hideSlot("Vector")
        addGroupOutput(ctree.group, "NodeSocketColor", "Color")
        addGroupOutput(ctree.group, "NodeSocketFloat", "Alpha")

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
                filepath = normalizePath(img.filepath)
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
        ignore = ( "inputs", "outputs", "rna_type", "internal_links", "interface", "texture_mapping", "color_mapping", "image_user", "node_preview")
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

