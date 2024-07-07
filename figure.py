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
from .node import Node, Instance
from .driver import DriverUser, getDrivenBoneFcurves

#-------------------------------------------------------------
#   FigureInstance
#-------------------------------------------------------------

class FigureInstance(Instance):

    def __init__(self, fileref, node, struct):
        for geo in node.geometries:
            geo.figureInst = self
        Instance.__init__(self, fileref, node, struct)
        self.figure = self
        self.planes = {}
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
        headtails = dict([(b.name, (mat@b.head_local, mat@b.tail_local)) for b in rig.data.bones])
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            eb.head, eb.tail = headtails[eb.name]
        setMode('OBJECT')


    def finalize(self, context):
        from .finger import getFingeredCharacters
        rig,meshes,chars,modded = getFingeredCharacters(self.rna, False)
        if rig and meshes:
            mesh = meshes[0]
            char = chars[0]
            rig.DazMesh = char
            for mesh,char in zip(meshes, chars):
                mesh.DazMesh = char
            self.poseChildren(rig, rig)
        elif meshes:
            for mesh,char in zip(meshes, chars):
                mesh.DazMesh = char
        Instance.finalize(self, context)
        if rig:
            enableRigNumLayers(rig, [T_BONES, T_WIDGETS])
            if chars:
                activateObject(context, rig)
                self.selectChildren(rig)
        if self.hiddenBones:
            for geonode in self.geometries:
                geonode.hideVertexGroups(self.hiddenBones.keys())


    def poseChildren(self, ob, rig):
        from .fix import ConstraintStore
        store = ConstraintStore()
        for child in ob.children:
            if child.type == 'ARMATURE':
                for pb in child.pose.bones:
                    if pb.name in rig.pose.bones.keys():
                        parb = rig.pose.bones[pb.name]
                        pb.matrix_basis = parb.matrix_basis
                        pb.lock_location = parb.lock_location
                        pb.lock_rotation = parb.lock_rotation
                        pb.lock_scale = parb.lock_scale
                        store.storeConstraints(parb.name, parb)
                        store.removeConstraints(pb)
                        store.restoreConstraints(parb.name, pb)
                self.poseChildren(child, rig)


    def selectChildren(self, rig):
        for child in rig.children:
            if child.type == 'ARMATURE':
                child.select_set(True)
                self.selectChildren(child)


    def poseRig(self, context):
        if not GS.useArmature:
            return
        from .bone import BoneInstance
        rig = self.rna
        activateObject(context, rig)
        setMode('OBJECT')
        self.poseArmature(rig)
        rig.DazRotLocks = rig.DazHasRotLocks = GS.useLockRot
        rig.DazLocLocks = rig.DazHasLocLocks = GS.useLockLoc
        rig.DazRotLimits = rig.DazHasRotLimits = GS.useLimitRot
        rig.DazLocLimits = rig.DazHasLocLimits = GS.useLimitLoc
        self.fixDependencyLoops(rig)
        setMode('OBJECT')
        self.loadAltMorphs()
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, False)
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
        from .driver import getDrivingBone
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
        from .mhx import dampedTrack
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
        if LS.rigname is None or self.isMainFigure(5):
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
            amt = self.data = bpy.data.armatures.new(inst.name)
            self.buildObject(context, inst, center)
            rig = self.rna
            LS.rigs[LS.rigname].append(rig)
            amt.display_type = 'STICK'
            rig.show_in_front = True
            if GS.unflipped:
                rig.data["DazUnflipped"] = True
            rig.data["DazHasAxes"] = True
            rig.DazInheritScale = False
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
        rig.DazRig = self.rigtype = getRigType1(inst.bones.keys(), False)
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
    }

    laxBones = {
        "genesis12" : ["abdomen", "lShldr", "rThigh"],
        "genesis38" : ["abdomenLower", "lShldrBend", "rThighTwist"],
        "genesis9" : ["spine1", "l_upperarm", "r_thigh"],
    }

    if strict:
        if match(strictBones["genesis38"], bones):
            return ("genesis3" if "lHeel" in bones else "genesis8")
        elif match(strictBones["genesis12"], bones):
            return ("genesis2" if "lSmallToe1" in bones else "genesis")
        elif match(strictBones["genesis9"], bones):
            return "genesis9"
    else:
        if match(laxBones["genesis38"], bones):
            return ("genesis3" if "lHeel" in bones else "genesis8")
        elif match(laxBones["genesis12"], bones):
            return ("genesis2" if "lSmallToe1" in bones else "genesis")
        elif match(laxBones["genesis9"], bones):
            return "genesis9"
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
#   Print bone matrix
#-------------------------------------------------------------

class DAZ_OT_PrintMatrix(DazOperator, IsArmature):
    bl_idname = "daz.print_matrix"
    bl_label = "Print Bone Matrix"
    bl_options = {'UNDO'}

    def run(self, context):
        pb = context.active_pose_bone
        print(pb.name)
        mat = pb.bone.matrix_local
        euler = mat.to_3x3().to_euler('XYZ')
        print(euler)
        print(Vector(euler)/D)
        print(mat)


class DAZ_OT_RotateBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.rotate_bones"
    bl_label = "Rotate Bones"
    bl_description = "Rotate selected bones the same angle"
    bl_options = {'UNDO'}

    X : FloatProperty(name = "X")
    Y : FloatProperty(name = "Y")
    Z : FloatProperty(name = "Z")

    def draw(self, context):
        self.layout.prop(self, "X")
        self.layout.prop(self, "Y")
        self.layout.prop(self, "Z")

    def run(self, context):
        rig = context.object
        rot = Vector((self.X, self.Y, self.Z))*D
        quat = Euler(rot).to_quaternion()
        for pb in rig.pose.bones:
            if pb.bone.select:
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_quaternion = quat
                else:
                    pb.rotation_euler = rot

#-------------------------------------------------------------
#   Add extra face bones
#-------------------------------------------------------------

def copyBoneInfo(srcpb, trgpb):
    for attr in ["rotation_mode", "lock_location", "lock_rotation", "lock_scale", "DazRotMode"]:
        setattr(trgpb, attr, getattr(srcpb, attr))
    for attr in ["bbone_x", "bbone_z", "use_relative_parent", "use_local_location", "use_inherit_rotation", "inherit_scale", "DazAngle"]:
        setattr(trgpb.bone, attr, getattr(srcpb.bone, attr))
    for attr in ["DazOrient", "DazHead", "DazNormal"]:
        setattr(trgpb.bone, attr, tuple(getattr(srcpb.bone, attr)))
    for key in ["DazRigIndex", "DazTrueName"]:
        if key in srcpb.bone.keys():
            trgpb.bone[key] = srcpb.bone[key]
    for attr in ["DazRestRotation", "DazAxes", "DazFlips", "DazLocLocks", "DazRotLocks"]:
        setattr(trgpb, attr, tuple(getattr(srcpb, attr)))
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
                    drivers[bname].append(Driver(fcu, True))
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
            pb.DazRotLocks = db.DazRotLocks
            pb.DazLocLocks = db.DazLocLocks
            pb.bone.inherit_scale = db.bone.inherit_scale


        from .driver import getShapekeyDriver
        from .fix import ConstraintStore
        if getattr(rig.data, self.attr):
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
        setMode('OBJECT')

        setMode('EDIT')
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
                if "DazExtraBone" in db.keys():
                    bone["DazExtraBone"] = db["DazExtraBone"]

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
        setattr(rig.data, self.attr, True)
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

        if rig.animation_data and rig.animation_data.action:
            for fcu in rig.animation_data.action.fcurves:
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


class DAZ_OT_SetAddExtraFaceBones(DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.add_extra_face_bones"
    bl_label = "Add Extra Face Bones"
    bl_description = "Add an extra layer of face bones, which can be both driven and posed"
    bl_options = {'UNDO'}

    type =  "face"
    attr = "DazExtraFaceBones"
    button = "Add Extra Face Bones"

    def getBoneNames(self, rig):
        inface = [
            "lEye", "rEye", "eye.L", "eye.R",
            "lowerJaw", "upperTeeth", "lowerTeeth", "lowerFaceRig",
            "tongue01", "tongue02", "tongue03", "tongue04",
            "tongue05", "tongue06", "tongueBase", "tongueTip",
        ]
        keys = rig.pose.bones.keys()
        bnames = [bname for bname in inface
                  if bname in keys and
                    drvBone(bname) not in keys]
        bnames += getAnchoredBoneNames(rig, ["upperFaceRig", "lowerFaceRig"])
        return bnames

    def checkAllowed(self, rig):
        return True

    def changeLayer(self, eb, rig):
        if rig.DazRig == "mhx":
            enableBoneNumLayer(eb, rig, L_FACE)
        elif rig.DazRig.startswith("rigify"):
            from .layers import R_DETAIL
            enableBoneNumLayer(eb, rig, R_DETAIL)

    def hasBoneDriver(self, bname, drivers):
        return True


def getAnchoredBoneNames(rig, anchors):
    bnames = []
    keys = rig.pose.bones.keys()
    for anchor in anchors:
        if anchor in keys:
            for pb in rig.pose.bones:
                if (not isDrvBone(pb.name) and
                    drvBone(pb.name) not in keys and
                    pb.parent and
                    pb.parent.name == anchor):
                    bnames.append(pb.name)
    return bnames


class DAZ_OT_MakeAllBonesPosable(DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.make_all_bones_posable"
    bl_label = "Make All Bones Posable"
    bl_description = "Add an extra layer of driven bones, to make them posable"
    bl_options = {'UNDO'}

    type =  "driven"
    attr = "DazExtraDrivenBones"
    button = "Make All Bones Posable"

    def getBoneNames(self, rig):
        exclude = ["lMetatarsals", "rMetatarsals", "l_metatarsal", "r_metatarsal"]
        driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
        bnames = {}
        for pb in rig.pose.bones:
            if (pb.name in driven.keys() and
                not isDrvBone(pb.name) and
                drvBone(pb.name) not in rig.pose.bones.keys() and
                pb.name not in exclude):
                if self.ignoreLocked and isLocationLocked(pb):
                    for fcu in driven[pb.name]:
                        bname,channel = getBoneChannel(fcu)
                        if channel != "location":
                            bnames[pb.name] = True
                            break
                else:
                    bnames[pb.name] = True
        return bnames


    def checkAllowed(self, rig):
        if rig.DazRig.startswith(("mhx", "rigify")):
            msg = "Rig type = %s" % rig.DazRig
        elif rig.DazSimpleIK:
            msg = "Rig has simple IK"
        elif rig.data.DazFinalized:
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

#----------------------------------------------------------
#   Remove Driven Bones
#----------------------------------------------------------

class DAZ_OT_RemoveDrivenBones(DazOperator, IsArmature):
    bl_idname = "daz.remove_driven_bones"
    bl_label = "Remove Driven Bones"
    bl_description = "Remove driven (drv) bones and drive the posable bones.\nThis undoes Make All Bones Posable"
    bl_options = {'UNDO'}

    def run(self, context):
        from .bone_data import BD
        rig = context.object
        if rig.animation_data:
            for fcu in list(rig.animation_data.drivers):
                bname,channel = getBoneChannel(fcu)
                if bname and isDrvBone(bname):
                    fcu.data_path = fcu.data_path.replace("(drv)", "")
        for pb in rig.pose.bones:
            for cns in list(pb.constraints):
                if (cns.type in ['COPY_TRANSFORMS', 'COPY_ROTATION'] and
                    isDrvBone(cns.subtarget)):
                    pb.constraints.remove(cns)
        setMode('EDIT')
        for eb in list(rig.data.edit_bones):
            if isDrvBone(eb.name):
                rig.data.edit_bones.remove(eb)
        setMode('OBJECT')

#-------------------------------------------------------------
#   Fix legacy posable bones
#-------------------------------------------------------------

class DAZ_OT_FixLegacyPosable(DazOperator, ExtraBones, IsArmature):
    bl_idname = "daz.fix_legacy_posable"
    bl_label = "Fix Legacy Posable Bones"
    bl_description = "Convert legacy posable bones to modern ones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        if isFinal(trg.bone_target):
                            trg.bone_target = baseBone(trg.bone_target)
        parents = {}
        setMode('EDIT')
        for eb in list(rig.data.edit_bones):
            par = eb.parent
            if par and isDrvBone(par.name):
                eb.parent = par.parent
                parents[eb.name] = par.name
            if isFinal(eb.name):
                rig.data.edit_bones.remove(eb)
        setMode('OBJECT')
        for bname in parents.keys():
            self.addCopyConstraint(rig, bname, [], [])


    def hasBoneDriver(self, bname, drivers):
        return True

#-------------------------------------------------------------
#   Finalize bones
#-------------------------------------------------------------

def finalizeArmature(rig):
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
    rig.data.DazFinalized = True


class DAZ_OT_FinalizeArmature(DazOperator, IsArmature):
    bl_idname = "daz.finalize_armature"
    bl_label = "Finalize Armature"
    bl_description = "Remove unused bone constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        finalizeArmature(rig)

#-------------------------------------------------------------
#   Toggle locks and constraints
#-------------------------------------------------------------

def getRnaName(string):
    if len(string) > 4 and string[-4] == ".":
        return string[:-4]
    else:
        return string

#----------------------------------------------------------
#   Toggle locks
#----------------------------------------------------------

def toggleLocks(self, context, attr, lock):
    if getattr(self, attr):
        for pb in self.pose.bones:
            setattr(pb, lock, getattr(pb, attr))
    else:
        for pb in self.pose.bones:
            setattr(pb, lock, FFalse)

def toggleRotLocks(self, context):
    toggleLocks(self, context, "DazRotLocks", "lock_rotation")

def toggleLocLocks(self, context):
    toggleLocks(self, context, "DazLocLocks", "lock_location")

#----------------------------------------------------------
#   Toggle Limits
#----------------------------------------------------------

def toggleLimits(rig, context, attr, type, exclude):
    auto = context.scene.tool_settings.use_keyframe_insert_auto
    driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
    for pb in rig.pose.bones:
        if pb.name in driven.keys():
            continue
        for cns in pb.constraints:
            if cns.type == type and cns.name not in exclude:
                cns.mute = False
                cns.influence = getattr(rig, attr)
                if auto:
                    cns.keyframe_insert("influence")

def toggleRotLimits(rig, context):
    exclude = ["Hint"] if rig.DazRig == "mhx" else []
    toggleLimits(rig, context, "DazRotLimits", "LIMIT_ROTATION", exclude)

def toggleLocLimits(rig, context):
    toggleLimits(rig, context, "DazLocLimits", "LIMIT_LOCATION", [])


class LockEnabler:
    def run(self, context):
        rig = getRigFromContext(context)
        exclude = ["Hint"] if rig.DazRig == "mhx" else []
        driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
        rig.DazLocLocks = self.lock
        rig.DazRotLocks = self.lock
        rig.DazLocLimits = self.limit
        rig.DazRotLimits = self.limit
        for pb in rig.pose.bones:
            if pb.name in driven.keys():
                continue
            self.setLocks(pb)
            for cns in pb.constraints:
                if cns.type == 'LIMIT_LOCATION':
                    cns.influence = self.limit
                elif cns.type == 'LIMIT_ROTATION' and cns.name not in exclude:
                    cns.influence = self.limit


class DAZ_OT_EnableLocksLimits(DazOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.enable_locks_limits"
    bl_label = "Enable Locks And Limits"
    bl_description = "Enable locks and limits"

    lock = True
    limit = 1.0

    def setLocks(self, pb):
        pb.lock_location = pb.DazLocLocks
        pb.lock_rotation = pb.DazRotLocks


class DAZ_OT_DisableLocksLimits(DazOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.disable_locks_limits"
    bl_label = "Disable Locks And Limits"
    bl_description = "Disable locks and limits"

    lock = False
    limit = 0.0

    def setLocks(self, pb):
        pb.lock_location = pb.lock_rotation = FFalse

#----------------------------------------------------------
#   Toggle Inherit Scale
#----------------------------------------------------------

def toggleInheritScale(self, context):
    inherits = ('FULL' if self.DazInheritScale else 'NONE')
    for bone in self.data.bones:
        bone.inherit_scale = inherits

#----------------------------------------------------------
#   Toggle Morph Armature
#----------------------------------------------------------

def toggleMorphArmatures(self, context):
    GS.toggleMorphArmatures(context.scene)

#-------------------------------------------------------------
#   Morph armature
#-------------------------------------------------------------

class DAZ_OT_MorphArmature(DazOperator, IsArmature):
    bl_idname = "daz.morph_armature"
    bl_label = "Morph Armature"
    bl_description = "Update the armature for ERC morphs"

    def run(self, context):
        from .runtime.morph_armature import getEditBones, morphArmature
        rig = context.object
        mode = rig.mode
        data = getEditBones(rig)
        bpy.ops.object.mode_set(mode='EDIT')
        morphArmature(data)
        bpy.ops.object.mode_set(mode=mode)

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
    DAZ_OT_PrintMatrix,
    DAZ_OT_RotateBones,
    DAZ_OT_SetAddExtraFaceBones,
    DAZ_OT_MakeAllBonesPosable,
    DAZ_OT_RemoveDrivenBones,
    DAZ_OT_FixLegacyPosable,
    DAZ_OT_FinalizeArmature,
    DAZ_OT_EnableLocksLimits,
    DAZ_OT_DisableLocksLimits,
    DAZ_OT_MorphArmature,
    DAZ_OT_InspectWorldMatrix,
    DAZ_OT_EnableAllLayers,
]

def register():
    from .propgroups import DazStringGroup

    bpy.types.Object.DazRotLocks = BoolPropOVR(
        name = "Rotation Locks",
        description = "Rotation Locks",
        default = True,
        update = toggleRotLocks)

    bpy.types.Object.DazLocLocks = BoolPropOVR(
        name = "Location Locks",
        description = "Location Locks",
        default = True,
        update = toggleLocLocks)

    bpy.types.Object.DazRotLimits = FloatPropOVR(1.0,
        name = "Rotation Limits",
        description = "Rotation Limits",
        min = 0.0, max = 1.0,
        update = toggleRotLimits)

    bpy.types.Object.DazLocLimits = FloatPropOVR(1.0,
        name = "Location Limits",
        description = "Location Limits",
        min = 0.0, max = 1.0,
        update = toggleLocLimits)

    bpy.types.Object.DazInheritScale = BoolPropOVR(
        name = "Inherit Scale",
        description = "Bones inherit scale",
        default = True,
        update = toggleInheritScale)

    bpy.types.Scene.DazAutoMorphArmatures = BoolProperty(
        name = "Auto Morph Armatures",
        description = "Automatically morph armatures on frame change",
        default = False,
        update = toggleMorphArmatures)

    bpy.types.Armature.DazBoneMap = CollectionProperty(type=DazStringGroup)


    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
