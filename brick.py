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
from .cycles import CyclesTree
from .pbr import PbrTree
from .utils import *


class BrickTree:
    def buildLayers(self):
        layers = self.findBrickLayers()
        if layers:
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


