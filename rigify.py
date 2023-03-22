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
from .fileutils import AF
from .fix import Fixer, GizmoUser, BendTwists, ConstraintStore


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


class Rigify:
    useOptimizePose : BoolProperty(
        name = "Optimize Pose For IK",
        description = "Optimize rest pose before rigifying.\nFor hand animation, because poses will not be imported correctly",
        default = True)

    useAutoAlign : BoolProperty(
        name = "Auto Align Hand/Foot",
        description = "Auto align hand and foot (Rigify parameter)",
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

    useRecalcRoll : BoolProperty(
        name = "Recalc Roll",
        description = "Recalculate the roll angles of the thigh and shin bones,\nso they are aligned with the global Z axis.\nFor Genesis 1,2, and 3 characters",
        default = False)

    GroupBones = [("Face ", R_FACE, 2, 6),
                  ("Face (detail) ", R_DETAIL, 2, 3),
                  ("Custom ", R_CUSTOM, 13, 6)]

    def setupDazSkeleton(self, rig):
        if rig.DazRig in ["genesis1", "genesis2"]:
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


    def renameBones(self, rig, bones):
        for dname,rname in bones.items():
            self.deleteBoneDrivers(rig, dname)
        setMode('EDIT')
        for dname,rname in bones.items():
            if dname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[dname]
                eb.name = rname
            else:
                msg = ("Did not find bone %s     " % dname)
                raise DazError(msg)
        setMode('OBJECT')


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
            eb.layers = list(eb.parent.layers)


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
                elif pb["rigify_type"] in [
                    "spines.super_spine",
                    "spines.basic_spine",
                    "basic.super_copy",
                    "limbs.super_palm",
                    "limbs.simple_tentacle"]:
                    pass
                else:
                    pass
                    #print("RIGIFYTYPE %s: %s" % (pb.name, pb["rigify_type"]))
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
            eb.layers = layer*[False] + [True] + (31-layer)*[False]


    def setupGroupBones(self, meta):
        for bname,layer,row,group in self.GroupBones:
            pb = meta.pose.bones[bname]
            pb["rigify_type"] = "basic.pivot"
            meta.data.layers[layer] = True
            rlayer = meta.data.rigify_layers[layer]
            rlayer.name = bname
            rlayer.row = row
            rlayer.group = group
        meta.data.layers[0] = False
        rlayer = meta.data.rigify_layers[0]
        rlayer.name = ""
        rlayer.group = 6


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


    def setupExtras(self, context, rig):
        def addRecursive(pb, extras):
            if pb.name not in extras.keys():
                extras[pb.name] = pb.name
            for child in pb.children:
                addRecursive(child, extras)

        extras = OrderedDict()
        taken = []
        for dbone in self.spineBones.keys():
            taken.append(dbone)
        for dbone in self.rigifySkel.values():
            if isinstance(dbone, tuple):
                dbone = dbone[0]
                if isinstance(dbone, tuple):
                    dbone = dbone[0]
            taken.append(dbone)
        for ob in getArmatureChildren(context, rig):
            for vgrp in ob.vertex_groups:
                if (vgrp.name not in taken and
                    vgrp.name in rig.data.bones.keys()):
                    extras[vgrp.name] = vgrp.name
        for bname in ["Face_Controls_XYZ"]:
            pb = rig.pose.bones.get(bname)
            if pb:
                addRecursive(pb, extras)
        for dbone in list(extras.keys()):
            bone = rig.data.bones[dbone]
            while bone.parent:
                pname = bone.parent.name
                if pname in extras.keys() or pname in taken:
                    break
                extras[pname] = pname
                bone = bone.parent
        for pb in rig.data.bones:
            if isDrvBone(pb.name):
                extras[pb.name] = pb.name
        return extras


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


    def checkRigifyEnabled(self, context):
        for addon in context.user_preferences.addons:
            if addon.module == "rigify":
                return True
        return False


    def getRigifyBone(self, bname, extras, bones):
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
        elif bname in extras.keys():
            rname = extras[bname]
        if rname and rname in bones.keys():
            return rname
        print("MISS", bname, rname)
        return None


    def getDazBones(self, rig):
        # Setup info about DAZ bones
        self.dazBones = OrderedDict()
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            self.dazBones[eb.name] = DazBone(eb)
        setMode('OBJECT')
        for pb in rig.pose.bones:
            self.dazBones[pb.name].getPose(pb)


    def createMeta(self, context):
        global RF
        from collections import OrderedDict
        from .mhx import connectToParent, unhideAllObjects
        from .figure import getRigType
        from .merge import mergeBones, mergeVertexGroups
        from .rigify_data import RigifyData

        print("Create metarig")
        rig = context.object
        scale = rig.DazScale
        scn = context.scene
        if not(rig and rig.type == 'ARMATURE'):
            raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)

        unhideAllObjects(context, rig)
        for bname in ["lEye", "rEye", "l_eye", "r_eye"]:
            pb = rig.pose.bones.get(bname)
            if pb:
                self.storeConstraints(bname, pb)

        if self.useOptimizePose:
            from .convert import optimizePose
            optimizePose(context, True)

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
        cns = meta.constraints.new('COPY_SCALE')
        cns.name = "Rigify Source"
        cns.target = rig
        cns.mute = True

        meta.DazMeta = True
        meta.DazRig = "metarig"
        meta.DazUseSplitNeck = (rig.DazRig in ["genesis3", "genesis8", "genesis9"])
        if meta.DazUseSplitNeck:
            self.splitNeck(meta)
        RF = RigifyData(meta)

        activateObject(context, rig)
        rig.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        print("  Fix bones", rig.DazRig)
        if rig.DazRig in ["genesis1", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            self.splitBone(rig, "chest", "chestUpper")
            self.splitBone(rig, "abdomen", "abdomen2")
        elif rig.DazRig in ["genesis3", "genesis8"]:
            self.deleteBendTwistDrvBones(rig)
            mergeBones(rig, RF.Genesis38Mergers, RF.Genesis38Parents, context)
            if not self.reuseBendTwists:
                mergeVertexGroups(rig, RF.Genesis38Mergers)
            self.renameBones(rig, RF.Genesis38Renames)
        elif rig.DazRig == "genesis9":
            if self.reuseBendTwists:
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
        connectToParent(rig, connectAll=True)
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
        if self.useCustomLayers:
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
        if self.useCustomLayers:
            self.setupGroupBones(meta)

        print("  Set connected")
        setMode('EDIT')
        self.setConnected(meta, connect, disconnect)
        self.recalcRoll(rig.DazRig, meta)
        setMode('OBJECT')

        print("Metarig created")
        return meta


    def rigifyMeta(self, context):
        self.createTmp()
        try:
            self.rigifyMeta1(context)
        finally:
            self.deleteTmp()


    def rigifyMeta1(self, context):
        from .driver import getBoneDrivers, getPropDrivers, copyProp
        from .node import setParent, clearParent
        from .mhx import unhideAllObjects, getBoneLayer

        print("Rigify metarig")
        meta = context.object
        setMode('OBJECT')
        rig = None
        for cns in meta.constraints:
            if cns.type == 'COPY_SCALE' and cns.name == "Rigify Source":
                rig = cns.target

        if rig is None:
            raise DazError("Original rig not found")
        coll = getCollection(context, rig)
        unhideAllObjects(context, rig)
        if rig.name not in coll.objects.keys():
            coll.objects.link(rig)

        setMode('POSE')
        for pb in meta.pose.bones:
            if hasattr(pb, "rigify_parameters"):
                if hasattr (pb.rigify_parameters, "roll_alignment"):
                    pb.rigify_parameters.roll_alignment = "manual"

        try:
            bpy.ops.pose.rigify_generate()
        except:
            raise DazError("Cannot rigify %s rig %s    " % (rig.DazRig, rig.name))

        scn = context.scene
        gen = context.object
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
        extras = self.setupExtras(context, rig)
        print("  Get driven bones")
        driven = {}
        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
            if fcus:
                driven[pb.name] = fcus

        # Add extra bones to generated rig
        print("  Add extra bones")
        faceLayers = R_FACE*[False] + [True] + (31-R_FACE)*[False]
        helpLayers = R_HELP*[False] + [True] + (31-R_HELP)*[False]
        setActiveObject(context, gen)
        setMode('EDIT')
        for dname,rname in extras.items():
            if dname not in self.dazBones.keys():
                continue
            dbone = self.dazBones[dname]
            eb = gen.data.edit_bones.new(rname)
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.use_deform = dbone.use_deform
            if eb.use_deform:
                eb.layers = faceLayers
                eb.layers[R_DEFORM] = True
            else:
                eb.layers = helpLayers
            if dname in driven.keys():
                eb.layers = helpLayers

        # Group bones
        print("  Create group bones")
        if self.useCustomLayers:
            for data in self.GroupBones:
                eb = gen.data.edit_bones[data[0]]
                eb.layers = helpLayers

        # Add parents to extra bones
        print("  Add parents to extra bones")
        for dname,rname in extras.items():
            if dname not in self.dazBones.keys():
                continue
            dbone = self.dazBones[dname]
            eb = gen.data.edit_bones[rname]
            if dbone.parent:
                parname = RF.ExtraParents.get(dbone.name)
                if parname not in gen.data.edit_bones.keys():
                    parname = self.getRigifyBone(dbone.parent, extras, gen.data.edit_bones)
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
        print(" Create tongue IK")
        setMode('OBJECT')
        setMode('EDIT')
        self.addTongueIkBone(gen, R_FACE)

        setMode('POSE')

        # Lock extras
        print("  Lock extras")
        for dname,rname in extras.items():
            if dname not in self.dazBones.keys():
                continue
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                self.dazBones[dname].setPose(pb, gen)
                mhxlayer,unlock = getBoneLayer(pb, gen)
                layer = MhxRigifyLayer[mhxlayer]
                pb.bone.layers = layer*[False] + [True] + (31-layer)*[False]
                if unlock:
                    pb.lock_location = (False, False, False)
                self.copyBoneInfo(dname, rname, rig, gen)
                if isFinal(dname):
                    pb.bone.layers = R_FIN*[False] + [True] + (31-R_FIN)*[False]


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
        conv = AF.loadEntry("genesis-%s" % meta.DazRigifyType, "converters")
        for srcname,trgname in conv.items():
            self.copyBoneInfo(srcname, trgname, rig, gen)

        # Handle bone parents
        print("  Handle bone parents")
        boneParents = []
        for ob in getArmatureChildren(context, rig):
            if ob.parent_type == 'BONE':
                boneParents.append((ob, ob.parent_bone))
                clearParent(ob)

        for ob,dname in boneParents:
            rname = self.getRigifyBone(dname, extras, gen.data.bones)
            if rname:
                print("Parent %s to bone %s" % (ob.name, rname))
                bone = gen.data.bones[rname]
                setParent(context, ob, gen, bone.name)
            else:
                print("Did not find bone parent %s" % dname)
                setParent(context, ob, gen, None)

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
        print("  Change vertex groups")
        activateObject(context, gen)
        self.bendTwistNames = {}
        for ob in getArmatureChildren(context, rig):
            if ob.type == 'MESH':
                ob.parent = gen

                self.spineBones["pelvis"] = ("spine", None)
                for dname in self.spineBones.keys():
                    rname,_pname = self.spineBones[dname]
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = "DEF-" + rname

                for rname,dname in self.rigifySkel.items():
                    if str(dname[1:]) in self.limbs.keys():
                        self.rigifySplitGroup(rname, dname, ob, rig, True, meta, gen)
                    elif isinstance(dname, str):
                        if dname in ob.vertex_groups.keys():
                            vgrp = ob.vertex_groups[dname]
                            vgrp.name = "DEF-" + rname
                    else:
                        self.mergeVertexGroups(rname, dname[1], ob)

                for dname,rname in extras.items():
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = rname

                self.changeAllTargets(ob, rig, gen)

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
        self.fixBoneDrivers(gen, assoc)
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
        self.addTongueIk(gen)

        # Finger IK
        if self.useFingerIk:
            self.fixFingerIk(rig, gen)

        # Improve IK
        if self.useImproveIk:
            from .simple import improveIk
            improveIk(gen)

        #Clean up
        print("  Clean up")
        gen.data.display_type = 'WIRE'
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
        setFkIk2(gen, False, gen.data.layers, False, 0)
        if activateObject(context, rig):
            deleteObjects(context, [rig])
        if self.useDeleteMeta:
            if activateObject(context, meta):
                deleteObjects(context, [meta])
        activateObject(context, gen)
        gen.name = name
        F = False
        T = True
        gen.data.layers = (
            F,T,F,T, F,F,F,T, F,F,T,F, F,T,F,F,
            T,F,F,F, F,F,F,F, F,F,F,F, T,F,F,F)
        print("Rigify created")


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
                trgpb.bone.layers = R_CUSTOM*[False] + [True] + (31-R_CUSTOM)*[False]


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


    def getChildren(self, pb):
        chlist = []
        for child in pb.children:
            chlist.append(child.name)
            chlist += self.getChildren(child)
        return chlist


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
        if self.useSplitShin and "shin" in ldname:
            splitBone()
        elif self.reuseBendTwists or "shin" in ldname:
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
            "lowerjaw" :        ("GZM_MJaw", 1),
            "lowerJaw" :        ("GZM_MJaw", 1),
            "eye.L" :           ("GZM_Circle025", 1),
            "eye.R" :           ("GZM_Circle025", 1),
            "ear.L" :           ("GZM_Circle025", 1.5),
            "ear.R" :           ("GZM_Circle025", 1.5),
            "pectoral.L" :      ("GZM_Pectoral", 1),
            "pectoral.R" :      ("GZM_Pectoral", 1),
            "metatarsals.L" :   ("GZM_Foot", 1),
            "metatarsals.R" :   ("GZM_Foot", 1),
            "gaze" :            ("GZM_Gaze", 1),
            "gaze.L" :          ("GZM_Circle025", 1),
            "gaze.R" :          ("GZM_Circle025", 1),
            "ik_tongue" :       ("GZM_Cone", 0.4),
        }
        self.makeGizmos(True, ["GZM_MJaw", "GZM_Circle025", "GZM_Foot", "GZM_Gaze", "GZM_Pectoral", "GZM_MTongue"])
        bgrp = gen.pose.bone_groups.new(name="DAZ")
        bgrp.color_set = 'CUSTOM'
        bgrp.colors.normal = (1.0, 0.5, 0)
        bgrp.colors.select = (0.596, 0.898, 1.0)
        bgrp.colors.active = (0.769, 1, 1)
        for pb in gen.pose.bones:
            if self.isFaceBone(pb):
                if not self.isEyeLid(pb):
                    self.addGizmo(pb, "GZM_Circle", 0.2)
                pb.bone_group = bgrp
            elif pb.name[0:6] == "tongue":
                self.addGizmo(pb, "GZM_MTongue", 1)
                pb.bone_group = bgrp
            elif (pb.name.startswith(("bigToe", "smallToe")) or
                  pb.name.endswith(("toe1.L", "toe2.L", "toe1.R", "toe2.R"))):
                self.addGizmo(pb, "GZM_Circle", 0.4)
                pb.bone_group = bgrp
            elif pb.name in gizmos.keys():
                gizmo,scale = gizmos[pb.name]
                self.addGizmo(pb, gizmo, scale)
                pb.bone_group = bgrp

        for rname in ["pectoral.L", "pectoral.R"]:
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                pb.bone.layers[4] = True

        # Hide some bones on a hidden layer
        for rname in [
            "upperTeeth", "lowerTeeth",
            ]:
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                pb.bone.layers = 29*[False] + [True] + 2*[False]


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

#-------------------------------------------------------------
#  Buttons
#-------------------------------------------------------------

class DAZ_OT_ConvertToRigify(DazPropsOperator, Rigify, Fixer, GizmoUser, BendTwists, ConstraintStore):
    bl_idname = "daz.convert_to_rigify"
    bl_label = "Convert To Rigify"
    bl_description = "Convert active rig to rigify"
    bl_options = {'UNDO'}

    useDeleteMeta : BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = True
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis"))

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useOptimizePose")
        self.layout.prop(self, "useAutoAlign")
        self.layout.prop(self, "useDeleteMeta")
        if bpy.app.version >= (3,3,0):
            self.layout.prop(self, "useSeparateIkToe")
        Fixer.draw(self, context)
        self.layout.prop(self, "useCustomLayers")
        self.layout.prop(self, "useRecalcRoll")


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
        from time import perf_counter
        from .figure import finalizeArmature
        t1 = perf_counter()
        print("Modifying DAZ rig to Rigify")
        rig = context.object
        rname = rig.name
        if self.useKeepRig:
            self.saveExistingRig(context)
        finalizeArmature(rig)
        self.createMeta(context)
        gen = self.rigifyMeta(context)
        t2 = perf_counter()
        print("DAZ rig %s successfully rigified in %.3f seconds" % (rname, t2-t1))


class DAZ_OT_CreateMeta(DazPropsOperator, Rigify, Fixer, BendTwists, ConstraintStore):
    bl_idname = "daz.create_meta"
    bl_label = "Create Metarig"
    bl_description = "Create a metarig from the active rig"
    bl_options = {'UNDO'}

    useAutoAlign = False
    useDeleteMeta = False

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useOptimizePose")
        Fixer.draw(self, context)
        self.layout.prop(self, "useCustomLayers")
        self.layout.prop(self, "useRecalcRoll")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig.startswith("genesis"))

    def run(self, context):
        if self.useKeepRig:
            self.saveExistingRig(context)
        self.createMeta(context)


class DAZ_OT_RigifyMetaRig(DazPropsOperator, Rigify, Fixer, GizmoUser, BendTwists, ConstraintStore):
    bl_idname = "daz.rigify_meta"
    bl_label = "Rigify Metarig"
    bl_description = "Convert metarig to rigify"
    bl_options = {'UNDO'}

    useKeepRig = False
    useDeleteMeta = False

    def __init__(self):
        Fixer.__init__(self)
        ConstraintStore.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useAutoAlign")
        self.layout.prop(self, "useCustomLayers")

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazMeta)

    def run(self, context):
        self.rigifyMeta(context)

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

    bpy.types.Object.MhaTongueIk = BoolPropOVR(
        name = "Tongue IK",
        description = "Tongue bones controlled by IK",
        default = False)

    bpy.types.Object.DazMeta = BoolProperty(default=False)
    bpy.types.Object.DazRigifyType = StringProperty(default="")
    bpy.types.Object.DazUseSplitNeck = BoolProperty(default=False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
