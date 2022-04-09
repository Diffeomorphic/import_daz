# Copyright (c) 2016-2022, Thomas Larsson
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


import bpy
from mathutils import Vector, Euler, Matrix
from .error import *
from .utils import *
from .animation import ActionOptions
from .fileutils import SingleFile, TextFile, CsvFile

#------------------------------------------------------------------
#   Generic FACS importer
#------------------------------------------------------------------

class FACSImporter(SingleFile, ActionOptions):

    makeNewAction : BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName : StringProperty(
        name = "Action Name",
        description = "Name of loaded action",
        default = "Action")

    useHeadLoc : BoolProperty(
        name = "Head Location",
        description = "Include head location animation",
        default = False)

    useHeadRot : BoolProperty(
        name = "Head Rotation",
        description = "Include head rotation animation",
        default = True)

    headDist : FloatProperty(
        name = "Head",
        description = "Fraction of head rotation that affects head",
        min = 0.0, max = 1.0,
        default = 0.15)

    neckUpperDist : FloatProperty(
        name = "Upper Neck",
        description = "Fraction of head rotation that affects upper neck",
        min = 0.0, max = 1.0,
        default = 0.4)

    neckLowerDist : FloatProperty(
        name = "Lower Neck",
        description = "Fraction of head rotation that affects lower neck",
        min = 0.0, max = 1.0,
        default = 0.4)

    abdomenDist : FloatProperty(
        name = "Abdomen",
        description = "Fraction of head rotation that affects abdomen",
        min = 0.0, max = 1.0,
        default = 0.05)

    useEyesRot : BoolProperty(
        name = "Eyes Rotation",
        description = "Include eyes rotation animation",
        default = True)


    def draw(self, context):
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "useHeadLoc")
        self.layout.prop(self, "useHeadRot")
        if self.useHeadRot:
            box = self.layout.box()
            box.prop(self, "headDist")
            box.prop(self, "neckUpperDist")
            box.prop(self, "neckLowerDist")
            box.prop(self, "abdomenDist")
        self.layout.prop(self, "useEyesRot")


    def run(self, context):
        from .morphing import getRigFromObject
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No rig selected")
        self.facstable = dict((key.lower(), value) for key,value in self.FacsTable.items())
        self.bshapes = []
        self.bskeys = {}
        self.hlockeys = {}
        self.hrotkeys = {}
        self.leyekeys = {}
        self.reyekeys = {}
        self.parse()
        first = list(self.bskeys.values())[0]
        print("Blendshapes: %d\nKeys: %d" % (len(self.bshapes), len(first)))
        if self.makeNewAction and rig.animation_data:
            rig.animation_data.action = None
        self.build(rig)
        if self.makeNewAction and rig.animation_data:
            act = rig.animation_data.action
            if act:
                act.name = self.actionName


    def build(self, rig):
        missing = []
        for bshape in self.bshapes:
            if bshape not in self.facstable.keys():
                missing.append(bshape)
        if missing:
            msg = "Missing blendshapes:     \n"
            for bshape in missing:
                msg += ("  %s\n" % bshape)
            raise DazError(msg)

        self.setupBones(rig)
        self.scale = rig.DazScale
        warned = []
        for t in self.bskeys.keys():
            frame = self.getFrame(t)
            self.setBoneFrame(t, frame)
            for bshape,value in zip(self.bshapes,self.bskeys[t]):
                prop = self.facstable[bshape]
                if prop in rig.keys():
                    rig[prop] = value
                    rig.keyframe_insert(propRef(prop), frame=frame, group="FACS")
                elif bshape not in warned:
                    print("MISS", bshape, prop)
                    warned.append(bshape)


    def setupBones(self, rig):
        self.leye = self.getBones(["lEye", "eye.L"], rig)
        self.reye = self.getBones(["rEye", "eye.R"], rig)
        self.head = self.getBones(["head"], rig)
        self.neckUpper = self.getBones(["neckUpper", "neck-1"], rig)
        self.neckLower = self.getBones(["neckLower", "neck"], rig)
        self.abdomen = self.getBones(["abdomenUpper", "spine-1", "spine_fk.002"], rig)
        self.hip = self.getBones(["hip", "torso"], rig)
        if self.head is None:
            self.headDist = 0
        if self.neckUpper is None:
            self.neckUpperDist = 0
        if self.neckLower is None:
            self.neckLowerDist = 0
        if self.abdomen is None:
            self.abdomenDist = 0
        distsum = self.headDist + self.neckUpperDist + self.neckLowerDist + self.abdomenDist
        self.headDist /= distsum
        self.neckUpperDist /= distsum
        self.neckLowerDist /= distsum
        self.abdomenDist /= distsum


    def setBoneFrame(self, t, frame):
        if self.useHeadLoc:
            self.hip.location = self.scale*self.hlockeys[t]
            self.hip.keyframe_insert("location", frame=frame, group="hip")
        if self.useHeadRot:
            self.setRotation(self.head, self.hrotkeys[t], frame, self.headDist)
            self.setRotation(self.neckUpper, self.hrotkeys[t], frame, self.neckUpperDist)
            self.setRotation(self.neckLower, self.hrotkeys[t], frame, self.neckLowerDist)
            self.setRotation(self.abdomen, self.hrotkeys[t], frame, self.abdomenDist)
        if self.useEyesRot:
            self.setRotation(self.leye, self.leyekeys[t], frame)
            self.setRotation(self.reye, self.reyekeys[t], frame)


    def setRotation(self, pb, euler, frame, fraction=None):
        if fraction == 0 or pb is None:
            return
        elif fraction is not None:
            euler = Euler(fraction*Vector(euler))
        mat = euler.to_matrix()
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = mat.to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
        else:
            pb.rotation_euler = mat.to_euler(pb.rotation_mode)
            pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)


    def getBones(self, bnames, rig):
        for bname in bnames:
            pb = self.getBone(bname, rig)
            if pb:
                return pb
        print("Did not find bones: %s" % bnames)
        return None


    def getBone(self, bname, rig):
        if bname not in rig.pose.bones.keys():
            return None
        pb = rig.pose.bones[bname]
        msg = ("Bone %s is driven.\nMake bones poseable first first" % bname)
        if rig.animation_data:
            datapath = 'pose.bones["%s"].rotation_euler' % bname
            for fcu in rig.animation_data.drivers:
                if fcu.data_path == datapath:
                    raise DazError(msg)
        return pb

#------------------------------------------------------------------
#   FaceCap
#------------------------------------------------------------------

class ImportFaceCap(DazOperator, TextFile, IsMeshArmature, FACSImporter):
    bl_idname = "daz.import_facecap"
    bl_label = "Import FaceCap File"
    bl_description = "Import a text file with facecap data"
    bl_options = {'UNDO'}

    fps : FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in FaceCap file",
        min = 0,
        default = 24)

    FacsTable = {
        "browInnerUp" : "facs_ctrl_BrowInnerUp",
        "browDown_L" : "facs_BrowDownLeft",
        "browDown_R" : "facs_BrowDownRight",
        "browOuterUp_L" : "facs_BrowOuterUpLeft",
        "browOuterUp_R" : "facs_BrowOuterUpRight",
        "eyeLookUp_L" : "facs_jnt_EyeLookUpLeft",
        "eyeLookUp_R" : "facs_jnt_EyeLookUpRight",
        "eyeLookDown_L" : "facs_jnt_EyeLookDownLeft",
        "eyeLookDown_R" : "facs_jnt_EyeLookDownRight",
        "eyeLookIn_L" : "facs_bs_EyeLookInLeft_div2",
        "eyeLookIn_R" : "facs_bs_EyeLookInRight_div2",
        "eyeLookOut_L" : "facs_bs_EyeLookOutLeft_div2",
        "eyeLookOut_R" : "facs_bs_EyeLookOutRight_div2",
        "eyeBlink_L" : "facs_jnt_EyeBlinkLeft",
        "eyeBlink_R" : "facs_jnt_EyeBlinkRight",
        "eyeSquint_L" : "facs_bs_EyeSquintLeft_div2",
        "eyeSquint_R" : "facs_bs_EyeSquintRight_div2",
        "eyeWide_L" : "facs_jnt_EyesWideLeft",
        "eyeWide_R" : "facs_jnt_EyesWideRight",
        "cheekPuff" : "facs_ctrl_CheekPuff",
        "cheekSquint_L" : "facs_bs_CheekSquintLeft_div2",
        "cheekSquint_R" : "facs_bs_CheekSquintRight_div2",
        "noseSneer_L" : "facs_bs_NoseSneerLeft_div2",
        "noseSneer_R" : "facs_bs_NoseSneerRight_div2",
        "jawOpen" : "facs_jnt_JawOpen",
        "jawForward" : "facs_jnt_JawForward",
        "jawLeft" : "facs_jnt_JawLeft",
        "jawRight" : "facs_jnt_JawRight",
        "mouthFunnel" : "facs_bs_MouthFunnel_div2",
        "mouthPucker" : "facs_bs_MouthPucker_div2",
        "mouthLeft" : "facs_bs_MouthLeft_div2",
        "mouthRight" : "facs_bs_MouthRight_div2",
        "mouthRollUpper" : "facs_bs_MouthRollUpper_div2",
        "mouthRollLower" : "facs_bs_MouthRollLower_div2",
        "mouthShrugUpper" : "facs_bs_MouthShrugUpper_div2",
        "mouthShrugLower" : "facs_bs_MouthShrugLower_div2",
        "mouthClose" : "facs_bs_MouthClose_div2",
        "mouthSmile_L" : "facs_bs_MouthSmileLeft_div2",
        "mouthSmile_R" : "facs_bs_MouthSmileRight_div2",
        "mouthFrown_L" : "facs_bs_MouthFrownLeft_div2",
        "mouthFrown_R" : "facs_bs_MouthFrownRight_div2",
        "mouthDimple_L" : "facs_bs_MouthDimpleLeft_div2",
        "mouthDimple_R" : "facs_bs_MouthDimpleRight_div2",
        "mouthUpperUp_L" : "facs_bs_MouthUpperUpLeft_div2",
        "mouthUpperUp_R" : "facs_bs_MouthUpperUpRight_div2",
        "mouthLowerDown_L" : "facs_bs_MouthLowerDownLeft_div2",
        "mouthLowerDown_R" : "facs_bs_MouthLowerDownRight_div2",
        "mouthPress_L" : "facs_bs_MouthPressLeft_div2",
        "mouthPress_R" : "facs_bs_MouthPressRight_div2",
        "mouthStretch_L" : "facs_bs_MouthStretchLeft_div2",
        "mouthStretch_R" : "facs_bs_MouthStretchRight_div2",
        "tongueOut" : "facs_bs_TongueOut",
    }

    def draw(self, context):
        self.layout.prop(self, "fps")
        FACSImporter.draw(self, context)


    def getFrame(self, t):
        return self.fps * 1e-3 * t

    # timestamp in milli seconds (file says nano),
    # head position xyz,
    # head eulerAngles xyz,
    # left-eye eulerAngles xy,
    # right-eye eulerAngles xy,
    # blendshapes
    def parse(self):
        with open(self.filepath, "r") as fp:
            for line in fp:
                line = line.strip()
                if line[0:3] == "bs,":
                    self.bshapes = [bshape.lower() for bshape in line.split(",")[1:]]
                elif line[0:2] == "k,":
                    words = line.split(",")
                    t = int(words[1])
                    self.hlockeys[t] = Vector((float(words[2]), -float(words[3]), -float(words[4])))
                    self.hrotkeys[t] = Euler((D*float(words[5]), D*float(words[6]), D*float(words[7])))
                    self.leyekeys[t] = Euler((D*float(words[9]), 0.0, D*float(words[8])))
                    self.reyekeys[t] = Euler((D*float(words[11]), 0.0, D*float(words[10])))
                    self.bskeys[t] = [float(word) for word in words[12:]]
                elif line[0:5] == "info,":
                    pass
                else:
                    raise DazError("Illegal syntax:\%s     " % line)

#------------------------------------------------------------------
#   Unreal Live Link
#------------------------------------------------------------------

LiveLinkFacsTable = {
    "browInnerUp" : "facs_ctrl_BrowInnerUp",
    "browDownLeft" : "facs_BrowDownLeft",
    "browDownRight" : "facs_BrowDownRight",
    "browOuterUpLeft" : "facs_BrowOuterUpLeft",
    "browOuterUpRight" : "facs_BrowOuterUpRight",
    "eyeLookUpLeft" : "facs_jnt_EyeLookUpLeft",
    "eyeLookUpRight" : "facs_jnt_EyeLookUpRight",
    "eyeLookDownLeft" : "facs_jnt_EyeLookDownLeft",
    "eyeLookDownRight" : "facs_jnt_EyeLookDownRight",
    "eyeLookInLeft" : "facs_bs_EyeLookInLeft_div2",
    "eyeLookInRight" : "facs_bs_EyeLookInRight_div2",
    "eyeLookOutLeft" : "facs_bs_EyeLookOutLeft_div2",
    "eyeLookOutRight" : "facs_bs_EyeLookOutRight_div2",
    "eyeBlinkLeft" : "facs_jnt_EyeBlinkLeft",
    "eyeBlinkRight" : "facs_jnt_EyeBlinkRight",
    "eyeSquintLeft" : "facs_bs_EyeSquintLeft_div2",
    "eyeSquintRight" : "facs_bs_EyeSquintRight_div2",
    "eyeWideLeft" : "facs_jnt_EyesWideLeft",
    "eyeWideRight" : "facs_jnt_EyesWideRight",
    "cheekPuff" : "facs_ctrl_CheekPuff",
    "cheekSquintLeft" : "facs_bs_CheekSquintLeft_div2",
    "cheekSquintRight" : "facs_bs_CheekSquintRight_div2",
    "noseSneerLeft" : "facs_bs_NoseSneerLeft_div2",
    "noseSneerRight" : "facs_bs_NoseSneerRight_div2",
    "jawOpen" : "facs_jnt_JawOpen",
    "jawForward" : "facs_jnt_JawForward",
    "jawLeft" : "facs_jnt_JawLeft",
    "jawRight" : "facs_jnt_JawRight",
    "mouthFunnel" : "facs_bs_MouthFunnel_div2",
    "mouthPucker" : "facs_bs_MouthPucker_div2",
    "mouthLeft" : "facs_bs_MouthLeft_div2",
    "mouthRight" : "facs_bs_MouthRight_div2",
    "mouthRollUpper" : "facs_bs_MouthRollUpper_div2",
    "mouthRollLower" : "facs_bs_MouthRollLower_div2",
    "mouthShrugUpper" : "facs_bs_MouthShrugUpper_div2",
    "mouthShrugLower" : "facs_bs_MouthShrugLower_div2",
    "mouthClose" : "facs_bs_MouthClose_div2",
    "mouthSmileLeft" : "facs_bs_MouthSmileLeft_div2",
    "mouthSmileRight" : "facs_bs_MouthSmileRight_div2",
    "mouthFrownLeft" : "facs_bs_MouthFrownLeft_div2",
    "mouthFrownRight" : "facs_bs_MouthFrownRight_div2",
    "mouthDimpleLeft" : "facs_bs_MouthDimpleLeft_div2",
    "mouthDimpleRight" : "facs_bs_MouthDimpleRight_div2",
    "mouthUpperUpLeft" : "facs_bs_MouthUpperUpLeft_div2",
    "mouthUpperUpRight" : "facs_bs_MouthUpperUpRight_div2",
    "mouthLowerDownLeft" : "facs_bs_MouthLowerDownLeft_div2",
    "mouthLowerDownRight" : "facs_bs_MouthLowerDownRight_div2",
    "mouthPressLeft" : "facs_bs_MouthPressLeft_div2",
    "mouthPressRight" : "facs_bs_MouthPressRight_div2",
    "mouthStretchLeft" : "facs_bs_MouthStretchLeft_div2",
    "mouthStretchRight" : "facs_bs_MouthStretchRight_div2",
    "tongueOut" : "facs_bs_TongueOut",
}

class ImportLiveLink(DazOperator, CsvFile, IsMeshArmature, FACSImporter):
    bl_idname = "daz.import_livelink"
    bl_label = "Import Live Link File"
    bl_description = "Import a csv file with Unreal's Live Link data"
    bl_options = {'UNDO'}

    FacsTable = LiveLinkFacsTable

    def getFrame(self, t):
        return t+1

    def parse(self):
        from csv import reader
        with open(self.filepath, newline='') as fp:
            lines = list(reader(fp))
        if len(lines) < 2:
            raise DazError("Found no keyframes")

        self.bshapes = [bshape.lower() for bshape in lines[0][2:-9]]
        for t,line in enumerate(lines[1:]):
            nums = [float(word) for word in line[2:]]
            self.bskeys[t] = nums[0:-9]
            self.hlockeys[t] = Vector((0,0,0))
            yaw,pitch,roll = nums[-9:-6]
            self.hrotkeys[t] = Euler((-pitch, -yaw, roll))
            yaw,pitch,roll = nums[-6:-3]
            self.leyekeys[t] = Euler((yaw, roll, pitch))
            yaw,pitch,roll = nums[-3:]
            self.reyekeys[t] = Euler((yaw, roll, pitch))

        for key in self.bshapes:
            if key not in self.facstable.keys():
                print(key)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    ImportFaceCap,
    ImportLiveLink,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)