# Copyright (c) 2016-2024, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


bl_info = {
    "name": "DAZ importer",
    "author": "Thomas Larsson",
    "version": (1,7,2),
    "blender": (3,6,0),
    "location": "UI > DAZ Setup, DAZ Runtime",
    "description": "Import native DAZ files (.duf, .dsf)",
    "warning": "",
    "doc_url": "https://bitbucket.org/Diffeomorphic/import_daz/wiki/Home",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import_daz/issues?status=new&status=open",
    "category": "Import-Export"}

#----------------------------------------------------------
#   Preferences
#----------------------------------------------------------

import bpy

class DazPreferences(bpy.types.AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    showSetupTab : bpy.props.BoolProperty(
        name = "Show Setup Tab",
        description = "Show the DAZ Setup tab",
        default = True)

    showRuntimeTab : bpy.props.BoolProperty(
        name = "Show Runtime Tab",
        description = "Show the DAZ Runtime tab",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "showSetupTab")
        self.layout.prop(self, "showRuntimeTab")


def getSetupEnabled(context):
    prefs = context.preferences.addons[__name__].preferences
    return (prefs and prefs.showSetupTab)


def getRuntimeEnabled(context):
    prefs = context.preferences.addons[__name__].preferences
    return (prefs and prefs.showRuntimeTab)

#----------------------------------------------------------
#   Modules
#----------------------------------------------------------

def importModules():
    import os
    import importlib
    global theModules

    try:
        theModules
    except NameError:
        theModules = []

    if theModules:
        print("\nReloading DAZ")
        for mod in theModules:
            importlib.reload(mod)
    else:
        print("\nLoading DAZ")
        modnames = ["buildnumber", "settings", "utils", "error", "load_json", "driver", "uilist",
                    "selector", "propgroups", "daz", "fileutils", "asset", "channels", "formula",
                    "bone_data", "transform", "node", "figure", "bone", "geometry",
                    "layers", "fix", "modifier", "animation", "simple", "load_morph", "morphing", "category", "dbzfile", "panel",
                    "tree", "material", "cycles", "cgroup", "pbr", "brick", "render", "camera", "light",
                    "guess", "convert", "files", "merge", "finger",
                    "matedit", "tables", "proxy", "hide", "store",
                    "mhx_data", "mhx", "rigify_data", "rigify", "hair", "transfer", "dforce", "main",
                    "udim", "hdmorphs", "preset", "moho", "facecap", "scan", "api",
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
            "matedit", "proxy", "rigify", "merge", "hide", "store",
            "mhx", "hair", "transfer", "dforce",
            "hdmorphs", "facecap", "preset", "moho", "udim", "scan"]

def register():
    for mod in theModules:
        modname = mod.__name__.rsplit(".",1)[-1]
        if modname in regnames:
            mod.register()
    GS.loadDefaults()
    GS.loadAbsPaths()
    bpy.utils.register_class(DazPreferences)


def unregister():
    bpy.utils.unregister_class(DazPreferences)
    for mod in reversed(theModules):
        modname = mod.__name__.rsplit(".",1)[-1]
        if modname in regnames:
            mod.unregister()


if __name__ == "__main__":
    register()

print("DAZ loaded")
