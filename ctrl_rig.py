# Copyright (c) 2016-2024, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import os
import bpy
from mathutils import *
from .error import *
from .utils import *

#----------------------------------------------------------
#   Framer class
#----------------------------------------------------------

class Framer(DazPropsOperator):
    frame_start : IntProperty(
        name = "Start",
        default = 1)

    frame_end : IntProperty(
        name = "End",
        default = 1)

    def draw(self, context):
        self.layout.prop(self, "frame_start")
        self.layout.prop(self, "frame_end")


    def setActiveRange(self, context, rig):
        adata = rig.animation_data
        if adata and adata.action:
            tmin = tmax = 1
            for fcu in adata.action.fcurves:
                times = [kp.co[0] for kp in fcu.keyframe_points]
                tmin = min(int(min(times)), tmin)
                tmax = max(int(max(times)), tmax)
            self.frame_start = tmin
            self.frame_end = tmax
        else:
            self.frame_start = self.frame_end = context.scene.frame_current


    def invoke(self, context, event):
        rig = getRigFromContext(context)
        rig = self.getControlRig(rig)
        self.setActiveRange(context, rig)
        return DazPropsOperator.invoke(self, context, event)


    def getControlRig(rig):
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'COPY_TRANSFORMS':
                    return cns.target
        return rig


    def bakeShapekeys(self, context, meshes, actname):
        scn = context.scene
        for ob in meshes:
            if ob.animation_data:
                ob.animation_data.action = None
        for frame in range(self.frame_start, self.frame_end+1):
            scn.frame_current = frame
            updateScene(context)
            for ob in meshes:
                for skey in ob.data.shape_keys.key_blocks:
                    skey.value = skey.value
                    if abs(skey.value) < 1e-4:
                        skey.value = 0
                    skey.keyframe_insert("value", frame=frame)
        for ob in meshes:
            if ob.data.shape_keys:
                act = getCurrentAction(ob.data.shape_keys)
                if act:
                    act.name = "%s:%s" % (actname[0:33], ob.name[0:30])
#-------------------------------------------------------------
#   Bake deform rig
#-------------------------------------------------------------

class ControlRigMuter:
    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Mute/unmute shapekeys too",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useShapekeys")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazRig.startswith(("mhx", "rigify")))

    def getProps(self, rig, gen):
        props = {}
        for prop in rig.keys():
            final = finalProp(prop)
            if final in gen.data.keys():
                props[prop] = gen.data[final]
        return props

    def muteConstraints(self, rig, mute):
        for pb in rig.pose.bones:
            if pb.get("DazSharedBone"):
                continue
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    cns.mute = mute
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            cns.mute = mute

    def getControlRig(self, rig):
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            return cns.target
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    return cns.target
        raise DazError("No control rig found")


def getCurrentAction(rna):
    if rna and rna.animation_data:
        return rna.animation_data.action
    return None

#-------------------------------------------------------------
#   Bake shapekeys
#-------------------------------------------------------------

class DAZ_OT_BakeShapekeys(Framer, IsMesh):
    bl_idname = "daz.bake_shapekeys"
    bl_label = "Bake Shapekeys"
    bl_description = "Bake shapekey values to current action.\nMute control rig afterwards"
    bl_options = {'UNDO'}

    def run(self, context):
        meshes = getSelectedMeshes(context)
        self.bakeShapekeys(context, meshes, "Shapes")

#-------------------------------------------------------------
#   Mute control rig
#-------------------------------------------------------------

class DAZ_OT_MuteControlRig(ControlRigMuter, Framer):
    bl_idname = "daz.mute_control_rig"
    bl_label = "Mute Control Rig"
    bl_description = "Disable drivers and copy location/rotation constraints"
    bl_options = {'UNDO'}

    useBake : BoolProperty(
        name = "Bake action",
        description = "Bake visual transform to an action",
        default = True)

    def draw(self, context):
        ControlRigMuter.draw(self, context)
        self.layout.prop(self, "useBake")
        if self.useBake:
            Framer.draw(self, context)

    def run(self, context):
        rig = context.object
        scn = context.scene
        gen = self.getControlRig(rig)
        act = getCurrentAction(gen)
        if act:
            actname = act.name
        else:
            actname = "Action"
        meshes = getShapeChildren(rig)
        bpy.ops.nla.bake(frame_start=self.frame_start, frame_end=self.frame_end, only_selected=False, visual_keying=True, bake_types={'OBJECT', 'POSE'})
        act = getCurrentAction(rig)
        shared = dict([(pb.name, pb) for pb in rig.pose.bones if pb.get("DazSharedBone")])
        if shared:
            for fcu in list(act.fcurves):
                bname,channel = getBoneChannel(fcu)
                if bname in shared.keys():
                    act.fcurves.remove(fcu)
            for pb in shared.values():
                pb.matrix_basis = Matrix()
        if self.useBake:
            if act:
                act.name = "%s:BAKED" % actname[0:58]
            if self.useShapekeys:
                self.bakeShapekeys(context, meshes, actname)
        else:
            rig.animation_data.action = None
        if self.useShapekeys:
            for ob in meshes:
                for skey in ob.data.shape_keys.key_blocks:
                    skey.driver_remove("value")
        self.muteConstraints(rig, True)
        gen.hide_set(True)
        props = self.getProps(rig, gen)
        fcurves = self.getFcurves(gen, props)
        for prop,value in props.items():
            rig.driver_remove(propRef(prop))
            rig[prop] = value
        if self.useBake and not self.useShapekeys:
            for prop,fcu in fcurves.items():
                self.setFcurve(rig, propRef(prop), fcu)

    def getFcurves(self, gen, props):
        fcurves = {}
        act = getCurrentAction(gen)
        if act:
            for fcu in act.fcurves:
                prop = getProp(fcu.data_path)
                if prop in props:
                    fcurves[prop] = fcu
        return fcurves

    def setFcurve(self, rna, path, fcu):
        rna.keyframe_insert(path)
        act = rna.animation_data.action
        fcu2 = act.fcurves.find(path)
        fcu2.keyframe_points.clear()
        for frame in range(self.frame_start, self.frame_end+1):
            value = fcu.evaluate(frame)
            fcu2.keyframe_points.insert(frame, value, options={'FAST'})

    def removePropFcurves(self, act):
        for fcu in list(act.fcurves):
            if isPropRef(fcu.data_path):
                act.fcurves.remove(fcu)

#-------------------------------------------------------------
#   Unmute control rig
#-------------------------------------------------------------

class DAZ_OT_UnmuteControlRig(ControlRigMuter, Framer):
    bl_idname = "daz.unmute_control_rig"
    bl_label = "Unmute Control Rig"
    bl_description = "Enable drivers and copy location/rotation constraints"
    bl_options = {'UNDO'}

    useClear : BoolProperty(
        name = "Clear action",
        description = "Clear the current action",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useClear")

    def run(self, context):
        from .driver import addDriver
        rig = context.object
        gen = self.getControlRig(rig)
        if gen is None:
            raise DazError("No control rig found")
        gen.hide_set(False)
        self.muteConstraints(rig, False)
        meshes = getShapeChildren(rig)
        props = self.getProps(rig, gen)
        if self.useClear and rig.animation_data:
            rig.animation_data.action = None
            unit = Matrix()
            rig.matrix_world = unit
            for pb in rig.pose.bones:
                pb.matrix_basis = unit
        for prop in props.keys():
            final = finalProp(prop)
            addDriver(rig, propRef(prop), gen, propRef(prop), "x")
        if self.useShapekeys:
            for ob in meshes:
                skeys = ob.data.shape_keys
                if self.useClear and skeys.animation_data:
                    skeys.animation_data.action = None
                for skey in skeys.key_blocks:
                    final = finalProp(skey.name)
                    if final in rig.data.keys():
                        addDriver(skeys, 'key_blocks["%s"].value' % skey.name, rig.data, propRef(final), "x")


#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_BakeShapekeys,
    DAZ_OT_MuteControlRig,
    DAZ_OT_UnmuteControlRig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
