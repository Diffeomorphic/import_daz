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

import bpy
from . import getSetupEnabled, getRuntimeEnabled
from .utils import *
from .buildnumber import BUILD
from .uilist import DAZ_UL_StandardMorphs
from .morphing import MS
from .layers import *

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

class DAZ_PT_SetupTab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Setup"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return getSetupEnabled(context)


class DAZ_PT_RuntimeTab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Runtime"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return getRuntimeEnabled(context)

#----------------------------------------------------------
#   Setup panel
#----------------------------------------------------------

class DAZ_PT_Setup(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "DAZ Setup (version 1.7.4.%04d)" % BUILD
    bl_options = set()

    def draw(self, context):
        scn = context.scene
        self.layout.operator("daz.easy_import_daz")
        self.layout.prop(scn, "DazFavoPath")
        self.layout.separator()
        self.layout.operator("daz.global_settings")
        self.layout.prop(scn, "DazPreferredRoot")


class DAZ_PT_SetupCorrections(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupCorrections"
    bl_label = "Corrections"

    def draw(self, context):
        self.layout.operator("daz.eliminate_empties")
        self.layout.operator("daz.merge_rigs")
        self.layout.operator("daz.merge_toes")
        self.layout.separator()
        self.layout.operator("daz.copy_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.apply_active_shapekey")
        self.layout.operator("daz.change_armature")


class DAZ_PT_SetupMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.update_settings")
        self.layout.operator("daz.save_local_textures")
        self.layout.operator("daz.resize_textures")
        self.layout.operator("daz.change_resolution")
        self.layout.separator()
        self.layout.operator("daz.merge_materials")
        self.layout.operator("daz.strip_material_names")
        self.layout.operator("daz.change_colors")
        self.layout.operator("daz.change_skin_color")
        self.layout.separator()
        self.layout.operator("daz.launch_editor")
        self.layout.operator("daz.reset_materials")
        self.layout.operator("daz.make_combo_material")


class DAZ_PT_SetupMorphs(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        ob = context.object
        if ob and ob.type in ['ARMATURE', 'MESH'] and ob.DazId:
            if ob.DazDriversDisabled:
                self.layout.label(text = "Morph Drivers Disabled")
                self.layout.operator("daz.enable_drivers")
                return
            elif ob.DazMorphPrefixes:
                return
            self.layout.operator("daz.import_units")
            self.layout.operator("daz.import_expressions")
            self.layout.operator("daz.import_visemes")
            self.layout.operator("daz.import_head")
            self.layout.operator("daz.import_facs")
            self.layout.operator("daz.import_facs_details")
            self.layout.operator("daz.import_facs_expressions")
            self.layout.operator("daz.import_body_morphs")
            self.layout.separator()
            self.layout.operator("daz.import_jcms")
            self.layout.operator("daz.import_masculine")
            self.layout.operator("daz.import_feminine")
            self.layout.operator("daz.import_flexions")
            self.layout.operator("daz.create_bulges")
            self.layout.separator()
            self.layout.operator("daz.import_standard_morphs")
            self.layout.operator("daz.import_custom_morphs")
            self.layout.separator()
            self.layout.operator("daz.import_baked_correctives")
            self.layout.operator("daz.import_daz_favorites")
            self.layout.operator("daz.save_favo_morphs")
            self.layout.operator("daz.load_favo_morphs")
            self.layout.separator()
        self.layout.operator("daz.transfer_shapekeys")
        self.layout.operator("daz.remove_shapekeys")


class DAZ_PT_SetupVisibility(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupVisibility"
    bl_label = "Visibility"

    def draw(self, context):
        self.layout.operator("daz.add_shrinkwrap")
        self.layout.operator("daz.make_invisible")
        self.layout.operator("daz.create_masks")
        self.layout.operator("daz.add_visibility_drivers")
        self.layout.operator("daz.remove_visibility_drivers")
        self.layout.operator("daz.add_shape_vis_drivers")


class DAZ_PT_SetupHair(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupHair"
    bl_label = "Hair"

    def draw(self, context):
        from .hair import getHairAndHuman
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.select_strands_by_size")
        self.layout.operator("daz.select_strands_by_width")
        self.layout.operator("daz.select_random_strands")
        self.layout.separator()
        self.layout.operator("daz.make_hair")
        hair,hum = getHairAndHuman(context, False)
        self.layout.label(text = "  Hair:  %s" % (hair.name if hair else None))
        self.layout.label(text = "  Human: %s" % (hum.name if hum else None))
        self.layout.separator()
        self.layout.operator("daz.update_hair")
        self.layout.operator("daz.color_hair")
        self.layout.operator("daz.combine_hairs")
        self.layout.separator()
        self.layout.operator("daz.mesh_add_pinning")
        self.layout.operator("daz.add_hair_rig")


class DAZ_PT_SetupFinishing(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupFinishing"
    bl_label = "Finishing"

    def draw(self, context):
        self.layout.operator("daz.merge_geografts")
        self.layout.operator("daz.merge_meshes")
        self.layout.operator("daz.merge_uv_layers")
        self.layout.operator("daz.make_udim_materials")
        self.layout.operator("daz.convert_widgets")
        self.layout.operator("daz.finalize_meshes")
        self.layout.separator()
        self.layout.operator("daz.make_all_bones_posable")
        self.layout.operator("daz.optimize_drivers")
        self.layout.operator("daz.remove_corrupt_drivers")
        self.layout.operator("daz.finalize_armature")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.connect_bone_chains")


class DAZ_PT_SetupRigging(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.add_simple_ik")
        self.layout.separator()
        self.layout.operator("daz.convert_to_mhx")
        self.layout.separator()
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")
        self.layout.separator()
        self.layout.operator("daz.add_mannequin")

#----------------------------------------------------------
#   Advanced setup panel
#----------------------------------------------------------

class DAZ_PT_Advanced(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "Advanced Setup"

    def draw(self, context):
        self.layout.operator("daz.import_daz_manually")


class DAZ_PT_AdvancedLowpoly(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedLowpoly"
    bl_label = "Lowpoly"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.separator()
        self.layout.operator("daz.apply_morphs")
        self.layout.operator("daz.make_quick_proxy")
        self.layout.separator()
        self.layout.operator("daz.make_faithful_proxy")
        self.layout.operator("daz.split_ngons")
        self.layout.operator("daz.quadify")
        self.layout.separator()
        self.layout.operator("daz.add_push")


class DAZ_PT_AdvancedHDMesh(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedHDMesh"
    bl_label = "HDMesh"

    def draw(self, context):
        if bpy.app.version >= (2,90,0):
            self.layout.operator("daz.make_multires")
            self.layout.separator()
        self.layout.operator("daz.bake_maps")
        self.layout.operator("daz.load_baked_maps")
        self.layout.separator()
        self.layout.operator("daz.load_normal_map")
        self.layout.operator("daz.load_scalar_disp")
        self.layout.operator("daz.load_vector_disp")
        self.layout.operator("daz.add_driven_value_nodes")


class DAZ_PT_AdvancedMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.import_daz_materials")
        self.layout.operator("daz.drive_shell_influence")
        self.layout.separator()
        self.layout.operator("daz.make_palette")
        self.layout.operator("daz.copy_materials")
        self.layout.separator()
        self.layout.operator("daz.combine_scene_materials")
        self.layout.operator("daz.find_missing_textures")
        self.layout.operator("daz.activate_diffuse")
        #self.layout.operator("daz.replace_materials")
        self.layout.operator("daz.scale_materials")
        self.layout.separator()
        self.layout.operator("daz.load_uv")
        self.layout.separator()
        self.layout.operator("daz.prune_node_trees")
        self.layout.operator("daz.prune_uv_maps")
        self.layout.separator()
        self.layout.operator("daz.collapse_udims")
        self.layout.operator("daz.restore_udims")
        self.layout.operator("daz.tiles_from_geograft")
        self.layout.operator("daz.fix_texture_tiles")
        self.layout.separator()
        self.layout.operator("daz.make_decal")
        self.layout.prop(context.scene, "DazDecalMask")
        self.layout.separator()
        self.layout.operator("daz.sort_materials_by_name")
        self.layout.operator("daz.make_shader_groups")


class DAZ_PT_AdvancedMesh(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMesh"
    bl_label = "Mesh"

    def draw(self, context):
        self.layout.operator("daz.limit_vertex_groups")
        self.layout.operator("daz.prune_vertex_groups")
        self.layout.operator("daz.create_graft_groups")
        self.layout.operator("daz.transfer_vertex_groups")
        self.layout.operator("daz.apply_subsurf")
        self.layout.operator("daz.copy_modifiers")
        self.layout.operator("daz.find_seams")


class DAZ_PT_AdvancedSimulation(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedSimulation"
    bl_label = "Simulation"

    def draw(self, context):
        self.layout.operator("daz.add_softbody")
        self.layout.separator()
        self.layout.operator("daz.make_simulation")
        self.layout.separator()
        self.layout.operator("daz.make_deflection")
        self.layout.operator("daz.make_collision")
        self.layout.operator("daz.make_cloth")


class DAZ_PT_AdvancedRigging(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.add_extra_face_bones")
        self.layout.separator()
        self.layout.operator("daz.change_prefix_to_suffix")
        self.layout.operator("daz.change_suffix_to_prefix")
        self.layout.separator()
        self.layout.operator("daz.batch_set_custom_shape")
        self.layout.operator("daz.optimize_pose")
        self.layout.operator("daz.improve_ik")
        self.layout.operator("daz.remove_driven_bones")
        self.layout.operator("daz.fix_legacy_posable")
        self.layout.operator("daz.fix_limit_rot_constraints")



class DAZ_PT_AdvancedMorphs(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        scn = context.scene
        self.layout.operator("daz.add_shape_to_category")
        self.layout.operator("daz.remove_shape_from_category")
        self.layout.operator("daz.rename_category")
        self.layout.operator("daz.join_categories")
        self.layout.operator("daz.protect_categories")
        self.layout.operator("daz.remove_categories")
        self.layout.operator("daz.remove_standard_morphs")
        self.layout.separator()
        self.layout.operator("daz.convert_morphs_to_shapekeys")
        self.layout.operator("daz.transfer_animation_to_shapekeys")
        self.layout.operator("daz.transfer_mesh_to_shape")
        self.layout.separator()
        self.layout.operator("daz.add_shapekey_drivers")
        self.layout.operator("daz.remove_shapekey_drivers")
        self.layout.operator("daz.remove_all_drivers")
        self.layout.operator("daz.apply_all_shapekeys")
        self.layout.operator("daz.mix_shapekeys")
        self.layout.operator("daz.visualize_shapekey")
        self.layout.separator()
        self.layout.operator("daz.update_slider_limits")
        self.layout.operator("daz.import_dbz")
        self.layout.operator("daz.copy_drivers")
        self.layout.operator("daz.update_morph_paths")

#----------------------------------------------------------
#   Utilities panel
#----------------------------------------------------------

class DAZ_PT_Utils(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "Utilities"

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
        layout.operator("daz.set_units")
        layout.operator("daz.scale_objects")
        layout.separator()
        layout.operator("daz.save_settings_file")
        layout.operator("daz.load_settings_file")
        layout.operator("daz.add_content_dirs")
        layout.separator()
        layout.operator("daz.scan_absolute_paths")
        layout.operator("daz.scan_morph_database")
        layout.operator("daz.scan_morph_directory")
        layout.separator()
        layout.operator("daz.decode_file")
        layout.operator("daz.check_database")
        layout.operator("daz.quote_unquote")
        layout.operator("daz.print_statistics")
        layout.operator("daz.update_all")
        layout.separator()
        box = layout.box()
        if ob:
            box.label(text = "Active Object: %s" % ob.type)
            box.prop(ob, "name")
            box.prop(ob, "DazBlendFile")
            box.prop(ob, "DazId")
            box.prop(ob, "DazUrl")
            box.prop(ob, "DazScene")
            box.prop(ob, "DazRig")
            box.prop(ob, "DazMesh")
            if ob.type == 'MESH':
                box.prop(ob.data, "DazFingerPrint")
            box.prop(ob, "DazScale")
            factor = 1/ob.DazScale
        else:
            box.label(text = "No active object")
            factor = 1
        layout.separator()
        pb = context.active_pose_bone
        box = layout.box()
        if pb:
            box.label(text = "Active Bone: %s" % pb.name)
            if "DazTrueName" in pb.bone.keys():
                box.label(text = "True Bone: %s" % pb.bone["DazTrueName"])
            self.propRow(box, pb.bone, "DazHead")
            self.propRow(box, pb.bone, "DazOrient")
            self.propRow(box, pb, "DazRotMode")
            self.propRow(box, pb, "DazLocLocks")
            self.propRow(box, pb, "DazRotLocks")
            mat = ob.matrix_world @ pb.matrix
            loc,quat,scale = mat.decompose()
            self.vecRow(box, factor*loc, "Location")
            self.vecRow(box, Vector(quat.to_euler())/D, "Rotation")
            self.vecRow(box, scale, "Scale")
        else:
            box.label(text = "No active bone")

        layout.separator()
        icon = 'CHECKBOX_HLT' if GS.silentMode else 'CHECKBOX_DEHLT'
        layout.operator("daz.set_silent_mode", icon=icon, emboss=False)
        layout.operator("daz.get_finger_print")
        layout.operator("daz.inspect_world_matrix")
        layout.operator("daz.enable_all_layers")


    def propRow(self, layout, rna, prop):
        row = layout.row()
        row.label(text=prop[3:])
        attr = getattr(rna, prop)
        for n in range(3):
            if isinstance(attr[n], float):
                row.label(text = "%.3f" % attr[n])
            else:
                row.label(text = str(attr[n]))

    def vecRow(self, layout, vec, text):
        row = layout.row()
        row.label(text=text)
        for n in range(3):
            row.label(text = "%.3f" % vec[n])

#----------------------------------------------------------
#   Runtime panel
#----------------------------------------------------------

class DAZ_PT_Runtime(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "DAZ Runtime (version 1.7.4.%04d)" % BUILD
    bl_options = set()

    def draw(self, context):
        self.layout.operator("daz.render_frames")
        self.layout.separator()
        self.layout.operator("daz.global_settings")
        self.layout.prop(context.scene, "DazPreferredRoot")

#----------------------------------------------------------
#   Posing panel
#----------------------------------------------------------

class DAZ_PT_Posing(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Posing"

    def draw(self, context):
        self.layout.operator("daz.import_pose")
        self.layout.operator("daz.import_expression")
        self.layout.operator("daz.import_poselib")
        self.layout.operator("daz.import_action")
        self.layout.separator()
        self.layout.operator("daz.import_node_pose")
        self.layout.separator()
        self.layout.operator("daz.clear_pose")
        op = self.layout.operator("daz.clear_morphs")
        op.morphset = "All"
        self.layout.operator("daz.copy_absolute_pose")
        self.layout.operator("daz.prune_action")
        self.layout.separator()
        self.layout.operator("daz.bake_pose_to_fk_rig")
        self.layout.operator("daz.bake_shapekeys")
        self.layout.operator("daz.mute_control_rig")
        self.layout.operator("daz.unmute_control_rig")
        self.layout.operator("daz.transfer_to_gaze")
        self.layout.operator("daz.transfer_from_gaze")
        self.layout.separator()
        self.layout.operator("daz.save_poses_to_file")
        self.layout.operator("daz.load_poses_from_file")


class DAZ_PT_LocksLimits(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Locks And Limits"

    def draw(self, context):
        rig = getRigFromContext(context, strict=False)
        if rig is None:
            return
        self.layout.operator("daz.enable_locks_limits")
        self.layout.operator("daz.disable_locks_limits")
        self.layout.prop(rig, "DazLocLocks")
        self.layout.prop(rig, "DazRotLocks")
        self.layout.prop(rig, "DazLocLimits")
        self.layout.prop(rig, "DazRotLimits")
        self.layout.prop(rig, "DazInheritScale")
        self.layout.operator("daz.impose_locks_limits")
        if rig.DazDriversDisabled:
            self.layout.operator("daz.enable_drivers")
        else:
            self.layout.operator("daz.disable_drivers")
        return
        self.layout.operator("daz.rotate_bones")


#----------------------------------------------------------
#   Morphs panel
#----------------------------------------------------------

class DAZ_PT_Morphs(DAZ_PT_RuntimeTab):
    useMesh = False

    @classmethod
    def poll(self, context):
        if not getRuntimeEnabled(context):
            return False
        rig = self.getCurrentRig(self, context)
        return (rig and
                not rig.DazDriversDisabled and
                (self.hasTheseMorphs(self, rig) or self.hasAdjustProp(self, rig)))


    def getCurrentRig(self, context):
        rig = context.object
        if rig is None:
            return None
        elif rig.type == 'MESH':
            rig = rig.parent
        if rig and rig.type == 'ARMATURE':
            return rig
        else:
            return None


    def hasTheseMorphs(self, rig):
        return getattr(rig, "Daz%s" % self.morphset)


    def hasAdjustProp(self, rig):
        adj = MS.Adjusters[self.morphset]
        return (adj in rig.keys())


    def draw(self, context):
        scn = context.scene
        rig = self.getCurrentRig(context)
        adj = MS.Adjusters[self.morphset]
        if adj in rig.keys():
            self.layout.prop(rig, propRef(adj))
        if not self.hasTheseMorphs(rig):
            return
        self.preamble(self.layout, rig)
        self.drawItems(scn, rig)


    def preamble(self, layout, rig):
        ftype = "Daz%s" % self.morphset
        self.activateLayout(layout, "", ftype, rig)
        self.keyLayout(layout, "", ftype, rig)


    def activateLayout(self, layout, category, ftype, rig):
        split = layout.split(factor=0.25)
        op = split.operator("daz.activate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op.ftype = ftype
        op = split.operator("daz.activate_protected")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op.ftype = ftype
        op = split.operator("daz.deactivate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op.ftype = ftype
        op = self.setMorphsBtn(split)
        op.category = category
        op.ftype = ftype


    def setMorphsBtn(self, layout):
        op = layout.operator("daz.set_morphs")
        op.morphset = self.morphset
        return op


    def keyLayout(self, layout, category, ftype, rig):
        split = layout.split(factor=0.25)
        op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
        op.morphset = self.morphset
        op.category = category
        op.ftype = ftype
        op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
        op.morphset = self.morphset
        op.category = category
        op.ftype = ftype
        op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
        op.morphset = self.morphset
        op.category = category
        op.ftype = ftype
        op = split.operator("daz.clear_morphs", text="", icon='X')
        op.morphset = self.morphset
        op.category = category
        op.ftype = ftype

    def drawItems(self, scn, rig):
        self.layout.template_list( self.uilist, "",
                                   rig, "Daz%s" % self.morphset,
                                   rig.data, "DazIndex%s" % self.morphset )


class DAZ_PT_MorphGroup(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Morphs"
    morphset = "All"

    @classmethod
    def poll(self, context):
        return getRuntimeEnabled(context)

    def draw(self, context):
        rig = self.getCurrentRig(context)
        if not rig:
            return
        if rig.DazDriversDisabled:
            self.layout.label(text = "Morph Drivers Disabled")
            self.layout.operator("daz.enable_drivers")
            return
        else:
            self.layout.operator("daz.disable_drivers")
        self.preamble(self.layout, rig)
        if GS.ercMethod == 'ARMATURE' and rig.DazRig.startswith("genesis"):
            row = self.layout.row()
            row.operator("daz.morph_armature")
            row.prop(context.scene, "DazAutoMorphArmatures")
        prop = "Adjust Morph Strength"
        if prop in rig.keys():
            self.layout.prop(rig, propRef(prop))


class DAZ_UL_Standard(DAZ_UL_StandardMorphs):
    morphset = "Standard"

class DAZ_PT_Standard(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Unclassified Standard Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Standard"
    ftype = "DazStandard"
    uilist = "DAZ_UL_Standard"


class DAZ_UL_Units(DAZ_UL_StandardMorphs):
    morphset = "Units"

class DAZ_PT_Units(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Face Units"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Units"
    ftype = "DazUnits"
    uilist = "DAZ_UL_Units"


class DAZ_UL_Head(DAZ_UL_StandardMorphs):
    morphset = "Head"

class DAZ_PT_Head(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Head"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Head"
    ftype = "DazHead"
    uilist = "DAZ_UL_Head"


class DAZ_UL_Expressions(DAZ_UL_StandardMorphs):
    morphset = "Expressions"

class DAZ_PT_Expressions(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Expressions"
    ftype = "DazExpressions"
    uilist = "DAZ_UL_Expressions"


class DAZ_UL_Visemes(DAZ_UL_StandardMorphs):
    morphset = "Visemes"

class DAZ_PT_Visemes(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Visemes"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Visemes"
    ftype = "DazVisemes"
    uilist = "DAZ_UL_Visemes"

    def draw(self, context):
        self.layout.operator("daz.load_moho")
        DAZ_PT_Morphs.draw(self, context)


class DAZ_UL_Facs(DAZ_UL_StandardMorphs):
    morphset = "Facs"

class DAZ_PT_Facs(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "FACS"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facs"
    ftype = "DazFacs"
    uilist = "DAZ_UL_Facs"

    def preamble(self, layout, rig):
        layout.operator("daz.import_facecap")
        layout.operator("daz.import_livelink")
        DAZ_PT_Morphs.preamble(self, layout, rig)


class DAZ_UL_FacsDetails(DAZ_UL_StandardMorphs):
    morphset = "Facsdetails"

class DAZ_PT_FacsDetails(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "FACS Details"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facsdetails"
    ftype = "DazFacsdetails"
    uilist = "DAZ_UL_FacsDetails"


class DAZ_UL_FacsExpressions(DAZ_UL_StandardMorphs):
    morphset = "Facsexpr"

class DAZ_PT_FacsExpressions(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "FACS Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facsexpr"
    ftype = "DazFacsexpr"
    uilist = "DAZ_UL_FacsExpressions"


class DAZ_UL_Body(DAZ_UL_StandardMorphs):
    morphset = "Body"

class DAZ_PT_Body(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Body Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Body"
    ftype = "DazBody"
    uilist = "DAZ_UL_Body"


class DAZ_UL_JCMs(DAZ_UL_StandardMorphs):
    morphset = "Jcms"

class DAZ_PT_JCMs(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "JCMs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Jcms"
    ftype = "DazJcms"
    uilist = "DAZ_UL_JCMs"


class DAZ_UL_Flexions(DAZ_UL_StandardMorphs):
    morphset = "Flexions"

class DAZ_PT_Flexions(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Flexions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Flexions"
    ftype = "DazFlexions"
    uilist = "DAZ_UL_Flexions"


class DAZ_UL_Baked(DAZ_UL_StandardMorphs):
    morphset = "Baked"

class DAZ_PT_Baked(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Baked"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Baked"
    ftype = "DazBaked"
    uilist = "DAZ_UL_Baked"

    def hasTheseMorphs(self, rig):
        return (rig.DazBaked and GS.useBakedMorphs)

    def draw(self, context):
        rig = self.getCurrentRig(context)
        if not self.hasTheseMorphs(rig):
            return
        for item in rig.DazBaked.values():
            value = rig.get(item.name)
            if value is not None:
                self.layout.label(text = "%s : %.3f" % (item.text, value))

#------------------------------------------------------------------------
#    Custom panels
#------------------------------------------------------------------------

class CustomDrawItems:
    def drawItems(self, scn, ob):
        row = self.layout.row()
        op = row.operator("daz.toggle_all_cats", text="Open All Categories")
        op.useOpen = True
        op.useMesh = self.useMesh
        op = row.operator("daz.toggle_all_cats", text="Close All Categories")
        op.useOpen = False
        op.useMesh = self.useMesh
        row.operator("daz.update_scrollbars")
        self.layout.separator()
        for cat in ob.DazMorphCats:
            box = self.layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name, icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name, icon="DOWNARROW_HLT", emboss=False)
            self.drawCustomBox(box, cat, scn, ob)


class DAZ_PT_CustomMorphs(DAZ_PT_Morphs, bpy.types.Panel, CustomDrawItems):
    bl_label = "Custom Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"

    def hasTheseMorphs(self, ob):
        return ob.DazCustomMorphs

    def preamble(self, layout, rig):
        pass

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob

    def drawCustomBox(self, box, cat, scn, rig):
        from .uilist import getCustomUIList
        adj = "Adjust Custom/%s" % cat.name
        if adj in rig.keys():
            box.prop(rig, propRef(adj))
        if len(cat.morphs) == 0:
            return
        ftype = "Custom/%s" % cat.name
        self.activateLayout(box, cat.name, ftype, rig)
        self.keyLayout(box, cat.name, ftype, rig)
        uilist = getCustomUIList(cat, scn)
        self.layout.template_list(uilist, "", cat, "morphs", cat, "index")


class DAZ_PT_CustomMeshMorphs(DAZ_PT_Morphs, bpy.types.Panel, CustomDrawItems):
    bl_label = "Mesh Shape Keys"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"
    useMesh = True

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and self.hasTheseMorphs(self, ob))

    def hasTheseMorphs(self, ob):
        return (ob.DazMeshMorphs or len(ob.DazAutoFollow) > 0)

    def draw(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and len(ob.DazAutoFollow) > 0:
            box = self.layout.box()
            box.label(text = "Auto Follow")
            for item in ob.DazAutoFollow:
                sname = item.name
                if (sname in ob.keys() and
                    sname in skeys.key_blocks.keys()):
                    skey = skeys.key_blocks[sname]
                    self.drawAutoItem(box, ob, skey, sname, item.text)
            self.layout.separator()
        if ob.DazMeshMorphs:
            DAZ_PT_Morphs.draw(self, context)


    def drawAutoItem(self, layout, ob, skey, sname, text):
        if GS.showFinalProps:
            split = layout.split(factor=0.8)
            split.prop(ob, propRef(sname), text=text)
            split.label(text = "%.3f" % skey.value)
        else:
            layout.prop(ob, propRef(sname), text=text)

    def getCurrentRig(self, context):
        return context.object

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob.data.shape_keys

    def setMorphsBtn(self, layout):
        return layout.operator("daz.set_shapes")

    def keyLayout(self, layout, category, ftype, rig):
        split = layout.split(factor=0.333)
        op = split.operator("daz.key_shapes", text="", icon='KEY_HLT')
        op.category = category
        op.ftype = ftype
        op = split.operator("daz.unkey_shapes", text="", icon='KEY_DEHLT')
        op.category = category
        op.ftype = ftype
        op = split.operator("daz.clear_shapes", text="", icon='X')
        op.category = category
        op.ftype = ftype


    def drawCustomBox(self, box, cat, scn, ob):
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        from .uilist import getShapeUIList
        ftype = "Mesh/%s" % cat.name
        self.activateLayout(box, cat.name, ftype, ob)
        self.keyLayout(box, cat.name, ftype, ob)
        uilist = getShapeUIList(cat, scn)
        self.layout.template_list(uilist, "", cat, "morphs", cat, "index")

#------------------------------------------------------------------------
#    Simple IK Panels
#------------------------------------------------------------------------

class DAZ_PT_DazSimpleLayers(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Layers"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (getRuntimeEnabled(context) and ob and ob.DazSimpleIK)

    def draw(self, context):
        rig = context.object
        self.layout.label(text="Layers")
        row = self.layout.row()
        row.operator("daz.select_named_layers")
        row.operator("daz.unselect_named_layers")
        self.layout.separator()
        layers = [
            (S_SPINE, S_FACE),
            (S_LARMFK, S_RARMFK),
            (S_LARMIK, S_RARMIK),
            (S_LLEGFK, S_RLEGFK),
            (S_LLEGIK, S_RLEGIK),
            (S_LHAND, S_RHAND),
            (S_LFOOT, S_RFOOT),
            (S_SPECIAL, None)]
        for m,n in layers:
            row = self.layout.row()
            if BLENDER3:
                row.prop(rig.data, "layers", index=m, toggle=True, text=SimpleLayers[m])
                if n:
                    row.prop(rig.data, "layers", index=n, toggle=True, text=SimpleLayers[n])
            else:
                cname = SimpleLayers[m]
                coll = rig.data.collections[cname]
                row.prop(coll, "is_visible", toggle=True, text=cname)
                if n:
                    cname = SimpleLayers[n]
                    coll = rig.data.collections[cname]
                    row.prop(coll, "is_visible", toggle=True, text=cname)


class DAZ_PT_DazSimpleIK(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Simple IK"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (getRuntimeEnabled(context) and ob and ob.DazSimpleIK)

    def draw(self, context):
        rig = context.object
        layout = self.layout
        layout.label(text="IK Influence")
        split = layout.split(factor=0.2)
        split.label(text="")
        split.label(text="Left")
        split.label(text="Right")
        split = layout.split(factor=0.2)
        split.label(text="Arm")
        split.prop(rig, "DazArmIK_L", text="")
        split.prop(rig, "DazArmIK_R", text="")
        split = layout.split(factor=0.2)
        split.label(text="Leg")
        split.prop(rig, "DazLegIK_L", text="")
        split.prop(rig, "DazLegIK_R", text="")

        layout.label(text="Snap FK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op.on = S_LARMFK
        op.off = S_LARMIK
        op = row.operator("daz.snap_simple_fk", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        op.on = S_RARMFK
        op.off = S_RARMIK
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op.on = S_LLEGFK
        op.off = S_LLEGIK
        op = row.operator("daz.snap_simple_fk", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"
        op.on = S_RLEGFK
        op.off = S_RLEGIK

        layout.label(text="Snap IK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op.pole = "lElbow"
        op.on = S_LARMIK
        op.off = S_LARMFK
        op = row.operator("daz.snap_simple_ik", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        op.pole = "rElbow"
        op.on = S_RARMIK
        op.off = S_RARMFK
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op.pole = "lKnee"
        op.on = S_LLEGIK
        op.off = S_LLEGFK
        op = row.operator("daz.snap_simple_ik", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"
        op.pole = "rKnee"
        op.on = S_RLEGIK
        op.off = S_RLEGFK

        layout.separator()
        layout.operator("daz.snap_all_simple_fk")
        layout.operator("daz.snap_all_simple_ik")
        layout.prop(rig, "DazRotLimits")

#------------------------------------------------------------------------
#   Visibility panels
#------------------------------------------------------------------------

class DAZ_PT_Visibility(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Visibility"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (getRuntimeEnabled(context) and ob and ob.DazVisibilityDrivers)

    def draw(self, context):
        pass


class DAZ_PT_ClothesVisibility(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Clothes"
    bl_parent_id = "DAZ_PT_Visibility"

    def draw(self, context):
        rig = context.object
        if rig.type == 'MESH':
            rig = rig.parent
        if rig and rig.type == 'ARMATURE':
            props = list(rig.keys())
            props.sort()
            if props:
                row = self.layout.row()
                row.operator("daz.show_all_vis")
                row.operator("daz.hide_all_vis")
                self.drawProps(rig, props, "Mhh")
                self.drawProps(rig, props, "DzS")

    def drawProps(self, rig, props, prefix):
        for prop in props:
            if prop[0:3] == prefix:
                icon = 'CHECKBOX_HLT' if rig[prop] else 'CHECKBOX_DEHLT'
                op = self.layout.operator("daz.toggle_vis", text=prop[3:], icon=icon, emboss=False)
                op.name = prop


class DAZ_PT_ShellVisibility(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Shells"
    bl_parent_id = "DAZ_PT_Visibility"

    def draw(self, context):
        ob = context.object
        props = [prop for prop in ob.keys() if prop[0:6] == "INFLU "]
        props.sort()
        if props:
            row = self.layout.row()
            op = row.operator("daz.set_shell_influence", text="All")
            op.value = 1.0
            op = row.operator("daz.set_shell_influence", text="None")
            op.value = 0.0
            for prop in props:
                row = self.layout.row()
                row.prop(ob, propRef(prop), text=prop[6:])
                icon = 'CHECKBOX_HLT' if ob[prop] > 0 else 'CHECKBOX_DEHLT'
                op = row.operator("daz.toggle_shell_influence", text="", icon=icon, emboss=False)
                op.prop = prop
        else:
            self.layout.operator("daz.set_shell_visibility")

#------------------------------------------------------------------------
#   DAZ Rigify props panels
#------------------------------------------------------------------------

class DAZ_PT_DazRigifyProps(bpy.types.Panel):
    bl_label = "DAZ Rigify Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and
                ob.DazRig in ["rigify", "rigify2"])

    def draw(self, context):
        rig = context.object
        self.layout.prop(rig, "MhaGazeFollowsHead", text="Gaze Follows Head")
        self.layout.prop(rig, "MhaGaze_L", text="Left Gaze")
        self.layout.prop(rig, "MhaGaze_R", text="Right Gaze")
        if rig.data.MhaFeatures & F_TONGUE:
            self.layout.prop(rig, "MhaTongueIk", text="Tongue IK")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_Setup,
    DAZ_PT_SetupCorrections,
    DAZ_PT_SetupMaterials,
    DAZ_PT_SetupMorphs,
    DAZ_PT_SetupVisibility,
    DAZ_PT_SetupHair,
    DAZ_PT_SetupFinishing,
    DAZ_PT_SetupRigging,

    DAZ_PT_Advanced,
    DAZ_PT_AdvancedLowpoly,
    DAZ_PT_AdvancedHDMesh,
    DAZ_PT_AdvancedMaterials,
    DAZ_PT_AdvancedMesh,
    DAZ_PT_AdvancedSimulation,
    DAZ_PT_AdvancedRigging,
    DAZ_PT_AdvancedMorphs,

    DAZ_PT_Utils,
    DAZ_PT_Runtime,
    DAZ_PT_Posing,
    DAZ_PT_LocksLimits,

    DAZ_UL_Standard,
    DAZ_UL_Units,
    DAZ_UL_Head,
    DAZ_UL_Expressions,
    DAZ_UL_Visemes,
    DAZ_UL_Facs,
    DAZ_UL_FacsDetails,
    DAZ_UL_FacsExpressions,
    DAZ_UL_Body,
    DAZ_UL_JCMs,
    DAZ_UL_Flexions,
    DAZ_UL_Baked,

    DAZ_PT_MorphGroup,
    DAZ_PT_Standard,
    DAZ_PT_Units,
    DAZ_PT_Head,
    DAZ_PT_Expressions,
    DAZ_PT_Visemes,
    DAZ_PT_Facs,
    DAZ_PT_FacsDetails,
    DAZ_PT_FacsExpressions,
    DAZ_PT_Body,
    DAZ_PT_JCMs,
    DAZ_PT_Flexions,
    DAZ_PT_Baked,

    DAZ_PT_CustomMorphs,
    DAZ_PT_CustomMeshMorphs,
    DAZ_PT_Visibility,
    DAZ_PT_ClothesVisibility,
    DAZ_PT_ShellVisibility,
    DAZ_PT_DazRigifyProps,

    DAZ_PT_DazSimpleLayers,
    DAZ_PT_DazSimpleIK,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
