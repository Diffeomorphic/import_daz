#  DAZ Importer - Tools for rigging figures imported with the DAZ Importer
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "MeshTools" in locals():
    print("Reloading Mesh Tools")
    import imp
    imp.reload(vertex_groups)
    imp.reload(modifiers)
    imp.reload(uvmaps)
    imp.reload(lowpoly)
    imp.reload(mesh_panel)
else:
    print("Loading Mesh Tools")
    from . import vertex_groups
    from . import modifiers
    from . import uvmaps
    from . import lowpoly
    from . import mesh_panel

MeshTools = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Mesh Tools")
    from . import vertex_groups, modifiers, uvmaps, lowpoly, mesh_panel
    vertex_groups.register()
    modifiers.register()
    uvmaps.register()
    lowpoly.register()
    mesh_panel.register()

def unregister():
    from . import vertex_groups, modifiers, uvmaps, lowpoly, mesh_panel
    mesh_panel.unregister()
    lowpoly.unregister()
    uvmaps.unregister()
    modifiers.unregister()
    vertex_groups.unregister()
