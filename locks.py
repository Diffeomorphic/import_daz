# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *

#----------------------------------------------------------
#   Enable locks and limits
#----------------------------------------------------------

class LockEnabler:
    useLocation : BoolProperty(
        name = "Location",
        default = True)

    useRotation : BoolProperty(
        name = "Rotation",
        default = True)

    useScale : BoolProperty(
        name = "Scale",
        default = True)

    useLocks : BoolProperty(
        name = "Locks",
        description = "Enable/Disable locks",
        default = True)

    useLimits : BoolProperty(
        name = "Limits",
        description = "Enable/Disable limits",
        default = True)

    limitType : EnumProperty(
        items = [('INFLUENCE', "Influence", "Enable/Disable constraint influence"),
                 ('MUTE', "Mute", "Mute/Unmute constraints"),
                 ('BOTH', "Both", "Both influence and mute")],
        name = "Type",
        default = 'INFLUENCE')

    useKeying : BoolProperty(
        name = "Key",
        description = "Key locks and constraints",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useLocation")
        self.layout.prop(self, "useRotation")
        self.layout.prop(self, "useScale")
        self.layout.separator()
        self.layout.prop(self, "useLocks")
        self.layout.prop(self, "useLimits")
        if self.useLimits:
            self.layout.prop(self, "limitType")
        self.layout.prop(self, "useKeying")

    def enableLocksLimits(self, rig, lock, limit, mute):
        from .driver import getDrivenBoneFcurves
        exclude = ["Hint"] if dazRna(rig).DazRig == "mhx" else []
        driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
        if self.useLocks:
            if self.useLocation:
                dazRna(rig).DazHasLocLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazHasLocLocks")
            if self.useRotation:
                dazRna(rig).DazHasRotLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazHasRotLocks")
            if self.useScale:
                dazRna(rig).DazHasScaleLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazHasScaleLocks")
        if self.useLimits:
            if self.useLocation:
                dazRna(rig).DazHasLocLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazHasLocLimits")
            if self.useRotation:
                dazRna(rig).DazHasRotLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazHasRotLimits")
            if self.useScale:
                dazRna(rig).DazHasScaleLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazHasScaleLimits")
        for pb in rig.pose.bones:
            if pb.name in driven.keys():
                continue
            if self.useLocks:
                self.setLocks(pb)
            for cns in pb.constraints:
                if ((cns.type == 'LIMIT_LOCATION' and
                     self.useLocation) or
                    (cns.type == 'LIMIT_ROTATION' and
                     self.useRotation and
                     cns.name not in exclude) or
                    (cns.type == 'LIMIT_SCALE' and
                     self.useScale)):
                    if self.limitType in ('INFLUENCE', 'BOTH'):
                        cns.influence = limit
                        if self.useKeying:
                            cns.keyframe_insert("influence")
                    if self.limitType in ('MUTE', 'BOTH'):
                        cns.mute = mute
                        if self.useKeying:
                            cns.keyframe_insert("mute")


class DAZ_OT_EnableLocksLimits(DazPropsOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.enable_locks_limits"
    bl_label = "Enable Locks And Limits"
    bl_description = "Enable locks and limits"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromContext(context)
        self.enableLocksLimits(rig, True, 1.0, False)

    def setLocks(self, pb):
        if self.useLocation:
            pb.lock_location = dazRna(pb).DazLocLocks
        if self.useRotation:
            pb.lock_rotation = dazRna(pb).DazRotLocks
        if self.useScale:
            pb.lock_scale = dazRna(pb).DazScaleLocks


class DAZ_OT_DisableLocksLimits(DazPropsOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.disable_locks_limits"
    bl_label = "Disable Locks And Limits"
    bl_description = "Disable locks and limits"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromContext(context)
        self.enableLocksLimits(rig, False, 0.0, True)

    def setLocks(self, pb):
        if self.useLocation:
            pb.lock_location = FFalse
        if self.useRotation:
            pb.lock_rotation = FFalse
        if self.useScale:
            pb.lock_scale = FFalse

#----------------------------------------------------------
#   Lock or unlock all channels
#----------------------------------------------------------

class DAZ_OT_LockAllChannels(DazPropsOperator, IsObject):
    bl_idname = "daz.lock_all_channels"
    bl_label = "Lock/Unlock All Channels"
    bl_description = "Lock or unlock all channels of selected objects"
    bl_options = {'UNDO'}

    useLock : BoolProperty(
        name = "Lock",
        description = "Enable locks",
        default = True)

    useObjects : BoolProperty(
        name = "Objects",
        description = "Enable/Disable locks for objects",
        default = True)

    useBones : BoolProperty(
        name = "Bones",
        description = "Enable/Disable locks for bones",
        default = False)

    useLocX : BoolProperty(
        name = "X Loc",
        description = "Lock X location",
        default = True)

    useLocY : BoolProperty(
        name = "Y Loc",
        description = "Lock Y location",
        default = True)

    useLocZ : BoolProperty(
        name = "Z Loc",
        description = "Lock X location",
        default = True)

    useRotX : BoolProperty(
        name = "X Rot",
        description = "Lock X rotation",
        default = True)

    useRotY : BoolProperty(
        name = "Y Rot",
        description = "Lock Y rotation",
        default = True)

    useRotZ : BoolProperty(
        name = "Z Rot",
        description = "Lock X rotation",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useLock")
        self.layout.prop(self, "useObjects")
        self.layout.prop(self, "useBones")
        if self.useBones:
            row = self.layout.row()
            row.prop(self, "useLocX")
            row.prop(self, "useLocY")
            row.prop(self, "useLocZ")
            row = self.layout.row()
            row.prop(self, "useRotX")
            row.prop(self, "useRotY")
            row.prop(self, "useRotZ")

    def run(self, context):
        value = (TTrue if self.useLock else FFalse)
        for ob in getSelectedObjects(context):
            if self.useObjects:
                for channel in ["lock_location", "lock_rotation", "lock_scale"]:
                    setattr(ob, channel, value)
            if self.useBones and ob.type == 'ARMATURE':
                for pb in ob.pose.bones:
                    for channel in ["lock_location", "lock_rotation", "lock_scale"]:
                        setattr(pb, channel, value)
                    if not self.useLocX:
                        pb.lock_location[0] = False
                    if not self.useLocY:
                        pb.lock_location[1] = False
                    if not self.useLocZ:
                        pb.lock_location[2] = False
                    if not self.useRotX:
                        pb.lock_rotation[0] = False
                    if not self.useRotY:
                        pb.lock_rotation[1] = False
                    if not self.useRotZ:
                        pb.lock_rotation[2] = False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_EnableLocksLimits,
    DAZ_OT_DisableLocksLimits,
    DAZ_OT_LockAllChannels
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
