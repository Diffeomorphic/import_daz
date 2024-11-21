# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *
from ..animation import FrameRange

#----------------------------------------------------------
#   Bake to FK
#----------------------------------------------------------

class DAZ_OT_BakeToFkRig(FrameRange, IsArmature):
    bl_idname = "daz.bake_pose_to_fk_rig"
    bl_label = "Bake Pose To FK Rig"
    bl_description = "Bake pose to the FK rig before saving pose preset.\nIK arms and legs must be baked separately"
    bl_options = {'UNDO'}

    BakeBones = {
        "rigify2" : {
            "chest" : ["spine_fk.001", "spine_fk.002", "spine_fk.003", "spine_fk.004"],
            "thumb.01_master.L" : ["thumb.02.L", "thumb.03.L"],
            "f_index.01_master.L" : ["f_index.01.L", "f_index.02.L", "f_index.03.L"],
            "f_middle.01_master.L" : ["f_middle.01.L", "f_middle.02.L", "f_middle.03.L"],
            "f_ring.01_master.L" : ["f_ring.01.L", "f_ring.02.L", "f_ring.03.L"],
            "f_pinky.01_master.L" : ["f_pinky.01.L", "f_pinky.02.L", "f_pinky.03.L"],
            "thumb.01_master.R" : ["thumb.02.R", "thumb.03.R"],
            "f_index.01_master.R" : ["f_index.01.R", "f_index.02.R", "f_index.03.R"],
            "f_middle.01_master.R" : ["f_middle.01.R", "f_middle.02.R", "f_middle.03.R"],
            "f_ring.01_master.R" : ["f_ring.01.R", "f_ring.02.R", "f_ring.03.R"],
            "f_pinky.01_master.R" : ["f_pinky.01.R", "f_pinky.02.R", "f_pinky.03.R"],
        },
        "mhx" : {
            "back" : ["spine", "spine-1", "chest", "chest-1"],
            "neckhead" : ["neck", "neck-1", "head"],
            "thumb.L" : ["thumb.02.L", "thumb.03.L"],
            "index.L" : ["f_index.01.L", "f_index.02.L", "f_index.03.L"],
            "middle.L" : ["f_middle.01.L", "f_middle.02.L", "f_middle.03.L"],
            "ring.L" : ["f_ring.01.L", "f_ring.02.L", "f_ring.03.L"],
            "pinky.L" : ["f_pinky.01.L", "f_pinky.02.L", "f_pinky.03.L"],
            "thumb.R" : ["thumb.02.R", "thumb.03.R"],
            "index.R" : ["f_index.01.R", "f_index.02.R", "f_index.03.R"],
            "middle.R" : ["f_middle.01.R", "f_middle.02.R", "f_middle.03.R"],
            "ring.R" : ["f_ring.01.R", "f_ring.02.R", "f_ring.03.R"],
            "pinky.R" : ["f_pinky.01.R", "f_pinky.02.R", "f_pinky.03.R"],
        },
    }

    def run(self, context):
        rig = context.object
        scn = context.scene
        if rig.DazRig in self.BakeBones.keys():
            self.banims = {}
            for baker,baked in self.BakeBones[rig.DazRig].items():
                self.getBones(rig, baker, baked)
            if rig.animation_data and rig.animation_data.action:
                act = rig.animation_data.action
                self.removeFromAction(act, rig)
                matrices = []
                for frame in range(self.startFrame, self.endFrame+1):
                    scn.frame_current = frame
                    updateScene(context)
                    matrices.append((frame, self.addMats()))
                for frame,mats in matrices:
                    scn.frame_current = frame
                    updateScene(context)
                    self.bake(mats, act, context)
            else:
                for bname in list(self.banims.keys()):
                    self.removeFromPose(bname, rig)
                mats = self.addMats()
                self.bake(mats, None, context)
        else:
            print("Nothing to bake for %s rig" % rig.DazRig)


    def getBones(self, rig, baker, baked):
        if baker in rig.pose.bones.keys():
            pb = rig.pose.bones[baker]
            bakedBones = []
            self.banims[baker] = (pb, bakedBones)
        else:
            print("Missing bone:", baker)
            return
        for bname in baked:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                bakedBones.append(pb)


    def addMats(self):
        mats = []
        for bname,banims in self.banims.items():
            bmats = []
            mats.append((banims[0], bmats))
            for pb in banims[1]:
                bmats.append((pb, pb.matrix.copy()))
        return mats


    def removeFromPose(self, bname, rig):
        pb = rig.pose.bones[bname]
        diff = pb.matrix_basis - Matrix()
        maxdiff = max([row.length for row in diff])
        if maxdiff < 1e-5:
            del self.banims[bname]


    def removeFromAction(self, act, rig):
        used = {}
        for fcu in act.fcurves:
            bname,channel = getBoneChannel(fcu)
            if bname:
                used[bname] = True
        for bname in list(self.banims.keys()):
            if bname not in used.keys():
                self.removeFromPose(bname, rig)


    def bake(self, mats, act, context):
        frame = context.scene.frame_current
        for pb,bmats in mats:
            pb.matrix_basis = Matrix()
            if act:
                insertKeys(pb, True, frame)
            context.view_layer.update()
            for pb,mat in bmats:
                pb.matrix = mat
                if act:
                    insertKeys(pb, True, frame)
                context.view_layer.update()
                if isLocationLocked(pb):
                    pb.location = Zero

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_BakeToFkRig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)