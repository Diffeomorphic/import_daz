# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

import math
from mathutils import *
from ..error import *
from ..utils import *
from ..propgroups import DazPairGroup
from ..driver import addDriver
from ..store import ConstraintStore
from ..fix import BendTwists, Fixer, GizmoUser
from ..bone_data import BD
from ..rig_utils import *
from .layers import *
from .mhx_data import MHX

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getBoneCopy(bname, model, rpbs, lock):
    pb = rpbs[bname]
    pb.DazRotMode = model.DazRotMode
    pb.rotation_mode = model.rotation_mode
    if lock:
        pb.lock_location = TTrue
    return pb


def addFingerIk(rig, ikname, bnames, parname, layers, prop1, prop2):
    nbones = len(bnames)
    if nbones < 2:
        return
    setMode('EDIT')
    parent = rig.data.edit_bones[parname]
    last = rig.data.edit_bones[bnames[-1]]
    makeBone(ikname, rig, last.tail, 2*last.tail-last.head, last.roll, layers[0], parent)
    setMode('OBJECT')
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

def applyBoneChildren(context, rig):
    from ..node import clearParent
    unhideAllObjects(context, rig)
    bonechildren = []
    for ob in rig.children:
        if ob.parent_type == 'BONE':
            bonechildren.append((ob, ob.parent_bone))
            clearParent(ob)
    return bonechildren

#-------------------------------------------------------------
#   Convert to MHX button
#-------------------------------------------------------------

class DAZ_OT_ConvertToMhx(DazPropsOperator, ConstraintStore, BendTwists, Fixer, GizmoUser):
    bl_idname = "daz.convert_to_mhx"
    bl_label = "Convert To MHX"
    bl_description = "Convert rig to MHX"
    bl_options = {'UNDO', 'PRESET'}

    gizmoFile = "mhx"
    useQuaternions = True

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

    useStretch : BoolProperty(
        name = "Stretchy Limbs",
        description = "Enable stretchiness for arms and legs",
        default = True)

    useSpineIk : BoolProperty(
        name = "Spine IK",
        description = "Spine IK (experimental)",
        default = True)

    useShaftWinder : BoolProperty(
        name = "Shaft Winder",
        description = "Add windoer for Dicktator/Futalicious shaft",
        default = False)

    shaftName : StringProperty(
        name = "Shaft Name",
        description = "Shaft bones start with this string (case insensitive)",
        default = "Shaft")

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

    useAnkleIk : BoolProperty(
        name = "Ankle IK",
        description = "Add extra foot and toe bones as IK targets",
        default = False)

    keepG9Twist : BoolProperty(
        name = "Keep Genesis 9 Twist Bones",
        description = "Keep the original twist bones for Genesis 9.\nNecessary for reexport to DAZ Studio but may lead to flipping",
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
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.get("DazSimpleIK"))

    def __init__(self):
        ConstraintStore.__init__(self)
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "usePoleTargets")
        if self.usePoleTargets:
            self.layout.prop(self, "showLinks")
            self.layout.prop(self, "elbowParent")
            self.layout.prop(self, "kneeParent")
        self.layout.prop(self, "useStretch")
        self.layout.prop(self, "addTweakBones")
        self.drawMeta()
        self.layout.prop(self, "useSpineIk")
        self.layout.prop(self, "useTongueIk")
        self.layout.prop(self, "useShaftWinder")
        if self.useShaftWinder:
            self.layout.prop(self, "shaftName")
        self.layout.prop(self, "useAnkleIk")
        self.layout.prop(self, "driverRotationMode")
        self.layout.prop(self, "keepG9Twist")
        self.layout.prop(self, "useRaiseError")


    def invoke(self, context, event):
        self.createBoneGroups(context.object)
        return DazPropsOperator.invoke(self, context, event)


    def storeState(self, context):
        from ..driver import muteDazFcurves
        DazPropsOperator.storeState(self, context)
        muteDazFcurves(self.activeObject, True)


    def restoreState(self, context):
        from ..driver import muteDazFcurves
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
        from ..figure import finalizeArmature
        rig = context.object
        self.rigname = rig.name
        rig.DazMhxLegacy = False
        self.makeRealParents(context, rig)
        self.meshes = getMeshChildren(rig)
        if self.keepRig:
            nrig = self.saveDazRig(context)
        else:
            nrig = None
        self.storeAllDrivers(rig, nrig, self.meshes)
        finalizeArmature(rig)
        clearBoneCollections(rig, [T_BONES, T_HIDDEN])
        enableAllRigLayers(rig, False)
        makeBoneCollections(rig, MhxLayers)
        self.createBoneGroups(rig)
        self.startGizmos(context, rig)
        self.sacred = ["root", "hips", "spine"]
        self.rolls = {}

        #-------------------------------------------------------------
        #   Fix and rename bones of the genesis rig
        #-------------------------------------------------------------

        showProgress(1, 25, "  Fix DAZ rig")
        useBendTwist = True
        self.bendTwistGenesis = []
        bendTwistBones = list(MHX.BendTwistBones)
        bendTwistChildren = {}
        self.constraints = {}
        enableAllRigLayers(rig)
        bonechildren = applyBoneChildren(context, rig)
        for pb in rig.pose.bones:
            pb.driver_remove("HdOffset")
            pb.driver_remove("TlOffset")
        if rig.DazRig in ["genesis3", "genesis8"]:
            self.bendTwistGenesis = MHX.BendTwistGenesis38
            for pb in rig.pose.bones:
                if pb.name.endswith(("Bend", "Twist")):
                    self.storeConstraints(pb.name, pb)
            showProgress(2, 25, "  Connect to parent")
            connectToParent(rig, connectAll=False)
            showProgress(3, 25, "  Delete bend-twist bones")
            self.deleteBendTwistDrvBones(rig)
            showProgress(4, 25, "  Rename bones")
            self.rename2Mhx(rig)
            showProgress(5, 25, "  Join bend and twist bones")
            bendTwistChildren = self.joinBendTwists(rig, {}, bendTwistBones, keep=False)
            showProgress(6, 25, "  Fix knees")
            self.fixKnees(rig)
        elif rig.DazRig == "genesis9":
            if self.keepG9Twist:
                showProgress(4, 25, "  Rename bones")
                self.rename2Mhx(rig)
                useBendTwist = False
            else:
                self.bendTwistGenesis = MHX.BendTwistGenesis9
                showProgress(2, 25, "  Connect to parent")
                connectToParent(rig, connectAll=False)
                showProgress(3, 25, "  Delete bend-twist bones")
                self.deleteBendTwistDrvBones(rig)
                showProgress(4, 25, "  Rename bones")
                self.rename2Mhx(rig)
                showProgress(5, 25, "  Join bend and twist bones")
                bendTwistChildren = self.joinBendTwists(rig, {}, bendTwistBones, keep=False)
                for ob in getMeshChildren(rig):
                    self.joinVertexGroups(ob, MHX.BendTwistGenesis9)
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
        if useBendTwist:
            showProgress(9, 25, "  Create bend and twist bones")
            self.createBendTwists(rig, bendTwistBones, bendTwistChildren)
        #showProgress(10, 25, "  Fix bone drivers")
        #self.fixBoneDrivers(rig, rig, MHX.BoneDrivers)

        #-------------------------------------------------------------
        #   Add MHX stuff
        #-------------------------------------------------------------

        showProgress(10, 25, "  Add master bone")
        self.addMaster(rig)
        showProgress(11, 25, "  Add tweak bones")
        self.addTweaks(rig)
        showProgress(12, 25, "  Add backbone")
        self.addBack(rig)
        self.addShaftWinder(rig)
        showProgress(13, 25, "  Setup FK-IK")
        self.setupFkIk(rig)
        showProgress(14, 25, "  Add long fingers")
        self.addFingerWinders(rig)
        showProgress(15, 25, "  Add layers")
        self.addLayers(rig)
        showProgress(16, 25, "  Add markers")
        self.addMarkers(rig)
        showProgress(17, 25, "  Add gizmos")
        self.addGizmos(rig, context)
        showProgress(18, 25, "  Add tongue control")
        self.addTongueControl(rig, [L_HEAD, L_FACE])
        showProgress(19, 25, "  Constrain bend and twist bones")
        self.constrainBendTwists(rig, bendTwistBones, self.useStretch)
        self.addCopyLocConstraints(rig)
        showProgress(20, 25, "  Restore constraints")
        self.restoreFixConstraints(context, rig)
        showProgress(21, 25, "  Fix constraints")
        deletes = self.fixConstraints(rig)
        self.restoreAllDrivers(rig, nrig, self.meshes, self.renamedBones)
        self.fixDrivers(rig.data)
        if self.driverRotationMode:
            from ..ctrl_rig import setDriverModes
            setDriverModes(rig, self.driverRotationMode, False)
        if rig.DazRig in ["genesis3", "genesis8"]:
            self.fixCustomShape(rig, ["head"], 4)
        showProgress(22, 25, "  Collect deform bones")
        self.collectDeformBones(rig)
        setMode('OBJECT')
        showProgress(23, 25, "  Rename face bones")
        self.renameFaceBones(rig, ["Eye", "Ear", "_eye", "_ear"])
        showProgress(24, 25, "  Add bone groups")
        self.addBoneGroups(rig)
        rig.MhxRig = True
        rig.data.MhaFeatures |= F_IDPROPS
        enableRigNumLayers(rig, [L_MAIN, L_SPINE, L_LARMIK, L_LLEGIK, L_RARMIK, L_RLEGIK])
        rig.DazRig = "mhx"

        for pb in rig.pose.bones:
            pb.bone.select = False
            if pb.custom_shape:
                pb.bone.show_wire = True

        self.restoreBoneChildren(bonechildren, context, rig)
        updateAll(context)
        if self.keepRig:
            self.tieBones(context, nrig, rig)
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

        from ..driver import getDrivenBoneFcurves
        driven = getDrivenBoneFcurves(rig)
        for pb in rig.pose.bones:
            if pb.name in fixed:
                continue
            layer,unlock = self.getBoneLayer(pb, rig, driven)
            enableBoneNumLayer(pb.bone, rig, layer)
            if False and unlock:
                pb.lock_location = FFalse
        self.checkTongueIk(rig)
        self.checkFingerIk(rig)


    def getBoneLayer(self, pb, rig, driven):
        lname = pb.name.lower()
        if pb.name in BD.HeadBones:
            return L_HEAD, False
        elif (isDrvBone(pb.name) or
              pb.name in driven.keys() or
              pb.name in BD.FaceRigs):
            return L_HELP, False
        elif pb.name in BD.Teeth:
            return L_TWEAK, False
        elif isFinal(pb.name) or isInNumLayer(pb.bone, rig, L_HELP2):
            return L_HELP2, False
        elif pb.name[0:6] == "tongue":
            return L_FACE, False
        elif pb.parent:
            par = pb.parent
            if par.name in BD.FaceRigs:
                return L_FACE, True
            elif (isDrvBone(par.name) and
                  par.parent and
                  par.parent.name in BD.FaceRigs):
                return L_FACE, True
        return L_CUSTOM, True


    def restoreBoneChildren(self, bonechildren, context, rig):
        def getMhxBone(bname):
            mname = MHX.BoneParents.get(bname[1:])
            if mname:
                bname = "%s.%s" % (mname, bname[0].upper())
            if bname in rig.data.bones.keys():
                return rig.data.bones[bname]
            if bname in MHX.Skeleton.keys():
                mname = MHX.Skeleton[bname][0]
                if mname in rig.data.bones.keys():
                    return rig.data.bones[mname]
                else:
                    print("Missing MHX bone:", bname, mname)
            return None

        from ..node import setParent
        layers = getRigLayers(rig)
        enableAllRigLayers(rig)
        for (ob, bname) in bonechildren:
            bone = getMhxBone(bname)
            if bone is None and isDrvBone(bname):
                bone = getMhxBone(baseBone(bname))
            if bone:
                setParent(context, ob, rig, bone.name)
            else:
                print("Could not restore bone parent %s for %s" % (bname, ob.name))
        setRigLayers(rig, layers)

    #-------------------------------------------------------------
    #   Bend Twist
    #-------------------------------------------------------------

    def getBendTwistNames(self, bname):
        words = bname.split(".", 1)
        if len(words) == 2:
            bendname = words[0] + "Bend." + words[1]
            twistname = words[0] + "Twist." + words[1]
        else:
            bendname = bname + "Bend"
            twistname = bname + "Twist"
        return bendname, twistname


    def joinBendTwists(self, rig, renames, bendTwistBones, keep=True):
        bendTwistChildren = {}
        setMode('OBJECT')
        rotmodes = {}
        for bname,tname,stretch in bendTwistBones:
            bendname,twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.pose.bones.keys() and
                    twistname in rig.pose.bones.keys()):
                continue
            pb = rig.pose.bones[bendname]
            rotmodes[bname] = pb.DazRotMode
            self.storeConstraints(bname, pb)
            self.removeConstraints(pb)
            self.deleteBoneDrivers(rig, bendname)
            pb = rig.pose.bones[twistname]
            self.removeConstraints(pb)
            self.deleteBoneDrivers(rig, twistname)

        setMode('EDIT')
        for bname,tname,stretch in bendTwistBones:
            bendname,twistname = self.getBendTwistNames(bname)
            bend = rig.data.edit_bones.get(bendname)
            twist = rig.data.edit_bones.get(twistname)
            target = rig.data.edit_bones.get(tname)
            if not (bend and twist and target):
                continue
            eb = rig.data.edit_bones.new(bname)
            eb.head = bend.head
            bend.tail = twist.head
            eb.tail = twist.tail
            eb.roll = bend.roll
            eb.parent = bend.parent
            eb.use_deform = False
            eb.use_connect = bend.use_connect
            nbendname,ntwistname = self.getSubBoneNames(bname)
            for child in bend.children:
                if child != twist:
                    if isDrvBone(child.name):
                        bendTwistChildren[child.name] = nbendname
                    child.parent = eb
            for child in twist.children:
                if isDrvBone(child.name):
                    bendTwistChildren[child.name] = ntwistname
                child.parent = eb

        for bname3,bname2 in renames.items():
            eb = rig.data.edit_bones[bname3]
            eb.name = bname2

        setMode('OBJECT')
        for bname,rotmode in rotmodes.items():
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                pb.DazRotMode = rotmode

        from ..figure import copyBoneInfo
        for bname,tname,stretch in bendTwistBones:
            bendname,twistname = self.getBendTwistNames(bname)
            srcbone = rig.pose.bones.get(bendname)
            trgbone = rig.pose.bones.get(bname)
            if srcbone and trgbone:
                copyBoneInfo(srcbone, trgbone)
                trgbone.DazRotLocks = FFalse

        setMode('EDIT')
        for bname,tname,stretch in bendTwistBones:
            bendname,twistname = self.getBendTwistNames(bname)
            if bendname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bendname]
                if keep:
                    enableBoneNumLayer(eb, rig, L_DEF)
                else:
                    rig.data.edit_bones.remove(eb)
            if twistname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[twistname]
                if keep:
                    enableBoneNumLayer(eb, rig, L_DEF)
                else:
                    rig.data.edit_bones.remove(eb)
        setMode('OBJECT')
        return bendTwistChildren


    def joinVertexGroups(self, ob, info):
        for bname, bend, twists in info:
            vgbend = ob.vertex_groups.get(bend)
            vgtwists = []
            for twist in twists:
                vgtwist = ob.vertex_groups.get(twist)
                if vgtwist:
                    vgtwists.append(vgtwist)
            if vgbend and vgtwists:
                pass
            elif vgbend:
                vgbend.name = bname
                continue
            elif not vgtwists:
                continue

            vgrp = ob.vertex_groups.new(name=bname)
            indices = [vgtwist.index for vgtwist in vgtwists]
            if vgbend:
                indices.append(vgbend.index)
            for v in ob.data.vertices:
                w = 0.0
                for g in v.groups:
                    if g.group in indices:
                        w += g.weight
                if w > 1e-4:
                    vgrp.add([v.index], w, 'REPLACE')
            if vgbend:
                ob.vertex_groups.remove(vgbend)
            for vgtwist in vgtwists:
                ob.vertex_groups.remove(vgtwist)
            vgrp.name = bname


    def getSubBoneNames(self, bname):
        base,suffix = bname.split(".")
        bendname = "%s.bend.%s" % (base, suffix)
        twistname = "%s.twist.%s" % (base, suffix)
        return bendname,twistname


    def createBendTwists(self, rig, bendTwistBones, bendTwistChildren):
        setMode('EDIT')
        for bname,tname,stretch in bendTwistBones:
            eb = rig.data.edit_bones.get(bname)
            if eb is None:
                continue
            vec = eb.tail - eb.head
            bendname,twistname = self.getSubBoneNames(bname)
            bend = rig.data.edit_bones.new(bendname)
            twist = rig.data.edit_bones.new(twistname)
            bend.head  = eb.head
            bend.tail = twist.head = eb.head+vec/2
            twist.tail = eb.tail
            bend.roll = twist.roll = eb.roll
            bend.parent = eb.parent
            twist.parent = bend
            bend.use_connect = eb.use_connect
            twist.use_connect = True
            eb.use_deform = False
            if self.addTweakBones:
                btwkname = self.getTweakBoneName(bendname)
                ttwkname = self.getTweakBoneName(twistname)
                bendtwk = rig.data.edit_bones.new(btwkname)
                twisttwk = rig.data.edit_bones.new(ttwkname)
                bendtwk.head = bend.head
                bendtwk.tail = twisttwk.head = twist.head
                twisttwk.tail = twist.tail
                bendtwk.roll = twisttwk.roll = eb.roll
                bendtwk.parent = bend
                twisttwk.parent = twist
                bend.use_deform = twist.use_deform = False
                bendtwk.use_deform = twisttwk.use_deform = True
                enableBoneNumLayer(bendtwk, rig, L_DEF)
                enableBoneNumLayer(twisttwk, rig, L_DEF)
                setBoneNumLayer(bendtwk, rig, L_TWEAK)
                setBoneNumLayer(twisttwk, rig, L_TWEAK)
                enableBoneNumLayer(bend, rig, L_HELP2)
                enableBoneNumLayer(twist, rig, L_HELP2)
                bvgname = btwkname
                tvgname = ttwkname
            else:
                bend.use_deform = twist.use_deform = True
                enableBoneNumLayer(bend, rig, L_DEF)
                enableBoneNumLayer(twist, rig, L_DEF)
                bvgname = bend.name
                tvgname = twist.name

            for ob in getMeshChildren(rig):
                if bname in ob.vertex_groups.keys():
                    self.splitVertexGroup(ob, bname, bvgname, tvgname, eb.head, eb.tail)
                else:
                    base,suffix = bname.split(".",1)
                    bendgrp = ob.vertex_groups.get("%sBend.%s" % (base, suffix))
                    if bendgrp:
                        bendgrp.name = bvgname
                    twistgrp = ob.vertex_groups.get("%sTwist.%s" % (base, suffix))
                    if twistgrp:
                        twistgrp.name = tvgname

        for bname, parname in bendTwistChildren.items():
            eb = rig.data.edit_bones.get(bname)
            par = rig.data.edit_bones.get(parname)
            if eb and par:
                eb.parent = par


    def constrainBendTwists(self, rig, bendTwistBones, useStretch):
        from ..rig_utils import dampedTrack, copyRotation, copyTransform, stretchTo
        setMode('OBJECT')
        for bname,tname,stretch in bendTwistBones:
            bendname,twistname = self.getSubBoneNames(bname)
            if not hasPoseBones(rig, [bname, bendname, twistname]):
                continue
            pb = rig.pose.bones[bname]
            bend = rig.pose.bones[bendname]
            twist = rig.pose.bones[twistname]
            bend.rotation_mode = twist.rotation_mode = pb.rotation_mode
            trg = rig.pose.bones[tname]
            cns = copyRotation(bend, pb, rig, space='LOCAL')
            cns.use_y = False
            cns = dampedTrack(bend, pb, rig)
            cns.head_tail = 1.0
            copyTransform(twist, pb, rig)
            if useStretch and stretch:
                stretchTo(bend, trg, rig, stretch, "x")
                stretchTo(twist, trg, rig, stretch, "x")
            if self.addTweakBones:
                btwkname = self.getTweakBoneName(bendname)
                ttwkname = self.getTweakBoneName(twistname)
                bendtwk = rig.pose.bones[btwkname]
                twisttwk = rig.pose.bones[ttwkname]
                self.addGizmo(bendtwk, "GZM_Ball", 0.25, blen=10*rig.DazScale)
                self.addGizmo(twisttwk, "GZM_Ball", 0.25, blen=10*rig.DazScale)

    #-------------------------------------------------------------
    #   Gizmos
    #-------------------------------------------------------------

    def addGizmos(self, rig, context):
        from ..driver import getDrivenBoneFcurves
        setMode('OBJECT')
        self.makeGizmos(True, None)

        def getData(data):
            if len(data) == 3:
                return data
            else:
                return data[0], data[1], None

        driven = getDrivenBoneFcurves(rig)
        for pb in rig.pose.bones:
            if (isDrvBone(pb.name) or
                isFinal(pb.name) or
                pb.name in BD.FaceRigs+BD.Teeth):
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
                        if pb.name in driven.keys():
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
        if BLENDER3:
            for idx,data in enumerate(MHX.BoneGroups):
                _bgname,color,layers = data
                bgrp = rig.pose.bone_groups[idx]
                for pb in rig.pose.bones:
                    for layer in layers:
                        if isInNumLayer(pb.bone, rig, layer):
                            pb.bone_group = bgrp
        elif GS.useBoneColors:
            for _bgname,color,layers in MHX.BoneGroups:
                for layer in layers:
                    coll = rig.data.collections.get(layer)
                    if coll:
                        for bone in coll.bones:
                            bone.color.palette = 'CUSTOM'
                            bone.color.custom.normal = color
                            bone.color.custom.select = (0.6, 0.9, 1.0)
                            bone.color.custom.active = (1.0, 1.0, 0.8)
            for pb in rig.pose.bones:
                if pb.custom_shape is None:
                    pb.bone.color.palette = 'DEFAULT'

    #-------------------------------------------------------------
    #   Fix knees
    #-------------------------------------------------------------

    def fixKnees(self, rig):
        if not self.usePoleTargets:
            return
        from ..bone import setRoll
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
        from ..winder import addWinder, addSuperWinder
        backbones = self.getExistingBones(rig, MHX.BackBones)
        layers = [L_SPINE2, L_SPINE, L_HELP, L_HELP2, L_DEF]
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
            shaft = self.shaftName.lower()
            nchars = len(shaft)
            return bname.lower()[0:nchars] == shaft and bname[nchars:].isdigit()

        return [bone.name for bone in rig.data.bones if isShaft(bone.name)]


    def addShaftWinder(self, rig):
        if self.useShaftWinder:
            from ..winder import addWinder
            setMhx(rig, "MhaShaftControl", True)
            shaftbones = self.getShaftBones(rig)
            shaftbones.sort()
            layers = [L_CUSTOM, L_CUSTOM2]
            influs = [1/(n+1)**2 for n in range(len(shaftbones))]
            addWinder(rig, "shaft", shaftbones, layers, "MhaShaftControl",
                useBaseLocation=True,
                useScale=True,
                influs=influs)

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

        setMode('OBJECT')
        from ..figure import copyBoneInfo
        rpbs = rig.pose.bones
        for bname in self.tweakBones:
            if bname and bname in rpbs.keys():
                tname = self.getTweakBoneName(bname)
                tb = rpbs[tname]
                pb = getBoneCopy(bname, tb, rpbs, False)
                copyBoneInfo(tb, pb)
                tb.lock_location = tb.lock_rotation = tb.lock_scale = FFalse
        setMode('OBJECT')


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
        from ..winder import addWinder
        if self.useFingerIk:
            rig.data.MhaFeatures |= F_FINGER
        for suffix,handlayer,finglayer,fklayer,iklayer in [
            ("L", L_LHAND, L_LFINGER, L_LARMFK, L_LARMIK),
            ("R", L_RHAND, L_RFINGER, L_RARMFK, L_RARMIK)]:
            prop1 = "MhaFingerControl_%s" % suffix
            setMhx(rig, prop1, True)
            if self.useFingerIk:
                prop2 = "MhaFingerIk_%s" % suffix
                setMhx(rig, prop2, 0.0)
            layers = [handlayer, finglayer, L_HELP, L_HELP2, L_DEF]
            fingname = self.makeFingerMaster(rig, suffix, handlayer)
            for m in range(5):
                bnames = self.getFingerNames(rig, m, suffix)
                windname = "%s.%s" % (MHX.Fingers[m], suffix)
                fkwind,pbones = addWinder(rig, windname, bnames, layers, prop1, parname=fingname)
                if fkwind is None:
                    continue
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


    def makeFingerMaster(self, rig, suffix, handlayer):
        hand0name = "hand0.%s" % suffix
        fingname = "fingers.%s" % suffix
        linkname = self.getFingerNames(rig, 2, suffix)[0]
        setMode('EDIT')
        hand0 = rig.data.edit_bones[hand0name]
        fingers = deriveBone(fingname, hand0, rig, handlayer, hand0)
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
        eb = rig.data.edit_bones.get(bname)
        if eb:
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
        for suffix, armFkLayer, armIkLayer, legFkLayer, legIkLayer, arm2Layer, leg2Layer in [
            ("L", L_LARMFK, L_LARMIK, L_LLEGFK, L_LLEGIK, L_LARM2IK, L_LLEG2IK),
            ("R", L_RARMFK, L_RARMIK, L_RLEGFK, L_RLEGIK, L_RARM2IK, L_RLEG2IK)]:
            upper_arm = self.setLayer("upper_arm.%s" % suffix, rig, L_HELP)
            forearm = self.setLayer("forearm.%s" % suffix, rig, L_HELP)
            hand0 = self.setLayer("hand.%s" % suffix, rig, L_DEF)
            if not (upper_arm and forearm and hand0):
                raise DazError("Rig missing arm bones")
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
            armSocket = makeBone("armSocket.%s" % suffix, rig, upper_arm.head, upper_arm.head+ez, 0, L_TWEAK, upper_arm.parent)
            armParent = deriveBone("arm_parent.%s" % suffix, armSocket, rig, L_HELP, hip)
            upper_arm.parent = armParent
            bend = rig.data.edit_bones.get("upper_arm.bend.%s" % suffix)
            if bend:
                bend.parent = armParent

            upper_armFk = deriveBone("upper_arm.fk.%s" % suffix, upper_arm, rig, armFkLayer, armParent)
            forearmFk = deriveBone("forearm.fk.%s" % suffix, forearm, rig, armFkLayer, upper_armFk)
            setConnected(forearmFk, forearm.use_connect)
            handFk = deriveBone("hand.fk.%s" % suffix, hand, rig, armFkLayer, forearmFk)
            handFk.use_connect = False
            layer = (L_HELP2 if self.usePoleTargets else armIkLayer)
            upper_armIk = deriveBone("upper_arm.ik.%s" % suffix, upper_arm, rig, layer, armParent)
            forearmIk = deriveBone("forearm.ik.%s" % suffix, forearm, rig, L_HELP2, upper_armIk)
            setConnected(forearmIk, forearm.use_connect)
            deriveBone("upper_arm.ik.twist.%s" % suffix, upper_arm, rig, arm2Layer, upper_armIk)
            forearmIkTwist = deriveBone("forearm.ik.twist.%s" % suffix, forearm, rig, arm2Layer, forearmIk)
            handIk = deriveBone("hand.ik.%s" % suffix, hand, rig, armIkLayer, master)
            hand0Ik = deriveBone("hand0.ik.%s" % suffix, hand, rig, L_HELP2, forearmIkTwist)

            if self.usePoleTargets:
                vec = upper_arm.matrix.to_3x3().col[2]
                vec.normalize()
                dist = max(upper_arm.length, forearm.length)
                locElbowPt = forearm.head - 1.2*dist*vec
                elbowFac = upper_arm.length/(upper_arm.length + forearm.length)
                elbowVec = forearm.tail - upper_arm.head
                elbowHead = upper_arm.head + elbowFac*elbowVec
                elbowPoleA = makeBone("elbowPoleA.%s" % suffix, rig, armSocket.head, armSocket.head + 0.2*elbowVec, 0, armIkLayer, armSocket)
                elbowPoleP = makeBone("elbowPoleP.%s" % suffix, rig, elbowHead, elbowHead + 0.2*elbowVec, 0, L_HELP2, armParent)
                parent = self.getElbowParent(rig, suffix)
                elbowPt = makeBone("elbow.pt.ik.%s" % suffix, rig, locElbowPt, locElbowPt+ez, 0, armIkLayer, parent)
                elbowLink = makeBone("elbow.link.%s" % suffix, rig, forearm.head, locElbowPt, 0, armIkLayer, upper_armIk)
                if self.showLinks:
                    elbowLink.hide_select = True
                else:
                    enableBoneNumLayer(elbowLink, rig, L_HIDDEN)

            thigh = self.setLayer("thigh.%s" % suffix, rig, L_HELP)
            shin = self.setLayer("shin.%s" % suffix, rig, L_HELP)
            foot = self.setLayer("foot.%s" % suffix, rig, L_HELP)
            toe = self.setLayer("toe.%s" % suffix, rig, L_HELP)
            if not (thigh and shin and foot):
                raise DazError("Rig missing leg bones")
            shin.tail = foot.head
            foot.use_connect = False
            if toe:
                foot.tail = toe.head
                setConnected(toe, True)

            legSocket = makeBone("legSocket.%s" % suffix, rig, thigh.head, thigh.head+ez, 0, L_TWEAK, thigh.parent)
            legParent = deriveBone("leg_parent.%s" % suffix, legSocket, rig, L_HELP, hip)
            thigh.parent = legParent
            bend = rig.data.edit_bones.get("thigh.bend.%s" % suffix)
            if bend:
                bend.parent = legParent

            thighFk = deriveBone("thigh.fk.%s" % suffix, thigh, rig, legFkLayer, thigh.parent)
            shinFk = deriveBone("shin.fk.%s" % suffix, shin, rig, legFkLayer, thighFk)
            setConnected(shinFk, shin.use_connect)
            footFk = deriveBone("foot.fk.%s" % suffix, foot, rig, legFkLayer, shinFk)
            footFk.use_connect = False
            toeFk = deriveBone("toe.fk.%s" % suffix, toe, rig, legFkLayer, footFk)
            setConnected(toeFk, True)
            layer = (L_HELP2 if self.usePoleTargets else legIkLayer)
            thighIk = deriveBone("thigh.ik.%s" % suffix, thigh, rig, layer, thigh.parent)
            if not self.usePoleTargets:
                setBoneNumLayer(thighIk, rig, leg2Layer)
            shinIk = deriveBone("shin.ik.%s" % suffix, shin, rig, L_HELP2, thighIk)
            setConnected(shinIk, shin.use_connect)
            deriveBone("thigh.ik.twist.%s" % suffix, thigh, rig, leg2Layer, thighIk)
            deriveBone("shin.ik.twist.%s" % suffix, shin, rig, leg2Layer, shinIk)

            if "heel.%s" % suffix in rig.data.edit_bones.keys():
                heel = rig.data.edit_bones["heel.%s" % suffix]
                locFootIk = (foot.head[0], heel.tail[1], toe.tail[2])
            else:
                vec = foot.tail - foot.head
                locFootIk = (foot.head[0], foot.head[1] - 0.5*vec[1], toe.tail[2])
            footIk = makeBone("foot.ik.%s" % suffix, rig, locFootIk, toe.tail, 180*D, legIkLayer, master)
            toeRev = makeBone("toe.rev.%s" % suffix, rig, toe.tail, toe.head, 0, legIkLayer, footIk)
            setConnected(toeRev, True)
            footRev = makeBone("foot.rev.%s" % suffix, rig, toe.head, foot.head, 0, legIkLayer, toeRev)
            setConnected(footRev, True)
            locAnkle = foot.head + (shin.tail-shin.head)/4
            if self.useAnkleIk:
                foot2 = deriveBone("foot.2.%s" % suffix, foot, rig, leg2Layer, master)
                setConnected(foot2, False)
                toe2 = deriveBone("toe.2.%s" % suffix, toe, rig, leg2Layer, foot2)
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
                kneePoleA = makeBone("kneePoleA.%s" % suffix, rig, legSocket.head, legSocket.head + 0.2*kneeVec, 0, legIkLayer, legSocket)
                kneePoleP = makeBone("kneePoleP.%s" % suffix, rig, kneeHead, kneeHead + 0.2*kneeVec, 0, L_HELP2, hip)
                setBoneNumLayer(kneePoleA, rig, leg2Layer)
                parent = self.getKneeParent(rig, suffix)
                kneePt = makeBone("knee.pt.ik.%s" % suffix, rig, locKneePt, locKneePt+ez, 0, legIkLayer, parent)
                setBoneNumLayer(kneePt, rig, leg2Layer)
                kneeLink = makeBone("knee.link.%s" % suffix, rig, shin.head, locKneePt, 0, legIkLayer, thighIk)
                if self.showLinks:
                    setBoneNumLayer(kneeLink, rig, leg2Layer)
                    kneeLink.hide_select = True
                else:
                    enableBoneNumLayer(kneeLink, rig, L_HIDDEN)

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

        from ..figure import copyBoneInfo
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
                #fkbone.rotation_mode = 'QUATERNION'
                bone.lock_rotation = FFalse

        for bname in ["hip", "pelvis"]:
            pb = rpbs[bname]
            pb.rotation_mode = 'YZX'

        rotmodes = {
            'YZX': ["shin", "shin.fk", "shin.ik", "shin.ik.twist",
                    "thigh", "thigh.fk", "thigh.ik", "thigh.ik.twist",
                    "forearm", "forearm.fk", "forearm.ik", "forearm.ik.twist",
                    "foot", "foot.fk", "foot.rev",
                    "toe", "toe.fk", "foot.2", "toe.2", "toe.rev",
                    "knee.pt.ik", "elbow.pt.ik", "elbowPoleA", "kneePoleA",
                   ],
            'YXZ' : ["upper_arm", "upper_arm.fk", "upper_arm.ik", "upper_arm.ik.twist",
                     "hand", "hand.fk", "hand.ik", "hand0.ik"],
        }
        for suffix in ["L", "R"]:
            for rmode,bnames in rotmodes.items():
                for bname in bnames:
                    pb = rpbs.get("%s.%s" % (bname,suffix))
                    if pb:
                        pb.rotation_mode = rmode
            if self.useQuaternions:
                for bname in ["upper_arm", "upper_arm.fk", "upper_arm.ik", "thigh", "thigh.fk", "thigh.ik"]:
                    pb = rpbs.get("%s.%s" % (bname,suffix))
                    if pb:
                        pb.rotation_mode = 'QUATERNION'

            armSocket = rpbs["armSocket.%s" % suffix]
            armParent = rpbs["arm_parent.%s" % suffix]
            upper_arm = rpbs["upper_arm.%s" % suffix]
            forearm = rpbs["forearm.%s" % suffix]
            hand = rpbs["hand.%s" % suffix]
            upper_armFk = getBoneCopy("upper_arm.fk.%s" % suffix, upper_arm, rpbs, True)
            forearmFk = getBoneCopy("forearm.fk.%s" % suffix, forearm, rpbs, True)
            handFk = getBoneCopy("hand.fk.%s" % suffix, hand, rpbs, True)
            upper_armIk = rpbs["upper_arm.ik.%s" % suffix]
            forearmIk = rpbs["forearm.ik.%s" % suffix]
            upper_armIkTwist = rpbs.get("upper_arm.ik.twist.%s" % suffix, upper_armIk)
            forearmIkTwist = rpbs.get("forearm.ik.twist.%s" % suffix, forearmIk)
            handIk = rpbs["hand.ik.%s" % suffix]
            hand0Ik = rpbs["hand0.ik.%s" % suffix]

            prop = "MhaArmHinge_%s" % suffix
            setMhx(rig, prop, 0.0)
            copyLocation(armParent, armSocket, rig)
            copyTransform(armParent, armSocket, rig, prop, "1-x")

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
                elbowLink.lock_location = TTrue
                elbowPoleA = rpbs["elbowPoleA.%s" % suffix]
                elbowPoleP = rpbs["elbowPoleP.%s" % suffix]
                elbowPoleA.lock_location = TTrue
                elbowPoleA.lock_rotation = (True,False,True)
                dampedTrack(elbowPoleA, handIk, rig)
                cns = copyLocation(elbowPoleA, handIk, rig)
                cns.influence = elbowFac
                copyTransform(elbowPoleP, elbowPoleA, rig)
                setMhx(rig, "MhaElbowParent_%s" % suffix, self.elbowParent)
                ikConstraint(forearmIk, handIk, elbowPt, -90, 2, rig)
                stretchTo(elbowLink, elbowPt, rig)
                elbowPt.rotation_euler[0] = -90*D
                elbowPt.lock_rotation = TTrue
            else:
                ikConstraint(forearmIk, handIk, None, 0, 2, rig)

            prop = "MhaForearmFollow_%s" % suffix
            setMhx(rig, prop, False)
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
            if self.useAnkleIk:
                foot2 = rpbs["foot.2.%s" % suffix]
                toe2 = rpbs["toe.2.%s" % suffix]
                toe2.lock_location = TTrue
            ankleIk = rpbs["ankle.ik.%s" % suffix]
            thighFk = getBoneCopy("thigh.fk.%s" % suffix, thigh, rpbs, True)
            shinFk = getBoneCopy("shin.fk.%s" % suffix, shin, rpbs, True)
            footFk = getBoneCopy("foot.fk.%s" % suffix, foot, rpbs, True)
            toeFk = getBoneCopy("toe.fk.%s" % suffix, toe, rpbs, True)
            thighIk = rpbs["thigh.ik.%s" % suffix]
            shinIk = rpbs["shin.ik.%s" % suffix]
            thighIkTwist = rpbs.get("thigh.ik.twist.%s" % suffix, thighIk)
            shinIkTwist = rpbs.get("shin.ik.twist.%s" % suffix, shinIk)
            footIk = rpbs["foot.ik.%s" % suffix]
            toeRev = rpbs["toe.rev.%s" % suffix]
            toeRev.lock_location = TTrue
            footRev = rpbs["foot.rev.%s" % suffix]
            footRev.lock_location = TTrue
            footRev.lock_rotation = (False,True,True)
            footInvIk = rpbs["foot.inv.ik.%s" % suffix]
            toeInvIk = rpbs["toe.inv.ik.%s" % suffix]

            prop = "MhaLegHinge_%s" % suffix
            setMhx(rig, prop, 0.0)
            copyLocation(legParent, legSocket, rig)
            copyTransform(legParent, legSocket, rig, prop, "1-x")

            prop1 = "MhaLegIk_%s" % suffix
            setMhx(rig, prop1, 1.0)
            if self.useAnkleIk:
                prop2 = "MhaLegIkToAnkle_%s" % suffix
                setMhx(rig, prop2, False)
            else:
                prop2 = None

            copyTransformFkIk(thigh, thighFk, thighIkTwist, rig, prop1)
            copyTransformFkIk(shin, shinFk, shinIkTwist, rig, prop1)
            copyTransformFkIk(foot, footFk, footInvIk, rig, prop1, prop2)
            copyTransformFkIk(toe, toeFk, toeInvIk, rig, prop1, prop2)

            addHint(shinIk, rig)
            if self.usePoleTargets:
                kneePt = rpbs["knee.pt.ik.%s" % suffix]
                kneeLink = rpbs["knee.link.%s" % suffix]
                kneeLink.lock_location = TTrue
                kneePoleA = rpbs["kneePoleA.%s" % suffix]
                kneePoleP = rpbs["kneePoleP.%s" % suffix]
                kneePoleA.lock_location = TTrue
                kneePoleA.lock_rotation = (True,False,True)
                dampedTrack(kneePoleA, ankleIk, rig)
                cns = copyLocation(kneePoleA, ankleIk, rig)
                cns.influence = kneeFac
                copyTransform(kneePoleP, kneePoleA, rig)
                setMhx(rig, "MhaKneeParent_%s" % suffix, self.kneeParent)

                ikConstraint(shinIk, ankleIk, kneePt, -90, 2, rig)
                stretchTo(kneeLink, kneePt, rig)
                kneePt.rotation_euler[0] = 90*D
                kneePt.lock_rotation = TTrue
            else:
                ikConstraint(shinIk, ankleIk, None, 0, 2, rig)

            if self.useAnkleIk:
                cns = copyTransform(ankleIk, foot2, rig)
                addMuteDriver(cns, rig, prop2)
                cns = copyTransform(foot, foot2, rig, prop1)
                addMuteDriver(cns, rig, prop2)
                cns = copyTransform(toe, toe2, rig, prop1)
                addMuteDriver(cns, rig, prop2)

            self.addGazeConstraint(rig, suffix)
            handFk.lock_location = FFalse
            footFk.lock_location = FFalse
            setMhx(rig, "MhaToeTarsal_%s" % suffix, False)

        self.addGazeFollowsHead(rig)
        setMhx(rig, "MhaLimitsOn", True)

    #-------------------------------------------------------------
    #   Restore constraints for bend-twist bones
    #-------------------------------------------------------------

    def restoreFixConstraints(self, context, rig):
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
        self.restoreAllConstraints(context, rig, ignore)
        if rig.DazRig not in ["genesis3", "genesis8"]:
            return
        for bname, bendname, twistnames in self.bendTwistGenesis:
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
                if self.useStretch:
                    setMhx(rig, prop, 1.0)
                else:
                    setMhx(rig, prop, 0.0)
                pb = rig.pose.bones["%s.%s" % (bname, suffix)]
                cns = copyLocation(pb, pb.parent, rig, prop, "1-x")
                cns.head_tail = 1.0


    def getElbowParent(self, rig, suffix):
        if self.elbowParent == 'HAND':
            bname = "elbowPoleP.%s" % suffix
        elif self.elbowParent == 'SHOULDER':
            bname = "arm_parent.%s" % suffix
        else:
            bname = "master"
        return rig.data.edit_bones[bname]


    def getKneeParent(self, rig, suffix):
        if self.kneeParent == 'FOOT':
            bname = "kneePoleP.%s" % suffix
        elif self.kneeParent == 'HIP':
            bname = "hip"
        else:
            bname = "master"
        return rig.data.edit_bones[bname]

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
            if self.useAnkleIk:
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


    def copyLocksLimits(self, rig, srcname, trgname, suffix):
        from ..store import copyConstraint
        src = rig.pose.bones["%s.%s" % (srcname, suffix)]
        trg = rig.pose.bones["%s.%s" % (trgname, suffix)]
        trg.lock_location = src.lock_location
        trg.lock_rotation = src.lock_rotation
        trg.lock_scale = src.lock_scale
        cns = getConstraint(src, 'LIMIT_ROTATION')
        if cns:
            copyConstraint(cns, trg, rig)


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
        #iktwist.lock_rotation = (True,False,True)
        fkbone = rig.pose.bones["%s.fk.%s" % (bname, suffix)]
        ikbone = rig.pose.bones["%s.ik.%s" % (bname, suffix)]
        ikbone.lock_ik_x = fkbone.lock_rotation[0]
        ikbone.lock_ik_y = fkbone.lock_rotation[1]
        ikbone.lock_ik_z = fkbone.lock_rotation[2]

    #-------------------------------------------------------------
    #   Toe rotation
    #-------------------------------------------------------------

    def copyToeRotation(self, rig, mute, suffix, toenames):
        from ..rig_utils import copyRotation
        toe = rig.pose.bones.get("toe.%s" % suffix)
        if toe:
            for toename in toenames:
                bname = "%s.%s" % (toename, suffix)
                pb = rig.pose.bones.get(bname)
                if pb:
                    cns = copyRotation(pb, toe, rig)
                    cns.subtarget = toe.name
                    cns.mute = mute
                    cns.use_y = False
                    cns.mix_mode = 'BEFORE'

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
        for suffix in ["L", "R"]:
            setMode('EDIT')
            foot = rig.data.edit_bones["foot.%s" % suffix]
            toe = rig.data.edit_bones["toe.%s" % suffix]
            offs = Vector((0, 0, 0.5*toe.length))
            if "heel.%s" % suffix in rig.data.edit_bones.keys():
                heelTail = rig.data.edit_bones["heel.%s" % suffix].tail
            else:
                heelTail = Vector((foot.head[0], foot.head[1], toe.head[2]))

            ballLoc = Vector((toe.head[0], toe.head[1], heelTail[2]))
            mBall = makeBone("ball.marker.%s" % suffix, rig, ballLoc, ballLoc+offs, 0, L_TWEAK, foot)
            toeLoc = Vector((toe.tail[0], toe.tail[1], heelTail[2]))
            mToe = makeBone("toe.marker.%s" % suffix, rig, toeLoc, toeLoc+offs, 0, L_TWEAK, toe)
            mHeel = makeBone("heel.marker.%s" % suffix, rig, heelTail, heelTail+offs, 0, L_TWEAK, foot)

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
    #   Move all deform bones to layer T_HIDDEN
    #-------------------------------------------------------------

    def collectDeformBones(self, rig):
        setMode('OBJECT')
        for bone in rig.data.bones:
            if bone.use_deform:
                setBoneNumLayer(bone, rig, L_DEF)


    def addLayers(self, rig):
        setMode('OBJECT')
        for suffix,armIkLayer in [("L", L_LARMIK), ("R", L_RARMIK)]:
            clavicle = rig.data.bones["clavicle.%s" % suffix]
            setBoneNumLayer(clavicle, rig, L_SPINE)
            setBoneNumLayer(clavicle, rig, armIkLayer)

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
        elif (pb.name in facebones or
              ".twist" in rb.name):
            space = 'LOCAL'
        else:
            space = 'POSE'
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
    "hip" :             ("GZM_Cube", 1, 0.5),
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
    "eye.R" :           ("GZM_Circle", 0.25, 1.0),
    "eye.L" :           ("GZM_Circle", 0.25, 1.0),
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
    "foot.ik" :         ("GZM_Cube", 0.25),
    "toe.rev" :         ("GZM_ToeRev", 1),
    "foot.2" :          ("GZM_HandIK", 0.7),
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

def setMhxToFk(rig, layers, useInsertKeys, frame):
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
    #for prop in ["MhaForearmFollow_L", "MhaForearmFollow_R"]:
    #    setValue(rig, prop, False)
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


def updateMhxWinders(rig, frame):
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
