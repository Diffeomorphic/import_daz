# Copyright (c) 2016-2021, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
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


import os
import bpy
from .utils import *
from .error import *
from .morphing import MorphGroup

#------------------------------------------------------------------
#   Save and Load pose to action
#------------------------------------------------------------------

class DAZ_OT_SavePosesToFile(DazPropsOperator, MorphGroup):
    bl_idname = "daz.save_poses_to_file"
    bl_label = "Save Poses To File"
    bl_description = "Save the current scene poses as a json file"
    bl_options = {'UNDO'}

    name : StringProperty(
        name = "Scene Name",
        description = "Name of the file to save the scene in",
        default = "scene")

    useOverwrite : BoolProperty(
        name = "Overwrite",
        description = "Overwrite existing action with the same name",
        default = False)

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

    useCamera : BoolProperty(
        name = "Cameras",
        description = "Save action for cameras",
        default = True)

    useLight : BoolProperty(
        name = "Lights",
        description = "Save action for lights",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "name")
        self.layout.prop(self, "useOverwrite")
        self.layout.prop(self, "useArmature")
        self.layout.prop(self, "useMesh")
        self.layout.prop(self, "useEmpty")
        self.layout.prop(self, "useCamera")
        self.layout.prop(self, "useLight")


    def run(self, context):
        from .morphing import getActivated, keyProp
        if not bpy.data.filepath:
            raise DazError("Save the blend file first")
        struct = {}
        scn = context.scene
        self.exclude = []
        for rig in getVisibleArmatures(context):
            self.excludeChildren(rig)
        for ob in getVisibleObjects(context):
            if ob in self.exclude:
                continue
            if not ((ob.type == 'ARMATURE' and self.useArmature) or
                    (ob.type == 'MESH' and self.useMesh) or
                    (ob.type == 'EMPTY' and self.useEmpty) or
                    (ob.type == 'CAMERA' and self.useCamera) or
                    (ob.type == 'LIGHT' and self.useLight)):
                continue
            self.setupDriven(ob)
            ostruct = self.saveTransform(ob, struct)
            dstruct = ostruct["data"] = {}
            if ob.type == 'ARMATURE':
                rig = ob
                amt = ob.data
                ostruct["layers"] = amt.layers
                ostruct["layers_protected"] = amt.layers_protected
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

        from .load_json import saveJson
        folder = os.path.join(os.path.dirname(bpy.data.filepath), "scenes")
        if not os.path.exists(folder):
            os.makedirs(folder)
        path = os.path.join(folder, "%s.json" % self.name)
        if os.path.exists(path) and not self.useOverwrite:
            raise DazError("File already exists:\n%s" % path)
        saveJson(struct, path)


    def excludeChildren(self, ob):
        for child in ob.children:
            self.exclude.append(child)
            self.excludeChildren(child)


    def setupDriven(self, rig):
        self.driven = {}
        if rig.animation_data is None:
            return
        for fcu in rig.animation_data.drivers:
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[":
                bname = words[1]
                if not (isDrvBone(bname) or isFinal(bname)):
                    channel = fcu.data_path.split(".")[-1]
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


class DAZ_OT_LoadPosesFromFile(DazPropsOperator):
    bl_idname = "daz.load_poses_from_file"
    bl_label = "Load Poses From File"
    bl_description = "Load poses for all objects from json file"
    bl_options = {'UNDO'}

    file : EnumProperty(
        items = getSceneFile,
        name = "File",
        description = "Name of the file containing the scene")

    def draw(self, context):
        self.layout.prop(self, "file")

    def run(self, context):
        if self.file == "-":
            return
        from .load_json import loadJson
        struct = loadJson(self.file)
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
                rig.data.layers = ostruct["layers"]
                rig.data.layers_protected = ostruct["layers_protected"]
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
                            elif isinstance(value0, int):
                                value = int(value)
                        rig[prop] = value


    def setTransform(self, pb, struct):
        for key in ["location", "rotation_quaternion", "rotation_euler", "scale"]:
            value = struct.get(key)
            if value is not None:
                setattr(pb, key, value)

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosesToFile,
    DAZ_OT_LoadPosesFromFile,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)