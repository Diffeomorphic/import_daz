# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "MorphFeature" in locals():
    print("Reloading Morph Tools")
    import imp
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
    print("Register Morph Tools")
    from . import category, shapekeys, morph_panel
    category.register()
    shapekeys.register()
    morph_panel.register()

def unregister():
    from . import category, shapekeys, morph_panel
    morph_panel.unregister()
    shapekeys.unregister()
    category.unregister()
