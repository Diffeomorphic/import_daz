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
elif "RigifyFeature" in locals():
    print("Reloading Rigify")
    import imp
    imp.reload(rigify_data)
    imp.reload(rigify)
    imp.reload(panel)
else:
    print("Loading Rigify")
    from . import rigify_data
    from . import rigify
    from . import panel
    RigifyFeature = True

#----------------------------------------------------------
#   Access
#----------------------------------------------------------

def setFkIk1(rig, ik, layers, useInsertKeys, frame):
    from . import rigify
    return rigify.setFkIk1(rig, ik, layers, useInsertKeys, frame)

def setFkIk2(rig, ik, layers, useInsertKeys, frame):
    from . import rigify
    return rigify.setFkIk2(rig, ik, layers, useInsertKeys, frame)

from .layers import R_DETAIL, R_CUSTOM

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Rigify")
    from . import rigify, panel
    rigify.register()
    panel.register()

def unregister():
    from . import rigify, panel
    rigify.unregister()
    panel.unregister()
