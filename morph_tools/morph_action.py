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
        morphlist = []
        for morphset in MS.Standards:
            pg = getattr(dazRna(rig), "Daz%s" % morphset)
            morphlist += list(pg.values())
        for cat in dazRna(rig).DazMorphCats:
            morphlist += list(cat.morphs.values())
        morphs = [morph for morph in morphlist if morph.name in rig.keys()]
        for morph in morphs:
            clearProp(rig, morph.name)
        for morph in morphs:
            prop,label = morph.name, morph.text
            print("MO", prop, label)
            act = bpy.data.actions.get(label)
            if act:
                bpy.data.actions.remove(act)
            setProp(rig, prop)
            #updateRigDrivers(context, rig)
            setMode('EDIT')
            setMode('OBJECT')
            self.morphToAction(rig, prop)
            clearProp(rig, prop)
            setMode('EDIT')
            setMode('OBJECT')
            self.fixAction(rig, prop, label)
            for ob in getMeshChildren(rig):
                self.fixAction(ob, prop, label)
        setMode('EDIT')
        setMode('OBJECT')


    def morphToAction(self, rig, prop):
        print("MAC", prop)

        def clearAction(rna):
            if rna and rna.animation_data:
                rna.animation_data.action = None

        clearAction(rig)
        for ob in getShapeChildren(rig):
            clearAction(ob.data.shape_keys)

        eps =  0.01*GS.scale
        for pb in rig.pose.bones:
            group = pb.name
            if isDrvBone(pb.name):
                continue
            if pb.location.length > eps:
                pb.keyframe_insert("location", group=group)
            if pb.rotation_mode == 'QUATERNION':
                if Vector(pb.rotation_quaternion[1:]).length > 1e-4:
                    pb.keyframe_insert("rotation_quaternion", group=group)
            else:
                if Vector(pb.rotation_euler).length > 1e-4:
                    pb.keyframe_insert("rotation_euler", group=group)
            if (pb.scale - One).length > 1e-4:
                pb.keyframe_insert("scale", group=group)

        for ob in getShapeChildren(rig):
            for skey in ob.data.shape_keys.key_blocks:
                if abs(skey.value) > 1e-3:
                    print("VAL", ob.name, skey.name, skey.value)
                    skey.keyframe_insert("value")


    def fixAction(self, rna, prop, label):
        act = None
        if rna and rna.animation_data:
            act = rna.animation_data.action
        if act is None:
            return
        print("ACT", rna, act)
        act.use_fake_user = True
        act.name = label
        act["DazName"] = prop
        print("*", act.name, act["DazName"])
        return
        fcurves = getActionSlot(act).fcurves
        for fcu in fcurves:
            for kp in fcu.keyframe_points:
                kp.interpolation = 'LINEAR'

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
