# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..guess import ColorProp
from ..selector import Selector
from .make_hair import CombineHair, HairOptions

#------------------------------------------------------------------------
#   Buttons
#------------------------------------------------------------------------

class IsHair:
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.particle_systems.active)

#------------------------------------------------------------------------
#   Hair Update
#------------------------------------------------------------------------

class HairUpdater:

    def getAllSettings(self, psys):
        psettings = self.getSettings(psys.settings)
        hdyn = psys.use_hair_dynamics
        if psys.cloth:
            csettings = self.getSettings(psys.cloth.settings)
        else:
            csettings = None
        return psettings, hdyn, csettings


    def setAllSettings(self, psys, data):
        psettings, hdyn, csettings = data
        self.setSettings(psys.settings, psettings)
        psys.use_hair_dynamics = hdyn
        if csettings is not None:
            self.setSettings(psys.cloth.settings, csettings)


    def getSettings(self, pset):
        settings = {}
        for key in dir(pset):
            attr = getattr(pset, key)
            if (key[0] == "_" or
                key in ["count"] or
                (key in ["material", "material_slot"] and
                 not self.affectMaterial)):
                continue
            if (
                isinstance(attr, int) or
                isinstance(attr, bool) or
                isinstance(attr, float) or
                isinstance(attr, str)
                ):
                settings[key] = attr
        return settings


    def setSettings(self, pset, settings):
        for key,value in settings.items():
            if key in ["use_absolute_path_time"]:
                continue
            try:
                setattr(pset, key, value)
            except AttributeError:
                pass


class DAZ_OT_UpdateHair(DazPropsOperator, HairUpdater, IsHair):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Copy settings from active particle system to all other particle systems"
    bl_options = {'UNDO'}

    affectMaterial : BoolProperty(
        name = "Affect Material",
        description = "Also change materials",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "affectMaterial")

    def run(self, context):
        hum = context.object
        psys0 = hum.particle_systems.active
        idx0 = hum.particle_systems.active_index
        data = self.getAllSettings(psys0)
        for idx,psys in enumerate(hum.particle_systems):
            if idx == idx0:
                continue
            hum.particle_systems.active_index = idx
            self.setAllSettings(psys, data)
        hum.particle_systems.active_index = idx0

#------------------------------------------------------------------------
#   Combine Hairs
#------------------------------------------------------------------------

class DAZ_OT_CombineHairs(DazOperator, CombineHair, HairUpdater, Selector, HairOptions):
    bl_idname = "daz.combine_hairs"
    bl_label = "Combine Hairs"
    bl_description = "Combine several hair particle systems into a single one"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.particle_systems) > 0)

    def draw(self, context):
        self.layout.prop(self, "size")
        Selector.draw(self, context)

    def invoke(self, context, event):
        return Selector.invoke(self, context, event)

    def getKeys(self, rig, ob):
        enums = []
        for n,psys in enumerate(ob.particle_systems):
            if psys.settings.type == 'HAIR':
                text = "(%3d)   %s" % (psys.settings.hair_step+1, psys.name)
                enum = (str(n), text, "All")
                enums.append(enum)
        return enums

    def getStrand(self, strand):
        return 0, len(strand), strand

    def getHairKey(self, n, mnum):
        mat = self.materials[0]
        return ("%d_%s" % (n, mat.name)), 0


    def getStrandsFromPsys(self, psys):
        strands = []
        for hair in psys.particles:
            strand = [v.co.copy() for v in hair.hair_keys]
            strands.append(strand)
        return strands


    def run(self, context):
        scn = context.scene
        ob = context.object
        psystems = []
        hsystems = {}
        haircount = -1
        for item in self.getSelectedItems():
            idx = int(item.name)
            psys = ob.particle_systems[idx]
            psystems.append((idx, psys))
        if len(psystems) == 0:
            raise DazError("No particle system selected")
        idx0, psys0 = psystems[0]
        self.affectMaterial = False
        data = self.getAllSettings(psys0)
        mname = psys0.settings.material_slot
        mat = ob.data.materials[mname]
        self.materials = [mat]

        for idx,psys in psystems:
            ob.particle_systems.active_index = idx
            psys = updateHair(context, ob, psys)
            strands = self.getStrandsFromPsys(psys)
            haircount = self.addStrands(ob, strands, hsystems, haircount)
        psystems.reverse()
        for idx,psys in psystems:
            ob.particle_systems.active_index = idx
            bpy.ops.object.particle_system_remove()
        hsystems = self.hairResize(self.size, hsystems, ob)
        for hsys in hsystems.values():
            hsys.build(context, ob)
        psys = ob.particle_systems.active
        self.setAllSettings(psys, data)

#------------------------------------------------------------------------
#   Color Hair
#------------------------------------------------------------------------

class DAZ_OT_ColorHair(DazPropsOperator, IsHair, ColorProp):
    bl_idname = "daz.color_hair"
    bl_label = "Color Hair"
    bl_description = "Change particle hair color"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        hum = context.object
        fade = False
        mats = {}
        for mat in hum.data.materials:
            mats[mat.name] = (mat, True)
        for psys in hum.particle_systems:
            pset = psys.settings
            mname = pset.material_slot
            if mname in mats.keys() and mats[mname][1]:
                mat = buildHairMaterial(mname, self.color, None, context, force=True)
                if fade:
                    addFade(mat, None)
                mats[mname] = (mat, False)

        for _,keep in mats.values():
            if not keep:
                hum.data.materials.pop()
        for mat,keep in mats.values():
            if not keep:
                hum.data.materials.append(mat)

#------------------------------------------------------------------------
#   Connect Hair - seems unused
#------------------------------------------------------------------------

class DAZ_OT_ConnectHair(DazOperator, IsHair):
    bl_idname = "daz.connect_hair"
    bl_label = "Connect Hair"
    bl_description = "(Re)connect hair"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        for mod in hum.modifiers:
            if isinstance(mod, bpy.types.ParticleSystemModifier):
                print(mod)

        nparticles = len(hum.particle_systems)
        for n in range(nparticles):
            hum.particle_systems.active_index = n
            print(hum.particle_systems.active_index, hum.particle_systems.active)
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.disconnect_hair()
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.connect_hair()
            bpy.ops.particle.particle_edit_toggle()

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_CombineHairs,
    DAZ_OT_UpdateHair,
    DAZ_OT_ColorHair,
    DAZ_OT_ConnectHair,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
