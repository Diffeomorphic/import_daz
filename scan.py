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


class DAZ_OT_ScanMorphDatabase(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = "Scan the DAZ database\nfor morphs for the present mesh,\nand build a database"

    useActive : BoolProperty(
        name = "Scan Active Mesh",
        description = "Only scan morphs for active mesh",
        default = True)

    useGenesis : BoolProperty(
        name = "Genesis",
        description = "Scan Genesis",
        default = False)

    useGenesis2Female : BoolProperty(
        name = "Genesis 2 Female",
        description = "Scan Genesis 2 female",
        default = False)

    useGenesis2Male : BoolProperty(
        name = "Genesis 2 Male",
        description = "Scan Genesis 2 male",
        default = False)

    useGenesis3Female : BoolProperty(
        name = "Genesis 3 Female",
        description = "Scan Genesis 3 female",
        default = False)

    useGenesis3Male : BoolProperty(
        name = "Genesis 3 Male",
        description = "Scan Genesis 3 male",
        default = False)

    useGenesis8Female : BoolProperty(
        name = "Genesis 8 Female",
        description = "Scan Genesis 8 female",
        default = False)

    useGenesis8Male : BoolProperty(
        name = "Genesis 8 Male",
        description = "Scan Genesis 8 male",
        default = False)

    useGenesis8_1Female : BoolProperty(
        name = "Genesis 8.1 Female",
        description = "Scan Genesis 8.1 female",
        default = False)

    useGenesis8_1Male : BoolProperty(
        name = "Genesis 8.1 Male",
        description = "Scan Genesis 8.1 male",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useActive")
        if not self.useActive:
            self.layout.separator()
            self.layout.prop(self, "useGenesis")
            self.layout.prop(self, "useGenesis2Female")
            self.layout.prop(self, "useGenesis2Male")
            self.layout.prop(self, "useGenesis3Female")
            self.layout.prop(self, "useGenesis3Male")
            self.layout.prop(self, "useGenesis8Female")
            self.layout.prop(self, "useGenesis8Male")
            self.layout.prop(self, "useGenesis8_1Female")
            self.layout.prop(self, "useGenesis8_1Male")

    def run(self, context):
        if self.useActive:
            self.rig, self.mesh, name, relpath, scanpath = getCharData(context)
            self.scanCharacter(context, name, relpath, scanpath)
        else:
            self.rig = self.mesh = None
            for attr,name,relpath in [
                ("useGenesis", "Genesis", "/data/DAZ 3D/Genesis/Base"),
                ("useGenesis2Female", "Genesis2Female", "/data/DAZ 3D/Genesis 2/Female"),
                ("useGenesis2Male", "Genesis2Male", "/data/DAZ 3D/Genesis 2/Male"),
                ("useGenesis3Female", "Genesis3Female", "/data/DAZ 3D/Genesis 3/Female"),
                ("useGenesis3Male", "Genesis3Male", "/data/DAZ 3D/Genesis 3/Male"),
                ("useGenesis8Female", "Genesis8Female", "/data/DAZ 3D/Genesis 8/Female"),
                ("useGenesis8Male", "Genesis8Male", "/data/DAZ 3D/Genesis 8/Male"),
                ("useGenesis8_1Female", "Genesis8_1Female", "/data/DAZ 3D/Genesis 8/Female 8_1"),
                ("useGenesis8_1Male", "Genesis8_1Male", "/data/DAZ 3D/Genesis 8/Male 8_1")
                ]:
                if getattr(self, attr):
                    scanpath = getScanPath(name)
                    self.scanCharacter(context, name, relpath, scanpath)


    def scanCharacter(self, context, name, relpath, scanpath):
        from .load_json import saveJson
        from time import perf_counter
        t1 = perf_counter()
        self.morphs = {}
        struct = {
            "name" : name,
            "path" : relpath,
            "morphs" : self.morphs,
        }
        self.count = 0
        self.maxcount = 1000000
        self.wm = context.window_manager
        self.wm.progress_begin(0, self.maxcount)
        LS.forMorphLoad(self.mesh)
        for dazpath in GS.getDazPaths():
            morphpath = "%s%s/Morphs" % (dazpath, relpath)
            morphpath = bpy.path.resolve_ncase(morphpath)
            self.scanMorphs(morphpath, len(morphpath))
        self.wm.progress_end()
        saveJson(struct, scanpath)
        t2 = perf_counter()
        print("Database for %s scanned in %.3f seconds" % (name, t2-t1))


    def scanMorphs(self, folderpath, nskip):
        def isExcluded(path):
            lpath = path.lower().replace("\\", "/")
            return lpath.endswith(
                ("/daz 3d/base",
                 "/daz 3d/base correctives",
                 "/daz 3d/base flexions",
                 "/daz 3d/base pose",
                 "/daz 3d/base pose head",
                 "/daz 3d/body",
                 "/daz 3d/control rig",
                 "/daz 3d/clones",
                 "/daz 3d/expressions",
                 "/daz 3d/facs",
                 "/daz 3d/head",
                 ))

        if self.count > self.maxcount:
            return
        if not os.path.exists(folderpath):
            print('Directory does not exist:\n"%s"' % folderpath)
            return
        for file in os.listdir(folderpath):
            path = os.path.join(folderpath, file)
            if os.path.isdir(path):
                self.scanMorphs(path, nskip)
            elif isExcluded(folderpath):
                pass
            elif file[0:5] != "alias":
                ext = os.path.splitext(file)[-1]
                if ext in [".duf", ".dsf"]:
                    self.scanMorph(path, nskip)


    def scanMorph(self, path, nskip):
        if self.count > self.maxcount:
            return
        from .load_json import loadJson
        from .files import parseAssetFile
        from .formula import Formula
        print("* %s" % path[nskip:])
        struct = loadJson(path, silent=True)
        asset = parseAssetFile(struct)
        if isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh, False)
            infos = self.evalExprs(asset, exprs)
            if infos:
                self.count += 1
                self.wm.progress_update(self.count)
                key = asset.id.rsplit("#",1)[-1]
                self.morphs[key.lower()] = infos


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
            if prop and factor and channel=="value":
                info = {
                    "morph" : output,
                    "factor" : factor,
                }
                infos.append(info)
        return infos


def getCharData(context):
    from .finger import getFingeredCharacter
    rig, mesh = getFingeredCharacter(context.object, GS.useModifiedMesh)[0:2]
    if mesh is None or not mesh.DazUrl:
        raise DazError("No mesh found")
    relfile = mesh.DazUrl.rsplit("#",1)[0]
    relpath = os.path.dirname(relfile)
    name = os.path.basename(os.path.splitext(relfile)[0])
    scanpath = getScanPath(name)
    return rig, mesh, name, relpath, scanpath


def getScanPath(name):
    folder = os.path.join(os.path.dirname(__file__), "data", "scanned")
    if not os.path.exists(folder):
        os.makedirs(folder)
    return os.path.join(folder, "%s.json" % name)

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
        self.rig, self.mesh, name, relpath, scanpath = getCharData(context)
        scn = context.scene
        self.useInsertKeys = scn.tool_settings.use_keyframe_insert_auto
        if not os.path.exists(scanpath):
            raise DazError("Scanned morphs for %s do not exist" % name)
        filepaths = self.getMultiFiles(["duf", "dsf"])
        if filepaths:
            struct = loadJson(scanpath)
            self.scanned = struct["morphs"]
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

