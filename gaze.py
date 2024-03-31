# Copyright (c) 2016-2024, Thomas Larsson
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
from mathutils import Matrix
from .utils import *
from .error import *

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
        self.layers = getRigLayers(rig)
        enableAllRigLayers(rig)


    def restoreState(self, context):
        rig = context.object
        setRigLayers(rig, self.layers)


    def setupBones(self, rig):
        self.leye = self.getBones(["lEye", "eye.L"], rig)
        self.reye = self.getBones(["rEye", "eye.R"], rig)
        self.gaze = rig.pose.bones["gaze"]
        self.lgaze = rig.pose.bones["gaze.L"]
        self.rgaze = rig.pose.bones["gaze.R"]
        self.FZ = Matrix.Rotation(math.pi, 4, 'Z')
        self.gazedist = (self.lgaze.bone.head_local - self.leye.bone.head_local).length


    def getBones(self, bnames, rig):
        for bname in bnames:
            pb = rig.pose.bones.get(bname)
            if pb:
                return pb
        print("Did not find bones: %s" % bnames)
        return None


    def getFrames(self, rig, scn, bnames):
        fstruct = {}
        if rig.animation_data and rig.animation_data.action:
            act = rig.animation_data.action
            for fcu in act.fcurves:
                bname,channel = getBoneChannel(fcu)
                if bname and bname in bnames:
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


class DAZ_OT_TransferToGaze(DazOperator, GazeTransferer):
    bl_idname = "daz.transfer_to_gaze"
    bl_label = "Transfer Eye To Gaze"
    bl_description = "Transfer eye bone animation to gaze bones"
    bl_options = {'UNDO'}

    def run(self, context):
        t1 = perf_counter()
        rig = context.object
        scn = context.scene
        self.setupBones(rig)
        rig["MhaGaze_L"] = 0.0
        rig["MhaGaze_R"] = 0.0
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
        rig["MhaGaze_L"] = 1.0
        rig["MhaGaze_R"] = 1.0
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


class DAZ_OT_TransferFromGaze(DazOperator, GazeTransferer):
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
        frames = self.getFrames(rig, scn, ["gaze", "gaze.L", "gaze.R"])
        for frame in frames:
            if frame is not None:
                scn.frame_current = frame
            rig["MhaGaze_L"] = 1.0
            rig["MhaGaze_R"] = 1.0
            updateScene(context)
            lmat = self.leye.matrix.copy()
            rmat = self.reye.matrix.copy()
            rig["MhaGaze_L"] = 0.0
            rig["MhaGaze_R"] = 0.0
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
    DAZ_OT_TransferToGaze,
    DAZ_OT_TransferFromGaze,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)