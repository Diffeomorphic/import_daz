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

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE, BLACK
from .utils import *
from .error import *

# ---------------------------------------------------------------------
#   CyclesGroup
# ---------------------------------------------------------------------

class MaterialGroup:
    def __init__(self):
        self.insockets = []
        self.outsockets = []


    def create(self, node, name, parent, ncols):
        self.group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        node.name = name
        node.node_tree = self.group
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode("NodeGroupInput", 0)
        self.outputs = self.addNode("NodeGroupOutput", ncols)
        self.parent = parent
        self.ncols = ncols


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


class CyclesGroup(MaterialGroup, CyclesTree):
    def create(self, node, name, parent, ncols):
        CyclesTree.__init__(self, parent.material)
        MaterialGroup.create(self, node, name, parent, ncols)

    def __repr__(self):
        return ("<NodeGroup %s>" % self.group)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(MaterialGroup):

    def __init__(self, push):
        MaterialGroup.__init__(self)
        self.push = push
        self.insockets += ["Influence", "Cycles", "Eevee", "UV", "Displacement"]
        self.outsockets += ["Cycles", "Eevee", "Displacement"]


    def create(self, node, name, parent):
        MaterialGroup.create(self, node, name, parent, 10)
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.inputs.new("NodeSocketFloat", "Displacement")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketFloat", "Displacement")


    def addNodes(self, args):
        shmat,uvname = args
        shmat.rna = self.parent.material.rna
        self.material = shmat
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer(uvname)
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        mult = self.addNode("ShaderNodeMath", 6)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Influence"], mult.inputs[0])
        self.linkScalar(tex, mult, alpha, 1)
        transp = self.blacken()
        self.addOutput(mult, transp, self.getCyclesSocket(), "Cycles")
        self.addOutput(mult, transp, self.getEeveeSocket(), "Eevee")
        self.buildDisplacementNodes()
        if self.displacement:
            mult2 = self.addNode("ShaderNodeMath", 9)
            mult2.label = "Multiply Displacement"
            mult2.operation = 'MULTIPLY'
            self.links.new(mult.outputs[0], mult2.inputs[0])
            self.links.new(self.displacement, mult2.inputs[1])
            self.links.new(mult2.outputs[0], self.outputs.inputs["Displacement"])
        else:
            self.links.new(self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])


class OpaqueShellGroup(ShellGroup):
    def blacken(self):
        return None


    def addOutput(self, mult, _transp, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 8)
        mix.inputs[0].default_value = 1
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class RefractiveShellGroup(ShellGroup):
    def blacken(self):
        transp = self.addNode("ShaderNodeBsdfTransparent", 7)
        transp.inputs[0].default_value[0:3] = BLACK
        for node in self.nodes:
            if node.type == 'GROUP' and "Refraction Color" in node.inputs.keys():
                node.inputs["Refraction Color"].default_value[0:3] = BLACK
                self.removeLink(node, "Refraction Color")
            elif node.type == 'BSDF_PRINCIPLED':
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
        self.links.new(mix.outputs[0], add.inputs[0])
        self.links.new(self.inputs.outputs[slot], add.inputs[1])
        self.links.new(add.outputs[0], self.outputs.inputs[slot])


class OpaqueShellCyclesGroup(OpaqueShellGroup, CyclesTree):
    def create(self, node, name, parent):
        CyclesTree.__init__(self, parent.material)
        OpaqueShellGroup.create(self, node, name, parent)


class OpaqueShellPbrGroup(OpaqueShellGroup, PbrTree):
    def create(self, node, name, parent):
        PbrTree.__init__(self, parent.material)
        OpaqueShellGroup.create(self, node, name, parent)


class RefractiveShellCyclesGroup(RefractiveShellGroup, CyclesTree):
    def create(self, node, name, parent):
        CyclesTree.__init__(self, parent.material)
        RefractiveShellGroup.create(self, node, name, parent)


class RefractiveShellPbrGroup(RefractiveShellGroup, PbrTree):
    def create(self, node, name, parent):
        PbrTree.__init__(self, parent.material)
        RefractiveShellGroup.create(self, node, name, parent)


# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class FresnelGroup(CyclesGroup):
    exponent = 0

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["IOR", "Roughness", "Normal"]
        self.outsockets += ["Fac"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketFloat", "Fac")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 0)

        divide = self.addNode("ShaderNodeMath", 1)
        divide.operation = 'DIVIDE'
        divide.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["IOR"], divide.inputs[1])

        if self.exponent:
            power = self.addNode("ShaderNodeMath", 1)
            power.operation = 'POWER'
            self.links.new(self.inputs.outputs["Roughness"], power.inputs[0])
            power.inputs[1].default_value = self.exponent

        bump = self.addNode("ShaderNodeBump", 1)
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.links.new(self.inputs.outputs["IOR"], mix1.inputs[1])
        self.links.new(divide.outputs["Value"], mix1.inputs[2])

        mix2 = self.addNode("ShaderNodeMixRGB", 2)
        if self.exponent:
            self.links.new(power.outputs[0], mix2.inputs["Fac"])
        else:
            self.links.new(self.inputs.outputs["Roughness"], mix2.inputs["Fac"])
        self.links.new(bump.outputs[0], mix2.inputs[1])
        self.links.new(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(mix1.outputs[0], fresnel.inputs["IOR"])
        self.links.new(mix2.outputs[0], fresnel.inputs["Normal"])
        self.links.new(fresnel.outputs["Fac"], self.outputs.inputs["Fac"])


class UberFresnelGroup(FresnelGroup):
    exponent = 2


class PBRSkinFresnelGroup(FresnelGroup):
    exponent = 4

# ---------------------------------------------------------------------
#   Mix Group. Mixes Cycles and Eevee
# ---------------------------------------------------------------------

class MixGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.mix1 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix1.label = "Cycles"
        self.mix2 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix2.label = "Eevee"
        self.links.new(self.inputs.outputs["Fac"], self.mix1.inputs[0])
        self.links.new(self.inputs.outputs["Fac"], self.mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[1])
        self.links.new(self.mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.mix2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Add Group. Adds to Cycles and Eevee
# ---------------------------------------------------------------------

class AddGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.add1 = self.addNode("ShaderNodeAddShader", 2)
        self.add2 = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(self.inputs.outputs["Cycles"], self.add1.inputs[0])
        self.links.new(self.inputs.outputs["Eevee"], self.add2.inputs[0])
        self.links.new(self.add1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.add2.outputs[0], self.outputs.inputs["Eevee"])

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
        self.links.new(node.outputs[0], self.add2.inputs[1])


class OneSidedGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 1)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        mix1 = self.addNode("ShaderNodeMixShader", 2)
        mix2 = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs[0])
        self.links.new(geo.outputs["Backfacing"], mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], mix2.inputs[1])
        self.links.new(trans.outputs[0], mix1.inputs[2])
        self.links.new(trans.outputs[0], mix2.inputs[2])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Diffuse Group
# ---------------------------------------------------------------------

class DiffuseGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.links.new(diffuse.outputs[0], self.mix1.inputs[2])
        self.links.new(diffuse.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Glossy Group
# ---------------------------------------------------------------------

class GlossyGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        self.links.new(glossy.outputs[0], self.mix1.inputs[2])
        self.links.new(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Top Coat Group
# ---------------------------------------------------------------------

class TopCoatGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Bump", "Height", "Distance", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketFloat", "Bump")
        self.group.inputs.new("NodeSocketFloat", "Distance")
        self.group.inputs.new("NodeSocketFloat", "Height")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        bump = self.addNode("ShaderNodeBump", 1)
        self.links.new(self.inputs.outputs["Bump"], bump.inputs["Strength"])
        self.links.new(self.inputs.outputs["Height"], bump.inputs["Height"])
        self.links.new(self.inputs.outputs["Distance"], bump.inputs["Distance"])
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])

        glossy = self.addNode("ShaderNodeBsdfGlossy", 2)
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(bump.outputs["Normal"], glossy.inputs["Normal"])
        self.links.new(glossy.outputs[0], self.mix1.inputs[2])
        self.links.new(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------

class RefractionGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += [
            "Thin Wall",
            "Refraction Color", "Refraction Roughness", "Refraction IOR",
            "Glossy Color", "Glossy Roughness", "Fresnel IOR", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketFloat", "Thin Wall")
        self.group.inputs.new("NodeSocketColor", "Refraction Color")
        self.group.inputs.new("NodeSocketFloat", "Refraction Roughness")
        self.group.inputs.new("NodeSocketFloat", "Refraction IOR")
        self.group.inputs.new("NodeSocketFloat", "Fresnel IOR")
        self.group.inputs.new("NodeSocketColor", "Glossy Color")
        self.group.inputs.new("NodeSocketFloat", "Glossy Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        refr = self.addNode("ShaderNodeBsdfRefraction", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], refr.inputs["Color"])
        self.links.new(self.inputs.outputs["Refraction Roughness"], refr.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Refraction IOR"], refr.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refr.inputs["Normal"])

        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], trans.inputs["Color"])

        thin = self.addNode("ShaderNodeMixShader", 2)
        thin.label = "Thin Wall"
        self.links.new(self.inputs.outputs["Thin Wall"], thin.inputs["Fac"])
        self.links.new(refr.outputs[0], thin.inputs[1])
        self.links.new(trans.outputs[0], thin.inputs[2])

        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 2)
        self.links.new(self.inputs.outputs["Fresnel IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        glossy = self.addNode("ShaderNodeBsdfGlossy", 2)
        self.links.new(self.inputs.outputs["Glossy Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(thin.outputs[0], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])

        self.links.new(mix.outputs[0], self.mix1.inputs[2])
        self.links.new(mix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Fake Caustics Group
# ---------------------------------------------------------------------

class FakeCausticsGroup(MixGroup):

    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 6)


    def addNodes(self, args):
        MixGroup.addNodes(self, args)
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
        self.links.new(lightpath.outputs["Is Shadow Ray"], self.mix1.inputs[0])
        self.links.new(lightpath.outputs["Is Shadow Ray"], self.mix2.inputs[0])
        self.links.new(trans.outputs[0], self.mix1.inputs[2])
        self.links.new(trans.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Transparent Group
# ---------------------------------------------------------------------

class TransparentGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        # Flip
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[2])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[2])
        self.links.new(trans.outputs[0], self.mix1.inputs[1])
        self.links.new(trans.outputs[0], self.mix2.inputs[1])

# ---------------------------------------------------------------------
#   Translucent Group
# ---------------------------------------------------------------------

class TranslucentGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += [
            "Color", "Gamma", "Scale", "Radius",
            "Cycles Mix Factor", "Eevee Mix Factor", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Gamma")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketFloat", "Cycles Mix Factor")
        self.group.inputs.new("NodeSocketFloat", "Eevee Mix Factor")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTranslucent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        self.links.new(self.inputs.outputs["Normal"], trans.inputs["Normal"])

        gamma = self.addNode("ShaderNodeGamma", 1)
        self.links.new(self.inputs.outputs["Color"], gamma.inputs["Color"])
        self.links.new(self.inputs.outputs["Gamma"], gamma.inputs["Gamma"])

        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        sss.falloff = GS.getSSSMethod()
        self.links.new(gamma.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])

        cmix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(self.inputs.outputs["Cycles Mix Factor"], cmix.inputs[0])
        self.links.new(trans.outputs[0], cmix.inputs[1])
        self.links.new(sss.outputs[0], cmix.inputs[2])

        emix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(self.inputs.outputs["Eevee Mix Factor"], emix.inputs[0])
        self.links.new(trans.outputs[0], emix.inputs[1])
        self.links.new(sss.outputs[0], emix.inputs[2])

        self.links.new(cmix.outputs[0], self.mix1.inputs[2])
        self.links.new(emix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Makeup Group
# ---------------------------------------------------------------------

class MakeupGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.links.new(diffuse.outputs[0], self.mix1.inputs[2])
        self.links.new(diffuse.outputs[0], self.mix2.inputs[2])

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

class DualLobeGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += [
            "Fac", "Cycles", "Eevee", "Weight", "IOR",
            "Roughness 1", "Roughness 2"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketFloat", "Weight")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")



    def addNodes(self, args=None):
        fresnel1 = self.addFresnel(True, "Roughness 1")
        glossy1 = self.addGlossy("Roughness 1", self.lobe1Normal)
        cycles1 = self.mixGlossy(fresnel1, glossy1, "Cycles")
        eevee1 = self.mixGlossy(fresnel1, glossy1, "Eevee")
        fresnel2 = self.addFresnel(False, "Roughness 2")
        glossy2 = self.addGlossy("Roughness 2", self.lobe2Normal)
        cycles2 = self.mixGlossy(fresnel2, glossy2, "Cycles")
        eevee2 = self.mixGlossy(fresnel2, glossy2, "Eevee")
        self.mixOutput(cycles1, cycles2, "Cycles")
        self.mixOutput(eevee1, eevee2, "Eevee")


    def addGlossy(self, roughness, useNormal):
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Weight"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy


    def mixGlossy(self, fresnel, glossy, slot):
        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])
        return mix


    def mixOutput(self, node1, node2, slot):
        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[2])
        self.links.new(node2.outputs[0], mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class DualLobeGroupUberIray(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = False

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addGroup(UberFresnelGroup, "DAZ Fresnel Uber", 1)
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel


class DualLobeGroupPBRSkin(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = True

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addGroup(PBRSkinFresnelGroup, "DAZ Fresnel PBR", 1)
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
#   Decal Group
# ---------------------------------------------------------------------

class DecalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color", "Influence"]
        self.outsockets += ["Color", "Alpha", "Combined"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.outputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Alpha")
        self.group.outputs.new("NodeSocketColor", "Combined")


    def addNodes(self, args):
        empty,img = args

        texco = self.addNode("ShaderNodeTexCoord", 0)
        texco.object = empty

        mapping = self.addNode("ShaderNodeMapping", 1)
        mapping.vector_type = 'POINT'
        mapping.inputs["Location"].default_value = (0.5, 0.5, 0)
        self.links.new(texco.outputs["Object"], mapping.inputs["Vector"])

        tex = self.addNode("ShaderNodeTexImage", 2)
        tex.image = img
        tex.interpolation = GS.imageInterpolation
        tex.extension = 'CLIP'
        self.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])

        mult = self.addNode("ShaderNodeMath", 3)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Influence"], mult.inputs[0])
        self.links.new(tex.outputs["Alpha"], mult.inputs[1])

        mix = self.addNode("ShaderNodeMixRGB", 4)
        mix.blend_type = 'MULTIPLY'
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Color"], mix.inputs[1])
        self.links.new(tex.outputs["Color"], mix.inputs[2])

        self.links.new(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.links.new(mult.outputs[0], self.outputs.inputs["Alpha"])
        self.links.new(mix.outputs[0], self.outputs.inputs["Combined"])

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
            innode,texnode,outnode,isnew = self.addSingleTexture(2, asset, map, colorSpace)
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
        self.links.new(mix.outputs[0], self.outputs.inputs["Color"])


    def mixColor(self, map, texnode, outnode):
        def setFactor(alpha, node, slot, mix):
            if alpha != 1:
                node = self.multiplyScalarTex(alpha, node, slot, 3)
                self.links.new(node.outputs[0], mix.inputs[0])
            else:
                self.links.new(node.outputs[slot], mix.inputs[0])

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
        "useFresnel" : (FresnelGroup, "DAZ Fresnel", []),
        "useEmission" : (EmissionGroup, "DAZ Emission", []),
        "useOneSided" : (OneSidedGroup, "DAZ One-Sided", []),
        "useOverlay" : (DiffuseGroup, "DAZ Overlay", []),
        "useGlossy" : (GlossyGroup, "DAZ Glossy", []),
        "useTopCoat" : (TopCoatGroup, "DAZ Top Coat", []),
        "useRefraction" : (RefractionGroup, "DAZ Refraction", []),
        "useFakeCaustics" : (FakeCausticsGroup, "DAZ Fake Caustics", [WHITE]),
        "useTransparent" : (TransparentGroup, "DAZ Transparent", []),
        "useTranslucent" : (TranslucentGroup, "DAZ Translucent", []),
        "useRayClip" : (RayClipGroup, "DAZ Ray Clip", []),
        "useDualLobeUber" : (DualLobeGroupUberIray, "DAZ Dual Lobe Uber", []),
        "useDualLobePBR" : (DualLobeGroupPBRSkin, "DAZ Dual Lobe PBR", []),
        "useVolume" : (VolumeGroup, "DAZ Volume", []),
        "useNormal" : (NormalGroup, "DAZ Normal", ["uvname"]),
        "useDisplacement" : (DisplacementGroup, "DAZ Displacement", []),
        "useDecal" : (DecalGroup, "DAZ Decal", [None, None]),
    }

    useFresnel : BoolProperty(name="Fresnel", default=False)
    useEmission : BoolProperty(name="Emission", default=False)
    useOneSided : BoolProperty(name="One Sided", default=False)
    useOverlay : BoolProperty(name="Diffuse Overlay", default=False)
    useGlossy : BoolProperty(name="Glossy", default=False)
    useTopCoat : BoolProperty(name="Top Coat", default=False)
    useRefraction : BoolProperty(name="Refraction", default=False)
    useFakeCaustics : BoolProperty(name="Fake Caustics", default=False)
    useTransparent : BoolProperty(name="Transparent", default=False)
    useTranslucent : BoolProperty(name="Translucent", default=False)
    useSSS : BoolProperty(name="Subsurface Scattering", default=False)
    useRayClip : BoolProperty(name="Ray Clip", default=False)
    useDualLobeUber : BoolProperty(name="Dual Lobe (Uber Shader)", default=False)
    useDualLobePBR : BoolProperty(name="Dual Lobe (PBR Skin)", default=False)
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
