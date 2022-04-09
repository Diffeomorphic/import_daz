# Copyright (c) 2016-2021, Thomas Larsson
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
    def __init__(self, cmat):
        self.type = 'CYCLES'
        self.material = cmat
        self.column = 1
        self.ycoords = NCOLUMNS*[2*YSIZE]
        self.nodes = None
        self.links = None
        self.groups = {}


    def __repr__(self):
        return ("<%s %s %s %s>" % (self.tree, self.material.rna, self.nodes, self.links))


    def makeTree(self):
        mat = self.material.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links


    def addNode(self, stype, col=None, size=0, label=None, parent=None):
        if col is None:
            col = self.column
        node = self.nodes.new(type = stype)
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= (YSIZE + size)
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node


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

