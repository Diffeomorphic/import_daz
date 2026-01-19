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
    from .figure import copyBoneInfo
    from .store import copyConstraint, removeConstraints
    from .driver import setFloatProp, getDriver
    from .rig_utils import copyTransform

    ercbones = [pb for pb in rig.pose.bones if isErcBone(pb.name)]
    basebones = [rig.pose.bones.get(ercBase(pb.name)) for pb in ercbones]
    for pb, ercb in zip(basebones, ercbones):
        if pb is None:
            continue
        bname = pb.name
        drvb = rig.pose.bones.get(drvBone(bname), pb)
        removeConstraints(ercb)
        for cns in pb.constraints:
            if cns.type == 'LIMIT_ROTATION':
                copyConstraint(cns, ercb, rig)

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

#-------------------------------------------------------------
#   Add HdOffset formulas. For IK bones
#-------------------------------------------------------------

def removeOffsetDrivers(rig):
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


def addOffsetDrivers(rig):
    from .driver import addDriverVar
    for bname,form in LS.ercFormulas.items():
        pb = rig.pose.bones.get(bname)
        for idx in range(3):
            key = form[0]
            if key == "BONE":
                bname1 = form[1]
            elif key == "COMP":
                bname1 = form[1+idx]
            else:
                print("Unknown HdOffset formula", form)
            paths = LS.ercDrivers.get("%s:%s" % (bname1, idx))
            if paths:
                fcu = pb.driver_add("HdOffset", idx)
                fcu.driver.type = 'SUM'
                for n,path in enumerate(paths):
                    addDriverVar(fcu, "t%02d" % n, path, rig.data)
                LS.ercDrivers["%s:%s" % (bname, idx)] = paths
            elif not isDspBone(bname):
                print("Missing ERC driver", bname, bname1, idx)

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

