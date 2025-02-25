# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from .error import *
from .utils import *

#----------------------------------------------------------
#   Framer class
#----------------------------------------------------------

class Framer(DazPropsOperator):
    frame_start : IntProperty(
        name = "Start",
        default = 1)

    frame_end : IntProperty(
        name = "End",
        default = 1)

    def draw(self, context):
        self.layout.prop(self, "frame_start")
        self.layout.prop(self, "frame_end")


    def setActiveRange(self, context, rig):
        adata = rig.animation_data
        if adata and adata.action:
            tmin = tmax = 1
            fcurves = getActionSlot(adata.action).fcurves
            for fcu in fcurves:
                times = [kp.co[0] for kp in fcu.keyframe_points]
                tmin = min(int(min(times)), tmin)
                tmax = max(int(max(times)), tmax)
            self.frame_start = tmin
            self.frame_end = tmax
        else:
            self.frame_start = self.frame_end = context.scene.frame_current


    def invoke(self, context, event):
        rig = getRigFromContext(context)
        rig = self.getControlRig(rig)
        self.setActiveRange(context, rig)
        return DazPropsOperator.invoke(self, context, event)


    def getControlRig(rig):
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'COPY_TRANSFORMS':
                    return cns.target
        return rig

