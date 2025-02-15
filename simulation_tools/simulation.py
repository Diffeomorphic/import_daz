# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import numpy as np
from ..utils import *
from ..error import *
from ..dforce import Collision, Cloth
from ..fileutils import DF

#-------------------------------------------------------------
#   Collision
#-------------------------------------------------------------

class DAZ_OT_MakeCollision(DazPropsOperator, Collision, Cloth, IsMesh):
    bl_idname = "daz.make_collision"
    bl_label = "Make Collision"
    bl_description = "Add collision modifiers to selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "collision")

    def run(self, context):
        meshes = getSelectedMeshes(context)
        if meshes:
            self.addClothCollection(context, meshes)
            for ob in meshes:
                self.addCollision(ob, self.collection)

#-------------------------------------------------------------
#   Cloth
#-------------------------------------------------------------

class DAZ_OT_MakeCloth(DazPropsOperator, Collision, Cloth, IsMesh):
    bl_idname = "daz.make_cloth"
    bl_label = "Make Cloth"
    bl_description = "Add cloth modifiers to selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawCloth(context, self.layout)

    def run(self, context):
        meshes = getSelectedMeshes(context)
        if meshes:
            self.addClothCollection(context, meshes)
            for ob in meshes:
                self.addCloth(ob)

#-------------------------------------------------------------
#   Make Simulation
#-------------------------------------------------------------

class DAZ_OT_MakeDForce(DazPropsOperator, Collision, Cloth):
    bl_idname = "daz.make_dforce"
    bl_label = "Make dForce Simulation"
    bl_description = "Add cloth and collision modifiers to selected meshes from DAZ data"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawCloth(context, self.layout)

    def run(self, context):
        meshes = getSelectedMeshes(context)
        if meshes:
            self.addClothCollection(context, meshes)
            for ob in meshes:
                if dazRna(ob).DazCloth:
                    self.addCloth(ob)
                elif dazRna(ob).DazCollision:
                    self.addCollision(ob, self.collection)

#-------------------------------------------------------------
#   Softbody
#-------------------------------------------------------------

from mathutils import Matrix

class SoftbodyOptions:
    useChest : BoolProperty(
        name = "Chest",
        description = "Add softbody simulation for chest",
        default = True)

    useBelly : BoolProperty(
        name = "Belly",
        description = "Add softbody simulation for belly",
        default = True)

    useGlutes : BoolProperty(
        name = "Glutes",
        description = "Add softbody simulation for glutes",
        default = True)

    useArms : BoolProperty(
        name = "Arm Collision",
        description = "Add collision to arms",
        default = True)

    useLegs : BoolProperty(
        name = "Leg Collision",
        description = "Add collision to legs",
        default = True)


class DAZ_OT_AddSoftbody(DazPropsOperator, SoftbodyOptions, Collision, IsMesh):
    bl_idname = "daz.add_softbody"
    bl_label = "Add Softbody"
    bl_description = "Add softbody simulation to selected meshes"
    bl_options = {'UNDO'}

    onConcave : EnumProperty(
        items = [('NONE', "None", "No modification to softbody objects"),
                 ('PLANAR', "Planar", "Make softbody faces planar"),
                 ('TRIANGULATE', "Triangulate", "Triangulate softbody meshes")],
        name = "Concave Polygons",
        description = "Method to avoid problems with concave polygons",
        default = 'NONE')

    useSmooth : BoolProperty(
        name = "Smooth",
        description = "Add a corrective smooth modifier to the meshes",
        default = True)

    useCombinedSoftbody : BoolProperty(
        name = "Combined Softbody",
        description = "Only use a combined softbody",
        default = True)

    useRemoveOld : BoolProperty(
        name = "Remove Existing Objects",
        description = "Remove existing collision and softbody objects",
        default = True)

    def draw(self, context):
        self.layout.label(text="Softbody Objects")
        self.layout.prop(self, "useChest")
        self.layout.prop(self, "useBelly")
        self.layout.prop(self, "useGlutes")
        self.layout.prop(self, "useCombinedSoftbody")
        self.layout.label(text="Collision Objects")
        self.layout.prop(self, "useArms")
        self.layout.prop(self, "useLegs")
        self.layout.separator()
        self.layout.prop(self, "useSmooth")
        self.layout.prop(self, "onConcave")
        self.layout.prop(self, "useRemoveOld")


    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False


    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def run(self, context):
        from ..matsel import makePermanentMaterial
        hum = self.human = context.object
        if hum.parent and hum.parent.type == 'ARMATURE':
            self.rig = hum.parent
        else:
            raise DazError("No armature found")
        selected = getSelectedMeshes(context)
        char = dazRna(hum).DazMesh.lower()
        struct = DF.loadEntry("softbody-%s" % char, "softbody")
        rigtype = dazRna(self.rig).DazRig.lower()
        bstruct = DF.loadEntry(rigtype, "softbody")
        self.bones = bstruct["bones"]
        self.fixDeformBones()
        subsurfs = {}
        multires = {}
        for ob in selected:
            subsurfs[ob.name] = self.removeSubsurf(ob)
            multires[ob.name] = self.setMultiresZero(ob)

        hstruct = struct["mesh"]
        self.addVertexGroups(hum, selected, hstruct["vertex_groups"])
        softcoll = self.addCollection(context, "Softbody")
        collcoll = self.addCollection(context, "Softbody Collisions")

        col = self.addObject("COLLISION", struct["collision"], hum, hstruct, collcoll)
        if col:
            makePermanentMaterial(col, "DazGreenInvis", (0,1,0,1))
            collcoll.objects.link(col)
            self.addArmature(col)
            self.addCollision(col)

        softbodies = []
        if self.useCombinedSoftbody:
            softbody = self.addObject("SOFTBODY", struct["softbody"], hum, hstruct, softcoll)
            if softbody:
                softbodies.append(softbody)
        else:
            for key,data in struct["softbody"].items():
                if getattr(self, "use%s" % key):
                    sstruct = {key:data}
                    softbody = self.addObject(key.upper(), sstruct, hum, hstruct, softcoll)
                    if softbody:
                        softbodies.append(softbody)

        for softbody in softbodies:
            softcoll.objects.link(softbody)

        if self.onConcave != 'NONE' and softbodies:
            bpy.ops.object.select_all(action='DESELECT')
            for softbody in softbodies:
                softbody.select_set(True)
            setMode('EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='SELECT')
            if self.onConcave == 'PLANAR':
                print("Make planar faces")
                bpy.ops.mesh.face_make_planar(factor=1.0, repeat=1)
            else:
                print("Convert to tris")
                bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
            setMode('OBJECT')

        from ..matsel import makePermanentMaterial
        for softbody in softbodies:
            makePermanentMaterial(softbody, "DazRedInvis", (1,0,0,1))
            self.addArmature(softbody)
            self.addSoftBody(softbody, context, collcoll)
            self.addCorrSmooth(softbody, "", 2, 'SIMPLE')
        self.hideCollection(context, softcoll)
        self.hideCollection(context, collcoll)

        for ob in selected:
            activateObject(context, ob)
            smooth = False
            for softbody in softbodies:
                if self.addSurfaceDeform(ob, softbody):
                    smooth = True
            if smooth:
                self.addCorrSmooth(ob, "SMOOTH", 4, 'LENGTH_WEIGHTED')
        activateObject(context, hum)
        for ob in selected:
            if not multires[ob.name]:
                self.restoreSubsurf(ob, subsurfs[ob.name])


    def fixDeformBones(self):
        for bname in self.bones.values():
            bone = self.rig.data.bones.get(bname)
            if bone:
                bone.use_deform = True


    def getBoneName(self, bname):
        if bname in self.bones.keys():
            return self.bones[bname]
        else:
            return bname


    def addVertexGroups(self, hum, selected, struct):
        if self.useCombinedSoftbody:
            weights = []
            for vname,data in struct.items():
                if (getattr(self, "use%s" % vname.capitalize()) and
                    not isinstance(data[0], str)):
                    weights += data
            self.addVertexGroup(hum, selected, "SOFTBODY", weights)
            for ob in selected:
                weights = []
                for vname,data in struct.items():
                    if (getattr(self, "use%s" % vname.capitalize()) and
                        isinstance(data[0], str)):
                        weights += self.getWeightsFromName(ob, vname, data)
                if weights:
                    vgrp = ob.vertex_groups.get("SOFTBODY")
                    if vgrp is None:
                        vgrp = ob.vertex_groups.new(name="SOFTBODY")
                    for vn,w in weights:
                        vgrp.add([vn], w, 'REPLACE')
        else:
            for vname,data in struct.items():
                if getattr(self, "use%s" % vname.capitalize()):
                    self.addVertexGroup(hum, selected, vname, data)


    def addVertexGroup(self, hum, selected, vname, data):
        for ob in selected:
            vgrp = ob.vertex_groups.get(vname)
            if vgrp:
                ob.vertex_groups.remove(vgrp)
        if data and isinstance(data[0], str):
            self.addVertexGroupFromNames(selected, vname, data)
        else:
            self.addVertexGroupFromWeights(hum, selected, vname, data)
        return vgrp


    def addVertexGroupFromNames(self, selected, vname, data):
        for ob in selected:
            bname = self.getBoneName(vname)
            weights = self.getWeightsFromName(ob, bname, data)
            if weights:
                vgrp = ob.vertex_groups.new(name=bname)
                for vn,w in weights:
                    vgrp.add([vn], w, 'REPLACE')


    def getWeightsFromName(self, ob, vname, data):
        wstruct = dict([(vn,0.0) for vn in range(len(ob.data.vertices))])
        for wname in data:
            bname = self.getBoneName(wname)
            vgrp = ob.vertex_groups.get(bname)
            if vgrp:
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group == vgrp.index:
                            wstruct[v.index] += g.weight
        wmax = max(list(wstruct.values()))
        if wmax > 0.1:
            return [(vn, max(0, min(1, 1.5*w))) for vn,w in wstruct.items() if w > 0.001]
        else:
            return []


    def addVertexGroupFromWeights(self, hum, selected, vname, weights):
        vgrp = hum.vertex_groups.new(name=vname)
        for vn,w in weights:
            vgrp.add([vn], w, 'REPLACE')
        bpy.ops.object.data_transfer(
            data_type = "VGROUP_WEIGHTS",
            vert_mapping = 'POLYINTERP_NEAREST',
            layers_select_src = vname,
            layers_select_dst = 'NAME')
        for ob in selected:
            vgrp = ob.vertex_groups.get(vname)
            if vgrp is None:
                print("No vertex group", ob.name, vname)
                continue
            ok = False
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == vgrp.index:
                        ok = True
                        break
            if not ok:
                if not ES.easy:
                    print("Remove %s from %s" % (vname, ob.name))
                ob.vertex_groups.remove(vgrp)


    def addCollection(self, context, cname):
        rigcoll = getCollection(context, self.rig)
        for coll in rigcoll.children.values():
            if baseName(coll.name) == cname:
                return coll
        coll = bpy.data.collections.new(cname)
        rigcoll.children.link(coll)
        return coll


    def hideCollection(self, context, coll):
        layer = getLayerCollection(context, coll)
        layer.hide_viewport = True
        coll.hide_render = True


    def addObject(self, name, struct, hum, hstruct, coll):
        # Collect data
        vn0 = 0
        verts = []
        faces = []
        vgroups = {}
        for key,data in struct.items():
            if getattr(self, "use%s" % key):
                verts += data["vertices"]
                faces += [[vn0+vn for vn in f] for f in data["faces"]]
                for vgname,weights in data["vertex_groups"].items():
                    if vgname not in vgroups.keys():
                        vgroups[vgname] = []
                    vgroup = vgroups[vgname]
                    vgroup += [(vn0+vn,w) for vn,w in weights]
                vn0 += len(data["vertices"])
        if not verts:
            return None

        # Transfer shape
        verts = self.transferShape(verts, hum, hstruct)

        # Remove previous objects
        if self.useRemoveOld:
            for ob in coll.objects.values():
                if baseName(ob.name) == name:
                    unlinkAll(ob, True)

        # Create mesh and vertex groups
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name, me)
        ob.name = name
        ob.hide_render = True
        ob.show_in_front = True
        for vname,weights in vgroups.items():
            if not weights:
                continue
            bname = self.getBoneName(vname)
            vgrp = ob.vertex_groups.new(name=bname)
            for vn,w in weights:
                vgrp.add([vn], w, 'REPLACE')
        return ob


    def transferShape(self, verts, hum, hstruct):
        basecoords = np.array(hstruct["vertices"], dtype=float)
        actcoords = np.array([list(v.co) for v in hum.data.vertices], dtype=float)
        coords = np.array(verts, dtype=float)
        if basecoords.shape != actcoords.shape:
            print("Shape mismatch", basecoords.shape, actcoords.shape)
            return verts
        diff = coords[:,np.newaxis,:] - basecoords[np.newaxis,:,:]
        dists = np.sum(np.abs(diff), axis=2)
        match = np.argmin(dists, axis=1)
        offsets = actcoords - basecoords
        coords = coords + offsets[match]
        return list(coords)


    def addArmature(self, ob):
        mod = ob.modifiers.new("Armature", 'ARMATURE')
        mod.object = self.rig
        mod.use_deform_preserve_volume = True
        ob.parent = self.rig


    def addSoftBody(self, ob, context, collcoll):
        mod = ob.modifiers.new("Softbody", 'SOFT_BODY')
        mset = mod.settings
        mset.collision_collection = collcoll
        mset.friction = 0.5
        mset.mass = 2.0
        mset.vertex_group_mass = "MASS"
        mset.speed = 1.56 / context.scene.render.fps * 30

        mset.use_goal = True
        mset.vertex_group_goal = "PIN"
        mset.goal_spring = 0.7
        mset.goal_friction = 0
        mset.goal_default = 1.0
        mset.goal_min = 0.0
        mset.goal_max = 1.0

        mset.use_edges = True
        mset.pull = 0.3
        mset.push = 0.3
        mset.damping = 30
        mset.bend = 0.15
        mset.use_edge_collision = True
        mset.use_face_collision = True
        mset.use_stiff_quads = True
        mset.shear = 1.0

        mset.use_self_collision = False
        mset.ball_size = 0.7
        mset.ball_stiff = 10.0
        mset.ball_damp = 0.5
        mset.choke = 0
        mset.fuzzy = 50

        mset.step_min = 16
        mset.step_max = 256
        mset.use_auto_step = False
        mset.error_threshold = 0.001


    def removeSubsurf(self, ob):
        mod = getModifier(ob, 'SUBSURF')
        subsurf = {}
        if mod:
            for key in dir(mod):
                if key[0] != "_":
                    subsurf[key] = getattr(mod, key)
            ob.modifiers.remove(mod)
        return subsurf


    def setMultiresZero(self, ob):
        mod = getModifier(ob, 'MULTIRES')
        if mod:
            levels = mod.levels
            mod.levels = 0
            return True
        return False


    def restoreSubsurf(self, ob, subsurf):
        if subsurf:
            ob.modifiers.new("Subsurf", 'SUBSURF')
            mod = ob.modifiers[-1]
            for key,value in subsurf.items():
                try:
                    setattr(mod, key, value)
                except AttributeError:
                    pass


    def addCorrSmooth(self, ob, vgrp, iters, stype):
        if not self.useSmooth:
            return
        for mod in list(ob.modifiers):
            if mod.type == 'CORRECTIVE_SMOOTH':
                ob.modifiers.remove(mod)
        mod = ob.modifiers.new("Corr Smooth", 'CORRECTIVE_SMOOTH')
        mod.factor = 0.5
        mod.iterations = iters
        mod.scale = 1.0
        mod.smooth_type = stype
        mod.vertex_group = vgrp


    def addSurfaceDeform(self, ob, softbody):
        if softbody.name not in ob.vertex_groups.keys():
            return False
        for mod in list(ob.modifiers):
            if mod.type == 'SURFACE_DEFORM' and mod.name == softbody.name:
                ob.modifiers.remove(mod)
        mod = ob.modifiers.new(softbody.name, 'SURFACE_DEFORM')
        mod.target = softbody
        mod.falloff = 4.0
        mod.strength = 1.0
        mod.vertex_group = softbody.name
        if hasattr(mod, "use_sparse_bind"):
            mod.use_sparse_bind = True
        bpy.ops.object.surfacedeform_bind(modifier=softbody.name)
        return True

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_MakeCollision,
    DAZ_OT_MakeCloth,
    DAZ_OT_MakeDForce,
    DAZ_OT_AddSoftbody,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
