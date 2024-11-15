#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
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
elif "SimpleIkFeature" in locals():
    print("Reloading Simple IK")
    import imp
    imp.reload(simple)
    imp.reload(panel)
else:
    print("Loading Simple IK")
    from . import simple
    from . import panel
    SimpleIkFeature = True

#----------------------------------------------------------
#   Access
#----------------------------------------------------------

def setSimpleToFk(rig, layers, useInsertKeys, frame):
    from . import simple
    return simple.setSimpleToFk(rig, layers, useInsertKeys, frame)

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Simple IK")
    from . import simple, panel
    simple.register()
    panel.register()

def unregister():
    from . import simple, panel
    simple.unregister()
    panel.unregister()
