#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
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
import math
from mathutils import *
from .utils import *
from .error import *

#----------------------------------------------------------
#  Make bone
#----------------------------------------------------------

def deriveBone(bname, eb0, rig, layer, parent):
    return makeBone(bname, rig, eb0.head, eb0.tail, eb0.roll, layer, parent)


def makeBone(bname, rig, head, tail, roll, layer, parent, headbone=None, tailbone=None):
    eb = rig.data.edit_bones.new(bname)
    eb.head = head
    eb.tail = tail
    eb.roll = normalizeRoll(roll)
    eb.use_connect = False
    eb.parent = parent
    eb.use_deform = False
    enableBoneNumLayer(eb, rig, layer)
    if headbone:
        LS.headbones[bname] = headbone.name
    if tailbone:
        LS.tailbones[bname] = tailbone.name
    return eb

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def setMhx(rna, prop, value):
    rna[prop] = value


def mhxProp(prop):
    if isinstance(prop, str):
        return propRef(prop)
    else:
        prop1,prop2 = prop
        return (propRef(prop1), propRef(prop2))


def addMuteDriver(cns, rig, prop):
    if prop:
        addDriver(cns, "mute", rig, mhxProp(prop), "not(x)")

#-------------------------------------------------------------
#   Constraints
#-------------------------------------------------------------

def copyTransform(bone, target, rig, prop=None, expr="x", space='POSE'):
    cns = bone.constraints.new('COPY_TRANSFORMS')
    cns.name = "Copy Transform %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    cns.owner_space = space
    cns.target_space = space
    return cns


def copyTransformFkIk(bone, boneFk, boneIk, rig, prop1, prop2=None):
    if boneFk is not None:
        cnsFk = copyTransform(bone, boneFk, rig)
        cnsFk.influence = 1.0
    if boneIk is not None:
        cnsIk = copyTransform(bone, boneIk, rig, prop1)
        cnsIk.influence = 0.0
        if prop2:
            addDriver(cnsIk, "mute", rig, mhxProp(prop2), "x")


def copyLocation(bone, target, rig, prop=None, expr="x", space='POSE'):
    cns = bone.constraints.new('COPY_LOCATION')
    cns.name = "Copy Location %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    cns.owner_space = space
    cns.target_space = space
    return cns


def copyRotation(bone, target, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_ROTATION')
    cns.name = "Copy Rotation %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.owner_space = space
    cns.target_space = space
    if bone.rotation_mode != 'QUATERNION':
        setEulerOrder(cns, bone.rotation_mode)
    elif target.rotation_mode != 'QUATERNION':
        setEulerOrder(cns, target.rotation_mode)
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def copyScale(bone, target, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_SCALE')
    cns.name = "Copy Scale %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.owner_space = space
    cns.target_space = space
    if prop is not None:
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def limitLocation(bone, rig):
    cns = bone.constraints.new('LIMIT_LOCATION')
    cns.owner_space = 'LOCAL'
    cns.use_transform_limit = True
    return cns


def limitRotation(bone, rig):
    cns = bone.constraints.new('LIMIT_ROTATION')
    cns.owner_space = 'LOCAL'
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = False
    cns.use_transform_limit = True
    return cns


def ikConstraint(last, target, pole, angle, count, rig, prop=None, expr="x"):
    cns = last.constraints.new('IK')
    cns.name = "IK %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    if pole:
        cns.pole_target = rig
        cns.pole_subtarget = pole.name
        cns.pole_angle = angle*D
    cns.chain_count = count
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def addHint(pb, rig):
    cns = pb.constraints.new('LIMIT_ROTATION')
    cns.name = "Hint"
    cns.owner_space = 'LOCAL'
    setEulerOrder(cns, pb.rotation_mode)
    cns.min_x = cns.max_x = 18*D
    cns.use_limit_x = cns.use_limit_y = cns.use_limit_z = True
    cns.use_transform_limit = True


def stretchTo(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('STRETCH_TO')
    cns.name = "StretchTo %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.volume = "NO_VOLUME"
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def dampedTrack(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('DAMPED_TRACK')
    cns.name = "Damped Track %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns


def trackTo(pb, target, rig, space='POSE'):
    cns = pb.constraints.new('TRACK_TO')
    cns.name = "Track To %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.up_axis = 'UP_Z'
    cns.use_target_z = True
    cns.target_space = space
    cns.owner_space = space
    return cns


def lockedTrack(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('LOCKED_TRACK')
    cns.name = "Locked Track %s" % target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.lock_axis = 'LOCK_X'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, mhxProp(prop), expr)
    return cns

#----------------------------------------------------------
#   Copy Absolute Pose
#----------------------------------------------------------

class DAZ_OT_CopyAbsolutePose(DazOperator, IsArmature):
    bl_idname = "daz.copy_absolute_pose"
    bl_label = "Copy Absolute Pose"
    bl_description = (
        "Copy pose in world space from active to selected armatures.\n" +
        "Only works properly if both armatures have the same bone names")
    bl_options = {'UNDO'}

    def run(self, context):
        from .animation import insertKeys
        src = context.object
        scn = context.scene
        auto = scn.tool_settings.use_keyframe_insert_auto
        roots = [pb for pb in src.pose.bones if pb.parent is None]
        for trg in getSelectedArmatures(context):
            if trg != src:
                for root in roots:
                    self.copyPose(root, trg)
                if auto:
                    for pb in trg.pose.bones:
                        insertKeys(pb, True, scn.frame_current)


    def copyPose(self, pb, trg):
        from .animation import imposeLocks
        trgpb = trg.pose.bones.get(pb.name)
        if trgpb:
            loc = trgpb.location.copy()
            trgpb.matrix = pb.matrix.copy()
            updatePose()
            if trgpb.parent:
                trgpb.location = loc
            imposeLocks(trgpb)
            for child in pb.children:
                self.copyPose(child, trg)

#-------------------------------------------------------------
#   Improve IK
#-------------------------------------------------------------

class DAZ_OT_ImproveIK(DazOperator, IsArmature):
    bl_idname = "daz.improve_ik"
    bl_label = "Improve IK"
    bl_description = "Improve IK behaviour"
    bl_options = {'UNDO'}

    def run(self, context):
        improveIk(context.object)


def improveIk(rig, exclude=[]):
    ikconstraints = []
    for pb in rig.pose.bones:
        if pb.name in exclude:
            continue
        for cns in pb.constraints:
            if cns.type == 'IK':
                ikconstraints.append((pb, cns, cns.mute))
                cns.mute = True
                pb.rotation_euler[0] = 30*D
                pb.lock_rotation[0] = True
    for pb,cns,mute in ikconstraints:
        pb.lock_rotation = TTrue
        pb.lock_location = TTrue
        cns.mute = mute
        pb.use_ik_limit_y = pb.use_ik_limit_z = False
        pb.lock_ik_y = pb.lock_ik_z = True
        pb.use_ik_limit_x = True
        pb.ik_min_x = -15*D
        pb.ik_max_x = 160*D

#----------------------------------------------------------
#   Batch set custom shape
#----------------------------------------------------------

class DAZ_OT_BatchSetCustomShape(DazPropsOperator, IsArmature):
    bl_idname = "daz.batch_set_custom_shape"
    bl_label = "Batch Set Custom Shape"
    bl_description = "Set the selected mesh as the custom shape of all selected bones"
    bl_options = {'UNDO'}

    useClear : BoolProperty(
        name = "Clear custom shapes",
        default = False)

    scale : FloatVectorProperty(
        name = "Scale",
        size=3,
        default=(1,1,1))

    translation : FloatVectorProperty(
        name = "Translation",
        size=3,
        default=(0,0,0))

    rotation : FloatVectorProperty(
        name = "Rotation",
        size=3,
        default=(0,0,0))

    def draw(self, context):
        self.layout.prop(self, "useClear")
        if not self.useClear:
            self.layout.prop(self, "scale")
            self.layout.prop(self, "translation")
            self.layout.prop(self, "rotation")

    def run(self, context):
        rig = context.object
        if self.useClear:
            for pb in rig.pose.bones:
                if pb.bone.select:
                    pb.custom_shape = None
        else:
            ob = None
            for ob1 in getSelectedObjects(context):
                if ob1 != rig:
                    ob = ob1
                    break
            if ob is None:
                raise DazError("No custom shape object selected")
            for pb in rig.pose.bones:
                if pb.bone.select:
                    pb.custom_shape = ob
                    setCustomShapeTransform(pb, self.scale, self.translation, Vector(self.rotation)*D)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyAbsolutePose,
    DAZ_OT_ImproveIK,
    DAZ_OT_BatchSetCustomShape,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
