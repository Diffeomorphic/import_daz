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
import os
from mathutils import Vector, Matrix, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .error import DazError
from .utils import *

#-------------------------------------------------------------
#   Cycles material
#-------------------------------------------------------------

class CyclesMaterial(Material):

    def __init__(self, fileref):
        Material.__init__(self, fileref)
        self.classType = CyclesMaterial
        self.tree = None
        self.useEevee = False


    def __repr__(self):
        treetype = "Unbuilt"
        if self.tree:
            treetype = self.tree.type
        geoname = None
        if self.geometry:
            geoname = self.geometry.name
        return ("<%sMaterial %s r:%s g:%s i:%s t:%s>" % (treetype, self.id, self.rna, geoname, self.ignore, self.hasAnyTexture()))


    def guessColor(self):
        from .guess import guessMaterialColor
        from .geometry import GeoNode
        from .finger import isCharacter
        color = LS.clothesColor
        mat = self.rna
        mtype = 'CLOTHES'
        if isinstance(self.geometry, GeoNode):
            ob = self.geometry.rna
        else:
            ob = self.mesh
        if ob is None:
            pass
        elif isCharacter(ob):
            color = LS.skinColor
        elif ob.data and ob.data.DazGraftGroup:
            color = LS.skinColor
            mtype = 'SKIN'
        guessMaterialColor(mat, GS.viewportColors, False, color, mtype)


    def build(self, context):
        if self.dontBuild():
            return
        Material.build(self, context)
        self.tree = self.setupTree()
        self.tree.build()


    def setupTree(self):
        from .pbr import PbrTree
        from .brick import BrickTree
        if self.isHair():
            from .hair import getHairTree
            geo = self.geometry
            if geo and geo.isStrandHair:
                geo.hairMaterials.append(self)
            return getHairTree(self)
        elif self.shader == 'BRICK':
            return BrickTree(self)
        else:
            if GS.materialMethod == 'PRINCIPLED':
                return PbrTree(self)
            else:
                return CyclesTree(self)


    def postbuild(self):
        Material.postbuild(self)
        geonode = self.geometry
        me = None
        if geonode and geonode.data and geonode.data.rna:
            geo = geonode.data
            me = geo.rna
            mnum = -1
            for mn,mat in enumerate(me.materials):
                if mat == self.rna:
                    mnum = mn
                    break
            if mnum < 0:
                return
            nodes = list(geo.nodes.values())
            if self.geoemit:
                self.correctEmitArea(nodes, me, mnum)
            if self.geobump:
                area = geo.getBumpArea(me, self.geobump.keys())
                self.correctBumpArea(area)

        if self.tree:
            if GS.pruneNodes:
                marked = pruneNodeTree(self.tree)
                if isinstance(self.tree, CyclesTree):
                    self.tree.selectDiffuse(marked)


    def addGeoBump(self, tex, socket):
        bumpmin = self.getValue("getChannelBumpMin", -0.01)
        bumpmax = self.getValue("getChannelBumpMax", 0.01)
        socket.default_value = (bumpmax-bumpmin) * LS.scale
        key = tex.name
        if key not in self.geobump.keys():
            self.geobump[key] = (tex, [])
        self.geobump[key][1].append(socket)


    def correctBumpArea(self, area):
        if area <= 0.0:
            return
        for tex,sockets in self.geobump.values():
            if not hasattr(tex, "image") or tex.image is None:
                continue
            width,height = tex.image.size
            density = width * height / area
            if density == 0.0:
                continue
            link = getLinkTo(self.tree, tex, "Vector")
            if link and link.from_node.type == 'MAPPING':
                scale = link.from_node.inputs["Scale"]
                density *= scale.default_value[0] * scale.default_value[1]
                if density == 0.0:
                    continue
            if density > 0:
                height = 3.0/math.sqrt(density)
            for socket in sockets:
                socket.default_value = height


    def correctEmitArea(self, nodes, me, mnum):
        ob = nodes[0].rna
        ob.data = me2 = me.copy()
        wmat = ob.matrix_world.copy()
        me2.transform(wmat)
        setWorldMatrix(ob, Matrix())
        area = sum([f.area for f in me2.polygons if f.material_index == mnum])
        ob.data = me
        setWorldMatrix(ob, wmat)
        bpy.data.meshes.remove(me2, do_unlink=True)

        area *= 1e-4/(LS.scale*LS.scale)
        for socket in self.geoemit:
            socket.default_value /= area
            for link in self.tree.links:
                if link.to_socket == socket:
                    node = link.from_node
                    if node.type == 'MATH':
                        node.inputs[0].default_value /= area


    def setTransSettings(self, useRefraction, useBlend, color, alpha):
        LS.usedFeatures["Transparent"] = True
        mat = self.rna
        if useBlend:
            mat.blend_method = 'BLEND'
            mat.show_transparent_back = False
        else:
            mat.blend_method = 'HASHED'
        mat.use_screen_refraction = useRefraction
        if hasattr(mat, "transparent_shadow_method"):
            mat.transparent_shadow_method = 'HASHED'
        else:
            mat.shadow_method = 'HASHED'
        if not self.isShellMat:
            mat.diffuse_color[0:3] = color
            mat.diffuse_color[3] = alpha

#-------------------------------------------------------------
#   Cycles node tree
#-------------------------------------------------------------

NCOLUMNS = 20
XSIZE = 300
YSIZE = 250


class CyclesTree:
    def __init__(self, cmat):
        self.type = 'CYCLES'
        self.material = cmat
        self.cycles = None
        self.eevee = None
        self.column = 4
        self.ycoords = NCOLUMNS*[2*YSIZE]
        self.texnodes = {}
        self.nodes = None
        self.links = None
        self.groups = {}
        self.layeredGroups = {}
        self.inShell = False
        self.isDecal = False

        self.diffuseColor = WHITE
        self.diffuseTex = None
        self.normal = None
        self.bump = None
        self.bumpval = 0
        self.bumptex = None
        self.texco = None
        self.texcos = {}
        self.displacement = None
        self.volume = None
        self.clipsocket = None
        self.useCutout = False
        self.useTranslucency = False
        self.pureMetal = False


    def __repr__(self):
        return ("<Cycles %s %s %s>" % (self.material.rna, self.nodes, self.links))


    def getValue(self, channel, default):
        return self.material.getValue(channel, default)


    def isEnabled(self, channel):
        return self.material.enabled[channel]


    def getColor(self, channel, default):
        return self.material.getColor(channel, default)


    def addNode(self, stype, col=None, size=0, label=None, parent=None):
        if col is None:
            col = self.column
        node = self.nodes.new(type = stype)
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= (YSIZE + size)
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node


    def getTexco(self, uv):
        key = self.material.getUvKey(uv, self.texcos)
        if key is None:
            return self.texco
        elif key not in self.texcos.keys():
            self.addUvNode(key, key)
        return self.texcos[key]


    def getCyclesSocket(self, node=None):
        if node is None:
            node = self.cycles
        if node is None:
            return None
        elif "Cycles" in node.outputs.keys():
            return node.outputs["Cycles"]
        else:
            return node.outputs[0]


    def getEeveeSocket(self, node=None):
        if node is None:
            node = self.eevee
        if node is None:
            return None
        elif "Eevee" in node.outputs.keys():
            return node.outputs["Eevee"]
        else:
            return node.outputs[0]


    def addGroup(self, classdef, name, col=None, size=0, args=[], force=False):
        if col is None:
            col = self.column
        node = self.addNode("ShaderNodeGroup", col, size=size)
        node.name = node.label = name
        group = classdef()
        if name in bpy.data.node_groups.keys() and not force:
            tree = bpy.data.node_groups[name]
            if group.checkSockets(tree):
                node.node_tree = tree
                return node
        group.create(node, name, self)
        group.addNodes(args)
        node.node_tree.name = name
        return node


    def addShellGroup(self, shell, push):
        shmat = shell.material
        shmat.isShellMat = True
        shname = shell.name
        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
            shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.material.name))
            return None
        node = self.addNode("ShaderNodeGroup")
        node.width = 240
        nname = ("%s_%s" % (shname, self.material.name))
        node.name = nname
        node.label = shname
        if shell.tree:
            node.node_tree = shell.tree
            node.inputs["Influence"].default_value = 1.0
            return node
        elif shell.match and shell.match.tree:
            node.node_tree = shell.tree = shell.match.tree
            node.inputs["Influence"].default_value = 1.0
            return node
        group = self.getShellGroup(shmat, push)
        group.create(node, nname, self)
        group.addNodes((shmat, shell.uv))
        node.inputs["Influence"].default_value = 1.0
        shell.tree = shmat.tree = node.node_tree
        shmat.geometry = self.material.geometry
        return node


    def getShellGroup(self, shmat, push):
        from .cgroup import OpaqueShellCyclesGroup, RefractiveShellCyclesGroup
        if shmat.isRefractive():
            return RefractiveShellCyclesGroup(push)
        else:
            return OpaqueShellCyclesGroup(push)


    def build(self):
        self.makeTree()
        self.buildLayer("")
        self.buildCutout()
        self.buildVolume()
        self.buildDisplacementNodes()
        self.buildDecals()
        self.buildShells()
        self.buildOutput()


    def buildDecals(self):
        if not self.material.decals:
            return
        if self.material.isShellMat:
            raise RuntimeError("BUG buildDecals: %s" % self)
        from .cgroup import MappingGroup
        decals = [(inst.getValue(["Priority"],0), n, inst) for n,inst in enumerate(self.material.decals)]
        decals.sort()
        for _,_,inst in decals:
            fmode = inst.getValue(["Face Mode"], 2)
            # [ "Front", "Back", "Front And Back" ]
            csys = self.getValue(["Texture Coordinate System"], 2)
            # [ "UVW", "World", "Object" ]
            if csys == 0:
                mapping = texco
            elif csys == 2:
                if inst.mappingNode:
                    mapping = self.addNode("ShaderNodeGroup")
                    mapping.name = mapping.label = inst.name
                    mapping.node_tree = inst.mappingNode
                else:
                    mapping = self.addGroup(MappingGroup, inst.name, args=[inst.rna], force=True)
                    inst.mappingNode = mapping.node_tree
            self.column += 1
            for geonode in inst.geometries:
                for dmat,grp in zip(geonode.materials.values(), geonode.data.polygon_material_groups):
                    dmat.isShellMat = True
                    if grp == "Front":
                        pass
                    elif grp == "Reverse":
                        continue
                    else:
                        raise RuntimeError("Unknown decal material group: %s" % grp)
                    node = self.addDecalGroup(dmat)
                    self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
                    self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
                    if csys == 2:
                        self.links.new(mapping.outputs["Depth Mask"], node.inputs["Influence"])
                    self.links.new(mapping.outputs["Vector"], node.inputs["UV"])
                    self.cycles = self.eevee = node
                    self.ycoords[self.column] -= 50


    def addDecalGroup(self, dmat):
        node = self.addNode("ShaderNodeGroup")
        node.width = 240
        node.name = dmat.name
        node.label = dmat.name
        if dmat.decalNode:
            node.node_tree = dmat.decalNode.node_tree
        else:
            group = self.getShellGroup(dmat, 0)
            group.create(node, dmat.name, self)
            group.isDecal = True
            group.addNodes((dmat, ""))
            dmat.decalNode = node
        node.inputs["Influence"].default_value = 1.0
        return node


    def buildShells(self):
        shells = []
        n = 0
        for shell in self.material.shells.values():
            for geonode in shell.geometry.nodes.values():
                shells.append((geonode.push, n, shell))
                n += 1
        shells.sort()
        if shells:
            self.column += 1
        for push,n,shell in shells:
            node = self.addShellGroup(shell, push)
            if node:
                self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
                self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
                self.links.new(self.getTexco(shell.uv), node.inputs["UV"])
                if self.displacement:
                    self.links.new(self.displacement, node.inputs["Displacement"])
                self.cycles = self.eevee = node
                self.displacement = node.outputs["Displacement"]
                self.ycoords[self.column] -= 50


    def buildLayer(self, uvname):
        self.buildNormal(uvname)
        self.buildBump()
        self.buildDetail(uvname)
        self.buildDiffuse()
        self.buildTranslucency()
        self.buildMakeup()
        self.buildOverlay()
        if self.material.basemix == 2:  # Weighted
            self.diffuseCycles = self.cycles
            self.diffuseEevee = self.eevee
            self.cycles = self.eevee = None
        dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
        if dualLobeWeight == 1:
            self.buildDualLobe()
        elif dualLobeWeight == 0:
            self.buildGlossy()
        else:
            self.buildGlossy()
            self.buildDualLobe()
        self.buildMetal()
        self.buildTopCoat()
        if self.material.isRefractive():
            self.buildRefraction()
        else:
            self.buildEmission()
        if self.material.basemix == 2:  # Weighted
            self.buildWeighted()


    def makeTree(self, slot="UV"):
        mat = self.material.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        return self.addTexco(slot)


    def addTexco(self, slot):
        if self.material.useDefaultUvs:
            node = self.addNode("ShaderNodeTexCoord", 1)
            self.texco = node.outputs[slot]
        else:
            node = self.addNode("ShaderNodeUVMap", 1)
            node.uv_map = self.material.uv_set.name
            self.texco = node.outputs["UV"]
        ox = self.getValue("getChannelHorizontalOffset", 0)
        oy = self.getValue("getChannelVerticalOffset", 0)
        kx = self.getValue("getChannelHorizontalTiles", 1)
        ky = self.getValue("getChannelVerticalTiles", 1)
        self.mapTexco(ox, oy, kx, ky)
        for key,uvset in self.material.uv_sets.items():
            self.addUvNode(key, uvset.name)
        return node


    def addUvNode(self, key, uvname):
        node = self.addNode("ShaderNodeUVMap", 1)
        node.uv_map = uvname
        slot = "UV"
        self.texcos[key] = node.outputs[slot]


    def mapTexco(self, ox, oy, kx, ky):
        if ox != 0 or oy != 0 or kx not in [0,1] or ky not in [0,1]:
            sx = sy = 1
            dx = dy = 0
            if kx != 0:
                sx = 1/kx
                dx = -ox/kx
            if ky != 0:
                sy = 1/ky
                dy = oy/ky
            mapping = self.addMappingNode((dx,dy,sx,sy,0), None)
            if mapping:
                self.linkVector(self.texco, mapping, 0)
                self.texco = mapping


    def addMappingNode(self, data, map):
        dx,dy,sx,sy,rz = data
        if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            mapping = self.addNode("ShaderNodeMapping", 1)
            mapping.vector_type = 'TEXTURE'
            if hasattr(mapping, "translation"):
                mapping.translation = (dx,dy,0)
                mapping.scale = (sx,sy,1)
                if rz != 0:
                    mapping.rotation = (0,0,rz)
            else:
                mapping.inputs['Location'].default_value = (dx,dy,0)
                mapping.inputs['Scale'].default_value = (sx,sy,1)
                if rz != 0:
                    mapping.inputs['Rotation'].default_value = (0,0,rz)
            if map and not map.invert and hasattr(mapping, "use_min"):
                mapping.use_min = mapping.use_max = 1
            return mapping
        return None

#-------------------------------------------------------------
#   Normal
#-------------------------------------------------------------

    def buildNormal(self, uvname):
        if not self.isEnabled("Normal"):
            return
        strength,tex = self.getColorTex("getChannelNormal", "NONE", 1.0, useFactor=False)
        if strength>0 and tex:
            self.buildNormalMap(strength, tex, uvname)


    def buildNormalMap(self, strength, tex, uvname):
        self.normal = self.addNode("ShaderNodeNormalMap", col=3)
        self.normal.space = "TANGENT"
        if uvname:
            self.normal.uv_map = uvname
        elif self.material.uv_set:
            self.normal.uv_map = self.material.uv_set.name
        self.normal.inputs["Strength"].default_value = strength
        self.links.new(tex.outputs[0], self.normal.inputs["Color"])


    def addOverlay(self, fac, factex, col):
        NORMAL = (0.5, 0.5, 1, 1)
        mix = self.addNode("ShaderNodeMixRGB", col)
        mix.blend_type = 'OVERLAY'
        self.linkScalar(factex, mix, fac, "Fac")
        mix.inputs["Color1"].default_value = NORMAL
        mix.inputs["Color2"].default_value = NORMAL
        return mix

#-------------------------------------------------------------
#   Bump
#-------------------------------------------------------------

    def buildBump(self):
        if not self.isEnabled("Bump"):
            return
        self.bumpval,self.bumptex = self.getColorTex("getChannelBump", "NONE", 0, False)
        if self.bumpval and self.bumptex:
            self.bump = self.buildBumpMap(self.bumpval, self.bumptex, col=3)
            self.linkNormal(self.bump)


    def buildBumpMap(self, bump, bumptex, col=3):
        node = self.addNode("ShaderNodeBump", col=col)
        node.inputs["Strength"].default_value = bump * GS.bumpFactor
        self.links.new(bumptex.outputs[0], node.inputs["Height"])
        self.material.addGeoBump(bumptex, node.inputs["Distance"])
        return node


    def linkBumpNormal(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])
        elif self.normal:
            self.links.new(self.normal.outputs["Normal"], node.inputs["Normal"])


    def linkBump(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])


    def linkNormal(self, node):
        if self.normal:
            self.links.new(self.normal.outputs["Normal"], node.inputs["Normal"])

#-------------------------------------------------------------
#   Detail
#-------------------------------------------------------------

    def buildDetail(self, uvname):
        if not self.isEnabled("Detail"):
            return
        weight,wttex = self.getColorTex(["Detail Weight"], "NONE", 0.0, isMask=True)
        if weight == 0:
            return
        texco = self.texco
        ox = LS.scale*self.getValue(["Detail Horizontal Offset"], 0)
        oy = LS.scale*self.getValue(["Detail Vertical Offset"], 0)
        kx = self.getValue(["Detail Horizontal Tiles"], 1)
        ky = self.getValue(["Detail Vertical Tiles"], 1)
        self.mapTexco(ox, oy, kx, ky)

        strength,tex = self.getColorTex(["Detail Normal Map"], "NONE", 1.0, useFactor=False)
        weight = weight*strength
        mode = self.getValue(["Detail Normal Map Mode"], 0)
        if weight == 0 or tex is None:
            pass
        elif mode == 0:
            # Height Map
            if self.bump:
                link = getLinkTo(self, self.bump, "Height")
                if link:
                    mult = self.addNode("ShaderNodeMath", 3)
                    mult.operation = 'MULTIPLY_ADD'
                    self.links.new(tex.outputs[0], mult.inputs[0])
                    self.linkScalar(wttex, mult, weight, 1)
                    self.links.new(link.from_socket, mult.inputs[2])
                    self.links.new(mult.outputs["Value"], self.bump.inputs["Height"])
            else:
                tex = self.multiplyTexs(tex, wttex)
                self.bump = self.buildBumpMap(weight, tex, col=3)
                self.linkNormal(self.bump)
        elif mode == 1:
            # Normal Map
            if self.normal:
                link = getLinkTo(self, self.normal, "Color")
                if link:
                    strength = self.normal.inputs["Strength"].default_value
                    if strength != 1.0:
                        mix1 = self.addOverlay(strength, None, 2)
                        self.links.new(link.from_socket, mix1.inputs["Color2"])
                        socket = mix1.outputs["Color"]
                        self.normal.inputs["Strength"].default_value = 1.0
                    else:
                        socket = link.from_socket
                    mix = self.addOverlay(weight, wttex, 3)
                    self.links.new(socket, mix.inputs["Color1"])
                    if tex:
                        self.links.new(tex.outputs[0], mix.inputs["Color2"])
                    self.links.new(mix.outputs["Color"], self.normal.inputs["Color"])
                else:
                    self.links.new(tex.outputs[0], self.normal.inputs["Color"])
            else:
                self.buildNormalMap(weight, tex, uvname)
                if wttex:
                    self.links.new(wttex.outputs[0], self.normal.inputs["Strength"])
                if self.bump:
                    self.links.new(self.normal.outputs["Normal"], self.bump.inputs["Normal"])

        self.texco = texco

#-------------------------------------------------------------
#   Diffuse and Diffuse Overlay
#-------------------------------------------------------------

    def getDiffuseColor(self):
        color,tex = self.getColorTex("getChannelDiffuse", "COLOR", WHITE)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect > 0:  # Scatter Transmit, Scatter Transmit Intensity
            tint = self.getColor(["SSS Reflectance Tint"], WHITE)
            color = self.compProd(color, tint)
        return color,tex


    def compProd(self, x, y):
        return [x[0]*y[0], x[1]*y[1], x[2]*y[2]]


    def buildDiffuse(self):
        self.column = 4
        if not self.isEnabled("Diffuse"):
            return
        color,tex = self.getDiffuseColor()
        node = self.addNode("ShaderNodeBsdfDiffuse")
        self.cycles = self.eevee = node
        self.linkColor(tex, node, color, "Color")
        roughness,roughtex = self.getColorTex(["Diffuse Roughness"], "NONE", 0, False)
        if self.isEnabled("Detail"):
            detrough,dettex = self.getColorTex(["Detail Specular Roughness Mult"], "NONE", 0, False)
            roughness *= detrough
            roughtex = self.multiplyTexs(dettex, roughtex)
        self.setRoughness(node, "Roughness", roughness, roughtex)
        self.linkBumpNormal(node)
        LS.usedFeatures["Diffuse"] = True
        self.diffuseColor = color
        self.diffuseTex = tex


    def buildOverlay(self):
        if self.getValue(["Diffuse Overlay Weight"], 0):
            self.column += 1
            slot = self.getImageSlot(["Diffuse Overlay Weight"])
            weight,wttex = self.getColorTex(["Diffuse Overlay Weight"], "NONE", 0, slot=slot, isMask=True)
            if self.getValue(["Diffuse Overlay Weight Squared"], False):
                power = 4
            else:
                power = 2
            if wttex:
                wttex = self.raiseToPower(wttex, power, slot)
            color,tex = self.getColorTex(["Diffuse Overlay Color"], "COLOR", WHITE)
            from .cgroup import DiffuseGroup
            node = self.addGroup(DiffuseGroup, "DAZ Overlay")
            self.linkColor(tex, node, color, "Color")
            roughness,roughtex = self.getColorTex(["Diffuse Overlay Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkBumpNormal(node)
            self.mixWithActive(weight**power, wttex, node)
            return True
        else:
            return False


    def getImageSlot(self, attr):
        if self.material.getImageMod(attr, "grayscale_mode") == "alpha":
            return "Alpha"
        else:
            return 0


    def raiseToPower(self, tex, power, slot):
        node = self.addNode("ShaderNodeMath", col=self.column-1)
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if slot not in tex.outputs.keys():
            slot = 0
        self.links.new(tex.outputs[slot], node.inputs[0])
        return node


    def getColorTex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None, slot=0, isMask=False):
        channel = self.material.getChannel(attr)
        if channel is None:
            return default,None
        if isinstance(channel, tuple):
            channel = channel[0]
        if useTex:
            tex = self.addTexImageNode(channel, colorSpace, isMask)
        else:
            tex = None
        if value is not None:
            pass
        elif channel["type"] in ["color", "float_color"]:
            value = self.material.getChannelColor(channel, default)
        elif channel["type"] in ["image"]:
            if isVector(default):
                value = WHITE
            else:
                value = 1.0
        else:
            value = self.material.getChannelValue(channel, default)
            if value < 0:
                return 0,None
        if useFactor:
            value,tex = self.multiplySomeTex(value, tex, slot)
        if isVector(value) and not isVector(default):
            value = (value[0] + value[1] + value[2])/3
        if not isVector(value):
            if maxval and value > maxval:
                value = maxval
            if isVector(default):
                value = (value, value, value)
        return value,tex

#-------------------------------------------------------------
#  Makeup
#-------------------------------------------------------------

    def buildMakeup(self):
        if not self.getValue(["Makeup Enable"], False):
            return False
        wt = self.getValue(["Makeup Weight"], 0)
        if wt == 0:
            return
        from .cgroup import MakeupGroup
        self.column += 1
        node = self.addGroup(MakeupGroup, "DAZ Makeup", size=100)
        color,tex = self.getColorTex(["Makeup Base Color"], "COLOR", WHITE, False)
        self.linkColor(tex, node, color, "Color")
        roughness,roughtex = self.getColorTex(["Makeup Roughness Mult"], "NONE", 0.0, False)
        self.linkScalar(roughtex, node, roughness, "Roughness")
        self.linkBumpNormal(node)
        wt,wttex = self.getColorTex(["Makeup Weight"], "NONE", 0.0, False, isMask=True)
        self.mixWithActive(wt, wttex, node)
        return True

#-------------------------------------------------------------
#  Dual Lobe
#-------------------------------------------------------------

    def buildDualLobe(self):
        from .cgroup import DualLobeGroupUberIray, DualLobeGroupPbrSkin
        if not self.isEnabled("Dual Lobe Specular"):
            return

        self.column += 1
        if self.material.shader == 'PBRSKIN':
            node = self.addGroup(DualLobeGroupPbrSkin, "DAZ Dual Lobe PBR", size=100)
        else:
            node = self.addGroup(DualLobeGroupUberIray, "DAZ Dual Lobe Uber", size=100)
        value,tex = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 0.5, False, isMask=True)
        node.inputs["Weight"].default_value = value
        if tex:
            wttex = self.multiplyScalarTex(value, tex)
            if wttex:
                self.links.new(wttex.outputs[0], node.inputs["Weight"])

        value,tex = self.getColorTex(["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        node.inputs["IOR"].default_value = 1.1 + 0.7*value
        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.links.new(iortex.outputs[0], node.inputs["IOR"])

        if self.material.shader == 'PBRSKIN':
            rough1,rough2,roughtex,ratio = self.getDualRoughness(0.0)
            self.setRoughness(node, "Roughness 1", rough1, roughtex)
            self.setRoughness(node, "Roughness 2", rough2, roughtex)
            ratio = 1 - ratio
        else:
            ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)
            rough1,roughtex1 = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 1", rough1, roughtex1)
            rough2,roughtex2 = self.getColorTex(["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 2", rough2, roughtex2)

        self.linkBumpNormal(node)
        self.mixWithActive(ratio, None, node, keep=True)
        LS.usedFeatures["Glossy"] = True


    def getDualRoughness(self, default):
        roughness,roughtex = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", default, False)
        lobe2mult = self.getValue(["Specular Lobe 2 Roughness Mult"], 1.0)
        duallobemult = self.getValue(["Dual Lobe Specular Roughness Mult"], 1.0)
        rough1 = roughness*duallobemult
        rough2 = roughness*duallobemult*lobe2mult
        ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)
        return rough1, rough2, roughtex, ratio

#-------------------------------------------------------------
#   Metal
#-------------------------------------------------------------

    def buildMetal(self):
        if not (self.isEnabled("Metallicity") and
                self.material.basemix == 0):
            return
        if self.getValue(["Metallic Weight"], 0) == 0:
            return
        from .cgroup import MetalGroupUber, MetalGroupPbrSkin
        self.column += 1
        if self.material.shader == 'PBRSKIN':
            node = self.addGroup(MetalGroupPbrSkin, "DAZ Metal PBR", size=100)
            rough1,rough2,roughtex, ratio = self.getDualRoughness(0.0)
            self.setRoughness(node, "Roughness 1", rough1, roughtex)
            self.setRoughness(node, "Roughness 2", rough2, roughtex)
            node.inputs["Dual Ratio"].default_value = ratio
        else:
            node = self.addGroup(MetalGroupUber, "DAZ Metal Uber", size=100)
            roughness,roughtex = self.getColorTex(["Glossy Roughness"], "NONE", 0)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            anisotropy,tex = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
            self.linkScalar(tex, node, anisotropy, "Anisotropy")
            anirot,tex = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            self.linkScalar(tex, node, 1 - anirot, "Rotation")

        self.linkColor(self.diffuseTex, node, self.diffuseColor, "Color")
        self.linkBumpNormal(node)
        weight,wttex = self.getColorTex(["Metallic Weight"], "NONE", 0)
        self.mixWithActive(weight, wttex, node)
        if weight == 1 and wttex is None:
            self.pureMetal = True

#-------------------------------------------------------------
#   Glossy
#-------------------------------------------------------------

    def getGlossyColor(self):
        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False, isMask=True)
        color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, False)
        if tex and strtex:
            tex = self.mixTexs('MULTIPLY', tex, strtex)
        elif strtex:
            tex = strtex
        color = strength*color
        if tex:
            tex = self.multiplyVectorTex(color, tex)
        return color,tex


    def buildGlossy(self):
        color = self.getColor("getChannelGlossyColor", BLACK)
        strength = self.getValue("getChannelGlossyLayeredWeight", 0)
        if isBlack(color) or strength == 0:
            return

        from .cgroup import GlossyGroup
        self.column += 1
        glossy = self.addGroup(GlossyGroup, "DAZ Glossy", size=100)
        color,tex = self.getGlossyColor()
        self.linkColor(tex, glossy, color, "Color")
        ior,iortex = self.getFresnelIOR()
        self.linkScalar(iortex, glossy, ior, "IOR")
        channel,value,roughness,invert = self.material.getGlossyRoughness(0.0)
        roughtex = self.addSlot(channel, glossy, "Roughness", roughness, value, invert)
        anisotropy,tex = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        self.linkScalar(tex, glossy, anisotropy, "Anisotropy")
        if anisotropy > 0:
            anirot,tex = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 1 - anirot
            self.linkScalar(tex, glossy, value, "Rotation")
        self.linkBumpNormal(glossy)

        LS.usedFeatures["Glossy"] = True
        if self.cycles:
            self.links.new(self.getCyclesSocket(), glossy.inputs["Cycles"])
        if self.eevee:
            self.links.new(self.getEeveeSocket(), glossy.inputs["Eevee"])
        self.eevee = self.cycles = glossy


    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
        ior = 1.45
        iortex = None
        if self.material.shader == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                value,tex = self.getColorTex(["Glossy Reflectivity"], "NONE", 0, False)
                factor = 0.7 * value
                ior = 1.1 + factor
            elif self.material.basemix == 1:  # Specular/Glossiness
                color,tex = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, False)
                factor = 0.7 * averageColor(color) / 0.078
                ior = 1.1 + factor
            elif self.material.basemix == 2:  # Weighted
                ior = 10
                tex = None
            if tex:
                iortex = self.multiplyAddScalarTex(factor, 1.1, tex)
        return ior, iortex

#-------------------------------------------------------------
#   Weigthed
#-------------------------------------------------------------

    def buildWeighted(self):
        diffweight,difftex = self.getColorTex(["Diffuse Weight"], "NONE", 0)
        glossweight,glosstex = self.getColorTex(["Glossy Weight"], "NONE", 0)
        fac = glossweight / (glossweight + diffweight)
        if fac == 0:
            self.cycles = self.diffuseCycles
            self.eevee = self.diffuseEevee
        elif fac == 1 and difftex is None and glosstex is None:
            pass
        else:
            from .cgroup import WeightedGroup
            self.column += 1
            node = self.addGroup(WeightedGroup, "DAZ Weighted", size=100)
            self.linkScalar(glosstex, node, fac, "Fac")
            if self.diffuseCycles:
                self.links.new(self.getCyclesSocket(self.diffuseCycles), node.inputs["Diffuse Cycles"])
            if self.diffuseEevee:
                self.links.new(self.getEeveeSocket(self.diffuseEevee), node.inputs["Diffuse Eevee"])
            if self.cycles:
                self.links.new(self.getCyclesSocket(), node.inputs["Glossy Cycles"])
            if self.eevee:
                self.links.new(self.getEeveeSocket(), node.inputs["Glossy Eevee"])
            self.cycles = self.eevee = node

#-------------------------------------------------------------
#   Top Coat
#-------------------------------------------------------------

    def buildTopCoat(self):
        if not self.isEnabled("Top Coat"):
            return
        topweight = self.getValue(["Top Coat Weight"], 0)
        if topweight == 0:
            return

        # Top Coat Layering Mode
        #   [ "Reflectivity", "Weighted", "Fresnel", "Custom Curve" ]
        lmode = self.getValue(["Top Coat Layering Mode"], 0)
        fresnel = refltex = None
        if lmode == 2:  # Fresnel
            from .cgroup import Fresnel2Group
            weight = 0.5
            fresnel = self.addGroup(Fresnel2Group, "DAZ Fresnel 2")
            fresnel.inputs["Power"].default_value = 1
            ior,iortex = self.getColorTex(["Top Coat IOR"], "NONE", 1.45)
            self.linkScalar(iortex, fresnel, ior, "IOR")

        if self.material.shader == 'UBER_IRAY':
            # Top Coat Bump Mode
            #   [ "Height Map", "Normal Map" ]
            if not fresnel:
                refl,refltex = self.getColorTex(["Reflectivity"], "NONE", 0, useFactor=False)
                weight = 0.05 * topweight * refl
            bump,bumptex = self.getColorTex(["Top Coat Bump"], "NONE", 0, useFactor=False)
        else:
            if not fresnel:
                refl,refltex = self.getColorTex(["Top Coat Reflectivity"], "NONE", 0, useFactor=False)
            weight = 0.05 * topweight * refl
            bump = self.getValue(["Top Coat Bump Weight"], 0)
            bump *= self.bumpval
            bumptex = None

        _,tex = self.getColorTex(["Top Coat Weight"], "NONE", 0, value=weight, isMask=True)
        weighttex = self.multiplyTexs(tex, refltex)
        color,coltex = self.getColorTex(["Top Coat Color"], "COLOR", WHITE)
        roughness,roughtex = self.getColorTex(["Top Coat Roughness"], "NONE", 0)
        if roughness == 0:
            glossiness,glosstex = self.getColorTex(["Top Coat Glossiness"], "NONE", 1)
            roughness = 1 - glossiness
            roughtex = self.invertTex(glosstex, 5)

        from .cgroup import TopCoatGroup
        self.column += 1
        top = self.addGroup(TopCoatGroup, "DAZ Top Coat", size=100)
        self.linkColor(coltex, top, color, "Color")
        self.linkScalar(roughtex, top, roughness, "Roughness")
        if self.material.shader == 'PBRSKIN':
            if self.bumptex:
                self.links.new(self.bumptex.outputs[0], top.inputs["Height"])
                self.material.addGeoBump(self.bumptex, top.inputs["Distance"])
            self.linkNormal(top)
        elif bumptex:
            self.links.new(bumptex.outputs[0], top.inputs["Height"])
            self.material.addGeoBump(bumptex, top.inputs["Distance"])
            self.linkBumpNormal(top)
        top.inputs["Bump"].default_value = bump * GS.bumpFactor
        self.mixWithActive(weight, weighttex, top)
        if fresnel:
            self.linkScalar(roughtex, fresnel, roughness, "Roughness")
            self.linkBumpNormal(fresnel)
            self.links.new(fresnel.outputs["Dielectric"], top.inputs["Fac"])

#-------------------------------------------------------------
#   Translucency
#-------------------------------------------------------------

    def checkTranslucency(self):
        if not self.isEnabled("Translucency"):
            return False
        if (self.material.isThinWall() or
            self.volume or
            self.getValue("getChannelTranslucencyWeight", 0) > 0.01):
            return True
        else:
            return False


    def buildTranslucency(self):
        if (GS.materialMethod != 'BSDF' or
            not self.checkTranslucency()):
            return
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if fac == 0 and effect != 1:
            return
        self.column += 1
        mat = self.material.rna
        color,tex = self.getTranslucentColor()
        if isBlack(color):
            return

        from .cgroup import TranslucentGroup
        node = self.addGroup(TranslucentGroup, "DAZ Translucent", size=200)
        node.width = 200
        self.linkColor(tex, node, color, "Color")
        node.inputs["Gamma"].default_value = 3.5
        node.inputs["Scale"].default_value = 1.0
        ssscolor,ssstex,sssmode = self.getSSSColor()
        radius,radtex = self.getSSSRadius(color, ssscolor, ssstex, sssmode)
        radius,ior,aniso = self.fixSSSRadius(radius)
        self.linkColor(radtex, node, radius, "Radius")
        node.inputs["IOR"].default_value = ior
        node.inputs["Anisotropy"].default_value = aniso
        node.inputs["Cycles Mix Factor"].default_value = (not GS.useVolume)
        node.inputs["Eevee Mix Factor"].default_value = 1.0
        self.linkBumpNormal(node)

        fac,factex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
        if effect == 1: # Scatter and transmit
            fac = 0.5 + fac/2
            if factex and factex.type == 'MATH':
                factex.inputs[0].default_value = fac
        self.mixWithActive(fac, factex, node)
        LS.usedFeatures["Transparent"] = True
        self.endSSS()


    def getTranslucentColor(self):
        color,tex = self.getColorTex(["Translucency Color"], "COLOR", BLACK)
        if (tex is None and
            (GS.useFakeTranslucencyTexture or not GS.useVolume)):
            tex = self.diffuseTex
        return color,tex


    def getSSSColor(self):
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            color,tex = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
        elif sssmode == 0:
            sss,tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            if sss > 1:
                sss = 1
            color = (sss,sss,sss)
        else:
            color,tex = WHITE,None
        return color,tex,sssmode


    def endSSS(self):
        LS.usedFeatures["SSS"] = True
        mat = self.material.rna
        if hasattr(mat, "use_sss_translucency"):
            mat.use_sss_translucency = True


    def getSSSRadius(self, color, ssscolor, ssstex, sssmode):
        # if there's no volume we use the sss to make translucency
        # please note that here we only use the iray base translucency color with no textures
        # as for blender 2.8x eevee doesn't support nodes in the radius channel so we deal with it
        if self.material.isThinWall():
            return color,None

        if sssmode == 1 and isWhite(ssscolor):
            ssscolor = BLACK
        elif sssmode == 0:  # Mono
            s,ssstex = self.getColorTex("getChannelSSSAmount", "NONE", 0)
            if s > 1:
                s = 1
            ssscolor = Vector((s,s,s))
        trans,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        if isWhite(trans):
            trans = BLACK

        rad,radtex = self.sumColors(ssscolor, ssstex, trans, transtex)
        radius = rad * 2.0 * LS.scale
        return radius,radtex


    def fixSSSRadius(self, radius):
        if bpy.app.version < (3,0,0):
            return radius, 0, 0
        elif GS.sssMethod == 'BURLEY':
            return 0.25*radius, 0, 0
        elif GS.sssMethod == 'RANDOM_WALK_FIXED_RADIUS':
            return 0.5*radius, 1.4, 0.8
        elif GS.sssMethod == 'RANDOM_WALK':
            return 0.1*radius, 1.4, 0.8

#-------------------------------------------------------------
#   Transparency
#-------------------------------------------------------------

    def sumColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self.mixTexs('ADD', tex, tex2)
        elif tex2:
            tex = tex2
        color = Vector(color) + Vector(color2)
        return color,tex


    def multiplyColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self.mixTexs('MULTIPLY', tex, tex2)
        elif tex2:
            tex = tex2
        color = self.compProd(color, color2)
        return color,tex


    def getRefractionColor(self):
        if self.getValue(["Share Glossy Inputs"], False):
            color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
            roughness, roughtex = self.getColorTex(["Glossy Roughness"], "NONE", 0, False, maxval=1)
        else:
            color,tex = self.getColorTex("getChannelRefractionColor", "COLOR", WHITE)
            roughness,roughtex = self.getColorTex(["Refraction Roughness"], "NONE", 0, False, maxval=1)
        return color, tex, roughness, roughtex


    def addInput(self, node, channel, slot, colorSpace, default, maxval=0):
        value,tex = self.getColorTex(channel, colorSpace, default, maxval=maxval)
        if isVector(default):
            node.inputs[slot].default_value[0:3] = value
        else:
            node.inputs[slot].default_value = value
        if tex:
            self.links.new(tex.outputs[0], node.inputs[slot])
        return value,tex


    def setRoughness(self, node, slot, roughness, roughtex, square=True):
        node.inputs[slot].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return roughness


    def buildRefraction(self):
        weight,wttex = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0)
        if weight == 0:
            return weight,wttex
        node,color = self.buildRefractionNode()
        self.mixWithActive(weight, wttex, node)
        if GS.useFakeCaustics and not self.material.isThinWall():
            from .cgroup import FakeCausticsGroup
            self.column += 1
            node = self.addGroup(FakeCausticsGroup, "DAZ Fake Caustics", args=[color], force=True)
            self.mixWithActive(weight, wttex, node, keep=True)
        return weight,wttex


    def buildRefractionNode(self):
        from .cgroup import RefractionGroup
        self.column += 1
        node = self.addGroup(RefractionGroup, "DAZ Refraction", size=150)
        node.width = 240

        color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
        roughness, roughtex = self.getColorTex(["Glossy Roughness"], "NONE", 0, False, maxval=1)
        self.linkColor(tex, node, color, "Glossy Color")
        self.linkScalar(roughtex, node, roughness, "Glossy Roughness")

        color,coltex,roughness,roughtex = self.getRefractionColor()
        ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
        aniso,anisotex = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        if aniso > 0:
            roughness = roughness ** (1/(1+aniso))
        anirot,rottex = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
        self.linkColor(coltex, node, color, "Refraction Color")

        self.linkScalar(roughtex, node, roughness, "Refraction Roughness")
        self.linkScalar(iortex, node, ior, "IOR")
        self.linkScalar(anisotex, node, aniso, "Anisotropy")
        self.linkScalar(rottex, node, 1 - anirot, "Rotation")
        if (self.material.isThinWall() or
            (ior == 1 and iortex is None)):
            node.inputs["Thin Wall"].default_value = 1
            self.material.setTransSettings(False, True, color, 0.1)
        else:
            node.inputs["Thin Wall"].default_value = 0
            self.material.setTransSettings(True, False, color, 0.2)
        self.linkBumpNormal(node)
        return node, color


    def buildCutout(self):
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        if alpha < 1 or tex:
            self.column += 1
            self.useCutout = True
            if alpha == 0:
                node = self.addNode("ShaderNodeBsdfTransparent")
                self.cycles = node
                self.eevee = node
                tex = None
            else:
                from .cgroup import TransparentGroup
                node = self.addGroup(TransparentGroup, "DAZ Transparent")
                self.mixWithActive(alpha, tex, node)
            node.inputs["Color"].default_value[0:3] = WHITE
            if alpha < 1 or tex:
                self.material.setTransSettings(False, False, WHITE, alpha)
            LS.usedFeatures["Transparent"] = True

    #-------------------------------------------------------------
    #   Emission
    #-------------------------------------------------------------

    def buildEmission(self):
        if not GS.useEmission:
            return
        color = self.getColor("getChannelEmissionColor", BLACK)
        if not isBlack(color):
            from .cgroup import EmissionGroup
            self.column += 1
            emit = self.addGroup(EmissionGroup, "DAZ Emission")
            self.addEmitColor(emit, "Color")
            strength = self.getLuminance(emit)
            emit.inputs["Strength"].default_value = strength
            self.links.new(self.getCyclesSocket(), emit.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), emit.inputs["Eevee"])
            self.cycles = self.eevee = emit
            self.addOneSided()


    def addEmitColor(self, emit, slot):
        color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
        if tex is None:
            _,tex = self.getColorTex(["Luminance"], "COLOR", BLACK)
        temp = self.getValue(["Emission Temperature"], None)
        if temp is None:
            self.linkColor(tex, emit, color, slot)
            return
        elif temp == 0:
            temp = 6500
        blackbody = self.addNode("ShaderNodeBlackbody", self.column-2)
        blackbody.inputs["Temperature"].default_value = temp
        if isWhite(color) and tex is None:
            self.links.new(blackbody.outputs["Color"], emit.inputs[slot])
        else:
            mult = self.addNode("ShaderNodeMixRGB", self.column-1)
            mult.blend_type = 'MULTIPLY'
            mult.inputs[0].default_value = 1
            self.links.new(blackbody.outputs["Color"], mult.inputs[1])
            self.linkColor(tex, mult, color, 2)
            self.links.new(mult.outputs[0], emit.inputs[slot])


    def getLuminance(self, emit):
        lum = self.getValue(["Luminance"], 1500)
        # "cd/m^2", "kcd/m^2", "cd/ft^2", "cd/cm^2", "lm", "W"
        units = self.getValue(["Luminance Units"], 3)
        factors = [1, 1000, 10.764, 10000, 1, 1]
        strength = lum/2 * factors[units] / 15000
        if units >= 4:
            self.material.geoemit.append(emit.inputs["Strength"])
            if units == 5:
                strength *= self.getValue(["Luminous Efficacy"], 1)
        return strength


    def addOneSided(self):
        twosided = self.getValue(["Two Sided Light"], False)
        if not twosided:
            from .cgroup import OneSidedGroup
            node = self.addGroup(OneSidedGroup, "DAZ One-Sided")
            self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
            self.cycles = self.eevee = node

    #-------------------------------------------------------------
    #   Volume
    #-------------------------------------------------------------

    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)


    def buildVolume(self):
        if (self.material.isThinWall() or
            self.pureMetal or
            not GS.useVolume):
            return
        self.volume = None
        if self.isEnabled("Translucency"):
            transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
            sssmode, ssscolor, ssstex = self.getSSSInfo(transcolor)
            if self.isEnabled("Transmission"):
                self.buildVolumeTransmission(transcolor, transtex)
            if self.isEnabled("Subsurface"):
                self.buildVolumeSubSurface(sssmode, ssscolor, ssstex)
        if self.volume:
            self.volume.width = 240
            LS.usedFeatures["Volume"] = True


    def getSSSInfo(self, transcolor):
        if self.material.shader == 'UBER_IRAY':
            sssmode = self.getValue(["SSS Mode"], 0)
        elif self.material.shader == 'PBRSKIN':
            sssmode = 1
        else:
            sssmode = 0
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            ssscolor,ssstex = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            return 1, ssscolor, ssstex
        else:
            return 0, WHITE, None


    def buildVolumeTransmission(self, transcolor, transtex):
        from .cgroup import VolumeGroup
        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
        if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
            self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            self.volume.inputs["Absorbtion Density"].default_value = 100/dist
            self.linkColor(transtex, self.volume, transcolor, "Absorbtion Color")


    def buildVolumeSubSurface(self, sssmode, ssscolor, ssstex):
        from .cgroup import VolumeGroup
        if self.material.shader == 'UBER_IRAY':
            factor = 50
        else:
            factor = 25

        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue(["Scattering Measurement Distance"], 0.0)
        if not (sssmode == 0 or isBlack(ssscolor) or isWhite(ssscolor) or dist == 0.0):
            color,tex = self.invertColor(ssscolor, ssstex, 6)
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            sss,tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            color = (sss,sss,sss)
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)

    #-------------------------------------------------------------
    #   Output
    #-------------------------------------------------------------

    def buildOutput(self):
        self.column += 1
        output = self.addNode("ShaderNodeOutputMaterial")
        output.target = 'ALL'
        if self.cycles:
            self.links.new(self.getCyclesSocket(), output.inputs["Surface"])
        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])
        if self.displacement:
            self.links.new(self.displacement, output.inputs["Displacement"])
        if self.volume or self.eevee:
            output.target = 'CYCLES'
            outputEevee = self.addNode("ShaderNodeOutputMaterial")
            outputEevee.target = 'EEVEE'
            if self.eevee:
                self.links.new(self.getEeveeSocket(), outputEevee.inputs["Surface"])
            elif self.cycles:
                self.links.new(self.getCyclesSocket(), outputEevee.inputs["Surface"])
            if self.displacement:
                self.links.new(self.displacement, outputEevee.inputs["Displacement"])


    def buildDisplacementNodes(self):
        channel = self.material.getChannelDisplacement()
        if not( channel and
                self.isEnabled("Displacement") and
                GS.useDisplacement):
            return
        tex = self.addTexImageNode(channel, "NONE", False)
        if tex:
            strength = self.material.getChannelValue(channel, 1)
            if strength == 0:
                return
            dmin = self.getValue("getChannelDispMin", -0.05)
            dmax = self.getValue("getChannelDispMax", 0.05)
            if dmin > dmax:
                tmp = dmin
                dmin = dmax
                dmax = tmp

            from .cgroup import DisplacementGroup
            node = self.addGroup(DisplacementGroup, "DAZ Displacement")
            self.links.new(tex.outputs[0], node.inputs["Texture"])
            node.inputs["Strength"].default_value = strength
            node.inputs["Max"].default_value = LS.scale * dmax
            node.inputs["Min"].default_value = LS.scale * dmin
            self.linkNormal(node)
            self.displacement = node.outputs["Displacement"]
            mat = self.material.rna
            mat.cycles.displacement_method = 'BOTH'


    def addSingleTexture(self, col, asset, map, colorSpace):
        if asset is None:
            from .material import srgbToLinearCorrect
            texnode = self.addNode("ShaderNodeRGB", col)
            if colorSpace == "COLOR":
                color = srgbToLinearCorrect(map.color)
            else:
                color = map.color
            texnode.outputs["Color"].default_value[0:3] = color
            return None, texnode, texnode, False

        isnew = False
        img = asset.buildCycles(colorSpace)
        if img:
            imgname = img.name
        else:
            imgname = asset.getName()
        texnode = self.getTexNode(imgname, colorSpace)
        if asset.hasMapping(map):
            innode = texnode = outnode = self.addTextureNode(col, img, map.label, colorSpace)
            data = asset.getImageMapping(img, self.material, map)
            mapping = self.addMappingNode(data, None)
            if mapping:
                innode.extension = 'CLIP'
                self.linkVector(mapping, innode)
                innode = mapping
            if map.invert:
                color,outnode = self.invertColor(map.color, outnode, col+1)
            return innode, texnode, outnode, True
        elif texnode:
            return texnode, texnode, texnode, False
        else:
            texnode = self.addTextureNode(col, img, imgname, colorSpace)
            self.setTexNode(imgname, texnode, colorSpace)
            return texnode, texnode, texnode, True


    def addTextureNode(self, col, img, imgname, colorSpace):
        node = self.addNode("ShaderNodeTexImage", col)
        node.image = img
        node.interpolation = GS.imageInterpolation
        node.label = imgname.rsplit("/",1)[-1]
        self.setColorSpace(node, colorSpace)
        node.name = imgname
        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1
        return node


    def setColorSpace(self, node, colorSpace):
        if hasattr(node, "color_space"):
            node.color_space = colorSpace


    def addImageTexNode(self, filepath, tname, col):
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        img.colorspace_settings.name = "Non-Color"
        return self.addTextureNode(col, img, tname, "NONE")


    def getTexNode(self, key, colorSpace):
        if key in self.texnodes.keys():
            for texnode,colorSpace1 in self.texnodes[key]:
                if colorSpace1 == colorSpace:
                    return texnode
        return None


    def setTexNode(self, key, texnode, colorSpace):
        if key not in self.texnodes.keys():
            self.texnodes[key] = []
        self.texnodes[key].append((texnode, colorSpace))


    def linkVector(self, texco, node, slot="Vector"):
        if (isinstance(texco, bpy.types.NodeSocketVector) or
            isinstance(texco, bpy.types.NodeSocketFloat)):
            self.links.new(texco, node.inputs[slot])
            return
        if "Vector" in texco.outputs.keys():
            self.links.new(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.links.new(texco.outputs["UV"], node.inputs[slot])


    def addTexImageNode(self, channel, colorSpace, isMask):
        col = self.column-2
        assets,maps = self.material.getTextures(channel)
        if len(assets) == 0:
            return None
        elif len(assets) == 1:
            innode,texnode,outnode,isnew = self.addSingleTexture(col, assets[0], maps[0], colorSpace)
            if self.isDecal:
                texnode.extension = 'CLIP'
                self.clipsocket = texnode.outputs["Alpha"]
            if isnew:
                self.linkVector(self.texco, innode)
            return outnode

        from .cgroup import LayeredGroup
        if "image" in channel.keys():
            name = unquote(channel["image"])
        else:
            name = "Layered"
        if name in self.layeredGroups.keys() and name != "Layered":
            return self.layeredGroups[name]
        else:
            node = self.addNode("ShaderNodeGroup", col)
            node.width = 240
            node.label = name
            group = LayeredGroup()
            group.create(node, name, self)
            self.linkVector(self.texco, node)
            group.addTextureNodes(assets, maps, colorSpace, isMask)
            node.inputs["Influence"].default_value = 1.0
            self.layeredGroups[name] = node
            return node


    def mixTexs(self, op, tex1, tex2, slot1=0, slot2=0, color1=None, color2=None, fac=1, factex=None):
        if fac < 1 or factex:
            pass
        elif tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1
        mix = self.addNode("ShaderNodeMixRGB", self.column-1)
        mix.blend_type = op
        mix.use_alpha = False
        mix.inputs[0].default_value = fac
        if factex:
            self.links.new(factex.outputs[0], mix.inputs[0])
        if color1:
            mix.inputs[1].default_value[0:3] = color1
        if tex1:
            self.links.new(tex1.outputs[slot1], mix.inputs[1])
        if color2:
            mix.inputs[2].default_value[0:3] = color2
        if tex2:
            self.links.new(tex2.outputs[slot2], mix.inputs[2])
        return mix


    def mixWithActive(self, fac, tex, shader, useAlpha=False, keep=False):
        if shader.type != 'GROUP':
            raise RuntimeError("BUG: mixWithActive", shader.type)
        shader.inputs["Fac"].default_value = 1.0
        if tex:
            if useAlpha and "Alpha" in tex.outputs.keys():
                texsocket = tex.outputs["Alpha"]
            else:
                texsocket = tex.outputs[0]
            self.links.new(texsocket, shader.inputs["Fac"])
        elif fac == 0 and not keep:
            return
        elif fac == 1 and not keep:
            self.cycles = shader
            self.eevee = shader
            return
        if self.eevee:
            self.links.new(self.getEeveeSocket(), shader.inputs["Eevee"])
            shader.inputs["Fac"].default_value = fac
        self.eevee = shader
        if self.cycles:
            self.links.new(self.getCyclesSocket(), shader.inputs["Cycles"])
            shader.inputs["Fac"].default_value = fac
        self.cycles = shader


    def linkColor(self, tex, node, color, slot=0):
        node.inputs[slot].default_value[0:3] = color
        if tex:
            tex = self.multiplyVectorTex(color, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def linkScalar(self, tex, node, value, slot):
        node.inputs[slot].default_value = value
        if tex:
            tex = self.multiplyScalarTex(value, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def addSlot(self, channel, node, slot, value, value0, invert, isMask=False):
        node.inputs[slot].default_value = value
        tex = self.addTexImageNode(channel, "NONE", isMask)
        if tex:
            tex = self.fixTex(tex, value0, invert)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def fixTex(self, tex, value, invert):
        _,tex = self.multiplySomeTex(value, tex)
        if invert:
            return self.invertTex(tex, 3)
        else:
            return tex


    def invertTex(self, tex, col):
        if tex:
            inv = self.addNode("ShaderNodeInvert", col)
            self.links.new(tex.outputs[0], inv.inputs["Color"])
            return inv
        else:
            return None


    def multiplySomeTex(self, value, tex, slot=0):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, slot)
        elif tex:
            tex = self.multiplyVectorTex(value, tex, slot)
        return value,tex


    def multiplyVectorTex(self, color, tex, slot=0, col=None):
        if isWhite(color):
            return tex
        elif isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mix = self.addNode("ShaderNodeMixRGB", col)
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value[0:3] = color
        self.links.new(tex.outputs[0], mix.inputs[2])
        return mix


    def multiplyScalarTex(self, value, tex, slot=0, col=None):
        if value == 1:
            return tex
        elif value == 0:
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.links.new(tex.outputs[slot], mult.inputs[1])
        return mult


    def multiplyAddScalarTex(self, factor, term, tex, slot=0, col=None):
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
        try:
            mult.operation = 'MULTIPLY_ADD'
            ok = True
        except TypeError:
            ok = False
        if ok:
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            mult.inputs[2].default_value = term
            return mult
        else:
            mult.operation = 'MULTIPLY'
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            add = self.addNode("ShaderNodeMath", col)
            add.operation = 'ADD'
            add.inputs[1].default_value = term
            self.links.new(mult.outputs[slot], add.inputs[0])
            return add


    def multiplyTexs(self, tex1, tex2):
        if tex1 and tex2:
            mult = self.addNode("ShaderNodeMath")
            mult.operation = 'MULTIPLY'
            self.links.new(tex1.outputs[0], mult.inputs[0])
            self.links.new(tex2.outputs[0], mult.inputs[1])
            return mult
        elif tex1:
            return tex1
        else:
            return tex2


    def selectDiffuse(self, marked):
        if self.diffuseTex and marked[self.diffuseTex.name]:
            self.diffuseTex.select = True
            self.nodes.active = self.diffuseTex


    def getLink(self, node, slot):
        for link in self.links:
            if (link.to_node == node and
                link.to_socket.name == slot):
                return link
        return None


    def removeLink(self, node, slot):
        link = self.getLink(node, slot)
        if link:
           self.links.remove(link)


    def replaceSlot(self, node, slot, value):
        node.inputs[slot].default_value = value
        self.removeLink(node, slot)

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def findTree(mat):
    tree = CyclesTree(None)
    tree.nodes = mat.node_tree.nodes
    tree.links = mat.node_tree.links
    return tree


def findTexco(tree, col=None):
    nodes = findNodes(tree, "TEX_COORD")
    if nodes:
        return nodes[0]
    elif col is not None:
        return tree.addNode("ShaderNodeTexCoord", col)


def findNodes(tree, nodeType):
    nodes = []
    for node in tree.nodes.values():
        if node.type == nodeType:
            nodes.append(node)
    return nodes


def findNode(tree, ntypes):
    if isinstance(ntypes, list):
        for ntype in ntypes:
            node = findNode(tree, ntype)
            if node:
                return node
    for node in tree.nodes:
        if node.type == ntypes:
            return node
    return None


def findLinksFrom(tree, ntype):
    links = []
    for link in tree.links:
        if link.from_node.type == ntype:
            links.append(link)
    return links


def findLinksTo(tree, ntype):
    links = []
    for link in tree.links:
        if link.to_node.type == ntype:
            links.append(link)
    return links


def getLinkTo(tree, node, slot):
    for link in tree.links:
        if (link.to_node == node and
            link.to_socket.name == slot):
            return link
    return None


def pruneNodeTree(tree):
    marked = {}
    output = False
    for node in tree.nodes:
        marked[node.name] = False
        if "Output" in node.name:
            marked[node.name] = True
            output = True
    if not output:
        print("No output node")
        return marked
    nmarked = 0
    n = 1
    while n > nmarked:
        nmarked = n
        n = 1
        for link in tree.links:
            if marked[link.to_node.name]:
                marked[link.from_node.name] = True
                n += 1

    for node in tree.nodes:
        node.select = False
        if not marked[node.name]:
            tree.nodes.remove(node)
    return marked


