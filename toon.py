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
        self.buildGlossy()
        self.buildEmission()


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
        glossy = self.addGroup(ToonGlossyGroup, "DAZ Toon Glossy")
        refl,refltex,texslot = self.getColorTex(["Glossy Reflectivity"], "COLOR", WHITE)
        rough,roughtex,texslot = self.getColorTex(["Glossy Roughness"], "NONE", 0.0)
        self.links.new(self.diffuse.outputs["Output"], glossy.inputs["Input"])
        self.linkColor(refltex, glossy, refl*fac, "Reflection")
        self.linkScalar(roughtex, glossy, rough, "Roughness")
        self.linkBumpNormal(glossy)
        self.cycles = glossy
        LS.usedFeatures["Glossy"] = True


    def setRenderSettings(self):
        mat = self.owner.rna
        if mat:
            mat.surface_render_method = 'BLENDED'

