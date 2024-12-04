# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import bpy
from mathutils import *
from math import pi
from collections import OrderedDict

from ..error import *
from ..utils import *
from ..fileutils import SingleFile, DufFile
from ..asset import normalizeRef, normalizeUrl
from ..load_json import saveJson

#----------------------------------------------------------
#   Preset base class
#----------------------------------------------------------

class Preset:
    useDazDirectory : BoolProperty(
        name = "DAZ Directory",
        description = "Save the file where it can be found by DAZ Studio",
        default = False)

    reldir: StringProperty(
        name = "Directory",
        description = "Directory relative to root path")

    author : StringProperty(
        name = "Author",
        description = "Author info in preset file",
        default = "Myself")

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
        self.layout.prop(self, "useDazDirectory")
        if self.useDazDirectory:
            self.drawFiles(context)
        self.drawAuthor()

    def drawAuthor(self):
        self.layout.prop(self, "author")
        self.layout.prop(self, "email")
        self.layout.prop(self, "website")
        self.drawPresentation()
        self.layout.prop(self, "useCompress")

    def drawPresentation(self):
        pass

    def drawFiles(self, context):
        self.layout.prop(context.scene, "DazPreferredRoot")
        self.layout.prop(self, "reldir")

    def getDefaultDirectory(self, ob):
        folder = os.path.dirname(ob.DazUrl.split("#",1)[0])
        return "%s/%s/%s" % (folder, self.subdir, self.author)

    def getFullDirectory(self, scn):
        return canonicalPath("%s/%s" % (scn.DazPreferredRoot, self.reldir))

    def getFilepath(self, context):
        if self.useDazDirectory:
            folder = self.getFullDirectory(context.scene)
            filename = os.path.basename(self.filepath)
            if len(os.path.splitext(filename)) == 1:
                filename = "%s.%s" % (filename, self.extension)
            return "%s/%s" % (folder, filename)
        else:
            return self.filepath

    def setFilepath(self, filename, folder=None):
        if not GS.rememberLastFolder:
            words = os.path.splitext(filename)
            filename = "%s%s" % (bpy.path.clean_name(words[0]), self.extension)
            if folder and os.path.exists(folder):
                self.filepath = "%s/%s" % (folder, filename)
            else:
                self.filepath = filename

    def setDefaultFilepath(self, ob, scn, fname):
        self.fromGS()
        self.reldir = self.getDefaultDirectory(ob)
        folder = self.getFullDirectory(scn)
        self.setFilepath(fname, folder)

    def fromGS(self):
        self.author = GS.author
        self.email = GS.email
        self.website = GS.website

    def toGS(self):
        GS.author = self.author
        GS.email = self.email
        GS.website = self.website

    def makeDazStruct(self, type, filepath):
        from datetime import datetime
        file,ext = os.path.splitext(filepath)
        filepath = normalizePath("%s%s" % (file, self.extension))
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

#-------------------------------------------------------------
#   Save UVs
#-------------------------------------------------------------

class DAZ_OT_SaveUV(DazOperator, Preset, DufFile, SingleFile):
    bl_idname = "daz.save_uv"
    bl_label = "Save UV Set"
    bl_description = "Save the active UV set as a duf file"

    subdir = "UV Sets"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.uv_layers.active)

    def invoke(self, context, event):
        ob = context.object
        self.setDefaultFilepath(ob, context.scene, ob.data.uv_layers.active.name)
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        ob = context.object
        self.toGS()
        uvlayer = ob.data.uv_layers.active
        filepath = self.getFilepath(context)
        struct, filepath = self.makeDazStruct("uv_set", filepath)
        uvstruct = OrderedDict()
        uvstruct["id"] = uvlayer.name
        uvstruct["name"] = uvlayer.name
        uvstruct["label"] = uvlayer.name
        uvstruct["vertex_count"] = len(ob.data.vertices)
        uvs = OrderedDict()
        uvs["count"] = len(uvlayer.data)
        uvs["values"] = [list(uv.uv) for uv in uvlayer.data]
        uvstruct["uvs"] = uvs
        polys = []
        m = 0
        for f in ob.data.polygons:
            for vn in f.vertices:
                polys.append([f.index, vn, m])
                m += 1
        uvstruct["polygon_vertex_indices"] = polys
        struct["uv_set_library"] = [uvstruct]
        scene = {"uvs": [
            { "id" : "%s-1" % uvlayer.name,
              "url" : "#%s" % normalizeRef(uvlayer.name) }
            ]
        }
        struct["scene"] = scene
        saveJson(struct, filepath, binary=self.useCompress, strict=False)
        print("UV set %s saved" % filepath)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SaveUV,

]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
