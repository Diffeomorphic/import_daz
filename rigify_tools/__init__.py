# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
    imp.reload(rigify_data)
    imp.reload(rigify)
    imp.reload(panel)
else:
    print("Loading Rigify Tools")
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
    print("Register Rigify Tools")
    from . import rigify, panel
    rigify.register()
    panel.register()

def unregister():
    from . import rigify, panel
    rigify.unregister()
    panel.unregister()
