# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "RigifyFeature" in locals():
    print("Reloading Rigify Tools")
    import imp
    imp.reload(rigify)
    imp.reload(rigify_snap)
    imp.reload(panel)
else:
    print("Loading Rigify Tools")
    from . import rigify
    from . import rigify_snap
    from . import panel
    RigifyFeature = True

#----------------------------------------------------------
#   Access
#----------------------------------------------------------

from .rigify_snap import setRigifyFkIk, setRigifyLayers, clearOtherRigify
from .layers import R_DETAIL, R_CUSTOM

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Rigify Tools")
    from . import rigify, rigify_snap, panel
    rigify.register()
    rigify_snap.register()
    panel.register()

def unregister():
    from . import rigify, rigify_snap, panel
    rigify.unregister()
    rigify_snap.unregister()
    panel.unregister()
