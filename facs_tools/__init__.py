# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "FacsFeature" in locals():
    print("Reloading FACS Tools")
    import imp
    imp.reload(facsbase)
    imp.reload(facecap)
    imp.reload(livelink)
    imp.reload(fbxfacs)
    imp.reload(vmdfacs)
    imp.reload(moho)
else:
    print("Loading FACS Tools")
    from . import facsbase
    from . import facecap
    from . import livelink
    from . import fbxfacs
    from . import vmdfacs
    from . import moho
    FacsFeature = True

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_RuntimeTab

class DAZ_PT_FACS(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Facial Animation"

    def draw(self, context):
        self.layout.operator("daz.import_facecap")
        self.layout.operator("daz.import_livelink")
        self.layout.operator("daz.import_fbx_facs")
        self.layout.operator("daz.import_vmd_facs")
        self.layout.separator()
        self.layout.operator("daz.import_moho")
        self.layout.separator()
        self.layout.operator("daz.copy_facs_animation")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register FACS Tools")
        bpy.utils.register_class(DAZ_PT_FACS)
        from . import facsbase, facecap, livelink, fbxfacs, vmdfacs, moho
        facsbase.register()
        facecap.register()
        livelink.register()
        fbxfacs.register()
        vmdfacs.register()
        moho.register()
    except (RuntimeError, ValueError):
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DAZ_PT_FACS)
        from . import facsbase, facecap, livelink, fbxfacs, vmdfacs, moho
        facsbase.unregister()
        facecap.unregister()
        livelink.unregister()
        fbxfacs.unregister()
        vmdfacs.unregister()
        moho.unregister()
    except (RuntimeError, ValueError):
        pass
