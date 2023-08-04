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
import os
from mathutils import *
from .error import *
from .utils import *
from .layers import *
from .driver import DriverUser, addDriver

#-------------------------------------------------------------
#   Fixer class
#-------------------------------------------------------------

class Fixer(DriverUser):

    useImproveIk : BoolProperty(
        name = "Improve IK",
        description = "Improve IK by prebending IK bones",
        default = True)

    useFingerIk : BoolProperty(
        name = "Finger IK",
        description = "Generate IK controls for fingers",
        default = False)

    useTongueIk : BoolProperty(
        name = "Tongue IK",
        description = "Generate IK controls for tongue",
        default = False)

    reuseBendTwists : BoolProperty(
        name = "Reuse Bend And Twist Bones",
        description = "Use the original bend-twist bones and vertex groups",
        default = True)

    useKeepRig : BoolProperty(
        name = "Keep DAZ Rig",
        description = "Keep the original DAZ rig for deformation",
        default = False)

    def draw(self, context):
        self.drawMeta()
        self.drawRigify()

    def drawMeta(self):
        self.layout.prop(self, "useKeepRig")
        self.layout.prop(self, "reuseBendTwists")
        self.layout.prop(self, "useFingerIk")

    def drawRigify(self):
        self.layout.prop(self, "useTongueIk")
        self.layout.prop(self, "useImproveIk")


    def __init__(self):
        DriverUser.__init__(self)
        self.messages = []
        self.renamedBones = {}


    def makeRealParents(self, context, rig):
        for ob in getVisibleMeshes(context):
            mod = getModifier(ob, 'ARMATURE')
            if mod and mod.object == rig:
                ob.parent = rig


    def printMessages(self):
        if self.messages:
            msg = "\n".join(self.messages)
            raise DazError(msg, warning=True)


    def copyLocksLimits(self, rig, srcname, trgname, suffix):
        src = rig.pose.bones["%s.%s" % (srcname, suffix)]
        trg = rig.pose.bones["%s.%s" % (trgname, suffix)]
        trg.lock_location = src.lock_location
        trg.lock_rotation = src.lock_rotation
        trg.lock_scale = src.lock_scale
        cns = getConstraint(src, 'LIMIT_ROTATION')
        if cns:
            copyConstraint(cns, trg, rig)


    def fixPelvis(self, rig):
        setMode('EDIT')
        hip = rig.data.edit_bones["hip"]
        if hip.tail[2] > hip.head[2]:
            for child in hip.children:
                child.use_connect = False
            head = Vector(hip.head)
            tail = Vector(hip.tail)
            hip.head = Vector((1,2,3))
            hip.tail = head
            hip.head = tail
        if "pelvis" not in rig.data.bones.keys():
            pelvis = rig.data.edit_bones.new("pelvis")
            pelvis.head = hip.head
            pelvis.tail = hip.tail
            pelvis.roll = hip.roll
            pelvis.parent = hip
            lThigh = rig.data.edit_bones["lThigh"]
            rThigh = rig.data.edit_bones["rThigh"]
            lThigh.parent = pelvis
            rThigh.parent = pelvis
        setMode('OBJECT')


    def fixCustomShape(self, rig, bnames, factor, offset=0):
        from .simple import setCustomShape
        for bname in bnames:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                if pb.custom_shape:
                    setCustomShape(pb, pb.custom_shape, factor)
                    if offset:
                        for v in pb.custom_shape.data.vertices:
                            v.co += offset
                return


    def fixHands(self, rig):
        setMode('EDIT')
        for suffix in ["L", "R"]:
            forearm = rig.data.edit_bones["forearm.%s" % suffix]
            hand = rig.data.edit_bones["hand.%s" % suffix]
            hand.head = forearm.tail
            flen = (forearm.tail - forearm.head).length
            vec = hand.tail - hand.head
            hand.tail = hand.head + 0.35*flen/vec.length*vec


    def fixCarpals(self, rig):
        Carpals = {
            "Carpal1" : "Index1",
            "Carpal2" : "Mid1",
            "Carpal3" : "Ring1",
            "Carpal4" : "Pinky1",
        }

        if "lCarpal3" in rig.data.bones.keys():
            return
        setMode('EDIT')
        for prefix in ["l", "r"]:
            for bname in ["Carpal1", "Carpal2"]:
                if prefix+bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[prefix+bname]
                    rig.data.edit_bones.remove(eb)
            hand = rig.data.edit_bones[prefix+"Hand"]
            hand.tail = 2*hand.tail - hand.head
            for bname,cname in Carpals.items():
                if prefix+cname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones.new(prefix+bname)
                    child = rig.data.edit_bones[prefix+cname]
                    eb.head = hand.head
                    eb.tail = child.head
                    eb.roll = child.roll
                    eb.parent = hand
                    child.parent = eb
                    child.use_connect = True
        setMode('OBJECT')
        for ob in getMeshChildren(rig):
            for prefix in ["l", "r"]:
                for vgrp in ob.vertex_groups:
                    if vgrp.name == prefix+"Carpal2":
                        vgrp.name = prefix+"Carpal4"


    def removeVertexGroups(self, rig, grpnames):
        for ob in getMeshChildren(rig):
            for gname in grpnames:
                vgrp = ob.vertex_groups.get(gname)
                if vgrp:
                    ob.vertex_groups.remove(vgrp)


    def fixBoneDrivers(self, rig, assoc0):
        def changeTargets(rna, rig):
            if rna.animation_data:
                drivers = list(rna.animation_data.drivers)
                print("    (%s %d)" % (rna.name, len(drivers)))
                for n,fcu in enumerate(drivers):
                    self.changeTarget(fcu, rna, rig, assoc)

        def getFinOffsDrivers(amt):
            findrivers = {}
            offsdrivers = []
            if amt.animation_data:
                for fcu in amt.animation_data.drivers:
                    prop = fcu.data_path[2:-2]
                    if isFinal(prop) or isRest(prop):
                        raw = baseProp(prop)
                        findrivers[raw] = fcu
                    elif ":Hdo:" in prop or ":Tlo:" in prop:
                        offsdrivers.append(fcu)
            return findrivers, offsdrivers

        assoc = dict([(bname,bname) for bname in rig.data.bones.keys()])
        for dname,bname in assoc0.items():
            assoc[dname] = bname
        findrivers,offsdrivers = getFinOffsDrivers(rig.data)
        print("    (%s %d)" % (rig.data.name, len(findrivers)))
        for fcu in findrivers.values():
            self.changeTarget(fcu, rig.data, rig, assoc)
        for fcu in offsdrivers:
            rig.data.animation_data.drivers.remove(fcu)
        for ob in rig.children:
            changeTargets(ob, rig)
            if ob.type == 'MESH' and ob.data.shape_keys:
                changeTargets(ob.data.shape_keys, rig)


    def changeTarget(self, fcu, rna, rig, assoc):
        channel = fcu.data_path
        idx = self.getArrayIndex(fcu)
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        success = True
        for var in fcu2.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT':
                    trg.id = rig
                elif trg.id_type == 'ARMATURE':
                    trg.id = rig.data
                if var.type == 'TRANSFORMS':
                    bname = trg.bone_target
                    defbone = "DEF-" + bname
                    if bname in assoc.keys():
                        trg.bone_target = assoc[bname]
                    elif defbone in rig.pose.bones.keys():
                        trg.bone_target = defbone
                    else:
                        success = False
        if success:
            fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
            fcu3.data_path = channel
            if idx >= 0:
                fcu3.array_index = idx
        self.clearTmpDriver(0)


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


    def saveDazRig(self, context):
        def dazName(string):
            return "%s_DAZ" % string

        def findChildrenRecursive(ob, objects):
            objects.append(ob)
            for child in ob.children:
                if not getHideViewport(child):
                    findChildrenRecursive(child, objects)

        def enableDrivers(rna):
            if rna.animation_data:
                for fcu in rna.animation_data.drivers:
                    fcu.mute = False

        rig = context.object
        scn = context.scene
        coll = getCollection(context, rig)
        activateObject(context, rig)
        bpy.ops.object.duplicate()

        newObjects = getSelectedObjects(context)
        nrig = None
        for ob in newObjects:
            enableDrivers(ob)
            enableDrivers(ob.data)
            ob.name = dazName(baseName(ob.name))
            if ob.data:
                ob.data.name = dazName(baseName(ob.data.name))
            if ob.type == 'ARMATURE' and ob != rig:
                nrig = ob
            unlinkAll(ob, False)
            coll.objects.link(ob)

        for ob in rig.children:
            wmat = ob.matrix_world.copy()
            ob.parent = nrig
            setWorldMatrix(ob, wmat)
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                mod.object = nrig
            skeys = ob.data.shape_keys
            if skeys:
                enableDrivers(skeys)
                for skey in skeys.key_blocks:
                    skey.mute = False

        activateObject(context, rig)
        return nrig


    def setRigName(self, rig, nrig, suffix):
        mhx = "%s_%s" % (self.rigname, suffix)
        rig.name = mhx
        rig.data.name = mhx
        nrig.name = self.rigname
        nrig.data.name = self.rigname

    #-------------------------------------------------------------
    #   Face Bone
    #-------------------------------------------------------------

    def setupFaceBones(self, rig):
        def addFaceBones(pb):
            for child in pb.children:
                facebones.append(child.name)
                addFaceBones(child)

        facebones = []
        head = rig.pose.bones.get("head")
        if head:
            addFaceBones(head)
        return facebones


    def isFaceBone(self, pb, rig):
        if pb.parent:
            par = pb.parent
            faces = ["head", "upperfacerig", "lowerfacerig"]
            if par.name.lower() in faces:
                return True
            elif (isDrvBone(par.name) and
                  par.parent and
                  par.parent.name.lower() in faces):
                return True
        return False


    def isEyeLid(self, pb):
        return ("eyelid" in pb.name.lower())

    #-------------------------------------------------------------
    #   Tongue IK
    #-------------------------------------------------------------

    def checkTongueIk(self, rig):
        if not self.useTongueIk:
            self.tongueBones = []
            return
        self.tongueBones = [bone.name for bone in rig.data.bones if ("tongue" in bone.name and not isDrvBone(bone.name))]
        if len(self.tongueBones) < 3:
            print("Did not find tongue")
            self.useTongueIk = False
            return
        print("Tongue bones:", self.tongueBones)
        self.tongueBones.sort()
        if self.checkDriven(rig, self.tongueBones, "Tongue IK"):
            self.useTongueIk = False


    def checkDriven(self, rig, bnames, string):
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (words[0] == "pose.bones[" and
                    words[1] in bnames):
                    self.messages.append("%s is disabled because\n%s has drivers" % (string, words[1]))
                    return True
        return False


    def addTongueIkBone(self, rig, layer, deflayer):
        if not self.useTongueIk:
            return
        from .mhx import makeBone
        root = rig.data.edit_bones[self.tongueBones[0]]
        for bname in self.tongueBones:
            eb = rig.data.edit_bones[bname]
            eb.use_connect = False
            trgb = makeBone("ik_%s" % bname, rig, eb.tail, 2*eb.tail-eb.head, eb.roll, layer, root.parent)


    def addTongueIk(self, rig):
        from .mhx import ikConstraint, stretchTo, setMhx, mhxProp
        prop = "MhaTongueIk"
        setMhx(rig, prop, 0)
        if not self.useTongueIk:
            return
        rig.data.MhaFeatures |= F_TONGUE
        for bname in self.tongueBones:
            pb = rig.pose.bones[bname]
            pb.lock_location = (True, True, True)
            for cns in list(pb.constraints):
                if cns.type == 'LIMIT_ROTATION':
                    self.setIkLimits(cns, pb, pb)
                    addDriver(cns, "influence", rig, mhxProp(prop), "1-x")
            trgb = rig.pose.bones["ik_%s" % bname]
            trgb.bone.use_deform = False
            self.addGizmo(trgb, "GZM_Ball", 0.2)
            addDriver(trgb.bone, "hide", rig, mhxProp(prop), "x==0")
            cns = stretchTo(pb, trgb, rig, prop)


    def setIkLimits(self, cns, fkbone, ikbone):
        for n,x in enumerate(["x", "y", "z"]):
            setattr(ikbone, "use_ik_limit_%s" % x, getattr(cns, "use_limit_%s" % x))
            setattr(ikbone, "ik_min_%s" % x, getattr(cns, "min_%s" % x))
            setattr(ikbone, "ik_max_%s" % x, getattr(cns, "max_%s" % x))
            setattr(ikbone, "lock_ik_%s" % x, fkbone.lock_rotation[n])
            #if fkbone.lock_rotation[n]:
            #    setattr(ikbone, "ik_stiffness_%s" % x, 0.99)

    #-------------------------------------------------------------
    #   Gaze Bones
    #-------------------------------------------------------------

    def addSingleGazeBone(self, rig, suffix, headLayer, helpLayer):
        from .mhx import makeBone, deriveBone
        prefix = suffix.lower()
        bnames = ["%sEye" % prefix, "%s_eye" % prefix, "eye.%s" % suffix]
        for bname in bnames:
            eye = rig.data.edit_bones.get(bname)
            if eye:
                break
        if eye is None:
            print("Did not find eye", bnames)
            return
        drvname = drvBone("eye.%s" % suffix)
        if drvname not in rig.data.edit_bones.keys():
            eyegaze = deriveBone(drvname, eye, rig, helpLayer, eye.parent)
            #eye.parent = eyegaze
        vec = eye.tail-eye.head
        vec.normalize()
        loc = eye.head + vec*rig.DazScale*30
        gaze = makeBone("gaze.%s" % suffix, rig, loc, loc+Vector((0,5*rig.DazScale,0)), 0, headLayer, None)


    def addCombinedGazeBone(self, rig, headLayer, helpLayer):
        from .mhx import makeBone, deriveBone
        lgaze = rig.data.edit_bones.get("gaze.L")
        rgaze = rig.data.edit_bones.get("gaze.R")
        head = rig.data.edit_bones.get("head")
        if lgaze and rgaze and head:
            loc = (lgaze.head + rgaze.head)/2
            gaze0 = makeBone("gaze0", rig, loc, loc+Vector((0,15*rig.DazScale,0)), 0, helpLayer, head)
            gaze1 = deriveBone("gaze1", gaze0, rig, helpLayer, None)
            gaze = deriveBone("gaze", gaze0, rig, headLayer, gaze1)
            lgaze.parent = gaze
            rgaze.parent = gaze


    def addGazeConstraint(self, rig, suffix):
        def constraintExists(pb, drv):
            if pb.name in self.constraints.keys():
                for struct in self.constraints[pb.name]:
                    if (struct["type"] == 'COPY_ROTATION' and
                        struct["subtarget"] == drv.name):
                        return True
            return False

        from .mhx import dampedTrack, copyRotation, setMhx
        eye = rig.pose.bones.get("eye.%s" % suffix)
        eyedrv = rig.pose.bones.get(drvBone("eye.%s" % suffix))
        gaze = rig.pose.bones.get("gaze.%s" % suffix)
        if not (eye and eyedrv and gaze):
            print("Cannot add gaze constraint")
            return
        prop = "MhaGaze_%s" % suffix
        setMhx(rig, prop, 1.0)
        if not constraintExists(eye, eyedrv):
            cns = copyRotation(eye, eyedrv, rig)
            cns.mix_mode = 'ADD'
        dampedTrack(eyedrv, gaze, rig, prop)


    def addGazeFollowsHead(self, rig):
        from .mhx import copyTransform, setMhx, mhxProp
        gaze0 = rig.pose.bones.get("gaze0")
        gaze1 = rig.pose.bones.get("gaze1")
        if gaze0 and gaze1:
            prop = "MhaGazeFollowsHead"
            setMhx(rig, prop, 1.0)
            copyTransform(gaze1, gaze0, rig, prop)

    #-------------------------------------------------------------
    #   Toe rotation
    #-------------------------------------------------------------

    def copyToeRotation(self, rig, mute, suffix, toenames):
        from .mhx import copyRotation
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
    #   Tie bones
    #-------------------------------------------------------------

    def getTweakBoneName(self, bname):
        return "NONE"


    def tieBones(self, rig, gen):
        def hasCopyConstraint(pb):
            for cns in list(pb.constraints):
                if cns.type.startswith("COPY"):
                    return True
            return False

        print("Tie bones of %s to %s" % (rig.name, gen.name))
        facebones = self.setupFaceBones(rig)
        assoc = dict([(bname,rname) for rname,bname in self.renamedBones.items()])
        for pb in rig.pose.bones:
            for cns in list(pb.constraints):
                pb.constraints.remove(cns)
            self.tieBone(pb, gen, assoc, facebones, rig.DazRig)
        cns = rig.constraints.new('COPY_TRANSFORMS')
        cns.name = "Copy Transform %s" % gen.name
        cns.target = gen

        for prop in rig.keys():
            final = finalProp(prop)
            if prop in gen.keys() and final in gen.data.keys():
                addDriver(rig, propRef(prop), gen, propRef(prop), "x")

        for ob in self.meshes:
            ob.parent = rig
            skeys = ob.data.shape_keys
            if skeys:
                retargetDrivers(skeys, gen, rig, True)
                for skey in skeys.key_blocks:
                    skey.mute = False
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                mod.object = rig
            for rname,dname in self.renamedBones.items():
                vgrp = ob.vertex_groups.get(rname)
                if vgrp:
                    vgrp.name = dname
                    continue
                tname = self.getTweakBoneName(rname)
                if tname and tname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[tname]
                    vgrp.name = dname

#-------------------------------------------------------------
#   Gizmos (custom shapes)
#-------------------------------------------------------------

class GizmoUser:
    def startGizmos(self, context, ob):
        from .node import createHiddenCollection
        self.gizmos = {}
        self.hidden = createHiddenCollection(context, ob)


    def makeGizmos(self, useEmpties, gnames):
        if useEmpties:
            self.makeEmptyGizmo("GZM_Circle", 'CIRCLE')
            self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
            self.makeEmptyGizmo("GZM_Cube", 'CUBE')
            self.makeEmptyGizmo("GZM_Cone", 'CONE')

        from .fileutils import DF
        struct = DF.loadEntry("mhx", "gizmos", True)
        if gnames is None:
            gnames = struct.keys()
        for gname in gnames:
            if gname in bpy.data.meshes.keys():
                me = bpy.data.meshes[gname]
            else:
                gizmo = struct[gname]
                me = bpy.data.meshes.new(gname)
                me.from_pydata(gizmo["verts"], gizmo["edges"], [])
            self.makeGizmo(gname, me)


    def getOldGizmo(self, gname):
        for gname1 in self.hidden.objects.keys():
            if baseName(gname1) == gname:
                ob = self.hidden.objects[gname1]
                self.gizmos[gname] = ob
                return ob
        return None


    def makeGizmo(self, gname, me, parent=None):
        ob = self.getOldGizmo(gname)
        if ob is not None:
            return ob
        ob = bpy.data.objects.new(gname, me)
        self.hidden.objects.link(ob)
        ob.parent = parent
        self.gizmos[gname] = ob
        #ob.hide_render = ob.hide_viewport = True
        return ob


    def makeEmptyGizmo(self, gname, dtype):
        ob = self.getOldGizmo(gname)
        if ob is not None:
            return ob
        empty = self.makeGizmo(gname, None)
        empty.empty_display_type = dtype
        return empty


    def addGizmo(self, pb, gname, scale, blen=None):
        from .simple import setCustomShape
        gizmo = self.gizmos[gname]
        pb.bone.show_wire = True
        if blen:
            scale = blen/pb.bone.length
        setCustomShape(pb, gizmo, scale)


    def renameFaceBones(self, rig, extra=[]):
        def renameFaceBone(bone):
            bname = bone.name
            newname = self.getOtherName(bname)
            if newname:
                renamed[bname] = newname
                bone.name = newname
                self.renamedBones[newname] = bname

        renamed = {}
        for pb in rig.pose.bones:
            if (self.isFaceBone(pb, rig) or
                pb.name[1:] in extra):
                renameFaceBone(pb.bone)
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if (hasattr(cns, "subtarget") and
                    cns.subtarget in renamed.keys()):
                    cns.subtarget = renamed[cns.subtarget]


    def getOtherName(self, bname):
        return getSuffixName(bname)


def getSuffixName(bname):
    if isDrvBone(bname) or isFinal(bname):
        return None
    if len(bname) >= 2 and bname[1].isupper():
        if bname[0] == "r":
            return "%s%s.R" % (bname[1].lower(), bname[2:])
        elif bname[0] == "l":
            return "%s%s.L" % (bname[1].lower(), bname[2:])
    elif len(bname) >= 3 and bname[1] == "_":
        if bname[0] == "r":
            return "%s%s.R" % (bname[2].lower(), bname[3:])
        elif bname[0] == "l":
            return "%s%s.L" % (bname[2].lower(), bname[3:])
    elif bname[0].isupper():
        return "%s%s" % (bname[0].lower(), bname[1:])
    else:
        return None


def getPreSufName(bname, rig):
    if bname in rig.data.bones.keys():
        return bname
    sufname = getSuffixName(bname)
    if sufname and sufname in rig.data.bones.keys():
        return sufname
    return None

#-------------------------------------------------------------
#   Replace left-right prefix with suffix
#-------------------------------------------------------------

class DAZ_OT_ChangePrefixToSuffix(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.change_prefix_to_suffix"
    bl_label = "Change Prefix To Suffix"
    bl_description = "Change l/r prefix to .L/.R suffix,\nto use Blender symmetry tools"
    bl_options = {'UNDO'}

    def run(self, context):
        self.renamedBones = {}
        for rig in getSelectedArmatures(context):
            if rig.DazRig[-7:] == ".suffix":
                raise DazError("%s already has suffix bones" % rig.name)
            if rig.DazRig.startswith(("mhx", "rigify")):
                raise DazError("Cannot change a %s rig to suffix" % rig.DazRig)
            self.renameFaceBones(rig)
            rig.DazRig = "%s.suffix" % rig.DazRig

    def isFaceBone(self, pb, rig):
        return True


class DAZ_OT_ChangeSuffixToPrefix(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.change_suffix_to_prefix"
    bl_label = "Change Suffix To Prefix"
    bl_description = "Change .L/.R suffix to l/r prefix,\nto prepare rig for MHX or Rigify"
    bl_options = {'UNDO'}

    def run(self, context):
        self.renamedBones = {}
        for rig in getSelectedArmatures(context):
            if rig.DazRig[-7:] != ".suffix":
                raise DazError("%s does not have suffix bones" % rig.name)
            self.rigtype = rig.DazRig = rig.DazRig[:-7]
            self.renameFaceBones(rig)

    def isFaceBone(self, pb, rig):
        return True

    def getOtherName(self, bname):
        if len(bname) < 2:
            return bname
        elif bname[-2:] in [".L", "_L"]:
            if self.rigtype == "genesis9":
                return "l_%s" % bname[0:-2]
            else:
                return "l%s%s" % (bname[0].upper(), bname[1:-2])
        elif bname[-2:] in [".R", "_R"]:
            if self.rigtype == "genesis9":
                return "r_%s" % bname[0:-2]
            else:
                return "r%s%s" % (bname[0].upper(), bname[1:-2])
        else:
            return bname

#-------------------------------------------------------------
#   Select seg01
#-------------------------------------------------------------

class DAZ_OT_SelectMatchingBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.select_matching_bones"
    bl_label = "Select Matching Bones"
    bl_description = "Select bones with matching names"
    bl_options = {'UNDO'}

    match : StringProperty(
        name = "Match",
        description = "Select all bones with matching names",
        default = "seg01")

    def draw(self, context):
        self.layout.prop(self, "match")

    def run(self, context):
        match = self.match.lower()
        for rig in getSelectedArmatures(context):
            for bone in rig.data.bones:
                bone.select = (match in bone.name.lower())

#-------------------------------------------------------------
#   Constraints class
#-------------------------------------------------------------

ConstraintAttributes = [
    "type", "name", "mute", "target", "subtarget", "mix_mode", "use_transform_limit",
    "head_tail", "use_offset", "owner_space", "target_space",
    "use_x", "use_y", "use_z",
    "invert_x", "invert_y", "invert_z",
    "use_limit_x", "use_limit_y", "use_limit_z",
    "use_min_x", "use_min_y", "use_min_z",
    "use_max_x", "use_max_y", "use_max_z",
    "min_x", "min_y", "min_z",
    "max_x", "max_y", "max_z",
]

def copyConstraints(src, trg, rig=None):
    for scns in src.constraints:
        copyConstraint(scns, trg, rig)


def copyConstraint(scns, trg, rig):
    tcns = trg.constraints.new(scns.type)
    for attr in ConstraintAttributes:
        if (hasattr(scns, attr) and attr != "type"):
            setattr(tcns, attr, getattr(scns, attr))
    if rig and hasattr(tcns, "target"):
        tcns.target = rig


class ConstraintStore:
    def __init__(self):
        self.constraints = {}


    def storeConstraints(self, key, pb):
        clist = []
        for cns in pb.constraints:
            struct = {}
            for attr in ConstraintAttributes:
                if hasattr(cns, attr):
                    struct[attr] = getattr(cns, attr)
            clist.append(struct)
        if clist and key:
            self.constraints[key] = clist


    def storeAllConstraints(self, rig):
        for pb in rig.pose.bones:
            self.storeConstraints(pb.name, pb)
            self.removeConstraints(pb)


    def getFkBone(self, key, rig):
        if len(key) > 2 and key[-2] == ".":
            base, suffix = key[:-2], key[-1]
            bname = "%s.fk.%s" % (base, suffix)
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
            bname = "%s_fk.%s" % (base, suffix)
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
        if key in rig.pose.bones.keys():
            return rig.pose.bones[key]
        return None


    def restoreAllConstraints(self, rig):
        for key,clist in self.constraints.items():
            if key:
                pb = self.getFkBone(key, rig)
                if pb:
                    for struct in clist:
                        self.restoreConstraint(struct, pb)


    def restoreConstraints(self, key, pb, target=None):
        if key not in self.constraints.keys():
            return
        clist = self.constraints[key]
        for struct in clist:
            self.restoreConstraint(struct, pb, target)


    def restoreConstraint(self, struct, pb, target=None):
        ctype = struct["type"]
        cns = pb.constraints.new(ctype)
        for attr,value in struct.items():
            if attr != "type":
                setattr(cns, attr, value)
        if target and hasattr(cns, "target"):
            cns.target = target


    def removeConstraints(self, pb):
        for cns in list(pb.constraints):
            cns.driver_remove("influence")
            cns.driver_remove("mute")
            pb.constraints.remove(cns)

#-------------------------------------------------------------
#   BendTwist class
#-------------------------------------------------------------

class BendTwists:

    def deleteBendTwistDrvBones(self, rig):
        from .driver import removeBoneSumDrivers
        setMode('OBJECT')
        btnames = []
        bnames = {}
        for bone in rig.data.bones:
            if isDrvBone(bone.name) or isFinal(bone.name):
                bname = baseBone(bone.name)
                if bname.endswith(("Bend", "Twist", "twist1", "twist2")):
                    btnames.append(bone.name)
                    bnames[bname] = True
            elif bone.name.endswith(("twist1", "twist2")):
                btnames.append(bone.name)
                bnames[bone.name] = True

        removeBoneSumDrivers(rig, bnames.keys())
        for pb in rig.pose.bones:
            if pb.name.endswith(("Bend", "Twist")):
                pb.driver_remove("location")
                pb.driver_remove("rotation_euler")
                pb.driver_remove("scale")
                for cns in list(pb.constraints):
                    pb.constraints.remove(cns)

        for ob in rig.children:
            if ob.parent and ob.parent_type == 'BONE':
                bname = ob.parent_bone
                if bname in btnames:
                    wmat = ob.matrix_world.copy()
                    if isDrvBone(bname):
                        bone = rig.data.bones[baseBone(bname)]
                    else:
                        bone = rig.data.bones[ob.parent_bone]
                    if bone.parent:
                        ob.parent = rig
                        ob.parent_type = 'BONE'
                        ob.parent_bone = bone.name
                    else:
                        ob.parent_type = 'OBJECT'
                    setWorldMatrix(ob, wmat)

        setMode('EDIT')
        for bname in btnames:
            eb = rig.data.edit_bones[bname]
            for cb in eb.children:
                cb.parent = eb.parent
            rig.data.edit_bones.remove(eb)


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
        setMode('POSE')
        hiddenLayer = 31*[False] + [True]
        rotmodes = {}
        for data in bendTwistBones:
            bname = data[0]
            tname = data[1]
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
        for data in bendTwistBones:
            bname = data[0]
            tname = data[1]
            bendname,twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.data.edit_bones.keys() and
                    twistname in rig.data.edit_bones.keys()):
                continue
            eb = rig.data.edit_bones.new(bname)
            bend = rig.data.edit_bones[bendname]
            twist = rig.data.edit_bones[twistname]
            target = rig.data.edit_bones[tname]
            eb.head = bend.head
            bend.tail = twist.head
            eb.tail = twist.tail
            eb.roll = bend.roll
            eb.parent = bend.parent
            eb.use_deform = False
            eb.use_connect = bend.use_connect
            children = [eb for eb in bend.children if eb != twist] + list(twist.children)
            for child in children:
                child.parent = eb

        for bname3,bname2 in renames.items():
            eb = rig.data.edit_bones[bname3]
            eb.name = bname2

        setMode('OBJECT')
        for bname,rotmode in rotmodes.items():
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                pb.DazRotMode = rotmode

        from .figure import copyBoneInfo
        for data in bendTwistBones:
            bname = data[0]
            tname = data[1]
            bendname,twistname = self.getBendTwistNames(bname)
            if not bendname in rig.data.bones.keys():
                continue
            srcbone = rig.pose.bones[bendname]
            trgbone = rig.pose.bones[bname]
            copyBoneInfo(srcbone, trgbone)

        setMode('EDIT')
        for data in bendTwistBones:
            bname = data[0]
            tname = data[1]
            bendname,twistname = self.getBendTwistNames(bname)
            if bendname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bendname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)
            if twistname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[twistname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)
        setMode('OBJECT')


    def deleteBoneDrivers(self, rig, bname):
        if bname in rig.data.bones.keys():
            path = 'pose.bones["%s"]' % bname
            for channel in ["location", "rotation_euler", "rotation_quaternion", "scale", "HdOffset", "TlOffset"]:
                rig.driver_remove("%s.%s" % (path, channel))


    def joinBendTwistVGroups(self, rig, info):
        for ob in getMeshChildren(rig):
            self.joinVertexGroups(ob, info)


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


    def createBendTwists(self, rig, bendTwistBones):
        defLayer = L_DEF*[False] + [True] + (31-L_DEF)*[False]
        finLayer = L_FIN*[False] + [True] + (31-L_FIN)*[False]
        tweakLayer = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]
        setMode('EDIT')

        for data in bendTwistBones:
            bname = data[0]
            eb = rig.data.edit_bones[bname]
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
            bend.layers = twist.layers = finLayer
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
                bendtwk.layers = twisttwk.layers = defLayer
                bendtwk.layers[L_TWEAK] = twisttwk.layers[L_TWEAK] = True
                bvgname = btwkname
                tvgname = ttwkname
            else:
                bend.use_deform = twist.use_deform = True
                bend.layers = twist.layers = defLayer
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


    def splitVertexGroup(self, ob, vgname, bvgname, tvgname, head, tail):
        vgrp = ob.vertex_groups.get(vgname)
        bendgrp = ob.vertex_groups.new(name=bvgname)
        bendgrp.name = bvgname
        twistgrp = ob.vertex_groups.new(name=tvgname)
        twistgrp.name = tvgname
        vec = tail-head
        vec /= vec.dot(vec)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = vec.dot(v.co - head)
                    if x < 0:
                        x = 0
                    elif x > 1:
                        x = 1
                    bendgrp.add([v.index], g.weight*(1-x), 'REPLACE')
                    twistgrp.add([v.index], g.weight*x, 'REPLACE')
        ob.vertex_groups.remove(vgrp)


    def constrainBendTwists(self, rig, bendTwistBones):
        from .mhx import dampedTrack, copyRotation, copyTransform, stretchTo
        setMode('POSE')
        ball = "GZM_Ball025"
        eulers = {
            "upper_arm" : "YXZ",
            "forearm" : "YZX",
            "thigh" : "YZX",
            "shin" : "YZX",
        }
        for bname,trgname,stretch,prop in bendTwistBones:
            bendname,twistname = self.getSubBoneNames(bname)
            if not hasPoseBones(rig, [bname, bendname, twistname]):
                continue
            pb = rig.pose.bones[bname]
            bend = rig.pose.bones[bendname]
            twist = rig.pose.bones[twistname]
            bend.rotation_mode = twist.rotation_mode = pb.rotation_mode
            pb2 = rig.pose.bones[trgname]
            if self.usePoleTargets:
                cns1 = dampedTrack(bend, pb2, rig)
                cns2 = copyTransform(twist, pb, rig)
            else:
                xyz = eulers[pb.name.split(".")[0]]
                cns = copyRotation(bend, pb, rig)
                cns.euler_order = xyz
                cns.use_y = False
                cns = copyRotation(twist, pb, rig)
                cns.euler_order = xyz
                cns.use_x = cns.use_z = False

            if stretch:
                cns = stretchTo(bend, pb2, rig, prop, "x")
                cns = stretchTo(twist, pb2, rig, prop, "x")
            if self.addTweakBones:
                btwkname = self.getTweakBoneName(bendname)
                ttwkname = self.getTweakBoneName(twistname)
                bendtwk = rig.pose.bones[btwkname]
                twisttwk = rig.pose.bones[ttwkname]
                self.addGizmo(bendtwk, ball, 1, blen=10*rig.DazScale)
                self.addGizmo(twisttwk, ball, 1, blen=10*rig.DazScale)

#-------------------------------------------------------------
#   Add IK goals
#-------------------------------------------------------------

class DAZ_OT_AddIkGoals(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_ik_goals"
    bl_label = "Add IK goals"
    bl_description = "Add IK goals"
    bl_options = {'UNDO'}

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains",
        default = False)

    hideBones : BoolProperty(
        name = "Hide Bones",
        description = "Hide all bones in the IK chains",
        default = False)

    lockBones : BoolProperty(
        name = "Lock Bones",
        description = "Lock all bones in the IK chains",
        default = False)

    disableBones : BoolProperty(
        name = "Disable Bones",
        description = "Disable all bones in the IK chains",
        default = False)

    fromRoots : BoolProperty(
        name = "From Root Bones",
        description = "Select IK chains from root bones",
        default = True)

    onlyConnected : BoolProperty(
        name = "Only Connected Bones",
        description = "Stop IK chain at disconnected bones",
        default = True)

    threshold : FloatProperty(
        name = "Threshold",
        description = "Threshold for stopping the IK chain",
        min = 0,
        default = 0.01)

    def draw(self, context):
        self.layout.prop(self, "fromRoots")
        self.layout.prop(self, "onlyConnected")
        if self.onlyConnected:
            self.layout.prop(self, "threshold")
        self.layout.separator()
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "hideBones")
        self.layout.prop(self, "lockBones")
        self.layout.prop(self, "disableBones")


    def ikGoalsFromSelected(self, rig):
        ikgoals = []
        for pb in rig.pose.bones:
            if pb.bone.select and not pb.children:
                clen = 0
                par = pb
                pbones = []
                while par and par.bone.select:
                    pbones.append(par)
                    clen += 1
                    par = par.parent
                if clen > 2:
                    root = pbones[-1]
                    pbones = pbones[:-1]
                    ikgoals.append((pb.name, clen-1, pbones, root))
        return ikgoals


    def ikGoalsFromRoots(self, rig):
        def nostop(pb):
            if len(pb.children) != 1:
                return False
            elif self.onlyConnected:
                child = pb.children[0]
                return ((child.head-pb.tail).length < self.threshold)
            return True

        ikgoals = []
        for root in rig.pose.bones:
            if root.bone.select:
                clen = 0
                pbones = []
                pb = root
                while pb and nostop(pb):
                    pb = pb.children[0]
                    pbones.append(pb)
                    clen += 1
                if clen > 2:
                    ikgoals.append((pb.name, clen-1, pbones, root))
        return ikgoals


    def run(self, context):
        for rig in getSelectedArmatures(context):
            self.addIkGoals(context, rig)


    def addIkGoals(self, context, rig):
        if self.fromRoots:
            ikgoals = self.ikGoalsFromRoots(rig)
        else:
            ikgoals = self.ikGoalsFromSelected(rig)

        setMode('EDIT')
        for bname, clen, pbones, root in ikgoals:
            eb = rig.data.edit_bones[bname]
            goalname = self.combineName(bname, "Goal")
            goal = rig.data.edit_bones.new(goalname)
            goal.head = eb.tail
            goal.tail = 2*eb.tail - eb.head
            goal.roll = eb.roll
            if self.usePoleTargets:
                for n in range(clen//2):
                    eb = eb.parent
                polename = self.combineName(bname, "Pole")
                pole = rig.data.edit_bones.new(polename)
                pole.head = eb.head + eb.length * eb.x_axis
                pole.tail = eb.tail + eb.length * eb.x_axis
                pole.roll = eb.roll

        setMode('OBJECT')
        self.startGizmos(context, rig)
        gzmBall = self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        gzmCube = self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        gzmCone = self.makeEmptyGizmo("GZM_Cone", 'CONE')

        setMode('POSE')
        for bname, clen, pbones, root in ikgoals:
            if bname not in rig.pose.bones.keys():
                continue
            pb = rig.pose.bones[bname]
            rmat = pb.bone.matrix_local
            root.custom_shape = gzmCube

            goalname = self.combineName(bname, "Goal")
            goal = rig.pose.bones[goalname]
            goal.rotation_mode = pb.rotation_mode
            goal.bone.use_local_location = True
            goal.matrix_basis = rmat.inverted() @ pb.matrix
            goal.custom_shape = gzmBall

            if self.usePoleTargets:
                pole = rig.pose.bones[polename]
                pole.rotation_mode = pb.rotation_mode
                pole.bone.use_local_location = True
                pole.matrix_basis = rmat.inverted() @ pb.matrix
                pole.custom_shape = gzmCone

            cns = getConstraint(pb, 'IK')
            if cns:
                pb.constraints.remove(cns)
            cns = pb.constraints.new('IK')
            cns.name = "IK %s" % goalname
            cns.target = rig
            cns.subtarget = goalname
            cns.chain_count = clen
            cns.use_location = True
            if self.usePoleTargets:
                cns.pole_target = rig
                cns.pole_subtarget = polename
                cns.pole_angle = 0*D
                cns.use_rotation = False
            else:
                cns.use_rotation = True

            if self.hideBones:
                for pb in pbones:
                    pb.bone.hide = True
            if self.lockBones:
                for pb in pbones:
                    lockAllTransform(pb)
            if self.disableBones:
                for pb in pbones:
                    pb.bone.hide_select = True


    def combineName(self, bname, string):
        if bname[-2:].lower() in [".l", ".r", "_l", "_r"]:
            return "%s%s%s" % (bname[:-2], string, bname[-2:])
        else:
            return "%s%s" % (bname, string)


#-------------------------------------------------------------
#   Add Winder
#-------------------------------------------------------------

class DAZ_OT_AddWinders(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_winders"
    bl_label = "Add Winders"
    bl_description = "Add winders to selected posebones"
    bl_options = {'UNDO'}

    winderLayer : IntProperty(
        name = "Winder Layer",
        description = "Bone layer for the winder bones",
        min = 1, max = 32,
        default = 1)

    windedLayer : IntProperty(
        name = "Winded Layer",
        description = "Bone layer for the winded bones",
        min = 1, max = 32,
        default = 2)

    useLockLoc : BoolProperty(
        name = "Lock Location",
        description = "Lock winder location even if original bone is not locked",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "winderLayer")
        self.layout.prop(self, "windedLayer")
        self.layout.prop(self, "useLockLoc")

    def invoke(self, context, event):
        rig = context.object
        if rig and rig.DazRig == "mhx":
            self.winderLayer = 17
            self.windedLayer = 18
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        rig = context.object
        self.winderLayers = (self.winderLayer-1)*[False] + [True] + (32-self.winderLayer)*[False]
        self.windedLayers = (self.windedLayer-1)*[False] + [True] + (32-self.windedLayer)*[False]
        self.startGizmos(context, rig)
        self.makeGizmos(False, ["GZM_Knuckle"])
        gizmo = self.gizmos["GZM_Knuckle"]
        for pb in self.findPoseRoots(rig):
            addWinder(rig, pb.name, gizmo, self.useLockLoc, self.winderLayers, self.windedLayers)


    def findPoseRoots(self, rig):
        proots = {}
        for pb in rig.pose.bones:
            if pb.bone.select and len(pb.children) == 1:
                proots[pb.name] = pb
        removes = {}
        for proot in proots.values():
            pb = proot
            while len(pb.children) == 1:
                pb = pb.children[0]
                removes[pb.name] = True
            if len(pb.children) > 0:
                removes[proot.name] = True
        for bname in removes.keys():
            if bname in proots.keys():
                del proots[bname]
        return proots.values()

#-------------------------------------------------------------
#   addWinder used in hide.py
#-------------------------------------------------------------

def addWinder(rig, bname, gizmo, useLockLoc, winderLayers, windedLayers, xaxis=None):
    from .mhx import copyRotation, copyScale, copyLocation
    wname = "Wind_%s" % bname
    setMode('EDIT')
    eb = rig.data.edit_bones[bname]
    tarb = rig.data.edit_bones.new(wname)
    tarb.head = eb.head
    tarb.tail = eb.tail
    tarb.roll = eb.roll
    tarb.parent = eb.parent
    tarb.layers = winderLayers
    n = 1
    length = eb.length
    while eb.children and len(eb.children) == 1:
        eb = eb.children[0]
        tarb.tail = eb.tail
        n += 1
        length += eb.length
    if xaxis is not None:
        from .bone import setRoll
        setRoll(tarb, xaxis)

    setMode('POSE')
    pb = rig.pose.bones[bname]
    winder = rig.pose.bones[wname]
    if gizmo:
        winder.custom_shape = gizmo
        winder.bone.show_wire = True
    winder.rotation_mode = pb.rotation_mode
    winder.matrix_basis = pb.matrix_basis
    winder.lock_location = pb.lock_location
    winder.lock_rotation = pb.lock_rotation
    winder.lock_scale = pb.lock_scale
    if useLockLoc:
        winder.lock_location = (True, True, True)

    infl = 2*pb.bone.length/length
    cns1 = copyRotation(pb, winder, rig)
    cns1.influence = infl
    cns2 = copyScale(pb, winder, rig)
    cns2.influence = infl
    if not useLockLoc:
        cns3 = copyLocation(pb, winder, rig)
        cns3.influence = infl
    pb.bone.layers = windedLayers
    while pb.children and len(pb.children) == 1:
        pb = pb.children[0]
        infl = 2*pb.bone.length/length
        cns1 = copyRotation(pb, winder, rig)
        cns1.use_offset = True
        cns1.influence = infl
        cns2 = copyScale(pb, winder, rig)
        cns2.use_offset = True
        cns2.influence = infl
        pb.bone.layers = windedLayers

#-------------------------------------------------------------
#   Retarget armature
#-------------------------------------------------------------

class DAZ_OT_ChangeArmature(DazPropsOperator, IsArmature):
    bl_idname = "daz.change_armature"
    bl_label = "Change Armature"
    bl_description = "Make the active armature the armature of selected meshes"
    bl_options = {'UNDO'}

    useRetarget : BoolProperty(
        name = "Retarget Drivers",
        description = "Retarget shapekey drivers to the new armature.\nWarning: Will cause errors if the new armature lack drivers",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useRetarget")

    def run(self, context):
        rig = context.object
        subrigs = {}
        for ob in getSelectedMeshes(context):
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                subrig = mod.object
                if subrig and subrig != rig:
                    subrigs[subrig.name] = subrig
                mod.object = rig
                if self.useRetarget:
                    retargetDrivers(ob.data.shape_keys, subrig, rig, False)
            if ob.parent and ob.parent_type == 'BONE':
                wmat = ob.matrix_world.copy()
                bname = ob.parent_bone
                ob.parent = rig
                ob.parent_type = 'BONE'
                ob.parent_bone = bname
                setWorldMatrix(ob, wmat)
            else:
                ob.parent = rig
        activateObject(context, rig)
        for subrig in subrigs.values():
            self.addExtraBones(subrig, rig)


    def addExtraBones(self, subrig, rig):
        extras = {}
        for bname in subrig.data.bones.keys():
            if bname not in rig.data.bones.keys():
                bone = subrig.data.bones[bname]
                if bone.parent:
                    pname = bone.parent.name
                else:
                    pname = None
                extras[bname] = (bone.head_local.copy(), bone.tail_local.copy(), bone.matrix_local.copy(), list(bone.layers), pname)
        if extras:
            setMode('EDIT')
            for bname,data in extras.items():
                eb = rig.data.edit_bones.new(bname)
                eb.head, eb.tail, mat, eb.layers, pname = data
                if pname is not None:
                    eb.parent = rig.data.edit_bones[pname]
                eb.matrix = mat
            setMode('OBJECT')


def retargetDrivers(rna, orig, nrig, force):
    if not (rna and rna.animation_data):
        return
    for fcu in rna.animation_data.drivers:
        fcu.mute = False
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT' and (force or trg.id == orig):
                    trg.id = nrig
                elif trg.id_type == 'ARMATURE' and (force or trg.id == orig.data):
                    trg.id = nrig.data
                elif trg.id_type not in ['KEY']:
                    print("Unexpected id: %s %s" % (trg.id_type, trg.id))

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddIkGoals,
    DAZ_OT_AddWinders,
    DAZ_OT_ChangePrefixToSuffix,
    DAZ_OT_ChangeSuffixToPrefix,
    DAZ_OT_SelectMatchingBones,
    DAZ_OT_ChangeArmature,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

