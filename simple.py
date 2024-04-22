# Copyright (c) 2016-2024, Thomas Larsson
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
from .layers import *
from .bone_data import BD
from .animation import FrameRange


S_ARMIK = (S_LARMIK, S_RARMIK)
S_ARMFK = (S_LARMFK, S_RARMFK)
S_LEGIK = (S_LLEGIK, S_RLEGIK)
S_LEGFK = (S_LLEGFK, S_RLEGFK)
S_HAND = (S_LHAND, S_RHAND)
S_FOOT = (S_LFOOT, S_RFOOT)

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


    def linearizeFcurve(self, rna, prop):
        if rna.animation_data and rna.animation_data.action:
            for fcu in rna.animation_data.action.fcurves:
                if fcu.data_path == prop:
                    for pt in fcu.keyframe_points:
                        pt.interpolation = 'LINEAR'
                    fcu.extrapolation = 'CONSTANT'


    def changeLayers(self, rig, on, off):
        if BLENDER3:
            rig.data.layers[on] = True
            rig.data.layers[off] = False
        else:
            coll = rig.data.collections[SimpleLayers[on]]
            coll.is_visible = True
            coll = rig.data.collections[SimpleLayers[off]]
            coll.is_visible = False


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
                sufname = getSuffixName(bname, True)
                if sufname not in rig.data.bones.keys():
                    return False
        return True


    def getLimbBoneNames(self, rig, prefix, type):
        self.genesis = self.getGenesisType(rig)
        if not self.genesis:
            return []
        from .fix import getPreSufName
        table = getattr(self, self.genesis+type)
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
    bl_options = {'UNDO', 'PRESET'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.DazSimpleIK)

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

    useErcIk : BoolProperty(
        name = "ERC Morphs Affect IK",
        description = "Let ERC morphs change the IK hands, IK heels, and pole target locations",
        default = True)

    useCopyRotation = True

    useRootBone : BoolProperty(
        name = "Root Bone",
        description = "Add a root bone which is the parent of all other bones",
        default = True)

    useReverseFoot : BoolProperty(
        name = "Reverse Foot",
        description = "Add reverse foot for IK",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useRootBone")
        self.layout.prop(self, "useArms")
        self.layout.prop(self, "useLegs")
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "useReverseFoot")
        self.layout.prop(self, "useImproveIk")
        if GS.ercMethod in ('ARMATURE', 'ALL'):
            self.layout.prop(self, "useErcIk")

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

    footTable = {
        "G12" : ("Toe", "HeelIK", "ToeIK", "TarsalsIK"),
        "G38" : ("Toe", "HeelIK", "ToeIK", "TarsalsIK"),
        "G9"  : ("_toes", "_heelIK", "_toesIK", "_tarsalsIK"),
    }

    armTable2 = {
        "G12" : ("ShldrIK", "ForearmIK"),
        "G38" : ("ShldrIK", "ForearmIK"),
        "G9" : ("_upperarmIK", "_forearmIK"),
    }

    legTable2 = {
        "G12" : ("ThighIK", "ShinIK"),
        "G38" : ("ThighIK", "ShinIK"),
        "G9" : ("_thighIK", "_shinIK"),
    }

    def run(self, context):
        rig = context.object
        IK = SimpleIK(self)
        LS.__init__()
        self.genesis = IK.getGenesisType(rig)
        if not self.genesis:
            raise DazError("Cannot create simple IK for the rig %s" % rig.name)
        enableAllRigLayers(rig, False)
        makeBoneCollections(rig, SimpleLayers)
        self.makeNewBones(rig, IK)
        self.makeCustomShapes(context, rig, IK)
        self.addConstraints(rig, IK)
        if GS.ercMethod in ('ARMATURE', 'ALL') and self.useErcIk:
            copyOffsetDrivers(rig)
        if self.useImproveIk:
            improveIk(rig)
        rig.DazSimpleIK = True
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = 1.0
        enableRigNumLayers(rig, [S_SPINE, S_FACE, S_LARMIK, S_RARMIK, S_LLEGIK, S_RLEGIK])
        assignOtherBones(rig, S_HIDDEN)


    def getEntry(self, table, prefix, bones):
        entry = []
        for bname in table[self.genesis]:
            if bname and bname in bones.keys():
                entry.append(bones[bname])
            else:
                lrname = "%s%s" % (prefix, bname)
                entry.append(bones.get(lrname, lrname))
        return entry

    #----------------------------------------------------------
    #   Make new bones
    #----------------------------------------------------------

    def stretchName(self, bname):
        return "%s_STR" % bname


    def makeNewBones(self, rig, IK):
        def makePole(bname, rig, eb, parent):
            mat = eb.matrix.to_3x3()
            xaxis = mat.col[0]
            zaxis = mat.col[2]
            head = eb.head - 40*rig.DazScale*zaxis
            tail = head + 10*rig.DazScale*Vector((0,0,1))
            makeBone(bname, rig, head, tail, 0, S_SPINE, parent, eb, eb)
            strname = self.stretchName(bname)
            stretch = makeBone(strname, rig, eb.head, head, 0, S_SPINE, eb, eb, eb)
            stretch.hide_select = True

        from .mhx import makeBone, deriveBone
        setMode('EDIT')
        ebones = rig.data.edit_bones
        if self.useRootBone:
            roots = [eb for eb in ebones if eb.parent is None]
            root = makeBone("Root", rig, (0,0,0), (0,0,10*rig.DazScale), 0, S_SPINE, None)
            for eb in roots:
                eb.parent = root
        else:
            root = None

        if self.useArms:
            for prefix,layer in [("l",S_LARMIK), ("r",S_RARMIK)]:
                hand, hikname, shldrBend, shldrTwist, foreBend, foreTwist, collar, elbowname = self.getEntry(self.armTable, prefix, ebones)
                handIK = makeBone(hikname, rig, hand.head, hand.tail, hand.roll, S_HIDDEN, root, hand, hand)
                foreTwist.tail = hand.head
                if self.useCopyRotation:
                    shikname, foreikname = self.getEntry(self.armTable2, prefix, ebones)
                    polelayer = (S_HIDDEN if self.usePoleTargets else layer)
                    shldrIK = makeBone(shikname, rig, shldrBend.head, shldrTwist.tail, shldrBend.roll, polelayer, shldrBend.parent, shldrBend, shldrTwist)
                    foreIK = makeBone(foreikname, rig, foreBend.head, foreTwist.tail, foreBend.roll, S_HIDDEN, shldrIK, foreBend, foreTwist)
                if IK.usePoleTargets:
                    elbow = makePole(elbowname, rig, foreBend, collar)

        if self.useLegs:
            for prefix,layer in [("l",S_LLEGIK), ("r",S_RLEGIK)]:
                foot, fikname, thighBend, thighTwist, shin, hip, kneename = self.getEntry(self.legTable, prefix, ebones)
                footIK = makeBone(fikname, rig, foot.head, foot.tail, foot.roll, S_HIDDEN, root, foot, foot)
                shin.tail = foot.head
                if self.useCopyRotation:
                    thikname, shinikname = self.getEntry(self.legTable2, prefix, ebones)
                    polelayer = (S_HIDDEN if self.usePoleTargets else layer)
                    thighIK = makeBone(thikname, rig, thighBend.head, thighTwist.tail, thighBend.roll, polelayer, thighBend.parent, thighBend, thighTwist)
                    shinIK = makeBone(shinikname, rig, shin.head, shin.tail, shin.roll, S_HIDDEN, thighIK, shin, shin)
                if IK.usePoleTargets:
                    knee = makePole(kneename, rig, shin, hip)

                if self.useReverseFoot:
                    toe, heelIK, toeIK, tarsalIK = self.getEntry(self.footTable, prefix, ebones)
                    toename, heelname, toename, tarsalname = self.getEntry(self.footTable, prefix, {})
                    head = Vector(foot.head)
                    tail = Vector(toe.head)
                    head[2] = tail[2]
                    #head[0] = tail[0]
                    heelIK = makeBone(heelname, rig, head, tail, 0, layer, root, foot, foot)
                    toeIK = makeBone(toename, rig, toe.head, toe.tail, toe.roll, layer, heelIK, toe, toe)
                    tarsalIK = makeBone(tarsalname, rig, toe.head, foot.head, 0, layer, heelIK, toe, shin)
                    footIK.parent = tarsalIK
                    deriveBone("MCH-%s" % tarsalname, tarsalIK, rig, S_HIDDEN, foot)
                    deriveBone("MCH-%s" % heelname, heelIK, rig, S_HIDDEN, foot)

    #----------------------------------------------------------
    #   Make custom shapes
    #----------------------------------------------------------

    def setCustomShape(self, pb, shape, scale=None):
        if shape not in self.customShapes.keys():
            return
        shape,scale0,offset,rotation = self.customShapes[shape]
        if scale is None:
            scale = scale0
        elif isinstance(scale, (int, float)):
            scale = scale*scale0
        else:
            scale = Vector([s0*s for s0,s in zip(scale0,scale)])
        pb.custom_shape = shape
        setCustomShapeTransform(pb, scale, Vector(offset)*pb.bone.length, rotation)


    def makeCustomShapes(self, context, rig, IK):
        def makeSpine(pb, width, tail=0.5, gizmo="CS_Circle"):
            s = width/pb.bone.length
            circle = "CS_%s" % pb.name
            makeCustomShape(circle, gizmo, (0,tail,0))
            self.setCustomShape(pb, circle, s)

        def makeCustomShape(csname, gname, offset=(0,0,0), scale=(1,1,1), rotation=(0,0,0)):
            if bpy.app.version < (3,1,0):
                return
            data = self.customShapes.get(gname)
            if data:
                ob = data[0]
            else:
                struct = self.gizmos[gname]
                verts = struct["verts"]
                me = bpy.data.meshes.new(gname)
                me.from_pydata(verts, struct["edges"], [])
                ob = bpy.data.objects.new(gname, me)
            if isinstance(scale, (int, float)):
                scale = (scale,scale,scale)
            self.customShapes[csname] = (ob, Vector(scale), Vector(offset), Vector(rotation)*D)

        from .fileutils import DF
        setMode('OBJECT')
        self.gizmos = DF.loadEntry("simple", "gizmos", True)
        self.customShapes = {}
        for gname,dtype in [
            ("CS_Circle", 'CIRCLE'),
            ("CS_Cube", 'CUBE'),
            ("CS_Ball", 'SPHERE')]:
            ob = bpy.data.objects.new(gname, None)
            ob.empty_display_type = dtype
            self.customShapes[gname] = (ob, One, Zero, Zero)

        spineWidth = 1
        lCollar = getPoseBone(rig, ("lCollar", "l_shoulder"))
        rCollar = getPoseBone(rig, ("rCollar", "r_shoulder"))
        if lCollar and rCollar:
            spineWidth = 0.5*(lCollar.bone.tail_local[0] - rCollar.bone.tail_local[0])

        makeCustomShape("CS_Rect", "CS_Cube", (0,0.5,0), (0.2,0.5,0.1))
        makeCustomShape("CS_Jaw", "CS_Cube", (0,0.5,0), (0.02,0.5,0.02))
        makeCustomShape("CS_Collar", "CS_Circle", (0,0.5,0), (0.7,0.5,0.2), (0,0,90))
        makeCustomShape("CS_HandFk", "CS_Circle", (0,0.5,0), (0.7,1,0.5), (0,0,90))
        makeCustomShape("CS_Tongue", "CS_Cube", (0,0.5,0), (0.5,0.5,0.1))
        makeCustomShape("CS_CircleY2", "CS_Circle", (0,1,0), 0.3)
        makeCustomShape("CS_Limb", "CS_Circle", (0,0.5,0), 0.25)
        makeCustomShape("CS_Face", "CS_Circle", (0,1,0), 0.2)
        makeCustomShape("CS_Line", "CS_Cube", (0,0.5,0), (0.0,0.5,0.0))
        makeCustomShape("CS_Pole", "CS_Ball", scale=0.25)
        makeCustomShape("CS_HandIk", "CS_Cube", (0,0.5,0), (0.1,0.5,0.25))
        makeCustomShape("CS_FootIk", "CS_Cube", (0,0.5,0), (0.25,0.5,0.1))
        makeCustomShape("CS_ToeIk", "CS_Cube", (0,0.5,0), (0.7,0.5,0.2))
        makeCustomShape("CS_HeelIk", "CS_Cube", (0,-0.5,0.2), (0.3,0.2,0.3))
        makeCustomShape("CS_Arrows", "Arrows")
        makeCustomShape("CS_Root", "CS_Circle", scale=7)
        makeCustomShape("CS_Pect", "CS_Circle", (0,1,0), 0.15)
        makeCustomShape("CS_Foot", "CS_Circle", (0,0.5,0), (0.5,1,1), (90,0,0))
        makeCustomShape("CS_ToeFk", "CS_Circle", (0,0.5,0), (1,1,0.5), (90,0,0))
        self.makeBoneGroups(rig)

        for pb in rig.pose.bones:
            lname = pb.name.lower()
            if pb.bone.hide:
                pass
            elif lname in ["upperfacerig", "lowerfacerig"]:
                enableBoneNumLayer(pb.bone, rig, T_HIDDEN)
            elif lname in ["upperteeth", "lowerteeth"]:
                self.addToLayer(pb, S_SPECIAL, rig, "Special")
            elif not isInNumLayer(pb.bone, rig, T_BONES):
                if not isInNumLayer(pb.bone, rig, T_HIDDEN):
                    self.addToLayer(pb, S_SPECIAL, rig, "Special")
            elif pb.parent and pb.parent.name.lower() in ["lowerfacerig", "upperfacerig"]:
                if pb.name.startswith(("lEyelid", "rEyelid", "l_eyelid", "r_eyelid")):
                    self.setCustomShape(pb, "CS_Line")
                else:
                    self.setCustomShape(pb, "CS_Face")
                self.addToLayer(pb, S_FACE, rig, "Face")
            elif pb.name in ["lEye", "rEye", "lEar", "rEar", "l_eye", "r_eye", "l_ear", "r_ear"]:
                self.setCustomShape(pb, "CS_CircleY2")
                self.addToLayer(pb, S_FACE, rig, "Face")
            elif lname == "lowerjaw":
                self.setCustomShape(pb, "CS_Jaw")
                self.addToLayer(pb, S_FACE, rig, "Face")
            elif pb.name.startswith("tongue"):
                self.setCustomShape(pb, "CS_Tongue")
                self.addToLayer(pb, S_FACE, rig, "Face")
            elif lname.endswith("hand"):
                self.setCustomShape(pb, "CS_HandFk")
                self.addToLayer(pb, S_ARMFK, rig, "FK")
            elif "carpal" in lname or "tarsal" in lname:
                self.addToLayer(pb, S_SPECIAL, rig, "Special")
            elif pb.name in ["lCollar", "rCollar", "l_shoulder", "r_shoulder"]:
                self.setCustomShape(pb, "CS_Collar")
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif lname.endswith("foot"):
                self.setCustomShape(pb, "CS_Foot")
                self.addToLayer(pb, S_LEGFK, rig, "FK")
            elif pb.name in ["lToe", "rToe", "l_toes", "r_toes"]:
                self.setCustomShape(pb, "CS_ToeFk")
                self.addToLayer(pb, S_LEGFK, rig, "Limb")
                if not self.useReverseFoot:
                    self.addToLayer(pb, S_LEGIK, rig, None)
            elif pb.name[1:] in IK.G12Arm + IK.G38Arm + IK.G9Arm:
                self.setCustomShape(pb, "CS_Limb")
                self.addToLayer(pb, S_ARMFK, rig, "FK")
            elif pb.name[1:] in IK.G12Leg + IK.G38Leg + IK.G9Leg:
                self.setCustomShape(pb, "CS_Limb")
                self.addToLayer(pb, S_LEGFK, rig, "FK")
            elif pb.name[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]:
                self.setCustomShape(pb, "CS_Limb")
                self.addToLayer(pb, S_HAND, rig, "Limb")
            elif pb.name == "hip":
                makeSpine(pb, 1.5*spineWidth, gizmo="CS_Cube")
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif pb.name == "pelvis":
                makeSpine(pb, 1.5*spineWidth, 1)
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif pb.name in IK.G38Spine + IK.G12Spine + IK.G9Spine:
                makeSpine(pb, spineWidth)
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif pb.name == "head":
                makeSpine(pb, 0.7*spineWidth, 1)
                self.addToLayer(pb, S_SPINE, rig, "Spine")
                self.addToLayer(pb, S_FACE, rig, None)
            elif pb.name in IK.G38Neck + IK.G12Neck + IK.G9Neck:
                makeSpine(pb, 0.5*spineWidth)
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif "toe" in lname:
                self.setCustomShape(pb, "CS_Limb")
                self.addToLayer(pb, S_FOOT, rig, "Limb")
            elif (pb.name[1:4] in ["Thu", "Ind", "Mid", "Rin", "Pin"] or
                  pb.name[1:5] in ["_thu", "_ind", "_mid", "_rin", "_pin"]):
                self.setCustomShape(pb, "CS_CircleY2")
                self.addToLayer(pb, S_HAND, rig, "Limb")
            elif "elbow" in lname:
                if not pb.name.endswith("STR"):
                    self.setCustomShape(pb, "CS_Pole")
                self.addToLayer(pb, S_ARMIK, rig, "IK")
            elif "knee" in lname:
                if not pb.name.endswith("STR"):
                    self.setCustomShape(pb, "CS_Pole")
                self.addToLayer(pb, S_LEGIK, rig, "IK")
            elif "pectoral" in lname:
                self.setCustomShape(pb, "CS_Pect")
                self.addToLayer(pb, S_SPINE, rig, "Spine")
            elif pb.name.endswith(("twist1", "twist2", "anchor", "footik", "handik")):
                pass
            else:
                #self.setCustomShape(pb, "CS_CircleY2")
                print("Unknown bone:", pb.name)

        from .node import createHiddenCollection
        hidden = createHiddenCollection(context, rig)
        for data in self.customShapes.values():
            ob = data[0]
            if ob.name not in hidden.objects:
                hidden.objects.link(ob)


    BoneGroups = {
        "Spine" :   (1,1,0),
        "FK" :      (0,1,0),
        "IK" :      (1,0,0),
        "Limb" :    (0,0,1),
        "Face" :    (1,0.5,0),
        "Special" :  (1,0,1),
    }

    def makeBoneGroups(self, rig):
        if BLENDER3:
            if len(rig.pose.bone_groups) != len(self.BoneGroups):
                for bg in list(rig.pose.bone_groups):
                    rig.pose.bone_groups.remove(bg)
                for bgname,color in self.BoneGroups.items():
                    bg = rig.pose.bone_groups.new(name=bgname)
                    bg.color_set = 'CUSTOM'
                    bg.colors.normal = color
                    bg.colors.select = (0.6, 0.9, 1.0)
                    bg.colors.active = (1.0, 1.0, 0.8)


    def addToLayer(self, pb, layer, rig, bgname):
        if isinstance(layer, tuple):
            if pb.name[0] == "l":
                layer = layer[0]
            elif pb.name[0] == "r":
                layer = layer[1]
            else:
                print("MISSING LAYER", layer, pb.name)
                return
        setBoneNumLayer(pb.bone, rig, layer)
        if rig and bgname:
            setBonegroup(pb, rig, bgname, self.BoneGroups[bgname])


    def addConstraints(self, rig, IK):
        def copyBoneProps(src, trg):
            trg.DazRotMode = src.DazRotMode
            trg.rotation_mode = src.rotation_mode
            trg.custom_shape = src.custom_shape

        def setStretchLine(pb):
            if not self.usePoleTargets:
                return
            strname = self.stretchName(pb.name)
            stretch = rpbs[strname]
            self.setCustomShape(stretch, "CS_Line")

        def driveConstraint(pb, type, rig, prop):
            for cns in pb.constraints:
                if cns.type == type:
                    addDriver(cns, "influence", rig, (mhxProp(prop), mhxProp("DazRotLimits")), "(1-x1)*x2")

        from .mhx import ikConstraint, addHint, copyRotation, stretchTo, copyTransform, dampedTrack, mhxProp
        from .driver import addDriver
        rpbs = rig.pose.bones
        if self.useRootBone:
            root = rpbs["Root"]
            self.setCustomShape(root, "CS_Root")
            root.rotation_mode = rig.rotation_mode

        for prefix in ["l", "r"]:
            suffix = prefix.upper()
            if self.useArms:
                armProp = "DazArmIK_%s" % suffix
                hand, handIK, shldrBend, shldrTwist, foreBend, foreTwist, collar, elbow = self.getEntry(self.armTable, prefix, rpbs)
                driveConstraint(hand, 'LIMIT_ROTATION', rig, armProp)
                setStretchLine(elbow)
                cns = copyTransform(hand, handIK, rig, prop=armProp, space='POSE')
                setEulerOrder(cns, hand.rotation_mode)
                self.addToLayer(handIK, S_ARMIK, rig, "IK")
            if self.useLegs:
                legProp = "DazLegIK_%s" % suffix
                foot, footIK, thighBend, thighTwist, shin, hip, knee = self.getEntry(self.legTable, prefix, rpbs)
                driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp)
                driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp)
                setStretchLine(knee)
                if not self.useReverseFoot:
                    copyBoneProps(foot, footIK)
                    self.addToLayer(footIK, S_LEGIK, rig, "IK")
                    cns = copyTransform(foot, footIK, rig, prop=legProp, space='POSE')
                    setEulerOrder(cns, foot.rotation_mode)
                else:
                    toe, heelIK, toeIK, tarsalIK = self.getEntry(self.footTable, prefix, rpbs)
                    toeIK.rotation_mode = toe.rotation_mode
                    tarsalIK.rotation_mode = foot.rotation_mode
                    toeIK.lock_location = tarsalIK.lock_location = TTrue
                    toeIK.lock_rotation = tarsalIK.lock_rotation = (False, True, True)
                    driveConstraint(toe, 'LIMIT_ROTATION', rig, legProp)
                    cns = copyTransform(foot, footIK, rig, prop=legProp, space='POSE')
                    setEulerOrder(cns, foot.rotation_mode)
                    cns = copyRotation(toe, toeIK, rig, prop=legProp, space='POSE')
                    setEulerOrder(cns, toe.rotation_mode)
                    self.addToLayer(heelIK, S_LEGIK, rig, "IK")
                    self.addToLayer(toeIK, S_LEGIK, rig, "IK")
                    self.addToLayer(tarsalIK, S_LEGIK, rig, "IK")
                    tarsalCopy = rpbs["MCH-%s" % tarsalIK.name]
                    heelCopy = rpbs["MCH-%s" % heelIK.name]
                    tarsalCopy.rotation_mode = tarsalIK.rotation_mode
                    heelCopy.rotation_mode = heelIK.rotation_mode

            if self.genesis == "G38":
                if self.useArms:
                    self.setCustomShape(handIK, "CS_HandIk")
                    IK.limitBone(shldrBend, True, False, rig, armProp)
                    IK.limitBone(shldrTwist, False, True, rig, armProp)
                    IK.limitBone(foreBend, True, False, rig, armProp)
                    IK.limitBone(foreTwist, False, True, rig, armProp)
                if self.useLegs:
                    self.setCustomShape(footIK, "CS_FootIk", 2)
                    IK.limitBone(thighBend, True, False, rig, legProp)
                    IK.limitBone(thighTwist, False, True, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)
            elif self.genesis == "G9":
                if self.useArms:
                    self.setCustomShape(handIK, "CS_HandIk")
                    IK.limitBone(shldrBend, False, False, rig, armProp)
                    IK.limitBone(foreBend, False, False, rig, armProp)
                if self.useLegs:
                    self.setCustomShape(footIK, "CS_FootIk")
                    IK.limitBone(thighBend, False, False, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)
            elif self.genesis == "G12":
                if self.useArms:
                    self.setCustomShape(handIK, "CS_HandIk", 2)
                    IK.limitBone(shldrBend, False, False, rig, armProp)
                    IK.limitBone(foreBend, False, False, rig, armProp)
                if self.useLegs:
                    self.setCustomShape(footIK, "CS_FootIk")
                    IK.limitBone(thighBend, False, False, rig, legProp)
                    IK.limitBone(shin, False, False, rig, legProp)

            if self.useLegs and self.useReverseFoot:
                self.setCustomShape(tarsalIK, "CS_FootIk")
                self.setCustomShape(toeIK, "CS_ToeIk")
                self.setCustomShape(heelIK, "CS_HeelIk")
                IK.limitBone(foot, False, False, rig, legProp)
                IK.limitBone(toe, False, False, rig, legProp)

            if IK.usePoleTargets:
                if self.useArms:
                    elbow.lock_rotation = TTrue
                    self.setCustomShape(elbow, "CS_Pole")
                    self.addToLayer(elbow, S_ARMIK, rig, "IK")
                    stretch = rpbs[self.stretchName(elbow.name)]
                    stretchTo(stretch, elbow, rig)
                    self.addToLayer(stretch, S_ARMIK, rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = TTrue
                if self.useLegs:
                    knee.lock_rotation = TTrue
                    self.setCustomShape(knee, "CS_Pole")
                    self.addToLayer(knee, S_LEGIK, rig, "IK")
                    stretch = rpbs[self.stretchName(knee.name)]
                    stretchTo(stretch, knee, rig)
                    self.addToLayer(stretch, S_LEGIK, rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = TTrue
            else:
                elbow = knee = None

            foreIK = shinIK = None
            if self.useCopyRotation:
                if self.useArms:
                    shldrIK, foreIK = self.getEntry(self.armTable2, prefix, rpbs)
                    copyBoneProps(shldrBend, shldrIK)
                    shldrIK.rotation_mode = BD.getDefaultMode(shldrBend)
                    copyBoneProps(foreBend, foreIK)
                    foreIK.lock_ik_z = True
                    shldrIK.lock_rotation = (True, False, True)
                    shldrIK.lock_location = foreIK.lock_location = TTrue
                    if self.useImproveIk:
                        addHint(foreIK, rig)
                    ikConstraint(foreIK, handIK, elbow, -90, 2, rig)
                    cns = dampedTrack(shldrBend, foreIK, rig, prop=armProp)
                    cns = copyRotation(shldrTwist, shldrIK, rig, prop=armProp, space='LOCAL')
                    cns.use_x = cns.use_z = False
                    setEulerOrder(cns, BD.getDefaultMode(shldrBend))
                    cns = dampedTrack(foreBend, handIK, rig, prop=armProp)
                    cns = copyRotation(foreTwist, handIK, rig, prop=armProp, space='LOCAL')
                    cns.use_x = cns.use_z = False
                    setEulerOrder(cns, foreTwist.rotation_mode)
                    self.setCustomShape(shldrIK, "CS_Arrows")
                    foreIK.custom_shape = None
                    setBonegroup(shldrIK, rig, "IK", self.BoneGroups["IK"])
                if self.useLegs:
                    thighIK, shinIK = self.getEntry(self.legTable2, prefix, rpbs)
                    copyBoneProps(thighBend, thighIK)
                    thighIK.rotation_mode = BD.getDefaultMode(thighBend)
                    copyBoneProps(shin, shinIK)
                    shinIK.lock_ik_y = shinIK.lock_ik_z = True
                    thighIK.lock_rotation = (True, False, True)
                    thighIK.lock_location = shinIK.lock_location = TTrue
                    if self.useImproveIk:
                        addHint(shinIK, rig)
                    ikConstraint(shinIK, footIK, knee, -90, 2, rig)
                    cns = dampedTrack(thighBend, shinIK, rig, prop=legProp)
                    cns = copyRotation(thighTwist, thighIK, rig, prop=legProp, space='LOCAL')
                    cns.use_x = cns.use_z = False
                    setEulerOrder(cns, BD.getDefaultMode(thighBend))
                    cns = copyTransform(shin, shinIK, rig, prop=legProp, space='POSE')
                    setEulerOrder(cns, shin.rotation_mode)
                    self.setCustomShape(thighIK, "CS_Arrows")
                    shinIK.custom_shape = None
                    setBonegroup(thighIK, rig, "IK", self.BoneGroups["IK"])
            elif self.genesis == "G38":
                if self.useArms:
                    if self.useImproveIk:
                        addHint(foreTwist, rig)
                    ikConstraint(foreTwist, handIK, elbow, -90, 4, rig, prop=armProp)
                if self.useLegs:
                    if self.useImproveIk:
                        addHint(shin, rig)
                    ikConstraint(shin, footIK, knee, -90, 3, rig, prop=legProp)
            else:
                if self.useArms:
                    if self.useImproveIk:
                        addHint(foreBend, rig)
                    ikConstraint(foreBend, handIK, elbow, -90, 2, rig, prop=armProp)
                if self.useLegs:
                    if self.useImproveIk:
                        addHint(shin, rig)
                    ikConstraint(shin, footIK, knee, -90, 2, rig, prop=legProp)


def copyOffsetDrivers(rig):
    def getDrivers(rig, attr):
        fcus = {}
        for fcu in rig.animation_data.drivers:
            bname,channel = getBoneChannel(fcu)
            if channel == attr:
                if bname not in fcus.keys():
                    fcus[bname] = []
                fcus[bname].append(fcu)
        return fcus

    def copyDrivers(rig, bones, attr):
        fcus = getDrivers(rig, attr)
        missing = []
        for bname1,bname0 in bones.items():
            pb1 = rig.pose.bones[bname1]
            setattr(pb1, attr, Zero)
            if bname0 in fcus.keys():
                for fcu0 in fcus[bname0]:
                    fcu1 = rig.animation_data.drivers.from_existing(src_driver=fcu0)
                    fcu1.data_path = 'pose.bones["%s"].%s' % (bname1, attr)
                    fcu1.array_index = fcu0.array_index
            else:
                missing.append((bname1,bname0))
        for bname1,bname0 in missing:
            print("MISS", bname1, bname0)

    from .driver import setFloatProp
    copyDrivers(rig, LS.headbones, "HdOffset")


def getPoseBone(rig, bnames):
    for bname in bnames:
        if bname in rig.pose.bones.keys():
            return rig.pose.bones[bname]
    return None


def setSimpleToFk(rig, layers, useInsertKeys, frame):
    if BLENDER3:
        for n in [S_LARMFK, S_RARMFK, S_LLEGFK, S_RLEGFK]:
            layers[n] = True
        for n in [S_LARMIK, S_RARMIK, S_LLEGIK, S_RLEGIK]:
            layers[n] = False
    else:
        for cname in ["FK Arm Left", "FK Arm Right", "FK Leg Left", "FK Leg Right"]:
            layers[cname] = rig.data.collections.get(cname)
        for cname in ["IK Arm Left", "IK Arm Right", "IK Leg Left", "IK Leg Right"]:
            if cname in layers.keys():
                del layers[cname]
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
            self.snapBones(rig, bnames, prop)
            self.setProp(rig, prop, False)
            self.linearizeFcurve(rig, prop)


    def snapBones(self, rig, bnames, prop):
        pbones,gmats = self.getSnapBones(rig, bnames)
        useGlobal = False
        self.setProp(rig, prop, 0.0)
        if useGlobal:
            updatePose()
        for pb in pbones:
            if useGlobal:
                pb.matrix = gmats[pb.name]
                updatePose()
            else:
                self.snapFkBone(pb, gmats)


    def getSnapBones(self, rig, bnames):
        from .fix import getPreSufName
        pbones = []
        gmats = {}
        for bname in bnames:
            pb = rig.pose.bones.get(getPreSufName(bname, rig))
            if pb:
                pbones.append(pb)
                gmats[pb.name] = pb.matrix.copy()
                if pb.parent and pb.parent.name not in gmats.keys():
                    gmats[pb.parent.name] = pb.parent.matrix.copy()
        return pbones, gmats


    def snapFkBone(self, pb, gmats):
        M1 = gmats[pb.name]
        R1 = pb.bone.matrix_local
        if pb.parent:
            M0 = gmats[pb.parent.name]
            R0 = pb.parent.bone.matrix_local
            pb.matrix_basis = R1.inverted() @ R0 @ M0.inverted() @ M1
        else:
            pb.matrix_basis = R1.inverted() @ M1
        self.keyPose(pb)


class DAZ_OT_SnapSimpleFK(DazOperator, SimpleFKSnapper):
    bl_idname = "daz.snap_simple_fk"
    bl_label = "Snap FK"
    bl_description = "Snap FK bones to IK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()
    if BLENDER3:
        on : IntProperty()
        off : IntProperty()
    else:
        on : StringProperty()
        off : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        self.snapSimpleFK(rig, self.prefix, self.type)
        self.changeLayers(rig, self.on, self.off)


class DAZ_OT_SnapAllSimpleFK(DazOperator, SimpleFKSnapper):
    bl_idname = "daz.snap_all_simple_fk"
    bl_label = "Snap FK All"
    bl_description = "Snap all FK bones to IK bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        for prefix,type,on,off in [
            ("l", "Arm", S_LARMFK, S_LARMIK),
            ("r", "Arm", S_RARMFK, S_RARMIK),
            ("l", "Leg", S_LLEGFK, S_LLEGIK),
            ("r", "Leg", S_RLEGFK, S_RLEGIK)]:
            self.snapSimpleFK(rig, prefix, type)
            self.changeLayers(rig, on, off)


class DAZ_OT_SnapAnimationFK(FrameRange, SimpleFKSnapper):
    bl_idname = "daz.snap_simple_fk_animation"
    bl_label = "Snap FK Animation"
    bl_description = "Snap FK animation for selected frames"
    bl_options = {'UNDO'}

    useLeftArm : BoolProperty(
        name = "Left Arm",
        description = "Include animation for left arm",
        default = True)

    useRightArm : BoolProperty(
        name = "Right Arm",
        description = "Include animation for right arm",
        default = True)

    useLeftLeg : BoolProperty(
        name = "Left Leg",
        description = "Include animation for left leg",
        default = True)

    useRightLeg : BoolProperty(
        name = "Right Leg",
        description = "Include animation for right leg",
        default = True)

    useLayerChange : BoolProperty(
        name = "Change Layers",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useLeftArm")
        self.layout.prop(self, "useRightArm")
        self.layout.prop(self, "useLeftLeg")
        self.layout.prop(self, "useRightLeg")
        self.layout.prop(self, "useLayerChange")
        FrameRange.draw(self, context)

    def run(self, context):
        rig = context.object
        scn = context.scene
        self.auto = True
        bnamess = []
        props = []
        if self.useLeftArm:
            bnamess.append(self.getLimbBoneNames(rig, "l", "Arm"))
            props.append(self.getIKProp("l", "Arm"))
        if self.useRightArm:
            bnamess.append(self.getLimbBoneNames(rig, "r", "Arm"))
            props.append(self.getIKProp("r", "Arm"))
        if self.useLeftLeg:
            bnamess.append(self.getLimbBoneNames(rig, "l", "Leg"))
            props.append(self.getIKProp("l", "Leg"))
        if self.useRightLeg:
            bnamess.append(self.getLimbBoneNames(rig, "r", "Leg"))
            props.append(self.getIKProp("r", "Leg"))
        for frame in range(self.startFrame, self.endFrame+1):
            scn.frame_current = self.frame = frame
            updateScene(context)
            for bnames in bnamess:
                pbones,gmats = self.getSnapBones(rig, bnames)
                for pb in pbones:
                    self.snapFkBone(pb, gmats)
        if self.useLayerChange:
            for frame in (self.startFrame, self.endFrame):
                for prop in props:
                    self.setProp(rig, prop, False)
            for prop in props:
                self.linearizeFcurve(rig, prop)
            if self.useLeftArm:
                self.changeLayers(rig, S_LARMFK, S_LARMIK)
            if self.useRightArm:
                self.changeLayers(rig, S_RARMFK, S_RARMIK)
            if self.useLeftLeg:
                self.changeLayers(rig, S_LLEGFK, S_LLEGIK)
            if self.useRightLeg:
                self.changeLayers(rig, S_RLEGFK, S_RLEGIK)

#----------------------------------------------------------
#   IK Snap
#----------------------------------------------------------

class SimpleIKSnapper(SimpleIK):
    def snapSimpleIK(self, rig, prefix, type, pole):
        bnames = self.getLimbBoneNames(rig, prefix, type)
        if type == "Leg":
            revbones = self.getRevBones(prefix, rig)
            if rig.DazRig == "genesis9":
                shldrik = "%s_thighIK" % prefix
            else:
                shldrik = "%sThighIK" % prefix
        else:
            revbones = []
            if rig.DazRig == "genesis9":
                shldrik = "%s_upperarmIK" % prefix
            else:
                shldrik = "%sShldrIK" % prefix
        if bnames:
            prop = self.getIKProp(prefix, type)
            self.setProp(rig, prop, 0.0)
            updatePose()
            self.snapBones(rig, bnames, prop, pole, shldrik, revbones)
            self.setProp(rig, prop, 1.0)
            self.linearizeFcurve(rig, prop)


    def getRevBones(self, prefix, rig):
        from .fix import getPreSufName
        if rig.DazRig == "genesis9":
            bonelist = [
                ("%s_heelIK" % prefix, "MCH-%s_heelIK" % prefix),
                ("%s_tarsalsIK" % prefix, "MCH-%s_tarsalsIK" % prefix),
                ("%s_toesIK" % prefix, "%s_toes" % prefix)]
        else:
            bonelist = [
                ("%sHeelIK" % prefix, "MCH-%sHeelIK" % prefix),
                ("%sTarsalsIK" % prefix, "MCH-%sTarsalsIK" % prefix),
                ("%sToeIK" % prefix, "%sToe" % prefix)]
        revbones = []
        for bname1,bname2 in bonelist:
            pb1 = rig.pose.bones.get(getPreSufName(bname1, rig))
            pb2 = rig.pose.bones.get(getPreSufName(bname2, rig))
            if pb1 and pb2:
                revbones.append((pb1, pb2))
        return revbones


    def snapBones(self, rig, bnames, prop, pole, shldrik, revbones):
        from .fix import getPreSufName
        hand = bnames[-1]
        handfk = rig.pose.bones.get(getPreSufName(hand, rig))
        if handfk is None:
            return
        handmat = handfk.matrix.copy()
        upbend = bnames[0]
        if len(bnames) == 3:
            loarm = bnames[1]
            uptwist = upbend
        else:
            loarm = bnames[2]
            uptwist = bnames[1]
        upbendfk = rig.pose.bones.get(getPreSufName(upbend, rig))
        uptwistfk = rig.pose.bones.get(getPreSufName(uptwist, rig))
        loarmfk = rig.pose.bones.get(getPreSufName(loarm, rig))
        pole = getPreSufName(pole, rig)
        if pole:
            poleik = rig.pose.bones.get(pole)
            polemat = self.getPoleMatrix(upbendfk, loarmfk)
        else:
            shldrik = rig.pose.bones.get(getPreSufName(shldrik, rig))
            if uptwistfk.rotation_mode == 'QUATERNION':
                xyz = BD.getDefaultMode(upbendfk)
                shldrrot = upbendfk.rotation_quaternion.to_euler(xyz)[1]
            else:
                shldrrot = uptwistfk.rotation_euler[1]
        revmats = []
        for pb1,pb2 in revbones:
            revmats.append((pb1, pb2.matrix.copy()))
        self.setProp(rig, prop, 1.0)
        for pb,mat in revmats:
            pb.matrix = mat
            updatePose()
            self.keyPose(pb)
        handik = rig.pose.bones.get(getPreSufName("%sIK" % hand, rig))
        if handik:
            handik.matrix = handmat
            updatePose()
            self.keyPose(handik)
        if pole:
            poleik.matrix = polemat
            updatePose()
            self.keyPose(poleik)
        elif shldrik:
            shldrik.rotation_euler = (0, shldrrot, 0)
            self.keyPose(shldrik)
        return
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
    bl_description = "Snap IK bones to FK bones.\nSnapping is only approximate"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()
    pole : StringProperty()
    if BLENDER3:
        on : IntProperty()
        off : IntProperty()
    else:
        on : StringProperty()
        off : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        self.snapSimpleIK(rig, self.prefix, self.type, self.pole)
        self.changeLayers(rig, self.on, self.off)


class DAZ_OT_SnapAllSimpleIK(DazOperator, SimpleIKSnapper):
    bl_idname = "daz.snap_all_simple_ik"
    bl_label = "Snap IK All"
    bl_description = "Snap all IK bones to FK bones.\nSnapping is only approximate"
    bl_options = {'UNDO'}

    pole : StringProperty()

    def run(self, context):
        rig = context.object
        self.initAuto(context)
        for prefix,type,pole,on,off in [
            ("l", "Arm", "lElbow", S_LARMIK, S_LARMFK),
            ("r", "Arm", "rElbow", S_RARMIK, S_RARMFK),
            ("l", "Leg", "lKnee", S_LLEGIK, S_LLEGFK),
            ("r", "Leg", "rKnee", S_RLEGIK, S_RLEGFK)]:
            self.snapSimpleIK(rig, prefix, type, pole)
            self.changeLayers(rig, on, off)

#----------------------------------------------------------
#   Connect bone chains
#----------------------------------------------------------

class DAZ_OT_ToggleFkIk(DazOperator, SimpleIKSnapper):
    bl_idname = "daz.toggle_fk_ik"
    bl_label = "Toggle FK IK"
    bl_description = "Toggle FK/IK"
    bl_options = {'UNDO'}

    prop : StringProperty()
    value : FloatProperty()

    def run(self, context):
        rig = context.object
        setattr(rig, self.prop, self.value)

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
                pb.lock_location = FFalse
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

class DAZ_OT_SelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.select_named_layers"
    bl_label = "All"
    bl_description = "Select all named layers and unselect all unnamed layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        if BLENDER3:
            rig.data.layers = 16*[False] + 15*[True] + [False]
        else:
            for coll in rig.data.collections:
                coll.is_visible = False
            for cname in SimpleLayers.values():
                coll = rig.data.collections.get(cname)
                if coll and cname != "Hidden":
                    coll.is_visible = True


class DAZ_OT_UnSelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.unselect_named_layers"
    bl_label = ("Only Active" if BLENDER3 else "None")
    bl_description = "Unselect all named and unnamed layers except active"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        if BLENDER3:
            m = 16
            bone = rig.data.bones.active
            if bone:
                for n in range(16,30):
                    if bone.layers[n]:
                        m = n
                        break
            rig.data.layers = m*[False] + [True] + (S_HIDDEN-m)*[False]
        else:
            coll0 = rig.data.collections.active
            for cname in SimpleLayers.values():
                coll = rig.data.collections.get(cname)
                if coll and coll != coll0:
                    coll.is_visible = False

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
            for pb in rig.pose.bones:
                if pb.bone.select:
                    pb.custom_shape = ob
                    setCustomShapeTransform(pb, self.scale, self.translation, Vector(self.rotation)*D)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddSimpleIK,
    DAZ_OT_SnapSimpleFK,
    DAZ_OT_SnapSimpleIK,
    DAZ_OT_SnapAllSimpleFK,
    DAZ_OT_SnapAllSimpleIK,
    DAZ_OT_SnapAnimationFK,
    DAZ_OT_ToggleFkIk,
    DAZ_OT_ConnectBoneChains,
    DAZ_OT_SelectNamedLayers,
    DAZ_OT_UnSelectNamedLayers,
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ImproveIK,
    DAZ_OT_BatchSetCustomShape,
]

def register():
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
