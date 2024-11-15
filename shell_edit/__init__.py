#  Shell Editor - Tools for manipulating shells and layered images from DAZ Importer
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

from ..debug import DEBUG

if not DEBUG:
    pass
elif "ShellEditFeature" in locals():
    print("Reloading Shell Editor")
    import imp
    imp.reload(shell)
    imp.reload(lie)
    imp.reload(uvs)
else:
    print("Loading Shell Editor")
    from . import shell
    from . import lie
    from . import uvs
    ShellEditFeature = True

#----------------------------------------------------------
#   Panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_ShellEdit(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "Shell Editor"

    def draw(self, context):
        self.layout.operator("daz.fix_shells")
        self.layout.operator("daz.replace_shells")
        self.layout.separator()
        self.layout.operator("daz.copy_shells")
        self.layout.operator("daz.sort_shells")
        self.layout.operator("daz.remove_shells")
        self.layout.operator("daz.add_custom_shell")
        self.layout.separator()
        self.layout.operator("daz.import_shells_as_images")
        self.layout.operator("daz.remove_shell_images")
        self.layout.operator("daz.fix_normal_groups")
        self.layout.separator()
        self.layout.operator("daz.disable_shell_drivers")
        self.layout.operator("daz.enable_shell_drivers")
        self.layout.operator("daz.remove_all_influs")
        self.layout.separator()
        self.layout.operator("daz.assign_shell_map")
        self.layout.operator("daz.prune_node_trees")
        self.layout.separator()
        self.layout.operator("daz.copy_uvs")
        self.layout.operator("daz.copy_attributes")
        self.layout.separator()
        self.layout.operator("daz.update_shell_drivers")

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_PT_ShellEdit
]

def register():
    print("Register Shell Edit")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import shell, lie, uvs
    shell.register()
    lie.register()
    uvs.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    from . import shell, lie, uvs
    uvs.unregister()
    lie.unregister()
    shell.unregister()
