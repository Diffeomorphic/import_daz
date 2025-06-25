# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..driver import setBoolProp, addDriver

#----------------------------------------------------------
#   Drive Modifier influence
#----------------------------------------------------------

class DAZ_OT_DriveModifierInfluence(DazOperator, IsMesh):
    bl_idname = "daz.drive_modifier_influence"
    bl_label = "Drive Modifier Influence"
    bl_description = "Create drivers for modifier visibility.\nTo disable modifier with file linking"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            rig = ob
            if ob.parent and ob.parent.type == 'ARMATURE':
                rig = ob.parent
                rig.hide_viewport = False
            obname = stripName(ob.name)
            for mod in ob.modifiers:
                prop = "Mhd%s %s " % (obname, mod.name)
                setBoolProp(rig, prop, True, True)
                addDriver(mod, "show_viewport", rig, propRef(prop), "x")
                addDriver(mod, "show_render", rig, propRef(prop), "x")
                dazRna(ob).DazVisibilityDrivers = True
                dazRna(rig).DazVisibilityDrivers = True

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_DriveModifierInfluence,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)