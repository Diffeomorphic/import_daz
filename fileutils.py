# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import json
from collections import OrderedDict
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .error import *
from .utils import *

#-------------------------------------------------------------
#   Global variables
#-------------------------------------------------------------

theImageExtensions = ["png", "jpeg", "jpg", "bmp", "tif", "tiff"]

class DataFolders:
    def __init__(self):
        self.converters = {}
        self.restposes = {}
        self.parents = {}
        self.ikposes = {}
        self.presets = {}
        self.lowpoly = {}
        self.softbody = {}
        self.altmorphs = {}
        self.scanned = {}
        self.tiles = {}
        self.gizmos = {}
        self.easy = {}
        self.rigify = {}

        self.SourceRigs = {
            "genesis" : "genesis1",
            "genesis_2_female" : "genesis2",
            "genesis_2_male" : "genesis2",
            "genesis_3_female" : "genesis3",
            "genesis_3_male" : "genesis3",
            "genesis_8_female" : "genesis8",
            "genesis_8_male" : "genesis8",
            "genesis_9" : "genesis9",
            "victoria_4" : "genesis3",
            "victoria_7" : "genesis3",
            "victoria_8" : "genesis8",
            "michael_4" : "genesis3",
            "michael_7" : "genesis3",
            "michael_8" : "genesis8",
        }

        self.ParentRigs = {
            "genesis" : "genesis",
            "genesis_2_female" : "genesis_2_female",
            "genesis_2_male" : "genesis_2_male",
            "genesis_3_female" : "genesis_3_female",
            "genesis_3_male" : "genesis_3_male",
            "genesis_8_female" : "genesis_8_female",
            "genesis_8_male" : "genesis_8_male",
            "genesis_9" : "genesis_9",
            "victoria_4" : "genesis_3_female",
            "victoria_7" : "genesis_3_female",
            "victoria_8" : "genesis_8_female",
            "michael_4" : "genesis_3_male",
            "michael_7" : "genesis_3_male",
            "michael_8" : "genesis_8_male",
        }

        self.AltRigNames = {
            "Genesis" : "genesis",
            "Genesis2-female" : "genesis_2_female",
            "Genesis2-male" : "genesis_2_male",
            "Genesis3-female" : "genesis_3_female",
            "Genesis3-male" : "genesis_3_male",
            "Genesis8-female" : "genesis_8_female",
            "Genesis8-male" : "genesis_8_male",
            "Genesis9" : "genesis_9",
        }

        self.TwistBones = {}
        self.TwistBones["genesis3"] = [
            ("lShldrBend", "lShldrTwist"),
            ("rShldrBend", "rShldrTwist"),
            ("lForearmBend", "lForearmTwist"),
            ("rForearmBend", "rForearmTwist"),
            ("lThighBend", "lThighTwist"),
            ("rThighBend", "rThighTwist"),
        ]
        self.TwistBones["genesis8"] = self.TwistBones["genesis3"]

        self.WidgetControls = [
            "/data/daz 3d/genesis 8/genesis 8_1 face controls/genesis 8.1 face controls.dsf#genesis 8.1 face controls",
            "/data/daz 3d/genesis 8/genesis 8_1 male face controls/genesis 8.1 male face controls.dsf#genesis 8.1 male face controls",
            "/data/laudanum/advance pussy/advancepussy_controls_v2/advance_pussy_controls_2073.dsf#advance_pussy_controls_2073",
        ]

        self.RestPoseItems = []
        folder = os.path.join(os.path.dirname(__file__), "data", "restposes")
        for file in os.listdir(folder):
            fname = os.path.splitext(file)[0]
            name = fname.replace("_", " ").capitalize()
            self.RestPoseItems.append((fname, name, name))


    def loadEntry(self, char, folder, strict=True):
        table = getattr(self, folder)
        if char in table.keys():
            return table[char]
        filepath = os.path.join(os.path.dirname(__file__), "data", folder, char +  ".json")
        print("Load", filepath, strict)
        if not os.path.exists(filepath):
            if strict:
                msg = "File does not exist:\n%s                 " % filepath
                print(msg)
                raise DazError(msg)
            else:
                data = {}
        else:
            with safeOpen(filepath, "r") as fp:
                data = json.load(fp, object_pairs_hook=OrderedDict)
        table[char] = data
        return table[char]


    def getOrientation(self, char, bname):
        entry = self.loadEntry(char, "restposes")
        poses = entry["pose"]
        if bname in poses.keys():
            orient, xyz = poses[bname][-2:]
            return orient, xyz
        else:
            return None, "XYZ"


    def getCenter(self, char):
        entry = self.loadEntry(char, "restposes", False)
        if "center" in entry.keys():
            return Vector(entry["center"])


DF = DataFolders()

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

def safeOpen(filepath, rw, encoding="utf-8-sig"):
    filepath = bpy.path.resolve_ncase(filepath)
    try:
        fp = open(filepath, rw, encoding=encoding)
    except FileNotFoundError:
        fp = None

    if fp is None:
        if rw[0] == "r":
            mode = "reading"
        else:
            mode = "writing"
        msg = ("Could not open file for %s:   \n" % mode +
               "%s          " % filepath)
        if mustOpen:
            raise DazError(msg)
        reportError(msg, warnPaths=True)
    return fp

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

the81Folders = {
    "/data/daz 3d/genesis 8/female" : "/data/daz 3d/genesis 8/female 8_1",
    "/data/daz 3d/genesis 8/female 8_1" : "/data/daz 3d/genesis 8/female",
    "/data/daz 3d/genesis 8/male" : "/data/daz 3d/genesis 8/male 8_1",
    "/data/daz 3d/genesis 8/male 8_1" : "/data/daz 3d/genesis 8/male",
}

def getFolders(reldir, subdirs, match81=True):
    def addFolders(reldir):
        for subdir in subdirs:
            folders = GS.getAbsPaths("%s/%s" % (reldir, subdir))
            for folder in folders:
                root = GS.getBasePath(folder)
                if root == prefroot:
                    preferred.append(folder)
                else:
                    others.append(folder)

    if reldir is None:
        return []
    prefroot = bpy.context.scene.DazPreferredRoot
    preferred = []
    others = []
    reldir = unquote(reldir)
    addFolders(reldir)
    if match81:
        reldir2 = the81Folders.get(reldir.lower())
        if reldir2:
            addFolders(reldir2)
    return preferred+others


def getFoldersFromObject(ob, subdirs, match81=True, usePeople=False):
    reldir = getReldirFromObject(ob, usePeople)
    return getFolders(reldir, subdirs, match81)


def getReldirFromObject(ob, usePeople):
    if ob is None:
        return None
    fileref = dazRna(ob).DazUrl.split("#")[0]
    if len(fileref) < 2:
        return None
    reldir = os.path.dirname(unquote(fileref))
    if usePeople:
        table = [
            ("/data/daz 3d/genesis/base", "/people/genesis"),
            ("/data/daz 3d/genesis 2/female", "/people/genesis 2 female"),
            ("/data/daz 3d/genesis 2/male", "/people/genesis 2 male"),
            ("/data/daz 3d/genesis 3/female", "/people/genesis 3 female"),
            ("/data/daz 3d/genesis 3/male", "/people/genesis 3 male"),
            ("/data/daz 3d/genesis 8/female 8_1", "/people/genesis 8 female"),
            ("/data/daz 3d/genesis 8/male 8_1", "/people/genesis 8 male"),
            ("/data/daz 3d/genesis 8/female", "/people/genesis 8 female"),
            ("/data/daz 3d/genesis 8/male", "/people/genesis 8 male"),
            ("/data/daz 3d/genesis 9/base", "/people/genesis 9"),
        ]
        lreldir = reldir.lower()
        for data,people in table:
            if lreldir.startswith(data):
                return lreldir.replace(data,people)
    return reldir


def findPathRecursive(pattern, relpath, subpath, library="modifier_library", useCheck=True, extensions=[".dsf", ".duf"]):
    def findFilesRecursive(folder):
        for file in os.listdir(folder):
            path = "%s/%s" % (folder, file)
            words = os.path.splitext(file.lower())
            if lpattern.endswith(words[0]) and words[-1] in extensions:
                paths.append(path)
            elif os.path.isdir(path):
                findFilesRecursive(path)

    def checkContent(path):
        from .load_json import JL
        struct = JL.load(path, silent=True)
        for lib in struct.get(library, []):
            if lib.get("name") == pattern:
                return True
        return False

    folders = getFolders(relpath, subpath, match81=True)
    lpattern = pattern.lower()
    paths = []
    for folder in folders:
        folder = folder.rstrip("/")
        findFilesRecursive(folder)
        if len(paths) == 1:
            return paths[0]
        elif len(paths) > 1:
            for path in paths:
                if not useCheck or checkContent(path):
                    return path
            return paths[0]
    return None


def findPathRecursiveFromObject(pattern, ob, subpath):
    reldir = getReldirFromObject(ob, False)
    return findPathRecursive(pattern, reldir, subpath)

#-------------------------------------------------------------
#    File extensions
#-------------------------------------------------------------

class DbzFile:
    filename_ext = ".dbz"
    filter_glob : StringProperty(default="*.dbz;*.json", options={'HIDDEN'})


class JsonFile:
    filename_ext = ".json"
    filter_glob : StringProperty(default="*.json", options={'HIDDEN'})


class JsonExportFile(ExportHelper):
    filename_ext = ".json"
    filter_glob : StringProperty(default="*.json", options={'HIDDEN'})
    filepath : StringProperty(
        name="File Path",
        description="Filepath used for exporting the .json file",
        maxlen=1024,
        default = "")


class ImageFile:
    filename_ext = ".png;.jpeg;.jpg;.bmp;.tif;.tiff"
    filter_glob : StringProperty(default="*.png;*.jpeg;*.jpg;*.bmp;*.tif;*.tiff", options={'HIDDEN'})


class DazImageFile:
    filename_ext = ".duf"
    filter_glob : StringProperty(default="*.duf;*.dsf;*.png;*.jpeg;*.jpg;*.bmp", options={'HIDDEN'})


class DazFile:
    filename_ext = ".dsf;.duf;*.dbz"
    filter_glob : StringProperty(default="*.dsf;*.duf;*.dbz", options={'HIDDEN'})


class DufFile:
    filename_ext = ".dsf;.duf"
    filter_glob : StringProperty(default="*.dsf;*.duf", options={'HIDDEN'})


class FbxFile:
    filename_ext = ".fbx"
    filter_glob : StringProperty(default="*.fbx", options={'HIDDEN'})


class DatFile:
    filename_ext = ".dat"
    filter_glob : StringProperty(default="*.dat", options={'HIDDEN'})


class TextFile:
    filename_ext = ".txt"
    filter_glob : StringProperty(default="*.txt", options={'HIDDEN'})


class CsvFile:
    filename_ext = ".csv"
    filter_glob : StringProperty(default="*.csv", options={'HIDDEN'})

#-------------------------------------------------------------
#   SingleFile and MultiFile
#-------------------------------------------------------------

def ensureExt(filepath, ext):
    return bpy.path.ensure_ext(os.path.splitext(filepath)[0], ext)


def getExistingFilePath(filepath, ext):
    filepath = ensureExt(bpy.path.abspath(filepath), ext)
    filepath = normalizePath(os.path.expanduser(filepath))
    filepath = bpy.path.resolve_ncase(filepath)
    if os.path.exists(filepath):
        return filepath
    else:
        raise DazError('File does not exist:\n"%s"' % filepath)


class SingleFile(ImportHelper):
    extension = ".duf"

    filepath : StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        default="")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MultiFile(ImportHelper):
    files : CollectionProperty(
        name = "File Path",
        type = bpy.types.OperatorFileListElement)

    directory : StringProperty(
        subtype='DIR_PATH')

    def invoke(self, context, event):
        LS.filepaths = []
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def setPreferredFolder(self, rig, meshes, folders, usePeople):
        if GS.rememberLastFolder:
            return
        dirs = []
        if meshes:
            dirs = getFoldersFromObject(meshes[0], folders, usePeople=usePeople)
        if not dirs:
            dirs = getFoldersFromObject(rig, folders, usePeople=usePeople)
        if dirs:
            self.properties.filepath = dirs[0]


    def getMultiFiles(self, extensions):
        def getTypedFilePath(filepath, exts):
            filepath = bpy.path.resolve_ncase(filepath)
            words = os.path.splitext(filepath)
            if len(words) == 2:
                fname,ext = words
            else:
                return None
            if fname[-4:] == ".tip":
                fname = fname[:-4]
            if ext in [".png", ".jpeg", ".jpg", ".bmp"]:
                if os.path.exists(fname):
                    words = os.path.splitext(fname)
                    if (len(words) == 2 and
                        words[1][1:] in exts):
                        return fname
                for ext1 in exts:
                    path = fname+"."+ext1
                    if os.path.exists(path):
                        return path
                return None
            elif ext[1:].lower() in exts:
                return filepath
            else:
                return None


        filepaths = []
        if LS.filepaths:
            for path in LS.filepaths:
                filepath = getTypedFilePath(path, extensions)
                if filepath:
                    filepaths.append(filepath)
        else:
            for file_elem in self.files:
                path = os.path.join(self.directory, file_elem.name)
                if os.path.isfile(path):
                    filepath = getTypedFilePath(path, extensions)
                    if filepath:
                        filepaths.append(filepath)
        return filepaths

#-------------------------------------------------------------
#   Copy presets
#-------------------------------------------------------------

def copyPresets(srcop, trgop):
    import shutil
    x,y,z = bpy.app.version
    bfolder = "%d.%d" % (x,y)
    folder = topdir = os.path.dirname(__file__)
    while topdir and not topdir.endswith(bfolder):
        dirs = os.path.split(topdir)
        if dirs[0] != topdir:
            topdir = dirs[0]
        else:
            return
    trgdir = os.path.join(topdir, "scripts", "presets", "operator", "daz.%s" % trgop)
    srcdir = os.path.join(folder, "data", "presets", srcop)
    try:
        if not os.path.exists(trgdir):
            os.makedirs(trgdir)
        for file in os.listdir(srcdir):
            if os.path.splitext(file)[-1] == ".py":
                src = os.path.join(srcdir, file)
                trg = os.path.join(trgdir, file)
                shutil.copy(src, trg)
    except:
        print("Could not copy preset files")

#----------------------------------------------------------
#   Get .dhdm and jcm files
#----------------------------------------------------------

def getHDDirs(ob, attr):
    if ob is None:
        ob = bpy.context.object
    if ob and ob.type == 'MESH':
        folders = {}
        for item in getattr(ob.data, attr):
            folder = os.path.dirname(item.s)
            folders[folder] = True
        return list(folders.keys())
    return []

