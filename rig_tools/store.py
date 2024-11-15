#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
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

import os
import bpy
from ..utils import *
from ..error import *
from ..selector import MorphGroup, getActivated, keyProp
from ..fileutils import SingleFile, JsonFile
from ..load_json import loadJson, saveJson

#------------------------------------------------------------------
#   Pose collector
#------------------------------------------------------------------

class PoseCollector:
    useArmature : BoolProperty(
        name = "Armatures",
        description = "Save action for armatures",
        default = True)

    useMesh : BoolProperty(
        name = "Meshes",
        description = "Save action for meshes",
        default = False)

    useEmpty : BoolProperty(
        name = "Empties",
        description = "Save action for empties",
        default = True)

    useCurves : BoolProperty(
        name = "Curves",
        description = "Save action for curves",
        default = True)

    useCamera : BoolProperty(
        name = "Cameras",
        description = "Save action for cameras",
        default = True)

    useLight : BoolProperty(
        name = "Lights",
        description = "Save action for lights",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useArmature")
        self.layout.prop(self, "useMesh")
        self.layout.prop(self, "useEmpty")
        self.layout.prop(self, "useCurves")
        self.layout.prop(self, "useCamera")
        self.layout.prop(self, "useLight")


    def collectData(self, context):
        struct = {}
        scn = context.scene
        self.exclude = []
        for rig in getVisibleArmatures(context):
            self.excludeChildren(rig)
        self.exclude = []
        for ob in getVisibleObjects(context):
            if ob in self.exclude:
                continue
            if not ((ob.type == 'ARMATURE' and self.useArmature) or
                    (ob.type == 'MESH' and self.useMesh) or
                    (ob.type == 'EMPTY' and self.useEmpty) or
                    (ob.type == 'CURVES' and self.useCurves) or
                    (ob.type == 'CAMERA' and self.useCamera) or
                    (ob.type == 'LIGHT' and self.useLight)):
                print("SKIP", ob.name, ob.type)
                continue
            self.setupDriven(ob)
            ostruct = self.saveTransform(ob, struct)
            dstruct = ostruct["data"] = {}
            if ob.type == 'ARMATURE':
                rig = ob
                amt = ob.data
                if BLENDER3:
                    ostruct["layers"] = amt.layers
                    ostruct["layers_protected"] = amt.layers_protected
                else:
                    ostruct["collections"] = [coll.name for coll in amt.collections if coll.is_visible]
                pstruct = ostruct["pose"] = {}
                for pb in rig.pose.bones:
                    self.saveTransform(pb, pstruct)
                morphs = self.getRelevantMorphs(scn, rig)
                mstruct = ostruct["morphs"] = {}
                for morph in morphs:
                    if getActivated(rig, rig, morph):
                        mstruct[morph] = rig[morph]
                for key,value in amt.items():
                    if (key[0:3] in ["Mha"] and
                        key[3:9] not in ["ToeTar", "ArmStr", "LegStr"]):
                        self.addValue(dstruct, key, value)

            if ob.type in ['CAMERA', 'LIGHT']:
                for key in dir(ob.data):
                    if key[0] != '_':
                        value = getattr(ob.data, key)
                        self.addValue(dstruct, key, value)
        return struct


    def excludeChildren(self, ob):
        for child in ob.children:
            self.exclude.append(child)
            self.excludeChildren(child)


    def setupDriven(self, rig):
        self.driven = {}
        if rig.animation_data is None:
            return
        for fcu in rig.animation_data.drivers:
            bname,channel = getBoneChannel(fcu)
            if bname and not isDrvBone(bname):
                self.setChannel(bname, channel, fcu.array_index)


    def setChannel(self, bname, channel, idx):
        if channel not in ["location", "rotation_quaternion", "rotation_euler", "scale"]:
            return
        if bname not in self.driven.keys():
            self.driven[bname] = {
                "location" : [False,False,False],
                "rotation_quaternion" : [False,False,False,False],
                "rotation_euler" : [False,False,False],
                "scale" : [False,False,False],
            }
        self.driven[bname][channel][idx] = True


    def saveTransform(self, pb, struct):
        if isDrvBone(pb.name) or isFinal(pb.name):
            return
        ostruct = struct[pb.name] = {}
        if self.isFreeLoc(pb, "location"):
            ostruct["location"] = tuple(pb.location)
        if pb.rotation_mode == 'QUATERNION':
            if self.isFree(pb, pb.lock_rotation, "rotation_quaternion"):
                ostruct["rotation_quaternion"] = tuple(pb.rotation_quaternion)
        else:
            if self.isFree(pb, pb.lock_rotation, "rotation_euler"):
                ostruct["rotation_euler"] = tuple(pb.rotation_euler)
        if self.isFree(pb, pb.lock_scale, "scale"):
            ostruct["scale"] = tuple(pb.scale)
        return ostruct


    def isFree(self, pb, locks, channel):
        if (locks[0] and locks[1] and locks[2]):
            return False
        drvbone = self.driven.get(pb.name)
        if drvbone:
            drv = drvbone[channel]
            if (drv[0] and drv[1] and drv[2]):
                return False
        return True


    def isFreeLoc(self, pb, channel):
        if isinstance(pb, bpy.types.PoseBone) and pb.bone.use_connect:
            return False
        else:
            return self.isFree(pb, pb.lock_location, channel)


    def addValue(self, struct, key, value):
        if (isinstance(value, int) or
            isinstance(value, float) or
            isinstance(value, bool) or
            isinstance(value, str)):
            struct[key] = value

#------------------------------------------------------------------
#   Pose collector
#------------------------------------------------------------------

class DAZ_OT_SavePosesToFile(DazOperator, PoseCollector, SingleFile, JsonFile, MorphGroup):
    bl_idname = "daz.save_poses_to_file"
    bl_label = "Save Poses To File"
    bl_description = "Save the current scene poses as a json file"
    bl_options = {'UNDO'}

    def run(self, context):
        struct = self.collectData(context)
        file = os.path.splitext(self.filepath)[0]
        filepath = normalizePath("%s.json" % file)
        saveJson(struct, filepath)
        print("%s saved" % filepath)

'''
def getSceneFile(scn, context):
    folder = os.path.join(os.path.dirname(bpy.data.filepath), "scenes")
    enums = []
    if os.path.exists(folder):
        for file in os.listdir(folder):
            words = os.path.splitext(file)
            if words[-1] == ".json":
                path = os.path.join(folder, file)
                enums.append((path, words[0], "Path to file"))
        enums.sort()
    if len(enums) == 0:
        enums = [("-", "No action found", "No action found")]
    return enums
'''
#------------------------------------------------------------------
#   Pose Setter
#------------------------------------------------------------------

class PoseSetter:
    def setPoses(self, context, struct):
        for oname,ostruct in struct.items():
            ob = bpy.data.objects.get(oname)
            if ob is None:
                print("Missing object", oname)
                continue
            print("Load", ob.name)
            self.setTransform(ob, ostruct)
            data = ostruct.get("data")
            if data:
                for key,value in data.items():
                    try:
                        setattr(ob.data, key, value)
                    except AttributeError:
                        pass
                    except TypeError:
                        pass
            if ob.type == 'ARMATURE':
                rig = ob
                if BLENDER3:
                    if "layers" in ostruct.keys():
                        rig.layers = ostruct["layers"]
                        rig.data.layers_protected = ostruct["layers_protected"]
                elif "collections" in ostruct.keys():
                    for coll in rig.data.collections:
                        coll.is_visible = False
                    for cname in ostruct["collections"]:
                        coll = rig.data.collections.get(cname)
                        if coll:
                            coll.is_visible = True
                pose = ostruct.get("pose")
                if pose:
                    for bname,bstruct in pose.items():
                        pb = rig.pose.bones.get(bname)
                        self.setTransform(pb, bstruct)
                morphs = ostruct.get("morphs")
                if morphs:
                    for prop,value in morphs.items():
                        if prop in rig.keys():
                            value0 = rig[prop]
                            if isinstance(value0, float):
                                value = float(value)
                            elif isinstance(value0, bool):
                                value = bool(value)
                            elif isinstance(value0, int):
                                value = int(value)
                        rig[prop] = value
                        if self.auto:
                            rig.keyframe_insert(propRef(prop))


    def setTransform(self, pb, struct):
        for key in ["location", "rotation_quaternion", "rotation_euler", "scale"]:
            value = struct.get(key)
            if value is not None:
                setattr(pb, key, value)
                if self.auto:
                    try:
                        pb.keyframe_insert(key)
                    except RuntimeError:
                        pass

#------------------------------------------------------------------
#   Load poses from file
#------------------------------------------------------------------

class DAZ_OT_LoadPosesFromFile(DazOperator, PoseSetter, SingleFile, JsonFile):
    bl_idname = "daz.load_poses_from_file"
    bl_label = "Load Poses From File"
    bl_description = "Load poses for all objects from json file"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(context.scene.tool_settings, "use_keyframe_insert_auto")

    def run(self, context):
        self.auto = context.scene.tool_settings.use_keyframe_insert_auto
        struct = loadJson(self.filepath)
        self.setPoses(context, struct)

#-------------------------------------------------------------
#   Key all poses
#-------------------------------------------------------------

class DAZ_OT_KeyAllPoses(DazOperator, PoseCollector, PoseSetter, MorphGroup):
    bl_idname = "daz.key_all_poses"
    bl_label = "Key All Poses"
    bl_description = "Insert keys for all objects at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        self.auto = True
        struct = self.collectData(context)
        self.setPoses(context, struct)

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosesToFile,
    DAZ_OT_LoadPosesFromFile,
    DAZ_OT_KeyAllPoses,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)