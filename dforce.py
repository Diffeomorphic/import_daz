# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
            reportError("Bug DynSim %s" % self.instance)
            return
        ob = geonode.rna
        if ob and ob.type == 'MESH':
            ob["DazCloth"] = True
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
                reportError(msg)
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
#   Collision
#-------------------------------------------------------------

class Collision:
    def drawCollision(self, context, layout):
        pass

    def addCollision(self, ob):
        from .store import removeModifier
        mod = getModifier(ob, 'COLLISION')
        if mod:
            return
        subsurf = removeModifier(ob, 'SUBSURF')
        mod = ob.modifiers.new("Collision", 'COLLISION')
        cset = ob.collision
        cset.damping = 1.0
        cset.thickness_outer = 0.1*GS.scale
        cset.thickness_inner = 1.0*GS.scale
        cset.cloth_friction = 0.0
        cset.use_culling = True
        if subsurf:
            subsurf.restore(ob)

#-------------------------------------------------------------
#   Cloth
#-------------------------------------------------------------

def getCollections(scn, context):
    colls = [(coll.name, coll.name, coll.name) for coll in bpy.data.collections]
    return [('NEW', "New", "Make new collision collection"),
            ('NONE', "None", "Don't use collision")] + colls


class Cloth:
    fixedPin = False

    pinGroup : StringProperty(
        name = "Pin Group",
        description = "Use this group as pin group",
        default = "dForce Pin")

    collision : EnumProperty(
        items = getCollections,
        name = "Collision Collection")

    def drawCloth(self, context, layout):
        if not self.fixedPin:
            layout.prop(self, "pinGroup")
        layout.prop(self, "collision")

    def addCollision(self, ob):
        pass

    def addClothCollection(self, context, ob):
        if self.collision == 'NONE':
            self.collection = None
        elif self.collision == 'NEW':
            self.collection = bpy.data.collections.get("Cloth Collision")
            if self.collection:
                return
            self.collection = bpy.data.collections.new("Cloth Collision")
            rig = ob.parent
            rigcoll = getCollection(context, rig)
            rigcoll.children.link(self.collection)
            for child in getMeshChildren(rig):
                if (child.get("DazCollision", False) and
                    not child.get("DazCloth", False)):
                    self.collection.objects.link(child)
        else:
            self.collection = bpy.data.collections.get(self.collision)
            for ob in self.collection.objects:
                self.addCollision(ob)


    def addCloth(self, ob):
        from .store import removeModifier
        collision = removeModifier(ob, 'COLLISION')
        subsurf = removeModifier(ob, 'SUBSURF')

        cloth = getModifier(ob, 'CLOTH')
        if cloth is None:
            cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        # Collision settings
        colset = cloth.collision_settings
        colset.collection = self.collection
        colset.distance_min = 0.1*GS.scale
        colset.self_distance_min = 0.1*GS.scale
        colset.collision_quality = 4
        colset.use_self_collision = False
        # Pinning
        cset.vertex_group_mass = self.pinGroup
        cset.pin_stiffness = 1.0

        if subsurf:
            subsurf.restore(ob)
        if collision:
            collision.restore(ob)

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

