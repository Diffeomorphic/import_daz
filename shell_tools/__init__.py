# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ..debug import DEBUG

if not DEBUG:
    pass
elif "ShellEditFeature" in locals():
    print("Reloading Shell Tools")
    import imp
    imp.reload(shell)
    imp.reload(import_shell)
    imp.reload(lie)
else:
    print("Loading Shell Tools")
    from . import shell
    from . import import_shell
    from . import lie
    ShellEditFeature = True

#----------------------------------------------------------
#   Panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Shells(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_ShellEdit"
    bl_label = "Shells"

    def draw(self, context):
        self.layout.operator("daz.import_shells")
        self.layout.separator()
        self.layout.operator("daz.fix_shells")
        self.layout.operator("daz.replace_shells")
        self.layout.operator("daz.copy_shells")
        self.layout.operator("daz.sort_shells")
        self.layout.operator("daz.remove_shells")
        self.layout.operator("daz.add_custom_shell")
        self.layout.separator()
        self.layout.operator("daz.assign_shell_map")


class DAZ_PT_ShellImages(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_ShellImages"
    bl_label = "Shell Images"

    def draw(self, context):
        self.layout.operator("daz.import_shells_as_images")
        self.layout.operator("daz.remove_shell_images")
        self.layout.operator("daz.fix_normal_groups")
        self.layout.operator("daz.set_hsv")


class DAZ_PT_ShellDrivers(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMaterials"
    bl_id = "DAZ_PT_ShellDrivers"
    bl_label = "Shell Drivers"

    def draw(self, context):
        self.layout.operator("daz.drive_shell_influence")
        self.layout.operator("daz.disable_shell_drivers")
        self.layout.operator("daz.enable_shell_drivers")
        self.layout.operator("daz.remove_all_influs")
        self.layout.operator("daz.retarget_shell_drivers")
        self.layout.operator("daz.update_shell_drivers")

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_PT_Shells,
    DAZ_PT_ShellImages,
    DAZ_PT_ShellDrivers
]

def register():
    print("Register Shell Tools")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import shell, import_shell, lie
    shell.register()
    import_shell.register()
    lie.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    from . import shell, import_shell, lie
    lie.unregister()
    import_shell.unregister()
    shell.unregister()
