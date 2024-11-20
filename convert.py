#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
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
#-------------------------------------------------------------

def optimizePose(context, useApplyRestPose):
    from .merge_rigs import applyRestPoses
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

