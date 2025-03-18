# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Matrix

from ..error import *
from ..utils import *
from ..selector import Selector, CustomSelector, CustomEnums
from ..uilist import updateScrollbars
from ..driver import DriverUser
from ..morphing import MS, MorphTypeOptions, addToCategories

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
        from ..morphing import getMorphList
        morphs = getMorphList(rig, self.morphset, sets=MS.Standards)
        keys = [(item.name, item.text, "All") for item in morphs]
        for cat in dazRna(rig).DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


    def specialKey(self, key):
        return key.startswith(("Daz", "daz_importer", "Adjust"))


    def invoke(self, context, event):
        global theMorphEnums, theCatEnums
        rig = self.rig = getRigFromContext(context)
        self.invoked = True
        theMorphEnums = [("All", "All", "All")]
        theCatEnums = [("All", "All", "All")]
        self.morphset = "All"
        self.morphnames = {}
        self.morphnames["All"] = []
        for morphset in MS.Standards:
            theMorphEnums.append((morphset, morphset, morphset))
            pg = getattr(dazRna(self.rig), "Daz%s" % morphset)
            self.morphnames["All"] += list(pg.keys())
            self.morphnames[morphset] = pg.keys()
        theMorphEnums.append(("Custom", "Custom", "Custom"))
        self.catnames = {}
        self.catnames["All"] = []
        for cat in dazRna(rig).DazMorphCats:
            theCatEnums.append((cat.name, cat.name, cat.name))
            self.morphnames["All"] += list(cat.morphs.keys())
            self.catnames["All"] += list(cat.morphs.keys())
            self.catnames[cat.name] = cat.morphs.keys()
        return Selector.invoke(self, context, event)

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
        cat = dazRna(rig).DazMorphCats[self.custom]
        cat.name = self.category
        updateScrollbars(context)

#------------------------------------------------------------------------
#   Remove category or morph type
#------------------------------------------------------------------------

class CategoryBasic:
    def selectCondition(self, item):
        return True

    def getKeys(self, rig, ob):
        keys = []
        for cat in dazRna(ob).DazMorphCats:
            key = cat.name
            keys.append((key,key,key))
        return keys


class MorphRemover(CategoryBasic):
    useDeleteShapekeys : BoolProperty(
        name = "Delete Shapekeys",
        description = "Delete both drivers and shapekeys",
        default = False)

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
        for ob in getShapeChildren(rig):
            skeys = ob.data.shape_keys
            self.removePropDrivers(skeys, raw, rig)
            self.removePropDrivers(skeys, final, amt)
            if ob.data.shape_keys:
                if raw in skeys.key_blocks.keys():
                    skey = skeys.key_blocks[raw]
                    if self.useDeleteShapekeys or self.useDeleteDrivers:
                        skey.driver_remove("value")
                        skey.driver_remove("mute")
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
                    if self.useDeleteShapekeys:
                        ob.shape_key_remove(skey)
        if raw in rig.keys():
            self.removeFromPropGroups(rig, raw)
        if self.useDeleteProps and self.useDeleteDrivers:
            if raw in rig.keys():
                clearProp(rig, raw)
                del rig[raw]
            if final in amt.keys():
                clearProp(amt, final)
                del amt[final]
            if rest in amt.keys():
                clearProp(amt, rest)
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
                clearProp(rna, prop)


    def removeFromPropGroups(self, rig, prop):
        from ..transfer import removeFromPropGroup
        for morphset in MS.Standards:
            pgs = getattr(dazRna(rig), "Daz%s" % morphset)
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
        self.removeMorphType(rig, self.usePowerpose, "PowerPose")
        self.removeMorphType(rig, self.useBody, "Body")
        self.removeMorphType(rig, self.useJcms, "Jcms")
        self.removeMorphType(rig, self.useFlexions, "Flexions")
        updateScrollbars(context)

    def removeMorphType(self, rig, use, morphset):
        if not use:
            return
        self.removeUrls(rig, morphset)
        for ob in getMeshChildren(rig):
            self.removeUrls(ob, morphset)
        pgs = getattr(dazRna(rig), "Daz%s" % morphset)
        props = [pg.name for pg in pgs]
        for prop in props:
            self.removeRigProp(rig, prop)
        self.removePropGroup(pgs)

    def removeUrls(self, ob, morphset):
        deletes = []
        for idx,item in enumerate(dazRna(ob).DazMorphUrls):
            if item.morphset == morphset:
                deletes.append(idx)
        deletes.reverse()
        for idx in deletes:
            dazRna(ob).DazMorphUrls.remove(idx)

#------------------------------------------------------------------------
#   Remove category
#------------------------------------------------------------------------

class CategorySelector(Selector):

    def run(self, context):
        items = [(item.index, item.name) for item in self.getSelectedItems()]
        items.sort()
        items.reverse()
        ob = context.object
        self.runObject(context, ob, items)
        updateScrollbars(context)

#------------------------------------------------------------------------
#   Remove category
#------------------------------------------------------------------------

class DAZ_OT_RemoveCategories(DazOperator, CategorySelector, MorphRemover, IsArmature):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    def runObject(self, context, rig, items):
        cats = [cat for idx,cat in items]
        if rig.type == 'ARMATURE':
            self.removeUrls(rig, cats)
            for ob in getMeshChildren(rig):
                self.removeUrls(ob, cats)
            for key in cats:
                cat = dazRna(rig).DazMorphCats[key]
                for pg in cat.morphs:
                    self.removeRigProp(rig, pg.name)
        for idx,key in items:
            dazRna(rig).DazMorphCats.remove(idx)
        if len(dazRna(rig).DazMorphCats) == 0:
            dazRna(rig).DazMeshMorphs = False


    def removeUrls(self, ob, cats):
        deletes = []
        for idx,item in enumerate(dazRna(ob).DazMorphUrls):
            if item.category in cats:
                deletes.append(idx)
        deletes.reverse()
        for idx in deletes:
            dazRna(ob).DazMorphUrls.remove(idx)

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

    def runObject(self, context, ob, items):
        props = []
        labels = []
        for idx,key in items:
            if key != self.custom:
                cat = dazRna(ob).DazMorphCats[key]
                props += [morph.name for morph in cat.morphs]
                labels += [morph.text for morph in cat.morphs]
        addToCategories(ob, props, labels, self.custom)
        for idx,key in items:
            if key != self.custom:
                dazRna(ob).DazMorphCats.remove(idx)

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
    for ob in getShapeChildren(rig):
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
    for cat in dazRna(rig).DazCategories:
        dazRna(rig).DazCategories.remove(cat)


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
        rig = getRigFromContext(context)
        self.props = [prop.lower() for prop in self.getSelectedProps()]
        if rig:
            if not self.props:
                self.props = [key.lower() for key in rig.keys() if not self.specialKey(key)]
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)
        updateScrollbars(context)


    def updatePropLimits(self, rig, context):
        from ..driver import setFloatProp
        if self.useShapekeys:
            for ob in getShapeChildren(rig):
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in self.props:
                        skey.slider_min = self.min
                        skey.slider_max = self.max
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in self.props and isinstance(rig[raw], float):
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

class RemoveAll(MorphRemover):
    useDeleteDrvBones : BoolProperty(
        name = "Delete Driven Bones",
        description = "Delete (drv) bones",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useDeleteProps")
        self.layout.prop(self, "useDeleteShapekeys")
        self.layout.prop(self, "useDeleteDrvBones")

    def run(self, context):
        self.initTmp()
        self.targets = {}
        meshes = getSelectedMeshes(context)
        rigs = getSelectedArmatures(context)
        for rig in rigs:
            for ob in rig.children:
                if ob.type == 'MESH' and ob not in meshes:
                    meshes.append(ob)
        self.runAll(context, rigs, meshes)
        if self.useDeleteProps:
            self.deleteProps(context, rigs)
        if self.useDeleteDrvBones:
            for rig in rigs:
                self.deleteDrvBones(rig)


    def removeDrivers(self, rna):
        if not (rna and rna.animation_data):
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


    def deleteProps(self, context, rigs):
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
                pgs = getattr(dazRna(rig), "Daz%s" % morphset)
                props = [pg.name for pg in pgs]
                for prop in props:
                    self.removeRigProp(rig, prop)
                self.removePropGroup(pgs)
            for cat in dazRna(rig).DazMorphCats.values():
                for pg in cat.morphs:
                    self.removeRigProp(rig, pg.name)
            self.removePropGroup(dazRna(rig).DazMorphCats)
            dazRna(rig).DazCustomMorphs = False
            for prop in list(rig.keys()):
                if prop.lower().startswith(("ectrl", "ejcm", "pbm", "phm")):
                    del rig[prop]
        updateScrollbars(context)


    def deleteDrvBones(self, rig):
        drvbones = []
        for pb in rig.pose.bones:
            if isDrvBone(pb.name):
                drvbones.append(pb.name)
            for cns in list(pb.constraints):
                if (cns.type == 'COPY_TRANSFORMS' and
                    cns.target == rig and
                    isDrvBone(cns.subtarget)):
                    pb.constraints.remove(cns)
        setMode('EDIT')
        for bname in set(drvbones):
            eb = rig.data.edit_bones.get(bname)
            rig.data.edit_bones.remove(eb)
        setMode('OBJECT')

#------------------------------------------------------------------
#   Remove all  drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllDrivers(DazPropsOperator, RemoveAll, DriverUser, IsMeshArmature):
    bl_idname = "daz.remove_all_drivers"
    bl_label = "Remove All Drivers"
    bl_description = "Remove all drivers from selected objects"
    bl_options = {'UNDO'}

    useDeleteDrivers = True

    def runAll(self, context, rigs, meshes):
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

#------------------------------------------------------------------
#   Bake all morph drivers
#------------------------------------------------------------------

class DAZ_OT_BakeAllErcDrivers(DazPropsOperator, RemoveAll, DriverUser, IsArmature):
    bl_idname = "daz.bake_all_erc_drivers"
    bl_label = "Bake All ERC Drivers"
    bl_description = "Bake all ERC drivers to selected rigs and children.\nOnly works if ERC method is Armature or Armature All"
    bl_options = {'UNDO'}

    def runAll(self, context, rigs, meshes):
        self.bones = {}
        self.shapes = {}
        for rig in rigs:
            bones = self.bones[rig.name] = {}
            for pb in rig.pose.bones:
                bones[pb.name] = (pb.head, pb.tail)
        for ob in meshes:
            skeys = ob.data.shape_keys
            shapes = self.shapes[ob.name] = {}
            if skeys:
                for skey in skeys.key_blocks:
                    shapes[skey.name] = skey.value

        for rig in rigs:
            self.removeDrivers(rig.data)
            self.removeDrivers(rig)
        for ob in meshes:
            self.removeDrivers(ob.data.shape_keys)

        for rig in rigs:
            for pb in rig.pose.bones:
                pb.matrix_basis = Matrix()
            if activateObject(context, rig):
                bones = self.bones[rig.name]
                setMode('EDIT')
                for eb in rig.data.edit_bones:
                    (eb.head, eb.tail) = bones[eb.name]
                setMode('OBJECT')
        for ob in meshes:
            skeys = ob.data.shape_keys
            if skeys:
                shapes = self.shapes[ob.name]
                for skey in skeys.key_blocks:
                    skey.value = shapes[skey.name]
                if self.useDeleteShapekeys:
                    bakeAllShapes(ob)


def bakeAllShapes(ob):
    from numpy import array
    skeys = ob.data.shape_keys
    if skeys is None:
        return
    verts = ob.data.vertices
    varr = array([v.co for v in verts])
    tarr = varr.copy()
    blocks = list(skeys.key_blocks)
    for skey in blocks:
        sarr = array([v.co for v in skey.data])
        tarr += skey.value * (sarr - varr)
    blocks.reverse()
    for skey in blocks:
        ob.shape_key_remove(skey)
    for v,co in zip(verts, tarr):
        v.co = co

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
        from ..driver import getShapekeyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromContext(context)
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
        updateScrollbars(context)


    def invoke(self, context, event):
        self.selectedItems.clear()
        ob = context.object
        rig = ob.parent
        if (rig and rig.type != 'ARMATURE'):
            rig = None
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks[1:]:
                if self.includeShapekey(skeys, skey.name):
                    item = self.selectedItems.add()
                    item.name = item.text = skey.name
                    item.category = self.getCategory(rig, ob, skey.name)
                    item.select = False
        return self.invokeDialog(context)

#-------------------------------------------------------------
#   Add shapekey to category
#-------------------------------------------------------------

class DAZ_OT_AddShapeToCategory(DazOperator, AddRemoveDriver, Selector, CustomEnums, CategoryString, IsShape):
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
            dazRna(ob).DazMeshMorphs = True
        updateScrollbars(context)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        return ""

#-------------------------------------------------------------
#   Add shapekey drivers
#-------------------------------------------------------------

class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, CategoryString, IsShape):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def handleShapekey(self, sname, rig, ob):
        from ..driver import setFloatProp, makePropDriver
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        final = finalProp(sname)
        setFloatProp(rig, sname, skey.value, skey.slider_min, skey.slider_max, True)
        setFloatProp(rig.data, final, skey.value, skey.slider_min, skey.slider_max, False)
        makePropDriver(propRef(sname), rig.data, propRef(final), rig, "x")
        makePropDriver(propRef(final), skey, "value", rig.data, "x")
        if GS.useMuteDrivers:
            makePropDriver(propRef(final), skey, "mute", rig.data, "abs(x)<0.0001")
        addToCategories(rig, [sname], None, self.category)
        dazRna(rig).DazCustomMorphs = True


    def includeShapekey(self, skeys, sname):
        from ..driver import getShapekeyDriver
        return (not getShapekeyDriver(skeys, sname))


    def getCategory(self, rig, ob, sname):
        return ""

#-------------------------------------------------------------
#   Remove shape from category
#-------------------------------------------------------------

class DAZ_OT_RemoveShapeFromCategory(DazOperator, AddRemoveDriver, CustomSelector, IsShape):
    bl_idname = "daz.remove_shape_from_category"
    bl_label = "Remove Shapekey From Category"
    bl_description = "Remove selected shapekeys from mesh category"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        snames = []
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in dazRna(ob).DazMorphCats:
                self.removeFromCategory(ob, snames, cat.name)
        else:
            self.removeFromCategory(ob, snames, self.custom)
        updateDrivers(ob.data.shape_keys)
        updateScrollbars(context)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        for cat in dazRna(ob).DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


    def removeFromCategory(self, ob, props, category):
        from ..transfer import removeFromPropGroup
        if category in dazRna(ob).DazMorphCats.keys():
            cat = dazRna(ob).DazMorphCats[category]
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)

#-------------------------------------------------------------
#   Remove shapekeys
#-------------------------------------------------------------

class DAZ_OT_RemoveShapekeys(DazOperator, AddRemoveDriver, CustomSelector, IsShape):
    bl_idname = "daz.remove_shapekeys"
    bl_label = "Remove Shapekeys"
    bl_description = "Remove shapekeys and drivers from active mesh"
    bl_options = {'UNDO'}

    def draw(self, context):
        Selector.draw(self, context)

    def includeShapekey(self, skeys, sname):
        return True

    def handleShapekey(self, sname, rig, ob):
        skey = ob.data.shape_keys.key_blocks[sname]
        skey.driver_remove("value")
        skey.driver_remove("mute")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        ob.shape_key_remove(skey)

    def getCategory(self, rig, ob, sname):
        return ""

#-------------------------------------------------------------
#   Remove zero shapekeys
#-------------------------------------------------------------

class DAZ_OT_RemoveZeroShapekeys(DazOperator, IsShape):
    bl_idname = "daz.remove_zero_shapekeys"
    bl_label = "Remove Zero Shapekeys"
    bl_description = "Remove zero shapekeys and their drivers from active mesh"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        deletes = dict([(skey.name, skey) for skey in skeys.key_blocks[1:] if skey.value == 0.0])
        print("DD", deletes)
        if skeys.animation_data and skeys.animation_data.action:
            fcurves = getActionBag(skeys.animation_data.action, 'KEY').fcurves
            for fcu in list(fcurves):
                words = fcu.data_path.split('"')
                if words[0] == "key_blocks[" and words[1] in deletes.keys():
                    fcurves.remove(fcu)
        for skey in deletes.values():
            ob.shape_key_remove(skey)
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            updateRigDrivers(context, rig)
        updateDrivers(ob.data.shape_keys)
        updateScrollbars(context)

#-------------------------------------------------------------
#   Remove shapekey drivers
#-------------------------------------------------------------

class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, CustomSelector, IsShape):
    bl_idname = "daz.remove_shapekey_drivers"
    bl_label = "Remove Shapekey Drivers"
    bl_description = "Remove rig drivers from shapekeys"
    bl_options = {'UNDO'}

    useRemoveProps : BoolProperty(
        name = "Remove Sliders",
        description = "Remove rig properties that drive the shapekeys",
        default = True)

    useSubmeshes : BoolProperty(
        name = "Remove From Submeshes",
        description = "Also remove drivers from other meshes in the same figure (eye-lashes etc.)",
        default = True)

    def draw(self, context):
        Selector.draw(self, context)

    def drawExtra(self, context):
        row = self.layout.row()
        row.prop(self, "useRemoveProps")
        row.prop(self, "useSubmeshes")

    def handleShapekey(self, sname, rig, ob):
        from ..transfer import removeShapeDriversAndProps
        skey = ob.data.shape_keys.key_blocks[sname]
        skey.driver_remove("value")
        skey.driver_remove("mute")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        if self.useSubmeshes and rig:
            for clo in getShapeChildren(rig):
                if clo != ob:
                    skey = clo.data.shape_keys.key_blocks.get(sname)
                    if skey:
                        skey.driver_remove("value")
                        skey.driver_remove("mute")
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
        if self.useRemoveProps:
            removeShapeDriversAndProps(ob.parent, sname)

    def includeShapekey(self, skeys, sname):
        from ..driver import getShapekeyDriver
        return getShapekeyDriver(skeys, sname)

    def getCategory(self, rig, ob, sname):
        if rig is None:
            return ""
        for cat in dazRna(rig).DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_ConvertMorphsToShapes(DazOperator, GeneralMorphSelector, IsMesh):
    bl_idname = "daz.convert_morphs_to_shapekeys"
    bl_label = "Convert Morphs To Shapekeys"
    bl_description = "Convert selected morphs to shapekeys.\nAll morphs are converted when called from script"
    bl_options = {'UNDO'}

    ignoreZeroShapes = False

    useLabels : BoolProperty(
        name = "Labels As Names",
        description = "Use the morph labels instead of morph names as shapekey names",
        default = True)

    onDelete : EnumProperty(
        items = [("NONE", "None", "Don't delete any shapekeys"),
                 ("USED", "Used", "Delete shapekeys used by converted morphs"),
                 ("BY_NAME", "By Name", "Delete some shapekeys based on names.\nJCMs are not deleted"),
                 ("ALL", "All", "Delete all existing shapekeys")],
        name = "Delete Existing Shapekeys",
        description = "Delete shapekeys that already exists",
        default = "BY_NAME")

    useAnimation : BoolProperty(
        name = "Convert Animation",
        description = "Convert morph animation to shapekey animation",
        default = True)

    def draw(self, context):
        GeneralMorphSelector.draw(self, context)
        row = self.layout.row()
        row.prop(self, "useLabels")
        row.prop(self, "useAnimation")
        row.prop(self, "onDelete")

    def run(self, context):
        ob = context.object
        scn = context.scene
        mod = getModifier(ob, 'ARMATURE')
        rig = ob.parent
        if (rig is None or rig.type != 'ARMATURE' or mod is None):
            raise DazError("No armature found")
        if dazRna(rig).DazDriversDisabled:
            raise DazError("Drivers are disabled")
        if self.invoked:
            if self.useLabels:
                items = dict([(item.name, item.text) for item in self.getSelectedItems()])
            else:
                items = dict([(item.name, item.name) for item in self.getSelectedItems()])
        else:
            lprops = [prop.lower() for prop in self.getSelectedProps()]
            if lprops:
                items = dict([(key, key) for key in rig.keys() if key.lower() in lprops])
            else:
                items = dict([(key, key) for key in rig.keys() if not self.specialKey(key)])
        nitems = len(items)
        skeys = ob.data.shape_keys
        if skeys is None:
            existing = {}
        elif self.onDelete == 'USED':
            existing = {}
        elif self.onDelete == "ALL":
            existing = dict([(skey.name, skey)
                for skey in skeys.key_blocks[1:]])
        elif self.onDelete == "BY_NAME":
            existing = dict([(skey.name, skey)
                for skey in skeys.key_blocks[1:]
                if not skey.name.lower().startswith("pjcm")])
        else:
            existing = {}
        startProgress("Convert morphs to shapekeys")
        t1 = t = perf_counter()
        for n,pair in enumerate(items.items()):
            key,mname = pair
            showProgress(n, nitems)
            clearProp(rig, key)
            if mname in existing.keys():
                del existing[mname]
                skey = skeys.key_blocks[mname]
                skey.name = "%s.001" % skey.name
                existing[skey.name] = skey
            if mname:
                setProp(rig, key)
                updateRigDrivers(context, rig)
                if self.onDelete == 'USED':
                    for skey in skeys.key_blocks[1:]:
                        if skey.value != 0.0 and mname != skey.name:
                            existing[skey.name] = skey
                mod = self.applyArmature(ob, rig, mod, key, mname)
                clearProp(rig, key)
        t2 = perf_counter()
        print("Converted %d morphs in %g seconds" % (n, t2-t1))
        updateRigDrivers(context, rig)
        if self.useAnimation and rig.animation_data:
            self.convertFcurves(ob.data.shape_keys, rig.animation_data.action, items)
        deleted = []
        for mname,skey in existing.items():
            self.clearShape(skey)
            deleted.append(skey.name)
            ob.shape_key_remove(skey)
        t2 = perf_counter()
        print("%d morphs converted in %g seconds" % (nitems, t2-t1))
        if GS.verbosity >= 3:
            print("Deleted:", deleted)


    def convertFcurves(self, skeys, act, items):
        if act is None or skeys is None:
            return
        fcurves = getActionBag(act, 'KEY').fcurves
        nstruct = {}
        for fcu in fcurves:
            prop = getProp(fcu.data_path)
            if prop and prop in items.keys():
                nstruct[items[prop]] = fcu
        if skeys.animation_data is None:
            skeys.animation_data_create()
        nact = bpy.data.actions.new(act.name)
        skeys.animation_data.action = nact
        nfcurves = getActionBag(nact, 'KEY').fcurves
        for key,fcu in nstruct.items():
            nfcu = nfcurves.new('key_blocks["%s"].value' % key)
            for kp in fcu.keyframe_points:
                nfcu.keyframe_points.insert(kp.co[0], kp.co[1], options={'FAST'})
        for prop,fcu in nstruct.items():
            fcurves.remove(fcu)


    def clearShape(self, skey):
        skey.driver_remove("value")
        skey.driver_remove("mute")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        skey.value = 0.0
        skey.mute = False


    def applyArmature(self, ob, rig, mod, key, mname):
        from ..driver import getPropMinMax
        mod.name = mname
        bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[mname]
        skey.value = 0.0
        skey.slider_min, skey.slider_max, default, ovr = getPropMinMax(rig, key)
        offsets = [(skey.data[vn].co - v.co).length for vn,v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * GS.scale    # eps = 0.1 mm
        if self.ignoreZeroShapes and abs(omax) < eps and abs(omin) < eps:
            ob.shape_key_remove(skey)
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)
        return nmod

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

    DAZ_OT_UpdateSliderLimits,
    DAZ_OT_AddDrivenValueNodes,
    DAZ_OT_RemoveAllDrivers,
    DAZ_OT_BakeAllErcDrivers,
    DAZ_OT_AddShapekeyDrivers,
    DAZ_OT_RemoveShapekeyDrivers,
    DAZ_OT_RemoveShapekeys,
    DAZ_OT_RemoveZeroShapekeys,

    DAZ_OT_ConvertMorphsToShapes,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
