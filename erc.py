# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *
from .morphing import PosableMaker

#-------------------------------------------------------------
#  Add ERC bones
#-------------------------------------------------------------

class DAZ_OT_AddErcBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.add_erc_bones"
    bl_label = "Add ERC Bones"
    bl_description = "Add ERC bones"
    bl_options = {'UNDO'}

    useParents : BoolProperty(
        name = "Parents",
        description = "ERC bones have the same parents as the original bones and copy their rotations",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useParents")

    def run(self, context):
        rig = context.object
        if dazRna(rig.data).DazErcStatus > 0:
            raise DazError("Rig already has ERC bones")
        addErcBones(rig, self.useParents)


def addErcBones(rig, useParents):
    from .rig_utils import deriveBone
    from .figure import copyBoneInfo
    defbones = [bone.name for bone in rig.data.bones if not isDrvBone(bone.name)]
    setMode('EDIT')
    for bname in defbones:
        eb = rig.data.edit_bones[bname]
        ercb = deriveBone(ercBone(bname), eb, rig, T_ERC, None)
        if useParents and eb.parent:
            ercb.parent = eb.parent
        ercb.use_deform = False
    setMode('OBJECT')
    for bname in defbones:
        pb = rig.pose.bones[bname]
        ercb = rig.pose.bones[ercBone(bname)]
        copyBoneInfo(pb, ercb)
        ercb.bone.color.palette = 'THEME09'
        ercb.color.palette = 'THEME09'
    coll = rig.data.collections.get(T_ERC)
    if coll:
        coll.is_visible = False
    dazRna(rig.data).DazErcStatus = 1

#-------------------------------------------------------------
#  Update ERC bones
#-------------------------------------------------------------

class DAZ_OT_UpdateErcBones(DazPropsOperator, PosableMaker, IsArmature):
    bl_idname = "daz.update_erc_bones"
    bl_label = "Update ERC Bones"
    bl_description = "Update ERC bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        if dazRna(rig.data).DazErcStatus == 0:
            raise DazError("Rig does not have ERC bones")
        elif dazRna(rig.data).DazErcStatus == 2:
            raise DazError("ERC bones have already been updated")
        if self.useMakePosable:
            removePosableBones(rig)
        updateErcBones(rig)
        self.makePosable(context, rig)


def updateErcBones(rig):
    ercbones = [pb for pb in rig.pose.bones if isErcBone(pb.name)]
    basebones = [rig.pose.bones.get(ercBase(pb.name)) for pb in ercbones]
    for pb, ercb in zip(basebones, ercbones):
        if pb:
            removeConstraints(ercb)
            for cns in pb.constraints:
                if cns.type == 'LIMIT_ROTATION':
                    copyConstraint(cns, ercb, rig)
            updateErcBone(rig, pb, ercb)
    setMode('EDIT')
    for eb in rig.data.edit_bones:
        if isDrvBone(eb.name) and "tongue" not in eb.name:
            rig.data.edit_bones.remove(eb)
    setMode('OBJECT')
    coll = rig.data.collections.get(T_BONES)
    if coll:
        coll.is_visible = False
    coll = rig.data.collections.get(T_ERC)
    if coll:
        coll.is_visible = True
    dazRna(rig.data).DazErcStatus = 2


def updateErcBone(rig, pb, ercb):
    from .figure import copyBoneInfo
    from .store import copyConstraint, removeConstraints
    from .driver import setFloatProp, getDriver
    from .rig_utils import copyTransform

    bname = pb.name
    drvb = rig.pose.bones.get(drvBone(bname), pb)

    for idx,ttype in enumerate(['LOC_X', 'LOC_Y', 'LOC_Z']):
        fcu0 = getDriver(rig, 'pose.bones["%s"].location' % drvb.name, idx)
        efcu = getDriver(rig, 'pose.bones["%s"].location' % ercb.name, idx)
        if efcu and fcu0:
            prop = "%s:ERC:%d" % (bname, idx)
            setFloatProp(rig.data, prop, 0.0, None, None, True)
            fcu1 = rig.data.animation_data.drivers.from_existing(src_driver=fcu0)
            fcu1.data_path = propRef(prop)
            if efcu.driver.type == 'SCRIPTED':
                efcu.driver.expression = "%s+y" % fcu.driver.expression
            elif efcu.driver.type == 'SUM':
                pass
            var = efcu.driver.variables.new()
            var.type = 'SINGLE_PROP'
            var.name = "y"
            trg = var.targets[0]
            trg.id_type = 'ARMATURE'
            trg.id = rig.data
            trg.data_path = propRef(prop)
        elif fcu0:
            fcu0.data_path = 'pose.bones["%s"].location' % ercb.name

        pb.driver_remove("location", idx)
        fcu = pb.driver_add("location", idx)
        fcu.driver.type = 'SCRIPTED'
        fcu.driver.expression = "-x"
        var = fcu.driver.variables.new()
        var.type = 'TRANSFORMS'
        var.name = "x"
        trg = var.targets[0]
        trg.id = rig
        trg.bone_target = ercb.name
        trg.transform_type = ttype
        trg.transform_space = 'LOCAL_SPACE'

    for channel,n in [("rotation_euler",3), ("rotation_quaternion",4), ("scale",3)]:
        for idx in range(n):
            fcu0 = getDriver(rig, 'pose.bones["%s"].%s' % (drvb.name, channel), idx)
            if fcu0:
                fcu0.data_path = 'pose.bones["%s"].%s' % (ercb.name, channel)

    removeConstraints(pb)
    cns = copyTransform(pb, ercb, rig, space='LOCAL')
    cns.mix_mode = 'BEFORE_FULL'
    pb.name = defBone(bname)
    ercb.name = bname
    copyBoneInfo(pb, ercb)
    copyBoneLayers(pb, ercb, rig)
    enableBoneNumLayer(pb.bone, rig, T_BONES)
    pb.bone.color.palette = 'THEME04'
    pb.color.palette = 'THEME04'
    if drvb != pb:
        for channel in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
            drvb.driver_remove(channel)

#-------------------------------------------------------------
#   Add HdOffset formulas. For IK bones
#-------------------------------------------------------------

def initErcDrivers(context, rig):
    from collections import OrderedDict

    if GS.ercMethod.startswith("ARMATURE"):
        LS.ercFormulas = OrderedDict()
        LS.ercDrivers = {}
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                bname,channel,_ = getBoneChannel(fcu)
                if channel == "HdOffset":
                    paths = [trg.data_path
                             for var in fcu.driver.variables
                             for trg in var.targets]
                    LS.ercDrivers["%s:%d" % (bname, fcu.array_index)] = paths
    else:
        for pb in rig.pose.bones:
            pb.driver_remove("HdOffset")

    if GS.ercMethod.startswith("ERC"):
        LS.ercFormulas = OrderedDict()
        LS.ercDrivers = {}
        if rig.data.animation_data is None:
            return
        ercpaths = set()
        for fcu in list(rig.data.animation_data.drivers):
            if ":Loc:" in fcu.data_path and fcu.driver.type == 'SCRIPTED':
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        ercpaths.add(trg.data_path)

        LS.ercMats = {}
        for path in ercpaths:
            prop = baseProp(getProp(path))
            setProp(rig, prop)
            updateRigDrivers(context, rig)
            LS.ercMats[prop] = dict([(pb.name, pb.matrix.copy()) for pb in rig.pose.bones])
            clearProp(rig, prop)


def addErcDrivers(context, rig):
    def getBoneNames(form, idx):
        key = form[0]
        if key == "BONE":
            return form[1], None
        elif key == "COMP":
            return form[1+idx], None
        elif key == "MID":
            return form[1], form[2]
        else:
            print("Unknown HdOffset formula", form)

    def addOffsetDrivers(rig):
        from .driver import addDriverVar

        for bname,form in LS.ercFormulas.items():
            pb = rig.pose.bones.get(bname)
            if pb is None:
                print("Missing bone:", bname)
                continue
            for idx in range(3):
                bname1, bname2 = getBoneNames(form, idx)
                paths = LS.ercDrivers.get("%s:%s" % (bname1, idx))
                if paths is None:
                    if isDrvBone(bname1):
                        paths = LS.ercDrivers.get("%s:%s" % (baseBone(bname1), idx))
                    else:
                        paths = LS.ercDrivers.get("%s:%s" % (drvBone(bname1), idx))
                if paths:
                    pb.driver_remove("HdOffset", idx)
                    fcu = pb.driver_add("HdOffset", idx)
                    if bname2:
                        paths = paths + LS.ercDrivers.get("%s:%s" % (bname2, idx), [])
                    fcu.driver.type = 'SCRIPTED'
                    expr = ""
                    for n,path in enumerate(paths):
                        vname = "t%d" % n
                        addDriverVar(fcu, vname, path, rig.data)
                        expr += "+%s" % vname
                    if len(paths) > 1:
                        fcu.driver.expression = "(%s)/%d" % (expr[1:], len(paths))
                    else:
                        fcu.driver.expression = expr
                    LS.ercDrivers["%s:%s" % (bname, idx)] = paths
                elif not isDspBone(bname):
                    print("Missing ERC driver", bname, bname1, idx)

    def addErcBoneDrivers(context, rig):
        from .rig_utils import copyTransform
        for bname,form in LS.ercFormulas.items():
            pb = rig.pose.bones[bname]
            drvb = rig.pose.bones[drvBone(bname)]
            drvb.driver_remove("location")
            drvb.bone.color.palette = 'THEME14'
            drvb.color.palette = 'THEME14'
            for idx in range(3):
                fcu = drvb.driver_add("location", idx)
                bname1, bname2 = getBoneNames(form, idx)
                pb1 = rig.pose.bones.get(bname1)
                if pb1 is None:
                    print("Missing bone: ", bname, bname1)
                    continue
                expr = ""
                vname = "A"
                for prop,gmats in LS.ercMats.items():
                    test = (bname.startswith(("lHand")) and idx==0)

                    # M1 = M0 * R0^-1 * R1 * L1
                    # L1 = R1^-1 * R0 * M0^-1 * M1
                    M1 = gmats[bname1]
                    R1 = drvb.bone.matrix_local
                    L1 = R1.inverted() @ M1
                    if test:
                        print("GG1", bname, bname1, pb1.name, prop, idx)
                        print(M1)
                    if pb1.parent:
                        parname = ercBase(pb1.parent.name)
                        M0 = gmats.get(defBone(parname))
                        if M0 is None:
                            M0 = gmats.get(parname)
                        if test:
                            print("PAR", parname)
                            print(M0)
                        if M0:
                            R0 = pb1.parent.bone.matrix_local
                            U0 = drvb.parent.bone.matrix_local
                            L1 = R1.inverted() @ R0 @ M0.inverted() @ M1
                        else:
                            print("Missing matrix:", parname)

                    lloc = L1.to_translation()
                    expr += "+%.3f*%s" % (lloc[idx], vname)
                    var = fcu.driver.variables.new()
                    var.name = vname
                    trg = var.targets[0]
                    trg.id_type = 'OBJECT'
                    trg.id = rig
                    trg.data_path = propRef(prop)
                    vname = nextLetter(vname)
                fcu.driver.expression = expr[1:]

            cns = copyTransform(pb, drvb, rig, space='LOCAL')
            cns.mix_mode = 'BEFORE_FULL'

    if GS.ercMethod.startswith("ARMATURE"):
        if LS.ercDrivers:
            addOffsetDrivers(rig)
    elif GS.ercMethod.startswith("ERC"):
        addErcBoneDrivers(context, rig)

#-------------------------------------------------------------
#  Remove Posable Bones
#-------------------------------------------------------------

class DAZ_OT_RemovePosableBones(DazOperator, IsArmature):
    bl_idname = "daz.remove_posable_bones"
    bl_label = "Remove Posable Bones"
    bl_description = "Remove Posable Bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        removePosableBones(rig)


def removePosableBones(rig):
    # Retarget drivers
    if rig.animation_data:
        for fcu in list(rig.animation_data.drivers):
            bname,_,_ = getBoneChannel(fcu)
            if bname is None:
                pass
            elif isDrvBone(bname):
                fcu.data_path = fcu.data_path.replace("(drv)", "")
            elif isDefBone(bname):
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        trg.bone_target = baseBone(trg.bone_target)
    # Remove constraints
    for pb in rig.pose.bones:
        for cns in list(pb.constraints):
            if cns.type == 'COPY_TRANSFORMS' and isDrvBone(cns.subtarget):
                pb.constraints.remove(cns)
    # Remove posable bones and rename drv bones
    setMode('EDIT')
    for drvb in list(rig.data.edit_bones):
        if isDrvBone(drvb.name):
            bname = baseBone(drvb.name)
            eb = rig.data.edit_bones.get(bname)
            if eb:
                drvb.use_deform = eb.use_deform
                rig.data.edit_bones.remove(eb)
                drvb.name = bname
    setMode('OBJECT')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddErcBones,
    DAZ_OT_UpdateErcBones,
    DAZ_OT_RemovePosableBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

