# Copyright (c) 2016-2023, Thomas Larsson
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

class AnimationFolders:
    def __init__(self):
        self.converters = {}
        self.restposes = {}
        self.parents = {}
        self.ikposes = {}
        self.presets = {}
        self.lowpoly = {}
        self.altmorphs = {}
        self.scanned = {}
        self.tiles = {}

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

        self.FaceControls = [
            "/data/daz 3d/genesis 8/genesis 8_1 face controls/genesis 8.1 face controls.dsf#genesis 8.1 face controls",
            "/data/daz 3d/genesis 8/genesis 8_1 male face controls/genesis 8.1 male face controls.dsf#genesis 8.1 male face controls",
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
        print("Load", filepath)
        if not os.path.exists(filepath):
            if strict:
                raise DazError("File %s    \n does not exist" % filepath)
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


AF = AnimationFolders()

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
        for basedir in GS.getDazPaths():
            for subdir in subdirs:
                folder = "%s/%s/%s" % (basedir, reldir, subdir)
                folder = folder.replace("//", "/")
                folder = bpy.path.resolve_ncase(folder)
                if os.path.exists(folder):
                    if basedir == prefroot:
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
    fileref = ob.DazUrl.split("#")[0]
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
                pdir = lreldir.replace(data,people)
                return bpy.path.resolve_ncase(pdir)
    return reldir


def findPathRecursive(pattern, relpath, subpath, library="modifier_library"):
    def findFilesRecursive(folder):
        for file in os.listdir(folder):
            path = "%s/%s" % (folder, file)
            words = os.path.splitext(file.lower())
            if lpattern.endswith(words[0]) and words[-1] in [".dsf", ".duf"]:
                paths.append(path)
            elif os.path.isdir(path):
                findFilesRecursive(path)

    def checkContent(path):
        from .load_json import loadJson
        struct = loadJson(path, silent=True)
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
                if checkContent(path):
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
    filename_ext = ".duf"
    filter_glob : StringProperty(default="*.duf", options={'HIDDEN'})


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
        LS.theFilePaths = []
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def setPreferredFolder(self, rig, meshes, folders, usePeople):
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
        if LS.theFilePaths:
            for path in LS.theFilePaths:
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
#   Open settings file
#-------------------------------------------------------------

def openSettingsFile(filepath):
    filepath = os.path.expanduser(filepath)
    filepath = bpy.path.resolve_ncase(filepath)
    try:
        fp = open(filepath, "r", encoding="utf-8-sig")
    except:
        fp = None
    if fp:
        import json
        try:
            return json.load(fp)
        except json.decoder.JSONDecodeError as err:
            print("File %s is corrupt" % filepath)
            print("Error: %s" % err)
            return None
        finally:
            fp.close()
    else:
        print("Could not open %s" % filepath)
        return None

#-------------------------------------------------------------
#   Daz Exporter
#-------------------------------------------------------------

class DazExporter:
    author : StringProperty(
        name = "Author",
        description = "Author info in preset file",
        default = "")

    email : StringProperty(
        name = "Email",
        description = "Email info in preset file",
        default = "")

    website : StringProperty(
        name = "Website",
        description = "Website info in preset file",
        default = "")

    useCompress: BoolProperty(
        name = "Compress File",
        description = "Gzip the output file",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "author")
        self.layout.prop(self, "email")
        self.layout.prop(self, "website")
        self.layout.prop(self, "useCompress")

    def makeDazStruct(self, type, filepath):
        from collections import OrderedDict
        from .asset import normalizeUrl
        from datetime import datetime
        file,ext = os.path.splitext(filepath)
        filepath = normalizePath("%s.duf" % file)
        struct = OrderedDict()
        struct["file_version"] = "0.6.0.0"
        astruct = {}
        astruct["id"] = normalizeUrl(filepath)
        astruct["type"] = type
        astruct["contributor"] = {
            "author" : self.author,
            "email" : self.email,
            "website" : self.website,
        }
        astruct["modified"] = str(datetime.now())
        struct["asset_info"] = astruct
        return struct, filepath

