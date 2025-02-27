# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import DazPropOperator
from .facsbase import FACSImporter, FACSCopier

#------------------------------------------------------------------
#   FBX
#------------------------------------------------------------------

class DAZ_OT_ImportFbxFacs(FACSImporter, DazPropOperator, FACSCopier):
    bl_idname = "daz.import_fbx_facs"
    bl_label = "Import FACS From FBX File"
    bl_description = "Import a fbx file with FACS animation"
    bl_options = {'UNDO'}

    filename_ext = ".fbx"
    filter_glob : StringProperty(default="*.fbx", options={'HIDDEN'})

    def parse(self, context):
        from .load import deleteObjects
        print("Importing FBX file")
        existing_objects = set(context.scene.objects)
        try:
            bpy.ops.import_scene.fbx(
                filepath = self.filepath,
                automatic_bone_orientation=True,
                ignore_leaf_bones=True)
        except AttributeError:
            raise MocapError("Blender's built-in FBX importer must be enabled")
        imported_objects = set(context.scene.objects) - existing_objects
        print("Temporary FBX objects imported: %s" % imported_objects)
        actions = []
        for ob in imported_objects:
            if ob and ob.animation_data:
                act = ob.animation_data.action
                if act:
                    actions.append(act)
            if ob.type == 'MESH':
                skeys = ob.data.shape_keys
                if skeys and skeys.animation_data:
                    act = skeys.animation_data.action
                    if act:
                        act.name = "%s Shapes" % ob.name
                        print("FBX MESH:", ob.name, skeys.name, act.name)
                        actions.append(act)
                        self.getFcurves(act)
        print("Deleting temporary FBX objects")
        for act in actions:
            bpy.data.actions.remove(act)
        deleteObjects(context, imported_objects)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportFbxFacs)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportFbxFacs)