#  DAZ Hair - Tools for rigging figures imported with the DAZ Importer
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

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG
import bpy
BLENDER3 = (bpy.app.version < (4,0,0))

if not DEBUG:
    pass
elif "HairToolsFeature" in locals():
    print("Reloading Hair Tools")
    import imp
    imp.reload(hair_builder)
    imp.reload(make_hair)
    imp.reload(hair_rig)
    if BLENDER3:
        imp.reload(particles)
else:
    print("Loading Hair Tools")
    from . import hair_builder
    from . import make_hair
    from . import hair_rig
    if BLENDER3:
        from . import particles
    HairToolsFeature = True

#----------------------------------------------------------
#   Hair panel
#----------------------------------------------------------

from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Hair(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_Hair"
    bl_label = "Hair"

    def draw(self, context):
        from .make_hair import getHairAndHuman
        self.layout.operator("daz.make_hair")
        hair,hum = getHairAndHuman(context, False)
        self.layout.label(text = "  Hair:  %s" % (hair.name if hair else None))
        self.layout.label(text = "  Human: %s" % (hum.name if hum else None))


class DAZ_PT_HairSelect(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Hair"
    bl_idname = "DAZ_PT_HairSelect"
    bl_label = "Select Hairs"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.select_strands_by_size")
        self.layout.operator("daz.select_strands_by_width")
        self.layout.operator("daz.select_random_strands")


class DAZ_PT_HairProxy(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Hair"
    bl_idname = "DAZ_PT_HairProxy"
    bl_label = "Hair Proxy"

    def draw(self, context):
        self.layout.operator("daz.make_hair_proxy")
        self.layout.operator("daz.mesh_add_pinning")
        self.layout.separator()
        self.layout.operator("daz.add_hair_rig")
        self.layout.operator("daz.set_envelopes")
        self.layout.operator("daz.toggle_hair_locks")


if BLENDER3:
    class DAZ_PT_HairParticles(DAZ_PT_SetupTab, bpy.types.Panel):
        bl_parent_id = "DAZ_PT_Hair"
        bl_idname = "DAZ_PT_HairParticles"
        bl_label = "Hair Particles"

        def draw(self, context):
            self.layout.operator("daz.update_hair")
            self.layout.operator("daz.color_hair")
            self.layout.operator("daz.combine_hairs")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

classes = [
    DAZ_PT_Hair,
    DAZ_PT_HairSelect,
    DAZ_PT_HairProxy,
]

def register():
    print("Register Hair Tools")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import hair_builder, make_hair, hair_rig, hair_select
    hair_builder.register()
    make_hair.register()
    hair_rig.register()
    hair_select.register()
    if BLENDER3:
        bpy.utils.register_class(DAZ_PT_HairParticles)
        from .import particles
        particles.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    from . import hair_builder, make_hair, hair_rig, hair_select
    hair_builder.unregister()
    make_hair.unregister()
    hair_rig.unregister()
    hair_select.unregister()
    if BLENDER3:
        bpy.utils.unregister_class(DAZ_PT_HairParticles)
        from .import particles
        particles.unregister()


