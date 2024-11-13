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

bl_info = {
    "name": "DAZ Importer",
    "author": "Thomas Larsson",
    "version": (4,2,1),
    "blender": (4,2,1),
    "location": "UI > DAZ Setup, DAZ Runtime",
    "description": "Importer for native DAZ files (.duf, .dsf)",
    "warning": "",
    "doc_url": "https://bitbucket.org/Diffeomorphic/import_daz/wiki/Home",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import_daz/issues?status=new&status=open",
    "category": "Import-Export"}

#----------------------------------------------------------
#   Modules
#----------------------------------------------------------

Modules = ["buildnumber", "settings", "utils", "error", "load_json", "driver", "uilist",
           "selector", "propgroups", "daz", "fileutils", "asset", "channels", "formula",
           "bone_data", "transform", "node", "figure", "bone", "geometry",
           "fix", "modifier", "load_morph", "morphing", "baked",
           "animation", "rig_utils", "category", "dbzfile", "panel",
           "tree", "material", "cycles", "cgroup", "pbr", "brick", "toon", "render", "camera", "light",
           "guess", "convert", "files", "finger",
           "matedit", "udim", "merge", "scale", "tables", "proxy", "hide",
           "transfer",
           "dforce", "pin", "hair", "main", "geonodes", "attr",
           "hdmorphs", "ctrl_rig", "moho", "gaze", "scan", "api",
    ]

from .debug import DEBUG

if not DEBUG:
    pass
elif "bpy" in locals():
    print("Reloading DAZ Importer v %d.%d.%d" % bl_info["version"])
    import imp
    for modname in Modules:
        exec("imp.reload(%s)" % modname)
    imp.reload(export_daz)
    imp.reload(rig_daz)
    imp.reload(shell_edit)
    imp.reload(simple_ik)
    imp.reload(rig_mhx)
    imp.reload(rig_rigify)

else:
    print("\nLoading DAZ Importer v %d.%d.%d" % bl_info["version"])
    for modname in Modules:
        exec("from . import %s" % modname)
    from .runtime import morph_armature
    from . import export_daz
    from . import rig_daz
    from . import shell_edit
    from . import simple_ik
    from . import rig_mhx
    from . import rig_rigify


import bpy
from .settings import GS
from .api import *

#----------------------------------------------------------
#   Preferences
#----------------------------------------------------------

import sys
import os

def toggleExportDaz(self, context):
    toggleModule("export_daz", self.useExportDaz)

def toggleRigDaz(self, context):
    toggleModule("rig_daz", self.useRigDaz)

def toggleShellEdit(self, context):
    toggleModule("shell_edit", self.useShellEdit)

def toggleSimpleIk(self, context):
    toggleModule("simple_ik", self.useSimpleIk)

def toggleRigMhx(self, context):
    toggleModule("rig_mhx", self.useRigMhx)

def toggleRigRigify(self, context):
    toggleModule("rig_rigify", self.useRigRigify)

def toggleModule(module, enable):
    if enable:
        exec("%s.register()" % module)
    else:
        exec("%s.unregister()" % module)


def updateSettings(self, context):
    GS.getSettingsDir(context)
    filepath = GS.getSettingsPath()
    GS.loadSettings(filepath)

class DazPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    if sys.platform == 'win32':
        defaultDir = os.path.expanduser("~\\Documents\\DAZ Importer")
    elif sys.platform == 'darwin':
        defaultDir = os.path.expanduser("~/DAZ Importer")
    else:
        defaultDir = os.path.expanduser("~/DAZ Importer")

    settingsDir : bpy.props.StringProperty(
        name = "Settings directory",
        description = "Directory holding Daz Importer global settings",
        subtype='DIR_PATH',
        default = defaultDir,
        update = updateSettings
    )

    useExportDaz : bpy.props.BoolProperty(
        name = "DAZ Exporter",
        description = "Enable DAZ Exporter tools",
        default = False,
        update = toggleExportDaz)

    useRigDaz : bpy.props.BoolProperty(
        name = "DAZ Rigging",
        description = "Enable tools for rigging DAZ figures",
        default = False,
        update = toggleRigDaz)

    useShellEdit : bpy.props.BoolProperty(
        name = "Shell Editor",
        description = "Tools for editing shells and layered images",
        default = False,
        update = toggleShellEdit)

    useSimpleIk : bpy.props.BoolProperty(
        name = "Simple IK",
        description = "Tools for simple IK",
        default = False,
        update = toggleSimpleIk)

    useRigMhx : bpy.props.BoolProperty(
        name = "MHX",
        description = "Enable tools for MHX rig",
        default = False,
        update = toggleRigMhx)

    useRigRigify : bpy.props.BoolProperty(
        name = "Rigify",
        description = "Enable tools for Rigify",
        default = False,
        update = toggleRigRigify)

    def draw(self, context):
        self.layout.prop(self, "settingsDir")
        #self.layout.operator("daz.update_settings")
        self.layout.operator("daz.load_settings_file")
        self.layout.operator("daz.save_settings_file")
        self.layout.label(text = "Features:")
        self.layout.prop(self, "useExportDaz")
        self.layout.prop(self, "useRigDaz")
        self.layout.prop(self, "useShellEdit")
        self.layout.prop(self, "useSimpleIk")
        self.layout.prop(self, "useRigMhx")
        self.layout.prop(self, "useRigRigify")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

Regnames = ["propgroups", "daz", "uilist", "driver", "selector",
            "figure", "geometry", "dbzfile", "simple", "rig_utils",
            "fix", "animation", "morphing", "category", "panel",
            "material", "cgroup", "render",
            "guess", "convert", "main", "finger",
            "matedit", "scale", "proxy", "rigify", "merge", "hide",
            "mhx", "pin", "hair", "transfer", "dforce", "gaze",
            "hdmorphs", "ctrl_rig", "moho", "udim", "scan", "attr",
            ]

def register():
    print("Register DAZ Importer")
    for modname in Modules:
        exec("from . import %s" % modname)
    for modname in Modules:
        if modname in Regnames:
            exec("%s.register()" % modname)

    bpy.utils.register_class(DazPreferences)
    addon = bpy.context.preferences.addons.get(__name__)
    prefs = addon.preferences
    if prefs:
        if prefs.useExportDaz:
            from . import export_daz
            export_daz.register()
        if prefs.useRigDaz:
            from . import rig_daz
            rig_daz.register()
        if prefs.useShellEdit:
            from . import shell_edit
            shell_edit.register()
        if prefs.useSimpleIk:
            from . import simple_ik
            simple_ik.register()
        if prefs.useRigMhx:
            from . import rig_mhx
            rig_mhx.register()
        if prefs.useRigRigify:
            from . import rig_rigify
            rig_rigify.register()

    GS.getSettingsDir(bpy.context)
    GS.loadDefaults()
    GS.loadAbsPaths()


def unregister():
    for modname in Modules:
        exec("from . import %s" % modname)
    for modname in reversed(Modules):
        if modname in Regnames:
            exec("%s.unregister()" % modname)

    addon = bpy.context.preferences.addons.get(__name__)
    prefs = addon.preferences
    if prefs:
        if prefs.useExportDaz:
            from . import export_daz
            export_daz.unregister()
        if prefs.useRigDaz:
            from . import rig_daz
            rig_daz.unregister()
        if prefs.useShellEdit:
            from . import shell_edit
            shell_edit.unregister()
        if prefs.useSimpleIk:
            from . import simple_ik
            simple_ik.unregister()
        if prefs.useRigMhx:
            from . import rig_mhx
            rig_mhx.unregister()
        if prefs.useRigRigify:
            from . import rig_rigify
            rig_rigify.unregister()
    bpy.utils.unregister_class(DazPreferences)


if __name__ == "__main__":
    register()

print("DAZ loaded")
