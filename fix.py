#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
import math
import os
from mathutils import *
from .error import *
from .utils import *
from .driver import DriverUser, addDriver

#-------------------------------------------------------------
#   Mha features
#-------------------------------------------------------------

F_TONGUE = 1
F_FINGER = 2
F_IDPROPS = 4
F_SPINE = 8
F_SHAFT = 16
F_NECK = 32

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

    useAutoEuler : BoolProperty(
        name = "Auto Euler",
        description = "Use Auto Euler as driver rotation mode for quaternion bones.\nAvoids some popping during animation at the cost of JCMs accuracy",
        default = True)

    keepRig : BoolProperty(
        name = "Keep DAZ Rig",
        description = "Keep the original DAZ rig for deformation",
        default = False)

    useModifyDazRig : BoolProperty(
        name = "Modify DAZ Rig",
        description = "Change the rest pose of the deform rig to match the control rig",
        default = False)

    def drawMeta(self):
        self.layout.prop(self, "keepRig")
        if self.keepRig:
            self.layout.prop(self, "useModifyDazRig")
        self.layout.prop(self, "useFingerIk")

    def drawRigify(self):
        self.layout.prop(self, "useTongueIk")
        self.layout.prop(self, "useImproveIk")
        self.layout.prop(self, "useAutoEuler")


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
            self.raiseWarning(msg)


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


    def fixCustomShape(self, rig, bnames, scale, offset=0):
        for bname in bnames:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                if pb.custom_shape:
                    setCustomShapeTransform(pb, scale)
                    if offset:
                        for v in pb.custom_shape.data.vertices:
                            v.co += offset
                return


    def fixHands(self, rig):
        setMode('EDIT')
        for suffix in ["L", "R"]:
            forearm = rig.data.edit_bones.get("forearm.%s" % suffix)
            hand = rig.data.edit_bones.get("hand.%s" % suffix)
            if forearm and hand:
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


    def fixBoneDrivers(self, rig, rig0, assoc0):
        def changeTargets(rna, rig, rig0):
            if rna.animation_data:
                drivers = list(rna.animation_data.drivers)
                if not ES.easy:
                    print("    (%s %d)" % (rna.name, len(drivers)))
                for n,fcu in enumerate(drivers):
                    self.changeTarget(fcu, rna, rig, rig0, assoc)

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
        if not ES.easy:
            print("    (%s %d)" % (rig.data.name, len(findrivers)))
        for fcu in findrivers.values():
            self.changeTarget(fcu, rig.data, rig, rig0, assoc)
        for fcu in offsdrivers:
            rig.data.animation_data.drivers.remove(fcu)
        for ob in rig.children:
            changeTargets(ob, rig, rig0)
            if ob.type == 'MESH' and ob.data.shape_keys:
                changeTargets(ob.data.shape_keys, rig, rig0)


    def changeTarget(self, fcu, rna, rig, rig0, assoc):
        def setVar(var):
            for trg in var.targets:
                if trg.id_type == 'OBJECT' and trg.id == rig0:
                    trg.id = rig
                elif trg.id_type == 'ARMATURE' and trg.id == rig0.data:
                    trg.id = rig.data
                if var.type == 'TRANSFORMS':
                    bname = trg.bone_target
                    defbone = "DEF-" + bname
                    if bname in assoc.keys():
                        trg.bone_target = assoc[bname]
                    elif defbone in rig.pose.bones.keys():
                        trg.bone_target = defbone
                    else:
                        return False
            return True

        channel = fcu.data_path
        idx = self.getArrayIndex(fcu)
        if fcu.driver is None:
            return
        for var in fcu.driver.variables:
            if not setVar(var):
                if idx >= 0:
                    rna.driver_remove(channel, idx)
                else:
                    rna.driver_remove(channel)
                return
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        ok = True
        for var in fcu2.driver.variables:
            ok = (ok and setVar(var))
        if ok:
            fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
            fcu3.data_path = channel
            if idx >= 0:
                fcu3.array_index = idx
        self.clearTmpDriver(0)


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
            if ob.type == 'MESH':
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
        self.tongueBones = [bone.name for bone in rig.data.bones if ("tongue" in bone.name and not isDrvBone(bone.name))]
        if len(self.tongueBones) < 3:
            print("Did not find tongue")
            self.useTongueIk = False
            return
        if not ES.easy:
            print("Tongue bones:", self.tongueBones)
        if self.checkDriven(rig, self.tongueBones, "Tongue IK"):
            self.useTongueIk = False


    def checkDriven(self, rig, bnames, string):
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                bname,channel = getBoneChannel(fcu)
                if bname and bname in bnames:
                    self.messages.append("%s is disabled because\n%s has drivers" % (string, bname))
                    return True
        return False

    #-------------------------------------------------------------
    #   Tongue Control
    #-------------------------------------------------------------

    def addTongueIkBones(self, rig, layer, deflayer):
        from .rig_utils import makeBone
        first = rig.data.edit_bones[self.tongueBones[0]]
        for bname in self.tongueBones:
            eb = rig.data.edit_bones[bname]
            eb.use_connect = False
            trgb = makeBone("ik_%s" % bname, rig, eb.tail, 2*eb.tail-eb.head, eb.roll, layer, first.parent)


    def addTongueControl(self, rig, layers):
        from .rig_utils import setMhx, mhxProp, stretchTo, addMuteDriver
        from .winder import addWinder
        from .driver import addDriver
        prop1 = "MhaTongueControl"
        setMhx(rig, prop1, True)
        winder,pbones = addWinder(rig, "tongue", self.tongueBones, layers, prop1, useLocation=True, useScale=True)
        if winder is None:
            return
        self.addGizmo(winder, "GZM_Knuckle", 1.0)
        if self.useTongueIk:
            prop2 = "MhaTongueIk"
            setMhx(rig, prop2, 0.0)
            rig.data.MhaFeatures |= F_TONGUE
            for bname in self.tongueBones:
                pb = rig.pose.bones[bname]
                pb.lock_location = TTrue
                for cns in list(pb.constraints):
                    if cns.type == 'LIMIT_ROTATION':
                        addDriver(cns, "influence", rig, mhxProp(prop2), "1-x")
                trgb = rig.pose.bones["ik_%s" % bname]
                trgb.bone.use_deform = False
                self.addGizmo(trgb, "GZM_Ball", 0.2)
                cns = stretchTo(pb, trgb, rig, prop2)
                addMuteDriver(cns, rig, prop1)

    #-------------------------------------------------------------
    #   Gaze Bones
    #-------------------------------------------------------------

    def addSingleGazeBone(self, rig, suffix, headLayer, helpLayer):
        from .rig_utils import makeBone, deriveBone
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
        from .rig_utils import makeBone, deriveBone
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

        from .rig_utils import dampedTrack, copyRotation, setMhx
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
        from .rig_utils import copyTransform, setMhx, mhxProp
        gaze0 = rig.pose.bones.get("gaze0")
        gaze1 = rig.pose.bones.get("gaze1")
        if gaze0 and gaze1:
            prop = "MhaGazeFollowsHead"
            setMhx(rig, prop, 1.0)
            copyTransform(gaze1, gaze0, rig, prop)

    #-------------------------------------------------------------
    #   Tie bones
    #-------------------------------------------------------------

    def getTweakBoneName(self, bname):
        return "NONE"


    def tieBones(self, context, rig, gen):
        def hasCopyConstraint(pb):
            for cns in list(pb.constraints):
                if cns.type.startswith("COPY"):
                    return True
            return False

        from .driver import retargetDrivers
        if not ES.easy:
            print("Tie bones of %s to %s" % (rig.name, gen.name))
        facebones = self.setupFaceBones(rig)
        assoc = dict([(bname,rname) for rname,bname in self.renamedBones.items()])
        if self.useModifyDazRig:
            activateObject(context, gen)
            setMode('EDIT')
            bdata = dict([(eb.name, (eb.head.copy(), eb.tail.copy(), eb.roll)) for eb in gen.data.edit_bones])
            setMode('OBJECT')
            activateObject(context, rig)
            setMode('EDIT')
            for eb in rig.data.edit_bones:
                rname = assoc.get(eb.name, eb.name)
                data = bdata.get(rname)
                if data:
                    eb.head, eb.tail, eb.roll = data
            setMode('OBJECT')
            activateObject(context, gen)
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
        struct = DF.loadEntry(self.gizmoFile, "gizmos", True)
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


    def addGizmo(self, pb, gname, scale, offset=None, blen=None):
        if gname not in self.gizmos.keys():
            print("Missing gizmo: %s" % gname)
            return
        gizmo = self.gizmos[gname]
        pb.bone.show_wire = True
        if blen:
            scale *= blen/pb.bone.length
        pb.custom_shape = gizmo
        if isinstance(offset, tuple):
            offset = Vector(offset)*pb.bone.length
        elif offset is not None:
            offset = offset*pb.bone.length
        setCustomShapeTransform(pb, scale, offset, None)


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
        return getSuffixName(bname, True)

#----------------------------------------------------------
#   Get suffix name
#----------------------------------------------------------

def getSuffixName(bname, useTwist):
    if useTwist and bname.endswith(("twist1", "twist2")):
        pass
    elif isDrvBone(bname) or isFinal(bname):
        return ""
    if len(bname) < 2:
        return bname
    elif bname[1].isupper():
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
        return ""


def getPreSufName(bname, rig):
    if bname in rig.data.bones.keys():
        return bname
    sufname = getSuffixName(bname, True)
    if sufname and sufname in rig.data.bones.keys():
        return sufname
    return ""

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
            if rig.DazRig.endswith(".suffix"):
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
            if not rig.DazRig.endswith(".suffix"):
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
#   Constraints class
#-------------------------------------------------------------

ConstraintAttributes = [
    "type", "name", "mute", "target", "subtarget", "mix_mode", "use_transform_limit",
    "head_tail", "use_offset", "owner_space", "target_space", "euler_order",
    "use_x", "use_y", "use_z",
    "invert_x", "invert_y", "invert_z",
    "use_limit_x", "use_limit_y", "use_limit_z",
    "use_min_x", "use_min_y", "use_min_z",
    "use_max_x", "use_max_y", "use_max_z",
    "min_x", "min_y", "min_z",
    "max_x", "max_y", "max_z",
    "influence",
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


    def restoreAllConstraints(self, context, rig, ignore):
        for key,clist in self.constraints.items():
            if key:
                pb = self.getFkBone(key, rig)
                if pb and pb.name not in ignore:
                    for struct in clist:
                        self.restoreConstraint(struct, pb)

        def fixBendTwistMixup(cns):
            if hasattr(cns, "target") and cns.target == rig and hasattr(cns, "subtarget"):
                bname = cns.subtarget
                if bname not in rig.data.bones:
                    bname1 = bname.replace("Bend.", ".bend.").replace("Twist.", ".twist.")
                    if bname1 in rig.data.bones:
                        cns.subtarget = bname1

        for ob in context.view_layer.objects:
            for cns in ob.constraints:
                fixBendTwistMixup(cns)
            if ob.type == 'ARMATURE':
                for pb in ob.pose.bones:
                    for cns in pb.constraints:
                        fixBendTwistMixup(cns)


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


    def removeConstraints(self, pb, onlyLimit=False):
        for cns in list(pb.constraints):
            if not onlyLimit or cns.type.startswith("LIMIT"):
                cns.driver_remove("influence")
                cns.driver_remove("mute")
                pb.constraints.remove(cns)

    #-------------------------------------------------------------
    #   Driver store
    #-------------------------------------------------------------

    def storeAllDrivers(self, rig, nrig, meshes):
        from .driver import Driver
        def storeDrivers(rna, key):
            if rna and rna.animation_data:
                drivers = self.drivers[key] = []
                for fcu in list(rna.animation_data.drivers):
                    if not someMatch([":Hdo:", ":Tlo:"], fcu.data_path):
                        driver = Driver(fcu, False)
                        drivers.append(driver)
                    rna.animation_data.drivers.remove(fcu)

        self.drivers = {}
        storeDrivers(rig.data, "_RIG_")
        for ob in meshes:
            storeDrivers(ob.data.shape_keys, "_SKEY_%s" % ob.name)
            storeDrivers(ob, "_OB_%s" % ob.name)


    def restoreAllDrivers(self, rig, nrig, meshes, renamed):
        def restoreDrivers(rna, key, assoc):
            drivers = self.drivers.get(key, [])
            for driver in drivers:
                driver.createDirect(rna, assoc)

        assoc = {}
        for mbone,dbone in renamed.items():
            defbone = "DEF-%s" % mbone
            if defbone in rig.data.bones.keys():
                assoc[dbone] = defbone
            else:
                assoc[dbone] = mbone.replace(".bend.", ".").replace(".twist.", ".")
        restoreDrivers(rig.data, "_RIG_", assoc)
        if nrig:
            assoc = {}
        for ob in meshes:
            restoreDrivers(ob.data.shape_keys, "_SKEY_%s" % ob.name, assoc)
            restoreDrivers(ob, "_OB_%s" % ob.name, assoc)

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


    def deleteBoneDrivers(self, rig, bname):
        if bname in rig.data.bones.keys():
            path = 'pose.bones["%s"]' % bname
            for channel in ["location", "rotation_euler", "rotation_quaternion", "scale", "HdOffset", "TlOffset"]:
                rig.driver_remove("%s.%s" % (path, channel))


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
        from .driver import retargetDrivers
        rig = context.object
        subrigs = {}
        for ob in getSelectedMeshes(context):
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                subrig = mod.object
                if subrig and subrig != rig:
                    subrigs[subrig.name] = subrig
                mod.object = rig
                if self.useRetarget and ob.data.shape_keys:
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
                extras[bname] = (bone.head_local.copy(), bone.tail_local.copy(), bone.matrix_local.copy(), getBoneLayers(bone, rig), pname)
        if extras:
            setMode('EDIT')
            for bname,data in extras.items():
                eb = rig.data.edit_bones.new(bname)
                eb.head, eb.tail, mat, layers, pname = data
                setBoneLayers(eb, rig, layers)
                if pname is not None:
                    eb.parent = rig.data.edit_bones[pname]
                eb.matrix = mat
            setMode('OBJECT')

#-------------------------------------------------------------
#   Fix limit rotation constraints
#-------------------------------------------------------------

class DAZ_OT_FixLimitRotConstraints(DazOperator, IsArmature):
    bl_idname = "daz.fix_limit_rot_constraints"
    bl_label = "Fix Limit Rotation Constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        from .bone_data import BD
        rig = context.object
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'LIMIT_ROTATION':
                    setEulerOrder(cns, BD.getDefaultMode(pb))

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangePrefixToSuffix,
    DAZ_OT_ChangeSuffixToPrefix,
    DAZ_OT_ChangeArmature,
    DAZ_OT_FixLimitRotConstraints,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Armature.MhaFeatures = IntProperty(default = 0)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

