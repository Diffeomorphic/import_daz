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
    "blender": (4,2,0),
    "location": "UI > DAZ Setup, DAZ Runtime",
    "description": "Importer for native DAZ files (.duf, .dsf)",
    "warning": "",
    "doc_url": "https://bitbucket.org/Diffeomorphic/import_daz/wiki/Home",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import_daz/issues?status=new&status=open",
    "category": "Import-Export"}

#----------------------------------------------------------
#   Modules
#----------------------------------------------------------

import bpy

def importModules():
    import os
    import importlib
    global theModules

    try:
        theModules
    except NameError:
        theModules = []

    if theModules:
        print("\nReloading DAZ Importer v %d.%d.%d" % bl_info["version"])
        for mod in theModules:
            importlib.reload(mod)
    else:
        print("\nLoading DAZ Importer v %d.%d.%d" % bl_info["version"])
        modnames = ["buildnumber", "settings", "utils", "error", "load_json", "driver", "uilist",
                    "selector", "propgroups", "daz", "fileutils", "asset", "channels", "formula",
                    "bone_data", "transform", "node", "figure", "bone", "geometry",
                    "layers", "fix", "modifier", "load_morph", "morphing", "animation", "simple", "category", "dbzfile", "panel",
                    "tree", "material", "cycles", "cgroup", "pbr", "brick", "render", "camera", "light",
                    "guess", "convert", "files", "merge", "finger",
                    "matedit", "scale", "tables", "proxy", "hide",
                    "mhx_data", "mhx", "rigify_data", "rigify", "transfer",
                    "dforce", "pin", "hair", "main",
                    "udim", "hdmorphs", "ctrl_rig", "moho", "gaze", "scan", "api",
                    "runtime.morph_armature"]
        if bpy.app.version >= (3,1,0):
            modnames.append("geonodes")
        anchor = os.path.basename(__file__[0:-12])
        theModules = []
        for modname in modnames:
            mod = importlib.import_module("." + modname, anchor)
            theModules.append(mod)

importModules()
from .settings import GS
from .api import *

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

regnames = ["propgroups", "daz", "uilist", "driver", "selector",
            "figure", "geometry", "dbzfile", "simple",
            "fix", "animation", "morphing", "category", "panel",
            "material", "cgroup", "render",
            "guess", "convert", "main", "finger",
            "matedit", "scale", "proxy", "rigify", "merge", "hide",
            "mhx", "pin", "hair", "transfer", "dforce", "gaze",
            "hdmorphs", "ctrl_rig", "moho", "udim", "scan"]

isRegistered = False

def register():
    global isRegistered
    if isRegistered:
        print("DAZ Importer already registered")
        return
    print("Register DAZ Importer")
    isRegistered = True
    for mod in theModules:
        modname = mod.__name__.rsplit(".",1)[-1]
        if modname in regnames:
            mod.register()
    GS.loadDefaults()
    GS.loadAbsPaths()


def unregister():
    global isRegistered
    isRegistered = False
    for mod in reversed(theModules):
        modname = mod.__name__.rsplit(".",1)[-1]
        if modname in regnames:
            mod.unregister()


if __name__ == "__main__":
    register()

print("DAZ loaded")
