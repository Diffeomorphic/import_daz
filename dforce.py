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

    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False

    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify

    def run(self, context):
        from .load_json import loadJson
        hum = self.human = context.object
        self.rig = hum.parent
        if hum.DazMesh != "Genesis8-female":
            raise DazError("Only G8F")
        folder = os.path.join(os.path.dirname(__file__), "data", "breasts")
        path = os.path.join(folder, "%s.json" % hum.DazMesh.lower())
        struct = loadJson(path)
        path = os.path.join(folder, "%s.json" % self.rig.DazRig.lower())
        bstruct = loadJson(path)
        self.bones = bstruct["bones"]
        self.corners = self.readCorners(hum, struct["vertices"])
        subsurf = self.removeSubsurf(hum)
        self.addVertexGroups(hum, struct)
        coll = self.addCollection(context)

        collisionObjects = {
            "Col1_L" : ["lShldrBend", "lShldrBend", "lShldrTwist", 0.15],
            "Col2_L" : ["lForearmBend", "lForearmBend", "lForearmTwist", 0.15],
            "Col3_L" : ["lHand", "lHand", "lHand", 0.45],
            "Col1_R" : ["rShldrBend", "rShldrBend", "rShldrTwist", 0.15],
            "Col2_R" : ["rForearmBend", "rForearmBend", "rForearmTwist", 0.15],
            "Col3_R" : ["rHand", "rHand", "rHand", 0.45],
        }
        col = self.addObject("COLLISION", collisionObjects, "Cube", context)
        coll.objects.link(col)
        self.addArmature(col)
        self.addCollision(col)

        softbodyObjects = {
            "Breast_L" : ["lPectoral", "lPectoral", "lPectoral", 0.3],
            "Breast_R" : ["rPectoral", "rPectoral", "rPectoral", 0.3],
        }
        softbody = self.addObject("SOFTBODY", softbodyObjects, "Icosphere", context)
        coll.objects.link(softbody)
        self.addArmature(softbody)
        self.addSoftBody(softbody)
        self.addCorrSmooth(softbody, "", 2)

        activateObject(context, hum)
        self.addSurfaceDeform(hum, softbody)
        self.addCorrSmooth(hum, "CHEST", 4)
        if False and subsurf:
            hum.modifiers.new("Subsurf", 'SUBSURF')
        activateObject(context, self.rig)
        bpy.ops.object.mode_set(mode='POSE')


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


    def addCollection(self, context):
        coll = bpy.data.collections.new("Simulation")
        rigcoll = getCollection(self.rig)
        rigcoll.children.link(coll)
        layer = getLayerCollection(context, coll)
        layer.hide_viewport = True
        coll.hide_render = True
        return coll


    def addObject(self, name, objects, mtype, context):
        objs = []
        for cname,data in objects.items():
            ob = self.addSubObject(cname, data, mtype, context)
            objs.append(ob)
        for ob in objs:
            ob.select_set(True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.ops.object.transform_apply()
        bpy.ops.object.join()
        ob.name = name
        ob.DazScale = self.human.DazScale
        ob.parent_type = 'OBJECT'
        ob.parent = self.rig
        unlinkAll(ob)
        return ob


    def addSubObject(self, cname, data, mtype, context):
        RX = Matrix.Rotation(90*D, 4, 'X')
        bname, bname1, bname2, rad = data
        pb1 = self.rig.pose.bones[self.bones[bname1]]
        pb2 = self.rig.pose.bones[self.bones[bname2]]
        head = pb1.bone.head_local
        tail = pb2.bone.tail_local
        length = (tail - head).length
        rot = pb1.matrix.to_3x3().to_4x4()
        if mtype == "Cube":
            rot = rot @ RX
            trans = Matrix.Translation((head+tail)/2)
            scale = Vector((rad,rad,0.5))*length
            bpy.ops.mesh.primitive_cube_add(size=2, scale=scale)
            lmat = trans @ rot
            ob = context.object
            self.parentBone(ob, cname, self.bones[bname], lmat)
        elif mtype == "Icosphere":
            bpy.ops.mesh.primitive_cube_add(size=2)
            ob = context.object
            verts = ob.data.vertices
            sign = (+1 if bname1 == "lPectoral" else -1)
            xmin,xmax,ymin,ymax,zmin,zmax = self.corners
            verts[0].co = (sign*xmin,ymin,zmin)
            verts[1].co = (sign*xmin,ymin,zmax)
            verts[2].co = (sign*xmin,ymax,zmin)
            verts[3].co = (sign*xmin,ymax,zmax)
            verts[4].co = (sign*xmax,ymin,zmin)
            verts[5].co = (sign*xmax,ymin,zmax)
            verts[6].co = (sign*xmax,ymax,zmin)
            verts[7].co = (sign*xmax,ymax,zmax)
            vgrp = ob.vertex_groups.new(name="Pin")
            for vn in [0,1,4,5]:
                vgrp.add([vn], 1.0, 'REPLACE')
            mod = ob.modifiers.new("Subsurf", 'SUBSURF')
            mod.levels = 1
            bpy.ops.object.modifier_apply(modifier="Subsurf")

        vgrp = ob.vertex_groups.new(name=bname1)
        for vn in range(len(ob.data.vertices)):
            vgrp.add([vn], 1.0, 'REPLACE')
        return ob


    def parentBone(self, ob, cname, bname, lmat):
        ob.name = cname
        ob.parent = self.rig
        if bname:
            ob.parent_type = 'BONE'
            ob.parent_bone = bname
        setWorldMatrix(ob, self.human.matrix_world @ lmat)


    def readCorners(self, hum, struct):
        def getCo(name, idx):
            return hum.data.vertices[struct[name]].co[idx]

        xmin = getCo("xmin", 0)
        xmax = getCo("xmax", 0)
        ymin = getCo("ymin", 1)
        ymax = getCo("ymax", 1)
        zmin = getCo("zmin", 2)
        zmax = getCo("zmax", 2)
        return (xmin,xmax,ymin,ymax,zmin,zmax)


    def addArmature(self, ob):
        mod = ob.modifiers.new("Armature", 'ARMATURE')
        mod.object = self.rig


    def addCollision(self, ob):
        mod = ob.modifiers.new("Collision", 'COLLISION')
        cset = ob.collision
        cset.damping = 1.0
        cset.thickness_outer = 0.1*ob.DazScale
        cset.thickness_inner = 0.1*ob.DazScale
        cset.use_culling = True


    def addSoftBody(self, ob, coll=None):
        mod = ob.modifiers.new("Softbody", 'SOFT_BODY')
        mset = mod.settings
        mset.collision_collection = coll
        mset.friction = 0.5
        mset.mass = 3.0

        mset.use_goal = True
        mset.vertex_group_goal = "Pin"
        mset.goal_spring = 1.0
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


    def removeSubsurf(self, hum):
        mod = getModifier(hum, 'SUBSURF')
        if mod:
            hum.modifiers.remove(mod)
            return True
        return False


    def addCorrSmooth(self, hum, vgrp, iters):
        mod = hum.modifiers.new("Corr Smooth", 'CORRECTIVE_SMOOTH')
        mod.factor = 0.5
        mod.iterations = iters
        mod.scale = 1.0
        mod.smooth_type = 'SIMPLE'
        mod.vertex_group = vgrp


    def addSurfaceDeform(self, hum, softbody):
        mod = hum.modifiers.new("Surface Deform", 'SURFACE_DEFORM')
        mod.target = softbody
        mod.falloff = 4.0
        mod.strength = 1.0
        mod.vertex_group = 'SOFTBODY'
        mod.use_sparse_bind = True
        bpy.ops.object.surfacedeform_bind(modifier="Surface Deform")

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