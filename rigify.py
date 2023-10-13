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
import os
from collections import OrderedDict
from mathutils import Vector

from .error import *
from .utils import *
from .layers import *
from .fileutils import DF
from .fix import Fixer, GizmoUser, BendTwists, ConstraintStore

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def setupRigifyData(meta):
    global RF
    from .rigify_data import RigifyData
    RF = RigifyData(meta)

#-------------------------------------------------------------
#   DazBone
#-------------------------------------------------------------

class DazBone:
    def __init__(self, eb):
        self.name = eb.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = None
        self.use_deform = eb.use_deform
        self.rotation_mode = None
        self.store = ConstraintStore()


    def getPose(self, pb):
        self.rotation_mode = pb.rotation_mode
        self.lock_location = pb.lock_location
        self.lock_rotation = pb.lock_rotation
        self.lock_scale = pb.lock_scale
        self.store.storeConstraints(pb.name, pb)


    def setPose(self, pb, rig):
        pb.rotation_mode = self.rotation_mode
        pb.lock_location = self.lock_location
        pb.lock_rotation = self.lock_rotation
        pb.lock_scale = self.lock_scale
        self.store.restoreConstraints(pb.name, pb, target=rig)


def addDicts(structs):
    joined = {}
    for struct in structs:
        for key,value in struct.items():
            joined[key] = value
    return joined

#-------------------------------------------------------------
#   RigifyCommon
#-------------------------------------------------------------

class RigifyCommon:
    gizmoFile = "mhx"

    GroupBones = [
        ("Face ", R_FACE, 2, 6),
        ("Face (detail) ", R_DETAIL, 2, 3),
        ("Custom ", R_CUSTOM, 13, 6)]

    def setupDazSkeleton(self, rig):
        if rig.DazRig in ["genesis", "genesis1", "genesis2"]:
            self.rigifySkel = RF.RigifyGenesis38
            self.rigifySkel["chestUpper"] = "chestUpper"
            self.rigifySkel["abdomen2"] = "abdomen2"
            self.spineBones = RF.Genesis38Spine
            self.genesisFingers = RF.Genesis1238Fingers
        elif rig.DazRig in ["genesis3", "genesis8"]:
            self.rigifySkel = RF.RigifyGenesis38
            self.spineBones = RF.Genesis38Spine
            self.genesisFingers = RF.Genesis1238Fingers
        elif rig.DazRig == "genesis9":
            self.rigifySkel = RF.RigifyGenesis9
            self.spineBones = RF.Genesis9Spine
            self.genesisFingers = RF.Genesis9Fingers

        self.dazSkel = {}
        for rbone, dbone in self.rigifySkel.items():
            if isinstance(dbone, tuple):
                dbone = dbone[0]
            if isinstance(dbone, str):
                self.dazSkel[dbone] = rbone


    def getDazBones(self, rig):
        # Setup info about DAZ bones
        self.dazBones = OrderedDict()
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            self.dazBones[eb.name] = DazBone(eb)
        setMode('OBJECT')
        for pb in rig.pose.bones:
            self.dazBones[pb.name].getPose(pb)

#-------------------------------------------------------------
#   MetaMaker
#-------------------------------------------------------------

class MetaMaker(RigifyCommon):
    useOptimizePose : BoolProperty(
        name = "Optimize Pose For IK",
        description = "Optimize rest pose before rigifying.\nFor hand animation, because poses will not be imported correctly",
        default = True)

    useAutoAlign : BoolProperty(
        name = "Auto Align Hand/Foot",
        description = "Auto align hand and foot (Rigify parameter)",
        default = True)

    useRecalcRoll : BoolProperty(
        name = "Recalc Roll",
        description = "Recalculate the roll angles of the thigh and shin bones,\nso they are aligned with the global Z axis.\nFor Genesis 1,2, and 3 characters",
        default = False)

    useSplitShin : BoolProperty(
        name = "Split Shin Bone",
        description = "Split the shin bone into bend and twist parts",
        default = False)

    useCustomLayers : BoolProperty(
        name = "Custom Layers",
        description = "Display layers for face and custom bones.\nNot for Rigify legacy",
        default = True)

    if bpy.app.version >= (3,3,0):
        useSeparateIkToe : BoolProperty(
            name = "Separate IK Toes",
            description = "Create separate IK toe controls for better IK/FK snapping",
            default = True)
    else:
        useSeparateIkToe = False


    def draw(self, context):
        self.layout.prop(self, "useOptimizePose")
        self.layout.prop(self, "useAutoAlign")
        self.layout.prop(self, "useRecalcRoll")
        self.layout.prop(self, "useSplitShin")
        self.layout.prop(self, "useCustomLayers")


    def createMeta(self, context):
        from collections import OrderedDict
        from .mhx import connectToParent, unhideAllObjects
        from .figure import getRigType, finalizeArmature
        from .merge import mergeBones, mergeVertexGroups

        print("Create metarig")
        rig = context.object
        scale = rig.DazScale
        scn = context.scene
        if not(rig and rig.type == 'ARMATURE'):
            raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)
        self.makeRealParents(context, rig)

        if self.useOptimizePose:
            from .convert import optimizePose
            optimizePose(context, True)
        if self.useKeepRig:
            dazrig = self.saveDazRig(context)
        else:
            dazrig = None
        finalizeArmature(rig)

        unhideAllObjects(context, rig)
        for bname in ["lEye", "rEye", "l_eye", "r_eye"]:
            pb = rig.pose.bones.get(bname)
            if pb:
                self.storeConstraints(bname, pb)

        # Create metarig
        setMode('OBJECT')
        try:
            bpy.ops.object.armature_human_metarig_add()
        except AttributeError:
            raise DazError("The Rigify add-on is not enabled. It is found under rigging.")
        bpy.ops.object.location_clear()
        bpy.ops.object.rotation_clear()
        bpy.ops.object.scale_clear()
        bpy.ops.transform.resize(value=(100*scale, 100*scale, 100*scale))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        print("  Fix metarig")
        meta = context.object
        makeBoneCollections(meta, RigifyLayers)
        cns = meta.constraints.new('COPY_SCALE')
        cns.name = "Rigify Source"
        cns.target = rig
        cns.mute = True

        meta["DazMetaRig"] = True
        meta.DazRig = "metarig"
        useSplitNeck = (rig.DazRig in ["genesis3", "genesis8", "genesis9"])
        if useSplitNeck:
            self.splitNeck(meta)
        meta["DazUseSplitNeck"] = useSplitNeck
        meta["DazSplitShin"] = self.useSplitShin
        meta["DazReuseBendTwists"] = self.reuseBendTwists
        meta["DazFingerIk"] = self.useFingerIk
        meta["DazCustomLayers"] = self.useCustomLayers

        setupRigifyData(meta)

        activateObject(context, rig)
        rig.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        print("  Fix bones", rig.DazRig)
        if rig.DazRig in ["genesis", "genesis1", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            self.splitBone(rig, "chest", "chestUpper")
            self.splitBone(rig, "abdomen", "abdomen2")
        elif rig.DazRig in ["genesis3", "genesis8"]:
            self.deleteBendTwistDrvBones(rig)
            print("DLL")
            mergers = dict((list(RF.Genesis38Mergers1.items()) + list(RF.Genesis38Mergers2.items())))
            print("MM", mergers)
            mergeBones(rig, mergers, RF.Genesis38Parents, context)
            print("NNN")
            if dazrig:
                pass
            elif meta["DazReuseBendTwists"]:
                mergeVertexGroups(rig, RF.Genesis38Mergers2)
            else:
                mergeVertexGroups(rig, mergers)
            self.renameBones(rig, RF.Genesis38Renames, dazrig)
            print("RR")
        elif rig.DazRig == "genesis9":
            if dazrig:
                pass
            elif meta["DazReuseBendTwists"]:
                self.removeVertexGroups(rig, RF.Genesis9Removes)
            else:
                mergeBones(rig, RF.Genesis9Mergers, RF.Genesis9Parents, context)
                mergeVertexGroups(rig, RF.Genesis9Mergers)
        else:
            msg = "Cannot rigify %s %s" % (rig.DazRig, rig.name)
            activateObject(context, meta)
            deleteObjects(context, [meta])
            raise DazError(msg)

        print("  Connect to parent")
        connectToParent(rig, connectAll=True, useSplitShin=self.useSplitShin)
        print("  Setup DAZ skeleton")
        self.setupDazSkeleton(rig)
        self.getDazBones(rig)

        # Fit metarig to default DAZ rig
        print("  Fit to DAZ")
        #setActiveObject(context, meta)
        meta.select_set(True)
        activateObject(context, meta)
        setMode('EDIT')
        self.fitToDaz(meta)
        hip = self.fitHip(meta)

        if rig.DazRig in ["genesis3", "genesis8", "genesis9"]:
            eb = meta.data.edit_bones[RF.head]
            eb.tail = eb.head + 1.0*(eb.tail - eb.head)

        self.fixHands(meta)
        self.fitLimbs(meta, hip)
        if meta["DazCustomLayers"]:
            self.addGroupBones(meta, rig)

        for eb in meta.data.edit_bones:
            if (eb.parent and
                eb.head == eb.parent.tail and
                eb.name not in RF.MetaDisconnect):
                eb.use_connect = True

        self.fitSpine(meta)
        print("  Reparent bones")
        self.reparentBones(meta, RF.MetaParents)
        print("  Add props to rigify")
        connect,disconnect = self.addRigifyProps(meta)
        if meta["DazCustomLayers"]:
            self.setupGroupBones(meta)

        print("  Set connected")
        setMode('EDIT')
        self.setConnected(meta, connect, disconnect)
        self.recalcRoll(rig.DazRig, meta)
        setMode('OBJECT')
        print("Metarig created")
        return rig, meta, dazrig


    def splitBone(self, rig, bname, upname):
        if upname in rig.data.bones.keys():
            return
        setMode('EDIT')
        eblow = rig.data.edit_bones[bname]
        vec = eblow.tail - eblow.head
        mid = eblow.head + vec/2
        ebup = rig.data.edit_bones.new(upname)
        for eb in eblow.children:
            eb.parent = ebup
        ebup.head = mid
        ebup.tail = eblow.tail
        ebup.parent = eblow
        ebup.roll = eblow.roll
        eblow.tail = mid
        setMode('OBJECT')


    def addRigifyProps(self, meta):
        # Add rigify properties to spine bones
        setMode('OBJECT')
        disconnect = []
        connect = []
        for pb in meta.pose.bones:
            if "rigify_type" in pb.keys():
                if pb["rigify_type"] == "":
                    pass
                elif pb["rigify_type"] == "spines.super_head":
                    disconnect.append(pb.name)
                elif pb["rigify_type"] == "limbs.super_finger":
                    connect += self.getChildren(pb)
                    pb.rigify_parameters.primary_rotation_axis = 'X'
                    pb.rigify_parameters.make_extra_ik_control = self.useFingerIk
                elif pb["rigify_type"] == "limbs.super_limb":
                    pb.rigify_parameters.rotation_axis = 'x'
                    pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
                elif pb["rigify_type"] == "limbs.leg":
                    pb.rigify_parameters.extra_ik_toe = self.useSeparateIkToe
                    pb.rigify_parameters.rotation_axis = 'x'
                    pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
                elif pb["rigify_type"] == "limbs.arm":
                    pb.rigify_parameters.rotation_axis = 'x'
                    pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
                elif pb["rigify_type"] in [
                    "spines.super_spine",
                    "spines.basic_spine",
                    "basic.super_copy",
                    "limbs.super_palm",
                    "limbs.simple_tentacle"]:
                    pass
                else:
                    pass
                    print("RIGIFYTYPE %s: %s" % (pb.name, pb["rigify_type"]))
            if hasattr (pb.rigify_parameters, "roll_alignment"):
                pb.rigify_parameters.roll_alignment = "manual"
        for rname,prop,value in RF.RigifyParams:
            if rname in meta.pose.bones:
                pb = meta.pose.bones[rname]
                setattr(pb.rigify_parameters, prop, value)
        return connect, disconnect


    def addGroupBones(self, meta, rig):
        tail = (0,0,10*rig.DazScale)
        for bname,layer,row,group in self.GroupBones:
            eb = meta.data.edit_bones.new(bname)
            eb.head = (0,0,0)
            eb.tail = tail
            enableBoneLayer(eb, meta, layer)


    def setupGroupBones(self, meta):
        for bname,layer,row,group in self.GroupBones:
            pb = meta.pose.bones[bname]
            pb["rigify_type"] = "basic.pivot"
            enableRigLayer(meta, layer)
            if bpy.app.version < (4,0,0):
                rlayer = meta.data.rigify_layers[layer]
                rlayer.name = bname
                rlayer.row = row
                rlayer.group = group
        if bpy.app.version < (4,0,0):
            meta.data.layers[0] = False
            rlayer = meta.data.rigify_layers[0]
            rlayer.name = ""
            rlayer.group = 6


    def getChildren(self, pb):
        chlist = []
        for child in pb.children:
            chlist.append(child.name)
            chlist += self.getChildren(child)
        return chlist


    def setConnected(self, meta, connect, disconnect):
        # Connect and disconnect bones that have to be so
        for rname in disconnect:
            eb = meta.data.edit_bones[rname]
            eb.use_connect = False
        for rname in connect:
            eb = meta.data.edit_bones[rname]
            eb.use_connect = True


    def recalcRoll(self, dazrig, meta):
        if not self.useRecalcRoll or dazrig in ["genesis8", "genesis9"]:
            return
        # https://bitbucket.org/Diffeomorphic/import_daz/issues/199/rigi-fy-thigh_ik_targetl-and
        for eb in meta.data.edit_bones:
            eb.select = False
        for rname in ["thigh.L", "thigh.R", "shin.L", "shin.R"]:
            eb = meta.data.edit_bones[rname]
            eb.select = True
        bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y')


    def splitNeck(self, meta):
        setMode('EDIT')
        spine = meta.data.edit_bones["spine"]
        spine3 = meta.data.edit_bones["spine.003"]
        bonelist={}
        bpy.ops.armature.select_all(action='DESELECT')
        spine3.select = True
        bpy.ops.armature.subdivide()
        spinebones = spine.children_recursive_basename
        chainlength = len(spinebones)
        for x in range(chainlength):
            y = str(x)
            spinebones[x].name = "spine" + "." + y
        for x in range(chainlength):
            y = str(x+1)
            spinebones[x].name = "spine" + ".00" + y
        bpy.ops.armature.select_all(action='DESELECT')
        setMode('OBJECT')


    def renameBones(self, rig, bones, dazrig):
        for dname,rname in bones.items():
            self.deleteBoneDrivers(rig, dname)
        setMode('EDIT')
        for dname,rname in bones.items():
            if dname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[dname]
                eb.name = rname
                self.renamedBones[rname] = dname
            else:
                msg = ("Did not find bone %s     " % dname)
                raise DazError(msg)
        setMode('OBJECT')
        if dazrig:
            for ob in getMeshChildren(rig):
                for dname,rname in bones.items():
                    vgrp = ob.vertex_groups.get(rname)
                    if vgrp:
                        vgrp.name = dname


    def fitToDaz(self, meta):
        for eb in meta.data.edit_bones:
            eb.use_connect = False

        for eb in meta.data.edit_bones:
            dname = self.rigifySkel.get(eb.name)
            if isinstance(dname, tuple):
                dname,_vgrps = dname
            if isinstance(dname, str):
                if dname in self.dazBones.keys():
                    dbone = self.dazBones[dname]
                    eb.head = dbone.head
                    eb.tail = dbone.tail
                    eb.roll = dbone.roll
            elif isinstance(dname, tuple):
                if (dname[0] in self.dazBones.keys() and
                    dname[1] in self.dazBones.keys()):
                    dbone1 = self.dazBones[dname[0]]
                    dbone2 = self.dazBones[dname[1]]
                    eb.head = dbone1.head
                    eb.tail = dbone2.head


    def fitHip(self, meta):
        hip = meta.data.edit_bones[RF.hips]
        dbone = self.dazBones["hip"]
        hip.tail = Vector((1,2,3))
        hip.head = dbone.tail
        hip.tail = dbone.head
        return hip


    def fitLimbs(self, meta, hip):
        for suffix in ["L", "R"]:
            shoulder = meta.data.edit_bones["shoulder.%s" % suffix]
            upperarm = meta.data.edit_bones["upper_arm.%s" % suffix]
            shin = meta.data.edit_bones["shin.%s" % suffix]
            foot = meta.data.edit_bones["foot.%s" % suffix]
            toe = meta.data.edit_bones["toe.%s" % suffix]

            vec = shoulder.tail - shoulder.head
            if (upperarm.head - shoulder.tail).length < 0.02*vec.length:
                shoulder.tail -= 0.02*vec

            if "pelvis.%s" % suffix in meta.data.edit_bones.keys():
                thigh = meta.data.edit_bones["thigh.%s" % suffix]
                pelvis = meta.data.edit_bones["pelvis.%s" % suffix]
                pelvis.head = hip.head
                pelvis.tail = thigh.head

            foot.head = shin.tail
            toe.head = foot.tail
            xa,ya,za = foot.head
            xb,yb,zb = toe.head

            heelhead = foot.head
            heeltail = Vector((xa, yb-1.3*(yb-ya), zb))
            mid = (toe.head + heeltail)/2
            r = Vector((yb-ya,0,0))
            if xa > 0:
                fac = 0.3
            else:
                fac = -0.3
            heel02head = mid + fac*r
            heel02tail = mid - fac*r

            if "heel.%s" % suffix in meta.data.edit_bones.keys():
                heel = meta.data.edit_bones["heel.%s" % suffix]
                heel.head = heelhead
                heel.tail = heeltail
            if "heel.02.%s" % suffix in meta.data.edit_bones.keys():
                heel02 = meta.data.edit_bones["heel.02.%s" % suffix]
                heel02.head = heel02head
                heel02.tail = heel02tail


    def fitSpine(self, meta):
        mbones = meta.data.edit_bones
        for dname in self.spineBones.keys():
            if dname not in self.dazBones.keys():
                continue
            rname,pname = self.spineBones[dname]
            dbone = self.dazBones[dname]
            if rname in mbones.keys():
                eb = mbones[rname]
            else:
                eb = mbones.new(dname)
                eb.name = rname
            eb.use_connect = False
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.parent = mbones[pname]
            eb.use_connect = True
            copyBoneLayers(eb.parent, eb, meta)


    def reparentBones(self, rig, parents):
        setMode('EDIT')
        for bname,pname in parents.items():
            if (pname in rig.data.edit_bones.keys() and
                bname in rig.data.edit_bones.keys()):
                eb = rig.data.edit_bones[bname]
                parb = rig.data.edit_bones[pname]
                eb.use_connect = False
                eb.parent = parb
        setMode('OBJECT')

#-------------------------------------------------------------
#   Rigifier
#-------------------------------------------------------------

class Rigifier(RigifyCommon):
    useImproveIk : BoolProperty(
        name = "Improve IK",
        description = "Improve IK by storing a bending angle.\nThis is compatible with daz poses but does not work with rigify poles so they can not be used.\nNot needed if Optimize Pose for IK is used",
        default = False)

    def setupExtras(self, context, rig):
        def addRecursive(pb):
            if pb.name not in self.extras.keys():
                self.extras[pb.name] = pb.name
            for child in pb.children:
                addRecursive(child)

        self.extras = OrderedDict()
        taken = []
        for dbone in self.spineBones.keys():
            taken.append(dbone)
        for dbone in self.rigifySkel.values():
            if isinstance(dbone, tuple):
                dbone = dbone[0]
                if isinstance(dbone, tuple):
                    dbone = dbone[0]
            taken.append(dbone)
        for ob in self.meshes:
            for vgrp in ob.vertex_groups:
                if (vgrp.name not in taken and
                    vgrp.name in rig.data.bones.keys()):
                    self.extras[vgrp.name] = vgrp.name
        for bname in ["Face_Controls_XYZ"]:
            pb = rig.pose.bones.get(bname)
            if pb:
                addRecursive(pb)
        for dbone in list(self.extras.keys()):
            bone = rig.data.bones[dbone]
            while bone.parent:
                pname = bone.parent.name
                if pname in self.extras.keys() or pname in taken:
                    break
                self.extras[pname] = pname
                bone = bone.parent
        for pb in rig.data.bones:
            if isDrvBone(pb.name):
                self.extras[pb.name] = pb.name


    def checkRigifyEnabled(self, context):
        for addon in context.user_preferences.addons:
            if addon.module == "rigify":
                return True
        return False


    def getRigifyBone(self, bname, bones):
        if bname in RF.DeformBones:
            rname = RF.DeformBones[bname]
        elif bname[1:] in RF.DeformBones:
            prefix = bname[0]
            rname = RF.DeformBones[bname[1:]] % prefix.upper()
        elif bname in self.spineBones.keys():
            rname,pname = self.spineBones[bname]
            rname = "DEF-%s" % rname
        elif bname in self.dazSkel.keys():
            rname = self.dazSkel[bname]
            if rname in RF.MetaBones.keys():
                rname = "DEF-%s" % RF.MetaBones[rname]
            else:
                rname = "DEF-%s" % rname
        elif bname in self.extras.keys():
            rname = self.extras[bname]
        else:
            rname = bname
        if rname in bones.keys():
            return rname
        if len(bname) > 2:
            if bname[1] == "_":
                pname = "%s.%s" % (bname[2:], bname[0].upper())
                if pname in bones.keys():
                    return pname
            pname = "%s%s" % (bname[0].lower(), bname[1:])
            if pname in bones.keys():
                return pname
            pname = "%s%s.%s" % (bname[1].lower(), bname[2:], bname[0].upper())
            if pname in bones.keys():
                return pname
        else:
            pname = ""
        if not isDrvBone(bname):
            print("MISS", bname, rname, pname)
        return None


    def rigifyMeta(self, context, rig, meta, dazrig):
        self.createTmp()
        try:
            return self.rigifyMeta1(context, rig, meta, dazrig)
        finally:
            self.deleteTmp()


    def rigifyMeta1(self, context, rig, meta, dazrig):
        from .driver import getBoneDrivers, getPropDrivers, copyProp
        from .mhx import unhideAllObjects, getBoneLayer

        print("Rigify metarig")
        setMode('OBJECT')
        setupRigifyData(meta)
        coll = getCollection(context, rig)
        unhideAllObjects(context, rig)
        if rig.name not in coll.objects.keys():
            coll.objects.link(rig)
        self.meshes = (getMeshChildren(dazrig) if dazrig else getMeshChildren(rig))

        setMode('POSE')
        try:
            bpy.ops.pose.rigify_generate()
        except:
            raise DazError("Cannot rigify %s rig %s    " % (rig.DazRig, rig.name))

        scn = context.scene
        gen = context.object
        makeBoneCollections(gen, RigifyLayers)
        if gen.name in scn.collection.objects:
            scn.collection.objects.unlink(gen)
        if gen.name not in coll.objects:
            coll.objects.link(gen)
        self.startGizmos(context, gen)
        print("Fix generated rig", gen.name)

        print("  Setup DAZ Skeleton")
        setActiveObject(context, rig)
        self.setupDazSkeleton(rig)
        self.getDazBones(rig)

        print("  Setup extras")
        self.setupExtras(context, rig)
        print("  Get driven bones")
        driven = {}
        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
            if fcus:
                driven[pb.name] = fcus

        # Add extra bones to generated rig
        print("  Add extra bones")
        setActiveObject(context, gen)
        setMode('EDIT')
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            dbone = self.dazBones[dname]
            eb = gen.data.edit_bones.new(rname)
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.use_deform = dbone.use_deform
            if eb.use_deform:
                enableBoneLayer(eb, gen, R_FACE)
                setBoneLayer(eb, gen, R_DEFORM)
            else:
                enableBoneLayer(eb, gen, R_HELP)
            if dname in driven.keys():
                enableBoneLayer(eb, gen, R_HELP)

        # Group bones
        print("  Create group bones")
        if meta["DazCustomLayers"]:
            for data in self.GroupBones:
                eb = gen.data.edit_bones[data[0]]
                enableBoneLayer(eb, gen, R_HELP)

        # Add parents to extra bones
        print("  Add parents to extra bones")
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            dbone = self.dazBones[dname]
            eb = gen.data.edit_bones[rname]
            if dbone.parent:
                parname = RF.ExtraParents.get(dbone.name)
                if parname not in gen.data.edit_bones.keys():
                    parname = self.getRigifyBone(dbone.parent, gen.data.edit_bones)
                if parname:
                    eb.parent = gen.data.edit_bones[parname]
                    eb.use_connect = (eb.parent != None and eb.parent.tail == eb.head)
                else:
                    print("No parent", dbone.name, dbone.parent)
                    if isDrvBone(dbone.name):
                        continue
                    bones = list(self.dazSkel.keys())
                    bones.sort()
                    print("Bones:", bones)
                    msg = ("Bone %s has no parent %s" % (dbone.name, dbone.parent))
                    raise DazError(msg)

        # Gaze bones
        print("  Create gaze bones")
        for suffix in ["L", "R"]:
            self.addSingleGazeBone(gen, suffix, R_FACE, R_HELP)
        self.addCombinedGazeBone(gen, R_FACE, R_HELP)
        self.checkTongueIk(gen)
        if self.useTongueIk:
            setMode('EDIT')
            self.addTongueIkBones(gen, R_FACE, R_DEFORM)

        setMode('POSE')

        # Lock extras
        print("  Lock extras")
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                self.dazBones[dname].setPose(pb, gen)
                mhxlayer,unlock = getBoneLayer(pb, gen)
                layer = MhxRigifyLayer[mhxlayer]
                enableBoneLayer(pb.bone, gen, layer)
                if unlock:
                    pb.lock_location = (False, False, False)
                self.copyBoneInfo(dname, rname, rig, gen)
                if isFinal(dname):
                    enableBoneLayer(pb.bone, gen, R_FIN)

        # Rescale custom shapes
        if rig.DazRig in ["genesis3", "genesis8"]:
            customfix = RF.CustomShapeFixGenesis38
        elif rig.DazRig == "genesis9":
            customfix = RF.CustomShapeFixGenesis9
        else:
            customfix = []
        for bnames,scale in customfix:
            self.fixCustomShape(gen, bnames, scale)
        self.fixCustomShape(gen, ["chest"], 1, Vector((0,-100*rig.DazScale,0)))

        # Add DAZ properties
        print("  Add DAZ properties")
        for key in list(rig.keys()):
            copyProp(key, rig, gen, True)
        for key in rig.data.keys():
            copyProp(key, rig.data, gen.data, False)

        # Some more bones
        conv = DF.loadEntry("genesis-%s" % meta.DazRigifyType, "converters")
        for srcname,trgname in conv.items():
            self.copyBoneInfo(srcname, trgname, rig, gen)

        # Handle bone parents
        print("  Reparent bones")
        children = (dazrig.children if dazrig else rig.children)
        for ob in children:
            if ob.parent_type == 'BONE':
                wmat = ob.matrix_world.copy()
                rname = self.getRigifyBone(ob.parent_bone, gen.data.bones)
                ob.parent = gen
                if rname:
                    print("    Parent %s to bone %s" % (ob.name, rname))
                    ob.parent_type = 'BONE'
                    ob.parent_bone = rname
                else:
                    print("    Did not find bone parent %s" % dname)
                    ob.parent_type = 'OBJECT'
                setWorldMatrix(ob, wmat)

        # Limbs
        if rig.DazRig == "genesis9":
            self.limbs = {
                "_upperarm" : "upper_arm",
                "_forearm" : "forearm",
                "_thigh" : "thigh",
                "_shin" : "shin",
            }
        else:
            self.limbs = {
                "Shldr" : "upper_arm",
                "ForeArm" : "forearm",
                "Thigh" : "thigh",
                "Shin" : "shin",
            }

        # Change vertex groups
        activateObject(context, gen)
        self.bendTwistNames = {}
        self.spineBones["pelvis"] = ("spine", None)
        if not dazrig:
            self.changeVertexGroups(context, rig, meta, gen)

        # Fix drivers
        print("  Fix drivers")
        assoc = {}
        for bname in rig.data.bones.keys():
            if isDrvBone(bname) or isFinal(bname):
                continue
            assoc[bname] = bname
        for rname,dname in self.rigifySkel.items():
            if isinstance(dname, tuple):
                dname = dname[0]
            orgname = self.getOrgDefBone(rname, gen)
            assoc[dname] = orgname
        for dname,rnames in self.spineBones.items():
            assoc[dname] = self.getOrgDefBone(rnames[0], gen)

        for fcu in getPropDrivers(rig):
            fcu2 = self.copyDriver(fcu, gen, old=rig, new=gen)
        for fcu in getPropDrivers(rig.data):
            fcu2 = self.copyDriver(fcu, gen.data, old=rig, new=gen)
        for bname, fcus in driven.items():
            if bname in gen.pose.bones.keys():
                pb = gen.pose.bones[bname]
                for fcu in fcus:
                    self.copyBoneProp(fcu, rig, gen, pb)
                for fcu in fcus:
                    fcu2 = self.copyDriver(fcu, gen, old=rig, new=gen, assoc=assoc)

        # Fix bend and twist drivers
        print("  Fix bend and twist drivers")
        for dname0,rname0 in self.limbs.items():
            for prefix,suffix in [("l","L"), ("r","R")]:
                dname = "%s%s" % (prefix, dname0)
                rname = "%s.%s" % (rname0, suffix)
                bname = self.getOrgDefBone(rname, gen)
                assoc[dname] = bname
                assoc["%sBend" % dname] = bname
                self.fixIkBone(dname, rig, (rname0, suffix), gen)
        self.fixBoneDrivers(gen, rig, assoc)
        self.renameBendTwistDrivers(gen.data)

        # Unlock bend locks
        for rname in ["upper_arm", "forearm", "thigh"]:
            for suffix in ["L", "R"]:
                bname = "%s_fk.%s" % (rname, suffix)
                pb = gen.pose.bones.get(bname)
                if pb is None:
                    bname = "%s.fk.%s" % (rname, suffix)
                    pb = gen.pose.bones.get(bname)
                if pb:
                    pb.lock_rotation = (False, False, False)

        # Face bone and gizmos
        if rig.DazRig == "genesis9":
            rename = ["_pectoral", "_eye", "_ear", "_metatarsal"]
            rename += [bone.name[1:] for bone in gen.data.bones
                if bone.name.endswith(("toe1", "toe2"))]
        else:
            rename = ["Pectoral", "Eye", "Ear", "Metatarsals"]
            rename += [bone.name[1:] for bone in gen.data.bones
                if bone.name[1:].startswith(("BigToe", "SmallToe"))]
        self.renameFaceBones(gen, rename)
        self.addGizmos(gen)

        # Gaze bones
        for suffix in ["L", "R"]:
            self.addGazeConstraint(gen, suffix)
        self.addGazeFollowsHead(gen)
        self.addTongueControl(gen)

        # Finger IK
        if meta["DazFingerIk"]:
            self.fixFingerIk(rig, gen)

        # Improve IK
        if self.useImproveIk:
            from .simple import improveIk
            improveIk(gen, exclude=self.tongueBones)

        #Clean up
        print("  Clean up")
        #gen.data.display_type = 'WIRE'
        gen.show_in_front = True
        gen.DazRig = meta.DazRigifyType
        name = rig.name
        if coll:
            if gen.name in scn.collection.objects:
                scn.collection.objects.unlink(gen)
            if gen.name not in coll.objects:
                coll.objects.link(gen)
            if meta.name in scn.collection.objects:
                scn.collection.objects.unlink(meta)
            if meta.name not in coll.objects:
                coll.objects.link(meta)
            for wname in ["WGTS_rig"]:
                wcoll = scn.collection.children.get(wname)
                if wcoll:
                    scn.collection.children.unlink(wcoll)
                    coll.children.link(wcoll)
                    layer = getLayerCollection(context, wcoll)
                    if layer:
                        layer.exclude = True
                    break
        if bpy.app.version < (4,0,0):
            setFkIk2(gen, False, gen.data.layers, False, 0)
        if activateObject(context, rig):
            deleteObjects(context, [rig])
        if self.useDeleteMeta:
            if activateObject(context, meta):
                deleteObjects(context, [meta])
        activateObject(context, gen)
        enableRigLayers(gen, [R_TORSO, R_FACE])
        gen.name = name
        if dazrig:
            self.tieBones(dazrig, gen)
            self.setRigName(gen, dazrig, "RIGIFY")
        print("Rigify created")
        return gen


    def copyBoneProp(self, fcu, rig, gen, pb):
        from .driver import copyProp
        bname = prop = None
        words = fcu.data_path.split('"')
        if words[0] == "pose.bones[" and words[2] == "][":
            bname = words[1]
            prop = words[3]
            if bname in rig.pose.bones.keys():
                copyProp(prop, rig.pose.bones[bname], pb, False)


    def copyBoneInfo(self, srcname, trgname, rig, gen):
        from .figure import copyBoneInfo
        if (srcname in rig.pose.bones.keys() and
            trgname in gen.pose.bones.keys()):
            srcpb = rig.pose.bones[srcname]
            trgpb = gen.pose.bones[trgname]
            copyBoneInfo(srcpb, trgpb)
            if srcpb.custom_shape:
                trgpb.custom_shape = srcpb.custom_shape
                if hasattr(trgpb, "custom_shape_scale"):
                    trgpb.custom_shape_scale = srcpb.custom_shape_scale
                else:
                    trgpb.custom_shape_scale_xyz = srcpb.custom_shape_scale_xyz
                enableBoneLayer(trgpb.bone, gen, R_CUSTOM)


    def getOrgDefBone(self, bname, rig):
        def isCopyTransformed(bname, rig, pb0):
            if bname not in rig.pose.bones.keys():
                return False
            pb = rig.pose.bones[bname]
            if getConstraint(pb, 'COPY_TRANSFORMS'):
                if pb0:
                    pb.rotation_mode = pb0.rotation_mode
                return True
            return False

        pb = rig.pose.bones.get(bname)
        if pb is None:
            pb = rig.pose.bones.get("%s_fk.%s" % (bname[:-2], bname[-1]))
        if pb is None:
            pb = rig.pose.bones.get("%s_fk_%s" % (bname[:-2], bname[-1]))
        if pb is None:
            pass
            #print("Could not find FK bone", bname)
        if isCopyTransformed("ORG-"+bname, rig, pb):
            return "ORG-"+bname
        elif isCopyTransformed("DEF-"+bname, rig, pb):
            return "DEF-"+bname
        else:
            return bname


    def renameBendTwistDrivers(self, rna):
        for fcu in list(rna.animation_data.drivers):
            words = fcu.data_path.split('"', 2)
            if words[1] in self.bendTwistNames.keys():
                fcu.data_path = '%s"%s"%s' % (words[0], self.bendTwistNames[words[1]], words[2])


    def changeVertexGroups(self, context, rig, meta, gen):
        print("  Change vertex groups")
        for ob in self.meshes:
            if ob.parent == gen and ob.parent_type == 'BONE':
                continue
            ob.parent = gen
            for dname in self.spineBones.keys():
                rname,_pname = self.spineBones[dname]
                if dname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[dname]
                    vgrp.name = "DEF-%s" % rname

            for rname,dname in self.rigifySkel.items():
                if str(dname[1:]) in self.limbs.keys():
                    self.rigifySplitGroup(rname, dname, ob, rig, True, meta, gen)
                elif isinstance(dname, str):
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = "DEF-%s" % rname
                else:
                    self.mergeVertexGroups(rname, dname[1], ob)

            for dname,rname in self.extras.items():
                if dname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[dname]
                    vgrp.name = rname

            self.changeAllTargets(ob, rig, gen)


    def fixIkBone(self, dname, rig, rname, gen):
        pb = rig.pose.bones.get(dname)
        if pb:
            rotmode = pb.rotation_mode
            locks = list(pb.lock_rotation)
            locks[1] = False
        else:
            print("Missing DAZ bone", dname)
            return
        pb = gen.pose.bones.get("%s_ik.%s" % rname)
        if pb is None:
            pb = gen.pose.bones.get("MCH-%s_ik.%s" % rname)
        if pb is None:
            pb = gen.pose.bones.get("%s.ik.%s" % rname)
        if pb is None:
            pb = gen.pose.bones.get("MCH-%s.ik.%s" % rname)
        if pb is None:
            print("Missing IK bone: %s_ik.%s" % rname)
        pb.rotation_mode = rotmode
        for n,x in enumerate(["x", "y", "z"]):
            setattr(pb, "lock_ik_%s" % x, locks[n])


    def rigifySplitGroup(self, rname, dname, ob, rig, before, meta, gen):
        def splitBone():
            bone = rig.data.bones[dname]
            if dname in ob.vertex_groups.keys():
                self.splitVertexGroup(ob, dname, bendname, twistname, bone.head_local, bone.tail_local)

        if before:
            bendname = "DEF-%s" % rname
            twistname = "DEF-%s.001" % rname
        else:
            bendname = "DEF-%s.01" % rname
            twistname = "DEF-%s.02" % rname
        ldname = dname.lower()
        if meta["DazSplitShin"] and "shin" in ldname:
            splitBone()
        elif meta["DazReuseBendTwists"] or "shin" in ldname:
            vgrps = [(vgrp.name.lower(),vgrp) for vgrp in ob.vertex_groups
                      if vgrp.name.lower().startswith(ldname)]
            for vname,vgrp in vgrps:
                if vname.endswith(("twist", "twist2")):
                    vgrp.name = twistname
                elif vname.endswith("twist1"):
                    vgrp.name = bendname
                else:
                    vgrp.name = bendname
        else:
            splitBone()



    def mergeVertexGroups(self, rname, dnames, ob):
        if not (dnames and
                dnames[0] in ob.vertex_groups.keys()):
            return
        vgrp = ob.vertex_groups[dnames[0]]
        vgrp.name = "DEF-" + rname


    def setBoneName(self, bone, gen):
        fkname = bone.name.replace(".", ".fk.")
        if fkname in gen.data.bones.keys():
            gen.data.bones[fkname]
            bone.fkname = fkname
            bone.ikname = fkname.replace(".fk.", ".ik")

        defname = "DEF-" + bone.name
        if defname in gen.data.bones.keys():
            gen.data.bones[defname]
            bone.realname = defname
            return

        defname1 = "DEF-" + bone.name + ".01"
        if defname in gen.data.bones.keys():
            gen.data.bones[defname1]
            bone.realname1 = defname1
            bone.realname2 = defname1.replace(".01.", ".02.")
            return

        defname1 = "DEF-" + bone.name.replace(".", ".01.")
        if defname in gen.data.bones.keys():
            gen.data.bones[defname1]
            bone.realname1 = defname1
            bone.realname2 = defname1.replace(".01.", ".02")
            return

        if bone.name in gen.data.bones.keys():
            gen.data.edit_bones[bone.name]
            bone.realname = bone.name


    def addGizmos(self, gen):
        gizmos = {
            "lowerjaw" :        ("GZM_MJaw", 1, R_FACE),
            "lowerJaw" :        ("GZM_MJaw", 1, R_FACE),
            "eye.L" :           ("GZM_Circle", 0.25, R_FACE),
            "eye.R" :           ("GZM_Circle", 0.25, R_FACE),
            "ear.L" :           ("GZM_Circle", 0.375, R_FACE),
            "ear.R" :           ("GZM_Circle", 0.375, R_FACE),
            "pelvis" :          (None, 1, R_HELP),
            "pectoral.L" :      ("GZM_Pectoral", 1, R_TORSOTWEAK),
            "pectoral.R" :      ("GZM_Pectoral", 1, R_TORSOTWEAK),
            "metatarsals.L" :   (None, 1, R_HELP),
            "metatarsals.R" :   (None, 1, R_HELP),
            "gaze" :            ("GZM_Gaze", 1, R_FACE),
            "gaze.L" :          ("GZM_Circle", 0.25, R_FACE),
            "gaze.R" :          ("GZM_Circle", 0.25, R_FACE),
            "ik_tongue" :       ("GZM_Cone", 0.4, R_FACE),
        }
        self.makeGizmos(True, ["GZM_MJaw", "GZM_Foot", "GZM_Gaze", "GZM_Pectoral", "GZM_MTongue"])
        if bpy.app.version < (4,0,0):
            bgrp = gen.pose.bone_groups.new(name="DAZ")
            bgrp.color_set = 'CUSTOM'
            bgrp.colors.normal = (1.0, 0.5, 0)
            bgrp.colors.select = (0.596, 0.898, 1.0)
            bgrp.colors.active = (0.769, 1, 1)
        for pb in gen.pose.bones:
            if pb.name in gizmos.keys():
                gizmo,scale,layer = gizmos[pb.name]
                if gizmo:
                    self.addGizmo(pb, gizmo, scale)
                setBonegroup(pb, gen, "DAZ")
                enableBoneLayer(pb.bone, gen, layer)
            elif self.isFaceBone(pb, gen):
                if not self.isEyeLid(pb):
                    self.addGizmo(pb, "GZM_Circle", 0.2)
                setBonegroup(pb, gen, "DAZ")
            elif pb.name[0:6] == "tongue":
                self.addGizmo(pb, "GZM_MTongue", 1)
                setBonegroup(pb, gen, "DAZ")
            elif (pb.name.startswith(("bigToe", "smallToe")) or
                  pb.name.endswith(("toe1.L", "toe2.L", "toe1.R", "toe2.R"))):
                self.addGizmo(pb, "GZM_Circle", 0.4)
                setBonegroup(pb, gen, "DAZ")

        # Hide some bones on a hidden layer
        for rname in [
            "upperTeeth", "lowerTeeth",
            ]:
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                enableBoneLayer(pb.bone, gen, 29)


    def fixFingerIk(self, rig, gen):
        for suffix in ["L", "R"]:
            for dfing,rfing in self.genesisFingers:
                for link in range(1,4):
                    dname = "%s%s%d" % (suffix.lower(), dfing, link)
                    rname = "ORG-%s.%02d.%s" % (rfing, link, suffix)
                    db = rig.pose.bones[dname]
                    pb = gen.pose.bones[rname]
                    for n,attr in [(0,"lock_ik_x"), (1,"lock_ik_y"), (2,"lock_ik_z")]:
                        if False and db.lock_rotation[n]:
                            setattr(pb, attr, True)
                    cns = getConstraint(db, 'LIMIT_ROTATION')
                    if cns:
                        for comp in ["x", "y", "z"]:
                            if getattr(cns, "use_limit_%s" % comp):
                                dmin = getattr(cns, "min_%s" % comp)
                                dmax = getattr(cns, "max_%s" % comp)
                                setattr(pb, "use_ik_limit_%s" % comp, True)
                                setattr(pb, "ik_min_%s" % comp, dmin)
                                setattr(pb, "ik_max_%s" % comp, dmax)


    def tieBone(self, pb, gen, assoc, facebones, rigtype):
        if pb.name.endswith(("twist1", "twist2", "metatarsal", "hand_anchor")):
            return
        from .mhx import copyLocation, copyRotation, copyTransform
        rname = self.getRigifyBone(pb.name, gen.data.bones)
        if rname is None:
            return
        rb = gen.pose.bones.get(rname)
        if rb is None:
            return
        elif pb.name == "pelvis":
            pass
        elif rname.startswith(("DEF-foot", "DEF-hand")):
            cns = copyTransform(pb, rb, gen, space='POSE')
        elif pb.name == "hip":
            if bpy.app.version >= (3,0,0):
                cns = copyTransform(pb, rb, gen, space='LOCAL')
                cns.target_space = 'LOCAL_OWNER_ORIENT'
            else:
                cns = copyLocation(pb, rb, gen, space='WORLD')
                cns.head_tail = 1.0
                cns = copyRotation(pb, rb, gen, space='LOCAL')
                cns.invert_x = False
                cns.invert_y = True
                cns.invert_z = True
        elif rname.startswith("DEF-toe"):
            if bpy.app.version >= (3,0,0):
                cns = copyTransform(pb, rb, gen, space='LOCAL')
                cns.target_space = 'LOCAL_OWNER_ORIENT'
            else:
                cns = copyRotation(pb, rb, gen, space='LOCAL')
                cns.invert_x = True
                cns.invert_y = False
                cns.invert_z = True
        elif rname.startswith(("DEF-palm", "DEF-spine")):
            cns = copyTransform(pb, rb, gen, space='LOCAL')
            if bpy.app.version >= (3,0,0):
                cns.target_space = 'LOCAL_OWNER_ORIENT'
        #elif "twist" in pb.name.lower():
        #    cns = copyRotation(pb, rb, gen, space='LOCAL')
        elif pb.name in facebones:
            cns = copyTransform(pb, rb, gen, space='LOCAL')
        else:
            cns = copyTransform(pb, rb, gen, space='POSE')

#-------------------------------------------------------------
#  Buttons
#-------------------------------------------------------------

class DAZ_OT_ConvertToRigify(DazPropsOperator, MetaMaker, Rigifier, Fixer, GizmoUser, BendTwists, ConstraintStore):
    bl_idname = "daz.convert_to_rigify"
    bl_label = "Convert To Rigify"
    bl_description = "Convert active rig to rigify"
    bl_options = {'UNDO', 'PRESET'}

    useDeleteMeta : BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = True
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.DazSimpleIK)

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    def draw(self, context):
        MetaMaker.draw(self, context)
        self.layout.prop(self, "useDeleteMeta")
        if bpy.app.version >= (3,3,0):
            self.layout.prop(self, "useSeparateIkToe")
        Fixer.draw(self, context)


    def storeState(self, context):
        from .driver import muteDazFcurves
        DazPropsOperator.storeState(self, context)
        rig = context.object
        self.dazDriversDisabled = rig.DazDriversDisabled
        muteDazFcurves(rig, True)


    def restoreState(self, context):
        from .driver import muteDazFcurves
        DazPropsOperator.restoreState(self, context)
        gen = context.object
        muteDazFcurves(gen, self.dazDriversDisabled)


    def run(self, context):
        t1 = perf_counter()
        print("Modifying DAZ rig to Rigify")
        rig,meta,dazrig = self.createMeta(context)
        self.rigname = rig.name
        gen = self.rigifyMeta(context, rig, meta, dazrig)
        t2 = perf_counter()
        print("DAZ rig %s successfully rigified in %.3f seconds" % (self.rigname, t2-t1))
        self.printMessages()


class DAZ_OT_CreateMeta(DazPropsOperator, MetaMaker, Fixer, BendTwists, ConstraintStore):
    bl_idname = "daz.create_meta"
    bl_label = "Create Metarig"
    bl_description = "Create a metarig from the active rig"
    bl_options = {'UNDO'}

    def draw(self, context):
        MetaMaker.draw(self, context)
        Fixer.draw(self, context)

    def drawRigify(self):
        pass

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis") and not ob.DazSimpleIK)

    def run(self, context):
        rig,meta,dazrig = self.createMeta(context)
        meta.data["DazOrigRig"] = rig.name
        if dazrig:
            meta.data["DazKeptRig"] = dazrig.name
        self.printMessages()


class DAZ_OT_RigifyMetaRig(DazPropsOperator, Rigifier, Fixer, GizmoUser, BendTwists, ConstraintStore):
    bl_idname = "daz.rigify_meta"
    bl_label = "Rigify Metarig"
    bl_description = "Convert metarig to rigify"
    bl_options = {'UNDO'}

    useDeleteMeta = False

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    def draw(self, context):
        Fixer.draw(self, context)

    def drawMeta(self):
        pass

    @classmethod
    def poll(self, context):
        rig = context.object
        return (rig and rig.get("DazMetaRig"))

    def run(self, context):
        meta = context.object
        rig = None
        self.rigname = meta.data.get("DazOrigRig")
        if self.rigname:
            rig = bpy.data.objects.get(self.rigname)
        if rig is None:
            raise DazError("Original rig not found")
        dazrig = None
        nrigname = meta.data.get("DazKeptRig")
        if nrigname:
            dazrig = bpy.data.objects.get(nrigname)
        self.rigifyMeta(context, rig, meta, dazrig)
        self.printMessages()

#-------------------------------------------------------------
#   Set rigify to FK. For load pose.
#-------------------------------------------------------------

def setFkIk1(rig, ik, layers, useInsertKeys, frame):
    value = float(ik)
    for bname in ["hand.ik.L", "hand.ik.R", "foot.ik.L", "foot.ik.R"]:
        pb = rig.pose.bones[bname]
        pb["ik_fk_switch"] = pb["ikfk_switch"] = value
        if useInsertKeys:
            pb.keyframe_insert(propRef("ik_fk_switch"), frame=frame)
            pb.keyframe_insert(propRef("ikfk_switch"), frame=frame)
    if "head.001" in rig.pose.bones.keys():
        pb = rig.pose.bones["head.001"]
        pb["neck_follow"] = value
        if useInsertKeys:
            pb.keyframe_insert(propRef("neck_follow"), frame=frame)
    for pname in ["MhaTongueIk"]:
        if pname in rig.keys():
            rig[pname] = 0.0
            if useInsertKeys:
                rig.keyframe_insert(propRef(pname), frame=frame)
        if pname in rig.data.keys():
            rig.data[pname] = 0.0
            if useInsertKeys:
                rig.data.keyframe_insert(propRef(pname), frame=frame)
    return layers


def setFkIk2(rig, fk, layers, useInsertKeys, frame):
    value = float(fk)
    for bname in ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]:
        pb = rig.pose.bones[bname]
        pb["IK_FK"] = value
        if useInsertKeys:
            pb.keyframe_insert(propRef("IK_FK"), frame=frame)
    if "torso" in rig.pose.bones.keys():
        pb = rig.pose.bones["torso"]
        pb["neck_follow"] = 1.0
        pb["head_follow"] = 1.0
        if useInsertKeys:
            pb.keyframe_insert(propRef("neck_follow"), frame=frame)
            pb.keyframe_insert(propRef("head_follow"), frame=frame)
    for suffix in ["L", "R"]:
        for fing in ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]:
            pb = rig.pose.bones.get("%s.01_ik.%s" % (fing, suffix))
            if pb:
                pb["FK_IK"] = 0.0
                if useInsertKeys:
                    pb.keyframe_insert(propRef("FK_IK"), frame=frame)
    for pname in ["MhaTongueIk"]:
        if pname in rig.keys():
            rig[pname] = 0.0
            if useInsertKeys:
                rig.keyframe_insert(propRef(pname), frame=frame)
        if pname in rig.data.keys():
            rig.data[pname] = 0.0
            if useInsertKeys:
                rig.data.keyframe_insert(propRef(pname), frame=frame)
    for n in [8, 11, 14, 17]:
        layers[n] = fk
    for n in [7, 10, 13, 16]:
        layers[n] = (not fk)
    return layers

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ConvertToRigify,
    DAZ_OT_CreateMeta,
    DAZ_OT_RigifyMetaRig,
]

def register():
    # Duplicated definitions from MHX RTS.

    bpy.types.Object.MhaGazeFollowsHead = FloatPropOVR(0.0,
        name = "Gaze Follows Head",
        min = 0, max = 1,
        description = "The gaze bone follows the head bone rotations")

    bpy.types.Object.MhaGaze_L = FloatPropOVR(0.0,
        name = "Gaze Left",
        min = 0, max = 1,
        description = "eye tracking the left gaze bone amount")

    bpy.types.Object.MhaGaze_R = FloatPropOVR(0.0,
        name = "Gaze Right",
        min = 0, max = 1,
        description = "eye tracking the right gaze bone amount")

    bpy.types.Object.MhaTongueIk = FloatPropOVR(0.0,
        name = "Tongue IK",
        min = 0, max = 1,
        description = "Tongue bones controlled by IK")

    bpy.types.Armature.MhaFeatures = IntProperty(default = 0)

    bpy.types.Object.DazRigifyType = StringProperty(default="")

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
