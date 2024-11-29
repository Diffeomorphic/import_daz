# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *

#----------------------------------------------------------
#   Toggle locks
#----------------------------------------------------------

def toggleLocks(self, context, attr, lock):
    if getattr(self, attr):
        for pb in self.pose.bones:
            setattr(pb, lock, getattr(pb, attr))
    else:
        for pb in self.pose.bones:
            setattr(pb, lock, FFalse)

def toggleRotLocks(self, context):
    toggleLocks(self, context, "DazRotLocks", "lock_rotation")

def toggleLocLocks(self, context):
    toggleLocks(self, context, "DazLocLocks", "lock_location")

#----------------------------------------------------------
#   Toggle Limits
#----------------------------------------------------------

def toggleLimits(rig, context, attr, type, exclude):
    from .driver import getDrivenBoneFcurves
    auto = context.scene.tool_settings.use_keyframe_insert_auto
    driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
    for pb in rig.pose.bones:
        if pb.name in driven.keys():
            continue
        for cns in pb.constraints:
            if cns.type == type and cns.name not in exclude:
                cns.mute = False
                cns.influence = getattr(rig, attr)
                if auto:
                    cns.keyframe_insert("influence")

def toggleRotLimits(rig, context):
    exclude = ["Hint"] if rig.DazRig == "mhx" else []
    toggleLimits(rig, context, "DazRotLimits", "LIMIT_ROTATION", exclude)

def toggleLocLimits(rig, context):
    toggleLimits(rig, context, "DazLocLimits", "LIMIT_LOCATION", [])

#----------------------------------------------------------
#   Enable locks and limits
#----------------------------------------------------------

class LockEnabler:
    def enableLocksLimits(self, rig, lock, limit):
        from .driver import getDrivenBoneFcurves
        exclude = ["Hint"] if rig.DazRig == "mhx" else []
        driven = getDrivenBoneFcurves(rig, useRigifySafe=True)
        rig.DazLocLocks = lock
        rig.DazRotLocks = lock
        rig.DazLocLimits = limit
        rig.DazRotLimits = limit
        for pb in rig.pose.bones:
            if pb.name in driven.keys():
                continue
            self.setLocks(pb)
            for cns in pb.constraints:
                if cns.type == 'LIMIT_LOCATION':
                    cns.influence = limit
                elif cns.type == 'LIMIT_ROTATION' and cns.name not in exclude:
                    cns.influence = limit


class DAZ_OT_EnableLocksLimits(DazOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.enable_locks_limits"
    bl_label = "Enable Locks And Limits"
    bl_description = "Enable locks and limits"

    def run(self, context):
        rig = getRigFromContext(context)
        self.enableLocksLimits(rig, True, 1.0)

    def setLocks(self, pb):
        pb.lock_location = pb.DazLocLocks
        pb.lock_rotation = pb.DazRotLocks


class DAZ_OT_DisableLocksLimits(DazOperator, LockEnabler, IsMeshArmature):
    bl_idname = "daz.disable_locks_limits"
    bl_label = "Disable Locks And Limits"
    bl_description = "Disable locks and limits"

    def run(self, context):
        rig = getRigFromContext(context)
        self.enableLocksLimits(rig, False, 0.0)

    def setLocks(self, pb):
        pb.lock_location = pb.lock_rotation = FFalse

#----------------------------------------------------------
#   Lock or unlock all channels
#----------------------------------------------------------

class DAZ_OT_LockAllChannels(DazPropsOperator, IsObject):
    bl_idname = "daz.lock_all_channels"
    bl_label = "Lock/Unlock All Channels"
    bl_description = "Lock or unlock all channels of selected objects"

    useEnable : BoolProperty(
        name = "Enable",
        description = "Enable locks",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useEnable")

    def run(self, context):
        value = (TTrue if self.useEnable else FFalse)
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
    bpy.types.Object.DazRotLocks = BoolPropOVR(
        name = "Rotation Locks",
        description = "Rotation Locks",
        default = True,
        update = toggleRotLocks)

    bpy.types.Object.DazLocLocks = BoolPropOVR(
        name = "Location Locks",
        description = "Location Locks",
        default = True,
        update = toggleLocLocks)

    bpy.types.Object.DazRotLimits = FloatPropOVR(1.0,
        name = "Rotation Limits",
        description = "Rotation Limits",
        min = 0.0, max = 1.0,
        update = toggleRotLimits)

    bpy.types.Object.DazLocLimits = FloatPropOVR(1.0,
        name = "Location Limits",
        description = "Location Limits",
        min = 0.0, max = 1.0,
        update = toggleLocLimits)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
