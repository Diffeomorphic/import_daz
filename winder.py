# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .rig_utils import *

#-------------------------------------------------------------
#   Winders
#-------------------------------------------------------------

def addSuperWinder(rig, windname, bnames, layers, prop1=None, prop2=None, factor=1, alignRoll=False, master=None):
    nbones = len(bnames)
    if nbones < 2:
        return
    if len(layers) == 2:
        lmain, lspine = layers
        lhelp = lhelp2 = ldef = T_HIDDEN
    else:
        lmain, lspine, lhelp, lhelp2, ldef = layers
    setMode('EDIT')
    first = rig.data.edit_bones[bnames[0]]
    last = rig.data.edit_bones[bnames[-1]]
    if master:
        master = rig.data.edit_bones.get(master)
    roll = first.roll
    wind = makeBone("MCH-%s" % windname, rig, first.head, last.tail, roll, lhelp, first.parent)
    fkwind = deriveBone(windname, wind, rig, lmain, first.parent)
    ikwind = makeBone("ik_%s" % windname, rig, last.tail, first.head, roll, lmain, master)
    revwind = deriveBone("REV-%s" % windname, ikwind, rig, lhelp, fkwind)
    revikwind = deriveBone("REV-ik_%s" % windname, wind, rig, lhelp, ikwind)
    eb0 = rig.data.edit_bones[bnames[0]]
    for bname in bnames[1:]:
        eb = rig.data.edit_bones[bname]
        eb0.tail = eb.head
        eb0 = eb
    eb0.tail = wind.tail
    eb = first.parent
    for bname in bnames:
        defb = rig.data.edit_bones[bname]
        if alignRoll:
            defb.roll = roll
        defb.name = "DEF-%s" % bname
        enableBoneNumLayer(defb, rig, ldef)
        mchb = deriveBone("MCH-%s" % bname, defb, rig, lhelp2, eb)
        eb = deriveBone(bname, defb, rig, lspine, mchb)

    from .figure import copyBoneInfo
    setMode('OBJECT')
    wind = rig.pose.bones["MCH-%s" % windname]
    fkwind = rig.pose.bones[windname]
    ikwind = rig.pose.bones["ik_%s" % windname]
    revwind = rig.pose.bones["REV-%s" % windname]
    revikwind = rig.pose.bones["REV-ik_%s" % windname]
    pbones = []
    defbones = []
    defb = None
    for n,bname in enumerate(bnames):
        pb = rig.pose.bones[bname]
        pbones.append(pb)
        mchb = rig.pose.bones["MCH-%s" % bname]
        mchb.bone.inherit_scale = 'NONE'
        if defb:
            cns = stretchTo(defb, pb, rig)
            cns.volume = 'VOLUME_XZX'
            #addMuteDriver(cns, rig, prop1)
        defb = rig.pose.bones["DEF-%s" % bname]
        copyBoneInfo(defb, pb)
        defb.bone.inherit_scale = 'NONE'
        defbones.append(defb)
        cns = copyTransform(defb, pb, rig, space='POSE')
        #addMuteDriver(cns, rig, prop1)
        cns = copyTransform(mchb, wind, rig, space='LOCAL')
        cns.influence = factor/nbones
        addMuteDriver(cns, rig, prop1)
    cns = stretchTo(defb, pb, rig)
    cns.volume = 'VOLUME_XZX'
    cns.head_tail = 1.0
    addMuteDriver(cns, rig, prop1)
    copyTransformFkIk(wind, fkwind, revikwind, rig, prop2)
    first = pbones[0]
    fkwind.rotation_mode = first.rotation_mode
    last = defbones[-1]
    for pb in last.children:
        pb.bone.inherit_scale = 'NONE'
    return fkwind, ikwind, pbones


def addWinder(rig, windname, bnames, layers,
        prop=None,
        parname=None,
        gizmo=None,
        useBaseLocation=False,
        useLocation=False,
        useScale=False,
        xaxis=None,
        influs=None):
    if len(bnames) < 3:
        print("Too few bones to wind: %s" % windname)
        return None, []
    setMode('EDIT')
    first = rig.data.edit_bones[bnames[0]]
    last = rig.data.edit_bones[bnames[-1]]
    windbone = makeBone(windname, rig, first.head, last.tail, first.roll, layers[0], first.parent)
    if xaxis is not None:
        from .bone import setRoll
        setRoll(windbone, xaxis)

    setMode('OBJECT')
    pb = rig.pose.bones[bnames[0]]
    pbones = [pb]
    winder = rig.pose.bones[windname]
    modernizeBone(winder)
    if gizmo:
        winder.custom_shape = gizmo
        winder.bone.show_wire = True
    winder.rotation_mode = pb.rotation_mode
    winder.matrix_basis = pb.matrix_basis
    #winder.lock_location = pb.lock_location
    winder.lock_rotation = pb.lock_rotation
    #winder.lock_scale = pb.lock_scale
    if not (useLocation or useBaseLocation):
        winder.lock_location = TTrue
    if not useScale:
        winder.lock_scale = TTrue

    def setLocks(locks, cns):
        if locks[0]:
            cns.use_x = False
        if locks[1]:
            cns.use_y = False
        if locks[2]:
            cns.use_z = False

    windedLayer = layers[1]
    cns = copyRotation(pb, winder, rig)
    setLocks(pb.lock_rotation, cns)
    cns.mix_mode = 'AFTER'
    infl = 2*pb.bone.length/winder.length
    if not influs:
        influs = len(bnames)*[infl]
    cns.influence = influs[0]
    addMuteDriver(cns, rig, prop)
    if useScale:
        cns = copyScale(pb, winder, rig)
        setLocks(pb.lock_scale, cns)
        if pb.bone.inherit_scale != "NONE":
            cns.influence = infl
        addMuteDriver(cns, rig, prop)
    if useBaseLocation or useLocation:
        cns = copyLocation(pb, winder, rig)
        addMuteDriver(cns, rig, prop)
    enableBoneNumLayer(pb.bone, rig, windedLayer)
    for bname,infl in zip(bnames[1:], influs[1:]):
        pb = rig.pose.bones[bname]
        pbones.append(pb)
        cns = copyRotation(pb, winder, rig)
        setLocks(pb.lock_rotation, cns)
        cns.mix_mode = 'AFTER'
        cns.influence = infl
        addMuteDriver(cns, rig, prop)
        infl = 2*pb.bone.length/winder.length
        if useScale:
            cns = copyScale(pb, winder, rig, space='LOCAL')
            setLocks(pb.lock_scale, cns)
            cns.mix_mode = 'AFTER'
            if pb.bone.inherit_scale != "NONE":
                cns.influence = infl
            addMuteDriver(cns, rig, prop)
        if useLocation:
            cns = copyLocation(pb, winder, rig, space='LOCAL')
            cns.mix_mode = 'AFTER'
            cns.influence = infl
            addMuteDriver(cns, rig, prop)
        enableBoneNumLayer(pb.bone, rig, windedLayer)
    return winder, pbones