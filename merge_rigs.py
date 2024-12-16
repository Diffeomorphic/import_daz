# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Matrix
from .utils import *
from .error import *
from .driver import DriverUser
from .locks import LockEnabler

#-------------------------------------------------------------
#   Get selected rigs
#-------------------------------------------------------------

def getSelectedRigs(context):
    rig = context.object
    if rig:
        setMode('OBJECT')
    subrigs = []
    for ob in getSelectedArmatures(context):
        if ob != rig:
            subrigs.append(ob)
    return rig, subrigs

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

def getDupName(subrig, bname):
    return "%s:%s" % (subrig.name, bname)


class BoneInfo:
    def __init__(self, bone, pb, parname, wmat):
        self.head = bone.head_local.copy()
        self.tail = bone.tail_local.copy()
        self.matrix_local = bone.matrix_local.copy()
        self.parent = parname
        self.use_deform = bone.use_deform
        self.pb = pb
        self.matrix = pb.matrix.copy()
        self.matrix_world = wmat


    def setEditBone(self, bname, ebones, subrig):
        eb = ebones.new(bname)
        eb.head = self.head
        eb.tail = self.tail
        if self.matrix_world:
            eb.matrix = self.matrix_world @ self.matrix_local
        else:
            eb.matrix = self.matrix_local
        self.use_deform = self.use_deform
        if self.parent is not None:
            if self.parent in ebones.keys():
                eb.parent = ebones[self.parent]
            else:
                dupname = getDupName(subrig, self.parent)
                eb.parent = ebones.get(dupname)


    def setPoseBone(self, pb, rig):
        from .figure import copyBoneInfo
        from .store import copyConstraints
        copyBoneInfo(self.pb, pb)
        copyConstraints(self.pb, pb, rig)
        if self.matrix_world:
            #pb.matrix = self.matrix_world @ self.matrix
            pb.matrix_basis = Matrix()
        else:
            pb.matrix = self.matrix
        pb.custom_shape = self.pb.custom_shape
        if hasattr(pb, "custom_shape_translation"):
            pb.custom_shape_scale_xyz = self.pb.custom_shape_scale_xyz
            pb.custom_shape_translation = self.pb.custom_shape_translation
            pb.custom_shape_rotation_euler = self.pb.custom_shape_rotation_euler


class MergeRigsOptions:
    duplicateDistance : FloatProperty(
        name = "Duplicate Distance (cm)",
        description = "Create separate bones if several bones with the same name are found,\nand they are at least this far apart (in centimeters)",
        min = 0.0,
        default = 1.0)

    useMergeNonConforming : EnumProperty(
        items = [('NEVER', "Never", "Don't merge non-conforming bones"),
                 ('CONTROLS', "Widget Controls", "Only merge known widget controls"),
                 ('CHILDREN', "Children", "Merge non-conforming bones of child rigs"),
                 ('ALL_RIGS', "All Rigs", "Merge all non-conforming bones, even it they belong to separate figures")],
        name = "Non-conforming Rigs",
        description = "Also merge non-conforming rigs.\n(Bone parented and with no bones in common with main rig)",
        default = 'CONTROLS')

    useConvertWidgets : BoolProperty(
        name = "Convert To Widgets",
        description = "Convert face controls to bone custom shapes",
        default = True)

    useHiddenRigs : BoolProperty(
        name = "Include Hidden Rigs",
        description = "Also merge bones from armatures that are hidden",
        default = False)


class DAZ_OT_MergeRigs(DazPropsOperator, MergeRigsOptions, DriverUser, IsArmature):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    useOnlySelected : BoolProperty(
        name = "Only Selected Rigs",
        description = "Only merge armatures that are children of selected armatures",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useOnlySelected")
        self.layout.prop(self, "useHiddenRigs")
        self.layout.prop(self, "duplicateDistance")
        self.layout.prop(self, "useMergeNonConforming")
        self.layout.prop(self, "useConvertWidgets")


    def run(self, context):
        def findSelectedRoots(objects):
            roots = []
            for ob in objects:
                if ob.type == 'ARMATURE' and ob.select_get():
                    roots.append(ob)
                else:
                    roots += findSelectedRoots(ob.children)
            return roots

        self.initTmp()
        root = context.object
        roots = [ob for ob in context.view_layer.objects if ob.parent is None]
        if self.useOnlySelected:
            roots = findSelectedRoots(roots)
        if self.useMergeNonConforming == 'ALL_RIGS' and len(roots) > 1:
            if root in roots:
                subroots = [rig for rig in roots if rig != root]
            else:
                subroots = roots
            roots = [ob for ob in roots if ob not in subroots]
            for ob in subroots:
                wmat = ob.matrix_world.copy()
                ob.parent = root
                setWorldMatrix(ob, wmat)
        excluded = findExcludedObjects(context, self.useHiddenRigs)
        if self.useMergeNonConforming in ['CHILDREN', 'ALL_RIGS']:
            rootmats = applyTransformToObjects(roots, excluded)
        else:
            rootmats = []
        deletes = []
        try:
            deletes = self.mergeRigs(context, roots, excluded)
        finally:
            restoreTransformsToObjects(rootmats)
        deleteObjects(context, deletes)


    def mergeRigs(self, context, roots, excluded):
        from .fileutils import DF

        def getObjects(ob, parent, objects, infos, widgets, info):
            if ob in excluded:
                return
            if parent and parent.type == 'ARMATURE':
                objects.append((ob, parent, ob.matrix_world.copy(), ob.hide_viewport, ob.hide_get()))
                ob.hide_viewport = False
                ob.hide_set(False)
            wmat = None
            if ob.type == 'ARMATURE':
                rig = ob
                parentBone = None
                if rig.parent is None or rig.parent.type != 'ARMATURE':
                    conforms = False
                elif rig.parent_type == 'BONE':
                    conforms = False
                    if self.useMergeNonConforming in ['CHILDREN', 'ALL_RIGS']:
                        conforms = True
                    elif (self.useMergeNonConforming == 'CONTROLS' and
                          rig.DazUrl.lower() in DF.WidgetControls):
                        conforms = True
                        widgets.append(rig)
                    if conforms:
                        parentBone = rig.parent_bone
                        wmat = rig.matrix_world.copy()
                else:
                    conforms = True
                if not conforms:
                    parent = rig
                    info = []
                    infos.append(info)
                bones = {}
                for pb in rig.pose.bones:
                    bone = pb.bone
                    if bone.parent:
                        parname = bone.parent.name
                    else:
                        parname = parentBone
                    bones[bone.name] = BoneInfo(bone, pb, parname, wmat)
                meshes = [child for child in rig.children if child.type == 'MESH']
                info.append((rig, bones, meshes))
            else:
                parent = ob
            for child in ob.children:
                getObjects(child, parent, objects, infos, widgets, info)

        # Collect info about objects and bones
        objects = []
        infos = []
        widgets = []
        for root in roots:
            getObjects(root, root.parent, objects, infos, widgets, [])

        def addMergedProp(rig, subrig, idx):
            pg = rig.data.DazMergedRigs.add()
            pg.name = str(idx)
            pg.s = subrig.DazUrl
            pg.b = (subrig.parent_bone is not None)

        # Add info about merge rigs
        # Rename duplicate bones
        deletes = []
        dupss = []
        for info in infos:
            rig,bones,_meshes = info[0]
            heads = {}
            dups = {}
            dupss.append(dups)
            idx = 0
            addMergedProp(rig, rig, idx)
            for subrig,subbones,meshes in info[1:]:
                deletes.append(subrig)
                for bname,binfo in subbones.items():
                    if bname in bones.keys():
                        if binfo.use_deform:
                            bone = rig.data.bones[bname]
                            bone.use_deform = True
                    else:
                        head0 = heads.get(bname)
                        if head0 and (binfo.head-head0).length > self.duplicateDistance * GS.scale:
                            dups[bname] = True
                        else:
                            heads[bname] = binfo.head
                idx += 1
                addMergedProp(rig, subrig, idx)

        # Create the new editbones
        hasNew = False
        taken = []
        for info,dups in zip(infos, dupss):
            rig,bones,_meshes = info[0]
            activateObject(context, rig)
            setMode('EDIT')
            for subrig,subbones,_submeshes in info[1:]:
                for bname,binfo in subbones.items():
                    if bname not in bones.keys() and bname not in taken:
                        hasNew = True
                        if bname in dups.keys():
                            dupname = getDupName(subrig, bname)
                            binfo.setEditBone(dupname, rig.data.edit_bones, subrig)
                        else:
                            binfo.setEditBone(bname, rig.data.edit_bones, subrig)
                            taken.append(bname)
            setMode('OBJECT')
        if hasNew:
            enableRigNumLayer(rig, T_CUSTOM)

        from .driver import copyProp, retargetDrivers
        from .morphing import copyCategories
        def copyProps(src, trg, ovr):
            for prop,value in src.items():
                if prop[0:3] != "Daz":
                    copyProp(prop, src, trg, ovr)

        # Copy rig, armature and posebone properties and drivers
        for info,dups in zip(infos, dupss):
            rig,bones,_meshes = info[0]
            for subrig,subbones,submeshes in info[1:]:
                for key,pg0 in subrig.data.DazBoneMap.items():
                    if key not in rig.data.DazBoneMap.keys():
                        pg = rig.data.DazBoneMap.add()
                        pg.name = pg0.name
                        pg.s = pg0.s

                copyProps(subrig, rig, True)
                copyProps(subrig.data, rig.data, False)
                copyCategories(subrig, rig)
                assoc = dict([(bname, getDupName(subrig, bname)) for bname in dups.keys()])
                self.copyAssocDrivers(subrig.data, rig.data, subrig, rig, assoc)
                self.copyAssocDrivers(subrig, rig, subrig, rig, assoc)
                for submesh in submeshes:
                    skeys = submesh.data.shape_keys
                    if skeys:
                        retargetDrivers(skeys, subrig, rig)
                    for mat in submesh.data.materials:
                        if mat:
                            retargetDrivers(mat.node_tree, subrig, rig)

                for bname,binfo in subbones.items():
                    if bname in bones.keys():
                        continue
                    elif bname in dups.keys():
                        dupname = getDupName(subrig, bname)
                        for mesh in submeshes:
                            vgrp = mesh.vertex_groups.get(bname)
                            if vgrp:
                                vgrp.name = dupname
                        pb = rig.pose.bones.get(dupname)
                    else:
                        pb = rig.pose.bones.get(bname)
                    if pb:
                        binfo.setPoseBone(pb, rig)
                        enableBoneNumLayer(pb.bone, rig, T_CUSTOM)

        # Widgets
        if widgets:
            from .proxy import WidgetConverter
            wrig = widgets[0]
            rig = wrig.parent
            ob = getMeshChildren(wrig)[0]
            if rig and ob and rig.type == 'ARMATURE':
                print("Convert %s to widgets for %s" % (ob.name, rig.name))
                activateObject(context, ob)
                wc = WidgetConverter()
                wc.convertWidgets(context, rig, ob)
                enableRigNumLayer(rig, T_WIDGETS)

        # Restore all objects
        for ob,parent,wmat,hide1,hide2 in objects:
            ob.parent = parent
            setWorldMatrix(ob, wmat)
            ob.hide_viewport = hide1
            ob.hide_set(hide2)
            if ob.type == 'MESH':
                mod = getModifier(ob, 'ARMATURE')
                if mod:
                    mod.object = parent

        return deletes

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

class DAZ_OT_CopyPose(DazPropsOperator, LockEnabler, IsArmature):
    bl_idname = "daz.copy_pose"
    bl_label = "Copy Pose"
    bl_description = "Copy pose from active rig to selected rigs"
    bl_options = {'UNDO'}

    useDisableLocks : BoolProperty(
        name = "Disable Locks And Limits",
        description = "Disable locks and limits",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useDisableLocks")

    def setLocks(self, pb):
        pb.lock_location = pb.lock_rotation = FFalse


    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            raise DazError("No source armature")
        if not subrigs:
            raise DazError("No target armature")

        def snapBone(pb, gmats):
            M1 = gmats.get(pb.name)
            if M1 is None:
                return
            R1 = pb.bone.matrix_local
            if pb.parent:
                M0 = gmats.get(pb.parent.name)
                if M0 is None:
                    return
                R0 = pb.parent.bone.matrix_local
                pb.matrix_basis = R1.inverted() @ R0 @ M0.inverted() @ M1
            else:
                pb.matrix_basis = R1.inverted() @ M1

        gmats = dict([(pb.name, pb.matrix.copy()) for pb in rig.pose.bones])
        for subrig in subrigs:
            if self.useDisableLocks:
                self.enableLocksLimits(rig, False, 0.0)
            print("Copy bones to %s:" % subrig.name)
            setWorldMatrix(subrig, rig.matrix_world)
            for pb in subrig.pose.bones:
                if pb.name in rig.pose.bones.keys():
                    snapBone(pb, gmats)

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(CollectionShower, DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):
    children = []
    for child in rig.children:
        setRestPose(child, rig, context)
        if activateObject(context, child):
            children.append((child, child.parent_type, child.parent_bone))
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    if activateObject(context, rig):
        bpy.ops.object.transform_apply()
        setMode('POSE')
        bpy.ops.pose.armature_apply()
        setMode('OBJECT')
    for child,type,bone in children:
        wmat = child.matrix_world.copy()
        child.parent = rig
        child.parent_type = type
        child.parent_bone = bone
        setWorldMatrix(child, wmat)


def safeTransformApply(useLocRot=True):
    try:
        bpy.ops.object.transform_apply(location=useLocRot, rotation=useLocRot, scale=True)
    except RuntimeError as err:
        print("Cannot apply transforms")


def applyAllObjectTransforms(rigs):
    bpy.ops.object.select_all(action='DESELECT')
    for rig in rigs:
        selectSet(rig, True)
    safeTransformApply()
    bpy.ops.object.select_all(action='DESELECT')
    status = []
    try:
        for rig in rigs:
            for ob in rig.children:
                if ob.parent_type != 'BONE':
                    status.append((ob, ob.hide_get(), ob.hide_select))
                    ob.hide_set(False)
                    ob.hide_select = False
                    selectSet(ob, True)
        safeTransformApply()
        for ob,hide,select in status:
            ob.hide_set(hide)
            ob.hide_select = select
        return True
    except RuntimeError:
        print("Could not apply object transformations")
        return False


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type != 'OBJECT' or ob.type != 'MESH':
        return
    if len(ob.vertex_groups) == 0:
        print("Mesh with no vertex groups: %s" % ob.name)
        return
    try:
        applyArmatureModifier(ob)
        ok = True
    except RuntimeError:
        print("Could not apply armature to %s" % ob.name)
        ok = False
    if ok:
        from .modifier import newArmatureModifier
        newArmatureModifier(rig.name, ob, rig)


def applyArmatureModifier(ob):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE':
            mname = mod.name
            if ob.data.shape_keys:
                if bpy.app.version < (2,90,0):
                    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                else:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                bpy.ops.object.modifier_apply(modifier=mname)

#-------------------------------------------------------------
#   Apply transform to objects
#-------------------------------------------------------------

def findExcludedObjects(context, useHidden):
    def excludeHidden(objects, layer):
        if not (layer.exclude or layer.hide_viewport):
            for ob in layer.collection.objects:
                if useHidden or not (ob.hide_viewport or ob.hide_get()):
                    objects.append(ob)
            for child in layer.children:
                excludeHidden(objects, child)

    objects = []
    excludeHidden(objects, context.view_layer.layer_collection)
    objects = set(objects)
    excluded = []
    for ob in context.scene.objects:
        if ob not in objects:
            excluded.append(ob)
    return excluded


def applyTransformToObjects(objects, excluded=[]):
    bpy.ops.object.select_all(action='DESELECT')
    parents = []
    for ob in objects:
        for child in ob.children:
            if child in excluded:
                continue
            parents.append((child, ob, child.matrix_world.copy(), child.hide_viewport, child.hide_get(), child.hide_select))
            child.hide_viewport = False
            child.hide_set(False)
            child.hide_select = False
            child.select_set(True)
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

    wmats = []
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        wmat = ob.matrix_world.copy()
        wmats.append((ob, wmat, ob.hide_viewport, ob.hide_get(), ob.hide_select))
        ob.hide_viewport = False
        ob.hide_set(False)
        ob.hide_select = False
        ob.select_set(True)
    bpy.ops.object.transform_apply()

    for child,ob,wmat,hide1,hide2,hide3 in parents:
        child.parent = ob
        setWorldMatrix(child, wmat)
        child.hide_viewport = hide1
        child.hide_set(hide2)
        child.hide_select = hide3

    return wmats


def restoreTransformsToObjects(wmats):
    bpy.ops.object.select_all(action='DESELECT')
    for ob,wmat,hide1,hide2,hide3 in wmats:
        setWorldMatrix(ob, wmat.inverted())
        ob.select_set(True)
    bpy.ops.object.transform_apply()
    for ob,wmat,hide1,hide2,hide3 in wmats:
        setWorldMatrix(ob, wmat)
        ob.hide_viewport = hide1
        ob.hide_set(hide2)
        ob.hide_select = hide3

#-------------------------------------------------------------
#   Merge toes
#-------------------------------------------------------------

def mergeBones(rig, mergers, parents, context):
    from .driver import removeBoneSumDrivers

    deletes = []
    for bones in mergers.values():
        deletes += bones + [drvBone(bone) for bone in bones]
    activateObject(context, rig)
    removeBoneSumDrivers(rig, deletes)

    swapped = {}
    for key,bnames in mergers.items():
        for bname in bnames:
            swapped[bname] = key
    for ob in rig.children:
        if ob.parent_type == 'BONE' and ob.parent_bone in swapped.keys():
            wmat = ob.matrix_world.copy()
            ob.parent_bone = swapped[ob.parent_bone]
            setWorldMatrix(ob, wmat)

    setMode('EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    for eb in rig.data.edit_bones:
        if eb.name in deletes:
            rig.data.edit_bones.remove(eb)


def mergeVertexGroups(rig, mergers):
    setMode('OBJECT')
    for toe in mergers.keys():
        bone = rig.data.bones.get(toe)
        if bone:
            bone.use_deform = True

    for ob in getMeshChildren(rig):
        for toe,subtoes in mergers.items():
            subgrps = []
            for subtoe in subtoes:
                if subtoe in ob.vertex_groups.keys():
                    subgrps.append(ob.vertex_groups[subtoe])
            if toe in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[toe]
            elif subgrps:
                vgrp = ob.vertex_groups.new(name=toe)
            else:
                continue
            idxs = [vg.index for vg in subgrps]
            idxs.append(vgrp.index)
            weights = dict([(vn,0) for vn in range(len(ob.data.vertices))])
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group in idxs:
                         weights[v.index] += g.weight
            for subgrp in subgrps:
                ob.vertex_groups.remove(subgrp)
            for vn,w in weights.items():
                if w > 1e-3:
                    vgrp.add([vn], w, 'REPLACE')

    updateDrivers(rig)


class DAZ_OT_MergeToes(DazOperator, IsArmature):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge separate toes into a single toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        genesisToes = {
            "lFoot" : ["lMetatarsals"],
            "rFoot" : ["rMetatarsals"],
            "lToe" : ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
                      "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
            "rToe" : ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
                      "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
            "l_foot" : ["l_metatarsal"],
            "r_foot" : ["r_metatarsal"],
            "l_toes" : ["l_bigtoe1", "l_indextoe1", "l_midtoe1", "l_ringtoe1", "l_pinkytoe1",
                        "l_bigtoe2", "l_indextoe2", "l_midtoe2", "l_ringtoe2", "l_pinkytoe2"],
            "r_toes" : ["r_bigtoe1", "r_indextoe1", "r_midtoe1", "r_ringtoe1", "r_pinkytoe1",
                        "r_bigtoe2", "r_indextoe2", "r_midtoe2", "r_ringtoe2", "r_pinkytoe2"],
        }

        newParents = {
            "lToe" : "lFoot",
            "rToe" : "rFoot",
            "l_toes" : "l_foot",
            "r_toes" : "r_foot",
        }
        rig = context.object
        mergeBones(rig, genesisToes, newParents, context)
        mergeVertexGroups(rig, genesisToes)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeRigs,
    DAZ_OT_CopyPose,
    DAZ_OT_ApplyRestPoses,
    DAZ_OT_MergeToes,
]

def register():
    from .propgroups import DazStringBoolGroup
    bpy.types.Armature.DazMergedRigs = CollectionProperty(type = DazStringBoolGroup)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

