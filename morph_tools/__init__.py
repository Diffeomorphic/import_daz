# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "MorphFeature" in locals():
    print("Reloading Morph Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    imp.reload(category)
    imp.reload(shapekeys)
    imp.reload(morph_panel)
else:
    print("Loading Morph Tools")
    from . import category
    from . import shapekeys
    from . import morph_panel
    MorphFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register Morph Tools")
        from . import category, shapekeys, morph_panel
        category.register()
        shapekeys.register()
        morph_panel.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import category, shapekeys, morph_panel
        morph_panel.unregister()
        shapekeys.unregister()
        category.unregister()
    except (RuntimeError, ValueError):
        pass
