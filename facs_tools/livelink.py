# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import DazPropOperator
from .facsbase import HeadUser, FACSImporter

#------------------------------------------------------------------
#   Unreal Live Link
#------------------------------------------------------------------

class DAZ_OT_ImportLiveLink(HeadUser, FACSImporter, DazPropOperator):
    bl_idname = "daz.import_livelink"
    bl_label = "Import Live Link File"
    bl_description = "Import a csv file with Unreal's Live Link data"
    bl_options = {'UNDO'}

    filename_ext = ".csv"
    filter_glob : StringProperty(default="*.csv", options={'HIDDEN'})

    def draw(self, context):
        FACSImporter.draw(self, context)
        HeadUser.draw(self, context)

    def getFrame(self, t):
        return t+1

    def parse(self, context):
        from csv import reader
        with open(self.filepath, newline='', encoding="utf-8-sig") as fp:
            lines = list(reader(fp))
        if len(lines) < 2:
            raise MocapError("Found no keyframes")

        self.bshapes = [bshape.lower() for bshape in lines[0][2:-9]]
        for t,line in enumerate(lines[1:]):
            nums = [float(word) for word in line[2:]]
            self.bskeys[t] = nums[0:-9]
            self.hlockeys[t] = Vector((0,0,0))
            yaw,pitch,roll = nums[-9:-6]
            self.hrotkeys[t] = Euler((-pitch, -yaw, roll))
            yaw,pitch,roll = nums[-6:-3]
            self.leyekeys[t] = Euler((-pitch, roll, yaw))
            yaw,pitch,roll = nums[-3:]
            self.reyekeys[t] = Euler((-pitch, roll, yaw))

        for key in self.bshapes:
            if key not in self.facstable.keys():
                print(key)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportLiveLink)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportLiveLink)
