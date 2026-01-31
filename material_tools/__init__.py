# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "MaterialToolsFeature" in locals():
    print("Reloading Material Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    imp.reload(editor)
    imp.reload(udim)
    imp.reload(decal)
    imp.reload(combo)
    imp.reload(palette)
    imp.reload(missing)
    imp.reload(material_panel)
else:
    print("Loading Material Tools")
    from . import editor
    from . import udim
    from . import decal
    from . import combo
    from . import palette
    from . import missing
    from . import material_panel
    MaterialToolsFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register Material Tools")
        from . import editor, udim, decal, combo, palette, missing, material_panel
        editor.register()
        decal.register()
        udim.register()
        combo.register()
        palette.register()
        missing.register()
        material_panel.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import editor, udim, decal, combo, palette, missing, material_panel
        editor.unregister()
        udim.unregister()
        decal.unregister()
        combo.unregister()
        palette.unregister()
        missing.unregister()
        material_panel.unregister()
    except (RuntimeError, ValueError):
        pass


