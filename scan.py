# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import time
import bpy
from bpy.props import *
from .error import *
from .utils import *
from .animation import MorphOptions
from .fileutils import SingleFile

CURRENT_VERSION = 6

theScannedFiles = {}

ScanPaths = [("useGenesis", "Genesis", "/data/DAZ 3D/Genesis/Base"),
             ("useGenesis2Female", "Genesis2Female", "/data/DAZ 3D/Genesis 2/Female"),
             ("useGenesis2Male", "Genesis2Male", "/data/DAZ 3D/Genesis 2/Male"),
             ("useGenesis3Female", "Genesis3Female", "/data/DAZ 3D/Genesis 3/Female"),
             ("useGenesis3Male", "Genesis3Male", "/data/DAZ 3D/Genesis 3/Male"),
             ("useGenesis8Female", "Genesis8Female", "/data/DAZ 3D/Genesis 8/Female"),
             ("useGenesis8Male", "Genesis8Male", "/data/DAZ 3D/Genesis 8/Male"),
             ("useGenesis8_1Female", "Genesis8_1Female", "/data/DAZ 3D/Genesis 8/Female 8_1"),
             ("useGenesis8_1Male", "Genesis8_1Male", "/data/DAZ 3D/Genesis 8/Male 8_1"),
             ("useGenesis9", "Genesis9", "/data/DAZ 3D/Genesis 9/Base"),
            ]


AltNames = {
            "Genesis8Female" : ("Genesis8_1Female", "/data/Daz 3D/Genesis 8/Female 8_1"),
            "Genesis8_1Female" : ("Genesis8Female", "/data/Daz 3D/Genesis 8/Female"),
            "Genesis8Male" : ("Genesis8_1Male", "/data/Daz 3D/Genesis 8/Male 8_1"),
            "Genesis8_1Male" : ("Genesis8Male", "/data/Daz 3D/Genesis 8/Male"),
            }

#----------------------------------------------------------
#   CharSelector
#----------------------------------------------------------

class CharSelector:
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

    useGenesis9 : BoolProperty(
        name = "Genesis 9",
        description = "Scan Genesis 9",
        default = False)

    def getActive(self, ob):
        return (ob and ob.type in ['MESH', 'ARMATURE'])

    def draw(self, context):
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
            self.layout.prop(self, "useGenesis9")

#----------------------------------------------------------
#   Scanner
#----------------------------------------------------------

class Scanner:
    useDefins = False

    def setupScanner(self, name, url):
        self.ids = {}
        self.formulas = {}
        self.defins = {}
        self.minmax = {}
        self.alias = {}
        modified = time.time()
        struct = {
            "name" : name,
            "url" : url,
            "ids" : self.ids,
            "directory" : self.directory,
            "modified" : str(modified),
            "version" : CURRENT_VERSION,
            "definitions" : self.defins,
            "alias" : self.alias,
            "formulas" : self.formulas,
            "minmax" : self.minmax,
        }
        self.count = 0
        self.maxcount = 1000000
        #self.maxcount = 10
        return struct


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
            else:
                ext = os.path.splitext(file)[-1]
                if ext in [".duf", ".dsf"]:
                    self.scanMorph(path, nskip)


    def scanMorph(self, path, nskip):
        if self.count > self.maxcount:
            return
        from .load_json import loadJson
        from .files import parseAssetFile
        from .formula import Formula
        from .modifier import Alias, Morph, ChannelAsset
        print("* %s" % path[nskip:])
        struct = loadJson(path, silent=True)
        if "modifier_library" not in struct.keys():
            return
        asset = parseAssetFile(struct)
        ref = info = key = prop = None
        if asset is None:
            return
        else:
            ref,key = asset.id.rsplit("#",1)
            key = normKey(key)
            if key != asset.name:
                self.ids[asset.name] = key
        if isinstance(asset, Morph):
            exprs,rig2 = asset.evalFormulas(self.rig, self.mesh, False)
            info,prop = self.evalExprs(asset, exprs)
            prop = normKey(prop)
        elif isinstance(asset, Alias):
            target = asset.target_channel.rsplit("#",1)[-1]
            if target[-6:] == "?value":
                target = normKey(target[:-6])
                if key != target:
                    self.alias[key] = target
        elif isinstance(asset, Formula):
            exprs,rig2 = asset.evalFormulas(self.rig, self.mesh, False)
            info,_ = self.evalExprs(asset, exprs)
        if key is None:
            return
        if (self.useMinmax and
            asset.min is not None and
            asset.max is not None):
            self.minmax[key] = (asset.min, asset.max)
        if ref:
            filepath = bpy.path.resolve_ncase(unquote(ref))
            folder = os.path.dirname(filepath)
            fname = os.path.splitext(os.path.basename(filepath))[0]
            if (self.useDefins or
                key.lower() != normKey(fname) or
                folder != self.directory):
                self.defins[key] = filepath
        if info and self.useFormulas:
            if prop:
                self.formulas[normKey(prop)] = info
            else:
                self.formulas[key] = info
        if info or ref:
            self.count += 1
            self.updateProgress()


    def updateProgress(self):
        self.wm.progress_update(self.count)


    def evalExprs(self, asset, exprs):
        info = {}
        prop = None
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
                    if expr.props:
                        target = expr.props[0]
                        prop = normKey(target.key)
                        info[normKey(output)] = (target.points if target.points else target.factor)
                elif key in ["translation", "rotation", "scale", "general_scale"]:
                    return info,prop
        return info,prop

#----------------------------------------------------------
#   Scan directory
#----------------------------------------------------------

class DAZ_OT_ScanMorphDirectory(DazOperator, SingleFile, Scanner, IsMesh):
    bl_idname = "daz.scan_morph_directory"
    bl_label = "Scan Morph Directory"
    bl_description = "Scan a single directory for morphs for the present mesh,\nand build a database"

    useMinmax = False

    useFormulas : BoolProperty(
        name = "Formulas",
        description = "Include formulas",
        default = True)

    useSubdirs : BoolProperty(
        name = "Subdirectories",
        description = "Also scan top level subdirectories",
        default = True)

    useDefins : BoolProperty(
        name = "Definitions",
        description = "Include paths to definitions.\nIf morph and file names differ",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useFormulas")
        self.layout.prop(self, "useDefins")
        self.layout.prop(self, "useSubdirs")

    def invoke(self, context, event):
        from .fileutils import getFoldersFromObject
        dirs = getFoldersFromObject(context.object, ["Morphs/"])
        if dirs:
            self.filepath = dirs[0]
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        ob = self.mesh = context.object
        self.rig = getRigFromMesh(ob)
        folder = os.path.dirname(self.filepath)
        url = dazRna(self.mesh).DazUrl
        name = url.rsplit("#", 1)[-1]
        scanpath = getScanPath(name)
        self.directory = GS.getRelativePath(folder).lower()
        struct = self.setupScanner(name, url)
        LS.forMorphLoad(ob)
        self.scanMorphs(folder, len(folder))
        if self.useSubdirs:
            for file in os.listdir(folder):
                subdir = "%s/%s" % (folder, file)
                if os.path.isdir(subdir):
                    self.directory = GS.getRelativePath(subdir).lower()
                    self.scanMorphs(subdir, len(subdir))
        if dazRna(ob.data).DazGraftGroup:
            graft = struct["geograft"] = {}
            graft["vertex_count"] = dazRna(ob.data).DazVertexCount
        saveJson(struct, scanpath)
        print('Saved "%s"' % scanpath)


    def scanMorphs(self, folderpath, nskip):
        for file in os.listdir(folderpath):
            path = os.path.join(folderpath, file)
            if os.path.isfile(path):
                ext = os.path.splitext(file)[-1]
                if ext in [".duf", ".dsf"]:
                    self.scanMorph(path, nskip)

    def updateProgress(self):
        return


    def setInfo(self, info, output, prop, factor):
        if prop and factor and not (prop == output and factor == 1):
            info[prop] = factor

#----------------------------------------------------------
#   Scan morph database
#----------------------------------------------------------

class DAZ_OT_ScanMorphDatabase(DazPropsOperator, CharSelector, Scanner):
    bl_idname = "daz.scan_morph_database"
    bl_label = "Scan Morph Database"
    bl_description = "Scan the DAZ database\nfor morphs for the present mesh,\nand build a database"

    useFormulas = True
    useMinmax = True
    directory = None

    def run(self, context):
        active = self.getActive(context.object)
        if active and self.useActive:
            self.rig, self.mesh, name, relpath = getCharData(context, False)
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
        t1 = perf_counter()
        struct = self.setupScanner(name, relpath)
        self.wm = context.window_manager
        self.wm.progress_begin(0, self.maxcount)
        LS.forMorphLoad(self.mesh)
        for morphpath in GS.getAbsPaths("%s/Morphs" % relpath):
            self.scanMorphs(morphpath, len(morphpath))
        self.wm.progress_end()
        saveJson(struct, scanpath)
        theScannedFiles[name] = struct
        t2 = perf_counter()
        print("Database for %s scanned in %.3f seconds and saved in\n%s" % (name, t2-t1, scanpath))


def getCharData(context, error):
    from .finger import getFingeredCharacters
    rig,meshes,chars,modded = getFingeredCharacters(context.object, True, useGenesis=True)
    mesh = context.object
    if meshes and dazRna(meshes[0]).DazUrl:
        mesh = meshes[0]
    elif mesh.type != 'MESH':
        msg = "Cannot scan database because no mesh was found"
        if error:
            raise DazError(msg)
        else:
            print(msg)
            return rig, None, "Unknown", None
    relfile = dazRna(mesh).DazUrl.rsplit("#",1)[0]
    relpath = os.path.dirname(relfile)
    name = os.path.basename(os.path.splitext(relfile)[0])
    return rig, mesh, name, relpath


def getScanPath(name):
    scanPath = GS.getDazSettingsPath(GS.scanFile)
    if not os.path.exists(scanPath):
        os.makedirs(scanPath)
    return os.path.join(scanPath, "%s.json" % name)


def normKey(key):
    if key is None:
        return None
    else:
        return unquote(key)

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


def loadScannedInfo(self, name, rig, relpath):
    def loadScanned(name, scanpath):
        defins = formulas = minmax = alias = {}
        struct = getScannedFile(name, scanpath, True)
        if struct:
            formulas = struct["formulas"]
            minmax = struct["minmax"]
            if "alias" in struct.keys():
                alias = struct["alias"]
            if relpath:
                defins = struct["definitions"]
        return defins, formulas, minmax, alias

    table = {
        "Genesis3-female" : "Genesis3Female",
        "Genesis3-male" : "Genesis3Male",
        "Genesis8-female" : "Genesis8Female",
        "Genesis8-male" : "Genesis8Male",
    }

    if not relpath:
        name = table.get(dazRna(rig).DazMesh, dazRna(rig).DazMesh)
    scanpath = getScanPath(name)
    if not os.path.exists(scanpath):
        msg = "Scanned morphs for %s do not exist" % name
        print(msg)
        return False
        raise DazError(msg)
    self.defins, self.formulas, self.minmax, self.alias = loadScanned(name, scanpath)
    if name in AltNames.keys():
        name2,relpath2 = AltNames[name]
        scanpath2 = getScanPath(name2)
        self.defins2, self.formulas2, self.minmax2, self.alias2 = loadScanned(name2, scanpath2)
    return True

#----------------------------------------------------------
#   Load missing morphs
#----------------------------------------------------------

def loadMissingMorphs(self, context, rig, missing, cat):
    from .morphing import CustomMorphLoader, StandardMorphLoader, addToCategories
    if not missing or not self.defins:
        return False
    standards = {}
    customs = []
    for ref in missing:
        key = normKey(ref)
        path = self.defins.get(key)
        if path is None:
            path = self.defins2.get(key)
        if path:
            path = GS.getAbsPath(path)
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
        mloader.getFingeredRigMeshes(context)
        mloader.morphset = mset
        mloader.category = ""
        mloader.hideable = True
        print("\nLoading missing %s morphs" % mset)
        mloader.getAllMorphs(namepaths, context)
        again = True
    if customs:
        mloader = CustomMorphLoader()
        mloader.getFingeredRigMeshes(context)
        mloader.morphset = "Custom"
        mloader.category = cat
        mloader.hideable = True
        dazRna(rig).DazCustomMorphs = True
        print("\nLoading morphs in category %s" % cat)
        mloader.getAllMorphs(customs, context)
        props = [prop for (prop,path,ref) in customs]
        addToCategories(rig, props, None, cat)
        again = True
    return again


def getMorphSet(path):
    lpath = normalizePath(path).lower()
    for subdir,mgrps in [
        ("/daz 3d/base correctives/", "Jcms"),
        ("/daz 3d/base flexions/", "Flexions"),
        ("/daz 3d/base pose/", [("ectrlv", "Visemes"), ("ectrl", "Units"), "Body"]),
        ("/daz 3d/base pose head/", [("ectrlv", "Visemes"), "Units"]),
        ("/daz 3d/expressions/", "Expressions"),
        ("/daz 3d/facs/", "Facs"),
        ("/daz 3d/facsdetails/", "Facsdetails"),
        ("/daz 3d/facsexpressions/", "Facsexpr"),
        ("/daz 3d/powerpose/", "Powerpose"),
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
#   Check database
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
        morphpath = GS.getAbsPath("%s/Morphs" % relpath)
        if morphpath and checkFolder(morphpath, modified):
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

    useAll : BoolProperty(
        name = "All Characters",
        description = "Scan morph database for all character types",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useAll")
        if not self.useAll:
            CharSelector.draw(self, context)


    def run(self, context):
        if self.useAll:
            needs = []
            for attr,name,relpath in ScanPaths:
                needs += checkNeedUpdate(name, relpath)
        elif self.useActive and self.getActive(context.object):
            rig, mesh, name, relpath = getCharData(context, False)
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
            self.raiseWarning(msg, useDialog=True)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ScanMorphDatabase,
    DAZ_OT_CheckDatabase,
    DAZ_OT_ScanMorphDirectory,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

