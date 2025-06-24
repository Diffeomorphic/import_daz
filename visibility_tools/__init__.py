# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
    imp.reload(hide_mod)
else:
    print("Loading Visibility Tools")
    from . import hide
    from . import hide_mod
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
        self.layout.operator("daz.select_covered_verts")
        self.layout.operator("daz.copy_masks")
        self.layout.operator("daz.add_visibility_drivers")
        self.layout.operator("daz.remove_visibility_drivers")
        self.layout.operator("daz.add_shape_vis_drivers")
        self.layout.operator("daz.drive_modifier_influence")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register Visibility Tools")
        bpy.utils.register_class(DAZ_PT_SetupVisibility)
        from . import hide
        hide.register()
        hide_mod.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DAZ_PT_SetupVisibility)
        from . import hide
        hide.unregister()
        hide_mod.unregister()
    except (RuntimeError, ValueError):
        pass


