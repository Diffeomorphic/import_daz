# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE, BLACK
from .tree import NodeGroup, hideAllBut, colorOutput
from .tree import addGroupInput, addGroupOutput, getGroupInput
from .utils import *
from .error import *

# ---------------------------------------------------------------------
#   Cycles Group
# ---------------------------------------------------------------------

class CyclesGroup(NodeGroup, CyclesTree):
    def create(self, node, name, parent, ncols):
        owner = (parent.owner if parent else None)
        CyclesTree.__init__(self, owner)
        NodeGroup.create(self, node, name, parent, ncols)


    def addMapRange(self, col):
        node = self.addNode("ShaderNodeMapRange", col)
        if hasattr(node, "data_type"):
            node.data_type = 'FLOAT'
        node.interpolation_type = 'LINEAR'
        node.inputs["From Min"].default_value = 0.0
        node.inputs["From Max"].default_value = 1.0
        node.inputs["To Min"].default_value = 0.0
        node.inputs["To Max"].default_value = 1.0
        return node

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(NodeGroup):
    GroupSize = 11

    def __init__(self, push):
        CyclesTree.__init__(self, None)
        NodeGroup.__init__(self)
        self.push = push
        self.insockets += ["Influence", "BSDF", "UV", "Displacement"]
        self.outsockets += ["BSDF", "Displacement"]


    def create(self, node, name, parent):
        NodeGroup.create(self, node, name, parent, self.GroupSize)
        addGroupInput(self.group, "NodeSocketFloat", "Influence")
        self.setMinMax("Influence", 0.0, 0.0, 10)
        addGroupInput(self.group, "NodeSocketShader", "BSDF")
        addGroupInput(self.group, "NodeSocketVector", "UV")
        self.hideSlot("UV")
        addGroupInput(self.group, "NodeSocketVector", "Displacement")
        self.hideSlot("Displacement")
        addGroupOutput(self.group, "NodeSocketShader", "BSDF")
        addGroupOutput(self.group, "NodeSocketVector", "Displacement")


    def addNodes(self, args):
        shmat,uvname = args
        shmat.copyShellBasics(self.parent.owner)
        self.owner = shmat
        self.cyclesOpaque = None
        self.pbrOpaque = None
        self.inShell = True
        self.texco = self.inputs.outputs["UV"]
        self.tileTexco()
        self.buildLayer(uvname)
        alpha,atex,_ = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
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
        self.addOutputs(mult)

        self.buildDisplacementNodes()
        if self.displacement:
            scale = self.addNode("ShaderNodeVectorMath", 8)
            scale.label = "Scale"
            scale.operation = 'SCALE'
            self.links.new(self.displacement, scale.inputs[0])
            self.links.new(mult.outputs[0], scale.inputs["Scale"])

            add = self.addNode("ShaderNodeVectorMath", 8)
            add.label = "Add"
            add.operation = 'ADD'
            self.links.new(self.inputs.outputs["Displacement"], add.inputs[0])
            self.links.new(scale.outputs[0], add.inputs[1])
            self.links.new(add.outputs[0], self.outputs.inputs["Displacement"])
        else:
            self.links.new(self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])

        if GS.useUnusedTextures:
            self.buildUnusedTextures()


class OpaqueShellGroup(ShellGroup):
    def addOutput(self, mult, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 10)
        mix.inputs[0].default_value = 1
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])
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
        self.links.new(transp.outputs[0], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])

        add = self.addNode("ShaderNodeAddShader", 9)
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

        mix2 = self.addNode("ShaderNodeMixShader", 10)
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

class FresnelGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["IOR", "Roughness", "Power", "Normal"]
        self.outsockets += ["Dielectric", "Metal", "Refraction"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        addGroupInput(self.group, "NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Power")
        self.setMinMax("Power", 1, 1, 4)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        addGroupOutput(self.group, "NodeSocketFloat", "Dielectric")
        addGroupOutput(self.group, "NodeSocketFloat", "Metal")
        addGroupOutput(self.group, "NodeSocketFloat", "Refraction")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 0)
        hideAllBut(geo, ["Incoming", "Backfacing"])

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

        mix1,a,b,out1 = self.addMixRgbNode('MIX', 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs[0])
        self.links.new(self.inputs.outputs["IOR"], a)
        self.links.new(divide.outputs["Value"], b)

        mix2,a,b,out2 = self.addMixRgbNode('MIX', 2)
        self.links.new(power.outputs[0], mix2.inputs[0])
        self.links.new(bump.outputs[0], a)
        self.links.new(geo.outputs["Incoming"], b)

        fresnel1 = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(out1, fresnel1.inputs["IOR"])
        self.links.new(out2, fresnel1.inputs["Normal"])
        self.links.new(fresnel1.outputs["Fac"], self.outputs.inputs["Dielectric"])

        fresnel2 = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(out1, fresnel2.inputs["IOR"])
        self.links.new(geo.outputs["Incoming"], fresnel2.inputs["Normal"])

        fresnel3 = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(self.inputs.outputs["IOR"], fresnel3.inputs["IOR"])
        self.links.new(out2, fresnel3.inputs["Normal"])
        self.links.new(fresnel3.outputs["Fac"], self.outputs.inputs["Refraction"])

        sub = self.addNode("ShaderNodeMath", 4)
        sub.operation = 'SUBTRACT'
        self.links.new(fresnel1.outputs["Fac"], sub.inputs[0])
        self.links.new(fresnel2.outputs["Fac"], sub.inputs[1])
        self.links.new(sub.outputs[0], self.outputs.inputs["Metal"])

# ---------------------------------------------------------------------
#   Schlick Group
# ---------------------------------------------------------------------

class SchlickGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Specular0", "Specular90", "Power"]
        self.outsockets += ["Fac"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        addGroupInput(self.group, "NodeSocketFloat", "Specular0")
        self.setMinMax("Specular0", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Specular90")
        self.setMinMax("Specular90", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Power")
        self.setMinMax("Power", 1, 1, 4)
        addGroupOutput(self.group, "NodeSocketFloat", "Fac")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 0)
        hideAllBut(geo, ["Normal", "Incoming"])

        dot = self.addNode("ShaderNodeVectorMath", 1)
        dot.operation = 'DOT_PRODUCT'
        self.links.new(geo.outputs["Normal"], dot.inputs[0])
        self.links.new(geo.outputs["Incoming"], dot.inputs[1])

        sub1 = self.addNode("ShaderNodeMath", 1)
        sub1.operation = 'SUBTRACT'
        sub1.inputs[0].default_value = 1.0
        self.links.new(dot.outputs["Value"], sub1.inputs[1])

        sub2 = self.addNode("ShaderNodeMath", 2)
        sub2.operation = 'SUBTRACT'
        self.links.new(self.inputs.outputs["Specular90"], sub2.inputs[0])
        self.links.new(self.inputs.outputs["Specular0"], sub2.inputs[1])

        power = self.addNode("ShaderNodeMath", 2)
        power.operation = 'POWER'
        self.links.new(sub1.outputs[0], power.inputs[0])
        self.links.new(self.inputs.outputs["Power"], power.inputs[1])

        mult = self.addNode("ShaderNodeMath", 3)
        mult.operation = 'MULTIPLY_ADD'
        self.links.new(sub2.outputs[0], mult.inputs[0])
        self.links.new(power.outputs[0], mult.inputs[1])
        self.links.new(self.inputs.outputs["Specular0"], mult.inputs[2])
        self.links.new(mult.outputs[0], self.outputs.inputs["Fac"])

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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketColor", "Color")


    def addNodes(self, args=None):
        if BLENDER4:
            sepname = "ShaderNodeSeparateRGB"
            combname = "ShaderNodeCombineRGB"
            slot = "Image"
            red,green,blue = "R", "G", "B"
        else:
            sepname = "ShaderNodeSeparateColor"
            combname = "ShaderNodeCombineColor"
            slot = "Color"
            red,green,blue = "Red", "Green", "Blue"

        sep = self.addNode(sepname, 1)
        self.links.new(self.inputs.outputs["Color"], sep.inputs[slot])
        absRed = self.addLog(sep.outputs[red])
        absGreen = self.addLog(sep.outputs[green])
        absBlue = self.addLog(sep.outputs[blue])

        comb = self.addNode(combname, 5)
        if not BLENDER4:
            sep.mode = 'RGB'
            comb.mode = 'RGB'
        self.links.new(absRed.outputs[0], comb.inputs[red])
        self.links.new(absGreen.outputs[0], comb.inputs[green])
        self.links.new(absBlue.outputs[0], comb.inputs[blue])
        self.links.new(comb.outputs[slot], self.outputs.inputs["Color"])


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
#   SkipZeroUv Group
# ---------------------------------------------------------------------

class SkipZeroUvGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["UV"]
        self.outsockets += ["Influence"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        addGroupInput(self.group, "NodeSocketVector", "UV")
        addGroupOutput(self.group, "NodeSocketFloat", "Influence")


    def addNodes(self, args=None):
        node = self.addNode("ShaderNodeVectorMath", 1)
        node.operation = 'LENGTH'
        self.links.new(self.inputs.outputs["UV"], node.inputs["Vector"])
        comp = self.addNode("ShaderNodeMath", 2)
        comp.operation = 'GREATER_THAN'
        self.links.new(node.outputs["Value"], comp.inputs[0])
        comp.inputs[1].default_value = 0
        self.links.new(comp.outputs[0], self.outputs.inputs["Influence"])

# ---------------------------------------------------------------------
#   Mix Group.
# ---------------------------------------------------------------------

class BSDFGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["BSDF"]
        self.outsockets += ["BSDF"]

    def createShaderSlots(self):
        addGroupInput(self.group, "NodeSocketShader", "BSDF")
        addGroupOutput(self.group, "NodeSocketShader", "BSDF")

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
        addGroupInput(self.group, "NodeSocketFloat", "Fac")
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
        addGroupInput(self.group, "NodeSocketVector", "UV")
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

class AltSSSGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["SSS Amount", "Diffuse Color", "Translucent Color", "Translucency Weight"]
        self.outsockets += ["Base Color", "Subsurface", "Subsurface Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        addGroupInput(self.group, "NodeSocketFloat", "SSS Amount")
        addGroupInput(self.group, "NodeSocketColor", "Diffuse Color")
        addGroupInput(self.group, "NodeSocketColor", "Translucent Color")
        addGroupInput(self.group, "NodeSocketFloat", "Translucency Weight")
        self.setMinMax("Translucency Weight", 0.5, 0.0, 1.0)
        addGroupOutput(self.group, "NodeSocketFloat", "Subsurface")
        addGroupOutput(self.group, "NodeSocketColor", "Base Color")
        addGroupOutput(self.group, "NodeSocketColor", "Subsurface Color")


    def addNodes(self, args=None):
        maprange = self.addMapRange(1)
        self.links.new(self.inputs.outputs["SSS Amount"], maprange.inputs["Value"])
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

        dodge1,a,b,out1 = self.addMixRgbNode('DODGE', 3)
        self.links.new(self.inputs.outputs["Translucency Weight"], dodge1.inputs[0])
        self.links.new(hsv1.outputs["Color"], a)
        self.links.new(self.inputs.outputs["Diffuse Color"], b)

        dodge2,a,b,out2 = self.addMixRgbNode('DODGE', 3)
        self.links.new(self.inputs.outputs["Translucency Weight"], dodge2.inputs[0])
        self.links.new(hsv2.outputs["Color"], a)
        self.links.new(self.inputs.outputs["Translucent Color"], b)

        self.links.new(maprange.outputs["Result"], self.outputs.inputs["Subsurface"])
        self.links.new(out1, self.outputs.inputs["Base Color"])
        self.links.new(out2, self.outputs.inputs["Subsurface Color"])

# ---------------------------------------------------------------------
#   Color Effect Group
# ---------------------------------------------------------------------

class ColorEffectGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Color", "Tint"]
        self.outsockets += ["Transmit Fac", "Intensity Fac", "Color"]

    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        addGroupInput(self.group, "NodeSocketFloat", "Fac")
        self.setMinMax("Fac", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketColor", "Tint")
        getGroupInput(self.group, "Tint").default_value = (1,1,1,1)
        addGroupOutput(self.group, "NodeSocketFloat", "Transmit Fac")
        addGroupOutput(self.group, "NodeSocketFloat", "Intensity Fac")
        addGroupOutput(self.group, "NodeSocketColor", "Color")

    def addNodes(self, args=None):
        mult,a,b,out = self.addMixRgbNode('MULTIPLY', 1)
        mult.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(self.inputs.outputs["Tint"], b)

        mix,a,b,mixout = self.addMixRgbNode('MIX', 2)
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        a.default_value[0:3] = BLACK
        self.links.new(colorOutput(mult), b)

        rgb,a,b,rgbout = self.addMixRgbNode('COLOR', 2)
        rgb.inputs[0].default_value = 1.0
        a.default_value[0:3] = WHITE
        self.links.new(colorOutput(mult), b)

        scale = self.addNode("ShaderNodeVectorMath", 3)
        scale.operation = 'SCALE'
        self.links.new(mixout, scale.inputs["Vector"])
        scale.inputs["Scale"].default_value = 1.0

        hsv2 = self.addNode("ShaderNodeHueSaturation", 3)
        hsv2.inputs["Hue"].default_value = 0.5
        hsv2.inputs["Saturation"].default_value = 0.0
        hsv2.inputs["Value"].default_value = 1.0
        hsv2.inputs["Fac"].default_value = 1.0
        self.links.new(mixout, hsv2.inputs["Color"])

        self.links.new(scale.outputs[0], self.outputs.inputs["Transmit Fac"])
        self.links.new(hsv2.outputs["Color"], self.outputs.inputs["Intensity Fac"])
        self.links.new(rgbout, self.outputs.inputs["Color"])

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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketColor", "Color")


    def addNodes(self, args=None):
        if BLENDER4:
            sepname = "ShaderNodeSeparateRGB"
            combname = "ShaderNodeCombineRGB"
            slot = "Image"
            red,green,blue = "R", "G", "B"
        else:
            sepname = "ShaderNodeSeparateColor"
            combname = "ShaderNodeCombineColor"
            slot = "Color"
            red,green,blue = "Red", "Green", "Blue"

        sep = self.addNode(sepname, 1)
        self.links.new(self.inputs.outputs["Color"], sep.inputs[slot])

        invRed = self.addNode("ShaderNodeInvert", 2)
        invRed.inputs["Fac"].default_value = 1.0
        self.links.new(sep.outputs[red], invRed.inputs["Color"])

        invGreen = self.addNode("ShaderNodeInvert", 2)
        invGreen.inputs["Fac"].default_value = 1.0
        self.links.new(sep.outputs[green], invGreen.inputs["Color"])

        comb = self.addNode(combname, 3)
        if not BLENDER4:
            sep.mode = 'RGB'
            comb.mode = 'RGB'
        self.links.new(comb.outputs[slot], self.outputs.inputs["Color"])
        self.links.new(invRed.outputs[0], comb.inputs[red])
        self.links.new(invGreen.outputs[0], comb.inputs[green])
        self.links.new(sep.outputs[blue], comb.inputs[blue])

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
        addGroupInput(self.group, "NodeSocketFloat", "Fac")
        self.setMinMax("Fac", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketShader", "Diffuse Cycles")
        addGroupInput(self.group, "NodeSocketShader", "Glossy Cycles")
        addGroupOutput(self.group, "NodeSocketShader", "BSDF")


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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Strength")


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
        hideAllBut(geo, ["Backfacing"])
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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)

        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
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
#   Toon Diffuse Group
# ---------------------------------------------------------------------

class ToonDiffuseGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color", "Ambience", "Normal"]
        self.outsockets += ["Output"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 6)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketColor", "Ambience")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        addGroupOutput(self.group, "NodeSocketColor", "Output")


    def addNodes(self, args=None):
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        diffuse.inputs["Color"].default_value[0:3] = WHITE
        diffuse.inputs["Roughness"].default_value = 0.0
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])

        toRgb = self.addNode("ShaderNodeShaderToRGB", 2)
        self.links.new(diffuse.outputs["BSDF"], toRgb.inputs["Shader"])

        maprange = self.addMapRange(3)
        maprange.interpolation_type = 'STEPPED'
        maprange.inputs["From Max"].default_value = 0.05
        maprange.inputs["Steps"].default_value = 1
        self.links.new(toRgb.outputs["Color"], maprange.inputs["Value"])

        node = self.addNode("ShaderNodeValue", 2)
        node.label = "HDRI Threshold"
        node.outputs["Value"].default_value = 0.05
        self.links.new(node.outputs["Value"], maprange.inputs["From Max"])

        mix,a,b,mixout = self.addMixRgbNode('MIX', 4)
        self.links.new(maprange.outputs["Result"], mix.inputs[0])
        self.links.new(self.inputs.outputs["Ambience"], a)
        b.default_value[0:3] = WHITE

        mult,a,b,multout = self.addMixRgbNode('MULTIPLY', 5)
        mult.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(mixout, b)
        self.links.new(multout, self.outputs.inputs["Output"])

# ---------------------------------------------------------------------
#   Toon Glossy Group
# ---------------------------------------------------------------------

class ToonGlossyGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Input", "Reflection", "Roughness", "Normal"]
        self.outsockets += ["Output"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        addGroupInput(self.group, "NodeSocketColor", "Input")
        addGroupInput(self.group, "NodeSocketColor", "Reflection")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        addGroupOutput(self.group, "NodeSocketColor", "Output")


    def addNodes(self, args=None):
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Reflection"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        toRgb = self.addNode("ShaderNodeShaderToRGB", 2)
        self.links.new(glossy.outputs["BSDF"], toRgb.inputs["Shader"])

        maprange = self.addMapRange(3)
        maprange.interpolation_type = 'SMOOTHERSTEP'
        maprange.inputs["From Max"].default_value = 0.2
        self.links.new(toRgb.outputs["Color"], maprange.inputs["Value"])

        screen,a,b,scrout = self.addMixRgbNode('SCREEN', 4)
        screen.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Input"], a)
        self.links.new(maprange.outputs["Result"], b)

        self.links.new(scrout, self.outputs.inputs["Output"])

# ---------------------------------------------------------------------
#   Toon Rim Group
# ---------------------------------------------------------------------

class ToonRimGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Input", "Rim", "Color", "Normal"]
        self.outsockets += ["Output"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        addGroupInput(self.group, "NodeSocketColor", "Input")
        addGroupInput(self.group, "NodeSocketFloat", "Rim")
        self.setMinMax("Rim", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        addGroupOutput(self.group, "NodeSocketColor", "Output")


    def addNodes(self, args=None):
        lweight = self.addNode("ShaderNodeLayerWeight", 1)
        self.links.new(self.inputs.outputs["Rim"], lweight.inputs["Blend"])
        self.links.new(self.inputs.outputs["Normal"], lweight.inputs["Normal"])

        maprange = self.addMapRange(2)
        maprange.interpolation_type = 'STEPPED'
        maprange.inputs["Steps"].default_value = 1
        self.links.new(lweight.outputs["Facing"], maprange.inputs["Value"])

        mult,a,b,multout = self.addMixRgbNode('MULTIPLY', 3)
        mult.inputs[0].default_value = 1.0
        self.links.new(maprange.outputs["Result"], a)
        self.links.new(self.inputs.outputs["Color"], b)

        screen,a,b,scrout = self.addMixRgbNode('SCREEN', 4)
        screen.inputs[0].default_value = 1.0
        self.links.new(multout, a)
        self.links.new(self.inputs.outputs["Input"], b)

        self.links.new(scrout, self.outputs.inputs["Output"])

# ---------------------------------------------------------------------
#   Toon Light Group
# ---------------------------------------------------------------------

class ToonLightGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Input"]
        self.outsockets += ["Output"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        addGroupInput(self.group, "NodeSocketColor", "Input")
        addGroupOutput(self.group, "NodeSocketColor", "Output")


    def addNodes(self, args=None):
        mult,a,b,multout = self.addMixRgbNode('MULTIPLY', 1)
        mult.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["Input"], a)

        rgb = self.addNode("ShaderNodeRGB", 0)
        rgb.label = "Light Color"
        rgb.outputs["Color"].default_value[0:3] = WHITE
        self.links.new(rgb.outputs["Color"], b)

        hsv = self.addNode("ShaderNodeHueSaturation", 2)
        hsv.inputs["Hue"].default_value = 0.5
        hsv.inputs["Saturation"].default_value = 1.0
        hsv.inputs["Value"].default_value = 1.0
        hsv.inputs["Fac"].default_value = 1.0
        self.links.new(multout, hsv.inputs["Color"])

        node = self.addNode("ShaderNodeValue", 1)
        node.label = "Light Intensity"
        node.outputs["Value"].default_value = 1.0
        self.links.new(node.outputs["Value"], hsv.inputs["Value"])

        self.links.new(hsv.outputs["Color"], self.outputs.inputs["Output"])

# ---------------------------------------------------------------------
#   Metal Group
# ---------------------------------------------------------------------

class MetalGroupUber(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 5)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
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

        mix,a,b,mixout = self.addMixRgbNode('MIX', 2)
        self.links.new(fresnel.outputs["Metal"], mix.inputs[0])
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(hsv.outputs["Color"], b)

        node = self.addNode("ShaderNodeBsdfAnisotropic", 3)
        node.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(mixout, node.inputs["Color"])
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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness 1")
        self.setMinMax("Roughness 1", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness 2")
        self.setMinMax("Roughness 2", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Dual Ratio")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
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
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
        fresnel.inputs["IOR"].default_value = 1.5
        self.links.new(self.inputs.outputs[slot], fresnel.inputs["Roughness"])
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        mix,a,b,mixout = self.addMixRgbNode('MIX', 2)
        self.links.new(fresnel.outputs["Metal"], mix.inputs[0])
        self.links.new(self.inputs.outputs["Color"], a)
        b.default_value[0:3] = WHITE

        glossy = self.addNode("ShaderNodeBsdfGlossy", 3)
        glossy.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(mixout, glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[slot], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy

# ---------------------------------------------------------------------
#   Top Coat Group
# ---------------------------------------------------------------------

class TopCoatGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Specular0", "Specular90", "Power", "Color", "Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 4)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Specular0")
        self.setMinMax("Specular0", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Specular90")
        self.setMinMax("Specular90", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Power")
        self.setMinMax("Power", 1, 1, 4)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)

        schlick = self.addGroup(SchlickGroup, "DAZ Schlick", 1)
        self.links.new(self.inputs.outputs["Specular0"], schlick.inputs["Specular0"])
        self.links.new(self.inputs.outputs["Specular90"], schlick.inputs["Specular90"])
        self.links.new(self.inputs.outputs["Power"], schlick.inputs["Power"])

        aniso = self.addNode("ShaderNodeBsdfAnisotropic", 1)
        aniso.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(self.inputs.outputs["Color"], aniso.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], aniso.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Anisotropy"], aniso.inputs["Anisotropy"])
        self.links.new(self.inputs.outputs["Rotation"], aniso.inputs["Rotation"])
        self.links.new(self.inputs.outputs["Normal"], aniso.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(schlick.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["BSDF"], mix.inputs[1])
        self.links.new(aniso.outputs[0], mix.inputs[2])

        self.mixCycles(mix.outputs[0], 2)

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------

class RefractionThinWallGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += self.extra + [
            "Refraction Color", "IOR",
            "Glossy Color", "Glossy Roughness", "Anisotropy", "Rotation", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 5)
        addGroupInput(self.group, "NodeSocketColor", "Refraction Color")
        self.addArgs()
        addGroupInput(self.group, "NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        addGroupInput(self.group, "NodeSocketColor", "Glossy Color")
        addGroupInput(self.group, "NodeSocketFloat", "Glossy Roughness")
        self.setMinMax("Glossy Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Rotation")
        self.setMinMax("Rotation", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        node = self.AddRefractionTransparent()

        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 2)
        fresnel.inputs["Power"].default_value = self.power
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
        self.links.new(fresnel.outputs[self.fresnel], mix.inputs[0])
        self.links.new(node.outputs[0], mix.inputs[1])
        self.links.new(aniso.outputs[0], mix.inputs[2])

        self.mixCycles(mix.outputs[0], 2)


class RefractionGroup(RefractionThinWallGroup):
    useRoughness = True
    power = 3
    fresnel = "Refraction"
    extra = ["Refraction Roughness"]

    def addArgs(self):
        addGroupInput(self.group, "NodeSocketFloat", "Refraction Roughness")
        self.setMinMax("Refraction Roughness", 0.5, 0.0, 1.0)

    def AddRefractionTransparent(self):
        node = self.addNode("ShaderNodeBsdfRefraction", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], node.inputs["Color"])
        self.links.new(self.inputs.outputs["Refraction Roughness"], node.inputs["Roughness"])
        self.links.new(self.inputs.outputs["IOR"], node.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], node.inputs["Normal"])
        return node


class ThinWallGroup(RefractionThinWallGroup):
    useRoughness = False
    power = 2
    fresnel = "Dielectric"
    extra = []

    def addArgs(self):
        return

    def AddRefractionTransparent(self):
        node = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], node.inputs["Color"])
        return node


# ---------------------------------------------------------------------
#   Fake Caustics Group
# ---------------------------------------------------------------------

class FakeCausticsGroup(FacMixGroup):

    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 6)


    def addNodes(self, args):
        FacMixGroup.addNodes(self, args)
        geo = self.addNode("ShaderNodeNewGeometry", 1)
        hideAllBut(geo, ["Incoming", "Normal"])

        dot = self.addNode("ShaderNodeVectorMath", 2)
        dot.operation = 'DOT_PRODUCT'
        self.links.new(geo.outputs["Normal"], dot.inputs[0])
        self.links.new(geo.outputs["Incoming"], dot.inputs[1])

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
        hideAllBut(lightpath, ["Is Shadow Ray"])
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
        addGroupInput(self.group, "NodeSocketColor", "Color")


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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Scale")
        addGroupInput(self.group, "NodeSocketVector", "Radius")
        addGroupInput(self.group, "NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        addGroupInput(self.group, "NodeSocketFloat", "Anisotropy")
        self.setMinMax("Anisotropy", 0.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")

    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        try:
            sss.falloff = GS.sssMethod
        except TypeError:
            pass
        self.links.new(self.inputs.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        if sss.falloff != 'BURLEY':
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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.mixCycles(diffuse.outputs[0], 2)

# ---------------------------------------------------------------------
#   Flakes Group
# ---------------------------------------------------------------------

class FlakesGroup(FacMixGroup):
    def __init__(self):
        FacMixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Strength", "Distance", "Scale", "From Min", "Normal"]


    def create(self, node, name, parent):
        FacMixGroup.create(self, node, name, parent, 6)
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Roughness")
        self.setMinMax("Roughness", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Strength")
        self.setMinMax("Strength", 1.0, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Distance")
        addGroupInput(self.group, "NodeSocketFloat", "Scale")
        addGroupInput(self.group, "NodeSocketFloat", "From Min")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")


    def addNodes(self, args=None):
        FacMixGroup.addNodes(self, args)

        noise = self.addNode("ShaderNodeTexNoise", 0)
        self.links.new(self.inputs.outputs["Scale"], noise.inputs["Scale"])
        noise.inputs["Detail"].default_value = 0.0
        noise.inputs["Roughness"].default_value = 0.0
        noise.inputs["Distortion"].default_value = 0.0

        maprange = self.addMapRange(1)
        self.links.new(noise.outputs["Fac"], maprange.inputs["Value"])
        self.links.new(self.inputs.outputs["From Min"], maprange.inputs["From Min"])

        mult = self.addNode("ShaderNodeMath", 2)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Fac"], mult.inputs[0])
        self.links.new(maprange.outputs["Result"], mult.inputs[1])

        bump = self.addNode("ShaderNodeBump", 2)
        self.links.new(self.inputs.outputs["Strength"], bump.inputs["Strength"])
        self.links.new(self.inputs.outputs["Distance"], bump.inputs["Distance"])
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        self.links.new(maprange.outputs["Result"], bump.inputs["Height"])

        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 3)
        fresnel.inputs["IOR"].default_value = 1.5
        fresnel.inputs["Power"].default_value = 2
        self.links.new(self.inputs.outputs["Roughness"], fresnel.inputs["Roughness"])
        self.links.new(bump.outputs["Normal"], fresnel.inputs["Normal"])

        hsv = self.addNode("ShaderNodeHueSaturation", 3)
        hsv.inputs["Hue"].default_value = 0.5
        hsv.inputs["Saturation"].default_value = 0.0
        hsv.inputs["Value"].default_value = 1.0
        hsv.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["Color"], hsv.inputs["Color"])

        mix,a,b,out = self.addMixRgbNode('MIX', 4)
        self.links.new(fresnel.outputs["Metal"], mix.inputs[0])
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(hsv.outputs["Color"], b)

        glossy = self.addNode("ShaderNodeBsdfGlossy", 5)
        glossy.distribution = 'ASHIKHMIN_SHIRLEY'
        self.links.new(out, glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(bump.outputs["Normal"], glossy.inputs["Normal"])

        self.mixCycles(mult.outputs[0], 0)
        self.mixCycles(glossy.outputs["BSDF"], 2)

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
        addGroupInput(self.group, "NodeSocketShader", "Emission")
        addGroupInput(self.group, "NodeSocketShader", "Transparent")
        addGroupOutput(self.group, "NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        lpath = self.addNode("ShaderNodeLightPath", 1)
        hideAllBut(lpath, ["Is Camera Ray", "Is Shadow Ray"])

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
        addGroupInput(self.group, "NodeSocketShader", "Shader")
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        lpath = self.addNode("ShaderNodeLightPath", 1)
        hideAllBut(lpath, ["Is Shadow Ray", "Is Reflection Ray"])

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
        addGroupInput(self.group, "NodeSocketFloat", "Ratio")
        self.setMinMax("Ratio", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "IOR")
        self.setMinMax("IOR", 1.0, 1.0, 5.0)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness 1")
        self.setMinMax("Roughness 1", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketFloat", "Roughness 2")
        self.setMinMax("Roughness 2", 0.5, 0.0, 1.0)
        addGroupInput(self.group, "NodeSocketVector", "Normal")
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
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
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
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
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
        addGroupInput(self.group, "NodeSocketColor", "Absorbtion Color")
        addGroupInput(self.group, "NodeSocketFloat", "Absorbtion Density")
        addGroupInput(self.group, "NodeSocketColor", "Scatter Color")
        addGroupInput(self.group, "NodeSocketFloat", "Scatter Density")
        addGroupInput(self.group, "NodeSocketFloat", "Scatter Anisotropy")
        addGroupOutput(self.group, "NodeSocketShader", "Volume")


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
        self.insockets += ["Strength", "Color", "UV"]
        self.outsockets += ["Normal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 8)
        addGroupInput(self.group, "NodeSocketFloat", "Strength")
        self.setMinMax("Strength", 1.0, 0.0, 1.0)
        color = addGroupInput(self.group, "NodeSocketColor", "Color")
        color.default_value = ((0.5, 0.5, 1.0, 1.0))
        addGroupInput(self.group, "NodeSocketVector", "UV")
        addGroupOutput(self.group, "NodeSocketVector", "Normal")


    def addNodes(self, args):
        # Generate TBN from Bump Node
        frame = self.nodes.new("NodeFrame")
        frame.label = "Generate TBN from Bump Node"

        uvgrads = self.addNode("ShaderNodeSeparateXYZ", 2, label="UV Gradients", parent=frame)
        self.links.new(self.inputs.outputs["UV"], uvgrads.inputs[0])

        tangent = self.addNode("ShaderNodeBump", 3, label="Tangent", parent=frame)
        tangent.invert = True
        tangent.inputs["Distance"].default_value = 1
        self.links.new(uvgrads.outputs[0], tangent.inputs["Height"])

        bitangent = self.addNode("ShaderNodeBump", 3, label="Bi-Tangent", parent=frame)
        bitangent.invert = True
        bitangent.inputs["Distance"].default_value = 1000
        self.links.new(uvgrads.outputs[1], bitangent.inputs["Height"])

        geo = self.addNode("ShaderNodeNewGeometry", 2, label="Normal", parent=frame)

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

        rgb,a,b,rgbout = self.addMixRgbNode('MIX', 3, parent=frame)
        self.links.new(self.inputs.outputs["Strength"], rgb.inputs[0])
        a.default_value = (0.5, 0.5, 1.0, 1.0)
        self.links.new(self.inputs.outputs["Color"], b)

        sub = self.addNode("ShaderNodeVectorMath", 4, parent=frame)
        sub.operation = 'SUBTRACT'
        self.links.new(rgbout, sub.inputs[0])
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
        addGroupInput(self.group, "NodeSocketFloat", "Texture")
        addGroupInput(self.group, "NodeSocketFloat", "Strength")
        addGroupInput(self.group, "NodeSocketFloat", "Max")
        addGroupInput(self.group, "NodeSocketFloat", "Min")
        addGroupInput(self.group, "NodeSocketVector", "Normal")
        self.hideSlot("Normal")
        addGroupOutput(self.group, "NodeSocketVector", "Displacement")


    def addNodes(self, args=None):
        sub = self.addNode("ShaderNodeMath", 1)
        sub.operation = 'SUBTRACT'
        self.links.new(self.inputs.outputs["Max"], sub.inputs[0])
        self.links.new(self.inputs.outputs["Min"], sub.inputs[1])

        mult = self.addNode("ShaderNodeMath", 2)
        mult.operation = 'MULTIPLY_ADD'
        self.links.new(self.inputs.outputs["Texture"], mult.inputs[0])
        self.links.new(sub.outputs[0], mult.inputs[1])
        self.links.new(self.inputs.outputs["Min"], mult.inputs[2])

        disp = self.addNode("ShaderNodeDisplacement", 3)
        self.links.new(mult.outputs[0], disp.inputs["Height"])
        disp.inputs["Midlevel"].default_value = 0
        self.links.new(self.inputs.outputs["Strength"], disp.inputs["Scale"])
        self.links.new(self.inputs.outputs["Normal"], disp.inputs["Normal"])

        self.links.new(disp.outputs[0], self.outputs.inputs["Displacement"])

# ---------------------------------------------------------------------
#   Mapping Group
# ---------------------------------------------------------------------

class DazDecalMapGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Vector"]
        self.outsockets += ["Depth Mask", "Vector"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        addGroupInput(self.group, "NodeSocketVector", "Vector")
        addGroupOutput(self.group, "NodeSocketFloat", "Depth Mask")
        addGroupOutput(self.group, "NodeSocketVector", "Vector")


    def addNodes(self, args):
        mapping1 = self.addNode("ShaderNodeMapping", 1)
        mapping1.vector_type = 'POINT'
        mapping1.inputs["Location"].default_value = (0, 0, 0)
        mapping1.inputs["Rotation"].default_value = (0, 0, 0)
        mapping1.inputs["Scale"].default_value = (0.1, 1.0, 0.1)
        self.links.new(self.inputs.outputs["Vector"], mapping1.inputs["Vector"])

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
        self.links.new(self.inputs.outputs["Vector"], mapping2.inputs["Vector"])
        self.links.new(mapping2.outputs["Vector"], self.outputs.inputs["Vector"])


def fixDecalMaps():
    # Lost the correct location somewhere
    mtree = bpy.data.node_groups.get("DAZ Decal Map")
    if mtree:
        map1,map2 = [mnode for mnode in mtree.nodes if mnode.type == 'MAPPING']
        if GS.verbosity >= 3:
            print("Fix maps",  map1.inputs["Location"].default_value,  map2.inputs["Location"].default_value)
        map1.inputs["Location"].default_value = (0, 0, 0)
        map1.inputs["Rotation"].default_value = (0, 0, 0)
        map1.inputs["Scale"].default_value = (0.1, 1.0, 0.1)
        map2.inputs["Location"].default_value = (0.5, 0.5, 0)
        map2.inputs["Rotation"].default_value = (-90*D, 0, 0)
        map2.inputs["Scale"].default_value = (2, 2 ,2)
    for map, loc, rot, scale in LS.mappingNodes:
        map.inputs["Location"].default_value = loc
        map.inputs["Rotation"].default_value = rot
        map.inputs["Scale"].default_value = scale


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
        addGroupInput(self.group, "NodeSocketColor", "Color")
        addGroupInput(self.group, "NodeSocketFloat", "Influence")
        addGroupOutput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketFloat", "Alpha")
        addGroupOutput(self.group, "NodeSocketColor", "Combined")
        addGroupOutput(self.group, "NodeSocketFloat", "Depth Mask")


    def addNodes(self, args):
        empty,img,mask,blendType = args
        texco,mapping = self.addDecalMapGroup(empty, col=1)

        tex = self.addNode("ShaderNodeTexImage", 2)
        tex.image = img
        tex.interpolation = GS.imageInterpolation
        tex.extension = 'CLIP'
        self.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        alpha = tex.outputs.get("Alpha", 1.0)

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

        mix1,a,b,out1 = self.addMixRgbNode(blendType, 4)
        self.links.new(mult.outputs[0], mix1.inputs[0])
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(tex.outputs["Color"], b)

        mix2,a,b,out2 = self.addMixRgbNode('MIX', 4)
        self.links.new(mapping.outputs["Depth Mask"], mix2.inputs[0])
        self.links.new(self.inputs.outputs["Color"], a)
        self.links.new(out1, b)

        self.links.new(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.links.new(mult.outputs[0], self.outputs.inputs["Alpha"])
        self.links.new(out2, self.outputs.inputs["Combined"])
        self.links.new(mapping.outputs["Depth Mask"], self.outputs.inputs["Depth Mask"])

# ---------------------------------------------------------------------
#   Layered Group
# ---------------------------------------------------------------------

class LayeredGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Vector", "Influence"]
        self.outsockets += ["Color", "Alpha"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 6)
        addGroupInput(self.group, "NodeSocketVector", "Vector")
        self.hideSlot("Vector")
        if GS.useLayeredInflu:
            addGroupInput(self.group, "NodeSocketFloat", "Influence")
            self.setMinMax("Influence", 0.0, 0.0, 10)
        addGroupOutput(self.group, "NodeSocketColor", "Color")
        addGroupOutput(self.group, "NodeSocketFloat", "Alpha")
        self.isDecal = parent.isDecal


    def addTextureNodes(self, assets, maps, imgmod, colorSpace, isMask):
        self.outnode = None
        self.mask = None
        texnode0 = None
        for asset,map in zip(assets, maps):
            innode,texnode,outnode,isnew = self.addSingleTexture(2, asset, map, imgmod, colorSpace)
            if texnode0 is None:
                texnode0 = texnode
            if innode:
                self.links.new(self.inputs.outputs["Vector"], innode.inputs["Vector"])
            if self.outnode is None:
                self.outnode = firstnode = outnode
            else:
                self.mixColor(map, texnode, outnode)
        if GS.useLayeredInflu:
            mix,a,b,mixout = self.addMixRgbNode('MIX', 5)
            mix.inputs[0].default_value = 1.0
            self.links.new(self.inputs.outputs["Influence"], mix.inputs[0])
            self.links.new(colorOutput(firstnode), a)
            self.links.new(colorOutput(self.outnode), b)
            self.links.new(mixout, self.outputs.inputs["Color"])
        else:
            self.links.new(colorOutput(self.outnode), self.outputs.inputs["Color"])
        self.outputs.inputs["Alpha"].default_value = 1.0
        socket = texnode0.outputs.get("Alpha")
        if socket:
            self.links.new(socket, self.outputs.inputs["Alpha"])
        firstnode.select = True
        self.nodes.active = firstnode


    def mixColor(self, map, texnode, outnode):
        def setFactor(alpha, node, slot, mix):
            if slot not in node.outputs.keys():
                slot = 0
            if alpha > 0 and alpha < 1:
                node = self.multiplyScalarTex(alpha, node, slot, col=3)
                self.links.new(node.outputs[0], mix.inputs[0])
            else:
                self.links.new(node.outputs[slot], mix.inputs[0])

        if map.ismask:
            self.mask = outnode
        elif map.transparency == 0:
            self.outnode = outnode
        else:
            BlendType = {
                "multiply" : 'MULTIPLY',
                "add" : 'ADD',
                "subtract" : 'SUBTRACT',
                "alpha_blend" : 'MIX',
                "blend_source_over" : 'MIX',
                "blend_color_burn" : 'BURN',
                "blend_color_dodge" : 'DODGE',
                "blend_darken" : 'DARKEN',
                "blend_difference" : 'DIFFERENCE',
                "blend_exclusion" : 'DIFFERENCE', # eh...
                "blend_hard_light" : 'LINEAR_LIGHT', # eh...
                "blend_lighten": 'LIGHTEN',
                "blend_multiply" : 'MULTIPLY',
                "blend_overlay": 'OVERLAY',
                "blend_plus" : 'ADD',
                "blend_screen" : 'SCREEN',
                "blend_soft_light": 'SOFT_LIGHT',
            }
            mix,a,b,out = self.addMixRgbNode(BlendType.get(map.operation, 'MIX'), 4)
            mix.inputs[0].default_value = map.transparency
            if self.mask:
                setFactor(map.transparency, self.mask, "Color", mix)
                self.mask = None
            else:
                setFactor(map.transparency, texnode, "Alpha", mix)
            self.links.new(colorOutput(self.outnode), a)
            self.links.new(colorOutput(outnode), b)
            self.outnode = mix

#----------------------------------------------------------
#   Make shader group
#----------------------------------------------------------

ShaderGroups = {
        "useDiffuse" : (DiffuseGroup, "DAZ Diffuse", []),
        "useLogColor" : (LogColorGroup, "DAZ Log Color", []),
        "useColorEffect" : (ColorEffectGroup, "DAZ Color Effect", []),
        "useFresnel" : (FresnelGroup, "DAZ Fresnel", []),
        "useSchlick" : (SchlickGroup, "DAZ Schlick", []),
        "useEmission" : (EmissionGroup, "DAZ Emission", []),
        "useOneSided" : (OneSidedGroup, "DAZ One-Sided", []),
        "useOverlay" : (DiffuseGroup, "DAZ Overlay", []),
        "useGlossy" : (GlossyGroup, "DAZ Glossy", []),
        "useTopCoat" : (TopCoatGroup, "DAZ Top Coat", []),
        "useRefraction" : (RefractionGroup, "DAZ Refraction", []),
        "useThinWall" : (ThinWallGroup, "DAZ Thin Wall", []),
        "useFakeCaustics" : (FakeCausticsGroup, "DAZ Fake Caustics", [WHITE]),
        "useTransparent" : (TransparentGroup, "DAZ Transparent", []),
        "useInvertNormalMap" : (InvertNormalMapGroup, "DAZ Invert NMap", []),
        "useTranslucent" : (TranslucentGroup, "DAZ Translucent", []),
        "useSubsurface" : (SubsurfaceGroup, "DAZ Subsurface", []),
        "useAltSSS" : (AltSSSGroup, "DAZ Alt SSS", []),
        "useFlakes" : (FlakesGroup, "DAZ Flakes", []),
        "useRayClip" : (RayClipGroup, "DAZ Ray Clip", []),
        "useDualLobeUber" : (DualLobeGroupUberIray, "DAZ Dual Lobe", []),
        "useDualLobePBR" : (DualLobeGroupPbrSkin, "DAZ Dual Lobe PBR", []),
        "useMetalUber" : (MetalGroupUber, "DAZ Metal", []),
        "useMetalPBR" : (MetalGroupPbrSkin, "DAZ Metal PBR", []),
        "useVolume" : (VolumeGroup, "DAZ Volume", []),
        "useNormal" : (NormalGroup, "DAZ Normal", ["uvname"]),
        "useDisplacement" : (DisplacementGroup, "DAZ Displacement", []),
        "useDecal" : (DecalGroup, "DAZ Decal", [None, None, None, 'MIX']),
        "useDecalMap" : (DazDecalMapGroup, "DAZ Decal Map", []),
        "useToonDiffuse" : (ToonDiffuseGroup, "DAZ Toon Diffuse", []),
        "useToonGlossy" : (ToonGlossyGroup, "DAZ Toon Glossy", []),
        "useToonRim" : (ToonRimGroup, "DAZ Toon Rim", []),
        "useToonLight" : (ToonLightGroup, "DAZ Toon Light", []),

    }

class DAZ_OT_MakeShaderGroups(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_shader_groups"
    bl_label = "Make Shader Groups"
    bl_description = "Create shader groups for the active material"
    bl_options = {'UNDO'}

    useDiffuse : BoolProperty(name="Diffuse", default=False)
    useLogColor : BoolProperty(name="Log Color", default=False)
    useColorEffect : BoolProperty(name="Color Effect", default=False)
    useTintedEffect : BoolProperty(name="Tinted Effect", default=False)
    useFresnel : BoolProperty(name="Fresnel", default=False)
    useSchlick : BoolProperty(name="Schlick", default=False)
    useEmission : BoolProperty(name="Emission", default=False)
    useOneSided : BoolProperty(name="One Sided", default=False)
    useOverlay : BoolProperty(name="Diffuse Overlay", default=False)
    useGlossy : BoolProperty(name="Glossy", default=False)
    useTopCoat : BoolProperty(name="Top Coat", default=False)
    useRefraction : BoolProperty(name="Refraction", default=False)
    useThinWall : BoolProperty(name="Thin Wall", default=False)
    useFakeCaustics : BoolProperty(name="Fake Caustics", default=False)
    useTransparent : BoolProperty(name="Transparent", default=False)
    useInvertNormalMap : BoolProperty(name="Invert Normal Map", default=False)
    useTranslucent : BoolProperty(name="Translucent", default=False)
    useSubsurface : BoolProperty(name="Subsurface", default=False)
    useAltSSS : BoolProperty(name="Alt SSS", default=False)
    useFlakes : BoolProperty(name="Metallic Flakes", default=False)
    useRayClip : BoolProperty(name="Ray Clip", default=False)
    useDualLobeUber : BoolProperty(name="Dual Lobe (Uber Shader)", default=False)
    useDualLobePBR : BoolProperty(name="Dual Lobe (PBR Skin)", default=False)
    useMetalUber : BoolProperty(name="Metal (Uber Shader)", default=False)
    useMetalPBR : BoolProperty(name="Metal (PBR Skin)", default=False)
    useVolume : BoolProperty(name="Volume", default=False)
    useNormal : BoolProperty(name="Normal", default=False)
    useDisplacement : BoolProperty(name="Displacement", default=False)
    useDecal : BoolProperty(name="Decal", default=False)
    useDecalMap : BoolProperty(name="Decal Map", default=False)
    useToonDiffuse : BoolProperty(name="Toon Diffuse", default=False)
    useToonGlossy : BoolProperty(name="Toon Glossy", default=False)
    useToonRim : BoolProperty(name="Toon Rim", default=False)
    useToonLight : BoolProperty(name="Toon Light", default=False)

    def draw(self, context):
        for key in ShaderGroups.keys():
            self.layout.prop(self, key)


    def run(self, context):
        from .cycles import makeCyclesTree
        ob = context.object
        if ob.active_material_index >= len(ob.data.materials):
            raise DazError("No material found")
        mat = ob.data.materials[ob.active_material_index]
        if mat is None:
            raise DazError("No active material")
        ctree = makeCyclesTree(mat)
        for key in ShaderGroups.keys():
            if getattr(self, key):
                group,gname,args = ShaderGroups[key]
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
