# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..fileutils import SingleFile
from .facsbase import HeadUser, FACSImporter

#------------------------------------------------------------------
#   VMD
#------------------------------------------------------------------

class DAZ_OT_ImportVmdFacs(FACSImporter, SingleFile, DazOperator):
    bl_idname = "daz.import_vmd_facs"
    bl_label = "Import FACS From VMD File"
    bl_description = "Import a vmd file with FACS animation.\nMMD Tools must be installed"
    bl_options = {'UNDO'}

    filename_ext = ".vmd"
    filter_glob : StringProperty(default="*.vmd", options={'HIDDEN'})
    useHeadLoc = False
    useHeadRot = False

    def parse(self, context):
        try:
            from bl_ext.blender_org.mmd_tools.core import vmd
            found = True
        except ModuleNotFoundError:
            found = False
        if not found:
            raise DazError("MMD Tools not found")
        vmdTable = BD.facsTables["VMD"]["facs"]
        vmdFile = vmd.File()
        vmdFile.load(filepath = self.filepath)
        first = True
        for key,frames in vmdFile.shapeKeyAnimation.items():
            bshape = vmdTable.get(key, key.lower())
            self.bshapes.append(bshape)
            if first:
                for frame in frames:
                    self.bskeys[frame.frame_number] = []
                first = False
            for frame in frames:
                t = frame.frame_number
                self.bskeys[t].append(frame.weight)
                '''
                self.hlockeys[t] = Vector((0,0,0))
                self.hrotkeys[t] = Euler((0,0,0))
                self.leyekeys[t] = Euler((0,0,0))
                self.reyekeys[t] = Euler((0,0,0))
                '''

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportVmdFacs)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportVmdFacs)
