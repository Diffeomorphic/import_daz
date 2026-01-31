# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..fileutils import SingleFile
from .facsbase import FACSImporter, FACSCopier

#------------------------------------------------------------------
#   FBX
#------------------------------------------------------------------

class DAZ_OT_ImportFbxFacs(FACSImporter, FACSCopier, SingleFile, DazOperator):
    bl_idname = "daz.import_fbx_facs"
    bl_label = "Import FACS From FBX File"
    bl_description = "Import a fbx file with FACS animation.\nThe FBX format add-on must be enabled."
    bl_options = {'UNDO'}

    filename_ext = ".fbx"
    filter_glob : StringProperty(default="*.fbx", options={'HIDDEN'})

    def parse(self, context):
        print("Importing FBX file")
        existing_objects = set(context.scene.objects)
        try:
            bpy.ops.import_scene.fbx(
                filepath = self.filepath,
                automatic_bone_orientation=True,
                ignore_leaf_bones=True)
        except AttributeError:
            raise DazError("Blender's built-in FBX importer must be enabled")
        except RuntimeError as err:
            raise DazError("Error when importing FBX file:\n%s       " % err)
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

#-------------------------------------------------------------
#   Delete objects
#-------------------------------------------------------------

def deleteObjects(context, objects):
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
    except RuntimeError:
        return
    for ob in objects:
        if ob:
            dtype = ob.type
            if ob.data:
                data = ob.data
                users = ob.data.users
            else:
                users = 0
            for coll in bpy.data.collections:
                if ob in coll.objects.values():
                    coll.objects.unlink(ob)
            bpy.data.objects.remove(ob)
            if users == 1:
                if dtype == 'MESH':
                    bpy.data.meshes.remove(data)
                elif dtype == 'ARMATURE':
                    bpy.data.armatures.remove(data)
                elif dtype == 'CURVES':
                    bpy.data.curves.remove(data)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportFbxFacs)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportFbxFacs)