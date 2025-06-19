# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Rigging panel
#----------------------------------------------------------

import bpy
from ..utils import *
from ..panel import DAZ_PT_SetupTab
class DAZ_PT_DazRigifyBuild(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_label = "Rigify"

    def draw(self, context):
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")

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
        return (ob and dazRna(ob).DazRig.startswith("rigify"))

    def draw(self, context):
        rig = context.object

        box = self.layout.box()
        box.label(text="Gaze")
        box.prop(rig, propRef("MhaGazeFollowsHead"), text="Gaze Follows Head")
        row = box.row()
        row.prop(rig, propRef("MhaGaze_L"), text="Left Gaze")
        row.prop(rig, propRef("MhaGaze_R"), text="Right Gaze")

        if "MhaTongueIk" in rig.keys():
            box = self.layout.box()
            box.prop(rig, propRef("MhaTongueControl"), text="Tongue FK/IK")
            box.prop(rig, propRef("MhaTongueIk"), text="IK")
            parprops = [prop for prop in rig.keys() if prop.startswith("MhaTongue_")]
            for parprop in parprops:
                text = "%s Parent" % parprop[10:].capitalize()
                box.prop(rig, propRef(parprop), text=text)

        if "MhaShaftIk" in rig.keys():
            box = self.layout.box()
            box.prop(rig, propRef("MhaShaftControl"), text="Shaft FK/IK")
            box.prop(rig, propRef("MhaShaftIk"), text="IK")
            parprops = [prop for prop in rig.keys() if prop.startswith("MhaShaft_")]
            for parprop in parprops:
                text = "%s Parent" % parprop[9:].capitalize()
                box.prop(rig, propRef(parprop), text=text)

        box = self.layout.box()
        box.label(text="Arms And Legs")
        row = box.row()
        row.operator("daz.rigify_set_fk_all")
        row.operator("daz.rigify_set_ik_all")
        row = box.row()
        row.operator("daz.rigify_snap_fk_all")
        row.operator("daz.rigify_snap_ik_all")
        row = box.row()
        row.operator("daz.rigify_fk_layers")
        row.operator("daz.rigify_ik_layers")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_DazRigifyBuild,
    DAZ_PT_DazRigifyProps,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
