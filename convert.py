# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, DF

#-------------------------------------------------------------
#   Load pose
#-------------------------------------------------------------

def getCharacterFromRig(rig):
    if dazRna(rig).DazMesh:
        char = dazRna(rig).DazMesh.lower().replace("-","_").replace("genesis", "genesis_")
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
            rot, dazRna(pb.bone).DazOrient, dazRna(pb).DazRotMode = pose[pbname]
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
    rig = context.object
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix()

    def getBones(bnames, rig):
        bones = []
        for bname in bnames:
            pb = rig.pose.bones.get(bname)
            if pb:
                bones.append(pb)
        return bones

    def setXAngles(angles, pbs, rig):
        for angle,pb in zip(angles, pbs):
            wmat = Euler((angle, 0, 0)).to_matrix().to_4x4()
            wmat.col[3] = pb.matrix.col[3]
            pb.matrix = wmat
            updateObject(context, rig)
            euler = pb.matrix_basis.to_euler()
            if useApplyRestPose:
                cns = getConstraint(pb, 'LIMIT_ROTATION')
                if cns:
                    cns.min_x -= euler.x
                    cns.max_x -= euler.x
                    cns.min_y -= euler.y
                    cns.max_y -= euler.y
                    cns.min_z -= euler.z
                    cns.max_z -= euler.z
                for ttype,angle in zip(('ROT_X', 'ROT_Z', 'ROT_Z'), euler):
                    shiftDriver(rig, rig, pb, ttype, angle)
                    shiftDriver(rig.data, rig, pb, ttype, angle)
                    for ob in getShapeChildren(rig):
                        shiftDriver(ob.data.shape_keys, rig, pb, ttype, angle)

    def shiftDriver(rna, rig, pb, ttype, angle):
        if rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    if (trg.id == rig and
                        trg.bone_target == pb.name and
                        trg.transform_type == ttype):
                        string = fcu.driver.expression.replace(var.name, "(%s+%.3f)" % (var.name, angle))
                        fcu.driver.expression = string

    thighs = getBones(["lThigh", "lThighBend", "l_thigh", "rThigh", "rThighBend", "r_thigh"], rig)
    shins = getBones(["lShin", "lShinBend", "l_shin", "rShin", "rShinBend", "r_shin"], rig)
    feet = getBones(["lFoot", "l_foot", "rFoot", "r_foot"], rig)
    fangles = [pb.matrix.to_euler().x for pb in feet]
    setXAngles([-100*D]*len(thighs), thighs, rig)
    setXAngles([-80*D]*len(shins), shins, rig)
    setXAngles(fangles, feet, rig)

    from .apply import applyRestPoses
    if useApplyRestPose:
        applyRestPoses(context, rig)

#-------------------------------------------------------------
#   Bone conversion
#-------------------------------------------------------------

def getConverter(srctype, trg, useConvertMerged=False):
    if srctype == "genesis8":
        srctype = "genesis3"
    elif srctype == "genesis":
        srctype = "genesis1"
    trgtype = dazRna(trg).DazRig
    if trgtype[-7:] == ".suffix":
        trgtype = trgtype[:-7]
    if trgtype == "genesis8":
        trgtype = "genesis3"
    elif trgtype == "genesis":
        trgtype = "genesis1"

    if srctype == "" or trgtype == "":
        return {},[]
    if (srctype in DF.TwistBones.keys() and
        trgtype not in DF.TwistBones.keys()):
        twists = DF.TwistBones[srctype]
    else:
        twists = []

    if srctype == trgtype:
        return {},twists
    if trgtype.startswith(("mhx", "rigify")):
        if useConvertMerged:
            file = "genesis-%s" % trgtype
        else:
            if srctype == "genesis2":
                srctype = "genesis1"
            file = "%s-%s" % (srctype, trgtype)
    elif trgtype == "genesis9":
        file = "genesis1238-genesis9"
    else:
        file = "%s-%s" % (srctype, trgtype)
    conv = DF.loadEntry(file, "converters", strict=False)
    if conv:
        print("Using converter", file)
    else:
        print("No converter", srctype, dazRna(trg).DazRig)
    return conv, twists

