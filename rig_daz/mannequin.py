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
from ..error import *
from ..utils import *
from ..tables import *

#-------------------------------------------------------------
#   Add mannequin
#   With improvements by ViSlArT, issue 756
#-------------------------------------------------------------

class DAZ_OT_AddMannequin(DazPropsOperator, IsMesh):
    bl_idname = "daz.add_mannequin"
    bl_label = "Add Mannequins"
    bl_description = "Add mannequins to selected meshes. Don't change rig after this."
    bl_options = {'UNDO'}

    headType : EnumProperty(
        items = [('SOLID', "Solid", "Solid head"),
                 ('JAW', "Jaw", "Head with jaws and eyes"),
                 ('FULL', "Full", "Head with all face bones"),
                 ],
        name = "Head Type",
        description = "How to make the mannequin head",
        default = 'JAW')

    mannColl : StringProperty(
        name = "Mannequin Collection",
        description = "Add mannequin to this collection",
        default = "Mannequin")

    meshColl : StringProperty(
        name = "Mesh Collection",
        description = "Add base meshes to this collection",
        default = "Meshes")

    useNormals : BoolProperty(
        name = "Transfer Normals",
        description = "Transfer custom normals to mannequin meshes",
        default = False)

    useVertexGroups : BoolProperty(
        name = "Transfer Vertex Groups",
        description = "Transfer vertex groups to mannequin meshes",
        default = False)

    ignoreBoneGroups : BoolProperty(
        name = "Ignore Bone Groups",
        description = "Don't transfer bone vertex groups",
        default = False)

    threshold : FloatProperty(
        name = "Threshold",
        description = "Minimum vertex weight to keep",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 1e-3)

    useVertexColors : BoolProperty(
        name = "Transfer Vertex Colors",
        description = "Transfer vertex colors to mannequin meshes",
        default = False)

    useUvLayers : BoolProperty(
        name = "Transfer UV Layers",
        description = "Transfer UV layers to mannequin meshes",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "headType")
        self.layout.prop(self, "mannColl")
        self.layout.prop(self, "meshColl")
        self.layout.prop(self, "useNormals")
        self.layout.prop(self, "useVertexGroups")
        if self.useVertexGroups:
            self.layout.prop(self, "ignoreBoneGroups")
            self.layout.prop(self, "threshold")
        self.layout.prop(self, "useVertexColors")
        self.layout.prop(self, "useUvLayers")


    def storeState(self, context):
        DazPropsOperator.storeState(self, context)
        self.meshes = []
        for ob in getSelectedMeshes(context):
            mod = getModifier(ob, 'NODES')
            if mod:
                self.meshes.append((ob, mod.show_viewport, mod.show_render))
                mod.show_viewport = mod.show_render = False


    def restoreState(self, context):
        DazPropsOperator.restoreState(self, context)
        for ob,viewport,render in self.meshes:
            mod = getModifier(ob, 'NODES')
            if mod:
                mod.show_viewport = viewport
                mod.show_render = render


    def run(self, context):
        obs,nobs,rig = self.addMannequins(context)
        if self.ignoreBoneGroups:
            bnames = rig.data.bones.keys()
        else:
            bnames = []
        for obname,ob in obs.items():
            self.transferData(context, ob, nobs[obname], bnames)


    def addMannequins(self, context):
        selected = getSelectedObjects(context)
        meshes = getSelectedMeshes(context)
        ob = context.object
        rig = ob.parent
        if not (rig and rig.type == 'ARMATURE'):
            raise DazError("Mesh %s has no armature parent" % ob)
        setActiveObject(context, rig)
        setMode('OBJECT')
        oldlayers = getRigLayers(rig)
        enableAllRigLayers(rig)
        oldpose = rig.data.pose_position
        rig.data.pose_position = 'REST'

        # Create group/collection
        mangrp = None
        scn = context.scene
        coll = rigcoll = getCollection(context, rig)
        obs = {}
        nobs = {}
        from ..hide import createSubCollection
        colls = list(rigcoll.children)
        meshcoll = createSubCollection(rigcoll, self.meshColl)
        for coll in colls:
            rigcoll.children.unlink(coll)
            meshcoll.children.link(coll)
        manncoll = createSubCollection(rigcoll, self.mannColl)

        # Add mannequin objects for selected meshes
        for ob in meshes:
            obs[ob.name] = ob
            masks = []
            for mod in ob.modifiers:
                if mod.type == 'MASK':
                    masks.append((mod, mod.vertex_group))
                    mod.vertex_group = ""
            nobs[ob.name] = self.addMannequin(ob, context, rig, manncoll, mangrp)
            for mod,vgrp in masks:
                mod.vertex_group = vgrp

        for ob in getSelectedObjects(context):
            if ob in selected:
                selectSet(ob, True)
            else:
                selectSet(ob, False)
        setRigLayers(rig, oldlayers)
        rig.data.pose_position = oldpose
        for ob in list(rigcoll.objects):
            if ob.type != 'ARMATURE':
                meshcoll.objects.link(ob)
                rigcoll.objects.unlink(ob)
        return obs, nobs, rig


    def addMannequin(self, ob, context, rig, coll, mangrp):
        faceverts, vertfaces = getVertFaces(ob)
        majors = {}
        skip = []
        for vgrp in ob.vertex_groups:
            bone = rig.data.bones.get(vgrp.name)
            if bone and bone.use_deform:
                majors[vgrp.index] = []
            else:
                skip.append(vgrp.index)
        for v in ob.data.vertices:
            wmax = 1e-3
            vbest = None
            for g in v.groups:
                if g.weight > wmax and g.group not in skip:
                    wmax = g.weight
                    vbest = v
                    gbest = g.group
            if vbest is not None:
                majors[gbest].append(vbest)

        roots = [bone for bone in rig.data.bones if bone.parent is None]
        for bone in roots:
            self.remapBones(bone, ob.vertex_groups, majors, None)

        mob = ob.evaluated_get(context.evaluated_depsgraph_get())

        face_mats = dict()
        if ob.data.materials:
            for rnd in range(3, 8):
                face_mats[rnd] = dict()
                for f in mob.data.polygons:
                    try:
                        mat = ob.material_slots[f.material_index].material
                    except IndexError:
                        continue
                    nn = tuple(round(x, rnd) for x in f.normal)
                    face_mats[rnd][nn] = mat

        obverts = mob.data.vertices
        nobinfos = []
        self.defaultMaterial = None
        for vgrp in ob.vertex_groups:
            if (vgrp.name not in rig.pose.bones.keys() or
                vgrp.index not in majors.keys()):
                continue
            fnums = []
            for v in majors[vgrp.index]:
                for fn in vertfaces[v.index]:
                    fnums.append(fn)
            fnums = list(set(fnums))

            nverts = []
            nfaces = []
            for fn in fnums:
                f = ob.data.polygons[fn]
                nverts += f.vertices
                nfaces.append(f.vertices)
            if not nfaces:
                continue
            nverts = list(set(nverts))
            nverts.sort()

            bone = rig.data.bones[vgrp.name]
            head = bone.head_local
            verts = [obverts[vn].co-head for vn in nverts]
            assoc = dict([(vn,n) for n,vn in enumerate(nverts)])
            faces = []
            for fverts in nfaces:
                faces.append([assoc[vn] for vn in fverts])

            name = "%s_%s" % (ob.name[0:3], vgrp.name)
            me = bpy.data.meshes.new(name)
            me.from_pydata(verts, [], faces)
            nob = bpy.data.objects.new(name, me)
            coll.objects.link(nob)
            nob.location = head
            lockAllTransforms(nob)
            nobinfos.append((nob, rig, bone, me))

            if face_mats:
                for f in me.polygons:
                    for rnd in reversed(range(3, 8)):
                        fmat = face_mats[rnd].get(tuple(round(x, rnd) for x in f.normal))
                        if fmat:
                            break
                    else:
                        fmat = self.getDefaultMaterial(ob)
                    if fmat.name not in me.materials:
                        me.materials.append(fmat)
                    for (i, mat_i) in enumerate(nob.material_slots):
                        if mat_i.material == fmat:
                            f.material_index = i
                            break

        updateScene(context)

        from ..node import setParent
        for nob, rig, bone, me in nobinfos:
            setParent(context, nob, rig, bone.name, update=False)
            if mangrp:
                mangrp.objects.link(nob)
        return [nobinfo[0] for nobinfo in nobinfos]


    def getDefaultMaterial(self, ob):
        from random import random
        from ..guess import getMaterialType
        if self.defaultMaterial is None:
            mat = bpy.data.materials.new("%s_Mannequin" % ob.name)
            self.defaultMaterial = mat
            mat.diffuse_color[0:3] = (random(), random(), random())
            for omat in ob.data.materials:
                if omat:
                    mat.diffuse_color = omat.diffuse_color
                    if getMaterialType(omat) == 'SKIN':
                        break
        return self.defaultMaterial


    def remapBones(self, bone, vgrps, majors, remap):
        special = {
            'SOLID' : ["head"],
            'JAW' : ["head", "lowerjaw", "leye", "reye"],
            'FULL' : []
              }
        if bone.name.lower() in special[self.headType]:
            if bone.name in vgrps.keys():
                remap = vgrps[bone.name].index
        elif remap is not None:
            if bone.name in vgrps.keys():
                gn = vgrps[bone.name].index
                if gn in majors.keys():
                    majors[remap] += majors[gn]
                    del majors[gn]
        for child in bone.children:
            self.remapBones(child, vgrps, majors, remap)


    def transferData(self, context, ob, nobs, bnames):
        print("Transfer data from %s to %d meshes" % (ob.name, len(nobs)))
        transfer = bpy.ops.object.data_transfer
        activateObject(context, ob)
        for nob in nobs:
            nob.select_set(True)

        if self.useNormals:
            for face in ob.data.polygons:
                if face.use_smooth:
                    bpy.ops.object.shade_smooth()
                    break
            if hasattr(ob.data, "use_auto_smooth") and ob.data.use_auto_smooth:
                transfer(data_type='CUSTOM_NORMAL')
                for nob in nobs:
                    nob.data.use_auto_smooth = True

        if ob.vertex_groups and self.useVertexGroups:
            from ..transfer import pruneVertexGroups
            transfer(data_type='VGROUP_WEIGHTS', layers_select_src='ALL', layers_select_dst='NAME')
            for nob in nobs:
                pruneVertexGroups(nob, self.threshold, bnames, False)
        if ob.data.vertex_colors and self.useVertexColors:
            transfer(data_type='VCOL', layers_select_src='ALL', layers_select_dst='NAME')
        if ob.data.uv_layers and self.useUvLayers:
            transfer(data_type='UV', layers_select_src='ALL', layers_select_dst='NAME')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_AddMannequin)


def unregister():
    bpy.utils.unregister_class(DAZ_OT_AddMannequin)