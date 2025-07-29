# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Vector, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .error import *
from .utils import *
from .cycles import CyclesTree, averageColor
from .tree import addGroupInput, addGroupOutput, getGroupInput, colorOutput, MixRGB

# ---------------------------------------------------------------------
#   Principled v 2
# ---------------------------------------------------------------------
#   https://projects.blender.org/blender/blender/issues/99447
#
#   PBR slots:
#   3.6                     4.0
#   Base Color              Base Color
#   Subsurface              Subsurface Weight
#   Subsurface Radius       Subsurface Radius
#   -                       Subsurface Scale
#   Subsurface Color        -
#   Subsurface IOR          -
#   Subsurface Anisotropy   -
#   Metallic                Metallic
#   Specular                Specular IOR Level
#   Specular Tint           Specular Tint
#   Roughness               Roughness
#   Anisotropic             Anisotropic
#   Anisotropic Rotation    Anisotropic Rotation
#   Sheen                   Sheen Weight
#   -                       Sheen Roughness
#   Sheen Tint              Sheen Tint
#   Clearcoat               Coat Weight
#   Clearcoat Roughness     Coat Roughness
#   -                       Coat IOR
#   -                       Coat Tint
#   IOR                     IOR
#   Transmission            Transmission Weight
#   Transmission Roughness  -
#   Emission                Emission Color
#   Emission Strength       Emission Strength
#   Alpha                   Alpha
#   Normal                  Normal
#   Clearcoat Normal        Coat Normal
#   Tangent                 Tangent
#   Weight                  Weight

if BLENDER3:
    class PbrSockets:
        SubsurfWeight = "Subsurface"
        Specular = "Specular"
        CoatWeight = "Clearcoat"
        CoatRoughness = "Clearcoat Roughness"
        CoatNormal = "Clearcoat Normal"
        SheenWeight = "Sheen"
        TransmitWeight = "Transmission"
        EmitColor = "Emission"
        TintComponents = 1

    def Tint(x):
        return x
else:
    class PbrSockets:
        SubsurfWeight = "Subsurface Weight"
        Specular = "Specular IOR Level"
        CoatWeight = "Coat Weight"
        CoatRoughness = "Coat Roughness"
        CoatNormal = "Coat Normal"
        SheenWeight = "Sheen Weight"
        TransmitWeight = "Transmission Weight"
        EmitColor = "Emission Color"
        TintComponents = 4

    def Tint(x):
        return (x,x,x,1)

PBR = PbrSockets()
# ---------------------------------------------------------------------
#   PbrTree
# ---------------------------------------------------------------------

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
        self.buildNormal(uvname)
        if LS.materialMethod != 'FBX_COMPATIBLE':
            self.buildBump(uvname)
        self.pbr = self.diffuse = self.addNode("ShaderNodeBsdfPrincipled", col=5)
        self.cycles = self.pbr
        self.linkPBRNormal(self.pbr)
        self.column = 4
        if LS.materialMethod == 'EXTENDED_PRINCIPLED':
            self.buildDetail(uvname)
        self.column = 5
        useTopCoatNode = self.checkTopCoat()
        self.column = 4
        self.buildPBRNode(useTopCoatNode, uvname)
        self.postPBR = False
        self.column = 7
        if LS.materialMethod == 'EXTENDED_PRINCIPLED':
            if self.owner.useTranslucency:
                self.buildTranslucency(uvname)
                self.postPBR = True
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
        if LS.materialMethod == 'EXTENDED_PRINCIPLED':
            if useTopCoatNode:
                self.postPBR = True
                self.buildTopCoat(uvname)
            self.buildWeighted()
        self.buildEmission()


    def linkPBRNormal(self, pbr):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], pbr.inputs["Normal"])
            if hasattr(pbr.inputs, PBR.CoatNormal):
                self.links.new(self.bump.outputs["Normal"], pbr.inputs[PBR.CoatNormal])
        elif self.normal:
            self.links.new(self.normal.outputs["Normal"], pbr.inputs["Normal"])
            if hasattr(pbr.inputs, PBR.CoatNormal):
                self.links.new(self.normal.outputs["Normal"], pbr.inputs[PBR.CoatNormal])


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
        for link in self.pbr.inputs[PBR.SubsurfWeight].links:
            self.links.new(link.from_socket, trans.inputs["Fac"])
        self.replaceSlot(self.pbr, PBR.SubsurfWeight, 0.0)
        self.thickness = None
        if BLENDER3:
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
        if (self.pbr and
            "Alpha" in self.pbr.inputs.keys() and
            not self.postPBR):
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
        elif self.pbr and PBR.EmitColor in self.pbr.inputs.keys() and not self.postPBR:
            color = self.getColor("getChannelEmissionColor", BLACK)
            if not isBlack(color):
                if LS.materialMethod == 'FBX_COMPATIBLE':
                    color,tex,_ = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
                    self.linkColor(tex, self.pbr, color, PBR.EmitColor)
                else:
                    self.addEmitColor(self.pbr, PBR.EmitColor)
                if "Emission Strength" in self.pbr.inputs.keys():
                    socket = self.pbr.inputs["Emission Strength"]
                    lum,lumtex = self.getLuminance(socket)
                    self.linkScalar(lumtex, self.pbr, lum, "Emission Strength")
        else:
            CyclesTree.buildEmission(self)
            self.postPBR = True

    #-------------------------------------------------------------
    #   PBR Node
    #-------------------------------------------------------------

    def buildPBRNode(self, useTopCoatNode, uvname):
        self.buildBaseSubsurface()
        self.buildMetallic()
        useTex = not (self.owner.basemix == 0 and self.pureMetal)
        self.buildSpecular(useTex)
        anisotropy = self.buildAnisotropy()
        self.buildRoughness(anisotropy, useTex)
        if LS.materialMethod == 'EXTENDED_PRINCIPLED' and not useTopCoatNode:
            self.addClearCoat(useTex, uvname)
        self.buildSheen()

    #-------------------------------------------------------------
    #   Base and Subsurface
    #-------------------------------------------------------------

    def buildBaseSubsurface(self):
        from .cycles import findTextureNode
        if not self.isEnabled("Diffuse"):
            color = WHITE
            tex = factex = None
            effect = None
        else:
            color,tex = self.getDiffuseColor()
            effect = self.getValue(["Base Color Effect"], 0)
            tint = self.getColor(["SSS Reflectance Tint"], WHITE)
            fac,factex = self.getFacFromTranslucency()

        self.pbr.inputs[PBR.SubsurfWeight].default_value = 0
        self.diffuseInput = tex
        if (LS.materialMethod == 'FBX_COMPATIBLE' or
            not self.isEnabled("Subsurface")):
            self.linkColor(tex, self.pbr, color, "Base Color")
            return

        transwt,wttex,texslot = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
        transcolor,transtex,_ = self.getColorTex(["Translucency Color"], "COLOR", BLACK)

        if effect:
            hasEffect,effnode = self.buildColorEffect(effect, color, tex, tint, 1-transwt, wttex, self.pbr, facslot=None, colorslot="Base Color")
        if effect and hasEffect:
            sub = self.addNode("ShaderNodeMath", 3)
            sub.operation = 'SUBTRACT'
            sub.inputs[0].default_value = 1
            self.links.new(effnode.outputs["Transmit Fac"], sub.inputs[1])
            self.links.new(sub.outputs[0], self.pbr.inputs[PBR.SubsurfWeight])
            transwt = 1
            wttex = sub
            color = WHITE
            tex = effnode
        else:
            self.linkScalar(wttex, self.pbr, transwt, PBR.SubsurfWeight)

        if self.owner.useTranslucency:
            self.linkColor(tex, self.pbr, color, "Base Color")
            return
        elif BLENDER3:
            self.linkColor(tex, self.pbr, color, "Base Color")
            if transwt > 0:
                gamma = self.addGamma(transcolor, transtex, "Gamma", 3.5)
                self.links.new(gamma.outputs["Color"], self.pbr.inputs["Subsurface Color"])
                self.thickness = 1.0
        else:
            if transwt > 0:
                gamma = self.addGamma(transcolor, transtex, "Gamma", 3.5)
                mix,a,b,out = self.addMixRgbNode('MIX')
                self.linkScalar(wttex, mix, transwt, 0)
                self.linkColor(tex, mix, color, MixRGB.Color1)
                self.links.new(gamma.outputs["Color"], b)
                self.links.new(out, self.pbr.inputs["Base Color"])
                self.thickness = 1.0
            else:
                self.linkColor(tex, self.pbr, color, "Base Color")

        self.pbr.subsurface_method = GS.sssMethod
        sss,ssscolor,ssstex,sssmode = self.getSSSColor()

        radius,radtex = self.getSSSRadius(transcolor, ssscolor, ssstex, sssmode)
        radius,ior,aniso = self.fixSSSRadius(radius)
        if not BLENDER3:
            rmax = max(radius)
            if rmax > 0:
                radius /= rmax
            self.pbr.inputs["Subsurface Scale"].default_value = rmax
            if GS.sssMethod != 'BURLEY':
                self.pbr.inputs["Subsurface Anisotropy"].default_value = aniso
            if GS.sssMethod == 'RANDOM_WALK_SKIN':
                self.pbr.inputs["Subsurface IOR"].default_value = ior
        elif GS.sssMethod != 'BURLEY' and hasattr(self.pbr.inputs, "Subsurface IOR"):
            self.pbr.inputs["Subsurface IOR"].default_value = ior
            self.pbr.inputs["Subsurface Anisotropy"].default_value = aniso
        self.linkColor(radtex, self.pbr, radius, "Subsurface Radius")
        self.column += 1
        self.endSSS()

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
        color, coltex = WHITE, None
        strength, strtex = 1.0, None
        refl, refltex = 0.5, None
        if self.owner.shader == 'UBER_IRAY':
            strength,strtex,_ = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            color,coltex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
            if self.owner.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl,refltex,_ = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                if BLENDER3:
                    refltex = self.mixTexs('MULTIPLY', strtex, refltex)
                    refl = 1.25 * refl * strength
            elif self.owner.basemix == 1:  # Specular/Glossiness
                spec,spectex,_ = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, True, useTex)
                if BLENDER3:
                    # principled specular = iray glossy specular * iray glossy layered weight * 16
                    color,coltex,_ = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, True, useTex)
                    refl = 16 * strength
                    refltex = spectex
                else:
                    refl = averageColor(spec) / 0.078
                    refltex = spectex
        elif self.owner.shader == 'PBRSKIN':
            if self.isEnabled("Dual Lobe Specular"):
                refl,refltex,_ = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 1.0, False)
        else:
            refl,refltex,_ = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            color,coltex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
        if useTex is None:
            refltex = None

        if BLENDER3:
            spec = clamp(refl*averageColor(color))
            spectex = self.mixTexs('MULTIPLY', refltex, coltex)
            self.linkScalar(spectex, self.pbr, spec, "Specular")
        else:
            self.replaceSlot(self.pbr, "IOR", 1.5)
            if strength == 0:
                refl = 0
            self.linkScalar(refltex, self.pbr, refl, "Specular IOR Level")
            color = strength*Vector(color)
            coltex = self.mixTexs('MULTIPLY', strtex, coltex)
            self.linkColor(coltex, self.pbr, color, "Specular Tint")

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
            self.replaceSlot(self.pbr, PBR.Specular, 0.5)
            self.replaceSlot(self.pbr, PBR.SubsurfWeight, 0.0)
            if BLENDER3:
                self.replaceSlot(self.pbr, "Subsurface Color", (1,1,1,1))
            self.replaceSlot(self.pbr, "Subsurface Radius", (0,0,0))
        if self.owner.shader == 'PBRSKIN':
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", Tint(0.0))
            if self.isEnabled("Dual Lobe Specular"):
                if LS.materialMethod == 'EXTENDED_PRINCIPLED':
                    self.replaceSlot(self.pbr, "Roughness", 0.0)
                else:
                    rough1,rough2,roughtex,ratio = self.getDualRoughness()
                    roughness = rough1*(1-ratio) + rough2*ratio
                    if self.isEnabled("Detail"):
                        detrough, detroughtex,_ = self.getColorTex(["Detail Specular Roughness Mult"], "NONE", 1.0, False)
                        roughness *= detrough
                        roughtex = self.multiplyTexs(detroughtex, roughtex)
                    self.linkScalar(roughtex, self.pbr, roughness, "Roughness")
            else:
                self.replaceSlot(self.pbr, "Roughness", 0.5)
        else:
            if self.pureMetal:
                self.replaceSlot(self.pbr, "Specular Tint", Tint(1.0))
            channel,value,roughness,invert = self.owner.getGlossyRoughness(0.5)
            roughness *= (1 + anisotropy)
            self.addSlot(channel, self.pbr, "Roughness", roughness, value, invert)

    #-------------------------------------------------------------
    #   Clearcoat
    #-------------------------------------------------------------

    def addClearCoat(self, useTex, uvname):
        if self.isEnabled("Top Coat"):
            top,toptex,texslot = self.getColorTex(["Top Coat Weight"], "NONE", 1.0, False, isMask=True)
            rough,roughtex,_ = self.getColorTex(["Top Coat Roughness"], "NONE", 1.45)
            color,coltex,_ = self.getColorTex(["Top Coat Color"], "COLOR", WHITE)
            self.linkScalar(roughtex, self.pbr, rough, PBR.CoatRoughness)
        else:
            top,toptex = 0.0,None
            color,coltex = WHITE,None
        if self.owner.shader == 'UBER_IRAY':
            if self.owner.basemix == 0:    # Metallic/Roughness
                refl,reftex,_ = self.getColorTex(["Glossy Reflectivity"], "NONE", 0.5, False, useTex)
                coattex = self.mixTexs('MULTIPLY', toptex, reftex)
                value = 1.25 * refl * top
            elif self.owner.basemix == 1:  # Specular/Glossiness
                coattex = toptex
                value = top
            elif self.owner.basemix == 2:  # Weighted
                coattex = None
                value = 0.0
        else:
            coattex = toptex
            value = top
        if not useTex:
            coattex = None
        self.setCoatWeight(clamp(value), coattex, color, coltex, uvname)


    def setCoatWeight(self, coat, coattex, color, coltex, uvname):
        if BLENDER3:
            self.linkScalar(coattex, self.pbr, coat, "Clearcoat")
        else:
            if coat == 0:
                self.pbr.inputs["Coat Weight"].default_value = 0
            else:
                self.pbr.inputs["Coat Weight"].default_value = 1
                self.linkScalar(coattex, self.pbr, 0.1*coat, "Coat IOR", add=1)
                self.linkColor(coltex, self.pbr, color, "Coat Tint")
                bump,normal = self.getTopCoatBump(uvname)
                self.linkTopCoatBump(bump, normal, self.pbr, "Coat Normal")

    #-------------------------------------------------------------
    #   Sheen
    #-------------------------------------------------------------

    def buildSheen(self):
        if self.isEnabled("Velvet"):
            velvet,tex,texslot = self.getColorTex(["Velvet Strength"], "NONE", 0.0)
            self.linkScalar(tex, self.pbr, velvet, PBR.SheenWeight)

    #-------------------------------------------------------------
    #   Glossy or Dual lobe
    #-------------------------------------------------------------

    def buildGlossyOrDualLobe(self):
        if self.owner.basemix == 2:
            CyclesTree.buildGlossyOrDualLobe(self)
        elif self.isEnabled("Dual Lobe Specular"):
            dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
            if dualLobeWeight > 0:
                self.buildDualLobe()
                self.replaceSlot(self.pbr, PBR.Specular, 0)
                self.postPBR = True

    #-------------------------------------------------------------
    #   Refraction
    #-------------------------------------------------------------

    def buildRefraction(self):
        if not self.isEnabled("Transmission"):
            return 0, None
        if LS.materialMethod != 'EXTENDED_PRINCIPLED' or self.owner.isPureRefractive():
            col = self.column
            self.column = 5
            weight,wttex,texslot = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0, isMask=True)
            if weight > 0:
                self.linkScalar(wttex, self.pbr, weight, PBR.TransmitWeight, texslot=texslot)
                self.thickness = 0.0
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
        strength,strtex,texslot = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False, isMask=True)
        tint = None
        if self.getValue(["Share Glossy Inputs"], False):
            tint = Tint(1.0)
        self.postPBR = True

        if self.owner.isThinWall:
            # if thin walled is on then there's no volume
            # and we use the clearcoat channel for reflections
            #
            # principled ior = 1
            # principled roughness = 0
            # BLENDER 3:
            #   principled clearcoat = (iray refraction index - 1) * 10 * iray glossy layered weight
            #   principled clearcoat roughness = 0
            # BLENDER 4:
            #   coat weight = iray glossy layered weight
            #   coat roughness = iray glossy roughness
            #   coat ior = iray refraction index
            #   coat tint = iray glossy color
            self.owner.setTransSettings(True, False, color, 0.1)
            self.replaceSlot(pbr, "IOR", 1.0)
            self.replaceSlot(pbr, "Roughness", 0.0)
            if BLENDER3:
                clearcoat = (ior-1)*10*strength
                self.removeLink(pbr, "Clearcoat")
                self.linkScalar(strtex, pbr, clearcoat, "Clearcoat", texslot=texslot)
                self.replaceSlot(pbr, "Clearcoat Roughness", 0)
            else:
                self.removeLink(pbr, "Coat Weight")
                self.linkScalar(strtex, pbr, strength, "Coat Weight", texslot=texslot)
                self.removeLink(pbr, "Coat IOR")
                self.linkScalar(iortex, pbr, ior, "Coat IOR")
                self.removeLink(pbr, "Coat Roughness")
                self.linkScalar(roughtex, pbr, roughness, "Coat Roughness")
                self.removeLink(pbr, "Coat Tint")
                self.linkColor(coltex, pbr, color, "Coat Tint")
            if LS.materialMethod == 'EXTENDED_PRINCIPLED':
                from .cgroup import RayClipGroup
                clip = self.addGroup(RayClipGroup, "DAZ Ray Clip", col=6)
                self.links.new(pbr.outputs["BSDF"], clip.inputs["Shader"])
                self.linkColor(coltex, clip, color, "Color")
                self.cycles = clip

        elif self.owner.isVolume():
            self.owner.setTransSettings(True, False, color, 0.1)
            self.replaceSlot(pbr, "Metallic", 0)
            self.replaceSlot(pbr, PBR.Specular, 0)
            self.replaceSlot(pbr, "IOR", 1.0)
            self.replaceSlot(pbr, "Roughness", 0.0)

        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # specular tint = iray glossy color * iray glossy layered weight
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness
            self.owner.setTransSettings(True, False, color, 0.2)
            self.replaceSlot(pbr, "Metallic", 0)
            self.replaceSlot(pbr, PBR.Specular, 0.5)
            self.removeLink(pbr, "IOR")
            self.linkScalar(iortex, pbr, ior, "IOR")
            self.removeLink(pbr, "Roughness")
            self.setRoughness(pbr, "Roughness", roughness, roughtex, square=False)
            if not BLENDER3:
                self.removeLink(pbr, "Specular Tint")
                tint = self.compProd(color, (strength, strength, strength))
                tinttex = self.mixTexs('MULTIPLY', coltex, strtex)
                self.linkColor(tinttex, pbr, tint, "Specular Tint")
                tint = None
            transcolor,transtex,_ = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
            dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
            if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
                coltex = self.mixTexs('MULTIPLY', coltex, transtex)
                color = self.compProd(color, transcolor)

        self.removeLink(pbr, "Base Color")
        self.linkColor(coltex, pbr, color, "Base Color")
        self.replaceSlot(pbr, PBR.SubsurfWeight, 0)
        if BLENDER3:
            self.removeLink(pbr, "Subsurface Color")
            pbr.inputs["Subsurface Color"].default_value[0:3] = WHITE
        if tint:
            self.replaceSlot(pbr, "Specular Tint", tint)
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
            if isinstance(value, (int, float)):
                value = Vector((value,value,value))
            self.pbr.inputs[slot].default_value[0:3] = value
        else:
            value = averageColor(value)
            if maxval and value > maxval:
                value = maxval
            self.pbr.inputs[slot].default_value = value

