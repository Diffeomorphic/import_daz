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
            setProp(rig, prop)
            #updateRigDrivers(context, rig)
            setMode('EDIT')
            setMode('OBJECT')
            self.morphToAction(rig, label, prop)
            clearProp(rig, prop)
        setMode('EDIT')
        setMode('OBJECT')


    def morphToAction(self, rig, label, prop):
        def makeNewAction(ob, label, prop):
            aname = "%s:%s" % (ob.name, label)
            act = bpy.data.actions.get(aname)
            if act:
                strip = act.layers[0].strips[0]
                for slot in act.slots:
                    strip.channelbag(slot).fcurves.clear()
            else:
                act = addNewAction(aname, "Morphs")
            act.use_fake_user = True
            act["DazName"] = prop
            return act, act.layers[0].strips[0].channelbags

        def addFrame(value, path, idx, group, threshold):
            if abs(value) > threshold:
                self.used = True
                fcu = bag.fcurves.new(data_path=path, index=idx)
                fcu.group = group
                fcu.keyframe_points.insert(1, value, options={'FAST'})
                kp = fcu.keyframe_points[0]
                kp.interpolation = 'LINEAR'

        def addBoneFrame(vec, channel, bname, group, threshold):
            for idx,elt in enumerate(vec):
                path = 'pose.bones["%s"].%s' % (bname, channel)
                addFrame(elt, path, idx, group, threshold)

        def addShapeFrame(value, channel, sname, group, threshold):
            path = 'key_blocks["%s"].value' % sname
            addFrame(value, path, -1, group, threshold)

        act, bags = makeNewAction(rig, label, prop)
        slot = act.slots.new('OBJECT', rig.name)
        bag = bags.new(slot)
        for pb in rig.pose.bones:
            bname = baseBone(pb.name)
            group = bag.groups.get(bname)
            if group is None:
                group = bag.groups.new(bname)
            self.used = False
            addBoneFrame(pb.location, "location", bname, group, 0.01*GS.scale)
            if pb.rotation_mode == 'QUATERNION':
                addBoneFrame(pb.rotation_quaternion, "rotation_quaternion", bname, group, 1e-4)
            else:
                addBoneFrame(pb.rotation_euler, "rotation_euler", bname, group, 1e-4)
            #addFrame(pb.scale, "scale", bname, group)
            if not self.used:
                bag.groups.remove(group)

        for ob in getShapeChildren(rig):
            slot = act.slots.new('KEY', ob.name)
            bag = bags.new(slot)
            group = bag.groups.get(ob.name)
            if group is None:
                group = bag.groups.new(ob.name)
            skeys = ob.data.shape_keys
            for skey in skeys.key_blocks[1:]:
                addShapeFrame(skey.value, "value", skey.name, group, 1e-3)

        print("*", act.name, act["DazName"])

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
