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
import os
from mathutils import Vector, Matrix, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .tree import Tree, NCOLUMNS, XSIZE, YSIZE
from .tree import findNodes, findNode, getLinkFrom, getLinkTo, pruneNodeTree, hideAllBut
from .error import DazError
from .utils import *

#-------------------------------------------------------------
#   Cycles material
#-------------------------------------------------------------

class CyclesMaterial(Material):

    def __init__(self, fileref):
        Material.__init__(self, fileref)
        self.tree = None
        self.mappingNodes = []


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
        from .finger import isGenesis
        color = LS.clothesColor
        mat = self.rna
        mtype = 'CLOTHES'
        if isinstance(self.geometry, GeoNode):
            ob = self.geometry.rna
        else:
            ob = self.mesh
        if ob is None:
            pass
        elif isGenesis(ob):
            color = LS.skinColor
            mtype = 'SKIN'
        elif (ob.data and
              (ob.data.DazGraftGroup or not ob.data.vertices)):
            color = LS.skinColor
            mtype = 'SKIN'
        guessMaterialColor(mat, GS.viewportColors, False, color, mtype)


    def build(self, context):
        if not Material.build(self, context):
            return
        self.tree = self.setupTree()
        self.tree.build()


    def getFromMaterial(self, context, mat):
        Material.build(self, context)
        self.rna = mat
        self.tree = self.setupTree()
        self.tree.getFromMaterial(mat)


    def setupTree(self):
        from .pbr import PbrTree
        from .brick import CyclesBrickTree, PbrBrickTree
        if self.isHair():
            from .hair import getHairTree
            geo = self.geometry
            if geo and geo.isStrandHair:
                geo.hairMaterials.append(self)
            return getHairTree(self)
        elif self.shader == 'BRICK':
            if LS.materialMethod == 'BSDF':
                return CyclesBrickTree(self)
            else:
                return PbrBrickTree(self)
        else:
            if LS.materialMethod == 'BSDF':
                return CyclesTree(self)
            else:
                return PbrTree(self)


    def postbuild(self):
        Material.postbuild(self)
        for key,node,data in self.mappingNodes:
            print("Fix mapping", key)
            dx,dy,sx,sy,rz = data
            node.inputs["Location"].default_value = (dx,dy,0)
            node.inputs["Rotation"].default_value = (0,0,rz)
            node.inputs["Scale"].default_value = (sx,sy,1)
        if self.tree:
            self.tree.postbuild()


    def addGeoBump(self, tex, socket):
        bumpmin = self.getValue("getChannelBumpMin", -0.01)
        bumpmax = self.getValue("getChannelBumpMax", 0.01)
        socket.default_value = (bumpmax-bumpmin) * LS.scale
        key = tex.name
        if key not in self.geobump.keys():
            self.geobump[key] = (tex, [])
        self.geobump[key][1].append(socket)


    def correctBumpArea(self, geo, me):
        if not self.geobump:
            return
        area = geo.getBumpArea(me, self.geobump.keys())
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
                x,y,z = scale.default_value
                if x != 0 and y != 0:
                    density /= x*y
                if density == 0.0:
                    continue
            if density > 0:
                height = 3.0/math.sqrt(density)
            for socket in sockets:
                socket.default_value = height


    def correctEmitArea(self, ob, mnum):
        if not self.geoemit:
            return
        me = ob.data
        me2 = me.copy()
        ob.data = me2
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
        if useRefraction is None and mat.blend_method != 'OPAQUE':
            pass
        elif useBlend:
            mat.blend_method = 'BLEND'
            mat.show_transparent_back = False
        else:
            mat.blend_method = 'HASHED'
        if useRefraction is not None:
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

class CyclesTree(Tree):
    def __init__(self, cmat):
        Tree.__init__(self, cmat)
        self.nodeTreeType = "ShaderNodeTree"
        self.nodeGroupType = "ShaderNodeGroup"
        self.cycles = None
        self.column = 1
        self.texnodes = {}
        self.layeredGroups = {}
        self.inShell = False
        self.isDecal = False

        self.diffuseInput = None
        self.diffuseColor = WHITE
        self.diffuse = None
        self.diffuseTex = None
        self.normal = None
        self.normalval = 0.0
        self.normaltex = None
        self.bump = None
        self.bumpval = 0
        self.bumptex = None
        self.texco = None
        self.uvnodes = {}
        self.detrough = 0
        self.detroughtex = None
        self.displacement = None
        self.volume = None
        self.emit = None
        self.clipsocket = None
        self.useCutout = False
        self.pureMetal = False


    def isEnabled(self, channel):
        return self.owner.enabled[channel]


    def getColor(self, channel, default):
        return self.owner.getColor(channel, default)


    def getTexco(self, uv):
        key = self.owner.getUvSet(uv, self.uvnodes)
        node = None
        if key is None:
            return node,self.texco
        elif key not in self.uvnodes.keys():
            self.uvnodes[key] = self.addUvNode(key)
        return self.uvnodes[key]


    def getCyclesSocket(self, node=None):
        if node is None:
            node = self.cycles
        if node is None:
            return None
        elif "BSDF" in node.outputs.keys():
            return node.outputs["BSDF"]
        else:
            return node.outputs[0]


    def linkCycles(self, node, slot):
        if self.cycles:
            self.links.new(self.getCyclesSocket(), node.inputs[slot])


    def addShellGroup(self, shell, push):
        shmat = shell.material
        shmat.isShellMat = True
        shname = shell.name
        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
            shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.owner.name))
            return None
        node = self.addNode("ShaderNodeGroup", size=15)
        node.width = 240
        nname = ("%s_%s" % (shname, self.owner.name))
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
        shell.tree = node.node_tree
        shmat.tree = CyclesTree(shmat)
        shmat.tree.nodes = shell.tree.nodes
        shmat.tree.links = shell.tree.links
        shmat.geometry = self.owner.geometry
        return node


    def getShellGroup(self, shmat, push):
        from .cgroup import OpaqueShellCyclesGroup, RefractiveShellCyclesGroup
        if shmat.isRefractive():
            return RefractiveShellCyclesGroup(push)
        else:
            return OpaqueShellCyclesGroup(push)


    def build(self):
        self.makeTree()
        self.column = 3
        self.buildLayers()
        self.buildCutout()
        if self.owner.useVolume:
            self.buildVolume()
        self.buildDisplacementNodes()
        self.buildDecals()
        self.buildShells()
        self.buildOutput()
        if GS.useUnusedTextures:
            self.buildUnusedTextures()


    def buildLayers(self):
        self.buildLayer("")


    def buildDecals(self):
        if not self.owner.decals:
            return
        if self.owner.isShellMat:
            raise RuntimeError("BUG buildDecals: %s" % self)
        from .cgroup import MappingGroup
        decals = [(inst.getValue(["Priority"],0), n, inst) for n,inst in enumerate(self.owner.decals)]
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
            self.addColumn()
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
                    self.linkCycles(node, "BSDF")
                    if csys == 2:
                        self.links.new(mapping.outputs["Depth Mask"], node.inputs["Influence"])
                    self.links.new(mapping.outputs["Vector"], node.inputs["UV"])
                    self.cycles = node


    def addDecalGroup(self, dmat):
        node = self.addNode("ShaderNodeGroup", size=15)
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
        if (LS.materialMethod == 'SINGLE_PRINCIPLED' or
            GS.shellMethod != 'MATERIAL'):
            return
        shells = []
        n = 0
        for shell in self.owner.shells.values():
            for geonode in shell.geometry.nodes.values():
                shells.append((geonode.push, n, shell))
                n += 1
        shells.sort()
        if shells:
            self.addColumn()
        if self.owner.geometry:
            geo = self.owner.geometry.data
            uvs = geo.uv_sets
        else:
            uvs = {}
        for push,n,shell in shells:
            node = self.addShellGroup(shell, push)
            if node:
                self.linkCycles(node, "BSDF")
                uvnode,uvsocket = self.getTexco(shell.uv)
                self.links.new(uvsocket, node.inputs["UV"])
                if self.displacement:
                    self.links.new(self.displacement, node.inputs["Displacement"])
                self.cycles = node
                self.displacement = node.outputs["Displacement"]


    def buildLayer(self, uvname):
        self.buildNormal(uvname)
        self.buildBump(uvname)
        self.buildDetail(uvname)
        self.column = 4
        if self.owner.useTranslucency:
            self.buildTranslucency(uvname)
        self.buildDiffuse()
        if not self.owner.useTranslucency:
            self.buildSubsurface()
        self.buildMakeup()
        self.buildOverlay()
        self.buildFlakes()
        self.prepareWeighted()
        self.buildGlossyOrDualLobe()
        self.buildMetal()
        self.buildTopCoat(uvname)
        if self.owner.isRefractive():
            self.buildRefraction()
        self.buildWeighted()
        self.buildEmission()


    def makeTree(self):
        mat = self.owner.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        return self.addTexco("UV")


    def getFromMaterial(self, mat):
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.texco = findTexco(self)
        self.normal = findNode(self, 'NORMAL_MAP')
        self.bump = findNode(self, 'BUMP')


    def getOutputs(self, grpnames):
        def getFromNode(self, node, slot):
            link = getLinkTo(self, node, slot)
            if link:
                return link.from_node
            else:
                return None

        def getToSocket(self, node, slot):
            link = getLinkFrom(self, node, slot)
            if link:
                return link.to_node, link.to_socket
            else:
                return None, None

        nodes = findNodes(self, 'GROUP')
        for idx,grpname in enumerate(grpnames):
            for node in nodes:
                if node.node_tree.name == grpname:
                    self.cycles = getFromNode(self, node, "BSDF")
                    if idx == 0:
                        tonode,cycles = getToSocket(self, node, "BSDF")
                    else:
                        cycles = node.inputs["BSDF"]
                        tonode = node
                    if cycles:
                        print("FOUND", grpname, idx)
                        if tonode:
                            self.column = int(tonode.location[0] // XSIZE)
                        if idx != 0:
                            self.ycoords = NCOLUMNS*[6*YSIZE]
                        return cycles

        cycles = None
        nodes = findNodes(self, 'OUTPUT_MATERIAL')
        for node in nodes:
            #node.location[0] += 3*XSIZE
            self.column = int(node.location[0] // XSIZE)
            self.cycles = getFromNode(self, node, "Surface")
            cycles = node.inputs["Surface"]
        self.ycoords = NCOLUMNS*[6*YSIZE]
        return cycles


    def linkToOutputs(self, cycles):
        if self.cycles:
            self.links.new(self.getCyclesSocket(), cycles)


    def addTexco(self, slot):
        if self.owner.uvNodeType == 'TEXCO' or not self.owner.uv_set:
            node = self.addNode("ShaderNodeTexCoord", size=2)
            node.hide = True
            hideAllBut(node, ["UV"])
            self.texco = node.outputs[slot]
        else:
            node, self.texco = self.addUvNode(self.owner.uv_set.name)
        self.tileTexco()
        return node


    def tileTexco(self):
        ox = self.getValue("getChannelHorizontalOffset", 0)
        oy = self.getValue("getChannelVerticalOffset", 0)
        kx = self.getValue("getChannelHorizontalTiles", 1)
        ky = self.getValue("getChannelVerticalTiles", 1)
        self.mapTexco(ox, oy, kx, ky)


    def addUvNode(self, uvname):
        if self.owner.uvNodeType == 'ATTRIBUTE':
            node = self.addNode("ShaderNodeAttribute", size=2)
            node.attribute_type == 'OBJECT'
            node.attribute_name = uvname
            node.label = uvname
            node.hide = True
            return node, node.outputs["Vector"]
        else:
            node = self.addNode("ShaderNodeUVMap", size=2)
            node.uv_map = uvname
            node.label = uvname
            node.hide = True
            return node, node.outputs["UV"]


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
            modulo,mapping = self.addMappingNode((dx,dy,sx,sy,0), None)
            if mapping:
                self.linkVector(self.texco, modulo, 0)
                self.texco = mapping


    def addMappingNode(self, data, map, imgname=""):
        dx,dy,sx,sy,rz = data
        if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            modulo = self.addNode("ShaderNodeVectorMath", 1, size=2)
            modulo.operation = 'MODULO'
            modulo.hide = True
            modulo.inputs[1].default_value = (1,1,1)
            mapping = self.addNode("ShaderNodeMapping", 1)
            mapping.vector_type = 'TEXTURE'
            self.links.new(modulo.outputs[0], mapping.inputs[0])
            mapping.inputs['Location'].default_value = (dx,dy,0)
            mapping.inputs['Scale'].default_value = (sx,sy,1)
            mapping.inputs['Rotation'].default_value = (0,0,rz)
            if map and not map.invert and hasattr(mapping, "use_min"):
                mapping.use_min = mapping.use_max = 1
            key = "%s:%s" % (self.owner.name, imgname)
            self.owner.mappingNodes.append((key, mapping, data))
            return modulo,mapping
        else:
            return None,None

    #-------------------------------------------------------------
    #   Normal Map
    #-------------------------------------------------------------

    def buildNormal(self, uvname):
        if self.isEnabled("Normal"):
            strength,tex,_ = self.getColorTex("getChannelNormal", "NONE", 1.0, useFactor=False)
            if strength>0 and tex:
                self.normal = self.buildNormalMap(strength, tex, uvname)
                self.normalval = strength
                self.normaltex = tex

        if GS.useAutoSmooth and self.getValue(["Smooth On"], False):
            rad = self.getValue(["Round Corners Radius"], 0) * 100 * LS.scale
            if rad != 0:
                node = self.addNode("ShaderNodeBevel", size=7)
                node.samples = 32
                node.inputs["Radius"].default_value = rad
                self.linkNormal(node)
                self.normal = node


    def buildNormalMap(self, strength, tex, uvname, col=None):
        if col is None:
            col = self.column
        normal = self.addNode("ShaderNodeNormalMap", size=7)
        normal.space = "TANGENT"
        if uvname:
            normal.uv_map = uvname
        elif self.owner.uv_set:
            normal.uv_map = self.owner.uv_set.name
        normal.inputs["Strength"].default_value = strength
        self.links.new(self.colorOutput(tex), normal.inputs["Color"])
        return normal


    def addOverlay(self, fac, factex, col=None):
        from .material import NORMAL
        if col is None:
            col = self.column-1
        mix,a,b,out = self.addMixRgbNode('OVERLAY', col)
        self.linkScalar(factex, mix, fac, 0)
        a.default_value = NORMAL
        b.default_value = NORMAL
        return mix,a,b,out

    #-------------------------------------------------------------
    #   Bump
    #-------------------------------------------------------------

    def buildBump(self, uvname):
        if not self.isEnabled("Bump"):
            return
        bumpmode = self.owner.getLayeredValue(["Bump Mode"], 0)
        if bumpmode == 0:
            self.bumpval,self.bumptex,_ = self.getColorTex("getChannelBump", "NONE", 0, False)
            if self.bumpval and self.bumptex:
                self.bump = self.buildBumpMap(self.bumpval, self.bumptex)
                self.linkNormal(self.bump)
        elif bumpmode == 1:
            strength,tex,_ = self.getColorTex("getChannelBump", "NONE", 0, False)
            if strength>0 and tex:
                self.normal = self.buildNormalMap(strength, tex, uvname)


    def buildBumpMap(self, bumpval, bumptex, col=None):
        if col == None:
            col = self.column
        bump = self.addNode("ShaderNodeBump", size=8)
        bump.inputs["Strength"].default_value = bumpval
        self.links.new(self.colorOutput(bumptex), bump.inputs["Height"])
        self.owner.addGeoBump(bumptex, bump.inputs["Distance"])
        return bump


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
        if (not self.isEnabled("Detail") or
            not self.getValue(["Detail Weight"], 0)):
            return
        weight,wttex,texslot = self.getColorTex(["Detail Weight"], "NONE", 0.0, isMask=True)
        texco = self.texco
        ox = LS.scale*self.getValue(["Detail Horizontal Offset"], 0)
        oy = LS.scale*self.getValue(["Detail Vertical Offset"], 0)
        kx = self.getValue(["Detail Horizontal Tiles"], 1)
        ky = self.getValue(["Detail Vertical Tiles"], 1)
        self.mapTexco(ox, oy, kx, ky)

        strength,tex,_ = self.getColorTex(["Detail Normal Map"], "NONE", 1.0, useFactor=False)
        weight = weight*strength
        mode = self.getValue(["Detail Normal Map Mode"], 0)
        if weight == 0 or tex is None:
            pass
        elif mode == 0:
            # Height Map
            if self.bump:
                link = getLinkTo(self, self.bump, "Height")
                if link:
                    mult = self.addNode("ShaderNodeMath", size=8)
                    mult.operation = 'MULTIPLY_ADD'
                    self.links.new(self.colorOutput(tex), mult.inputs[0])
                    self.linkScalar(wttex, mult, weight, 1)
                    self.links.new(link.from_socket, mult.inputs[2])
                    self.links.new(mult.outputs["Value"], self.bump.inputs["Height"])
            else:
                tex = self.multiplyTexs(tex, wttex)
                self.bump = self.buildBumpMap(weight, tex)
                self.linkNormal(self.bump)
        elif mode == 1:
            # Normal Map
            if self.normal:
                link = getLinkTo(self, self.normal, "Color")
                if link:
                    strength = self.normal.inputs["Strength"].default_value
                    if strength != 1.0:
                        _,a,b,socket = self.addOverlay(strength, None)
                        self.links.new(link.from_socket, b)
                        self.normal.inputs["Strength"].default_value = 1.0
                    else:
                        socket = link.from_socket
                    node,a,b,out = self.addOverlay(weight, wttex)
                    self.links.new(socket, a)
                    if tex:
                        self.links.new(self.colorOutput(tex), b)
                    self.links.new(out, self.normal.inputs["Color"])
                    self.normaltex = node
                else:
                    self.links.new(self.colorOutput(tex), self.normal.inputs["Color"])
            else:
                self.normal = self.buildNormalMap(weight, tex, uvname)
                if wttex:
                    self.links.new(self.colorOutput(wttex), self.normal.inputs["Strength"])
                if self.bump:
                    self.links.new(self.normal.outputs["Normal"], self.bump.inputs["Normal"])

        self.detrough, self.detroughtex,_ = self.getColorTex(["Detail Specular Roughness Mult"], "NONE", 0, False)
        self.texco = texco

    #-------------------------------------------------------------
    #   Color effect
    #-------------------------------------------------------------

    def buildColorEffect(self, value, color, tex, tint, fac, factex, node, facslot="Fac", colorslot="Color"):
        # [ "Scatter Only", "Scatter & Transmit", "Scatter & Transmit Intensity" ]
        if fac == 0:
            return None
        elif value == 0:     # Scatter Only
            if facslot:
                self.linkScalar(factex, node, fac, facslot)
            if colorslot:
                return self.linkColor(tex, node, color, colorslot)
        else:
            from .cgroup import ColorEffectGroup
            effect = self.addGroup(ColorEffectGroup, "DAZ Color Effect", col=self.column-1)
            if tint is None:
                tint = WHITE
            effect.inputs["Tint"].default_value[0:3] = tint
            self.linkScalar(factex, effect, fac, "Fac")
            colorInput = self.linkColor(tex, effect, color, "Color")
            self.moveTex(tex, effect)
            outfac = {
                1:  "Transmit Fac", # Scatter & Transmit
                2:  "Intensity Fac" # Scatter & Transmit Intensity
            }
            if facslot:
                node.inputs[facslot].default_value = fac
                self.links.new(effect.outputs[outfac[value]], node.inputs[facslot])
            if colorslot:
                node.inputs[colorslot].default_value[0:3] = color
                self.links.new(effect.outputs["Color"], node.inputs[colorslot])
            return effect


    def compProd(self, x, y):
        return [x[0]*y[0], x[1]*y[1], x[2]*y[2]]

    #-------------------------------------------------------------
    #   Diffuse
    #-------------------------------------------------------------

    def getDiffuseColor(self):
        color,tex,_ = self.getColorTex("getChannelDiffuse", "COLOR", WHITE)
        self.diffuseColor = color
        self.diffuseTex = findTextureNode(tex)
        return color,tex


    def buildDiffuse(self):
        if not self.isEnabled("Diffuse"):
            return
        from .cgroup import DiffuseGroup
        self.addColumn()
        color,tex = self.getDiffuseColor()
        fac,factex = self.getFacFromTranslucency()
        if fac == 0:
            return
        self.diffuse = self.addGroup(DiffuseGroup, "DAZ Diffuse")
        tint = self.getColor(["SSS Reflectance Tint"], WHITE)
        effect = self.getValue(["Base Color Effect"], 0)
        self.diffuseInput = self.buildColorEffect(effect, color, tex, tint, fac, factex, self.diffuse)
        if self.cycles:
            self.links.new(self.cycles.outputs["BSDF"], self.diffuse.inputs["BSDF"])
        self.cycles = self.diffuse
        roughness,roughtex,_ = self.getColorTex(["Diffuse Roughness"], "NONE", 0, False)
        if self.isEnabled("Detail"):
            roughness *= self.detrough
            roughtex = self.multiplyTexs(self.detroughtex, roughtex)
        self.setRoughness(self.diffuse, "Roughness", roughness, roughtex)
        self.linkBumpNormal(self.diffuse)
        LS.usedFeatures["Diffuse"] = True


    def getFacFromTranslucency(self):
        if self.owner.useTranslucency:
            wt,wttex,texslot = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
            if wt == 1.0 and not wttex:
                return 0,None
            elif wttex:
                mix = self.addNode("ShaderNodeMath", self.column-2, size=8)
                mix.operation = 'MULTIPLY_ADD'
                self.linkScalar(wttex, mix, wt, 0)
                mix.inputs[1].default_value = -1
                mix.inputs[2].default_value = 1
                return 1,mix
            else:
                return 1-wt,None
        else:
            return 1,None

    #-------------------------------------------------------------
    #   Diffuse Overlay
    #-------------------------------------------------------------

    def buildOverlay(self):
        if (not self.getValue(["Diffuse Overlay Weight"], 0) or
            LS.materialMethod == 'SINGLE_PRINCIPLED'):
            return False
        self.addColumn()
        fac,factex,texslot = self.getColorTex(["Diffuse Overlay Weight"], "NONE", 0, isMask=True)
        if self.getValue(["Diffuse Overlay Weight Squared"], False):
            power = 4
        else:
            power = 2
        if factex:
            factex = self.raiseToPower(factex, power, texslot)
            texslot = 0
        color,tex,_ = self.getColorTex(["Diffuse Overlay Color"], "COLOR", WHITE)
        from .cgroup import DiffuseGroup
        node = self.addGroup(DiffuseGroup, "DAZ Overlay")
        effect = self.getValue(["Diffuse Overlay Color Effect"], 0)
        self.buildColorEffect(effect, color, tex, None, fac, factex, node)
        roughness,roughtex,_ = self.getColorTex(["Diffuse Overlay Roughness"], "NONE", 0, False)
        self.setRoughness(node, "Roughness", roughness, roughtex)
        self.linkBumpNormal(node)
        self.mixWithActive(fac**power, factex, texslot, node, effect=effect)
        return True


    def getImageSlot(self, attr):
        if self.owner.getImageMod(attr, "grayscale_mode") == "alpha":
            return "Alpha"
        else:
            return 0


    def raiseToPower(self, tex, power, slot, col=None):
        if col is None:
            col = self.column-1
        node = self.addNode("ShaderNodeMath", col, size=8)
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if slot in tex.outputs.keys():
            socket = tex.outputs[slot]
        else:
            socket = self.colorOutput(tex)
        self.links.new(socket, node.inputs[0])
        return node


    def getColorTex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None, isMask=False):
        texslot = self.getImageSlot(attr)
        channel = self.owner.getLayeredChannel(attr)
        if channel is None:
            return default,None,0
        if isinstance(channel, tuple):
            channel = channel[0]
        if useTex:
            tex = self.addTexImageNode(channel, colorSpace, texslot, isMask)
        else:
            tex = None
        if value is not None:
            pass
        elif channel["type"] in ["color", "float_color"]:
            value = self.owner.getChannelColor(channel, default)
        elif channel["type"] in ["image"]:
            if isVector(default):
                value = WHITE
            else:
                value = 1.0
        else:
            value = self.owner.getChannelValue(channel, default)
            if value < 0:
                return 0,None,0
        if useFactor:
            value,tex = self.multiplySomeTex(value, tex, texslot)
        if isVector(value) and not isVector(default):
            value = (value[0] + value[1] + value[2])/3
        if not isVector(value):
            if maxval and value > maxval:
                value = maxval
            if isVector(default):
                value = (value, value, value)
        return value,tex,texslot

    #-------------------------------------------------------------
    #  Makeup
    #-------------------------------------------------------------

    def buildMakeup(self):
        if (not self.isEnabled("Makeup") or
            not self.getValue(["Makeup Weight"], 0) or
            LS.materialMethod == 'SINGLE_PRINCIPLED'):
            return False
        from .cgroup import MakeupGroup
        self.addColumn()
        node = self.addGroup(MakeupGroup, "DAZ Makeup", size=10)
        color,tex,_ = self.getColorTex(["Makeup Base Color"], "COLOR", WHITE, False)
        self.linkColor(tex, node, color, "Color")
        roughness,roughtex,_ = self.getColorTex(["Makeup Roughness Mult"], "NONE", 0.0, False)
        self.linkScalar(roughtex, node, roughness, "Roughness")
        self.linkBumpNormal(node)
        wt,wttex,texslot = self.getColorTex(["Makeup Weight"], "NONE", 0.0, False, isMask=True)
        self.mixWithActive(wt, wttex, texslot, node)
        return True

    #-------------------------------------------------------------
    #  Flakes
    #-------------------------------------------------------------

    def buildFlakes(self):
        if (not self.isEnabled("Metallic Flakes") or
            not self.getValue(["Metallic Flakes Weight"], 0) or
            LS.materialMethod == 'SINGLE_PRINCIPLED'):
            return False
        from .cgroup import FlakesGroup
        self.addColumn()
        node = self.addGroup(FlakesGroup, "DAZ Flakes", size=12)
        color,tex,_ = self.getColorTex(["Metallic Flakes Color"], "COLOR", WHITE, False)
        fac,factex,texslot = self.getColorTex(["Metallic Flakes Weight"], "NONE", 0.0, False, isMask=True)
        effect = self.getValue(["Metallic Flakes Color Effect"], 0)
        self.buildColorEffect(effect, color, tex, None, fac, factex, node)
        roughness,roughtex,_ = self.getColorTex(["Metallic Flakes Roughness"], "NONE", 0.0, False)
        self.linkScalar(roughtex, node, roughness, "Roughness")
        size = max(0.01, self.getValue(["Metallic Flakes Size"], 1))
        density = self.getValue(["Metallic Flakes Density"], 0)
        if self.owner.shader == 'PBRSKIN':
            node.inputs["Strength"].default_value = 1
            node.inputs["Distance"].default_value = (size*0.005)/100
            node.inputs["Scale"].default_value = 20/(size*0.005)
            node.inputs["From Min"].default_value = (1-density)**2

        else:
            node.inputs["Strength"].default_value = self.getValue(["Metallic Flakes Strength"], 0)
            node.inputs["Distance"].default_value = size/100
            node.inputs["Scale"].default_value = 20/size
            node.inputs["From Min"].default_value = (1-density)**2
        self.linkBumpNormal(node)
        self.mixWithActive(fac, factex, texslot, node, effect=effect, keep=True)
        return True

    #-------------------------------------------------------------
    #  Dual Lobe
    #-------------------------------------------------------------

    def buildGlossyOrDualLobe(self):
        if self.isEnabled("Dual Lobe Specular"):
            dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
        else:
            dualLobeWeight = 0
        if dualLobeWeight == 1:
            self.buildDualLobe()
        elif dualLobeWeight == 0:
            self.buildGlossy()
        else:
            self.buildGlossy()
            self.buildDualLobe()


    def buildDualLobe(self):
        from .cgroup import DualLobeGroupUberIray, DualLobeGroupPbrSkin
        if not self.isEnabled("Dual Lobe Specular"):
            return
        self.addColumn()
        if self.owner.shader == 'PBRSKIN':
            node = self.addGroup(DualLobeGroupPbrSkin, "DAZ Dual Lobe PBR", size=10)
        else:
            node = self.addGroup(DualLobeGroupUberIray, "DAZ Dual Lobe", size=10)

        fac,factex,texslot = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 0.5, False, isMask=True)
        value,tex,_ = self.getColorTex(["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        node.inputs["IOR"].default_value = 1.1 + 0.7*value
        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.links.new(self.colorOutput(iortex), node.inputs["IOR"])

        if self.owner.shader == 'PBRSKIN':
            rough1,rough2,roughtex,ratio = self.getDualRoughness(0.0)
            self.setRoughness(node, "Roughness 1", rough1, roughtex)
            self.setRoughness(node, "Roughness 2", rough2, roughtex)
            ratio = 1 - ratio
        else:
            ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)
            rough1,roughtex1,_ = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 1", rough1, roughtex1)
            rough2,roughtex2,_ = self.getColorTex(["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 2", rough2, roughtex2)

        node.inputs["Ratio"].default_value = ratio
        self.linkBumpNormal(node)
        self.mixWithActive(fac, factex, texslot, node, keep=True)
        LS.usedFeatures["Glossy"] = True


    def getDualRoughness(self, default):
        roughness,roughtex,_ = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", default, False)
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
                self.owner.basemix == 0):
            return
        if self.getValue(["Metallic Weight"], 0) == 0:
            return
        from .cgroup import MetalGroupUber, MetalGroupPbrSkin
        self.addColumn()
        if self.owner.shader == 'PBRSKIN':
            node = self.addGroup(MetalGroupPbrSkin, "DAZ Metal PBR", size=10)
            self.linkColor(self.diffuseTex, node, self.diffuseColor, "Color")
            rough1,rough2,roughtex, ratio = self.getDualRoughness(0.0)
            self.setRoughness(node, "Roughness 1", rough1, roughtex)
            self.setRoughness(node, "Roughness 2", rough2, roughtex)
            node.inputs["Dual Ratio"].default_value = ratio
        else:
            node = self.addGroup(MetalGroupUber, "DAZ Metal", size=4)
            self.linkColor(self.diffuseTex, node, self.diffuseColor, "Color")
            roughness,roughtex,_ = self.getColorTex(["Glossy Roughness"], "NONE", 0)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            anisotropy,tex,_ = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
            self.linkScalar(tex, node, anisotropy, "Anisotropy")
            anirot,tex,_ = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            self.linkScalar(tex, node, 1 - anirot, "Rotation")

        node.inputs["Color"].default_value[0:3] = self.diffuseColor
        if self.diffuseInput:
            self.links.new(self.colorOutput(self.diffuseInput), node.inputs["Color"])
        self.linkBumpNormal(node)
        weight,wttex,texslot = self.getColorTex(["Metallic Weight"], "NONE", 0)
        self.mixWithActive(weight, wttex, texslot, node)
        if weight == 1 and wttex is None:
            self.pureMetal = True

    #-------------------------------------------------------------
    #   Glossy
    #-------------------------------------------------------------

    def buildGlossy(self):
        color = self.getColor("getChannelGlossyColor", BLACK)
        fac = self.getValue("getChannelGlossyLayeredWeight", 0)
        if isBlack(color) or fac == 0:
            return

        from .cgroup import GlossyGroup
        self.addColumn()
        glossy = self.addGroup(GlossyGroup, "DAZ Glossy", size=12)
        fac,factex,texslot = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 0)
        color,tex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, False)
        effect = self.getValue(["Glossy Color Effect"], 0)
        self.buildColorEffect(effect, color, tex, None, fac, factex, glossy)
        ior,iortex = self.getFresnelIOR()
        self.linkScalar(iortex, glossy, ior, "IOR")
        channel,value,roughness,invert = self.owner.getGlossyRoughness(0.0)
        roughtex = self.addSlot(channel, glossy, "Roughness", roughness, value, invert)
        anisotropy,tex,_ = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        self.linkScalar(tex, glossy, anisotropy, "Anisotropy")
        if anisotropy > 0:
            anirot,tex,_ = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 1 - anirot
            self.linkScalar(tex, glossy, value, "Rotation")
        self.linkBumpNormal(glossy)
        self.mixWithActive(fac, factex, texslot, glossy, effect=effect, keep=True)
        LS.usedFeatures["Glossy"] = True


    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
        ior = 1.45
        iortex = None
        if self.owner.shader == 'UBER_IRAY':
            if self.owner.basemix == 0:    # Metallic/Roughness
                value,tex,_ = self.getColorTex(["Glossy Reflectivity"], "NONE", 0, False)
                factor = 0.7 * value
                ior = 1.1 + factor
            elif self.owner.basemix == 1:  # Specular/Glossiness
                color,tex,_ = self.getColorTex(["Glossy Specular"], "COLOR", WHITE, False)
                factor = 0.7 * averageColor(color) / 0.078
                ior = 1.1 + factor
            elif self.owner.basemix == 2:  # Weighted
                ior = 10
                tex = None
            if tex:
                iortex = self.multiplyAddScalarTex(factor, 1.1, tex)
        return ior, iortex

    #-------------------------------------------------------------
    #   Weigthed
    #-------------------------------------------------------------

    def prepareWeighted(self):
        if (self.owner.basemix == 2 and
            LS.materialMethod != 'SINGLE_PRINCIPLED'):
            self.diffuseCycles = self.cycles
            self.cycles = None
            return True
        else:
            return False


    def buildWeighted(self):
        if (self.owner.basemix != 2 or
            LS.materialMethod == 'SINGLE_PRINCIPLED'):
            return False
        diffweight,difftex,_ = self.getColorTex(["Diffuse Weight"], "NONE", 0)
        glossweight,glosstex,texslot = self.getColorTex(["Glossy Weight"], "NONE", 0)
        if glossweight == 0:
            self.cycles = self.diffuseCycles
            return False
        if glossweight + diffweight == 0:
            fac = 1
        else:
            fac = glossweight / (glossweight + diffweight)
        if fac == 1 and difftex is None and glosstex is None:
            return False
        else:
            from .cgroup import WeightedGroup
            self.addColumn()
            node = self.addGroup(WeightedGroup, "DAZ Weighted", size=4)
            self.linkScalar(glosstex, node, fac, "Fac", texslot=texslot)
            if self.diffuseCycles:
                self.links.new(self.getCyclesSocket(self.diffuseCycles), node.inputs["Diffuse Cycles"])
            self.linkCycles(node, "Glossy Cycles")
            self.cycles = node
            return True

    #-------------------------------------------------------------
    #   Top Coat
    #-------------------------------------------------------------

    def checkTopCoat(self):
        return (LS.materialMethod != 'SINGLE_PRINCIPLED' and
                self.isEnabled("Top Coat") and
                self.getValue(["Top Coat Weight"], 0))


    def buildTopCoat(self, uvname):
        if not self.checkTopCoat():
            return
        fac,factex,texslot = self.getColorTex(["Top Coat Weight"], "NONE", 0)
        color,coltex,_ = self.getColorTex(["Top Coat Color"], "COLOR", WHITE)
        # Top Coat Layering Mode
        #   [ "Reflectivity", "Weighted", "Fresnel", "Custom Curve" ]
        spec0tex = spec90tex = powertex = None
        lmode = self.getValue(["Top Coat Layering Mode"], 0)
        if lmode == 0:      # Reflectivity
            refl,spec0tex,_ = self.getColorTex(["Reflectivity", "Top Coat Reflectivity"], "NONE", 0, useFactor=False)
            spec0 = 0.08 * refl
            spec90 = 1
            power = 5
        elif lmode == 1:    # Weighted
            spec0 = 1
            spec90 = 1
            power = 1
        elif lmode == 2:    # Fresnel
            ior,spec0tex,_ = self.getColorTex(["Top Coat IOR"], "NONE", 1.45)
            spec0 = ((ior-1)/(ior+1))**2
            spec90 = 0.5
            power = 5
        elif lmode == 3:    # Custom curve
            spec0,spec0tex,_ = self.getColorTex(["Top Coat Curve Normal"], "NONE", 1)
            spec90,spec90tex,_ = self.getColorTex(["Top Coat Curve Grazing"], "NONE", 1)
            power,powertex,_ = self.getColorTex(["Top Coat Curve Exponent"], "NONE", 1)

        bump = normal = None
        if self.owner.shader == 'UBER_IRAY':
            bumpmode = self.getValue(["Top Coat Bump Mode"], 0)
            bumpval,bumptex,_ = self.getColorTex(["Top Coat Bump"], "NONE", 0, useFactor=False)
            if bumptex is None:
                pass
            elif bumpmode == 0:   # Height map
                bump = self.mixBump(bumpmode, bumpval, bumptex)
            elif bumpmode == 1:   # Normal map
                normal = self.mixNormal(bumpmode, bumpval, bumptex, uvname)
        else:
            bumpval = self.getValue(["Top Coat Bump Weight"], 0)
            if self.bumptex:
                bump = self.buildBumpMap(bumpval*self.bumpval, self.bumptex)
                self.linkNormal(bump)

        roughness,roughtex,_ = self.getColorTex(["Top Coat Roughness"], "NONE", 0)
        if roughness == 0:
            glossiness,glosstex,_ = self.getColorTex(["Top Coat Glossiness"], "NONE", 1)
            roughness = 1 - glossiness**2
            roughtex = self.invertTex(glosstex, 5)
        aniso,anitex,_ = self.getColorTex(["Top Coat Anisotropy"], "NONE", 0)
        anirot,rottex,_ = self.getColorTex(["Top Coat Rotations"], "NONE", 0)

        from .cgroup import TopCoatGroup
        self.addColumn()
        top = self.addGroup(TopCoatGroup, "DAZ Top Coat", size=20)
        top.width = 200
        effect = self.getValue(["Top Coat Color Effect"], 0)
        self.buildColorEffect(effect, color, coltex, None, fac, factex, top)
        self.linkScalar(spec0tex, top, spec0, "Specular0")
        self.linkScalar(spec90tex, top, spec90, "Specular90")
        self.linkScalar(powertex, top, power, "Power")
        self.linkScalar(roughtex, top, roughness, "Roughness")
        self.linkScalar(anitex, top, aniso, "Anisotropy")
        self.linkScalar(rottex, top, 1 - anirot, "Rotation")
        if bump:
            self.links.new(bump.outputs["Normal"], top.inputs["Normal"])
        elif normal:
            self.links.new(normal.outputs["Normal"], top.inputs["Normal"])
        else:
            self.linkBumpNormal(top)
        self.mixWithActive(fac, factex, texslot, top, keep=True, effect=effect)


    def mixBump(self, bumpmode, bumpval, bumptex):
        bump = self.buildBumpMap(bumpval, bumptex)
        self.linkBumpNormal(bump)
        return bump


    def mixNormal(self, bumpmode, bumpval, bumptex, uvname):
        if self.normaltex:
            maxval = max(bumpval, self.normalval)
            if maxval > 1.0:
                normalbase,a,b,out = self.addOverlay(self.normalval/maxval, None)
                self.links.new(self.colorOutput(self.normaltex), b)
                mixval = bumpval/maxval
            else:
                normalbase = self.normaltex
                mixval = bumpval
            mix,a,b,out = self.addOverlay(mixval, None)
            mix.inputs[0].default_value = mixval
            self.links.new(self.colorOutput(normalbase), a)
            self.links.new(self.colorOutput(bumptex), b)
            bumptex = mix
        normal = self.buildNormalMap(bumpval, bumptex, uvname)
        if self.bumptex:
            bump = self.buildBumpMap(self.bumpval, self.bumptex)
            self.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
            return bump
        else:
            return normal

    #-------------------------------------------------------------
    #   Translucency
    #-------------------------------------------------------------

    def buildTranslucency(self, uvname):
        from .cgroup import TranslucentGroup
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        color = self.getColor(["Translucency Color"], BLACK)
        if fac == 0 or isBlack(color):
            return None
        node = self.addGroup(TranslucentGroup, "DAZ Translucent", size=8)
        node.inputs["Fac"].default_value = 1.0
        color,tex,_ = self.getColorTex(["Translucency Color"], "COLOR", BLACK)
        self.linkColor(tex, node, color, "Color")
        node.width = 200
        if self.getValue(["Invert Transmission Normal"], 0):
            normal = bump = None
            if self.normalval and self.normaltex:
                from .cgroup import InvertNormalMapGroup
                inv = self.addGroup(InvertNormalMapGroup, "DAZ Invert NMap", col=self.column-1)
                self.links.new(self.colorOutput(self.normaltex), inv.inputs["Color"])
                normal = self.buildNormalMap(self.normalval, inv, uvname, col=self.column-1)
                self.links.new(inv.outputs["Color"], normal.inputs["Color"])
            if self.bumpval and self.bumptex:
                inv = self.addNode("ShaderNodeInvert", col=self.column-1, size=5)
                inv.inputs["Fac"].default_value = 1.0
                self.links.new(self.colorOutput(self.bumptex), inv.inputs["Color"])
                bump = self.buildBumpMap(self.bumpval, inv, col=self.column-1)
                if normal:
                    self.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
            if bump:
                self.links.new(bump.outputs["Normal"], node.inputs["Normal"])
            elif normal:
                self.links.new(normal.outputs["Normal"], node.inputs["Normal"])
        else:
            self.linkBumpNormal(node)
        self.linkTranslucency(node)
        LS.usedFeatures["Transparent"] = True
        self.endSSS()
        return node


    def linkTranslucency(self, node):
        self.cycles = node

    #-------------------------------------------------------------
    #   Subsurface scattering
    #-------------------------------------------------------------

    def buildSubsurface(self):
        from .cgroup import SubsurfaceGroup
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        transcolor = self.getColor(["Translucency Color"], BLACK)
        if fac == 0 or isBlack(transcolor):
            return
        self.addColumn()
        transcolor,transtex,_ = self.getColorTex(["Translucency Color"], "COLOR", BLACK)
        transwt,wttex,texslot = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0, isMask=True)
        sss,ssscolor,ssstex,sssmode = self.getSSSColor()
        node = self.addGroup(SubsurfaceGroup, "DAZ Subsurface", size=14)
        node.inputs["Scale"].default_value = 1.0
        radius,radtex = self.getSSSRadius(transcolor, ssscolor, ssstex, sssmode)
        radius,ior,aniso = self.fixSSSRadius(radius)
        self.linkColor(radtex, node, radius, "Radius")
        node.inputs["IOR"].default_value = ior
        node.inputs["Anisotropy"].default_value = aniso
        node.width = 200
        self.column -= 1
        if GS.useAltSss:
            from .cgroup import AltSSSGroup
            fix = self.addGroup(AltSSSGroup, "DAZ Alt SSS")
            fix.inputs["Diffuse Color"].default_value[0:3] = self.diffuseColor
            if self.diffuseInput:
                self.links.new(self.colorOutput(self.diffuseInput), fix.inputs["Diffuse Color"])
            self.linkScalar(ssstex, fix, sss, "SSS Amount")
            self.linkColor(transtex, fix, transcolor, "Translucent Color")
            self.linkScalar(wttex, fix, transwt, "Translucency Weight")
            self.links.new(fix.outputs["Base Color"], self.diffuse.inputs["Color"])
            self.links.new(fix.outputs["Subsurface Color"], node.inputs["Color"])
            self.links.new(fix.outputs["Subsurface"], node.inputs["Fac"])
            self.linkCycles(node, "BSDF")
            self.cycles = node
        else:
            gamma = self.addNode("ShaderNodeGamma", size=7)
            gamma.inputs["Gamma"].default_value = 3.5
            self.linkColor(transtex, gamma, transcolor, "Color")
            self.links.new(gamma.outputs["Color"], node.inputs["Color"])
            self.mixWithActive(transwt, wttex, texslot, node)
        self.column += 1
        self.linkBumpNormal(node)
        LS.usedFeatures["Transparent"] = True
        self.endSSS()


    def getSSSColor(self):
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            color,tex,_ = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            sss = (color[0] + color[1] + color[2])/3
        elif sssmode == 0:
            sss,tex,_ = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            if sss > 1:
                sss = 1
            color = (sss,sss,sss)
        else:
            color,tex = WHITE,None
        return sss,color,tex,sssmode


    def endSSS(self):
        LS.usedFeatures["SSS"] = True
        mat = self.owner.rna
        if hasattr(mat, "use_sss_translucency"):
            mat.use_sss_translucency = True


    def getSSSRadius(self, color, ssscolor, ssstex, sssmode):
        # if there's no volume we use the sss to make translucency
        # please note that here we only use the iray base translucency color with no textures
        # as for blender 2.8x eevee doesn't support nodes in the radius channel so we deal with it
        if self.owner.isThinWall:
            return color,None

        if sssmode == 1 and isWhite(ssscolor):
            ssscolor = BLACK
        elif sssmode == 0:  # Mono
            s,ssstex,_ = self.getColorTex("getChannelSSSAmount", "NONE", 0)
            if s > 1:
                s = 1
            ssscolor = Vector((s,s,s))
        trans,transtex,_ = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
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


    def getRefractionColor(self):
        if self.getValue(["Share Glossy Inputs"], False):
            color,tex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
            roughness, roughtex,_ = self.getColorTex(["Glossy Roughness"], "NONE", 0, False, maxval=1)
        else:
            color,tex,_ = self.getColorTex("getChannelRefractionColor", "COLOR", WHITE)
            roughness,roughtex,_ = self.getColorTex(["Refraction Roughness"], "NONE", 0, False, maxval=1)
        return color, tex, roughness, roughtex


    def addInput(self, node, channel, slot, colorSpace, default, maxval=0):
        value,tex,_ = self.getColorTex(channel, colorSpace, default, maxval=maxval)
        if isVector(default):
            node.inputs[slot].default_value[0:3] = value
        else:
            node.inputs[slot].default_value = value
        if tex:
            self.links.new(self.colorOutput(tex), node.inputs[slot])
        return value,tex


    def setRoughness(self, node, slot, roughness, roughtex, square=True):
        node.inputs[slot].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(self.colorOutput(tex), node.inputs[slot])
        return roughness


    def buildRefraction(self):
        weight,wttex,texslot = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0)
        if weight == 0:
            return weight,wttex
        node,color = self.buildRefractionNode()
        self.mixWithActive(weight, wttex, texslot, node, keep=True)
        if (GS.useFakeCaustics and
            bpy.app.version < (3,4,0) and
            not self.inShell and
            not self.owner.isThinWall):
            from .cgroup import FakeCausticsGroup
            self.addColumn()
            node = self.addGroup(FakeCausticsGroup, "DAZ Fake Caustics", args=[color], force=True)
            self.mixWithActive(weight, wttex, texslot, node, keep=True)
        return weight,wttex


    def buildRefractionNode(self):
        from .cgroup import RefractionGroup, ThinWallGroup
        self.addColumn()
        ior,iortex,_ = self.getColorTex("getChannelIOR", "NONE", 1.45)
        thin = (self.owner.isThinWall or (ior == 1 and iortex is None))
        if thin:
            node = self.addGroup(ThinWallGroup, "DAZ Thin Wall", size=15)
        else:
            node = self.addGroup(RefractionGroup, "DAZ Refraction", size=15)
        node.width = 240

        color,tex,_ = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
        roughness, roughtex,_ = self.getColorTex(["Glossy Roughness"], "NONE", 0, False, maxval=1)
        self.linkColor(tex, node, color, "Glossy Color")
        self.linkScalar(roughtex, node, roughness, "Glossy Roughness")

        color,coltex,roughness,roughtex = self.getRefractionColor()
        aniso,anisotex,_ = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        if aniso > 0:
            roughness = roughness ** (1/(1+aniso))
        anirot,rottex,_ = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
        self.linkColor(coltex, node, color, "Refraction Color")

        if not thin:
            self.linkScalar(roughtex, node, roughness, "Refraction Roughness")
        self.linkScalar(iortex, node, ior, "IOR")
        self.linkScalar(anisotex, node, aniso, "Anisotropy")
        self.linkScalar(rottex, node, 1 - anirot, "Rotation")
        if thin:
            self.owner.setTransSettings(True, True, color, 0.1)
        else:
            self.owner.setTransSettings(True, False, color, 0.2)
        self.linkBumpNormal(node)
        return node, color


    def buildCutout(self):
        alpha,tex,texslot = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        if alpha < 1 or tex:
            self.addColumn()
            self.useCutout = True
            if alpha == 0:
                node = self.addNode("ShaderNodeBsdfTransparent", size=5)
                self.cycles = node
                tex = None
            else:
                from .cgroup import TransparentGroup
                node = self.addGroup(TransparentGroup, "DAZ Transparent")
                self.mixWithActive(alpha, tex, texslot, node)
            node.inputs["Color"].default_value[0:3] = WHITE
            if alpha < 1 or tex:
                self.owner.setTransSettings(None, False, WHITE, alpha)
            LS.usedFeatures["Transparent"] = True
            if self.emit and GS.useGhostLight:
                self.addColumn()
                from .cgroup import GhostLightGroup
                ghost = self.addGroup(GhostLightGroup, "DAZ Ghost Light")
                self.links.new(self.emit.outputs["BSDF"], ghost.inputs["Emission"])
                self.links.new(node.outputs["BSDF"], ghost.inputs["Transparent"])
                self.cycles = ghost

    #-------------------------------------------------------------
    #   Emission
    #-------------------------------------------------------------

    def buildEmission(self):
        if not GS.useEmission:
            return
        color = self.getColor("getChannelEmissionColor", BLACK)
        if not isBlack(color):
            from .cgroup import EmissionGroup
            self.addColumn()
            emit = self.addGroup(EmissionGroup, "DAZ Emission")
            self.addEmitColor(emit, "Color")
            socket = emit.inputs["Strength"]
            strength = self.getLuminance(socket)
            socket.default_value = strength
            self.linkCycles(emit, "BSDF")
            self.cycles = self.emit = emit
            self.addOneSided()


    def addEmitColor(self, emit, slot):
        color,tex,_ = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
        if tex is None:
            _,tex,_ = self.getColorTex(["Luminance"], "COLOR", BLACK)
        temp = self.getValue(["Emission Temperature"], None)
        if temp is None:
            self.linkColor(tex, emit, color, slot)
            return
        elif temp == 0:
            temp = 6500
        blackbody = self.addNode("ShaderNodeBlackbody", self.column-2, size=5)
        blackbody.inputs["Temperature"].default_value = temp
        if isWhite(color) and tex is None:
            self.links.new(blackbody.outputs["Color"], emit.inputs[slot])
        else:
            mult,a,b,out = self.addMixRgbNode('MULTIPLY', self.column-1)
            mult.inputs[0].default_value = 1
            self.links.new(blackbody.outputs["Color"], a)
            self.linkColor(tex, mult, color, self.MixColor2)
            self.links.new(out, emit.inputs[slot])


    def getLuminance(self, socket):
        lum = self.getValue(["Luminance"], 1500)
        # "cd/m^2", "kcd/m^2", "cd/ft^2", "cd/cm^2", "lm", "W"
        units = self.getValue(["Luminance Units"], 3)
        factors = [1, 1000, 10.764, 10000, 1, 1]
        strength = lum/2 * factors[units] / 15000
        if units >= 4:
            self.owner.geoemit.append(socket)
            if units == 5:
                strength *= self.getValue(["Luminous Efficacy"], 1)
        return strength


    def addOneSided(self):
        twosided = self.getValue(["Two Sided Light"], False)
        if not twosided:
            from .cgroup import OneSidedGroup
            node = self.addGroup(OneSidedGroup, "DAZ One-Sided", size=6)
            self.linkCycles(node, "BSDF")
            self.cycles = node

    #-------------------------------------------------------------
    #   Volume
    #-------------------------------------------------------------

    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)


    def buildVolume(self):
        if self.pureMetal:
            return
        self.volume = None
        if self.isEnabled("Translucency"):
            if self.isEnabled("Transmission"):
                self.buildVolumeTransmission()
            if self.isEnabled("Subsurface"):
                self.buildVolumeSubSurface()
        if self.volume:
            self.volume.width = 240
            LS.usedFeatures["Volume"] = True


    def buildVolumeTransmission(self):
        from .cgroup import VolumeGroup
        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
        if dist == 0:
            return
        color,tex,_ = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        if isBlack(color) or (isWhite(color) and tex is None):
            return
        self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
        self.volume.inputs["Absorbtion Density"].default_value = 200/dist
        self.linkColor(tex, self.volume, color, "Absorbtion Color")


    def buildVolumeSubSurface(self):
        from .cgroup import VolumeGroup, LogColorGroup
        dist = self.getValue(["Scattering Measurement Distance"], 0.0)
        if dist == 0:
            return
        if self.owner.shader == 'UBER_IRAY':
            sssmode = self.getValue(["SSS Mode"], 0)
        elif self.owner.shader == 'PBRSKIN':
            sssmode = 1
        else:
            sssmode = 0
        if sssmode == 0:    # Mono
            sss,tex,_ = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            if sss == 0:
                return
            color = (sss,sss,sss)
        elif sssmode == 1:  # Chromatic
            color,tex,_ = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            if isBlack(color) or (isWhite(color) and tex is None):
                return
            node = self.addGroup(LogColorGroup, "DAZ Log Color", col=self.column-1, size=6)
            self.linkColor(tex, node, color, "Color")
            tex = node
        if self.volume is None:
            self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
        self.volume.inputs["Scatter Color"].default_value[0:3] = color
        if tex:
            self.links.new(self.colorOutput(tex), self.volume.inputs["Scatter Color"])
        self.volume.inputs["Scatter Density"].default_value = 100/dist
        self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)

    #-------------------------------------------------------------
    #   Output
    #-------------------------------------------------------------

    def buildOutput(self):
        self.addColumn()
        output = self.addNode("ShaderNodeOutputMaterial")
        output.target = 'ALL'
        if self.cycles:
            self.links.new(self.getCyclesSocket(), output.inputs["Surface"])
        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])
        if self.displacement:
            self.links.new(self.displacement, output.inputs["Displacement"])
            mat = self.owner.rna
            mat.cycles.displacement_method = 'DISPLACEMENT'
        return output

    #-------------------------------------------------------------
    #   Displacment
    #-------------------------------------------------------------

    def buildDisplacementNodes(self):
        strength = self.owner.getDisplacementStrength()
        if strength == 0:
            return
        channel = self.owner.getChannelDisplacement()
        tex = self.addTexImageNode(channel, "NONE", 0, False)
        if tex:
            dmin = self.getValue("getChannelDispMin", -0.05)
            dmax = self.getValue("getChannelDispMax", 0.05)
            if dmin > dmax:
                tmp = dmin
                dmin = dmax
                dmax = tmp

            from .cgroup import DisplacementGroup
            node = self.addGroup(DisplacementGroup, "DAZ Displacement")
            self.links.new(self.colorOutput(tex), node.inputs["Texture"])
            node.inputs["Strength"].default_value = strength
            node.inputs["Max"].default_value = LS.scale * dmax
            node.inputs["Min"].default_value = LS.scale * dmin
            self.linkNormal(node)
            self.displacement = node.outputs["Displacement"]

    #-------------------------------------------------------------
    #   Unused Textures
    #-------------------------------------------------------------

    def buildUnusedTextures(self):
        def getColorSpace(key):
            noncolor = ["bump", "weight", "normal"]
            for word in noncolor:
                if word in key:
                    return "NONE"
            return "COLOR"

        def foundMatch(texnodes, inputs):
            for key in texnodes.keys():
                if key not in inputs.keys():
                    return False
            return True

        def getNodeGroup(texnodes):
            name = "Unused Textures"
            for group in bpy.data.node_groups:
                if (group.name.startswith(name) and
                    foundMatch(texnodes, group.inputs)):
                    return group
            group = bpy.data.node_groups.new(name, "ShaderNodeTree")
            for key in texnodes.keys():
                group.inputs.new("NodeSocketColor", key)
            return group

        self.column += 2
        texnodes = {}
        for key,channel in self.owner.channels.items():
            if key not in self.owner.usedChannels.keys():
                colorspace = getColorSpace(key.lower())
                texnode = self.addTexImageNode(channel, colorspace, 0, False)
                if texnode:
                    texnodes[key] = texnode
        if texnodes:
            node = self.addNode("ShaderNodeGroup", size=2*len(texnodes))
            node.width = 400
            group = getNodeGroup(texnodes)
            node.node_tree = group
            node.name = node.label = group.name
            for key,texnode in texnodes.items():
                self.links.new(texnode.outputs["Color"], node.inputs[key])

    #-------------------------------------------------------------
    #   Textures
    #-------------------------------------------------------------

    def addSingleTexture(self, col, asset, map, colorSpace):
        if asset is None:
            from .material import srgbToLinearCorrect
            texnode = self.addNode("ShaderNodeRGB", col, size=10)
            if colorSpace == "COLOR":
                color = srgbToLinearCorrect(map.color)
            else:
                color = map.color
            texnode.outputs["Color"].default_value[0:3] = color
            return None, texnode, texnode, False

        img,imgname = asset.buildImage(colorSpace)
        texnode,outnode = self.getTexNode(imgname, colorSpace)
        if texnode:
            isnew = False
        else:
            texnode = outnode = self.addTextureNode(col, img, imgname)
            self.setTexNode(imgname, texnode, outnode, "COLOR")
            if colorSpace in ["COLOR", "NONE"]:
                gamma = self.addGamma(col, texnode, "Linear", 1/2.2)
                self.setTexNode(imgname, texnode, gamma, "NONE")
                if colorSpace == "NONE":
                    outnode = gamma
            isnew = True

        innode = texnode
        if asset.hasMapping(map):
            data = asset.getImageMapping(img, self.owner, map)
            modulo,mapping = self.addMappingNode(data, None, imgname)
            if mapping:
                innode.extension = 'CLIP'
                self.linkVector(mapping, innode)
                innode = modulo
            if map.invert:
                color,outnode = self.invertColor(map.color, outnode, col+1)
        return innode, texnode, outnode, isnew


    def addGamma(self, col, texnode, label, value):
        gamma = self.addNode("ShaderNodeGamma", col=col, size=2)
        gamma.label = label
        gamma.inputs["Gamma"].default_value = value
        self.links.new(texnode.outputs["Color"], gamma.inputs["Color"])
        gamma.hide = True
        return gamma


    def addTextureNode(self, col, img, imgname, size=2):
        node = self.addNode("ShaderNodeTexImage", col, size=size)
        node.image = img
        node.interpolation = GS.imageInterpolation
        node.label = imgname.rsplit("/",1)[-1]
        node.name = imgname
        node.hide = True
        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1
        return node


    def getTexNode(self, key, colorSpace):
        nodes = self.texnodes.get(key, {})
        return nodes.get(colorSpace, (None,None))


    def setTexNode(self, key, texnode, outnode, colorSpace):
        if key not in self.texnodes.keys():
            self.texnodes[key] = {}
        self.texnodes[key][colorSpace] = (texnode, outnode)


    def linkVector(self, texco, node, slot="Vector"):
        if (isinstance(texco, bpy.types.NodeSocketVector) or
            isinstance(texco, bpy.types.NodeSocketFloat)):
            self.links.new(texco, node.inputs[slot])
            return
        if "Vector" in texco.outputs.keys():
            self.links.new(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.links.new(texco.outputs["UV"], node.inputs[slot])


    def addTexImageNode(self, channel, colorSpace, texslot, isMask):
        col = self.column-1
        assets,maps = self.owner.getTextures(channel)
        if len(assets) == 0:
            return None
        elif len(assets) == 1:
            innode,texnode,outnode,isnew = self.addSingleTexture(col, assets[0], maps[0], colorSpace)
            if self.isDecal:
                texnode.extension = 'CLIP'
                self.clipsocket = texnode.outputs["Alpha"]
            if isnew:
                self.linkVector(self.texco, innode)
            if texslot == "Alpha":
                return texnode
            else:
                return outnode

        from .cgroup import LayeredGroup
        if "image" in channel.keys():
            name = unquote(channel["image"])
            if name[0] == "#":
                name = name[1:]
            name = "LIE %s" % name
            if name in self.layeredGroups.keys():
                return self.layeredGroups[name]
        else:
            name = "LIE Layered"
        node = self.addNode("ShaderNodeGroup", col)
        tree = LS.layeredGroups.get(name)
        if tree:
            node.node_tree = tree
        else:
            group = LayeredGroup()
            group.create(node, name, self)
            group.addTextureNodes(assets, maps, colorSpace, isMask)
            if name != "LIE Layered":
                LS.layeredGroups[name] = node.node_tree
        node.width = 240
        node.label = name
        self.linkVector(self.texco, node)
        node.inputs["Influence"].default_value = 1.0
        self.layeredGroups[name] = node
        return node


    def mixTexs(self, op, tex1, tex2, color1=None, color2=None, fac=1, factex=None):
        if fac < 1 or factex:
            pass
        elif tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1
        mix,a,b,out = self.addMixRgbNode(op, self.column-2)
        #mix.use_alpha = False
        mix.inputs[0].default_value = fac
        if factex:
            self.links.new(self.colorOutput(factex), mix.inputs[0])
        if color1:
            a.default_value[0:3] = color1
        if tex1:
            self.links.new(self.colorOutput(tex1), a)
        if color2:
            b.default_value[0:3] = color2
        if tex2:
            self.links.new(self.colorOutput(tex2), b)
        return mix


    def mixWithActive(self, fac, factex, texslot, node, keep=False, effect=0):
        if node.type != 'GROUP':
            raise RuntimeError("BUG: mixWithActive", node.type)
        node.inputs["Fac"].default_value = fac
        if effect or factex or keep:
            pass
        elif fac == 0:
            return
        elif fac == 1:
            self.cycles = node
            return
        if self.cycles:
            self.links.new(self.getCyclesSocket(), node.inputs["BSDF"])
            if not effect:
                self.linkScalar(factex, node, fac, "Fac", texslot=texslot)
        self.cycles = node


    def linkColor(self, tex, node, color, slot):
        node.inputs[slot].default_value[0:3] = color
        if tex:
            tex = self.multiplyVectorTex(color, tex)
            if tex:
                self.links.new(self.colorOutput(tex), node.inputs[slot])
        return tex


    def linkScalar(self, tex, node, value, slot, texslot=None):
        node.inputs[slot].default_value = value
        if tex:
            tex = self.multiplyScalarTex(value, tex)
            if tex:
                if texslot:
                    self.links.new(tex.outputs[texslot], node.inputs[slot])
                else:
                    self.links.new(self.colorOutput(tex), node.inputs[slot])
        return tex


    def addSlot(self, channel, node, slot, value, value0, invert, isMask=False):
        node.inputs[slot].default_value = value
        tex = self.addTexImageNode(channel, "NONE", 0, isMask)
        if tex:
            _,tex = self.multiplySomeTex(value0, tex)
            if invert:
                tex = self.invertTex(tex, 3)
            if tex:
                self.links.new(self.colorOutput(tex), node.inputs[slot])
        return tex


    def invertTex(self, tex, col):
        if tex:
            inv = self.addNode("ShaderNodeInvert", col, size=5)
            self.links.new(self.colorOutput(tex), inv.inputs["Color"])
            return inv
        else:
            return None


    def multiplySomeTex(self, value, tex, slot=None):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, slot)
        elif tex:
            tex = self.multiplyVectorTex(value, tex, slot)
        return value,tex


    def multiplyVectorTex(self, color, tex, slot=None, col=None):
        if isWhite(color):
            return tex
        elif isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GAMMA', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mult,a,b,out = self.addMixRgbNode('MULTIPLY', col)
        mult.inputs[0].default_value = 1.0
        a.default_value[0:3] = color
        self.linkSlot(tex, slot, b)
        self.moveTex(tex, mult)
        return mult


    def linkSlot(self, tex, slot, socket):
        if slot == "Alpha":
            if tex.type == "GAMMA":
                tex = tex.inputs["Color"].links[0].from_node
            if tex.type == "TEX_IMAGE":
                self.links.new(tex.outputs["Alpha"], socket)
            else:
                self.links.new(self.colorOutput(tex), socket)
        else:
            self.links.new(self.colorOutput(tex), socket)


    def multiplyScalarTex(self, value, tex, slot=None, col=None, force=False):
        if value == 1:
            return tex
        elif value == 0 or tex is None:
            return None
        elif (not force and tex.type not in ['TEX_IMAGE', 'GAMMA', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col, size=8)
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.linkSlot(tex, slot, mult.inputs[1])
        self.moveTex(tex, mult)
        return mult


    def multiplyAddScalarTex(self, factor, term, tex, slot=None, col=None):
        if tex is None:
            return None
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col, size=8)
        mult.operation = 'MULTIPLY_ADD'
        self.linkSlot(tex, slot, mult.inputs[0])
        mult.inputs[1].default_value = factor
        mult.inputs[2].default_value = term
        self.moveTex(tex, mult)
        return mult


    def multiplyTexs(self, tex1, tex2, operation='MULTIPLY'):
        if tex1 and tex2:
            mult = self.addNode("ShaderNodeMath", size=8)
            mult.operation = operation
            self.links.new(self.colorOutput(tex1), mult.inputs[0])
            self.links.new(self.colorOutput(tex2), mult.inputs[1])
            self.moveTex(tex1, mult)
            self.moveTex(tex2, mult)
            return mult
        elif tex1:
            return tex1
        else:
            return tex2


    def postbuild(self):
        if GS.usePruneNodes:
            from .geometry import getActiveUvLayer
            active = None
            if self.owner.geometry:
                ob = self.owner.geometry.rna
                if ob:
                    active = getActiveUvLayer(ob)
            difftexname = diffname = None
            if self.diffuseTex:
                difftexname = self.diffuseTex.name
            if self.diffuse:
                diffname = self.diffuse.name
            marked = pruneNodeTree(self, active)
            hasDiffuseTex = difftexname and marked.get(difftexname)
            hasDiffuse = diffname and marked.get(diffname)
        else:
            hasDiffuseTex = self.diffuseTex
            hasDiffuse = self.diffuse
        for node in self.nodes:
            node.select = False
        if hasDiffuseTex:
            try:
                self.diffuseTex.select = True
                self.nodes.active = self.diffuseTex
            except UnicodeDecodeError:
                print("Illegal diffuse texture in %s:\n %s" % (self.owner.name, self.diffuseTex))
                self.diffuseTex = None
        elif hasDiffuse:
            self.diffuse.select = True
            self.nodes.active = self.diffuse


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

def findMaterial(mat):
    dmat = CyclesMaterial(None)
    dmat.setupBasics()
    dmat.rna = mat
    dmat.tree = tree = findTree(mat)
    tree.owner = dmat
    return dmat


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
        node = tree.addNode("ShaderNodeTexCoord", col, size=2)
        node.hide = True
        hideAllBut(node, ["UV"])
        return node


def findTextureNode(tex):
    if tex is None:
        return None
    elif tex.type == "TEX_IMAGE":
        return tex
    for inp in tex.inputs:
        if inp.type == "RGBA":
            for link in inp.links:
                tex2 = findTextureNode(link.from_node)
                if tex2:
                    return tex2
    return None


def makeCyclesTree(mat):
    cmat = CyclesMaterial("")
    ctree = CyclesTree(cmat)
    ctree.nodes = mat.node_tree.nodes
    ctree.links = mat.node_tree.links
    ctree.column = 0
    return ctree

