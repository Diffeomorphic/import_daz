# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

import os
import copy
from collections import OrderedDict

from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from mathutils import Vector, Matrix

WHITE = Vector((1.0,1.0,1.0))
GREY = Vector((0.5,0.5,0.5))
BLACK = Vector((0.0,0.0,0.0))
NORMAL = (0.5, 0.5, 1, 1)

#-------------------------------------------------------------
#   Materials
#-------------------------------------------------------------

class Material(Asset, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.scene = None
        self.shader = 'UBER_IRAY'
        self.textures = OrderedDict()
        self.groups = []
        self.ignore = False
        self.force = False
        self.partial = False
        self.shells = {}
        self.geometry = None
        self.mesh = None
        self.geoemit = []
        self.geobump = {}
        self.decals = []
        self.uv_set = None
        self.uv_sets = {}
        self.uvNodeType = 'TEXCO'
        self.udim = 0
        self.basemix = 0
        self.isShellMat = False
        self.enabled = {}
        self.decalNode = None
        self.layer = None


    def __repr__(self):
        return ("<Material %s %s %s %s>" % (self.id, self.shader, self.geometry.name, self.rna))


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)


    def addToGeoNode(self, geonode):
        if GS.useMaterialsByIndex:
            key = self.name
        else:
            key = skipName(self.name)
        if key in geonode.materials.keys():
            msg = ("Duplicate geonode material: %s\n" % key +
                   "  %s\n" % geonode +
                   "  %s\n" % geonode.materials[key] +
                   "  %s" % self)
            reportError(msg)
        geonode.materials[key] = self
        self.geometry = geonode


    def update(self, struct):
        from .geometry import Geometry, GeoNode
        Asset.update(self, struct)
        Channels.update(self, struct)
        geo = geonode = None
        if LS.useGeometries and "geometry" in struct.keys():
            ref = struct["geometry"]
            geo = self.getAsset(ref)
            if isinstance(geo, GeoNode):
                geonode = geo
                geo = geonode.data
            elif isinstance(geo, Geometry):
                iref = instRef(ref)
                if iref in geo.nodes.keys():
                    geonode = geo.nodes[iref]
            if geonode:
                self.addToGeoNode(geonode)
        if LS.useGeometries and "uv_set" in struct.keys():
            from .geometry import Uvset
            uvset = self.getTypedAsset(struct["uv_set"], Uvset)
            if uvset:
                if geo:
                    geo.uv_sets[uvset.name] = uvset
                self.uvNodeType = 'UVMAP'
                self.uv_set = uvset


    def copyShellBasics(self, dmat):
        self.basemix = dmat.basemix
        self.useVolume = dmat.useVolume
        self.useTranslucency = dmat.useTranslucency
        self.isThinWall = dmat.isThinWall
        self.enabled = dmat.enabled
        self.rna = dmat.rna


    def setupBasics(self):
        self.basemix = self.getValue(["Base Mixing"], 0)
        #  "PBR Metallicity/Roughness", "PBR Specular/Glossiness", "Weighted"
        self.useVolume = False
        self.useTranslucency = True
        self.isThinWall = self.getValue(["Thin Walled"], False)

        if self.shader == 'UBER_IRAY':
            self.enabled = {
                "Diffuse" : True,
                "Subsurface" : True,
                "Bump" : True,
                "Normal" : True,
                "Displacement" : True,
                "Metallicity" : True,
                "Translucency" : True,
                "Transmission" : True,
                "Dual Lobe Specular" : True,
                "Top Coat" : True,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : True,
                "Velvet" : False,
            }
            self.useTranslucency = (
                self.getValue("getChannelTranslucencyWeight", 1) != 0)
            self.useVolume = (
                self.getValue("getChannelTranslucencyWeight", 1) != 0 or
                self.getValue("getChannelRefractionWeight", 1) != 0)

        elif self.shader == 'PBRSKIN':
            self.enabled = {
                "Diffuse" : self.getValue(["Diffuse Enable"], False),
                "Subsurface" : self.getValue(["Sub Surface Enable"], False),
                "Bump" : self.getValue(["Bump Enable"], False),
                "Normal" : self.getValue(["Bump Enable"], False),
                "Displacement" : True,
                "Metallicity" : self.getValue(["Metallicity Enable"], False),
                "Translucency" : self.getValue(["Translucency Enable"], False),
                "Transmission" : self.getValue(["Transmission Enable"], False),
                "Dual Lobe Specular" : self.getValue(["Dual Lobe Specular Enable"], False),
                "Top Coat" : self.getValue(["Top Coat Enable"], False),
                "Makeup" : self.getValue(["Makeup Enable"], False),
                "Specular Occlusion" : self.getValue(["Specular Occlusion Enable"], False),
                "Detail" : self.getValue(["Detail Enable"], False),
                "Metallic Flakes" : self.getValue(["Metallic Flakes Enable"], False),
                "Velvet" : False,
            }
            self.useTranslucency = (
                self.enabled["Translucency"] and
                self.getValue("getChannelTranslucencyWeight", 1) != 0)
            self.useVolume = self.useTranslucency

        elif self.shader == 'DAZ_SHADER':
            self.enabled = {
                "Diffuse" : self.getValue(["Diffuse Active"], False),
                "Subsurface" : self.getValue(["Subsurface Active"], False),
                "Bump" : self.getValue(["Bump Active"], False),
                "Normal" : False,
                "Displacement" : self.getValue(["Displacement Active"], False),
                "Metallicity" : self.getValue(["Metallicity Active"], False),
                "Translucency" : self.getValue(["Translucency Active"], False),
                "Transmission" : not self.getValue(["Opacity Active"], False),
                "Dual Lobe Specular" : False,
                "Top Coat" : False,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : False,
                "Velvet" : not self.getValue(["Velvet Active"], False),
            }

        elif self.shader == 'TOON':
            self.enabled = {
                "Diffuse" : True,
                "Subsurface" : False,
                "Bump" : True,
                "Normal" : True,
                "Displacement" : True,
                "Metallicity" : False,
                "Translucency" : False,
                "Transmission" : False,
                "Dual Lobe Specular" : False,
                "Top Coat" : False,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : False,
                "Velvet" : False,
        }

        elif self.shader == 'BRICK':
            self.enabled = {
                "Diffuse" : True,
                "Subsurface" : True,
                "Bump" : True,
                "Normal" : True,
                "Displacement" : True,
                "Metallicity" : False,
                "Translucency" : True,
                "Transmission" : True,
                "Dual Lobe Specular" : False,
                "Top Coat" : False,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : False,
                "Velvet" : True,
        }
        else:
            raise DazError("Bug: Unknown shader %s" % self.shader)

        if not GS.useVolume:
            self.useTranslucency = False
            self.useVolume = False
        elif LS.materialMethod == 'BSDF':
            if GS.skinMethod != 'IRAY' and self.isVoluSkinMaterial():
                self.useTranslucency = False
                self.useVolume = False
            if self.isThinWall:
                self.useVolume = False
        elif LS.materialMethod == 'EXTENDED_PRINCIPLED':
            self.useVolume = False
            if self.isVoluSkinMaterial():
                self.useTranslucency = False
            elif self.isVolume():
                self.useVolume = True
        elif LS.materialMethod == 'FBX_COMPATIBLE':
            self.useTranslucency = False
            self.useVolume = False


    def isRefractive(self):
        return ((self.getValue("getChannelRefractionWeight", 0) != 0 or
                 self.getValue("getChannelOpacity", 1) != 1))


    def isPureRefractive(self):
        return (self.isPure("getChannelRefractionWeight", 0, 1) or
                self.isPure("getChannelOpacity", 1, 0))


    def isVolume(self):
        return ((self.getValue("getChannelRefractionWeight", 0) == 1 or
                 self.getValue("getChannelOpacity", 1) == 0) and
                self.getValue("getChannelIOR", 1) == 1 and
                not self.isThinWall and
                (self.getValue(["Transmitted Measurement Distance"], 0.0) or
                 self.getValue(["Scattering Measurement Distance"], 0.0)))


    def isPure(self, attr, default, value):
        channel = self.getChannel(attr)
        return (self.getChannelValue(channel, default) == value and
                not self.hasTextures(channel))


    def isHair(self):
        if "Root Transmission Color" in self.channels.keys():
            if GS.onHairMaterial == 'HAIR':
                return True
            elif GS.onHairMaterial == 'NORMAL':
                return False
            elif self.geometry and self.geometry.data:
                return (len(self.geometry.data.faces) == 0)
            else:
                return True
        return False


    def isVoluSkinMaterial(self):
        if (self.getValue("getChannelTranslucencyWeight", 1) == 0 or
            not self.enabled["Translucency"] or
            not self.enabled["Transmission"] or
            not self.enabled["Subsurface"] or
            self.getValue("getChannelCutoutOpacity", 1) != 1):
            return False
        color = self.getValue(["Transmitted Color"], BLACK)
        dist = self.getValue(["Transmitted Measurement Distance"], 0)
        if isBlack(color) or isWhite(color) or dist == 0:
            return False
        dist = self.getValue(["Scattering Measurement Distance"], 0)
        if dist == 0:
            return False
        sssmode = self.getValue(["SSS Mode"], 0)
        if sssmode == 0:    # Mono
            if self.getValue(["SSS Amount"], 1) == 0:
                return False
        elif sssmode == 1:  # Chromatic
            color = self.getValue("getChannelSSSColor", BLACK)
            if isBlack(color) or isWhite(color):
                return False
        return True


    def setExtra(self, struct):
        if struct["type"] == "studio/material/uber_iray":
            self.shader = 'UBER_IRAY'
        elif struct["type"] == "studio/material/daz_brick":
            shadername = unquote(self.url.rsplit("#",1)[-1])
            if shadername == "PBRSkin":
                self.shader = 'PBRSKIN'
            elif shadername.startswith("FilaToon"):
                self.shader = 'TOON'
            elif shadername in ["Blended Dual Lobe Hair", "4-Layer Uber PBR MDL"]:
                self.shader = 'BRICK'
            else:
                self.shader = 'BRICK'
                self.addUnsupportedShader(shadername)
        elif struct["type"] == "studio/material/daz_shader":
            self.shader = 'DAZ_SHADER'
            if "definition" in struct.keys():
                shadername = struct["definition"]
                self.addUnsupportedShader(shadername)
        elif struct["type"].startswith("studio/material/"):
            n = len("studio/material/")
            shadername = struct["type"][n:]
            table = {
                "strand_hair_rsl" : "RSL Strand Shader",
            }
            shadername = table.get(shadername, shadername)
            self.addUnsupportedShader(shadername)


    def addUnsupportedShader(self, shadername):
        if shadername not in LS.shaders.keys():
            LS.shaders[shadername] = []
        LS.shaders[shadername].append(self.name)



    def getSSSMethod(self):
        from .guess import getMatType
        geonode = self.geometry
        if geonode and geonode.data:
            geo = geonode.data
        else:
            geo = None
        if BLENDER3:
            if GS.sssMethod == 'BURLEY_SKIN':
                mtype = getMatType(self.name, geo)
                return ('RANDOM_WALK' if mtype == 'SKIN' else 'BURLEY')
            elif GS.sssMethod == 'RANDOM_WALK_SKIN':
                return 'RANDOM_WALK'
            else:
                return GS.sssMethod
        else:
            if GS.sssMethod == 'BURLEY_SKIN':
                mtype = getMatType(self.name, geo)
                return ('RANDOM_WALK_SKIN' if mtype == 'SKIN' else 'BURLEY')
            elif GS.sssMethod == 'RANDOM_WALK_FIXED_RADIUS':
                return 'RANDOM_WALK'
            else:
                return GS.sssMethod


    def build(self, context):
        from .geometry import Geometry, GeoNode
        self.setupBasics()
        if self.dontBuild():
            return False
        if GS.verbosity >= 3:
            print("Build material '%s'" % self.name)
        mat = self.rna
        if mat is None:
            mat = self.rna = bpy.data.materials.new(self.name)
            setModernProps(mat)
            LS.materials[self.name] = mat

        if GS.useStoreMaterialMapping:
            mat["Horizonal Offset"] = self.getValue("getChannelHorizontalOffset", 0.0)
            mat["Vertical Offset"] = self.getValue("getChannelVerticalOffset", 0.0)
            mat["Horizonal Tiles"] = self.getValue("getChannelHorizontalTiles", 1)
            mat["Vertical Tiles"] = self.getValue("getChannelVerticalTiles", 1)

        scn = self.scene = context.scene
        dazRna(mat).DazShader = self.shader
        if self.uv_set:
            self.uv_sets[self.uv_set.name] = self.uv_set
        geonode = self.geometry
        if (isinstance(geonode, GeoNode) and
            geonode.data and
            geonode.data.uv_sets):
            for uv,uvset in geonode.data.uv_sets.items():
                if uvset:
                    self.uv_sets[uv] = self.uv_sets[uvset.name] = uvset
        for shell in self.shells.values():
            pass
            #shell.material.shader = self.shader
        if GS.verbosity >= 3:
            print("Material '%s' built" % self.name)
        return True


    def dontBuild(self):
        if (self.ignore or self.isShellMat):
            return True
        elif self.force:
            return False
        elif self.geometry:
            return (not self.geometry.isVisibleMaterial(self))
        return False


    def postbuild(self):
        if LS.useMaterials:
            self.guessColor()


    def guessColor(self):
        return


    def getUvSet(self, key, struct):
        if key not in struct.keys():
            uvset = None
            #print("Looking for UV set '%s'" % key)
            if self.geometry and self.geometry.data:
                geo = self.geometry.data
                url = geo.id
                uvset = geo.findUvSet(key, url)
                if not uvset:
                    path = url.replace("male%208_1/genesis8_1", "male/genesis8")
                    if path == url:
                        path = url.replace("male/genesis8", "male%208_1/genesis8_1")
                    if path != url:
                        uvset = geo.findUvSet(key, path)
            if not uvset:
                msg = ("Missing UV for '%s': '%s' not in %s" % (self.getLabel(), key, list(struct.keys())))
                reportError(msg, trigger=(3,5))
        return key


    def fixUdim(self, context, udim):
        mat = self.rna
        if mat is None:
            return
        try:
            dazRna(mat).DazUDim = udim
        except ValueError:
            print("UDIM out of range: %d" % udim)
        dazRna(mat).DazVDim = 0
        addUdimTree(mat.node_tree, udim, 0)


    def getDisplacementStrength(self):
        if (self.enabled["Displacement"] and
            GS.useDisplacement):
            return self.getValue("getChannelDisplacement", 0)
        else:
            return 0


    def getSubDLevel(self, level):
        if self.getDisplacementStrength():
            subd = self.getValue(["SubD Displacement Level"], 0)
            if subd > level:
                level = subd
        for shell in self.shells.values():
            level = shell.material.getSubDLevel(level)
        return level

#-------------------------------------------------------------
#   Get channels
#-------------------------------------------------------------

    def getLayeredChannel(self, channels):
        if self.layer is not None and isinstance(channels, list):
            layerChannels = ["%s %s" % (self.layer, channel.capitalize()) for channel in channels]
            layerChannels += ["%s %s" % (self.layer, channel) for channel in channels]
            if self.layer == "Base":
                layerChannels = channels + layerChannels
            channel = self.getChannel(layerChannels)
            return channel
        return self.getChannel(channels)

    def getLayeredValue(self, channels, default):
        return self.getChannelValue(self.getLayeredChannel(channels), default)

    def getChannelDiffuse(self):
        return self.getLayeredChannel(["Diffuse Color", "diffuse"])

    def getDiffuse(self):
        return self.getColor("getChannelDiffuse", BLACK)

    def getChannelGlossyColor(self):
        return self.getTexChannel(["Glossy Color", "specular", "Specular Color"])

    def getChannelGlossyLayeredWeight(self):
        return self.getTexChannel(["Glossy Layered Weight", "Glossy Weight", "specular_strength", "Specular Strength"])


    def getGlossyRoughness(self, default):
        invert = False
        channel = self.getLayeredChannel(["Glossy Roughness"])
        if channel is None:
            channel = self.getLayeredChannel(["glossiness", "Glossiness"])
            if channel:
                invert = True
        value = clamp( self.getChannelValue(channel, default) )
        if invert:
            return channel, value, (1-value), True
        else:
            return channel, value, value, False


    def getChannelOpacity(self):
        return self.getLayeredChannel(["Opacity Strength", "opacity"])

    def getChannelCutoutOpacity(self):
        return self.getLayeredChannel(["Cutout Opacity", "transparency"])

    def getChannelEmissionColor(self):
        return self.getLayeredChannel(["emission", "Emission Color"])

    def getChannelReflectionColor(self):
        return self.getLayeredChannel(["reflection", "Reflection Color"])

    def getChannelReflectionStrength(self):
        return self.getLayeredChannel(["reflection_strength", "Reflection Strength"])

    def getChannelRefractionColor(self):
        return self.getLayeredChannel(["refraction", "Refraction Color"])

    def getChannelRefractionWeight(self):
        return self.getLayeredChannel(["Refraction Weight", "refraction_strength"])

    def getChannelIOR(self):
        return self.getLayeredChannel(["ior", "Refraction Index"])

    def getChannelTranslucencyWeight(self):
        return self.getLayeredChannel(["translucency", "Translucency Weight"])

    def getChannelSSSColor(self):
        return self.getLayeredChannel(["SSS Color", "Subsurface Color"])

    def getChannelSSSAmount(self):
        return self.getLayeredChannel(["SSS Amount", "Subsurface Strength"])

    def getChannelSSSScale(self):
        return self.getLayeredChannel(["SSS Scale", "Subsurface Scale"])

    def getChannelNormal(self):
        return self.getLayeredChannel(["normal", "Normal Map"])

    def getChannelBump(self):
        return self.getLayeredChannel(["bump", "Bump Strength"])

    def getChannelBumpMin(self):
        return self.getLayeredChannel(["bump_min", "Bump Minimum", "Negative Bump"])

    def getChannelBumpMax(self):
        return self.getChannel(["bump_max", "Bump Maximum", "Positive Bump"])

    def getChannelDisplacement(self):
        return self.getLayeredChannel(["displacement", "Displacement Strength"])

    def getChannelDispMin(self):
        return self.getLayeredChannel(["displacement_min", "Displacement Minimum", "Minimum Displacement"])

    def getChannelDispMax(self):
        return self.getLayeredChannel(["displacement_max", "Displacement Maximum", "Maximum Displacement"])

    def getChannelHorizontalTiles(self):
        return self.getLayeredChannel(["u_scale", "Horizontal Tiles"])

    def getChannelHorizontalOffset(self):
        return self.getLayeredChannel(["u_offset", "Horizontal Offset"])

    def getChannelVerticalTiles(self):
        return self.getLayeredChannel(["v_scale", "Vertical Tiles"])

    def getChannelVerticalOffset(self):
        return self.getLayeredChannel(["v_offset", "Vertical Offset"])


    def getColor(self, attr, default):
        return self.getChannelColor(self.getLayeredChannel(attr), default)


    def getTexChannel(self, channels):
        for key in channels:
            channel = self.getLayeredChannel([key])
            if channel and self.hasTextures(channel):
                return channel
        return self.getLayeredChannel(channels)


    def hasTexChannel(self, channels):
        for key in channels:
            channel = self.getLayeredChannel([key])
            if channel and self.hasTextures(channel):
                return True
        return False


    def getChannelColor(self, channel, default, warn=True):
        color = self.getChannelValue(channel, default, warn)
        if isinstance(color, (int, float)):
            color = (color, color, color)
        if channel and channel["type"] == "color":
            return srgbToLinearCorrect(color)
        else:
            return srgbToLinearGamma22(color)


    def getTextures(self, channel):
        if isinstance(channel, tuple):
            channel = channel[0]
        if channel is None:
            return [],[]
        elif "image" in channel.keys():
            if channel["image"] is None:
                return [],[]
            else:
                asset = self.getAsset(channel["image"])
                if asset and asset.maps:
                    maps = asset.maps
                else:
                    maps = []
        elif "image_file" in channel.keys():
            url = channel["image_file"]
            map = Map({}, False)
            map.url = channel["image_file"]
            maps = [map]
        elif "map" in channel.keys():
            maps = Maps(self.fileref)
            maps.parse(channel["map"])
            raise DazError("Map in channel.keys: %s" % channel["map"])
        else:
            return [],[]

        texs = []
        for map in maps:
            if map.url:
                tex = map.getTexture()
            else:
                tex = None
            texs.append(tex)
        return texs,maps


    def hasTextures(self, channel):
        return (self.getTextures(channel)[0] != [])


    def hasAnyTexture(self):
        for key in self.channels:
            channel = self.getLayeredChannel([key])
            if self.getTextures(channel)[0]:
                return True
        return False


    def sssActive(self):
        if not self.enabled["Subsurface"]:
            return False
        if self.isRefractive() or self.isThinWall:
            return False
        return True

#-------------------------------------------------------------
#   UDims
#-------------------------------------------------------------

def addUdimTree(tree, udim, vdim):
    if tree is None:
        return
    for node in tree.nodes:
        if node.type == 'MAPPING':
            if hasattr(node, "translation"):
                slot = node.translation
            else:
                slot = node.inputs["Location"].default_value
            slot[0] = udim
            slot[1] = vdim
        elif node.type == 'GROUP':
            addUdimTree(node.node_tree, udim, vdim)

#-------------------------------------------------------------
#   Maps
#-------------------------------------------------------------

class Map:
    def __init__(self, map, ismask):
        self.url = None
        self.label = None
        self.operation = "alpha_blend"
        self.color = WHITE
        self.ismask = ismask
        self.image = None
        self.texture = None
        self.gamma = 1.0
        self.size = None
        for key,default in [
            ("url", None),
            ("color", WHITE),
            ("label", None),
            ("operation", None),
            ("invert", False),
            ("transparency", 1),
            ("rotation", 0),
            ("xmirror", False),
            ("ymirror", False),
            ("xscale", 1),
            ("yscale", 1),
            ("xoffset", 0),
            ("yoffset", 0)]:
            if key in map.keys():
                setattr(self, key, map[key])
            else:
                setattr(self, key, default)


    def __repr__(self):
        return ("<Map %s %s %s %.2f (%s %s) (%s %s)>" % (self.label, self.ismask, self.size, self.gamma, self.xoffset, self.yoffset, self.xscale, self.yscale))


    def getTexture(self):
        if self.texture is None:
            self.texture = Texture(self)
        return self.texture


    def build(self):
        if self.image:
            return self.image
        elif self.url:
            self.image = getImage(self.url)
            return self.image
        else:
            return self

#-------------------------------------------------------------
#   getImage used by shell editor
#-------------------------------------------------------------

def getImage(url):
    if url in LS.images.keys():
        return LS.images[url]
    filepath = GS.getAbsPath(url)
    if not filepath:
        reportError('Image not found:  \n"%s"' % filepath, trigger=(3,5))
        return None
    else:
        try:
            img = bpy.data.images.load(filepath)
        except (RuntimeError, TypeError):
            img = None
        if img is None:
            reportError('Error when reading image:\n"%s"\n"%s"' % (url,filepath), trigger=(2,3))
            return None
        imgname = os.path.splitext(os.path.basename(filepath))[0]
        img.name = unquote(bpy.path.clean_name(imgname))
        img["DazFilePath"] = filepath
        LS.images[url] = img
    return img

#-------------------------------------------------------------
#   Images
#-------------------------------------------------------------

class Images(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.maps = []

    def __repr__(self):
        return ("<Images %s r: %s>" % (self.id, self.maps))

    def parse(self, struct):
        Asset.parse(self, struct)
        size = None
        gamma = 1.0
        for key,data in struct.items():
            if key == "map":
                for mstruct in data:
                    if "mask" in mstruct.keys():
                        self.maps.append(Map(mstruct["mask"], True))
                    self.maps.append(Map(mstruct, False))
            elif key == "map_size":
                size = data
            elif key == "map_gamma" and data != 0.0:
                gamma = data
        for map in self.maps:
            map.size = size
            map.gamma = gamma

#-------------------------------------------------------------
#   Texture
#-------------------------------------------------------------

class Texture:
    def __init__(self, map):
        self.rna = None
        self.map = map
        self.image = None

    def __repr__(self):
        return ("<Texture %s %s %s>" % (self.map.url, self.map.image, self.rna))


    def getName(self):
        if self.map.url:
            return self.map.url
        elif self.map.image:
            return self.map.image.name
        else:
            return ""


    def buildImage(self, colorSpace):
        def fixUdimChar(imgname):
            fname,ext = os.path.splitext(imgname)
            if len(fname) > 5 and fname[-4:].isdigit() and fname[-5] in ["-", " "]:
                tile = int(fname[-4:])
                if tile > 1000 and tile < 1100:
                    imgname = "%s_%s%s" % (fname[:-5], fname[-4:], ext)
            return imgname

        if self.image:
            return self.image, self.image.name
        elif self.map.url:
            self.image = self.map.build()
        elif self.map.image:
            self.image = self.map.image
        if self.image is None:
            imgname = fixUdimChar(unquote(self.getName()))
            return None, imgname
        else:
            imgname = fixUdimChar(self.image.name)
            if imgname != self.image.name:
                self.image.name = imgname
            if colorSpace == "LINEAR":
                setColorSpaceLinear(self.image)
            else:
                setColorSpaceSRGB(self.image)
            return self.image, self.image.name


    def hasMapping(self, map):
        return (map and
                (map.size is not None or
                 map.gamma != 1.0))


    def getImageMapping(self, img, dmat, map):
        # mapping scale x = texture width / lie document size x * (lie x scale / 100)
        # mapping scale y = texture height / lie document size y * (lie y scale / 100)
        # mapping location x = udim place + lie x position * (lie y scale / 100) / lie document size x
        # mapping location y = (lie document size y - texture height * (lie y scale / 100) - lie y position) / lie document size y

        if img is None:
            return (0,0,1,1,0)

        if map.size is None:
            dx = dmat.getValue("getChannelHorizontalOffset", 0.0)
            dy = dmat.getValue("getChannelVerticalOffset", 0.0)
            sx = 1.0/dmat.getValue("getChannelHorizontalTiles", 1)
            sy = 1.0/dmat.getValue("getChannelVerticalTiles", 1)
            rz = 0.0
            return (dx,dy,sx,sy,rz)

        tx,ty = img.size
        mx,my = map.size
        kx,ky = tx/mx,ty/my
        ox,oy = map.xoffset/mx, map.yoffset/my
        rz = map.rotation
        ox += dmat.getValue("getChannelHorizontalOffset", 0.0)
        oy += dmat.getValue("getChannelVerticalOffset", 0.0)
        kx *= dmat.getValue("getChannelHorizontalTiles", 1)
        ky *= dmat.getValue("getChannelVerticalTiles", 1)
        sx = map.xscale*kx
        sy = map.yscale*ky

        if rz == 0:
            dx = ox
            dy = 1 - sy - oy
            if map.xmirror:
                dx = sx + ox
                sx = -sx
            if map.ymirror:
                dy = 1 - oy
                sy = -sy
        elif rz == 90:
            dx = ox
            dy = 1 - oy
            if map.xmirror:
                dy = 1 - sy - oy
                sy = -sy
            if map.ymirror:
                dx = sx + ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 270*D
        elif rz == 180:
            dx = sx + ox
            dy = 1 - oy
            if map.xmirror:
                dx = ox
                sx = -sx
            if map.ymirror:
                dy = 1 - sy - oy
                sy = -sy
            rz = 180*D
        elif rz == 270:
            dx = sx + ox
            dy = 1 - sy - oy
            if map.xmirror:
                dy = 1 - oy
                sy = -sy
            if map.ymirror:
                dx = ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 90*D

        return (dx,dy,sx,sy,rz)

#-------------------------------------------------------------z
#   Utilities
#-------------------------------------------------------------

def setColorSpace(img, alts):
    for alt in alts:
        try:
            img.colorspace_settings.name = alt
            return
        except TypeError:
            pass
    msg = "No matching color space in %s" % alts
    reportError(msg)

CSSRGB = ["sRGB", "sRGB OETF", "srgb_texture", "AgX Base sRGB", "Filmic sRGB"]
CSNonColor = ["Non-Color", "Raw", "Non-Colour Data", "Generic Data", "Utilities - Raw"]
CSLinear = ["Linear", "Linear Rec.709", "Linear BT.709 I-D65", "Linear BT.709", "Utilities - Linear - Rec.709", "lin_rec709",
            "Linear CIE-XYZ D65", "Linear CIE-XYZ E", "Linear DCI-P3 D65", "Linear Rec.2020"]

def setColorSpaceSRGB(img):
    setColorSpace(img, CSSRGB)

def isSRGBImage(img):
    return (img.colorspace_settings.name in CSSRGB)

def setColorSpaceNone(img):
    setColorSpace(img, CSNonColor)

def setColorSpaceLinear(img):
    setColorSpace(img, CSLinear)

def isWhite(color):
    return (tuple(color[0:3]) == (1.0,1.0,1.0))

def isBlack(color):
    return (tuple(color[0:3]) == (0.0,0.0,0.0))

def srgbToLinearCorrect(srgb):
    lin = []
    for s in srgb:
        if s < 0:
            l = 0
        elif s < 0.04045:
            l = s/12.92
        else:
            l = ((s+0.055)/1.055)**2.4
        lin.append(l)
    return Vector(lin)


def srgbToLinearGamma22(srgb):
    lin = []
    for s in srgb:
        if s < 0:
            l = 0
        else:
            l = round(s**2.2, 6)
        lin.append(l)
    return Vector(lin)

# ---------------------------------------------------------------------
#   Copy materials
# ---------------------------------------------------------------------

class DAZ_OT_CopyMaterials(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_materials"
    bl_label = "Copy Materials"
    bl_description = "Copy materials from active mesh to selected meshes"
    bl_options = {'UNDO'}

    useReplaceFaces : BoolProperty(
        name = "Replace Face Assignment",
        description = "Replace all materials and reassign face numbers.\nThe meshes must have identical topology",
        default = False)

    useMatchNames : BoolProperty(
        name = "Match Names",
        description = "Match materials based on names rather than material slots",
        default = True)

    errorMismatch : BoolProperty(
        name = "Error On Mismatch",
        description = "Raise an error if the number of source and target materials are different",
        default = True)

    useAddMaterials : BoolProperty(
        name = "Add New Materials",
        description = "Add materials after existing materials",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useAddMaterials")
        if self.useAddMaterials:
            return
        self.layout.prop(self, "useReplaceFaces")
        if not self.useReplaceFaces:
            self.layout.prop(self, "useMatchNames")
            if not self.useMatchNames:
                self.layout.prop(self, "errorMismatch")


    def run(self, context):
        src = context.object
        self.mismatch = ""
        found = False
        for trg in getSelectedMeshes(context):
            if trg != src:
                if self.useAddMaterials:
                    self.addMaterials(src, trg)
                elif self.useReplaceFaces:
                    self.replaceFaces(src, trg)
                elif self.useMatchNames:
                    self.copyByName(src, trg)
                else:
                    self.copyByIndex(src, trg)
                found = True
        if not found:
            raise DazError("No target mesh selected")
        if self.mismatch:
            msg = "Material number mismatch.\n" + self.mismatch
            self.raiseWarning(msg)


    def addMaterials(self, src, trg):
        for mat in src.data.materials:
            trg.data.materials.append(mat)


    def replaceFaces(self, src, trg):
        from .finger import getFingerPrint
        if getFingerPrint(src) != getFingerPrint(trg):
            raise DazError("Meshes have different topology")
        trg.data.materials.clear()
        for mat in src.data.materials:
            trg.data.materials.append(mat)
        for fsrc,ftrg in zip(src.data.polygons, trg.data.polygons):
            ftrg.material_index = fsrc.material_index


    def copyByName(self, src, trg):
        for mat in src.data.materials:
            mn = self.getMatch(mat.name, trg.data.materials)
            if mn is not None:
                trg.data.materials[mn] = mat
            else:
                print("No match for %s" % mat.name)


    def getMatch(self, mname, mats):
        sname = stripName(mname)
        for mn,mat in enumerate(mats):
            tname = stripName(mat.name)
            if sname.lower() == tname.lower():
                return mn
        return None


    def copyByIndex(self, src, trg):
        ntrgmats = len(trg.data.materials)
        nsrcmats = len(src.data.materials)
        if ntrgmats != nsrcmats:
            self.mismatch += ("\n%s (%d materials) != %s (%d materials)"
                          % (src.name, nsrcmats, trg.name, ntrgmats))
            if self.errorMismatch:
                msg = "Material number mismatch.\n" + self.mismatch
                raise DazError(msg)
        mnums = [(f,f.material_index) for f in trg.data.polygons]
        srclist = list(enumerate(src.data.materials))
        trglist = list(enumerate(trg.data.materials))
        trgrest = trglist[nsrcmats:ntrgmats]
        trglist = trglist[:nsrcmats]
        srcrest = srclist[ntrgmats:nsrcmats]
        srclist = srclist[:ntrgmats]
        trg.data.materials.clear()
        for _,mat in srclist:
            trg.data.materials.append(mat)
        for _,mat in trgrest:
            trg.data.materials.append(mat)
        for f,mn in mnums:
            f.material_index = mn

#----------------------------------------------------------
#   Prune node tree
#----------------------------------------------------------

class DAZ_OT_PruneNodeTrees(DazPropsOperator):
    bl_idname = "daz.prune_node_trees"
    bl_label = "Prune Node Trees"
    bl_description = "Prune all material node trees for selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'CURVES'])

    useDeleteUnusedNodes : BoolProperty(
        name = "Delete Unused Nodes",
        description = "Delete nodes not connected to material output",
        default = True)

    useHideTexNodes : BoolProperty(
        name = "Hide Texture Nodes",
        description = "Hide all texture nodes",
        default = True)

    usePruneTexco : BoolProperty(
        name = "Prune Texture Coordinates",
        description = "Delete texture coordinates nodes not connected to mapping nodes",
        default = True)

    useHideOutputs : BoolProperty(
        name = "Hide Unused Outputs",
        description = "Hide unused output sockets",
        default = True)

    keepUnusedTextures : BoolProperty(
        name = "Keep Unused Textures",
        description = "Keep textures from unused channels",
        default = True)

    useFixColorSpace : BoolProperty(
        name = "Fix Color Space",
        default = True)

    useDazImages : BoolProperty(
        name = "DAZ Images",
        description = "Make node groups for DAZ images",
        default = True)

    useBeautify : BoolProperty(
        name = "Beautify",
        description = "Beautify node tree",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useDeleteUnusedNodes")
        self.layout.prop(self, "useHideTexNodes")
        self.layout.prop(self, "usePruneTexco")
        self.layout.prop(self, "useHideOutputs")
        self.layout.prop(self, "keepUnusedTextures")
        self.layout.prop(self, "useFixColorSpace")
        self.layout.prop(self, "useDazImages")
        self.layout.prop(self, "useBeautify")


    def run(self, context):
        from .geometry import getActiveUvLayer
        from .tree import pruneNodeTree
        for ob in getSelectedMeshes(context):
            LS.__init__()
            active = getActiveUvLayer(ob)
            for mat in ob.data.materials:
                if mat:
                    pruneNodeTree(mat.node_tree,
                                  active,
                                  self.useDeleteUnusedNodes,
                                  self.useHideTexNodes,
                                  self.usePruneTexco,
                                  self.useHideOutputs,
                                  self.keepUnusedTextures,
                                  self.useFixColorSpace,
                                  self.useDazImages,
                                  self.useBeautify,
                                  )

#----------------------------------------------------------
#   Render settings
#----------------------------------------------------------

def checkRenderSettings(context, force):
    from .light import getMinLightSettings

    renderSettingsCycles = {
        "Bounces" : [("max_bounces", ">", 8)],
        "Diffuse" : [("diffuse_bounces", ">", 1)],
        "Glossy" : [("glossy_bounces", ">", 4)],
        "Transparent" : [("transparent_max_bounces", ">", 32),
                         ("transmission_bounces", ">", 8),
                         ("caustics_refractive", "=", True)],
        "Volume" : [("volume_bounces", ">", 4)],
    }

    renderSettingsEeveeOld = {
        "Transparent" : [
                 ("use_ssr", "=", True),
                 ("use_ssr_refraction", "=", True),
                 ("use_ssr_halfres", "=", False),
                 ("ssr_thickness", "<", 2*GS.scale),
                 ("ssr_quality", ">", 1.0),
                 ("ssr_max_roughness", ">", 1.0),
                ],
        "Bounces" : [("shadow_cube_size", ">", "1024"),
                 ("shadow_cascade_size", ">", "2048"),
                 ("use_shadow_high_bitdepth", "=", True),
                 ("use_soft_shadows", "=", True),
                 ("light_threshold", "<", 0.001),
                 ("sss_samples", ">", 16),
                 ("sss_jitter_threshold", ">", 0.5),
                ],
    }

    renderSettingsEeveeNew = {
        "Transparent" : [
            ("use_raytracing", "=", True),
            ("ray_tracing_method", "=", 'SCREEN'),
            ("ray_tracing_options", "&", [
                ("resolution_scale", "=", "1"),
                ("trace_max_roughness", ">", 0.5)
            ]),
        ]
    }


    renderSettingsRender = {
        "Bounces" : [("hair_type", "=", 'STRIP')],
    }

    lightSettings = {
        "Bounces" : getMinLightSettings(),
    }

    scn = context.scene
    handle = GS.onRenderSettings
    if force:
        handle = "UPDATE"
    msg = ""
    msg += checkSettings(scn.cycles, renderSettingsCycles, handle, "Cycles Settings", force)
    msg += checkSettings(scn.render, renderSettingsRender, handle, "Render Settings", force)
    if bpy.app.version >= (4,2,0):
        msg += checkSettings(scn.eevee, renderSettingsEeveeNew, handle, "Eevee Settings", force)
    else:
        msg += checkSettings(scn.eevee, renderSettingsEeveeOld, handle, "Eevee Settings", force)
        handle = GS.onLightSettings
        if force:
            handle = "UPDATE"
        for light in getVisibleObjects(context):
            if light.type == 'LIGHT':
                header = ('Light "%s" settings' % light.name)
                msg += checkSettings(light.data, lightSettings, handle, header, force)

    if msg:
        msg += "See http://diffeomorphic.blogspot.com/2020/04/render-settings.html for details."
        #print(msg)
        return msg
    else:
        return ""


def checkSettings(engine, settings, handle, header, force):
    def updateSettings(engine, data, ok):
        for attr,op,minval in data:
            if not hasattr(engine, attr):
                continue
            val = getattr(engine, attr)
            if op == "&":
                ok = updateSettings(val, minval, ok)
            else:
                fix,minval = checkSetting(attr, op, val, minval, ok, header)
                if fix:
                    ok = False
                    if handle == "UPDATE":
                        setattr(engine, attr, minval)
        return ok

    msg = ""
    if handle == "IGNORE":
        return msg
    ok = True
    for key,used in LS.usedFeatures.items():
        if (force or used) and key in settings.keys():
            ok = updateSettings(engine, settings[key], ok)
    if not ok and handle == "WARN":
        msg = ("%s are insufficient to render this scene correctly.\n" % header)
    return msg


def checkSetting(attr, op, val, minval, first, header):
    negop = None
    eps = 1e-4
    if op == "=":
        if val != minval:
            negop = "!="
    elif op == ">":
        if isinstance(val, str):
            if int(val) < int(minval):
                negop = "<"
        elif val < minval-eps:
            negop = "<"
    elif op == "<":
        if isinstance(val, str):
            if int(val) > int(minval):
                negop = ">"
        elif val > minval+eps:
            negop = ">"

    if negop:
        msg = ("  %s: %s %s %s" % (attr, val, negop, minval))
        if first:
            print("%s:" % header)
        print(msg)
        return True,minval
    else:
        return False,minval

#----------------------------------------------------------
#   Update Render settings
#----------------------------------------------------------

class DAZ_OT_UpdateRenderSettings(DazOperator):
    bl_idname = "daz.update_render_settings"
    bl_label = "Update Render Settings"
    bl_description = "Update render and light settings if they are inadequate"
    bl_options = {'UNDO'}

    def run(self, context):
        checkRenderSettings(context, True)

#----------------------------------------------------------
#   Prune images
#----------------------------------------------------------

class DAZ_OT_PruneImages(DazOperator):
    bl_idname = "daz.prune_images"
    bl_label = "Prune Images"
    bl_description = "Remove all unused images"
    bl_options = {'UNDO'}

    def run(self, context):
        for img in list(bpy.data.images):
            if img.users == 0:
                print("Remove %s" % img.name)
                bpy.data.images.remove(img)

#----------------------------------------------------------
#   Strip material names
#----------------------------------------------------------
class DAZ_OT_StripMaterialNames(DazPropsOperator, IsMesh):
    bl_idname = "daz.strip_material_names"
    bl_label = "Strip Material Names"
    bl_description = "Strip endings from material names"
    bl_options = {'UNDO'}

    useCombineMaterials : BoolProperty(
        name = "Combine Materials",
        description = "Combine materials with the same stripped name",
        default = False)

    useStripDazEndings : BoolProperty(
        name = "Strip DAZ Endings",
        description = "Strip -n endings, otherwise only strip .001 endings",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useCombineMaterials")
        self.layout.prop(self, "useStripDazEndings")

    def run(self, context):
        mats = {}
        for ob in getSelectedMeshes(context):
            for n,mat in enumerate(ob.data.materials):
                if mat:
                    if self.useStripDazEndings:
                        mname = baseName(stripName(mat.name))
                    else:
                        mname = baseName(mat.name)
                    if self.useCombineMaterials and mname in mats.keys():
                        ob.data.materials[n] = mats[mname]
                    else:
                        mat.name = mname
                        mats[mname] = mat

#----------------------------------------------------------
#   Sort materials by name
#----------------------------------------------------------

class DAZ_OT_SortMaterialsByName(DazOperator, IsMesh):
    bl_idname = "daz.sort_materials_by_name"
    bl_label = "Sort Materials By Name"
    bl_description = "Reorder materials by name as in DAZ Studio"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            sortMaterialsByName(ob)


def sortMaterialsByName(ob):
    mnums = [f.material_index for f in ob.data.polygons]
    mats = [(mat.name, n, mat) for n,mat in enumerate(ob.data.materials)]
    mats.sort()
    ob.data.materials.clear()
    for mdata in mats:
        ob.data.materials.append(mdata[2])
    assoc = {}
    for m,data in enumerate(mats):
        assoc[data[1]] = m
    nfaces = len(ob.data.polygons)
    data = [assoc.get(mnums[fn],0) for fn in range(nfaces)]
    ob.data.polygons.foreach_set("material_index", data)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyMaterials,
    DAZ_OT_PruneNodeTrees,
    DAZ_OT_PruneImages,
    DAZ_OT_UpdateRenderSettings,
    DAZ_OT_StripMaterialNames,
    DAZ_OT_SortMaterialsByName,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
