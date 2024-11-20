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

import bpy
from bpy.props import *
from .utils import *
from .error import *

#------------------------------------------------------------------------
#   Show/Hide all
#------------------------------------------------------------------------

class SetAllVisibility:
    prefix : StringProperty()

    def run(self, context):
        from .selector import autoKeyProp
        rig = getRigFromContext(context)
        scn = context.scene
        if rig is None:
            return
        for key in rig.keys():
            if key[0:3] == "Mhh":
                if key:
                    rig[key] = self.on
                    autoKeyProp(rig, key, scn, scn.frame_current, True)
        updateDrivers(rig)


class DAZ_OT_ShowAllVis(DazOperator, SetAllVisibility):
    bl_idname = "daz.show_all_vis"
    bl_label = "Show All"
    bl_description = "Show all meshes/makeup of this rig"

    on = True


class DAZ_OT_HideAllVis(DazOperator, SetAllVisibility):
    bl_idname = "daz.hide_all_vis"
    bl_label = "Hide All"
    bl_description = "Hide all meshes/makeup of this rig"

    on = False


class DAZ_OT_ToggleVis(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_vis"
    bl_label = "Toggle Vis"
    bl_description = "Toggle visibility of this mesh"

    name : StringProperty()

    def run(self, context):
        from .selector import autoKeyProp
        rig = getRigFromContext(context)
        scn = context.scene
        if rig:
            rig[self.name] = not rig[self.name]
            autoKeyProp(rig, self.name, scn, scn.frame_current, True)
            updateDrivers(rig)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ShowAllVis,
    DAZ_OT_HideAllVis,
    DAZ_OT_ToggleVis,
]

def register():
    bpy.types.Object.DazVisibilityDrivers = BoolProperty(default = False)
    bpy.types.Object.DazVisibilityCollections = BoolProperty(default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

