# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
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
        if BLENDER3:
            table = dict([(lname,layer) for layer,lname in RigifyLayers.items()])
            for key,data in entry["gizmos"].items():
                gizmo,scale,lname = data
                self.gizmos[key] = (gizmo, scale, table[lname])
            self.layer_correct = {}
        else:
            for key,data in entry["gizmos"].items():
                self.gizmos[key] = data
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
        self.owner_orient = entry.get("owner_orient", [])
        self.local_with_parent = entry.get("local_with_parent", [])
        self.twist_bones = entry.get("twist_bones", {})
        self.drv_twist_bones = [drvBone(bname) for bname in self.twist_bones.keys()]

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
    ikOptimization : EnumProperty(
        items = [('POSE', "IK Pose", "Change the Genesis rest pose into the Rigify rest pose. Works with poles, does not work with DAZ poses"),
                 ('POLE', "IK Poles", "Change the location of the IK poles. Works with both poles and DAZ poses"),
                 ('HINT', "IK Hint", "Add a hint angle to IK constraints, works with DAZ poses"),
                 ('NONE', "IK None", "No IK optimization. Works with prebended figures, where the Rigify rest pose is exported from DAZ studio")],
        name = "IK Optimization",
        description = "Method used for optimizing the rest pose before rigifying",
        default = 'POSE')

    useAutoAlign : BoolProperty(
        name = "Auto Align Hand/Foot",
        description = "Auto align hand and foot (Rigify parameter)",
        default = True)

    useRecalcRoll : BoolProperty(
        name = "Recalc Roll",
        description = "Recalculate the roll angles of the thigh and shin bones,\nso they are aligned with the global Z axis.\nFor Genesis 1,2, and 3 characters",
        default = False)

    useSplitShin : BoolProperty(
        name = "Split Shin Vertex Group",
        description = "Split the shin vertex groups into bend and twist parts",
        default = False)

    useCustomLayers : BoolProperty(
        name = "Custom Layers",
        description = "Display layers for face and custom bones.\nNot for Rigify legacy",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "ikOptimization")
        #self.layout.prop(self, "useAutoAlign")
        #self.layout.prop(self, "useRecalcRoll")
        self.layout.prop(self, "useSplitShin")
        if BLENDER3:
            self.layout.prop(self, "useCustomLayers")


    def createMeta(self, context):
        from collections import OrderedDict
        from ..rig_utils import unhideAllObjects, connectToParent
        from ..figure import getRigType, finalizeArmature
        from ..merge_rigs import mergeBones, mergeVertexGroups, applyTransformToObjects
        from ..apply import safeTransformApply
        from ..store import copyConstraints

        print("Create metarig")
        rig = context.object
        wmats = applyTransformToObjects(context, [rig])
        self.setupDazSkeleton(rig)
        scale = GS.scale
        scn = context.scene
        if not(rig and rig.type == 'ARMATURE'):
            raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)
        self.makeRealParents(context, rig)

        if self.ikOptimization == 'POSE' and dazRna(rig).DazRig.startswith("genesis"):
            from ..convert import optimizePose
            optimizePose(context, True)
        if self.keepRig:
            dazrig = self.saveDazRig(context, rig)
        else:
            dazrig = None
        finalizeArmature(context, rig)

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
        meta.show_in_front = True
        meta.display_type = 'WIRE'
        meta["DazRigifyType"] = self.meta.rigify_type
        makeBoneCollections(meta, RigifyLayers)
        cns = meta.constraints.new('COPY_SCALE')
        cns.name = "Rigify Source"
        cns.target = rig
        cns.mute = True

        meta["DazMetaRig"] = True
        meta.DazRig = "metarig"
        meta["DazSplitShin"] = self.useSplitShin
        meta["DazIkOptimization"]= self.ikOptimization
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
        entry = DF.loadEntry("connect", "rigify")
        bnames = entry["limbs"] + entry["spine"] + entry["fingers"]
        connectToParent(rig, bnames)
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

        def setRigifyAttributes(rrna, mrna):
            for attr in dir(rrna):
                if attr.lower().startswith("rigify"):
                    try:
                        setattr(mrna, attr, getattr(rrna, attr))
                    except AttributeError:
                        pass

        print("  Rigify armature data")
        setRigifyAttributes(rig.data, meta.data)
        if not BLENDER3:
            knownlayers = [T_BONES, T_CUSTOM, T_TWEAK, T_WIDGETS, T_HIDDEN]
            for bcoll in rig.data.collections:
                if bcoll.name in knownlayers:
                    continue
                mcoll = meta.data.collections.get(bcoll.name)
                if mcoll is None:
                    mcoll = meta.data.collections.new(bcoll.name)
                setRigifyAttributes(bcoll, mcoll)

        def getParams(attrs):
            return [(key, getattr(attrs, key)) for key in dir(attrs) if key[0] != "_"]

        def setParams(attrs, params):
            for key,value in params:
                try:
                    setattr(attrs, key, value)
                except AttributeError:
                    pass

        print("  Add custom chains")
        chains = {}
        for pb in list(rig.pose.bones):
            if pb.rigify_type:
                if pb.name in meta.data.bones.keys():
                    pb.name = "%s.001" % pb.name
                chains[pb.name] = (pb.rigify_type, getParams(pb.rigify_parameters))
        if chains:
            meta.select_set(True)
            rig.select_set(True)
            cbones = {}
            setMode('EDIT')
            for bname in chains.keys():
                self.addChain(bname, rig, meta, cbones)
            setMode('OBJECT')
            for bname,rdata in chains.items():
                rtype,params = rdata
                pb = meta.pose.bones[bname]
                pb.rigify_type = rtype
                setParams(pb.rigify_parameters, params)
            for bname,pname in cbones.items():
                mbone = meta.data.bones[bname]
                if BLENDER3:
                    setBoneNumLayer(mbone, meta, R_CUSTOM)
                else:
                    colls = getBoneLayers(mbone, rig)
                    layer = (colls[0].name if colls else R_CUSTOM)
                    setBoneNumLayer(mbone, meta, layer)
                    db = rig.pose.bones[bname]
                    pb = meta.pose.bones[bname]
                    copyConstraints(db, pb, meta)

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


    def addChain(self, bname, rig, meta, cbones):
        def getParents(eb, meta):
            par = eb.parent
            if par:
                if par.name in self.daz.rigifybones.keys():
                    return [(eb.name, self.daz.rigifybones[par.name])]
                elif par.name in cbones.keys():
                    return [(eb.name, par.name)]
                else:
                    parents = getParents(par, meta)
                    parents.append((eb.name, par.name))
                    return parents
            else:
                return [(eb.name, None)]

        def getChildren(eb, meta):
            if len(eb.children) == 1:
                child = eb.children[0]
                if child.name in cbones.keys():
                    return []
                else:
                    return [(child.name, eb.name)] + getChildren(child, meta)
            else:
                return []

        def addBones(rig, meta, bnames, cbones):
            for bname,pname in bnames:
                eb = meta.data.edit_bones.new(bname)
                db = rig.data.edit_bones[bname]
                eb.head = db.head
                eb.tail = db.tail
                eb.roll = db.roll
                if pname:
                    eb.parent = meta.data.edit_bones[pname]
                    eb.use_connect = db.use_connect
                cbones[bname] = pname

        root = rig.data.edit_bones[bname]
        parents = getParents(root, meta)
        children = getChildren(root, meta)
        print("    Add Chain:", bname, parents, len(children))
        addBones(rig, meta, parents, cbones)
        addBones(rig, meta, children, cbones)


    def addRigifyProps(self, meta):
        # Add rigify properties to spine bones
        setMode('OBJECT')
        disconnect = []
        connect = []
        for pb in meta.pose.bones:
            if hasattr(pb, "rigify_type"):
                rigify_type = pb.rigify_type
            else:
                rigify_type = pb.get("rigify_type", "")
            if rigify_type != "":
                disconnect.append(pb.name)
            if rigify_type == "":
                pass
            elif rigify_type == "spines.super_head":
                pass
            elif rigify_type in [
                    "limbs.super_finger",
                    "limbs.front_paw",
                    "limbs.rear_paw"]:
                connect += self.getChildren(pb)
                pb.rigify_parameters.primary_rotation_axis = 'X'
                pb.rigify_parameters.make_extra_ik_control = self.useFingerIk
            elif rigify_type == "limbs.super_limb":
                pb.rigify_parameters.rotation_axis = 'x'
                pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
            elif rigify_type == "limbs.leg":
                pb.rigify_parameters.extra_ik_toe = (bpy.app.version >= (3,3,0))
                pb.rigify_parameters.rotation_axis = 'x'
                pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
            elif rigify_type == "limbs.arm":
                pb.rigify_parameters.rotation_axis = 'x'
                pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
            elif rigify_type == "spines.basic_tail":
                connect += self.getChildren(pb)
            elif rigify_type in [
                "basic.raw_copy",
                "spines.super_spine",
                "spines.basic_spine",
                "basic.super_copy",
                "limbs.super_palm",
                "limbs.simple_tentacle"]:
                pass
            else:
                pass
                print("RIGIFYTYPE %s: %s" % (pb.name, rigify_type))
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
    def drawRigify(self):
        self.layout.prop(self, "tongueControl")
        self.layout.prop(self, "shaftControl")
        if self.shaftControl != 'NONE':
            self.layout.prop(self, "shaftName")
        self.layout.prop(self, "addNondeformExtras")


    def setupExtras(self, context, rig, meta):
        def addRecursive(pb):
            if pb.name not in self.extras.keys():
                self.extras[pb.name] = rigifySafe(pb.name)
            for child in pb.children:
                addRecursive(child)

        self.extras = OrderedDict()
        taken = set()
        self.origBones = set()

        for dbone,_,_ in self.daz.spine:
            taken.add(dbone)
        for dbone in self.daz.dazbones.values():
            if isinstance(dbone, list):
                dbone = dbone[0]
                if isinstance(dbone, list):
                    dbone = dbone[0]
            taken.add(dbone)
        for dbone in meta.data.bones.keys():
            if dbone not in taken:
                taken.add(dbone)
                self.origBones.add(dbone)
        if self.addNondeformExtras:
            for bname in rig.data.bones.keys():
                if bname not in taken:
                    self.extras[bname] = rigifySafe(bname)
        else:
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
            print("Missing bone:", bname, rname, pname)
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
        setMode('POSE')
        try:
            bpy.ops.pose.rigify_generate()
        except:
            raise DazError("Cannot rigify %s rig %s    " % (dazRna(rig).DazRig, rig.name))
        setMode('OBJECT')
        scn = context.scene
        gen = context.object
        gen.data["MhaFeatures"] = 0

        coll = getCollection(context, rig)
        unhideAllObjects(context, rig)
        if rig.name not in coll.objects.keys():
            coll.objects.link(rig)
        self.meshes = (getMeshChildren(dazrig) if dazrig else getMeshChildren(rig))

        if not BLENDER3 and "Root" in gen.data.collections.keys():
            # Add rig UI
            makeBoneCollections(gen, RigifyLayers)
            root = gen.data.collections["Root"]
            for bcoll in gen.data.collections:
                if (bcoll.rigify_ui_row == 0 and
                    bcoll.name not in ["DEF", "MCH", "ORG", "Help"]):
                    row = root.rigify_ui_row
                    bcoll.rigify_ui_row = row - 1
                    bcoll.rigify_color_set_id = 3
                    bcoll.rigify_sel_set = False
                    bcoll.rigify_ui_title = bcoll.name
                    root.rigify_ui_row = row+1
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
        self.setupExtras(context, rig, meta)
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

        # Orig DEF bones
        newDefBones = []
        for bname in self.origBones:
            defname = "DEF-%s" % bname
            if defname not in gen.data.edit_bones.keys():
                orgname = "ORG-%s" % bname
                orgbone = gen.data.edit_bones.get(orgname)
                if orgbone:
                    eb = gen.data.edit_bones.new(defname)
                    eb.head = orgbone.head
                    eb.tail = orgbone.tail
                    eb.roll = orgbone.roll
                    eb.parent = orgbone.parent
                    enableBoneNumLayer(eb, gen, R_DEF)
                    newDefBones.append((defname, orgname))

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
        self.tongueBones = self.checkTongueIk(rig)
        self.shaftBones = self.getShaftBones(rig)
        setMode('EDIT')
        if self.tongueControl != 'NONE':
            self.addIkBones("tongue", self.tongueBones, gen, self.tongueControl, R_FACE, R_DEF, R_HELP, ["root"])
        if self.shaftControl != 'NONE':
            self.addIkBones("shaft", self.shaftBones, gen, self.shaftControl, R_CUSTOM, R_DEF, R_HELP, ["root"])

        setMode('OBJECT')

        # Add constraints to new bones
        print("  Add contraints to custom bones")
        from ..rig_utils import copyTransform
        for defname,orgname in newDefBones:
            defbone = gen.pose.bones[defname]
            orgbone = gen.pose.bones[orgname]
            cns = copyTransform(defbone, orgbone, gen)

        # Lock extras
        print("  Lock extras")
        for dname,rname in self.extras.items():
            if dname not in self.dazBones.keys():
                continue
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                db = rig.pose.bones.get(dname)
                self.dazBones[dname].setPose(pb, gen)
                layer,unlock = self.getBoneLayer(pb, db, rig, gen, driven)
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
        if DAZ_PROPS:
            rig.daz_importer.copy(gen.daz_importer)
            rig.data.daz_importer.copy(gen.data.daz_importer)
            setModernProps(gen)
            setModernProps(gen.data)

        # Some more bones
        conv = DF.loadEntry("genesis-%s" % meta.get("DazRigifyType", ""), "converters")
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
        self.fixBoneDrivers(gen, rig, assoc)
        self.renameBendTwistDrivers(gen.data)

        # Locks and limit constraints
        from ..store import copyConstraint
        def addLimits(pb, rname):
            dname = self.daz.dazbones.get(rname)
            if isinstance(dname, str):
                db = rig.pose.bones.get(dname)
                if db:
                    pb.lock_location = db.lock_location
                    pb.lock_rotation = db.lock_rotation
                    pb.lock_scale = db.lock_scale
                    if self.useLimitConstraints:
                        for cns in db.constraints:
                            if cns.type.startswith("LIMIT"):
                                tcns = copyConstraint(cns, pb, gen)

        for pb in gen.pose.bones:
            addLimits(pb, pb.name)
            if pb.name[-5:-1] == "_fk.":
                rname = "%s.%s" % (pb.name[:-5], pb.name[-1])
                addLimits(pb, rname)

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
        if self.tongueControl != 'NONE':
            self.addIkControl("tongue", self.tongueBones, self.tongueControl, "MhaTongueControl", "MhaTongueIk", 0, gen, [R_FACE, R_DETAIL], ["root"])
        if self.shaftControl != 'NONE':
            influs = [1/(n+1)**2 for n in range(len(self.shaftBones))]
            self.addIkControl("shaft", self.shaftBones, self.shaftControl, "MhaShaftControl", "MhaShaftIk", 0, gen, [R_CUSTOM, R_TORSOTWEAK], ["root"], influs)

        # Finger IK
        if meta["DazFingerIk"]:
            self.fixFingerIk(rig, gen)

        if meta["DazIkOptimization"] == 'HINT':
            self.fixPoles(meta, gen, True)
        elif meta["DazIkOptimization"] == 'POLE':
            self.fixPoles(meta, gen, False)

        #Clean up
        print("  Clean up")
        #gen.data.display_type = 'WIRE'
        gen.show_in_front = True
        modernizeBones(gen)
        dazRna(gen).DazRig = meta.get("DazRigifyType", "")
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
            setRigifyFkIk(gen, 0.0, False, 0)
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


    def getBoneLayer(self, pb, db, rig, gen, driven):
        lname = pb.name.lower()
        if pb.name in BD.HeadBones:
            return R_FACE, False
        elif (isDrvBone(pb.name) or
              pb.name in driven.keys() or
              pb.name in BD.FaceRigs):
            return R_HELP, False
        elif pb.name in BD.Teeth:
            return R_CUSTOM, False
        elif isFinal(pb.name) or isInNumLayer(pb.bone, gen, R_HELP):
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

        if db and not BLENDER3:
            knownlayers = [T_BONES, T_CUSTOM, T_TWEAK, T_WIDGETS, T_HIDDEN]
            for bcoll in getBoneLayers(db, rig):
                if bcoll.name not in knownlayers:
                    rcoll = gen.data.collections.get(bcoll.name)
                    if rcoll is None:
                        rcoll = gen.data.collections.new(bcoll.name)
                    return rcoll.name, True

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
        srcpb = rig.pose.bones.get(srcname)
        trgpb = gen.pose.bones.get(trgname)
        if srcpb and trgpb:
            copyBoneInfo(srcpb, trgpb, usePoseBone=False)
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

        def replaceVGroup(dname, nname):
            if dname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[dname]
                vgrp.name = nname

        for dname,rname,pname in self.daz.spine:
            replaceVGroup(dname, "DEF-%s" % rname)
        for rname,dname in self.daz.dazbones.items():
            if str(dname[1:]) in self.daz.limbs.keys():
                self.rigifySplitGroup(rname, dname, ob, rig, True, meta, gen)
            elif isinstance(dname, str):
                replaceVGroup(dname, "DEF-%s" % rname)
            else:
                self.mergeVertexGroups(rname, dname[1], ob)
        for dname,rname in self.extras.items():
            replaceVGroup(dname, rname)
        for dname in self.origBones:
            replaceVGroup(dname, "DEF-%s" % dname)


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
            for mat in ob.data.materials:
                if mat and mat.node_tree and mat.node_tree.animation_data:
                    for fcu in mat.node_tree.animation_data.drivers:
                        self.setId(fcu, rig, newrig)
            for mod in ob.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    mod.object = newrig


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


    def fixPoles(self, meta, gen, useHint):
        from ..rig_utils import addHint
        bnames = [("MCH-shin_ik.L", "thigh_ik_target.L", "MCH-thigh_ik_target.parent.L"),
                  ("MCH-shin_ik.R", "thigh_ik_target.R", "MCH-thigh_ik_target.parent.R"),
                  ("MCH-forearm_ik.L", "upper_arm_ik_target.L", "MCH-upper_arm_ik_target.parent.L"),
                  ("MCH-forearm_ik.R", "upper_arm_ik_target.R", "MCH-upper_arm_ik_target.parent.R")]
        setMode('EDIT')
        for bname,polename,parname in bnames:
            eb = gen.data.edit_bones.get(bname)
            pole = gen.data.edit_bones.get(polename)
            parent = gen.data.edit_bones.get(parname)
            if eb and pole:
                y = pole.length
                pole.head[0] = eb.head[0]
                pole.tail = pole.head + Vector((0, y, 0))
                if parent:
                    parent.head = pole.head
                    parent.tail = pole.tail
        setMode('OBJECT')
        if useHint:
            for bname,polename,parname in bnames:
                pb = gen.pose.bones.get(bname)
                if pb:
                    n = len(pb.constraints)
                    addHint(pb, gen, 'YZX')
                    pb.constraints.move(n, 0)


    def tieBone(self, pb, rig, gen, assoc, facebones, rigtype):
        if pb.name in self.daz.drv_twist_bones:
            return
        if pb.name.endswith(("metatarsal", "hand_anchor")):
            return
        from ..rig_utils import copyLocation, copyRotation, copyTransform, stretchTo
        rname = self.getRigifyBone(pb.name, gen.data.bones)
        if rname is None:
            return
        rb = gen.pose.bones.get(rname)
        if rb is None:
            return
        elif pb.name == "hip":
            cns = copyRotation(pb, rb, gen, space='LOCAL')
            cns.target_space = 'LOCAL_OWNER_ORIENT'
            cns = copyLocation(pb, rb, gen, space='POSE')
            cns.head_tail = 1.0
        elif pb.name == "pelvis":
            pass
        elif pb.name in self.daz.owner_orient:
            cns = copyTransform(pb, rb, gen, space='LOCAL')
            cns.target_space = 'LOCAL_OWNER_ORIENT'
        elif pb.name in facebones:
            cns = copyTransform(pb, rb, gen, space='LOCAL')
        elif pb.name in self.daz.twist_bones.keys():
            twname = self.daz.twist_bones[pb.name]
            twb = gen.pose.bones[twname]
            cns = copyRotation(pb, twb, gen, space='POSE')
        elif "twist" in pb.name.lower():
            cns = copyRotation(pb, rb, gen, space='LOCAL')
        elif (pb.name in self.daz.local_with_parent or
              rname.startswith("DEF-spine")):
            cns = copyTransform(pb, rb, gen, space='LOCAL_WITH_PARENT')
            cns = copyLocation(pb, rb, gen, space='POSE')
        elif pb.name[1:] in ("Shin", "_shin"):
            twname = "DEF-shin.%s.001" % rb.name[-1]
            tb = gen.pose.bones[twname]
            cns = stretchTo(pb, tb, gen)
            cns.head_tail = 1.0
            cns = copyRotation(pb, rb, gen, space='POSE')
        else:
            cns = copyTransform(pb, rb, gen, space='LOCAL')
            cns.target_space = 'LOCAL_OWNER_ORIENT'

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
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
