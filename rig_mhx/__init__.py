#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "MHX" in locals():
    print("Reloading MHX")
    import imp
    imp.reload(mhx_data)
    imp.reload(mhx)
else:
    print("Loading MHX")
    from . import mhx_data
    from . import mhx

MHX = True

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
    print("Register MHX")
    bpy.utils.register_class(DAZ_PT_DazMhxBuild)
    from . import mhx
    mhx.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_DazMhxBuild)
    from . import mhx
    mhx.unregister()
