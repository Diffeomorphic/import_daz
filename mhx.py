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

import math
from mathutils import *
from .error import *
from .utils import *
from .propgroups import DazPairGroup
from .fix import ConstraintStore, BendTwists, Fixer, GizmoUser

#-------------------------------------------------------------
#   Bone layers
#-------------------------------------------------------------

L_MAIN =    0
L_SPINE =   1

L_LARMIK =  2
L_LARMFK =  3
L_LLEGIK =  4
L_LLEGFK =  5
L_LHAND =   6
L_LFINGER = 7
L_LEXTRA =  12
L_LTOE =    13

L_RARMIK =  18
L_RARMFK =  19
L_RLEGIK =  20
L_RLEGFK =  21
L_RHAND =   22
L_RFINGER = 23
L_REXTRA =  28
L_RTOE =    29

L_FACE =    8
L_TWEAK =   9
L_HEAD =    10
L_CUSTOM =  16

L_HELP =    14
L_HELP2 =   15
L_HIDE =    29
L_FIN =     30
L_DEF =     31


def fkLayers():
    return [L_MAIN, L_SPINE, L_HEAD,
            L_LARMFK, L_LLEGFK, L_LHAND, L_LFINGER,
            L_RARMFK, L_RLEGFK, L_RHAND, L_RFINGER]

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
    eb.layers = layer*[False] + [True] + (31-layer)*[False]
    return eb


def normalizeRoll(roll):
    if roll > 180*D:
        return roll - 360*D
    elif roll < -180*D:
        return roll + 360*D
    else:
        return roll

#-------------------------------------------------------------
#   Constraints
#-------------------------------------------------------------

def copyTransform(bone, target, rig, prop=None, expr="x"):
    cns = bone.constraints.new('COPY_TRANSFORMS')
    cns.name = "Copy Transform %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def copyTransformFkIk(bone, boneFk, boneIk, rig, prop1, prop2=None):
    if boneFk is not None:
        cnsFk = copyTransform(bone, boneFk, rig)
        cnsFk.influence = 1.0
    if boneIk is not None:
        cnsIk = copyTransform(bone, boneIk, rig, prop1)
        cnsIk.influence = 0.0
        if prop2:
            addDriver(cnsIk, "mute", rig, prop2, "x")


def copyLocation(bone, target, rig, prop=None, expr="x"):
    cns = bone.constraints.new('COPY_LOCATION')
    cns.name = "Copy Location %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def copyRotation(bone, target, rig, prop=None, expr="x", space='LOCAL', amt=None):
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
        if amt is None:
            amt = rig
        addDriver(cns, "influence", amt, prop, expr)
    return cns


def copyScale(bone, target, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_SCALE')
    cns.name = "Copy Scale %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.owner_space = space
    cns.target_space = space
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def hintRotation(ikbone, rig):
    cns = limitRotation(ikbone, rig)
    cns.name = "Hint"
    cns.min_x = 18*D
    cns.max_x = 18*D
    cns.use_limit_x = True


def limitRotation(bone, rig, prop=None, expr="x"):
    cns = bone.constraints.new('LIMIT_ROTATION')
    cns.owner_space = 'LOCAL'
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = False
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def ikConstraint(last, target, pole, angle, count, rig, prop=None, expr="x", amt=None):
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
        if amt is None:
            amt = rig
        addDriver(cns, "influence", amt, prop, expr)
    return cns


def stretchTo(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('STRETCH_TO')
    cns.name = "StretchTo %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.volume = "NO_VOLUME"
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def dampedTrack(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('DAMPED_TRACK')
    cns.name = "Damped Track %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def trackTo(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('TRACK_TO')
    cns.name = "TrackTo %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.up_axis = 'UP_Z'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def childOf(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('CHILD_OF')
    cns.name = "ChildOf %s" % target
    cns.target = rig
    cns.subtarget = target
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def armatureConstraint(pb, rig, drivers):
    cns = pb.constraints.new('ARMATURE')
    for bone,prop,expr in drivers:
        target = cns.targets.new()
        target.target = rig
        target.subtarget = bone
        addDriver(target, "weight", rig, prop, expr)
    return cns


def setMhxProp(rig, prop, value):
    setattr(rig, prop, value)
    return
    if not isinstance(value, str):
        rig[prop] = value
    from .driver import setFloatProp, setBoolProp
    if isinstance(value, float):
        setFloatProp(rig, prop, value, 0.0, 1.0, True)
    elif isinstance(value, bool):
        setBoolProp(rig, prop, value, True)


def addDriver(rna, channel, rig, prop, expr):
    from .driver import addDriverVar
    fcu = rna.driver_add(channel)
    fcu.driver.type = 'SCRIPTED'
    if isinstance(prop, str):
        fcu.driver.expression = expr
        addDriverVar(fcu, "x", prop, rig)
    else:
        prop1,prop2 = prop
        fcu.driver.expression = expr
        addDriverVar(fcu, "x1", prop1, rig)
        addDriverVar(fcu, "x2", prop2, rig)


def getPropString(prop, x):
    if isinstance(prop, tuple):
        return prop[1], ("(1-%s)" % (x))
    else:
        return prop, x

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
    bl_options = {'UNDO'}

    addTweakBones : BoolProperty(
        name = "Tweak Bones",
        description = "Add tweak bones",
        default = True
    )

    showLinks : BoolProperty(
        name = "Show Link Bones",
        description = "Show link bones",
        default = True
    )

    useChildOfConstraints : BoolProperty(
        name = "ChildOf Constraints (Experimental)",
        description = ("Use childOf constraints for parents of elbow and knee pole targets.\n" +
                       "May cause problems for FK-IK snapping"),
        default = False
    )

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

    useRenameBones : BoolProperty(
        name = "Rename Face Bones",
        description = "Rename face bones from l/r prefix to .L/.R suffix",
        default = True
    )

    boneGroups : CollectionProperty(
        type = DazPairGroup,
        name = "Bone Groups")

    useRaiseError : BoolProperty(
        name = "Missing Bone Errors",
        description = "Raise error for missing bones",
        default = True
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis"))


    DefaultBoneGroups = [
        ('Spine',        (1,1,0),   (L_MAIN, L_SPINE)),
        ('Left Arm FK',  (0.5,0,0), (L_LARMFK,)),
        ('Right Arm FK', (0,0,0.5), (L_RARMFK,)),
        ('Left Arm IK',  (1,0,0),   (L_LARMIK,)),
        ('Right Arm IK', (0,0,1),   (L_RARMIK,)),
        ('Left Hand',    (1,0,0),   (L_LHAND,)),
        ('Right Hand',   (0,0,1),   (L_RHAND,)),
        ('Left Fingers', (0.5,0,0), (L_LFINGER,)),
        ('Right Fingers',(0,0,0.5), (L_RFINGER,)),
        ('Left Leg FK',  (0.5,0,0), (L_LLEGFK,)),
        ('Right Leg FK', (0,0,0.5), (L_RLEGFK,)),
        ('Left Leg IK',  (1,0,0),   (L_LLEGIK,)),
        ('Right Leg IK', (0,0,1),   (L_RLEGIK,)),
        ('Left Toes',    (0.5,0,0), (L_LTOE,)),
        ('Right Toes',   (0,0,0.5), (L_RTOE,)),
        ('Face',         (0,1,0),   (L_HEAD, L_FACE)),
        ('Tweak',        (0,0.5,0), (L_TWEAK,)),
        ('Custom',       (1,0.5,0), (L_CUSTOM,)),
    ]

    BendTwistBones = [
        ("shin.L", "foot.L", True, "MhaLegStretch_L"),
        ("thigh.L", "shin.L", False, "MhaLegStretch_L"),
        ("forearm.L", "hand.L", True, "MhaArmStretch_L"),
        ("upper_arm.L", "forearm.L", False, "MhaArmStretch_L"),
        ("shin.R", "foot.R", True, "MhaLegStretch_R"),
        ("thigh.R", "shin.R", False, "MhaLegStretch_R"),
        ("forearm.R", "hand.R", True, "MhaArmStretch_R"),
        ("upper_arm.R", "forearm.R", False, "MhaArmStretch_R"),
        ]

    Knees = [
        ("thigh.L", "shin.L", Vector((0,-1,0))),
        ("thigh.R", "shin.R", Vector((0,-1,0))),
        ("upper_arm.L", "forearm.L", Vector((0,1,0))),
        ("upper_arm.R", "forearm.R", Vector((0,1,0))),
    ]

    Correctives = {
        "upper_armBend.L" : "upper_arm.bend.L",
        "forearmBend.L" : "forearm.bend.L",
        "thighBend.L" : "thigh.bend.L",
        "upper_armBend.R" : "upper_arm.bend.R",
        "forearmBend.R" : "forearm.bend.R",
        "thighBend.R" : "thigh.bend.R",

        "lShldrBend(fin)" : "upper_arm.bend.L",
        "lForearmBend(fin)" : "forearm.bend.L",
        "lThighBend(fin)" : "thigh.bend.L",
        "rShldrBend(fin)" : "upper_arm.bend.R",
        "rForearmBend(fin)" : "forearm.bend.R",
        "rThighBend(fin)" : "thigh.bend.R",
    }

    DrivenParents = {
        "lowerFaceRig" :        "lowerJaw",
        drvBone("lowerTeeth") : "lowerJaw",
        drvBone("tongue01") :   "lowerTeeth",
    }

    def __init__(self):
        ConstraintStore.__init__(self)
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "addTweakBones")
        self.layout.prop(self, "showLinks")
        Fixer.draw(self, context)
        self.layout.prop(self, "useChildOfConstraints")
        self.layout.prop(self, "elbowParent")
        self.layout.prop(self, "kneeParent")
        self.layout.prop(self, "useFoot2")
        self.layout.prop(self, "useRenameBones")
        self.layout.prop(self, "useRaiseError")

    def invoke(self, context, event):
        self.createBoneGroups(context.object)
        return DazPropsOperator.invoke(self, context, event)


    def storeState(self, context):
        from .driver import muteDazFcurves
        DazPropsOperator.storeState(self, context)
        muteDazFcurves(context.object, True)


    def restoreState(self, context):
        from .driver import muteDazFcurves
        DazPropsOperator.restoreState(self, context)
        rig = context.object
        muteDazFcurves(rig, rig.DazDriversDisabled)


    def createBoneGroups(self, rig):
        if len(rig.pose.bone_groups) != len(self.DefaultBoneGroups):
            for bg in list(rig.pose.bone_groups):
                rig.pose.bone_groups.remove(bg)
            for bgname,color,_layers in self.DefaultBoneGroups:
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
        from time import perf_counter
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


    def convertMhx(self, context):
        from .merge import reparentToes
        from .figure import finalizeArmature
        if self.useKeepRig:
            self.saveExistingRig(context)
        rig = context.object
        rig.DazMhxLegacy = False
        finalizeArmature(rig)
        self.createBoneGroups(rig)
        self.startGizmos(context, rig)

        #-------------------------------------------------------------
        #   MHX skeleton
        #   (mhx, genesis, layer)
        #-------------------------------------------------------------

        self.skeleton = [
            ("hip", "hip", L_MAIN),
            ("pelvis", "pelvis", L_SPINE),

            ("thigh.L", "lThigh", L_LLEGFK),
            ("thighBend.L", "lThighBend", L_LLEGFK),
            ("thighTwist.L", "lThighTwist", L_LLEGFK),
            ("shin.L", "lShin", L_LLEGFK),
            ("foot.L", "lFoot", L_LLEGFK),
            ("toe.L", "lToe", L_LLEGFK),
            ("heel.L", "lHeel", L_LTOE),
            ("tarsal.L", "lMetatarsals", L_LTOE),

            ("thigh.R", "rThigh", L_RLEGFK),
            ("thighBend.R", "rThighBend", L_RLEGFK),
            ("thighTwist.R", "rThighTwist", L_RLEGFK),
            ("shin.R", "rShin", L_RLEGFK),
            ("foot.R", "rFoot", L_RLEGFK),
            ("toe.R", "rToe", L_RLEGFK),
            ("heel.R", "rHeel", L_RTOE),
            ("tarsal.R", "rMetatarsals", L_RTOE),

            ("spine", "abdomenLower", L_SPINE),
            ("spine", "abdomen", L_SPINE),
            ("spine-1", "abdomenUpper", L_SPINE),
            ("spine-1", "abdomen2", L_SPINE),
            ("chest", "chest", L_SPINE),
            ("chest", "chestLower", L_SPINE),
            ("chest-1", "chestUpper", L_SPINE),
            ("pectoral.L", "lPectoral", L_TWEAK),
            ("pectoral.R", "rPectoral", L_TWEAK),
            ("neck", "neck", L_SPINE),
            ("neck", "neckLower", L_SPINE),
            ("neck-1", "neckUpper", L_SPINE),
            ("head", "head", L_SPINE),

            ("clavicle.L", "lCollar", L_LARMFK),
            ("upper_arm.L", "lShldr", L_LARMFK),
            ("upper_armBend.L", "lShldrBend", L_LARMFK),
            ("upper_armTwist.L", "lShldrTwist", L_LARMFK),
            ("forearm.L", "lForeArm", L_LARMFK),
            ("forearmBend.L", "lForearmBend", L_LARMFK),
            ("forearmTwist.L", "lForearmTwist", L_LARMFK),
            ("hand.L", "lHand", L_LARMFK),
            ("palm_index.L", "lCarpal1", L_LFINGER),
            ("palm_middle.L", "lCarpal2", L_LFINGER),
            ("palm_ring.L", "lCarpal3", L_LFINGER),
            ("palm_pinky.L", "lCarpal4", L_LFINGER),

            ("clavicle.R", "rCollar", L_RARMFK),
            ("upper_arm.R", "rShldr", L_RARMFK),
            ("upper_armBend.R", "rShldrBend", L_RARMFK),
            ("upper_armTwist.R", "rShldrTwist", L_RARMFK),
            ("forearm.R", "rForeArm", L_RARMFK),
            ("forearmBend.R", "rForearmBend", L_RARMFK),
            ("forearmTwist.R", "rForearmTwist", L_RARMFK),
            ("hand.R", "rHand", L_RARMFK),
            ("palm_index.R", "rCarpal1", L_RFINGER),
            ("palm_middle.R", "rCarpal2", L_RFINGER),
            ("palm_ring.R", "rCarpal3", L_RFINGER),
            ("palm_pinky.R", "rCarpal4", L_RFINGER),

            ("thumb.01.L", "lThumb1", L_LFINGER),
            ("thumb.02.L", "lThumb2", L_LFINGER),
            ("thumb.03.L", "lThumb3", L_LFINGER),
            ("f_index.01.L", "lIndex1", L_LFINGER),
            ("f_index.02.L", "lIndex2", L_LFINGER),
            ("f_index.03.L", "lIndex3", L_LFINGER),
            ("f_middle.01.L", "lMid1", L_LFINGER),
            ("f_middle.02.L", "lMid2", L_LFINGER),
            ("f_middle.03.L", "lMid3", L_LFINGER),
            ("f_ring.01.L", "lRing1", L_LFINGER),
            ("f_ring.02.L", "lRing2", L_LFINGER),
            ("f_ring.03.L", "lRing3", L_LFINGER),
            ("f_pinky.01.L", "lPinky1", L_LFINGER),
            ("f_pinky.02.L", "lPinky2", L_LFINGER),
            ("f_pinky.03.L", "lPinky3", L_LFINGER),

            ("thumb.01.R", "rThumb1", L_RFINGER),
            ("thumb.02.R", "rThumb2", L_RFINGER),
            ("thumb.03.R", "rThumb3", L_RFINGER),
            ("f_index.01.R", "rIndex1", L_RFINGER),
            ("f_index.02.R", "rIndex2", L_RFINGER),
            ("f_index.03.R", "rIndex3", L_RFINGER),
            ("f_middle.01.R", "rMid1", L_RFINGER),
            ("f_middle.02.R", "rMid2", L_RFINGER),
            ("f_middle.03.R", "rMid3", L_RFINGER),
            ("f_ring.01.R", "rRing1", L_RFINGER),
            ("f_ring.02.R", "rRing2", L_RFINGER),
            ("f_ring.03.R", "rRing3", L_RFINGER),
            ("f_pinky.01.R", "rPinky1", L_RFINGER),
            ("f_pinky.02.R", "rPinky2", L_RFINGER),
            ("f_pinky.03.R", "rPinky3", L_RFINGER),

            ("big_toe.01.L", "lBigToe", L_LTOE),
            ("small_toe_1.01.L", "lSmallToe1", L_LTOE),
            ("small_toe_2.01.L", "lSmallToe2", L_LTOE),
            ("small_toe_3.01.L", "lSmallToe3", L_LTOE),
            ("small_toe_4.01.L", "lSmallToe4", L_LTOE),
            ("big_toe.02.L", "lBigToe_2", L_LTOE),
            ("small_toe_1.02.L", "lSmallToe1_2", L_LTOE),
            ("small_toe_2.02.L", "lSmallToe2_2", L_LTOE),
            ("small_toe_3.02.L", "lSmallToe3_2", L_LTOE),
            ("small_toe_4.02.L", "lSmallToe4_2", L_LTOE),

            ("big_toe.01.R", "rBigToe", L_RTOE),
            ("small_toe_1.01.R", "rSmallToe1", L_RTOE),
            ("small_toe_2.01.R", "rSmallToe2", L_RTOE),
            ("small_toe_3.01.R", "rSmallToe3", L_RTOE),
            ("small_toe_4.01.R", "rSmallToe4", L_RTOE),
            ("big_toe.02.R", "rBigToe_2", L_RTOE),
            ("small_toe_1.02.R", "rSmallToe1_2", L_RTOE),
            ("small_toe_2.02.R", "rSmallToe2_2", L_RTOE),
            ("small_toe_3.02.R", "rSmallToe3_2", L_RTOE),
            ("small_toe_4.02.R", "rSmallToe4_2", L_RTOE),
        ]

        self.sacred = ["root", "hips", "spine"]

        #-------------------------------------------------------------
        #   Fix and rename bones of the genesis rig
        #-------------------------------------------------------------

        showProgress(1, 25, "  Fix DAZ rig")
        self.constraints = {}
        rig.data.layers = 32*[True]
        bchildren = applyBoneChildren(context, rig)
        for pb in rig.pose.bones:
            pb.driver_remove("HdOffset")
            pb.driver_remove("TlOffset")
        if rig.DazRig in ["genesis3", "genesis8"]:
            showProgress(2, 25, "  Connect to parent")
            connectToParent(rig)
            showProgress(3, 25, "  Reparent toes")
            reparentToes(rig, context, False)
            showProgress(4, 25, "  Rename bones")
            self.deleteBendTwistDrvBones(rig)
            self.rename2Mhx(rig)
            showProgress(5, 25, "  Join bend and twist bones")
            self.joinBendTwists(rig, {}, keep=False, useJoin=False)
            showProgress(6, 25, "  Fix knees")
            self.fixKnees(rig)
            showProgress(7, 25, "  Fix hands")
            self.fixHands(rig)
            showProgress(8, 25, "  Store all constraints")
            self.storeAllConstraints(rig)
            showProgress(9, 25, "  Create bend and twist bones")
            self.createBendTwists(rig)
            showProgress(10, 25, "  Fix bone drivers")
            self.fixBoneDrivers(rig, self.Correctives)
        elif rig.DazRig in ["genesis1", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            connectToParent(rig)
            reparentToes(rig, context, False)
            self.rename2Mhx(rig)
            self.fixGenesis2Problems(rig)
            self.fixKnees(rig)
            self.fixHands(rig)
            self.storeAllConstraints(rig)
            self.createBendTwists(rig)
            self.fixBoneDrivers(rig, self.Correctives)
        else:
            raise DazError("Cannot convert %s to Mhx" % rig.name)

        #-------------------------------------------------------------
        #   Add MHX stuff
        #-------------------------------------------------------------

        showProgress(12, 25, "  Add long fingers")
        self.addLongFingers(rig)
        showProgress(13, 25, "  Add tweak bones")
        self.addTweaks(rig)
        showProgress(14, 25, "  Add backbone")
        self.addBack(rig)
        showProgress(15, 25, "  Add master bone")
        self.addMaster(rig)
        showProgress(16, 25, "  Setup FK-IK")
        self.setupFkIk(rig)
        showProgress(17, 25, "  Add layers")
        self.addLayers(rig)
        showProgress(18, 25, "  Add markers")
        self.addMarkers(rig)
        showProgress(19, 25, "  Add gizmos")
        self.addGizmos(rig, context)
        showProgress(11, 25, "  Constrain bend and twist bones")
        self.constrainBendTwists(rig)
        self.addCopyLocConstraints(rig)
        self.addChildofConstraints(rig)
        showProgress(20, 25, "  Restore constraints")
        self.restoreAllConstraints(rig)
        showProgress(21, 25, "  Fix constraints")
        deletes = self.fixConstraints(rig)
        self.addTongueIk(rig)
        self.fixDrivers(rig.data)
        if rig.DazRig in ["genesis3", "genesis8"]:
            self.fixCustomShape(rig, ["head"], 4)
        showProgress(22, 25, "  Collect deform bones")
        self.collectDeformBones(rig)
        setMode('POSE')
        showProgress(23, 25, "  Rename face bones")
        self.renameFaceBones(rig, ["Eye", "Ear"])
        showProgress(24, 25, "  Add bone groups")
        self.addBoneGroups(rig)
        rig.MhxRig = True
        rig.data.display_type = 'OCTAHEDRAL'
        rig.data.display_type = 'WIRE'
        T = True
        F = False
        rig.data.layers = [T,T,T,F, T,F,T,F, F,F,F,F, F,F,F,F,
                           F,F,T,F, T,F,T,F, F,F,F,F, F,F,F,F]
        rig.DazRig = "mhx"

        for pb in rig.pose.bones:
            pb.bone.select = False
            if pb.custom_shape:
                pb.bone.show_wire = True

        self.restoreBoneChildren(bchildren, context, rig)
        updateAll(context)


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
            heel.layers = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]

    #-------------------------------------------------------------
    #   Rename bones
    #-------------------------------------------------------------

    def rename2Mhx(self, rig):
        fixed = []
        helpLayer = L_HELP*[False] + [True] + (31-L_HELP)*[False]
        deformLayer = 31*[False] + [True]

        setMode('EDIT')
        for bname,pname in self.DrivenParents.items():
            if (bname in rig.data.edit_bones.keys() and
                pname in rig.data.edit_bones.keys()):
                eb = rig.data.edit_bones[bname]
                parb = rig.data.edit_bones[pname]
                eb.parent = parb
                eb.layers = helpLayer
                fixed.append(bname)

        setMode('OBJECT')
        for bone in rig.data.bones:
            if bone.name in self.sacred:
                bone.name = bone.name + ".1"

        for mname,dname,layer in self.skeleton:
            if dname in rig.data.bones.keys():
                bone = rig.data.bones[dname]
                if dname != mname:
                    bone.name = mname
                bone.layers = layer*[False] + [True] + (31-layer)*[False]
                fixed.append(mname)

        for pb in rig.pose.bones:
            bname = pb.name
            lname = bname.lower()
            if bname in fixed:
                continue
            layer,unlock = getBoneLayer(pb, rig)
            pb.bone.layers = layer*[False] + [True] + (31-layer)*[False]
            if False and unlock:
                pb.lock_location = (False,False,False)


    def restoreBoneChildren(self, bchildren, context, rig):
        from .node import setParent
        layers = list(rig.data.layers)
        rig.data.layers = 32*[True]
        for (ob, bname) in bchildren:
            bone = self.getMhxBone(rig, bname)
            if bone:
                setParent(context, ob, rig, bone.name)
            else:
                print("Could not restore bone parent for %s", ob.name)
        rig.data.layers = layers


    def getMhxBone(self, rig, bname):
        if bname in rig.data.bones.keys():
            return rig.data.bones[bname]
        for mname,dname,_ in self.skeleton:
            if dname == bname:
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
        self.makeGizmos(None)

        for pb in rig.pose.bones:
            if isDrvBone(pb.name) or isFinal(pb.name):
                continue
            elif pb.name in Gizmos.keys():
                gizmo,scale = Gizmos[pb.name]
                self.addGizmo(pb, gizmo, scale)
            elif pb.name[-2:] in [".L", ".R"] and pb.name[:-2] in LRGizmos.keys():
                gizmo,scale = LRGizmos[pb.name[:-2]]
                self.addGizmo(pb, gizmo, scale)
            elif pb.name[0:4] == "palm":
                self.addGizmo(pb, "GZM_Ellipse", 1)
            elif pb.name[0:6] == "tongue":
                self.addGizmo(pb, "GZM_MTongue", 1)
            elif self.isFaceBone(pb) and not self.isEyeLid(pb):
                self.addGizmo(pb, "GZM_Circle", 0.2)
            else:
                for pname in self.FingerNames + ["big_toe", "small_toe"]:
                    if pb.name.startswith(pname):
                        self.addGizmo(pb, "GZM_Circle", 0.4)
                for pname,shape,scale in [
                        ("pectoral", "GZM_Ball025", 1) ,
                        ("heel", "GZM_Ball025End", 1)]:
                    if pb.name.startswith(pname):
                        if isBoneDriven(rig, pb):
                            pb.bone.layers[L_HELP] = True
                            pb.bone.layers[L_TWEAK] = False
                        else:
                            self.addGizmo(pb, shape, scale)

        for bname in self.tweakBones:
            if bname is None:
                continue
            if bname.startswith(("pelvis", "chest", "clavicle")):
                gizmo = "GZM_Ball025End"
            else:
                gizmo = "GZM_Ball025"
            twkname = self.getTweakBoneName(bname)
            if twkname in rig.pose.bones.keys():
                tb = rig.pose.bones[twkname]
                self.addGizmo(tb, gizmo, 1, blen=10*rig.DazScale)

    #-------------------------------------------------------------
    #   Bone groups
    #-------------------------------------------------------------

    def addBoneGroups(self, rig):
        for idx,data in enumerate(self.DefaultBoneGroups):
            _bgname,_theme,layers = data
            bgrp = rig.pose.bone_groups[idx]
            for pb in rig.pose.bones.values():
                for layer in layers:
                    if pb.bone.layers[layer]:
                        pb.bone_group = bgrp

    #-------------------------------------------------------------
    #   Backbone
    #-------------------------------------------------------------

    def addBack(self, rig):
        BackBones = ["spine", "spine-1", "chest", "chest-1"]
        NeckBones = ["neck", "neckLower", "neckUpper", "head"]

        setMode('EDIT')
        if "spine" in rig.data.edit_bones:
            spine = rig.data.edit_bones["spine"]
        else:
            return self.raiseError("spine")
        if "chest-1" in rig.data.edit_bones:
            chest = rig.data.edit_bones["chest-1"]
        elif "chest" in rig.data.edit_bones:
            chest = rig.data.edit_bones["chest"]
        else:
            return self.raiseError("chest")
        makeBone("back", rig, spine.head, chest.tail, 0, L_MAIN, spine.parent)
        if "neck" in rig.data.edit_bones:
            neck = rig.data.edit_bones["neck"]
        elif "neckLower" in rig.data.edit_bones:
            neck = rig.data.edit_bones["neckLower"]
        else:
            return self.raiseError("neck")
        if "head" in rig.data.edit_bones:
            head = rig.data.edit_bones["head"]
        else:
            return self.raiseError("head")
        makeBone("neckhead", rig, neck.head, head.tail, 0, L_MAIN, neck.parent)
        setMode('POSE')
        self.addBackWinder(rig, "back", BackBones)
        self.addBackWinder(rig, "neckhead", NeckBones)


    def addBackWinder(self, rig, bname, bones):
        back = rig.pose.bones[bname]
        back.rotation_mode = 'YZX'
        back.lock_location = (True,True,True)
        for bname in bones:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                cns = copyRotation(pb, back, rig)
                cns.use_offset = True

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
            None, "hand.L", None, "foot.L",
            None, "hand.R", None, "foot.R",
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
        tweakLayers = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]
        for bname in self.tweakBones:
            if bname is None:
                sb = None
            elif bname in rig.data.edit_bones.keys():
                tb = rig.data.edit_bones[bname]
                tb.name = self.getTweakBoneName(bname)
                conn = tb.use_connect
                tb.use_connect = False
                tb.layers = tweakLayers
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

    FingerNames = ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]
    PalmNames = ["palm_thumb", "palm_index", "palm_index", "palm_middle", "palm_middle"]

    def linkName(self, m, n, suffix):
        return ("%s.0%d.%s" % (self.FingerNames[m], n+1, suffix))


    def longName(self, m, suffix):
        fname = self.FingerNames[m]
        if fname[0:2] == "f_":
            return "%s.%s" % (fname[2:], suffix)
        else:
            return "%s.%s" % (fname, suffix)


    def palmName(self, m, suffix):
        return "%s.%s" % (self.PalmNames[m], suffix)


    def addLongFingers(self, rig):
        setMode('EDIT')
        for suffix,dlayer in [("L",0), ("R",16)]:
            hand = rig.data.edit_bones["hand.%s" % suffix]
            for m in range(5):
                if m == 0:
                    fing1Name = self.linkName(0, 1, suffix)
                    palmName = self.linkName(0, 0, suffix)
                else:
                    fing1Name = self.linkName(m, 0, suffix)
                    palmName = self.palmName(m, suffix)
                if fing1Name in rig.data.edit_bones.keys():
                    fing1 = rig.data.edit_bones[fing1Name]
                else:
                    self.raiseError(fing1Name)
                    continue
                if palmName in rig.data.edit_bones.keys():
                    palm = rig.data.edit_bones[palmName]
                else:
                    self.raiseError(palmName)
                    continue
                fing3Name = self.linkName(m, 2, suffix)
                if fing3Name in rig.data.edit_bones.keys():
                    fing3 = rig.data.edit_bones[fing3Name]
                else:
                    self.raiseError(fing3Name)
                    continue
                makeBone(self.longName(m, suffix), rig, fing1.head, fing3.tail, fing1.roll, L_LHAND+dlayer, palm)
                if self.useFingerIk:
                    vec = fing3.tail - fing3.head
                    makeBone("ik_" + self.longName(m, suffix), rig, fing3.tail, fing3.tail+vec, fing3.roll, L_LHAND+dlayer, hand)

        setMode('POSE')
        for suffix,dlayer in [("L",0), ("R",16)]:
            prop1 = "MhaFingerControl_%s" % suffix
            setMhxProp(rig, prop1, True)
            prop2 = "MhaFingerIk_%s" % suffix
            setMhxProp(rig, prop2, False)
            if self.useFingerIk:
                props = (prop1,prop2)
                expr = "(x2 or not(x1))"
            else:
                props = prop1
                expr = "not(x)"
            thumb1Name = self.linkName(0, 0, suffix)
            if thumb1Name in rig.data.bones.keys():
                thumb1 = rig.data.bones[thumb1Name]
            else:
                self.raiseError(thumb1Name)
                continue
            thumb1.layers[L_LHAND+dlayer] = True
            for m in range(5):
                if m == 0:
                    n0 = 1
                else:
                    n0 = 0
                long = rig.pose.bones[self.longName(m, suffix)]
                long.lock_location = (True,True,True)
                long.lock_rotation = (False,True,False)
                fing = rig.pose.bones[self.linkName(m, n0, suffix)]
                fing.lock_rotation = (False,True,False)
                long.rotation_mode = fing.rotation_mode
                cns = copyRotation(fing, long, rig)
                cns.use_offset = True
                addDriver(cns, "mute", rig, props, expr)
                addDriver(long.bone, "hide", rig, props, expr)
                for n in range(n0+1,3):
                    fing = rig.pose.bones[self.linkName(m, n, suffix)]
                    fing.lock_rotation = (False,True,True)
                    cns = copyRotation(fing, long, rig)
                    cns.use_y = cns.use_z = False
                    cns.use_offset = True
                    addDriver(cns, "mute", rig, props, expr)

    #-------------------------------------------------------------
    #   FK/IK
    #-------------------------------------------------------------

    def setLayer(self, bname, rig, layer):
        eb = rig.data.edit_bones[bname]
        eb.layers = layer*[False] + [True] + (31-layer)*[False]
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
        self.rolls = {}
        hip = rig.data.edit_bones["hip"]
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
            rig.data.edit_bones["upper_arm.bend.%s" % suffix].parent = armParent

            upper_armFk = deriveBone("upper_arm.fk.%s" % suffix, upper_arm, rig, L_LARMFK+dlayer, armParent)
            forearmFk = deriveBone("forearm.fk.%s" % suffix, forearm, rig, L_LARMFK+dlayer, upper_armFk)
            setConnected(forearmFk, forearm.use_connect)
            handFk = deriveBone("hand.fk.%s" % suffix, hand, rig, L_LARMFK+dlayer, forearmFk)
            handFk.use_connect = False
            upper_armIk = deriveBone("upper_arm.ik.%s" % suffix, upper_arm, rig, L_HELP2, armParent)
            forearmIk = deriveBone("forearm.ik.%s" % suffix, forearm, rig, L_HELP2, upper_armIk)
            setConnected(forearmIk, forearm.use_connect)
            handIk = deriveBone("hand.ik.%s" % suffix, hand, rig, L_LARMIK+dlayer, self.master)
            hand0Ik = deriveBone("hand0.ik.%s" % suffix, hand, rig, L_HELP2, forearmIk)
            upper_armIkTwist = deriveBone("upper_arm.ik.twist.%s" % suffix, upper_arm, rig, L_LARMIK+dlayer, upper_armIk)
            forearmIkTwist = deriveBone("forearm.ik.twist.%s" % suffix, forearm, rig, L_LARMIK+dlayer, forearmIk)

            vec = upper_arm.matrix.to_3x3().col[2]
            vec.normalize()
            dist = max(upper_arm.length, forearm.length)
            locElbowPt = forearm.head - 1.2*dist*vec
            elbowPoleA = makeBone("elbowPoleA.%s" % suffix, rig, armSocket.head, armSocket.head-ez, 0, L_LARMIK+dlayer, armSocket)
            elbowPoleP = makeBone("elbowPoleP.%s" % suffix, rig, forearm.head, forearm.head-ez, 0, L_HELP2, armParent)
            parent = self.getElbowParent(rig, suffix)
            elbowPt = makeBone("elbow.pt.ik.%s" % suffix, rig, locElbowPt, locElbowPt+ez, 0, L_LARMIK+dlayer, parent)
            elbowLink = makeBone("elbow.link.%s" % suffix, rig, forearm.head, locElbowPt, 0, L_LARMIK+dlayer, upper_armIk)
            if self.showLinks:
                elbowLink.hide_select = True
            else:
                elbowLink.layers = L_HIDE*[False] + [True] + (31-L_HIDE)*[False]

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
            rig.data.edit_bones["thigh.bend.%s" % suffix].parent = legParent

            thighFk = deriveBone("thigh.fk.%s" % suffix, thigh, rig, L_LLEGFK+dlayer, thigh.parent)
            shinFk = deriveBone("shin.fk.%s" % suffix, shin, rig, L_LLEGFK+dlayer, thighFk)
            setConnected(shinFk, shin.use_connect)
            footFk = deriveBone("foot.fk.%s" % suffix, foot, rig, L_LLEGFK+dlayer, shinFk)
            footFk.use_connect = False
            toeFk = deriveBone("toe.fk.%s" % suffix, toe, rig, L_LLEGFK+dlayer, footFk)
            setConnected(toeFk, True)
            thighIk = deriveBone("thigh.ik.%s" % suffix, thigh, rig, L_HELP2, thigh.parent)
            shinIk = deriveBone("shin.ik.%s" % suffix, shin, rig, L_HELP2, thighIk)
            setConnected(shinIk, shin.use_connect)
            thighIkTwist = deriveBone("thigh.ik.twist.%s" % suffix, thigh, rig, L_LLEGIK+dlayer, thighIk)
            thighIkTwist.layers[L_LEXTRA+dlayer] = True
            shinIkTwist = deriveBone("shin.ik.twist.%s" % suffix, shin, rig, L_LLEGIK+dlayer, shinIk)
            shinIkTwist.layers[L_LEXTRA+dlayer] = True

            if "heel.%s" % suffix in rig.data.edit_bones.keys():
                heel = rig.data.edit_bones["heel.%s" % suffix]
                locFootIk = (foot.head[0], heel.tail[1], toe.tail[2])
            else:
                vec = foot.tail - foot.head
                locFootIk = (foot.head[0], foot.head[1] - 0.5*vec[1], toe.tail[2])
            footIk = makeBone("foot.ik.%s" % suffix, rig, locFootIk, toe.tail, 180*D, L_LLEGIK+dlayer, self.master)
            toeRev = makeBone("toe.rev.%s" % suffix, rig, toe.tail, toe.head, 0, L_LLEGIK+dlayer, footIk)
            setConnected(toeRev, True)
            footRev = makeBone("foot.rev.%s" % suffix, rig, toe.head, foot.head, 0, L_LLEGIK+dlayer, toeRev)
            setConnected(footRev, True)
            locAnkle = foot.head + (shin.tail-shin.head)/4
            if self.useFoot2:
                foot2 = deriveBone("foot.2.%s" % suffix, foot, rig, L_LEXTRA+dlayer, self.master)
                setConnected(foot2, False)
                toe2 = deriveBone("toe.2.%s" % suffix, toe, rig, L_LEXTRA+dlayer, foot2)
                setConnected(toe2, True)
            ankleIk = deriveBone("ankle.ik.%s" % suffix, foot, rig, L_HELP2, footRev)

            vec = thigh.matrix.to_3x3().col[2]
            vec.normalize()
            dist = max(thigh.length, shin.length)
            locKneePt = shin.head - 1.2*dist*vec
            kneePoleA = makeBone("kneePoleA.%s" % suffix, rig, legSocket.head, legSocket.head-ez, 0, L_LLEGIK+dlayer, legSocket)
            kneePoleP = makeBone("kneePoleP.%s" % suffix, rig, shin.head, shin.head-ez, 0, L_HELP2, hip)
            kneePoleA.layers[L_LEXTRA+dlayer] = True
            parent = self.getKneeParent(rig, suffix)
            kneePt = makeBone("knee.pt.ik.%s" % suffix, rig, locKneePt, locKneePt+ez, 0, L_LLEGIK+dlayer, parent)
            kneePt.layers[L_LEXTRA+dlayer] = True
            kneeLink = makeBone("knee.link.%s" % suffix, rig, shin.head, locKneePt, 0, L_LLEGIK+dlayer, thighIk)
            if self.showLinks:
                kneeLink.layers[L_LEXTRA+dlayer] = True
                kneeLink.hide_select = True
            else:
                kneeLink.layers = L_HIDE*[False] + [True] + (31-L_HIDE)*[False]

            footInvFk = deriveBone("foot.inv.fk.%s" % suffix, footRev, rig, L_HELP2, footFk)
            toeInvFk = deriveBone("toe.inv.fk.%s" % suffix, toeRev, rig, L_HELP2, toeFk)
            footInvIk = deriveBone("foot.inv.ik.%s" % suffix, foot, rig, L_HELP2, footRev)
            toeInvIk = deriveBone("toe.inv.ik.%s" % suffix, toe, rig, L_HELP2, toeRev)

            self.addSingleGazeBone(rig, suffix, L_HEAD, L_HELP)

            for bname in ["upper_arm.fk", "forearm.fk", "hand.fk",
                          "thigh.fk", "shin.fk", "foot.fk", "toe.fk"]:
                self.rolls["%s.%s" % (bname,suffix)] = rig.data.edit_bones["%s.%s" % (bname,suffix)].roll

        self.addCombinedGazeBone(rig, L_HEAD, L_HELP)
        self.addTongueIkBone(rig, L_HEAD)

        from .figure import copyBoneInfo
        setMode('OBJECT')
        setMode('POSE')
        rpbs = rig.pose.bones
        master = rpbs["master"]
        for suffix in ["L", "R"]:
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
            upper_armIkTwist = rpbs["upper_arm.ik.twist.%s" % suffix]
            forearmIkTwist = rpbs["forearm.ik.twist.%s" % suffix]
            handIk = rpbs["hand.ik.%s" % suffix]
            hand0Ik = rpbs["hand0.ik.%s" % suffix]
            elbowPt = rpbs["elbow.pt.ik.%s" % suffix]
            elbowLink = rpbs["elbow.link.%s" % suffix]

            prop = "MhaForearmFollow_%s" % suffix
            setMhxProp(rig, prop, True)
            prop = "MhaArmHinge_%s" % suffix
            setMhxProp(rig, prop, 0.0)
            cns = copyTransform(armParent, armSocket, rig)
            addDriver(cns, "influence", rig, prop, "1-x")
            cns = copyLocation(armParent, armSocket, rig)
            addDriver(cns, "influence", rig, prop, "x")

            prop = "MhaArmIk_%s" % suffix
            setMhxProp(rig, prop, 1.0)
            copyTransformFkIk(upper_arm, upper_armFk, upper_armIkTwist, rig, prop)
            copyTransformFkIk(forearm, forearmFk, forearmIkTwist, rig, prop)
            copyTransformFkIk(hand, handFk, handIk, rig, prop)
            copyTransform(hand0Ik, handIk, rig)

            elbowPoleA = rpbs["elbowPoleA.%s" % suffix]
            elbowPoleP = rpbs["elbowPoleP.%s" % suffix]
            elbowPoleA.lock_location = (True,True,True)
            elbowPoleA.lock_rotation = (True,False,True)
            dampedTrack(elbowPoleA, handIk, rig)
            cns = copyLocation(elbowPoleA, handIk, rig)
            cns.influence = upper_arm.bone.length/(upper_arm.bone.length + forearm.bone.length)
            copyTransform(elbowPoleP, elbowPoleA, rig)
            if not self.useChildOfConstraints:
                setMhxProp(rig, "MhaElbowParent_%s" % suffix, self.elbowParent)

            #hintRotation(forearmIk, rig)
            ikConstraint(forearmIk, handIk, elbowPt, -90, 2, rig)
            stretchTo(elbowLink, elbowPt, rig)
            elbowPt.rotation_euler[0] = -90*D
            elbowPt.lock_rotation = (True,True,True)

            cns1 = copyRotation(forearm, handFk, rig, space='LOCAL')
            cns2 = copyRotation(forearm, hand0Ik, rig, prop, space='LOCAL')
            cns1.use_x = cns1.use_z = cns2.use_x = cns2.use_z = False
            forearmFk.lock_rotation[1] = True

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
            thighIkTwist = rpbs["thigh.ik.twist.%s" % suffix]
            shinIkTwist = rpbs["shin.ik.twist.%s" % suffix]
            kneePt = rpbs["knee.pt.ik.%s" % suffix]
            kneeLink = rpbs["knee.link.%s" % suffix]
            footIk = rpbs["foot.ik.%s" % suffix]
            toeRev = rpbs["toe.rev.%s" % suffix]
            footRev = rpbs["foot.rev.%s" % suffix]
            footInvIk = rpbs["foot.inv.ik.%s" % suffix]
            toeInvIk = rpbs["toe.inv.ik.%s" % suffix]

            prop = "MhaLegHinge_%s" % suffix
            setMhxProp(rig, prop, 0.0)
            cns = copyTransform(legParent, legSocket, rig)
            addDriver(cns, "influence", rig, prop, "1-x")
            cns = copyLocation(legParent, legSocket, rig)
            addDriver(cns, "influence", rig, prop, "x")

            prop1 = "MhaLegIk_%s" % suffix
            setMhxProp(rig, prop1, 1.0)
            prop2 = "MhaLegIkToAnkle_%s" % suffix
            setMhxProp(rig, prop2, 0.0)

            footRev.lock_rotation = (False,True,True)

            copyTransformFkIk(thigh, thighFk, thighIkTwist, rig, prop1)
            copyTransformFkIk(shin, shinFk, shinIkTwist, rig, prop1)
            copyTransformFkIk(foot, footFk, footInvIk, rig, prop1, prop2)
            copyTransformFkIk(toe, toeFk, toeInvIk, rig, prop1, prop2)

            kneePoleA = rpbs["kneePoleA.%s" % suffix]
            kneePoleP = rpbs["kneePoleP.%s" % suffix]
            kneePoleA.lock_location = (True,True,True)
            kneePoleA.lock_rotation = (True,False,True)
            dampedTrack(kneePoleA, ankleIk, rig)
            cns = copyLocation(kneePoleA, ankleIk, rig)
            cns.influence = thigh.bone.length/(thigh.bone.length + shin.bone.length)
            copyTransform(kneePoleP, kneePoleA, rig)
            if not self.useChildOfConstraints:
                setMhxProp(rig, "MhaKneeParent_%s" % suffix, self.kneeParent)

            fixIk(rig, [shinIk.name])
            ikConstraint(shinIk, ankleIk, kneePt, -90, 2, rig)
            stretchTo(kneeLink, kneePt, rig)
            kneePt.rotation_euler[0] = 90*D
            kneePt.lock_rotation = (True,True,True)
            if self.useFoot2:
                copyTransform(ankleIk, foot2, rig, prop2)
                copyTransform(foot, foot2, rig, prop2)
                copyTransform(toe, toe2, rig, prop2)

            self.addGazeConstraint(rig, suffix)

            self.lockLocations([
                upper_armFk, forearmFk,
                upper_armIk, forearmIk, upper_armIkTwist, forearmIkTwist, elbowLink,
                thighFk, shinFk, toeFk,
                thighIk, shinIk, thighIkTwist, shinIkTwist, kneeLink, footRev, toeRev,
            ])
            handFk.lock_location = footFk.lock_location = (False,False,False)

        self.addGazeFollowsHead(rig)
        setMhxProp(rig, "MhaLimitsOn", True)
        for prop in ["MhaToeTarsal_L", "MhaToeTarsal_R"]:
            setMhxProp(rig, prop, False)


    def lockLocations(self, bones):
        for pb in bones:
            lock = (not pb.bone.use_connect)
            pb.lock_location = (lock,lock,lock)

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
                setMhxProp(rig, prop, 0.0)
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
            setMhxProp(rig, handprop, (float)(self.elbowParent=='HAND'))
            setMhxProp(rig, shoulderprop, (float)(self.elbowParent=='SHOULDER'))
            pb = rig.pose.bones["elbow.pt.ik.%s" % suffix]
            cns = childOf(pb, "master", rig, (handprop, shoulderprop), "1-min(1,x1+x2)")
            cns.name = "ChildOf Master"
            cns = childOf(pb, "elbowPoleP.%s" % suffix, rig, handprop, "x")
            cns.name = "ChildOf Hand"
            cns = childOf(pb, "arm_parent.%s" % suffix, rig, shoulderprop, "x")
            cns.name = "ChildOf Shoulder"

            footprop = "MhaKneeFoot_%s" % suffix
            hipprop = "MhaKneeHip_%s" % suffix
            setMhxProp(rig, footprop, (float)(self.kneeParent=='FOOT'))
            setMhxProp(rig, hipprop, (float)(self.kneeParent=='HIP'))
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
            self.unlimitYrot(rig, "hand.fk.%s" % suffix)
            if self.useFingerIk:
                self.addFingerIk(rig, suffix)
            self.copyToeRotation(rig, True, suffix, ["big_toe.01", "small_toe_1.01", "small_toe_2.01", "small_toe_3.01", "small_toe_4.01"])


    def flipLimits(self, rig, bname, oldname):
        roll = self.rolls[bname]
        oldroll = self.rolls[oldname]
        flip = round(2*(roll-oldroll)/math.pi)
        if flip:
            self.flips[bname.replace(".fk", "")] = flip
            print("FLIP", bname, flip)
            pb = rig.pose.bones[bname]
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


    def unlimitYrot(self, rig, bname):
        pb = rig.pose.bones[bname]
        cns = getConstraint(pb, 'LIMIT_ROTATION')
        if cns:
            cns.use_limit_y = False


    def copyIkLimits(self, rig, bname, suffix):
        fkbone = rig.pose.bones["%s.fk.%s" % (bname, suffix)]
        ikbone = rig.pose.bones["%s.ik.%s" % (bname, suffix)]
        iktwist = rig.pose.bones["%s.ik.twist.%s" % (bname, suffix)]
        iktwist.lock_rotation = (True,False,True)
        cns = getConstraint(fkbone, 'LIMIT_ROTATION')
        if cns:
            self.setIkLimits(cns, fkbone, ikbone)
            ikcns = limitRotation(iktwist, rig)
            ikcns.use_limit_y = True
            ikcns.min_y = cns.min_y
            ikcns.max_y = cns.max_y


    def addFingerIk(self, rig, suffix):
        prop = "MhaFingerIk_%s" % suffix
        n0 = 1
        for m in range(5):
            for n in range(n0,3):
                bname = self.linkName(m, n, suffix)
                pb = rig.pose.bones[bname]
                cns = getConstraint(pb, 'LIMIT_ROTATION')
                if cns:
                    self.setIkLimits(cns, pb, pb)
                    addDriver(cns, "mute", rig, prop, "x")
            bname = "ik_%s" % self.longName(m, suffix)
            target = rig.pose.bones[bname]
            cns = ikConstraint(pb, target, None, 0, 3-n0, rig)
            cns.use_rotation = True
            addDriver(cns, "mute", rig, prop, "not(x)")
            addDriver(target.bone, "hide", rig, prop, "not(x)")
            n0 = 0

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
                                    fcu.driver.expression = "-(%s)" % fcu.driver.expression
                            elif trg.transform_type == "ROT_Z":
                                trg.transform_type = "ROT_X"
                                if flip == 1:
                                    fcu.driver.expression = "-(%s)" % fcu.driver.expression

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
        self.master = makeBone("master", rig, (0,0,0), (0,hip.head[2]/5,0), 0, L_MAIN, None)
        hip.parent = self.master
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
                bone.layers[L_DEF] = True


    def addLayers(self, rig):
        setMode('OBJECT')
        for suffix,dlayer in [("L",0), ("R",16)]:
            clavicle = rig.data.bones["clavicle.%s" % suffix]
            clavicle.layers[L_SPINE] = True
            clavicle.layers[L_LARMIK+dlayer] = True

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
    facerigs = ["upperFaceRig", "lowerFaceRig"]
    if pb.name in ["lEye", "rEye", "lEar", "rEar", "upperJaw", "lowerJaw", "upperTeeth", "lowerTeeth"]:
        return L_HEAD, False
    elif (isDrvBone(pb.name) or
        isBoneDriven(rig, pb) or
        pb.name in facerigs):
        return L_HELP, False
    elif isFinal(pb.name) or pb.bone.layers[L_FIN]:
        return L_FIN, False
    elif pb.name[0:6] == "tongue":
        return L_HEAD, False
    elif pb.parent:
        par = pb.parent
        if par.name in facerigs:
            return L_FACE, True
        elif (isDrvBone(par.name) and
              par.parent and
              par.parent.name in facerigs):
            return L_FACE, True
    return L_CUSTOM, True


def connectToParent(rig):
    setMode('EDIT')
    for bname in [
        "abdomenUpper", "chestLower", "chestUpper", "neckLower", "neckUpper",
        "lShldrTwist", "lForeArm", "lForearmBend", "lForearmTwist", "lHand",
        "rShldrTwist", "rForeArm", "rForearmBend", "rForearmTwist", "rHand",
        "lThumb2", "lThumb3",
        "lIndex1", "lIndex2", "lIndex3",
        "lMid1", "lMid2", "lMid3",
        "lRing1", "lRing2", "lRing3",
        "lPinky1", "lPinky2", "lPinky3",
        "rThumb2", "rThumb3",
        "rIndex1", "rIndex2", "rIndex3",
        "rMid1", "rMid2", "rMid3",
        "rRing1", "rRing2", "rRing3",
        "rPinky1", "rPinky2", "rPinky3",
        "lThighTwist", "lShin", "lFoot", "lToe",
        "rThighTwist", "rShin", "rFoot", "rToe",
        ]:
        if bname in rig.data.edit_bones.keys():
            eb = rig.data.edit_bones[bname]
            if isDrvBone(eb.parent.name):
                eb = eb.parent
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
    "neckhead" :        ("GZM_Knuckle", 1),
    "ik_tongue" :       ("GZM_Cone", 0.4),

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
    "rEye" :            ("GZM_Circle025", 1),
    "lEye" :            ("GZM_Circle025", 1),
    "rEar" :            ("GZM_Circle025", 1.5),
    "lEar" :            ("GZM_Circle025", 1.5),
    "gaze" :            ("GZM_Gaze", 1),
}

LRGizmos = {
    "pectoral" :        ("GZM_Pectoral", 1),
    "clavicle" :        ("GZM_Ball025End", 1),

    # Head

    "gaze" :            ("GZM_Circle025", 1),
    "uplid" :           ("GZM_UpLid", 1),
    "lolid" :           ("GZM_LoLid", 1),

    # Leg

    "thigh.fk" :        ("GZM_Circle025", 1),
    "shin.fk" :         ("GZM_Circle025", 1),
    "thigh.ik.twist":   ("GZM_Circle025", 1),
    "shin.ik.twist" :   ("GZM_Circle025", 1),
    "foot.fk" :         ("GZM_Foot", 1),
    "tarsal" :          ("GZM_Foot", 1),
    "toe.fk" :          ("GZM_Toe", 1),
    "legSocket" :       ("GZM_Cube", 0.25),
    "foot.rev" :        ("GZM_FootRev", 1),
    "foot.ik" :         ("GZM_FootIK", 1),
    "toe.rev" :         ("GZM_ToeRev", 1),
    "foot.2" :          ("GZM_Foot", 1),
    "toe.2" :           ("GZM_Toe", 1),
    "knee.pt.ik" :      ("GZM_Cone", 0.25),
    "kneePoleA" :       ("GZM_Knuckle", 1),
    "toe.marker" :      ("GZM_Ball025", 1),
    "ball.marker" :     ("GZM_Ball025", 1),
    "heel.marker" :     ("GZM_Ball025", 1),

    # Arm
    "clavicle" :        ("GZM_Shoulder", 1),
    "upper_arm.fk" :    ("GZM_Circle025", 1),
    "forearm.fk" :      ("GZM_Circle025", 1),
    "upper_arm.ik.twist" :  ("GZM_Circle025", 1),
    "forearm.ik.twist" :    ("GZM_Circle025", 1),
    "hand.fk" :         ("GZM_Hand", 1),
    "handTwk" :         ("GZM_Circle", 0.4),
    "armSocket" :       ("GZM_Cube", 0.25),
    "hand.ik" :         ("GZM_HandIK", 1),
    "elbow.pt.ik" :     ("GZM_Cone", 0.25),
    "elbowPoleA" :      ("GZM_Knuckle", 1),

    # Finger
    "thumb" :           ("GZM_Knuckle", 1),
    "index" :           ("GZM_Knuckle", 1),
    "middle" :          ("GZM_Knuckle", 1),
    "ring" :            ("GZM_Knuckle", 1),
    "pinky":            ("GZM_Knuckle", 1),

    "ik_thumb" :        ("GZM_Cone", 0.4),
    "ik_index" :        ("GZM_Cone", 0.4),
    "ik_middle" :       ("GZM_Cone", 0.4),
    "ik_ring" :         ("GZM_Cone", 0.4),
    "ik_pinky":         ("GZM_Cone", 0.4),
    }

#-------------------------------------------------------------
#   Set all limbs to FK.
#   Used by load pose etc.
#-------------------------------------------------------------

def setToFk(rig, layers):
    for pname in [
        "MhaArmIk_L", "MhaArmIk_R", "MhaLegIk_L", "MhaLegIk_R",
        "MhaTongueIk", "MhaFingerIk_L", "MhaFingerIk_R"]:
        if pname in rig.keys():
            rig[pname] = 0.0
        if pname in rig.data.keys():
            rig.data[pname] = 0.0
    for layer in [L_LARMFK, L_RARMFK, L_LLEGFK, L_RLEGFK]:
        layers[layer] = True
    for layer in [L_LARMIK, L_RARMIK, L_LLEGIK, L_RLEGIK]:
        layers[layer] = False
    return layers

#-------------------------------------------------------------
#   Fix IK. Used by rigify and simple rig
#-------------------------------------------------------------

def fixIk(rig, bnames):
    for bname in bnames:
        if bname in rig.pose.bones.keys():
            pb = rig.pose.bones[bname]
            pb.use_ik_limit_x = True
            pb.ik_min_x = 0
            pb.ik_max_x = 160*D

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
