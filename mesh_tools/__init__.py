# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if DEBUG and "MeshTools" in locals():
    print("Reloading Mesh Tools")
    import bpy
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    imp.reload(vertex_groups)
    imp.reload(modifiers)
    imp.reload(uvmaps)
    imp.reload(attr)
    imp.reload(lowpoly)
    imp.reload(tube)
    imp.reload(mesh_panel)
else:
    print("Loading Mesh Tools")
    from . import vertex_groups
    from . import modifiers
    from . import uvmaps
    from . import attr
    from . import lowpoly
    from . import tube
    from . import mesh_panel

MeshTools = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    try:
        print("Register Mesh Tools")
        from . import vertex_groups, modifiers, uvmaps, attr, lowpoly, mesh_panel, tube
        vertex_groups.register()
        modifiers.register()
        uvmaps.register()
        attr.register()
        lowpoly.register()
        mesh_panel.register()
        tube.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import vertex_groups, modifiers, uvmaps, attr, lowpoly, mesh_panel, tube
        mesh_panel.unregister()
        lowpoly.unregister()
        uvmaps.unregister()
        attr.unregister()
        modifiers.unregister()
        vertex_groups.unregister()
        tube.unregister()
    except (RuntimeError, ValueError):
        pass
