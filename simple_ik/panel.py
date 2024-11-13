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

#------------------------------------------------------------------------
#    Simple IK Panels
#------------------------------------------------------------------------

import bpy
from .layers import *
from ..panel import DAZ_PT_SetupTab, DAZ_PT_RuntimeTab

class DAZ_PT_SetupSimple(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_SetupRigging"
    bl_idname = "DAZ_PT_SetupSimple"
    bl_label = "Simple IK"

    def draw(self, context):
        self.layout.operator("daz.add_simple_ik")


class DAZ_PT_DazSimpleIK(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_label = "Simple IK"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.DazSimpleIK)

    def draw(self, context):
        rig = context.object


class DAZ_PT_DazSimpleLayers(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_DazSimpleIK"
    bl_label = "Layers"

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
            (S_TWEAK, S_SPECIAL)]
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


class DAZ_PT_DazSimpleFKIK(DAZ_PT_RuntimeTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_DazSimpleIK"
    bl_label = "FK/IK"

    def draw(self, context):
        def toggleFKIK(row, prop, limb):
            if getattr(rig, prop) > 0.5:
                text = "IK"
                value = 0.0
            else:
                text = "FK"
                value = 1.0
            op = row.operator("daz.toggle_fk_ik", text="%s %s" % (limb, text))
            op.prop = prop
            op.value = value

        rig = context.object
        layout = self.layout
        row = layout.row()
        row.label(text = "Left")
        row.label(text = "Right")
        row = layout.row()
        toggleFKIK(row, "DazArmIK_L", "Arm")
        toggleFKIK(row, "DazArmIK_R", "Arm")
        row = layout.row()
        toggleFKIK(row, "DazLegIK_L", "Leg")
        toggleFKIK(row, "DazLegIK_R", "Leg")
        layout.label(text="IK Influence")
        row = layout.row()
        row.prop(rig, "DazArmIK_L", text="Arm")
        row.prop(rig, "DazArmIK_R", text="Arm")
        row = layout.row()
        row.prop(rig, "DazLegIK_L", text="Leg")
        row.prop(rig, "DazLegIK_R", text="Leg")
        layout.label(text="IK Stretchiness")
        row = layout.row()
        row.prop(rig, "DazStretchArms", text="Arms")
        row.prop(rig, "DazStretchLegs", text="Legs")

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
        layout.operator("daz.disable_locks_limits")
        layout.operator("daz.snap_all_simple_fk")
        layout.operator("daz.snap_all_simple_ik")
        layout.operator("daz.snap_simple_fk_animation")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_SetupSimple,
    DAZ_PT_DazSimpleIK,
    DAZ_PT_DazSimpleLayers,
    DAZ_PT_DazSimpleFKIK,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
