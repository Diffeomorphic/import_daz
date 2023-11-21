# Copyright (c) 2016-2023, Thomas Larsson
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

import math
from mathutils import *
from .error import *
from .utils import *
from .layers import *
from .propgroups import DazPairGroup
from .driver import addDriver
from .fix import ConstraintStore, BendTwists, Fixer, GizmoUser
from .mhx_data import MHX

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

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getBoneCopy(bname, model, rpbs):
    pb = rpbs[bname]
    pb.DazRotMode = model.DazRotMode
    pb.rotation_mode = model.rotation_mode
    return pb


def deriveBone(bname, eb0, rig, layer, parent):
    return makeBone(bname, rig, eb0.head, eb0.tail, eb0.roll, layer, parent)


def makeBone(bname, rig, head, tail, roll, layer, parent):
    eb = rig.data.edit_bones.new(bname)
    eb.head = head
    eb.tail = tail
    eb.roll = normalizeRoll(roll)
    eb.use_connect = False
    eb.parent = parent
    eb.use_deform = False
    enableBoneNumLayer(eb, rig, layer)
    return eb


def normalizeRoll(roll):
    if roll > 180*D:
        return roll - 360*D
    elif roll < -180*D:
        return roll + 360*D
    else:
        return roll


def addMuteDriver(cns, rig, prop):
    if prop:
        addDriver(cns, "mute", rig, mhxProp(prop), "not(x)")

#-------------------------------------------------------------
#   Constraints
#-------------------------------------------------------------

def copyTransform(bone, target, rig, prop=None, expr="x", space='WORLD'):
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


def copyLocation(bone, target, rig, prop=None, expr="x", space='WORLD'):
    cns = bone.constraints.new('COPY_LOCATION')
    cns.name = "Copy Location %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
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
    if (bone.rotation_mode != 'QUATERNION' and
        bone.rotation_mode == target.rotation_mode):
        cns.euler_order = bone.rotation_mode
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


def limitLocation(bone, rig):
    cns = bone.constraints.new('LIMIT_LOCATION')
    cns.owner_space = 'LOCAL'
    cns.use_transform_limit = True
    return cns


def limitRotation(bone, rig):
    cns = bone.constraints.new('LIMIT_ROTATION')
    cns.owner_space = 'LOCAL'
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = False
    cns.use_transform_limit = True
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
    cns.euler_order = pb.rotation_mode
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


def childOf(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('CHILD_OF')
    cns.name = "ChildOf %s" % target
    cns.target = rig
    cns.subtarget = target
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def armatureConstraint(pb, rig, drivers):
    cns = pb.constraints.new('ARMATURE')
    for bone,prop,expr in drivers:
        target = cns.targets.new()
        target.target = rig
        target.subtarget = bone
        addDriver(target, "weight", rig, mhxProp(prop), expr)
    return cns


def getPropString(prop, x):
    if isinstance(prop, tuple):
        return prop[1], ("(1-%s)" % (x))
    else:
        return prop, x

#-------------------------------------------------------------
#   Winders
#-------------------------------------------------------------

def addSuperWinder(rig, windname, bnames, layers, prop1=None, prop2=None, factor=1, alignRoll=False, master=None):
    nbones = len(bnames)
    if nbones < 2:
        return
    if len(layers) == 2:
        lmain, lspine = layers
        lhelp = lhelp2 = ldef = 31
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
    setMode('POSE')
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
        cns = copyTransform(defb, pb, rig, space='WORLD')
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


def addWinder(rig, windname, bnames, layers, prop=None, parname=None, gizmo=None, useBaseLocation=False, useLocation=False, useScale=False, xaxis=None):
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

    setMode('POSE')
    pb = rig.pose.bones[bnames[0]]
    pbones = [pb]
    winder = rig.pose.bones[windname]
    if gizmo:
        winder.custom_shape = gizmo
        winder.bone.show_wire = True
    winder.rotation_mode = pb.rotation_mode
    winder.matrix_basis = pb.matrix_basis
    #winder.lock_location = pb.lock_location
    winder.lock_rotation = pb.lock_rotation
    #winder.lock_scale = pb.lock_scale
    if not useLocation:
        winder.lock_location = (True, True, True)
    if not useScale:
        winder.lock_scale = (True, True, True)

    def setLocks(locks, cns):
        if locks[0]:
            cns.use_x = False
        if locks[1]:
            cns.use_y = False
        if locks[2]:
            cns.use_z = False

    windedLayer = layers[1]
    infl = 2*pb.bone.length/winder.length
    cns = copyRotation(pb, winder, rig)
    setLocks(pb.lock_rotation, cns)
    cns.use_offset = True
    cns.influence = infl
    addMuteDriver(cns, rig, prop)
    if useScale:
        cns = copyScale(pb, winder, rig)
        setLocks(pb.lock_scale, cns)
        cns.influence = infl
        addMuteDriver(cns, rig, prop)
    if useBaseLocation:
        cns = copyLocation(pb, winder, rig)
        cns.influence = infl
        addMuteDriver(cns, rig, prop)
    enableBoneNumLayer(pb.bone, rig, windedLayer)
    for bname in bnames[1:]:
        pb = rig.pose.bones[bname]
        pbones.append(pb)
        #infl = 2*pb.bone.length/winder.length
        cns = copyRotation(pb, winder, rig)
        setLocks(pb.lock_rotation, cns)
        cns.use_offset = True
        cns.influence = infl
        addMuteDriver(cns, rig, prop)
        if useScale:
            cns = copyScale(pb, winder, rig, space='LOCAL')
            setLocks(pb.lock_scale, cns)
            cns.use_offset = True
            cns.influence = infl
            addMuteDriver(cns, rig, prop)
        if useLocation:
            cns = copyLocation(pb, winder, rig, space='LOCAL')
            cns.use_offset = True
            cns.influence = infl
            addMuteDriver(cns, rig, prop)
        enableBoneNumLayer(pb.bone, rig, windedLayer)
    return winder, pbones


def addFingerIk(rig, ikname, bnames, parname, layers, prop1, prop2):
    nbones = len(bnames)
    if nbones < 2:
        return
    setMode('EDIT')
    parent = rig.data.edit_bones[parname]
    last = rig.data.edit_bones[bnames[-1]]
    makeBone(ikname, rig, last.tail, 2*last.tail-last.head, last.roll, layers[0], parent)
    setMode('POSE')
    ikgoal = rig.pose.bones[ikname]
    first = rig.pose.bones[bnames[0]]
    influ = 1.0/(nbones+1)
    cns = dampedTrack(first, ikgoal, rig, prop2, "%.3f*x" % influ)
    cns.influence = influ
    addMuteDriver(cns, rig, prop1)
    for n,bname in enumerate(bnames[1:]):
        pb = rig.pose.bones[bname]
        influ = 0.4 + n*0.4
        cns = lockedTrack(pb, ikgoal, rig, prop2, "%.3f*x" % influ)
        cns.influence = influ
        addMuteDriver(cns, rig, prop1)

#-------------------------------------------------------------
#   Bone children
#-------------------------------------------------------------

def unhideAllObjects(context, rig):
    for key in rig.keys():
        if key[0:3] == "Mhh":
            rig[key] = True
    updateScene(context)


def applyBoneChildren(context, rig):
    from .node import clearParent
    unhideAllObjects(context, rig)
    bchildren = []
    for ob in rig.children:
        if ob.parent_type == 'BONE':
            bchildren.append((ob, ob.parent_bone))
            clearParent(ob)
    return bchildren

#-------------------------------------------------------------
#   Convert to MHX button
#-------------------------------------------------------------

class DAZ_OT_ConvertToMhx(DazPropsOperator, ConstraintStore, BendTwists, Fixer, GizmoUser):
    bl_idname = "daz.convert_to_mhx"
    bl_label = "Convert To MHX"
    bl_description = "Convert rig to MHX"
    bl_options = {'UNDO', 'PRESET'}

    gizmoFile = "mhx"

    addTweakBones : BoolProperty(
        name = "Tweak Bones",
        description = "Add tweak bones",
        default = False)

    showLinks : BoolProperty(
        name = "Show Link Bones",
        description = "Show link bones",
        default = True)

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Use pole targets for IK.\nEnable for perfect FK/IK snapping",
        default = False)

    useSpineIk : BoolProperty(
        name = "Spine IK",
        description = "Spine IK (experimental)",
        default = True)

    useShaftWinder : BoolProperty(
        name = "Shaft Winder",
        description = "Add windoer for Dicktator/Futalicious shaft",
        default = False)

    useChildOfConstraints : BoolProperty(
        name = "ChildOf Constraints (Experimental)",
        description = ("Use childOf constraints for parents of elbow and knee pole targets.\n" +
                       "May cause problems for FK-IK snapping"),
        default = False)

    useFixKnees : BoolProperty(
        name = "Fix Elbows And Knees",
        description = "Change elbow and knee location for better IK",
        default = True)

    elbowParent : EnumProperty(
        items = [('HAND', "Hand", "Parent elbow pole target to IK hand"),
                 ('SHOULDER', "Shoulder", "Parent elbow pole target to shoulder"),
                 ('MASTER', "Master", "Parent elbow pole target to the master bone")],
        name = "Elbow Parent",
        description = "Parent of elbow pole target")

    kneeParent : EnumProperty(
        items = [('FOOT', "Foot", "Parent knee pole target to IK foot"),
                 ('HIP', "Hip", "Parent knee pole target to hip"),
                 ('MASTER', "Master", "Parent knee pole target to the master bone")],
        name = "Knee Parent",
        description = "Parent of knee pole target")

    useFoot2 : BoolProperty(
        name = "Second IK Foot",
        description = "Add extra foot and toe bones as IK targets",
        default = False)

    boneGroups : CollectionProperty(
        type = DazPairGroup,
        name = "Bone Groups")

    useRaiseError : BoolProperty(
        name = "Missing Bone Errors",
        description = "Raise error for missing bones",
        default = True)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.DazSimpleIK)

    def __init__(self):
        ConstraintStore.__init__(self)
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "usePoleTargets")
        if self.usePoleTargets:
            self.layout.prop(self, "showLinks")
            self.layout.prop(self, "useFixKnees")
        self.layout.prop(self, "addTweakBones")
        Fixer.draw(self, context)
        self.layout.prop(self, "useChildOfConstraints")
        self.layout.prop(self, "elbowParent")
        self.layout.prop(self, "kneeParent")
        self.layout.prop(self, "useFoot2")
        self.layout.prop(self, "useRaiseError")

    def drawRigify(self):
        self.layout.prop(self, "useSpineIk")
        self.layout.prop(self, "useTongueIk")
        self.layout.prop(self, "useShaftWinder")

    def invoke(self, context, event):
        self.createBoneGroups(context.object)
        return DazPropsOperator.invoke(self, context, event)


    def storeState(self, context):
        from .driver import muteDazFcurves
        DazPropsOperator.storeState(self, context)
        muteDazFcurves(self.activeObject, True)


    def restoreState(self, context):
        from .driver import muteDazFcurves
        rig = self.activeObject
        muteDazFcurves(rig, rig.DazDriversDisabled)
        DazPropsOperator.restoreState(self, context)


    def createBoneGroups(self, rig):
        if not BLENDER3:
            return
        if len(rig.pose.bone_groups) != len(MHX.BoneGroups):
            for bg in list(rig.pose.bone_groups):
                rig.pose.bone_groups.remove(bg)
            for bgname,color,_layers in MHX.BoneGroups:
                bg = rig.pose.bone_groups.new(name=bgname)
                bg.color_set = 'CUSTOM'
                bg.colors.normal = color
                bg.colors.select = (0.6, 0.9, 1.0)
                bg.colors.active = (1.0, 1.0, 0.8)


    def checkMhxEnabled(self, rig):
        try:
            getattr(rig, "MhaFingerControl_L")
            return True
        except AttributeError:
            return False


    def run(self, context):
        rig = context.object
        if not self.checkMhxEnabled(rig):
            msg = ("The MHX Runtime System is not enabled.   \nThe add-on is found under Rigging")
            raise DazError(msg)
        startProgress("Convert %s to MHX" % rig.name)
        t1 = perf_counter()
        self.createTmp()
        try:
            self.convertMhx(context)
        finally:
            self.deleteTmp()
        t2 = perf_counter()
        showProgress(25, 25, "MHX rig created in %.1f seconds" % (t2-t1))
        endProgress()
        self.printMessages()


    def convertMhx(self, context):
        from .figure import finalizeArmature
        rig = context.object
        self.rigname = rig.name
        rig.DazMhxLegacy = False
        self.makeRealParents(context, rig)
        if self.keepRig:
            nrig = self.saveDazRig(context)
        self.meshes = getMeshChildren(rig)
        finalizeArmature(rig)
        clearBoneCollections(rig)
        makeBoneCollections(rig, MhxLayers)
        self.createBoneGroups(rig)
        self.startGizmos(context, rig)
        self.sacred = ["root", "hips", "spine"]
        self.rolls = {}

        #-------------------------------------------------------------
        #   Fix and rename bones of the genesis rig
        #-------------------------------------------------------------

        showProgress(1, 25, "  Fix DAZ rig")
        bendTwistBones = list(MHX.BendTwistBones)
        self.constraints = {}
        enableAllRigLayers(rig)
        bchildren = applyBoneChildren(context, rig)
        for pb in rig.pose.bones:
            pb.driver_remove("HdOffset")
            pb.driver_remove("TlOffset")
        if rig.DazRig in ["genesis3", "genesis8"]:
            for pb in rig.pose.bones:
                if pb.name.endswith(("Bend", "Twist")):
                    self.storeConstraints(pb.name, pb)
            showProgress(2, 25, "  Connect to parent")
            connectToParent(rig, connectAll=False)
            showProgress(4, 25, "  Rename bones")
            self.deleteBendTwistDrvBones(rig)
            if not self.reuseBendTwists:
                self.joinBendTwistVGroups(rig, MHX.BendTwistGenesis38)
            self.rename2Mhx(rig)
            showProgress(5, 25, "  Join bend and twist bones")
            self.joinBendTwists(rig, {}, bendTwistBones, keep=False)
            showProgress(6, 25, "  Fix knees")
            self.fixKnees(rig)
        elif rig.DazRig == "genesis9":
            showProgress(2, 25, "  Connect to parent")
            connectToParent(rig, connectAll=False)
            showProgress(4, 25, "  Rename bones")
            if not self.reuseBendTwists:
                self.deleteBendTwistDrvBones(rig)
                self.joinBendTwistVGroups(rig, MHX.BendTwistGenesis9)
            self.rename2Mhx(rig)
        elif rig.DazRig in ["genesis", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            connectToParent(rig, connectAll=False)
            self.rename2Mhx(rig)
            self.fixGenesis2Problems(rig)
        elif rig.DazRig.endswith(".suffix"):
            raise DazError("%s has suffix bones.\nConvert to prefix before converting to MHX" % rig.name)
        else:
            raise DazError("Cannot convert %s to MHX" % rig.name)

        showProgress(7, 25, "  Fix hands")
        self.fixHands(rig)
        showProgress(8, 25, "  Store all constraints")
        self.storeAllConstraints(rig)
        showProgress(9, 25, "  Create bend and twist bones")
        self.createBendTwists(rig, bendTwistBones)
        showProgress(10, 25, "  Fix bone drivers")
        self.fixBoneDrivers(rig, rig, MHX.BoneDrivers)

        #-------------------------------------------------------------
        #   Add MHX stuff
        #-------------------------------------------------------------

        showProgress(12, 25, "  Add master bone")
        self.addMaster(rig)
        showProgress(14, 25, "  Add tweak bones")
        self.addTweaks(rig)
        showProgress(15, 25, "  Add backbone")
        self.addBack(rig)
        self.addShaftWinder(rig)
        showProgress(16, 25, "  Setup FK-IK")
        self.setupFkIk(rig)
        showProgress(13, 25, "  Add long fingers")
        self.addFingerWinders(rig)
        showProgress(17, 25, "  Add layers")
        self.addLayers(rig)
        showProgress(18, 25, "  Add markers")
        self.addMarkers(rig)
        showProgress(19, 25, "  Add gizmos")
        self.addGizmos(rig, context)
        showProgress(11, 25, "  Add tongue control")
        self.addTongueControl(rig)
        showProgress(11, 25, "  Constrain bend and twist bones")
        self.constrainBendTwists(rig, bendTwistBones)
        self.addCopyLocConstraints(rig)
        self.addChildofConstraints(rig)
        showProgress(20, 25, "  Restore constraints")
        self.restoreFixConstraints(rig)
        showProgress(21, 25, "  Fix constraints")
        deletes = self.fixConstraints(rig)
        self.fixDrivers(rig.data)
        if rig.DazRig in ["genesis3", "genesis8"]:
            self.fixCustomShape(rig, ["head"], 4)
        showProgress(22, 25, "  Collect deform bones")
        self.collectDeformBones(rig)
        setMode('POSE')
        showProgress(23, 25, "  Rename face bones")
        self.renameFaceBones(rig, ["Eye", "Ear", "_eye", "_ear"])
        showProgress(24, 25, "  Add bone groups")
        self.addBoneGroups(rig)
        rig.MhxRig = True
        rig.data.MhaFeatures |= F_IDPROPS
        T = True
        F = False
        enableRigNumLayers(rig, [L_MAIN, L_SPINE, L_LARMIK, L_LLEGIK, L_RARMIK, L_RLEGIK, L_LHAND, L_RHAND])
        rig.DazRig = "mhx"

        for pb in rig.pose.bones:
            pb.bone.select = False
            if pb.custom_shape:
                pb.bone.show_wire = True

        self.restoreBoneChildren(bchildren, context, rig)
        updateAll(context)
        if self.keepRig:
            self.tieBones(nrig, rig)
            self.setRigName(rig, nrig, "MHX")


    def fixGenesis2Problems(self, rig):
        setMode('EDIT')
        rebs = rig.data.edit_bones
        for suffix in ["L", "R"]:
            foot = rebs["foot.%s" % suffix]
            toe = rebs["toe.%s" % suffix]
            heel = rebs.new("heel.%s" % suffix)
            heel.parent = foot.parent
            heel.head = foot.head
            heel.tail = (toe.head[0], 1.5*foot.head[1]-0.5*toe.head[1], toe.head[2])
            enableBoneNumLayer(heel, rig, L_TWEAK)

    #-------------------------------------------------------------
    #   Rename bones
    #-------------------------------------------------------------

    def rename2Mhx(self, rig):
        setMode('EDIT')
        fixed = []
        for bname,pname in MHX.DrivenParents.items():
            if (bname in rig.data.edit_bones.keys() and
                pname in rig.data.edit_bones.keys()):
                eb = rig.data.edit_bones[bname]
                parb = rig.data.edit_bones[pname]
                eb.parent = parb
                enableBoneNumLayer(eb, rig, L_HELP)
                fixed.append(bname)

        setMode('OBJECT')
        for bone in rig.data.bones:
            bname = bone.name
            if bone.name in self.sacred:
                bone.name = mname = bname + ".1"
            elif bname in MHX.Skeleton.keys():
                mname,layer = MHX.Skeleton[bname]
                if bname != mname:
                    bone.name = mname
                enableBoneNumLayer(bone, rig, layer)
                fixed.append(mname)
            else:
                continue
            if bname.endswith("Bend"):
                mname = mname.replace("Bend", ".bend")
            elif bname.endswith("Twist"):
                mname = mname.replace("Twist", ".twist")
            self.renamedBones[mname] = bname

        for mname, bname in MHX.ExtraRenames:
            self.renamedBones[mname] = self.renamedBones[bname]

        for pb in rig.pose.bones:
            if pb.name in fixed:
                continue
            layer,unlock = getBoneLayer(pb, rig)
            enableBoneNumLayer(pb.bone, rig, layer)
            if False and unlock:
                pb.lock_location = (False,False,False)
        self.checkTongueIk(rig)
        self.checkFingerIk(rig)


    def restoreBoneChildren(self, bchildren, context, rig):
        from .node import setParent
        layers = getRigLayers(rig)
        enableAllRigLayers(rig)
        for (ob, bname) in bchildren:
            bone = self.getMhxBone(rig, bname)
            if bone is None and isDrvBone(bname):
                bone = self.getMhxBone(rig, baseBone(bname))
            if bone:
                setParent(context, ob, rig, bone.name)
            else:
                print("Could not restore bone parent %s for %s" % (bname, ob.name))
        setRigLayers(rig, layers)


    def getMhxBone(self, rig, bname):
        if bname in rig.data.bones.keys():
            return rig.data.bones[bname]
        if bname in MHX.Skeleton.keys():
            mname = MHX.Skeleton[bname][0]
            if mname[-2] == ".":
                if mname[-6:-2] == "Bend":
                    mname = "%s.bend.%s" % (mname[:-6],  mname[-1])
                elif mname[-7:-2] == "Twist":
                    mname = "%s.twist.%s" % (mname[:-7],  mname[-1])
            if mname in rig.data.bones.keys():
                return rig.data.bones[mname]
            else:
                print("Missing MHX bone:", bname, mname)
        return None

    #-------------------------------------------------------------
    #   Gizmos
    #-------------------------------------------------------------

    def addGizmos(self, rig, context):
        from .driver import isBoneDriven
        setMode('OBJECT')
        self.makeGizmos(True, None)

        def getData(data):
            if len(data) == 3:
                return data
            else:
                return data[0], data[1], None

        for pb in rig.pose.bones:
            if (isDrvBone(pb.name) or
                isFinal(pb.name) or
                pb.name in MHX.FaceRigs+MHX.Teeth):
                continue
            elif pb.name in Gizmos.keys():
                gizmo,scale,offset = getData(Gizmos[pb.name])
                self.addGizmo(pb, gizmo, scale, offset)
            elif pb.name[-2:] in [".L", ".R"] and pb.name[:-2] in LRGizmos.keys():
                gizmo,scale,offset = getData(LRGizmos[pb.name[:-2]])
                self.addGizmo(pb, gizmo, scale, offset)
            elif pb.name[0:6] == "tongue":
                self.addGizmo(pb, "GZM_MTongue", 1)
            elif self.isEyeLid(pb):
                self.addGizmo(pb, "GZM_Line", 1)
            elif self.isFaceBone(pb, rig):
                self.addGizmo(pb, "GZM_Circle", 0.2)
            else:
                for pname in MHX.F_Fingers + ["big_toe", "small_toe"]:
                    if pb.name.startswith(pname):
                        self.addGizmo(pb, "GZM_Circle", 0.4)
                for pname,shape,scale,offset in [
                        ("pectoral", "GZM_Ball", 0.25, 0) ,
                        ("heel", "GZM_Ball", 0.25, 1)]:
                    if pb.name.startswith(pname):
                        if isBoneDriven(rig, pb):
                            setBoneNumLayer(pb.bone, L_HELP)
                            setBoneNumLayer(pb.bone, L_TWEAK, False)
                        else:
                            self.addGizmo(pb, shape, scale, offset)

        for bname in self.tweakBones:
            if bname is None:
                continue
            twkname = self.getTweakBoneName(bname)
            if twkname in rig.pose.bones.keys():
                tb = rig.pose.bones[twkname]
                self.addGizmo(tb, "GZM_Ball", 0.25, 0.5, blen=10*rig.DazScale)

    #-------------------------------------------------------------
    #   Bone groups
    #-------------------------------------------------------------

    def addBoneGroups(self, rig):
        if not BLENDER3:
            return
        for idx,data in enumerate(MHX.BoneGroups):
            _bgname,_theme,layers = data
            bgrp = rig.pose.bone_groups[idx]
            for pb in rig.pose.bones.values():
                for layer in layers:
                    if isInNumLayer(pb.bone, rig, layer):
                        pb.bone_group = bgrp

    #-------------------------------------------------------------
    #   Fix knees
    #-------------------------------------------------------------

    def fixKnees(self, rig):
        if not (self.useFixKnees and self.usePoleTargets):
            return
        from .bone import setRoll
        eps = 0.5
        setMode('EDIT')
        for thigh,shin,zaxis in MHX.Knees:
            eb1 = rig.data.edit_bones[thigh]
            eb2 = rig.data.edit_bones[shin]
            hip = eb1.head
            knee = eb2.head
            ankle = eb2.tail
            dankle = ankle-hip
            vec = ankle-hip
            vec.normalize()
            dknee = knee-hip
            dmid = vec.dot(dknee)*vec
            offs = dknee-dmid
            if offs.length/dknee.length < eps:
                knee = hip + dmid + zaxis*offs.length
                xaxis = zaxis.cross(vec)
            else:
                xaxis = vec.cross(dknee)
                xaxis.normalize()
            eb1.tail = eb2.head = knee
            setRoll(eb1, xaxis)
            eb2.roll = eb1.roll

    #-------------------------------------------------------------
    #   Backbone
    #-------------------------------------------------------------

    def getExistingBones(self, rig, bnames):
        return [bname for bname in bnames if bname in rig.data.bones.keys()]


    def addBack(self, rig):
        backbones = self.getExistingBones(rig, MHX.BackBones)
        layers = [L_MAIN, L_SPINE, L_HELP, L_HELP2, L_DEF]
        setMhx(rig, "MhaSpineControl", True)
        if self.useSpineIk:
            rig.data.MhaFeatures |= F_SPINE
            setMhx(rig, "MhaSpineIk", 0.0)
            addSuperWinder(rig, "back", backbones, layers, "MhaSpineControl", "MhaSpineIk", master="master")
        else:
            addWinder(rig, "back", backbones, layers, "MhaSpineControl")
        setMhx(rig, "MhaNeckControl", True)
        neckbones = self.getExistingBones(rig, MHX.NeckBones)
        addWinder(rig, "neckhead", neckbones, layers, "MhaNeckControl")


    def getShaftBones(self, rig):
        def isShaft(bname):
            return (bname.lower()[0:5] == "shaft" and bname[5:].isdigit())

        return [bone.name for bone in rig.data.bones if isShaft(bone.name)]


    def addShaftWinder(self, rig):
        if self.useShaftWinder:
            setMhx(rig, "MhaShaftControl", True)
            shaftbones = self.getShaftBones(rig)
            shaftbones.sort()
            layers = [L_CUSTOM, L_CUSTOM2]
            addWinder(rig, "shaft", shaftbones, layers, "MhaShaftControl", useBaseLocation=True, useScale=True)

    #-------------------------------------------------------------
    #   Spine tweaks
    #-------------------------------------------------------------

    def addTweaks(self, rig):
        if not self.addTweakBones:
            self.tweakBones = []
            return

        self.tweakBones = [
            None, "spine", "spine-1", "chest", "chest-1",
            None, "neck", "neck-1",
            None, "pelvis",
            None, "hand.L", None, "shin.L", "foot.L",
            None, "hand.R", None, "shin.R", "foot.R",
            ]

        self.noTweakParents = [
            "spine", "spine-1", "chest", "chest-1", "neck", "neck-1", "head",
            "clavicle.L", "upper_arm.L", "hand.L", "thigh.L", "shin.L", "foot.L",
            "clavicle.R", "upper_arm.R", "hand.R", "thigh.R", "shin.R", "foot.R",
        ]

        setMode('OBJECT')
        for bname in self.tweakBones:
            self.deleteBoneDrivers(rig, bname)
        setMode('EDIT')
        for bname in self.tweakBones:
            if bname is None:
                sb = None
            elif bname in rig.data.edit_bones.keys():
                tb = rig.data.edit_bones[bname]
                tb.name = self.getTweakBoneName(bname)
                conn = tb.use_connect
                tb.use_connect = False
                enableBoneNumLayer(tb, rig, L_TWEAK)
                if sb is None:
                    sb = tb.parent
                sb = deriveBone(bname, tb, rig, L_SPINE, sb)
                setConnected(sb, conn)
                tb.parent = sb
                for eb in tb.children:
                    if eb.name in self.noTweakParents:
                        eb.parent = sb

        setMode('POSE')
        from .figure import copyBoneInfo
        rpbs = rig.pose.bones
        tweakCorrectives = {}
        for bname in self.tweakBones:
            if bname and bname in rpbs.keys():
                tname = self.getTweakBoneName(bname)
                tweakCorrectives[tname] = bname
                tb = rpbs[tname]
                pb = getBoneCopy(bname, tb, rpbs)
                copyBoneInfo(tb, pb)
                tb.lock_location = tb.lock_rotation = tb.lock_scale = (False,False,False)

        setMode('OBJECT')
        #self.fixBoneDrivers(rig, tweakCorrectives)


    def getTweakBoneName(self, bname):
        if bname[-2] == ".":
            return "%s.twk%s" % (bname[:-2], bname[-2:])
        else:
            return "%s.twk" % bname

    #-------------------------------------------------------------
    #   Fingers
    #-------------------------------------------------------------

    def linkName(self, m, n, suffix):
        return ("%s.0%d.%s" % (MHX.F_Fingers[m], n+1, suffix))


    def checkFingerIk(self, rig):
        if self.useFingerIk:
            bnames = [self.linkName(m, n, suffix) for m in range(5) for n in range(3) for suffix in ["L", "R"]]
            if self.checkDriven(rig, bnames, "Finger IK"):
                self.useFingerIk = False


    def getFingerNames(self, rig, m, suffix):
        bnames = [self.linkName(m, n, suffix) for n in range(3)]
        return [bname for bname in bnames if bname in rig.data.bones.keys()]


    def addFingerWinders(self, rig):
        if self.useFingerIk:
            rig.data.MhaFeatures |= F_FINGER
        for suffix,dlayer in [("L",0), ("R",16)]:
            prop1 = "MhaFingerControl_%s" % suffix
            setMhx(rig, prop1, True)
            if self.useFingerIk:
                prop2 = "MhaFingerIk_%s" % suffix
                setMhx(rig, prop2, 0.0)
            layers = [L_LHAND+dlayer, L_LFINGER+dlayer, L_HELP, L_HELP2, L_DEF]
            fingname = self.makeFingerMaster(rig, suffix, dlayer)
            for m in range(5):
                bnames = self.getFingerNames(rig, m, suffix)
                windname = "%s.%s" % (MHX.Fingers[m], suffix)
                fkwind,pbones = addWinder(rig, windname, bnames, layers, prop1, parname=fingname)
                fingers = rig.pose.bones[fingname]
                cns = copyRotation(fkwind, fingers, rig, space='LOCAL')
                cns.use_offset = True
                cns.influence = (0.5 if m==0 else 1.0)
                addMuteDriver(cns, rig, prop1)
                if self.useFingerIk:
                    ikname = "%s.ik.%s" % (MHX.Fingers[m], suffix)
                    addFingerIk(rig, ikname, bnames, fingname, layers, prop1, prop2)
                fkwind.lock_rotation = (False,True,False)
                lock = (False,True,False)
                for pb in pbones:
                    pb.lock_rotation = lock
                    lock = (False,True,True)


    def makeFingerMaster(self, rig, suffix, dlayer):
        hand0name = "hand0.%s" % suffix
        fingname = "fingers.%s" % suffix
        linkname = self.getFingerNames(rig, 2, suffix)[0]
        setMode('EDIT')
        hand0 = rig.data.edit_bones[hand0name]
        fingers = deriveBone(fingname, hand0, rig, L_LARMIK+dlayer, hand0)
        setBoneNumLayer(fingers, rig, L_LARMFK+dlayer)
        link = rig.data.edit_bones[linkname]
        fingers.roll = link.roll
        setMode('OBJECT')
        fingers = rig.pose.bones[fingname]
        link = rig.pose.bones[linkname]
        fingers.rotation_mode = link.rotation_mode
        fingers.lock_rotation = (False,True,True)
        return fingname

    #-------------------------------------------------------------
    #   FK/IK
    #-------------------------------------------------------------

    def setLayer(self, bname, rig, layer):
        eb = rig.data.edit_bones[bname]
        enableBoneNumLayer(eb, rig, layer)
        self.rolls[bname] = eb.roll
        return eb


    FkIk = {
        ("thigh.L", "shin.L", "foot.L"),
        ("upper_arm.L", "forearm.L", "toe.L"),
        ("thigh.R", "shin.R", "foot.R"),
        ("upper_arm.R", "forearm.R", "toe.R"),
    }

    def setupFkIk(self, rig):
        setMode('EDIT')
        hip = rig.data.edit_bones["hip"]
        master = rig.data.edit_bones["master"]
        for suffix,dlayer in [("L",0), ("R",16)]:
            upper_arm = self.setLayer("upper_arm.%s" % suffix, rig, L_HELP)
            forearm = self.setLayer("forearm.%s" % suffix, rig, L_HELP)
            hand0 = self.setLayer("hand.%s" % suffix, rig, L_DEF)
            hand0.name = "hand0.%s" % suffix
            forearm.tail = hand0.head
            vec = forearm.tail - forearm.head
            vec.normalize()
            tail = hand0.head + vec*hand0.length
            roll = normalizeRoll(forearm.roll + 90*D)
            if abs(roll - hand0.roll) > 180*D:
                roll = normalizeRoll(roll + 180*D)
            hand = makeBone("hand.%s" % suffix, rig, hand0.head, tail, roll, L_HELP, forearm)
            hand.use_connect = False
            hand0.use_connect = False
            hand0.parent = hand

            size = 10*rig.DazScale
            ez = Vector((0,0,size))
            armSocket = makeBone("armSocket.%s" % suffix, rig, upper_arm.head, upper_arm.head+ez, 0, L_LEXTRA+dlayer, upper_arm.parent)
            armParent = deriveBone("arm_parent.%s" % suffix, armSocket, rig, L_HELP, hip)
            upper_arm.parent = armParent
            bend = rig.data.edit_bones.get("upper_arm.bend.%s" % suffix)
            if bend:
                bend.parent = armParent

            upper_armFk = deriveBone("upper_arm.fk.%s" % suffix, upper_arm, rig, L_LARMFK+dlayer, armParent)
            forearmFk = deriveBone("forearm.fk.%s" % suffix, forearm, rig, L_LARMFK+dlayer, upper_armFk)
            setConnected(forearmFk, forearm.use_connect)
            handFk = deriveBone("hand.fk.%s" % suffix, hand, rig, L_LARMFK+dlayer, forearmFk)
            handFk.use_connect = False
            layer = (L_HELP2 if self.usePoleTargets else L_LARMIK+dlayer)
            upper_armIk = deriveBone("upper_arm.ik.%s" % suffix, upper_arm, rig, layer, armParent)
            forearmIk = deriveBone("forearm.ik.%s" % suffix, forearm, rig, L_HELP2, upper_armIk)
            setConnected(forearmIk, forearm.use_connect)
            if self.usePoleTargets:
                upper_armIkTwist = deriveBone("upper_arm.ik.twist.%s" % suffix, upper_arm, rig, L_LEXTRA+dlayer, upper_armIk)
            else:
                upper_armIkTwist = None
            forearmIkTwist = deriveBone("forearm.ik.twist.%s" % suffix, forearm, rig, L_LEXTRA+dlayer, forearmIk)
            handIk = deriveBone("hand.ik.%s" % suffix, hand, rig, L_LARMIK+dlayer, master)
            hand0Ik = deriveBone("hand0.ik.%s" % suffix, hand, rig, L_HELP2, forearmIkTwist)

            if self.usePoleTargets:
                vec = upper_arm.matrix.to_3x3().col[2]
                vec.normalize()
                dist = max(upper_arm.length, forearm.length)
                locElbowPt = forearm.head - 1.2*dist*vec
                elbowFac = upper_arm.length/(upper_arm.length + forearm.length)
                elbowVec = forearm.tail - upper_arm.head
                elbowHead = upper_arm.head + elbowFac*elbowVec
                elbowPoleA = makeBone("elbowPoleA.%s" % suffix, rig, armSocket.head, armSocket.head + 0.2*elbowVec, 0, L_LARMIK+dlayer, armSocket)
                elbowPoleP = makeBone("elbowPoleP.%s" % suffix, rig, elbowHead, elbowHead + 0.2*elbowVec, 0, L_HELP2, armParent)
                parent = self.getElbowParent(rig, suffix)
                elbowPt = makeBone("elbow.pt.ik.%s" % suffix, rig, locElbowPt, locElbowPt+ez, 0, L_LARMIK+dlayer, parent)
                elbowLink = makeBone("elbow.link.%s" % suffix, rig, forearm.head, locElbowPt, 0, L_LARMIK+dlayer, upper_armIk)
                if self.showLinks:
                    elbowLink.hide_select = True
                else:
                    enableBoneNumLayer(elbowLink, rig, L_HIDE)

            thigh = self.setLayer("thigh.%s" % suffix, rig, L_HELP)
            shin = self.setLayer("shin.%s" % suffix, rig, L_HELP)
            foot = self.setLayer("foot.%s" % suffix, rig, L_HELP)
            toe = self.setLayer("toe.%s" % suffix, rig, L_HELP)
            shin.tail = foot.head
            foot.tail = toe.head
            foot.use_connect = False
            setConnected(toe, True)

            legSocket = makeBone("legSocket.%s" % suffix, rig, thigh.head, thigh.head+ez, 0, L_LEXTRA+dlayer, thigh.parent)
            legParent = deriveBone("leg_parent.%s" % suffix, legSocket, rig, L_HELP, hip)
            thigh.parent = legParent
            bend = rig.data.edit_bones.get("thigh.bend.%s" % suffix)
            if bend:
                bend.parent = legParent

            thighFk = deriveBone("thigh.fk.%s" % suffix, thigh, rig, L_LLEGFK+dlayer, thigh.parent)
            shinFk = deriveBone("shin.fk.%s" % suffix, shin, rig, L_LLEGFK+dlayer, thighFk)
            setConnected(shinFk, shin.use_connect)
            footFk = deriveBone("foot.fk.%s" % suffix, foot, rig, L_LLEGFK+dlayer, shinFk)
            footFk.use_connect = False
            toeFk = deriveBone("toe.fk.%s" % suffix, toe, rig, L_LLEGFK+dlayer, footFk)
            setConnected(toeFk, True)
            layer = (L_HELP2 if self.usePoleTargets else L_LLEGIK+dlayer)
            thighIk = deriveBone("thigh.ik.%s" % suffix, thigh, rig, layer, thigh.parent)
            shinIk = deriveBone("shin.ik.%s" % suffix, shin, rig, L_HELP2, thighIk)
            setConnected(shinIk, shin.use_connect)
            if self.usePoleTargets:
                thighIkTwist = deriveBone("thigh.ik.twist.%s" % suffix, thigh, rig, L_LEXTRA+dlayer, thighIk)
            else:
                thighIkTwist = None
            shinIkTwist = deriveBone("shin.ik.twist.%s" % suffix, shin, rig, L_LEXTRA+dlayer, shinIk)

            if "heel.%s" % suffix in rig.data.edit_bones.keys():
                heel = rig.data.edit_bones["heel.%s" % suffix]
                locFootIk = (foot.head[0], heel.tail[1], toe.tail[2])
            else:
                vec = foot.tail - foot.head
                locFootIk = (foot.head[0], foot.head[1] - 0.5*vec[1], toe.tail[2])
            footIk = makeBone("foot.ik.%s" % suffix, rig, locFootIk, toe.tail, 180*D, L_LLEGIK+dlayer, master)
            toeRev = makeBone("toe.rev.%s" % suffix, rig, toe.tail, toe.head, 0, L_LLEGIK+dlayer, footIk)
            setConnected(toeRev, True)
            footRev = makeBone("foot.rev.%s" % suffix, rig, toe.head, foot.head, 0, L_LLEGIK+dlayer, toeRev)
            setConnected(footRev, True)
            locAnkle = foot.head + (shin.tail-shin.head)/4
            if self.useFoot2:
                foot2 = deriveBone("foot.2.%s" % suffix, foot, rig, L_LEXTRA+dlayer, master)
                setConnected(foot2, False)
                toe2 = deriveBone("toe.2.%s" % suffix, toe, rig, L_LEXTRA+dlayer, foot2)
                setConnected(toe2, True)
            ankleIk = deriveBone("ankle.ik.%s" % suffix, foot, rig, L_HELP2, footRev)

            if self.usePoleTargets:
                vec = thigh.matrix.to_3x3().col[2]
                vec.normalize()
                dist = max(thigh.length, shin.length)
                locKneePt = shin.head - 1.2*dist*vec
                kneeFac = thigh.length/(thigh.length + shin.length)
                kneeVec = shin.tail - thigh.head
                kneeHead = thigh.head + kneeFac*kneeVec
                kneePoleA = makeBone("kneePoleA.%s" % suffix, rig, legSocket.head, legSocket.head + 0.2*kneeVec, 0, L_LLEGIK+dlayer, legSocket)
                kneePoleP = makeBone("kneePoleP.%s" % suffix, rig, kneeHead, kneeHead + 0.2*kneeVec, 0, L_HELP2, hip)
                setBoneNumLayer(kneePoleA, rig, L_LEXTRA+dlayer)
                parent = self.getKneeParent(rig, suffix)
                kneePt = makeBone("knee.pt.ik.%s" % suffix, rig, locKneePt, locKneePt+ez, 0, L_LLEGIK+dlayer, parent)
                setBoneNumLayer(kneePt, rig, L_LEXTRA+dlayer)
                kneeLink = makeBone("knee.link.%s" % suffix, rig, shin.head, locKneePt, 0, L_LLEGIK+dlayer, thighIk)
                if self.showLinks:
                    setBoneNumLayer(kneeLink, rig, L_LEXTRA+dlayer)
                    kneeLink.hide_select = True
                else:
                    enableBoneNumLayer(kneeLink, rig, L_HIDE)

            footInvFk = deriveBone("foot.inv.fk.%s" % suffix, footRev, rig, L_HELP2, footFk)
            toeInvFk = deriveBone("toe.inv.fk.%s" % suffix, toeRev, rig, L_HELP2, toeFk)
            footInvIk = deriveBone("foot.inv.ik.%s" % suffix, foot, rig, L_HELP2, footRev)
            toeInvIk = deriveBone("toe.inv.ik.%s" % suffix, toe, rig, L_HELP2, toeRev)

            self.addSingleGazeBone(rig, suffix, L_HEAD, L_HELP)

            for bname in ["upper_arm.fk", "forearm.fk", "hand.fk",
                          "thigh.fk", "shin.fk", "foot.fk", "toe.fk"]:
                self.rolls["%s.%s" % (bname,suffix)] = rig.data.edit_bones["%s.%s" % (bname,suffix)].roll

        self.addCombinedGazeBone(rig, L_HEAD, L_HELP)
        if self.useTongueIk:
            self.addTongueIkBones(rig, L_HEAD, L_DEF)

        from .figure import copyBoneInfo
        setMode('OBJECT')
        rpbs = rig.pose.bones
        master = rpbs["master"]
        for suffix in ["L", "R"]:
            for b0name,bname in [("hand0", "hand")]:
                pb0 = rpbs["%s.%s" % (b0name, suffix)]
                pb = rpbs["%s.%s" % (bname, suffix)]
                copyBoneInfo(pb0, pb)
            for bname in ["upper_arm", "forearm", "hand",
                          "thigh", "shin", "foot", "toe"]:
                bone = rpbs["%s.%s" % (bname, suffix)]
                fkbone = rpbs["%s.fk.%s" % (bname, suffix)]
                copyBoneInfo(bone, fkbone)
                fkbone.rotation_mode = 'QUATERNION'
                bone.lock_rotation = (False, False, False)

        for bname in ["hip", "pelvis"]:
            pb = rpbs[bname]
            pb.rotation_mode = 'YZX'

        rotmodes = {
            'QUATERNION' : ["upper_arm", "upper_arm.fk", "upper_arm.ik", "thigh", "thigh.fk", "thigh.ik"],
            'YZX': ["shin", "shin.fk", "shin.ik", "thigh.ik.twist", "shin.ik.twist",
                    "forearm", "forearm.fk", "forearm.ik", "upper_arm.ik.twist", "forearm.ik.twist",
                    "foot", "foot.fk", "toe", "toe.fk", "foot.2", "toe.2",
                    "foot.rev", "toe.rev",
                    "knee.pt.ik", "elbow.pt.ik", "elbowPoleA", "kneePoleA",
                   ],
            'YXZ' : ["hand", "hand.fk", "hand.ik", "hand0.ik"],
        }
        for suffix in ["L", "R"]:
            for rmode,bnames in rotmodes.items():
                for bname in bnames:
                    pb = rpbs.get("%s.%s" % (bname,suffix))
                    if pb:
                        pb.rotation_mode = rmode

            armSocket = rpbs["armSocket.%s" % suffix]
            armParent = rpbs["arm_parent.%s" % suffix]
            upper_arm = rpbs["upper_arm.%s" % suffix]
            forearm = rpbs["forearm.%s" % suffix]
            hand = rpbs["hand.%s" % suffix]
            upper_armFk = getBoneCopy("upper_arm.fk.%s" % suffix, upper_arm, rpbs)
            forearmFk = getBoneCopy("forearm.fk.%s" % suffix, forearm, rpbs)
            handFk = getBoneCopy("hand.fk.%s" % suffix, hand, rpbs)
            upper_armIk = rpbs["upper_arm.ik.%s" % suffix]
            forearmIk = rpbs["forearm.ik.%s" % suffix]
            upper_armIkTwist = rpbs.get("upper_arm.ik.twist.%s" % suffix, upper_armIk)
            forearmIkTwist = rpbs["forearm.ik.twist.%s" % suffix]
            handIk = rpbs["hand.ik.%s" % suffix]
            hand0Ik = rpbs["hand0.ik.%s" % suffix]

            prop = "MhaArmHinge_%s" % suffix
            setMhx(rig, prop, 0.0)
            cns = copyTransform(armParent, armSocket, rig)
            addDriver(cns, "influence", rig, mhxProp(prop), "1-x")
            cns = copyLocation(armParent, armSocket, rig)
            addDriver(cns, "influence", rig, mhxProp(prop), "x")

            ikprop = "MhaArmIk_%s" % suffix
            setMhx(rig, ikprop, 1.0)
            copyTransformFkIk(upper_arm, upper_armFk, upper_armIkTwist, rig, ikprop)
            copyTransformFkIk(forearm, forearmFk, forearmIkTwist, rig, ikprop)
            copyTransformFkIk(hand, handFk, handIk, rig, ikprop)
            copyTransform(hand0Ik, handIk, rig)

            addHint(forearmIk, rig)
            if self.usePoleTargets:
                elbowPt = rpbs["elbow.pt.ik.%s" % suffix]
                elbowLink = rpbs["elbow.link.%s" % suffix]
                elbowPoleA = rpbs["elbowPoleA.%s" % suffix]
                elbowPoleP = rpbs["elbowPoleP.%s" % suffix]
                elbowPoleA.lock_location = (True,True,True)
                elbowPoleA.lock_rotation = (True,False,True)
                dampedTrack(elbowPoleA, handIk, rig)
                cns = copyLocation(elbowPoleA, handIk, rig)
                cns.influence = elbowFac
                copyTransform(elbowPoleP, elbowPoleA, rig)
                if not self.useChildOfConstraints:
                    setMhx(rig, "MhaElbowParent_%s" % suffix, self.elbowParent)
                ikConstraint(forearmIk, handIk, elbowPt, -90, 2, rig)
                stretchTo(elbowLink, elbowPt, rig)
                elbowPt.rotation_euler[0] = -90*D
                elbowPt.lock_rotation = (True,True,True)
            else:
                ikConstraint(forearmIk, handIk, None, 0, 2, rig)

            prop = "MhaForearmFollow_%s" % suffix
            setMhx(rig, prop, True)
            cns1 = copyRotation(forearm, handFk, rig, space='LOCAL')
            cns2 = copyRotation(forearm, hand0Ik, rig, ikprop, space='LOCAL')
            cns1.use_x = cns1.use_z = cns2.use_x = cns2.use_z = False
            addMuteDriver(cns1, rig, prop)
            addMuteDriver(cns2, rig, prop)
            forearmFk.lock_rotation[1] = True
            addDriver(forearmFk, "lock_rotation", rig, mhxProp(prop), "x", index=1)

            legSocket = rpbs["legSocket.%s" % suffix]
            legParent = rpbs["leg_parent.%s" % suffix]
            thigh = rpbs["thigh.%s" % suffix]
            shin = rpbs["shin.%s" % suffix]
            foot = rpbs["foot.%s" % suffix]
            toe = rpbs["toe.%s" % suffix]
            if self.useFoot2:
                foot2 = rpbs["foot.2.%s" % suffix]
                toe2 = rpbs["toe.2.%s" % suffix]
            ankleIk = rpbs["ankle.ik.%s" % suffix]
            thighFk = getBoneCopy("thigh.fk.%s" % suffix, thigh, rpbs)
            shinFk = getBoneCopy("shin.fk.%s" % suffix, shin, rpbs)
            footFk = getBoneCopy("foot.fk.%s" % suffix, foot, rpbs)
            toeFk = getBoneCopy("toe.fk.%s" % suffix, toe, rpbs)
            thighIk = rpbs["thigh.ik.%s" % suffix]
            shinIk = rpbs["shin.ik.%s" % suffix]
            thighIkTwist = rpbs.get("thigh.ik.twist.%s" % suffix, thighIk)
            shinIkTwist = rpbs["shin.ik.twist.%s" % suffix]
            footIk = rpbs["foot.ik.%s" % suffix]
            toeRev = rpbs["toe.rev.%s" % suffix]
            footRev = rpbs["foot.rev.%s" % suffix]
            footInvIk = rpbs["foot.inv.ik.%s" % suffix]
            toeInvIk = rpbs["toe.inv.ik.%s" % suffix]

            prop = "MhaLegHinge_%s" % suffix
            setMhx(rig, prop, 0.0)
            cns = copyTransform(legParent, legSocket, rig)
            addDriver(cns, "influence", rig, mhxProp(prop), "1-x")
            cns = copyLocation(legParent, legSocket, rig)
            addDriver(cns, "influence", rig, mhxProp(prop), "x")

            prop1 = "MhaLegIk_%s" % suffix
            setMhx(rig, prop1, 1.0)
            if self.useFoot2:
                prop2 = "MhaLegIkToAnkle_%s" % suffix
                setMhx(rig, prop2, False)
            else:
                prop2 = None

            footRev.lock_rotation = (False,True,True)
            copyTransformFkIk(thigh, thighFk, thighIkTwist, rig, prop1)
            copyTransformFkIk(shin, shinFk, shinIkTwist, rig, prop1)
            copyTransformFkIk(foot, footFk, footInvIk, rig, prop1, prop2)
            copyTransformFkIk(toe, toeFk, toeInvIk, rig, prop1, prop2)

            addHint(shinIk, rig)
            if self.usePoleTargets:
                kneePt = rpbs["knee.pt.ik.%s" % suffix]
                kneeLink = rpbs["knee.link.%s" % suffix]
                kneePoleA = rpbs["kneePoleA.%s" % suffix]
                kneePoleP = rpbs["kneePoleP.%s" % suffix]
                kneePoleA.lock_location = (True,True,True)
                kneePoleA.lock_rotation = (True,False,True)
                dampedTrack(kneePoleA, ankleIk, rig)
                cns = copyLocation(kneePoleA, ankleIk, rig)
                cns.influence = kneeFac
                copyTransform(kneePoleP, kneePoleA, rig)
                if not self.useChildOfConstraints:
                    setMhx(rig, "MhaKneeParent_%s" % suffix, self.kneeParent)

                ikConstraint(shinIk, ankleIk, kneePt, -90, 2, rig)
                stretchTo(kneeLink, kneePt, rig)
                kneePt.rotation_euler[0] = 90*D
                kneePt.lock_rotation = (True,True,True)
                if self.useFoot2:
                    copyTransform(ankleIk, foot2, rig, prop2)
                    copyTransform(foot, foot2, rig, prop2)
                    copyTransform(toe, toe2, rig, prop2)
            else:
                ikConstraint(shinIk, ankleIk, None, 0, 2, rig)

            self.addGazeConstraint(rig, suffix)

            locks = [
                upper_armFk, forearmFk,
                upper_armIk, forearmIk, upper_armIkTwist, forearmIkTwist,
                thighFk, shinFk, toeFk,
                thighIk, shinIk, thighIkTwist, shinIkTwist, footRev, toeRev,
            ]
            if self.usePoleTargets:
                locks += [elbowLink, kneeLink]
            self.lockLocations(locks)
            handFk.lock_location = footFk.lock_location = (False,False,False)
            setMhx(rig, "MhaToeTarsal_%s" % suffix, False)

        self.addGazeFollowsHead(rig)
        setMhx(rig, "MhaLimitsOn", True)


    def lockLocations(self, bones):
        for pb in bones:
            lock = (not pb.bone.use_connect)
            pb.lock_location = (lock,lock,lock)

    #-------------------------------------------------------------
    #   Restore constraints for bend-twist bones
    #-------------------------------------------------------------

    def restoreFixConstraints(self, rig):
        def getLimitRot(clist):
            for elt in clist:
                if elt["type"] == 'LIMIT_ROTATION':
                    return elt

        ignore = []
        if self.useSpineIk:
            ignore += MHX.BackBones + MHX.NeckBones
        if self.useFingerIk:
            for m in range(5):
                for suffix in ["L", "R"]:
                    ignore += self.getFingerNames(rig, m, suffix)
        if self.useTongueIk:
            ignore += self.tongueBones
        if self.useShaftWinder:
            ignore += self.getShaftBones(rig)
        self.restoreAllConstraints(rig, ignore)
        if rig.DazRig not in ["genesis3", "genesis8"]:
            return
        for bname, bendname, twistnames in MHX.BendTwistGenesis38:
            clist = self.constraints.get(bendname, [])
            cinfo = getLimitRot(clist)
            if not cinfo:
                continue
            twistname = twistnames[0]
            clist1 = self.constraints.get(twistname, [])
            cinfo1 = getLimitRot(clist1)
            if cinfo1:
                for key in ["use_limit_y", "min_y", "max_y"]:
                    cinfo[key] = cinfo1[key]
            pb = rig.pose.bones.get("%s.fk.%s" % (bname[:-2], bname[-1]))
            self.restoreConstraint(cinfo, pb)

    #-------------------------------------------------------------
    #   Toggle constraints
    #-------------------------------------------------------------

    def addCopyLocConstraints(self, rig):
        for suffix in ["L", "R"]:
            for bname,part in [
                ("hand", "Arm"),
                ("hand.fk", "Arm"),
                ("foot", "Leg"),
                ("foot.fk", "Leg")]:
                prop = "Mha%sStretch_%s" % (part, suffix)
                setMhx(rig, prop, 0.0)
                pb = rig.pose.bones["%s.%s" % (bname, suffix)]
                cns = copyLocation(pb, pb.parent, rig, prop, "1-x")
                cns.head_tail = 1.0


    def getElbowParent(self, rig, suffix):
        if self.useChildOfConstraints:
            return None
        elif self.elbowParent == 'HAND':
            bname = "elbowPoleP.%s" % suffix
        elif self.elbowParent == 'SHOULDER':
            bname = "arm_parent.%s" % suffix
        else:
            bname = "master"
        return rig.data.edit_bones[bname]


    def getKneeParent(self, rig, suffix):
        if self.useChildOfConstraints:
            return None
        elif self.kneeParent == 'FOOT':
            bname = "kneePoleP.%s" % suffix
        elif self.kneeParent == 'HIP':
            bname = "hip"
        else:
            bname = "master"
        return rig.data.edit_bones[bname]


    def addChildofConstraints(self, rig):
        if not self.useChildOfConstraints:
            return
        rig.MhxChildOfConstraints = True
        for suffix in ["L", "R"]:
            handprop = "MhaElbowHand_%s" % suffix
            shoulderprop = "MhaElbowShoulder_%s" % suffix
            setMhx(rig, handprop, (float)(self.elbowParent=='HAND'))
            setMhx(rig, shoulderprop, (float)(self.elbowParent=='SHOULDER'))
            pb = rig.pose.bones["elbow.pt.ik.%s" % suffix]
            cns = childOf(pb, "master", rig, (handprop, shoulderprop), "1-min(1,x1+x2)")
            cns.name = "ChildOf Master"
            cns = childOf(pb, "elbowPoleP.%s" % suffix, rig, handprop, "x")
            cns.name = "ChildOf Hand"
            cns = childOf(pb, "arm_parent.%s" % suffix, rig, shoulderprop, "x")
            cns.name = "ChildOf Shoulder"

            footprop = "MhaKneeFoot_%s" % suffix
            hipprop = "MhaKneeHip_%s" % suffix
            setMhx(rig, footprop, (float)(self.kneeParent=='FOOT'))
            setMhx(rig, hipprop, (float)(self.kneeParent=='HIP'))
            pb = rig.pose.bones["knee.pt.ik.%s" % suffix]
            cns = childOf(pb, "master", rig, (footprop, hipprop), "1-min(1,x1+x2)")
            cns.name = "ChildOf Master"
            cns = childOf(pb, "kneePoleP.%s" % suffix, rig, footprop, "x")
            cns.name = "ChildOf Foot"
            cns = childOf(pb, "hip", rig, hipprop, "x")
            cns.name = "ChildOf Hip"

    #-------------------------------------------------------------
    #   Fix constraints -
    #-------------------------------------------------------------

    def fixConstraints(self, rig):
        self.flips = {}
        for suffix in ["L", "R"]:
            self.unlockYrot(rig, "upper_arm.fk.%s" % suffix)
            self.unlockYrot(rig, "forearm.fk.%s" % suffix)
            self.unlockYrot(rig, "thigh.fk.%s" % suffix)
            self.copyIkLimits(rig, "upper_arm", suffix)
            self.copyIkLimits(rig, "forearm", suffix)
            self.copyIkLimits(rig, "thigh", suffix)
            self.copyIkLimits(rig, "shin", suffix)
            if self.useFoot2:
                self.copyLocksLimits(rig, "toe.fk", "toe.2", suffix)
            self.flipLimits(rig, "upper_arm.fk.%s" % suffix, "upper_arm.%s" % suffix)
            self.flipLimits(rig, "forearm.fk.%s" % suffix, "forearm.%s" % suffix)
            self.flipLimits(rig, "hand.fk.%s" % suffix, "hand.%s" % suffix)
            self.flipLimits(rig, "thigh.fk.%s" % suffix, "thigh.%s" % suffix)
            self.flipLimits(rig, "shin.fk.%s" % suffix, "shin.%s" % suffix)
            self.flipLimits(rig, "foot.fk.%s" % suffix, "foot.%s" % suffix)
            self.flipLimits(rig, "toe.fk.%s" % suffix, "toe.%s" % suffix)
            self.driveYrot(rig, "hand.fk.%s" % suffix, "MhaForearmFollow_%s" % suffix)
            self.copyToeRotation(rig, True, suffix, ["big_toe.01", "small_toe_1.01", "small_toe_2.01", "small_toe_3.01", "small_toe_4.01"])


    def flipLimits(self, rig, bname, oldname):
        roll = self.rolls[bname]
        oldroll = self.rolls[oldname]
        flip = round(2*(roll-oldroll)/math.pi)
        if flip:
            self.flips[bname.replace(".fk", "")] = flip
            pb = rig.pose.bones[bname]
            flips = list(pb.DazFlips)
            axes = [2,1,0]
            for n,i in enumerate(list(pb.DazAxes)):
                j = axes[i]
                pb.DazAxes[n] = j
                pb.DazFlips[n] = flips[j]
            cns = getConstraint(pb, 'LIMIT_ROTATION')
            if cns:
                usex, minx, maxx = cns.use_limit_x, cns.min_x, cns.max_x
                usez, minz, maxz = cns.use_limit_z, cns.min_z, cns.max_z
                if flip == -1:
                    cns.use_limit_x, cns.min_x, cns.max_x = usez, minz, maxz
                    cns.use_limit_z, cns.min_z, cns.max_z = usex, -maxx, -minx
                elif flip == 1:
                    cns.use_limit_x, cns.min_x, cns.max_x = usez, -maxz, -minz
                    cns.use_limit_z, cns.min_z, cns.max_z = usex, minx, maxx
                elif flip == 2 or flip == -2:
                    cns.use_limit_x, cns.min_x, cns.max_x = usex, -maxx, -minx
                    cns.use_limit_z, cns.min_z, cns.max_z = usez, -maxz, -minz


    def unlockYrot(self, rig, bname):
        pb = rig.pose.bones[bname]
        pb.lock_rotation[1] = False
        cns = getConstraint(pb, 'LIMIT_ROTATION')
        if cns:
            cns.use_limit_y = True
            cns.min_y = -90*D
            cns.max_y = 90*D


    def driveYrot(self, rig, bname, prop):
        pb = rig.pose.bones[bname]
        cns = getConstraint(pb, 'LIMIT_ROTATION')
        if cns:
            addDriver(cns, "use_limit_y", rig, mhxProp(prop), "not(x)")


    def copyIkLimits(self, rig, bname, suffix):
        iktwist = rig.pose.bones.get("%s.ik.twist.%s" % (bname, suffix))
        if iktwist:
            iktwist.lock_rotation = (True,False,True)
        fkbone = rig.pose.bones["%s.fk.%s" % (bname, suffix)]
        ikbone = rig.pose.bones["%s.ik.%s" % (bname, suffix)]
        ikbone.lock_ik_x = fkbone.lock_rotation[0]
        ikbone.lock_ik_y = fkbone.lock_rotation[1]
        ikbone.lock_ik_z = fkbone.lock_rotation[2]

    #-------------------------------------------------------------
    #   Fix drivers
    #-------------------------------------------------------------

    def fixDrivers(self, rna):
        table = {
            "hand0.L" : "hand.L",
            "hand0.R" : "hand.R",
        }
        def getBaseBone(bname):
            if ".twk" in bname:
                return bname.replace(".twk", "")
            else:
                return table.get(bname)

        def flipString(string):
            if string[0:6] == "clamp(":
                expr,limits = string[6:].split(",",1)
                return "clamp(-(%s),%s" % (expr,limits)
            else:
                return "-(%s)" % string

        if rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    bname = getBaseBone(trg.bone_target)
                    if bname is not None:
                        trg.bone_target = bname
                        if bname in self.flips.keys():
                            flip = self.flips[bname]
                            if trg.transform_type == "ROT_X":
                                trg.transform_type = "ROT_Z"
                                if flip == -1:
                                    fcu.driver.expression = flipString(fcu.driver.expression)
                            elif trg.transform_type == "ROT_Z":
                                trg.transform_type = "ROT_X"
                                if flip == 1:
                                    fcu.driver.expression = flipString(fcu.driver.expression)

    #-------------------------------------------------------------
    #   Markers
    #-------------------------------------------------------------

    def addMarkers(self, rig):
        for suffix,dlayer in [("L",0), ("R",16)]:
            setMode('EDIT')
            foot = rig.data.edit_bones["foot.%s" % suffix]
            toe = rig.data.edit_bones["toe.%s" % suffix]
            offs = Vector((0, 0, 0.5*toe.length))
            if "heel.%s" % suffix in rig.data.edit_bones.keys():
                heelTail = rig.data.edit_bones["heel.%s" % suffix].tail
            else:
                heelTail = Vector((foot.head[0], foot.head[1], toe.head[2]))

            ballLoc = Vector((toe.head[0], toe.head[1], heelTail[2]))
            mBall = makeBone("ball.marker.%s" % suffix, rig, ballLoc, ballLoc+offs, 0, L_LEXTRA+dlayer, foot)
            toeLoc = Vector((toe.tail[0], toe.tail[1], heelTail[2]))
            mToe = makeBone("toe.marker.%s" % suffix, rig, toeLoc, toeLoc+offs, 0, L_LEXTRA+dlayer, toe)
            mHeel = makeBone("heel.marker.%s" % suffix, rig, heelTail, heelTail+offs, 0, L_LEXTRA+dlayer, foot)

    #-------------------------------------------------------------
    #   Master bone
    #-------------------------------------------------------------

    def addMaster(self, rig):
        setMode('EDIT')
        hip = rig.data.edit_bones["hip"]
        master = makeBone("master", rig, (0,0,0), (0,hip.head[2]/5,0), 0, L_MAIN, None)
        hip.parent = master
        return
        for eb in rig.data.edit_bones:
            if (eb.parent is None and
                eb != master and
                eb.name not in self.noparents):
                eb.parent = master

    #-------------------------------------------------------------
    #   Move all deform bones to layer 31
    #-------------------------------------------------------------

    def collectDeformBones(self, rig):
        setMode('OBJECT')
        for bone in rig.data.bones:
            if bone.use_deform:
                setBoneNumLayer(bone, rig, L_DEF)


    def addLayers(self, rig):
        setMode('OBJECT')
        for suffix,dlayer in [("L",0), ("R",16)]:
            clavicle = rig.data.bones["clavicle.%s" % suffix]
            setBoneNumLayer(clavicle, rig, L_SPINE)
            setBoneNumLayer(clavicle, rig, L_LARMIK+dlayer)

    #-------------------------------------------------------------
    #   Tie bone
    #-------------------------------------------------------------

    def tieBone(self, pb, gen, assoc, facebones, rigtype):
        rname = assoc.get(pb.name, pb.name)
        rb = gen.pose.bones.get(rname)
        if rb is None:
            print('Cannot tie "%s" to "%s"' % (pb.name, rname))
            return
        if (not pb.parent or
            rb.name.startswith(("hand0.", "foot."))):
            space = 'POSE'
        elif pb.name in facebones:
            space = 'LOCAL'
        else:
            space = 'POSE'
        if ".twist" in rb.name:
            cns = copyRotation(pb, rb, gen, space='LOCAL')
        else:
            cns = copyTransform(pb, rb, gen, space=space)

    #-------------------------------------------------------------
    #   Error on missing bone
    #-------------------------------------------------------------

    def raiseError(self, bname):
        msg = "No %s bone" % bname
        if self.useRaiseError:
            raise DazError(msg)
        else:
            print(msg)

#-------------------------------------------------------------
#   getBoneLayer, connectToParent used by Rigify
#-------------------------------------------------------------

def getBoneLayer(pb, rig):
    from .driver import isBoneDriven
    lname = pb.name.lower()
    if pb.name in MHX.HeadBones:
        return L_HEAD, False
    elif (isDrvBone(pb.name) or
        isBoneDriven(rig, pb) or
        pb.name in MHX.FaceRigs):
        return L_HELP, False
    elif pb.name in MHX.Teeth:
        return L_TWEAK, False
    elif isFinal(pb.name) or isInNumLayer(pb.bone, rig, L_FIN):
        return L_FIN, False
    elif pb.name[0:6] == "tongue":
        return L_FACE, False
    elif pb.parent:
        par = pb.parent
        if par.name in MHX.FaceRigs:
            return L_FACE, True
        elif (isDrvBone(par.name) and
              par.parent and
              par.parent.name in MHX.FaceRigs):
            return L_FACE, True
    return L_CUSTOM, True


def connectToParent(rig, connectAll=False, useSplitShin=False):
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


def setConnected(eb, conn):
    if eb.tail != eb.parent.tail:
        eb.use_connect = conn

#-------------------------------------------------------------
#   Gizmos used by winders
#-------------------------------------------------------------

Gizmos = {
    "master" :          ("GZM_Master", 1),
    "back" :            ("GZM_Knuckle", 1),
    "ik_back" :         ("GZM_CrownHips", 0.3),
    "neckhead" :        ("GZM_Knuckle", 1),
    "ik_neckhead" :     ("GZM_CrownHips", 0.3),
    "tongue" :          ("GZM_Knuckle", 1),
    "ik_tongue" :       ("GZM_Cone", -0.2),
    "shaft" :           ("GZM_Knuckle", 1),
    "ik_shaft" :        ("GZM_Cone", -0.2),

    #Spine
    "root" :            ("GZM_CrownHips", 1),
    "hip" :             ("GZM_CrownHips", 1),
    "hips" :            ("GZM_CircleHips", 1),
    "pelvis" :          ("GZM_CircleHips", 1),
    "spine" :           ("GZM_CircleSpine", 1),
    "spine-1" :         ("GZM_CircleSpine", 1),
    "chest" :           ("GZM_CircleChest", 1),
    "chest-1" :         ("GZM_CircleChest", 1),
    "neck" :            ("GZM_MNeck", 1),
    "neck-1" :          ("GZM_MNeck", 1),
    "head" :            ("GZM_MHead", 1),
    "lowerJaw" :        ("GZM_MJaw", 1),
    "lowerjaw" :        ("GZM_MJaw", 1),
    "eye.R" :           ("GZM_Circle", 0.25),
    "eye.L" :           ("GZM_Circle", 0.25),
    "ear.R" :           ("GZM_Circle", 0.375),
    "ear.L" :           ("GZM_Circle", 0.375),
    "gaze" :            ("GZM_Gaze", 1),
}

LRGizmos = {
    "pectoral" :        ("GZM_Pectoral", 1),
    "clavicle" :        ("GZM_Ball", 0.25, 1),

    # Head

    "gaze" :            ("GZM_Circle", 0.25),
    "uplid" :           ("GZM_UpLid", 1),
    "lolid" :           ("GZM_LoLid", 1),

    # Leg

    "thigh.fk" :        ("GZM_Circle", 0.25, 0.5),
    "shin.fk" :         ("GZM_Circle", 0.25, 0.5),
    "thigh.ik":         ("GZM_Arrows", 1),
    "thigh.ik.twist":   ("GZM_Circle", 0.25, 0.5),
    "shin.ik.twist" :   ("GZM_Circle", 0.25, 0.5),
    "foot.fk" :         ("GZM_Foot", 1),
    "toe.fk" :          ("GZM_Toe", 1),
    "legSocket" :       ("GZM_Cube", 0.25),
    "foot.rev" :        ("GZM_FootRev", 1),
    "foot.ik" :         ("GZM_FootIK", 1),
    "toe.rev" :         ("GZM_ToeRev", 1),
    "foot.2" :          ("GZM_Foot", 1),
    "toe.2" :           ("GZM_Toe", 1),
    "knee.pt.ik" :      ("GZM_Cone", 0.25),
    "kneePoleA" :       ("GZM_Knuckle", 1),
    "knee.link" :       ("GZM_Line", 1),
    "toe.marker" :      ("GZM_Ball", 0.25),
    "ball.marker" :     ("GZM_Ball", 0.25),
    "heel.marker" :     ("GZM_Ball", 0.25),
    "ankle.ik" :        ("GZM_Ball", 0.25),

    # Arm
    "clavicle" :        ("GZM_Shoulder", 1),
    "upper_arm.fk" :    ("GZM_Circle", 0.25, 0.5),
    "forearm.fk" :      ("GZM_Circle", 0.25, 0.5),
    "upper_arm.ik" :    ("GZM_Arrows", 1),
    "upper_arm.ik.twist" :  ("GZM_Circle", 0.25, 0.5),
    "forearm.ik.twist" :    ("GZM_Circle", 0.25, 0.5),
    "hand.fk" :         ("GZM_Hand", 1),
    "handTwk" :         ("GZM_Circle", 0.4),
    "armSocket" :       ("GZM_Cube", 0.25),
    "hand.ik" :         ("GZM_HandIK", 1),
    "elbow.pt.ik" :     ("GZM_Cone", 0.25),
    "elbowPoleA" :      ("GZM_Knuckle", 1),
    "elbow.link" :      ("GZM_Line", 1),

    # Finger
    "thumb" :           ("GZM_Knuckle", 1),
    "index" :           ("GZM_Knuckle", 1),
    "middle" :          ("GZM_Knuckle", 1),
    "ring" :            ("GZM_Knuckle", 1),
    "pinky":            ("GZM_Knuckle", 1),

    "thumb.ik" :        ("GZM_Cone", 0.2),
    "index.ik" :        ("GZM_Cone", 0.2),
    "middle.ik" :       ("GZM_Cone", 0.2),
    "ring.ik" :         ("GZM_Cone", 0.2),
    "pinky.ik":         ("GZM_Cone", 0.2),

    "fingers" :         ("GZM_Cube", (0.4,0.5,0.1), 0.5),
    }

#-------------------------------------------------------------
#   Set all limbs to FK.
#   Used by load pose etc.
#-------------------------------------------------------------

def setToFk(rig, layers, useInsertKeys, frame):
    def setValue(rig, prop, value):
        if hasattr(rig, prop):
            setattr(rig, prop, value)
            if useInsertKeys:
                rig.keyframe_insert(prop, frame=frame)
        elif prop in rig.keys():
            rig[prop] = value
            if useInsertKeys:
                rig.keyframe_insert(propRef(prop), frame=frame)
        elif prop in rig.data.keys():
            rig.data[prop] = value
            if useInsertKeys:
                rig.data.keyframe_insert(propRef(prop), frame=frame)

    for prop in ["MhaArmIk_L", "MhaArmIk_R", "MhaLegIk_L", "MhaLegIk_R", "MhaSpineIk", "MhaTongueIK", "MhaShaftIK"]:
        setValue(rig, prop, 0.0)
    for prop in ["MhaTongueIk", "MhaFingerIk_L", "MhaFingerIk_R"]:
        setValue(rig, prop, 0)
    for prop in ["MhaForearmFollow_L", "MhaForearmFollow_R"]:
        setValue(rig, prop, False)
    if BLENDER3:
        for layer in [L_LARMFK, L_RARMFK, L_LLEGFK, L_RLEGFK]:
            layers[layer] = True
        for layer in [L_LARMIK, L_RARMIK, L_LLEGIK, L_RLEGIK]:
            layers[layer] = False
    else:
        for cname in ["FK Arm Left", "FK Arm Right", "FK Leg Left", "FK Leg Right"]:
            layers[cname] = rig.data.collections.get(cname)
        for cname in ["IK Arm Left", "IK Arm Right", "IK Leg Left", "IK Leg Right"]:
            if cname in layers.keys():
                del layers[cname]
    return layers


def updateWinders(rig, frame):
    winders = ["back"]
    for suffix in ["L", "R"]:
        winders += ["%s.%s" % (fing, suffix) for fing in MHX.Fingers]
    for bname in winders:
        revwind = rig.pose.bones.get("REV-%s" % bname)
        ikwind = rig.pose.bones.get("ik_%s" % bname)
        if revwind and ikwind:
            ikwind.matrix = revwind.matrix

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DAZ_OT_ConvertToMhx,
]

def register():
    bpy.types.Object.DazMhxLegacy = BoolProperty(default = True)
    bpy.types.Object.MhxRig = BoolProperty(default = False)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
