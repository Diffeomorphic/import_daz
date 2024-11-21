# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
    imp.reload(wrappers)
    imp.reload(legacy)
    imp.reload(rig_panel)
else:
    print("Loading Rig Tools")
    from . import mute
    from . import ikgoals
    from . import prefix
    from . import wrappers
    from . import legacy
    from . import rig_panel
    RigToolsFeature = True

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Rig Tools")
    from . import mute, ikgoals, prefix
    from . import wrappers, legacy, rig_panel
    mute.register()
    ikgoals.register()
    prefix.register()
    wrappers.register()
    legacy.register()
    rig_panel.register()

def unregister():
    from . import mute, ikgoals, prefix
    from . import wrappers, legacy, rig_panel
    rig_panel.unregister()
    legacy.unregister()
    wrappers.unregister()
    prefix.unregister()
    ikgoals.unregister()
    mute.unregister()
