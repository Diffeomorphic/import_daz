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

class DAZ_OT_SavePosesToActions(DazPropsOperator, MorphGroup):
    bl_idname = "daz.save_poses_to_actions"
    bl_label = "Save Poses To Actions"
    bl_description = "Save the current scene poses as named actions"
    bl_options = {'UNDO'}

    prefix : StringProperty(
        name = "Action Prefix",
        description = "Action prefix",
        default = "Scene")

    useOverwrite : BoolProperty(
        name = "Overwrite",
        description = "Overwrite existing action with the same name",
        default = True)

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
        self.layout.prop(self, "prefix")
        self.layout.prop(self, "useOverwrite")
        self.layout.prop(self, "useArmature")
        self.layout.prop(self, "useMesh")
        self.layout.prop(self, "useEmpty")
        self.layout.prop(self, "useCamera")
        self.layout.prop(self, "useLight")


    def run(self, context):
        from .morphing import getActivated, keyProp
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
            self.insertKeys(ob, scn.frame_current)
            if ob.type == 'ARMATURE':
                rig = ob
                for pb in rig.pose.bones:
                    self.insertKeys(pb, scn.frame_current)
                morphs = self.getRelevantMorphs(scn, rig)
                for morph in morphs:
                    if getActivated(rig, rig, morph):
                        keyProp(rig, morph, scn.frame_current)
                updateRigDrivers(context, rig)
            self.saveAction(ob, "")

            if False and ob.type in ['CAMERA', 'LIGHT']:
                for key in dir(ob.data):
                    if key[0] != '_':
                        try:
                            ob.data.keyframe_insert(key, frame=scn.frame_current)
                        except TypeError:
                            pass
                self.saveAction(ob.data, ":%s" % ob.type[0:3])


    def saveAction(self, rna, infix):
        if rna.animation_data:
            act = rna.animation_data.action
            if act:
                aname = "%s%s:%s" % (self.prefix, infix, rna.name)
                if self.useOverwrite and aname in bpy.data.actions.keys():
                    for act2 in list(bpy.data.actions):
                        if act2.name.startswith(aname):
                            bpy.data.actions.remove(act2)
                act.name = aname
                act.use_fake_user = True
                rna.animation_data.action = None
                print("Saved %s" % act.name)


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


    def insertKeys(self, pb, frame):
        if isDrvBone(pb.name) or isFinal(pb.name):
            return
        if self.isFreeLoc(pb, "location"):
            pb.keyframe_insert("location", frame=frame, group=pb.name)
        if pb.rotation_mode == 'QUATERNION':
            if self.isFreeRot(pb, "rotation_quaternion"):
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
        else:
            if self.isFreeRot(pb, "rotation_euler"):
                pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)


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
        elif not self.isFree(pb, pb.lock_location, channel):
            return False
        for cns in pb.constraints:
            if cns.mute or cns.type[0:5] == 'LIMIT':
                pass
            else:
                return False
        return True


    def isFreeRot(self, pb, channel):
        if not self.isFree(pb, pb.lock_rotation, channel):
            return False
        for cns in pb.constraints:
            if cns.mute or cns.type[0:5] == 'LIMIT':
                pass
            elif cns.type == 'COPY_ROTATION' and cns.mix_mode == 'OFFSET':
                pass
            else:
                return False
        return True


def getActionPrefix(scn, context):
    ob = context.object
    enums = []
    taken = []
    for act in bpy.data.actions:
        words = act.name.split(":")
        prefix = words[0]
        if len(words) == 2 and prefix not in taken:
            enums.append((prefix, prefix, prefix))
            taken.append(prefix)
    enums.sort()
    if len(enums) == 0:
        enums = [("-", "No action found", "No action found")]
    return enums


class DAZ_OT_LoadPosesFromActions(DazPropsOperator):
    bl_idname = "daz.load_poses_from_actions"
    bl_label = "Load Poses From Actions"
    bl_description = "Load poses for all objects from named actions"
    bl_options = {'UNDO'}

    prefix : EnumProperty(
        items = getActionPrefix,
        name = "Action Prefix",
        description = "Action prefix")

    def draw(self, context):
        self.layout.prop(self, "prefix")

    def run(self, context):
        if self.prefix == "-":
            return
        self.objects = []
        for ob in getVisibleObjects(context):
            aname = "%s:%s" % (self.prefix, ob.name)
            self.loadAction(ob, aname)
            if ob.type in ['CAMERA', 'LIGHT']:
                aname = "%s:%s:%s" % (self.prefix, ob.type[0:3], ob.name)
                self.loadAction(ob.data, aname)
        updateScene(context)
        for rna in self.objects:
            rna.animation_data.action = None


    def loadAction(self, rna, aname):
        act = bpy.data.actions.get(aname)
        if act:
            print("Loaded %s" % act.name)
            rna.animation_data.action = act
            self.objects.append(rna)

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosesToActions,
    DAZ_OT_LoadPosesFromActions,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)