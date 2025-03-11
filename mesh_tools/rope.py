# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import numpy as np
from ..error import *
from ..utils import *

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
        rings = self.findRings(ob)
        print("RYY", rings)
        strand = self.findCenters(rings, ob)
        strands = [strand]
        self.buildCurves(context, strands, ob)


    def findRings(self, ob):
        from ..tables import getVertEdges, otherEnd
        vertedges = getVertEdges(ob)
        ring = [v.index for v in ob.data.vertices if v.select]
        rings = []
        taken = []
        while ring:
            print("RR", ring)
            rings.append(ring)
            taken += ring
            redges = [(vn, vertedges[vn]) for vn in ring]
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