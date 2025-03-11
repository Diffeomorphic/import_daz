# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *

#-------------------------------------------------------------
#   Find Tube
#-------------------------------------------------------------

class DAZ_OT_FindTube(DazOperator, IsMesh):
    bl_idname = "daz.find_tube"
    bl_label = "Find Tube"
    bl_description = "Find curve at center of tube"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        print("OB", ob)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_FindTube,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)