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
from .utils import *
from .error import *
from .bone_data import BD

#-------------------------------------------------------------
#   Simple IK
#-------------------------------------------------------------

class SimpleIK:
    def __init__(self, btn=None):
        if btn:
            self.usePoleTargets = btn.usePoleTargets
        else:
            self.usePoleTargets = False

    G38Arm = ["ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Hand"]
    G38Leg = ["ThighBend", "ThighTwist", "Shin", "Foot"]
    G38Spine = ["abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G38Neck = ["neckLower", "neckUpper", "head"]
    G38Thumb = ["Thumb1", "Thumb2", "Thumb3"]
    G38Index = ["Index1", "Index2", "Index3"]
    G38Mid = ["Mid1", "Mid2", "Mid3"]
    G38Ring = ["Ring1", "Ring2", "Ring3"]
    G38Pinky = ["Pinky1", "Pinky2", "Pinky3"]
    G38BigToe = ["BigToe", "BigToe_2"]
    G38SmallToe1 = ["SmallToe1", "SmallToe1_2"]
    G38SmallToe2 = ["SmallToe2", "SmallToe2_2"]
    G38SmallToe3 = ["SmallToe3", "SmallToe3_2"]
    G38SmallToe4 = ["SmallToe4", "SmallToe4_2"]
    G38Tongue = ["tongue01", "tongue02", "tongue03", "tongue04"]

    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["abdomen", "abdomen2", "spine", "chest"]
    G12Neck = ["neck", "head"]
    G12Thumb = G38Thumb
    G12Index = G38Index
    G12Mid = G38Mid
    G12Ring = G38Ring
    G12Pinky = G38Pinky
    G12BigToe = G12SmallToe1 = G12SmallToe2 = G12SmallToe3 = G12SmallToe4 = []
    G12Tongue = ["tongueBase", "tongue01", "tongue02", "tongue03", "tongue04", "tongue05", "tongueTip"]

    G9Arm = ["_upperarm", "_forearm", "_hand"]
    G9Leg = ["_thigh", "_shin", "_foot"]
    G9Spine = ["spine1", "spine2", "spine3", "spine4"]
    G9Neck = ["neck1", "neck2", "head"]
    G9Thumb = ["_thumb1", "_thumb2", "_thumb3"]
    G9Index = ["_index1", "_index2", "_index3"]
    G9Mid = ["_mid1", "_mid2", "_mid3"]
    G9Ring = ["_ring1", "_ring2", "_ring3"]
    G9Pinky = ["_pinky1", "_pinky2", "_pinky3"]
    G9BigToe = ["_bigtoe1", "_bigtoe2"]
    G9SmallToe1 = ["_indextoe1", "_indextoe2"]
    G9SmallToe2 = ["_midtoe1", "_midtoe2"]
    G9SmallToe3 = ["_ringtoe1", "_ringtoe2"]
    G9SmallToe4 = ["_pinkytoe1", "_pinkytoe2"]
    G9Tongue = ["tongue01", "tongue02", "tongue03", "tongue04", "tongue05"]

    def getIKProp(self, prefix, type):
        return ("Daz%sIK_%s" % (type, prefix.upper()))

    def keyPose(self, pb):
        if self.auto:
            pb.keyframe_insert("location", frame=self.frame)
            if pb.rotation_mode == 'QUATERNION':
                pb.keyframe_insert("rotation_quaternion", frame=self.frame)
            else:
                pb.keyframe_insert("rotation_euler", frame=self.frame)
            pb.keyframe_insert("scale", frame=self.frame)

    def initAuto(self, context):
        scn = context.scene
        self.auto = scn.tool_settings.use_keyframe_insert_auto
        self.frame = scn.frame_current

    def setProp(self, rna, prop, value):
        setattr(rna, prop, value)
        if self.auto:
            rna.keyframe_insert(prop, frame=self.frame)

    def getGenesisType(self, rig):
        if (self.hasAllBones(rig, self.G38Arm+self.G38Leg, "l") and
            self.hasAllBones(rig, self.G38Arm+self.G38Leg, "r") and
            self.hasAllBones(rig, self.G38Spine, "")):
            return "G38"
        if (self.hasAllBones(rig, self.G12Arm+self.G12Leg, "l") and
            self.hasAllBones(rig, self.G12Arm+self.G12Leg, "r")):
            return "G12"
        if (self.hasAllBones(rig, self.G9Arm+self.G9Leg, "l") and
            self.hasAllBones(rig, self.G9Arm+self.G9Leg, "r") and
            self.hasAllBones(rig, self.G9Spine, "")):
            return "G9"
        raise DazError("%s is not a Genesis armature" % rig.name)
        return None


    def hasAllBones(self, rig, bnames, prefix):
        from .fix import getSuffixName
        bnames = [prefix+bname for bname in bnames]
        for bname in bnames:
            if bname not in rig.data.bones.keys():
                sufname = getSuffixName(bname)
                if sufname not in rig.data.bones.keys():
                    return False
        return True


    def getLimbBoneNames(self, rig, prefix, type):
        genesis = self.getGenesisType(rig)
        if not genesis:
            return []
        from .fix import getPreSufName
        table = getattr(self, genesis+type)
        prenames = []
        for bname in table:
            prename = "%s%s" % (prefix, bname)
            if getPreSufName(prename, rig):
                prenames.append(prename)
        return prenames


    def insertIKKeys(self, rig, frame):
        from .fix import getPreSufName
        bnames = ["lHandIK", "rHandIK", "lFootIK", "rFootIK",
                  "l_handIK", "r_handIK", "l_footIK", "r_footIK"]
        for bname in bnames:
            bname = getPreSufName(bname, rig)
            if bname:
                pb = rig.pose.bones[bname]
                pb.keyframe_insert("location", frame=frame, group=bname)
                pb.keyframe_insert("rotation_euler", frame=frame, group=bname)


    def limitBone(self, pb, bend, twist, rig, prop, stiffness=(0,0,0)):
        pb.lock_ik_x = pb.lock_rotation[0]
        pb.lock_ik_y = pb.lock_rotation[1]
        pb.lock_ik_z = pb.lock_rotation[2]

        if bend:
            pb.lock_ik_y = True
        if twist:
            pb.lock_ik_x = True
            pb.lock_ik_z = True

        pb.ik_stiffness_x = stiffness[0]
        pb.ik_stiffness_y = stiffness[1]
        pb.ik_stiffness_z = stiffness[2]

        pb.driver_remove("rotation_euler")

#-------------------------------------------------------------
#   Add Simple IK
#-------------------------------------------------------------

class DAZ_OT_AddSimpleIK(DazPropsOperator):
    bl_idname = "daz.add_simple_ik"
    bl_label = "Add Simple IK"
    bl_description = (
        "Add Simple IK constraints to the active rig.\n" +
        "This will not work if the rig has body morphs affecting arms and legs,\n" +
        "and the bones have been made posable")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and ob.DazCustomShapes and not ob.DazSimpleIK)

    useArms : BoolProperty(
        name = "Arm IK",
        description = "Add IK to arms",
        default = True)

    useLegs : BoolProperty(
        name = "Leg IK",
        description = "Add IK to legs",
        default = True)

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains.\nPoses will not be loaded correctly.",
        default = False)

    useImproveIk : BoolProperty(
        name = "Improve IK",
        description = "Improve IK by prebending IK bones",
        default = True)

    useCopyRotation = True

    useRootBone : BoolProperty(
        name = "Root Bone",
        description = "Add a root bone which is the parent of all other bones",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useRootBone")
        self.layout.prop(self, "useArms")
        self.layout.prop(self, "useLegs")
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "useImproveIk")


    def run(self, context):
        def makePole(bname, rig, eb, parent):
            from .mhx import makeBone
            mat = eb.matrix.to_3x3()
            xaxis = mat.col[0]
            zaxis = mat.col[2]
            head = eb.head - 40*rig.DazScale*zaxis
            tail = head + 10*rig.DazScale*Vector((0,0,1))
            makeBone(bname, rig, head, tail, 0, 0, parent)
            strname = stretchName(bname)
            stretch = makeBone(strname, rig, eb.head, head, 0, 0, eb)
            stretch.hide_select = True

        def stretchName(bname):
            return (bname+"_STR")

        def driveConstraint(pb, type, rig, prop):
            from .driver import addDriver
            for cns in pb.constraints:
                if cns.type == type:
                    addDriver(cns, "influence", rig, (prop, "DazRotLimits"), "(1-x1)*x2")

        def copyBoneProps(src, trg):
            trg.DazRotMode = src.DazRotMode
            trg.rotation_mode = src.rotation_mode
            trg.custom_shape = src.custom_shape

        rig = context.object
        if rig.DazSimpleIK:
            raise DazError("The rig %s already has simple IK" % rig.name)
        if not rig.DazCustomShapes:
            raise DazError("Make custom shapes first")

        from .mhx import makeBone, getBoneCopy, ikConstraint, copyRotation, stretchTo
        IK = SimpleIK(self)
        genesis = IK.getGenesisType(rig)
        if not genesis:
            raise DazError("Cannot create simple IK for the rig %s" % rig.name)

        rig.DazSimpleIK = True
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = 1

        LS.customShapes = []
        csHandIk = makeCustomShape("CS_HandIk", "RectX")
        csFootIk = makeCustomShape("CS_FootIk", "RectZ")
        if IK.usePoleTargets:
            csCube = makeCustomShape("CS_Cube", "Cube", scale=0.3)

        armTable = {
            "G12" : ("Hand", "HandIK", "Shldr", "Shldr", "ForeArm", "ForeArm", "Collar", "Elbow"),
            "G38" : ("Hand", "HandIK", "ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Collar", "Elbow"),
            "G9" : ("_hand", "_handIK", "_upperarm", "_upperarm", "_forearm", "_forearm", "_shoulder", "_elbow"),
        }

        legTable = {
            "G12" : ("Foot", "FootIK", "Thigh", "Thigh", "Shin", "hip", "Knee"),
            "G38" : ("Foot", "FootIK", "ThighBend", "ThighTwist", "Shin", "hip", "Knee"),
            "G9" : ("_foot", "_footIK", "_thigh", "_thigh", "_shin", "hip", "_knee"),
        }

        armTable2 = {
            "G38" : ("ShldrIKTwist", "ForearmIKTwist"),
        }

        legTable2 = {
            "G38" : ("ThighIKTwist", "ShinIKTwist"),
        }

        def getEntry(table, key, prefix, bones):
            entry = []
            for bname in table[key]:
                if bname and bname in bones.keys():
                    entry.append(bones[bname])
                else:
                    lrname = "%s%s" % (prefix, bname)
                    entry.append(bones.get(lrname, lrname))
            return entry

        setMode('EDIT')
        ebones = rig.data.edit_bones
        if self.useRootBone:
            roots = [eb for eb in ebones if eb.parent is None]
            root = makeBone("Root", rig, (0,0,0), (0,0,10*rig.DazScale), 0, 16, None)
            for eb in roots:
                eb.parent = root
            csRoot = makeCustomShape("CS_Root", "CircleY")
        else:
            root = None

        for prefix,dlayer in [("l",0), ("r",1)]:
            if self.useArms:
                hand, hikname, shldrBend, shldrTwist, foreBend, foreTwist, collar, elbowname = getEntry(armTable, genesis, prefix, ebones)
                handIK = makeBone(hikname, rig, hand.head, hand.tail, hand.roll, 0, root)
                foreTwist.tail = hand.head
                if genesis == "G38" and self.useCopyRotation:
                    shikname, foreikname = getEntry(armTable2, genesis, prefix, ebones)
                    layer = (30 if self.usePoleTargets else 26+dlayer)
                    shldrIK = makeBone(shikname, rig, shldrBend.head, shldrBend.tail, shldrBend.roll, layer, shldrBend.parent)
                    foreIK = makeBone(foreikname, rig, foreBend.head, foreTwist.tail, foreBend.roll, 30, shldrIK)
                if IK.usePoleTargets:
                    elbow = makePole(elbowname, rig, foreBend, collar)

            if self.useLegs:
                foot, fikname, thighBend, thighTwist, shin, hip, kneename = getEntry(legTable, genesis, prefix, ebones)
                footIK = makeBone(fikname, rig, foot.head, foot.tail, foot.roll, 0, root)
                shin.tail = foot.head
                if genesis == "G38" and self.useCopyRotation:
                    thikname, shinikname = getEntry(legTable2, genesis, prefix, ebones)
                    layer = (30 if self.usePoleTargets else 28+dlayer)
                    thighIK = makeBone(thikname, rig, thighBend.head, thighTwist.tail, thighBend.roll, layer, thighBend.parent)
                    shinIK = makeBone(shinikname, rig, shin.head, shin.tail, shin.roll, 30, thighIK)
                if IK.usePoleTargets:
                    knee = makePole(kneename, rig, shin, hip)

        setMode('OBJECT')
        rpbs = rig.pose.bones
        if self.useRootBone:
            root = rpbs["Root"]
            setCustomShape(root, csRoot, 7)

        for prefix in ["l", "r"]:
            suffix = prefix.upper()
            if self.useArms:
                armProp = "DazArmIK_" + suffix
                hand, handIK, shldrBend, shldrTwist, foreBend, foreTwist, collar, elbow = getEntry(armTable, genesis, prefix, rpbs)
                driveConstraint(hand, 'LIMIT_ROTATION', rig, armProp)
                copyBoneProps(hand, handIK)
                copyRotation(hand, handIK, rig, prop=armProp, space='WORLD')
                addToLayer(handIK, "IK Arm", rig, "IK")
            if self.useLegs:
                legProp = "DazLegIK_" + suffix
                foot, footIK, thighBend, thighTwist, shin, hip, knee = getEntry(legTable, genesis, prefix, rpbs)
                driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp)
                copyBoneProps(foot, footIK)
                copyRotation(foot, footIK, rig, prop=legProp, space='WORLD')
                addToLayer(footIK, "IK Leg", rig, "IK")

            if genesis == "G38":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 1.5)
                    IK.limitBone(shldrBend, True, False, rig, armProp)
                    IK.limitBone(shldrTwist, False, True, rig, armProp)
                    IK.limitBone(foreBend, True, False, rig, armProp)
                    IK.limitBone(foreTwist, False, True, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 3.0)
                    IK.limitBone(thighBend, True, False, rig, legProp)
                    IK.limitBone(thighTwist, False, True, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)

            elif genesis == "G9":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 3.0)
                    IK.limitBone(shldrBend, False, False, rig, armProp)
                    IK.limitBone(foreBend, False, False, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 1.5)
                    IK.limitBone(thighBend, False, False, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)

            elif genesis == "G12":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 3.0)
                    IK.limitBone(shldrBend, False, False, rig, armProp)
                    IK.limitBone(foreBend, False, False, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 1.5)
                    IK.limitBone(thighBend, False, False, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)

            if IK.usePoleTargets:
                if self.useArms:
                    elbow.lock_rotation = (True,True,True)
                    elbow.custom_shape = csCube
                    addToLayer(elbow, "IK Arm", rig, "IK")
                    stretch = rpbs[stretchName(elbow.name)]
                    stretchTo(stretch, elbow, rig)
                    addToLayer(stretch, "IK Arm", rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = (True,True,True)
                if self.useLegs:
                    knee.lock_rotation = (True,True,True)
                    knee.custom_shape = csCube
                    addToLayer(knee, "IK Leg", rig, "IK")
                    stretch = rpbs[stretchName(knee.name)]
                    stretchTo(stretch, knee, rig)
                    addToLayer(stretch, "IK Leg", rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = (True,True,True)
            else:
                elbow = knee = None

            foreIK = shinIK = None
            if genesis == "G38" and self.useCopyRotation:
                if self.useArms:
                    shldrIK, foreIK = getEntry(armTable2, genesis, prefix, rpbs)
                    copyBoneProps(shldrBend, shldrIK)
                    copyBoneProps(foreBend, foreIK)
                    foreIK.lock_ik_z = True
                    shldrIK.lock_rotation = (True, False, True)
                    shldrIK.lock_location = foreIK.lock_location = (True, True, True)
                    ikConstraint(foreIK, handIK, elbow, -90, 2, rig)
                    cns = copyRotation(shldrBend, shldrIK, rig, prop=armProp)
                    cns.euler_order = BD.getDefaultMode(shldrBend)
                    cns.use_y = False
                    cns = copyRotation(shldrTwist, shldrIK, rig, prop=armProp)
                    cns.euler_order = BD.getDefaultMode(shldrTwist)
                    cns.use_x = cns.use_z = False
                    cns = copyRotation(foreBend, foreIK, rig, prop=armProp)
                    cns.euler_order = foreBend.rotation_mode
                    cns.use_y = False
                    cns = copyRotation(foreTwist, handIK, rig, prop=armProp, space='LOCAL_WITH_PARENT')
                    cns.use_x = cns.use_z = False
                if self.useLegs:
                    thighIK, shinIK = getEntry(legTable2, genesis, prefix, rpbs)
                    copyBoneProps(thighBend, thighIK)
                    copyBoneProps(shin, shinIK)
                    shinIK.lock_ik_y = shinIK.lock_ik_z = True
                    thighIK.lock_rotation = (True, False, True)
                    thighIK.lock_location = shinIK.lock_location = (True, True, True)
                    ikConstraint(shinIK, footIK, knee, -90, 2, rig)
                    cns = copyRotation(thighBend, thighIK, rig, prop=legProp)
                    cns.euler_order = BD.getDefaultMode(thighBend)
                    cns.use_y = False
                    cns = copyRotation(thighTwist, thighIK, rig, prop=legProp)
                    cns.euler_order = BD.getDefaultMode(thighTwist)
                    cns.use_x = cns.use_z = False
                    cns = copyRotation(shin, shinIK, rig, prop=legProp)
                    cns.euler_order = shin.rotation_mode
            elif genesis == "G38":
                if self.useArms:
                    ikConstraint(foreTwist, handIK, elbow, -90, 4, rig, prop=armProp)
                if self.useLegs:
                    ikConstraint(shin, footIK, knee, -90, 3, rig, prop=legProp)
            else:
                if self.useArms:
                    ikConstraint(foreTwist, handIK, elbow, -90, 2, rig, prop=armProp)
                if self.useLegs:
                    ikConstraint(shin, footIK, knee, -90, 2, rig, prop=legProp)

        if self.useImproveIk:
            improveIk(rig)
        from .node import createHiddenCollection
        hidden = createHiddenCollection(context, rig)
        for ob in LS.customShapes:
            hidden.objects.link(ob)
            #ob.hide_viewport = ob.hide_render = True
        T = True
        F = False
        rig.data.layers = 16*[F] + [T,T,F,F, F,F,F,F, F,F,T,T, T,T,F,F]
        rig.data.display_type = 'WIRE'

#----------------------------------------------------------
#   Custom shapes
#----------------------------------------------------------

def makeCustomShape(csname, gname, offset=(0,0,0), scale=1):
    from .fileutils import AF
    struct = AF.loadEntry("simple", "gizmos", True)
    me = bpy.data.meshes.new(csname)
    verts = struct["verts"]
    u,v,w = offset
    if isinstance(scale, tuple):
        a,b,c = scale
    else:
        a,b,c = scale,scale,scale
    verts = [(a*(x+u), b*(y+v), c*(z+w)) for x,y,z in struct["verts"]]
    me.from_pydata(verts, struct["edges"], [])
    ob = bpy.data.objects.new(csname, me)
    LS.customShapes.append(ob)
    return ob


def getPoseBone(rig, bnames):
    for bname in bnames:
        if bname in rig.pose.bones.keys():
            return rig.pose.bones[bname]
    return None


def getGenesisName(genesis, bnames):
    if genesis in ["G12", "G38"]:
        return bnames[0]
    elif genesis == "G9":
        return bnames[1]


class DAZ_OT_AddCustomShapes(DazOperator):
    bl_idname = "daz.add_custom_shapes"
    bl_label = "Add Custom Shapes"
    bl_description = "Add custom shapes to the bones of the active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.DazCustomShapes)

    def run(self, context):
        rig = context.object
        coll = getCollection(context, rig)
        LS.customShapes = []
        IK = SimpleIK()
        makeBoneGroups(rig)

        csCollar = makeCustomShape("CS_Collar", "CircleX", (0,1,0), (0,0.5,0.1))
        csHandFk = makeCustomShape("CS_HandFk", "CircleX", (0,1,0), (0,0.6,0.5))
        csCarpal = makeCustomShape("CS_Carpal", "CircleZ", (0,1,0), (0.1,0.5,0))
        csTongue = makeCustomShape("CS_Tongue", "CircleZ", (0,1,0), (1.5,0.5,0))
        circleY2 = makeCustomShape("CS_CircleY2", "CircleY", scale=1/3)
        csLimb = makeCustomShape("CS_Limb", "CircleY", (0,2,0), scale=1/4)
        csBend = makeCustomShape("CS_Bend", "CircleY", (0,1,0), scale=1/2)
        csFace = makeCustomShape("CS_Face", "CircleY", scale=1/5)
        csCube = makeCustomShape("CS_Cube", "Cube", scale=1/2)

        spineWidth = 1
        lCollar = getPoseBone(rig, ("lCollar", "l_shoulder"))
        rCollar = getPoseBone(rig, ("rCollar", "r_shoulder"))
        if lCollar and rCollar:
            spineWidth = 0.5*(lCollar.bone.tail_local[0] - rCollar.bone.tail_local[0])

        csFoot = None
        csToe = None
        lFoot = getPoseBone(rig, ("lFoot", "l_foot"))
        lToe = getPoseBone(rig, ("lToe", "l_toes"))
        if lFoot and lToe:
            footFactor = (lToe.bone.head_local[1] - lFoot.bone.head_local[1])/(lFoot.bone.tail_local[1] - lFoot.bone.head_local[1])
            csFoot = makeCustomShape("CS_Foot", "CircleZ", (0,1,0), (0.8,0.5*footFactor,0))
            csToe = makeCustomShape("CS_Toe", "CircleZ", (0,1,0), (1,0.5,0))

        for bnames in [("upperFaceRig", "upperfacerig"),
                       ("lowerFaceRig", "lowerfacerig"),
                       ("lMetatarsals", "l_metatarsal"),
                       ("rMetatarsals", "r_metatarsal"),
                       ("upperTeeth", "upperteeth"),
                       ("lowerTeeth", "lowerteeth")]:
            pb = getPoseBone(rig, bnames)
            if pb:
                pb.bone.layers = [False] + [True] + 30*[False]

        for pb in rig.pose.bones:
            lname = pb.name.lower()
            if not pb.bone.layers[0]:
                pass
            elif pb.parent and pb.parent.name in ["lowerFaceRig", "upperFaceRig", "lowerfacerig", "upperfacerig"]:
                if pb.name.startswith(("lEyelid", "rEyelid", "l_eyelid", "r_eyelid")):
                    setCustomShape(pb, csFace, 0.3, 1.0)
                else:
                    setCustomShape(pb, csFace)
                addToLayer(pb, "Face", rig, "Spine")
            elif pb.name in ["lEye", "rEye", "lEar", "rEar", "l_eye", "r_eye", "l_ear", "r_ear"]:
                setCustomShape(pb, circleY2, None, 1.0)
                addToLayer(pb, "Face", rig, "Spine")
            elif lname == "lowerjaw":
                setCustomShape(pb, csCollar)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name.startswith("tongue"):
                setCustomShape(pb, csTongue)
                addToLayer(pb, "Face", rig, "Spine")
            elif lname.endswith("hand"):
                setCustomShape(pb, csHandFk)
                addToLayer(pb, "FK Arm", rig, "FK")
            elif lname.endswith("handik"):
                setCustomShape(pb, csHandIk, 1.8)
                addToLayer(pb, "IK Arm", rig, "IK")
            elif "carpal" in lname:
                setCustomShape(pb, csCarpal)
                addToLayer(pb, "Hand", rig, "Limb")
            elif pb.name in ["lCollar", "rCollar", "l_shoulder", "r_shoulder"]:
                setCustomShape(pb, csCollar)
                addToLayer(pb, "Spine", rig, "Spine")
            elif lname.endswith("foot"):
                setCustomShape(pb, csFoot)
                addToLayer(pb, "FK Leg", rig, "FK")
            elif lname.endswith("footik"):
                setCustomShape(pb, csFoot, 1.8)
                addToLayer(pb, "IK Leg", rig, "IK")
            elif pb.name in ["lToe", "rToe", "l_toes", "r_toes"]:
                setCustomShape(pb, csToe)
                addToLayer(pb, "FK Leg", rig, "Limb")
                addToLayer(pb, "IK Leg")
                addToLayer(pb, "Foot")
            elif pb.name[1:] in IK.G12Arm + IK.G38Arm + IK.G9Arm:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "FK Arm", rig, "FK")
            elif pb.name[1:] in IK.G12Leg + IK.G38Leg + IK.G9Leg:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "FK Leg", rig, "FK")
            elif pb.name[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "Hand", rig, "Limb")
            elif pb.name == "hip":
                self.makeSpine(pb, 2*spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name == "pelvis":
                self.makeSpine(pb, 1.5*spineWidth, 0.5)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name in IK.G38Spine + IK.G12Spine + IK.G9Spine:
                self.makeSpine(pb, spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name == "head":
                self.makeSpine(pb, 0.7*spineWidth, 1)
                addToLayer(pb, "Spine", rig, "Spine")
                addToLayer(pb, "Face")
            elif pb.name in IK.G38Neck + IK.G12Neck + IK.G9Neck:
                self.makeSpine(pb, 0.5*spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif "toe" in lname:
                setCustomShape(pb, circleY2)
                addToLayer(pb, "Foot", rig, "Limb")
            elif (pb.name[1:4] in ["Thu", "Ind", "Mid", "Rin", "Pin"] or
                  pb.name[1:5] in ["_thu", "_ind", "_mid", "_rin", "_pin"]):
                setCustomShape(pb, circleY2)
                addToLayer(pb, "Hand", rig, "Limb")
            elif "elbow" in lname:
                if not pb.name.endswith("STR"):
                    setCustomShape(pb, csCube)
                addToLayer(pb, "IK Arm", rig, "IK")
            elif "knee" in lname:
                if not pb.name.endswith("STR"):
                    setCustomShape(pb, csCube)
                addToLayer(pb, "IK Leg", rig, "IK")
            elif "pectoral" in lname:
                setCustomShape(pb, circleY2, 0.3, 1.0)
            elif pb.name.endswith(("twist1", "twist2")):
                pass
            elif lname.endswith("anchor"):
                pass
            else:
                #setCustomShape(pb, circleY2)
                print("Unknown bone:", pb.name)

        from .node import createHiddenCollection
        hidden = createHiddenCollection(context, rig)
        for ob in LS.customShapes:
            hidden.objects.link(ob)
            #ob.hide_viewport = ob.hide_render = True
        rig.DazCustomShapes = True
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


    def makeSpine(self, pb, width, tail=0.5):
        s = width/pb.bone.length
        circle = makeCustomShape("CS_" + pb.name, "CircleY", (0,tail/s,0))
        setCustomShape(pb, circle, s)


class DAZ_OT_RemoveCustomShapes(DazOperator, IsArmature):
    bl_idname = "daz.remove_custom_shapes"
    bl_label = "Remove Custom Shapes"
    bl_description = "Remove custom shapes from the bones of the active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            pb.custom_shape = None


def setSimpleToFk(rig, layers, useInsertKeys, frame):
    for lname in ["Left FK Arm", "Right FK Arm", "Left FK Leg", "Right FK Leg"]:
        layers[BoneLayers[lname]] = True
    for lname in ["Left IK Arm", "Right IK Arm", "Left IK Leg", "Right IK Leg"]:
        layers[BoneLayers[lname]] = False
    for attr in ["DazArmIK_L", "DazArmIK_R", "DazLegIK_L", "DazLegIK_R"]:
        setattr(rig, attr, 0)
        if useInsertKeys:
            rig.keyframe_insert(attr, frame=frame)
    return layers

#----------------------------------------------------------
#   FK Snap
#----------------------------------------------------------

class SimpleFKSnapper(SimpleIK):
    def snapSimpleFK(self, rig, prefix, type):
        bnames = self.getLimbBoneNames(rig, prefix, type)
        if bnames:
            prop = self.getIKProp(prefix, type)
            self.setProp(rig, prop, True)
            updatePose()
            self.snapBones(rig, bnames, prop)
            toggleLayer(rig, "FK", prefix, type, True)
            toggleLayer(rig, "IK", prefix, type, False)
            self.setProp(rig, prop, False)


    def snapBones(self, rig, bnames, prop):
        from .fix import getPreSufName
        mats = []
        for bname in bnames:
            pb = rig.pose.bones.get(getPreSufName(bname, rig))
            if pb:
                mats.append((pb, pb.matrix.copy()))
        self.setProp(rig, prop, 0.0)
        updatePose()
        for pb,mat in mats:
            pb.matrix = mat
            updatePose()
            self.keyPose(pb)


class DAZ_OT_SnapSimpleFK(DazOperator, SimpleFKSnapper):
    bl_idname = "daz.snap_simple_fk"
    bl_label = "Snap FK"
    bl_description = "Snap FK bones to IK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        self.snapSimpleFK(rig, self.prefix, self.type)


class DAZ_OT_SnapAllSimpleFK(DazOperator, SimpleFKSnapper):
    bl_idname = "daz.snap_all_simple_fk"
    bl_label = "Snap FK All"
    bl_description = "Snap all FK bones to IK bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        for prefix,type in [("l", "Arm"), ("r", "Arm"), ("l", "Leg"), ("r", "Leg")]:
            self.snapSimpleFK(rig, prefix, type)

#----------------------------------------------------------
#   IK Snap
#----------------------------------------------------------

class SimpleIKSnapper(SimpleIK):

    def snapSimpleIK(self, rig, prefix, type, pole):
        bnames = self.getLimbBoneNames(rig, prefix, type)
        if bnames:
            prop = self.getIKProp(prefix, type)
            self.setProp(rig, prop, 0.0)
            updatePose()
            self.snapBones(rig, bnames, prop, pole)
            toggleLayer(rig, "FK", prefix, type, False)
            toggleLayer(rig, "IK", prefix, type, True)
            self.setProp(rig, prop, 1.0)


    def snapBones(self, rig, bnames, prop, pole):
        from .fix import getPreSufName
        hand = bnames[-1]
        handfk = rig.pose.bones.get(getPreSufName(hand, rig))
        if handfk is None:
            return
        handmat = handfk.matrix.copy()
        pole = getPreSufName(pole, rig)
        if pole:
            poleik = rig.pose.bones.get(pole)
            uparm = bnames[0]
            loarm = bnames[1] if len(bnames) == 3 else bnames[2]
            uparmfk = rig.pose.bones.get(getPreSufName(uparm, rig))
            loarmfk = rig.pose.bones.get(getPreSufName(loarm, rig))
            polemat = self.getPoleMatrix(uparmfk, loarmfk)
        self.setProp(rig, prop, 1.0)
        handik = rig.pose.bones.get(getPreSufName("%sIK" % hand, rig))
        if handik:
            handik.matrix = handmat
            updatePose()
            self.keyPose(handik)
        if pole:
            poleik.matrix = polemat
            updatePose()
            self.keyPose(poleik)
        for bname in bnames:
            pb = rig.pose.bones.get(getPreSufName(bname, rig))
            if pb:
                pb.matrix_basis = Matrix()
                updatePose()
                self.keyPose(pb)


    def getPoleMatrix(self, above, below):
        ay = Vector(above.matrix.col[1][:3])
        by = Vector(below.matrix.col[1][:3])
        az = Vector(above.matrix.col[2][:3])
        bz = Vector(below.matrix.col[2][:3])
        p0 = Vector(below.matrix.col[3][:3])
        n = ay.cross(by)
        if abs(n.length) > 1e-4:
            d = ay - by
            n.normalize()
            d -= d.dot(n)*n
            d.normalize()
            if d.dot(az) > 0:
                d = -d
            p = p0 + 2*above.bone.length*d
        else:
            p = p0
        return Matrix.Translation(p)


class DAZ_OT_SnapSimpleIK(DazOperator, SimpleIKSnapper):
    bl_idname = "daz.snap_simple_ik"
    bl_label = "Snap IK"
    bl_description = "Snap IK bones to FK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()
    pole : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        self.snapSimpleIK(rig, self.prefix, self.type, self.pole)


class DAZ_OT_SnapAllSimpleIK(DazOperator, SimpleIKSnapper):
    bl_idname = "daz.snap_all_simple_ik"
    bl_label = "Snap IK All"
    bl_description = "Snap all IK bones to FK bones"
    bl_options = {'UNDO'}

    pole : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        for prefix,type,pole in [
            ("l", "Arm", "lElbow"),
            ("r", "Arm", "rElbow"),
            ("l", "Leg", "lKnee"),
            ("r", "Leg", "rKnee")]:
            self.snapSimpleIK(rig, prefix, type, pole)

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def toggleLayer(rig, fk, prefix, type, on):
    side = {"l" : "Left", "r" : "Right"}
    lname = ("%s %s %s" % (side[prefix], fk, type))
    layer = BoneLayers[lname]
    rig.data.layers[layer] = on

#----------------------------------------------------------
#   Set custom shape
#----------------------------------------------------------

def setCustomShape(pb, shape, scale=None, offset=None):
    if offset and not hasattr(pb, "custom_shape_translation"):
        return
    pb.custom_shape = shape
    if scale is None:
        pass
    elif hasattr(pb, "custom_shape_scale"):
        pb.custom_shape_scale = scale
    else:
        pb.custom_shape_scale_xyz = (scale, scale, scale)
    if offset is not None:
        pb.custom_shape_translation.y = offset*pb.bone.length

#----------------------------------------------------------
#   Connect bone chains
#----------------------------------------------------------

class DAZ_OT_ConnectBoneChains(DazPropsOperator, SimpleIK, IsArmature):
    bl_idname = "daz.connect_bone_chains"
    bl_label = "Connect Bone Chains"
    bl_description = "Connect all bones in chains to their parents"
    bl_options = {'UNDO'}

    useArms : BoolProperty(
        name = "Arms",
        description = "Connect arm bones",
        default = True)

    useLegs : BoolProperty(
        name = "Legs",
        description = "Connect leg bones",
        default = True)

    useSpine : BoolProperty(
        name = "Spine",
        description = "Connect spine bones",
        default = False)

    useNeck : BoolProperty(
        name = "Neck",
        description = "Connect neck bones",
        default = False)

    useFingers : BoolProperty(
        name = "Fingers",
        description = "Connect finger bones",
        default = True)

    useToes : BoolProperty(
        name = "Toes",
        description = "Connect toe bones",
        default = True)

    useTongue : BoolProperty(
        name = "Tongue",
        description = "Connect tongue bones",
        default = True)

    useSelected : BoolProperty(
        name = "Selected",
        description = "Connect selected bones",
        default = False)

    unlock : BoolProperty(
        name = "Unlock Last Bone",
        description = "Remove location locks of the last bone in each chain for use as Auto IK target",
        default = True)

    location : EnumProperty(
        items = [('HEAD', "Child Head", "Connect at the head of the child bone"),
                 ('TAIL', "Parent Tail", "Connect at the tail of the parent bone"),
                 ('CENTER', "Center", "Connect at the midpoint between the parent tail and child head")],
        name = "Location",
        description = "Where to connect parent and child bones",
        default = 'HEAD')

    def draw(self, context):
        self.layout.prop(self, "useSelected")
        if not self.useSelected:
            self.layout.prop(self, "useArms")
            self.layout.prop(self, "useLegs")
            self.layout.prop(self, "useSpine")
            self.layout.prop(self, "useNeck")
            self.layout.prop(self, "useFingers")
            self.layout.prop(self, "useToes")
            self.layout.prop(self, "useTongue")
        self.layout.prop(self, "location")
        self.layout.prop(self, "unlock")


    def run(self, context):
        rig = context.object
        self.getBoneNames(rig)
        wmats = []
        for ob in rig.children:
            if ob.parent_type == 'BONE':
                wmats.append((ob, ob.matrix_world.copy()))
        setMode('EDIT')
        for chain in self.chains:
            parb = rig.data.edit_bones[chain[0]]
            for child in chain[1:]:
                eb = rig.data.edit_bones[child]
                if isDrvBone(eb.parent.name):
                    self.relocate(parb, eb)
                    self.relocate(parb, eb.parent)
                    eb.parent.use_connect = True
                else:
                    self.relocate(parb, eb)
                    eb.use_connect = True
                parb = eb
        if self.unlock:
            for chain in self.chains:
                pb = rig.pose.bones[chain[-1]]
                pb.lock_location = (False,False,False)
        setMode('OBJECT')
        for ob,wmat in wmats:
            setWorldMatrix(ob, wmat)


    def relocate(self, parb, eb):
        if self.location == 'TAIL':
            eb.head = parb.tail
        elif self.location == 'HEAD':
            parb.tail = eb.head
        elif self.location == 'CENTER':
            center = (eb.head + parb.tail)/2
            parb.tail = eb.head = center


    def getBoneNames(self, rig):
        self.chains = []
        if self.useSelected:
            roots = []
            for bone in rig.data.bones:
                if bone.parent is None:
                    roots.append(bone)
            for root in roots:
                self.getChildNames(rig, root)
            return self.chains
        if self.useArms:
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Arm")
                self.chains.append(chain)
        if self.useLegs:
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Leg")
                self.chains.append(chain)
        if self.useFingers:
            for prefix in ["l", "r"]:
                for finger in ["Thumb", "Index", "Mid", "Ring", "Pinky"]:
                    chain = self.getLimbBoneNames(rig, prefix, finger)
                    self.chains.append(chain)
        if self.useToes:
            for prefix in ["l", "r"]:
                for toe in ["BigToe", "SmallToe1", "SmallToe2", "SmallToe3", "SmallToe4"]:
                    chain = self.getLimbBoneNames(rig, prefix, toe)
                    if chain:
                        self.chains.append(chain)
        if self.useTongue:
            chain = self.getLimbBoneNames(rig, "", "Tongue")
            self.chains.append(chain)
        if self.useSpine:
            chain = self.getLimbBoneNames(rig, "", "Spine")
            self.chains.append(chain)
        if self.useNeck:
            chain = self.getLimbBoneNames(rig, "", "Neck")
            self.chains.append(chain)
        return self.chains


    def getChildNames(self, rig, bone):
        if bone.select:
            self.chain = []
            self.getChainNames(rig, bone)
            self.chains.append(self.chain)
        else:
            for child in bone.children:
                self.getChildNames(rig, child)


    def getChainNames(self, rig, bone):
        if bone.select:
            self.chain.append(bone.name)
            for child in bone.children:
                self.getChainNames(rig, child)

#----------------------------------------------------------
#   Named Layers
#----------------------------------------------------------

BoneLayers = {
    "Spine" : 16,
    "Face" : 17,
    "Left FK Arm" : 18,
    "Right FK Arm" : 19,
    "Left FK Leg" : 20,
    "Right FK Leg" : 21,
    "Left Hand" : 22,
    "Right Hand" : 23,
    "Left Foot" : 24,
    "Right Foot" : 25,
    "Left IK Arm" : 26,
    "Right IK Arm" : 27,
    "Left IK Leg" : 28,
    "Right IK Leg" : 29,
}


def makeBoneGroups(rig):
    BoneGroups = [
        ("Spine",   (1,1,0)),
        ("FK",      (0,1,0)),
        ("IK",      (1,0,0)),
        ("Limb",    (0,0,1)),
    ]
    if len(rig.pose.bone_groups) != len(BoneGroups):
        for bg in list(rig.pose.bone_groups):
            rig.pose.bone_groups.remove(bg)
        for bgname,color in BoneGroups:
            bg = rig.pose.bone_groups.new(name=bgname)
            bg.color_set = 'CUSTOM'
            bg.colors.normal = color
            bg.colors.select = (0.6, 0.9, 1.0)
            bg.colors.active = (1.0, 1.0, 0.8)


def addToLayer(pb, lname, rig=None, bgname=None):
    if lname in BoneLayers.keys():
        n = BoneLayers[lname]
    elif pb.name[0] == "l" and "Left "+lname in BoneLayers.keys():
        n = BoneLayers["Left "+lname]
    elif pb.name[0] == "r" and "Right "+lname in BoneLayers.keys():
        n = BoneLayers["Right "+lname]
    else:
        print("MISSING LAYER", lname, pb.name)
        return
    pb.bone.layers[n] = True
    if rig and bgname:
        pb.bone_group = rig.pose.bone_groups[bgname]


class DAZ_OT_SelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.select_named_layers"
    bl_label = "All"
    bl_description = "Select all named layers and unselect all unnamed layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


class DAZ_OT_UnSelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.unselect_named_layers"
    bl_label = "Only Active"
    bl_description = "Unselect all named and unnamed layers except active"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        m = 16
        bone = rig.data.bones.active
        if bone:
            for n in range(16,30):
                if bone.layers[n]:
                    m = n
                    break
        rig.data.layers = m*[False] + [True] + (31-m)*[False]

#----------------------------------------------------------
#   Copy Absolute Pose
#----------------------------------------------------------

class DAZ_OT_CopyAbsolutePose(DazOperator, IsArmature):
    bl_idname = "daz.copy_absolute_pose"
    bl_label = "Copy Absolute Pose"
    bl_description = (
        "Copy pose in world space from active to selected armatures.\n" +
        "Only works properly if both armatures have the same bone names")
    bl_options = {'UNDO'}

    def run(self, context):
        from .animation import insertKeys
        src = context.object
        scn = context.scene
        auto = scn.tool_settings.use_keyframe_insert_auto
        roots = [pb for pb in src.pose.bones if pb.parent is None]
        for trg in getSelectedArmatures(context):
            if trg != src:
                for root in roots:
                    self.copyPose(root, trg)
                if auto:
                    for pb in trg.pose.bones:
                        insertKeys(pb, True, scn.frame_current)


    def copyPose(self, pb, trg):
        from .animation import imposeLocks
        trgpb = trg.pose.bones.get(pb.name)
        if trgpb:
            loc = trgpb.location.copy()
            trgpb.matrix = pb.matrix.copy()
            updatePose()
            if trgpb.parent:
                trgpb.location = loc
            imposeLocks(trgpb)
            for child in pb.children:
                self.copyPose(child, trg)

#-------------------------------------------------------------
#   Improve IK
#-------------------------------------------------------------

class DAZ_OT_ImproveIK(DazOperator, IsArmature):
    bl_idname = "daz.improve_ik"
    bl_label = "Improve IK"
    bl_description = "Improve IK behaviour"
    bl_options = {'UNDO'}

    def run(self, context):
        improveIk(context.object)


def improveIk(rig, exclude=[]):
    ikconstraints = []
    for pb in rig.pose.bones:
        if pb.name in exclude:
            continue
        for cns in pb.constraints:
            if cns.type == 'IK':
                ikconstraints.append((pb, cns, cns.mute))
                cns.mute = True
                pb.lock_rotation[0] = False
                pb.rotation_euler[0] = 15*D
    for pb,cns,mute in ikconstraints:
        pb.lock_rotation = (False, True, True)
        pb.lock_location = (True, True, True)
        cns.mute = mute
        pb.use_ik_limit_x = pb.use_ik_limit_y = pb.use_ik_limit_z = False
        pb.lock_ik_y = pb.lock_ik_z = True

#----------------------------------------------------------
#   Batch set custom shape
#----------------------------------------------------------

class DAZ_OT_BatchSetCustomShape(DazPropsOperator, IsArmature):
    bl_idname = "daz.batch_set_custom_shape"
    bl_label = "Batch Set Custom Shape"
    bl_description = "Set the selected mesh as the custom shape of all selected bones"
    bl_options = {'UNDO'}

    useClear : BoolProperty(
        name = "Clear custom shapes",
        default = False)

    scale : FloatVectorProperty(
        name = "Scale",
        size=3,
        default=(1,1,1))

    translation : FloatVectorProperty(
        name = "Translation",
        size=3,
        default=(0,0,0))

    rotation : FloatVectorProperty(
        name = "Rotation",
        size=3,
        default=(0,0,0))

    def draw(self, context):
        self.layout.prop(self, "useClear")
        if not self.useClear:
            self.layout.prop(self, "scale")
            self.layout.prop(self, "translation")
            self.layout.prop(self, "rotation")

    def run(self, context):
        rig = context.object
        if self.useClear:
            for pb in rig.pose.bones:
                if pb.bone.select:
                    pb.custom_shape = None
        else:
            ob = None
            for ob1 in getSelectedObjects(context):
                if ob1 != rig:
                    ob = ob1
                    break
            if ob is None:
                raise DazError("No custom shape object selected")
            x,y,z = self.scale
            scale = (x+y+z)/3
            for pb in rig.pose.bones:
                if pb.bone.select:
                    pb.custom_shape = ob
                    if hasattr(pb, "custom_shape_scale_xyz"):
                        pb.custom_shape_scale_xyz = self.scale
                    elif hasattr(pb, "custom_shape_scale"):
                        pb.custom_shape_scale = scale
                    if hasattr(pb, "custom_shape_translation"):
                        pb.custom_shape_translation = self.translation
                    if hasattr(pb, "custom_shape_rotation_euler"):
                        pb.custom_shape_rotation_euler = Vector(self.rotation)*D

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddCustomShapes,
    DAZ_OT_RemoveCustomShapes,
    DAZ_OT_AddSimpleIK,
    DAZ_OT_SnapSimpleFK,
    DAZ_OT_SnapSimpleIK,
    DAZ_OT_SnapAllSimpleFK,
    DAZ_OT_SnapAllSimpleIK,
    DAZ_OT_ConnectBoneChains,
    DAZ_OT_SelectNamedLayers,
    DAZ_OT_UnSelectNamedLayers,
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ImproveIK,
    DAZ_OT_BatchSetCustomShape,
]

def register():
    bpy.types.Object.DazCustomShapes = BoolProperty(default=False)
    bpy.types.Armature.DazFinalized = BoolProperty(default=False)
    bpy.types.Object.DazSimpleIK = BoolProperty(default=False)
    bpy.types.Object.DazArmIK_L = FloatProperty(name="Left Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazArmIK_R = FloatProperty(name="Right Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_L = FloatProperty(name="Left Leg IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_R = FloatProperty(name="Right Leg IK", default=0.0, precision=3, min=0.0, max=1.0)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
