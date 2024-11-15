#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
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
elif "MorphFeature" in locals():
    print("Reloading Morph Tools")
    import imp
    imp.reload(category)
    imp.reload(shapekeys)
    imp.reload(morph_panel)
else:
    print("\nLoading Morph Tools")
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
