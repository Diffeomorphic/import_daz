# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..fix import *
from ..pin import Pinner
from ..winder import addWinder

import math

#-------------------------------------------------------------
#   Select seg01
#-------------------------------------------------------------

class DAZ_OT_SelectMatchingBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.select_matching_bones"
    bl_label = "Select Matching Bones"
    bl_description = "Select bones with matching names"
    bl_options = {'UNDO'}

    match : StringProperty(
        name = "Match",
        description = "Select all bones with matching names",
        default = "seg01")

    def draw(self, context):
        self.layout.prop(self, "match")

    def run(self, context):
        match = self.match.lower()
        for rig in getSelectedArmatures(context):
            for bone in rig.data.bones:
                bone.select = (match in bone.name.lower())

#-------------------------------------------------------------
#   Lock channels
#-------------------------------------------------------------

class DAZ_OT_LockChannels(DazPropsOperator, IsObject):
    bl_idname = "daz.lock_channels"
    bl_label = "Lock Channels"
    bl_description = "Lock certain channels"
    bl_options = {'UNDO'}

    useNonzero : BoolProperty(
        name = "Nonzero Channels",
        description = "Don't lock non-zero channels",
        default = True)

    useTwist : BoolProperty(
        name = "Twist",
        description = "Don't lcok local Y rotation",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useNonzero")
        self.layout.prop(self, "useTwist")

    def run(self, context):
        def lockAll(pb, channel, lockchannel, default):
            values = getattr(pb, channel)
            locks = getattr(pb, lockchannel)
            for n in range(3):
                if not self.useNonzero or abs(values[n]-default) < 1e-7:
                    locks[n] = True
                    values[n] = default

        for ob in getSelectedObjects(context):
            lockAll(ob, "location", "lock_location", 0)
            lockAll(ob, "rotation_euler", "lock_rotation", 0)
            lockAll(ob, "scale", "lock_scale", 1)
            if ob.type == 'ARMATURE':
                for pb in ob.pose.bones:
                    lockAll(pb, "location", "lock_location", 0)
                    lockAll(pb, "rotation_euler", "lock_rotation", 0)
                    lockAll(pb, "scale", "lock_scale", 1)
                    if self.useTwist:
                        pb.lock_rotation[1] = False

#-------------------------------------------------------------
#   Clear center
#-------------------------------------------------------------

class DAZ_OT_ClearCenter(DazOperator, IsObject):
    bl_idname = "daz.clear_center"
    bl_label = "Clear Center"
    bl_description = "Move object to DAZ center"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedObjects(context):
            if ob.parent is None:
                ob.location = d2b(ob.DazCenter)
            ob.DazCenter = Zero
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

#-------------------------------------------------------------
#   Add IK goals
#-------------------------------------------------------------

class DAZ_OT_AddIkGoals(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_ik_goals"
    bl_label = "Add IK goals"
    bl_description = "Add IK goals"
    bl_options = {'UNDO'}

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains",
        default = False)

    hideBones : BoolProperty(
        name = "Hide Bones",
        description = "Hide all bones in the IK chains",
        default = False)

    lockBones : BoolProperty(
        name = "Lock Bones",
        description = "Lock all bones in the IK chains",
        default = False)

    disableBones : BoolProperty(
        name = "Disable Bones",
        description = "Disable all bones in the IK chains",
        default = False)

    fromRoots : BoolProperty(
        name = "From Root Bones",
        description = "Select IK chains from root bones",
        default = True)

    ikTargetParent : EnumProperty(
        items = [('NONE', "None", "IK targets not parented"),
                 ('IMMEDIATE', "Immediate", "Parent IK targets to root bones' immediate parent"),
                 ('ULTIMATE', "Ultimate", "Parent IK targets to root bones' ultimate parent")],
        name = "IK Target Parents",
        description = "IK targets parents",
        default = 'NONE')

    onlyConnected : BoolProperty(
        name = "Only Connected Bones",
        description = "Stop IK chain at disconnected bones",
        default = True)

    useDeleteDisconnected : BoolProperty(
        name = "Delete Disconnected",
        description = "Delete disconnected bones and their vertex groups",
        default = False)

    threshold : FloatProperty(
        name = "Threshold",
        description = "Threshold for stopping the IK chain",
        min = 0,
        default = 0.01)

    def draw(self, context):
        self.layout.prop(self, "fromRoots")
        self.layout.prop(self, "ikTargetParent")
        self.layout.prop(self, "onlyConnected")
        if self.onlyConnected:
            self.layout.prop(self, "threshold")
            self.layout.prop(self, "useDeleteDisconnected")
        self.layout.separator()
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "hideBones")
        self.layout.prop(self, "lockBones")
        self.layout.prop(self, "disableBones")


    def ikGoalsFromSelected(self, rig):
        ikgoals = []
        for pb in rig.pose.bones:
            if pb.bone.select and not pb.children:
                clen = 0
                par = pb
                pbones = []
                while par and par.bone.select:
                    pbones.append(par)
                    clen += 1
                    par = par.parent
                if clen > 2:
                    root = pbones[-1]
                    pbones = pbones[:-1]
                    ikgoals.append((pb.name, clen-1, pbones, root.name))
        return ikgoals, []


    def ikGoalsFromRoots(self, rig):
        def nostop(pb):
            if len(pb.children) != 1:
                return False
            elif self.onlyConnected:
                child = pb.children[0]
                return ((child.head-pb.tail).length < self.threshold)
            return True

        ikgoals = []
        deletes = []
        for root in rig.pose.bones:
            if root.bone.select:
                clen = 0
                pbones = []
                pb = root
                while pb and nostop(pb):
                    pb = pb.children[0]
                    pbones.append(pb)
                    clen += 1
                if clen > 2:
                    ikgoals.append((pb.name, clen-1, pbones, root.name))
                    if self.useDeleteDisconnected:
                        while pb and len(pb.children) == 1:
                            pb = pb.children[0]
                            deletes.append(pb.name)
        return ikgoals, deletes


    def run(self, context):
        for rig in getSelectedArmatures(context):
            activateObject(context, rig)
            self.addIkGoals(context, rig)


    def addIkGoals(self, context, rig):
        if self.fromRoots:
            ikgoals,deletes = self.ikGoalsFromRoots(rig)
        else:
            ikgoals,deletes = self.ikGoalsFromSelected(rig)

        setMode('EDIT')
        for bname, clen, pbones, rootname in ikgoals:
            root = rig.data.edit_bones[rootname]
            eb = rig.data.edit_bones[bname]
            goalname = self.combineName(bname, "Goal")
            goal = rig.data.edit_bones.new(goalname)
            goal.head = eb.tail
            goal.tail = 2*eb.tail - eb.head
            goal.roll = eb.roll
            if self.ikTargetParent == 'IMMEDIATE':
                goal.parent = root.parent
            elif self.ikTargetParent == 'ULTIMATE':
                parent = root.parent
                while parent and parent.parent:
                    parent = parent.parent
                goal.parent = parent
            if self.usePoleTargets:
                for n in range(clen//2):
                    eb = eb.parent
                polename = self.combineName(bname, "Pole")
                pole = rig.data.edit_bones.new(polename)
                pole.head = eb.head + eb.length * eb.x_axis
                pole.tail = eb.tail + eb.length * eb.x_axis
                pole.roll = eb.roll
        if self.useDeleteDisconnected:
            for bname in deletes:
                eb = rig.data.edit_bones.get(bname)
                if eb:
                    rig.data.edit_bones.remove(eb)

        setMode('OBJECT')
        self.startGizmos(context, rig)
        gzmBall = self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        gzmCube = self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        gzmCone = self.makeEmptyGizmo("GZM_Cone", 'CONE')

        for bname, clen, pbones, rootname in ikgoals:
            if bname not in rig.pose.bones.keys():
                continue
            root = rig.pose.bones[rootname]
            pb = rig.pose.bones[bname]
            rmat = pb.bone.matrix_local
            root.custom_shape = gzmCube

            goalname = self.combineName(bname, "Goal")
            goal = rig.pose.bones[goalname]
            goal.rotation_mode = pb.rotation_mode
            goal.bone.use_local_location = True
            goal.matrix_basis = rmat.inverted() @ pb.matrix
            goal.custom_shape = gzmBall

            if self.usePoleTargets:
                pole = rig.pose.bones[polename]
                pole.rotation_mode = pb.rotation_mode
                pole.bone.use_local_location = True
                pole.matrix_basis = rmat.inverted() @ pb.matrix
                pole.custom_shape = gzmCone

            cns = getConstraint(pb, 'IK')
            if cns:
                pb.constraints.remove(cns)
            cns = pb.constraints.new('IK')
            cns.name = "IK %s" % goalname
            cns.target = rig
            cns.subtarget = goalname
            cns.chain_count = clen
            cns.use_location = True
            if self.usePoleTargets:
                cns.pole_target = rig
                cns.pole_subtarget = polename
                cns.pole_angle = 0*D
                cns.use_rotation = False
            else:
                cns.use_rotation = True

            if self.hideBones:
                for pb in pbones:
                    pb.bone.hide = True
            if self.lockBones:
                for pb in pbones:
                    lockAllTransform(pb)
            if self.disableBones:
                for pb in pbones:
                    pb.bone.hide_select = True

        if self.useDeleteDisconnected:
            setMode('OBJECT')
            for ob in getMeshChildren(rig):
                if not activateObject(context, ob):
                    continue
                setMode('EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                vgnums = []
                for vgname in deletes:
                    vgrp = ob.vertex_groups.get(vgname)
                    if vgrp:
                        vgnums.append(vgrp.index)
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group in vgnums and g.weight > 0.5:
                            v.select = True
                            break
                bpy.ops.mesh.delete(type='VERT')
                setMode('OBJECT')
            activateObject(context, rig)


    def combineName(self, bname, string):
        if bname[-2:].lower() in [".l", ".r", "_l", "_r"]:
            return "%s%s%s" % (bname[:-2], string, bname[-2:])
        else:
            return "%s%s" % (bname, string)

#-------------------------------------------------------------
#   Add Winder
#-------------------------------------------------------------

class DAZ_OT_AddWinders(Pinner, DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_winders"
    bl_label = "Add Winders"
    bl_description = "Add winders to selected posebones"
    bl_options = {'UNDO'}

    gizmoFile = "knuckle"

    winderLayer : IntProperty(
        name = "Winder Layer",
        description = "Bone layer for the winder bones",
        min = 1, max = 32,
        default = 1)

    windedLayer : IntProperty(
        name = "Winded Layer",
        description = "Bone layer for the winded bones",
        min = 1, max = 32,
        default = 2)

    useBaseLocation : BoolProperty(
        name = "Base Location",
        description = "Add driver for location of base bone",
        default = False)

    useLocation : BoolProperty(
        name = "Location",
        description = "Add driver for location of other bones",
        default = False)

    useScale : BoolProperty(
        name = "Scale",
        description = "Add driver for scale",
        default = False)

    strength : FloatProperty(
        name = "Strength",
        description = "An overall strength factor for copy rotation influence",
        min = 0.0, max = 5.0,
        default = 1.0)

    def draw(self, context):
        Pinner.draw(self, context)
        self.layout.prop(self, "strength")
        if BLENDER3:
            self.layout.prop(self, "winderLayer")
            self.layout.prop(self, "windedLayer")
        self.layout.prop(self, "useBaseLocation")
        self.layout.prop(self, "useLocation")
        self.layout.prop(self, "useScale")

    def invoke(self, context, event):
        if BLENDER3:
            rig = context.object
            if rig and rig.DazRig == "mhx":
                self.winderLayer = 17
                self.windedLayer = 18
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        def findChildren(pb):
            bnames = []
            while len(pb.children) == 1:
                bnames.append(pb.name)
                pb = pb.children[0]
            bnames.append(pb.name)
            return bnames

        rig = context.object
        node = self.getCurveMapping()
        cu = node.mapping.curves[3]
        self.startGizmos(context, rig)
        self.makeGizmos(False, ["GZM_Knuckle"])
        gizmo = self.gizmos["GZM_Knuckle"]
        for root in self.findPoseRoots(rig):
            windname = "Wind_%s" % root.name
            bnames = findChildren(root)
            if BLENDER3:
                layers = [self.winderLayer-1, self.windedLayer-1]
            else:
                layers = ("Custom", "Deform")
            dx = 1.0/len(bnames)
            influs = []
            for n,bname in enumerate(bnames):
                y0 = node.mapping.evaluate(cu, n*dx)
                y1 = node.mapping.evaluate(cu, (n+1)*dx)
                infl = self.strength*max(0, y1-y0)
                influs.append(infl)
            addWinder(rig, windname, bnames, layers,
                gizmo = gizmo,
                useBaseLocation = self.useBaseLocation,
                useLocation = self.useLocation,
                useScale = self.useScale,
                influs = influs
                )


    def findPoseRoots(self, rig):
        proots = {}
        for pb in rig.pose.bones:
            if pb.bone.select and len(pb.children) == 1:
                proots[pb.name] = pb
        removes = {}
        for proot in proots.values():
            pb = proot
            while len(pb.children) == 1:
                pb = pb.children[0]
                removes[pb.name] = True
            if len(pb.children) > 0:
                removes[proot.name] = True
        for bname in removes.keys():
            if bname in proots.keys():
                del proots[bname]
        return proots.values()

#-------------------------------------------------------------
#   Add Tail
#-------------------------------------------------------------

class DAZ_OT_AddTails(DazPropsOperator, IsArmature):
    bl_idname = "daz.add_tails"
    bl_label = "Add Tails"
    bl_description = "Add tails to selected posebones"
    bl_options = {'UNDO'}

    radius : FloatProperty(
        name = "Radius",
        description = "Radius of the cloth object",
        default = 0.01)

    def run(self, context):
        for rig in getSelectedArmatures(context):
            for pb in rig.pose.bones:
                if pb.bone.select:
                    self.addTail(context, rig, pb)


    def addTail(self, context, rig, root):
        def getBones(pb):
            bnames = [pb.name]
            while len(pb.bone.children) == 1:
                pb = pb.children[0]
                bnames.append(pb.name)
            return bnames

        def addVerts(loc, mat):
            mat = mat.to_3x3()
            ex = mat.col[0]
            ez = mat.col[2]
            #return [loc+R*ex, loc+R*ez, loc-R*ex, loc-R*ez]
            return [loc.copy(), loc+R*(ez-ex), loc-2*R*ex, loc-R*(ex+ez)]

        def addFaces(n):
            return [(n-4,n-3,n+1,n), (n-3,n-2,n+2,n+1), (n-2,n-1,n+3,n+2), (n-1,n-4,n,n+3)]

        coll = getCollection(context, rig)
        bnames = getBones(root)
        nbones = len(bnames)
        verts = []
        faces = [(0,1,2,3)]
        R = self.radius
        setMode('EDIT')
        vn = 0
        for bname in bnames:
            eb = rig.data.edit_bones[bname]
            verts += addVerts(eb.head, eb.matrix)
            if vn > 0:
                faces += addFaces(vn)
                eb.parent = None
            vn += 4
        verts += addVerts(eb.tail, eb.matrix)
        faces.append((vn,vn+1,vn+2,vn+3))
        faces += addFaces(vn)
        setMode('OBJECT')

        # Make cloth object
        clothname = "%s Cloth" % rig.name
        me = bpy.data.meshes.new(clothname)
        me.from_pydata(verts, [], faces)
        cloth = bpy.data.objects.new(clothname, me)
        clothcoll = bpy.data.collections.new(clothname)
        coll.children.link(clothcoll)
        clothcoll.objects.link(cloth)
        cloth.hide_render = True
        wmat = cloth.matrix_world
        cloth.parent = rig
        if root.parent:
            cloth.parent_type = 'BONE'
            cloth.parent_bone = root.parent.name
        setWorldMatrix(cloth, wmat)

        # Pinning group
        vgrp = cloth.vertex_groups.new(name = "Pin")
        for n in range(nbones+1):
            w = max(0.1, min(1.0, (1-3*n/nbones)))
            for vn in (4*n, 4*n+1, 4*n+2, 4*n+3):
                vgrp.add([vn], w, 'REPLACE')
        # Cloth modifier
        mod = cloth.modifiers.new("Cloth", 'CLOTH')
        cset = mod.settings
        cset.mass = 1.0
        cset.quality = 20
        cset.air_damping = 1.0
        cset.tension_stiffness = 1000
        cset.shear_stiffness = 100
        cset.bending_stiffness = 10
        cset.bending_model = 'LINEAR'
        # Collision settings
        colset = mod.collision_settings
        colset.distance_min = 0.015
        colset.self_distance_min = 0.015
        colset.collision_quality = 2
        colset.use_self_collision = False
        # Pinning
        cset.vertex_group_mass = "Pin"
        cset.pin_stiffness = 1.0

        # Add empties and constraints
        emptycoll = bpy.data.collections.new("%s Empties" % rig.name)
        coll.children.link(emptycoll)

        def addEmpty(cloth, n, loc):
            activateObject(context, cloth)
            setMode('EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            cloth.data.vertices[4*n].select = True
            setMode('OBJECT')
            ename = "Empty %d" % n
            empty = bpy.data.objects.new(ename, None)
            emptycoll.objects.link(empty)
            empty.location = loc
            empty.empty_display_size = self.radius
            empty.select_set(True)
            bpy.ops.object.parent_set(type='VERTEX', keep_transform=True)
            mat = Matrix.Translation(loc)
            setWorldMatrix(empty, mat)
            empty.location = (0,0,0)
            return empty

        empties = []
        for n,bname in enumerate(bnames):
            pb = rig.pose.bones[bname]
            empty = addEmpty(cloth, n, pb.bone.head_local)
            empties.append(empty)
            cns = pb.constraints.new('COPY_LOCATION')
            cns.target = empty
        empty = addEmpty(cloth, n+1, pb.bone.tail_local)
        empties.append(empty)
        for bname,empty in zip(bnames, empties[1:]):
            pb = rig.pose.bones[bname]
            cns = pb.constraints.new('STRETCH_TO')
            #cns = pb.constraints.new('DAMPED_TRACK')
            #cns.track_axis = 'TRACK_Y'
            cns.target = empty

#-------------------------------------------------------------
#   Move Geograft bones
#-------------------------------------------------------------

class DAZ_OT_MoveGraftBones(DazOperator, IsArmature):
    bl_idname = "daz.move_graft_bones"
    bl_label = "Move Graft Bones"
    bl_description = "Move geograft bones to Tweak layer"
    bl_options = {'UNDO'}

    Bones = ["Genital base", "Anal base", "Clitoral hood base", "Labia majora", "Labia minora"]

    def run(self, context):
        def moveChildrenToTweak(pb):
            for child in pb.children:
                if child.name not in self.Bones:
                    enableBoneNumLayer(child, rig, T_TWEAK)
                    moveChildrenToTweak(child)

        rig = context.object
        for bname in self.Bones:
            pb = rig.pose.bones.get(bname)
            if pb:
                moveChildrenToTweak(pb)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_LockChannels,
    DAZ_OT_ClearCenter,
    DAZ_OT_AddIkGoals,
    DAZ_OT_AddWinders,
    DAZ_OT_AddTails,
    DAZ_OT_SelectMatchingBones,
    DAZ_OT_MoveGraftBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

