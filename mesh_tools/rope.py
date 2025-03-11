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

class DAZ_OT_FindTube(DazOperator, IsMesh):
    bl_idname = "daz.find_tube"
    bl_label = "Find Tube"
    bl_description = "Find curve at center of tube"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        self.vertedges = getVertEdges(ob)
        self.neighbors = {}
        for vn in range(len(ob.data.vertices)):
            self.neighbors[vn] = [otherEnd(vn, e) for e in self.vertedges[vn]]
        ring = self.findFirstRing(ob)
        print("FR", ring)
        self.showVerts(ring, ob)
        return
        rings = self.findRings(ring, ob)
        print("RYY", rings)
        strand = self.findCenters(rings, ob)
        strands = [strand]
        self.buildCurves(context, strands, ob)


    def findFirstRing(self, ob):
        def findRing(vn, ring):
            ring.append(vn)
            for vn2 in self.neighbors[vn]:
                v2 = ob.data.vertices[vn2]
                if v2.select and vn2 not in ring:
                    findRing(vn2, ring)

        first = [0] + self.neighbors[0]
        self.showVerts(first, ob)
        setMode('EDIT')
        bpy.ops.mesh.loop_multi_select(ring=False)
        setMode('OBJECT')
        rings = []
        for vn in self.neighbors[0]:
            ring = [0]
            findRing(vn, ring)
            rings.append((len(ring), ring))
        rings.sort()
        return rings[0][1]


    def showVerts(self, vnums, ob):
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        for vn in vnums:
            ob.data.vertices[vn].select = True

    def findRings(self, ring, ob):
        rings = []
        taken = []
        while ring:
            print("RR", ring)
            rings.append(ring)
            taken += ring
            redges = [(vn, self.vertedges[vn]) for vn in ring]
            ring = []
            for vn,vedges in redges:
                for e in vedges:
                    vn2 = otherEnd(vn, e)
                    if vn2 not in taken:
                        ring.append(vn2)
        return rings


    def findCenters(self, rings, ob):
        strand = []
        alocs = np.array([tuple(v.co) for v in ob.data.vertices], dtype = float)
        for ring in rings:
            center = np.average(alocs[ring], axis=0)
            strand.append(center)
        return strand


    def buildCurves(self, context, strands, ob):
        r = 1.0*GS.scale
        bpy.ops.curve.primitive_bezier_circle_add(radius=r)
        bevel = context.object

        cuname = "Center:%s" % ob.name
        cu = bpy.data.curves.new(cuname, 'CURVE')
        cu.dimensions = '3D'
        cu.twist_mode = 'MINIMUM'
        cu.bevel_mode = 'OBJECT'
        cu.bevel_object = bevel
        for strand in strands:
            npoints = len(strand)
            spline = cu.splines.new('POLY')
            spline.points.add(npoints-1)
            for co,point in zip(strand, spline.points):
                point.co[0:3] = co
        cuob = bpy.data.objects.new(cuname, cu)
        context.collection.objects.link(cuob)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_FindTube,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)