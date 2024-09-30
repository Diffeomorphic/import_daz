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
           "layers", "fix", "modifier", "load_morph", "morphing", "baked",
           "animation", "simple", "category", "dbzfile", "panel",
           "tree", "material", "cycles", "cgroup", "pbr", "brick", "render", "camera", "light",
           "guess", "convert", "files", "merge", "finger",
           "matedit", "scale", "tables", "proxy", "hide",
           "mhx_data", "mhx", "rigify_data", "rigify", "transfer",
           "dforce", "pin", "hair", "main", "geonodes",
           "preset", "pose_preset", "morph_preset",
           "udim", "hdmorphs", "ctrl_rig", "moho", "gaze", "scan", "api",
    ]

if "bpy" in locals():
    print("Reloading DAZ Importer v %d.%d.%d" % bl_info["version"])
    import imp
    for modname in Modules:
        exec("imp.reload(%s)" % modname)
    #imp.reload("runtime.morph_armature")
else:
    print("\nLoading DAZ Importer v %d.%d.%d" % bl_info["version"])
    import bpy
    for modname in Modules:
        exec("from . import %s" % modname)
    from .runtime import morph_armature

from .settings import GS
from .api import *

#----------------------------------------------------------
#   Preferences
#----------------------------------------------------------

import sys
import os

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

    def draw(self, context):
        self.layout.prop(self, "settingsDir")
        #self.layout.operator("daz.update_settings")
        self.layout.operator("daz.load_settings_file")
        self.layout.operator("daz.save_settings_file")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

Regnames = ["propgroups", "daz", "uilist", "driver", "selector",
            "figure", "geometry", "dbzfile", "simple",
            "fix", "animation", "morphing", "category", "panel",
            "material", "cgroup", "render",
            "guess", "convert", "main", "finger",
            "matedit", "scale", "proxy", "rigify", "merge", "hide",
            "mhx", "pin", "hair", "transfer", "dforce", "gaze",
            "hdmorphs", "ctrl_rig", "moho", "udim", "scan",
            "preset", "pose_preset", "morph_preset"]

isRegistered = False

def register():
    global isRegistered
    if isRegistered:
        print("DAZ Importer already registered")
        return
    print("Register DAZ Importer")
    isRegistered = True
    for modname in Modules:
        if modname in Regnames:
            exec("%s.register()" % modname)
    bpy.utils.register_class(DazPreferences)
    GS.getSettingsDir(bpy.context)
    GS.loadDefaults()
    GS.loadAbsPaths()


def unregister():
    global isRegistered
    isRegistered = False
    bpy.utils.unregister_class(DazPreferences)
    for modname in reversed(Modules):
        if modname in Regnames:
            exec("%s.unregister()" % modname)


if __name__ == "__main__":
    register()

print("DAZ loaded")
