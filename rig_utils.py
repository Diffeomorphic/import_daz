# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .utils import *
from .error import *
from .driver import addDriver

#----------------------------------------------------------
#  Make bone
#----------------------------------------------------------

def deriveBone(bname, eb0, rig, layer, parent):
    return makeBone(bname, rig, eb0.head, eb0.tail, eb0.roll, layer, parent)


def makeBone(bname, rig, head, tail, roll, layer, parent, headbone=None, tailbone=None):
    eb = rig.data.edit_bones.new(bname)
    eb.head = head
    eb.tail = tail
    eb.roll = normalizeRoll(roll)
    eb.use_connect = False
    eb.parent = parent
    eb.use_deform = False
    enableBoneNumLayer(eb, rig, layer)
    if headbone:
        LS.headbones[bname] = headbone.name
    if tailbone:
        LS.tailbones[bname] = tailbone.name
    return eb


def normalizeRoll(roll):
    if roll > 180*D:
        return roll - 360*D
    elif roll < -180*D:
        return roll + 360*D
    else:
        return roll


def unhideAllObjects(context, rig):
    for key in rig.keys():
        if key[0:3] == "Mhh":
            rig[key] = True
    updateScene(context)

#-------------------------------------------------------------
#   connectToParent used by Rigify
#-------------------------------------------------------------

def connectToParent(rig, connectAll=False, useSplitShin=False):
    from .mhx_tools.mhx_data import MHX
    setMode('EDIT')
    if useSplitShin:
        shinBones = MHX.ConnectShin
        otherBones = MHX.ConnectOther
    else:
        shinBones = []
        otherBones = MHX.ConnectOther + MHX.ConnectShin
    if connectAll:
        allBones = MHX.ConnectBendTwist + shinBones + otherBones
    else:
        allBones = MHX.ConnectBendTwist + shinBones
    for eb in rig.data.edit_bones:
        if eb.name in allBones:
            eb.parent.tail = eb.head
            eb.use_connect = True

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def setMhx(rna, prop, value):
    rna[prop] = value


def mhxProp(prop):
    if isinstance(prop, str):
        return propRef(prop)
    else:
        prop1,prop2 = prop
        return (propRef(prop1), propRef(prop2))


def addMuteDriver(cns, rig, prop):
    if prop:
        addDriver(cns, "mute", rig, mhxProp(prop), "not(x)")

#-------------------------------------------------------------
#   Constraints
#-------------------------------------------------------------

def copyTransform(bone, target, rig, prop=None, expr="x", space='POSE'):
    cns = bone.constraints.new('COPY_TRANSFORMS')
    cns.name = "Copy Transform %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    cns.owner_space = space
    cns.target_space = space
    return cns


def copyTransformFkIk(bone, boneFk, boneIk, rig, prop1, prop2=None):
    if boneFk is not None:
        cnsFk = copyTransform(bone, boneFk, rig)
        cnsFk.influence = 1.0
    if boneIk is not None:
        cnsIk = copyTransform(bone, boneIk, rig, prop1)
        cnsIk.influence = 0.0
        if prop2:
            addDriver(cnsIk, "mute", rig, mhxProp(prop2), "x")


def copyLocation(bone, target, rig, prop=None, expr="x", space='POSE'):
    cns = bone.constraints.new('COPY_LOCATION')
    cns.name = "Copy Location %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    cns.owner_space = space
    cns.target_space = space
    return cns


def copyRotation(bone, target, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_ROTATION')
    cns.name = "Copy Rotation %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.owner_space = space
    cns.target_space = space
    if bone.rotation_mode != 'QUATERNION':
        setEulerOrder(cns, bone.rotation_mode)
    elif target.rotation_mode != 'QUATERNION':
        setEulerOrder(cns, target.rotation_mode)
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def copyScale(bone, target, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_SCALE')
    cns.name = "Copy Scale %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.owner_space = space
    cns.target_space = space
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def limitLocation(bone, rig, prop=None):
    cns = bone.constraints.new('LIMIT_LOCATION')
    cns.owner_space = 'LOCAL'
    cns.use_min_x = cns.use_min_y = cns.use_min_z = True
    cns.use_max_x = cns.use_max_y = cns.use_max_z = True
    cns.use_transform_limit = True
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), "x")
    return cns


def limitRotation(bone, rig, prop=None):
    cns = bone.constraints.new('LIMIT_ROTATION')
    cns.owner_space = 'LOCAL'
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = True
    cns.use_transform_limit = True
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), "x")
    return cns


def ikConstraint(last, target, pole, angle, count, rig, prop=None, expr="x"):
    cns = last.constraints.new('IK')
    cns.name = "IK %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if pole:
        cns.pole_target = rig
        cns.pole_subtarget = pole.name
        cns.pole_angle = angle*D
    cns.chain_count = count
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def addHint(pb, rig):
    cns = pb.constraints.new('LIMIT_ROTATION')
    cns.name = "Hint"
    cns.owner_space = 'LOCAL'
    setEulerOrder(cns, pb.rotation_mode)
    cns.min_x = cns.max_x = 18*D
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = True
    cns.use_transform_limit = True


def stretchTo(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('STRETCH_TO')
    cns.name = "StretchTo %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.volume = "NO_VOLUME"
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def dampedTrack(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('DAMPED_TRACK')
    cns.name = "Damped Track %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def trackTo(pb, target, rig, space='POSE'):
    cns = pb.constraints.new('TRACK_TO')
    cns.name = "Track To %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.up_axis = 'UP_Z'
    cns.use_target_z = True
    cns.target_space = space
    cns.owner_space = space
    return cns


def lockedTrack(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('LOCKED_TRACK')
    cns.name = "Locked Track %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.lock_axis = 'LOCK_X'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns

#-------------------------------------------------------------
#   Improve IK
#-------------------------------------------------------------

def improveIk(rig, exclude=[]):
    ikconstraints = []
    for pb in rig.pose.bones:
        if pb.name in exclude:
            continue
        for cns in pb.constraints:
            if cns.type == 'IK':
                ikconstraints.append((pb, cns, cns.mute))
                cns.mute = True
                pb.rotation_euler[0] = 30*D
                pb.lock_rotation[0] = True
    for pb,cns,mute in ikconstraints:
        pb.lock_rotation = TTrue
        pb.lock_location = TTrue
        cns.mute = mute
        pb.use_ik_limit_y = pb.use_ik_limit_z = False
        pb.lock_ik_y = pb.lock_ik_z = True
        pb.use_ik_limit_x = True
        pb.ik_min_x = -15*D
        pb.ik_max_x = 160*D
