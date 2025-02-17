# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from ..error import *
from ..utils import *

#-------------------------------------------------------------
#   Convert morphs to action
#-------------------------------------------------------------

class DAZ_OT_MorphsToAction(DazOperator, IsArmature):
    bl_idname = "daz.morphs_to_action"
    bl_label = "Morphs To Action"
    bl_description = "Convert Morphs To Action"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        scn = context.scene
        props = [prop for prop in rig.keys()
                 if not prop.startswith(("daz", "Daz", "_"))]
        for prop in props:
            clearProp(rig, prop)
        for prop in props:
            print("PP", prop)
            setProp(rig, prop)
            updateRigDrivers(context, rig)
            act = bpy.data.actions.get(prop)
            if act:
                act.fcurves.clear()
            else:
                act = bpy.data.actions.new(prop)
            self.morphToAction(rig, prop, act)
            clearProp(rig, prop)


    def morphToAction(self, rig, prop, act):
        def addFrame(vec, channel, bname, group, threshold):
            for idx,elt in enumerate(vec):
                if abs(elt) > threshold:
                    path = 'pose.bones["%s"].%s' % (bname, channel)
                    fcu = act.fcurves.new(data_path=path, index=idx)
                    fcu.group = group
                    fcu.keyframe_points.insert(1, elt)  #, options={'FAST'})

        for pb in rig.pose.bones:
            bname = baseBone(pb.name)
            group = act.groups.get(bname)
            if group is None:
                group = act.groups.new(bname)
            addFrame(pb.location, "location", bname, group, 0.01*GS.scale)
            if pb.rotation_mode == 'QUATERNION':
                addFrame(pb.rotation_quaternion, "rotation_quaternion", bname, group, 1e-4)
            else:
                addFrame(pb.rotation_euler, "rotation_euler", bname, group, 1e-4)
            #addFrame(pb.scale, "scale", bname, group)



#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MorphsToAction,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
