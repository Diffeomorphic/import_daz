# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..fileutils import SingleFile
from .facsbase import HeadUser, FACSImporter

#------------------------------------------------------------------
#   FaceCap
#------------------------------------------------------------------

class DAZ_OT_ImportFaceCap(HeadUser, FACSImporter, SingleFile, DazOperator):
    bl_idname = "daz.import_facecap"
    bl_label = "Import FaceCap File"
    bl_description = "Import a text file with facecap data"
    bl_options = {'UNDO'}

    filename_ext = ".txt"
    filter_glob : StringProperty(default="*.txt", options={'HIDDEN'})

    def draw(self, context):
        FACSImporter.draw(self, context)
        HeadUser.draw(self, context)

    def getFrame(self, t):
        return self.fps * 1e-3 * t

    # timestamp in milli seconds (file says nano),
    # head position xyz,
    # head eulerAngles xyz,
    # left-eye eulerAngles xy,
    # right-eye eulerAngles xy,
    # blendshapes
    def parse(self, context):
        with open(self.filepath, "r", encoding="utf-8-sig") as fp:
            for line in fp:
                line = line.strip()
                if line[0:3] == "bs,":
                    self.bshapes = [bshape.lower() for bshape in line.split(",")[1:]]
                elif line[0:2] == "k,":
                    words = line.split(",")
                    t = int(words[1])
                    self.hlockeys[t] = Vector((float(words[2]), -float(words[3]), -float(words[4])))
                    self.hrotkeys[t] = Euler((D*float(words[5]), D*float(words[6]), D*float(words[7])))
                    self.leyekeys[t] = Euler((D*float(words[9]), 0.0, D*float(words[8])))
                    self.reyekeys[t] = Euler((D*float(words[11]), 0.0, D*float(words[10])))
                    self.bskeys[t] = [float(word) for word in words[12:]]
                elif line[0:5] == "info,":
                    pass
                else:
                    raise DazError("Illegal syntax:\%s     " % line)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportFaceCap)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportFaceCap)