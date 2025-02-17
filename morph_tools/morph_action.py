# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..morphing import MS

#-------------------------------------------------------------
#   Convert morphs to action
#-------------------------------------------------------------

class DAZ_OT_ConvertMorphsToAction(DazOperator, IsArmature):
    bl_idname = "daz.convert_morphs_to_action"
    bl_label = "Convert Morphs To Action"
    bl_description = "Convert morphs to action"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        morphnames = []
        for morphset in MS.Standards:
            pg = getattr(dazRna(rig), "Daz%s" % morphset)
            morphnames += list(pg.keys())
        for cat in dazRna(rig).DazMorphCats:
            morphnames += list(cat.morphs.keys())
        props = [prop for prop in rig.keys() if prop in morphnames]
        for prop in props:
            clearProp(rig, prop)
        for prop in props:
            print("*", prop)
            act = bpy.data.actions.get(prop)
            if act:
                act.fcurves.clear()
            else:
                act = bpy.data.actions.new(prop)
            act.use_fake_user = True
            setProp(rig, prop)
            #updateRigDrivers(context, rig)
            setMode('EDIT')
            setMode('OBJECT')
            self.morphToAction(rig, prop, act)
            clearProp(rig, prop)
        setMode('EDIT')
        setMode('OBJECT')


    def morphToAction(self, rig, prop, act):
        def addFrame(vec, channel, bname, group, threshold):
            for idx,elt in enumerate(vec):
                if abs(elt) > threshold:
                    self.used = True
                    path = 'pose.bones["%s"].%s' % (bname, channel)
                    fcu = act.fcurves.new(data_path=path, index=idx)
                    fcu.group = group
                    fcu.keyframe_points.insert(1, elt, options={'FAST'})
                    kp = fcu.keyframe_points[0]
                    kp.interpolation = 'LINEAR'

        for pb in rig.pose.bones:
            bname = baseBone(pb.name)
            group = act.groups.get(bname)
            if group is None:
                group = act.groups.new(bname)
            self.used = False
            addFrame(pb.location, "location", bname, group, 0.01*GS.scale)
            if pb.rotation_mode == 'QUATERNION':
                addFrame(pb.rotation_quaternion, "rotation_quaternion", bname, group, 1e-4)
            else:
                addFrame(pb.rotation_euler, "rotation_euler", bname, group, 1e-4)
            #addFrame(pb.scale, "scale", bname, group)
            if not self.used:
                act.groups.remove(group)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ConvertMorphsToAction,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
