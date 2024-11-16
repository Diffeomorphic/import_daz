#  DAZ Materials - Tools for rigging figures imported with the DAZ Importer
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
elif "MaterialToolsFeature" in locals():
    print("Reloading Material Tools")
    import imp
    imp.reload(material_panel)
else:
    print("Loading Material Tools")
    from . import material_panel
    MaterialToolsFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Material Tools")
    bpy.utils.register_class(DAZ_PT_Materials)
    from . import material_panel
    material_panel.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_Materials)
    from . import material_panel
    material_panel.unregister()


