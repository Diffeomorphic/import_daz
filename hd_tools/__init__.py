# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "HDFeature" in locals():
    print("Reloading HD Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    imp.reload(hd_morphs)
else:
    print("Loading HD Tools")
    from . import hd_morphs
    HDFeature = True

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_HDMesh(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_HDMesh"
    bl_label = "HD Mesh"

    def draw(self, context):
        self.layout.operator("daz.copy_grafts_groups")
        if bpy.app.version >= (2,90,0):
            self.layout.operator("daz.make_multires")
            self.layout.separator()
        self.layout.operator("daz.bake_maps")
        self.layout.operator("daz.load_baked_maps")
        self.layout.separator()
        self.layout.operator("daz.load_normal_map")
        self.layout.operator("daz.load_scalar_disp")
        self.layout.operator("daz.load_vector_disp")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register HD Tools")
        bpy.utils.register_class(DAZ_PT_HDMesh)
        from . import hd_morphs
        hd_morphs.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DAZ_PT_HDMesh)
        from . import hd_morphs
        hd_morphs.unregister()
    except (RuntimeError, ValueError):
        pass
