# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import *
from ..error import *
from ..utils import *
from ..framer import Framer

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
#   Bake deform rig
#-------------------------------------------------------------

class ControlRigMuter(Framer):
    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Mute/unmute shapekeys too",
        default = True)

    useMuteAll : BoolProperty(
        name = "All Constraints",
        description = "Mute/unmute all bone constraints, not just copy transform",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useShapekeys")
        self.layout.prop(self, "useMuteAll")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not dazRna(ob).DazRig.startswith(("mhx", "rigify")))


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


    def getProps(self, rig, gen):
        props = {}
        for prop in rig.keys():
            final = finalProp(prop)
            if final in gen.data.keys():
                props[prop] = gen.data[final]
        return props


    def muteConstraints(self, rig, mute):
        for pb in rig.pose.bones:
            if dazRna(pb).DazSharedBone:
                continue
            for cns in pb.constraints:
                if self.useMuteAll or cns.type.startswith("COPY"):
                    if cns.target == rig:
                        cns.mute = not mute
                    else:
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
#   Mute control rig
#-------------------------------------------------------------

class DAZ_OT_MuteControlRig(ControlRigMuter):
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
        activateObject(context, rig)
        gen = self.getControlRig(rig)
        act = getCurrentAction(gen)
        if act:
            actname = act.name
        else:
            actname = "Action"
        meshes = getShapeChildren(rig)
        drvmatss = self.getDrivenMatrices(context, rig)
        bpy.ops.nla.bake(frame_start=self.frame_start,
                         frame_end=self.frame_end,
                         only_selected=False,
                         visual_keying=True,
                         bake_types={'OBJECT', 'POSE'})
        self.setDrivenMatrices(context, rig, drvmatss)

        act = getCurrentAction(rig)
        shared = dict([(pb.name, pb) for pb in rig.pose.bones
                        if dazRna(pb).DazSharedBone])
        fcurves = getActionFcurves(act)
        for fcu in list(fcurves):
            bname,channel,cnsname = getBoneChannel(fcu)
            if (bname in shared.keys() or
                channel is None or
                channel.startswith("Daz")):
                fcurves.remove(fcu)
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
        fstruct = {}
        act = getCurrentAction(gen)
        if act:
            fcurves = getActionFcurves(act)
            for fcu in fcurves:
                prop = getProp(fcu.data_path)
                if prop in props:
                    fstruct[prop] = fcu
        return fstruct


    def setFcurve(self, rna, path, fcu):
        rna.keyframe_insert(path)
        fcurves = getActionBag(rna.animation_data.action, rna.id_type).fcurves
        fcu2 = fcurves.find(path)
        fcu2.keyframe_points.clear()
        for frame in range(self.frame_start, self.frame_end+1):
            value = fcu.evaluate(frame)
            fcu2.keyframe_points.insert(frame, value, options={'FAST'})


    def getDrivenMatrices(self, context, rig):
        scn = context.scene
        drvmatss = []
        for frame in range(self.frame_start, self.frame_end+1):
            drvmats = []
            drvmatss.append((frame, drvmats))
            scn.frame_current = frame
            updateScene(context)
            for pb in rig.pose.bones:
                drvb = rig.pose.bones.get(drvBone(pb.name, True))
                if drvb:
                    drvmats.append((pb, drvb, drvb.matrix_basis.copy()))
        return drvmatss


    def setDrivenMatrices(self, context, rig, drvmatss):
        scn = context.scene
        for frame,drvmats in drvmatss:
            scn.frame_current = frame
            updateScene(context)
            for pb,drvb,drvmat in drvmats:
                pb.matrix_basis = drvmat.inverted() @ pb.matrix_basis
                trunc2Default(pb, "location", 0, GS.scale*1e-4)
                pb.keyframe_insert("location", frame=frame)
                drvb.keyframe_delete("location", frame=frame)
                trunc2Default(drvb, "location", 0, GS.scale*1e-4)
                if pb.rotation_mode == 'QUATERNION':
                    pb.keyframe_insert("rotation_quaternion", frame=frame)
                    drvb.keyframe_delete("rotation_quaternion", frame=frame)
                else:
                    trunc2Default(pb, "rotation_euler", 0, 1e-4)
                    pb.keyframe_insert("rotation_euler", frame=frame)
                    drvb.keyframe_delete("rotation_euler", frame=frame)
                    trunc2Default(drvb, "rotation_euler", 0, 1e-4)
                trunc2Default(pb, "scale", 1, 1e-4)
                pb.keyframe_insert("scale", frame=frame)
                drvb.keyframe_delete("scale", frame=frame)
                trunc2Default(drvb, "scale", 1, 1e-4)

#-------------------------------------------------------------
#   Unmute control rig
#-------------------------------------------------------------

class DAZ_OT_UnmuteControlRig(ControlRigMuter):
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
        ControlRigMuter.draw(self, context)

    def run(self, context):
        from ..driver import addDriver
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
