# Copyright (c) 2016-2021, Thomas Larsson
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
from .utils import *

#----------------------------------------------------------
#   Morphs UIList
#----------------------------------------------------------

# These would be saved with the .blend file
class UIListProps(bpy.types.PropertyGroup):
    # ~ name: bpy.props.StringProperty()  # this is created implicitly
    use_filter_invert: bpy.props.BoolProperty(name="Invert", default=False, description="Invert filtering")
    reverse_order: bpy.props.BoolProperty(name="Reverse", default=False, description="Reverse the order of shown items")
    filter_name: bpy.props.StringProperty(name="Filter by Name", default="", description="Only show items matching this name (use '*' as wildcard)", options={'TEXTEDIT_UPDATE'})


theFilterFlags = {}
theFilterInvert = {}

class DAZ_UL_MorphList(bpy.types.UIList):
    def draw_item(self, context, layout, data, morph, icon, active, indexProp):
        rig,amt = self.getRigAmt(context)
        key = morph.name
        if rig is None or key not in rig.keys():
            return
        split = layout.split(factor=0.8)
        final = finalProp(key)
        if GS.showFinalProps and final in amt.keys():
            split2 = split.split(factor=0.8)
            split2.prop(rig, propRef(key), text=morph.text)
            split2.label(text = "%.3f" % amt[final])
        else:
            split.prop(rig, propRef(key), text=morph.text)
        row = split.row()
        self.showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset, op.category = self.getMorphCat(data)
        op.ftype = self.getFilterType(data)


    def getRigAmt(self, context):
        rig = context.object
        while rig.type != 'ARMATURE' and rig.parent:
            rig = rig.parent
        if rig.type == 'ARMATURE':
            amt = rig.data
            return rig, amt
        else:
            return None, None


    def showBool(self, layout, ob, key, text=""):
        from .morphing import getExistingActivateGroup
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
        flt_neworder = helper_funcs.sort_items_by_name(morphs, "text")
        ftype = self.getFilterType(data)
        theFilterFlags[ftype] = flt_flags
        theFilterInvert[ftype] = self.use_filter_invert
        return flt_flags, flt_neworder


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


class DAZ_UL_Shapes(DAZ_UL_MorphList):
    def draw_item(self, context, layout, cat, morph, icon, active, indexProp):
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

    def getFilterType(self, cat):
        return "Mesh/%s" % cat.name

#-------------------------------------------------------------
#   Update dynamic classes
#-------------------------------------------------------------

class DAZ_OT_UpdateDynamicClasses(bpy.types.Operator):
    bl_idname = "daz.update_dynamic_classes"
    bl_label = "Update Dynamic Classes"
    bl_description = "Update all dynamic classes in the scene"

    def execute(self, context):
        for ob in getVisibleObjects(context):
            if ob.type == 'ARMATURE':
                updateRigClasses(context, ob)
            elif ob.type == 'MESH':
                updateMeshClasses(context, ob)
        return{'FINISHED'}


def updateRigClasses(context, rig):
    global theDynamicMorphClasses
    dynmorphs = context.scene.DazDynMorphs
    for cat in rig.DazMorphCats:
        uil = getattr(dynmorphs, cat.name, None)
        if uil is None:
            classname = "DAZ_UL_Custom_%s" % cat.name
            data = {}
            new_type = type(classname, (DAZ_UL_CustomMorphs,), data)
            bpy.utils.register_class(new_type)
            theDynamicMorphClasses[cat.name] = new_type
            uil = dynmorphs.add()
            uil.name = cat.name
    print("DD", theDynamicMorphClasses.items())


def updateMeshClasses(context, ob):
    global theDynamicShapeClasses
    print("MES", ob)
    dynshapes = context.scene.DazDynShapes
    for cat in ob.DazMorphCats:
        uil = getattr(dynshapes, cat.name, None)
        if uil is None:
            classname = "DAZ_UL_Shapes_%s" % cat.name
            data = {}
            new_type = type(classname, (DAZ_UL_Shapes,), data)
            bpy.utils.register_class(new_type)
            theDynamicShapeClasses[cat.name] = new_type
            uil = dynshapes.add()
            uil.name = cat.name
    print("SSS", theDynamicShapeClasses.items())


def getCustomUIList(cat):
    global theDynamicMorphClasses
    if cat.name in theDynamicMorphClasses.keys():
        return "DAZ_UL_Custom_%s" % cat.name
    else:
        return "DAZ_UL_CustomMorphs"

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    UIListProps,
    DAZ_UL_CustomMorphs,
    DAZ_UL_Shapes,

    DAZ_OT_UpdateDynamicClasses,
]

theDynamicMorphClasses = {}
theDynamicShapeClasses = {}

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.DazDynMorphs = bpy.props.CollectionProperty(type=UIListProps)
    bpy.types.Scene.DazDynShapes = bpy.props.CollectionProperty(type=UIListProps)


def unregister():
    for cls in theDynamicMorphClasses.values():
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.DazDynMorphs
    for cls in theDynamicShapeClasses:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.DazDynShapes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
