# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "MHXFeature" in locals():
    print("Reloading MHX Tools")
    import imp
    imp.reload(mhx_data)
    imp.reload(mhx)
else:
    print("Loading MHX Tools")
    from . import mhx_data
    from . import mhx
    MHXFeature = True

#----------------------------------------------------------
#   Access
#----------------------------------------------------------

def setMhxToFk(rig, layers, useInsertKeys, frame):
    from . import mhx
    return mhx.setMhxToFk(rig, layers, useInsertKeys, frame)

from .layers import L_FACE, L_CUSTOM

#----------------------------------------------------------
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab
class DAZ_PT_DazMhxBuild(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_label = "MHX"

    def draw(self, context):
        self.layout.operator("daz.convert_to_mhx")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_DazMhxBuild,
]

def register():
    print("Register MHX Tools")
    bpy.utils.register_class(DAZ_PT_DazMhxBuild)
    from . import mhx
    mhx.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_DazMhxBuild)
    from . import mhx
    mhx.unregister()
