# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..pin import Pinner
from ..dforce import Cloth, Collision

#-------------------------------------------------------------
#   HairBuilder class
#-------------------------------------------------------------

class HairBuilder(Pinner, Collision, Cloth):

    hairPoseSim : EnumProperty(
        items = [('NONE', "None", "Neither posing nor simulation"),
                 ('POSING', "Posing", "Posing"),
                 ('SIMULATION', "Simulation", "Simulation")],
        name = "Hair Posing/Simulation",
        description = "Add a hair proxy mesh for posing or simulation",
        default = 'NONE')

    useVertexGroups : BoolProperty(
        name = "Copy Vertex Groups",
        description = "Copy vertex groups to proxy mesh",
        default = False)

    proxyType : EnumProperty(
        items = [('LINE', "Line", "Line proxy mesh"),
                 ('SHEET', "Sheet", "Sheet proxy mesh"),
                 ('TUBE', "Tube", "Tubular proxy mesh")],
        name = "Proxy Mesh",
        description = "Proxy mesh type",
        default = 'SHEET')

    proxyWidth : FloatProperty(
        name = "Proxy width (mm)",
        description = "Width of the proxy strands",
        min = 0.001,
        max = 10,
        precision = 3,
        default = 1.0)

    usePinGroup : BoolProperty(
        name = "Pinning Group",
        description = "Add a pinning group to the hair proxy",
        default = True)

    useClothSimulation : BoolProperty(
        name = "Cloth Simulation",
        description = "Add a cloth simulation",
        default = True)

    def drawPoseSim(self, context, layout):
        layout.prop(self, "hairPoseSim")
        if self.hairPoseSim == 'POSING':
            layout.prop(self, "proxyType")
            layout.prop(self, "useVertexGroups")
        elif self.hairPoseSim == 'SIMULATION':
            layout.prop(self, "proxyType")
            layout.prop(self, "proxyWidth")
            layout.prop(self, "usePinGroup")
            if self.usePinGroup:
                self.drawMapping(context, layout)
                layout.separator()
            layout.prop(self, "useClothSimulation")
            if self.useClothSimulation:
                self.drawCloth(context, layout)
                self.drawCollision(context, layout)


    def buildMesh(self, context, hname, strands, hair, hum, mnames):
        def getVectors(coords):
            if len(coords) == 1:
                return Vector((1,0,0)), Vector((0,1,0))
            tang = coords[-1] - coords[0]
            norm = tang.cross(Vector((0,0,1)))
            return tang.normalized(), norm.normalized()

        nverts = 0
        verts = []
        edges = []
        faces = []
        for strand in strands:
            verts += strand
        nverts = len(verts)
        dr = self.proxyWidth * 0.1 * GS.scale
        if self.hairPoseSim == 'NONE':
            return
        elif self.hairPoseSim == 'POSING' and self.proxyType == 'LINE':
            m = 0
            for strand in strands:
                nsverts = len(strand)
                edges += [(m+n, m+n+1) for n in range(nsverts-1)]
                m += nsverts
        elif self.proxyType in ['SHEET', 'LINE']:
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*norm
                    verts.append(tuple(v))
            m1 = -1
            for strand in strands:
                if not strand:
                    continue
                m1 += 1
                m2 = m1+nverts
                for s in strand[1:]:
                    faces.append((m1, m1+1, m2+1, m2))
                    m1 += 1
                    m2 += 1
        elif self.proxyType == 'TUBE':
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*norm
                    verts.append(tuple(v))
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*tang.cross(norm)
                    verts.append(tuple(v))
            m1 = -1
            for strand in strands:
                if not strand:
                    continue
                m1 += 1
                m2 = m1+nverts
                m3 = m1+2*nverts
                faces.append((m1, m2, m3))
                for s in strand[1:]:
                    faces.append((m1, m1+1, m2+1, m2))
                    faces.append((m2, m2+1, m3+1, m3))
                    faces.append((m3, m3+1, m1+1, m1))
                    m1 += 1
                    m2 += 1
                    m3 += 1
                faces.append((m1, m3, m2))

        me = bpy.data.meshes.new(hname)
        me.from_pydata(verts, edges, faces)
        #me.DazHairType = self.proxyType
        ob = self.buildObject(hname, me, hair, hum, mnames)

        def addWeights(vgrp, strands, m):
            for strand in strands:
                nsverts = len(strand)
                for n in range(nsverts):
                    vgrp.add([m+n], n/(nsverts-1), 'REPLACE')
                m += nsverts

        vgrp = ob.vertex_groups.new(name="Root Distance")
        addWeights(vgrp, strands, 0)
        if self.proxyType == 'SHEET':
            addWeights(vgrp, strands, nverts)
            if self.proxyType == 'TUBE':
                addWeights(vgrp, strands, 2*nverts)
        return ob


    def buildHairProxy(self, context, hname, strands, hair, hum):
        mat = bpy.data.materials.get("Hair Proxy")
        if mat is None:
            mat = bpy.data.materials.new("Hair Proxy")
            mat.diffuse_color[0:3] = (1,0,0)
        proxy = self.buildMesh(context, hname, strands, hair, hum, [mat.name])
        proxy.hide_render = True
        if self.hairPoseSim == 'SIMULATION' and self.usePinGroup:
            self.addHairPinning(proxy)
            if self.useClothSimulation:
                self.collision = 'NONE'
                self.addCloth(context, proxy)
        return proxy


    def buildCurves(self, context, hname, strands, hair, hum, mnames):
        cu = bpy.data.curves.new(hname, 'CURVE')
        cu.dimensions = '3D'
        cu.twist_mode = 'TANGENT'
        for strand in strands:
            npoints = len(strand)
            spline = cu.splines.new('POLY')
            spline.points.add(npoints-1)
            for co,point in zip(strand, spline.points):
                point.co[0:3] = co
        return self.buildObject(hname, cu, hair, hum, mnames)


    def buildHairCurves(self, context, hname, strands, hair, hum, mnames):
        from ..geometry import getActiveUvLayer
        curves = bpy.data.hair_curves.new(self.name)
        sizes = [len(strand) for strand in strands]
        curves.add_curves(sizes)
        for strand,curve in zip(strands, curves.curves):
            for pos,point in zip(strand, curve.points):
                point.position = pos
        curves.surface = hum
        uvlayer = getActiveUvLayer(hum)
        if uvlayer:
            curves.surface_uv_map = uvlayer.name
        return self.buildObject(hname, curves, hair, hum, mnames)


    def buildObject(self, hname, data, hair, hum, mnames):
        ob = bpy.data.objects.new(hname, data)
        wmat = ob.matrix_world.copy()
        ob.parent = hum
        ob.parent_bone = hair.parent_bone
        ob.parent_type = hair.parent_type
        setWorldMatrix(ob, wmat)
        for mname in mnames:
            mat = bpy.data.materials.get(mname)
            data.materials.append(mat)
        return ob


    def linkHair(self, ob, hum, coll):
        coll.objects.link(ob)
        rig = hum.parent
        if rig and rig.type == 'ARMATURE':
            head = rig.data.bones.get("head")
            wmat = ob.matrix_world.copy()
            ob.parent = rig
            if head:
                ob.parent_type = 'BONE'
                ob.parent_bone = head.name
            setWorldMatrix(ob, wmat)


    def addFollowProxy(self, hair, proxy):
        from ..geonodes import FollowProxyGroup
        from ..tree import addNodeGroup
        from ..store import ModStore
        stores = []
        for mod in list(hair.modifiers):
            if not (mod.type == 'NODES' and
                    mod.node_group and
                    mod.node_group.name == "DAZ Follow Proxy"):
                stores.append(ModStore(mod))
            hair.modifiers.remove(mod)
        mod = hair.modifiers.new("Follow %s" % proxy.name, 'NODES')
        mod.node_group = addNodeGroup(FollowProxyGroup, "DAZ Follow Proxy")
        mod["Socket_1"] = proxy
        for store in stores:
            store.restore(hair)

#-------------------------------------------------------------
#   Make Hair Proxy
#-------------------------------------------------------------

class DAZ_OT_MakeHairProxy(DazPropsOperator, HairBuilder, IsCurves):
    bl_idname = "daz.make_hair_proxy"
    bl_label = "Make Hair Proxy"
    bl_description = "Make proxy for hair curves and add cloth simulation to it"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawPoseSim(context, self.layout)

    def invoke(self, context, event):
        self.invokePinner()
        self.hairPoseSim = 'SIMULATION'
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        hair = context.object
        hum = hair.parent
        hname = baseName(hair.name).lstrip("Hair ")
        strands = []
        for cu in hair.data.curves:
            strand = [tuple(point.position) for point in cu.points]
            strands.append(strand)
        proxy = self.buildHairProxy(context, hname, strands, hair, hum)
        proxy.name = "Proxy %s" % baseName(hair.name)
        self.linkHair(proxy, hum, context.collection)
        self.addFollowProxy(hair, proxy)

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_MakeHairProxy,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
