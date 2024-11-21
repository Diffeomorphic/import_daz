# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .material import WHITE, GREY, BLACK, isWhite, isBlack
from .cycles import CyclesMaterial, CyclesTree

#------------------------------------------------------------------------
#   Materials
#------------------------------------------------------------------------

def buildHairMaterial(mname, color, img, context, force=False):
    color = list(color[0:3])
    hmat = HairMaterial(mname, color, img)
    hmat.force = force
    hmat.build(context, color, img)
    return hmat.rna


class HairMaterial(CyclesMaterial):

    def __init__(self, name, color, img):
        CyclesMaterial.__init__(self, name)
        self.name = name
        self.color = color
        self.image = img


    def guessColor(self):
        if self.rna:
            self.rna.diffuse_color = self.color


    def build(self, context, color, img):
        from .material import Material
        if not Material.build(self, context):
            return
        self.tree = getHairTree(self, color, img)
        self.tree.build()
        self.rna.diffuse_color[0:3] = self.color


def getHairTree(dmat, color=BLACK, img=None):
    #print("Creating %s hair material" % LS.hairMaterialMethod)
    if LS.hairMaterialMethod == 'HAIR_PRINCIPLED':
        return HairPBRTree(dmat, color, img)
    elif LS.hairMaterialMethod == 'PRINCIPLED':
        return HairEeveeTree(dmat, color, img)
    else:
        return HairBSDFTree(dmat, color, img)

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat, color, img):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = color
        self.image = img
        self.root = Vector(color)
        self.tip = Vector(color)
        self.roottex = None
        self.tiptex = None


    def build(self):
        self.makeTree()
        self.buildLayer("")


    def initLayer(self):
        self.column = 4
        self.active = None
        self.buildBump()


    def addTexco(self, slot):
        CyclesTree.addTexco(self, slot)
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        #self.texco = self.info.outputs["Intercept"]


    def buildOutput(self):
        self.addColumn()
        output = self.addNode('ShaderNodeOutputMaterial')
        self.links.new(self.active.outputs[0], output.inputs['Surface'])


    def buildBump(self):
        strength = self.getValue(["Bump Strength"], 1)
        if False and strength:
            bump = self.addNode("ShaderNodeBump", col=2)
            bump.inputs["Strength"].default_value = strength
            bump.inputs["Distance"].default_value = 0.1 * GS.scale
            bump.inputs["Height"].default_value = 1
            self.normal = bump


    def linkTangent(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Tangent"])


    def linkBumpNormal(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Normal"])


    def addRamp(self, node, label, root, tip, endpos=1, slot="Color"):
        if self.image:
            root = tip = WHITE
        ramp = self.addNode('ShaderNodeValToRGB', col=self.column-2)
        ramp.label = label
        self.links.new(self.info.outputs["Intercept"], ramp.inputs['Fac'])
        ramp.color_ramp.interpolation = 'LINEAR'
        colramp = ramp.color_ramp
        elt = colramp.elements[0]
        elt.position = 0
        if len(root) == 3:
            elt.color = list(root) + [1]
        else:
            elt.color = root
        elt = colramp.elements[1]
        elt.position = endpos
        if len(tip) == 3:
            elt.color = list(tip) + [0]
        else:
            elt.color = tip
        if node:
            node.inputs[slot].default_value[0:3] == root
        if self.image:
            xyz = self.addNode("ShaderNodeCombineXYZ", col = self.column-3)
            xyz.inputs[0].default_value = 0.5
            xyz.inputs[1].default_value = 0.5
            xyz.inputs[2].default_value = 0.5
            tex = self.addNode("ShaderNodeTexImage", col=self.column-2, size=2)
            tex.image = self.image
            tex.hide = True
            self.links.new(xyz.outputs["Vector"], tex.inputs["Vector"])
            mult,a,b,socket = self.addMixRgbNode('MULTIPLY', self.column-1, size=12)
            mult.inputs[0].default_value = 1
            self.links.new(ramp.outputs["Color"], a)
            self.links.new(tex.outputs["Color"], b)
        else:
            socket = ramp.outputs["Color"]
        return ramp,socket


    def readColor(self, factor):
        root,self.roottex,_ = self.getColorTex(["Hair Root Color"], "COLOR", self.color, useFactor=False)
        tip,self.tiptex,_ = self.getColorTex(["Hair Tip Color"], "COLOR", self.color, useFactor=False)
        self.owner.rna.diffuse_color[0:3] = root
        self.root = factor * Vector(root)
        self.tip = factor * Vector(tip)


    def linkRamp(self, ramp, socket, texs, node, slot):
        out = socket
        for tex in texs:
            if tex:
                mix,a,b,out = self.addMixRgbNode('MULTIPLY', col=self.column-1)
                mix.inputs[0].default_value = 1.0
                self.links.new(tex.outputs[0], a)
                self.links.new(ramp.outputs[0], b)
                break
        self.links.new(out, node.inputs[slot])
        return out


    def setRoughness(self, diffuse, rough):
        diffuse.inputs["Roughness"].default_value = rough


    def mixSockets(self, socket1, socket2, weight):
        mix = self.addNode('ShaderNodeMixShader')
        mix.inputs[0].default_value = weight
        self.links.new(socket1, mix.inputs[1])
        self.links.new(socket2, mix.inputs[2])
        return mix


    def mixShaders(self, node1, node2, weight):
        return self.mixSockets(node1.outputs[0], node2.outputs[0], weight)


    def addShaders(self, node1, node2):
        add = self.addNode('ShaderNodeAddShader')
        self.links.new(node1.outputs[0], add.inputs[0])
        self.links.new(node2.outputs[0], add.inputs[1])
        return add

#-------------------------------------------------------------
#   Hair tree BSDF
#-------------------------------------------------------------

class HairBSDFTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.5)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        self.addColumn()
        if trans and refl:
            #weight = self.getValue(["Highlight Weight"], 0.11)
            weight = self.getValue(["Glossy Layer Weight"], 0.5)
            self.active = self.mixShaders(trans, refl, weight)
        #self.buildAnisotropic()
        self.buildCutout()
        self.buildOutput()


    def buildTransmission(self):
        root,roottex,_ = self.getColorTex(["Root Transmission Color"], "COLOR", self.color, useFactor=False)
        tip,tiptex,_ = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color, useFactor=False)
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 1
        trans.inputs["RoughnessV"].default_value = 1
        ramp,socket = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, socket, [roottex, tiptex], trans, "Color")
        #self.linkTangent(trans)
        self.active = trans
        return trans


    def buildHighlight(self):
        refl = self.addNode('ShaderNodeBsdfHair')
        refl.component = 'Reflection'
        refl.inputs['Offset'].default_value = 0
        refl.inputs["RoughnessU"].default_value = 0.02
        refl.inputs["RoughnessV"].default_value = 1.0
        ramp,socket = self.addRamp(refl, "Reflection", self.root, self.tip)
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], refl, "Color")
        self.active = refl
        return refl


    def buildAnisotropic(self):
        # Anisotropic
        aniso = self.getValue(["Anisotropy"], 0)
        if aniso:
            if aniso > 0.2:
                aniso = 0.2
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.rootramp.outputs[0], node.inputs["Color"])
            node.inputs["Anisotropy"].default_value = aniso
            arots = self.getValue(["Anisotropy Rotations"], 0)
            node.inputs["Rotation"].default_value = arots
            self.linkTangent(node)
            self.linkBumpNormal(node)
            self.addColumn()
            self.active = self.addShaders(self.active, node)


    def buildCutout(self):
        # Cutout
        alpha = self.getValue(["Cutout Opacity"], 1)
        if alpha < 1:
            transp = self.addNode("ShaderNodeBsdfTransparent")
            transp.inputs["Color"].default_value[0:3] = WHITE
            self.addColumn()
            self.active = self.mixShaders(transp, self.active, alpha)
            self.owner.setTransSettings(False, False, WHITE, alpha)

#-------------------------------------------------------------
#   Hair tree Principled
#-------------------------------------------------------------

class HairPBRTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfHairPrincipled")
        ramp,socket = self.addRamp(pbr, "Color", self.root, self.tip)
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], pbr, "Color")
        pbr.inputs["Roughness"].default_value = 0.2
        pbr.inputs["Radial Roughness"].default_value = 0.8
        pbr.inputs["IOR"].default_value = 1.1
        self.buildOutput()

#-------------------------------------------------------------
#   Hair tree Eevee
#-------------------------------------------------------------

class HairEeveeTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfPrincipled")
        ramp,socket = self.addRamp(pbr, "Color", self.root, self.tip, slot="Base Color")
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], pbr, "Base Color")
        pbr.inputs["Metallic"].default_value = 0.9
        pbr.inputs["Roughness"].default_value = 0.2
        self.buildOutput()
