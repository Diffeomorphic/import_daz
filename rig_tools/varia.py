# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
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
        fcurves = getActionFcurves(act)
        for fcu in list(fcurves):
            bname,channel,cnsname = getBoneChannel(fcu)
            if bname in bnames and channel == "rotation_euler":
                fcurves.remove(fcu)

        qlist = {}
        deletes = []
        for fcu in fcurves:
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
            fcus = [fcurves.new(path, index=idx, action_group=bname) for idx in range(3)]
            for t,quat in quats.items():
                euler = quat.to_euler()
                for idx,fcu in enumerate(fcus):
                    fcu.keyframe_points.insert(t, euler[idx], options={'FAST'})

        for fcu in deletes:
            fcurves.remove(fcu)

#-------------------------------------------------------------
#   Add Display Transform
#-------------------------------------------------------------

class DAZ_OT_AddDisplayTransform(DazOperator, IsArmature):
    bl_idname = "daz.add_display_transform"
    bl_label = "Add Display Transform"
    bl_description = "Add display transform bones to the active armature, targeting the selected mesh"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..rig_utils import addDisplayTransform
        if BLENDER4:
            raise DazError("bpy.ops.daz.add_display_transform requires Blender 5.0 or higher")
        rig = context.object
        meshes = getSelectedMeshes(context)
        if len(meshes) != 1:
            raise DazError("Exactly one mesh must be selected")
        if dazRna(rig).DazRig.startswith("rigify"):
            headname = "DEF-spine.007"
        else:
            headname = "head"
        if not addDisplayTransform(rig, meshes[0], headname):
            raise DazError("Failed to add display transform bones")

#-------------------------------------------------------------
#   Copy Roll
#-------------------------------------------------------------

class DAZ_OT_CopyRolls(DazPropsOperator, IsArmature):
    bl_idname = "daz.copy_rolls"
    bl_label = "Copy Roll Angles"
    bl_description = "Copy roll angles from active to selected"
    bl_options = {'UNDO'}

    useOrientation : BoolProperty(
        name = "Copy Bone Orientation",
        description = "Copy the full bone matrix rather than just the roll angle",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useOrientation")

    def run(self, context):
        src = context.object
        targets = [trg for trg in getSelectedArmatures(context) if trg != src]
        src.select_set(True)
        setMode('EDIT')
        for trg in targets:
            for srcb in src.data.edit_bones:
                eb = trg.data.edit_bones.get(srcb.name)
                if eb:
                    if self.useOrientation:
                        ematrix = srcb.matrix.copy()
                        ematrix.col[3][:3] = eb.head.copy()
                        eb.matrix = ematrix
                    else:
                        eb.roll = srcb.roll
        #setMode('OBJECT')

#-------------------------------------------------------------
#   Check Rest Poses
#-------------------------------------------------------------

class DAZ_OT_CheckRestPoses(DazOperator, IsArmature):
    bl_idname = "daz.check_rest_poses"
    bl_label = "Check Rest Poses"
    bl_description = "Check that rest pose is the same"
    bl_options = {'UNDO'}

    def run(self, context):
        rig1 = context.object
        eps = 1e-4
        for rig2 in getSelectedArmatures(context):
            if rig2 != rig1:
                diffs = {}
                setMode('EDIT')
                for eb2 in rig2.data.edit_bones:
                    eb1 = rig1.data.edit_bones.get(eb2.name)
                    if eb1:
                        if ((eb1.head - eb2.head).length > eps or
                            (eb1.tail - eb2.tail).length > eps or
                            abs(eb1.roll - eb2.roll) > eps):
                            diff = (eb1.roll, eb2.roll)
                            diffs[eb1.name] = diff
                setMode('OBJECT')
                print('Checked "%s" vs "%s"' % (rig2.name, rig1.name))
                for bname,diff in diffs.items():
                    print(bname, diff)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_HideUnusedLinks,
    DAZ_OT_MakeEulers,
    DAZ_OT_AddDisplayTransform,
    DAZ_OT_CopyRolls,
    DAZ_OT_CheckRestPoses
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
