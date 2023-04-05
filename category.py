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

import os
import bpy

from .error import *
from .utils import *
from .selector import Selector, CustomSelector, getRigFromObject, CustomEnums
from .uilist import updateScrollbars
from .driver import DriverUser
from .morphing import MS, MorphTypeOptions

#------------------------------------------------------------------------
#   General Morph selector
#------------------------------------------------------------------------

theMorphEnums = []
theCatEnums = []

def getMorphEnums(scn, context):
    return theMorphEnums

def getCatEnums(scn, context):
    return theCatEnums

class GeneralMorphSelector(Selector):
    morphset : EnumProperty(
        items = getMorphEnums,
        name = "Type")

    category : EnumProperty(
        items = getCatEnums,
        name = "Category")

    invoked = False

    def selectCondition(self, item):
        if self.morphset == "Custom":
            return (item.name in self.catnames[self.category])
        else:
            return (item.name in self.morphnames[self.morphset])

    def draw(self, context):
        self.layout.prop(self, "morphset")
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def getKeys(self, rig, ob):
        morphs = getMorphList(rig, self.morphset, sets=MS.Standards)
        keys = [(item.name, item.text, "All") for item in morphs]
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


    def specialKey(self, key):
        if (key[0:3] == "Daz" or
            key[0:6] == "Adjust"):
            return True
        return False


    def invoke(self, context, event):
        global theMorphEnums, theCatEnums
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        self.invoked = True
        theMorphEnums = [("All", "All", "All")]
        theCatEnums = [("All", "All", "All")]
        self.morphset = "All"
        self.morphnames = {}
        self.morphnames["All"] = []
        for morphset in MS.Standards:
            theMorphEnums.append((morphset, morphset, morphset))
            pg = getattr(self.rig, "Daz"+morphset)
            self.morphnames["All"] += list(pg.keys())
            self.morphnames[morphset] = pg.keys()
        theMorphEnums.append(("Custom", "Custom", "Custom"))
        self.catnames = {}
        self.catnames["All"] = []
        for cat in rig.DazMorphCats:
            theCatEnums.append((cat.name, cat.name, cat.name))
            self.morphnames["All"] += list(cat.morphs.keys())
            self.catnames["All"] += list(cat.morphs.keys())
            self.catnames[cat.name] = cat.morphs.keys()
        return Selector.invoke(self, context, event)

#------------------------------------------------------------------------
#   Categories
#------------------------------------------------------------------------

def addToCategories(ob, props, labels, category):
    from .driver import setBoolProp
    if not labels:
        from .modifier import getCanonicalKey
        labels = [getCanonicalKey(prop) for prop in props]
    if props and ob is not None:
        cats = dict([(cat.name,cat) for cat in ob.DazMorphCats])
        if category not in cats.keys():
            cat = ob.DazMorphCats.add()
            cat.name = category
        else:
            cat = cats[category]
        setBoolProp(cat, "active", True, True)
        for prop,label in zip(props, labels):
            if prop not in cat.morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = cat.morphs[prop]
            morph.name = prop
            morph.text = label
            setBoolProp(morph, "active", True, True)

#------------------------------------------------------------------------
#   Rename category
#------------------------------------------------------------------------

class CategoryString:
    category : StringProperty(
        name = "Category",
        description = "Add morphs to this category of custom morphs",
        default = "Shapes"
        )

class DAZ_OT_RenameCategory(DazPropsOperator, CustomEnums, CategoryString, IsMeshArmature):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def draw(self, context):
       self.layout.prop(self, "custom")
       self.layout.prop(self, "category", text="New Name")

    def run(self, context):
        rig = context.object
        cat = rig.DazMorphCats[self.custom]
        cat.name = self.category
        updateScrollbars(context)


def removeFromPropGroup(pgs, prop):
    idxs = []
    for n,item in enumerate(pgs):
        if item.name == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgs.remove(n)


def removeFromAllMorphsets(rig, prop):
    for morphset in MS.Standards:
        pgs = getattr(rig, "Daz" + morphset)
        removeFromPropGroup(pgs, prop)
    for cat in rig.DazMorphCats.values():
        removeFromPropGroup(cat.morphs, prop)

#------------------------------------------------------------------------
#   Remove category or morph type
#------------------------------------------------------------------------

class CategoryBasic:
    def selectCondition(self, item):
        return True

    def getKeys(self, rig, ob):
        keys = []
        for cat in ob.DazMorphCats:
            key = cat.name
            keys.append((key,key,key))
        return keys


class MorphRemover(CategoryBasic):
    useDeleteShapekeys : BoolProperty(
        name = "Delete Shapekeys",
        description = "Delete both drivers and shapekeys",
        default = True)

    useDeleteProps : BoolProperty(
        name = "Delete Properties",
        description = "Delete object and armature properties associated with this morph",
        default = True)

    useDeleteDrivers : BoolProperty(
        name = "Delete Drivers",
        description = "Delete drivers associated with this morph",
        default = True)

    def drawExtra(self, context):
        self.layout.prop(self, "useDeleteShapekeys")
        self.layout.prop(self, "useDeleteDrivers")
        if self.useDeleteDrivers:
            self.layout.prop(self, "useDeleteProps")


    def removeRigProp(self, rig, raw):
        amt = rig.data
        final = finalProp(raw)
        rest = restProp(raw)
        if self.useDeleteDrivers:
            self.removePropDrivers(rig, raw, rig)
            self.removePropDrivers(amt, final, amt)
            self.removePropDrivers(amt, rest, amt)
        for ob in rig.children:
            if ob.type == 'MESH':
                skeys = ob.data.shape_keys
                self.removePropDrivers(skeys, raw, rig)
                self.removePropDrivers(skeys, final, amt)
                if ob.data.shape_keys:
                    if raw in skeys.key_blocks.keys():
                        skey = skeys.key_blocks[raw]
                        if self.useDeleteShapekeys or self.useDeleteDrivers:
                            skey.driver_remove("value")
                            skey.driver_remove("slider_min")
                            skey.driver_remove("slider_max")
                        if self.useDeleteShapekeys:
                            ob.shape_key_remove(skey)
        if raw in rig.keys():
            self.removeFromPropGroups(rig, raw)
        if self.useDeleteProps and self.useDeleteDrivers:
            if raw in rig.keys():
                rig[raw] = 0.0
                del rig[raw]
            if final in amt.keys():
                amt[final] = 0.0
                del amt[final]
            if rest in amt.keys():
                amt[rest] = 0.0
                del amt[rest]


    def removePropDrivers(self, rna, prop, rig):
        def matchesPath(var, path, rig):
            if var.type == 'SINGLE_PROP':
                trg = var.targets[0]
                return (trg.id == rig and trg.data_path == path)
            return False

        def removeVar(vname, string):
            string = string.replace("+%s" % vname, "").replace("-%s" % vname, "")
            words = string.split("*%s" % vname)
            nwords = []
            for word in words:
                n = len(word)-1
                while n >= 0 and (word[n].isdigit() or word[n] == "."):
                    n -= 1
                if n >= 0 and word[n] in ["+", "-"]:
                    n -= 1
                if n >= 0:
                    nwords.append(word[:n+1])
            string = "".join(nwords)
            return string.replace("()", "0")

        if rna is None or rna.animation_data is None:
            return
        path = propRef(prop)
        fcus = []
        for fcu in rna.animation_data.drivers:
            if fcu.data_path == path:
                fcus.append(fcu)
                continue
            vars = []
            keep = False
            for var in fcu.driver.variables:
                if matchesPath(var, path, rig):
                    vars.append(var)
                else:
                    keep = True
            if keep:
                if fcu.driver.type == 'SCRIPTED':
                    string = fcu.driver.expression
                    for var in vars:
                        string = removeVar(var.name, string)
                    fcu.driver.expression = string
                for var in vars:
                    fcu.driver.variables.remove(var)
            else:
                fcus.append(fcu)
        props = {}
        props[prop] = True
        for fcu in fcus:
            prop = getProp(fcu.data_path)
            if prop:
                props[prop] = True
            try:
                rna.driver_remove(fcu.data_path, fcu.array_index)
            except TypeError:
                pass
        for prop in props.keys():
            if prop in rna.keys():
                rna[prop] = 0.0


    def removeFromPropGroups(self, rig, prop):
        for morphset in MS.Standards:
            pgs = getattr(rig, "Daz%s" % morphset)
            removeFromPropGroup(pgs, prop)


    def removePropGroup(self, pgs):
        idxs = list(range(len(pgs)))
        idxs.reverse()
        for idx in idxs:
            pgs.remove(idx)

#------------------------------------------------------------------------
#   Remove standard morphs
#------------------------------------------------------------------------

class DAZ_OT_RemoveStandardMorphs(DazPropsOperator, MorphTypeOptions, MorphRemover, IsArmature):
    bl_idname = "daz.remove_standard_morphs"
    bl_label = "Remove Standard Morphs"
    bl_description = "Remove selected standard morphs and associated drivers"
    bl_options = {'UNDO'}

    isMhxAware = False

    def run(self, context):
        rig = context.object
        self.removeMorphType(rig, self.useUnits, "Units")
        self.removeMorphType(rig, self.useExpressions, "Expressions")
        self.removeMorphType(rig, self.useVisemes, "Visemes")
        self.removeMorphType(rig, self.useHead, "Head")
        self.removeMorphType(rig, self.useFacs, "Facs")
        self.removeMorphType(rig, self.useFacsdetails, "Facsdetails")
        self.removeMorphType(rig, self.useFacsexpr, "Facsexpr")
        self.removeMorphType(rig, self.useBody, "Body")
        self.removeMorphType(rig, self.useJcms, "Jcms")
        self.removeMorphType(rig, self.useFlexions, "Flexions")
        updateScrollbars(context)

    def removeMorphType(self, rig, use, morphset):
        if not use:
            return
        pgs = getattr(rig, "Daz%s" % morphset)
        props = [pg.name for pg in pgs]
        for prop in props:
            self.removeRigProp(rig, prop)
        self.removePropGroup(pgs)

#------------------------------------------------------------------------
#   Remove category
#------------------------------------------------------------------------

class CategorySelector(Selector):

    def run(self, context):
        items = [(item.index, item.name) for item in self.getSelectedItems()]
        items.sort()
        items.reverse()
        ob = context.object
        self.runObject(context, ob, items, (ob.type == 'MESH'))
        updateScrollbars(context)

#------------------------------------------------------------------------
#   Remove category
#------------------------------------------------------------------------

class DAZ_OT_RemoveCategories(DazOperator, CategorySelector, MorphRemover, IsArmature):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    def runObject(self, context, ob, items, isMesh):
        for idx,key in items:
            cat = ob.DazMorphCats[key]
            ob.DazMorphCats.remove(idx)
            if not isMesh:
                for pg in cat.morphs:
                    self.removeRigProp(rig, pg.name)
        if len(ob.DazMorphCats) == 0:
            ob.DazMeshMorphs = False

#------------------------------------------------------------------------
#   Join categories
#------------------------------------------------------------------------

class DAZ_OT_JoinCategories(DazOperator, CategorySelector, CustomEnums, CategoryBasic, IsArmature):
    bl_idname = "daz.join_categories"
    bl_label = "Join Categories"
    bl_description = "Join selected categories with the chosen category"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "custom")
        CategorySelector.draw(self, context)

    def runObject(self, context, ob, items, isMesh):
        props = []
        labels = []
        for idx,key in items:
            if key != self.custom:
                cat = ob.DazMorphCats[key]
                props += [morph.name for morph in cat.morphs]
                labels += [morph.text for morph in cat.morphs]
        addToCategories(ob, props, labels, self.custom)
        for idx,key in items:
            if key != self.custom:
                ob.DazMorphCats.remove(idx)

#------------------------------------------------------------------------
#   Protect category
#------------------------------------------------------------------------

class DAZ_OT_ProtectCategories(DazOperator, CategorySelector, CategoryBasic, IsArmature):
    bl_idname = "daz.protect_categories"
    bl_label = "Protect Categories"
    bl_description = "Protect/unprotect all morphs in selected categories"
    bl_options = {'UNDO'}

    useProtect : BoolProperty(
        name = "Protect Morphs",
        description = "Protect all morphs in selected categories if enabled, otherwise unprotect them",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useProtect")
        CategorySelector.draw(self, context)

    def runObject(self, context, ob, items, isMesh):
        from .driver import setProtected
        from .selector import setActivated
        for idx,key in items:
            cat = ob.DazMorphCats[key]
            for pg in cat.morphs:
                setProtected(ob, pg.name, self.useProtect)
                if self.useProtect:
                    setActivated(ob, pg.name, False)

#------------------------------------------------------------------------
#   Apply morphs
#------------------------------------------------------------------------

def getShapeKeyCoords(ob):
    coords = [v.co for v in ob.data.vertices]
    skeys = []
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if abs(skey.value) > 1e-4:
                coords = [co + skey.value*(skey.data[n].co - ob.data.vertices[n].co) for n,co in enumerate(coords)]
            skeys.append(skey)
    return skeys,coords


def applyMorphs(rig, props):
    for ob in rig.children:
        basic = ob.data.shape_keys.key_blocks[0]
        skeys,coords = getShapeKeyCoords(ob)
        for skey in skeys:
            path = 'key_blocks["%s"].value' % skey.name
            getDrivingProps(ob.data.shape_keys, path, props)
            ob.shape_key_remove(skey)
        basic = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(basic)
        for vn,co in enumerate(coords):
            ob.data.vertices[vn].co = co
    print("Morphs applied")


def getDrivingProps(rna, channel, props):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = trg.data_path.split('"')[1]
                    props[prop] = trg.id


def removeDrivingProps(rig, props):
    for prop,id in props.items():
        if rig == id:
            del rig[prop]
    for cat in rig.DazCategories:
        rig.DazCategories.remove(cat)


#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

class DAZ_OT_UpdateSliderLimits(DazOperator, GeneralMorphSelector, IsMeshArmature):
    bl_idname = "daz.update_slider_limits"
    bl_label = "Update Slider Limits"
    bl_description = "Update selected slider min and max values.\nAll slider limits are selected when called from script"
    bl_options = {'UNDO'}

    min : FloatProperty(
        name = "Min",
        description = "Minimum slider value",
        default = 0.0)

    max : FloatProperty(
        name = "Max",
        description = "Maximum slider value",
        default = 1.0)

    useSliders : BoolProperty(
        name = "Sliders",
        description = "Update min and max for slider values",
        default = True)

    useFinal : BoolProperty(
        name = "Final",
        description = "Update min and max for final values",
        default = True)

    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Update min and max for shapekeys",
        default = True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "min")
        row.prop(self, "max")
        row = self.layout.row()
        row.prop(self, "useSliders")
        row.prop(self, "useFinal")
        row.prop(self, "useShapekeys")
        GeneralMorphSelector.draw(self, context)


    def run(self, context):
        ob = context.object
        rig = getRigFromObject(ob)
        if self.invoked:
            self.props = [item.name.lower() for item in self.getSelectedItems()]
        if rig:
            if not self.invoked:
                self.props = [key.lower() for key in rig.keys() if not self.specialKey(key)]
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)
        updateScrollbars(context)


    def updatePropLimits(self, rig, context):
        from .driver import setFloatProp
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys and self.useShapekeys:
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in self.props:
                        skey.slider_min = self.min
                        skey.slider_max = self.max
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in self.props:
                if self.useSliders:
                    setFloatProp(rig, raw, rig[raw], self.min, self.max, True)
                if self.useFinal:
                    final = finalProp(raw)
                    if final in amt.keys():
                        setFloatProp(amt, final, amt[final], self.min, self.max, False)
        updateRigDrivers(context, rig)
        print("Slider limits updated")

#------------------------------------------------------------------
#   Remove all morph drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllDrivers(DazPropsOperator, MorphRemover, DriverUser, IsMeshArmature):
    bl_idname = "daz.remove_all_drivers"
    bl_label = "Remove All Drivers"
    bl_description = "Remove all drivers from selected objects"
    bl_options = {'UNDO'}

    useDeleteDrivers = True

    def draw(self, context):
        self.layout.prop(self, "useDeleteProps")
        if self.useDeleteProps:
            self.layout.prop(self, "useDeleteShapekeys")

    def run(self, context):
        self.targets = {}
        meshes = getSelectedMeshes(context)
        rigs = getSelectedArmatures(context)
        for rig in rigs:
            for ob in rig.children:
                if ob.type == 'MESH' and ob not in meshes:
                    meshes.append(ob)
        for ob in meshes:
            skeys = ob.data.shape_keys
            if skeys:
                self.removeDrivers(skeys)
                if self.useDeleteShapekeys:
                    skeylist = list(skeys.key_blocks)
                    skeylist.reverse()
                    for skey in skeylist:
                        ob.shape_key_remove(skey)

        for rig in rigs:
            self.removeDrivers(rig.data)
            self.removeDrivers(rig)

        if not self.useDeleteProps:
            return

        for path,rna in self.targets.items():
            words = path.split('"')
            if len(words) == 5 and words[0] == "pose.bones[" and words[4] == "]":
                bname = words[1]
                prop = words[3]
                pb = rna.pose.bones[bname]
                if prop in pb.keys():
                    del pb[prop]
            elif len(words) == 3 and words[2] == "]":
                prop = words[1]
                if prop in rna.keys():
                    del rna[prop]

        for rig in rigs:
            for morphset in MS.Morphsets:
                pgs = getattr(rig, "Daz%s" % morphset)
                props = [pg.name for pg in pgs]
                for prop in props:
                    self.removeRigProp(rig, prop)
                self.removePropGroup(pgs)
            for cat in rig.DazMorphCats.values():
                for pg in cat.morphs:
                    self.removeRigProp(rig, pg.name)
            self.removePropGroup(rig.DazMorphCats)
            rig.DazCustomMorphs = False
            for prop in list(rig.keys()):
                if prop.lower().startswith(("ectrl", "ejcm", "pbm", "phm")):
                    del rig[prop]
        updateScrollbars(context)


    def removeDrivers(self, rna):
        if not rna.animation_data:
            return
        for fcu in list(rna.animation_data.drivers):
            if fcu.driver:
                if getProp(fcu.data_path):
                    self.targets[fcu.data_path] = rna
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        self.targets[trg.data_path] = trg.id
            idx = self.getArrayIndex(fcu)
            self.removeDriver(rna, fcu.data_path, idx)

#-------------------------------------------------------------
#   Add driven value nodes
#-------------------------------------------------------------

class DAZ_OT_AddDrivenValueNodes(DazOperator, Selector, DriverUser, IsMesh):
    bl_idname = "daz.add_driven_value_nodes"
    bl_label = "Add Driven Value Nodes"
    bl_description = "Add driven value nodes"
    bl_options = {'UNDO'}

    allSets = MS.Morphsets

    def getKeys(self, rig, ob):
        skeys = ob.data.shape_keys
        if skeys:
            return [(sname, sname, "All") for sname in skeys.key_blocks.keys()]
        else:
            return []


    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text = "Active material: %s" % mat.name)
        Selector.draw(self, context)


    def run(self, context):
        from .driver import getShapekeyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromObject(ob)
        mat = ob.data.materials[ob.active_material_index]
        props = self.getSelectedProps()
        nprops = len(props)
        for n,prop in enumerate(props):
            skey = skeys.key_blocks[prop]
            fcu = getShapekeyDriver(skeys, prop)
            node = mat.node_tree.nodes.new(type="ShaderNodeValue")
            node.name = node.label = skey.name
            node.location = (-1100, 250-250*n)
            if fcu:
                channel = ('nodes["%s"].outputs[0].default_value' % node.name)
                fcu2 = mat.node_tree.driver_add(channel)
                fcu2 = self.copyFcurve(fcu, fcu2)

#-------------------------------------------------------------
#   Add and remove driver
#-------------------------------------------------------------

class AddRemoveDriver:

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            for sname in self.getSelectedProps():
                self.handleShapekey(sname, rig, ob)
            updateRigDrivers(context, rig)
        updateDrivers(ob.data.shape_keys)


    def invoke(self, context, event):
        self.selection.clear()
        ob = context.object
        rig = ob.parent
        if (rig and rig.type != 'ARMATURE'):
            rig = None
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks[1:]:
                if self.includeShapekey(skeys, skey.name):
                    item = self.selection.add()
                    item.name = item.text = skey.name
                    item.category = self.getCategory(rig, ob, skey.name)
                    item.select = False
        return self.invokeDialog(context)


    def createRawFinPair(self, rig, raw, rna, channel, value, min, max):
        from .driver import addDriverVar, setFloatProp, removeModifiers
        final = finalProp(raw)
        setFloatProp(rig, raw, value, min, max, True)
        setFloatProp(rig.data, final, value, min, max, False)
        fcu = rig.data.driver_add(propRef(final))
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", propRef(raw), rig)
        fcu.driver.expression = "a"
        fcu = rna.driver_add(channel)
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", propRef(final), rig.data)
        fcu.driver.expression = "a"


class DAZ_OT_AddShapeToCategory(DazOperator, AddRemoveDriver, Selector, CustomEnums, CategoryString, IsMesh):
    bl_idname = "daz.add_shape_to_category"
    bl_label = "Add Shapekey To Category"
    bl_description = "Add selected shapekeys to mesh category"
    bl_options = {'UNDO'}

    makenew : BoolProperty(
        name = "New Category",
        description = "Create a new category",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "makenew")
        if self.makenew:
            self.layout.prop(self, "category")
        else:
            self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        if self.makenew:
            cat = self.category
        elif self.custom == "All":
            raise DazError("Cannot add to all categories")
        else:
            cat = self.custom
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            addToCategories(ob, [sname], None, cat)
            ob.DazMeshMorphs = True
        updateScrollbars(context)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, CategoryString, IsMesh):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def handleShapekey(self, sname, rig, ob):
        from .driver import getShapekeyDriver
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        if getShapekeyDriver(skeys, skey.name):
            raise DazError("Shapekey %s is already driven" % skey.name)
        self.createRawFinPair(rig, sname, skey, "value", skey.value, skey.slider_min, skey.slider_max)
        addToCategories(rig, [sname], None, self.category)
        rig.DazCustomMorphs = True


    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return (not getShapekeyDriver(skeys, sname))


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_RemoveShapeFromCategory(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shape_from_category"
    bl_label = "Remove Shapekey From Category"
    bl_description = "Remove selected shapekeys from mesh category"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        snames = []
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in ob.DazMorphCats:
                self.removeFromCategory(ob, snames, cat.name)
        else:
            self.removeFromCategory(ob, snames, self.custom)
        updateDrivers(ob.data.shape_keys)
        updateScrollbars(context)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


    def removeFromCategory(self, ob, props, category):
        if category in ob.DazMorphCats.keys():
            cat = ob.DazMorphCats[category]
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)


class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shapekey_drivers"
    bl_label = "Remove Shapekey Drivers"
    bl_description = "Remove rig drivers from shapekeys"
    bl_options = {'UNDO'}

    def handleShapekey(self, sname, rig, ob):
        skey = ob.data.shape_keys.key_blocks[sname]
        skey.driver_remove("value")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        removeShapeDriversAndProps(ob.parent, sname)

    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return getShapekeyDriver(skeys, sname)

    def getCategory(self, rig, ob, sname):
        if rig is None:
            return ""
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


def removeShapeDriversAndProps(rig, sname):
    if rig and rig.type == 'ARMATURE':
        final = finalProp(sname)
        rig.data.driver_remove(propRef(final))
        if final in rig.data.keys():
            del rig.data[final]
        if sname in rig.keys():
            del rig[sname]
        removeFromAllMorphsets(rig, sname)


#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_ConvertMorphsToShapes(DazOperator, GeneralMorphSelector, IsMesh):
    bl_idname = "daz.convert_morphs_to_shapekeys"
    bl_label = "Convert Morphs To Shapekeys"
    bl_description = "Convert selected morphs to shapekeys.\nAll morphs are converted when called from script"
    bl_options = {'UNDO'}

    useLabels : BoolProperty(
        name = "Labels As Names",
        description = "Use the morph labels instead of morph names as shapekey names",
        default = False)

    useDelete : BoolProperty(
        name = "Delete Existing Shapekeys",
        description = "Delete shapekeys that already exists",
        default = False)

    def draw(self, context):
        GeneralMorphSelector.draw(self, context)
        row = self.layout.row()
        row.prop(self, "useLabels")
        row.prop(self, "useDelete")

    def run(self, context):
        ob = context.object
        mod = getModifier(ob, 'ARMATURE')
        rig = ob.parent
        if (rig is None or rig.type != 'ARMATURE' or mod is None):
            raise DazError("No armature found")
        if rig.DazDriversDisabled:
            raise DazError("Drivers are disabled")
        if self.invoked:
            if self.useLabels:
                items = [(item.name, item.text) for item in self.getSelectedItems()]
            else:
                items = [(item.name, item.name) for item in self.getSelectedItems()]
        else:
            items = [(key, key) for key in rig.keys() if not self.specialKey(self, key)]
        nitems = len(items)
        skeys = ob.data.shape_keys
        existing = {}
        if self.useDelete and skeys:
            for skey in skeys.key_blocks[1:]:
                existing[skey.name] = skey
                skey.driver_remove("value")
                skey.driver_remove("slider_min")
                skey.driver_remove("slider_max")
        startProgress("Convert morphs to shapekeys")
        t1 = t = perf_counter()
        for n,item in enumerate(items):
            t0 = t
            key,mname = item
            showProgress(n, nitems)
            rig[key] = 0.0
            if skeys and mname in skeys.key_blocks.keys():
                print("Skip", mname)
                if mname in existing.keys():
                    del existing[mname]
                continue
            if mname:
                rig[key] = 1.0
                updateRigDrivers(context, rig)
                mod = self.applyArmature(ob, rig, mod, mname)
                rig[key] = 0.0
                t = perf_counter()
                print("Converted %s in %g seconds" % (mname, t-t0))
        updateRigDrivers(context, rig)
        for skey in existing.values():
            ob.shape_key_remove(skey)
        t2 = perf_counter()
        print("%d morphs converted in %g seconds" % (nitems, t2-t1))


    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        if bpy.app.version < (2,90,0):
            bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        else:
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[mname]
        skey.value = 0.0
        offsets = [(skey.data[vn].co - v.co).length for vn,v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * ob.DazScale    # eps = 0.1 mm
        if abs(omax) < eps and abs(omin) < eps:
            #idx = skeys.key_blocks.keys().index(skey.name)
            #ob.active_shape_key_index = idx
            ob.shape_key_remove(skey)
            #ob.active_shape_key_index = 0
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)
        return nmod

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_TransferAnimationToShapekeys(DazOperator, IsMeshArmature):
    bl_idname = "daz.transfer_animation_to_shapekeys"
    bl_label = "Transfer Animation To Shapekeys"
    bl_description = (
        "Transfer the armature action to actions for shapekeys.\n" +
        "From active armature to selected meshes.\n" +
        "Transferred morph F-curves are removed from the armature action")
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if not (rig and rig.animation_data and rig.animation_data.action):
            raise DazError("No action found")
        actrig = rig.animation_data.action
        meshes = [ob for ob in rig.children if ob.type == 'MESH' and ob.data.shape_keys]
        if not meshes:
            raise DazError("No meshes with shapekeys selected")

        self.morphnames = {}
        for morphset in MS.Standards:
            pgs = getattr(rig, "Daz"+morphset)
            for pg in pgs:
                self.morphnames[pg.name] = pg.text
        for cat in rig.DazMorphCats:
            for pg in cat.morphs:
                self.morphnames[pg.name] = pg.text

        for ob in meshes:
            skeys = ob.data.shape_keys
            act = None
            fcurves = {}
            for fcurig in actrig.fcurves:
                prop = getProp(fcurig.data_path)
                if prop:
                    skey = self.getShape(prop, skeys)
                    if skey:
                        channel = 'key_blocks["%s"].value' % skey.name
                        if skeys.animation_data is None:
                            skeys.animation_data_create()
                        skey.keyframe_insert("value")
                        if act is None:
                            act = skeys.animation_data.action
                            act.name = "%s:%s" % (ob.name, actrig.name)
                        fcu = act.fcurves.find(channel)
                        self.copyFcurve(fcurig, fcu)
                        fcurves[fcurig.data_path] = fcurig
            for fcu in fcurves.values():
                actrig.fcurves.remove(fcu)


    def getShape(self, prop, skeys):
        if prop in skeys.key_blocks.keys():
            return skeys.key_blocks[prop]
        sname = self.morphnames.get(prop)
        if sname in skeys.key_blocks.keys():
            return skeys.key_blocks[sname]
        return None


    def copyFcurve(self, fcu1, fcu2):
        for kp in list(fcu2.keyframe_points):
            fcu2.keyframe_points.remove(kp, fast=True)
        for kp in fcu1.keyframe_points:
            fcu2.keyframe_points.insert(kp.co[0], kp.co[1], options={'FAST'})
        for attr in ['color', 'color_mode', 'extrapolation', 'hide', 'lock', 'mute', 'select']:
            setattr(fcu2, attr, getattr(fcu1, attr))

#-------------------------------------------------------------
#   Transfer verts to shapekeys
#-------------------------------------------------------------

class DAZ_OT_MeshToShape(DazOperator, IsMesh):
    bl_idname = "daz.transfer_mesh_to_shape"
    bl_label = "Transfer Mesh To Shapekey"
    bl_description = "Transfer selected mesh to active shapekey"
    bl_options = {'UNDO'}

    def run(self, context):
        trg = context.object
        skeys = trg.data.shape_keys
        if skeys is None:
            raise DazError("Target mesh must have shapekeys")
        idx = trg.active_shape_key_index
        if idx == 0:
            raise DazError("Cannot transfer to Basic shapekeys")
        objects = [ob for ob in getSelectedMeshes(context) if ob != trg]
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected")
        src = objects[0]
        nsverts = len(src.data.vertices)
        ntverts = len(trg.data.vertices)
        if nsverts != ntverts:
            raise DazError("Vertex count mismatch:  \n%d != %d" % (nsverts, ntverts))
        skey = skeys.key_blocks[idx]
        for v in src.data.vertices:
            skey.data[v.index].co = v.co

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_AddShapeToCategory,
    DAZ_OT_RemoveShapeFromCategory,
    DAZ_OT_RenameCategory,
    DAZ_OT_RemoveStandardMorphs,
    DAZ_OT_RemoveCategories,
    DAZ_OT_JoinCategories,
    DAZ_OT_ProtectCategories,

    DAZ_OT_UpdateSliderLimits,
    DAZ_OT_AddDrivenValueNodes,
    DAZ_OT_RemoveAllDrivers,
    DAZ_OT_AddShapekeyDrivers,
    DAZ_OT_RemoveShapekeyDrivers,

    DAZ_OT_ConvertMorphsToShapes,
    DAZ_OT_TransferAnimationToShapekeys,
    DAZ_OT_MeshToShape,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
