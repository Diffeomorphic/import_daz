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
import os
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
        #print("\nCREA", self)

    def __repr__(self):
        return "<DForce %s\ni: %s\nm: %s\ne: %s>" % (self.type, self.instance, self.modifier, self.instance.rna)

    def build(self, context):
        print("Build", self)
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
        if isinstance(self.instance, Instance):
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
#   Breast bounce
#-------------------------------------------------------------

from mathutils import Matrix

class DAZ_OT_AddBounce(DazOperator, IsMesh):
    bl_idname = "daz.add_bounce"
    bl_label = "Add Breast Bounce"
    bl_description = "Add breast bounce (G8F only)"
    bl_options = {'UNDO'}

    def run(self, context):
        from .load_json import loadJson
        from .finger import getFingerPrint
        ob = context.object
        rig = ob.parent
        if ob.DazMesh != "Genesis8-female":
            raise DazError("Only G8F")
        folder = os.path.dirname(__file__)
        path = os.path.join(folder, "data", "breasts", "%s.json" % ob.DazMesh.lower())
        struct = loadJson(path)
        finger = getFingerPrint(ob)
        if finger != struct["finger_print"]:
            msg = ("Fingerprint mismatch:\n  %s != %s\n" % (finger, struct["finger_print"]) +
                   '"%s" is not a mesh of type %s\n' % (ob.name, struct["name"]))
            raise DazError(msg)
        self.addVertexGroups(ob, struct["vertex_groups"])
        self.objects = []
        self.addCollisionObjects(context, ob, rig)
        self.applyTransforms()
        subsurf = self.removeSubsurf(ob)
        llat = self.addLattice(context, ob, rig, "Lat_L", "lPectoral", [6, 6, 6])
        rlat = self.addLattice(context, ob, rig, "Lat_R", "rPectoral", [6, 6, 6])
        lempty,lico,lgoal = self.addHelpers(context, ob, rig, struct["vertices"]["lNipple"], "lPectoral", "L")
        rempty,rico,rgoal = self.addHelpers(context, ob, rig, struct["vertices"]["rNipple"], "rPectoral", "R")
        ribo = self.addToCollections(context, ob, rig)
        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='POSE')
        self.dampedTrack(rig, "lPectoral", lgoal)
        self.dampedTrack(rig, "rPectoral", rgoal)
        self.addCorrSmooth(ob)
        if subsurf:
            ob.modifiers.new("Subsurf", 'SUBSURF')
        self.addRigidBodyWorld(context, ribo)
        self.addRigidBodyConstraint(context, lempty, lico, lgoal)
        self.addRigidBodyConstraint(context, rempty, rico, rgoal)



    def addVertexGroups(self, ob, struct):
        for vname,verts in struct.items():
            vgrp = ob.vertex_groups.get(vname)
            if vgrp:
                ob.vertex_groups.remove(vgrp)
            vgrp = ob.vertex_groups.new(name=vname)
            for vn,w in verts:
                vgrp.add([vn], w, 'REPLACE')


    def addCollisionObjects(self, context, ob, rig):
        collisionObjects = {
            "Col1_L" : ["lShldrBend", "Cylinder", "lShldrBend", "lShldrTwist", 0.15],
            "Col2_L" : ["lForearmBend", "Cylinder", "lForearmBend", "lForearmTwist", 0.15],
            "Col3_L" : ["lHand", "Cylinder", "lHand", "lHand", 0.45],
            "Col1_R" : ["rShldrBend", "Cylinder", "rShldrBend", "rShldrTwist", 0.15],
            "Col2_R" : ["rForearmBend", "Cylinder", "rForearmBend", "rForearmTwist", 0.15],
            "Col3_R" : ["rHand", "Cylinder", "rHand", "rHand", 0.45],
            "Ico_L" : ["lPectoral", "Icosphere", "lPectoral", "lPectoral", 0.2],
            "Ico_R" : ["rPectoral", "Icosphere", "rPectoral", "rPectoral", 0.2],
        }
        RX = Matrix.Rotation(90*D, 4, 'X')
        for cname,data in collisionObjects.items():
            bname, mtype, bname1, bname2, rad = data
            pb1 = rig.pose.bones[bname1]
            pb2 = rig.pose.bones[bname2]
            head = pb1.bone.head_local
            tail = pb2.bone.tail_local
            length = (tail - head).length
            rot = pb1.matrix.to_3x3().to_4x4()
            if mtype == "Cylinder":
                rot = rot @ RX
                trans = Matrix.Translation((head+tail)/2)
                bpy.ops.mesh.primitive_cylinder_add(radius=rad*length, depth=length)
                innerThick = 1.0
            elif mtype == "Icosphere":
                trans = Matrix.Translation(0.2*head + 0.8*tail)
                bpy.ops.mesh.primitive_ico_sphere_add(radius=rad*length)
                innerThick = 5.0
            wmat = trans @ rot
            col = context.object
            unlinkAll(col)
            self.parentBone(col, cname, rig, bname, wmat)
            mod = col.modifiers.new("Collision", 'COLLISION')
            col.collision.thickness_outer = 0.1*ob.DazScale
            col.collision.thickness_inner = innerThick*ob.DazScale


    def addHelpers(self, context, ob, rig, vnum, bname, suffix):
        nip = ob.data.vertices[vnum].co
        bone = rig.data.bones[bname]
        x = 0.0
        loc = (1-x)*bone.head_local + x*bone.tail_local

        bpy.ops.object.empty_add(location=loc)
        empty1 = context.object
        empty1.empty_display_size = 0.1
        wmat = empty1.matrix_world.copy()
        self.parentBone(empty1, "RiBoEmpty_%s" % suffix, rig, bone.parent.name, wmat)

        bpy.ops.mesh.primitive_ico_sphere_add(radius=ob.DazScale)
        ico = context.object
        loc[2] = nip[2]
        wmat = Matrix.Translation(loc).to_4x4()
        self.parentBone(ico, "RiBoIco_%s" % suffix, empty1, None, wmat)

        bpy.ops.object.empty_add()
        empty2 = context.object
        empty2.empty_display_size = 0.1
        self.parentBone(empty2, "RiBoCns_%s" % suffix, ico, None, wmat)

        bpy.ops.mesh.primitive_ico_sphere_add(radius=2*ob.DazScale)
        goal = context.object
        wmat = Matrix.Translation(nip).to_4x4()
        self.parentBone(goal, "RiBoGoal_%s" % suffix, rig, bone.parent.name, wmat)
        return empty2, ico, goal


    def addRigidBodyWorld(self, context, ribo):
        bpy.ops.rigidbody.world_add()
        world = context.scene.rigidbody_world
        world.collection = ribo


    def addRigidBodyConstraint(self, context, empty, ico, goal):
        ico.rigid_body.type = 'PASSIVE'
        goal.rigid_body.type = 'ACTIVE'
        activateObject(context, empty)
        bpy.ops.rigidbody.constraint_add()
        rbc = empty.rigid_body_constraint
        rbc.type = 'GENERIC_SPRING'
        rbc.enabled = True
        rbc.disable_collisions = True
        rbc.object1 = ico
        rbc.object2 = goal
        for x,stiff,damp in [("x", 80, 1), ("y", 100, 5), ("z", 80, 1)]:
            setattr(rbc, "use_spring_ang_%s" % x, True)
            setattr(rbc, "spring_stiffness_ang_%s" % x, stiff)
            setattr(rbc, "spring_damping_ang_%s" % x, damp)
        for x,stiff,damp in [("x", 1000, 100), ("y", 1000, 100), ("z", 1000, 100)]:
            setattr(rbc, "use_spring_%s" % x, True)
            setattr(rbc, "spring_stiffness_%s" % x, stiff)
            setattr(rbc, "spring_damping_%s" % x, damp)


    def addLattice(self, context, ob, rig, lname, bname, size):
        pb = rig.pose.bones[bname]
        head = pb.bone.head_local
        tail = pb.bone.tail_local
        rot = pb.matrix.to_3x3().to_4x4()
        trans = Matrix.Translation(0.2*head + 0.8*tail)
        scale = Matrix.Diagonal(size).to_4x4()
        wmat = trans @ rot @ scale.inverted()
        bpy.ops.object.add(type='LATTICE')
        lat = context.object
        unlinkAll(lat)
        ldata = lat.data
        (ldata.points_u, ldata.points_v, ldata.points_w) = size
        self.parentBone(lat, lname, rig, bname, wmat)
        mod = ob.modifiers.new(lat.name, 'LATTICE')
        mod.object = lat
        mod.vertex_group = "%s_copy" % bname
        mod.strength = 1.0
        return lat


    def parentBone(self, ob, cname, rig, bname, wmat):
        ob.name = cname
        ob.parent = rig
        if bname:
            ob.parent_type = 'BONE'
            ob.parent_bone = bname
        setWorldMatrix(ob, wmat)
        self.objects.append(ob)


    def applyTransforms(self):
        bpy.ops.object.select_all(action='DESELECT')
        for ob in self.objects:
            ob.select_set(True)
        bpy.ops.object.transform_apply()


    def addToCollections(self, context, ob, rig):
        collections = {
            "L" : ["Col1_L", "Col2_L", "Col3_L", "Col2_R", "Col3_R", "Ico_R", "Lat_L"],
            "R" : ["Col2_L", "Col3_L", "Col1_R", "Col2_R", "Col3_R", "Ico_L", "Lat_R"],
            "RiBo" : ["RiBoEmpty_L", "RiBoIco_L", "RiBoCns_L", "RiBoGoal_L",
                      "RiBoEmpty_R", "RiBoIco_R", "RiBoCns_R", "RiBoGoal_R"],
        }
        scncoll = rigcoll = context.scene.collection
        for coll in bpy.data.collections:
            if rig.name in coll.objects:
                rigcoll = coll
                break
        colls = {}
        for cname,obnames in collections.items():
            coll = bpy.data.collections.new(name=cname)
            colls[cname] = coll
            rigcoll.children.link(coll)
            layer = getLayerCollection(context, coll)
            layer.hide_viewport = True
            coll.hide_render = True
            for obname in obnames:
                ob = bpy.data.objects[obname]
                if ob.name in scncoll.objects:
                    scncoll.objects.unlink(ob)
                coll.objects.link(ob)
        return colls["RiBo"]


    def dampedTrack(self, rig, bname, goal):
        pb = rig.pose.bones[bname]
        cns = pb.constraints.new('DAMPED_TRACK')
        cns.target = goal
        cns.track_axis = 'TRACK_Y'
        cns.influence = 0.5
        return cns


    def removeSubsurf(self, ob):
        mod = getModifier(ob, 'SUBSURF')
        if mod:
            ob.modifiers.remove(mod)
            return True
        return False


    def addCorrSmooth(self, ob):
        mod = ob.modifiers.new("Corr Smooth", 'CORRECTIVE_SMOOTH')
        mod.factor = 0.5
        mod.iterations = 3
        mod.scale = 1.0
        mod.smooth_type = 'SIMPLE'
        mod.vertex_group = "Breasts"

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_MakeCollision,
    DAZ_OT_MakeCloth,
    DAZ_OT_MakeSimulation,
    DAZ_OT_AddBounce,
]

def register():
    bpy.types.Object.DazCollision = BoolProperty(default = True)
    bpy.types.Object.DazCloth = BoolProperty(default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)