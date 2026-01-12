# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .utils import *
from .error import *
from .driver import addDriver, setBoolProp, setFloatProp

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


def connectToParent(rig, bnames):
    setMode('EDIT')
    for eb in rig.data.edit_bones:
        if eb.name in bnames:
            eb.parent.tail = eb.head
            eb.use_connect = True

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def setMhx(rna, prop, value):
    if isinstance(value, bool):
        setBoolProp(rna, prop, value, True)
    elif isinstance(value, float):
        setFloatProp(rna, prop, value, 0.0, 1.0, True)
    else:
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
        cns.euler_order = bone.rotation_mode
    elif target.rotation_mode != 'QUATERNION':
        cns.euler_order = target.rotation_mode
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


def addHint(pb, rig, rotmode=None, hint=18):
    cns = pb.constraints.new('LIMIT_ROTATION')
    cns.name = "Hint"
    cns.owner_space = 'LOCAL'
    if rotmode:
        cns.euler_order = rotmode
    else:
        cns.euler_order = pb.rotation_mode
    cns.min_x = cns.max_x = hint*D
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

#-------------------------------------------------------------
#   Add display transform
#-------------------------------------------------------------

def addDisplayTransform(rig, mesh, headname):
    if rig.animation_data is None:
        return False
    head = rig.pose.bones.get(headname)
    if head is None:
        print("No head bone found")
        return False

    def illegal(bname):
        lname = bname.lower()
        for string in ["brow", "nose", "cheek", "mouth"]:
            if string in lname:
                return False
        for string in ["jaw", "eye", "lid", "ear", "tongue"]:
            if string in lname:
                return True
        return False

    def findDisplayBones(rig, parent, defbones):
        for pb in parent.children:
            if (pb.name in mesh.vertex_groups.keys() and
                pb.custom_shape and
                not illegal(pb.name)):
                defbones.add(pb.name)
            findDisplayBones(rig, pb, defbones)

    defbones = set()
    findDisplayBones(rig, head, defbones)
    print("Add display bones to:\n%s" % defbones)

    def dspName(bname):
        return "%s(dsp)" % bname

    setMode('EDIT')
    for bname in defbones:
        eb = rig.data.edit_bones[bname]
        dspb = deriveBone(dspName(bname), eb, rig, "Display", eb.parent)
        dspb.use_deform = False
    setMode('OBJECT')
    for bname in defbones:
        dspb = rig.pose.bones[dspName(bname)]
        cns = dspb.constraints.new('COPY_LOCATION')
        cns.target = mesh
        cns.subtarget = bname
        pb = rig.pose.bones[bname]
        pb.custom_shape_transform = dspb
        pb.use_transform_at_custom_shape = True
        pb.use_transform_around_custom_shape = True
        pb.use_custom_shape_bone_size = True
    coll = rig.data.collections.get("Display")
    if coll:
        coll.is_visible = False
    return True

#-------------------------------------------------------------
#   Add ERC bones
#-------------------------------------------------------------

def addErcBones(rig, gizmo, useParents):
    defbones = [bone.name for bone in rig.data.bones if not isDrvBone(bone.name)]
    setMode('EDIT')
    for bname in defbones:
        eb = rig.data.edit_bones[bname]
        ercb = deriveBone(ercBone(bname), eb, rig, "ERC", None)
        if useParents and eb.parent:
            #parname = ercBone(eb.parent.name)
            #ercb.parent = rig.data.edit_bones[parname]
            ercb.parent = eb.parent
        ercb.use_deform = False
    setMode('OBJECT')
    for bname in defbones:
        pb = rig.pose.bones[bname]
        ercb = rig.pose.bones[ercBone(bname)]
        ercb.bone.color.palette = 'THEME09'
        ercb.color.palette = 'THEME09'
        if gizmo is None:
            continue
        if pb.custom_shape is None:
            pb.custom_shape = gizmo
            pb.custom_shape_translation[1] = pb.bone.length/2
            pb.custom_shape_scale_xyz = (0.1, 0.5, 0.1)
            pb.bone.show_wire = True
        pb.bone.display_type = 'OCTAHEDRAL'
        pb.custom_shape_transform = ercb
        pb.use_transform_at_custom_shape = True
        pb.use_transform_around_custom_shape = True
        pb.use_custom_shape_bone_size = True
    coll = rig.data.collections.get("ERC")
    if coll:
        coll.is_visible = False
    dazRna(rig.data).DazHasErcBones = True


def updateErcBones(rig):
    from .figure import copyBoneInfo
    from .store import copyConstraint, removeConstraints
    from .driver import addGeneralDriver
    ercbones = [pb for pb in rig.pose.bones if isErcBone(pb.name)]
    basebones = [rig.pose.bones.get(ercBase(pb.name)) for pb in ercbones]
    for pb, ercb in zip(basebones, ercbones):
        if pb is None:
            continue
        bname = pb.name
        pb.name = defBone(bname)
        ercb.name = bname
        removeConstraints(ercb)
        copyBoneInfo(pb, ercb)
        for cns in pb.constraints:
            if cns.type == 'LIMIT_ROTATION':
                copyConstraint(cns, ercb, rig)
        ercb.lock_location = pb.lock_location
        ercb.lock_rotation = pb.lock_rotation
        ercb.lock_scale = pb.lock_scale

        pb.driver_remove("location")
        for idx,ttype in enumerate(['LOC_X', 'LOC_Y', 'LOC_Z']):
            fcu = pb.driver_add("location", idx)
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = "-x"
            var = fcu.driver.variables.new()
            var.type = 'TRANSFORMS'
            var.name = "x"
            trg = var.targets[0]
            trg.id = rig
            trg.bone_target = ercb.name
            trg.transform_type = ttype
            trg.transform_space = 'LOCAL_SPACE'
        removeConstraints(pb)
        cns = copyTransform(pb, ercb, rig, space='LOCAL')
        cns.mix_mode = 'BEFORE_FULL'
    coll = rig.data.collections.get("Bones")
    if coll:
        coll.is_visible = False
    coll = rig.data.collections.get("ERC")
    if coll:
        coll.is_visible = True


