# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..figure import *

#-------------------------------------------------------------
#   Select seg
#-------------------------------------------------------------

class DAZ_OT_HideUnusedLinks(DazPropsOperator, IsArmature):
    bl_idname = "daz.hide_unused_links"
    bl_label = "Hide Unused Links"
    bl_description = "Move unconnected bones with matching names away"
    bl_options = {'UNDO'}

    match : StringProperty(
        name = "Match",
        description = "Name string of bones to hide",
        default = "seg")

    useDelete : BoolProperty(
        name = "Delete",
        description = "Delete hidden bones and vertices",
        default = True)

    threshold = 0.001

    def draw(self, context):
        self.layout.prop(self, "match")
        self.layout.prop(self, "useDelete")

    def run(self, context):
        def addRecursive(bone):
            for child in bone.children:
                addRecursive(child)
            bnames.append(bone.name)

        match = self.match.lower()
        rigs = getSelectedArmatures(context)
        for rig in rigs:
            firsts = []
            for pb in rig.pose.bones:
                words = pb.name.lower().rsplit(match, 1)
                if len(words) == 2 and words[1].isdigit() and pb.parent:
                    if ((pb.head-pb.parent.tail).length > self.threshold and
                        int(words[1]) > 1):
                        firsts.append(pb.name)
            if self.useDelete and activateObject(context, rig):
                bnames = []
                for bname in firsts:
                    addRecursive(rig.data.bones[bname])
                setMode('EDIT')
                for bname in bnames:
                    eb = rig.data.edit_bones[bname]
                    rig.data.edit_bones.remove(eb)
                setMode('OBJECT')
                for ob in getMeshChildren(rig):
                    if activateObject(context, ob):
                        groups = [vgrp.index for vgrp in ob.vertex_groups if vgrp.name in bnames]
                        setMode('EDIT')
                        bpy.ops.mesh.select_all(action='DESELECT')
                        setMode('OBJECT')
                        for v in ob.data.vertices:
                            for g in v.groups:
                                if g.group in groups:
                                    v.select = True
                                    break
                        setMode('EDIT')
                        bpy.ops.mesh.delete(type='VERT')
                        setMode('OBJECT')
            else:
                for bname in firsts:
                    pb = rig.pose.bones[bname]
                    pb.location = (-10,-10,-10)

#-------------------------------------------------------------
#   Make Eulers
#-------------------------------------------------------------

class DAZ_OT_MakeEulers(DazOperator, IsArmature):
    bl_idname = "daz.make_eulers"
    bl_label = "Make Eulers"
    bl_description = "Convert all quaternion bones to XYZ Eulers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        bnames = []
        for pb in rig.pose.bones:
            if pb.rotation_mode == 'QUATERNION':
                pb.rotation_mode = 'XYZ'
                bnames.append(pb.name)
        if rig.animation_data:
            act = rig.animation_data.action
            if act:
                self.convertAction(act, rig, bnames)


    def convertAction(self, act, rig, bnames):
        for fcu in list(getActionSlot(act).fcurves):
            bname,channel,cnsname = getBoneChannel(fcu)
            if bname in bnames and channel == "rotation_euler":
                getActionSlot(act).fcurves.remove(fcu)

        qlist = {}
        deletes = []
        for fcu in getActionSlot(act).fcurves:
            bname,channel,cnsname = getBoneChannel(fcu)
            if bname in bnames and channel == "rotation_quaternion":
                deletes.append(fcu)
                quats = qlist.get(bname)
                if quats is None:
                    quats = qlist[bname] = {}
                for kp in fcu.keyframe_points:
                    t = int(kp.co[0])
                    quat = quats.get(t)
                    if quat is None:
                        quat = quats[t] = Quaternion()
                    quat[fcu.array_index] = kp.co[1]

        for bname,quats in qlist.items():
            path = 'pose.bones["%s"].rotation_euler' % bname
            fcus = [getActionSlot(act).fcurves.new(path, index=idx, action_group=bname) for idx in range(3)]
            for t,quat in quats.items():
                euler = quat.to_euler()
                for idx,fcu in enumerate(fcus):
                    fcu.keyframe_points.insert(t, euler[idx], options={'FAST'})

        for fcu in deletes:
            getActionSlot(act).fcurves.remove(fcu)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_HideUnusedLinks,
    DAZ_OT_MakeEulers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
