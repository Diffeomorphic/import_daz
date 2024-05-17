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
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, JsonExportFile, DF

#-------------------------------------------------------------
#   Load pose
#-------------------------------------------------------------

def getCharacterFromRig(rig):
    if rig.DazMesh:
        char = rig.DazMesh.lower().replace("-","_").replace("genesis", "genesis_")
        if char[-1] == "_":
            char = char[:-1]
        print("Character: %s" % char)
        return char
    else:
        return None


def loadPose(context, rig, entry):

    def getBoneName(bname, bones):
        if bname in bones.keys():
            return bname
        elif isDrvBone(bname):
            bname = baseBone(bname)
            if bname in bones.keys():
                return bname
        elif (bname[-4:] == "Copy" and
              bname[:-4] in bones.keys()):
            return bname[:-4]
        return None

    def loadBonePose(context, pb, pose):
        pbname = getBoneName(pb.name, pose)
        if pbname and pb.name[:-4] != "Copy":
            rot, pb.bone.DazOrient, pb.DazRotMode = pose[pbname]
            euler = Euler(rot)
            mat = euler.to_matrix()
            rmat = pb.bone.matrix_local.to_3x3()
            if pb.parent:
                par = pb.parent
                rmat = par.bone.matrix_local.to_3x3().inverted() @ rmat
                mat = par.matrix.to_3x3().inverted() @ mat
            bmat = rmat.inverted() @ mat
            pb.matrix_basis = bmat.to_4x4()
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_euler[n] = 0
            updateScene(context)

        if pb.name != "head":
            for child in pb.children:
                loadBonePose(context, child, pose)

    roots = [pb for pb in rig.pose.bones if pb.parent is None]
    loadBonePose(context, roots[0], entry["pose"])

#-------------------------------------------------------------
#   Optimize pose for IK
#   Function used by rigify
#-------------------------------------------------------------

class DAZ_OT_OptimizePose(DazPropsOperator, IsArmature):
    bl_idname = "daz.optimize_pose"
    bl_label = "Optimize Pose For IK"
    bl_description = "Optimize pose for IK.\nIncompatible with pose loading and body morphs"
    bl_options = {'UNDO'}

    useApplyRestPose : BoolProperty(
        name = "Apply Rest Pose",
        description = "Apply current pose as rest pose for all armatures",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useApplyRestPose")

    def run(self, context):
        optimizePose(context, self.useApplyRestPose)


def optimizePose(context, useApplyRestPose):
    from .merge import applyRestPoses
    rig = context.object
    char = getCharacterFromRig(rig)
    if char is None:
        reportError("Could not optimize pose because the character was not recognized.")
        return
    entry = DF.loadEntry(char, "ikposes")
    loadPose(context, rig, entry)
    if useApplyRestPose:
        applyRestPoses(context, rig, [])

#-------------------------------------------------------------
#   Bone conversion
#-------------------------------------------------------------

def getConverter(srctype, trg):
    if srctype == "genesis8":
        srctype = "genesis3"
    trgtype = trg.DazRig
    if trgtype[-7:] == ".suffix":
        trgtype = trgtype[:-7]
    if trgtype == "genesis8":
        trgtype = "genesis3"

    if srctype == "" or trgtype == "":
        return {},[]
    if (srctype in DF.TwistBones.keys() and
        trgtype not in DF.TwistBones.keys()):
        twists = DF.TwistBones[srctype]
    else:
        twists = []

    if srctype == trgtype:
        return {},twists
    if trgtype in ["mhx", "rigify", "rigify2"]:
        file = "genesis-%s" % trgtype
    elif trgtype == "genesis9":
        file = "genesis1238-genesis9"
    else:
        file = "%s-%s" % (srctype, trgtype)
    conv = DF.loadEntry(file, "converters")
    if not conv:
        print("No converter", srctype, trg.DazRig)
    return conv, twists

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_OptimizePose,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
