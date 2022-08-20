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

CURRENT_VERSION = 5

theScannedFiles = {}

ScanPaths = [("useGenesis", "Genesis", "/data/DAZ 3D/Genesis/Base"),
             ("useGenesis2Female", "Genesis2Female", "/data/DAZ 3D/Genesis 2/Female"),
             ("useGenesis2Male", "Genesis2Male", "/data/DAZ 3D/Genesis 2/Male"),
             ("useGenesis3Female", "Genesis3Female", "/data/DAZ 3D/Genesis 3/Female"),
             ("useGenesis3Male", "Genesis3Male", "/data/DAZ 3D/Genesis 3/Male"),
             ("useGenesis8Female", "Genesis8Female", "/data/DAZ 3D/Genesis 8/Female"),
             ("useGenesis8Male", "Genesis8Male", "/data/DAZ 3D/Genesis 8/Male"),
             ("useGenesis8_1Female", "Genesis8_1Female", "/data/DAZ 3D/Genesis 8/Female 8_1"),
             ("useGenesis8_1Male", "Genesis8_1Male", "/data/DAZ 3D/Genesis 8/Male 8_1")
            ]


AltNames = {
            "Genesis8Female" : ("Genesis8_1Female", "/data/Daz 3D/Genesis 8/Female 8_1"),
            "Genesis8_1Female" : ("Genesis8Female", "/data/Daz 3D/Genesis 8/Female"),
            "Genesis8Male" : ("Genesis8_1Male", "/data/Daz 3D/Genesis 8/Male 8_1"),
            "Genesis8_1Male" : ("Genesis8Male", "/data/Daz 3D/Genesis 8/Male"),
            }

class CharSelector:
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


class DAZ_OT_ScanMorphDatabase(DazPropsOperator, CharSelector):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = "Scan the DAZ database\nfor morphs for the present mesh,\nand build a database"

    def run(self, context):
        active = self.getActive(context.object)
        if active and self.useActive:
            self.rig, self.mesh, name, relpath = getCharData(context)
            scanpath = getScanPath(name)
            self.scanCharacter(context, name, relpath, scanpath)
        else:
            self.rig = self.mesh = None
            for attr,name,relpath in ScanPaths:
                if getattr(self, attr):
                    scanpath = getScanPath(name)
                    self.scanCharacter(context, name, relpath, scanpath)


    def scanCharacter(self, context, name, relpath, scanpath):
        global theScannedFiles
        from .load_json import saveJson
        from time import perf_counter, ctime
        t1 = perf_counter()
        self.formulas = {}
        self.defins = {}
        self.minmax = {}
        modified = str(os.path.getmtime(scanpath))
        struct = {
            "name" : name,
            "path" : relpath,
            "modified" : modified,
            "version" : CURRENT_VERSION,
            "definitions" : self.defins,
            "formulas" : self.formulas,
            "minmax" : self.minmax,
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
        from .modifier import Morph, ChannelAsset
        print("* %s" % path[nskip:])
        struct = loadJson(path, silent=True)
        if "modifier_library" not in struct.keys():
            return
        asset = parseAssetFile(struct)
        ref = info = key = None
        if isinstance(asset, Morph):
            ref,key = asset.id.rsplit("#",1)
        elif isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh, False)
            info = self.evalExprs(asset, exprs)
            ref,key = asset.id.rsplit("#",1)
        if (key is not None and
            asset.min is not None and
            asset.max is not None):
            self.minmax[key] = (asset.min, asset.max)
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
            for key,value in data.items():
                if key == "*fileref":
                    ref,channel = value
                elif key == "value":
                    expr = value[0]
                    prop = expr["prop"]
                    factor = expr["factor"]
                elif key in ["translation", "rotation", "scale", "general_scale"]:
                    return {}
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

def getScannedFile(name, scanpath, checkVersion):
    global theScannedFiles
    if name not in theScannedFiles.keys():
        from .load_json import loadJson
        theScannedFiles[name] = loadJson(scanpath)
    struct = theScannedFiles[name]
    if struct and checkVersion:
        version = struct.get("version")
        if version is None or version < CURRENT_VERSION:
            msg = "Scanned database file for %s is outdated.\nPlease rescan database first" % name
            raise DazError(msg)
    return struct


def loadScannedInfo(self, name):
    def loadScanned(name, scanpath):
        defins = formulas = minmax = {}
        struct = getScannedFile(name, scanpath, True)
        if struct:
            defins = struct["definitions"]
            formulas = struct["formulas"]
            if "minmax" in struct.keys():
                minmax = struct["minmax"]
        return defins, formulas, minmax

    scanpath = getScanPath(name)
    if not os.path.exists(scanpath):
        raise DazError("Scanned morphs for %s do not exist" % name)
    self.defins, self.formulas, self.minmax = loadScanned(name, scanpath)
    if name in AltNames.keys():
        name2,relpath2 = AltNames[name]
        scanpath2 = getScanPath(name2)
        self.defins2, self.formulas2, self.minmax2 = loadScanned(name2, scanpath2)

#----------------------------------------------------------
#   Load missing morphs
#----------------------------------------------------------

def loadMissingMorphs(self, context, rig, missing, cat):
    def getFullPath(path):
        for folder in GS.getDazPaths():
            path1 = "%s%s" % (folder, path)
            fullpath = bpy.path.resolve_ncase(path1.replace("//", "/"))
            if os.path.exists(fullpath):
                return fullpath
        return None

    #from .asset import setDazPaths
    from .morphing import CustomMorphLoader, StandardMorphLoader, addToCategories
    if not missing:
        return False
    standards = {}
    customs = []
    #setDazPaths()
    for ref in missing:
        path = self.defins.get(ref)
        if path is None:
            path = self.defins2.get(ref)
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
    for subdir,mgrps in [
        ("/daz 3d/base correctives/", "Jcms"),
        ("/daz 3d/base flexions/", "Flexions"),
        ("/daz 3d/base pose/", [("ectrlv", "Visemes"), ("ectrl", "Units"), "BODY"]),
        ("/daz 3d/base pose head/", [("ectrlv", "Visemes"), "Units"]),
        ("/daz 3d/expressions/", "Expressions"),
        ("/daz 3d/facs/", "Facs"),
        ("/daz 3d/facsexpressions/", "Facsexpr"),
        ]:
        if isinstance(mgrps, list):
            morphgroup = None
            lfile = os.path.basename(lpath)
            for prefix,mgrp in mgrps[:-1]:
                if lfile.startswith(prefix):
                    morphgroup = mgrp
                    break
            if not morphgroup:
                morphgroup = mgrps[-1]
        else:
            morphgroup = mgrps
        if subdir in lpath:
            return morphgroup
    return "Custom"

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def checkNeedUpdate(name, relpath):
    def checkFolder(folder, modified):
        if not os.path.exists(folder):
            print('Directory does not exist:\n"%s"' % folder)
            return False
        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            mod = os.path.getmtime(path)
            if mod > modified:
                print("Modified path:", path)
                return True
            if os.path.isdir(path):
                if checkFolder(path, modified):
                    return True
        return False

    def checkChar(name, relpath):
        scanpath = getScanPath(name)
        if not os.path.exists(scanpath):
            return True
        struct = getScannedFile(name, scanpath, False)
        if struct:
            version = struct.get("version")
            if version != CURRENT_VERSION:
                return True
            modified = float(struct["modified"])
        for dazpath in GS.getDazPaths():
            morphpath = "%s%s/Morphs" % (dazpath, relpath)
            morphpath = bpy.path.resolve_ncase(morphpath)
            if checkFolder(morphpath, modified):
                return True
        return False

    needs = []
    if checkChar(name, relpath):
        needs.append(name)
    return needs


def checkNeedUpdates(name, relpath):
    needs = checkNeedUpdate(name, relpath)
    if name in AltNames.keys():
        name2,relpath2 = AltNames[name]
        if checkNeedUpdate(name2, relpath2):
            needs.append(name2)
    return needs


class DAZ_OT_CheckDatabase(DazPropsOperator, CharSelector):
    bl_idname = "daz.check_database"
    bl_label = "Check Database For Updates"
    bl_description = ""

    def run(self, context):
        active = self.getActive(context.object)
        if active and self.useActive:
            rig, mesh, name, relpath = getCharData(context)
            needs = checkNeedUpdates(name, relpath)
        else:
            needs = []
            for attr,name,relpath in ScanPaths:
                if getattr(self, attr):
                    needs += checkNeedUpdate(name, relpath)
        if needs:
            msg = "The following databases need to be rescanned:\n"
            for name in needs:
                msg += "    %s\n" % name
            raise DazError(msg, warning=True)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ScanMorphDatabase,
    DAZ_OT_CheckDatabase,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

