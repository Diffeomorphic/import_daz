# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.props import *
from ..utils import *
from ..error import *
from ..selector import Selector

def getMaskName(string):
    return "Mask_" + string.split(".",1)[0]

def getHidePropName(string):
    return "Mhh" + string.split(".",1)[0]

def isHideProp(string):
    return (string[0:3] == "Mhh")

def getMannequinName(string):
    return "MhhMannequin"

#------------------------------------------------------------------------
#    Setup: Add and remove hide drivers
#------------------------------------------------------------------------

class SingleGroup:
    singleGroup : BoolProperty(
        name = "Single Group",
        description = "Treat all selected meshes as a single group",
        default = False)

    groupName : StringProperty(
        name = "Group Name",
        description = "Name of the single group",
        default = "All")


class DAZ_OT_AddVisibility(DazPropsOperator, SingleGroup, IsArmature):
    bl_idname = "daz.add_visibility_drivers"
    bl_label = "Add Visibility Drivers"
    bl_description = "Control visibility of selected meshes with rig property"
    bl_options = {'UNDO'}

    useCollections : BoolProperty(
        name = "Add Collections",
        description = "Move selected meshes to new collections",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "singleGroup")
        if self.singleGroup:
            self.layout.prop(self, "groupName")
        self.layout.prop(self, "useCollections")


    def run(self, context):
        rig = context.object
        print("Create visibility drivers for %s:" % rig.name)
        meshes = getSelectedMeshes(context)
        if self.singleGroup:
            obnames = [self.groupName]
            for ob in meshes:
                self.createObjectVisibility(rig, ob, self.groupName)
        else:
            obnames = []
            for ob in meshes:
                self.createObjectVisibility(rig, ob, ob.name)
                obnames.append(ob.name)
        for ob in getMeshChildren(rig):
            self.createMaskVisibility(rig, ob, obnames)
            dazRna(ob).DazVisibilityDrivers = True
        dazRna(rig).DazVisibilityDrivers = True
        updateDrivers(rig)

        if self.useCollections:
            self.addCollections(context, rig, meshes)

        print("Visibility drivers created")


    def createObjectVisibility(self, rig, ob, obname):
        from ..driver import setBoolProp, makePropDriver
        prop = getHidePropName(obname)
        setBoolProp(rig, prop, True, True, "Show %s" % prop)
        makePropDriver(propRef(prop), ob, "hide_viewport", rig, expr="not(x)")
        makePropDriver(propRef(prop), ob, "hide_render", rig, expr="not(x)")


    def createMaskVisibility(self, rig, ob, obnames):
        from ..driver import makePropDriver
        props = {}
        for obname in obnames:
            modname = getMaskName(obname)
            props[modname] = getHidePropName(obname)
        masked = False
        for mod in ob.modifiers:
            if (mod.type == 'MASK' and
                mod.name in props.keys()):
                prop = props[mod.name]
                makePropDriver(propRef(prop), mod, "show_viewport", rig, expr="x")
                makePropDriver(propRef(prop), mod, "show_render", rig, expr="x")


    def addCollections(self, context, rig, selected):
        def moveToCollection(ob, newcoll):
            if newcoll is None:
                return
            for coll in bpy.data.collections:
                if ob in coll.objects.values():
                    coll.objects.unlink(ob)
                if ob not in newcoll.objects.values():
                    newcoll.objects.link(ob)

        from ..proxy import createSubCollection
        rigcoll = getCollection(context, rig)
        if rigcoll is None:
            raise DazError("No collection found")
        print("Create visibility collections for %s:" % rig.name)
        if self.singleGroup:
            coll = createSubCollection(rigcoll, self.groupName)
            for ob in selected:
                moveToCollection(ob, coll)
        else:
            for ob in selected:
                coll = createSubCollection(rigcoll, ob.name)
                moveToCollection(ob, coll)
        dazRna(rig).DazVisibilityCollections = True
        print("Visibility collections created")

#------------------------------------------------------------------------
#   Remove visibility
#------------------------------------------------------------------------

class DAZ_OT_RemoveVisibility(DazPropsOperator):
    bl_idname = "daz.remove_visibility_drivers"
    bl_label = "Remove Visibility Drivers"
    bl_description = "Remove ability to control visibility from rig property"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and dazRna(ob).DazVisibilityDrivers)

    useAllMeshes : BoolProperty(
        name = "All Meshes In Scene",
        description = "Remove visibility drivers from all meshes in scene,\nnot just children of the active rig",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useAllMeshes")

    def run(self, context):
        rig = context.object
        if self.useAllMeshes:
            meshes = [ob for ob in context.view_layer.objects if ob.type == 'MESH']
        else:
            meshes = getMeshChildren(rig)
        for ob in meshes:
            ob.driver_remove("hide_viewport")
            ob.driver_remove("hide_render")
            ob.hide_set(False)
            ob.hide_viewport = False
            ob.hide_render = False
            for mod in ob.modifiers:
                if mod.type == 'MASK':
                    mod.driver_remove("show_viewport")
                    mod.driver_remove("show_render")
                    mod.show_viewport = True
                    mod.show_render = True
        for prop in list(rig.keys()):
            if isHideProp(prop):
                del rig[prop]
        updateDrivers(rig)
        dazRna(rig).DazVisibilityDrivers = False
        print("Visibility drivers removed")

#------------------------------------------------------------------------
#   Mask modifiers
#------------------------------------------------------------------------

class DAZ_OT_CreateMasks(DazPropsOperator, SingleGroup, IsMesh):
    bl_idname = "daz.create_masks"
    bl_label = "Create Masks"
    bl_description = "Create vertex groups and mask modifiers in active mesh for selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "singleGroup")
        if self.singleGroup:
            self.layout.prop(self, "groupName")


    def run(self, context):
        hum = context.object
        print("Create masks for %s:" % hum.name)
        if self.singleGroup:
            modname = getMaskName(self.groupName)
            print("  ", modname)
            self.createMask(hum, modname)
        else:
            meshes = [ob for ob in getSelectedMeshes(context) if ob != hum]
            for ob in meshes:
                modname = getMaskName(ob.name)
                print("  ", ob.name, modname)
                self.createMask(hum, modname)
        print("Masks created")


    def createMask(self, hum, modname):
        mod = None
        for mod1 in hum.modifiers:
            if mod1.type == 'MASK' and mod1.name == modname:
                mod = mod1
        if modname in hum.vertex_groups.keys():
            vgrp = hum.vertex_groups[modname]
        else:
            vgrp = hum.vertex_groups.new(name=modname)
        if mod is None:
            mod = hum.modifiers.new(modname, 'MASK')
        mod.vertex_group = modname
        mod.invert_vertex_group = True

#------------------------------------------------------------------------
#   Copy Masks
#------------------------------------------------------------------------

class DAZ_OT_CopyMasks(DazOperator, Selector, IsMesh):
    bl_idname = "daz.copy_masks"
    bl_label = "Copy Masks"
    bl_description = "Copy selected mask modifiers and vertex groups from active to selected"
    bl_options = {'UNDO'}

    columnWidth = 300
    ncols = 4

    def invoke(self, context, event):
        ob = context.object
        self.selectedItems.clear()
        for mod in ob.modifiers:
            if mod.type == 'MASK':
                item = self.selectedItems.add()
                item.name = mod.name
                item.text = mod.name
                item.select = False
        return self.invokeDialog(context)


    def run(self, context):
        src = context.object
        masks = []
        for mod in src.modifiers:
            item = self.selectedItems.get(mod.name)
            if item and item.select:
                masks.append(mod)
        masknames = []
        for mask in masks:
            vgrp = src.vertex_groups.get(mask.vertex_group)
            if vgrp:
                src.vertex_groups.active = vgrp
                masknames.append(vgrp.name)
                bpy.ops.object.data_transfer(
                    data_type = "VGROUP_WEIGHTS",
                    vert_mapping = 'NEAREST',
                    layers_select_src = 'ACTIVE',
                    layers_select_dst = 'NAME')
        for trg in getSelectedMeshes(context):
            if trg != src:
                self.copyModifiers(masks, trg)


    def copyModifiers(self, masks, trg):
        for mask in masks:
            mod = trg.modifiers.get(mask.name)
            if mod is None:
                mod = trg.modifiers.new(mask.name, 'MASK')
            mod.vertex_group = mask.vertex_group
            mod.invert_vertex_group = mask.invert_vertex_group

#------------------------------------------------------------------------
#   Shrinkwrap
#------------------------------------------------------------------------

class DAZ_OT_AddShrinkwrap(DazPropsOperator, IsMesh):
    bl_idname = "daz.add_shrinkwrap"
    bl_label = "Add Shrinkwrap"
    bl_description = "Add shrinkwrap modifiers to selected meshes covering the active mesh.\nOptionally add solidify modifiers"
    bl_options = {'UNDO'}

    offset : FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 2.0)

    useSolidify : BoolProperty(
        name = "Solidify",
        description = "Add a solidify modifier too",
        default = False)

    thickness : FloatProperty(
        name = "Thickness (mm)",
        description = "Thickness of the surface",
        default = 2.0)

    useAddVertexGroup : BoolProperty(
        name = "Add Vertex Groups",
        description = "Add influence vertex groups",
        default = True)

    useApply : BoolProperty(
        name = "Apply Modifiers",
        description = "Apply modifiers afterwards",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "offset")
        self.layout.prop(self, "useSolidify")
        if self.useSolidify:
            self.layout.prop(self, "thickness")
        self.layout.prop(self, "useAddVertexGroup")
        if not self.useAddVertexGroup:
            self.layout.prop(self, "useApply")
        self.layout.label(text = "This tool now adds shrinkwrap to selected meshes")


    def run(self, context):
        hum = context.object
        meshes = [ob for ob in getSelectedMeshes(context) if ob != hum]
        for ob in meshes:
            activateObject(context, ob)
            self.makeShrinkwrap(ob, hum)
            if self.useSolidify:
                self.makeSolidify(ob)


    def makeShrinkwrap(self, ob, hum):
        mod = None
        for mod1 in ob.modifiers:
            if mod1.type == 'SHRINKWRAP' and mod1.target == hum:
                print("Object %s already has shrinkwrap modifier targeting %s" % (ob.name, hum.name))
                mod = mod1
                break
        if mod is None:
            mod = ob.modifiers.new("Shrinkwrap %s" % hum.name, 'SHRINKWRAP')
        modname = mod.name
        mod.target = hum
        mod.wrap_method = 'NEAREST_SURFACEPOINT'
        mod.wrap_mode = 'OUTSIDE'
        mod.offset = 0.1*GS.scale*self.offset
        if self.useAddVertexGroup:
            if modname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[modname]
            else:
                vgrp = ob.vertex_groups.new(name=modname)
            mod.vertex_group = modname
            mod.invert_vertex_group = True

        elif self.useApply and not ob.data.shape_keys:
            applyModifier(mod.name)


    def makeSolidify(self, ob):
        mod = getModifier(ob, 'SOLIDIFY')
        if mod:
            print("Object %s already has solidify modifier" % ob.name)
        else:
            mod = ob.modifiers.new("Solidify", 'SOLIDIFY')
        mod.thickness = 0.1*GS.scale*self.thickness
        mod.offset = 0.0
        if self.useApply and not ob.data.shape_keys:
            applyModifier(mod.name)

#------------------------------------------------------------------------
#   Add invisible material
#------------------------------------------------------------------------

class DAZ_OT_MakeInvisible(DazOperator, IsMesh):
    bl_idname = "daz.make_invisible"
    bl_label = "Make Invisible"
    bl_description = "Hide selected faces by assigning an invisible material to them"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..matsel import makePermanentMaterial
        ob = context.object
        bpy.ops.object.mode_set(mode='OBJECT')
        makePermanentMaterial(ob, "Invisio", (0.8,0.8,0.8,0))

#----------------------------------------------------------
#   Shapekey selector
#----------------------------------------------------------

class ShapekeySelector(Selector):
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)

    def selectCondition(self, item):
        return True

    def getKeys(self, rig, ob):
        return [(skey.name, skey.name, skey.name) for skey in ob.data.shape_keys.key_blocks[1:]]


class DAZ_OT_AddShapeVisDrivers(DazOperator, ShapekeySelector):
    bl_idname = "daz.add_shape_vis_drivers"
    bl_label = "Add Shapekey Visibility Drivers"
    bl_description = "Add drivers to selected shapekeys,\ndepending on the visibility of selected clothes"
    bl_options = {'UNDO'}

    useInvert : BoolProperty(
        name = "Inverted Drivers",
        description = "Enable shapekey when clothes are visible",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useInvert")
        ShapekeySelector.draw(self, context)

    def run(self, context):
        from ..driver import addDriverVar
        hum = context.object
        rig = getRigFromContext(context)
        clothes = [ob for ob in getSelectedMeshes(context) if ob != hum]
        if len(clothes) < 1:
            raise DazError("At least two meshes must be selected")
        if self.useInvert:
            form = "1-%s"
        else:
            form = "%s"
        props = []
        for clo in clothes:
            if not dazRna(clo).DazVisibilityDrivers:
                raise DazError("Create visibility drivers first")
            prop = getHidePropName(clo.name)
            if prop not in rig.keys():
                rig[prop] = 1.0
            props.append(prop)
        snames = self.getSelectedValues()
        for skey in hum.data.shape_keys.key_blocks:
            if skey.name in snames:
                skey.driver_remove("value")
                fcu = skey.driver_add("value")
                fcu.driver.type = 'SCRIPTED'
                final = finalProp(skey.name)
                letter = "a"
                expr = ""
                for prop in props:
                    addDriverVar(fcu, letter, propRef(prop), rig)
                    expr = expr + "*(1-%s)" % letter
                    letter = nextLetter(letter)
                if rig and final in rig.data.keys():
                    addDriverVar(fcu, letter, propRef(final), rig.data)
                    expr = expr + "+%s" % letter
                fcu.driver.expression = form % expr[1:]

#----------------------------------------------------------
#   Shapekey selector
#----------------------------------------------------------

class DAZ_OT_SelectCoveredVerts(DazPropsOperator, IsMesh):
    bl_idname = "daz.select_covered_verts"
    bl_label = "Select Covered Vertices"
    bl_description = "Select vertices that are covered by selected meshes"
    bl_options = {'UNDO'}

    maxDist : FloatProperty(
        name = "Max Distance (cm)",
        description = "Max distance between face and cover",
        min = 0,
        default = 2)

    minDist : FloatProperty(
        name = "Min Distance (cm)",
        description = "Min distance between face and cover",
        max = 0,
        default = -1)

    def draw(self, context):
        self.layout.prop(self, "maxDist")
        self.layout.prop(self, "minDist")

    def run(self, context):
        hum = context.object
        clothes = [clo for clo in getSelectedMeshes(context) if clo != hum]
        activateObject(context, hum)
        setMode('EDIT')
        bpy.ops.mesh.select_mode(type='VERT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        minDist = -self.minDist * GS.scale
        maxDist = self.maxDist * GS.scale
        verts = hum.data.vertices
        corners = [[(vn, verts[vn].co) for vn in f.vertices] for f in hum.data.polygons]
        normals = [f.normal for f in hum.data.polygons]
        from mathutils.bvhtree import BVHTree
        deps = context.evaluated_depsgraph_get()
        for clo in clothes:
            uncovered = {}
            bvhtree = BVHTree.FromObject(clo, deps)
            for fdata,no in zip(corners, normals):
                for vn,co in fdata:
                    ray = bvhtree.ray_cast(co, no, maxDist)
                    if ray[0] is None and minDist > 0:
                        ray = bvhtree.ray_cast(co, -no, minDist)
                    if ray[0] is None:
                        for vn1,_ in fdata:
                            uncovered[vn1] = True
                        continue
            covered = [v for v in hum.data.vertices if v.index not in uncovered]
            for v in covered:
                v.select = True
            clo.hide_set(True)


    def sequel(self, context):
        if context.object:
            setMode('EDIT')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddVisibility,
    DAZ_OT_RemoveVisibility,
    DAZ_OT_CreateMasks,
    DAZ_OT_CopyMasks,
    DAZ_OT_AddShrinkwrap,
    DAZ_OT_MakeInvisible,
    DAZ_OT_AddShapeVisDrivers,
    DAZ_OT_SelectCoveredVerts,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


