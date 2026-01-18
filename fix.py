# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .error import *
from .utils import *
from .rig_utils import *
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
        description = "Improve IK by storing a bending angle.\nThis is compatible with daz poses but does not work with rigify poles so they can not be used.\nNot needed if Optimize Pose for IK is used",
        default = False)

    useLimitConstraints : BoolProperty(
        name = "Limit Constraints",
        description = "Copy limit location and limit rotation constraints to FK bones",
        default = True)

    useFingerIk : BoolProperty(
        name = "Finger IK",
        description = "Generate IK controls for fingers",
        default = False)

    enumControls = [('NONE', "None", "No controls"),
                    ('WINDER', "Winder", "Winder"),
                    ('IK', "IK", "IK controls"),
                    ('BOTH', "Both", "Both winder and IK controls")]

    tongueControl : EnumProperty(
        items = enumControls,
        name = "Tongue Control",
        description = "Generate controls for tongue",
        default = 'NONE')

    shaftControl : EnumProperty(
        items = enumControls,
        name = "Shaft Control",
        description = "Generate controls for Dicktator/Futalicious shaft",
        default = 'NONE')

    shaftName : StringProperty(
        name = "Shaft Name",
        description = "Shaft bones start with this string (case insensitive)",
        default = "Shaft")

    addNondeformExtras : BoolProperty(
        name = "Non-deform Extra Bones",
        description = "Add extra bones to the Rigify armature,\neven if they don't correspond to any vertex group",
        default = True)

    keepRig : BoolProperty(
        name = "Keep DAZ Rig",
        description = "Keep the original DAZ rig for deformation",
        default = False)

    useDisplayTransform : BoolProperty(
        name = "Display Transform Bones",
        description = "Add display transform bones to facial bones",
        default = True)

    def drawMeta(self):
        self.layout.prop(self, "keepRig")
        self.layout.prop(self, "useFingerIk")


    def initFixer(self, keepOffsetDrivers=False):
        from .store import ConstraintStore
        self.initTmp()
        self.messages = []
        self.renamedBones = {}
        self.store = ConstraintStore()
        self.store.keepOffsetDrivers = keepOffsetDrivers


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


    def fixCustomShape(self, rig, bname, scale, offset):
        pb = rig.pose.bones.get(bname)
        if pb and pb.custom_shape:
            if isinstance(offset, (int, float)):
                offset = (offset, offset, offset)
            trans = Vector(offset)*GS.scale
            setCustomShapeTransform(pb, scale, trans=trans)


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


    def fixG3Toes(self, rig):
        setMode('OBJECT')
        toenames = ["BigToe", "SmallToe1", "SmallToe2", "SmallToe3", "SmallToe4"]
        drvnames = [drvBone(bname) for bname in toenames]
        if rig.animation_data:
            fcurves = rig.animation_data.drivers
            for fcu in list(fcurves):
                bname,_,_ = getBoneChannel(fcu)
                if bname[1:] in toenames + drvnames:
                    fcurves.remove(fcu)
        for prefix in ["l", "r"]:
            for bname in toenames:
                pb = rig.pose.bones.get("%s%s" % (prefix, bname))
                if pb:
                    for cns in list(pb.constraints):
                        if cns.type == "COPY_TRANSFORMS" and cns.subtarget == drvBone(pb.name):
                            pb.constraints.remove(cns)
        setMode('EDIT')
        for prefix in ["l", "r"]:
            tarsal =  rig.data.edit_bones.get("%sMetatarsals" % prefix)
            toes = rig.data.edit_bones.get("%sToe" % prefix)
            for bname in toenames:
                toe = rig.data.edit_bones.get("%s%s" % (prefix, bname))
                toe.parent = toes
            for bname in drvnames:
                eb = rig.data.edit_bones.get("%s%s" % (prefix, bname))
                rig.data.edit_bones.remove(eb)


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


    def saveDazRig(self, context, rig):
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
        bnames = [bone.name for bone in rig.data.bones
                  if (bone.name.startswith(("tongue", "mtongue")) and
                      not isDrvBone(bone.name))]
        if len(bnames) < 3:
            print("Did not find tongue")
            self.tongueControl = 'NONE'
            return []
        if not ES.easy:
            print("Tongue bones:", bnames)
        if self.checkDriven(rig, bnames, "Tongue IK"):
            self.tongueControl = 'NONE'
        return bnames


    def checkDriven(self, rig, bnames, string):
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname and bname in bnames and cnsname is None:
                    self.messages.append("%s is disabled because\n%s has drivers" % (string, bname))
                    return True
        return False

    #-------------------------------------------------------------
    #   Tongue Control
    #-------------------------------------------------------------

    def addIkBones(self, wname, bnames, rig, ctrl, layer, deflayer, helplayer, parnames):
        if ctrl not in ['IK', 'BOTH']:
            return
        if (len(bnames) == 0 or
            bnames[0] not in rig.data.edit_bones.keys()):
            print("%s bones not found." % wname.capitalize())
            return
        bname = bnames[0]
        first = rig.data.edit_bones[bnames[0]]
        parent = deriveBone("%s_parent" % wname, first.parent, rig, helplayer, first.parent)
        for parname in parnames:
            par = rig.data.edit_bones[parname]
            deriveBone("%s_%s" % (wname, parname), first.parent, rig, helplayer, par)

        revlist = bnames.copy()
        revlist.reverse()
        invb = None
        for bname in revlist:
            eb = rig.data.edit_bones[bname]
            eb.use_connect = False
            trgb = makeBone("ik_%s" % bname, rig, eb.tail, 2*eb.tail-eb.head, 0, layer, parent, ["TAIL", eb])
            if invb is None:
                invb = trgb
                parent = first.parent
            invb = makeBone("inv_%s" % bname, rig, trgb.tail, trgb.head, 0, helplayer, invb, ["TAIL", trgb])


    def addIkControl(self, wname, bnames, ctrl, prop1, prop2, flag, rig, layers, parnames, influs=None):
        if len(bnames) == 0:
            return
        elif bnames[0] not in rig.pose.bones.keys():
            print("%s bone %s not found." % (wname.capitalize(), bnames[0]))
            return
        from .driver import addDriver

        if flag:
            rig.data["MhaFeatures"] |= flag
        setMhx(rig, prop1, True)
        if ctrl in ['WINDER', 'BOTH']:
            from .winder import addWinder
            winder,pbones = addWinder(rig, wname, bnames, layers, prop1, useLocation=True, useScale=True)
            if winder:
                self.addGizmo(winder, "GZM_Knuckle", 1.0)

        if ctrl in ['IK', 'BOTH']:
            setMhx(rig, prop2, 1.0)
            nbones = len(bnames)
            for n,bname in enumerate(bnames):
                pb = rig.pose.bones[bname]
                pb.lock_location = TTrue
                for cns in list(pb.constraints):
                    if cns.type == 'LIMIT_ROTATION':
                        addDriver(cns, "influence", rig, mhxProp(prop2), "1-x")
                trgb = rig.pose.bones["ik_%s" % bname]
                trgb.bone.use_deform = False
                if n == nbones-1:
                    self.addGizmo(trgb, "GZM_Cone", 0.4)
                    trgb.lock_scale = TTrue
                else:
                    self.addGizmo(trgb, "GZM_Ball", 0.2)
                    trgb.lock_rotation = trgb.lock_scale = TTrue
                    invb = rig.pose.bones["inv_%s" % bname]
                    cns = copyLocation(trgb, invb, rig, space='POSE')
                    cns.head_tail = 1.0
                    cns.influence = ((n+1)/nbones)**1.6
                cns = stretchTo(pb, trgb, rig, prop2)
                addMuteDriver(cns, rig, prop1)

            pb = rig.pose.bones["%s_parent" % wname]
            for parname in parnames:
                parprop = "Mha%s_%s" % (wname.capitalize(), parname)
                setMhx(rig, parprop, 0.0)
                parent = rig.pose.bones["%s_%s" % (wname, parname)]
                cns = copyTransform(pb, parent, rig, parprop, space='POSE')

    #-------------------------------------------------------------
    #   Sbaft Bones
    #-------------------------------------------------------------

    def getShaftBones(self, rig):
        def isShaft(bname):
            shaft = self.shaftName.lower()
            nchars = len(shaft)
            return bname.lower()[0:nchars] == shaft and bname[nchars:].isdigit()

        bnames = [bone.name for bone in rig.data.bones if isShaft(bone.name)]
        bnames.sort()
        print("Shaft bones: %s" % bnames)
        return bnames

    #-------------------------------------------------------------
    #   Gaze Bones
    #-------------------------------------------------------------

    def getEyeBone(self, rig, suffix):
        prefix = suffix.lower()
        bnames = ["%sEye" % prefix, "%s_eye" % prefix, "eye.%s" % suffix]
        for bname in bnames:
            eye = rig.data.edit_bones.get(bname)
            if eye:
                return eye
        print("Did not find eye", bnames)
        return None


    def addSingleGazeBone(self, rig, suffix, headLayer, helpLayer):
        eye = self.getEyeBone(rig, suffix)
        if eye is None:
            return
        drvname = drvBone("eye.%s" % suffix)
        if drvname not in rig.data.edit_bones.keys():
            eyegaze = deriveBone(drvname, eye, rig, helpLayer, eye.parent)
        vec = eye.tail-eye.head
        vec.normalize()
        loc = eye.head + vec*GS.scale*20
        gaze = makeBone("gaze.%s" % suffix, rig, loc, loc+Vector((0,5*GS.scale,0)), 0, headLayer, None, ["OFFS", eye, vec*GS.scale*20])


    def addCombinedGazeBone(self, rig, headLayer, helpLayer):
        leye = self.getEyeBone(rig, "L")
        reye = self.getEyeBone(rig, "R")
        lgaze = rig.data.edit_bones.get("gaze.L")
        rgaze = rig.data.edit_bones.get("gaze.R")
        head = rig.data.edit_bones.get("head")
        uy = GS.scale*Vector((0,1,0))
        if lgaze and rgaze and leye and reye:
            loc = (leye.head + reye.head)/2
            gaze0 = makeBone("gaze0", rig, loc, loc-20*uy, 0, helpLayer, head, head)
            gaze1 = deriveBone("gaze1", gaze0, rig, helpLayer, None)
            gaze = makeBone("gaze", rig, loc-20*uy, loc-10*uy, 0, headLayer, gaze1, head)
            lgaze.parent = gaze
            rgaze.parent = gaze


    def addGazeConstraint(self, rig, suffix):
        def constraintExists(pb, drv):
            if pb.name in self.store.constraints.keys():
                for struct in self.store.constraints[pb.name]:
                    if (struct["type"] == 'COPY_ROTATION' and
                        struct["subtarget"] == drv.name):
                        return True
            return False

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
        gaze0 = rig.pose.bones.get("gaze0")
        gaze1 = rig.pose.bones.get("gaze1")
        gaze = rig.pose.bones.get("gaze")
        head = rig.pose.bones.get("head")
        if gaze0 and gaze1:
            prop = "MhaGazeFollowsHead"
            setMhx(rig, prop, 1.0)
            copyTransform(gaze1, gaze0, rig, prop)
            if gaze and head:
                cns = limitLocation(gaze, rig, prop)
                cns.min_x = cns.min_z = -20*GS.scale
                cns.max_x = cns.max_z = 20*GS.scale
                limitRotation(gaze, rig, prop)
                dampedTrack(gaze, gaze0, rig, prop)

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
        for pb in rig.pose.bones:
            for cns in list(pb.constraints):
                pb.constraints.remove(cns)
            self.tieBone(pb, rig, gen, assoc, facebones, dazRna(rig).DazRig)
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
    #   Display transform bones
    #-------------------------------------------------------------

    def addDisplayTransform(self, rig, headname):
         if self.useDisplayTransform and not BLENDER4:
            from .finger import getGenesis
            mesh = getGenesis(self.meshes)
            if not (mesh and addDisplayTransform(rig, mesh, headname)):
                print ("Failed to add display transform bones")

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
                renameBone(bone, newname)
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
                self.store.storeConstraints(pb.name, pb)
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
        vec = tail-head
        vec /= vec.dot(vec)
        bend = {}
        twist = {}
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = max(0, min(1, vec.dot(v.co - head)))
                    bend[v.index] = g.weight*(1-x)
                    twist[v.index] = g.weight*x
        ob.vertex_groups.remove(vgrp)

        def addGroup(ob, nname, weights):
            ogrp = ob.vertex_groups.get(nname)
            if ogrp:
                ob.vertex_groups.remove(ogrp)
            ngrp = ob.vertex_groups.new(name=nname)
            for vn,w in weights.items():
                if w > 0:
                    ngrp.add([vn], w, 'REPLACE')

        addGroup(ob, bvgname, bend)
        addGroup(ob, tvgname, twist)

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
        for ob in getSelectedObjects(context):
            if ob == rig:
                continue
            if ob.type in ['MESH', 'CURVES']:
                mod = getModifier(ob, 'ARMATURE')
                if mod:
                    subrig = mod.object
                    if subrig and subrig != rig:
                        subrigs[subrig.name] = subrig
                    mod.object = rig
                    if self.useRetarget and ob.data.shape_keys:
                        retargetDrivers(ob.data.shape_keys, subrig, rig, False)
            parent = dazRna(ob).DazParentBone
            if parent:
                from .node import getConvertedBoneName
                bname = getConvertedBoneName(rig, parent)
            elif ob.parent and ob.parent_type == 'BONE':
                bname = ob.parent_bone
            else:
                bname = None
            if bname:
                wmat = ob.matrix_world.copy()
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

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangeArmature,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

