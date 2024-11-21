# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *

#-------------------------------------------------------------
#   Apply subsurf modifier
#-------------------------------------------------------------

class SubsurfApplier:
    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False

    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def getModifier(self, ob):
        return getModifier(ob, self.modifierType)


    def run(self, context):
        from ..driver import Driver
        ob = context.object
        mod = self.getModifier(ob)
        if not mod:
            raise DazError("Object %s\n has no %s modifier.    " % (ob.name, self.modifierType))

        startProgress("Apply %s Modifier" % self.modifierType)
        nob = copyObject(ob, "XXX")
        applyShape(nob, 0)
        applyModifier(context, nob, mod.name)
        drivers = []
        skeys = ob.data.shape_keys
        if skeys:
            if skeys.animation_data:
                for fcu in skeys.animation_data.drivers:
                    drivers.append(Driver(fcu, True))
            for idx,skey in enumerate(skeys.key_blocks):
                tmp = copyObject(ob, skey.name)
                applyShape(tmp, idx)
                applyModifier(context, tmp, mod.name)
                copyShape(tmp, nob, skey.name)
                deleteObjects(context, [tmp])

        # Restore drivers
        nskeys = nob.data.shape_keys
        if nskeys:
            for driver in drivers:
                sname,channel = getShapeChannel(driver)
                if sname:
                    nskey = nskeys.key_blocks.get(sname)
                    if nskey:
                        fcu = nskey.driver_add(channel)
                        driver.fill(fcu)

        if self.useRecreate:
            self.recreate(context, ob, nob)
        else:
            activateObject(context, nob)
        obname = ob.name
        nob.name = obname
        nob.name = obname
        deleteObjects(context, [ob])


    def recreate(self, context, ob, nob):
        if self.useApplyRest:
            rig = ob.parent
            if rig and activateObject(context, rig):
                setMode('POSE')
                bpy.ops.pose.armature_apply(selected=False)
                setMode('OBJECT')
        activateObject(context, nob)
        nob.modifiers.clear()
        for mod in ob.modifiers:
            nmod = nob.modifiers.new(mod.name, mod.type)
            for key in dir(mod):
                copyModifier(mod, nmod)
        nob.parent = ob.parent


def copyModifier(smod, tmod):
    for attr in dir(smod):
        if (attr[0] != "_" and
            attr not in ["bl_rna", "is_override_data", "rna_type", "type"]):
            value = getattr(smod, attr)
            if (isSimpleType(value) or
                isinstance(value, (bpy.types.Object, bpy.types.NodeTree))):
                try:
                    setattr(tmod, attr, getattr(smod, attr))
                except AttributeError:
                    pass


def copyObject(ob, name):
    nob = ob.copy()
    nob.name = name
    if ob.data:
        nob.data = ob.data.copy()
        nob.data.name = name
    for coll in bpy.data.collections:
        if ob.name in coll.objects:
            coll.objects.link(nob)
    return nob


def applyShape(ob, idx):
    skeys = ob.data.shape_keys
    if skeys is not None:
        for n,skey in reversed(list(enumerate(skeys.key_blocks))):
            if n != idx:
                ob.shape_key_remove(skey)
        ob.shape_key_remove(skeys.key_blocks[0])


def applyModifier(context, ob, modname):
    activateObject(context, ob)
    bpy.ops.object.modifier_apply(modifier=modname)


def copyShape(src, trg, sname):
    skey = trg.shape_key_add(name=sname)
    data = skey.data
    for vn,v in enumerate(src.data.vertices):
        data[vn].co = v.co.copy()


class DAZ_OT_ApplySubsurf(SubsurfApplier, DazOperator, IsMesh):
    bl_idname = "daz.apply_subsurf"
    bl_label = "Apply Subsurf"
    bl_description = "Apply subsurf modifier, maintaining shapekeys"
    bl_options = {'UNDO'}

    modifierType = 'SUBSURF'
    useRecreate = False


class DAZ_OT_ApplyMultires(SubsurfApplier, DazOperator, IsMesh):
    bl_idname = "daz.apply_multires"
    bl_label = "Apply Multires"
    bl_description = "Apply multires modifier, maintaining shapekeys"
    bl_options = {'UNDO'}

    modifierType = 'MULTIRES'
    useRecreate = False


class DAZ_OT_ApplyActiveModifier(SubsurfApplier, DazPropsOperator, IsMesh):
    bl_idname = "daz.apply_active_modifier"
    bl_label = "Apply Active Modifier"
    bl_description = "Apply active modifier, maintaining shapekeys"
    bl_options = {'UNDO'}

    modifierType = 'ACTIVE'

    useRecreate : BoolProperty(
        name = "Recreate Modifier",
        description = "Create a new modifier of the same type",
        default = True)

    useApplyRest : BoolProperty(
        name = "Apply Rest Pose",
        description = "Apply parent rig rest pose",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useRecreate")
        self.layout.prop(self, "useApplyRest")

    def getModifier(self, ob):
        mod = ob.modifiers.active
        if mod:
            self.modifierType = mod.type
        return mod

#----------------------------------------------------------
#   Copy modifiers
#----------------------------------------------------------

class DAZ_OT_CopyModifiers(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_modifiers"
    bl_label = "Copy Modifiers"
    bl_description = "Copy modifiers from active mesh to selected"
    bl_options = {'UNDO'}

    offset : FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 5.0)

    useSubsurf : BoolProperty(
        name = "Use Subsurf",
        description = "Also copy subsurf and multires modifiers",
        default = False)

    useRemoveCloth : BoolProperty(
        name = "Remove Cloth",
        description = "Remove cloth modifiers from source mesh",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useSubsurf")
        self.layout.prop(self, "useRemoveCloth")

    def run(self, context):
        from .store import ModStore
        src = context.object
        stores = []
        for mod in list(src.modifiers):
            if (self.useSubsurf or
                mod.type not in ['SUBSURF', 'MULTIRES']):
                stores.append(ModStore(mod))
            if (self.useRemoveCloth and
                mod.type in ['COLLISION', 'CLOTH', 'SOFTBODY']):
                src.modifiers.remove(mod)
        for trg in getSelectedMeshes(context):
            if trg != src:
                trg.parent = src.parent
                for store in stores:
                    print("RES", store)
                    store.restore(trg)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_ApplySubsurf,
    DAZ_OT_ApplyMultires,
    DAZ_OT_ApplyActiveModifier,
    DAZ_OT_CopyModifiers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
