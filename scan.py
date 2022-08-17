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
from .animation import MorphOptions

CURRENT_VERSION = 3

theScannedFiles = {}

class DAZ_OT_ScanMorphDatabase(DazPropsOperator):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = "Scan the DAZ database\nfor morphs for the present mesh,\nand build a database"

    useStandardMorphs : BoolProperty(
        name = "Include Standard Morphs",
        description = "Include standard morphs bundled with DAZ Studio in scan.\nSlows down scanning but necessary to find missing standard morphs",
        default = True)

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

    def getActive(self, ob):
        return (ob and ob.type in ['MESH', 'ARMATURE'])

    def draw(self, context):
        #self.layout.prop(self, "useStandardMorphs")
        active = self.getActive(context.object)
        if active:
            self.layout.prop(self, "useActive")
            self.layout.separator()
        if not (active and self.useActive):
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
        active = self.getActive(context.object)
        if active and self.useActive:
            self.rig, self.mesh, name, relpath = getCharData(context)
            scanpath = getScanPath(name)
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
        global theScannedFiles
        from .load_json import saveJson
        from time import perf_counter
        t1 = perf_counter()
        self.formulas = {}
        self.defins = {}
        struct = {
            "name" : name,
            "path" : relpath,
            "version" : CURRENT_VERSION,
            "definitions" : self.defins,
            "formulas" : self.formulas,
        }
        self.count = 0
        self.maxcount = 1000000
        #self.maxcount = 10
        self.wm = context.window_manager
        self.wm.progress_begin(0, self.maxcount)
        LS.forMorphLoad(self.mesh)
        for dazpath in GS.getDazPaths():
            morphpath = "%s%s/Morphs" % (dazpath, relpath)
            morphpath = bpy.path.resolve_ncase(morphpath)
            self.scanMorphs(morphpath, len(morphpath))
        self.wm.progress_end()
        saveJson(struct, scanpath)
        theScannedFiles[name] = struct
        t2 = perf_counter()
        print("Database for %s scanned in %.3f seconds and saved in\n%s" % (name, t2-t1, scanpath))


    def scanMorphs(self, folderpath, nskip):
        if self.count > self.maxcount:
            return
        if not os.path.exists(folderpath):
            print('Directory does not exist:\n"%s"' % folderpath)
            return
        for file in os.listdir(folderpath):
            path = os.path.join(folderpath, file)
            if os.path.isdir(path):
                self.scanMorphs(path, nskip)
            elif not self.useStandardMorphs and getMorphSet(folderpath) != "Custom":
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
        from .modifier import Morph
        from .channels import Channels
        print("* %s" % path[nskip:])
        struct = loadJson(path, silent=True)
        if "modifier_library" not in struct.keys():
            print("NOPE", path)
            return
        asset = parseAssetFile(struct)
        ref = info = None
        if isinstance(asset, Morph):
            ref,key = asset.id.rsplit("#",1)
        elif isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh, False)
            info = self.evalExprs(asset, exprs)
            ref,key = asset.id.rsplit("#",1)
        elif isinstance(asset, Channels):
            print("CHA", asset)
            pass
        if ref:
            filepath = bpy.path.resolve_ncase(unquote(ref))
            #key = key.lower()
            self.defins[key] = filepath
        if info:
            self.formulas[key] = info
        if info or ref:
            self.count += 1
            self.wm.progress_update(self.count)


    def evalExprs(self, asset, exprs):
        info = {}
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
                info[output] = factor
        return info


def getCharData(context):
    from .finger import getFingeredCharacter
    rig, mesh = getFingeredCharacter(context.object, GS.useModifiedMesh)[0:2]
    if mesh is None or not mesh.DazUrl:
        raise DazError("No mesh found")
    relfile = mesh.DazUrl.rsplit("#",1)[0]
    relpath = os.path.dirname(relfile)
    name = os.path.basename(os.path.splitext(relfile)[0])
    return rig, mesh, name, relpath


def getScanPath(name):
    if not os.path.exists(GS.scanPath):
        os.makedirs(GS.scanPath)
    return os.path.join(GS.scanPath, "%s.json" % name)

#----------------------------------------------------------
#   Load scanned info
#----------------------------------------------------------

def loadScannedInfo(name):
    def loadScanned(name, scanpath):
        global theScannedFiles
        if name not in theScannedFiles.keys():
            from .load_json import loadJson
            theScannedFiles[name] = loadJson(scanpath)
        struct = theScannedFiles[name]
        if struct:
            version = struct.get("version")
            if version is None or version < CURRENT_VERSION:
                msg = "Scanned database file for %s is outdated.\nPlease rescan database first" % name
                raise DazError(msg)
            return struct["definitions"], struct["formulas"]
        else:
            return {}, {}

    altNames = {
        "Genesis8Female" : "Genesis8_1Female",
        "Genesis8_1Female" : "Genesis8Female",
        "Genesis8Male" : "Genesis8_1Male",
        "Genesis8_1Male" : "Genesis8Male",
    }

    scanpath = getScanPath(name)
    if not os.path.exists(scanpath):
        raise DazError("Scanned morphs for %s do not exist" % name)
    defins, formulas = loadScanned(name, scanpath)
    name2 = altNames.get(name)
    if name2:
        scanpath2 = getScanPath(name2)
        defins2, formulas2 = loadScanned(name2, scanpath2)
    return defins, defins2, formulas, formulas2

#----------------------------------------------------------
#   Load missing morphs
#----------------------------------------------------------

def loadMissingMorphs(context, rig, missing, cat, defins, defins2):
    def getFullPath(path):
        for folder in G.theDazPaths:
            path1 = "%s%s" % (folder, path)
            fullpath = bpy.path.resolve_ncase(path1.replace("//", "/"))
            if os.path.exists(fullpath):
                return fullpath
        return None

    from .asset import setDazPaths
    from .morphing import CustomMorphLoader, StandardMorphLoader, addToCategories
    if not missing:
        return False
    standards = {}
    customs = []
    setDazPaths()
    for ref in missing:
        path = defins.get(ref)
        if path is None:
            path = defins2.get(ref)
        if path:
            path = getFullPath(path)
        if path:
            mset = getMorphSet(path)
            if mset == "Custom":
                customs.append((ref, path, mset))
            elif mset is not None:
                if mset not in standards.keys():
                    standards[mset] = []
                standards[mset].append((ref, path, mset))
    again = False
    for mset,namepaths in standards.items():
        mloader = StandardMorphLoader()
        mloader.morphset = mset
        mloader.category = ""
        mloader.hideable = True
        print("\nLoading missing %s morphs" % mset)
        mloader.getAllMorphs(namepaths, context, True)
        again = True
    if customs:
        mloader = CustomMorphLoader()
        rig.DazCustomMorphs = True
        mloader.morphset = "Custom"
        mloader.category = cat
        mloader.hideable = True
        print("\nLoading morphs in category %s" % cat)
        mloader.getAllMorphs(customs, context, True)
        props = [prop for (prop,path,ref) in customs]
        addToCategories(rig, props, cat)
        again = True
    return again


def getMorphSet(path):
    lpath = path.lower().replace("\\", "/")
    for subdir,morphgroup in [
        ("/daz 3d/base/", "Units"),
        ("/daz 3d/base correctives/", "Jcms"),
        ("/daz 3d/base flexions/", "Flexions"),
        ("/daz 3d/base pose/", "Body"),
        ("/daz 3d/base pose head/", "Units"),
        ("/daz 3d/expressions/", "Expressions"),
        ("/daz 3d/facs/", "Facs"),
        ("/daz 3d/facsexpressions/", "Facsexpr"),
        ]:
        if subdir in lpath:
            return morphgroup
    return "Custom"

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

