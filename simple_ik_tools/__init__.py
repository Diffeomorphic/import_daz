# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "SimpleIkFeature" in locals():
    print("Reloading Simple IK Tools")
    import imp
    imp.reload(simple)
    imp.reload(panel)
else:
    print("Loading Simple IK Tools")
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
    try:
        print("Register Simple IK Tools")
        from . import simple, panel
        simple.register()
        panel.register()
    except (RuntimeError, ValueError):
        pass

def unregister():
    try:
        from . import simple, panel
        simple.unregister()
        panel.unregister()
    except (RuntimeError, ValueError):
        pass
