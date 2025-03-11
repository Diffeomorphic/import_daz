# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG, EXPERIMENTAL

if not DEBUG:
    pass
elif "MeshTools" in locals():
    print("Reloading Mesh Tools")
    import imp
    imp.reload(vertex_groups)
    imp.reload(modifiers)
    imp.reload(uvmaps)
    imp.reload(attr)
    imp.reload(lowpoly)
    if EXPERIMENTAL:
        imp.reload(rope)
    imp.reload(mesh_panel)
else:
    print("Loading Mesh Tools")
    from . import vertex_groups
    from . import modifiers
    from . import uvmaps
    from . import attr
    from . import lowpoly
    if EXPERIMENTAL:
        from . import rope
    from . import mesh_panel

MeshTools = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Mesh Tools")
    from . import vertex_groups, modifiers, uvmaps, attr, lowpoly, mesh_panel
    vertex_groups.register()
    modifiers.register()
    uvmaps.register()
    attr.register()
    lowpoly.register()
    mesh_panel.register()
    if EXPERIMENTAL:
        from . import rope
        rope.register()

def unregister():
    from . import vertex_groups, modifiers, uvmaps, attr, lowpoly, mesh_panel
    mesh_panel.unregister()
    lowpoly.unregister()
    uvmaps.unregister()
    attr.unregister()
    modifiers.unregister()
    vertex_groups.unregister()
    if EXPERIMENTAL:
        from . import rope
        rope.unregister()
