# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "ObjectToolsFeature" in locals():
    print("Reloading Object Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib
        imp = importlib
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
    try:
        print("Register Object Tools")
        bpy.utils.register_class(DAZ_PT_Objects)
        from . import mannequin, categorize, scale
        mannequin.register()
        categorize.register()
        scale.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DAZ_PT_Objects)
        from . import mannequin, categorize, scale
        mannequin.unregister()
        categorize.unregister()
        scale.unregister()
    except (RuntimeError, ValueError):
        pass


