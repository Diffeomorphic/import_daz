# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
from .fileutils import SingleFile, MultiFile, ImageFile, JsonFile
from .animation import theImageExtensions
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
        #self.channels = OrderedDict()
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
        elif LS.materialMethod in ['SINGLE_PRINCIPLED', 'FBX_COMPATIBLE']:
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
        return ("Root Transmission Color" in self.channels.keys())


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


    def build(self, context):
        from .geometry import Geometry, GeoNode
        self.setupBasics()
        if self.dontBuild():
            return False
        if GS.verbosity >= 4:
            print("Build material %s" % self.name)
        mat = self.rna
        if mat is None:
            mat = self.rna = bpy.data.materials.new(self.name)
            LS.materials[self.name] = mat
        scn = self.scene = context.scene
        mat.DazShader = self.shader
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
            mat.DazUDim = udim
        except ValueError:
            print("UDIM out of range: %d" % udim)
        mat.DazVDim = 0
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
        if isinstance(color, int) or isinstance(color, float):
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


    def getMapping(self, mat, map):
        if self.images["COLOR"]:
            img = self.images["COLOR"]
            return self.getImageMapping(img, mat, map)
        elif self.images["NONE"]:
            img = self.images["NONE"]
            return self.getImageMapping(img, mat, map)
        else:
            reportError("BUG: getMapping finds no image", trigger=(3,5))
            return (0,0,1,1,0)


    def getImageMapping(self, img, mat, map):
        # mapping scale x = texture width / lie document size x * (lie x scale / 100)
        # mapping scale y = texture height / lie document size y * (lie y scale / 100)
        # mapping location x = udim place + lie x position * (lie y scale / 100) / lie document size x
        # mapping location y = (lie document size y - texture height * (lie y scale / 100) - lie y position) / lie document size y

        if img is None:
            return (0,0,1,1,0)

        if map.size is None:
            dx = mat.getValue("getChannelHorizontalOffset", 0.0)
            dy = mat.getValue("getChannelVerticalOffset", 0.0)
            sx = 1.0/mat.getValue("getChannelHorizontalTiles", 1)
            sy = 1.0/mat.getValue("getChannelVerticalTiles", 1)
            rz = 0.0
            return (dx,dy,sx,sy,rz)

        tx,ty = img.size
        mx,my = map.size
        kx,ky = tx/mx,ty/my
        ox,oy = map.xoffset/mx, map.yoffset/my
        rz = map.rotation
        ox += mat.getValue("getChannelHorizontalOffset", 0.0)
        oy += mat.getValue("getChannelVerticalOffset", 0.0)
        kx *= mat.getValue("getChannelHorizontalTiles", 1)
        ky *= mat.getValue("getChannelVerticalTiles", 1)
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

#-------------------------------------------------------------
#   Use hidden textures
#-------------------------------------------------------------

class HiddenTextureUser:
    useHiddenMeshes : BoolProperty(
        name = "Also Hidden Meshes",
        description = "Also save textures from hidden meshes",
        default = True)

    def getMeshes(self, context):
        if self.useHiddenMeshes:
            return [ob for ob in bpy.data.objects if ob.type == 'MESH']
        else:
            return getVisibleMeshes(context)

#-------------------------------------------------------------
#   Save local textures
#-------------------------------------------------------------

class LocalTextureSaver(HiddenTextureUser):
    @classmethod
    def poll(self, context):
        return (bpy.data.filepath and context.object and context.object.type == 'MESH')

    def saveLocalTextures(self, context):
        folder = normalizePath(os.path.dirname(bpy.data.filepath))
        if GS.useLowerResFolders:
            self.subdir = "/textures/original"
        else:
            self.subdir = "/textures"
        self.texpath = "%s%s" % (folder, self.subdir)
        self.basepath = "%s/textures" % folder
        print('Save textures to "%s"' % self.texpath)
        if not os.path.exists(self.texpath):
            os.makedirs(self.texpath)

        self.images = []
        for ob in self.getMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    if mat.use_nodes:
                        self.saveNodesInTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.saveTextureSlots(psys.settings)
            dazRna(ob).DazLocalTextures = True

        for src,img in self.images:
            if src.startswith(self.basepath):
                print("Already local: %s" % src)
                continue
            file = bpy.path.basename(src)
            srclower = normalizePath(src).lower()
            if (self.keepDirs and
                "/textures/" in srclower and
                "/textures/original/" not in srclower):
                subpath = os.path.dirname(srclower.rsplit("/textures/",1)[1])
                folder = "%s/%s" % (self.texpath, subpath)
                if not os.path.exists(folder):
                    print("Make %s" % folder)
                    os.makedirs(folder)
                trg = "%s/%s" % (folder, file)
            else:
                trg = "%s/%s" % (self.texpath, file)
            self.changeImage(src, trg, img)


    def changeImage(self, src, trg, img):
        from shutil import copyfile
        if not os.path.exists(src):
            msg = "Missing texture file:\n%s" % src
            print(msg)
            raise DazError(msg)
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n=> %s" % (src, trg))
            copyfile(src, trg)
        if img is None:
            if trg in bpy.data.images.keys():
                img = bpy.data.images[trg]
            else:
                img = bpy.data.images.load(trg)
        img.filepath = bpy.path.relpath(trg)
        return img


    def saveImage(self, img):
        if img:
            path = bpy.path.abspath(img.filepath)
            path = bpy.path.reduce_dirs([path])[0]
            self.images.append((normalizePath(path), img))


    def saveNodesInTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                self.saveImage(node.image)
            elif node.type == 'GROUP':
                self.saveNodesInTree(node.node_tree)


    def saveTextureSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex:
                tex = mtex.texture
                if hasattr(tex, "image") and tex.image:
                    self.saveImage(tex.image)


class DAZ_OT_SaveLocalTextures(LocalTextureSaver, DazPropsOperator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Local Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"

    keepDirs : BoolProperty(
        name = "Keep Directories",
        description = "Keep the directory tree from Daz Studio, otherwise flatten the directory structure",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "keepDirs")
        self.layout.prop(self, "useHiddenMeshes")

    def run(self, context):
        self.saveLocalTextures(context)

#-------------------------------------------------------------
#   Combine identical materials
#-------------------------------------------------------------

class MaterialCombiner:
    ignoreBump : BoolProperty(
        name = "Ignore Bump Strength",
        description = "Merge materials even if the bump strengths differ",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "ignoreBump")

    def combine(self, context):
        self.setupShells(context)
        self.nCombined = 0
        if self.acrossObjects:
            table,diffuse = self.setupTable(self.meshes)
            for ob in self.meshes:
                self.combineMaterials(ob, table, diffuse)
        else:
            for ob in self.meshes:
                table,diffuse = self.setupTable([ob])
                self.combineMaterials(ob, table, diffuse)
        if not ES.easy:
            print("Number of materials combined: %d" % self.nCombined)


    def setupShells(self, context):
        shelled = []
        for shell in getVisibleMeshes(context):
            mod = getModifier(shell, 'NODES')
            if mod and "Input_1" in mod.keys() and isinstance(mod["Input_1"], bpy.types.Object):
                shelled.append(mod["Input_1"])
        self.meshes = []
        for ob in self.getMeshes(context):
            if ob in shelled:
                print("Object with shell: %s" % ob.name)
            else:
                self.meshes.append(ob)


    def setupTable(self, meshes):
        def norm(color):
            r,g,b,a = color
            return max((abs(r-g), abs(r-b), abs(g-b)))

        mats = []
        for ob in meshes:
            for mat in ob.data.materials:
                if mat:
                    mats.append(mat)
        table = {}
        diffuse = {}
        mats2 = []
        for mat in mats:
            taken = False
            for mat2 in mats2:
                if self.areSameMaterial(mat, mat2):
                    table[mat.name] = mat2
                    if norm(mat.diffuse_color) < norm(mat2.diffuse_color):
                        diffuse[mat2.name] = (mat.name, mat.diffuse_color)
                    taken = True
                    if mat.DazMaterialType == 'SKIN':
                        mat2.DazMaterialType = 'SKIN'
                    break
            if not taken:
                table[mat.name] = mat
                mats2.append(mat)
        return table,diffuse


    def combineMaterials(self, ob, table, diffuse):
        mats = list(ob.data.materials)
        facenums,phairs = clearMaterials(ob)
        mdatas = []
        for mat in mats:
            if mat is None:
                mat2 = None
                mdatas.append(None)
            else:
                mat2 = table[mat.name]
                mdatas.append( diffuse.get(mat.name, (mat.name, mat.diffuse_color)) )
                ob.data.materials.append(mat2)
        for mat,mdata in zip(mats, mdatas):
            if mat:
                mat.name, mat.diffuse_color = mdata
        for f,mn in zip(ob.data.polygons, facenums):
            f.material_index = mn
        for pset,matslot in phairs:
            pset.material_slot = matslot


    def keepMaterial(self, n, mat, ob):
        for mat2 in self.matlist:
            if self.areSameMaterial(mat, mat2):
                m = self.reindex[n] = self.assoc[mat2.name]
                self.newname[mat.name] = mat2.name
                return False
        return True


    def areSameMaterial(self, mat1, mat2):
        mname1 = mat1.name
        mname2 = mat2.name
        deadMatProps = [
            "texture_slots", "node_tree",
            "name", "name_full", "active_texture",
            "diffuse_color"
        ]
        matProps = self.getRelevantProps(mat1, deadMatProps)
        if not self.haveSameAttrs(mat1, mat2, matProps, mname1, mname2):
            return False
        if mat1.use_nodes and mat2.use_nodes:
            if self.areSameCycles(mat1.node_tree, mat2.node_tree, mname1, mname2):
                if not ES.easy:
                    print("%s = %s" % (mat1.name, mat2.name))
                self.nCombined += 1
                return True
            else:
                return False
        else:
            return False


    def getRelevantProps(self, rna, deadProps):
        props = []
        for prop in dir(rna):
            if (prop[0] != "_" and
                prop not in deadProps):
                props.append(prop)
        return props


    def haveSameAttrs(self, rna1, rna2, props, mname1, mname2):
        for prop in props:
            attr1 = attr2 = None
            if (prop[0] == "_" or
                prop[0:3] == "Daz" or
                prop in ["select", "session_uid"]):
                pass
            elif hasattr(rna1, prop) and hasattr(rna2, prop):
                attr1 = getattr(rna1, prop)
                if prop == "name":
                    attr1 = self.fixKey(attr1, mname1, mname2)
                attr2 = getattr(rna2, prop)
                if not self.checkEqual(attr1, attr2):
                    return False
            elif hasattr(rna1, prop) or hasattr(rna2, prop):
                return False
        return True


    def checkEqual(self, attr1, attr2):
        if (isinstance(attr1, int) or
            isinstance(attr1, float) or
            isinstance(attr1, str)):
            return (attr1 == attr2)
        elif isinstance(attr1, bpy.types.Image):
            return (isinstance(attr2, bpy.types.Image) and (attr1.name == attr2.name))
        elif (isinstance(attr1, set) and isinstance(attr2, set)):
            return True
        elif hasattr(attr1, "__len__") and hasattr(attr2, "__len__"):
            if (len(attr1) != len(attr2)):
                return False
            for n in range(len(attr1)):
                if not self.checkEqual(attr1[n], attr2[n]):
                    return False
        return True


    def areSameCycles(self, tree1, tree2, mname1, mname2):
        def rehash(struct):
            nstruct = {}
            for key,node in struct.items():
                if node.name[0:2] == "T_":
                    nstruct[node.name] = node
                elif node.type == 'GROUP':
                    nstruct[node.node_tree.name] = node
                else:
                    nstruct[key] = node
            return nstruct

        nodes1 = rehash(tree1.nodes)
        nodes2 = rehash(tree2.nodes)
        if not self.haveSameKeys(nodes1, nodes2, mname1, mname2):
            return False
        if not self.haveSameKeys(tree1.links, tree2.links, mname1, mname2):
            return False
        for key1,node1 in nodes1.items():
            key2 = self.fixKey(key1, mname1, mname2)
            node2 = nodes2[key2]
            if not self.areSameNode(node1, node2, mname1, mname2):
                return False
        for link1 in tree1.links:
            hit = False
            for link2 in tree2.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        for link2 in tree2.links:
            hit = False
            for link1 in tree1.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        return True


    def areSameNode(self, node1, node2, mname1, mname2):
        if node1.type != node2.type:
            return False
        if not self.haveSameKeys(node1, node2, mname1, mname2):
            return False
        deadNodeProps = ["dimensions", "location"]
        nodeProps = self.getRelevantProps(node1, deadNodeProps)
        if node1.type == 'GROUP':
            if node1.node_tree != node2.node_tree:
                return False
        elif not self.haveSameAttrs(node1, node2, nodeProps, mname1, mname2):
            return False
        if not self.haveSameInputs(node1, node2):
            return False
        return True


    def areSameLink(self, link1, link2, mname1, mname2):
        fromname1 = self.getNodeName(link1.from_node)
        toname1 = self.getNodeName(link1.to_node)
        fromname2 = self.getNodeName(link2.from_node)
        toname2 = self.getNodeName(link2.to_node)
        fromname1 = self.fixKey(fromname1, mname1, mname2)
        toname1 = self.fixKey(toname1, mname1, mname2)
        return (
            (fromname1 == fromname2) and
            (toname1 == toname2) and
            (link1.from_socket.name == link2.from_socket.name) and
            (link1.to_socket.name == link2.to_socket.name)
        )


    def getNodeName(self, node):
        if node.type == 'GROUP':
            return node.node_tree.name
        else:
            return node.name


    def haveSameInputs(self, node1, node2):
        if len(node1.inputs) != len(node2.inputs):
            return False
        for n,socket1 in enumerate(node1.inputs):
            socket2 = node2.inputs[n]
            if hasattr(socket1, "default_value"):
                if not hasattr(socket2, "default_value"):
                    return False
                val1 = socket1.default_value
                val2 = socket2.default_value
                if (hasattr(val1, "__len__") and
                    hasattr(val2, "__len__")):
                    for m in range(len(val1)):
                        if val1[m] != val2[m]:
                            return False
                elif (val1 != val2 and
                      not (node1.type == "BUMP" and self.ignoreBump)):
                    return False
            elif hasattr(socket2, "default_value"):
                return False
        return True


    def fixKey(self, key, mname1, mname2):
        n = len(key) - len(mname1)
        if key[n:] == mname1:
            return key[:n] + mname2
        else:
            return key


    def haveSameKeys(self, struct1, struct2, mname1, mname2):
        m = len(mname1)
        for key1 in struct1.keys():
            if key1 in ["interface"]:
                continue
            key2 = self.fixKey(key1, mname1, mname2)
            if key2 not in struct2.keys():
                return False
        return True


class DAZ_OT_CombineSceneMaterials(MaterialCombiner, DazPropsOperator):
    bl_idname = "daz.combine_scene_materials"
    bl_label = "Combine Scene Materials"
    bl_description = "Combine identical materials in scene across objects"
    bl_options = {'UNDO'}

    acrossObjects = True

    def run(self, context):
        self.combine(context)

    def getMeshes(self, context):
        return getVisibleMeshes(context)

#-------------------------------------------------------------
#   Merge identical materials
#-------------------------------------------------------------

class DAZ_OT_MergeMaterials(MaterialCombiner, DazPropsOperator, IsMesh):
    bl_idname = "daz.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge identical materials of selected meshes"
    bl_options = {'UNDO'}

    acrossObjects = False

    def run(self, context):
        self.combine(context)
        self.nMerged = 0
        for ob in self.meshes:
            self.mergeSlots(ob)
        if not ES.easy:
            print("Number of material slots merged: %d" % self.nMerged)

    def getMeshes(self, context):
        return getSelectedMeshes(context)

    def mergeSlots(self, ob):
        assoc = {}
        reindex = {}
        mats = []
        mnum = 0
        reduced = False
        for mn,mat in enumerate(ob.data.materials):
            if mat is None:
                reduced = True
            elif mat.name in assoc.keys():
                reindex[mn] = assoc[mat.name]
                if not ES.easy:
                    print("%s: %d = %d" % (mat.name, mn, assoc[mat.name]))
                self.nMerged += 1
                reduced = True
            else:
                reindex[mn] = mnum
                assoc[mat.name] = mnum
                mats.append(mat)
                mnum += 1

        if reduced:
            facenums,phairs = clearMaterials(ob)
            for mnum,mat in enumerate(mats):
                ob.data.materials.append(mat)
            for f,mn in zip(ob.data.polygons, facenums):
                f.material_index = reindex[mn]
            for pset,matslot in phairs:
                mnum2 = assoc[matslot]
                pset.material_slot = mats[mnum2].name


def clearMaterials(ob):
    facenums = [f.material_index for f in ob.data.polygons]
    phairs = []
    for psys in ob.particle_systems:
        pset = psys.settings
        phairs.append((pset, pset.material_slot))
    ob.data.materials.clear()
    return facenums,phairs

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

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class ChangeResolution(HiddenTextureUser):
    steps : IntProperty(
        name = "Steps",
        description = "Resize original images with this number of steps",
        min = 0, max = 8,
        default = 2)

    resizeAll : BoolProperty(
        name = "Resize All",
        description = "Resize all textures of the selected meshes",
        default = True)

    def initResolution(self):
        self.filenames = []
        self.images = {}

    def getFileNames(self, paths):
        for path in paths:
            fname = bpy.path.basename(self.getBasePath(path))
            self.filenames.append(fname)


    def getAllTextures(self, context, resolveUDIM):
        paths = {}
        for ob in self.getMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    self.getTreeTextures(mat.node_tree, paths, resolveUDIM)
            for psys in ob.particle_systems:
                self.getSlotTextures(psys.settings, paths)
        return paths


    def getSlotTextures(self, mat, paths):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                paths[mtex.texture.image.filepath] = True


    def getTreeTextures(self, tree, paths, resolveUDIM):
        if tree is None:
            return
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                if img.source == 'TILED':
                    folder,basename,ext = self.getTiledPath(img.filepath)
                    for file1 in os.listdir(folder):
                        fname1,ext1 = os.path.splitext(file1)
                        if fname1[:-4] == basename and ext1 == ext:
                            if bpy.app.version >= (3,1,0) and resolveUDIM:
                                path = os.path.join(folder, "%s%s%s" % (fname1[:-4], "<UDIM>", ext1))
                            else:
                                path = os.path.join(folder, "%s%s" % (fname1, ext1))
                            paths[path] = True
                else:
                    paths[img.filepath] = True
            elif node.type == 'GROUP':
                self.getTreeTextures(node.node_tree, paths, resolveUDIM)


    def getTiledPath(self, filepath):
        path = bpy.path.abspath(filepath)
        path = bpy.path.reduce_dirs([path])[0]
        folder = os.path.dirname(path)
        fname,ext = os.path.splitext(bpy.path.basename(path))
        if fname[-6:] == "<UDIM>":
            return folder, fname[:-6], ext
        else:
            return folder, fname[:-4], ext


    def replaceTextures(self, context):
        for ob in self.getMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    self.resizeTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.resizeSlots(psys.settings)


    def resizeSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                img = self.replaceImage(mtex.texture.image)
                mtex.texture.image = img


    def resizeTree(self, tree):
        if tree is None:
            return
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                img = self.replaceImage(node.image)
                node.image = img
                if img:
                    node.name = img.name
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)


    def getBasePath(self, path):
        path = self.getBasePathNames(normalizePath(path))
        if GS.useLowerResFolders:
            words = path.split("/textures/res", 1)
            if len(words) == 2:
                path = "%s/textures/original%s" % (words[0], words[1][1:])
        return path


    def getBasePathNames(self, path):
        fname,ext = os.path.splitext(path)
        if fname[-5:] == "-res0":
            return "%s%s" % (fname[:-5], ext)
        elif fname[-5:-1] == "-res" and fname[-1].isdigit():
            return "%s%s" % (fname[:-5], ext)
        elif (fname[-10:-6] == "-res" and
              fname[-6].isdigit() and
              fname[-5] == "_" and
              fname[-4:].isdigit()):
            return "%s%s%s" % (fname[:-10], fname[-5:], ext)
        elif (fname[-12:-8] == "-res" and
              fname[-8].isdigit() and
              fname[-7:] == "_<UDIM>"):
            return "%s%s%s" % (fname[:-12], fname[-7:], ext)
        else:
            return path


    def replaceImage(self, img):
        if img is None:
            return None
        colorSpace = img.colorspace_settings.name
        if colorSpace not in self.images.keys():
            self.images[colorSpace] = {}
        images = self.images[colorSpace]

        path = self.getBasePath(img.filepath)
        filename = bpy.path.basename(path)
        if filename not in self.filenames:
            return img

        newname,newpath = self.getNewPath(path)
        if img.source == 'TILED':
            if newname[-6:] == "<UDIM>":
                newname = newname[:-7]
            else:
                newname = newname[:-5]
        if newpath == img.filepath:
            return img
        elif newpath in images.keys():
            return images[newpath][1]
        oldimg = bpy.data.images.get(newname)
        if oldimg and oldimg.filepath == newpath:
            return oldimg
        try:
            newimg = self.loadNewImage(img, newpath)
        except RuntimeError:
            newimg = None
        if newimg:
            newimg.name = newname
            newimg.name = newname
            newimg.colorspace_settings.name = colorSpace
            newimg.source = img.source
            images[newpath] = (img, newimg)
            return newimg
        else:
            print('"%s" does not exist' % newpath)
            return img


    def loadNewImage(self, img, newpath):
        print('Replace "%s" with "%s"' % (img.filepath, newpath))
        if img.source == 'TILED':
            folder,basename,ext = self.getTiledPath(newpath)
            newimg = None
            print("Tiles:")
            for file1 in os.listdir(folder):
                fname1,ext1 = os.path.splitext(file1)
                if fname1[:-4] == basename and ext1 == ext:
                    path = os.path.join(folder, file1)
                    img = bpy.data.images.load(path)
                    udim = int(fname1[-4:])
                    if newimg is None:
                        newimg = img
                        newimg.source = 'TILED'
                        tile = img.tiles[0]
                        tile.number = udim
                        if bpy.app.version >= (3,1,0):
                            path2,ext2 = os.path.splitext(newimg.filepath)
                            newimg.filepath = "%s%s%s" % (path2[:-4],"<UDIM>",ext2)
                            newimg.name=basename[:-1]
                    else:
                        newimg.tiles.new(tile_number = udim)
                    print('  "%s"' % file1)
            return newimg
        else:
            return bpy.data.images.load(newpath)


    def getNewPathFolders(self, path):
        if self.steps == 0:
            return path
        words = path.split("/textures/original/", 1)
        if len(words) != 2:
            words = path.split("/textures/", 1)
        if len(words) == 2:
            newpath = "%s/textures/res%d/%s" % (words[0], self.steps, words[1])
            folder = getProperPath(os.path.dirname(newpath))
            if not os.path.exists(folder):
                os.makedirs(folder)
            return newpath
        else:
            msg = 'Illegal path: %s' % path
            print(msg)
            raise DazError(msg)


    def getNewPath(self, path):
        if GS.useLowerResFolders:
            path = self.getNewPathFolders(path)
        base,ext = os.path.splitext(path)
        if self.steps == 0:
            newbase = base
        elif len(base) > 5 and base[-5] == "_" and base[-4:].isdigit():
            newbase = ("%s-res%d%s" % (base[:-5], self.steps, base[-5:]))
        elif len(base) > 7 and base[-7:] == "_<UDIM>":
            newbase = ("%s-res%d%s" % (base[:-7], self.steps, base[-7:]))
        else:
            newbase = ("%s-res%d" % (base, self.steps))
        newname = bpy.path.basename(newbase)
        newpath = "%s%s" % (newbase, ext)
        return newname, newpath


class DAZ_OT_ChangeResolution(DazOperator, ChangeResolution):
    bl_idname = "daz.change_resolution"
    bl_label = "Change Resolution"
    bl_description = (
        "Change all textures of selected meshes with resized versions.\n" +
        "The resized textures must already exist.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)

    def draw(self, context):
        self.layout.prop(self, "steps")
        self.layout.prop(self, "useHiddenMeshes")

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        self.initResolution()
        self.overwrite = False
        paths = self.getAllTextures(context, True)
        self.getFileNames(paths.keys())
        self.replaceTextures(context)


class DAZ_OT_ResizeTextures(DazOperator, ImageFile, MultiFile, ChangeResolution):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = "Replace all textures of selected meshes with resized versions"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)

    def draw(self, context):
        self.layout.prop(self, "steps")
        self.layout.prop(self, "resizeAll")
        self.layout.prop(self, "useHiddenMeshes")

    def invoke(self, context, event):
        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures/")
        self.properties.filepath = texpath
        return MultiFile.invoke(self, context, event)

    def run(self, context):
        self.initResolution()
        if self.resizeAll:
            paths = self.getAllTextures(context, False)
        else:
            paths = self.getMultiFiles(theImageExtensions)
        self.getFileNames(paths)

        scale = int(2**self.steps)
        for path in paths:
            path = getProperPath(path)
            base = self.getBasePath(path)
            _,newpath = self.getNewPath(base)
            if not os.path.exists(newpath) and os.path.exists(base):
                img = bpy.data.images.load(base)
                if img is None:
                    print("Could not load %s" % base)
                    continue
                x,y = img.size
                img.scale(int(x/scale), int(y/scale))
                img.filepath_raw = newpath
                print("%s => %s: %s => %s" % (os.path.basename(path), os.path.basename(newpath), (x,y), tuple(img.size)))
                img.save()
                img.buffers_free()
            else:
                print("Skip", newpath)

        self.replaceTextures(context)

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
        from .tree import pruneMaterials
        for ob in getSelectedMeshes(context):
            pruneMaterials(ob,
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
#   Utility
#----------------------------------------------------------

def getProperPath(path):
    if path[0:2] == "//":
        return os.path.join(os.path.dirname(bpy.data.filepath), path[2:])
    return path

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


class DAZ_OT_UpdateRenderSettings(DazOperator):
    bl_idname = "daz.update_render_settings"
    bl_label = "Update Render Settings"
    bl_description = "Update render and light settings if they are inadequate"
    bl_options = {'UNDO'}

    def run(self, context):
        checkRenderSettings(context, True)

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

    def draw(self, context):
        self.layout.prop(self, "useCombineMaterials")

    def run(self, context):
        mats = {}
        for ob in getSelectedMeshes(context):
            for n,mat in enumerate(ob.data.materials):
                if mat:
                    mname = baseName(stripName(mat.name))
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
    for data in mats:
        ob.data.materials.append(data[2])
    assoc = {}
    for m,data in enumerate(mats):
        assoc[data[1]] = m
    for f in ob.data.polygons:
        f.material_index = assoc.get(mnums[f.index],0)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SaveLocalTextures,
    DAZ_OT_CombineSceneMaterials,
    DAZ_OT_MergeMaterials,
    DAZ_OT_CopyMaterials,
    DAZ_OT_PruneNodeTrees,
    DAZ_OT_ChangeResolution,
    DAZ_OT_ResizeTextures,
    DAZ_OT_UpdateRenderSettings,
    DAZ_OT_StripMaterialNames,
    DAZ_OT_SortMaterialsByName,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazLocalTextures = BoolProperty(default = False)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
