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
from .error import *


class DAZ_OT_ScanMorphDatabase(DazOperator, IsMesh):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = ""

    def run(self, context):
        from .load_json import saveJson
        from .morphing import getRigFromObject
        self.mesh = context.object
        self.rig = getRigFromObject(self.mesh)
        if not self.rig.DazUrl:
            raise DazError("Not a character")
        relfile,char = self.rig.DazUrl.rsplit("#",1)
        relpath = os.path.dirname(relfile)
        self.struct = {
            "name" : char,
            "path" : relpath,
        }
        LS.forMorphLoad(self.mesh)
        self.count = 100
        for dazpath in GS.getDazPaths():
            morphpath = "%s%s/Morphs" % (dazpath, relpath)
            morphpath = bpy.path.resolve_ncase(morphpath)
            self.scanMorphs(morphpath)
        folder = os.path.join(os.path.dirname(__file__), "data", "scanned")
        if not os.path.exists(folder):
            os.makedirs(folder)
        path = os.path.join(folder, "%s.json" % char)
        saveJson(self.struct, path)
        print("Database for %s scanned" % char)


    def scanMorphs(self, folderpath):
        if self.count < 0:
            return
        if not os.path.exists(folderpath):
            print("NOPE", folderpath)
            return
        for file in os.listdir(folderpath):
            path = os.path.join(folderpath, file)
            if os.path.isdir(path):
                self.scanMorphs(path)
            else:
                ext = os.path.splitext(file)[-1]
                if ext in [".duf", ".dsf"]:
                    self.scanMorph(path)


    def scanMorph(self, path):
        from .load_json import loadJson
        from .files import parseAssetFile
        from .formula import Formula
        if self.count < 0:
            return
        print("PP", path)
        struct = loadJson(path, silent=True)
        asset = parseAssetFile(struct)
        if isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh)
            infos = self.evalExprs(asset, exprs)
            if infos:
                self.count -= 1
                self.struct[asset.id] = infos


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

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ScanMorphDatabase,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

