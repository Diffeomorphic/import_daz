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

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "MorphFeature" in locals():
    print("Reloading Morph Tools")
    import imp
    imp.reload(category)
else:
    print("\nLoading Morph Tools")
    from . import category
    MorphFeature = True

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Categories(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMorphs"
    bl_idname = "DAZ_PT_Categories"
    bl_label = "Categories"

    def draw(self, context):
        self.layout.operator("daz.remove_shapekeys")
        self.layout.separator()
        self.layout.operator("daz.add_shape_to_category")
        self.layout.operator("daz.remove_shape_from_category")
        self.layout.operator("daz.rename_category")
        self.layout.operator("daz.join_categories")
        self.layout.operator("daz.remove_categories")
        self.layout.operator("daz.remove_standard_morphs")
        self.layout.operator("daz.protect_categories")
        self.layout.operator("daz.protect_morphs")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Categories,
]

def register():
    print("Register Morph Tools")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import category
    category.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    from . import category
    category.unregister()
