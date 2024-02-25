# Copyright (c) 2016-2024, Thomas Larsson
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


import os
import bpy

from .error import *
from .utils import *
from .driver import isProtected

#-------------------------------------------------------------
#   Selector
#-------------------------------------------------------------

def getSelector():
    global theSelector
    return theSelector

def setSelector(selector):
    global theSelector
    theSelector = selector


class DAZ_OT_SelectAll(bpy.types.Operator):
    bl_idname = "daz.select_all"
    bl_label = "All"
    bl_description = "Select all"

    def execute(self, context):
        getSelector().selectAll(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectNone(bpy.types.Operator):
    bl_idname = "daz.select_none"
    bl_label = "None"
    bl_description = "Select none"

    def execute(self, context):
        getSelector().selectNone(context)
        return {'PASS_THROUGH'}


class DazSelectGroup(bpy.types.PropertyGroup):
    text : StringProperty()
    category : StringProperty()
    index : IntProperty()
    select : BoolProperty()

    def __lt__(self, other):
        return (self.text < other.text)


class Selector():
    selection : CollectionProperty(type = DazSelectGroup)

    filter : StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
        )

    defaultSelect = False
    columnWidth = 180
    ncols = 6
    nrows = 20
    mincols = 3

    def draw(self, context):
        scn = context.scene
        self.drawSelectionRow()
        self.layout.prop(self, "filter", icon='VIEWZOOM', text="")
        self.drawExtra(context)
        self.layout.separator()
        items = [item for item in self.selection if self.isSelected(item)]
        items.sort()
        nitems = len(items)
        ncols = self.ncols
        nrows = self.nrows
        if nitems > ncols*nrows:
            nrows = nitems//ncols + 1
        else:
            ncols = nitems//nrows + 1
            if ncols < self.mincols:
                ncols = self.mincols
                nrows = (nitems-1)//ncols + 1
        cols = []
        for n in range(ncols):
            cols.append(items[0:nrows])
            items = items[nrows:]
        for m in range(nrows):
            row = self.layout.row()
            for col in cols:
                if m < len(col):
                    item = col[m]
                    row.prop(item, "select", text="")
                    row.label(text=item.text)
                else:
                    row.label(text="")


    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")


    def drawExtra(self, context):
        pass


    def selectAll(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = True


    def selectNone(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = False


    def isSelected(self, item):
        return (self.selectCondition(item) and self.filtered(item))


    def selectCondition(self, item):
        return True


    def filtered(self, item):
        return (not self.filter or self.filter.lower() in item.text.lower())


    def getSelectedItems(self):
        return [item for item in self.selection if item.select and self.isSelected(item)]


    def getSelectedProps(self):
        if LS.theFilePaths:
            return LS.theFilePaths
        else:
            return [item.name for item in self.getSelectedItems()]


    def invokeDialog(self, context):
        setSelector(self)
        LS.theFilePaths = []
        wm = context.window_manager
        ncols = len(self.selection)//self.nrows + 1
        if ncols > self.ncols:
            ncols = self.ncols
        elif ncols < self.mincols:
            ncols = self.mincols
        wm.invoke_props_dialog(self, width=ncols*self.columnWidth)
        return {'RUNNING_MODAL'}


    def invoke(self, context, event):
        scn = context.scene
        ob = context.object
        rig = self.rig = getRigFromContext(context)
        self.selection.clear()
        for idx,data in enumerate(self.getKeys(rig, ob)):
            prop,text,cat = data
            item = self.selection.add()
            item.name = prop
            item.text = text
            item.category = cat
            item.index = idx
            item.select = self.defaultSelect
        return self.invokeDialog(context)

#------------------------------------------------------------------------
#
#------------------------------------------------------------------------

def getActiveCategories(scn, context):
    ob = context.object
    cats = [(cat.name,cat.name,cat.name) for cat in ob.DazMorphCats]
    cats.sort()
    return cats

def getActiveAllCategories(scn, context):
    return [("All", "All", "All")] + getActiveCategories(scn, context)

class CustomEnums:
    custom : EnumProperty(
        items = getActiveCategories,
        name = "Category")

class CustomAllEnums:
    custom : EnumProperty(
        items = getActiveAllCategories,
        name = "Category")

#------------------------------------------------------------------------
#   Custom Selector
#------------------------------------------------------------------------

class CustomSelector(Selector, CustomAllEnums):

    def selectCondition(self, item):
        return (self.custom == "All" or item.category == self.custom)

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        keys = []
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys

#------------------------------------------------------------------------
#   JCM selector
#------------------------------------------------------------------------

class JCMSelector(Selector):
    bodypart : EnumProperty(
        items = [("All", "All", "All. Easy import transfers these shapekeys to all meshes"),
                 ("Face", "Face", "Face. Easy import transfers these shapekeys to lashes"),
                 ("Body", "Body", "Body. Easy import transfers these shapekeys to clothes and geografts"),
                 ("Custom", "Custom", "Custom. Easy import does not transfer these shapekeys"),
                 ("NoFace", "Body Or Custom", "Body or custom")],
        name = "Body part",
        description = "Part of character that the morphs affect",
        default = "All")

    def selectCondition(self, item):
        return (self.bodypart == "All" or
                item.category == self.bodypart or
                (self.bodypart == "NoFace" and item.category != "Face"))

    def drawSelectionRow(self):
        row = self.layout.row()
        row.prop(self, "bodypart")
        row.operator("daz.select_all")
        row.operator("daz.select_none")

    def getKeys(self, rig, ob):
        keys = []
        skeys = ob.data.shape_keys
        for skey in skeys.key_blocks[1:]:
            keys.append((skey.name, skey.name, self.bodyparts[skey.name]))
        return keys

    def invoke(self, context, event):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            print("Object %s has no shapekeys")
            return {'FINISHED'}
        self.bodyparts = classifyShapekeys(ob, skeys)
        return Selector.invoke(self, context, event)


def classifyShapekeys(ob, skeys):
    morphs = {}
    bodyparts = {}
    pgs = ob.data.DazBodyPart
    for skey in skeys.key_blocks[1:]:
        if skey.name in pgs.keys():
            item = pgs[skey.name]
            if item.s not in morphs.keys():
                morphs[item.s] = []
            morphs[item.s].append(skey.name)
            bodyparts[skey.name] = item.s
        else:
            bodyparts[skey.name] = "Custom"
    return bodyparts

#-------------------------------------------------------------
#   Classes
#-------------------------------------------------------------

class MorphGroup:
    morphset : StringProperty(default = "All")
    category : StringProperty(default = "")
    prefix : StringProperty(default = "")
    ftype : StringProperty(default = "")

    def init(self, morphset, category, prefix, ftype):
        self.morphset = morphset
        self.category = category
        self.prefix = prefix
        self.ftype = ftype


    def getFiltered(self):
        from .uilist import theFilterFlags, theFilterInvert
        if self.ftype in theFilterFlags.keys():
            if theFilterInvert[self.ftype]:
                return [(f == 0) for f in theFilterFlags[self.ftype]]
            else:
                return theFilterFlags[self.ftype]
        else:
            return 50*[True]


    def getRelevantMorphs(self, scn, rig, adjusters=False):
        filtered = self.getFiltered()
        morphs = []
        if rig is None:
            return morphs
        if self.morphset == "Custom":
            return self.getCustomMorphs(scn, rig)
        elif rig.DazMorphPrefixes:
            for key in rig.keys():
                if key[0:2] == "Dz":
                    raise DazError("OLD morphs", rig, key)
        elif self.morphset == "All":
            from .morphing import MS
            if adjusters:
                adj = "Adjust Morph Strength"
                if adj in rig.keys():
                    morphs.append(adj)
            for mset in MS.Standards:
                pgs = getattr(rig, "Daz%s" % mset)
                morphs += [key for key in pgs.keys()]
            for cat in rig.DazMorphCats:
                morphs += [morph.name for morph in cat.morphs]
        else:
            if adjusters:
                adj = "Adjust %s" % self.morphset
                if adj in rig.keys():
                    morphs.append(adj)
            pgs = getattr(rig, "Daz%s" % self.morphset)
            morphs += [key for key,on in zip(pgs.keys(), filtered) if on]
        return morphs


    def getCustomMorphs(self, scn, ob):
        filtered = self.getFiltered()
        morphs = []
        if self.category:
            for cat in ob.DazMorphCats:
                if cat.name == self.category:
                    morphs = [morph.name for morph,on in zip(cat.morphs, filtered) if on]
                    return morphs
        else:
            for cat in ob.DazMorphCats:
                morphs += [morph.name for morph,on in zip(cat.morphs, filtered) if on]
        return morphs


    def getRelevantShapes(self, ob):
        skeys = ob.data.shape_keys
        if skeys is None:
            return [], []
        if self.morphset == "All":
            morphs = list(skeys.key_blocks[1:])
            return morphs, skeys
        filtered = self.getFiltered()
        cats = []
        if self.category:
            cat = ob.DazMorphCats.get(self.category)
            if cat:
                cats = [cat]
        else:
            cats = ob.DazMorphCats
        morphs = []
        for cat in cats:
            morphs += [morph for morph,on in zip(cat.morphs, filtered) if on]
        return morphs, skeys

#------------------------------------------------------------------------
#   Select and unselect all
#------------------------------------------------------------------------

class Activator(MorphGroup):
    useMesh : BoolProperty(default=False)

    def run(self, context):
        scn = context.scene
        if self.useMesh:
            ob = context.object
            props = self.getCustomMorphs(scn, ob)
        else:
            ob = getRigFromContext(context)
            props = self.getRelevantMorphs(scn, ob)
        for prop in props:
            activate = self.getActivate(ob, prop)
            setActivated(ob, prop, activate)


def setActivated(ob, key, value):
    from .driver import setBoolProp
    if ob is None:
        return
    pg = getActivateGroup(ob, key)
    setBoolProp(pg, "active", value, True)


def getActivated(ob, rna, key, force=False):
    if key not in rna.keys():
        return False
    elif force:
        return True
    else:
        pg = getActivateGroup(ob, key)
        return pg.active


def getExistingActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        return None


def getActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        try:
            pg = rig.DazActivated.add()
            pg.name = key
            return pg
        except TypeError as err:
            msg = "Failed to load morph, because\n%s" % err
        raise DazError(msg)


class DAZ_OT_ActivateAll(DazOperator, Activator):
    bl_idname = "daz.activate_all"
    bl_label = "All"
    bl_description = "Activate all unprotected morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        return (not isProtected(ob, prop))


class DAZ_OT_ActivateProtected(DazOperator, Activator):
    bl_idname = "daz.activate_protected"
    bl_label = "Protected"
    bl_description = "Activate all protected morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        return isProtected(ob, prop)


class DAZ_OT_DeactivateAll(DazOperator, Activator):
    bl_idname = "daz.deactivate_all"
    bl_label = "None"
    bl_description = "Deactivate all morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        return False

#------------------------------------------------------------------
#   Clear morphs
#------------------------------------------------------------------

def setMorphs(value, rig, mgrp, scn, frame, force):
    morphs = mgrp.getRelevantMorphs(scn, rig)
    for morph in morphs:
        if (getActivated(rig, rig, morph, force) and
            isinstance(rig[morph], float)):
            rig[morph] = value
            autoKeyProp(rig, morph, scn, frame, force)


def setShapes(value, ob, mgrp, scn, frame):
    morphs,skeys = mgrp.getRelevantShapes(ob)
    for morph in morphs:
        if getActivated(ob, skeys.key_blocks, morph.name):
            skeys.key_blocks[morph.name].value = value
            autoKeyShape(skeys, morph.name, scn, frame)


class DAZ_OT_ClearMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear Morphs"
    bl_description = "Set all selected morphs of specified type to zero.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        for rig in getRigsFromContext(context):
            setMorphs(0.0, rig, self, scn, scn.frame_current, False)
            updateRigDrivers(context, rig)


class DAZ_OT_SetMorphs(DazPropsOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.set_morphs"
    bl_label = "Set Morphs"
    bl_description = "Set all selected morphs of specified type to given value.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    value : FloatProperty(
        name = "Value",
        description = "Set all selected morphs to this value",
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "value")

    def run(self, context):
        scn = context.scene
        for rig in getRigsFromContext(context):
            setMorphs(self.value, rig, self, scn, scn.frame_current, False)
            updateRigDrivers(context, rig)


class DAZ_OT_ClearShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.clear_shapes"
    bl_label = "Clear Shapes"
    bl_description = "Set all selected shapekey values of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        setShapes(0.0, context.object, self, scn, scn.frame_current)


class DAZ_OT_SetShapes(DazPropsOperator, MorphGroup, IsMesh):
    bl_idname = "daz.set_shapes"
    bl_label = "Set Shapes"
    bl_description = "Set all selected shapekey values of specified type to given value.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    value : FloatProperty(
        name = "Value",
        description = "Set all selected shapekeys to this value",
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "value")

    def run(self, context):
        scn = context.scene
        setShapes(self.value, context.object, self, scn, scn.frame_current)

#------------------------------------------------------------------
#   Add morphs to keyset
#------------------------------------------------------------------

class DAZ_OT_AddKeysets(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add selected morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromContext(context)
        if rig:
            scn = context.scene
            aksi = scn.keying_sets.active_index
            if aksi <= -1:
                aks = scn.keying_sets.new(idname = "daz_morphs", name = "daz_morphs")
            aks = scn.keying_sets.active
            morphs = self.getRelevantMorphs(scn, rig)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    aks.paths.add(rig.id_data, propRef(morph))
            updateRigDrivers(context, rig)

#------------------------------------------------------------------
#   Set morph keys
#------------------------------------------------------------------

class DAZ_OT_KeyMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromContext(context)
        if rig:
            scn = context.scene
            morphs = self.getRelevantMorphs(scn, rig, adjusters=True)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    keyProp(rig, morph, scn.frame_current)
            updateRigDrivers(context, rig)


class DAZ_OT_KeyShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.key_shapes"
    bl_label = "Set Keys"
    bl_description = "Set keys for all shapes of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        scn = context.scene
        morphs,skeys = self.getRelevantShapes(ob)
        for morph in morphs:
            if getActivated(ob, skeys.key_blocks, morph.name):
                keyShape(skeys, morph.name, scn.frame_current)

#------------------------------------------------------------------
#   Remove morph keys
#------------------------------------------------------------------

class DAZ_OT_UnkeyMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromContext(context)
        if rig and rig.animation_data and rig.animation_data.action:
            scn = context.scene
            morphs = self.getRelevantMorphs(scn, rig, adjusters=True)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    unkeyProp(rig, morph, scn.frame_current)
            updateRigDrivers(context, rig)


class DAZ_OT_UnkeyShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.unkey_shapes"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all shapekeys of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        scn = context.scene
        morphs,skeys = self.getRelevantShapes(ob)
        if skeys and skeys.animation_data and skeys.animation_data.action:
            for morph in morphs:
                if getActivated(ob, skeys.key_blocks, morph.name):
                    unkeyShape(skeys, morph.name, scn.frame_current)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

class DAZ_OT_ToggleAllCats(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    useMesh : BoolProperty(default=False)
    useOpen : BoolProperty()

    def run(self, context):
        rig = getRigFromContext(context, self.useMesh)
        if rig:
            for cat in rig.DazMorphCats:
                cat["active"] = self.useOpen

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def keyProp(rig, key, frame):
    rig.keyframe_insert(propRef(key), frame=frame)


def keyShape(skeys, key, frame):
    skeys.keyframe_insert('key_blocks["%s"].value' % key, frame=frame)


def unkeyProp(rig, key, frame):
    try:
        rig.keyframe_delete(propRef(key), frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def unkeyShape(skeys, key, frame):
    try:
        skeys.keyframe_delete('key_blocks["%s"].value' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = propRef(key)
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def autoKeyShape(skeys, key, scn, frame):
    if scn.tool_settings.use_keyframe_insert_auto:
        keyShape(skeys, key, frame)


def pinProp(rig, scn, key, mgrp, frame, value=1.0):
    if rig:
        setMorphs(0.0, rig, mgrp, scn, frame, True)
        rig[key] = value
        autoKeyProp(rig, key, scn, frame, True)


def pinShape(ob, scn, key, mgrp, frame):
    skeys = ob.data.shape_keys
    if skeys:
        setShapes(0.0, ob, mgrp, scn, frame)
        skeys.key_blocks[key].value = 1.0
        autoKeyShape(skeys, key, scn, frame)


class DAZ_OT_PinProp(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        from .morphing import MP
        rig = getRigFromContext(context)
        scn = context.scene
        MP.setupMorphPaths(False)
        pinProp(rig, scn, self.key, self, scn.frame_current)
        updateRigDrivers(context, rig)


class DAZ_OT_PinShape(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.pin_shape"
    bl_label = ""
    bl_description = "Pin shapekey value"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        ob = context.object
        scn = context.scene
        pinShape(ob, scn, self.key, self, scn.frame_current)


#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DazSelectGroup,

    DAZ_OT_SelectAll,
    DAZ_OT_SelectNone,

    DAZ_OT_ActivateAll,
    DAZ_OT_ActivateProtected,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_SetMorphs,
    DAZ_OT_ClearShapes,
    DAZ_OT_SetShapes,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_KeyShapes,
    DAZ_OT_UnkeyShapes,
    DAZ_OT_PinProp,
    DAZ_OT_PinShape,
    DAZ_OT_ToggleAllCats,

]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
