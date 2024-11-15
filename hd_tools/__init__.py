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
elif "HDFeature" in locals():
    print("Reloading HD Tools")
    import imp
    imp.reload(hd_morphs)
else:
    print("Loading HD Tools")
    from . import hd_morphs
    HDFeature = True

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_HDMesh(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_HDMesh"
    bl_label = "HD Mesh"

    def draw(self, context):
        self.layout.operator("daz.copy_grafts_groups")
        if bpy.app.version >= (2,90,0):
            self.layout.operator("daz.make_multires")
            self.layout.separator()
        self.layout.operator("daz.bake_maps")
        self.layout.operator("daz.load_baked_maps")
        self.layout.separator()
        self.layout.operator("daz.load_normal_map")
        self.layout.operator("daz.load_scalar_disp")
        self.layout.operator("daz.load_vector_disp")
        self.layout.operator("daz.add_driven_value_nodes")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register HD Tools")
    bpy.utils.register_class(DAZ_PT_HDMesh)
    from . import hd_morphs
    hd_morphs.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_HDMesh)
    from . import hd_morphs
    hd_morphs.unregister()
