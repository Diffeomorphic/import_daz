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
    "version": (4,3,0),
    "blender": (4,3,0),
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
           "store", "fix", "modifier", "load_morph", "morphing", "baked",
           "animation", "rig_utils", "dbzfile", "panel",
           "tree", "material", "cycles", "cgroup", "pbr", "brick", "toon", "hair_material",
           "render", "camera", "light", "visibility",
           "guess", "convert", "files", "finger",
           "merge_uvs", "merge_grafts", "merge_rigs", "empties",
           "matsel", "tables", "proxy", "transfer",
           "dforce", "pin", "main", "geonodes",
           "hd_data", "ctrl_rig", "moho", "scan", "api",
    ]

from .debug import DEBUG

if not DEBUG:
    pass
elif "bpy" in locals():
    print("Reloading DAZ Importer v %d.%d.%d" % bl_info["version"])
    import imp
    for modname in Modules:
        exec("imp.reload(%s)" % modname)
    imp.reload(simple_ik_tools)
    imp.reload(mhx_tools)
    imp.reload(rigify_tools)
    imp.reload(rig_tools)
    imp.reload(pose_tools)
    imp.reload(object_tools)
    imp.reload(material_tools)
    imp.reload(mesh_tools)
    imp.reload(morph_tools)
    imp.reload(hair_tools)
    imp.reload(visibility_tools)
    imp.reload(hd_tools)
    imp.reload(simulation_tools)
    imp.reload(export_tools)
    imp.reload(shell_tools)

else:
    print("\nLoading DAZ Importer v %d.%d.%d" % bl_info["version"])
    for modname in Modules:
        exec("from . import %s" % modname)
    from .runtime import morph_armature
    from . import simple_ik_tools
    from . import mhx_tools
    from . import rigify_tools
    from . import rig_tools
    from . import pose_tools
    from . import object_tools
    from . import material_tools
    from . import mesh_tools
    from . import morph_tools
    from . import hair_tools
    from . import visibility_tools
    from . import hd_tools
    from . import simulation_tools
    from . import export_tools
    from . import shell_tools


import bpy
from bpy.props import BoolProperty
from .settings import GS
from .api import *

#----------------------------------------------------------
#   Preferences
#----------------------------------------------------------

import sys
import os

def toggleSimpleIkTools(self, context):
    toggleModule("simple_ik_tools", self.useSimpleIkTools)

def toggleMhxTools(self, context):
    toggleModule("mhx_tools", self.useMhxTools)

def toggleRigifyTools(self, context):
    toggleModule("rigify_tools", self.useRigifyTools)

def toggleRigTools(self, context):
    toggleModule("rig_tools", self.useRigTools)

def togglePoseTools(self, context):
    toggleModule("pose_tools", self.usePoseTools)

def toggleObjectTools(self, context):
    toggleModule("object_tools", self.useObjectTools)

def toggleMaterialTools(self, context):
    toggleModule("material_tools", self.useMaterialTools)

def toggleMeshTools(self, context):
    toggleModule("mesh_tools", self.useMeshTools)

def toggleMorphTools(self, context):
    toggleModule("morph_tools", self.useMorphTools)

def toggleHairTools(self, context):
    toggleModule("hair_tools", self.useHairTools)

def toggleVisibilityTools(self, context):
    toggleModule("visibility_tools", self.useVisibilityTools)

def toggleHDTools(self, context):
    toggleModule("hd_tools", self.useHDTools)

def toggleSimulationTools(self, context):
    toggleModule("simulation_tools", self.useSimulationTools)

def toggleExportTools(self, context):
    toggleModule("export_tools", self.useExportTools)

def toggleShellTools(self, context):
    toggleModule("shell_tools", self.useShellTools)

def toggleModule(module, enable):
    exec("from . import %s" % module)
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

    useSimpleIkTools : BoolProperty(
        name = "Simple IK Tools",
        description = "Tools for simple IK",
        default = False,
        update = toggleSimpleIkTools)

    useMhxTools : BoolProperty(
        name = "MHX Tools",
        description = "Tools for MHX rig",
        default = False,
        update = toggleMhxTools)

    useRigifyTools : BoolProperty(
        name = "Rigify Tools",
        description = "Tools for Rigify",
        default = False,
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
        default = False,
        update = toggleHairTools)

    useVisibilityTools : BoolProperty(
        name = "Visibility Tools",
        description = "Tools for dealing with Visibility morphs",
        default = False,
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
        default = False,
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
        self.layout.prop(self, "settingsDir")
        #self.layout.operator("daz.update_settings")
        self.layout.operator("daz.load_settings_file")
        self.layout.operator("daz.save_settings_file")
        self.layout.label(text = "Features:")
        self.layout.prop(self, "useRigTools")
        self.layout.prop(self, "useSimpleIkTools")
        self.layout.prop(self, "useMhxTools")
        self.layout.prop(self, "useRigifyTools")
        self.layout.prop(self, "usePoseTools")
        self.layout.prop(self, "useObjectTools")
        self.layout.prop(self, "useMaterialTools")
        self.layout.prop(self, "useShellTools")
        self.layout.prop(self, "useMeshTools")
        self.layout.prop(self, "useMorphTools")
        self.layout.prop(self, "useHairTools")
        self.layout.prop(self, "useVisibilityTools")
        self.layout.prop(self, "useHDTools")
        self.layout.prop(self, "useSimulationTools")
        self.layout.prop(self, "useExportTools")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

Regnames = ["propgroups", "daz", "uilist", "driver", "selector",
            "figure", "geometry", "dbzfile",
            "fix", "animation", "morphing", "panel",
            "material", "cgroup", "render", "visibility",
            "guess", "main", "finger",
            "matsel", "proxy",
            "merge_grafts", "merge_rigs", "empties",
            "pin", "transfer", "moho", "scan",
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
        if prefs.useSimpleIkTools:
            from . import simple_ik_tools
            simple_ik_tools.register()
        if prefs.useMhxTools:
            from . import mhx_tools
            mhx_tools.register()
        if prefs.useRigifyTools:
            from . import rigify_tools
            rigify_tools.register()
        if prefs.useRigTools:
            from . import rig_tools
            rig_tools.register()
        if prefs.usePoseTools:
            from . import pose_tools
            pose_tools.register()
        if prefs.useObjectTools:
            from . import object_tools
            object_tools.register()
        if prefs.useMaterialTools:
            from . import material_tools
            material_tools.register()
        if prefs.useMeshTools:
            from . import mesh_tools
            mesh_tools.register()
        if prefs.useMorphTools:
            from . import morph_tools
            morph_tools.register()
        if prefs.useHairTools:
            from . import hair_tools
            hair_tools.register()
        if prefs.useVisibilityTools:
            from . import visibility_tools
            visibility_tools.register()
        if prefs.useHDTools:
            from . import hd_tools
            hd_tools.register()
        if prefs.useSimulationTools:
            from . import simulation_tools
            simulation_tools.register()
        if prefs.useExportTools:
            from . import export_tools
            export_tools.register()
        if prefs.useShellTools:
            from . import shell_tools
            shell_tools.register()

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
        if prefs.useSimpleIkTools:
            from . import simple_ik_tools
            simple_ik_tools.unregister()
        if prefs.useMhxTools:
            from . import mhx_tools
            mhx_tools.unregister()
        if prefs.useRigifyTools:
            from . import rigify_tools
            rigify_tools.unregister()
        if prefs.useRigTools:
            from . import rig_tools
            rig_tools.unregister()
        if prefs.usePoseTools:
            from . import pose_tools
            pose_tools.unregister()
        if prefs.useObjectTools:
            from . import object_tools
            object_tools.unregister()
        if prefs.useMaterialTools:
            from . import material_tools
            material_tools.unregister()
        if prefs.useMeshTools:
            from . import mesh_tools
            mesh_tools.unregister()
        if prefs.useMorphTools:
            from . import morph_tools
            morph_tools.unregister()
        if prefs.useHairTools:
            from . import hair_tools
            hair_tools.unregister()
        if prefs.useVisibilityTools:
            from . import visibility_tools
            visibility_tools.unregister()
        if prefs.useHDTools:
            from . import hd_tools
            hd_tools.unregister()
        if prefs.useSimulationTools:
            from . import simulation_tools
            simulation_tools.unregister()
        if prefs.useExportTools:
            from . import export_tools
            export_tools.unregister()
        if prefs.useShellTools:
            from . import shell_tools
            shell_tools.unregister()
    bpy.utils.unregister_class(DazPreferences)


if __name__ == "__main__":
    register()

print("DAZ loaded")
