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

class DAZ_OT_AddBounce(DazPropsOperator, IsMesh):
    bl_idname = "daz.add_bounce"
    bl_label = "Add Breast Bounce"
    bl_description = "Add breast bounce (G8F only)"
    bl_options = {'UNDO'}

    latsize : IntProperty(
        name = "Lattice Size",
        description = "Number of lattice points in each direction",
        min = 2, max = 10,
        default = 6)

    useSoftBody : BoolProperty(
        name = "Softbody Simulation",
        description = "Add softbody simulation",
        default = True)

    useRigidBody : BoolProperty(
        name = "Rigid Body Simulation",
        description = "Add rigid body simulation",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "latsize")
        self.layout.prop(self, "useSoftBody")
        self.layout.prop(self, "useRigidBody")

    def run(self, context):
        from .load_json import loadJson
        hum = context.object
        rig = hum.parent
        if hum.DazMesh != "Genesis8-female":
            raise DazError("Only G8F")
        folder = os.path.join(os.path.dirname(__file__), "data", "breasts")
        path = os.path.join(folder, "%s.json" % hum.DazMesh.lower())
        struct = loadJson(path)
        path = os.path.join(folder, "%s.json" % rig.DazRig.lower())
        bstruct = loadJson(path)
        bones = bstruct["bones"]
        lPect = bones["lPectoral"]
        rPect = bones["rPectoral"]
        subsurf = self.removeSubsurf(hum)
        self.objects = []
        if self.useSoftBody:
            self.addVertexGroups(hum, struct)
            self.addCollisionObjects(context, hum, rig, bones)
            #self.applyTransforms()
            scale = self.readScale(hum, struct)
            llat = self.addLattice(context, hum, rig, "Lat_L", lPect, scale)
            rlat = self.addLattice(context, hum, rig, "Lat_R", rPect, scale)
        verts = struct["vertices"]
        if self.useRigidBody:
            lico1,lico2,lempty,lgoal = self.addHelpers(context, hum, rig, verts["lNipple"], verts["lTop"], lPect, "L")
            rico1,rico2,rempty,rgoal = self.addHelpers(context, hum, rig, verts["rNipple"], verts["rTop"], rPect, "R")
        colls = self.addToCollections(context, rig)
        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='POSE')
        if self.useRigidBody:
            self.dampedTrack(rig, lPect, lico2)
            self.dampedTrack(rig, rPect, rico2)
        self.addCorrSmooth(hum)
        if subsurf:
            hum.modifiers.new("Subsurf", 'SUBSURF')
        if self.useRigidBody:
            world = self.addRigidBodyWorld(context)
            self.addRigidBodyConstraint(context, world, lico1, lico2, lempty, lgoal)
            self.addRigidBodyConstraint(context, world, rico1, rico2, rempty, rgoal)
        if self.useSoftBody:
            self.addSoftBody(llat, colls["Col_L"])
            self.addSoftBody(rlat, colls["Col_R"])


    def addVertexGroups(self, hum, struct):
        from .finger import getFingerPrint
        finger = getFingerPrint(hum)
        if GS.useModifiedMesh:
            from .geometry import restoreOrigVerts
            hasOrig, restored = restoreOrigVerts(hum, -1)
            if hasOrig:
                finger = hum.data.DazFingerPrint
        if finger != struct["finger_print"]:
            msg = ("Fingerprint mismatch:\n  %s != %s\n" % (finger, struct["finger_print"]) +
                   '"%s" is not a mesh of type %s\n' % (hum.name, struct["name"]))
            raise DazError(msg)

        for vname,verts in struct["vertex_groups"].items():
            vgrp = hum.vertex_groups.get(vname)
            if vgrp:
                hum.vertex_groups.remove(vgrp)
            vgrp = hum.vertex_groups.new(name=vname)
            if isModifiedMesh(hum):
                pgs = hum.data.DazOrigVerts
                for vn0,w in verts:
                    vn = pgs[str(vn0)].a
                    if vn >= 0:
                        vgrp.add([vn], w, 'REPLACE')
            else:
                for vn,w in verts:
                    vgrp.add([vn], w, 'REPLACE')


    def addCollisionObjects(self, context, hum, rig, bones):
        collisionObjects = {
            "Col1_L" : ["lShldrBend", "Cylinder", "lShldrBend", "lShldrTwist", 0.15],
            "Col2_L" : ["lForearmBend", "Cylinder", "lForearmBend", "lForearmTwist", 0.15],
            "Col3_L" : ["lHand", "Cylinder", "lHand", "lHand", 0.45],
            "Col1_R" : ["rShldrBend", "Cylinder", "rShldrBend", "rShldrTwist", 0.15],
            "Col2_R" : ["rForearmBend", "Cylinder", "rForearmBend", "rForearmTwist", 0.15],
            "Col3_R" : ["rHand", "Cylinder", "rHand", "rHand", 0.45],
            "Ico_L" : ["lPectoral", "Icosphere", "lPectoral", "lPectoral", 0.3],
            "Ico_R" : ["rPectoral", "Icosphere", "rPectoral", "rPectoral", 0.3],
        }
        RX = Matrix.Rotation(90*D, 4, 'X')
        for cname,data in collisionObjects.items():
            bname, mtype, bname1, bname2, rad = data
            pb1 = rig.pose.bones[bones[bname1]]
            pb2 = rig.pose.bones[bones[bname2]]
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
            lmat = trans @ rot
            col = context.object
            unlinkAll(col)
            self.parentBone(col, cname, rig, bones[bname], hum, lmat)
            mod = col.modifiers.new("Collision", 'COLLISION')
            col.collision.thickness_outer = 0.1*hum.DazScale
            col.collision.thickness_inner = innerThick*hum.DazScale


    def addHelpers(self, context, hum, rig, vnip, vtop, bname, suffix):
        if isModifiedMesh(hum):
            vnum = hum.data.DazOrigVerts[str(vnum)].a
        nip = hum.data.vertices[vnip].co
        top = hum.data.vertices[vtop].co
        bone = rig.data.bones[bname]
        x = 0.0
        loc = (1-x)*bone.head_local + x*bone.tail_local

        bpy.ops.object.empty_add()
        empty1 = context.object
        empty1.empty_display_size = 0.1
        lmat = Matrix.Translation(loc).to_4x4()
        self.parentBone(empty1, "RiBoEmpty_%s" % suffix, rig, bone.parent.name, hum, lmat)

        bpy.ops.mesh.primitive_ico_sphere_add(radius=2*hum.DazScale)
        ico1 = context.object
        loc[2] = top[2]
        lmat = Matrix.Translation(loc).to_4x4()
        self.parentBone(ico1, "RiBoIco1_%s" % suffix, empty1, None, hum, lmat)

        bpy.ops.object.empty_add()
        empty2 = context.object
        empty2.empty_display_size = 0.1
        self.parentBone(empty2, "RiBoCns_%s" % suffix, ico1, None, hum, lmat)

        bpy.ops.mesh.primitive_ico_sphere_add(radius=4*hum.DazScale)
        ico2 = context.object
        lmat = Matrix.Translation(nip).to_4x4()
        self.parentBone(ico2, "RiBoIco2_%s" % suffix, None, None, hum, lmat)

        bpy.ops.object.empty_add()
        goal = context.object
        goal.empty_display_size = 0.1
        self.parentBone(goal, "RiBoGoal_%s" % suffix, rig, bone.parent.name, hum, lmat)

        return ico1, ico2, empty2, goal


    def addRigidBodyWorld(self, context):
        scn = context.scene
        if scn.rigidbody_world is None:
            bpy.ops.rigidbody.world_add()
        world = scn.rigidbody_world
        if world.collection is None:
            rbcoll = bpy.data.collections.new(name="RigidBodyCollection")
            world.collection = rbcoll
        return world


    def addRigidBodyConstraint(self, context, world, ico1, ico2, empty, goal):
        world.collection.objects.link(ico1)
        world.collection.objects.link(ico2)
        ico1.rigid_body.type = 'PASSIVE'
        ico2.rigid_body.type = 'ACTIVE'
        activateObject(context, empty)
        bpy.ops.rigidbody.constraint_add()
        rbc = empty.rigid_body_constraint
        rbc.type = 'GENERIC_SPRING'
        rbc.enabled = True
        rbc.disable_collisions = True
        rbc.object1 = ico1
        rbc.object2 = ico2
        for x,stiff,damp in [("x", 80, 1), ("y", 100, 5), ("z", 80, 1)]:
            setattr(rbc, "use_spring_ang_%s" % x, True)
            setattr(rbc, "spring_stiffness_ang_%s" % x, stiff)
            setattr(rbc, "spring_damping_ang_%s" % x, damp)
        for x,stiff,damp in [("x", 1000, 100), ("y", 1000, 100), ("z", 1000, 100)]:
            setattr(rbc, "use_spring_%s" % x, True)
            setattr(rbc, "spring_stiffness_%s" % x, stiff)
            setattr(rbc, "spring_damping_%s" % x, damp)


    def readScale(self, hum, struct):
        def getCo(name, idx):
            return hum.data.vertices[struct["vertices"][name]].co[idx]

        xmin = getCo("xmin", 0)
        xmax = getCo("xmax", 0)
        ymin = getCo("ymin", 1)
        ymax = getCo("ymax", 1)
        zmin = getCo("zmin", 2)
        zmax = getCo("zmax", 2)
        scale = Vector((abs(xmax-xmin), abs(ymax-ymin), abs(zmax-zmin)))
        print("SCAL", scale)
        return scale


    def addLattice(self, context, hum, rig, lname, bname, scale):
        pb = rig.pose.bones[bname]
        head = pb.bone.head_local
        tail = pb.bone.tail_local
        rot = pb.matrix.to_3x3().to_4x4()
        trans = Matrix.Translation(1.0*tail + 0.0*head)
        smat = Matrix.Diagonal(scale).to_4x4()
        lmat = trans @ rot @ smat
        bpy.ops.object.add(type='LATTICE')
        lat = context.object
        unlinkAll(lat)
        (lat.data.points_u, lat.data.points_v, lat.data.points_w) = 3*[self.latsize]
        self.parentBone(lat, lname, rig, bname, hum, lmat)
        # Vertex group
        vgrp = lat.vertex_groups.new(name="Pin")
        x0s = Vector((0,0,0))
        ks = Vector((1,1,1))
        dxs = Vector((0,0,0))
        for n in range(3):
            coords = [v.co[n] for v in lat.data.points]
            xmin = min(coords)
            xmax = max(coords)
            x0s[n] = xmin
            ks[n] = 1/(xmax-xmin)
        for vn,v in enumerate(lat.data.points):
            for n in range(3):
                dx = ks[n]*(v.co[n] - x0s[n])
                dxs[n] = dx
            x,y,z = dxs
            # x, 1-y, 1-z
            w = 3*(1-y)*(0.25 + abs(x-0.5))
            w = max(0, min(1, w))
            vgrp.add([vn], w, 'REPLACE')

        mod = hum.modifiers.new(lat.name, 'LATTICE')
        mod.object = lat
        mod.vertex_group = "%s_copy" % bname
        mod.strength = 1.0
        return lat


    def addSoftBody(self, lat, coll):
        mod = lat.modifiers.new("Softbody", 'SOFT_BODY')
        mset = mod.settings
        mset.collision_collection = coll
        mset.friction = 0.5
        mset.mass = 1.0

        mset.use_goal = True
        mset.vertex_group_goal = "Pin"
        mset.goal_spring = 0.8
        mset.goal_friction = 10
        mset.goal_default = 1.0
        mset.goal_min = 0.6
        mset.goal_max = 1.0

        mset.use_edges = True
        mset.pull = 0.2
        mset.push = 0.2
        mset.damping = 40
        mset.bend = 2.0
        mset.use_edge_collision = True
        mset.use_face_collision = True

        mset.use_stiff_quads = True
        mset.shear = 0.1
        mset.use_self_collision = True
        mset.ball_size = 0.7
        mset.ball_stiff = 10.0
        mset.ball_damp = 0.5
        mset.choke = 0
        mset.fuzzy = 50

        effwts = mset.effector_weights
        effwts.collection = coll
        if self.useRigidBody:
            effwts.gravity = 0.0


    def parentBone(self, ob, cname, rig, bname, hum, lmat):
        ob.name = cname
        ob.parent = rig
        if bname:
            ob.parent_type = 'BONE'
            ob.parent_bone = bname
        setWorldMatrix(ob, hum.matrix_world @ lmat)
        #ob.select_set(True)
        #bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        self.objects.append(ob)


    def applyTransforms(self):
        bpy.ops.object.select_all(action='DESELECT')
        for ob in self.objects:
            ob.select_set(True)
        bpy.ops.object.transform_apply()


    def addToCollections(self, context, rig):
        collections = {}
        if self.useSoftBody:
            collections["Col_L"] = ["Col1_L", "Col2_L", "Col3_L", "Col2_R", "Col3_R", "Ico_R", "Lat_L"]
            collections["Col_R"] = ["Col2_L", "Col3_L", "Col1_R", "Col2_R", "Col3_R", "Ico_L", "Lat_R"]
        if self.useRigidBody:
            collections["RiBo"] = [
                "RiBoEmpty_L", "RiBoIco1_L", "RiBoCns_L", "RiBoIco2_L", "RiBoGoal_L",
                "RiBoEmpty_R", "RiBoIco1_R", "RiBoCns_R", "RiBoIco2_R", "RiBoGoal_R"]
        scn = context.scene
        scncoll = rigcoll = scn.collection
        for coll in bpy.data.collections:
            if rig.name in coll.objects:
                rigcoll = coll
                break
        dyncoll = bpy.data.collections.new(name="Dynamics")
        scncoll.children.link(dyncoll)
        layer = getLayerCollection(context, dyncoll)
        layer.hide_viewport = True
        dyncoll.hide_render = True
        #rigcoll.children.link(dyncoll)

        colls = {}
        for cname,obnames in collections.items():
            coll = bpy.data.collections.new(name=cname)
            colls[cname] = coll
            coll.hide_render = True
            dyncoll.children.link(coll)
            for obname in obnames:
                ob = bpy.data.objects[obname]
                if ob.name in scncoll.objects:
                    scncoll.objects.unlink(ob)
                coll.objects.link(ob)
        return colls


    def dampedTrack(self, rig, bname, goal):
        pb = rig.pose.bones[bname]
        cns = pb.constraints.new('DAMPED_TRACK')
        cns.target = goal
        cns.track_axis = 'TRACK_Y'
        cns.influence = 0.5
        return cns


    def removeSubsurf(self, hum):
        mod = getModifier(hum, 'SUBSURF')
        if mod:
            hum.modifiers.remove(mod)
            return True
        return False


    def addCorrSmooth(self, hum):
        mod = hum.modifiers.new("Corr Smooth", 'CORRECTIVE_SMOOTH')
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