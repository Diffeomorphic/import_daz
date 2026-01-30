# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "ExportFeature" in locals():
    print("Reloading Export Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    imp.reload(preset)
    imp.reload(pose_preset)
    imp.reload(morph_preset)
else:
    print("Loading Export Tools")
    from . import preset
    from . import pose_preset
    from . import morph_preset
    ExportFeature = True

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_RuntimeTab

class DAZ_PT_Export(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Export"

    def draw(self, context):
        self.layout.operator("daz.make_control_rig")
        self.layout.operator("daz.save_pose_preset")
        self.layout.operator("daz.save_morph_presets")
        self.layout.operator("daz.save_daz_figure")
        self.layout.operator("daz.save_uv")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Export,
]

def register():
    try:
        print("Register Export Tools")
        for cls in classes:
            bpy.utils.register_class(cls)
        from . import preset, pose_preset, morph_preset
        preset.register()
        pose_preset.register()
        morph_preset.register()
    except (RuntimeError, ValueError):
        pass


def unregister():
    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        from . import preset, pose_preset, morph_preset
        morph_preset.unregister()
        pose_preset.unregister()
        preset.unregister()
    except (RuntimeError, ValueError):
        pass
