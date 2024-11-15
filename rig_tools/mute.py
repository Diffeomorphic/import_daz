#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
from ..figure import *

#-------------------------------------------------------------
#   Categorize
#-------------------------------------------------------------

class DAZ_OT_CategorizeObjects( DazOperator, IsMeshArmature):
    bl_idname = "daz.categorize_objects"
    bl_label = "Categorize Objects"
    bl_description = "Move unparented objects and their children to separate categories"

    def run(self, context):
        def linkObjects(ob, coll):
            for coll1 in bpy.data.collections:
                if ob.name in coll1.objects:
                    coll1.objects.unlink(ob)
            coll.objects.link(ob)
            for child in ob.children:
                linkObjects(child, coll)

        roots = []
        for ob in getSelectedObjects(context):
            if ob.parent is None and ob.type in ['MESH', 'ARMATURE']:
                roots.append(ob)
        print("Roots", roots)
        parcoll = context.collection
        for root in roots:
            coll = bpy.data.collections.new(root.name)
            parcoll.children.link(coll)
            linkObjects(root, coll)

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
                self.convertAction(act, bnames)


    def convertAction(self, act, bnames):
        for fcu in list(act.fcurves):
            bname,channel = getBoneChannel(fcu)
            if bname in bnames and channel == "rotation_euler":
                act.fcurves.remove(fcu)

        qlist = {}
        deletes = []
        for fcu in act.fcurves:
            bname,channel = getBoneChannel(fcu)
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
            fcus = [act.fcurves.new(path, index=idx, action_group=bname) for idx in range(3)]
            for t,quat in quats.items():
                euler = quat.to_euler()
                for idx,fcu in enumerate(fcus):
                    fcu.keyframe_points.insert(t, euler[idx], options={'FAST'})

        for fcu in deletes:
            act.fcurves.remove(fcu)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CategorizeObjects,
    DAZ_OT_HideUnusedLinks,
    DAZ_OT_MakeEulers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
