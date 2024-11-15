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
elif "ExportFeature" in locals():
    print("Reloading Export Tools")
    import imp
    imp.reload(preset)
    imp.reload(pose_preset)
    imp.reload(morph_preset)
else:
    print("Loading Export Tools")
    from . import preset
    from . import pose_preset
    from . import morph_preset
    ExportFeature = True

#----------------------------------------------------------
#   Export panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_RuntimeTab

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
    print("Register Export Tools")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import preset, pose_preset, morph_preset
    preset.register()
    pose_preset.register()
    morph_preset.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    from . import preset, pose_preset, morph_preset
    morph_preset.unregister()
    pose_preset.unregister()
    preset.unregister()
