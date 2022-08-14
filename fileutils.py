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

import bpy
import os
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .error import *
from .utils import *

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
        reportError(msg, warnPaths=True, trigger=(2,4))
    return fp

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

the81Folders = {
    "/data/DAZ 3D/Genesis 8/Female" : "/data/DAZ 3D/Genesis 8/Female 8_1",
    "/data/DAZ 3D/Genesis 8_1/Female" : "/data/DAZ 3D/Genesis 8/Female 8",
    "/data/DAZ 3D/Genesis 8/Male" : "/data/DAZ 3D/Genesis 8/Male 8_1",
    "/data/DAZ 3D/Genesis 8_1/Male" : "/data/DAZ 3D/Genesis 8/Male 8",
}

def getFolders(ob, subdirs, match81=False):
    def addFolders(reldir):
        for basedir in GS.getDazPaths():
            for subdir in subdirs:
                folder = "%s/%s/%s" % (basedir, reldir, subdir)
                folder = folder.replace("//", "/")
                folder = bpy.path.resolve_ncase(folder)
                if os.path.exists(folder):
                    folders.append(folder)

    if ob is None:
        return []
    fileref = ob.DazUrl.split("#")[0]
    if len(fileref) < 2:
        return []
    reldir = os.path.dirname(fileref)
    folders = []
    addFolders(reldir)
    if match81:
        reldir2 = the81Folders.get(reldir)
        if reldir2:
            addFolders(reldir2)
    return folders

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

def getExistingFilePath(filepath, ext):
    filepath = bpy.path.ensure_ext(bpy.path.abspath(filepath), ext)
    filepath = os.path.expanduser(filepath).replace("\\", "/")
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
        G.theFilePaths = []
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


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
        if G.theFilePaths:
            for path in G.theFilePaths:
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
        default = os.getlogin())

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
        filepath = "%s.duf" % file
        filepath = filepath.replace("\\", "/")
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

