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
import math
from mathutils import Vector, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .error import *
from .utils import *
from .cycles import CyclesTree

class PbrTree(CyclesTree):
    def __init__(self, pbrmat):
        CyclesTree.__init__(self, pbrmat)
        self.pbr = None
        self.type = 'PBR'


    def __repr__(self):
        return ("<Pbr %s %s %s>" % (self.material.rna, self.nodes, self.links))


    def buildLayer(self, uvname):
        self.column = 4
        self.pbr = self.addNode("ShaderNodeBsdfPrincipled")
        self.ycoords[self.column] -= 500
        self.cycles = self.eevee = self.pbr
        self.buildNormal(uvname)
        self.buildBump()
        self.buildDetail(uvname)
        self.buildPBRNode()
        self.linkPBRNormal(self.pbr)
        self.postPBR = False
        if self.buildMakeup():
            self.postPBR = True
        if self.buildOverlay():
            self.postPBR = True
        if self.prepareWeighted():
            self.postPBR = True
            CyclesTree.buildGlossyOrDualLobe(self)
            self.buildTopCoat()
        else:
            self.buildGlossyOrDualLobe()
        if self.material.isRefractive():
            self.buildRefraction()
        else:
            self.buildEmission()
        self.buildWeighted()


    def linkPBRNormal(self, pbr):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], pbr.inputs["Normal"])
            self.links.new(self.bump.outputs["Normal"], pbr.inputs["Clearcoat Normal"])
        elif self.normal:
            self.links.new(self.normal.outputs["Normal"], pbr.inputs["Normal"])
            self.links.new(self.normal.outputs["Normal"], pbr.inputs["Clearcoat Normal"])


    def getShellGroup(self, shmat, push):
        from .cgroup import OpaqueShellPbrGroup, RefractiveShellPbrGroup
        if shmat.isRefractive():
            return RefractiveShellPbrGroup(push)
        else:
            return OpaqueShellPbrGroup(push)


    def buildCutout(self):
        if self.pbr and "Alpha" in self.pbr.inputs.keys() and not self.postPBR:
            alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1)
            if alpha < 1 or tex:
                self.material.setTransSettings(False, False, WHITE, alpha)
                self.useCutout = True
            self.pbr.inputs["Alpha"].default_value = alpha
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Alpha"])
        else:
            CyclesTree.buildCutout(self)


    def buildVolume(self):
        pass


    def buildEmission(self):
        if not GS.useEmission:
            return
        elif self.pbr and "Emission" in self.pbr.inputs.keys():
            color = self.getColor("getChannelEmissionColor", BLACK)
            if not isBlack(color):
                self.addEmitColor(self.pbr, "Emission")
        else:
            CyclesTree.buildEmission(self)
            self.postPBR = True


    def buildPBRNode(self):
        # Basic
        if self.isEnabled("Diffuse"):
            color,tex = self.getDiffuseColor()
            self.diffuseColor = color
            self.diffuseTex = tex
            self.linkColor(tex, self.pbr, color, "Base Color")
        else:
            self.diffuseColor = WHITE
            self.diffuseTex = None

        # Metallic Weight
        if self.isEnabled("Metallicity"):
            metallicity,tex = self.getColorTex(["Metallic Weight"], "NONE", 0.0)
            self.linkScalar(tex, self.pbr, metallicity, "Metallic")
            self.pureMetal = (metallicity == 1 and tex is None)
        else:
            metallicity = 0
        useTex = not (self.material.basemix == 0 and self.pureMetal)

        # Subsurface scattering
        self.buildSSS()

        # Anisotropic
        anisotropy,tex = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        if anisotropy > 0:
            self.linkScalar(tex, self.pbr, anisotropy, "Anisotropic")
            anirot,tex = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 0.75 - anirot
            self.linkScalar(tex, self.pbr, value, "Anisotropic Rotation")

        # Specular
        strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        if self.material.shader == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl,reftex = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                color,coltex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
                if reftex and coltex:
                    reftex = self.mixTexs('MULTIPLY', coltex, reftex)
                elif coltex:
                    reftex = coltex
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 1.25 * refl * strength
                value = factor * averageColor(color)
            elif self.material.basemix == 1:  # Specular/Glossiness
                # principled specular = iray glossy specular * iray glossy layered weight * 16
                color,reftex = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, True, useTex)
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 16 * strength
                value = factor * averageColor(color)
            elif self.material.basemix == 2:  # Weighted
                value = 0.0
                tex = None
        else:
            color,coltex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
            tex = self.mixTexs('MULTIPLY', strtex, coltex)
            value = factor = strength * averageColor(color)

        self.pbr.inputs["Specular"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(factor), tex)
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Specular"])

        # Roughness
        if self.pureMetal:
            self.replaceSlot(self.pbr, "Specular", 0.5)
            self.replaceSlot(self.pbr, "Subsurface", 0.0)
            self.replaceSlot(self.pbr, "Subsurface Color", (1,1,1,1))
            self.replaceSlot(self.pbr, "Subsurface Radius", (0,0,0))
        if self.material.shader == 'PBRSKIN':
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", 0.0)
            rough1,rough2,roughtex,ratio = self.getDualRoughness(0.0)
            roughness = rough1*(1-ratio) + rough2*ratio
            self.linkScalar(roughtex, self.pbr, roughness, "Roughness")
        else:
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", 1.0)
            channel,value,roughness,invert = self.material.getGlossyRoughness(0.5)
            roughness *= (1 + anisotropy)
            self.addSlot(channel, self.pbr, "Roughness", roughness, value, invert)

        # Clearcoat
        top,toptex = self.getColorTex(["Top Coat Weight"], "NONE", 1.0, False, isMask=True)
        if self.material.shader == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                refl,reftex = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                tex = self.mixTexs('MULTIPLY', toptex, reftex)
                value = 1.25 * refl * top
            elif self.material.basemix == 1:  # Specular/Glossiness
                tex = toptex
                value = top
            elif self.material.basemix == 2:  # Weighted
                tex = None
                value = 0.0
        else:
            tex = toptex
            value = top
        self.pbr.inputs["Clearcoat"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(value), tex)
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Clearcoat"])

        rough,tex = self.getColorTex(["Top Coat Roughness"], "NONE", 1.45)
        self.linkScalar(tex, self.pbr, rough, "Clearcoat Roughness")

        # Sheen
        if self.isEnabled("Velvet"):
            velvet,tex = self.getColorTex(["Velvet Strength"], "NONE", 0.0)
            self.linkScalar(tex, self.pbr, velvet, "Sheen")


    def buildSSS(self):
        if not self.isEnabled("Subsurface"):
            return
        if not self.checkTranslucency():
            return
        wt,wttex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
        if wt == 0:
            return
        color,coltex = self.getTranslucentColor()
        if isBlack(color):
            return
        # a 3.5 gamma for the translucency texture is used to avoid the "white skin" effect
        gamma = self.addNode("ShaderNodeGamma", col=3)
        gamma.inputs["Gamma"].default_value = 3.5
        ssscolor,ssstex,sssmode = self.getSSSColor()
        radius,radtex = self.getSSSRadius(color, ssscolor, ssstex, sssmode)
        radius,ior,aniso = self.fixSSSRadius(radius)
        self.linkColor(coltex, gamma, color, "Color")
        self.pbr.subsurface_method = GS.getSSSMethod()
        self.links.new(gamma.outputs[0], self.pbr.inputs["Subsurface Color"])
        self.linkScalar(wttex, self.pbr, wt, "Subsurface")
        self.linkColor(radtex, self.pbr, radius, "Subsurface Radius")
        if bpy.app.version >= (3,0,0):
            self.pbr.inputs["Subsurface IOR"].default_value = ior
            self.pbr.inputs["Subsurface Anisotropy"].default_value = aniso
        self.endSSS()


    def getRefractionWeight(self):
        channel = self.material.getChannelRefractionWeight()
        if channel:
            return self.getColorTex("getChannelRefractionWeight", "NONE", 0.0, isMask=True)
        channel = self.material.getChannelOpacity()
        if channel:
            value,tex = self.getColorTex("getChannelOpacity", "NONE", 1.0)
            invtex = self.fixTex(tex, value, True)
            return 1-value, invtex
        return 1,None


    def buildGlossyOrDualLobe(self):
        if self.material.basemix == 2:
            CyclesTree.buildGlossyOrDualLobe(self)
        else:
            dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
            if dualLobeWeight > 0:
                self.buildDualLobe()
                self.replaceSlot(self.pbr, "Specular", 0)
                self.postPBR = True


    def buildRefraction(self):
        if GS.refractiveMethod == 'BSDF':
            data = CyclesTree.buildRefraction(self)
            self.postPBR = True
            return data

        weight,wttex = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0, isMask=True)
        if weight == 0:
            return weight,wttex
        color,coltex,roughness,roughtex = self.getRefractionColor()
        ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)

        if GS.refractiveMethod == 'SECOND':
            if (weight < 1 or
                wttex or
                self.inShell or
                self.material.basemix == 2):
                self.column += 1
                pbr = pbr2 = self.addNode("ShaderNodeBsdfPrincipled")
                self.ycoords[self.column] -= 500
                self.linkPBRNormal(pbr2)
                pbr2.inputs["Transmission"].default_value = 1.0
            else:
                pbr = self.pbr
                pbr2 = None
                self.replaceSlot(pbr, "Transmission", weight)

            if self.material.isThinWall():
                from .cgroup import RayClipGroup
                self.column += 1
                clip = self.addGroup(RayClipGroup, "DAZ Ray Clip")
                self.links.new(pbr.outputs[0], clip.inputs["Shader"])
                self.linkColor(coltex, clip, color, "Color")
                self.cycles = self.eevee = clip
            else:
                clip = pbr

            if pbr2:
                if self.inShell:
                    self.replaceSlot(pbr, "Transmission", 1.0)
                    self.cycles = self.eevee = clip
                elif self.material.basemix == 2:
                    self.cycles = self.eevee = clip
                else:
                    self.column += 1
                    mix = self.mixShaders(weight, wttex, self.pbr, clip)
                    self.cycles = self.eevee = mix
            self.postPBR = True
        else:
            pbr = self.pbr
            self.replaceSlot(pbr, "Transmission", weight)

        if self.material.isThinWall():
            # if thin walled is on then there's no volume
            # and we use the clearcoat channel for reflections
            #  principled ior = 1
            #  principled roughness = 0
            #  principled clearcoat = (iray refraction index - 1) * 10 * iray glossy layered weight
            #  principled clearcoat roughness = 0
            self.material.setTransSettings(True, False, color, 0.1)
            self.replaceSlot(pbr, "IOR", 1.0)
            self.replaceSlot(pbr, "Roughness", 0.0)
            strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False, isMask=True)
            clearcoat = (ior-1)*10*strength
            self.removeLink(pbr, "Clearcoat")
            self.linkScalar(strtex, pbr, clearcoat, "Clearcoat")
            self.replaceSlot(pbr, "Clearcoat Roughness", 0)

        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness
            self.material.setTransSettings(True, False, color, 0.2)
            transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
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
        self.pbr = pbr
        return weight,wttex


    def mixShaders(self, weight, wttex, node1, node2):
        mix = self.addNode("ShaderNodeMixShader")
        mix.inputs[0].default_value = weight
        if wttex:
            self.links.new(wttex.outputs[0], mix.inputs[0])
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

