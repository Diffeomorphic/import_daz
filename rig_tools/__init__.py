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
elif "RigToolsFeature" in locals():
    print("Reloading Rig Tools")
    import imp
    imp.reload(mute)
    imp.reload(ikgoals)
    imp.reload(prefix)
    imp.reload(scale)
    imp.reload(store)
    imp.reload(bvh)
    imp.reload(mannequin)
    imp.reload(wrappers)
    imp.reload(legacy)
    #imp.reload(unreal)
    imp.reload(rig_panel)
else:
    print("Loading Rig Tools")
    from . import mute
    from . import ikgoals
    from . import prefix
    from . import scale
    from . import store
    from . import bvh
    from . import mannequin
    from . import wrappers
    from . import legacy
    #from . import unreal
    from . import rig_panel
    RigToolsFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Rig Tools")
    from . import mute, ikgoals, prefix, scale, store, bvh
    from . import mannequin, wrappers, legacy, rig_panel, unreal
    mute.register()
    ikgoals.register()
    prefix.register()
    scale.register()
    store.register()
    bvh.register()
    mannequin.register()
    wrappers.register()
    legacy.register()
    rig_panel.register()
    #unreal.register()

def unregister():
    from . import mute, ikgoals, prefix, scale, store, bvh
    from . import mannequin, wrappers, legacy, rig_panel, unreal
    #unreal.unregister()
    rig_panel.unregister()
    legacy.unregister()
    wrappers.unregister()
    mannequin.unregister()
    bvh.unregister()
    scale.unregister()
    store.unregister()
    prefix.unregister()
    ikgoals.unregister()
    mute.unregister()
