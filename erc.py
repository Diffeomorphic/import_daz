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
        ercb = deriveBone(ercBone(bname), eb, rig, "ERC", None)
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
    coll = rig.data.collections.get("ERC")
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
        copyBoneInfo(pb, ercb)
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

            for channel in ["rotation_euler", "rotation_quaternion", "scale"]:
                fcu0 = getDriver(rig, 'pose.bones["%s"].%s' % (drvb.name, channel), idx)
                if fcu0:
                    fcu0.data_path = 'pose.bones["%s"].%s' % (ercb.name, channel)

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

        removeConstraints(pb)
        cns = copyTransform(pb, ercb, rig, space='LOCAL')
        cns.mix_mode = 'BEFORE_FULL'
        pb.name = defBone(bname)
        ercb.name = bname
        ercb.lock_location = pb.lock_location
        ercb.lock_rotation = pb.lock_rotation
        ercb.lock_scale = pb.lock_scale
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

    coll = rig.data.collections.get("Bones")
    if coll:
        coll.is_visible = False
    coll = rig.data.collections.get("ERC")
    if coll:
        coll.is_visible = True
    dazRna(rig.data).DazErcStatus = 2

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddErcBones,
    DAZ_OT_UpdateErcBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

