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

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE, BLACK
from .tree import NodeGroup
from .utils import *
from .error import *

class CyclesGroup(NodeGroup, CyclesTree):
    def create(self, node, name, parent, ncols):
        CyclesTree.__init__(self, parent.owner)
        NodeGroup.create(self, node, name, parent, ncols)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(NodeGroup):
    def __init__(self, push):
        CyclesTree.__init__(self, None)
        NodeGroup.__init__(self)
        self.push = push
        self.insockets += ["Influence", "BSDF", "UV", "Displacement"]
        self.outsockets += ["BSDF", "Displacement"]


    def create(self, node, name, parent):
        NodeGroup.create(self, node, name, parent, 9)
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.inputs.new("NodeSocketShader", "BSDF")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.hideSlot("UV")
        self.group.inputs.new("NodeSocketVector", "Displacement")
        self.hideSlot("Displacement")
        self.group.outputs.new("NodeSocketShader", "BSDF")
        self.group.outputs.new("NodeSocketVector", "Displacement")


    def addNodes(self, args):
        shmat,uvname = args
        shmat.copyBasics(self.parent.owner)
        self.owner = shmat
        self.cyclesOpaque = None
        self.pbrOpaque = None
        self.inShell = True
        self.texco = self.inputs.outputs["UV"]
        self.tileTexco()
        self.buildLayer(uvname)
        alpha,atex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        mult = self.addNode("ShaderNodeMath", 6)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Influence"], mult.inputs[0])
        if (alpha < 1 or atex) and self.clipsocket:
            self.linkScalar(atex, mult, alpha, 1)
            mult2 = self.addNode("ShaderNodeMath", 6)
            mult2.operation = 'MULTIPLY'
            self.links.new(mult.outputs[0], mult2.inputs[0])
            self.links.new(self.clipsocket, mult2.inputs[1])
            mult = mult2
        elif (alpha < 1 or atex):
            self.linkScalar(atex, mult, alpha, 1)
        elif self.clipsocket:
            self.links.new(self.clipsocket, mult.inputs[1])
        else:
            mult.inputs[1].default_value = 1.0

        inv = self.addNode("ShaderNodeMath", 7)
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        self.links.new(mult.outputs[0], inv.inputs[1])
        self.addOutputs(inv)

        self.buildDisplacementNodes()
        if self.displacement:
            scale = self.addNode("ShaderNodeVectorMath", 8)
            scale.label = "Scale"
            scale.operation = 'SCALE'
            self.links.new(self.displacement, scale.inputs[0])
            self.links.new(mult.outputs[0], scale.inputs["Scale"])
            self.links.new(scale.outputs[0], self.outputs.inputs["Displacement"])
        else:
            self.links.new(self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])


class OpaqueShellGroup(ShellGroup):
    def addOutput(self, mult, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 8)
        mix.inputs[0].default_value = 1
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[2])
        self.links.new(socket, mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])

    def addOutputs(self, mult):
        if self.cycles:
            self.addOutput(mult, self.getCyclesSocket(), "BSDF")


class RefractiveShellGroup(ShellGroup):
    def storeOpaque(self):
        self.cyclesOpaque = self.getCyclesSocket()
        self.cycles = None

    def blacken(self):
        transp = self.addNode("ShaderNodeBsdfTransparent", 7)
        transp.inputs[0].default_value[0:3] = BLACK
        for node in self.nodes:
            if node.type == 'GROUP' and "Refraction Color" in node.inputs.keys():
                node.inputs["Refraction Color"].default_value[0:3] = BLACK
                self.removeLink(node, "Refraction Color")
            elif node.type == 'BSDF_PRINCIPLED' and node != self.pbrOpaque:
                node.inputs["Base Color"].default_value[0:3] = BLACK
                self.removeLink(node, "Base Color")
                node.inputs["Transmission"].default_value = 0
                self.removeLink(node, "Transmission")
        return transp

    def addOutput(self, mult, transp, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 8)
        mix.inputs[0].default_value = 1
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(transp.outputs[0], mix.inputs[2])
        self.links.new(socket, mix.inputs[1])

        add = self.addNode("ShaderNodeAddShader", 8)
        self.links.new(self.inputs.outputs[slot], add.inputs[0])
        self.links.new(mix.outputs[0], add.inputs[1])
        self.links.new(add.outputs[0], self.outputs.inputs[slot])
        return add

    def mixOutputs(self, mult, add, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 9)
        mix.inputs[0].default_value = 1
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(add.outputs[0], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])

        mix2 = self.addNode("ShaderNodeMixShader", 9)
        mix2.inputs[0].default_value = self.weight
        if self.wttex:
            self.links.new(self.wttex.outputs[0], mix2.inputs[0])
        self.links.new(mix.outputs[0], mix2.inputs[1])
        self.links.new(add.outputs[0], mix2.inputs[2])
        self.links.new(mix2.outputs[0], self.outputs.inputs[slot])

    def addOutputs(self, mult):
        transp = self.blacken()
        if self.cyclesOpaque and self.cycles:
            add = self.addOutput(mult, transp, self.getCyclesSocket(), "BSDF")
            self.mixOutputs(mult, add, self.cyclesOpaque, "BSDF")
            return
        if self.cyclesOpaque:
            self.cycles = self.cyclesOpaque
        if self.cycles:
            self.addOutput(mult, transp, self.getCyclesSocket(), "BSDF")


class OpaqueShellCyclesGroup(OpaqueShellGroup, CyclesTree):
    def create(self, node, name, parent):
        CyclesTree.__init__(self, parent.owner)
        OpaqueShellGroup.create(self, node, name, parent)


class OpaqueShellPbrGroup(OpaqueShellGroup, PbrTree):
    def create(self, node, name, parent):
        PbrTree.__init__(self, parent.owner)
        OpaqueShellGroup.create(self, node, name, parent)


class RefractiveShellCyclesGroup(RefractiveShellGroup, CyclesTree):
    def create(self, node, name, parent):
        CyclesTree.__init__(self, parent.owner)
        RefractiveShellGroup.create(self, node, name, parent)

    def buildRefraction(self):
        self.storeOpaque()
        self.weight, self.wttex = CyclesTree.buildRefraction(self)


class RefractiveShellPbrGroup(RefractiveShellGroup, PbrTree):
    def create(self, node, name, parent):
        PbrTree.__init__(self, parent.owner)
        RefractiveShellGroup.create(self, node, name, parent)

    def buildRefraction(self):
        self.storeOpaque()
        self.pbrOpaque = self.pbr
        self.weight, self.wttex = PbrTree.buildRefraction(self)

# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class Fresnel2Group(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["IOR", "Roughness", "Power", "Normal"]
        self.outsockets += ["Dielectric", "Metal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Power")
        self.setMinMax("Power", 1, 1, 4)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        self.group.outputs.new("NodeSocketFloat", "Dielectric")
        self.group.outputs.new("NodeSocketFloat", "Metal")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 0)

        divide = self.addNode("ShaderNodeMath", 1)
        divide.operation = 'DIVIDE'
        divide.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["IOR"], divide.inputs[1])

        power = self.addNode("ShaderNodeMath", 1)
        power.operation = 'POWER'
        self.links.new(self.inputs.outputs["Roughness"], power.inputs[0])
        self.links.new(self.inputs.outputs["Power"], power.inputs[1])

        bump = self.addNode("ShaderNodeBump", 1)
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.links.new(self.inputs.outputs["IOR"], mix1.inputs[1])
        self.links.new(divide.outputs["Value"], mix1.inputs[2])

        mix2 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(power.outputs[0], mix2.inputs["Fac"])
        self.links.new(bump.outputs[0], mix2.inputs[1])
        self.links.new(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel1 = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(mix1.outputs[0], fresnel1.inputs["IOR"])
        self.links.new(mix2.outputs[0], fresnel1.inputs["Normal"])
        self.links.new(fresnel1.outputs["Fac"], self.outputs.inputs["Dielectric"])

        fresnel2 = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(mix1.outputs[0], fresnel2.inputs["IOR"])
        self.links.new(geo.outputs["Incoming"], fresnel2.inputs["Normal"])

        sub = self.addNode("ShaderNodeMath", 4)
        sub.operation = 'SUBTRACT'
        self.links.new(fresnel1.outputs["Fac"], sub.inputs[0])
        self.links.new(fresnel2.outputs["Fac"], sub.inputs[1])
        self.links.new(sub.outputs[0], self.outputs.inputs["Metal"])

# ---------------------------------------------------------------------
#   LogColor Group
# ---------------------------------------------------------------------

class LogColorGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color"]
        self.outsockets += ["Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        sep = self.addNode("ShaderNodeSeparateRGB", 1)
        self.links.new(self.inputs.outputs["Color"], sep.inputs["Image"])
        abs0 = self.addLog(sep.outputs[0])
        abs1 = self.addLog(sep.outputs[1])
        abs2 = self.addLog(sep.outputs[2])
        comb = self.addNode("ShaderNodeCombineRGB", 5)
        self.links.new(abs0.outputs[0], comb.inputs[0])
        self.links.new(abs1.outputs[0], comb.inputs[1])
        self.links.new(abs2.outputs[0], comb.inputs[2])
        self.links.new(comb.outputs["Image"], self.outputs.inputs["Color"])


    def addLog(self, socket):
        clamp = self.addNode("ShaderNodeClamp", 2)
        clamp.clamp_type = 'MINMAX'
        self.links.new(socket, clamp.inputs[0])
        clamp.inputs[1].default_value = 0.0
        clamp.inputs[2].default_value = 0.999

        log = self.addNode("ShaderNodeMath", 3)
        log.operation = 'LOGARITHM'
        self.links.new(clamp.outputs[0], log.inputs[0])
        log.inputs[1].default_value = 2.720

        abs = self.addNode("ShaderNodeMath", 4)
        abs.operation = 'ABSOLUTE'
        self.links.new(log.outputs[0], abs.inputs[0])
        return abs

# ---------------------------------------------------------------------
#   Mix Group.
# ---------------------------------------------------------------------

class BSDFGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["BSDF"]
        self.outsockets += ["BSDF"]

    def createShaderSlots(self):
        self.group.inputs.new("NodeSocketShader", "BSDF")
        self.group.outputs.new("NodeSocketShader", "BSDF")

    def mixCycles(self, socket, slot):
        self.links.new(socket, self.mix1.inputs[slot])

# ---------------------------------------------------------------------
#   Fac Mix Group.
# ---------------------------------------------------------------------

class FacMixGroup(BSDFGroup):
    def __init__(self):
        BSDFGroup.__init__(self)
        self.insockets += ["Fac"]

    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.setMinMax("Fac", 0.5, 0.0, 1.0)
        self.createShaderSlots()

    def addNodes(self, args=None):
        self.mix1 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix1.label = "Mix"
        self.links.new(self.inputs.outputs["BSDF"], self.mix1.inputs[1])
        self.links.new(self.mix1.outputs[0], self.outputs.inputs["BSDF"])
        self.mixCycles(self.inputs.outputs["Fac"], 0)

# ---------------------------------------------------------------------
#   Add Group. Adds to Cycles and Eevee
# ---------------------------------------------------------------------

class AddGroup(BSDFGroup):

    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.createShaderSlots()


    def addNodes(self, args=None):
        self.add1 = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(self.inputs.outputs["BSDF"], self.add1.inputs[0])
        self.links.new(self.add1.outputs[0], self.outputs.inputs["BSDF"])

# ---------------------------------------------------------------------
#   BrickLayerGroup
# ---------------------------------------------------------------------

class BrickLayerGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["UV"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 10)
        self.group.inputs.new("NodeSocketVector", "UV")
        self.hideSlot("UV")


    def addNodes(self, args, flip):
        FacMixGroup.addNodes(self, args)
        self.inShell = True
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer("")
        if flip:
            self.linkCycles(self.mix1, 1)
            self.links.new(self.inputs.outputs["BSDF"], self.mix1.inputs[2])
        else:
            self.linkCycles(self.mix1, 2)

# ---------------------------------------------------------------------
#   SSS Fix Group. Midnight's fix for translucent materials
#   https://bitbucket.org/Diffeomorphic/import_daz/issues/1082/better-eevee-principled-materials
# ---------------------------------------------------------------------

class SSSFixGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["SSS Amount", "Diffuse Color", "Translucent Color", "Translucency Weight"]
        self.outsockets += ["Base Color", "Subsurface", "Subsurface Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "SSS Amount")
        self.group.inputs.new("NodeSocketColor", "Diffuse Color")
        self.group.inputs.new("NodeSocketColor", "Translucent Color")
        self.group.inputs.new("NodeSocketFloat", "Translucency Weight")
        self.setMinMax("Translucency Weight", 0.5, 0.0, 1.0)
        self.group.outputs.new("NodeSocketFloat", "Subsurface")
        self.group.outputs.new("NodeSocketColor", "Base Color")
        self.group.outputs.new("NodeSocketColor", "Subsurface Color")


    def addNodes(self, args=None):
        maprange = self.addNode("ShaderNodeMapRange", 1)
        maprange.data_type = 'FLOAT'
        maprange.interpolation_type = 'LINEAR'
        self.links.new(self.inputs.outputs["SSS Amount"], maprange.inputs["Value"])
        maprange.inputs["From Min"].default_value = 0.0
        maprange.inputs["From Max"].default_value = 1.0
        maprange.inputs["To Min"].default_value = 0.0
        maprange.inputs["To Max"].default_value = 0.5

        inv = self.addNode("ShaderNodeMath", 1)
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Translucency Weight"], inv.inputs[1])

        hsv1 = self.addNode("ShaderNodeHueSaturation", 2)
        hsv1.inputs["Hue"].default_value = 0.5
        hsv1.inputs["Saturation"].default_value = 1.0
        self.links.new(inv.outputs[0], hsv1.inputs["Value"])
        hsv1.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["Diffuse Color"], hsv1.inputs["Color"])

        hsv2 = self.addNode("ShaderNodeHueSaturation", 2)
        hsv2.inputs["Hue"].default_value = 0.5
        hsv2.inputs["Saturation"].default_value = 1.0
        self.links.new(inv.outputs[0], hsv2.inputs["Value"])
        hsv2.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["Translucent Color"], hsv2.inputs["Color"])

        dodge1 = self.addNode("ShaderNodeMixRGB", 3)
        dodge1.blend_type = 'DODGE'
        self.links.new(self.inputs.outputs["Translucency Weight"], dodge1.inputs["Fac"])
        self.links.new(hsv1.outputs["Color"], dodge1.inputs["Color1"])
        self.links.new(self.inputs.outputs["Diffuse Color"], dodge1.inputs["Color2"])

        dodge2 = self.addNode("ShaderNodeMixRGB", 3)
        dodge2.blend_type = 'DODGE'
        self.links.new(self.inputs.outputs["Translucency Weight"], dodge2.inputs["Fac"])
        self.links.new(hsv2.outputs["Color"], dodge2.inputs["Color1"])
        self.links.new(self.inputs.outputs["Translucent Color"], dodge2.inputs["Color2"])

        self.links.new(maprange.outputs["Result"], self.outputs.inputs["Subsurface"])
        self.links.new(dodge1.outputs["Color"], self.outputs.inputs["Base Color"])
        self.links.new(dodge2.outputs["Color"], self.outputs.inputs["Subsurface Color"])

# ---------------------------------------------------------------------
#   Color Effect Group
# ---------------------------------------------------------------------

class ColorEffectGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Color"]
        self.outsockets += ["Transmit Fac", "Intensity Fac", "Color"]

    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.setMinMax("Fac", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Transmit Fac")
        self.group.outputs.new("NodeSocketFloat", "Intensity Fac")
        self.group.outputs.new("NodeSocketColor", "Color")

    def getTint(self):
        return self.inputs

    def addNodes(self, args=None):
        mix = self.addNode("ShaderNodeMixRGB", 2)
        mix.blend_type = 'MIX'
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        mix.inputs[1].default_value[0:3] = BLACK
        tint = self.getTint()
        self.links.new(tint.outputs["Color"], mix.inputs[2])

        rgb = self.addNode("ShaderNodeMixRGB", 2)
        rgb.blend_type = 'COLOR'
        rgb.inputs[0].default_value = 1.0
        rgb.inputs[1].default_value[0:3] = WHITE
        self.links.new(tint.outputs["Color"], rgb.inputs[2])

        scale = self.addNode("ShaderNodeVectorMath", 3)
        scale.operation = 'SCALE'
        self.links.new(mix.outputs["Color"], scale.inputs["Vector"])
        scale.inputs["Scale"].default_value = 1.0

        hsv2 = self.addNode("ShaderNodeHueSaturation", 3)
        hsv2.inputs["Hue"].default_value = 0.5
        hsv2.inputs["Saturation"].default_value = 0.0
        hsv2.inputs["Value"].default_value = 1.0
        hsv2.inputs["Fac"].default_value = 1.0
        self.links.new(mix.outputs["Color"], hsv2.inputs["Color"])

        self.links.new(scale.outputs[0], self.outputs.inputs["Transmit Fac"])
        self.links.new(hsv2.outputs["Color"], self.outputs.inputs["Intensity Fac"])
        self.links.new(rgb.outputs["Color"], self.outputs.inputs["Color"])


class TintedEffectGroup(ColorEffectGroup):
    def __init__(self):
        ColorEffectGroup.__init__(self)
        self.insockets += ["Tint"]

    def create(self, node, name, parent):
        ColorEffectGroup.create(self, node, name, parent)
        self.group.inputs.new("NodeSocketColor", "Tint")

    def getTint(self):
        tint = self.addNode("ShaderNodeMixRGB", 1)
        tint.blend_type = 'MULTIPLY'
        tint.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Color"], tint.inputs[1])
        self.links.new(self.inputs.outputs["Tint"], tint.inputs[2])
        return tint

# ---------------------------------------------------------------------
#   Invert Normal Map Group
# ---------------------------------------------------------------------

class InvertNormalMapGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color"]
        self.outsockets += ["Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        sep = self.addNode("ShaderNodeSeparateRGB", 1)
        self.links.new(self.inputs.outputs["Color"], sep.inputs["Image"])
        inv1 = self.addNode("ShaderNodeInvert", 2)
        inv1.inputs["Fac"].default_value = 1.0
        self.links.new(sep.outputs["R"], inv1.inputs["Color"])
        inv2 = self.addNode("ShaderNodeInvert", 2)
        inv2.inputs["Fac"].default_value = 1.0
        self.links.new(sep.outputs["G"], inv2.inputs["Color"])
        comb = self.addNode("ShaderNodeCombineRGB", 3)
        self.links.new(inv1.outputs[0], comb.inputs["R"])
        self.links.new(inv2.outputs[0], comb.inputs["G"])
        self.links.new(sep.outputs["B"], comb.inputs["B"])
        self.links.new(comb.outputs["Image"], self.outputs.inputs["Color"])

# ---------------------------------------------------------------------
#   Weighted Group. For weighted mode
# ---------------------------------------------------------------------

class WeightedGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Diffuse Cycles", "Glossy Cycles"]
        self.outsockets += ["BSDF"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.setMinMax("Fac", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketShader", "Diffuse Cycles")
        self.group.inputs.new("NodeSocketShader", "Glossy Cycles")
        self.group.outputs.new("NodeSocketShader", "BSDF")


    def addNodes(self, args=None):
        self.mix1 = self.addNode("ShaderNodeMixShader", 1)
        self.links.new(self.inputs.outputs["Fac"], self.mix1.inputs[0])
        self.links.new(self.inputs.outputs["Diffuse Cycles"], self.mix1.inputs[1])
        self.links.new(self.inputs.outputs["Glossy Cycles"], self.mix1.inputs[2])
        self.links.new(self.mix1.outputs[0], self.outputs.inputs["BSDF"])

# ---------------------------------------------------------------------
#   Emission Group
# ---------------------------------------------------------------------

class EmissionGroup(AddGroup):

    def __init__(self):
        AddGroup.__init__(self)
        self.insockets += ["Color", "Strength"]


    def create(self, node, name, parent):
        AddGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Strength")


    def addNodes(self, args=None):
        AddGroup.addNodes(self, args)
        node = self.addNode("ShaderNodeEmission", 1)
        self.links.new(self.inputs.outputs["Color"], node.inputs["Color"])
        self.links.new(self.inputs.outputs["Strength"], node.inputs["Strength"])
        self.links.new(node.outputs[0], self.add1.inputs[1])


class OneSidedGroup(BSDFGroup):
    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.createShaderSlots()


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 1)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        mix1 = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs[0])
        self.links.new(self.inputs.outputs["BSDF"], mix1.inputs[1])
        self.links.new(trans.outputs[0], mix1.inputs[2])
        self.links.new(mix1.outputs[0], self.outputs.inputs["BSDF"])

# ---------------------------------------------------------------------
#   Diffuse Group
# ---------------------------------------------------------------------

class DiffuseGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.mixCycles(diffuse.outputs[0], 2)

# ---------------------------------------------------------------------
#   Glossy Group
# ---------------------------------------------------------------------

class GlossyGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "IOR", "Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)

        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 1)
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Roughness"], fresnel.inputs["Roughness"])
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        aniso = self.addNode("ShaderNodeBsdfAnisotropic", 1)
        aniso.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(self.inputs.outputs["Color"], aniso.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], aniso.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Anisotropy"], aniso.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Rotation"], aniso.inputs["Rotation"])
        self.links.new(self.inputs.outputs["Normal"], aniso.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["BSDF"], mix.inputs[1])
        self.links.new(aniso.outputs[0], mix.inputs[2])

        self.mixCycles(mix.outputs[0], 2)


# ---------------------------------------------------------------------
#   Metal Group
# ---------------------------------------------------------------------

class MetalGroupUber(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 1)
        fresnel.inputs["IOR"].default_value = 1.5
        self.links.new(self.inputs.outputs["Roughness"], fresnel.inputs["Roughness"])
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        hsv = self.addNode("ShaderNodeHueSaturation", 1)
        hsv.inputs["Hue"].default_value = 0.5
        hsv.inputs["Saturation"].default_value = 0.0
        hsv.inputs["Value"].default_value = 1.0
        hsv.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["Color"], hsv.inputs["Color"])

        mix = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(fresnel.outputs["Metal"], mix.inputs["Fac"])
        self.links.new(self.inputs.outputs["Color"], mix.inputs[1])
        self.links.new(hsv.outputs["Color"], mix.inputs[2])

        node = self.addNode("ShaderNodeBsdfAnisotropic", 3)
        node.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(mix.outputs["Color"], node.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], node.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Anisotropy"], node.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Rotation"], node.inputs["Rotation"])
        self.links.new(self.inputs.outputs["Normal"], node.inputs["Normal"])

        self.mixCycles(node.outputs[0], 2)


class MetalGroupPbrSkin(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness 1",  "Roughness 2", "Dual Ratio", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.setMinMax("Roughness 1", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.setMinMax("Roughness 2", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Dual Ratio")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        glossy1 = self.addGlossy("Roughness 1")
        glossy2 = self.addGlossy("Roughness 2")
        mix = self.addNode("ShaderNodeMixShader", 4)
        self.links.new(self.inputs.outputs["Dual Ratio"], mix.inputs[0])
        self.links.new(glossy1.outputs[0], mix.inputs[1])
        self.links.new(glossy2.outputs[0], mix.inputs[2])
        self.mixCycles(mix.outputs[0], 2)


    def addGlossy(self, slot):
        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 1)
        fresnel.inputs["IOR"].default_value = 1.5
        self.links.new(self.inputs.outputs[slot], fresnel.inputs["Roughness"])
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(fresnel.outputs["Metal"], mix.inputs["Fac"])
        self.links.new(self.inputs.outputs["Color"], mix.inputs[1])
        mix.inputs[2].default_value[0:3] = WHITE

        glossy = self.addNode("ShaderNodeBsdfGlossy", 3)
        glossy.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(mix.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[slot], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy

# ---------------------------------------------------------------------
#   Top Coat Group
# ---------------------------------------------------------------------

class TopCoatGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)

        aniso = self.addNode("ShaderNodeBsdfAnisotropic", 1)
        aniso.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(self.inputs.outputs["Color"], aniso.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], aniso.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Anisotropy"], aniso.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Rotation"], aniso.inputs["Rotation"])
        self.links.new(self.inputs.outputs["Normal"], aniso.inputs["Normal"])

        self.mixCycles(aniso.outputs[0], 2)

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------

class RefractionGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += [
            "Thin Wall",
            "Refraction Color", "Refraction Roughness", "IOR",
            "Glossy Color", "Glossy Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketFloat", "Thin Wall")
        self.setMinMax("Thin Wall", 0, 0, 1)
        self.group.inputs.new("NodeSocketColor", "Refraction Color")
        self.group.inputs.new("NodeSocketFloat", "Refraction Roughness")
        self.setMinMax("Refraction Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        self.group.inputs.new("NodeSocketColor", "Glossy Color")
        self.group.inputs.new("NodeSocketFloat", "Glossy Roughness")
        self.setMinMax("Glossy Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        refr = self.addNode("ShaderNodeBsdfRefraction", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], refr.inputs["Color"])
        self.links.new(self.inputs.outputs["Refraction Roughness"], refr.inputs["Roughness"])
        self.links.new(self.inputs.outputs["IOR"], refr.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refr.inputs["Normal"])

        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], trans.inputs["Color"])

        thin = self.addNode("ShaderNodeMixShader", 2)
        thin.label = "Thin Wall"
        self.links.new(self.inputs.outputs["Thin Wall"], thin.inputs["Fac"])
        self.links.new(refr.outputs[0], thin.inputs[1])
        self.links.new(trans.outputs[0], thin.inputs[2])

        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 2)
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        aniso = self.addNode("ShaderNodeBsdfAnisotropic", 2)
        aniso.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(self.inputs.outputs["Glossy Color"], aniso.inputs["Color"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], aniso.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Anisotropy"], aniso.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Rotation"], aniso.inputs["Rotation"])
        self.links.new(self.inputs.outputs["Normal"], aniso.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(fresnel.outputs["Dielectric"], mix.inputs[0])
        self.links.new(thin.outputs[0], mix.inputs[1])
        self.links.new(aniso.outputs[0], mix.inputs[2])

        self.mixCycles(mix.outputs[0], 2)

# ---------------------------------------------------------------------
#   Fake Caustics Group
# ---------------------------------------------------------------------

class FakeCausticsGroup(FacMixGroup):

    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 6)


    def addNodes(self, args):
        FacMixGroup.addNodes(self, args)
        normal = self.addNode("ShaderNodeNewGeometry", 1)
        incoming = self.addNode("ShaderNodeNewGeometry", 1)

        dot = self.addNode("ShaderNodeVectorMath", 2)
        dot.operation = 'DOT_PRODUCT'
        self.links.new(normal.outputs["Normal"], dot.inputs[0])
        self.links.new(incoming.outputs["Incoming"], dot.inputs[1])

        ramp = self.addNode('ShaderNodeValToRGB', 3)
        self.links.new(dot.outputs["Value"], ramp.inputs['Fac'])
        colramp = ramp.color_ramp
        colramp.interpolation = 'LINEAR'
        color = args[0]
        elt = colramp.elements[0]
        elt.position = 0.9
        elt.color[0:3] = 0.5*color
        elt = colramp.elements[1]
        elt.position = 1.0
        elt.color[0:3] = 10*color

        lightpath = self.addNode("ShaderNodeLightPath", 4, size=100)
        trans = self.addNode("ShaderNodeBsdfTransparent", 4)
        self.links.new(ramp.outputs["Color"], trans.inputs["Color"])
        self.mixCycles(lightpath.outputs["Is Shadow Ray"], 0)
        self.mixCycles(trans.outputs[0], 2)

# ---------------------------------------------------------------------
#   Transparent Group
# ---------------------------------------------------------------------

class TransparentGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        # Flip
        self.mixCycles(self.inputs.outputs["BSDF"], 2)
        self.mixCycles(trans.outputs[0], 1)

# ---------------------------------------------------------------------
#   Subsurface Group
# ---------------------------------------------------------------------

class SubsurfaceGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Scale", "Radius", "IOR", "Anisotropy", "Normal"]

    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        self.group.inputs.new("NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")

    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        sss.falloff = GS.getSSSMethod()
        self.links.new(self.inputs.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        if bpy.app.version >= (3,0,0):
            self.links.new(self.inputs.outputs["IOR"], sss.inputs["IOR"])
            self.links.new(self.inputs.outputs["Anisotropy"], sss.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])
        self.mixCycles(sss.outputs[0], 2)

# ---------------------------------------------------------------------
#   Translucent Group
# ---------------------------------------------------------------------

class TranslucentGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Normal"]

    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")

    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTranslucent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        self.links.new(self.inputs.outputs["Normal"], trans.inputs["Normal"])
        self.mixCycles(trans.outputs[0], 2)

# ---------------------------------------------------------------------
#   Makeup Group
# ---------------------------------------------------------------------

class MakeupGroup(FacMixGroup):

    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.mixCycles(diffuse.outputs[0], 2)

# ---------------------------------------------------------------------
#   Ghost Light Group
# ---------------------------------------------------------------------

class GhostLightGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Emission", "Transparent"]
        self.outsockets += ["Shader"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Emission")
        self.group.inputs.new("NodeSocketShader", "Transparent")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        lpath = self.addNode("ShaderNodeLightPath", 1)

        max1 = self.addNode("ShaderNodeMath", 2)
        max1.operation = 'MAXIMUM'
        self.links.new(lpath.outputs["Is Camera Ray"], max1.inputs[0])
        self.links.new(lpath.outputs["Is Shadow Ray"], max1.inputs[1])

        max2 = self.addNode("ShaderNodeMath", 2)
        max2.operation = 'MAXIMUM'
        self.links.new(max1.outputs[0], max2.inputs[0])
        self.links.new(lpath.outputs["Is Reflection Ray"], max2.inputs[1])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(max2.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Emission"], mix.inputs[1])
        self.links.new(self.inputs.outputs["Transparent"], mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])

# ---------------------------------------------------------------------
#   Ray Clip Group
# ---------------------------------------------------------------------

class RayClipGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Shader", "Color"]
        self.outsockets += ["Shader"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        lpath = self.addNode("ShaderNodeLightPath", 1)

        max = self.addNode("ShaderNodeMath", 2)
        max.operation = 'MAXIMUM'
        self.links.new(lpath.outputs["Is Shadow Ray"], max.inputs[0])
        self.links.new(lpath.outputs["Is Reflection Ray"], max.inputs[1])

        trans = self.addNode("ShaderNodeBsdfTransparent", 2)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(max.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Shader"], mix.inputs[1])
        self.links.new(trans.outputs[0], mix.inputs[2])

        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])

# ---------------------------------------------------------------------
#   Dual Lobe Group
# ---------------------------------------------------------------------

class DualLobeGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Ratio", "IOR", "Roughness 1", "Roughness 2"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Ratio")
        self.setMinMax("Ratio", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.setMinMax("Roughness 1", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.setMinMax("Roughness 2", 0.5, 0.0, 1.0)
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        fresnel1 = self.addFresnel(True, "Roughness 1")
        glossy1 = self.addGlossy("Roughness 1", self.lobe1Normal)
        cycles1 = self.mixGlossy(fresnel1, glossy1, "BSDF")
        fresnel2 = self.addFresnel(False, "Roughness 2")
        glossy2 = self.addGlossy("Roughness 2", self.lobe2Normal)
        cycles2 = self.mixGlossy(fresnel2, glossy2, "BSDF")
        self.mixOutput(cycles1, cycles2, "BSDF")


    def addGlossy(self, roughness, useNormal):
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Fac"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy


    def mixGlossy(self, fresnel, glossy, slot):
        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs["Dielectric"], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])
        return mix


    def mixOutput(self, node1, node2, slot):
        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(self.inputs.outputs["Ratio"], mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[2])
        self.links.new(node2.outputs[0], mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class DualLobeGroupUberIray(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = False

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 1)
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel


class DualLobeGroupPbrSkin(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = True

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2", 1)
        fresnel.inputs["Power"].default_value = 4
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel

# ---------------------------------------------------------------------
#   Volume Group
# ---------------------------------------------------------------------

class VolumeGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += [
            "Absorbtion Color", "Absorbtion Density", "Scatter Color",
            "Scatter Density", "Scatter Anisotropy"]
        self.outsockets += ["Volume"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Absorbtion Color")
        self.group.inputs.new("NodeSocketFloat", "Absorbtion Density")
        self.group.inputs.new("NodeSocketColor", "Scatter Color")
        self.group.inputs.new("NodeSocketFloat", "Scatter Density")
        self.group.inputs.new("NodeSocketFloat", "Scatter Anisotropy")
        self.group.outputs.new("NodeSocketShader", "Volume")


    def addNodes(self, args=None):
        absorb = self.addNode("ShaderNodeVolumeAbsorption", 1)
        self.links.new(self.inputs.outputs["Absorbtion Color"], absorb.inputs["Color"])
        self.links.new(self.inputs.outputs["Absorbtion Density"], absorb.inputs["Density"])

        scatter = self.addNode("ShaderNodeVolumeScatter", 1)
        self.links.new(self.inputs.outputs["Scatter Color"], scatter.inputs["Color"])
        self.links.new(self.inputs.outputs["Scatter Density"], scatter.inputs["Density"])
        self.links.new(self.inputs.outputs["Scatter Anisotropy"], scatter.inputs["Anisotropy"])

        volume = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(absorb.outputs[0], volume.inputs[0])
        self.links.new(scatter.outputs[0], volume.inputs[1])
        self.links.new(volume.outputs[0], self.outputs.inputs["Volume"])

# ---------------------------------------------------------------------
#   Normal Group
#
#   https://blenderartists.org/t/way-faster-normal-map-node-for-realtime-animation-playback-with-tangent-space-normals/1175379
# ---------------------------------------------------------------------

class NormalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Strength", "Color"]
        self.outsockets += ["Normal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 8)

        strength = self.group.inputs.new("NodeSocketFloat", "Strength")
        strength.default_value = 1.0
        strength.min_value = 0.0
        strength.max_value = 1.0

        color = self.group.inputs.new("NodeSocketColor", "Color")
        color.default_value = ((0.5, 0.5, 1.0, 1.0))

        self.group.outputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args):
        # Generate TBN from Bump Node
        frame = self.nodes.new("NodeFrame")
        frame.label = "Generate TBN from Bump Node"

        uvmap = self.addNode("ShaderNodeUVMap", 1, parent=frame)
        if args[0]:
            uvmap.uv_map = args[0]

        uvgrads = self.addNode("ShaderNodeSeparateXYZ", 2, label="UV Gradients", parent=frame)
        self.links.new(uvmap.outputs["UV"], uvgrads.inputs[0])

        tangent = self.addNode("ShaderNodeBump", 3, label="Tangent", parent=frame)
        tangent.invert = True
        tangent.inputs["Distance"].default_value = 1
        self.links.new(uvgrads.outputs[0], tangent.inputs["Height"])

        bitangent = self.addNode("ShaderNodeBump", 3, label="Bi-Tangent", parent=frame)
        bitangent.invert = True
        bitangent.inputs["Distance"].default_value = 1000
        self.links.new(uvgrads.outputs[1], bitangent.inputs["Height"])

        geo = self.addNode("ShaderNodeNewGeometry", 3, label="Normal", parent=frame)

        # Transpose Matrix
        frame = self.nodes.new("NodeFrame")
        frame.label = "Transpose Matrix"

        sep1 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(tangent.outputs["Normal"], sep1.inputs[0])

        sep2 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(bitangent.outputs["Normal"], sep2.inputs[0])

        sep3 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(geo.outputs["Normal"], sep3.inputs[0])

        comb1 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[0], comb1.inputs[0])
        self.links.new(sep2.outputs[0], comb1.inputs[1])
        self.links.new(sep3.outputs[0], comb1.inputs[2])

        comb2 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[1], comb2.inputs[0])
        self.links.new(sep2.outputs[1], comb2.inputs[1])
        self.links.new(sep3.outputs[1], comb2.inputs[2])

        comb3 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[2], comb3.inputs[0])
        self.links.new(sep2.outputs[2], comb3.inputs[1])
        self.links.new(sep3.outputs[2], comb3.inputs[2])

        # Normal Map Processing
        frame = self.nodes.new("NodeFrame")
        frame.label = "Normal Map Processing"

        rgb = self.addNode("ShaderNodeMixRGB", 3, parent=frame)
        self.links.new(self.inputs.outputs["Strength"], rgb.inputs[0])
        rgb.inputs[1].default_value = (0.5, 0.5, 1.0, 1.0)
        self.links.new(self.inputs.outputs["Color"], rgb.inputs[2])

        sub = self.addNode("ShaderNodeVectorMath", 4, parent=frame)
        sub.operation = 'SUBTRACT'
        self.links.new(rgb.outputs["Color"], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.5)

        add = self.addNode("ShaderNodeVectorMath", 5, parent=frame)
        add.operation = 'ADD'
        self.links.new(sub.outputs[0], add.inputs[0])
        self.links.new(sub.outputs[0], add.inputs[1])

        # Matrix * Normal Map
        frame = self.nodes.new("NodeFrame")
        frame.label = "Matrix * Normal Map"

        dot1 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot1.operation = 'DOT_PRODUCT'
        self.links.new(comb1.outputs[0], dot1.inputs[0])
        self.links.new(add.outputs[0], dot1.inputs[1])

        dot2 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot2.operation = 'DOT_PRODUCT'
        self.links.new(comb2.outputs[0], dot2.inputs[0])
        self.links.new(add.outputs[0], dot2.inputs[1])

        dot3 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot3.operation = 'DOT_PRODUCT'
        self.links.new(comb3.outputs[0], dot3.inputs[0])
        self.links.new(add.outputs[0], dot3.inputs[1])

        comb = self.addNode("ShaderNodeCombineXYZ", 7, parent=frame)
        self.links.new(dot1.outputs["Value"], comb.inputs[0])
        self.links.new(dot2.outputs["Value"], comb.inputs[1])
        self.links.new(dot3.outputs["Value"], comb.inputs[2])

        self.links.new(comb.outputs[0], self.outputs.inputs["Normal"])

# ---------------------------------------------------------------------
#   Detail Group
# ---------------------------------------------------------------------

class DetailGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Texture", "Strength", "Max", "Min", "Normal"]
        self.outsockets += ["Displacement"]


# ---------------------------------------------------------------------
#   Displacement Group
# ---------------------------------------------------------------------

class DisplacementGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Texture", "Strength", "Max", "Min", "Normal"]
        self.outsockets += ["Displacement"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Texture")
        self.group.inputs.new("NodeSocketFloat", "Strength")
        self.group.inputs.new("NodeSocketFloat", "Max")
        self.group.inputs.new("NodeSocketFloat", "Min")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        self.group.outputs.new("NodeSocketVector", "Displacement")


    def addNodes(self, args=None):
        bw = self.addNode("ShaderNodeRGBToBW", 1)
        self.links.new(self.inputs.outputs["Texture"], bw.inputs[0])

        sub = self.addNode("ShaderNodeMath", 1)
        sub.operation = 'SUBTRACT'
        self.links.new(self.inputs.outputs["Max"], sub.inputs[0])
        self.links.new(self.inputs.outputs["Min"], sub.inputs[1])

        mult = self.addNode("ShaderNodeMath", 2)
        mult.operation = 'MULTIPLY'
        self.links.new(bw.outputs[0], mult.inputs[0])
        self.links.new(sub.outputs[0], mult.inputs[1])

        add = self.addNode("ShaderNodeMath", 2)
        add.operation = 'ADD'
        self.links.new(mult.outputs[0], add.inputs[0])
        self.links.new(self.inputs.outputs["Min"], add.inputs[1])

        disp = self.addNode("ShaderNodeDisplacement", 3)
        self.links.new(add.outputs[0], disp.inputs["Height"])
        disp.inputs["Midlevel"].default_value = 0
        self.links.new(self.inputs.outputs["Strength"], disp.inputs["Scale"])
        self.links.new(self.inputs.outputs["Normal"], disp.inputs["Normal"])

        self.links.new(disp.outputs[0], self.outputs.inputs["Displacement"])

# ---------------------------------------------------------------------
#   Mapping Group
# ---------------------------------------------------------------------

class MappingGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.outsockets += ["Depth Mask", "Vector"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.outputs.new("NodeSocketFloat", "Depth Mask")
        self.group.outputs.new("NodeSocketVector", "Vector")


    def addNodes(self, args):
        empty = args[0]
        texco = self.addNode("ShaderNodeTexCoord", 0)
        texco.object = empty

        mapping1 = self.addNode("ShaderNodeMapping", 1)
        mapping1.vector_type = 'POINT'
        mapping1.inputs["Location"].default_value = (0, 0, 0)
        mapping1.inputs["Rotation"].default_value = (0, 0, 0)
        mapping1.inputs["Scale"].default_value = (0.1, 1.0, 0.1)
        self.links.new(texco.outputs["Object"], mapping1.inputs["Vector"])

        grad = self.addNode("ShaderNodeTexGradient", 2)
        grad.gradient_type = 'SPHERICAL'
        self.links.new(mapping1.outputs["Vector"], grad.inputs["Vector"])

        gate = self.addNode("ShaderNodeMath", 3)
        gate.operation = 'GREATER_THAN'
        self.links.new(grad.outputs["Color"], gate.inputs[0])
        gate.inputs[1].default_value = 0.75
        self.links.new(gate.outputs[0], self.outputs.inputs["Depth Mask"])

        mapping2 = self.addNode("ShaderNodeMapping", 2)
        mapping2.vector_type = 'POINT'
        mapping2.inputs["Location"].default_value = (0.5, 0.5, 0)
        mapping2.inputs["Rotation"].default_value = (-90*D, 0, 0)
        mapping2.inputs["Scale"].default_value = (2, 2 ,2)
        self.links.new(texco.outputs["Object"], mapping2.inputs["Vector"])
        self.links.new(mapping2.outputs["Vector"], self.outputs.inputs["Vector"])

# ---------------------------------------------------------------------
#   Decal Group
# ---------------------------------------------------------------------

class DecalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color", "Influence"]
        self.outsockets += ["Color", "Alpha", "Combined", "Depth Mask"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.outputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Alpha")
        self.group.outputs.new("NodeSocketColor", "Combined")
        self.group.outputs.new("NodeSocketFloat", "Depth Mask")


    def addNodes(self, args):
        empty,img,mask,blendType = args
        if empty:
            ename = empty.name
        else:
            ename = "NONE"
        mapping = self.addGroup(MappingGroup, ename, args=[empty], col=1)

        tex = self.addNode("ShaderNodeTexImage", 2)
        tex.image = img
        tex.interpolation = GS.imageInterpolation
        tex.extension = 'CLIP'
        self.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        alpha = tex.outputs["Alpha"]

        if mask:
            masktex = self.addNode("ShaderNodeTexImage", 2)
            masktex.image = mask
            masktex.interpolation = GS.imageInterpolation
            masktex.extension = 'CLIP'
            self.links.new(mapping.outputs["Vector"], masktex.inputs["Vector"])
            alpha = masktex.outputs["Color"]

        mult = self.addNode("ShaderNodeMath", 3)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Influence"], mult.inputs[0])
        self.links.new(alpha, mult.inputs[1])

        mix2 = self.addNode("ShaderNodeMixRGB", 4)
        mix2.blend_type = 'MIX'
        self.links.new(mapping.outputs["Depth Mask"], mix2.inputs[0])
        self.links.new(self.inputs.outputs["Color"], mix2.inputs[1])

        mix1 = self.addNode("ShaderNodeMixRGB", 4)
        mix1.blend_type = blendType
        self.links.new(mult.outputs[0], mix1.inputs[0])
        self.links.new(self.inputs.outputs["Color"], mix1.inputs[1])
        self.links.new(tex.outputs["Color"], mix1.inputs[2])
        self.links.new(mix1.outputs["Color"], mix2.inputs[2])

        self.links.new(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.links.new(mult.outputs[0], self.outputs.inputs["Alpha"])
        self.links.new(mix2.outputs[0], self.outputs.inputs["Combined"])
        self.links.new(mapping.outputs["Depth Mask"], self.outputs.inputs["Depth Mask"])

# ---------------------------------------------------------------------
#   Layered Group
# ---------------------------------------------------------------------

class LayeredGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Vector", "Influence"]
        self.outsockets += ["Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketVector", "Vector")
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addTextureNodes(self, assets, maps, colorSpace, isMask):
        self.outnode = None
        self.mask = None
        for asset,map in zip(assets, maps):
            innode,texnode,outnode,isnew = self.addSingleTexture(2, asset, map, "COLOR")
            if innode:
                self.links.new(self.inputs.outputs["Vector"], innode.inputs["Vector"])
            if self.outnode is None:
                self.outnode = firstnode = outnode
            else:
                self.mixColor(map, texnode, outnode)
        mix = self.addNode("ShaderNodeMixRGB", 5)
        mix.blend_type = 'MIX'
        mix.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Influence"], mix.inputs[0])
        self.links.new(firstnode.outputs[0], mix.inputs[1])
        self.links.new(self.outnode.outputs[0], mix.inputs[2])
        if colorSpace == "NONE":
            gamma = self.addNode("ShaderNodeGamma", 5)
            self.links.new(mix.outputs["Color"], gamma.inputs["Color"])
            gamma.inputs["Gamma"].default_value = 1/2.2
            self.links.new(gamma.outputs[0], self.outputs.inputs["Color"])
        else:
            self.links.new(mix.outputs[0], self.outputs.inputs["Color"])


    def mixColor(self, map, texnode, outnode):
        def setFactor(alpha, node, slot, mix):
            if alpha != 1:
                node = self.multiplyScalarTex(alpha, node, slot, 3)
                self.links.new(node.outputs[0], mix.inputs[0])
            elif slot in node.outputs.keys():
                self.links.new(node.outputs[slot], mix.inputs[0])
            else:
                mix.inputs[0].default_value = 1

        if map.ismask:
            self.mask = outnode
        else:
            mix = self.addNode("ShaderNodeMixRGB", 4)
            blendType = {
                "multiply" : 'MULTIPLY',
                "add" : 'ADD',
                "subtract" : 'SUBTRACT',
                "alpha_blend" : 'MIX',
            }
            mix.blend_type = blendType[map.operation]
            mix.inputs[0].default_value = map.transparency
            if self.mask:
                setFactor(map.transparency, self.mask, "Color", mix)
                self.mask = None
                mix.use_alpha = False
            else:
                setFactor(map.transparency, texnode, "Alpha", mix)
                mix.use_alpha = False
            self.links.new(self.outnode.outputs["Color"], mix.inputs[1])
            self.links.new(outnode.outputs["Color"], mix.inputs[2])
            self.outnode = mix

#----------------------------------------------------------
#   Make shader group
#----------------------------------------------------------

class DAZ_OT_MakeShaderGroups(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_shader_groups"
    bl_label = "Make Shader Groups"
    bl_description = "Create shader groups for the active material"
    bl_options = {'UNDO'}

    groups = {
        "useDiffuse" : (DiffuseGroup, "DAZ Diffuse", []),
        "useLogColor" : (LogColorGroup, "DAZ Log Color", []),
        "useColorEffect" : (ColorEffectGroup, "DAZ Color Effect", []),
        "useTintedEffect" : (TintedEffectGroup, "DAZ Tinted Effect", []),
        "useFresnel" : (Fresnel2Group, "DAZ Fresnel 2", []),
        "useEmission" : (EmissionGroup, "DAZ Emission", []),
        "useOneSided" : (OneSidedGroup, "DAZ One-Sided", []),
        "useOverlay" : (DiffuseGroup, "DAZ Overlay", []),
        "useGlossy" : (GlossyGroup, "DAZ Glossy", []),
        "useTopCoat" : (TopCoatGroup, "DAZ Top Coat", []),
        "useRefraction" : (RefractionGroup, "DAZ Refraction", []),
        "useFakeCaustics" : (FakeCausticsGroup, "DAZ Fake Caustics", [WHITE]),
        "useTransparent" : (TransparentGroup, "DAZ Transparent", []),
        "useInvertNormalMap" : (InvertNormalMapGroup, "DAZ Invert NMap", []),
        "useTranslucent" : (TranslucentGroup, "DAZ Translucent", []),
        "useSubsurface" : (SubsurfaceGroup, "DAZ Subsurface", []),
        "useRayClip" : (RayClipGroup, "DAZ Ray Clip", []),
        "useDualLobeUber" : (DualLobeGroupUberIray, "DAZ Dual Lobe", []),
        "useDualLobePBR" : (DualLobeGroupPbrSkin, "DAZ Dual Lobe PBR", []),
        "useMetalUber" : (MetalGroupUber, "DAZ Metal", []),
        "useMetalPBR" : (MetalGroupPbrSkin, "DAZ Metal PBR", []),
        "useVolume" : (VolumeGroup, "DAZ Volume", []),
        "useNormal" : (NormalGroup, "DAZ Normal", ["uvname"]),
        "useDisplacement" : (DisplacementGroup, "DAZ Displacement", []),
        "useDecal" : (DecalGroup, "DAZ Decal", [None, None, None, 'MIX']),
    }

    useDiffuse : BoolProperty(name="Diffuse", default=False)
    useLogColor : BoolProperty(name="Log Color", default=False)
    useColorEffect : BoolProperty(name="Color Effect", default=False)
    useTintedEffect : BoolProperty(name="Tinted Effect", default=False)
    useFresnel : BoolProperty(name="Fresnel", default=False)
    useEmission : BoolProperty(name="Emission", default=False)
    useOneSided : BoolProperty(name="One Sided", default=False)
    useOverlay : BoolProperty(name="Diffuse Overlay", default=False)
    useGlossy : BoolProperty(name="Glossy", default=False)
    useTopCoat : BoolProperty(name="Top Coat", default=False)
    useRefraction : BoolProperty(name="Refraction", default=False)
    useFakeCaustics : BoolProperty(name="Fake Caustics", default=False)
    useTransparent : BoolProperty(name="Transparent", default=False)
    useInvertNormalMap : BoolProperty(name="Invert Normal Map", default=False)
    useTranslucent : BoolProperty(name="Translucent", default=False)
    useSubsurface : BoolProperty(name="Subsurface", default=False)
    useRayClip : BoolProperty(name="Ray Clip", default=False)
    useDualLobeUber : BoolProperty(name="Dual Lobe (Uber Shader)", default=False)
    useDualLobePBR : BoolProperty(name="Dual Lobe (PBR Skin)", default=False)
    useMetalUber : BoolProperty(name="Metal (Uber Shader)", default=False)
    useMetalPBR : BoolProperty(name="Metal (PBR Skin)", default=False)
    useVolume : BoolProperty(name="Volume", default=False)
    useNormal : BoolProperty(name="Normal", default=False)
    useDisplacement : BoolProperty(name="Displacement", default=False)
    useDecal : BoolProperty(name="Decal", default=False)

    def draw(self, context):
        for key in self.groups.keys():
            self.layout.prop(self, key)


    def run(self, context):
        from .cycles import CyclesMaterial, CyclesTree
        ob = context.object
        if ob.active_material_index >= len(ob.data.materials):
            raise DazError("No material found")
        mat = ob.data.materials[ob.active_material_index]
        if mat is None:
            raise DazError("No active material")
        cmat = CyclesMaterial("")
        ctree = CyclesTree(cmat)
        ctree.nodes = mat.node_tree.nodes
        ctree.links = mat.node_tree.links
        ctree.column = 0
        for key in self.groups.keys():
            if getattr(self, key):
                group,gname,args = self.groups[key]
                ctree.column += 1
                node = ctree.addGroup(group, gname, args=args)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeShaderGroups,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
