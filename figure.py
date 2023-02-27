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
    auto = context.scene.tool_settings.use_keyframe_insert_auto
    for pb in self.pose.bones:
        for cns in pb.constraints:
            if cns.type == type:
                cns.mute = False
                if cns.name != "Hint":
                    cns.influence = getattr(self, attr)
                    if auto:
                        cns.keyframe_insert("influence")

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
    DAZ_OT_CategorizeObjects,
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
