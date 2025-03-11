# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import numpy as np
from ..error import *
from ..utils import *
from ..tables import getVertEdges, otherEnd

#-------------------------------------------------------------
#   Find Tube
#-------------------------------------------------------------

class DAZ_OT_ConvertTubesCurves(DazOperator, IsMesh):
    bl_idname = "daz.convert_tubes_curves"
    bl_label = "Convert Tubes To Curves"
    bl_description = "Find curves at center of tubes"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        obname = ob.name
        mats = list(ob.data.materials)
        colls = [coll for coll in bpy.data.collections if ob.name in coll.objects.keys()]
        setMode('EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        setMode('OBJECT')
        meshes = getSelectedMeshes(context)
        strands = []
        for ob in meshes:
            if activateObject(context, ob):
                strand = self.findStrand(ob)
                strands.append(strand)
                for coll in colls:
                    coll.objects.unlink(ob)
        cuob = self.buildCurves(context, strands, obname, mats, colls)
        activateObject(context, cuob)


    def findStrand(self, ob):
        self.vertedges = getVertEdges(ob)
        self.neighbors = {}
        for vn in range(len(ob.data.vertices)):
            self.neighbors[vn] = [otherEnd(vn, e) for e in self.vertedges[vn]]
        ring, perps, cyclic = self.findFirstRing(ob)
        self.showVerts(ring, ob)
        rings = self.findRings(ring, perps, ob)
        strand = self.findCenters(rings, ob)
        return strand, cyclic


    def findFirstRing(self, ob):
        def findLoop(vn, loop):
            loop.append(vn)
            for vn2 in self.neighbors[vn]:
                v2 = ob.data.vertices[vn2]
                if v2.select and vn2 not in loop:
                    findLoop(vn2, loop)

        setMode('EDIT')
        bpy.ops.mesh.select_non_manifold()
        setMode('OBJECT')
        loops = [v.index for v in ob.data.vertices if v.select]
        if loops:
            loop = []
            findLoop(loops[0], loop)
            return loop, [], False

        first = [0] + self.neighbors[0]
        self.showVerts(first, ob)
        setMode('EDIT')
        bpy.ops.mesh.loop_multi_select(ring=False)
        setMode('OBJECT')
        loops = []
        for vn in self.neighbors[0]:
            loop = [0]
            findLoop(vn, loop)
            loops.append((len(loop), loop))
        loops.sort()
        ring = loops[0][1]
        perps = [vn for vn in self.neighbors[0] if vn not in ring]
        return ring, perps, True


    def showVerts(self, vnums, ob):
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        for vn in vnums:
            ob.data.vertices[vn].select = True


    def findRings(self, ring, perps, ob):
        rings = []
        taken = []
        rest = []
        while ring:
            rings.append(ring)
            taken += ring
            neigh = [self.neighbors[vn] for vn in ring]
            ring = [vn2 for vlist in neigh
                        for vn2 in vlist
                        if vn2 not in taken]
            if len(perps) > 1:
                rest = []
                for vn in perps:
                    vnums = [vn2 for vn2 in self.neighbors[vn] if vn2 in ring]
                    vnums.append(vn)
                    self.showVerts(vnums, ob)
                    setMode('EDIT')
                    bpy.ops.mesh.loop_multi_select(ring=False)
                    setMode('OBJECT')
                    ring2 = [v.index for v in ob.data.vertices if v.select]
                    rest.append(ring2)
                ring = rest[0]
                rest = rest[1:]
            perps = []
        rings += rest
        return rings


    def findCenters(self, rings, ob):
        strand = []
        alocs = np.array([tuple(v.co) for v in ob.data.vertices], dtype = float)
        for ring in rings:
            center = np.average(alocs[ring], axis=0)
            strand.append(center)
        return strand


    def buildCurves(self, context, strands, obname, mats, colls):
        r = 1.0*GS.scale
        bpy.ops.curve.primitive_bezier_circle_add(radius=r)
        bevel = context.object
        bevel.name = "Bevel:%s" % obname

        cuname = "Center:%s" % obname
        cu = bpy.data.curves.new(cuname, 'CURVE')
        cu.dimensions = '3D'
        cu.twist_mode = 'MINIMUM'
        cu.bevel_mode = 'OBJECT'
        cu.bevel_object = bevel
        if mats:
            cumat = cu.materials.append(mats[0])
        for strand,cyclic in strands:
            npoints = len(strand)
            spline = cu.splines.new('POLY')
            spline.points.add(npoints-1)
            for co,point in zip(strand, spline.points):
                point.co[0:3] = co
            spline.use_cyclic_u = cyclic
        cuob = bpy.data.objects.new(cuname, cu)
        unlinkAll(bevel, False)
        bevel.parent = cuob
        for coll in colls:
            coll.objects.link(cuob)
            coll.objects.link(bevel)
        return cuob

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ConvertTubesCurves,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)