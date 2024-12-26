# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
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
    status = []
    for ob in objects:
        try:
            status.append((ob, ob.hide_get(), ob.hide_select))
            ob.hide_set(False)
            ob.hide_select = False
            if ob.parent and ob.parent_type == 'BONE':
                wmats.append((ob, ob.matrix_world.copy()))
            elif ob.parent and ob.parent_type.startswith('VERTEX'):
                pass
            elif ob.type in ['MESH', 'ARMATURE']:
                selectSet(ob, True)
        except ReferenceError:
            pass

    removeObjectDrivers(objects)
    safeTransformApply()
    for ob,wmat in wmats:
        setWorldMatrix(ob, wmat)
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
        name = "Apply Transforms",
        description = "Apply Object Transforms",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useApplyTransforms")

    def run(self, context):
        rig = context.object
        if self.useApplyTransforms:
            objects = getSelectedObjectAndChildren(context)
            applyTransforms(objects)
        applyRestPoses(context, rig)


def applyRestPoses(context, rig):
    def muteShapekeys(skeys):
        muted = []
        if skeys:
            for skey in skeys.key_blocks:
                muted.append((skey, skey.mute))
                skey.mute = True
        return muted

    children = []
    hasamt = []
    for ob in rig.children:
        if activateObject(context, ob):
            children.append((ob, ob.parent_type, ob.parent_bone, ob.matrix_world.copy()))
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            if ob.type == 'MESH' and ob.parent_type == 'OBJECT':
                mod = getModifier(ob, 'ARMATURE')
                skeys = ob.data.shape_keys
                if mod:
                    hasamt.append(ob)
                    muted = muteShapekeys(ob.data.shape_keys)
                    applyArmatureModifier(ob)
                    for skey,mute in muted:
                        skey.mute = mute

    def removeBoneDrivers(rig):
        bmats = {}
        for pb in rig.pose.bones:
            bmats[pb.name] = pb.matrix_basis.copy()
        changed = []
        if rig.animation_data:
            for fcu in list(rig.animation_data.drivers):
                bname,channel,cnsname = getBoneChannel(fcu)
                if cnsname is None and channel != "HdOffset":
                    pb = rig.pose.bones[bname]
                    value = getattr(pb, channel)[fcu.array_index]
                    if abs(value) > 1e-6:
                        bmat = bmats.get(bname)
                        if bmat:
                            rig.animation_data.drivers.remove(fcu)
                            changed.append(bname)
        for bname in set(changed):
            pb = rig.pose.bones[bname]
            pb.matrix_basis = bmats[bname]

    if activateObject(context, rig):
        removeBoneDrivers(rig)
        bpy.ops.object.transform_apply()
        setMode('POSE')
        bpy.ops.pose.armature_apply()
        setMode('OBJECT')

    for ob,type,bone,wmat in children:
        ob.parent = rig
        ob.parent_type = type
        ob.parent_bone = bone
        setWorldMatrix(ob, wmat)
    from .modifier import newArmatureModifier
    for ob in hasamt:
        newArmatureModifier(rig.name, ob, rig)


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
    except RuntimeError as err:
        print("Cannot apply transforms")


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
                if bpy.app.version < (2,90,0):
                    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                else:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                bpy.ops.object.modifier_apply(modifier=mname)


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

