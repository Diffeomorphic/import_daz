# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
                dazRna(rig).DazLocLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazLocLocks")
            if self.useRotation:
                dazRna(rig).DazRotLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazRotLocks")
            if self.useScale:
                dazRna(rig).DazScaleLocks = lock
                if self.useKeying:
                    rig.keyframe_insert("DazScaleLocks")
        if self.useLimits:
            if self.useLocation:
                dazRna(rig).DazLocLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazLocLimits")
            if self.useRotation:
                dazRna(rig).DazRotLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazRotLimits")
            if self.useScale:
                dazRna(rig).DazScaleLimits = limit
                if self.useKeying:
                    rig.keyframe_insert("DazScaleLimits")
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

    useLock : BoolProperty(
        name = "Lock",
        description = "Enable locks",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useLock")

    def run(self, context):
        value = (TTrue if self.useLock else FFalse)
        for ob in getSelectedObjects(context):
            for channel in ["lock_location", "lock_rotation", "lock_scale"]:
                setattr(ob, channel, value)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_EnableLocksLimits,
    DAZ_OT_DisableLocksLimits,
    DAZ_OT_LockAllChannels
]

def register():
    bpy.types.Object.DazRotLocks = bpy.props.BoolProperty(
        name = "Rot",
        description = "Rotation Locks",
        default = True,
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazLocLocks = bpy.props.BoolProperty(
        name = "Loc",
        description = "Location Locks",
        default = True,
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazScaleLocks = bpy.props.BoolProperty(
        name = "Sca",
        description = "Scale Locks",
        default = True,
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazRotLimits = bpy.props.FloatProperty(
        name = "Rot",
        description = "Rotation Limits",
        min = 0.0, max = 1.0,
        default = 1.0,
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazLocLimits = bpy.props.FloatProperty(
        name = "Loc",
        description = "Location Limits",
        min = 0.0, max = 1.0,
        default = 1.0,
        override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Object.DazScaleLimits = bpy.props.FloatProperty(
        name = "Sca",
        description = "Scale Limits",
        min = 0.0, max = 1.0,
        default = 1.0,
        override={'LIBRARY_OVERRIDABLE'})

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
