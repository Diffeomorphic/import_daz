# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .utils import *
from .error import *
from .node import Node, Instance
from .driver import DriverUser

#-------------------------------------------------------------
#   FigureInstance
#-------------------------------------------------------------

class FigureInstance(Instance):

    def __init__(self, fileref, node, struct):
        for geo in node.geometries:
            geo.figureInst = self
        Instance.__init__(self, fileref, node, struct)
        self.figure = self
        self.bones = {}
        self.hiddenBones = {}


    def __repr__(self):
        return "<FigureInstance %s %d P: %s R: %s>" % (self.node.name, self.index, self.node.parent, self.rna)

    def buildExtra(self, context):
        pass

    def getRig(self):
        return self.rna

    def postbuild(self, context):
        Instance.postbuild(self, context)
        if LS.fitFile and GS.useArmature:
            self.shiftBones(context, self.rna, self.worldmat.inverted())


    def shiftBones(self, context, rig, mat):
        from .node import isUnitMatrix
        if isUnitMatrix(mat):
            return
        activateObject(context, rig)
        emats = dict([(bone.name, mat@bone.matrix_local.copy())
                       for bone in rig.data.bones])
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            eb.matrix = emats[eb.name]
        setMode('OBJECT')


    def finalize(self, context):
        from .finger import getFingeredCharacters
        from .bone import BoneInstance
        rig,meshes,chars,modded = getFingeredCharacters(self.rna, False)
        if rig and meshes:
            mesh = meshes[0]
            char = chars[0]
            dazRna(rig).DazMesh = char
            for mesh,char in zip(meshes, chars):
                dazRna(mesh).DazMesh = char
            #self.poseChildren(rig, rig)
        elif meshes:
            for mesh,char in zip(meshes, chars):
                dazRna(mesh).DazMesh = char
        if rig:
            inst = self.getConformInstance()
            if inst:
                self.copyParentPose(inst.rna, rig)
        Instance.finalize(self, context)
        if rig:
            for child in self.children.values():
                if isinstance(child, BoneInstance):
                    child.buildFormulas(rig, False)
                enableRigNumLayers(rig, [T_BONES, T_WIDGETS])
            if chars:
                activateObject(context, rig)
                self.selectChildren(rig)
        if self.hiddenBones:
            for geonode in self.geometries:
                geonode.hideFaceGroups(self.hiddenBones.keys())


    def copyParentPose(self, par, rig):
        if rig is None or par is None:
            return
        from .store import ConstraintStore
        store = ConstraintStore()
        for pb in rig.pose.bones:
            if pb.name in par.pose.bones.keys():
                parb = par.pose.bones[pb.name]
                pb.matrix_basis = parb.matrix_basis
                pb.lock_location = parb.lock_location
                pb.lock_rotation = parb.lock_rotation
                pb.lock_scale = parb.lock_scale
                store.storeConstraints(parb.name, parb)
                store.removeConstraints(pb)
                store.restoreConstraints(parb.name, pb)


    def selectChildren(self, rig):
        for child in rig.children:
            if child.type == 'ARMATURE':
                child.select_set(True)
                self.selectChildren(child)


    def poseRig(self, context):
        if not GS.useArmature:
            return
        rig = self.rna
        activateObject(context, rig)
        setMode('OBJECT')
        self.poseArmature(rig)
        dazRna(rig).DazHasRotLocks = GS.useLockRot
        dazRna(rig).DazHasLocLocks = GS.useLockLoc
        dazRna(rig).DazHasRotLimits = GS.useLimitRot
        dazRna(rig).DazHasLocLimits = GS.useLimitLoc
        self.fixDependencyLoops(rig)
        setMode('OBJECT')
        self.loadAltMorphs()
        self.addPointingConstraints(rig)


    def loadAltMorphs(self):
        from .bone import BoneInstance
        from .fileutils import DF
        self.altmorphs = {}
        url = unquote(self.node.id)
        if url.lower() in DF.WidgetControls:
            if (isinstance(self.parent, BoneInstance) and
                isinstance(self.parent.figure, FigureInstance)):
                    fig = unquote(self.parent.figure.node.id)
                    if fig.lower() == "/data/daz 3d/genesis 9/base/genesis9.dsf#genesis9":
                        struct = DF.loadEntry("genesis9", "altmorphs", False)
                        if struct:
                            self.altmorphs = struct["morphs"]


    def poseArmature(self, rig):
        from .bone import BoneInstance
        from .driver import getDrivenBoneFcurves
        tchildren = {}
        missing = []
        self.driven = getDrivenBoneFcurves(rig)
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(self, False, tchildren, missing)
        if missing and GS.verbosity > 2:
            print("Missing bones when posing %s" % self.name)
            print("  %s" % [inst.node.name for inst in missing])


    def fixDependencyLoops(self, rig):
        from .driver import getDrivingBone, getDrivenBoneFcurves
        needfix = {}
        driven = getDrivenBoneFcurves(rig)
        for bname,fcus in driven.items():
            pb = rig.pose.bones[bname]
            for fcu in fcus:
                bname = getDrivingBone(fcu, rig)
                if bname:
                    for child in pb.children:
                        if child.name == bname:
                            needfix[pb.name] = (child.name, fcus)

        if needfix:
            if GS.verbosity > 1:
                print("Fix dependency loops:", list(needfix.keys()))
            setMode('EDIT')
            for bname in needfix.keys():
                cname = needfix[bname][0]
                eb = rig.data.edit_bones[bname]
                cb = rig.data.edit_bones[cname]
                eb.use_connect = False
                cb.use_connect = False
                cb.parent = eb.parent
            setMode('OBJECT')
            for bname in needfix.keys():
                fcus = needfix[bname][1]
                self.clearBendDrivers(fcus)


    def addPointingConstraints(self, rig):
        from .rig_utils import dampedTrack
        for bname,trgname in self.node.pointing.items():
            pb = rig.pose.bones.get(bname)
            trg = rig.pose.bones.get(drvBone(trgname))
            if pb and trg:
                dampedTrack(pb, trg, rig)
            else:
                trg = rig.pose.bones.get(trgname)
                if pb and trg:
                    dampedTrack(pb, trg, rig)


    def clearBendDrivers(self, fcus):
        for fcu in fcus:
            if fcu.array_index != 1:
                fcu.driver.expression = "0"
                for var in fcu.driver.variables:
                    fcu.driver.variables.remove(var)


    def setLSRig(self):
        def isMainFigure(level):
            if self.getConformTarget():
                return False
            par = self.parent
            while (par and
                   not isinstance(par, FigureInstance) and
                   not par.getConformTarget()):
                par = par.parent
            return(par is None)

        if LS.rigname is None or isMainFigure(5):
            LS.rigname = self.name
            LS.rigs[LS.rigname] = []
            LS.meshes[LS.rigname] = []
            LS.objects[LS.rigname] = []
            LS.hairs[LS.rigname] = []
            LS.hdmeshes[LS.rigname] = []

#-------------------------------------------------------------
#   Figure
#-------------------------------------------------------------

class Figure(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.restPose = False
        self.bones = {}
        self.presentation = None
        self.figure = self
        self.pointing = {}


    def __repr__(self):
        return ("<Figure %s %d %s>" % (self.id, self.count, self.instances.keys()))


    def makeInstance(self, fileref, struct):
        return FigureInstance(fileref, self, struct)


    def parse(self, struct):
        Node.parse(self, struct)
        if "presentation" in struct.keys():
            self.presentation = struct["presentation"]


    def build(self, context, inst):
        from .bone import BoneInstance
        from .asset import Asset
        scn = context.scene
        if GS.verbosity >= 4:
            print("Build figure %s" % self.name)
        center = d2b(inst.attributes["center_point"])
        Asset.build(self, context, inst)
        inst.setLSRig()
        for geonode in inst.geometries:
            geonode.buildObject(context, inst, center)
            geonode.rna.location = Zero
        if GS.useArmature:
            amt = self.data = bpy.data.armatures.new(noHDName(inst.name))
            setModernProps(amt)
            self.buildObject(context, inst, center)
            rig = self.rna
            LS.rigs[LS.rigname].append(rig)
            amt.display_type = 'STICK'
            rig.show_in_front = True
            if GS.unflipped:
                dazRna(rig.data).DazUnflipped = True
            dazRna(rig.data).DazHasAxes = True
            dazRna(rig).DazInheritScale = False
        else:
            rig = amt = None
        for geonode in inst.geometries:
            geonode.parent = geonode.figure = self
            geonode.rna.parent = rig
            geonode.addLSMesh(geonode.rna, inst, LS.rigname)
        if not GS.useArmature:
            return
        center = inst.attributes["center_point"]
        activateObject(context, rig)
        setMode('EDIT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(self, inst, rig, None, center, False)
        if self.pointing:
            self.pointBones(rig)
        setMode('OBJECT')
        modernizeBones(rig)
        self.rigtype = getRigType1(inst.bones.keys(), False)
        dazRna(rig).DazRig = dazRna(rig).DazOriginalRig = self.rigtype
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)


    def pointBones(self, rig):
        for bname,trgname in self.pointing.items():
            eb = rig.data.edit_bones.get(bname)
            trg = rig.data.edit_bones.get(trgname)
            if eb and trg:
                eb.tail = (eb.head + trg.head)/2
        for bname,trgname in self.pointing.items():
            if trgname in self.pointing.keys():
                trg = rig.data.edit_bones.get(trgname)
                drv = rig.data.edit_bones.new(drvBone(trgname))
                enableBoneNumLayer(drv, rig, T_HIDDEN)
                drv.head = trg.head
                drv.tail = trg.tail
                drv.roll = trg.roll
                drv.parent = trg.parent
                trg.parent = drv


def getRigType(data, strict):
    if isinstance(data, bpy.types.Object):
        return getRigType1(data.pose.bones.keys(), strict)
    else:
        return getRigType1(data, strict)


def getRigType1(bones, strict):
    def match(tests, bones):
        for test in tests:
            if test not in bones:
                return False
        return True

    strictBones = {
        "genesis12" : ["abdomen", "lShldr", "rThigh", "lMid3", "rMid3", "upperJaw"],
        "genesis38" : ["abdomenLower", "lShldrBend", "rThighTwist", "lMid3", "rMid3", "lSmallToe2_2", "rSmallToe2_2", "lNasolabialLower"],
        "genesis9" : ["spine1", "l_upperarm", "r_thigh", "l_mid3", "r_mid3", "l_midtoe2", "r_midtoe2", "l_nostril"],
        "daz_dog8" : ["lPastern", "lHaunch"],
        "daz_horse3" : ["r_cannon_hind", "l_hoof_fore"],
        "daz_horse2" : ["rCannonHind", "lHoofFore"],
        "daz_big_cat2" : ["lPawHind", "Tail11", "lForeArm"],
    }

    laxBones = {
        "genesis12" : ["abdomen", "lShldr", "rThigh"],
        "genesis38" : ["abdomenLower", "lShldrBend", "rThighTwist"],
        "genesis9" : ["spine1", "l_upperarm", "r_thigh"],
        "daz_dog8" : ["lPastern", "lHaunch"],
        "daz_horse3" : ["r_cannon_hind", "l_hoof_fore"],
        "daz_horse2" : ["rCannonHind", "lHoofFore"],
        "daz_big_cat2" : ["lPawHind", "Tail11", "lForeArm"],
    }

    if strict:
        if match(strictBones["genesis38"], bones):
            return ("genesis3" if "lHeel" in bones else "genesis8")
        elif match(strictBones["genesis12"], bones):
            return ("genesis2" if "lSmallToe1" in bones else "genesis")
        else:
            for key, tests in strictBones.items():
                if match(tests, bones):
                    return key
    else:
        if match(laxBones["genesis38"], bones):
            return ("genesis3" if "lHeel" in bones else "genesis8")
        elif match(laxBones["genesis12"], bones):
            return ("genesis2" if "lSmallToe1" in bones else "genesis")
        else:
            for key, tests in laxBones.items():
                if match(tests, bones):
                    return key
    if "ball.marker.L" in bones:
        return "mhx"
    else:
        return ""


class LegacyFigure(Figure):

    def __init__(self, fileref):
        Figure.__init__(self, fileref)


    def __repr__(self):
        return ("<LegacyFigure %s>" % (self.id))

#-------------------------------------------------------------
#   Add extra face bones
#-------------------------------------------------------------

def copyBoneInfo(srcpb, trgpb, usePoseBone=True):
    modernizeBone(trgpb)
    if usePoseBone:
        for attr in ["rotation_mode", "lock_location", "lock_rotation", "lock_scale"]:
            setattr(trgpb, attr, getattr(srcpb, attr))
    for attr in ["bbone_x", "bbone_z", "use_relative_parent", "use_local_location", "use_inherit_rotation", "inherit_scale"]:
        setattr(trgpb.bone, attr, getattr(srcpb.bone, attr))
    for attr in ["DazRotMode"]:
        setattr(dazRna(trgpb), attr, getattr(dazRna(srcpb), attr))
    for attr in ["DazTrueName"]:
        setattr(dazRna(trgpb.bone), attr, getattr(dazRna(srcpb.bone), attr))
    for attr in ["DazOrient", "DazHead"]:
        setattr(dazRna(trgpb.bone), attr, tuple(getattr(dazRna(srcpb.bone), attr)))
    for attr in ["DazRestRotation", "DazAxes", "DazFlips", "DazLocLocks", "DazRotLocks"]:
        setattr(dazRna(trgpb), attr, tuple(getattr(dazRna(srcpb), attr)))
    for key in ["lock_ik", "ik_stiffness", "use_ik_limit", "ik_min", "ik_max"]:
        for x in ["x", "y", "z"]:
            attr = "%s_%s" % (key, x)
            if hasattr(srcpb, attr):
                setattr(trgpb, attr, getattr(srcpb, attr))


class ExtraBones(DriverUser):
    ignoreLocked : BoolProperty(
        name = "Ignore Locked Location",
        description = "Don't create posable bones for locked location channels",
        default = True)

    errorOnFail : BoolProperty(
        name = "Fail On Error",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "ignoreLocked")

    def run(self, context):
        rig = context.object
        if not self.checkAllowed(rig):
            return
        t1 = perf_counter()
        self.initTmp()
        oldvis = getRigLayers(rig)
        enableAllRigLayers(rig)
        success = False
        self.createTmp()
        try:
            self.addExtraBones(rig)
            success = True
        finally:
            self.deleteTmp()
            setRigLayers(rig, oldvis)
        t2 = perf_counter()
        print("%s completed in %.1f seconds" % (self.button, t2-t1))


    def correctDriver(self, fcu, rig):
        varnames = dict([(var.name,True) for var in fcu.driver.variables])
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.bone_target:
                    self.combineDrvFinBone(fcu, rig, var, trg, varnames)
                if trg.data_path:
                    trg.data_path = self.replaceDataPathDrv(trg.data_path)


    def correctScaleDriver(self, fcu, pb):
        for var in fcu.driver.variables:
            if var.name == "parscale":
                for trg in var.targets:
                    bname = baseBone(trg.bone_target)
                    if bname in self.bnames:
                        trg.bone_target = bname


    def replaceDataPathDrv(self, string):
        words = string.split('"')
        if words[0] == "pose.bones[":
            bname = words[1]
            return string.replace(propRef(bname), propRef(baseBone(bname)))
        return string


    def combineDrvFinBone(self, fcu, rig, var, trg, varnames):
        if trg.transform_type[0:3] == "ROT":
            trg.bone_target = baseBone(trg.bone_target)
        else:
            self.combineDrvSimple(fcu, var, trg, varnames)


    def combineDrvSimple(self, fcu, var, trg, varnames):
        if var.name == "parscale":
            return
        bones = self.getTargetBones(fcu)
        if trg.bone_target in bones:
            return
        from .driver import Target
        vname2 = var.name+"2"
        if vname2 in varnames.keys():
            return
        var2 = fcu.driver.variables.new()
        var2.name = vname2
        var2.type = var.type
        target2 = Target(trg)
        trg2 = var2.targets[0]
        target2.create(trg2)
        trg2.bone_target = baseBone(trg.bone_target)
        expr = fcu.driver.expression.replace(var.name, "(%s+%s)" % (var.name, var2.name))
        fcu.driver.expression = expr


    def addCopyConstraint(self, rig, bname, boneDrivers, sumDrivers):
        if (self.hasBoneDriver(bname, boneDrivers) or
            self.hasBoneDriver(bname, sumDrivers)):
            pb = rig.pose.bones[bname]
            cns = pb.constraints.new('COPY_TRANSFORMS')
            cns.name = "Copy %s" % bname
            cns.target = rig
            cns.subtarget = drvBone(bname)
            cns.target_space = 'LOCAL'
            cns.owner_space = 'LOCAL'
            cns.influence = 1.0
            cns.mix_mode = 'AFTER'


    def hasBoneDriver(self, bname, drivers):
        if bname in drivers.keys():
            for drv in drivers[bname]:
                channel = drv.data_path.rsplit(".",1)[-1]
                if channel in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
                    return True
        return False


    def updateScriptedDrivers(self, rna):
        if rna.animation_data:
            fcus = [fcu for fcu in rna.animation_data.drivers
                    if fcu.driver.type == 'SCRIPTED']
            for fcu in fcus:
                channel = fcu.data_path
                vtargets,btargets = self.getVarBoneTargets(fcu)
                for btarget in btargets:
                    bname = baseBone(btarget[1])
                    if bname and bname in self.bnames and fcu.driver:
                        fcu2 = self.getTmpDriver(0)
                        self.copyFcurve(fcu, fcu2)
                        rna.driver_remove(channel)
                        self.setBoneTarget(fcu2, bname)
                        fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
                        fcu3.data_path = channel
                        self.clearTmpDriver(0)


    def storeRemoveBoneSumDrivers(self, rig):
        def store(fcus, rig):
            from .driver import Driver
            drivers = {}
            for bname in fcus.keys():
                drivers[bname] = []
                for fcu in fcus[bname]:
                    drivers[bname].append(Driver(fcu))
            return drivers

        from .driver import removeDriverFCurves, getAllBoneSumDrivers
        boneFcus, sumFcus = getAllBoneSumDrivers(rig, self.bnames)
        boneDrivers = store(boneFcus, rig)
        sumDrivers = store(sumFcus, rig)
        removeDriverFCurves(boneFcus.values(), rig)
        removeDriverFCurves(sumFcus.values(), rig)
        return boneDrivers, sumDrivers


    def restoreBoneSumDrivers(self, rig, drivers):
        for bname,bdrivers in drivers.items():
            pb = rig.pose.bones[drvBone(bname)]
            for driver in bdrivers:
                fcu = self.getTmpDriver(0)
                driver.fill(fcu)
                if driver.data_path.endswith(".scale"):
                    self.correctScaleDriver(fcu, pb)
                else:
                    self.correctDriver(fcu, rig)
                fcu2 = rig.animation_data.drivers.from_existing(src_driver=fcu)
                fcu2.data_path = driver.data_path.replace(propRef(bname), propRef(drvBone(bname)))
                fcu2.array_index = driver.array_index
                self.clearTmpDriver(0)


    def addExtraBones(self, rig):
        def copyEditBone(db, rig, bname):
            eb = rig.data.edit_bones.new(bname)
            eb.head = db.head
            eb.tail = db.tail
            eb.roll = db.roll
            eb.use_deform = db.use_deform
            return eb


        def copyPoseBone(db, pb, rig):
            modernizeBone(pb)
            copyBoneLayers(db.bone, pb.bone, rig)
            enableBoneNumLayer(db.bone, rig, T_HIDDEN)
            pb.rotation_mode = db.rotation_mode
            pb.lock_location = db.lock_location
            pb.lock_rotation = db.lock_rotation
            pb.lock_scale = db.lock_scale
            pb.custom_shape = db.custom_shape
            if hasattr(pb, "custom_shape_scale"):
                pb.custom_shape_scale = db.custom_shape_scale
            else:
                pb.custom_shape_scale_xyz = db.custom_shape_scale_xyz
            dazRna(pb).DazRotLocks = dazRna(db).DazRotLocks
            dazRna(pb).DazLocLocks = dazRna(db).DazLocLocks
            dazRna(pb.bone).DazRigIndex = dazRna(db.bone).DazRigIndex
            dazRna(pb.bone).DazBoneParentRig = dazRna(db.bone).DazBoneParentRig
            pb.bone.inherit_scale = db.bone.inherit_scale

        from .driver import getShapekeyDriver
        from .store import ConstraintStore
        if getattr(dazRna(rig.data), self.attr):
            msg = "Rig %s already has extra %s bones" % (rig.name, self.type)
            print(msg)

        if not ES.easy:
            print("  Rename bones")
        self.bnames = self.getBoneNames(rig)
        self.removeLimits(rig)
        boneDrivers, sumDrivers = self.storeRemoveBoneSumDrivers(rig)
        setMode('EDIT')
        for bname in self.bnames:
            eb = rig.data.edit_bones[bname]
            eb.name = drvBone(bname)

        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            eb = copyEditBone(db, rig, bname)
            eb.parent = db.parent
            db.use_deform = False
            self.changeLayer(eb, rig)
        setMode('OBJECT')

        for bname in self.bnames:
            if (bname not in rig.pose.bones.keys() or
                drvBone(bname) not in rig.pose.bones.keys()):
                pass
            else:
                bone = rig.data.bones[bname]
                db = rig.data.bones[drvBone(bname)]
                bone["DazExtraBone"] = db.get("DazExtraBone", False)

        setMode('EDIT')
        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            for cb in db.children:
                if cb.name != bname:
                    cb.parent = rig.data.edit_bones[bname]

        if not ES.easy:
            print("  Change constraints")
        setMode('OBJECT')
        store = ConstraintStore()
        for bname in self.bnames:
            pb = rig.pose.bones[bname]
            db = rig.pose.bones[drvBone(bname)]
            copyPoseBone(db, pb, rig)
            db.custom_shape = None
            copyBoneInfo(db, pb)
            store.storeConstraints(db.name, db)
            store.removeConstraints(db, onlyLimit=True)
            self.addCopyConstraint(rig, bname, boneDrivers, sumDrivers)
            store.restoreConstraints(db.name, pb)
        for pb in rig.pose.bones:
            if not isDrvBone(pb.name):
                for cns in pb.constraints:
                    if (hasattr(cns, "subtarget") and
                        isDrvBone(cns.subtarget) and
                        drvBone(pb.name) != cns.subtarget):
                        cns.subtarget = baseBone(cns.subtarget)

        if not ES.easy:
            print("  Restore bone drivers")
        self.restoreBoneSumDrivers(rig, boneDrivers)
        if not ES.easy:
            print("  Restore sum drivers")
        self.restoreBoneSumDrivers(rig, sumDrivers)
        if not ES.easy:
            print("  Update scripted drivers")
        self.updateScriptedDrivers(rig.data)
        if not ES.easy:
            print("  Update drivers")
        setattr(dazRna(rig.data), self.attr, True)
        updateDrivers(rig)

        if not ES.easy:
            print("  Update vertex groups")
        setMode('OBJECT')
        for ob in rig.children:
            if ob.parent_type == 'BONE' and isDrvBone(ob.parent_bone):
                bname = baseBone(ob.parent_bone)
                if bname in self.bnames:
                    wmat = ob.matrix_world.copy()
                    ob.parent_bone = bname
                    setWorldMatrix(ob, wmat)
            if ob.type == 'MESH':
                for vgrp in ob.vertex_groups:
                    if isDrvBone(vgrp.name):
                        vgname = baseBone(vgrp.name)
                        if vgname in self.bnames:
                            vgrp.name = vgname
                skeys = ob.data.shape_keys
                if skeys:
                    for skey in skeys.key_blocks[1:]:
                        fcu = getShapekeyDriver(skeys, skey.name)
                        if fcu:
                            self.correctDriver(fcu, rig)
                    updateDrivers(ob)

        fcurves = getRnaFcurves(rig)
        for fcu in fcurves:
            if fcu.group and "(drv)" in fcu.group.name:
                fcu.group.name = fcu.group.name.replace("(drv)", "")
            if (fcu.data_path.startswith("pose.bones[") and
                "(drv)" in fcu.data_path):
                fcu.data_path = fcu.data_path.replace("(drv)", "")

        for pb in rig.pose.bones:
            if isDrvBone(pb.name):
                pb.matrix_basis = Matrix()


    def removeLimits(self, rig):
        for bname in self.bnames:
            pb = rig.pose.bones[bname]
            for cns in list(pb.constraints):
                if cns.type in ['LIMIT_LOCATION', 'LIMIT_ROTATION', 'LIMIT_SCALE']:
                    for channel in ["min_x", "min_y", "min_z", "max_x", "max_y", "max_z"]:
                        cns.driver_remove(channel)


class DAZ_OT_MakeAllBonesPosable(CollectionShower, DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.make_all_bones_posable"
    bl_label = "Make All Bones Posable"
    bl_description = "Add an extra layer of driven bones, to make them posable"
    bl_options = {'UNDO'}

    type =  "driven"
    attr = "DazExtraDrivenBones"
    button = "Make All Bones Posable"

    def getBoneNames(self, rig):
        from .driver import getDrivenBoneFcurves
        exclude = ["lMetatarsals", "rMetatarsals", "l_metatarsal", "r_metatarsal"]
        driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
        bnames = {}
        for pb in rig.pose.bones:
            if (pb.name in driven.keys() and
                not isDrvBone(pb.name) and
                drvBone(pb.name) not in rig.pose.bones.keys() and
                pb.name not in exclude and
                not isErcBone(pb.name)):
                if self.ignoreLocked and isLocationLocked(pb):
                    for fcu in driven[pb.name]:
                        bname,channel,cnsname = getBoneChannel(fcu)
                        if channel != "location" and cnsname is None:
                            bnames[pb.name] = True
                            break
                else:
                    bnames[pb.name] = True
        return bnames


    def checkAllowed(self, rig):
        if dazRna(rig).DazRig.startswith(("mhx", "rigify")):
            msg = "Rig type = %s" % dazRna(rig).DazRig
        elif rig.get("DazSimpleIK"):
            msg = "Rig has simple IK"
        elif dazRna(rig.data).DazFinalized:
            msg = "Rig has been finalized"
        else:
            return True
        msg = "Cannot make bones posable.     \n%s" % msg
        print(msg)
        if self.errorOnFail:
            raise DazError(msg)
        else:
            return False


    def changeLayer(self, eb, rig):
        pass

    def hasBoneDriver(self, bname, drivers):
        return True

#-------------------------------------------------------------
#   Finalize bones
#-------------------------------------------------------------

def finalizeArmature(context, rig):
    from .driver import getDrivenBoneFcurves
    extras = ExtraBones()
    drivers = getDrivenBoneFcurves(rig, useRigifySafe=True)
    for pb in rig.pose.bones:
        if not isDrvBone(pb.name):
            drvname = drvBone(pb.name)
            db = rig.pose.bones.get(drvname)
            if db and drvname not in drivers.keys():
                for cns in pb.constraints:
                    if cns.type == 'COPY_TRANSFORMS' and cns.subtarget == drvname:
                        pb.constraints.remove(cns)
                        break

    def fixLickalicious(rig):
        for bone in list(rig.data.bones):
            if bone.name.startswith("tongue"):
                bone.name = bone.name.replace("tongue", "tgn")
                enableBoneNumLayer(bone, rig, T_HIDDEN)
        for ob in getMeshChildren(rig):
            for vgrp in list(ob.vertex_groups):
                if vgrp.name.startswith("tongue"):
                    vgrp.name = vgrp.name.replace("tongue", "tgn")

        from .merge_rigs import mergeBones, mergeVertexGroups
        setMode('EDIT')
        eb1 = rig.data.edit_bones.get("lmtongue08")
        eb2 = rig.data.edit_bones.get("rtongue08")
        if eb1 and eb2:
            eb1.name = "mtongue08"
            eb1.tail = (eb1.tail + eb2.tail)/2
            setMode('OBJECT')
            bones = {"mtongue08" : ["rtongue08"]}
            mergeBones(rig, bones, {}, context)
            mergeVertexGroups(rig, bones)


    if "mtongue07" in rig.data.bones.keys():
        fixLickalicious(rig)

    dazRna(rig.data).DazFinalized = True



class DAZ_OT_FinalizeArmature(DazOperator, IsArmature):
    bl_idname = "daz.finalize_armature"
    bl_label = "Finalize Armature"
    bl_description = "Remove unused bone constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        finalizeArmature(context, rig)

#----------------------------------------------------------
#   Toggle Inherit Scale
#----------------------------------------------------------

def toggleInheritScale(self, context):
    inherits = ('FULL' if self.DazInheritScale else 'NONE')
    for bone in self.data.bones:
        bone.inherit_scale = inherits

#-------------------------------------------------------------
#   Morph armature
#-------------------------------------------------------------

class DAZ_OT_MorphArmature(DazOperator, IsArmature):
    bl_idname = "daz.morph_armature"
    bl_label = "Morph Armature"
    bl_description = "Update the armature for ERC morphs"

    def run(self, context):
        rig = context.object
        if dazRna(rig.data).DazHasErcBones:
            from .rig_utils import morphErcArmature
            morphErcArmature(rig)
        else:
            from .runtime.morph_armature import getEditBones, morphArmature
            mode = rig.mode
            data = getEditBones(rig)
            setMode('EDIT')
            morphArmature(data)
            setMode(mode)

#-------------------------------------------------------------
#   For debugging
#-------------------------------------------------------------

class DAZ_OT_InspectWorldMatrix(DazOperator, IsObject):
    bl_idname = "daz.inspect_world_matrix"
    bl_label = "Inspect World Matrix"
    bl_description = "List world matrix of active object"

    def run(self, context):
        ob = context.object
        print("World Matrix", ob.name)
        print(ob.matrix_world)
        rig = ob.parent
        if rig and ob.parent_type == 'BONE':
            pb = rig.pose.bones[ob.parent_bone]
            print("Inverse Parent Matrix", pb.name)
            print(pb.matrix.inverted())
            print(ob.matrix_parent_inverse)


class DAZ_OT_EnableAllLayers(DazOperator, IsArmature):
    bl_idname = "daz.enable_all_layers"
    bl_label = "Enable All Layers"
    bl_description = "Enable all bone layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        enableAllRigLayers(rig)
        for bone in rig.data.bones:
            bone.hide_select = False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeAllBonesPosable,
    DAZ_OT_FinalizeArmature,
    DAZ_OT_MorphArmature,
    DAZ_OT_InspectWorldMatrix,
    DAZ_OT_EnableAllLayers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
