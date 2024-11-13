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
#   Rigging panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab
class DAZ_PT_DazRigifyBuild(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_label = "Rigify"

    def draw(self, context):
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")

#------------------------------------------------------------------------
#   DAZ Rigify props panels
#------------------------------------------------------------------------

class DAZ_PT_DazRigifyProps(bpy.types.Panel):
    bl_label = "DAZ Rigify Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and
                ob.DazRig in ["rigify", "rigify2"])

    def draw(self, context):
        rig = context.object
        self.layout.prop(rig, "MhaGazeFollowsHead", text="Gaze Follows Head")
        self.layout.prop(rig, "MhaGaze_L", text="Left Gaze")
        self.layout.prop(rig, "MhaGaze_R", text="Right Gaze")
        from ..fix import F_TONGUE
        if rig.data.MhaFeatures & F_TONGUE:
            self.layout.prop(rig, "MhaTongueIk", text="Tongue IK")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_DazRigifyBuild,
    DAZ_PT_DazRigifyProps,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
