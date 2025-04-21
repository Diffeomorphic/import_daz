# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
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
    imp.reload(varia)
    imp.reload(connect_chains)
    imp.reload(ikgoals)
    imp.reload(prefix)
    imp.reload(wrappers)
    imp.reload(legacy)
    imp.reload(rig_panel)
else:
    print("Loading Rig Tools")
    from . import varia
    from . import connect_chains
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
    try:
        print("Register Rig Tools")
        from . import varia, connect_chains, ikgoals, prefix
        from . import wrappers, legacy, rig_panel
        varia.register()
        connect_chains.register()
        ikgoals.register()
        prefix.register()
        wrappers.register()
        legacy.register()
        rig_panel.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import varia, connect_chains, ikgoals, prefix
        from . import wrappers, legacy, rig_panel
        rig_panel.unregister()
        legacy.unregister()
        wrappers.unregister()
        prefix.unregister()
        ikgoals.unregister()
        connect_chains.unregister()
        varia.unregister()
    except (RuntimeError, ValueError):
        pass
