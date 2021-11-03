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
from mathutils import Vector, Matrix
from .asset import Asset
from .error import reportError
from .utils import LS, GS
from . import globvars as G

class FileAsset(Asset):

    def __init__(self, fileref, toplevel):
        Asset.__init__(self, fileref)
        self.nodes = []
        self.modifiers = []
        self.uvs = []
        self.materials = []
        self.animations = []
        self.instances = {}
        self.extras = []
        self.sources = []
        self.toplevel = toplevel
        if toplevel:
            self.caller = self
            self.camera = None


    def __repr__(self):
        return ("<File %s>" % self.id)


    def parse(self, struct):
        msg = ("+FILE %s" % self.fileref)
        G.theTrace.append(msg)
        if GS.verbosity > 4:
            print(msg)

        sources = []
        if "asset_info" in struct.keys():
            Asset.parse(self, struct["asset_info"])

        if LS.useUV and "uv_set_library" in struct.keys():
            from .geometry import Uvset
            for ustruct in struct["uv_set_library"]:
                asset = self.parseTypedAsset(ustruct, Uvset)
                self.uvs.append(asset)

        if LS.useGeometries and "geometry_library" in struct.keys():
            from .geometry import Geometry
            for gstruct in struct["geometry_library"]:
                asset = self.parseTypedAsset(gstruct, Geometry)

        if LS.useNodes and "node_library" in struct.keys():
            from .node import parseNode
            for nstruct in struct["node_library"]:
                asset = parseNode(self, nstruct)

        if LS.useModifiers and "modifier_library" in struct.keys():
            from .modifier import parseModifierAsset
            for mstruct in struct["modifier_library"]:
                asset = parseModifierAsset(self, mstruct)

        if LS.useImages and "image_library" in struct.keys():
            from .material import Images
            for mstruct in struct["image_library"]:
                asset = self.parseTypedAsset(mstruct, Images)

        if LS.useMaterials and "material_library" in struct.keys():
            from .cycles import CyclesMaterial
            for mstruct in struct["material_library"]:
                asset = self.parseTypedAsset(mstruct, CyclesMaterial)

        if "scene" in struct.keys():
            scene = struct["scene"]

            if LS.useNodes and "nodes" in scene.keys():
                from .node import Node
                from .geometry import Geometry
                from .bone import Bone
                for nstruct in scene["nodes"]:
                    asset = self.parseUrlAsset(nstruct)
                    if isinstance(asset, Geometry):
                        reportError("Bug: expected node not geometry.\n%s" % asset, trigger=(2,3))
                    elif asset:
                        inst = asset.makeInstance(self.fileref, nstruct)
                        self.instances[inst.id] = inst
                        self.nodes.append((asset, inst))

            if LS.useMaterials and "materials" in scene.keys():
                for mstruct in scene["materials"]:
                    from .cycles import CyclesMaterial
                    from copy import deepcopy
                    if "url" in mstruct.keys():
                        base = self.getAsset(mstruct["url"])
                    else:
                        base = None
                    asset = CyclesMaterial(self.fileref)
                    asset.parse(mstruct)
                    if base:
                        asset.channels = deepcopy(base.channels)
                    asset.update(mstruct)
                    self.materials.append(asset)

            if LS.useModifiers and "modifiers" in scene.keys():
                for mstruct in scene["modifiers"]:
                    asset = self.parseUrlAsset(mstruct)
                    if asset is None:
                        continue
                    if "parent" in mstruct.keys():
                        par = self.getAsset(mstruct["parent"])
                        if par:
                            inst = par.getInstance(mstruct["parent"], self)
                        else:
                            inst = None
                    else:
                        par = inst = None
                    self.modifiers.append((asset,inst))

            if self.toplevel:
                self.parseRender(scene)

        msg = ("-FILE %s" % self.fileref)
        G.theTrace.append(msg)
        if GS.verbosity > 4:
            print(msg)
        return self


    def makeLocalNode(self, struct):
        from .asset import storeAsset
        if "preview" in struct.keys():
            preview = struct["preview"]
        else:
            return None
        if preview["type"] == "figure":
            from .figure import Figure
            asset = Figure(self.fileref)
        elif preview["type"] == "bone":
            from .bone import Bone
            asset = Bone(self.fileref)
        else:
            from .node import Node
            asset = Node(self.fileref)
        head = asset.attributes["center_point"] = Vector(preview["center_point"])
        tail = asset.attributes["end_point"] = Vector(preview["end_point"])
        xaxis = (tail-head).normalized()
        yaxis = Vector((0,1,0))
        zaxis = -xaxis.cross(yaxis).normalized()
        omat = Matrix((xaxis,yaxis,zaxis)).transposed()
        orient = Vector(omat.to_euler())
        tail = asset.attributes["orientation"] = orient
        asset.rotation_order = preview["rotation_order"]

        asset.parse(struct)
        asset.update(struct)
        self.saveAsset(struct, asset)
        if "url" in struct.keys():
            url = struct["url"]
            storeAsset(asset, url)
        if "geometries" in struct.keys():
            geos = struct["geometries"]
            for n,geonode in enumerate(asset.geometries):
                storeAsset(geonode, geonode.id)
                inst = geonode.makeInstance(self.fileref, geos[n])
                self.instances[inst.id] = inst
                self.nodes.append((geonode, inst))
                geo = geonode.data
                if geo:
                    for mname in geo.polygon_material_groups:
                        ref = self.fileref + "#" + mname
                        dmat = self.getAsset(ref)
                        if dmat and dmat not in self.materials:
                            self.materials.append(dmat)
        return asset


    def parseRender(self, scene):
        if "current_camera" in scene.keys():
            self.camera = self.getAsset(scene["current_camera"])
        backdrop = {}
        if "backdrop" in scene.keys():
            backdrop = scene["backdrop"]
        if "extra" in scene.keys():
            sceneSettings = renderSettings = {}
            for extra in scene["extra"]:
                if extra["type"] == "studio_scene_settings":
                    sceneSettings = extra
                elif extra["type"] == "studio_render_settings":
                    renderSettings = extra
            if renderSettings:
                from .render import parseRenderOptions
                parseRenderOptions(renderSettings, sceneSettings, backdrop, self.fileref)


    def parseTypedAsset(self, struct, typedAsset):
        from .asset import getAssetFromStruct
        from .geometry import Geometry
        if "url" in struct.keys():
            return self.parseUrlAsset(struct)
        else:
            asset = getAssetFromStruct(struct, self.fileref)
            if asset:
                if isinstance(asset, Geometry):
                    msg = ("Duplicate geometry definition:\n  %s" % asset)
                    reportError(msg, trigger=(2,4))
                return asset
            else:
                asset = typedAsset(self.fileref)
            asset.parse(struct)
            self.saveAsset(struct, asset)
            return asset


    def build(self, context):
        print("BUILD FILE?", self)
        for asset in self.assets:
            if asset.type == "figure":
                asset.build(context)


def getUrlPath(url):
    relpath = url.split("#")[0]
    return relpath, getDazPath(relpath)


def parseAssetFile(struct, toplevel=False, fileref=None):
    from .asset import storeAsset, getId, getExistingFile
    if fileref is None and "asset_info" in struct.keys():
        ainfo = struct["asset_info"]
        if "id" in ainfo.keys():
            fileref = getId(ainfo["id"], "")
    if fileref is None:
        return None
    asset = getExistingFile(fileref)
    if asset is None:
        asset = FileAsset(fileref, toplevel)
        storeAsset(asset, fileref)

    if asset is None:
        return None
    elif LS.useMorphOnly:
        from .modifier import parseMorph
        return parseMorph(asset, struct)
    else:
        return asset.parse(struct)
