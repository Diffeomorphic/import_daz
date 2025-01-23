# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from collections import OrderedDict
from mathutils import Vector

from ..error import *
from ..utils import *
from .layers import *
from ..fileutils import DF
from ..fix import Fixer, GizmoUser, BendTwists
from ..bone_data import BD

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def rigifySafe(bname):
    if bname in ["root"]:
        return "_%s" % bname
    else:
        return bname

#-------------------------------------------------------------
#   DazBone
#-------------------------------------------------------------

class DazBone:
    def __init__(self, eb):
        from ..store import ConstraintStore
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


    def __repr__(self):
        return ("<DBONE %s %s>" % (self.name, self.head))


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

class MetaData:
    def __init__(self, entry):
        self.rigify_type = entry["rigify_type"]
        self.hip = entry["hip"]
        self.flip_hip = entry["flip_hip"]
        self.disable_bbones = entry.get("disable_bbones", False)
        self.disconnect = entry["disconnect"]
        self.parents = entry["parents"]
        self.spine = entry["spine"]
        self.rename = entry.get("rename", [])
        self.delete = entry["delete"]
        self.delete_children = entry.get("delete_children", [])
        self.parameters = entry["parameters"]

        default_layers = [R_ROOT, R_TORSO, R_FACE, R_ARMIK_L, R_ARMIK_R, R_LEGIK_L, R_LEGIK_R]
        if BLENDER3:
            self.layers = default_layers
        else:
            self.layers = entry.get("layers", default_layers)

        self.gizmos = {
            "eye.L" :           ["GZM_Circle", 0.25, R_FACE],
            "eye.R" :           ["GZM_Circle", 0.25, R_FACE],
            "l_eye" :           ["GZM_Circle", 0.25, R_FACE],
            "r_eye" :           ["GZM_Circle", 0.25, R_FACE],
            "ear.L" :           ["GZM_Circle", 0.375, R_FACE],
            "ear.R" :           ["GZM_Circle", 0.375, R_FACE],
            "l_ear" :           ["GZM_Circle", 0.375, R_FACE],
            "r_ear" :           ["GZM_Circle", 0.375, R_FACE],
            "gaze" :            ["GZM_Gaze", 1, R_FACE],
            "gaze.L" :          ["GZM_Circle", 0.25, R_FACE],
            "gaze.R" :          ["GZM_Circle", 0.25, R_FACE],
            "ik_tongue" :       ["GZM_Cone", 0.4, R_FACE],
        }
        for key,data in entry["gizmos"].items():
            self.gizmos[key] = data

        if BLENDER3:
            self.layer_correct = {}
        else:
            self.layer_correct = entry.get("layer_correct", {})


class DazData:
    def __init__(self, entry, meta):
        self.dazbones = entry["skeleton"]
        self.adjust = entry.get("adjust", {})
        self.fingers = entry["fingers"]
        self.limbs = entry["limbs"]
        self.parents = entry.get("parents", {})
        self.extra_parents = entry.get("extra_parents", {})
        self.resize = entry.get("resize", {})
        self.split = entry.get("split", {})
        self.cuts = entry.get("cuts", {})
        self.cutbase = entry.get("cutbase", {})
        self.deform = entry.get("deform_bones", {})
        self.tail = entry.get("tail", [])
        self.mergers = entry.get("mergers", {})
        self.reuse = entry.get("reuse", [])
        self.removes = entry.get("removes", [])
        self.renames = entry.get("renames", {})
        self.predelete = entry.get("predelete", [])
        self.custom_shape_fix = entry.get("custom_shape_fix", {})
        self.face_bones = entry.get("face_bones", [])

        self.rigifybones = dict(
            [(dbone, rbone) for rbone, dbone in self.dazbones.items()])

        self.spine = []
        pname = meta.hip
        for rname in meta.spine:
            dname = self.dazbones[rname]
            self.spine.append((dname, rname, pname))
            pname = rname
            self.deform[dname] = "DEF-%s" % rname


class RigifyCommon:
    gizmoFile = "mhx"
    reuseBendTwists = True

    if BLENDER3:
        GroupBones = [
            ("Face ", R_FACE, 2, 6),
            ("Face (detail) ", R_DETAIL, 2, 3),
            ("Custom ", R_CUSTOM, 13, 6)]


    def setupDazSkeleton(self, rig):
        table = {
            "genesis" : "genesis12",
            "genesis1" : "genesis12",
            "genesis2" : "genesis12",
            "genesis3" : "genesis38",
            "genesis8" : "genesis38",
            "genesis9" : "genesis9",
            "daz_dog8" : "daz_dog8",
            "daz_horse3" : "daz_horse3",
            "daz_horse2" : "daz_horse2",
            "daz_big_cat2" : "daz_big_cat2",
        }

        self.daz_rig = table.get(dazRna(rig).DazRig)
        if self.daz_rig:
            entry = DF.loadEntry(self.daz_rig, "rigify")
            print("Setup DAZ skeleton", self.daz_rig)
        else:
            raise DazError("BUG: Rigify for %s not supported" % dazRna(rig).DazRig)
        self.meta_type = entry["meta_type"]
        entry2 = DF.loadEntry(self.meta_type, "rigify")
        self.meta = MetaData(entry2)
        self.daz = DazData(entry, self.meta)


    def setupDazBones(self, rig):
        # Setup info about DAZ bones
        print("Setup DAZ bones")
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
        from ..rig_utils import unhideAllObjects, connectToParent
        from ..figure import getRigType, finalizeArmature
        from ..merge_rigs import mergeBones, mergeVertexGroups
        from ..apply import safeTransformApply

        print("Create metarig")
        rig = context.object
        self.setupDazSkeleton(rig)
        scale = GS.scale
        scn = context.scene
        if not(rig and rig.type == 'ARMATURE'):
            raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)
        self.makeRealParents(context, rig)

        if self.useOptimizePose and dazRna(rig).DazRig.startswith("genesis"):
            from ..convert import optimizePose
            optimizePose(context, True)
        if self.keepRig:
            dazrig = self.saveDazRig(context)
        else:
            dazrig = None
        finalizeArmature(rig)

        unhideAllObjects(context, rig)
        for bname in ["lEye", "rEye", "l_eye", "r_eye"]:
            pb = rig.pose.bones.get(bname)
            if pb:
                self.store.storeConstraints(bname, pb)

        # Create metarig
        setMode('OBJECT')
        adder = getattr(bpy.ops.object, "armature_%s_metarig_add" % self.meta_type)
        try:
            adder()
        except AttributeError:
            raise DazError("The Rigify add-on is not enabled. It is found under rigging.")
        bpy.ops.object.location_clear()
        bpy.ops.object.rotation_clear()
        bpy.ops.object.scale_clear()
        bpy.ops.transform.resize(value=(100*scale, 100*scale, 100*scale))
        safeTransformApply(False)

        print("  Fix metarig")
        meta = context.object
        meta.DazRigifyType = self.meta.rigify_type
        makeBoneCollections(meta, RigifyLayers)
        cns = meta.constraints.new('COPY_SCALE')
        cns.name = "Rigify Source"
        cns.target = rig
        cns.mute = True

        meta["DazMetaRig"] = True
        meta.DazRig = "metarig"
        meta["DazSplitShin"] = self.useSplitShin
        meta["DazFingerIk"] = self.useFingerIk
        meta["DazCustomLayers"] = self.useCustomLayers

        self.adjustMetaBones(meta)

        if activateObject(context, rig):
            safeTransformApply()

        print("  Fix bones", dazRna(rig).DazRig)
        if self.daz_rig == "genesis12":
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            for bname,others in self.daz.split.items():
                self.splitBone(rig, bname, others)
        elif self.daz_rig == "genesis38":
            self.deleteBendTwistDrvBones(rig)
            mergeBones(rig, self.daz.mergers, self.daz.parents, context)
            if dazrig:
                pass
            elif self.reuseBendTwists:
                mergers = dict([(bname,bones)
                                for bname,bones in self.daz.mergers.items()
                                if bname not in self.daz.reuse])
                mergeVertexGroups(rig, mergers)
            else:
                mergeVertexGroups(rig, self.daz.mergers)
            self.renameBones(rig, self.daz.renames, dazrig)
            for pb in rig.pose.bones:
                self.store.restoreBendTwist(pb.name, pb)
        elif self.daz_rig == "genesis9":
            if dazrig:
                pass
            elif self.reuseBendTwists:
                self.removeVertexGroups(rig, self.daz.removes)
            else:
                mergeBones(rig, self.daz.mergers, self.daz.parents, context)
                mergeVertexGroups(rig, self.daz.mergers)
        else:
            for bname,others in self.daz.split.items():
                self.splitBone(rig, bname, others)
            mergeBones(rig, self.daz.mergers, self.daz.parents, context)
            mergeVertexGroups(rig, self.daz.mergers)

        print("  Connect to parent")
        connectToParent(rig, connectAll=True, useSplitShin=self.useSplitShin)
        print("  Setup DAZ bones")
        self.setupDazBones(rig)

        # Fit metarig to default DAZ rig
        print("  Fit to DAZ")
        #setActiveObject(context, meta)
        meta.select_set(True)
        activateObject(context, meta)
        setMode('EDIT')
        hip = self.fitToDaz(meta)

        for dname,factor in self.daz.resize.items():
            rname = self.daz.rigifybones[dname]
            eb = meta.data.edit_bones[rname]
            eb.tail = eb.head + (factor-1)*(eb.tail - eb.head)

        self.fixHands(meta)
        if self.meta_type == "human":
            self.fitLimbs(meta, hip)
        if BLENDER3 and meta["DazCustomLayers"]:
            self.addGroupBones(meta, rig)

        ebones = meta.data.edit_bones
        for eb in ebones:
            if (eb.parent and
                eb.head == eb.parent.tail and
                eb.name not in self.meta.disconnect):
                eb.use_connect = True

        self.fitSpine(ebones)
        print("  Reparent bones")
        self.reparentBones(ebones)
        setMode('OBJECT')

        print("  Add props to rigify")
        connect,disconnect = self.addRigifyProps(meta)
        if BLENDER3 and meta["DazCustomLayers"]:
            self.setupGroupBones(meta)

        print("  Set connected")
        setMode('EDIT')
        self.setConnected(meta, connect, disconnect)
        self.recalcRoll(dazRna(rig).DazRig, meta)
        setMode('OBJECT')
        print("Metarig created")
        return rig, meta, dazrig


    def adjustMetaBones(self, meta):
        setMode('EDIT')
        ebones = meta.data.edit_bones

        # Rename
        for bname,newname in self.meta.rename:
            eb = ebones[bname]
            eb.name = newname

        # Cuts
        for bname,ncuts in self.daz.cuts.items():
            bpy.ops.armature.select_all(action='DESELECT')
            eb = ebones[bname]
            eb.select = True
            bpy.ops.armature.subdivide(number_cuts = ncuts)

        for bname,data in self.daz.cutbase.items():
            prefix,n0 = data
            base = ebones[bname]
            bones = base.children_recursive_basename
            for n,eb in enumerate(bones):
                eb.name = "tmp.%d" % n
            for n,eb in enumerate(bones):
                eb.name = "%s.%03d" % (prefix, n+n0)

        # Delete face bones
        def deleteChildren(eb):
            for child in eb.children:
                deleteChildren(child)
                ebones.remove(child)

        for bname in self.meta.delete_children:
            eb = ebones[bname]
            deleteChildren(eb)
        for bname in self.meta.delete:
            eb = ebones[bname]
            ebones.remove(eb)
        for bname in self.daz.predelete:
            eb = ebones[bname]
            for child in eb.children:
                child.parent = eb.parent
            ebones.remove(eb)
        setMode('OBJECT')


    def splitBone(self, rig, bname, others):
        if others[0] in rig.data.bones.keys():
            return
        setMode('EDIT')
        eb0 = rig.data.edit_bones[bname]
        nbones = len(others)+1
        vec = (eb0.tail - eb0.head)/nbones
        children = list(eb0.children)
        loc = eb0.tail = eb0.head + vec
        par = eb0
        for n,bname in enumerate(others):
            eb = rig.data.edit_bones.new(bname)
            eb.head = loc
            eb.tail = loc + vec
            eb.roll = eb0.roll
            eb.parent = par
            eb.use_connect = True
            par = eb
            loc += vec
        for eb in eb0.children:
            eb.parent = par
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
                elif pb["rigify_type"] in [
                        "limbs.super_finger",
                        "limbs.front_paw",
                        "limbs.rear_paw"]:
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
                elif pb["rigify_type"] == "spines.basic_tail":
                    connect += self.getChildren(pb)
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
        for rname,prop,value in self.meta.parameters:
            if rname in meta.pose.bones:
                pb = meta.pose.bones[rname]
                setattr(pb.rigify_parameters, prop, value)
        return connect, disconnect


    if BLENDER3:
        def addGroupBones(self, meta, rig):
            tail = (0,0,10*GS.scale)
            for bname,layer,row,group in self.GroupBones:
                eb = meta.data.edit_bones.new(bname)
                eb.head = (0,0,0)
                eb.tail = tail
                enableBoneNumLayer(eb, meta, layer)

        def setupGroupBones(self, meta):
            for bname,layer,row,group in self.GroupBones:
                pb = meta.pose.bones[bname]
                pb["rigify_type"] = "basic.pivot"
                enableRigNumLayer(meta, layer)
                rlayer = meta.data.rigify_layers[layer]
                rlayer.name = bname
                rlayer.row = row
                rlayer.group = group
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
        ebones = meta.data.edit_bones
        for eb in ebones:
            eb.use_connect = False

        for eb in ebones:
            dname = self.daz.dazbones.get(eb.name)
            if isinstance(dname, list):
                dname,_vgrps = dname
            if dname in self.dazBones.keys():
                dbone = self.dazBones[dname]
                bnames = self.daz.adjust.get(dname)
                if bnames:
                    dbone1 = self.dazBones[bnames[0]]
                    dbone2 = self.dazBones[bnames[1]]
                    eb.head = dbone1.head
                    eb.tail = dbone2.head
                    eb.roll = dbone.roll
                else:
                    eb.head = dbone.head
                    eb.tail = dbone.tail
                    eb.roll = dbone.roll

        # Flip hip
        hip = ebones[self.meta.hip]
        if self.meta.flip_hip:
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


    def fitSpine(self, ebones):
        for dname,rname,pname in self.daz.spine:
            dbone = self.dazBones[dname]
            if rname in ebones.keys():
                eb = ebones[rname]
            else:
                eb = ebones.new(dname)
                eb.name = rname
            eb.use_connect = False
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.parent = ebones[pname]
            eb.use_connect = True


    def reparentBones(self, ebones):
        for bname,pname in self.meta.parents.items():
            if (pname in ebones.keys() and
                bname in ebones.keys()):
                eb = ebones[bname]
                parb = ebones[pname]
                eb.use_connect = False
                eb.parent = parb

#-------------------------------------------------------------
#   Rigifier
#-------------------------------------------------------------

class Rigifier(RigifyCommon):
    def setupExtras(self, context, rig):
        def addRecursive(pb):
            if pb.name not in self.extras.keys():
                self.extras[pb.name] = rigifySafe(pb.name)
            for child in pb.children:
                addRecursive(child)

        self.extras = OrderedDict()
        taken = []
        for dbone,_,_ in self.daz.spine:
            taken.append(dbone)
        for dbone in self.daz.dazbones.values():
            if isinstance(dbone, list):
                dbone = dbone[0]
                if isinstance(dbone, list):
                    dbone = dbone[0]
            taken.append(dbone)
        for ob in self.meshes:
            for vgrp in ob.vertex_groups:
                if (vgrp.name not in taken and
                    vgrp.name in rig.data.bones.keys()):
                    self.extras[vgrp.name] = rigifySafe(vgrp.name)
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
        if bname in self.daz.deform.keys():
            rname = self.daz.deform[bname]
        elif bname[1:] in self.daz.deform.keys():
            prefix = bname[0]
            rname = self.daz.deform[bname[1:]] % prefix.upper()
        elif bname in self.daz.rigifybones.keys():
            rname = self.daz.rigifybones[bname]
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
        from ..driver import getDrivenBoneFcurves, getPropDrivers, copyProp
        from ..rig_utils import unhideAllObjects

        print("Rigify metarig")
        setMode('OBJECT')
        coll = getCollection(context, rig)
        unhideAllObjects(context, rig)
        if rig.name not in coll.objects.keys():
            coll.objects.link(rig)
        self.meshes = (getMeshChildren(dazrig) if dazrig else getMeshChildren(rig))

        setMode('POSE')
        try:
            bpy.ops.pose.rigify_generate()
        except:
            raise DazError("Cannot rigify %s rig %s    " % (dazRna(rig).DazRig, rig.name))
        setMode('OBJECT')

        scn = context.scene
        gen = context.object
        if not BLENDER3:
            # Add rig UI
            makeBoneCollections(gen, RigifyLayers)
            root = gen.data.collections.get("Root")
            custom = gen.data.collections.get("Custom")
            if root and custom:
                row = root.rigify_ui_row
                custom.rigify_ui_row = row - 1
                custom.rigify_color_set_id = 3
                custom.rigify_sel_set = False
                custom.rigify_ui_title = "Custom"
        if gen.name in scn.collection.objects:
            scn.collection.objects.unlink(gen)
        if gen.name not in coll.objects:
            coll.objects.link(gen)
        self.startGizmos(context, gen)
        print("Fix generated rig", gen.name)

        print("  Setup DAZ Skeleton")
        setActiveObject(context, rig)
        self.setupDazSkeleton(rig)
        self.setupDazBones(rig)
        if self.meta.disable_bbones:
            for bone in gen.data.bones:
                bone.bbone_segments = 1
        if self.meta.layer_correct:
            for bcoll in gen.data.collections:
                name2 = self.meta.layer_correct.get(bcoll.name)
                if name2:
                    bcoll2 = gen.data.collections[name2]
                    for bone in list(bcoll.bones):
                        bcoll.unassign(bone)
                        bcoll2.assign(bone)

        print("  Setup extras")
        self.setupExtras(context, rig)
        print("  Get driven bones")
        driven = getDrivenBoneFcurves(rig)

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
                enableBoneNumLayer(eb, gen, R_DETAIL)
                setBoneNumLayer(eb, gen, R_DEF)
            else:
                enableBoneNumLayer(eb, gen, R_HELP)
            if dname in driven.keys():
                enableBoneNumLayer(eb, gen, R_HELP)

        # Group bones
        if BLENDER3 and meta["DazCustomLayers"]:
            print("  Create group bones")
            for data in self.GroupBones:
                eb = gen.data.edit_bones[data[0]]
                enableBoneNumLayer(eb, gen, R_HELP)

        # Add parents to extra bones
        print("  Add parents to extra bones")
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            dbone = self.dazBones[dname]
            eb = gen.data.edit_bones[rname]
            if dbone.parent:
                parname = self.daz.extra_parents.get(dbone.name)
                if parname not in gen.data.edit_bones.keys():
                    parname = self.getRigifyBone(dbone.parent, gen.data.edit_bones)
                if parname:
                    eb.parent = gen.data.edit_bones[parname]
                    eb.use_connect = (eb.parent != None and eb.parent.tail == eb.head)
                else:
                    print("No parent", dbone.name, dbone.parent)
                    if isDrvBone(dbone.name):
                        continue
                    bones = list(self.daz.rigifybones.keys())
                    bones.sort()
                    print("Bones:", bones)
                    msg = ("Bone %s has no parent %s" % (dbone.name, dbone.parent))
                    raise DazError(msg)

        # Gaze bones
        print("  Create gaze bones")
        for suffix in ["L", "R"]:
            self.addSingleGazeBone(gen, suffix, R_FACE, R_HELP)
        self.addCombinedGazeBone(gen, R_FACE, R_HELP)
        self.checkTongueIk(rig)
        if self.useTongueIk:
            setMode('EDIT')
            self.addTongueIkBones(gen, R_FACE, R_DEF)

        setMode('OBJECT')

        # Lock extras
        print("  Lock extras")
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                self.dazBones[dname].setPose(pb, gen)
                layer,unlock = self.getBoneLayer(pb, gen, driven)
                enableBoneNumLayer(pb.bone, gen, layer)
                if unlock:
                    pb.lock_location = FFalse
                self.copyBoneInfo(dname, rname, rig, gen)

        # Rescale custom shapes
        for bname,tfm in self.daz.custom_shape_fix.items():
            scale,offset = tfm
            if offset:
                offset = Vector(offset)*GS.scale
            self.fixCustomShape(gen, bname, scale, offset)

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

        # Change vertex groups
        activateObject(context, gen)
        self.bendTwistNames = {}
        print("  Change vertex groups")
        for ob in self.meshes:
            if dazrig:
                self.changeAllTargets(ob, rig, dazrig)
            else:
                self.changeVertexGroups(ob, rig, meta, gen)
                self.changeAllTargets(ob, rig, gen)

        # Fix drivers
        print("  Fix drivers")
        assoc = {}
        for bname in rig.data.bones.keys():
            if isDrvBone(bname) or isFinal(bname):
                continue
            assoc[bname] = bname
        for rname,dname in self.daz.dazbones.items():
            if isinstance(dname, list):
                dname = dname[0]
            orgname = self.getOrgDefBone(rname, gen)
            assoc[dname] = orgname
        for dname,rname,pname in self.daz.spine:
            assoc[dname] = self.getOrgDefBone(rname, gen)

        for fcu in getPropDrivers(rig):
            self.copyDriver(fcu, gen, old=rig, new=gen)
        for fcu in getPropDrivers(rig.data):
            self.copyDriver(fcu, gen.data, old=rig, new=gen)
        for bname, fcus in driven.items():
            if bname in gen.pose.bones.keys():
                pb = gen.pose.bones[bname]
                for fcu in fcus:
                    self.copyBoneProp(fcu, rig, gen, pb)
                for fcu in fcus:
                    self.copyDriver(fcu, gen, old=rig, new=gen, assoc=assoc)

        # Fix bend and twist drivers
        print("  Fix bend and twist drivers")
        for dname0,rname0 in self.daz.limbs.items():
            for prefix,suffix in [("l","L"), ("r","R")]:
                dname = "%s%s" % (prefix, dname0)
                rname = "%s.%s" % (rname0, suffix)
                bname = self.getOrgDefBone(rname, gen)
                assoc[dname] = bname
                assoc["%sBend" % dname] = bname
                self.fixIkBone(dname, rig, (rname0, suffix), gen)
        self.fixBoneDrivers(gen, rig, assoc)
        self.renameBendTwistDrivers(gen.data)

        # Limit constraints
        if self.useLimitConstraints:
            from ..store import copyConstraint
            def addLimits(pb, rname):
                dname = self.daz.dazbones.get(rname)
                if isinstance(dname, str):
                    db = rig.pose.bones.get(dname)
                    if db:
                        for cns in db.constraints:
                            if cns.type.startswith("LIMIT"):
                                copyConstraint(cns, pb, gen)

            for pb in gen.pose.bones:
                addLimits(pb, pb.name)
                if pb.name[-5:-1] == "_fk.":
                    rname = "%s.%s" % (pb.name[:-5], pb.name[-1])
                    addLimits(pb, rname)

        # Unlock bend locks
        for rname in ["upper_arm", "forearm", "thigh"]:
            for suffix in ["L", "R"]:
                bname = "%s_fk.%s" % (rname, suffix)
                pb = gen.pose.bones.get(bname)
                if pb is None:
                    bname = "%s.fk.%s" % (rname, suffix)
                    pb = gen.pose.bones.get(bname)
                if pb:
                    pb.lock_rotation = FFalse

        # Face bone and gizmos
        if dazRna(rig).DazRig == "genesis9":
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
        if self.useTongueIk:
            self.addTongueControl(gen, [R_FACE, R_DETAIL])

        # Finger IK
        if meta["DazFingerIk"]:
            self.fixFingerIk(rig, gen)

        # Improve IK
        if self.useImproveIk:
            from ..rig_utils import improveIk
            improveIk(gen, exclude=self.tongueBones)

        if self.driverRotationMode:
            from ..fix import setDriverModes
            setDriverModes(gen, self.driverRotationMode, True)

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
        if BLENDER3:
            from .rigify_snap import setRigifyFkIk, setRigifyLayers, clearOtherRigify
            setRigifyFkIk(gen, 1.0, False, 0)
            setRigifyLayers(rig, True, gen.data.layers)
            clearOtherRigify(gen, False, 0)
        if activateObject(context, rig):
            deleteObjects(context, [rig])
        if self.useDeleteMeta:
            if activateObject(context, meta):
                deleteObjects(context, [meta])
        activateObject(context, gen)
        enableRigNumLayers(gen, self.meta.layers)
        gen.name = name
        if dazrig:
            self.tieBones(context, dazrig, gen)
            self.setRigName(gen, dazrig, "RIGIFY")
        print("Rigify created")
        return gen


    def getBoneLayer(self, pb, rig, driven):
        lname = pb.name.lower()
        if pb.name in BD.HeadBones:
            return R_FACE, False
        elif (isDrvBone(pb.name) or
              pb.name in driven.keys() or
              pb.name in BD.FaceRigs):
            return R_HELP, False
        elif pb.name in BD.Teeth:
            return R_CUSTOM, False
        elif isFinal(pb.name) or isInNumLayer(pb.bone, rig, R_HELP):
            return R_HELP, False
        elif lname.startswith("tongue"):
            return R_DETAIL, False
        elif pb.parent:
            par = pb.parent
            if par.name in BD.FaceRigs:
                return R_DETAIL, True
            elif (isDrvBone(par.name) and
                  par.parent and
                  par.parent.name in BD.FaceRigs):
                return R_DETAIL, True
        return R_CUSTOM, True


    def copyBoneProp(self, fcu, rig, gen, pb):
        from ..driver import copyProp
        bname = prop = None
        words = fcu.data_path.split('"')
        if words[0] == "pose.bones[" and words[2] == "][":
            bname = words[1]
            prop = words[3]
            if bname in rig.pose.bones.keys():
                copyProp(prop, rig.pose.bones[bname], pb, False)


    def copyBoneInfo(self, srcname, trgname, rig, gen):
        from ..figure import copyBoneInfo
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
                enableBoneNumLayer(trgpb.bone, gen, R_CUSTOM)


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


    def changeVertexGroups(self, ob, rig, meta, gen):
        if ob.parent == gen and ob.parent_type == 'BONE':
            return
        ob.parent = gen
        for dname,rname,pname in self.daz.spine:
            if dname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[dname]
                vgrp.name = "DEF-%s" % rname

        for rname,dname in self.daz.dazbones.items():
            if str(dname[1:]) in self.daz.limbs.keys():
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


    def changeAllTargets(self, ob, rig, newrig):
        if ob.animation_data:
            for fcu in ob.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.data.animation_data:
            for fcu in ob.data.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.type == 'MESH':
            if ob.data.shape_keys and ob.data.shape_keys.animation_data:
                for fcu in ob.data.shape_keys.animation_data.drivers:
                    self.setId(fcu, rig, newrig)
            for mod in ob.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    mod.object = newrig


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
        self.makeGizmos(True, ["GZM_MJaw", "GZM_Foot", "GZM_Gaze", "GZM_Pectoral", "GZM_MTongue", "GZM_Knuckle"])
        color = (1.0, 0.5, 0)
        if BLENDER3:
            bgrp = gen.pose.bone_groups.new(name="DAZ")
            bgrp.color_set = 'CUSTOM'
            bgrp.colors.normal = color
            bgrp.colors.select = (0.596, 0.898, 1.0)
            bgrp.colors.active = (0.769, 1, 1)
        for pb in gen.pose.bones:
            lname = pb.name.lower()
            if pb.name in self.meta.gizmos.keys():
                gizmo,scale,layer = self.meta.gizmos[pb.name]
                if gizmo:
                    self.addGizmo(pb, gizmo, scale)
                setBonegroup(pb, gen, "DAZ", color)
                enableBoneNumLayer(pb.bone, gen, layer)
            elif self.isFaceBone(pb, gen):
                if not self.isEyeLid(pb):
                    self.addGizmo(pb, "GZM_Circle", 0.2)
                setBonegroup(pb, gen, "DAZ", color)
            elif pb.name in self.daz.face_bones:
                self.addGizmo(pb, "GZM_Circle", 0.2)
                setBonegroup(pb, gen, "DAZ", color)
                enableBoneNumLayer(pb.bone, gen, R_FACE)
            elif lname.startswith("tongue"):
                self.addGizmo(pb, "GZM_MTongue", 1)
                setBonegroup(pb, gen, "DAZ", color)
            elif (pb.name.startswith(("bigToe", "smallToe")) or
                  pb.name.endswith(("toe1.L", "toe2.L", "toe1.R", "toe2.R"))):
                self.addGizmo(pb, "GZM_Circle", 0.4)
                setBonegroup(pb, gen, "DAZ", color)

        # Hide some bones on a hidden layer
        for rname in [
            "upperTeeth", "lowerTeeth",
            ]:
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                enableBoneNumLayer(pb.bone, gen, R_DEF)


    def fixFingerIk(self, rig, gen):
        for suffix in ["L", "R"]:
            for dfing,rfing in self.daz.fingers:
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
        from ..rig_utils import copyLocation, copyRotation, copyTransform
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
                cns = copyRotation(pb, rb, gen, space='LOCAL')
                cns.invert_x = False
                cns.invert_y = True
                cns.invert_z = True
            cns = copyLocation(pb, rb, gen, space='POSE')
            cns.head_tail = 1.0
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

class DAZ_OT_ConvertToRigify(DazPropsOperator, MetaMaker, Rigifier, Fixer, GizmoUser, BendTwists):
    bl_idname = "daz.convert_to_rigify"
    bl_label = "Convert To Rigify"
    bl_description = "Convert active rig to rigify"
    bl_options = {'UNDO', 'PRESET'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and
                ob.type == 'ARMATURE' and
                dazRna(ob).DazRig.startswith(("genesis", "daz_dog", "daz_big_cat", "daz_horse")) and
                not ob.get("DazSimpleIK"))

    useDeleteMeta : BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = True
    )

    def draw(self, context):
        MetaMaker.draw(self, context)
        self.layout.prop(self, "useDeleteMeta")
        if bpy.app.version >= (3,3,0):
            self.layout.prop(self, "useSeparateIkToe")
        self.drawMeta()
        self.drawRigify()


    def storeState(self, context):
        from ..driver import muteDazFcurves
        DazPropsOperator.storeState(self, context)
        rig = context.object
        self.dazDriversDisabled = dazRna(rig).DazDriversDisabled
        muteDazFcurves(rig, True)


    def restoreState(self, context):
        from ..driver import muteDazFcurves
        DazPropsOperator.restoreState(self, context)
        gen = context.object
        muteDazFcurves(gen, self.dazDriversDisabled)


    def run(self, context):
        self.initFixer()
        t1 = perf_counter()
        print("Modifying DAZ rig to Rigify")
        rig,meta,dazrig = self.createMeta(context)
        self.rigname = rig.name
        gen = self.rigifyMeta(context, rig, meta, dazrig)
        t2 = perf_counter()
        print("DAZ rig %s successfully rigified in %.3f seconds" % (self.rigname, t2-t1))
        self.printMessages()


class DAZ_OT_CreateMeta(DazPropsOperator, MetaMaker, Fixer, BendTwists):
    bl_idname = "daz.create_meta"
    bl_label = "Create Metarig"
    bl_description = "Create a metarig from the active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and
                ob.type == 'ARMATURE' and
                dazRna(ob).DazRig.startswith(("genesis", "daz_dog", "daz_big_cat", "daz_horse")) and
                not ob.get("DazSimpleIK"))

    def draw(self, context):
        MetaMaker.draw(self, context)
        self.drawMeta()

    def run(self, context):
        self.initFixer()
        rig,meta,dazrig = self.createMeta(context)
        meta.data["DazOrigRig"] = rig.name
        if dazrig:
            meta.data["DazKeptRig"] = dazrig.name
        self.printMessages()


class DAZ_OT_RigifyMetaRig(DazPropsOperator, Rigifier, Fixer, GizmoUser, BendTwists):
    bl_idname = "daz.rigify_meta"
    bl_label = "Rigify Metarig"
    bl_description = "Convert metarig to rigify"
    bl_options = {'UNDO'}

    useDeleteMeta = False

    def draw(self, context):
        self.drawRigify()

    @classmethod
    def poll(self, context):
        rig = context.object
        return (rig and rig.get("DazMetaRig"))

    def run(self, context):
        self.initFixer()
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

    bpy.types.Object.MhaGazeFollowsHead = bpy.props.FloatProperty(
        name = "Gaze Follows Head",
        min = 0, max = 1,
        default = 0.0,
        description = "The gaze bone follows the head bone rotations",
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.MhaGaze_L = bpy.props.FloatProperty(
        name = "Gaze Left",
        min = 0, max = 1,
        default = 0.0,
        description = "eye tracking the left gaze bone amount",
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.MhaGaze_R = bpy.props.FloatProperty(
        name = "Gaze Right",
        min = 0, max = 1,
        default = 0.0,
        description = "eye tracking the right gaze bone amount",
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.MhaTongueIk = bpy.props.FloatProperty(
        name = "Tongue IK",
        min = 0, max = 1,
        default = 0.0,
        description = "Tongue bones controlled by IK",
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazRigifyType = StringProperty(default="")

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
