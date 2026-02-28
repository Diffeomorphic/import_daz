# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import numpy as np
from .utils import *
from .error import *

#------------------------------------------------------------------
#   Apply transforms
#------------------------------------------------------------------

class DAZ_OT_ApplyTransforms(DazOperator):
    bl_idname = "daz.apply_transforms"
    bl_label = "Apply Transforms"
    bl_description = "Apply transforms to selected objects and its children"
    bl_options = {'UNDO'}

    def run(self, context):
        objects = getSelectedObjectAndChildren(context)
        applyTransforms(objects)


def getSelectedObjectAndChildren(context):
    def addChildren(ob):
        objects.append(ob)
        for child in ob.children:
             addChildren(child)

    objects = []
    for ob in getSelectedObjects(context):
        addChildren(ob)
    return set(objects)


def applyTransforms(objects):
    print("Apply transforms")
    bpy.ops.object.select_all(action='DESELECT')
    wmats = []
    vpmats = []
    status = []
    for ob in objects:
        try:
            status.append((ob, ob.hide_get(), ob.hide_select))
            ob.hide_set(False)
            ob.hide_select = False
            if ob.parent and ob.parent_type == 'BONE':
                wmats.append((ob, ob.matrix_world.copy()))
            elif ob.parent and ob.parent_type.startswith('VERTEX'):
                vpmats.append((ob, ob.parent.matrix_basis.copy()))
            elif ob.type in ['MESH', 'ARMATURE']:
                selectSet(ob, True)
        except ReferenceError:
            pass

    removeObjectDrivers(objects)
    safeTransformApply()
    for ob,wmat in wmats:
        setWorldMatrix(ob, wmat)
    for ob,vpmat in vpmats:
        ob.matrix_basis = vpmat.inverted() @ ob.matrix_basis
    for ob,hide,select in status:
        ob.hide_set(hide)
        ob.hide_select = select

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(CollectionShower, DazPropsOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    useApplyTransforms : BoolProperty(
        name = "Apply Object Transforms",
        description = "Apply Object Transforms",
        default = True)

    useApplyShapekeys : BoolProperty(
        name = "Apply Shapekeys",
        description = "Apply all shapekeys",
        default = False)

    useMergeTiedBones : BoolProperty(
        name = "Merge Tied Bones",
        description = "Merge tied bones to main rig and delete tied rigs",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useApplyTransforms")
        self.layout.prop(self, "useApplyShapekeys")
        self.layout.prop(self, "useMergeTiedBones")

    def run(self, context):
        rig = context.object
        objects = getSelectedObjectAndChildren(context)
        if self.useApplyTransforms:
            applyTransforms(objects)
        tied = applyRestPoses(context, rig, self.useMergeTiedBones)
        if self.useApplyShapekeys:
            for ob in objects:
                if ob.type == 'MESH':
                    applyAllShapekeys(ob)
        if tied:
            deleteObjects(context, tied)


def applyRestPoses(context, rig, useMergeTiedBones=False):
    if rig is None:
        return []

    def muteShapekeys(skeys):
        muted = []
        if skeys:
            for skey in skeys.key_blocks:
                muted.append((skey, skey.mute))
                skey.mute = True
        return muted

    def applyModifiers(rig, children, hasamt, tied):
        for ob in rig.children:
            if activateObject(context, ob):
                children.append((ob, ob.parent_type, ob.parent_bone, ob.matrix_world.copy()))
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                if dazRna(ob).DazTiedRig:
                    tied.append((ob, list(ob.children)))
                    applyModifiers(ob, children, hasamt, tied)
                elif ob.type == 'MESH' and ob.parent_type == 'OBJECT':
                    mod = getModifier(ob, 'ARMATURE')
                    skeys = ob.data.shape_keys
                    if mod:
                        hasamt.append(ob)
                        muted = muteShapekeys(ob.data.shape_keys)
                        applyArmatureModifier(ob)
                        for skey,mute in muted:
                            skey.mute = mute

    children = []
    hasamt = []
    tied = []
    applyModifiers(rig, children, hasamt, tied)

    def removeBoneDrivers(rig):
        bmats = {}
        for pb in rig.pose.bones:
            bmats[pb.name] = pb.matrix_basis.copy()
        changed = []
        if rig.animation_data:
            for fcu in list(rig.animation_data.drivers):
                bname,channel,cnsname = getBoneChannel(fcu)
                if (bname in rig.pose.bones.keys() and
                    cnsname is None and
                    channel != "HdOffset"):
                    pb = rig.pose.bones[bname]
                    value = getattr(pb, channel)[fcu.array_index]
                    if abs(value) > getEpsilon(channel):
                        bmat = bmats.get(bname)
                        if bmat:
                            rig.animation_data.drivers.remove(fcu)
                            changed.append(bname)
        for bname in set(changed):
            pb = rig.pose.bones[bname]
            pb.matrix_basis = bmats[bname]

    def mergeTiedBones(tied, rig):
        from .merge_rigs import BoneInfo, getDupName
        infos = []
        bnames = []
        dups = []
        for subrig,children in tied:
            binfos = {}
            infos.append((subrig, binfos, children))
            for pb in subrig.pose.bones:
                if not getConstraint(pb, 'COPY_TRANSFORMS'):
                    parname = None
                    if pb.bone.parent:
                        parname = pb.bone.parent.name
                    binfo = BoneInfo(pb.bone, pb, parname, None)
                    lmat = pb.bone.matrix_local.copy()
                    bname = pb.name
                    binfos[bname] = (binfo, pb.matrix.copy())
                    if bname in bnames:
                        dups.append(bname)
                    else:
                        bnames.append(bname)
        dups = set(dups)
        setMode('EDIT')
        hasnew = False
        for subrig,binfos,children in infos:
            for bname,data in binfos.items():
                binfo,mat = data
                if bname in dups:
                    bname = getDupName(subrig, bname)
                eb = binfo.setEditBone(bname, rig.data.edit_bones, subrig)
                eb.matrix = mat
                hasnew = True
        setMode('OBJECT')
        if hasnew:
            enableRigNumLayer(rig, T_CUSTOM)
            for subrig,binfos,children in infos:
                for bname in binfos.keys():
                    if bname in dups:
                        bname = getDupName(subrig, bname)
                    pb = rig.pose.bones.get(bname)
                    if bname:
                        enableBoneNumLayer(pb.bone, rig, T_CUSTOM)
                for bname in dups:
                    for ob in children:
                        vgrp = ob.vertex_groups.get(bname)
                        if vgrp:
                            vgrp.name = getDupName(subrig, bname)

    if activateObject(context, rig):
        removeBoneDrivers(rig)
        bpy.ops.object.transform_apply()
        setMode('POSE')
        bpy.ops.pose.armature_apply()
        setMode('OBJECT')
        if tied and useMergeTiedBones:
            mergeTiedBones(tied, rig)

    for ob,type,bone,wmat in children:
        ob.parent = rig
        ob.parent_type = type
        ob.parent_bone = bone
        setWorldMatrix(ob, wmat)
    from .modifier import newArmatureModifier
    for ob in hasamt:
        if activateObject(context, ob):
            newArmatureModifier(rig.name, ob, rig)
    return [subrig for subrig,children in tied]


def removeObjectDrivers(objects):
    for ob in objects:
        try:
            adata = ob.animation_data
        except ReferenceError:
            continue
        if adata:
            for fcu in list(ob.animation_data.drivers):
                if fcu.data_path in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
                    ob.animation_data.drivers.remove(fcu)


def safeTransformApply(useLocRot=True):
    try:
        bpy.ops.object.transform_apply(location=useLocRot, rotation=useLocRot, scale=True)
        ok = True
    except RuntimeError:
        ok = False
    if not ok:
        bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False, obdata_animation=False)
        try:
           bpy.ops.object.transform_apply(location=useLocRot, rotation=useLocRot, scale=True)
        except RuntimeError as err:
            raise DazError(err)


def applyAllObjectTransforms(rigs):
    bpy.ops.object.select_all(action='DESELECT')
    for rig in rigs:
        selectSet(rig, True)
    safeTransformApply()
    bpy.ops.object.select_all(action='DESELECT')
    status = []
    try:
        for rig in rigs:
            for ob in rig.children:
                if ob.parent_type != 'BONE':
                    status.append((ob, ob.hide_get(), ob.hide_select))
                    ob.hide_set(False)
                    ob.hide_select = False
                    selectSet(ob, True)
        safeTransformApply()
        for ob,hide,select in status:
            ob.hide_set(hide)
            ob.hide_select = select
        return True
    except RuntimeError:
        print("Could not apply object transformations")
        return False


def applyArmatureModifier(ob):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE':
            mname = mod.name
            if ob.data.shape_keys:
                applyModifierAsShape(mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                applyModifier(mname)

#----------------------------------------------------------
#   Apply shapekeys
#----------------------------------------------------------

def applyAllShapekeys(ob):
    skeys = ob.data.shape_keys
    applied = []
    if skeys:
        nverts = len(ob.data.vertices)
        verts = np.array([v.co for v in ob.data.vertices])
        coords = verts.copy()
        for skey in skeys.key_blocks:
            scoords = np.array([skey.data[n].co for n in range(nverts)])
            coords += skey.value*(scoords - verts)
            applied.append(skey)
        applied.reverse()
        for skey in applied:
            ob.shape_key_remove(skey)
        for v,co in zip(ob.data.vertices, coords):
            v.co = co

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ApplyTransforms,
    DAZ_OT_ApplyRestPoses,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

