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
from .utils import *
from .buildnumber import BUILD
from .uilist import DAZ_UL_StandardMorphs
from .morphing import MS

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

class DAZ_PT_SetupTab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Setup"
    bl_options = {'DEFAULT_CLOSED'}


class DAZ_PT_RuntimeTab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Runtime"
    bl_options = {'DEFAULT_CLOSED'}

#----------------------------------------------------------
#   Setup tab
#----------------------------------------------------------

class DAZ_PT_Setup(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "DAZ Setup (version 4.3.0.%04d)" % BUILD
    bl_options = set()

    def draw(self, context):
        scn = context.scene
        self.layout.operator("daz.easy_import_daz")
        self.layout.prop(scn, "DazFavoPath")
        self.layout.separator()
        self.layout.operator("daz.import_daz_manually")
        self.layout.separator()
        self.layout.operator("daz.global_settings")
        self.layout.prop(scn, "DazPreferredRoot")

#----------------------------------------------------------
#   Corrections
#----------------------------------------------------------

class DAZ_PT_SetupCorrections(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupCorrections"
    bl_label = "Corrections"

    def draw(self, context):
        self.layout.operator("daz.eliminate_empties")
        self.layout.operator("daz.merge_rigs")
        self.layout.operator("daz.apply_transforms")
        self.layout.operator("daz.merge_toes")
        self.layout.separator()
        self.layout.operator("daz.copy_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.apply_active_shapekey")
        self.layout.operator("daz.change_armature")

#----------------------------------------------------------
#   Materials
#----------------------------------------------------------

class DAZ_PT_SetupMaterials(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.import_daz_materials")
        self.layout.separator()
        self.layout.operator("daz.save_local_textures")
        self.layout.operator("daz.resize_textures")
        self.layout.separator()
        self.layout.operator("daz.merge_materials")
        self.layout.operator("daz.change_colors")

#----------------------------------------------------------
#   Morphs
#----------------------------------------------------------

class DAZ_PT_SetupMorphs(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        ob = context.object
        rig = getRigFromContext(context)
        if ob and ob.type in ['ARMATURE', 'MESH'] and ob.DazId:
            if rig and rig.DazDriversDisabled:
                self.layout.label(text = "Morph Drivers Disabled")
                self.layout.operator("daz.enable_drivers")
                return
            self.layout.operator("daz.import_standard_morphs")
            self.layout.operator("daz.import_custom_morphs")
            self.layout.operator("daz.import_dbz")
            self.layout.separator()
            self.layout.operator("daz.import_baked_correctives")
            self.layout.operator("daz.import_daz_favorites")
            self.layout.operator("daz.save_favo_morphs")
            self.layout.operator("daz.load_favo_morphs")
            self.layout.separator()
        self.layout.operator("daz.transfer_shapekeys")


class DAZ_PT_SetupStandardMorphs(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupMorphs"
    bl_idname = "DAZ_PT_SetupStandardMorphs"
    bl_label = "Standard Morphs"

    def draw(self, context):
        self.layout.operator("daz.import_units")
        self.layout.operator("daz.import_expressions")
        self.layout.operator("daz.import_visemes")
        self.layout.operator("daz.import_head")
        self.layout.operator("daz.import_facs")
        self.layout.operator("daz.import_facs_details")
        self.layout.operator("daz.import_facs_expressions")
        self.layout.operator("daz.import_powerpose")
        self.layout.operator("daz.import_anime")
        self.layout.operator("daz.import_body_morphs")
        self.layout.separator()
        self.layout.operator("daz.import_jcms")
        self.layout.operator("daz.import_masculine")
        self.layout.operator("daz.import_feminine")
        self.layout.operator("daz.import_flexions")
        self.layout.operator("daz.create_bulges")

#----------------------------------------------------------
#   Finishing
#----------------------------------------------------------

class DAZ_PT_SetupFinishing(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupFinishing"
    bl_label = "Finishing"

    def draw(self, context):
        self.layout.operator("daz.merge_geografts")
        self.layout.operator("daz.convert_widgets")
        self.layout.operator("daz.finalize_meshes")
        self.layout.separator()
        self.layout.operator("daz.make_all_bones_posable")
        self.layout.operator("daz.optimize_drivers")
        self.layout.operator("daz.remove_corrupt_drivers")
        self.layout.operator("daz.finalize_armature")
        self.layout.operator("daz.apply_rest_pose")

#----------------------------------------------------------
#   Rigging
#----------------------------------------------------------

class DAZ_PT_SetupRigging(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_SetupRigging"
    bl_label = "Rigging"

    def draw(self, context):
        pass

#----------------------------------------------------------
#   Utilities panel
#----------------------------------------------------------

class DAZ_PT_Utils(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_label = "Utilities"

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
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
            if ob.parent and ob.parent_type.startswith('VERTEX'):
                self.propRow(box, ob, "parent_vertices", "ParVerts")
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
        layout.operator("daz.select_parent_verts")
        layout.operator("daz.enable_all_layers")
        layout.operator("daz.add_content_dirs")


    def propRow(self, layout, rna, prop, text=None):
        if text is None:
            text = prop[3:]
        row = layout.row()
        row.label(text=text)
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
    bl_label = "DAZ Runtime (version 4.3.0.%04d)" % BUILD
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


class DAZ_PT_MorePosing(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Posing"
    bl_label = "More Posing Tools"

    def draw(self, context):
        self.layout.operator("daz.copy_absolute_pose")
        self.layout.operator("daz.prune_action")
        self.layout.separator()
        self.layout.operator("daz.bake_pose_to_fk_rig")
        self.layout.operator("daz.bake_shapekeys")
        self.layout.operator("daz.mute_control_rig")
        self.layout.operator("daz.unmute_control_rig")
        self.layout.operator("daz.transfer_to_gaze")
        self.layout.operator("daz.transfer_from_gaze")


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

#----------------------------------------------------------
#   Morphs panel
#----------------------------------------------------------

class DAZ_PT_Morphs(DAZ_PT_RuntimeTab):
    useMesh = False

    @classmethod
    def poll(self, context):
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
        prop = "Daz%s" % self.morphset
        return getattr(rig, prop)


    def hasAdjustProp(self, rig):
        adj = MS.Adjusters.get(self.morphset, "")
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
        return True

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
        if GS.ercMethod in ('ARMATURE', 'ALL') and rig.DazRig.startswith("genesis"):
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
        layout.label(text="FaceCap and LiveLink")
        layout.label(text="moved to BVH Retargeter")
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


class DAZ_UL_Anime(DAZ_UL_StandardMorphs):
    morphset = "Anime"

class DAZ_PT_Anime(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Anime"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Anime"
    ftype = "DazAnime"
    uilist = "DAZ_UL_Anime"


class DAZ_UL_Powerpose(DAZ_UL_StandardMorphs):
    morphset = "Powerpose"

class DAZ_PT_Powerpose(DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "PowerPose"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Powerpose"
    ftype = "DazPowerpose"
    uilist = "DAZ_UL_Powerpose"


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
        return rig.DazBaked #and GS.useBakedMorphs)

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


    def drawCustomBox(self, box, cat, scn, rig):
        adj = self.getCatAdjuster(cat)
        if adj in rig.keys():
            box.prop(rig, propRef(adj))
        if len(cat.morphs) == 0:
            return
        ftype = self.getCatFtype(cat)
        self.activateLayout(box, cat.name, ftype, rig)
        self.keyLayout(box, cat.name, ftype, rig)
        uilist = self.getUIList(cat, scn)
        self.layout.template_list(uilist, "", cat, "morphs", cat, "index")


class DAZ_PT_CustomMorphs(CustomDrawItems, DAZ_PT_Morphs, bpy.types.Panel):
    bl_label = "Custom Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"

    def hasTheseMorphs(self, ob):
        return ob.DazCustomMorphs

    def preamble(self, layout, rig):
        pass

    def getRna(self, ob):
        return ob

    def getCatAdjuster(self, cat):
        return "Adjust Custom/%s" % cat.name

    def getCatFtype(self, cat):
        return "Custom/%s" % cat.name

    def getUIList(self, cat, scn):
        from .uilist import getCustomUIList
        return getCustomUIList(cat, scn)


class DAZ_PT_CustomMeshMorphs(CustomDrawItems, DAZ_PT_Morphs, bpy.types.Panel):
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
            if GS.useMeshDrivers:
                prop = "Adjust Morph Strength"
                if prop in ob.keys():
                    self.layout.prop(ob, propRef(prop))
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

    def getRna(self, ob):
        return ob.data.shape_keys

    def setMorphsBtn(self, layout):
        return layout.operator("daz.set_shapes")

    def getCatAdjuster(self, cat):
        return "Adjust Custom/%s" % cat.name

    def getCatFtype(self, cat):
        return "Mesh/%s" % cat.name

    def getUIList(self, cat, scn):
        from .uilist import getShapeUIList
        return getShapeUIList(cat, scn)


    def keyShapeLayout(self, layout, category, ftype, rig):
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
        if GS.useMeshDrivers:
            CustomDrawItems.drawCustomBox(self, box, cat, scn, ob)
            return
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        ftype = self.getCatFtype(cat)
        self.activateLayout(box, cat.name, ftype, ob)
        self.keyShapeLayout(box, cat.name, ftype, ob)
        uilist = self.getUIList(cat, scn)
        self.layout.template_list(uilist, "", cat, "morphs", cat, "index")

#------------------------------------------------------------------------
#   Visibility panels
#------------------------------------------------------------------------

class DAZ_PT_Visibility(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Visibility"

    @classmethod
    def poll(cls, context):
        return context.object

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
        from .matsel import getShellProps
        props = getShellProps(context)
        props.sort()
        if props:
            row = self.layout.row()
            op = row.operator("daz.set_shell_influence", text="All")
            op.value = 1.0
            op = row.operator("daz.set_shell_influence", text="None")
            op.value = 0.0
            self.layout.prop(context.scene, "DazFilter", icon='VIEWZOOM', text="")
            for prop,ob in props:
                row = self.layout.row()
                row.prop(ob, propRef(prop), text=prop[6:])
                icon = 'CHECKBOX_HLT' if ob[prop] > 0 else 'CHECKBOX_DEHLT'
                op = row.operator("daz.toggle_shell_influence", text="", icon=icon, emboss=False)
                op.prop = prop
                op.object = ob.name

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_Setup,
    DAZ_PT_SetupCorrections,
    DAZ_PT_SetupMaterials,
    DAZ_PT_SetupMorphs,
    DAZ_PT_SetupStandardMorphs,
    DAZ_PT_SetupFinishing,
    DAZ_PT_SetupRigging,

    DAZ_PT_Utils,
    DAZ_PT_Runtime,
    DAZ_PT_Posing,
    DAZ_PT_MorePosing,
    DAZ_PT_LocksLimits,

    DAZ_UL_Standard,
    DAZ_UL_Units,
    DAZ_UL_Head,
    DAZ_UL_Expressions,
    DAZ_UL_Visemes,
    DAZ_UL_Facs,
    DAZ_UL_FacsDetails,
    DAZ_UL_FacsExpressions,
    DAZ_UL_Anime,
    DAZ_UL_Powerpose,
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
    DAZ_PT_Anime,
    DAZ_PT_Powerpose,
    DAZ_PT_Body,
    DAZ_PT_JCMs,
    DAZ_PT_Flexions,
    DAZ_PT_Baked,

    DAZ_PT_CustomMorphs,
    DAZ_PT_CustomMeshMorphs,
    DAZ_PT_Visibility,
    DAZ_PT_ClothesVisibility,
    DAZ_PT_ShellVisibility,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
