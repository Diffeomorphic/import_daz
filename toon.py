# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .cycles import CyclesTree
from .material import WHITE, BLACK
from .tree import colorOutput
from .utils import *

class ToonTree(CyclesTree):
    def __init__(self, cmat):
        CyclesTree.__init__(self, cmat)
        self.type = 'TOON'


    def buildLayer(self, uvname):
        self.buildNormal(uvname)
        self.buildBump(uvname)
        self.column = 4
        self.buildDiffuse()
        self.buildRim()
        self.buildGlossy()
        self.buildEmission()
        self.buildLight()


    def buildBumpMap(self, bumpval, bumptex):
        bump = self.addNode("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bumpval
        self.links.new(colorOutput(bumptex), bump.inputs["Height"])
        bump.inputs["Distance"].default_value = 0.2 * GS.scale * GS.bumpMultiplier
        return bump


    def correctBumpArea(self, geo, me):
        pass


    def buildDiffuse(self):
        from .cgroup import ToonDiffuseGroup
        color,tex = self.getDiffuseColor()
        node = self.addGroup(ToonDiffuseGroup, "DAZ Toon Diffuse")
        self.linkColor(tex, node, color, "Color")
        threshold = self.getValue(["Shadow Threshold"], 0)
        if threshold == -1:
            node.inputs["Ambience"].default_value[0:3] = WHITE
        else:
            amb,ambtex,texslot = self.getColorTex(["Ambient"], "COLOR", WHITE)
            self.linkColor(ambtex, node, amb, "Ambience")
        self.linkBumpNormal(node)
        self.cycles = self.diffuse = node
        LS.usedFeatures["Diffuse"] = True


    def buildShellGroups(self, shells):
        LS.toons.append(self.owner.geometry)


    def buildGlossy(self):
        fac = self.getValue(["Glossy Layered Weight"], 0)
        if fac == 0:
            return
        from .cgroup import ToonGlossyGroup
        node = self.addGroup(ToonGlossyGroup, "DAZ Toon Glossy")
        refl,refltex,texslot = self.getColorTex(["Glossy Reflectivity"], "COLOR", WHITE)
        rough,roughtex,texslot = self.getColorTex(["Glossy Roughness"], "NONE", 0.0)
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.linkColor(refltex, node, refl*fac, "Reflection")
        self.linkScalar(roughtex, node, rough, "Roughness")
        self.linkBumpNormal(node)
        self.cycles = node
        LS.usedFeatures["Glossy"] = True


    def buildRim(self):
        rim = self.getValue(["Rim Amount"], 0)
        if rim == 0:
            return
        from .cgroup import ToonRimGroup
        node = self.addGroup(ToonRimGroup, "DAZ Toon Rim")
        color,tex,texslot = self.getColorTex(["Rim Color"], "COLOR", WHITE)
        rim,rimtex,texslot = self.getColorTex(["Rim Amount"], "NONE", 0)
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.linkScalar(rimtex, node, rim, "Rim")
        self.linkColor(tex, node, color, "Color")
        self.linkBumpNormal(node)
        self.cycles = node
        LS.usedFeatures["Rim"] = True


    def buildLight(self):
        from .cgroup import ToonLightGroup
        node = self.addGroup(ToonLightGroup, "DAZ Toon Light")
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.cycles = node


    def setRenderSettings(self):
        mat = self.owner.rna
        if mat:
            mat.surface_render_method = 'BLENDED'

