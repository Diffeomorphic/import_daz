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

import bpy
import os
import numpy as np
from .utils import *
from .error import *

theSimPresets = {}

#-------------------------------------------------------------
#  dForce simulation
#-------------------------------------------------------------

class DForce:
    def __init__(self, inst, mod, extra):
        self.instance = inst
        self.modifier = mod
        self.extra = extra

    def __repr__(self):
        return "<DForce %s\ni: %s\nm: %s\ne: %s>" % (self.type, self.instance, self.modifier, self.instance.rna)

    def build(self, context):
        pass

#-------------------------------------------------------------
#  studio/modifier/dynamic_generate_hair
#-------------------------------------------------------------

class DynGenHair(DForce):
    type = "DynGenHair"

#-------------------------------------------------------------
#  studio/modifier/dynamic_simulation
#-------------------------------------------------------------

class DynSim(DForce):
    type = "DynSim"

    def build(self, context):
        if not GS.useSimulation:
            return
        from .node import Instance
        from .geometry import GeoNode
        if isinstance(self.instance, Instance) and self.instance.geometries:
            geonode = self.instance.geometries[0]
        elif isinstance(self.instance, GeoNode):
            geonode = self.instance
        else:
            reportError("Bug DynSim %s" % self.instance, trigger=(2,3))
            return
        ob = geonode.rna
        if ob and ob.type == 'MESH':
            ob.DazCloth = True
            self.addPinVertexGroup(ob, geonode)


    def addPinVertexGroup(self, ob, geonode):
        nverts = len(ob.data.vertices)

        # Influence group
        useInflu = False
        if "influence_weights" in self.extra.keys():
            vcount = self.extra["vertex_count"]
            if vcount == nverts:
                useInflu = True
                influ = dict([(vn,0.0) for vn in range(nverts)])
                vgrp = ob.vertex_groups.new(name = "dForce Influence")
                weights = self.extra["influence_weights"]["values"]
                for vn,w in weights:
                    influ[vn] = w
                    vgrp.add([vn], w, 'REPLACE')
            else:
                msg = ("Influence weight mismatch: %d != %d" % (vcount, nverts))
                reportError(msg, trigger=(2,4))
        if not useInflu:
            influ = dict([(vn,1.0) for vn in range(nverts)])

        # Constant per material vertex group
        vgrp = ob.vertex_groups.new(name = "dForce Pin")
        geo = geonode.data
        mnums = dict([(mgrp, mn) for mn,mgrp in enumerate(geo.polygon_material_groups)])
        for simset in geonode.simsets:
            strength = simset.modifier.getValue(["Dynamics Strength"], 0.0)
            if strength == 1.0 and not useInflu:
                continue
            for mgrp in simset.modifier.groups:
                mn = mnums[mgrp]
                for f in ob.data.polygons:
                    if f.material_index == mn:
                        for vn in f.vertices:
                            vgrp.add([vn], 1-strength*influ[vn], 'REPLACE')
        return vgrp

#-------------------------------------------------------------
#   Make Collision
#-------------------------------------------------------------

class Collision:
    collDist : FloatProperty(
        name = "Collision Distance",
        description = "Minimun collision distance (mm)",
        min = 1.0, max = 20.0,
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "collDist")

    def addCollision(self, ob):
        subsurf = hideModifier(ob, 'SUBSURF')
        mod = getModifier(ob, 'COLLISION')
        if mod is None:
            mod = ob.modifiers.new("Collision", 'COLLISION')
        ob.collision.thickness_outer = 0.1*ob.DazScale*self.collDist
        if subsurf:
            subsurf.restore(ob)


class DAZ_OT_MakeCollision(DazPropsOperator, Collision, IsMesh):
    bl_idname = "daz.make_collision"
    bl_label = "Make Collision"
    bl_description = "Add collision modifiers to selected meshes"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.addCollision(ob)

#-------------------------------------------------------------
#   Make Cloth
#-------------------------------------------------------------

class Cloth:
    simPreset : EnumProperty(
        items = [('cotton.json', "Cotton", "Cotton"),
                 ('denim.json', "Denim", "Denim"),
                 ('leather.json', "Leather", "Leather"),
                 ('rubber.json', "Rubber", "Rubber"),
                 ('silk.json', "Silk", "Silk")],
        name = "Preset",
        description = "Simulation preset")

    pinGroup : StringProperty(
        name = "Pin Group",
        description = "Use this group as pin group",
        default = "dForce Pin")

    simQuality : IntProperty(
        name = "Simulation Quality",
        description = "Simulation Quality",
        default = 16)

    collQuality : IntProperty(
        name = "Collision Quality",
        description = "Collision Quality",
        default = 4)

    gsmFactor : FloatProperty(
        name = "GSM Factor",
        description = "GSM Factor (vertex mass multiplier)",
        min = 0.0,
        default = 0.5)

    def draw(self, context):
        self.layout.prop(self, "simPreset")
        self.layout.prop(self, "pinGroup")
        self.layout.prop(self, "simQuality")
        self.layout.prop(self, "collQuality")
        self.layout.prop(self, "gsmFactor")


    def addCloth(self, ob):
        scale = ob.DazScale
        collision = hideModifier(ob, 'COLLISION')
        subsurf = hideModifier(ob, 'SUBSURF')

        cloth = getModifier(ob, 'CLOTH')
        if cloth is None:
            cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        self.setPreset(cset)
        cset.mass *= self.gsmFactor
        cset.quality = self.simQuality
        # Collision settings
        colset = cloth.collision_settings
        colset.distance_min = 0.1*scale*self.collDist
        colset.self_distance_min = 0.1*scale*self.collDist
        colset.collision_quality = self.collQuality
        colset.use_self_collision = True
        # Pinning
        cset.vertex_group_mass = self.pinGroup
        cset.pin_stiffness = 1.0

        if subsurf:
            subsurf.restore(ob)
        if collision:
            collision.restore(ob)


    def setPreset(self, cset):
        global theSimPresets
        if not theSimPresets:
            from .load_json import loadJson
            folder = os.path.dirname(__file__) + "/data/presets"
            for file in os.listdir(folder):
                filepath = os.path.join(folder, file)
                theSimPresets[file] = loadJson(filepath)
        struct = theSimPresets[self.simPreset]
        for key,value in struct.items():
            setattr(cset, key, value)


class DAZ_OT_MakeCloth(DazPropsOperator, Cloth, Collision, IsMesh):
    bl_idname = "daz.make_cloth"
    bl_label = "Make Cloth"
    bl_description = "Add cloth modifiers to selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        Cloth.draw(self, context)
        Collision.draw(self, context)

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.addCloth(ob)

#-------------------------------------------------------------
#  studio/modifier/dynamic_hair_follow
#-------------------------------------------------------------

class DynHairFlw(DForce):
    type = "DynHairFlw"

#-------------------------------------------------------------
#  studio/modifier/line_tessellation
#-------------------------------------------------------------

class LinTess(DForce):
    type = "LinTess"

#-------------------------------------------------------------
#  studio/simulation_settings/dynamic_simulation
#-------------------------------------------------------------

class SimSet(DForce):
    type = "SimSet"

#-------------------------------------------------------------
#  class for storing modifiers
#-------------------------------------------------------------

def hideModifier(ob, mtype):
    mod = getModifier(ob, mtype)
    if mod:
        store = ModStore(mod)
        ob.modifiers.remove(mod)
        return store
    else:
        return None


class ModStore:
    def __init__(self, mod):
        self.name = mod.name
        self.type = mod.type
        self.data = {}
        self.store(mod, self.data)
        self.settings = {}
        if hasattr(mod, "settings"):
            self.store(mod.settings, self.settings)
        self.collision_settings = {}
        if hasattr(mod, "collision_settings"):
            self.store(mod.collision_settings, self.collision_settings)


    def store(self, data, struct):
        for key in dir(data):
            if (key[0] == '_' or
                key == "name" or
                key == "type"):
                continue
            value = getattr(data, key)
            if (isSimpleType(value) or
                isinstance(value, bpy.types.Object)):
                struct[key] = value


    def restore(self, ob):
        mod = ob.modifiers.new(self.name, self.type)
        self.restoreData(self.data, mod)
        if self.settings:
            self.restoreData(self.settings, mod.settings)
        if self.collision_settings:
            self.restoreData(self.collision_settings, mod.collision_settings)


    def restoreData(self, struct, data):
        for key,value in struct.items():
            try:
                setattr(data, key, value)
            except:
                pass

#-------------------------------------------------------------
#   Make Simulation
#-------------------------------------------------------------

class Settings:
    filepath = "~/daz_importer_simulations.json"

    props = ["simPreset", "pinGroup", "simQuality",
             "collQuality", "gsmFactor", "collDist"]

    def invoke(self, context, event):
        from .fileutils import openSettingsFile
        struct = openSettingsFile(self.filepath)
        if struct:
            print("Load settings from", self.filepath)
            self.readSettings(struct)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def readSettings(self, struct):
        if "simulation-settings" in struct.keys():
            settings = struct["simulation-settings"]
            for key,value in settings.items():
                if key in self.props:
                    setattr(self, key, value)

    def saveSettings(self):
        from .load_json import saveJson
        struct = {}
        for key in self.props:
            value = getattr(self, key)
            struct[key] = value
        filepath = os.path.expanduser(self.filepath)
        saveJson({"simulation-settings" : struct}, filepath)
        print("Settings file %s saved" % filepath)


class DAZ_OT_MakeSimulation(DazOperator, Collision, Cloth, Settings):
    bl_idname = "daz.make_simulation"
    bl_label = "Make Simulation"
    bl_description = "Create simulation from Daz data"
    bl_options = {'UNDO'}

    def draw(self, context):
        Cloth.draw(self, context)
        Collision.draw(self, context)

    def run(self, context):
        for ob in getVisibleMeshes(context):
            if ob.DazCollision:
                self.addCollision(ob)
            if ob.DazCloth:
                self.addCloth(ob)
        self.saveSettings()

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


class DAZ_OT_AddSoftbody(DazPropsOperator, SoftbodyOptions, IsMesh):
    bl_idname = "daz.add_softbody"
    bl_label = "Add Softbody"
    bl_description = "Add softbody simulation to selected meshes"
    bl_options = {'UNDO'}

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
        self.layout.prop(self, "useRemoveOld")


    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False


    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def run(self, context):
        from .load_json import loadJson
        from .hide import makePermanentMaterial
        hum = self.human = context.object
        if hum.parent and hum.parent.type == 'ARMATURE':
            self.rig = hum.parent
        else:
            raise DazError("No armature found")
        selected = getSelectedMeshes(context)
        folder = os.path.join(os.path.dirname(__file__), "data", "softbody")
        path = os.path.join(folder, "softbody-%s.json" % hum.DazMesh.lower())
        if not os.path.exists(path):
            msg = ("No softbody simulation exists for this type of mesh:\n%s" % hum.DazMesh)
            raise DazError(msg)
        struct = loadJson(path)

        path = os.path.join(folder, "%s.json" % self.rig.DazRig.lower())
        bstruct = loadJson(path)
        self.bones = bstruct["bones"]
        self.fixDeformBones()
        subsurfs = {}
        multires = {}
        for ob in selected:
            subsurfs[ob.name] = self.removeSubsurf(ob)
            multires[ob.name] = self.setMultiresZero(ob)

        hstruct = struct["mesh"]
        self.addVertexGroups(hum, selected, hstruct["vertex_groups"])
        coll = self.addCollection(context)

        col = self.addObject("COLLISION", struct["collision"], hum, hstruct, coll)
        if col:
            makePermanentMaterial(col, "DazGreenInvis", (0,1,0,1))
            coll.objects.link(col)
            self.addArmature(col)
            self.addCollision(col)

        softbodies = []
        if self.useCombinedSoftbody:
            softbody = self.makeSoftbody("SOFTBODY", struct["softbody"], hum, hstruct, coll, context)
            softbodies.append(softbody)
        else:
            for key,data in struct["softbody"].items():
                if getattr(self, "use%s" % key):
                    sstruct = {key:data}
                    softbody = self.makeSoftbody(key.upper(), sstruct, hum, hstruct, coll, context)
                    if softbody:
                        softbodies.append(softbody)

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
                print("Remove %s from %s" % (vname, ob.name))
                ob.vertex_groups.remove(vgrp)


    def addCollection(self, context):
        rigcoll = getCollection(context, self.rig)
        for coll in rigcoll.children.values():
            if baseName(coll.name) == "Simulation":
                return coll
        coll = bpy.data.collections.new("Simulation")
        rigcoll.children.link(coll)
        layer = getLayerCollection(context, coll)
        layer.hide_viewport = True
        coll.hide_render = True
        return coll


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
                    unlinkAll(ob)

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


    def makeSoftbody(self, name, sstruct, hum, hstruct, coll, context):
        from .hide import makePermanentMaterial
        softbody = self.addObject(name, sstruct, hum, hstruct, coll)
        if softbody:
            makePermanentMaterial(softbody, "DazRedInvis", (1,0,0,1))
            coll.objects.link(softbody)
            self.addArmature(softbody)
            self.addSoftBody(softbody, context)
            self.addCorrSmooth(softbody, "", 2, 'SIMPLE')
        return softbody


    def addArmature(self, ob):
        mod = ob.modifiers.new("Armature", 'ARMATURE')
        mod.object = self.rig
        mod.use_deform_preserve_volume = True
        ob.parent = self.rig


    def addCollision(self, ob):
        mod = ob.modifiers.new("Collision", 'COLLISION')
        cset = ob.collision
        cset.damping = 1.0
        cset.thickness_outer = 1.0*ob.DazScale
        cset.thickness_inner = 1.0*ob.DazScale
        cset.use_culling = True


    def addSoftBody(self, ob, context, coll=None):
        mod = ob.modifiers.new("Softbody", 'SOFT_BODY')
        mset = mod.settings
        mset.collision_collection = coll
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
        mod.use_sparse_bind = True
        bpy.ops.object.surfacedeform_bind(modifier=softbody.name)
        return True

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_MakeCollision,
    DAZ_OT_MakeCloth,
    DAZ_OT_MakeSimulation,
    DAZ_OT_AddSoftbody,
]

def register():
    bpy.types.Object.DazCollision = BoolProperty(default = True)
    bpy.types.Object.DazCloth = BoolProperty(default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)