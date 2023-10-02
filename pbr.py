# Copyright (c) 2016-2023, Thomas Larsson
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
import math
from mathutils import Vector, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .error import *
from .utils import *
from .cycles import CyclesTree
from .tree import colorOutput

class PbrTree(CyclesTree):
    def __init__(self, pbrmat):
        CyclesTree.__init__(self, pbrmat)
        self.pbr = None
        self.type = 'PBR'
        self.translucent = None
        self.metal = 0
        self.metaltex = None


    def __repr__(self):
        return ("<Pbr %s %s %s>" % (self.owner.rna, self.nodes, self.links))


    def buildLayer(self, uvname):
        self.column = 3
        self.addNode("ShaderNodeBsdfPrincipled", col=5)
        self.cycles = self.pbr
        self.linkPBRNormal(self.pbr)
        self.column = 4
        self.buildDetail(uvname)
        self.column = 5
        useTopCoatNode = self.checkTopCoat()
        self.buildPBRNode(useTopCoatNode)
        self.postPBR = False
        self.column = 7
        if self.owner.useTranslucency:
            self.buildTranslucency(uvname)
        if self.buildMakeup():
            self.postPBR = True
        if self.buildOverlay():
            self.postPBR = True
        if self.buildFlakes():
            self.postPBR = True
        if self.prepareWeighted():
            CyclesTree.buildGlossyOrDualLobe(self)
            self.postPBR = True
        else:
            self.buildGlossyOrDualLobe()
        if self.owner.isRefractive():
            self.buildRefraction()
        if useTopCoatNode:
            self.postPBR = True
            self.buildTopCoat(uvname)
        self.buildWeighted()
        self.buildEmission()


    def linkPBRNormal(self, pbr):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], pbr.inputs["Normal"])
            if hasattr(pbr.inputs, "Clearcoat Normal"):
                self.links.new(self.bump.outputs["Normal"], pbr.inputs["Clearcoat Normal"])
        elif self.normal:
            self.links.new(self.normal.outputs["Normal"], pbr.inputs["Normal"])
            if hasattr(pbr.inputs, "Clearcoat Normal"):
                self.links.new(self.normal.outputs["Normal"], pbr.inputs["Clearcoat Normal"])


    def linkTranslucency(self, trans):
        fac,factex,texslot = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0)
        self.mixWithActive(fac, factex, texslot, trans)
        if self.metal:
            self.addColumn()
            mix = self.addNode("ShaderNodeMixShader")
            self.linkScalar(self.metaltex, mix, self.metal, 0)
            self.links.new(trans.outputs["BSDF"], mix.inputs[1])
            self.links.new(self.pbr.outputs["BSDF"], mix.inputs[2])
            self.cycles = mix

        #effect = self.getValue(["Base Color Effect"], 0)
        #tint = self.getColor(["SSS Reflectance Tint"], WHITE)
        #self.buildColorEffect(effect, self.diffuseColor, self.diffuseTex, tint, fac, factex, self.pbr, colorslot="Base Color")
        self.replaceSlot(self.pbr, "Subsurface", 0.0)
        self.replaceSlot(self.pbr, "Subsurface Color", (1,1,1,1))
        self.replaceSlot(self.pbr, "Subsurface Radius", (0,0,0))


    def getShellGroup(self, shmat, push):
        from .cgroup import OpaqueShellPbrGroup, RefractiveShellPbrGroup
        if shmat.isRefractive():
            return RefractiveShellPbrGroup(push)
        else:
            return OpaqueShellPbrGroup(push)

    #-------------------------------------------------------------
    #   Cutout
    #-------------------------------------------------------------

    def buildCutout(self):
        if self.pbr and "Alpha" in self.pbr.inputs.keys() and not self.postPBR:
            alpha,tex,texslot = self.getColorTex("getChannelCutoutOpacity", "NONE", 1)
            if alpha < 1 or tex:
                self.owner.setTransSettings(None, False, WHITE, alpha)
                self.useCutout = True
            self.linkScalar(tex, self.pbr, alpha, "Alpha", texslot=texslot)
        else:
            CyclesTree.buildCutout(self)

    #-------------------------------------------------------------
    #   Emission
    #-------------------------------------------------------------

    def buildEmission(self):
        if not GS.useEmission:
            return
        elif self.pbr and "Emission" in self.pbr.inputs.keys() and not self.postPBR:
            color = self.getColor("getChannelEmissionColor", BLACK)
            if not isBlack(color):
                self.addEmitColor(self.pbr, "Emission")
                if "Emission Strength" in self.pbr.inputs.keys():
                    socket = self.pbr.inputs["Emission Strength"]
                    strength = self.getLuminance(socket)
                    socket.default_value = strength
        else:
            CyclesTree.buildEmission(self)
            self.postPBR = True

    #-------------------------------------------------------------
    #   PBR Node
    #-------------------------------------------------------------

    def buildPBRNode(self, useTopCoatNode):
        self.buildBaseSubsurface()
        self.buildMetallic()
        useTex = not (self.owner.basemix == 0 and self.pureMetal)
        self.buildSpecular(useTex)
        anisotropy = self.buildAnisotropy()
        self.buildRoughness(anisotropy, useTex)
        if not useTopCoatNode:
            self.addClearCoat(useTex)
        self.buildSheen()

    #-------------------------------------------------------------
    #   Base and Subsurface
    #-------------------------------------------------------------

    def buildBaseSubsurface(self):
        from .cycles import findTextureNode
        if not self.isEnabled("Diffuse"):
            color = WHITE
            tex = None
        else:
            color,tex = self.getDiffuseColor()
        self.diffuseInput = self.linkColor(tex, self.pbr, color, "Base Color")
        self.pbr.inputs["Subsurface"].default_value = 0

        if not (self.isEnabled("Subsurface") or not self.owner.useTranslucency):
            return
        self.column -= 1
        transwt,wttex,texslot = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
        transcolor,transtex,_ = self.getColorTex(["Translucency Color"], "COLOR", BLACK)
        if isBlack(transcolor):
            self.column += 1
            return
        self.pbr.subsurface_method = GS.getSSSMethod()
        sss,ssscolor,ssstex,sssmode = self.getSSSColor()

        if GS.useAltSss:
            self.addSubsurfaceMidnight(transwt, wttex, sss, ssstex, transcolor, transtex, texslot)
        else:
            self.addSubsurfaceColor(transwt, wttex, transcolor, transtex, texslot)

        radius,radtex = self.getSSSRadius(transcolor, ssscolor, ssstex, sssmode)
        radius,ior,aniso = self.fixSSSRadius(radius)
        self.linkColor(radtex, self.pbr, radius, "Subsurface Radius")
        if bpy.app.version >= (3,0,0):
            self.pbr.inputs["Subsurface IOR"].default_value = ior
            self.pbr.inputs["Subsurface Anisotropy"].default_value = aniso
        self.column += 1
        self.endSSS()


    def addSubsurfaceColor(self, transwt, wttex, transcolor, transtex, texslot):
        gamma = self.addNode("ShaderNodeGamma", size=7)
        gamma.inputs["Gamma"].default_value = 3.5
        self.linkColor(transtex, gamma, transcolor, "Color")
        self.links.new(gamma.outputs["Color"], self.pbr.inputs["Subsurface Color"])
        self.linkScalar(wttex, self.pbr, transwt, "Subsurface", texslot=texslot)


    def addSubsurfaceMidnight(self, transwt, wttex, sss, ssstex, transcolor, transtex, texslot):
        from .cgroup import AltSSSGroup
        fix = self.addGroup(AltSSSGroup, "DAZ Alt SSS")
        self.linkScalar(ssstex, fix, sss, "SSS Amount")
        fix.inputs["Diffuse Color"].default_value[0:3] = self.diffuseColor
        if self.diffuseInput:
            self.links.new(colorOutput(self.diffuseInput), fix.inputs["Diffuse Color"])
        self.linkColor(transtex, fix, transcolor, "Translucent Color")
        self.linkScalar(wttex, fix, transwt, "Translucency Weight", texslot=texslot)
        self.links.new(fix.outputs["Base Color"], self.pbr.inputs["Base Color"])
        self.links.new(fix.outputs["Subsurface Color"], self.pbr.inputs["Subsurface Color"])
        self.links.new(fix.outputs["Subsurface"], self.pbr.inputs["Subsurface"])

    #-------------------------------------------------------------
    #   Metallic
    #-------------------------------------------------------------

    def buildMetallic(self):
        if self.isEnabled("Metallicity"):
            self.metal,self.metaltex,_ = self.getColorTex(["Metallic Weight"], "NONE", 0.0)
            self.linkScalar(self.metaltex, self.pbr, self.metal, "Metallic")
            self.pureMetal = (self.metal == 1 and self.metaltex is None)

    #-------------------------------------------------------------
    #   Specular
    #-------------------------------------------------------------

    def buildSpecular(self, useTex):
        # Specular
        factor = value = 0.0
        tex = None
        if self.owner.shader == 'UBER_IRAY':
            strength,strtex,texslot = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            if self.owner.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl,reftex,_ = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                color,coltex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
                if reftex and coltex:
                    reftex = self.mixTexs('MULTIPLY', coltex, reftex)
                elif coltex:
                    reftex = coltex
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 1.25 * refl * strength
                value = factor * averageColor(color)
            elif self.owner.basemix == 1:  # Specular/Glossiness
                # principled specular = iray glossy specular * iray glossy layered weight * 16
                color,reftex,_ = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, True, useTex)
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 16 * strength
                value = factor * averageColor(color)
        elif self.owner.shader == 'PBRSKIN':
            if self.isEnabled("Dual Lobe Specular"):
                value,tex,texslot = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 1.0, False)
                factor = value
        else:
            strength,strtex,texslot = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            color,coltex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
            tex = self.mixTexs('MULTIPLY', strtex, coltex)
            value = factor = strength * averageColor(color)

        self.pbr.inputs["Specular"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(factor), tex)
            if tex:
                self.links.new(colorOutput(tex), self.pbr.inputs["Specular"])

    #-------------------------------------------------------------
    #   Anisotropy
    #-------------------------------------------------------------

    def buildAnisotropy(self):
        anisotropy,tex,_ = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        if anisotropy > 0:
            self.linkScalar(tex, self.pbr, anisotropy, "Anisotropic")
            anirot,tex,_ = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 0.75 - anirot
            self.linkScalar(tex, self.pbr, value, "Anisotropic Rotation")
        return anisotropy

    #-------------------------------------------------------------
    #   Roughness
    #-------------------------------------------------------------

    def buildRoughness(self, anisotropy, useTex):
        if self.pureMetal:
            self.replaceSlot(self.pbr, "Specular", 0.5)
            self.replaceSlot(self.pbr, "Subsurface", 0.0)
            self.replaceSlot(self.pbr, "Subsurface Color", (1,1,1,1))
            self.replaceSlot(self.pbr, "Subsurface Radius", (0,0,0))
        if self.owner.shader == 'PBRSKIN':
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", 0.0)
            if self.isEnabled("Dual Lobe Specular"):
                rough1,rough2,roughtex,ratio = self.getDualRoughness(0.0)
                roughness = rough1*(1-ratio) + rough2*ratio
                if self.isEnabled("Detail"):
                    roughness *= self.detrough
                    roughtex = self.multiplyTexs(self.detroughtex, roughtex)
                self.linkScalar(roughtex, self.pbr, roughness, "Roughness")
            else:
                self.replaceSlot(self.pbr, "Roughness", 0.0)
        else:
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", 1.0)
            channel,value,roughness,invert = self.owner.getGlossyRoughness(0.5)
            roughness *= (1 + anisotropy)
            self.addSlot(channel, self.pbr, "Roughness", roughness, value, invert)

    #-------------------------------------------------------------
    #   Clearcoat
    #-------------------------------------------------------------

    def addClearCoat(self, useTex):
        if self.isEnabled("Top Coat"):
            top,toptex,texslot = self.getColorTex(["Top Coat Weight"], "NONE", 1.0, False, isMask=True)
            rough,roughtex,_ = self.getColorTex(["Top Coat Roughness"], "NONE", 1.45)
            self.linkScalar(roughtex, self.pbr, rough, "Clearcoat Roughness")
        else:
            top,toptex = 0.0,None
        if self.owner.shader == 'UBER_IRAY':
            if self.owner.basemix == 0:    # Metallic/Roughness
                refl,reftex,_ = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                tex = self.mixTexs('MULTIPLY', toptex, reftex)
                value = 1.25 * refl * top
            elif self.owner.basemix == 1:  # Specular/Glossiness
                tex = toptex
                value = top
            elif self.owner.basemix == 2:  # Weighted
                tex = None
                value = 0.0
        else:
            tex = toptex
            value = top
        self.pbr.inputs["Clearcoat"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(value), tex)
            if tex:
                self.links.new(colorOutput(tex), self.pbr.inputs["Clearcoat"])

    #-------------------------------------------------------------
    #   Sheen
    #-------------------------------------------------------------

    def buildSheen(self):
        if self.isEnabled("Velvet"):
            velvet,tex,texslot = self.getColorTex(["Velvet Strength"], "NONE", 0.0)
            self.linkScalar(tex, self.pbr, velvet, "Sheen")

    #-------------------------------------------------------------
    #   Glossy or Dual lobe
    #-------------------------------------------------------------

    def buildGlossyOrDualLobe(self):
        if LS.materialMethod == 'SINGLE_PRINCIPLED':
            return
        elif self.owner.basemix == 2:
            CyclesTree.buildGlossyOrDualLobe(self)
        elif self.isEnabled("Dual Lobe Specular"):
            dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
            if dualLobeWeight > 0:
                self.buildDualLobe()
                self.replaceSlot(self.pbr, "Specular", 0)
                self.postPBR = True

    #-------------------------------------------------------------
    #   Refraction
    #-------------------------------------------------------------

    def buildRefraction(self):
        if not self.isEnabled("Transmission"):
            return 0, None
        if LS.materialMethod == 'SINGLE_PRINCIPLED' or self.owner.isPureRefractive():
            col = self.column
            self.column = 5
            weight,wttex,texslot = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0, isMask=True)
            if weight > 0:
                self.linkScalar(wttex, self.pbr, weight, "Transmission", texslot=texslot)
                self.setRefractivePrincipled()
            else:
                self.column = col
            return weight,wttex
        else:
            self.postPBR = True
            return CyclesTree.buildRefraction(self)


    def setRefractivePrincipled(self):
        pbr = self.cycles = self.pbr
        color,coltex,roughness,roughtex = self.getRefractionColor()
        ior,iortex,_ = self.getColorTex("getChannelIOR", "NONE", 1.45)
        self.postPBR = True

        if self.owner.isThinWall:
            # if thin walled is on then there's no volume
            # and we use the clearcoat channel for reflections
            #  principled ior = 1
            #  principled roughness = 0
            #  principled clearcoat = (iray refraction index - 1) * 10 * iray glossy layered weight
            #  principled clearcoat roughness = 0
            self.owner.setTransSettings(True, False, color, 0.1)
            self.replaceSlot(pbr, "IOR", 1.0)
            self.replaceSlot(pbr, "Roughness", 0.0)
            strength,strtex,texslot = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False, isMask=True)
            clearcoat = (ior-1)*10*strength
            self.removeLink(pbr, "Clearcoat")
            self.linkScalar(strtex, pbr, clearcoat, "Clearcoat", texslot=texslot)
            self.replaceSlot(pbr, "Clearcoat Roughness", 0)
            if LS.materialMethod == 'EXTENDED_PRINCIPLED':
                from .cgroup import RayClipGroup
                clip = self.addGroup(RayClipGroup, "DAZ Ray Clip", col=6)
                self.links.new(pbr.outputs["BSDF"], clip.inputs["Shader"])
                self.linkColor(coltex, clip, color, "Color")
                self.cycles = clip

        elif self.owner.isVolume():
            self.owner.setTransSettings(True, False, color, 0.1)
            self.replaceSlot(pbr, "Metallic", 0)
            self.replaceSlot(pbr, "Specular", 0)
            self.replaceSlot(pbr, "IOR", 1.0)
            self.replaceSlot(pbr, "Roughness", 0.0)

        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness
            self.owner.setTransSettings(True, False, color, 0.2)
            transcolor,transtex,_ = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
            dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
            if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
                coltex = self.mixTexs('MULTIPLY', coltex, transtex)
                color = self.compProd(color, transcolor)
            self.replaceSlot(pbr, "Metallic", 0)
            self.replaceSlot(pbr, "Specular", 0.5)
            self.removeLink(pbr, "IOR")
            self.linkScalar(iortex, pbr, ior, "IOR")
            self.removeLink(pbr, "Roughness")
            self.setRoughness(pbr, "Roughness", roughness, roughtex, square=False)

        self.removeLink(pbr, "Base Color")
        self.linkColor(coltex, pbr, color, "Base Color")
        self.replaceSlot(pbr, "Subsurface", 0)
        self.removeLink(pbr, "Subsurface Color")
        pbr.inputs["Subsurface Color"].default_value[0:3] = WHITE
        if self.getValue(["Share Glossy Inputs"], False):
            self.replaceSlot(pbr, "Specular Tint", 1.0)
        self.addColumn()

    #-------------------------------------------------------------
    #   Utilities
    #-------------------------------------------------------------

    def mixShaders(self, weight, wttex, node1, node2):
        mix = self.addNode("ShaderNodeMixShader", size=5)
        mix.inputs[0].default_value = weight
        if wttex:
            self.links.new(colorOutput(wttex), mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[1])
        self.links.new(node2.outputs[0], mix.inputs[2])
        return mix


    def setPBRValue(self, slot, value, default, maxval=0):
        if isinstance(default, Vector):
            if isinstance(value, float) or isinstance(value, int):
                value = Vector((value,value,value))
            self.pbr.inputs[slot].default_value[0:3] = value
        else:
            value = averageColor(value)
            if maxval and value > maxval:
                value = maxval
            self.pbr.inputs[slot].default_value = value

