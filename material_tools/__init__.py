#  DAZ Materials - Tools for editing materials imported with the DAZ Importer
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
    print("Register Material Tools")
    from . import editor, udim, decal, combo, palette, missing, material_panel
    editor.register()
    decal.register()
    udim.register()
    combo.register()
    palette.register()
    missing.register()
    material_panel.register()

def unregister():
    from . import editor, udim, decal, combo, palette, missing, material_panel
    editor.unregister()
    udim.unregister()
    decal.unregister()
    combo.unregister()
    palette.unregister()
    missing.unregister()
    material_panel.unregister()


