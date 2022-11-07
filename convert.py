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
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, JsonExportFile, AF
from .animation import HideOperator

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
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useApplyRestPose")

    def run(self, context):
        optimizePose(context, self.useApplyRestPose)


def optimizePose(context, useApplyRestPose):
    from .merge import applyRestPoses
    rig = context.object
    char = getCharacterFromRig(rig)
    if char is None:
        raise DazError("Did not recognize character")
    entry = AF.loadEntry(char, "ikposes")
    loadPose(context, rig, entry)
    if useApplyRestPose:
        applyRestPoses(context, rig, [])

#-------------------------------------------------------------
#   Convert Rig
#-------------------------------------------------------------

class DAZ_OT_ConvertRigPose(DazPropsOperator):
    bl_idname = "daz.convert_rig"
    bl_label = "Convert DAZ Rig"
    bl_description = "Convert current DAZ rig to other DAZ rig"
    bl_options = {'UNDO'}

    newRig : EnumProperty(
        items = AF.RestPoseItems,
        name = "New Rig",
        description = "Convert active rig to this",
        default = "genesis_3_female")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig[0:7] == "genesis")

    def draw(self, context):
        self.layout.prop(self, "newRig")

    def run(self, context):
        rig = context.object
        scn = context.scene
        scale = 1.0
        if self.newRig in AF.SourceRigs.keys():
            modify = False
            src = AF.SourceRigs[self.newRig]
            conv,twists = getConverter(src, rig)
            if conv:
                self.renameBones(rig, conv)
        else:
            modify = True
            src = self.newRig
            table = AF.restposes[src]
            if "translate" in table.keys():
                self.renameBones(rig, table["translate"])
            if "scale" in table.keys():
                scale = table["scale"] * rig.DazScale
        entry = AF.loadEntry(self.newRig, "restposes")
        loadPose(context, rig, entry)
        rig.DazRig = src
        print("Rig converted to %s" % self.newRig)
        if scale != 1.0:
            raise DazError("Use scale = %.5f when loading BVH files.       " % scale, True)


    def renameBones(self, rig, conv):
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            if eb.name in conv.keys():
                data = conv[eb.name]
                if isinstance(data, list):
                    eb.name = data[0]
                    if data[1] == "reverse":
                        head = tuple(eb.head)
                        tail = tuple(eb.tail)
                        eb.head = (1,2,3)
                        eb.tail = head
                        eb.head = tail
                else:
                    eb.name = data
        setMode('OBJECT')

#-------------------------------------------------------------
#   Bone conversion
#-------------------------------------------------------------

def getConverter(stype, trg):
    if stype == "genesis8":
        stype = "genesis3"
    trgtype = trg.DazRig
    if trgtype == "genesis8":
        trgtype = "genesis3"

    if stype == "" or trgtype == "":
        return {},[]
    if (stype in AF.TwistBones.keys() and
        trgtype not in AF.TwistBones.keys()):
        twists = AF.TwistBones[stype]
    else:
        twists = []

    if stype == trgtype:
        return {},twists
    if trgtype == "mhx":
        char = stype[:-1] + "-mhx"
    elif trgtype[0:6] == "rigify":
        char = stype[:-1] + "-" + trgtype
    elif trgtype == "genesis9":
        char = "genesis1238-genesis9"
    else:
        char = stype + "-" + trgtype

    conv = AF.loadEntry(char, "converters")
    if not conv:
        print("No converter", stype, trg.DazRig)
    return conv, twists

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_OptimizePose,
    DAZ_OT_ConvertRigPose,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
