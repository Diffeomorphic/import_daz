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

if "bpy" in locals():
    print("Reloading DAZ Exporter")
    import imp
    imp.reload(preset)
    imp.reload(pose_preset)
    imp.reload(morph_preset)
else:
    print("\nLoading DAZ Exporter")
    import bpy
    from . import preset
    from . import pose_preset
    from . import morph_preset

from ..panel import DAZ_PT_RuntimeTab

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

class DAZ_PT_Export(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Export"

    def draw(self, context):
        self.layout.operator("daz.make_control_rig")
        self.layout.operator("daz.save_pose_preset")
        self.layout.operator("daz.save_morph_presets")
        self.layout.operator("daz.save_daz_figure")
        self.layout.operator("daz.save_uv")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Export,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    preset.register()
    pose_preset.register()
    morph_preset.register()
     

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    morph_preset.unregister()
    pose_preset.unregister()
    preset.unregister()
    