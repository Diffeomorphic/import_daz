# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .cycles import CyclesTree
from .pbr import PbrTree
from .utils import *


class BrickTree:
    def buildLayers(self):
        layers = self.findBrickLayers()
        if layers:
            if GS.verbosity >= 3:
                print("Building brick layers:", layers)
            node = self.addBrickLayer("Base", False)
            node.inputs["Fac"].default_value = 1
            self.cycles = node
            for layer in layers[1:]:
                node = self.addBrickLayer(layer, True)
                channels = ["%s Weight" % layer, "%s Layer Weight" % layer]
                weight,wttex,_ = self.getColorTex(channels, "NONE", 1)
                print("  Brick layer", layer, weight)
                self.mixWithActive(weight, wttex, None, node)
        else:
            self.buildLayer("")


    def findBrickLayers(self):
        layers = {}
        for channel in self.owner.channels.keys():
            if (channel[0:5] == "Base " and
                channel not in ["Base Color Effect"]):
                layers["Base"] = True
            elif channel[0:6] == "Layer " and channel[6].isdigit():
                layers[channel[0:7]] = True
        layers = list(layers.keys())
        layers.sort()
        return layers


    def addBrickLayer(self, layer, flip):
        from .cgroup import BrickLayerGroup
        self.owner.layer = layer
        node = self.addNode("ShaderNodeGroup")
        node.name = layer
        node.label = layer
        group = BrickLayerGroup()
        group.create(node, layer, self)
        group.addNodes([], flip)
        self.links.new(self.texco, node.inputs["UV"])
        self.owner.layer = None
        return node


class CyclesBrickTree(BrickTree, CyclesTree):
    def __init__(self, cmat):
        CyclesTree.__init__(self, cmat)
        self.type = 'CBRICK'


class PbrBrickTree(BrickTree, PbrTree):
    def __init__(self, cmat):
        PbrTree.__init__(self, cmat)
        self.type = 'PBRICK'


