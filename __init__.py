#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2026, Thomas Larsson
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
    "version": (5,2,0),
    "blender": (5,2,0),
    "location": "UI > DAZ Setup, DAZ Runtime",
    "description": "Importer for native DAZ files (.duf, .dsf)",
    "warning": "",
    "doc_url": "https://github.com/Diffeomorphic/import_daz/wiki",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import_daz/issues?status=new&status=open",
    "category": "Import-Export"}

#----------------------------------------------------------
#   In some Blender builds numpy isn't found because
#   "site-packages" is not in sys.path
#----------------------------------------------------------

import sys
import os
try:
    import numpy
    fail = False
except ModuleNotFoundError:
    fail = True

if fail:
    missing = []
    for path in sys.path:
        if os.path.basename(path) == "python":
            packpath = os.path.join(path, "site-packages")
            if packpath not in sys.path:
                missing.append(packpath)
    print("Adding missing packages")
    for path in missing:
        print("  Add %s" % path)
        sys.path.append(path)

#----------------------------------------------------------
#   Modules
#----------------------------------------------------------

Modules = ["buildnumber", "settings", "utils", "error", "load_json", "driver", "uilist",
           "selector", "propgroups", "daz", "apply", "fileutils", "asset", "channels", "formula",
           "rig_utils", "bone_data", "transform", "node", "figure", "bone", "geometry",
           "store", "modifier", "load_morph", "morphing", "slider", "baked",
           "animation", "fix", "dbzfile", "panel", "erc",
           "tree", "material", "cycles", "cgroup", "pbr", "brick", "toon", "hair_material",
           "render", "camera", "light", "visibility",
           "guess", "convert", "files", "finger", "locks", "bone_chains",
           "merge_uvs", "merge_grafts", "merge_rigs", "empties",
           "matsel", "tables", "proxy", "transfer",
           "dforce", "pin", "main", "geonodes", "winder",
           "hd_data", "framer", "scan", "api",
    ]

Features = [
    "rig_tools", "simple_ik_tools", "mhx_tools",
    "rigify_tools", "pose_tools", "facs_tools", "object_tools",
    "material_tools", "shell_tools", "mesh_tools",
    "morph_tools", "hair_tools", "visibility_tools",
    "hd_tools", "simulation_tools", "export_tools",
]

FeatureNames = [
    "RigTools", "SimpleIkTools", "MhxTools",
    "RigifyTools", "PoseTools", "FacsTools", "ObjectTools",
    "MaterialTools", "ShellTools", "MeshTools",
    "MorphTools", "HairTools", "VisibilityTools",
    "HDTools", "SimulationTools", "ExportTools",
]


from .debug import DEBUG

if not DEBUG:
    pass
elif "bpy" in locals():
    print("Reloading DAZ Importer v %d.%d.%d" % bl_info["version"])
    if bpy.app.version < (5,0,0):
        import imp
    else:
        import importlib as imp
    for modname in Modules:
        exec("imp.reload(%s)" % modname)
    imp.reload(runtime.morph_armature)
    for feature in Features:
        exec("imp.reload(%s)" % feature)
else:
    print("\nLoading DAZ Importer v %d.%d.%d" % bl_info["version"])
    for modname in Modules:
        exec("from . import %s" % modname)
    from .runtime import morph_armature
    for feature in Features:
        exec("from . import %s" % feature)


import bpy
from bpy.props import BoolProperty
from .settings import GS
from .api import *

#----------------------------------------------------------
#   Preferences
#----------------------------------------------------------

def toggleModule(module, enable):
    exec("from . import %s" % module)
    if enable:
        exec("%s.register()" % module)
    else:
        exec("%s.unregister()" % module)


for feature,fname in zip(Features, FeatureNames):
    func = (
        'def toggle%s(self, context):\n' % fname +
        '    toggleModule("%s", self.use%s)\n' % (feature, fname)
    )
    exec(func)


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

    useSimpleIkTools : BoolProperty(
        name = "Simple IK Tools",
        description = "Tools for simple IK",
        default = False,
        update = toggleSimpleIkTools)

    useMhxTools : BoolProperty(
        name = "MHX Tools",
        description = "Tools for MHX rig",
        default = True,
        update = toggleMhxTools)

    useRigifyTools : BoolProperty(
        name = "Rigify Tools",
        description = "Tools for Rigify",
        default = True,
        update = toggleRigifyTools)

    useMaterialTools : BoolProperty(
        name = "Material Tools",
        description = "Tools for dealing with DAZ materials",
        default = False,
        update = toggleMaterialTools)

    useMeshTools : BoolProperty(
        name = "Mesh Tools",
        description = "Tools for dealing with DAZ meshes",
        default = False,
        update = toggleMeshTools)

    useMorphTools : BoolProperty(
        name = "Morph Tools",
        description = "Tools for dealing with DAZ morphs",
        default = False,
        update = toggleMorphTools)

    useHairTools : BoolProperty(
        name = "Hair Tools",
        description = "Tools for dealing with Hair morphs",
        default = True,
        update = toggleHairTools)

    useVisibilityTools : BoolProperty(
        name = "Visibility Tools",
        description = "Tools for dealing with Visibility morphs",
        default = True,
        update = toggleVisibilityTools)

    useHDTools : BoolProperty(
        name = "HD Tools",
        description = "Tools for dealing with HD morphs",
        default = False,
        update = toggleHDTools)

    useSimulationTools : BoolProperty(
        name = "Simulation Tools",
        description = "Simulation",
        default = False,
        update = toggleSimulationTools)

    useExportTools : BoolProperty(
        name = "Export Tools",
        description = "Tools for exporting presets and UV maps back to DAZ Studio",
        default = True,
        update = toggleExportTools)

    useRigTools : BoolProperty(
        name = "Rigging Tools",
        description = "Tools for rigging DAZ figures",
        default = False,
        update = toggleRigTools)

    usePoseTools : BoolProperty(
        name = "Pose Tools",
        description = "Tools for posing DAZ figures",
        default = False,
        update = togglePoseTools)

    useFacsTools : BoolProperty(
        name = "FACS Tools",
        description = "Tools for importing FACS animations",
        default = False,
        update = toggleFacsTools)

    useObjectTools : BoolProperty(
        name = "Object Tools",
        description = "Tools for objects",
        default = False,
        update = toggleObjectTools)

    useShellTools : BoolProperty(
        name = "Shell Tools",
        description = "Tools for editing shells and layered images",
        default = False,
        update = toggleShellTools)

    def draw(self, context):
        global thePrefs
        thePrefs = self
        self.layout.prop(self, "settingsDir")
        #self.layout.operator("daz.update_settings")
        row = self.layout.row()
        row.operator("daz.load_settings_file")
        row.operator("daz.save_settings_file")
        row = self.layout.row()
        row.operator("daz.enable_all_features")
        row.operator("daz.diaable_all_features")
        self.layout.label(text = "Features:")
        for fname in FeatureNames:
            self.layout.prop(self, "use%s" % fname)


class DAZ_OT_EnableAllFeatures(bpy.types.Operator):
    bl_idname = "daz.enable_all_features"
    bl_label = "Enable All Features"

    def execute(self, context):
        global thePrefs
        for fname in FeatureNames:
            setattr(thePrefs, "use%s" % fname, True)
        return {'PASS_THROUGH'}


class DAZ_OT_DisableAllFeatures(bpy.types.Operator):
    bl_idname = "daz.diaable_all_features"
    bl_label = "Disable All Features"

    def execute(self, context):
        global thePrefs
        for fname in FeatureNames:
            setattr(thePrefs, "use%s" % fname, False)
        return {'PASS_THROUGH'}

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

Regnames = ["propgroups", "daz", "uilist", "driver", "selector",
            "figure", "geometry", "dbzfile",
            "fix", "animation", "morphing", "slider", "panel", "erc",
            "material", "cgroup", "render", "visibility",
            "guess", "main", "finger", "locks",
            "matsel", "proxy",
            "merge_grafts", "merge_rigs", "apply", "empties",
            "pin", "transfer", "scan",
            ]

def register():
    print("Register DAZ Importer")
    for modname in Modules:
        exec("from . import %s" % modname)
    for modname in Modules:
        if modname in Regnames:
            exec("%s.register()" % modname)

    bpy.utils.register_class(DAZ_OT_EnableAllFeatures)
    bpy.utils.register_class(DAZ_OT_DisableAllFeatures)

    bpy.utils.register_class(DazPreferences)
    addon = bpy.context.preferences.addons.get(__name__)
    prefs = addon.preferences
    if prefs:
        for feature,fname in zip(Features, FeatureNames):
            if getattr(prefs, "use%s" % fname):
                exec("from . import %s" % feature)
                exec("%s.register()" % feature)

    GS.getSettingsDir(bpy.context)
    GS.loadDefaults()


def unregister():
    from .runtime import morph_armature
    morph_armature.unregister()
    for modname in Modules:
        exec("from . import %s" % modname)
    for modname in reversed(Modules):
        if modname in Regnames:
            exec("%s.unregister()" % modname)

    bpy.utils.unregister_class(DAZ_OT_EnableAllFeatures)
    bpy.utils.unregister_class(DAZ_OT_DisableAllFeatures)

    addon = bpy.context.preferences.addons.get(__name__)
    prefs = addon.preferences
    if prefs:
        for feature,fname in zip(Features, FeatureNames):
            if getattr(prefs, "use%s" % fname):
                exec("from . import %s" % feature)
                exec("%s.unregister()" % feature)
    bpy.utils.unregister_class(DazPreferences)


if __name__ == "__main__":
    register()

print("DAZ loaded")
