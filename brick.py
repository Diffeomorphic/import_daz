# Copyright (c) 2016-2024, Thomas Larsson
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


