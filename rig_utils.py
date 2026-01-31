# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
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

def renameBone(eb, bname):
    if LS.ercDrivers:
        for idx in range(3):
            paths = LS.ercDrivers.get("%s:%d" % (eb.name, idx), [])
            LS.ercDrivers["%s:%d" % (bname, idx)] = paths
        LS.ercFormulas[bname] = form = ["BONE", eb.name]
        updateErcMats(form, bname)
    eb.name = bname


def updateErcMats(form, bname):
    if LS.ercMats:
        if form[0] in ["BONE", "MID"]:
            for gmats in LS.ercMats.values():
                gmats[bname] = gmats[form[1]]
        elif form[0] == "COMP":
            for gmats in LS.ercMats.values():
                gmats[bname] = Matrix()
                for idx,fname in enumerate(form[1:]):
                    gmats[bname].row[idx] = gmats[fname].row[idx]


def deriveBone(bname, eb0, rig, layer, parent):
    return makeBone(bname, rig, eb0.head, eb0.tail, eb0.roll, layer, parent, eb0)


def makeBone(bname, rig, head, tail, roll, layer, parent, formula=None, headbone=None, tailbone=None):
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
    if formula and LS.ercFormulas is not None and not isDefBone(bname):

        def makeFormula(form):
            if isinstance(form, bpy.types.EditBone):
                data = ["BONE", form.name]
            elif form[0] == "COMP":
                data = ["COMP", form[1].name, form[2].name, form[3].name]
            elif form[0] == "MID":
                if form[2]:
                    data = ["MID", form[1].name, form[2].name]
                else:
                    data = ["BONE", form[1].name]
            else:
                print("Unknown formula", form)
                return []
            updateErcMats(data, bname)
            return data

        if GS.ercMethod.startswith("ERC"):
            drvb = rig.data.edit_bones.new(drvBone(bname))
            drvb.use_connect = False
            drvb.head = head
            drvb.tail = tail
            drvb.roll = eb.roll
            if parent:
                parname = ercBase(parent.name)
                eb.parent = parent
                drvb.parent = rig.data.edit_bones.get(drvBone(parname), eb.parent)
            drvb.use_deform = False
            enableBoneNumLayer(drvb, rig, T_HIDDEN)
            LS.ercFormulas[bname] = makeFormula(formula)
        else:
            LS.ercFormulas[bname] = makeFormula(formula)
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

#----------------------------------------------------------
#   Get suffix name
#----------------------------------------------------------

def getSuffixName(bname, useTwist):
    if useTwist and bname.endswith(("twist1", "twist2")):
        pass
    elif isDrvBone(bname) or isFinal(bname):
        return ""
    if len(bname) < 2:
        return bname
    elif bname[1].isupper():
        if bname[0] == "r":
            return "%s%s.R" % (bname[1].lower(), bname[2:])
        elif bname[0] == "l":
            return "%s%s.L" % (bname[1].lower(), bname[2:])
    elif len(bname) >= 3 and bname[1] == "_":
        if bname[0] == "r":
            return "%s%s.R" % (bname[2].lower(), bname[3:])
        elif bname[0] == "l":
            return "%s%s.L" % (bname[2].lower(), bname[3:])
    elif bname[0].isupper():
        return "%s%s" % (bname[0].lower(), bname[1:])
    else:
        return ""


def getPreSufName(bname, rig):
    if bname in rig.data.bones.keys():
        return bname
    sufname = getSuffixName(bname, True)
    if sufname and sufname in rig.data.bones.keys():
        return sufname
    return ""

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

    setMode('EDIT')
    for bname in defbones:
        eb = rig.data.edit_bones[bname]
        dspb = deriveBone(dspBone(bname), eb, rig, "Display", eb.parent)
        dspb.use_deform = False
    setMode('OBJECT')
    for bname in defbones:
        dspb = rig.pose.bones[dspBone(bname)]
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

