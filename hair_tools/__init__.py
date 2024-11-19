#  DAZ Hair - Tools for rigging figures imported with the DAZ Importer
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
elif "HairToolsFeature" in locals():
    print("Reloading Hair Tools")
    import imp
    imp.reload(make_hair)
else:
    print("Loading Hair Tools")
    from . import make_hair
    HairToolsFeature = True

#----------------------------------------------------------
#   Hair panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

#----------------------------------------------------------
#   Hair
#----------------------------------------------------------

class DAZ_PT_SetupHair(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupHair"
    bl_label = "Hair"

    def draw(self, context):
        from .make_hair import getHairAndHuman
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.select_strands_by_size")
        self.layout.operator("daz.select_strands_by_width")
        self.layout.operator("daz.select_random_strands")
        self.layout.separator()
        self.layout.operator("daz.make_hair")
        hair,hum = getHairAndHuman(context, False)
        self.layout.label(text = "  Hair:  %s" % (hair.name if hair else None))
        self.layout.label(text = "  Human: %s" % (hum.name if hum else None))
        self.layout.separator()
        self.layout.operator("daz.make_hair_proxy")
        self.layout.operator("daz.mesh_add_pinning")
        self.layout.separator()
        self.layout.operator("daz.add_hair_rig")
        self.layout.operator("daz.set_envelopes")
        self.layout.operator("daz.toggle_hair_locks")
        self.layout.separator()
        self.layout.operator("daz.update_hair")
        self.layout.operator("daz.color_hair")
        self.layout.operator("daz.combine_hairs")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Hair Tools")
    bpy.utils.register_class(DAZ_PT_SetupHair)
    from . import make_hair
    make_hair.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_SetupHair)
    from . import make_hair
    make_hair.unregister()


