#  DAZ Visibility - Tools for rigging figures imported with the DAZ Importer
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
elif "VisibilityToolsFeature" in locals():
    print("Reloading Visibility Tools")
    import imp
    imp.reload(hide)
else:
    print("Loading Visibility Tools")
    from . import hide
    VisibilityToolsFeature = True

#----------------------------------------------------------
#   Visibility panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

#----------------------------------------------------------
#   Visibility
#----------------------------------------------------------

class DAZ_PT_SetupVisibility(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupVisibility"
    bl_label = "Visibility"

    def draw(self, context):
        self.layout.operator("daz.add_shrinkwrap")
        self.layout.operator("daz.make_invisible")
        self.layout.operator("daz.create_masks")
        self.layout.operator("daz.copy_masks")
        self.layout.operator("daz.add_visibility_drivers")
        self.layout.operator("daz.remove_visibility_drivers")
        self.layout.operator("daz.add_shape_vis_drivers")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Visibility Tools")
    bpy.utils.register_class(DAZ_PT_SetupVisibility)
    from . import hide
    hide.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_SetupVisibility)
    from . import hide
    hide.unregister()


