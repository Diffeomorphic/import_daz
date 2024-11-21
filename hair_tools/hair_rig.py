# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import numpy as np
from ..error import *
from ..utils import *
from ..fix import GizmoUser
from .make_hair import Separator

# ---------------------------------------------------------------------
#   Add Hair Rig
# ---------------------------------------------------------------------

class HairBoneInfo:
    def __init__(self, bones, weights, xaxis, hairs):
        self.bones = bones
        self.weights = weights
        self.xaxis = xaxis
        self.hairs = hairs


class DAZ_OT_AddHairRig(DazPropsOperator, Separator, GizmoUser, IsMesh):
    bl_idname = "daz.add_hair_rig"
    bl_label = "Add Hair Rig"
    bl_description = "Add an armature to mesh hair"
    bl_options = {'UNDO'}

    useSeparateLoose = True
    sparsity = 1
    gizmoFile = "knuckle"

    nSectors : IntProperty(
        name = "Sectors",
        description = "Number of sectors",
        min = 2, max = 36,
        default = 12)

    sectorOffset : IntProperty(
        name = "Sector Offset",
        description = "Angle to beginning of first sector",
        min = 0, max = 90,
        default = 0)

    hairLength : IntProperty(
        name = "Hair Length",
        description = "Number of bones in a hair",
        min = 2, max = 10,
        default = 5)

    keepVertexNumbers : BoolProperty(
        name = "Keep Vertex Numbers",
        description = "Keep vertex numbers.\nThis is necessary for hair proxy meshes",
        default = True)

    controlMethod : EnumProperty(
        items = [('NONE', "None", "Don't add control bones"),
                 ('IK', "IK", "IK controls"),
                 ('BBONE', "Bendy Bones", "Bendy bones"),
                 ('WINDER', "Winder", "Winder")],
        name = "Control Method",
        description = "Method for controlling hair posing",
        default = 'NONE')

    useHideBones : BoolProperty(
        name = "Hide IK Deform Bones",
        description = "Hide the deform bones if using IK",
        default = True)

    useSeparateRig : BoolProperty(
        name = "Separate Hair Rig",
        description = "Make a separate rig parented to the head bone,\ninstead of adding bones to the main rig",
        default = True)

    headName : StringProperty(
        name = "Head",
        description = "Name of the head bone",
        default = "head")

    useVertexGroups : BoolProperty(
        name = "Vertex Groups",
        description = "Create vertex groups based on Z coordinate",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "nSectors")
        self.layout.prop(self, "sectorOffset")
        self.layout.prop(self, "hairLength")
        self.layout.prop(self, "keepVertexNumbers")
        self.layout.prop(self, "useVertexGroups")
        self.layout.prop(self, "controlMethod")
        if self.controlMethod == 'IK':
            self.layout.prop(self, "useHideBones")
        if False and self.controlMethod != 'BBONE':
            self.layout.prop(self, "useSeparateRig")
        self.layout.prop(self, "useCheckStrips")
        self.layout.prop(self, "headName")


    def run(self, context):
        ob = context.object
        hairname = ob.name
        rig = ob.parent
        if rig is None:
            raise DazError("No rig found")
        if rig is None or rig.type != 'ARMATURE':
            raise DazError("Hair must have an armature")
        if self.headName not in rig.data.bones.keys():
            raise DazError('No head bone named "%s"' % self.headName)
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            ob.modifiers.remove(mod)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

        # Remove old vertex groups
        for vgrp in list(ob.vertex_groups):
            if vgrp.name not in ["Root Distance"]:
                ob.vertex_groups.remove(vgrp)

        # Create a separate hair rig
        if self.useSeparateRig or self.controlMethod == 'BBONE':
            rig = self.addSeparateRig(context, hairname, rig)

        # Duplicate mesh and store original vertex number in an attribute
        self.startGizmos(context, rig)
        activateObject(context, ob)
        origMesh = None
        if self.keepVertexNumbers and not BLENDER3:
            bpy.ops.object.duplicate()
            for ob1 in getSelectedMeshes(context):
                if ob1 != ob:
                    origMesh = ob
                    ob = ob1
                    ob.name = "DUPLI"
                    break
            activateObject(context, ob)
        if origMesh:
            self.storeOrigVerts(ob)

        # Divide hair into sectors
        hairs = self.getMeshHairs(context, ob, None)
        sectors = {}
        for hair in hairs:
            data = self.getAngleCoord(hair)
            angle = data[0] - self.sectorOffset
            key = int(math.floor(self.nSectors*angle/360 + 0.5))
            if key >= self.nSectors:
                key -= self.nSectors
            elif key < 0:
                key += self.nSectors
            if key not in sectors.keys():
                sectors[key] = []
            sectors[key].append((hair,data))
        activateObject(context, rig)

        # Build deform bones and compute weights
        setMode('EDIT')
        head = rig.data.edit_bones[self.headName]
        binbones = {}
        for key,sector in sectors.items():
            binbones[key] = self.buildBones(context, key, sector, head, rig)

        # Build control bones
        if self.controlMethod == 'IK':
            for key,bininfo in binbones.items():
                self.addIkBone(key, bininfo, head, rig)
        elif self.controlMethod == 'BBONE':
            for key,bininfo in binbones.items():
                self.addBendyBones(key, bininfo, head, rig)
            rig.data.display_type = 'BBONE'
        #self.addSkull(rig, binbones)

        setMode('OBJECT')
        hairs = []
        for key,bininfo in binbones.items():
            hair = self.mergeObjects(context, bininfo.hairs, "Sector %d" % key)
            bininfo.hairs = [hair]
            hairs.append(hair)
        for key,bininfo in binbones.items():
            self.hideBones(bininfo, rig)

        # Add vertex groups
        if self.useVertexGroups:
            for key,bininfo in binbones.items():
                self.buildVertexGroups(key, bininfo)

        # Add constraints for control bones
        if self.controlMethod == 'IK':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for key,bininfo in binbones.items():
                self.addIkConstraint(key, bininfo, rig, gizmo)
        elif self.controlMethod == 'BBONE':
            for key,bininfo in binbones.items():
                self.addBendyConstraints(key, bininfo, rig)
        elif False and self.controlMethod == 'NONE':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for bininfo in binbones.values():
                self.addAutoIk(bininfo, rig, gizmo)
        elif self.controlMethod == 'WINDER':
            from ..winder import addWinder
            self.makeGizmos(False, ["GZM_Knuckle"])
            gizmo = self.gizmos["GZM_Knuckle"]
            activateObject(context, rig)
            for key,bininfo in binbones.items():
                bnames = [bone[0] for bone in bininfo.bones]
                windname = "Wind_%s" % bnames[0]
                layers = [T_WIDGETS, T_HIDDEN]
                addWinder(rig, windname, bnames, layers, gizmo=gizmo, useLocation=True, xaxis=bininfo.xaxis)
            activateObject(context, ob)

       # Merge rigs
        ob = self.mergeObjects(context, hairs, hairname)
        if origMesh:
            self.restoreOrigVerts(origMesh, ob)
            deleteObjects(context, [ob])
            ob = origMesh

        self.makeEnvelope(context, ob, rig)
        activateObject(context, ob)
        wmat = ob.matrix_world.copy()
        ob.parent = rig
        ob.parent_type = 'OBJECT'
        if self.useVertexGroups:
            addArmatureModifier(ob, rig, "Armature Hair")
        setWorldMatrix(ob, wmat)
        bpy.ops.object.transform_apply()
        enableRigNumLayer(rig, T_WIDGETS)
        enableRigNumLayer(rig, T_HIDDEN, False)


    def mergeObjects(self, context, hairs, hairname):
        print("Merge %d objects to %s" % (len(hairs), hairs[0].name))
        activateObject(context, hairs[0])
        for hair in hairs:
            hair.select_set(True)
        bpy.ops.object.join()
        ob = context.object
        ob.name = hairname
        bpy.ops.object.shade_smooth()
        return ob


    def storeOrigVerts(self, ob):
        ovi:Attribute = ob.data.attributes.new("orig_vertex", 'INT', 'POINT')
        for v in ob.data.vertices:
            ovi.data[v.index].value = v.index


    def restoreOrigVerts(self, origMesh, ob):
        origMesh.vertex_groups.clear()
        weights = {}
        ngrps = {}
        for gn,vgrp in enumerate(ob.vertex_groups):
            ngrp = origMesh.vertex_groups.new(name = vgrp.name)
            ngrps[gn] = ngrp
        for v in ob.data.vertices:
            weights[v.index] = dict([(g.group, g.weight) for g in v.groups])
        ovi = ob.data.attributes["orig_vertex"]
        for vn,elt in enumerate(ovi.data):
            ovn = elt.value
            for gn,w in weights[vn].items():
                ngrps[gn].add([ovn], w, 'REPLACE')


    def makeEnvelope(self, context, ob, rig):
        for bone in rig.data.bones:
            if bone.name == "Skull":
                bone.envelope_distance = 10*GS.scale
                bone.head_radius = 3*GS.scale
                bone.tail_radius = 3*GS.scale
            elif bone.use_deform:
                bone.envelope_distance = 50*GS.scale/self.nSectors
                bone.head_radius = 20*GS.scale/self.nSectors
                bone.tail_radius = 20*GS.scale/self.nSectors
            else:
                bone.envelope_distance = 0.1*GS.scale
                bone.head_radius = 0.1*GS.scale
                bone.tail_radius = 0.1*GS.scale


    def addSeparateRig(self, context, hairname, rig):
        rigname = "%s Rig" % hairname
        amt = bpy.data.armatures.new(rigname)
        hairrig = bpy.data.objects.new(rigname, amt)
        hairrig.parent = rig
        hairrig.parent_type = 'BONE'
        hairrig.parent_bone = self.headName
        hairrig.show_in_front = True
        for coll in bpy.data.collections:
            if rig.name in coll.objects:
                coll.objects.link(hairrig)
        activateObject(context, rig)
        setMode('EDIT')
        eb = rig.data.edit_bones[self.headName]
        head = eb.head.copy()
        tail = eb.tail.copy()
        roll = eb.roll
        setMode('OBJECT')
        activateObject(context, hairrig)
        setWorldMatrix(hairrig, rig.matrix_world)
        bpy.ops.object.transform_apply()
        setMode('EDIT')
        eb = amt.edit_bones.new(self.headName)
        eb.head = head
        eb.tail = tail
        eb.roll = roll
        setMode('OBJECT')
        hairrig.data.display_type = 'STICK'
        hairrig.lock_location = TTrue
        bone = amt.bones[self.headName]
        enableBoneNumLayer(bone, hairrig, T_HIDDEN)
        return hairrig


    def getAngleCoord(self, hair):
        coord = np.array([list(v.co) for v in hair.data.vertices])
        x,y,z = np.average(coord, axis=0)
        angle = math.atan2(y, x)/D
        if angle < 0:
            angle += 360
        return angle,coord


    def buildBones(self, context, key, sector, head, rig):
        from ..bone import setRoll
        hair,data = sector[0]
        coord = data[1]
        hairs = [hair]
        for hair,data in sector[1:]:
            coord = np.append(coord, data[1], axis=0)
            hairs.append(hair)
        z = coord[:,2]
        zmin = np.min(z)
        zmax = np.max(z)
        dz = (zmax - zmin)/self.hairLength
        npoints = self.hairLength+1
        joints = []
        for n in range(npoints):
            c = zmax - n*dz - 0.5*dz
            idxs = np.argwhere(np.abs(z-c) <= dz)
            batch = coord[idxs]
            r = np.average(batch, axis=0)
            r = r.reshape((3,))
            if n == 0:
                r[0] = 0
            else:
                r[2] = zmax - n*dz
            joints.append(r)

        angle = (key*360/self.nSectors + self.sectorOffset)
        x = math.cos(angle*D)
        y = math.sin(angle*D)
        arrow = np.array((x,y,0))
        c = np.array(head.tail)
        dr = coord-c
        dr[:,2] = 0
        norm = np.linalg.norm(dr, axis=1)
        nmin = np.min(norm)
        nmax = np.max(norm)
        rmin = np.array((nmin*x + c[0], nmin*y + c[1], zmax))
        rmax = np.array((nmax*x + c[0], nmax*y + c[1], zmin))
        e1 = rmin - c
        e2 = rmax - c
        xaxis = Vector(np.cross(e1, e2))
        xaxis.normalize()

        weights = np.zeros((coord.shape[0], npoints), dtype=float)
        c = zmax - 0.5*dz
        weights[:,0] = np.clip((z-c)/dz, 0.0, 1.0)
        for n in range(1,npoints):
            c = zmax - n*dz + 0.5*dz
            weights[:,n] = np.clip(1-np.abs(z-c)/dz, 0.0, 1.0)
        idxs = np.argwhere(z < zmin + 0.5*dz)
        weights[idxs,npoints-1] = 1.0
        idxs = np.argwhere(np.dot(coord, arrow) < 0)
        weights[idxs,:] = 0
        weights[idxs,0] = 1.0

        bones = []
        locs = []
        parent = head
        r0 = joints[0]
        for n,r1 in enumerate(joints[1:]):
            bname = "Hair_%d_%d" % (key, n)
            eb = rig.data.edit_bones.new(bname)
            eb.head = r0
            eb.tail = r1
            if self.controlMethod == 'WINDER':
                setRoll(eb, xaxis)
            eb.parent = parent
            if n > 0:
                eb.use_connect = True
            bones.append((bname, r0, r1))
            r0 = r1
            parent = eb

        return HairBoneInfo(bones, weights, xaxis, hairs)


    def getIkName(self, key):
        return "Hair_%d_IK" % key


    def addIkBone(self, key, bininfo, head, rig):
        def normalize(v):
            return v/np.linalg.norm(v)

        lastname,r0,r1 = bininfo.bones[-1]
        eb = rig.data.edit_bones.new(self.getIkName(key))
        eb.head = r1
        eb.tail = r1 + rig.DazScale*normalize(r1-r0)
        eb.parent = head


    def getHandleName(self, key, n):
        return "Handle_%d_%d" % (key, n)


    def addBendyBones(self, key, bininfo, head, rig):
        def addHandle(n):
            handle = rig.data.edit_bones.new(self.getHandleName(key, n))
            handle.head = r0 - eps*dr
            handle.tail = r0 + eps*dr
            handle.use_connect = False
            handle.parent = None
            return handle

        eps = 0.05
        bb = None
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            dr = r1 - r0
            if bb:
                bb.tail = r0 - eps*dr
            bb = rig.data.edit_bones[bname]
            bb.use_connect = False
            handle = addHandle(n)
            bb.parent = handle
            bb.head = r0 + eps*dr
        r0 = r1
        bb.tail = r0 - eps*dr
        handle = addHandle(len(bininfo.bones))


    def addSkull(self, rig, binbones):
        centers = []
        for bininfo in binbones.values():
            centers.append(bininfo.bones[0][1])
        coord = np.array(centers)
        x,y,z = np.average(coord, axis=0)
        head = rig.data.edit_bones.get(self.headName)
        skull = rig.data.edit_bones.new("Skull")
        skull.head = (0, y-5*GS.scale, z-2*GS.scale)
        skull.tail = (0, y+5*GS.scale, z-2*GS.scale)
        skull.parent = head
        enableBoneNumLayer(skull, rig, T_HIDDEN)


    def addAutoIk(self, bininfo, rig, gizmo):
        lname,r0,r1 = bininfo.bones[-1]
        pb = rig.pose.bones[lname]
        pb.custom_shape = gizmo
        setCustomShapeTransform(pb, self.hairLength/25)


    def addIkConstraint(self, key, bininfo, rig, gizmo):
        ikname = self.getIkName(key)
        lastname,r0,r1 = bininfo.bones[-1]
        pb = rig.pose.bones[lastname]
        cns = pb.constraints.new('IK')
        cns.name = "IK %s" % ikname
        cns.target = rig
        cns.subtarget = ikname
        cns.chain_count = len(bininfo.bones)
        cns.use_location = True
        cns.use_rotation = True
        pb = rig.pose.bones[ikname]
        pb.bone.show_wire = True
        pb.custom_shape = gizmo
        pb.bone.use_deform = False
        enableBoneNumLayer(pb.bone, rig, T_WIDGETS)


    def addBendyConstraints(self, key, bininfo, rig):
        def getHandle(n):
            handlename = self.getHandleName(key, n)
            handle = rig.pose.bones[handlename]
            handle.bone.bbone_x = handleSize
            handle.bone.bbone_z = handleSize
            handle.bone.use_deform = False
            return handle

        from ..rig_utils import stretchTo
        bboneSize = 0.1*GS.scale
        handleSize = 0.5*GS.scale

        rig.data.display_type = 'BBONE'
        head = rig.data.bones[self.headName]
        head.bbone_x = 1*GS.scale
        head.bbone_z = 1*GS.scale
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            bone = rig.data.bones[bname]
            enableBoneNumLayer(bone, rig, T_WIDGETS)

        handle = getHandle(0)
        enableBoneNumLayer(handle, rig, T_WIDGETS)
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            pb = rig.pose.bones[bname]
            lockAllTransforms(pb)
            pb.bone.bbone_segments = 6
            pb.bone.bbone_x = bboneSize
            pb.bone.bbone_z = bboneSize
            pb.bone.bbone_handle_type_start = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_start = handle.bone
            handle = getHandle(n+1)
            enableBoneNumLayer(handle, rig, T_WIDGETS)
            pb.bone.bbone_handle_type_end = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_end = handle.bone
            stretchTo(pb, handle, rig)
            pb.bone.hide_select = True


    def hideBones(self, bininfo, rig):
        if self.controlMethod == 'IK' and self.useHideBones:
            layer = T_HIDDEN
        else:
            layer = T_WIDGETS
        for bname,r0,r1 in bininfo.bones:
            bone = rig.data.bones[bname]
            enableBoneNumLayer(bone, rig, layer)


    def buildVertexGroups(self, key, bininfo):
        print("Build sector %d weights: %d" % (key, len(bininfo.hairs)))
        for hair in bininfo.hairs:
            hgrp = hair.vertex_groups.new(name=self.headName)
            vgrps = [hgrp]
            for bname,r0,r1 in bininfo.bones:
                vgrp = hair.vertex_groups.new(name=bname)
                vgrps.append(vgrp)
            weights = bininfo.weights
            for gn,vgrp in enumerate(vgrps):
                for vn,w in enumerate(weights[:,gn]):
                    if w > 0.001:
                        vgrp.add([vn], w, 'REPLACE')


def addArmatureModifier(ob, rig, modname):
    from ..store import addModifierFirst
    mod = getModifier(ob, 'ARMATURE')
    if mod is None:
        mod = addModifierFirst(ob, modname, 'ARMATURE')
        mod.object = rig
    else:
        mod.object = rig
        mod.name = modname

# ---------------------------------------------------------------------
#   Add Hair Rig
# ---------------------------------------------------------------------

class DAZ_OT_SetEnvelopes(DazPropsOperator, IsArmature):
    bl_idname = "daz.set_envelopes"
    bl_label = "Set Envelopes"
    bl_description = "Change the envelopes of all deform bones"
    bl_options = {'UNDO'}

    envelope_distance : FloatProperty(
        name = "Distance",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    head_radius : FloatProperty(
        name = "Head Radius",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    tail_radius : FloatProperty(
        name = "Tail Radius",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    def draw(self, context):
        self.layout.prop(self, "envelope_distance")
        self.layout.prop(self, "head_radius")
        self.layout.prop(self, "tail_radius")

    def invoke(self, context, event):
        rig = context.object
        for bone in rig.data.bones:
            if isHairBone(bone):
                self.envelope_distance = bone.envelope_distance
                self.head_radius = bone.head_radius
                self.tail_radius = bone.tail_radius
                break
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        rig = context.object
        for bone in rig.data.bones:
            if isHairBone(bone):
                bone.envelope_distance = self.envelope_distance
                bone.head_radius = self.head_radius
                bone.tail_radius = self.tail_radius

# ---------------------------------------------------------------------
#   Toggle Hair Locks
# ---------------------------------------------------------------------

class DAZ_OT_ToggleHairLocks(DazOperator, IsArmature):
    bl_idname = "daz.toggle_hair_locks"
    bl_label = "Toggle Hair Locks"
    bl_description = "Disable/enable locking of all deform bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        lock = None
        for bone in rig.data.bones:
            if isHairBone(bone):
                if lock is None:
                    lock = (not bone.hide_select)
                bone.hide_select = lock


def isHairBone(bone):
    words = bone.name.split("_")
    return (bone.use_deform and
            len(words) >= 3 and
            words[1].isdigit() and
            words[2].isdigit())

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_AddHairRig,
    DAZ_OT_SetEnvelopes,
    DAZ_OT_ToggleHairLocks,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
