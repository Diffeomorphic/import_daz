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
#   Rigging panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab


class DAZ_PT_Lowpoly(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_Lowpoly"
    bl_label = "Lowpoly"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.apply_morphs")
        self.layout.operator("daz.make_lowpoly")
        self.layout.operator("daz.add_push")


#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Lowpoly,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
