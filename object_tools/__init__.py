#  DAZ Objects - Tools for rigging figures imported with the DAZ Importer
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
elif "ObjectToolsFeature" in locals():
    print("Reloading Object Tools")
    import imp
    imp.reload(mannequin)
    imp.reload(categorize)
    imp.reload(scale)
else:
    print("Loading Object Tools")
    from . import mannequin
    from . import categorize
    from . import scale
    ObjectToolsFeature = True

#----------------------------------------------------------
#   Objects panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Objects(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_id = "DAZ_PT_Objects"
    bl_label = "Objects"

    def draw(self, context):
        self.layout.operator("daz.add_mannequin")
        self.layout.operator("daz.categorize_objects")
        self.layout.operator("daz.scale_objects")
        self.layout.operator("daz.scale_materials")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Object Tools")
    bpy.utils.register_class(DAZ_PT_Objects)
    from . import mannequin, categorize, scale
    mannequin.register()
    categorize.register()
    scale.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_Objects)
    from . import mannequin, categorize, scale
    mannequin.unregister()
    categorize.unregister()
    scale.unregister()


