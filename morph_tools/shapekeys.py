# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..morphing import MS

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
        rig = getRigFromContext(context)
        if not (rig and rig.animation_data and rig.animation_data.action):
            raise DazError("No action found")
        actrig = rig.animation_data.action
        fcurves_rig = getActionSlot(actrig).fcurves
        meshes = getShapeChildren(rig)
        if not meshes:
            raise DazError("No meshes with shapekeys selected")

        self.morphnames = {}
        for morphset in MS.Standards:
            pgs = getattr(dazRna(rig), "Daz%s" % morphset)
            for pg in pgs:
                self.morphnames[pg.name] = pg.text
        for cat in dazRna(rig).DazMorphCats:
            for pg in cat.morphs:
                self.morphnames[pg.name] = pg.text

        for ob in meshes:
            skeys = ob.data.shape_keys
            actslot = None
            fstruct = {}
            for fcurig in fcurves_rig:
                prop = getProp(fcurig.data_path)
                if prop:
                    skey = self.getShape(prop, skeys)
                    if skey:
                        channel = 'key_blocks["%s"].value' % skey.name
                        if skeys.animation_data is None:
                            skeys.animation_data_create()
                        skey.keyframe_insert("value")
                        if actslot is None:
                            act = skeys.animation_data.action
                            act.name = "%s:%s" % (ob.name, actrig.name)
                            actslot = getActionSlot(act, 'KEY')
                        fcu = actslot.fcurves.find(channel)
                        self.copyFcurve(fcurig, fcu)
                        fstruct[fcurig.data_path] = fcurig
            for fcu in fstruct.values():
                fcurves_rig.remove(fcu)


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
#   Apply all shapekeys
#-------------------------------------------------------------

class DAZ_OT_ApplyAllShapekeys(DazOperator, IsShape):
    bl_idname = "daz.apply_all_shapekeys"
    bl_label = "Apply All Shapekeys"
    bl_description = "Apply all shapekeys to selected meshes"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..apply import applyAllShapekeys
        for ob in getSelectedMeshes(context):
            applyAllShapekeys(ob)

#----------------------------------------------------------
#   Mix Shapekeys
#----------------------------------------------------------

def shapekeyItems1(self, context):
    filter = self.filter1.lower()
    enums = [(sname,sname,sname)
            for sname in context.object.data.shape_keys.key_blocks.keys()[1:]
            if filter in sname.lower()
           ]
    enums.sort()
    return enums


def shapekeyItems2(self, context):
    filter = self.filter2.lower()
    enums = [(sname,sname,sname)
              for sname in context.object.data.shape_keys.key_blocks.keys()[1:]
              if filter in sname.lower()
            ]
    enums.sort()
    return [("-", "-", "None")] + enums


class DAZ_OT_MixShapekeys(DazOperator, IsShape):
    bl_idname = "daz.mix_shapekeys"
    bl_label = "Mix Shapekeys"
    bl_description = "Mix shapekeys"
    bl_options = {'UNDO'}

    shape1 : EnumProperty(
        items = shapekeyItems1,
        name = "Shapekey 1",
        description = "First shapekey")

    shape2 : EnumProperty(
        items = shapekeyItems2,
        name = "Shapekey 2",
        description = "Second shapekey")

    factor1 : FloatProperty(
        name = "Factor 1",
        description = "First factor",
        default = 1.0)

    factor2 : FloatProperty(
        name = "Factor 2",
        description = "Second factor",
        default = 1.0)

    allSimilar : BoolProperty(
        name = "Mix All Similar",
        description = "Mix all shapekeys with similar names",
        default = False)

    overwrite : BoolProperty(
        name = "Overwrite First",
        description = "Overwrite the first shapekey",
        default = True)

    delete : BoolProperty(
        name = "Delete Merged",
        description = "Delete unused shapekeys after merge",
        default = True)

    newName : StringProperty(
        name = "New shapekey",
        description = "Name of new shapekey",
        default = "Shapekey")

    filter1 : StringProperty(
        name = "Filter 1",
        description = "Show only items containing this string",
        default = ""
        )

    filter2 : StringProperty(
        name = "Filter 2",
        description = "Show only items containing this string",
        default = ""
        )

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "allSimilar")
        row.prop(self, "overwrite")
        row.prop(self, "delete")
        row = self.layout.split(factor=0.2)
        row.label(text="")
        row.label(text="First")
        row.label(text="Second")
        if self.allSimilar:
            row = self.layout.split(factor=0.2)
            row.label(text="Factor")
            row.prop(self, "factor1", text="")
            row.prop(self, "factor2", text="")
            return
        row = self.layout.split(factor=0.2)
        row.label(text="")
        row.prop(self, "filter1", icon='VIEWZOOM', text="")
        row.prop(self, "filter2", icon='VIEWZOOM', text="")
        row = self.layout.split(factor=0.2)
        row.label(text="Factor")
        row.prop(self, "factor1", text="")
        row.prop(self, "factor2", text="")
        row = self.layout.split(factor=0.2)
        row.label(text="Shapekey")
        row.prop(self, "shape1", text="")
        row.prop(self, "shape2", text="")
        if not self.overwrite:
            self.layout.prop(self, "newName")


    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self, width=500)
        return {'RUNNING_MODAL'}


    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if self.allSimilar:
            shapes = self.findSimilar(ob, skeys)
            for shape1,shape2 in shapes:
                print("Mix", shape1, shape2)
                self.mixShapekeys(ob, skeys, shape1, shape2)
        else:
            self.mixShapekeys(ob, skeys, self.shape1, self.shape2)


    def findSimilar(self, ob, skeys):
        slist = list(skeys.key_blocks.keys())
        slist.sort()
        shapes = []
        for n in range(len(slist)-1):
            shape1 = slist[n]
            shape2 = slist[n+1]
            words = shape2.rsplit(".",1)
            if (len(words) == 2 and
                words[0] == shape1):
                shapes.append((shape1,shape2))
        return shapes


    def mixShapekeys(self, ob, skeys, shape1, shape2):
        if shape1 == shape2:
            raise DazError("Cannot merge shapekey to itself")
        skey1 = skeys.key_blocks[shape1]
        if shape2 == "-":
            skey2 = None
            factor = self.factor1 - 1
            coords = [(self.factor1 * skey1.data[n].co - factor * v.co)
                       for n,v in enumerate(ob.data.vertices)]
        else:
            skey2 = skeys.key_blocks[shape2]
            factor = self.factor1 + self.factor2 - 1
            coords = [(self.factor1 * skey1.data[n].co +
                       self.factor2 * skey2.data[n].co - factor * v.co)
                       for n,v in enumerate(ob.data.vertices)]
        if self.overwrite:
            skey = skey1
        else:
            skey = ob.shape_key_add(name=self.newName)
        for n,co in enumerate(coords):
            skey.data[n].co = co
        if self.delete:
            if skey2:
                self.deleteShape(ob, skeys, skey2, shape2)
            if not self.overwrite:
                self.deleteShape(ob, skeys, skey1, shape1)


    def deleteShape(self, ob, skeys, skey, sname):
        from ..transfer import removeShapeDriversAndProps
        skey.driver_remove("value")
        skey.driver_remove("mute")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        removeShapeDriversAndProps(ob.parent, sname)
        updateDrivers(skeys)
        ob.shape_key_remove(skey)

#----------------------------------------------------------
#   Shapekey to vertexgroup
#----------------------------------------------------------

class DAZ_OT_VisualizeShapekey(DazPropsOperator, IsShape):
    bl_idname = "daz.visualize_shapekey"
    bl_label = "Visualize Shapekey"
    bl_description = "Visualize shapekey as a vertex group"
    bl_options = {'UNDO'}

    mindist : FloatProperty(
        name = "Lower Threshold",
        description = "Lower threshold for shapekey distance, in mm",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 0.1)

    maxdist : FloatProperty(
        name = "Upper Threshold",
        description = "Upper threshold for shapekey distance, in mm",
        min = 0.0, max = 100.0,
        precision = 4,
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "mindist")
        self.layout.prop(self, "maxdist")

    def run(self, context):
        ob = context.object
        eps = 0.1*self.mindist*GS.scale
        factor = 10/(self.maxdist*GS.scale)
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[ob.active_shape_key_index]
        if skey.name not in ob.vertex_groups:
            vgrp = ob.vertex_groups.new(name=skey.name)
        else:
            vgrp = ob.vertex_groups[skey.name]
            for vn,v in enumerate(ob.data.vertices):
                vgrp.remove([vn])
        dists = [(vn,(skey.data[vn].co - v.co).length) for vn,v in enumerate(ob.data.vertices)]
        weights = [(vn,factor*dist) for vn,dist in dists if dist > eps]
        for vn,w in weights:
            vgrp.add([vn], w, 'REPLACE')

#----------------------------------------------------------
#   Mute Shapekeys
#----------------------------------------------------------

class DAZ_OT_MuteShapekeys(DazPropsOperator, IsShape):
    bl_idname = "daz.mute_shapekeys"
    bl_label = "Mute Shapekeys"
    bl_description = "Mute or unmute all shapekeys of selected meshes"
    bl_options = {'UNDO'}

    show : BoolProperty(
        name = "Show",
        description = "Mute shapekeys if disabled, otherwise unmute",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "show")

    def run(self, context):
        mute = (not self.show)
        for ob in getSelectedMeshes(context):
            skeys = ob.data.shape_keys
            if skeys:
                for skey in skeys.key_blocks:
                    skey.mute = mute

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_ApplyAllShapekeys,
    DAZ_OT_MixShapekeys,
    DAZ_OT_VisualizeShapekey,
    DAZ_OT_MeshToShape,
    DAZ_OT_TransferAnimationToShapekeys,
    DAZ_OT_MuteShapekeys,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)