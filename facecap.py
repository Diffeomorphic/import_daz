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

    useShapekeys : BoolProperty(
        name = "Load To Shapekeys",
        description = "Load morphs to mesh shapekeys instead of rig properties",
        default = False)

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

    useEyes : BoolProperty(
        name = "Eyes",
        description = "Include eyes animation",
        default = True)

    useTongue : BoolProperty(
        name = "Tongue",
        description = "Include tongue animation",
        default = True)


    def draw(self, context):
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "useShapekeys")
        self.layout.separator()
        self.layout.prop(self, "useHeadLoc")
        self.layout.prop(self, "useHeadRot")
        if self.useHeadRot:
            box = self.layout.box()
            box.prop(self, "headDist")
            box.prop(self, "neckUpperDist")
            box.prop(self, "neckLowerDist")
            box.prop(self, "abdomenDist")
        self.layout.prop(self, "useEyes")
        self.layout.prop(self, "useTongue")


    def run(self, context):
        from .morphing import getRigFromObject
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No rig selected")
        if "MhaGaze_L" in rig.data.keys():
            rig.data["MhaGaze_L"] = rig.data["MhaGaze_R"] = 0.0
        self.facstable = dict((key.lower(), value) for key,value in self.FacsTable.items())
        self.bshapes = []
        self.bskeys = {}
        self.hlockeys = {}
        self.hrotkeys = {}
        self.leyekeys = {}
        self.reyekeys = {}
        self.shapekeys = {}
        if self.useShapekeys:
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    for skey in ob.data.shape_keys.key_blocks:
                        self.shapekeys[skey.name] = True
        self.parse()
        first = list(self.bskeys.values())[0]
        print("Blendshapes: %d\nKeys: %d" % (len(self.bshapes), len(first)))
        if self.makeNewAction and rig.animation_data:
            rig.animation_data.action = None
        if self.makeNewAction and self.useShapekeys:
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys and ob.data.shape_keys.animation_data:
                    ob.data.shape_keys.animation_data.action = None
        self.build(rig, context)
        if self.makeNewAction and rig.animation_data:
            act = rig.animation_data.action
            if act:
                act.name = self.actionName


    def build(self, rig, context):
        def isMatch(string, bases):
            for base in bases:
                if string in base:
                    return True
            return False

        missing = []
        for bshape in self.bshapes:
            if bshape not in self.facstable.keys():
                missing.append(bshape)
        if missing:
            msg = "Missing blendshapes:     \n"
            for bshape in missing:
                msg += ("  %s\n" % bshape)
            raise DazError(msg)

        from time import perf_counter
        self.setupBones(rig)
        self.facsShapes = self.setupFacsProps(self.shapekeys.keys())
        self.facsProps = self.setupFacsProps(rig.keys())
        missingShapes = {}
        self.scale = rig.DazScale
        warned = []
        nframes = len(self.bskeys)
        t1 = perf_counter()
        for n,t in enumerate(self.bskeys.keys()):
            frame = self.getFrame(t)
            self.setBoneFrame(t, frame, context)
            for bshape,value in zip(self.bshapes,self.bskeys[t]):
                prop = self.facsShapes.get(bshape)
                if prop:
                    for ob in rig.children:
                        if ob.type == 'MESH' and ob.data.shape_keys:
                            if prop in ob.data.shape_keys.key_blocks.keys():
                                skey = ob.data.shape_keys.key_blocks[prop]
                                skey.value = value
                                skey.keyframe_insert("value", frame=frame)
                            else:
                                if ob.name not in missingShapes.keys():
                                    missingShapes[ob.name] = {}
                                missingShapes[ob.name][prop] = True
                    continue

                prop = self.facsProps.get(bshape)
                if prop:
                    rig[prop] = value
                    rig.keyframe_insert(propRef(prop), frame=frame, group="FACS")
                    continue

                if bshape not in warned:
                    print("MISS", bshape, prop)
                    warned.append(bshape)
        t2 = perf_counter()
        print("%d frames loaded in %g seconds" % (nframes, t2-t1))
        if missingShapes:
            msg = "The following objects are missing shapekeys:\n"
            for obname in missingShapes.keys():
                msg += "  %s\n" % obname
            raise DazError(msg, warning=True)


    def setupFacsProps(self, props):
        def loopTable(bases, props):
            if isinstance(bases, str):
                bases = [bases]
            for prefix in ["", "facs_", "facs_ctrl_", "facs_jnt_", "facs_bs_"]:
                for suffix in ["", "_div2"]:
                    for base in bases:
                        prop = "%s%s%s" % (prefix, base, suffix)
                        if prop in props:
                            return prop
            return None

        table = {}
        for bshape,bases in self.facstable.items():
            if (not self.useEyes and "eye" in bshape or
                not self.useTongue and "tongue" in bshape):
                continue
            table[bshape] = loopTable(bases, props)
        return table


    def setupBones(self, rig):
        self.leye = self.getBones(["lEye", "l_eye", "eye.L"], rig)
        self.reye = self.getBones(["rEye", "r_eye", "eye.R"], rig)
        self.head = self.getBones(["head"], rig)
        self.neckUpper = self.getBones(["neckUpper", "neck2", "neck-1"], rig)
        self.neckLower = self.getBones(["neckLower", "neck1", "neck"], rig)
        self.abdomen = self.getBones(["abdomenUpper", "spine2", "spine-1", "spine_fk.002"], rig)
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


    def setBoneFrame(self, t, frame, context):
        if self.useHeadLoc:
            self.hip.location = self.scale*self.hlockeys[t]
            self.hip.keyframe_insert("location", frame=frame, group="hip")
        if self.useHeadRot:
            self.setRotation(self.head, self.hrotkeys[t], frame, self.headDist)
            self.setRotation(self.neckUpper, self.hrotkeys[t], frame, self.neckUpperDist)
            self.setRotation(self.neckLower, self.hrotkeys[t], frame, self.neckLowerDist)
            self.setRotation(self.abdomen, self.hrotkeys[t], frame, self.abdomenDist)
        if self.useEyes:
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
        def getBone(bname, rig):
            if bname not in rig.pose.bones.keys():
                return None
            pb = rig.pose.bones[bname]
            if rig.animation_data and not self.useShapekeys:
                msg = ("Bone %s is driven.\nMake bones posable first" % bname)
                datapath = 'pose.bones["%s"].rotation_euler' % bname
                for fcu in rig.animation_data.drivers:
                    if fcu.data_path == datapath:
                        raise DazError(msg)
            return pb

        for bname in bnames:
            pb = getBone(bname, rig)
            if pb:
                return pb
        print("Did not find bones: %s" % bnames)
        return None

#------------------------------------------------------------------
#   FaceCap
#------------------------------------------------------------------

class ImportFaceCap(FACSImporter, DazOperator, TextFile, IsMeshArmature):
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
        "browInnerUp" : "BrowInnerUp",
        "browDown_L" : "BrowDownLeft",
        "browDown_R" : "BrowDownRight",
        "browOuterUp_L" : "BrowOuterUpLeft",
        "browOuterUp_R" : "BrowOuterUpRight",
        "eyeLookUp_L" : "EyeLookUpLeft",
        "eyeLookUp_R" : "EyeLookUpRight",
        "eyeLookDown_L" : "EyeLookDownLeft",
        "eyeLookDown_R" : "EyeLookDownRight",
        "eyeLookIn_L" : "EyeLookInLeft",
        "eyeLookIn_R" : "EyeLookInRight",
        "eyeLookOut_L" : "EyeLookOutLeft",
        "eyeLookOut_R" : "EyeLookOutRight",
        "eyeBlink_L" : "EyeBlinkLeft",
        "eyeBlink_R" : "EyeBlinkRight",
        "eyeSquint_L" : "EyeSquintLeft",
        "eyeSquint_R" : "EyeSquintRight",
        "eyeWide_L" : ("EyesWideLeft", "EyeWideLeft"),
        "eyeWide_R" : ("EyesWideRight", "EyeWideRight"),
        "cheekPuff" : "CheekPuff",
        "cheekSquint_L" : "CheekSquintLeft",
        "cheekSquint_R" : "CheekSquintRight",
        "noseSneer_L" : "NoseSneerLeft",
        "noseSneer_R" : "NoseSneerRight",
        "jawOpen" : "JawOpen",
        "jawForward" : "JawForward",
        "jawLeft" : "JawLeft",
        "jawRight" : "JawRight",
        "mouthFunnel" : "MouthFunnel",
        "mouthPucker" : "MouthPucker",
        "mouthLeft" : "MouthLeft",
        "mouthRight" : "MouthRight",
        "mouthRollUpper" : "MouthRollUpper",
        "mouthRollLower" : "MouthRollLower",
        "mouthShrugUpper" : "MouthShrugUpper",
        "mouthShrugLower" : "MouthShrugLower",
        "mouthClose" : "MouthClose",
        "mouthSmile_L" : "MouthSmileLeft",
        "mouthSmile_R" : "MouthSmileRight",
        "mouthFrown_L" : "MouthFrownLeft",
        "mouthFrown_R" : "MouthFrownRight",
        "mouthDimple_L" : "MouthDimpleLeft",
        "mouthDimple_R" : "MouthDimpleRight",
        "mouthUpperUp_L" : "MouthUpperUpLeft",
        "mouthUpperUp_R" : "MouthUpperUpRight",
        "mouthLowerDown_L" : "MouthLowerDownLeft",
        "mouthLowerDown_R" : "MouthLowerDownRight",
        "mouthPress_L" : "MouthPressLeft",
        "mouthPress_R" : "MouthPressRight",
        "mouthStretch_L" : "MouthStretchLeft",
        "mouthStretch_R" : "MouthStretchRight",
        "tongueOut" : "TongueOut",
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
        with open(self.filepath, "r", encoding="utf-8-sig") as fp:
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
    "browInnerUp" : "BrowInnerUp",
    "browDownLeft" : "BrowDownLeft",
    "browDownRight" : "BrowDownRight",
    "browOuterUpLeft" : "BrowOuterUpLeft",
    "browOuterUpRight" : "BrowOuterUpRight",
    "eyeLookUpLeft" : "EyeLookUpLeft",
    "eyeLookUpRight" : "EyeLookUpRight",
    "eyeLookDownLeft" : "EyeLookDownLeft",
    "eyeLookDownRight" : "EyeLookDownRight",
    "eyeLookInLeft" : "EyeLookInLeft",
    "eyeLookInRight" : "EyeLookInRight",
    "eyeLookOutLeft" : "EyeLookOutLeft",
    "eyeLookOutRight" : "EyeLookOutRight",
    "eyeBlinkLeft" : "EyeBlinkLeft",
    "eyeBlinkRight" : "EyeBlinkRight",
    "eyeSquintLeft" : "EyeSquintLeft",
    "eyeSquintRight" : "EyeSquintRight",
    "eyeWideLeft" : ("EyesWideLeft", "EyeWideLeft"),
    "eyeWideRight" : ("EyesWideRight", "EyeWideRight"),
    "cheekPuff" : "CheekPuff",
    "cheekSquintLeft" : "CheekSquintLeft",
    "cheekSquintRight" : "CheekSquintRight",
    "noseSneerLeft" : "NoseSneerLeft",
    "noseSneerRight" : "NoseSneerRight",
    "jawOpen" : "JawOpen",
    "jawForward" : "JawForward",
    "jawLeft" : "JawLeft",
    "jawRight" : "JawRight",
    "mouthFunnel" : "MouthFunnel",
    "mouthPucker" : "MouthPucker",
    "mouthLeft" : "MouthLeft",
    "mouthRight" : "MouthRight",
    "mouthRollUpper" : "MouthRollUpper",
    "mouthRollLower" : "MouthRollLower",
    "mouthShrugUpper" : "MouthShrugUpper",
    "mouthShrugLower" : "MouthShrugLower",
    "mouthClose" : "MouthClose",
    "mouthSmileLeft" : "MouthSmileLeft",
    "mouthSmileRight" : "MouthSmileRight",
    "mouthFrownLeft" : "MouthFrownLeft",
    "mouthFrownRight" : "MouthFrownRight",
    "mouthDimpleLeft" : "MouthDimpleLeft",
    "mouthDimpleRight" : "MouthDimpleRight",
    "mouthUpperUpLeft" : "MouthUpperUpLeft",
    "mouthUpperUpRight" : "MouthUpperUpRight",
    "mouthLowerDownLeft" : "MouthLowerDownLeft",
    "mouthLowerDownRight" : "MouthLowerDownRight",
    "mouthPressLeft" : "MouthPressLeft",
    "mouthPressRight" : "MouthPressRight",
    "mouthStretchLeft" : "MouthStretchLeft",
    "mouthStretchRight" : "MouthStretchRight",
    "tongueOut" : "TongueOut",
}

class ImportLiveLink(FACSImporter, DazOperator, CsvFile, IsMeshArmature):
    bl_idname = "daz.import_livelink"
    bl_label = "Import Live Link File"
    bl_description = "Import a csv file with Unreal's Live Link data"
    bl_options = {'UNDO'}

    FacsTable = LiveLinkFacsTable

    def getFrame(self, t):
        return t+1

    def parse(self):
        from csv import reader
        with open(self.filepath, newline='', encoding="utf-8-sig") as fp:
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

#------------------------------------------------------------------
#   Gaze transfer
#------------------------------------------------------------------

class GazeTransferer:
    @classmethod
    def poll(self, context):
        rig = context.object
        return (rig and rig.type == 'ARMATURE' and
                "gaze" in rig.pose.bones.keys() and
                "gaze.L" in rig.pose.bones.keys() and
                "gaze.R" in rig.pose.bones.keys())


    def storeState(self, context):
        rig = context.object
        self.layers = list(rig.data.layers)
        rig.data.layers = 32*[True]


    def restoreState(self, context):
        rig = context.object
        rig.data.layers = self.layers


    def setupBones(self, rig):
        self.leye = self.getBones(["lEye", "eye.L"], rig)
        self.reye = self.getBones(["rEye", "eye.R"], rig)
        self.gaze = rig.pose.bones["gaze"]
        self.lgaze = rig.pose.bones["gaze.L"]
        self.rgaze = rig.pose.bones["gaze.R"]
        self.FZ = Matrix.Rotation(math.pi, 4, 'Z')
        self.gazedist = (self.lgaze.bone.head_local - self.leye.bone.head_local).length


    def getFrames(self, rig, scn, bnames):
        fstruct = {}
        if rig.animation_data and rig.animation_data.action:
            act = rig.animation_data.action
            for fcu in act.fcurves:
                words = fcu.data_path.split('"')
                if words[0] == "pose.bones[" and words[1] in bnames:
                    for kp in fcu.keyframe_points:
                        t = kp.co[0]
                        fstruct[t] = True
        if len(fstruct) > 0:
            try:
                scn.frame_current = fstruct.keys()[0]
                useInts = False
            except TypeError:
                useInts = True
            if useInts:
                fstruct = dict([(int(frame),True) for frame in fstruct.keys()])
            frames = list(fstruct.keys())
            frames.sort()
            return frames
        else:
            return [None]


class TransferToGaze(DazOperator, GazeTransferer):
    bl_idname = "daz.transfer_to_gaze"
    bl_label = "Transfer Eye To Gaze"
    bl_description = "Transfer eye bone animation to gaze bones"
    bl_options = {'UNDO'}

    def run(self, context):
        t1 = perf_counter()
        rig = context.object
        scn = context.scene
        self.setupBones(rig)
        rig.data["MhaGaze_L"] = rig.data["MhaGaze_R"] = 0.0
        frames = self.getFrames(rig, scn, ["eye.L", "eye.R", "lEye", "rEye"])
        for frame in frames:
            if frame is not None:
                scn.frame_current = frame
            updateScene(context)
            lmat = self.getGaze(self.leye)
            rmat = self.getGaze(self.reye)
            mat = 0.5*(lmat + rmat)
            self.setMatrix(self.gaze, mat, frame)
            updateScene(context)
            self.setMatrix(self.lgaze, lmat, frame)
            self.setMatrix(self.rgaze, rmat, frame)
        rig.data["MhaGaze_L"] = rig.data["MhaGaze_R"] = 1.0
        updateScene(context)
        t2 = perf_counter()
        print("%d frames converted in %g seconds" % (len(frames), t2-t1))


    def getGaze(self, eye):
        loc = eye.matrix.to_translation()
        vec = eye.matrix.to_quaternion().to_matrix().col[1]
        vec.normalize()
        mat = eye.matrix @ self.FZ
        mat.col[3][0:3] = loc + vec*self.gazedist
        eye.matrix_basis = Matrix()
        return mat


    def setMatrix(self, pb, mat, frame):
        pb.matrix = mat
        if frame is not None:
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
            pb.keyframe_insert("location", frame=frame, group=pb.name)


class TransferFromGaze(DazOperator, GazeTransferer):
    bl_idname = "daz.transfer_from_gaze"
    bl_label = "Transfer Gaze To Eye"
    bl_description = "Transfer gaze bone animation to eye bones"
    bl_options = {'UNDO'}

    def run(self, context):
        t1 = perf_counter()
        rig = context.object
        scn = context.scene
        self.setupBones(rig)
        unit = Matrix()
        frames = self.getFrames(rig, scn, ["eye.L", "eye.R", "lEye", "rEye"])
        for frame in frames:
            if frame is not None:
                scn.frame_current = frame
            rig.data["MhaGaze_L"] = rig.data["MhaGaze_R"] = 1.0
            updateScene(context)
            lmat = self.leye.matrix.copy()
            rmat = self.reye.matrix.copy()
            rig.data["MhaGaze_L"] = rig.data["MhaGaze_R"] = 0.0
            updateScene(context)
            self.setEuler(self.leye, lmat, frame)
            self.setEuler(self.reye, rmat, frame)
            self.setQuat(self.lgaze, unit, frame)
            self.setQuat(self.rgaze, unit, frame)
            self.setQuat(self.gaze, unit, frame)
        updateScene(context)
        t2 = perf_counter()
        print("%d frames converted in %g seconds" % (len(frames), t2-t1))


    def setEuler(self, pb, mat, frame):
        pb.matrix = mat
        if frame is not None:
            pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)


    def setQuat(self, pb, mat, frame):
        pb.matrix_basis = mat
        if frame is not None:
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
            pb.keyframe_insert("location", frame=frame, group=pb.name)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    ImportFaceCap,
    ImportLiveLink,
    TransferToGaze,
    TransferFromGaze,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)