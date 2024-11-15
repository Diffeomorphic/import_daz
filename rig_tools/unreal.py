#  DAZ Rigging - Tools for rigging figures imported with the DAZ Importer
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

import numpy as np
import os
import bpy
from ..figure import *
from ..fileutils import SingleFile, FbxFile, ensureExt
from ..driver import removeBoneSumDrivers

#-------------------------------------------------------------
#
#-------------------------------------------------------------

U_UNREAL = "Unreal"
U_OTHER = "Other"

UR = {
    "Skeleton" : {
        "hip" : "root",
        "pelvis" : "pelvis",
        "abdomen" : "spine_01",
        "abdomenLower" : "spine_01",
        "spine1" : "spine_01",
        "abdomen2" : "spine_02",
        "abdomenUpper" : "spine_02",
        "spine2" : "spine_02",
        "chest" : "spine_03",
        "chestLower" : "spine_03",
        "spine3" : "spine_03",
        #"chestUpper" : "chest-1",
        #"spine4" : "chest-1",
        "neck" : "neck_01",
        "neckLower" : "neck_01",
        "neck1" : "neck_01",
        #"neckUpper" : "neck-1",
        #"neck2" : "neck-1",
        "head" : "head",

        #"lPectoral" : "pectoral_l",
        #"l_pectoral" : "pectoral_l",
        "lCollar" : "clavicle_l",
        "l_shoulder" : "clavicle_l",
        "lShldr" : "upperarm_l",
        "lShldrBend" : "upperarm_l",
        "lShldrTwist" : "upperarm_twist_01_l",
        "l_upperarm" : "upperarm_l",
        "l_upperarmtwist1" : "upperarm_twist_01_l",
        "l_upperarmtwist2" : "upperarm_twist_02_l",
        "lForeArm" : "lowerarm_l",
        "lForearmBend" : "lowerarm_l",
        "lForearmTwist" : "lowerarm_twist_01_l",
        "l_forearm" : "lowerarm_l",
        "l_forearmtwist1" : "forearm_twist01_l",
        "l_forearmtwist2" : "forearm_twist02_l",
        "lHand" : "hand_l",
        "l_hand" : "hand_l",

        #"rPectoral" : "pectoral_r",
        #"r_pectoral" : "pectoral_r",
        "rCollar" : "clavicle_r",
        "r_shoulder" : "clavicle_r",
        "rShldr" : "upperarm_r",
        "rShldrBend" : "upperarm_r",
        "rShldrTwist" : "upperarm_twist_01_r",
        "r_upperarm" : "upperarm_r",
        "r_upperarmtwist1" : "upperarm_twist_01_r",
        "r_upperarmtwist2" : "upperarm_twist_02_r",
        "rForeArm" : "lowerarm_r",
        "rForearmBend" : "lowerarm_r",
        "rForearmTwist" : "lowerarm_twist_01_r",
        "r_forearm" : "lowerarm_r",
        "r_forearmtwist1" : "forearm_twist01_r",
        "r_forearmtwist2" : "forearm_twist02_r",
        "rHand" : "hand_r",
        "r_hand" : "hand_r",

        "lThigh" : "thigh_l",
        "lThighBend" : "thigh_l",
        "lThighTwist" : "thigh_twist_01_l",
        "l_thigh" : "thigh_l",
        "l_thightwist1" : "thigh_twist01_l",
        "l_thightwist2" : "thigh_twist02_l",
        "lShin" : "calf_l",
        "l_shin" : "calf_l",
        "lFoot" : "foot_l",
        "l_foot" : "foot_l",
        #"lMetatarsals" : "tarsal_l",
        #"l_metatarsal" : "tarsal_l",
        "lToe" : "ball_l",
        "l_toes" : "ball_l",
        #"lHeel" : "heel_l",

        "rThigh" : "thigh_r",
        "rThighBend" : "thigh_r",
        "rThighTwist" : "thigh_twist_01_r",
        "r_thigh" : "thigh_r",
        "r_thightwist1" : "thigh_twist_01_r",
        "r_thightwist2" : "thigh_twist_02_r",
        "rShin" : "calf_r",
        "r_shin" : "calf_r",
        "rFoot" : "foot_r",
        "r_foot" : "foot_r",
        #"rMetatarsals" : "tarsal_r",
        #"r_metatarsal" : "tarsal_r",
        "rToe" : "ball_r",
        "r_toes" : "ball_r",
        #"rHeel" : "heel_r",

        "lThumb1" : "thumb_01_l",
        "lThumb2" : "thumb_02_l",
        "lThumb3" : "thumb_03_l",
        "lIndex1" : "index_01_l",
        "lIndex2" : "index_02_l",
        "lIndex3" : "index_03_l",
        "lMid1" : "middle_01_l",
        "lMid2" : "middle_02_l",
        "lMid3" : "middle_03_l",
        "lRing1" : "ring_01_l",
        "lRing2" : "ring_02_l",
        "lRing3" : "ring_03_l",
        "lPinky1" : "pinky_01_l",
        "lPinky2" : "pinky_02_l",
        "lPinky3" : "pinky_03_l",

        "l_thumb1" : "thumb_01_l",
        "l_thumb2" : "thumb_02_l",
        "l_thumb3" : "thumb_03_l",
        "l_index1" : "index_01_l",
        "l_index2" : "index_02_l",
        "l_index3" : "index_03_l",
        "l_mid1" : "middle_01_l",
        "l_mid2" : "middle_02_l",
        "l_mid3" : "middle_03_l",
        "l_ring1" : "ring_01_l",
        "l_ring2" : "ring_02_l",
        "l_ring3" : "ring_03_l",
        "l_pinky1" : "pinky_01_l",
        "l_pinky2" : "pinky_02_l",
        "l_pinky3" : "pinky_03_l",

        "rThumb1" : "thumb_01_r",
        "rThumb2" : "thumb_02_r",
        "rThumb3" : "thumb_03_r",
        "rIndex1" : "index_01_r",
        "rIndex2" : "index_02_r",
        "rIndex3" : "index_03_r",
        "rMid1" : "middle_01_r",
        "rMid2" : "middle_02_r",
        "rMid3" : "middle_03_r",
        "rRing1" : "ring_01_r",
        "rRing2" : "ring_02_r",
        "rRing3" : "ring_03_r",
        "rPinky1" : "pinky_01_r",
        "rPinky2" : "pinky_02_r",
        "rPinky3" : "pinky_03_r",

        "r_thumb1" : "thumb_01_r",
        "r_thumb2" : "thumb_02_r",
        "r_thumb3" : "thumb_03_r",
        "r_index1" : "index_01_r",
        "r_index2" : "index_02_r",
        "r_index3" : "index_03_r",
        "r_mid1" : "middle_01_r",
        "r_mid2" : "middle_02_r",
        "r_mid3" : "middle_03_r",
        "r_ring1" : "ring_01_r",
        "r_ring2" : "ring_02_r",
        "r_ring3" : "ring_03_r",
        "r_pinky1" : "pinky_01_r",
        "r_pinky2" : "pinky_02_r",
        "r_pinky3" : "pinky_03_r"
    }
}

class DAZ_OT_MakeUnreal(DazOperator, IsArmature):
    bl_idname = "daz.make_unreal"
    bl_label = "Make Unreal"
    bl_description = "Prepare for Unreal Engine"

    def run(self, context):
        rig = context.object
        ubones = UR["Skeleton"]
        for bone in list(rig.data.bones):
            if bone.name in ubones.keys():
                enableBoneNumLayer(bone, rig, U_UNREAL)

        removeBoneSumDrivers(rig, rig.data.bones.keys())

        setMode('EDIT')
        deletes = {}
        for eb in list(rig.data.edit_bones):
            uname = ubones.get(eb.name)
            par = eb.parent
            if uname:
                eb.name = uname
                if par and "twist" in par.name:
                    eb.use_connect = False
                    eb.parent = par.parent
            else:
                if par and par.name in deletes.keys():
                    deletes[eb.name] = deletes[par.name]
                else:
                    deletes[eb.name] = par.name
        for bname in deletes.keys():
            eb = rig.data.edit_bones[bname]
            rig.data.edit_bones.remove(eb)

        setMode('OBJECT')
        groups = {}
        for bname,uname in deletes.items():
            if uname not in groups.keys():
                groups[uname] = []
            groups[uname].append(bname)

        for ob in rig.children:
            fnums = []
            mnums = []
            if ob.type == 'MESH':
                if getModifier(ob, 'ARMATURE'):
                    self.changeVertexGroups(ob, groups)
                for mn,mat in enumerate(ob.data.materials):
                    if mat:
                        if self.changeMaterial(mat):
                            fnums += [f.index for f in ob.data.polygons if f.material_index == mn]
                            mnums.append(mn)
                if fnums:
                    activateObject(context, ob)
                    setMode('EDIT')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    setMode('OBJECT')
                    for fn in fnums:
                        ob.data.polygons[fn].select = True
                    setMode('EDIT')
                    bpy.ops.mesh.delete(type='VERT')
                    setMode('OBJECT')
                if mnums:
                    mnums.reverse()
                    for mn in mnums:
                        ob.active_material_index = mn
                        bpy.ops.object.material_slot_remove()
            if ob.parent_type == 'BONE':
                uname = ubones.get(ob.parent_bone)
                if uname:
                    ob.parent_bone = uname


    def changeVertexGroups(self, ob, groups):
        nverts = len(ob.data.vertices)
        ngrps = len(ob.vertex_groups)
        weights = np.zeros((ngrps, nverts), dtype=float)
        for v in ob.data.vertices:
            for g in v.groups:
                weights[g.group, v.index] = g.weight
        deletes = []
        for uname,bnames in groups.items():
            vgrp = ob.vertex_groups.get(uname)
            if vgrp:
                wts = weights[vgrp.index].copy()
                change = False
                for bname in bnames:
                    subgrp = ob.vertex_groups.get(bname)
                    if subgrp:
                        wts += weights[subgrp.index]
                        deletes.append(subgrp)
                    change = True
                if change:
                    nonzero = np.nonzero(wts)[0].astype(int)
                    if len(nonzero) > 0:
                        for vn in nonzero:
                            vgrp.add([int(vn)], wts[vn], 'REPLACE')
        for vgrp in deletes:
            ob.vertex_groups.remove(vgrp)


    def changeMaterial(self, mat):
        changed = False
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                trans = node.inputs["Transmission Weight"].default_value
                if trans > 0:
                    node.inputs["Alpha"].default_value = 1-trans
                    changed = True
        return changed

#----------------------------------------------------------
#   Export Unreal
#----------------------------------------------------------

class DAZ_OT_ExportUnreal(DazOperator, SingleFile, FbxFile, IsArmature):
    bl_idname = "daz.export_unreal"
    bl_label = "Export Unreal"
    bl_description = "Export"

    exportType : EnumProperty(
        items = [('MESH', "Mesh", "Mesh"),
                 ('ACTION', "Action", "Action")],
        name = "Type",
        default = 'MESH')

    def draw(self, context):
        self.layout.prop(self, "exportType")

    def run(self, context):
        rig = context.object
        if self.exportType == 'MESH':
            otypes = {'ARMATURE', 'MESH'}
            fname = rig.name
        elif self.exportType == 'ACTION':
            otypes = {'ARMATURE'}
            fname = rig.animation_data.action.name
            fname = fname.split(":")[0].lower()
        filepath = ensureExt(self.filepath, ".fbx")
        print('Export %s to "%s"' % (otypes, filepath))
        bpy.ops.export_scene.fbx(
            filepath = filepath,
            use_active_collection = False,
            use_visible = True,
            object_types = otypes,
            mesh_smooth_type = 'FACE',
            use_armature_deform_only = False,
            add_leaf_bones = False,
            armature_nodetype = 'ROOT',
            bake_anim = True,
            bake_anim_use_all_bones = True,
            bake_anim_use_nla_strips = False,
            bake_anim_use_all_actions = False,
            )

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeUnreal,
    DAZ_OT_ExportUnreal,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
