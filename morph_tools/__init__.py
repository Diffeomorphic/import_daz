# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "MorphFeature" in locals():
    print("Reloading Morph Tools")
    import imp
    imp.reload(category)
    imp.reload(shapekeys)
    imp.reload(morph_action)
    imp.reload(morph_panel)
else:
    print("Loading Morph Tools")
    from . import category
    from . import shapekeys
    from . import morph_action
    from . import morph_panel
    MorphFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register Morph Tools")
        from . import category, shapekeys, morph_action, morph_panel
        category.register()
        shapekeys.register()
        morph_action.register()
        morph_panel.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import category, shapekeys, morph_action, morph_panel
        morph_panel.unregister()
        morph_action.unregister()
        shapekeys.unregister()
        category.unregister()
    except (RuntimeError, ValueError):
        pass
