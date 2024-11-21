# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.app.handlers import persistent
from .utils import *
from .driver import isProtected

#----------------------------------------------------------
#   Morphs UIList
#----------------------------------------------------------

theFilterFlags = {}
theFilterInvert = {}

def morphText(rig, morph, prefix):
    label = morph.text
    n = len(prefix)
    if label.lower()[0:n] == prefix:
        label = label[n:]
    if isProtected(rig, morph.name):
        return "* %s" % label
    else:
        return label


class DAZ_UL_MorphList(bpy.types.UIList):
    def draw_item(self, context, layout, data, morph, icon, active, indexProp):
        rig,amt = self.getRigAmt(context)
        key = morph.name
        if rig is None or key not in rig.keys():
            return
        morphset, category = self.getMorphCat(data)
        if morphset == "Custom" and GS.useStripCategory:
            prefix = category.lower()
        else:
            prefix = ""
        split = layout.split(factor=0.8)
        final = finalProp(key)
        if GS.showFinalProps and final in amt.keys():
            split2 = split.split(factor=0.8)
            split2.prop(rig, propRef(key), text=morphText(rig, morph, prefix))
            split2.label(text = "%.3f" % amt[final])
        else:
            split.prop(rig, propRef(key), text=morphText(rig, morph, prefix))
        row = split.row()
        self.showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset = morphset
        op.category = category
        op.ftype = self.getFilterType(data)


    def getRigAmt(self, context):
        rig = context.object
        while rig.type != 'ARMATURE' and rig.parent:
            rig = rig.parent
        if rig.type == 'ARMATURE':
            return rig, rig.data
        else:
            return None, None


    def showBool(self, layout, ob, key, text=""):
        from .selector import getExistingActivateGroup
        pg = getExistingActivateGroup(ob, key)
        if pg is not None:
            layout.prop(pg, "active", text=text)


    def filter_items(self, context, data, propname):
        global theFilterFlags, theFilterInvert
        morphs = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list
        flt_flags = []
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, morphs, "text")
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(morphs)

        if GS.showUsedPropsOnly and isinstance(data, bpy.types.Object):
            amt = data.data
            flt_flags = [flag * (amt.get(finalProp(morph.name), 0.0) != 0.0)
                         for flag,morph in zip(flt_flags, morphs)]

        flt_neworder = helper_funcs.sort_items_by_name(morphs, "text")
        ftype = self.getFilterType(data)
        theFilterFlags[ftype] = flt_flags
        theFilterInvert[ftype] = self.use_filter_invert
        return flt_flags, flt_neworder


def canonizeCat(catname):
    return "".join([c for c in catname if c.isalnum()])


class DAZ_UL_StandardMorphs(DAZ_UL_MorphList):
    def getMorphCat(self, data):
        return self.morphset, ""

    def getFilterType(self, data):
        return "Daz%s" % self.morphset


class DAZ_UL_CustomMorphs(DAZ_UL_MorphList):
    def getMorphCat(self, cat):
        return "Custom", cat.name

    def getFilterType(self, cat):
        return "Custom/%s" % cat.name


class DAZ_UL_Shapekeys(DAZ_UL_MorphList):
    def draw_item(self, context, layout, cat, morph, icon, active, indexProp):
        if GS.useMeshDrivers:
            DAZ_UL_MorphList.draw_item(self, context, layout, cat, morph, icon, active, indexProp)
            return
        ob = context.object
        skeys = ob.data.shape_keys
        key = morph.name
        if skeys and key in skeys.key_blocks.keys():
            skey = skeys.key_blocks[key]
            row = layout.split(factor=0.8)
            row.prop(skey, "value", text=morph.text)
            self.showBool(row, ob, key)
            op = row.operator("daz.pin_shape", icon='UNPINNED')
            op.key = key
            op.category = cat.name

    def getMorphCat(self, cat):
        return "Mesh", cat.name

    def getFilterType(self, cat):
        return "Mesh/%s" % cat.name

    def getRigAmt(self, context):
        ob = context.object
        if ob.type == 'MESH':
            return ob, ob.data
        else:
            return None, None

#-------------------------------------------------------------
#   Update scrollbars
#-------------------------------------------------------------

class DAZ_OT_UpdateScrollbars(bpy.types.Operator):
    bl_idname = "daz.update_scrollbars"
    bl_label = "Update Scrollbars"
    bl_description = "Update all scrollbars"

    def execute(self, context):
        print("Update Scrollbars:", [ob.name for ob in context.scene.objects])
        updateScrollbars(context)
        return{'FINISHED'}


def updateScrollbars(context):
    def updateRigScrollbars(scn, rig):
        global theMorphScrollbars
        for cat in rig.DazMorphCats:
            catname = canonizeCat(cat.name)
            if catname not in theMorphScrollbars.keys():
                classname = "DAZ_UL_Custom_%s" % catname
                new_type = type(classname, (DAZ_UL_CustomMorphs,), {})
                bpy.utils.register_class(new_type)
                theMorphScrollbars[catname] = new_type

    def updateMeshScrollbars(scn, ob):
        global theShapeScrollbars
        for cat in ob.DazMorphCats:
            catname = canonizeCat(cat.name)
            if catname not in theShapeScrollbars.keys():
                classname = "DAZ_UL_Shape_%s" % catname
                new_type = type(classname, (DAZ_UL_Shapekeys,), {})
                bpy.utils.register_class(new_type)
                theShapeScrollbars[catname] = new_type

    scn = context.scene
    for ob in scn.objects:
        if ob.type == 'ARMATURE':
            updateRigScrollbars(scn, ob)
        elif ob.type == 'MESH':
            updateMeshScrollbars(scn, ob)

#-------------------------------------------------------------
#   Get UIList class name
#-------------------------------------------------------------

def getCustomUIList(cat, scn):
    global theMorphScrollbars
    catname = canonizeCat(cat.name)
    if catname in theMorphScrollbars.keys():
        return "DAZ_UL_Custom_%s" % catname
    else:
        return "DAZ_UL_CustomMorphs"


def getShapeUIList(cat, scn):
    global theShapeScrollbars
    catname = canonizeCat(cat.name)
    if catname in theShapeScrollbars.keys():
        return "DAZ_UL_Shape_%s" % catname
    else:
        return "DAZ_UL_Shapekeys"

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

@persistent
def onLoad(dummy):
    updateScrollbars(bpy.context)


classes = [
    DAZ_UL_CustomMorphs,
    DAZ_UL_Shapekeys,
    DAZ_OT_UpdateScrollbars,
]

theMorphScrollbars = {}
theShapeScrollbars = {}

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(onLoad)


def unregister():
    bpy.app.handlers.load_post.remove(onLoad)
    for cls in theMorphScrollbars.values():
        bpy.utils.unregister_class(cls)
    for cls in theShapeScrollbars.values():
        bpy.utils.unregister_class(cls)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
