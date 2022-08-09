# Copyright (c) 2016-2022, Thomas Larsson
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

import os
import bpy
from bpy.props import *
from .error import *
from .utils import *


class DAZ_OT_ScanMorphDatabase(DazOperator, IsMeshArmature):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = ""

    def run(self, context):
        from .load_json import saveJson
        from .finger import getFingeredCharacter
        self.rig, self.mesh = getFingeredCharacter(context.object, GS.useModifiedMesh)[0:2]
        if not self.rig.DazUrl:
            raise DazError("Not a character")
        relfile,char = self.rig.DazUrl.rsplit("#",1)
        relpath = os.path.dirname(relfile)
        self.struct = {}
        LS.forMorphLoad(self.mesh)
        self.count = 1000
        for dazpath in GS.getDazPaths():
            morphpath = "%s%s/Morphs" % (dazpath, relpath)
            morphpath = bpy.path.resolve_ncase(morphpath)
            self.scanMorphs(morphpath, len(morphpath))
        folder = os.path.join(os.path.dirname(__file__), "data", "scanned")
        if not os.path.exists(folder):
            os.makedirs(folder)
        path = os.path.join(folder, "%s.json" % char)
        saveJson(self.struct, path)
        print("Database for %s scanned" % char)


    def scanMorphs(self, folderpath, n):
        if self.count < 0:
            return
        if not os.path.exists(folderpath):
            print("NOPE", folderpath)
            return
        for file in os.listdir(folderpath):
            path = os.path.join(folderpath, file)
            if os.path.isdir(path):
                self.scanMorphs(path, n)
            else:
                ext = os.path.splitext(file)[-1]
                if ext in [".duf", ".dsf"]:
                    self.scanMorph(path, n)


    def scanMorph(self, path, n):
        if self.count < 0:
            return
        from .load_json import loadJson
        from .files import parseAssetFile
        from .formula import Formula
        print("* %s" % path[n:])
        struct = loadJson(path, silent=True)
        asset = parseAssetFile(struct)
        if isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh)
            infos = self.evalExprs(asset, exprs)
            if infos:
                self.count -= 1
                key = asset.id.rsplit("#",1)[-1]
                self.struct[key.lower()] = infos


    def evalExprs(self, asset, exprs):
        infos = []
        for output,data in exprs.items():
            ref = None
            channel = None
            prop = None
            factor = 0
            if "*fileref" in data.keys():
                ref,channel = data["*fileref"]
            if "value" in data.keys():
                expr = data["value"][0]
                prop = expr["prop"]
                factor = expr["factor"]
            if ref and prop and factor and channel=="value":
                info = {
                    "path" : ref,
                    "morph" : output,
                    "factor" : factor,
                }
                infos.append(info)
        return infos

#-------------------------------------------------------------
#   Import Scanned Morph
#-------------------------------------------------------------

from .fileutils import MultiFile, DazImageFile

class DAZ_OT_ImportScanned(DazOperator, MultiFile, DazImageFile, IsMeshArmature):
    bl_idname = "daz.import_scanned"
    bl_label = "Import Morph"
    bl_description = "Import morphs only from DAZ pose preset file(s),\nusing the scanned morph database for missing morphs"
    bl_options = {'UNDO'}

    def draw(self, context):
        toolset = context.scene.tool_settings
        self.layout.prop(toolset, "use_keyframe_insert_auto")


    def run(self, context):
        from .load_json import loadJson
        from .morphing import clearAllMorphs
        from .finger import getFingeredCharacter
        self.rig, self.mesh = getFingeredCharacter(context.object, GS.useModifiedMesh)[0:2]
        scn = context.scene
        self.useInsertKeys = scn.tool_settings.use_keyframe_insert_auto
        _,char = self.rig.DazUrl.rsplit("#",1)
        folder = os.path.join(os.path.dirname(__file__), "data", "scanned")
        if not os.path.exists(folder):
            os.makedirs(folder)
        scanpath = os.path.join(folder, "%s.json" % char)
        if not os.path.exists(scanpath):
            raise DazError("Scanned morphs for %s do not exist" % char)
        filepaths = self.getMultiFiles(["duf", "dsf"])
        if filepaths:
            self.scanned = loadJson(scanpath)
            #clearAllMorphs(self.rig, scn.frame_current, self.useInsertKeys)
            for n,filepath in enumerate(filepaths):
                self.importFile(filepath, scn.frame_current + n)
            updateDrivers(self.rig)


    def importFile(self, filepath, frame):
        from .load_json import loadJson
        struct = loadJson(filepath, False)
        scene = struct.get("scene")
        if scene is None:
            return
        anims = scene.get("animations")
        if anims is None:
            return
        prefix = "name://@selection#"
        suffix = ":?value/value"
        m = len(prefix)
        n = len(suffix)
        keyframes = {}
        for anim in anims:
            url = anim["url"]
            if url[0:m] == prefix and url[-n:] == suffix:
                prop = url[m:-n]
                if prop in self.rig.keys():
                    morphs = [(prop, 1.0)]
                elif prop in self.scanned.keys():
                    morphs = [(data["morph"], data["factor"]) for data in self.scanned[prop]]
                else:
                    continue
                for t,value in anim["keys"]:
                    if t not in keyframes.keys():
                        keyframes[t] = {}
                    data = keyframes[t]
                    for prop,factor in morphs:
                        if prop not in data.keys():
                            data[prop] = 0.0
                        data[prop] += value*factor
        for t,data in keyframes.items():
            for prop,value in data.items():
                if prop in self.rig.keys():
                    self.rig[prop] = value
                    if self.useInsertKeys:
                        self.rig.keyframe_insert(propRef(prop), frame=frame+t, group=prop)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ScanMorphDatabase,
    DAZ_OT_ImportScanned,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

