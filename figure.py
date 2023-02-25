# Copyright (c) 2016-2022, Thomas Larsson
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
        self.planes = {}
        self.bones = {}
        self.hiddenBones = {}


    def __repr__(self):
        return "<FigureInstance %s %d P: %s R: %s>" % (self.node.name, self.index, self.node.parent, self.rna)


    def buildExtra(self, context):
        pass


    def postbuild(self, context):
        Instance.postbuild(self, context)
        if LS.fitFile and LS.useArmature:
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
            if (char.startswith("Genesis") and
                mesh.name in [self.name, "%s.001" % self.name]):
                mesh.name = "%s Mesh" % self.name
            for mesh,char in zip(meshes, chars):
                mesh.DazMesh = char
            self.poseChildren(rig, rig)
        elif meshes:
            for mesh,char in zip(meshes, chars):
                mesh.DazMesh = char
        self.rna.name = self.name
        Instance.finalize(self, context)
        if rig and chars:
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
        if not LS.useArmature:
            return
        from .bone import BoneInstance
        rig = self.rna
        activateObject(context, rig)
        setMode('POSE')
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


    def loadAltMorphs(self):
        from .bone import BoneInstance
        from .fileutils import AF
        self.altmorphs = {}
        url = unquote(self.node.id)
        if url.lower() in AF.FaceControls:
            if (isinstance(self.parent, BoneInstance) and
                isinstance(self.parent.figure, FigureInstance)):
                    fig = unquote(self.parent.figure.node.id)
                    if fig.lower() == "/data/daz 3d/genesis 9/base/genesis9.dsf#genesis9":
                        struct = AF.loadEntry("genesis9", "altmorphs", False)
                        if struct:
                            self.altmorphs = struct["morphs"]


    def poseArmature(self, rig):
        from .bone import BoneInstance
        tchildren = {}
        missing = []
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(self, False, tchildren, missing)
        if missing and GS.verbosity > 2:
            print("Missing bones when posing %s" % self.name)
            print("  %s" % [inst.node.name for inst in missing])


    def fixDependencyLoops(self, rig):
        from .driver import getBoneDrivers, getDrivingBone
        needfix = {}
        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
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
            setMode('POSE')
            for bname in needfix.keys():
                fcus = needfix[bname][1]
                self.clearBendDrivers(fcus)


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


    def __repr__(self):
        return ("<Figure %s %d %s>" % (self.id, self.count, self.rna))


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

        center = d2b(inst.attributes["center_point"])
        Asset.build(self, context, inst)
        inst.setLSRig()
        for geonode in inst.geometries:
            geonode.buildObject(context, inst, center)
            geonode.rna.location = Zero
        if LS.useArmature:
            amt = self.data = bpy.data.armatures.new(inst.name)
            self.buildObject(context, inst, center)
            rig = self.rna
            LS.rigs[LS.rigname].append(rig)
            amt.display_type = 'STICK'
            rig.show_in_front = True
            rig.data.DazUnflipped = GS.unflipped
            rig.DazInheritScale = False
        else:
            rig = amt = None
        for geonode in inst.geometries:
            geonode.parent = geonode.figure = self
            geonode.rna.parent = rig
            geonode.addLSMesh(geonode.rna, inst, LS.rigname)
        if not LS.useArmature:
            return
        center = inst.attributes["center_point"]
        activateObject(context, rig)
        setMode('EDIT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(self, inst, rig, None, center, False)
        setMode('OBJECT')
        rig.DazRig = self.rigtype = getRigType1(inst.bones.keys(), True)
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)


def getModifierPath(moddir, folder, tfile):
    try:
        files = list(os.listdir(moddir+folder))
    except FileNotFoundError:
        files = []
    for file in files:
        file = tolower(file)
        if file == tfile:
            return folder+"/"+tfile
        elif os.path.isdir(moddir+folder+"/"+file):
            path = getModifierPath(moddir, folder+"/"+file, tfile)
            if path:
                return path
    return None


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
        "genesis12" : ["abdomen", "lShldr", "lMid3", "rMid3", "upperJaw"],
        "genesis38" : ["abdomenLower", "lShldrBend", "lMid3", "rMid3", "lSmallToe2_2", "rSmallToe2_2", "lNasolabialLower"],
        "genesis9" : ["spine1", "l_upperarm", "l_mid3", "r_mid3", "l_midtoe2", "r_midtoe2", "l_nostril"],
    }

    laxBones = {
        "genesis12" : ["abdomen", "lShldr"],
        "genesis38" : ["abdomenLower", "lShldrBend"],
        "genesis9" : ["spine1", "l_upperarm"],
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
    trgpb.rotation_mode = srcpb.rotation_mode
    trgpb.lock_location = srcpb.lock_location
    trgpb.lock_rotation = srcpb.lock_rotation
    trgpb.lock_scale = srcpb.lock_scale
    trgpb.bone.DazOrient = Vector(srcpb.bone.DazOrient)
    trgpb.bone.DazHead = Vector(srcpb.bone.DazHead)
    trgpb.bone.DazTail = Vector(srcpb.bone.DazTail)
    trgpb.bone.DazAngle = srcpb.bone.DazAngle
    trgpb.bone.DazNormal = Vector(srcpb.bone.DazNormal)
    trgpb.DazRotMode = srcpb.DazRotMode
    #if "DazAltName" in srcpb.keys():
    #    trgpb.DazAltName = srcpb.DazAltName
    for key in ["lock_ik", "ik_stiffness", "use_ik_limit", "ik_min", "ik_max"]:
        for x in ["x", "y", "z"]:
            attr = "%s_%s" % (key, x)
            if hasattr(srcpb, attr):
                setattr(trgpb, attr, getattr(srcpb, attr))


class ExtraBones(DriverUser):

    def run(self, context):
        from time import perf_counter
        rig = context.object
        self.checkAllowed(rig)
        t1 = perf_counter()
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        self.createTmp()
        try:
            self.addExtraBones(rig)
            success = True
        finally:
            self.deleteTmp()
            rig.data.layers = oldvis
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
        def addFields(cns, rig, bname):
            cns.target = rig
            cns.subtarget = drvBone(bname)
            cns.target_space = 'LOCAL'
            cns.owner_space = 'LOCAL'
            cns.influence = 1.0

        pb = rig.pose.bones[bname]
        isLoc1,isRot1,isScale1 = self.isSuchDriver(bname, boneDrivers)
        isLoc2,isRot2,isScale2 = self.isSuchDriver(bname, sumDrivers)
        if isLoc1 or isLoc2:
            cns = pb.constraints.new('COPY_LOCATION')
            cns.name = "Copy Location %s" % bname
            addFields(cns, rig, bname)
            cns.use_offset = True
        if isRot1 or isRot2:
            cns = pb.constraints.new('COPY_ROTATION')
            cns.name = "Copy Rotation %s" % bname
            if pb.parent and pb.parent.rotation_mode != 'QUATERNION':
                cns.euler_order = pb.parent.rotation_mode
            addFields(cns, rig, bname)
            cns.mix_mode = 'ADD'
        if isScale1 or isScale2:
            cns = pb.constraints.new('COPY_SCALE')
            cns.name = "Copy Scale %s" % bname
            addFields(cns, rig, bname)
            cns.use_offset = True


    def isSuchDriver(self, bname, drivers):
        isLoc = isRot = isScale = False
        if bname in drivers.keys():
            for drv in drivers[bname]:
                channel = drv.data_path.rsplit(".",1)[-1]
                if channel == "location":
                    isLoc = True
                elif channel in ["rotation_euler", "rotation_quaternion"]:
                    isRot = True
                elif channel == "scale":
                    isScale = True
        return isLoc, isRot, isScale


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
            eb.layers = list(db.layers)
            eb.use_deform = db.use_deform
            return eb


        def copyPoseBone(db, pb):
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
        drivenLayers = 31*[False] + [True]
        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            eb = copyEditBone(db, rig, bname)
            eb.parent = db.parent
            db.layers = drivenLayers
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
                bone.DazExtraBone = db.DazExtraBone

        setMode('EDIT')
        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            for cb in db.children:
                if cb.name != bname:
                    cb.parent = rig.data.edit_bones[bname]

        print("  Change constraints")
        setMode('POSE')
        store = ConstraintStore()
        for bname in self.bnames:
            pb = rig.pose.bones[bname]
            db = rig.pose.bones[drvBone(bname)]
            copyPoseBone(db, pb)
            db.custom_shape = None
            copyBoneInfo(db, pb)
            store.storeConstraints(db.name, db)
            store.removeConstraints(db)
            self.addCopyConstraint(rig, bname, boneDrivers, sumDrivers)
            store.restoreConstraints(db.name, pb)

        print("  Restore bone drivers")
        self.restoreBoneSumDrivers(rig, boneDrivers)
        print("  Restore sum drivers")
        self.restoreBoneSumDrivers(rig, sumDrivers)
        print("  Update scripted drivers")
        self.updateScriptedDrivers(rig.data)
        print("  Update drivers")
        setattr(rig.data, self.attr, True)
        updateDrivers(rig)

        print("  Update vertex groups")
        setMode('OBJECT')
        for ob in rig.children:
            if ob.type == 'MESH':
                for vgrp in ob.vertex_groups:
                    if isDrvBone(vgrp.name):
                        vgname = baseBone(vgrp.name)
                        if vgname in self.bnames:
                            vgrp.name = vgname

        print("  Update shapekeys")
        for ob in rig.children:
            if ob.type == 'MESH':
                skeys = ob.data.shape_keys
                if skeys:
                    for skey in skeys.key_blocks[1:]:
                        fcu = getShapekeyDriver(skeys, skey.name)
                        if fcu:
                            self.correctDriver(fcu, rig)
            updateDrivers(ob)

        if rig.animation_data and rig.animation_data.action:
            for fcu in rig.animation_data.action.fcurves:
                if "(drv)" in fcu.group.name:
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


class DAZ_OT_SetAddExtraFaceBones(DazOperator, ExtraBones, IsArmature):
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
                    not isFinal(bname) and
                    drvBone(bname) not in keys]
        bnames += getAnchoredBoneNames(rig, ["upperFaceRig", "lowerFaceRig"])
        return bnames

    def checkAllowed(self, rig):
        pass

    def changeLayer(self, eb, rig):
        if rig.DazRig == "mhx":
            eb.layers = 8*[False] + [True] + 23*[False]
        elif rig.DazRig[0:6] == "rigify":
            eb.layers = 2*[False] + [True] + 29*[False]

    def isSuchDriver(self, bname, drivers):
        return True, True, False


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


class DAZ_OT_MakeAllBonesPosable(DazOperator, ExtraBones, IsArmature):
    bl_idname = "daz.make_all_bones_posable"
    bl_label = "Make All Bones Posable"
    bl_description = "Add an extra layer of driven bones, to make them posable"
    bl_options = {'UNDO'}

    type =  "driven"
    attr = "DazExtraDrivenBones"
    button = "Make All Bones Posable"

    def getBoneNames(self, rig):
        from .driver import isBoneDriven
        exclude = ["lMetatarsals", "rMetatarsals", "l_metatarsal", "r_metatarsal"]
        return [pb.name for pb in rig.pose.bones
                if not isDrvBone(pb.name) and
                    not isFinal(pb.name) and
                    isBoneDriven(rig, pb) and
                    drvBone(pb.name) not in rig.pose.bones.keys() and
                    pb.name not in exclude]

    def checkAllowed(self, rig):
        if rig.DazRig[0:3] in ["mhx", "rig"]:
            msg = "Rig type = %s" % rig.DazRig
        elif rig.DazSimpleIK:
            msg = "Rig has simple IK"
        elif rig.data.DazFinalized:
            msg = "Rig has been finalized"
        else:
            msg = ""
        if msg:
            msg = "Cannot make bones posable.     \n%s" % msg
            print(msg)
            raise DazError(msg)

    def changeLayer(self, eb, rig):
        pass

    def isSuchDriver(self, bname, drivers):
        #isLoc,isRot,isScale = ExtraBones.isSuchDriver(self, bname, drivers)
        return True, True, True

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


    def isSuchDriver(self, bname, drivers):
        return True, True, True

#-------------------------------------------------------------
#   Finalize bones
#-------------------------------------------------------------

def finalizeArmature(rig):
    from .driver import getBoneDrivers
    extras = ExtraBones()
    for pb in rig.pose.bones:
        if not isDrvBone(pb.name) and not isFinal(pb.name):
            drvname = drvBone(pb.name)
            db = rig.pose.bones.get(drvname)
            isLoc = isRot = isScale = False
            if db:
                drivers = {drvname : getBoneDrivers(rig, db)}
                isLoc,isRot,isScale = extras.isSuchDriver(drvname, drivers)
                for test,ctype,cname in [
                    (isLoc, 'COPY_LOCATION', "Copy Location %s" % pb.name),
                    (isRot, 'COPY_ROTATION', "Copy Rotation %s" % pb.name),
                    (isScale, 'COPY_SCALE', "Copy Scale %s" % pb.name)]:
                    if not test:
                        for cns in pb.constraints:
                            if cns.type == ctype and cns.name == cname:
                                pb.constraints.remove(cns)
                                break
    rig.data.DazFinalized = True


class DAZ_OT_FinalizeArmature(DazOperator, IsArmature):
    bl_idname = "daz.finalize_armature"
    bl_label = "Finalize Armature"
    bl_description = "Remove unused bone constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        finalizeArmature(context.object)

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
            setattr(pb, lock, (False,False,False))

def toggleRotLocks(self, context):
    toggleLocks(self, context, "DazRotLocks", "lock_rotation")

def toggleLocLocks(self, context):
    toggleLocks(self, context, "DazLocLocks", "lock_location")

#----------------------------------------------------------
#   Toggle Limits
#----------------------------------------------------------

def toggleLimits(self, context, attr, type):
    for pb in self.pose.bones:
        for cns in pb.constraints:
            if cns.type == type:
                cns.mute = not getattr(self, attr)

def toggleRotLimits(self, context):
    toggleLimits(self, context, "DazRotLimits", "LIMIT_ROTATION")

def toggleLocLimits(self, context):
    toggleLimits(self, context, "DazLocLimits", "LIMIT_LOCATION")

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
    from .runtime.morph_armature import onFrameChangeDaz, unregister
    unregister()
    if context.scene.DazAutoMorphArmatures:
        bpy.app.handlers.frame_change_post.append(onFrameChangeDaz)

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
    G38Spine = ["hip", "abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G38Neck = ["neckLower", "neckUpper"]
    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["hip", "abdomen", "abdomen2", "spine", "chest"]
    G12Neck = ["neck"]
    G9Arm = ["_upperarm", "_forearm", "_hand"]
    G9Leg = ["_thigh", "_shin", "_foot"]
    G9Spine = ["hip", "spine1", "spine2", "spine3", "spine4"]
    G9Neck = ["neck1", "neck2"]


    def storeProps(self, rig):
        self.ikprops = (rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R)

    def setProps(self, rig, onoff):
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = onoff

    def restoreProps(self, rig):
        rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R = self.ikprops

    def getIKProp(self, prefix, type):
        return ("Daz%sIK_%s" % (type, prefix.upper()))

    def updatePose(self):
        bpy.context.view_layer.update()

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
                sufname = getSuffixName(bname)
                if sufname not in rig.data.bones.keys():
                    return False
        return True


    def getLimbBoneNames(self, rig, prefix, type):
        genesis = self.getGenesisType(rig)
        if not genesis:
            return []
        from .fix import getPreSufName
        table = getattr(self, genesis+type)
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

class DAZ_OT_AddSimpleIK(DazPropsOperator, IsArmature):
    bl_idname = "daz.add_simple_ik"
    bl_label = "Add Simple IK"
    bl_description = (
        "Add Simple IK constraints to the active rig.\n" +
        "This will not work if the rig has body morphs affecting arms and legs,\n" +
        "and the bones have been made posable")
    bl_options = {'UNDO'}

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

    def draw(self, context):
        self.layout.prop(self, "useArms")
        self.layout.prop(self, "useLegs")
        self.layout.prop(self, "usePoleTargets")


    def run(self, context):
        def makePole(bname, rig, eb, parent):
            from .mhx import makeBone
            mat = eb.matrix.to_3x3()
            xaxis = mat.col[0]
            zaxis = mat.col[2]
            head = eb.head - 40*rig.DazScale*zaxis
            tail = head + 10*rig.DazScale*Vector((0,0,1))
            makeBone(bname, rig, head, tail, 0, 0, parent)
            strname = stretchName(bname)
            stretch = makeBone(strname, rig, eb.head, head, 0, 0, eb)
            stretch.hide_select = True

        def stretchName(bname):
            return (bname+"_STR")

        def driveConstraint(pb, type, rig, prop, expr):
            from .mhx import addDriver
            for cns in pb.constraints:
                if cns.type == type:
                    addDriver(cns, "influence", rig, prop, expr)

        rig = context.object
        if rig.DazSimpleIK:
            raise DazError("The rig %s already has simple IK" % rig.name)
        if not rig.DazCustomShapes:
            raise DazError("Make custom shapes first")

        from .mhx import makeBone, getBoneCopy, ikConstraint, copyRotation, stretchTo, fixIk
        IK = SimpleIK(self)
        genesis = IK.getGenesisType(rig)
        if not genesis:
            raise DazError("Cannot create simple IK for the rig %s" % rig.name)

        rig.DazSimpleIK = True
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = True

        LS.customShapes = []
        csHandIk = makeCustomShape("CS_HandIk", "RectX")
        csFootIk = makeCustomShape("CS_FootIk", "RectZ")
        if IK.usePoleTargets:
            csCube = makeCustomShape("CS_Cube", "Cube", scale=0.3)

        armTable = {
            "G12" : ("Hand", "HandIK", "Shldr", "ForeArm", "ForeArm", "", "", "Collar", "Elbow"),
            "G38" : ("Hand", "HandIK", "ShldrBend", "ForearmBend", "ForearmTwist", "ShldrIK", "ForearmIK", "Collar", "Elbow"),
            "G9" : ("_hand", "_handIK", "_shldr", "_forearm", "_forearm", "", "", "_shoulder", "_elbow"),
        }

        legTable = {
            "G12" : ("Foot", "FootIK", "Thigh", "Shin", "", "hip", "Knee"),
            "G38" : ("Foot", "FootIK", "ThighBend", "Shin", "ThighIK", "hip", "Knee"),
            "G9" : ("_foot", "_footIK", "_thigh", "_shin", "", "hip", "_knee"),
        }

        def getEntry(table, key, prefix):
            entry = []
            for bname in table[key]:
                if bname and bname in rig.data.bones.keys():
                    entry.append(bname)
                elif bname:
                    entry.append("%s%s" % (prefix, bname))
                else:
                    entry.append(None)
            return entry

        setMode('EDIT')
        ebones = rig.data.edit_bones
        for prefix in ["l", "r"]:
            if self.useArms:
                handname, hikname, shldrname, forebendname, foretwistname, shikname, foreikname, collarname, elbowname = getEntry(armTable, genesis, prefix)
                hand = ebones[handname]
                handIK = makeBone(hikname, rig, hand.head, hand.tail, hand.roll, 0, None)
                forebend = ebones[forebendname]
                foretwist = ebones[foretwistname]
                foretwist.tail = hand.head
                if shikname:
                    shldr = ebones[shldrname]
                    shldrIK = makeBone(shikname, rig, shldr.head, shldr.tail, shldr.roll, 31, shldr.parent)
                    forebend.parent = shldrIK
                collar = ebones[collarname]
                if IK.usePoleTargets:
                    elbow = makePole(elbowname, rig, foretwist, collar)

            if self.useLegs:
                footname, fikname, thighname, shinname, thikname, hipname, kneename = getEntry(legTable, genesis, prefix)
                foot = ebones[footname]
                shin = ebones[shinname]
                footIK = makeBone(fikname, rig, foot.head, foot.tail, foot.roll, 0, None)
                shin.tail = foot.head
                if thikname:
                    thigh = ebones[thighname]
                    thighIK = makeBone(thikname, rig, thigh.head, thigh.tail, thigh.roll, 31, thigh.parent)
                    shin.parent = thighIK
                hip = ebones[hipname]
                if IK.usePoleTargets:
                    knee = makePole(kneename, rig, shin, hip)

        setMode('OBJECT')
        rpbs = rig.pose.bones
        for prefix in ["l", "r"]:
            suffix = prefix.upper()
            if self.useArms:
                armProp = "DazArmIK_" + suffix
                hand = getPoseBone(rig, (prefix+"Hand", prefix+"_hand"))
                driveConstraint(hand, 'LIMIT_ROTATION', rig, armProp, "1-x")
                hikname = getGenesisName(genesis, (prefix+"HandIK", prefix+"_handIK"))
                handIK = getBoneCopy(hikname, hand, rpbs)
                copyRotation(hand, handIK, rig, prop=armProp, space='WORLD')
                addToLayer(handIK, "IK Arm", rig, "IK")
            if self.useLegs:
                legProp = "DazLegIK_" + suffix
                foot = getPoseBone(rig, (prefix+"Foot", prefix+"_foot"))
                driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp, "1-x")
                fikname = getGenesisName(genesis, (prefix+"FootIK", prefix+"_footIK"))
                footIK = getBoneCopy(fikname, foot, rpbs)
                copyRotation(foot, footIK, rig, prop=legProp, space='WORLD')
                addToLayer(footIK, "IK Leg", rig, "IK")

            if genesis == "G38":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 1.5)
                    shldrBend = rpbs[prefix+"ShldrBend"]
                    IK.limitBone(shldrBend, True, False, rig, armProp)
                    shldrTwist = rpbs[prefix+"ShldrTwist"]
                    IK.limitBone(shldrTwist, False, True, rig, armProp)
                    forearmBend = rpbs[prefix+"ForearmBend"]
                    IK.limitBone(forearmBend, True, False, rig, armProp)
                    forearmTwist = rpbs[prefix+"ForearmTwist"]
                    IK.limitBone(forearmTwist, False, True, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 3.0)
                    thighBend = rpbs[prefix+"ThighBend"]
                    IK.limitBone(thighBend, True, False, rig, legProp)
                    thighTwist = rpbs[prefix+"ThighTwist"]
                    IK.limitBone(thighTwist, False, True, rig, legProp)
                    shin = rpbs[prefix+"Shin"]
                    IK.limitBone(shin, False, False, rig, legProp)
                    fixIk(rig, [shin.name])
                    shin.lock_ik_z = True

            elif genesis == "G9":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 3.0)
                    shldr = rpbs[prefix+"_upperarm"]
                    IK.limitBone(shldr, False, False, rig, armProp)
                    forearm = rpbs[prefix+"_forearm"]
                    IK.limitBone(forearm, False, False, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 1.5)
                    thigh = rpbs[prefix+"_thigh"]
                    IK.limitBone(thigh, False, False, rig, legProp)
                    shin = rpbs[prefix+"_shin"]
                    IK.limitBone(shin, False, False, rig, legProp)
                    fixIk(rig, [shin.name])
                    shin.lock_ik_z = True

            elif genesis == "G12":
                if self.useArms:
                    setCustomShape(handIK, csHandIk, 3.0)
                    shldr = rpbs[prefix+"Shldr"]
                    IK.limitBone(shldr, False, False, rig, armProp)
                    forearm = rpbs[prefix+"ForeArm"]
                    IK.limitBone(forearm, False, False, rig, armProp)
                if self.useLegs:
                    setCustomShape(footIK, csFootIk, 1.5)
                    thigh = rpbs[prefix+"Thigh"]
                    IK.limitBone(thigh, False, False, rig, legProp)
                    shin = rpbs[prefix+"Shin"]
                    IK.limitBone(shin, False, False, rig, legProp)
                    fixIk(rig, [shin.name])
                    shin.lock_ik_z = True

            if IK.usePoleTargets:
                if self.useArms:
                    elbow = getPoseBone(rig, (prefix+"Elbow", prefix+"_elbow"))
                    elbow.lock_rotation = (True,True,True)
                    elbow.custom_shape = csCube
                    addToLayer(elbow, "IK Arm", rig, "IK")
                    stretch = rpbs[stretchName(elbow.name)]
                    stretchTo(stretch, elbow, rig)
                    addToLayer(stretch, "IK Arm", rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = (True,True,True)
                if self.useLegs:
                    knee = getPoseBone(rig, (prefix+"Knee", prefix+"_knee"))
                    knee.lock_rotation = (True,True,True)
                    knee.custom_shape = csCube
                    addToLayer(knee, "IK Leg", rig, "IK")
                    stretch = rpbs[stretchName(knee.name)]
                    stretchTo(stretch, knee, rig)
                    addToLayer(stretch, "IK Leg", rig, "IK")
                    stretch.lock_rotation = stretch.lock_location = (True,True,True)
            else:
                elbow = knee = None

            if genesis == "G38":
                if self.useArms:
                    ikConstraint(forearmTwist, handIK, elbow, -90, 3, rig, prop=armProp)
                    shldrIK = rpbs[prefix+"ShldrIK"]
                    shldrIK.rotation_mode = shldrBend.rotation_mode
                    cns = copyRotation(shldrBend, shldrIK, rig, prop=armProp)
                    cns.euler_order = shldrBend.rotation_mode
                    cns.use_y = False
                    cns = copyRotation(shldrTwist, shldrIK, rig, prop=armProp)
                    cns.euler_order = shldrTwist.rotation_mode
                    cns.use_x = cns.use_z = False
                if self.useLegs:
                    ikConstraint(shin, footIK, knee, -90, 2, rig, prop=legProp)
                    thighIK = rpbs[prefix+"ThighIK"]
                    thighIK.rotation_mode = thighBend.rotation_mode
                    cns = copyRotation(thighBend, thighIK, rig, prop=legProp)
                    cns.euler_order = thighBend.rotation_mode
                    cns.use_y = False
                    cns = copyRotation(thighTwist, thighIK, rig, prop=legProp)
                    cns.euler_order = thighTwist.rotation_mode
                    cns.use_x = cns.use_z = False
            else:
                if self.useArms:
                    ikConstraint(forearm, handIK, elbow, -90, 2, rig, prop=armProp)
                if self.useLegs:
                    ikConstraint(shin, footIK, knee, -90, 2, rig, prop=legProp)

        from .node import createHiddenCollection
        hidden = createHiddenCollection(context, rig)
        for ob in LS.customShapes:
            hidden.objects.link(ob)
            #ob.hide_viewport = ob.hide_render = True
        T = True
        F = False
        rig.data.layers = 16*[F] + [T,T,F,F, F,F,F,F, F,F,T,T, T,T,F,F]
        rig.data.display_type = 'WIRE'

#----------------------------------------------------------
#   Connect bones in IK chains
#----------------------------------------------------------

class DAZ_OT_ConnectIKChains(DazPropsOperator, SimpleIK, IsArmature):
    bl_idname = "daz.connect_ik_chains"
    bl_label = "Connect IK Chains"
    bl_description = "Connect all bones in IK chains to their parents"
    bl_options = {'UNDO'}

    type : EnumProperty(
        items = [('ARMS', "Arms Only", "Connect arms only"),
                 ('LEGS', "Legs Only", "Connect legs only"),
                 ('ARMSLEGS', "Arms And Legs", "Connect both arms and legs"),
                 ('SELECTED', "Selected", "Connect selected bones")],
        name = "Chain Types",
        description = "Connect the specified types of chains",
        default = 'ARMSLEGS')

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
        self.layout.prop(self, "type")
        self.layout.prop(self, "location")
        self.layout.prop(self, "unlock")


    def run(self, context):
        rig = context.object
        self.getBoneNames(rig)
        setMode("EDIT")
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
            setMode("EDIT")
            for chain in self.chains:
                pb = rig.pose.bones[chain[-1]]
                pb.lock_location = (False,False,False)


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
        if self.type == 'ARMS':
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Arm")
                self.chains.append(chain)
        elif self.type == 'LEGS':
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Leg")
                self.chains.append(chain)
        elif self.type == 'ARMSLEGS':
            for prefix in ["l", "r"]:
                for type in ["Arm", "Leg"]:
                    chain = self.getLimbBoneNames(rig, prefix, type)
                    self.chains.append(chain)
        elif self.type == 'SELECTED':
            roots = []
            for bone in rig.data.bones:
                if bone.parent is None:
                    roots.append(bone)
            for root in roots:
                self.getChildNames(rig, root)
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
#   Custom shapes
#----------------------------------------------------------

BoneLayers = {
    "Spine" : 16,
    "Face" : 17,
    "Left FK Arm" : 18,
    "Right FK Arm" : 19,
    "Left FK Leg" : 20,
    "Right FK Leg" : 21,
    "Left Hand" : 22,
    "Right Hand" : 23,
    "Left Foot" : 24,
    "Right Foot" : 25,
    "Left IK Arm" : 26,
    "Right IK Arm" : 27,
    "Left IK Leg" : 28,
    "Right IK Leg" : 29,
}


def makeBoneGroups(rig):
    BoneGroups = [
        ("Spine",   (1,1,0)),
        ("FK",      (0,1,0)),
        ("IK",      (1,0,0)),
        ("Limb",    (0,0,1)),
    ]
    if len(rig.pose.bone_groups) != len(BoneGroups):
        for bg in list(rig.pose.bone_groups):
            rig.pose.bone_groups.remove(bg)
        for bgname,color in BoneGroups:
            bg = rig.pose.bone_groups.new(name=bgname)
            bg.color_set = 'CUSTOM'
            bg.colors.normal = color
            bg.colors.select = (0.6, 0.9, 1.0)
            bg.colors.active = (1.0, 1.0, 0.8)


def addToLayer(pb, lname, rig=None, bgname=None):
    if lname in BoneLayers.keys():
        n = BoneLayers[lname]
    elif pb.name[0] == "l" and "Left "+lname in BoneLayers.keys():
        n = BoneLayers["Left "+lname]
    elif pb.name[0] == "r" and "Right "+lname in BoneLayers.keys():
        n = BoneLayers["Right "+lname]
    else:
        print("MISSING LAYER", lname, pb.name)
        return
    pb.bone.layers[n] = True
    if rig and bgname:
        pb.bone_group = rig.pose.bone_groups[bgname]


class DAZ_OT_SelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.select_named_layers"
    bl_label = "All"
    bl_description = "Select all named layers and unselect all unnamed layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


class DAZ_OT_UnSelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.unselect_named_layers"
    bl_label = "Only Active"
    bl_description = "Unselect all named and unnamed layers except active"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        m = 16
        bone = rig.data.bones.active
        if bone:
            for n in range(16,30):
                if bone.layers[n]:
                    m = n
                    break
        rig.data.layers = m*[False] + [True] + (31-m)*[False]

#----------------------------------------------------------
#   Custom shapes
#----------------------------------------------------------

def makeCustomShape(csname, gname, offset=(0,0,0), scale=1):
    Gizmos = {
        "CircleX" : {
            "verts" : [[0, 1, 0], [0, 0.9808, 0.1951], [0, 0.9239, 0.3827], [0, 0.8315, 0.5556], [0, 0.7071, 0.7071], [0, 0.5556, 0.8315], [0, 0.3827, 0.9239], [0, 0.1951, 0.9808], [0, 0, 1], [0, -0.1951, 0.9808], [0, -0.3827, 0.9239], [0, -0.5556, 0.8315], [0, -0.7071, 0.7071], [0, -0.8315, 0.5556], [0, -0.9239, 0.3827], [0, -0.9808, 0.1951], [0, -1, 0], [0, -0.9808, -0.1951], [0, -0.9239, -0.3827], [0, -0.8315, -0.5556], [0, -0.7071, -0.7071], [0, -0.5556, -0.8315], [0, -0.3827, -0.9239], [0, -0.1951, -0.9808], [0, 0, -1], [0, 0.1951, -0.9808], [0, 0.3827, -0.9239], [0, 0.5556, -0.8315], [0, 0.7071, -0.7071], [0, 0.8315, -0.5556], [0, 0.9239, -0.3827], [0, 0.9808, -0.1951]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "CircleY" : {
            "verts" : [[1, 0, 0], [0.9808, 0, 0.1951], [0.9239, 0, 0.3827], [0.8315, 0, 0.5556], [0.7071, 0, 0.7071], [0.5556, 0, 0.8315], [0.3827, 0, 0.9239], [0.1951, 0, 0.9808], [0, 0, 1], [-0.1951, 0, 0.9808], [-0.3827, 0, 0.9239], [-0.5556, 0, 0.8315], [-0.7071, 0, 0.7071], [-0.8315, 0, 0.5556], [-0.9239, 0, 0.3827], [-0.9808, 0, 0.1951], [-1, 0, 0], [-0.9808, 0, -0.1951], [-0.9239, 0, -0.3827], [-0.8315, 0, -0.5556], [-0.7071, 0, -0.7071], [-0.5556, 0, -0.8315], [-0.3827, 0, -0.9239], [-0.1951, 0, -0.9808], [0, 0, -1], [0.1951, 0, -0.9808], [0.3827, 0, -0.9239], [0.5556, 0, -0.8315], [0.7071, 0, -0.7071], [0.8315, 0, -0.5556], [0.9239, 0, -0.3827], [0.9808, 0, -0.1951]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "CircleZ" : {
            "verts" : [[0, 1, 0], [-0.1951, 0.9808, 0], [-0.3827, 0.9239, 0], [-0.5556, 0.8315, 0], [-0.7071, 0.7071, 0], [-0.8315, 0.5556, 0], [-0.9239, 0.3827, 0], [-0.9808, 0.1951, 0], [-1, 0, 0], [-0.9808, -0.1951, 0], [-0.9239, -0.3827, 0], [-0.8315, -0.5556, 0], [-0.7071, -0.7071, 0], [-0.5556, -0.8315, 0], [-0.3827, -0.9239, 0], [-0.1951, -0.9808, 0], [0, -1, 0], [0.1951, -0.9808, 0], [0.3827, -0.9239, 0], [0.5556, -0.8315, 0], [0.7071, -0.7071, 0], [0.8315, -0.5556, 0], [0.9239, -0.3827, 0], [0.9808, -0.1951, 0], [1, 0, 0], [0.9808, 0.1951, 0], [0.9239, 0.3827, 0], [0.8315, 0.5556, 0], [0.7071, 0.7071, 0], [0.5556, 0.8315, 0], [0.3827, 0.9239, 0], [0.1951, 0.9808, 0]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "Cube" : {
            "verts" : [[-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5]],
            "edges" : [[2, 0], [0, 1], [1, 3], [3, 2], [6, 2], [3, 7], [7, 6], [4, 6], [7, 5], [5, 4], [0, 4], [5, 1]]
        },
        "RectX" : {
            "verts" : [[0, 0, 0.3], [0, 0, -0.3], [0, 1, 0.5], [0, 1, -0.5]],
            "edges" : [[2, 0], [0, 1], [1, 3], [3, 2]]
        },
        "RectZ" : {
            "verts" : [[0.3, 0, 0], [-0.3, 0, 0], [0.5, 1, 0], [-0.5, 1, 0]],
            "edges" : [[2, 0], [0, 1], [1, 3], [3, 2]]
    }
    }
    me = bpy.data.meshes.new(csname)
    struct = Gizmos[gname]
    verts = struct["verts"]
    u,v,w = offset
    if isinstance(scale, tuple):
        a,b,c = scale
    else:
        a,b,c = scale,scale,scale
    verts = [(a*(x+u), b*(y+v), c*(z+w)) for x,y,z in struct["verts"]]
    me.from_pydata(verts, struct["edges"], [])
    ob = bpy.data.objects.new(csname, me)
    LS.customShapes.append(ob)
    return ob


def getPoseBone(rig, bnames):
    for bname in bnames:
        if bname in rig.pose.bones.keys():
            return rig.pose.bones[bname]
    return None


def getGenesisName(genesis, bnames):
    if genesis in ["G12", "G38"]:
        return bnames[0]
    elif genesis == "G9":
        return bnames[1]


class DAZ_OT_AddCustomShapes(DazOperator, IsArmature):
    bl_idname = "daz.add_custom_shapes"
    bl_label = "Add Custom Shapes"
    bl_description = "Add custom shapes to the bones of the active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        coll = getCollection(context, rig)
        LS.customShapes = []
        IK = SimpleIK()
        makeBoneGroups(rig)

        csCollar = makeCustomShape("CS_Collar", "CircleX", (0,1,0), (0,0.5,0.1))
        csHandFk = makeCustomShape("CS_HandFk", "CircleX", (0,1,0), (0,0.6,0.5))
        csCarpal = makeCustomShape("CS_Carpal", "CircleZ", (0,1,0), (0.1,0.5,0))
        csTongue = makeCustomShape("CS_Tongue", "CircleZ", (0,1,0), (1.5,0.5,0))
        circleY2 = makeCustomShape("CS_CircleY2", "CircleY", scale=1/3)
        csLimb = makeCustomShape("CS_Limb", "CircleY", (0,2,0), scale=1/4)
        csBend = makeCustomShape("CS_Bend", "CircleY", (0,1,0), scale=1/2)
        csFace = makeCustomShape("CS_Face", "CircleY", scale=1/5)
        csCube = makeCustomShape("CS_Cube", "Cube", scale=1/2)

        spineWidth = 1
        lCollar = getPoseBone(rig, ("lCollar", "l_shoulder"))
        rCollar = getPoseBone(rig, ("rCollar", "r_shoulder"))
        if lCollar and rCollar:
            spineWidth = 0.5*(lCollar.bone.tail_local[0] - rCollar.bone.tail_local[0])

        csFoot = None
        csToe = None
        lFoot = getPoseBone(rig, ("lFoot", "l_foot"))
        lToe = getPoseBone(rig, ("lToe", "l_toes"))
        if lFoot and lToe:
            footFactor = (lToe.bone.head_local[1] - lFoot.bone.head_local[1])/(lFoot.bone.tail_local[1] - lFoot.bone.head_local[1])
            csFoot = makeCustomShape("CS_Foot", "CircleZ", (0,1,0), (0.8,0.5*footFactor,0))
            csToe = makeCustomShape("CS_Toe", "CircleZ", (0,1,0), (1,0.5,0))

        for bnames in [("upperFaceRig", "upperfacerig"),
                       ("lowerFaceRig", "lowerfacerig"),
                       ("lMetatarsals", "l_metatarsal"),
                       ("rMetatarsals", "r_metatarsal"),
                       ("upperTeeth", "upperteeth"),
                       ("lowerTeeth", "lowerteeth")]:
            pb = getPoseBone(rig, bnames)
            if pb:
                pb.bone.layers = [False] + [True] + 30*[False]

        for pb in rig.pose.bones:
            lname = pb.name.lower()
            if not pb.bone.layers[0]:
                pass
            elif pb.parent and pb.parent.name in ["lowerFaceRig", "upperFaceRig", "lowerfacerig", "upperfacerig"]:
                if pb.name.startswith(("lEyelid", "rEyelid", "l_eyelid", "r_eyelid")):
                    setCustomShape(pb, csFace, 0.3, 1.0)
                else:
                    setCustomShape(pb, csFace)
                addToLayer(pb, "Face", rig, "Spine")
            elif pb.name in ["lEye", "rEye", "lEar", "rEar", "l_eye", "r_eye", "l_ear", "r_ear"]:
                setCustomShape(pb, circleY2, None, 1.0)
                addToLayer(pb, "Face", rig, "Spine")
            elif lname == "lowerjaw":
                setCustomShape(pb, csCollar)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name.startswith("tongue"):
                setCustomShape(pb, csTongue)
                addToLayer(pb, "Face", rig, "Spine")
            elif lname.endswith("hand"):
                setCustomShape(pb, csHandFk)
                addToLayer(pb, "FK Arm", rig, "FK")
            elif lname.endswith("handik"):
                setCustomShape(pb, csHandIk, 1.8)
                addToLayer(pb, "IK Arm", rig, "IK")
            elif "carpal" in lname:
                setCustomShape(pb, csCarpal)
                addToLayer(pb, "Hand", rig, "Limb")
            elif pb.name in ["lCollar", "rCollar", "l_shoulder", "r_shoulder"]:
                setCustomShape(pb, csCollar)
                addToLayer(pb, "Spine", rig, "Spine")
            elif lname.endswith("foot"):
                setCustomShape(pb, csFoot)
                addToLayer(pb, "FK Leg", rig, "FK")
            elif lname.endswith("footik"):
                setCustomShape(pb, csFoot, 1.8)
                addToLayer(pb, "IK Leg", rig, "IK")
            elif pb.name in ["lToe", "rToe", "l_toes", "r_toes"]:
                setCustomShape(pb, csToe)
                addToLayer(pb, "FK Leg", rig, "Limb")
                addToLayer(pb, "IK Leg")
                addToLayer(pb, "Foot")
            elif pb.name[1:] in IK.G12Arm + IK.G38Arm + IK.G9Arm:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "FK Arm", rig, "FK")
            elif pb.name[1:] in IK.G12Leg + IK.G38Leg + IK.G9Leg:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "FK Leg", rig, "FK")
            elif pb.name[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]:
                setCustomShape(pb, csLimb)
                addToLayer(pb, "Hand", rig, "Limb")
            elif pb.name == "hip":
                self.makeSpine(pb, 2*spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name == "pelvis":
                self.makeSpine(pb, 1.5*spineWidth, 0.5)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name in IK.G38Spine + IK.G12Spine + IK.G9Spine:
                self.makeSpine(pb, spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name in IK.G38Neck + IK.G12Neck + IK.G9Neck:
                self.makeSpine(pb, 0.5*spineWidth)
                addToLayer(pb, "Spine", rig, "Spine")
            elif pb.name == "head":
                self.makeSpine(pb, 0.7*spineWidth, 1)
                addToLayer(pb, "Spine", rig, "Spine")
                addToLayer(pb, "Face")
            elif "toe" in lname:
                setCustomShape(pb, circleY2)
                addToLayer(pb, "Foot", rig, "Limb")
            elif (pb.name[1:4] in ["Thu", "Ind", "Mid", "Rin", "Pin"] or
                  pb.name[1:5] in ["_thu", "_ind", "_mid", "_rin", "_pin"]):
                setCustomShape(pb, circleY2)
                addToLayer(pb, "Hand", rig, "Limb")
            elif "elbow" in lname:
                if not pb.name.endswith("STR"):
                    setCustomShape(pb, csCube)
                addToLayer(pb, "IK Arm", rig, "IK")
            elif "knee" in lname:
                if not pb.name.endswith("STR"):
                    setCustomShape(pb, csCube)
                addToLayer(pb, "IK Leg", rig, "IK")
            elif "pectoral" in lname:
                setCustomShape(pb, circleY2, 0.3, 1.0)
            elif pb.name.endswith(("twist1", "twist2")):
                pass
            elif lname.endswith("anchor"):
                pass
            else:
                #setCustomShape(pb, circleY2)
                print("Unknown bone:", pb.name)

        from .node import createHiddenCollection
        hidden = createHiddenCollection(context, rig)
        for ob in LS.customShapes:
            hidden.objects.link(ob)
            #ob.hide_viewport = ob.hide_render = True
        rig.DazCustomShapes = True
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


    def makeSpine(self, pb, width, tail=0.5):
        s = width/pb.bone.length
        circle = makeCustomShape("CS_" + pb.name, "CircleY", (0,tail/s,0))
        setCustomShape(pb, circle, s)


class DAZ_OT_RemoveCustomShapes(DazOperator, IsArmature):
    bl_idname = "daz.remove_custom_shapes"
    bl_label = "Remove Custom Shapes"
    bl_description = "Remove custom shapes from the bones of the active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            pb.custom_shape = None


def setSimpleToFk(rig, layers):
    for lname in ["Left FK Arm", "Right FK Arm", "Left FK Leg", "Right FK Leg"]:
        layers[BoneLayers[lname]] = True
    for lname in ["Left IK Arm", "Right IK Arm", "Left IK Leg", "Right IK Leg"]:
        layers[BoneLayers[lname]] = False
    rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = 0.0
    return layers

#----------------------------------------------------------
#   FK Snap
#----------------------------------------------------------

class DAZ_OT_SnapSimpleFK(DazOperator, SimpleIK):
    bl_idname = "daz.snap_simple_fk"
    bl_label = "Snap FK"
    bl_description = "Snap FK bones to IK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()

    def run(self, context):
        rig = context.object
        bnames = self.getLimbBoneNames(rig, self.prefix, self.type)
        if bnames:
            prop = self.getIKProp(self.prefix, self.type)
            setattr(rig, prop, True)
            self.updatePose()
            self.snapSimpleFK(rig, bnames, prop)
            toggleLayer(rig, "FK", self.prefix, self.type, True)
            toggleLayer(rig, "IK", self.prefix, self.type, False)
            setattr(rig, prop, False)


    def snapSimpleFK(self, rig, bnames, prop):
        from .fix import getPreSufName
        mats = []
        for bname in bnames:
            pb = rig.pose.bones.get(getPreSufName(bname, rig))
            if pb:
                mats.append((pb, pb.matrix.copy()))
        setattr(rig, prop, False)
        self.updatePose()
        for pb,mat in mats:
            pb.matrix = mat
            self.updatePose()

#----------------------------------------------------------
#   IK Snap
#----------------------------------------------------------

class DAZ_OT_SnapSimpleIK(DazOperator, SimpleIK):
    bl_idname = "daz.snap_simple_ik"
    bl_label = "Snap IK"
    bl_description = "Snap IK bones to FK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()
    pole : StringProperty()

    def run(self, context):
        rig = context.object
        bnames = self.getLimbBoneNames(rig, self.prefix, self.type)
        if bnames:
            prop = self.getIKProp(self.prefix, self.type)
            setattr(rig, prop, False)
            self.updatePose()
            self.snapSimpleIK(rig, bnames, prop)
            toggleLayer(rig, "FK", self.prefix, self.type, False)
            toggleLayer(rig, "IK", self.prefix, self.type, True)
            setattr(rig, prop, True)


    def snapSimpleIK(self, rig, bnames, prop):
        from .fix import getPreSufName
        hand = bnames[-1]
        handfk = rig.pose.bones.get(getPreSufName(hand, rig))
        if handfk is None:
            return
        handmat = handfk.matrix.copy()
        pole = getPreSufName(self.pole, rig)
        if pole:
            poleik = rig.pose.bones.get(pole)
            uparm = bnames[0]
            loarm = bnames[1] if len(bnames) == 3 else bnames[2]
            uparmfk = rig.pose.bones.get(getPreSufName(uparm, rig))
            loarmfk = rig.pose.bones.get(getPreSufName(loarm, rig))
            polemat = self.getPoleMatrix(uparmfk, loarmfk)
        setattr(rig, prop, True)
        handik = rig.pose.bones.get(getPreSufName("%sIK" % hand, rig))
        if handik:
            handik.matrix = handmat
            self.updatePose()
        if pole:
            poleik.matrix = polemat
            self.updatePose()
        for bname in bnames:
            pb = rig.pose.bones.get(getPreSufName(bname, rig))
            if pb:
                pb.matrix_basis = Matrix()
                self.updatePose()


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


def toggleLayer(rig, fk, prefix, type, on):
    side = {"l" : "Left", "r" : "Right"}
    lname = ("%s %s %s" % (side[prefix], fk, type))
    layer = BoneLayers[lname]
    rig.data.layers[layer] = on

#----------------------------------------------------------
#   Set custom shape
#----------------------------------------------------------

def setCustomShape(pb, shape, scale=None, offset=None):
    if offset and not hasattr(pb, "custom_shape_translation"):
        return
    pb.custom_shape = shape
    if scale is None:
        pass
    elif hasattr(pb, "custom_shape_scale"):
        pb.custom_shape_scale = scale
    else:
        pb.custom_shape_scale_xyz = (scale, scale, scale)
    if offset is not None:
        pb.custom_shape_translation.y = offset*pb.bone.length

#-------------------------------------------------------------
#   Categorize
#-------------------------------------------------------------

class DAZ_OT_CategorizeObjects(DazOperator, IsMeshArmature):
    bl_idname = "daz.categorize_objects"
    bl_label = "Categorize Objects"
    bl_description = "Move unparented objects and their children to separate categories"

    def run(self, context):
        def linkObjects(ob, coll):
            for coll1 in bpy.data.collections:
                if ob.name in coll1.objects:
                    coll1.objects.unlink(ob)
            coll.objects.link(ob)
            for child in ob.children:
                linkObjects(child, coll)

        roots = []
        for ob in getSelectedObjects(context):
            if ob.parent is None and ob.type in ['MESH', 'ARMATURE']:
                roots.append(ob)
        print("Roots", roots)
        parcoll = context.collection
        for root in roots:
            coll = bpy.data.collections.new(root.name)
            parcoll.children.link(coll)
            linkObjects(root, coll)

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


class DAZ_OT_EnableAllLayers(DazOperator, IsArmature):
    bl_idname = "daz.enable_all_layers"
    bl_label = "Enable All Layers"
    bl_description = "Enable all bone layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        rig.data.layers = 32*[True]
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
    DAZ_OT_FixLegacyPosable,
    DAZ_OT_FinalizeArmature,
    DAZ_OT_ConnectIKChains,
    DAZ_OT_SelectNamedLayers,
    DAZ_OT_UnSelectNamedLayers,
    DAZ_OT_AddCustomShapes,
    DAZ_OT_RemoveCustomShapes,
    DAZ_OT_AddSimpleIK,
    DAZ_OT_SnapSimpleFK,
    DAZ_OT_SnapSimpleIK,
    DAZ_OT_CategorizeObjects,
    DAZ_OT_MorphArmature,
    DAZ_OT_InspectWorldMatrix,
    DAZ_OT_EnableAllLayers,
]

def register():
    from .propgroups import DazStringGroup

    bpy.types.Object.DazCustomShapes = BoolProperty(default=False)
    bpy.types.Armature.DazFinalized = BoolProperty(default=False)
    bpy.types.Object.DazSimpleIK = BoolProperty(default=False)
    bpy.types.Object.DazArmIK_L = BoolProperty(name="Left Arm IK", default=False)
    bpy.types.Object.DazArmIK_R = BoolProperty(name="Right Arm IK", default=False)
    bpy.types.Object.DazLegIK_L = BoolProperty(name="Left Leg IK", default=False)
    bpy.types.Object.DazLegIK_R = BoolProperty(name="Right Leg IK", default=False)

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

    bpy.types.Object.DazRotLimits = BoolPropOVR(
        name = "Rotation Limits",
        description = "Rotation Limits",
        default = True,
        update = toggleRotLimits)

    bpy.types.Object.DazLocLimits = BoolPropOVR(
        name = "Location Limits",
        description = "Location Limits",
        default = True,
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
