# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *

#-------------------------------------------------------------
#   Constraints class
#-------------------------------------------------------------

ConstraintAttributes = [
    "type", "name", "mute", "target", "subtarget", "mix_mode", "use_transform_limit",
    "head_tail", "use_offset", "owner_space", "target_space", "euler_order",
    "use_x", "use_y", "use_z",
    "invert_x", "invert_y", "invert_z",
    "use_limit_x", "use_limit_y", "use_limit_z",
    "use_min_x", "use_min_y", "use_min_z",
    "use_max_x", "use_max_y", "use_max_z",
    "min_x", "min_y", "min_z",
    "max_x", "max_y", "max_z",
    "influence",
]

def copyConstraints(src, trg, rig=None):
    for scns in src.constraints:
        copyConstraint(scns, trg, rig)


def copyConstraint(scns, trg, rig):
    tcns = trg.constraints.new(scns.type)
    for attr in ConstraintAttributes:
        if (hasattr(scns, attr) and attr != "type"):
            setattr(tcns, attr, getattr(scns, attr))
    if rig and hasattr(tcns, "target"):
        tcns.target = rig


class ConstraintStore:
    def __init__(self):
        self.constraints = {}


    def storeConstraints(self, key, pb):
        clist = []
        for cns in pb.constraints:
            struct = {}
            for attr in ConstraintAttributes:
                if hasattr(cns, attr):
                    struct[attr] = getattr(cns, attr)
            clist.append(struct)
        if clist and key:
            self.constraints[key] = clist


    def storeAllConstraints(self, rig):
        for pb in rig.pose.bones:
            self.storeConstraints(pb.name, pb)
            self.removeConstraints(pb)


    def getFkBone(self, key, rig):
        if len(key) > 2 and key[-2] == ".":
            base, suffix = key[:-2], key[-1]
            bname = "%s.fk.%s" % (base, suffix)
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
            bname = "%s_fk.%s" % (base, suffix)
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
        if key in rig.pose.bones.keys():
            return rig.pose.bones[key]
        return None


    def restoreAllConstraints(self, context, rig, ignore):
        for key,clist in self.constraints.items():
            if key:
                pb = self.getFkBone(key, rig)
                if pb and pb.name not in ignore:
                    for struct in clist:
                        self.restoreConstraint(struct, pb)

        def fixBendTwistMixup(cns):
            if hasattr(cns, "target") and cns.target == rig and hasattr(cns, "subtarget"):
                bname = cns.subtarget
                if bname not in rig.data.bones:
                    bname1 = bname.replace("Bend.", ".bend.").replace("Twist.", ".twist.")
                    if bname1 in rig.data.bones:
                        cns.subtarget = bname1

        for ob in context.view_layer.objects:
            for cns in ob.constraints:
                fixBendTwistMixup(cns)
            if ob.type == 'ARMATURE':
                for pb in ob.pose.bones:
                    for cns in pb.constraints:
                        fixBendTwistMixup(cns)


    def restoreConstraints(self, key, pb, target=None):
        if key not in self.constraints.keys():
            return
        clist = self.constraints[key]
        for struct in clist:
            self.restoreConstraint(struct, pb, target)


    def restoreConstraint(self, struct, pb, target=None):
        ctype = struct["type"]
        cns = pb.constraints.new(ctype)
        for attr,value in struct.items():
            if attr != "type":
                setattr(cns, attr, value)
        if target and hasattr(cns, "target"):
            cns.target = target


    def removeConstraints(self, pb, onlyLimit=False):
        for cns in list(pb.constraints):
            if not onlyLimit or cns.type.startswith("LIMIT"):
                cns.driver_remove("influence")
                cns.driver_remove("mute")
                pb.constraints.remove(cns)

    #-------------------------------------------------------------
    #   Driver store
    #-------------------------------------------------------------

    def storeAllDrivers(self, rig, nrig, meshes):
        from .driver import Driver
        def storeDrivers(rna, key):
            if rna and rna.animation_data:
                drivers = self.drivers[key] = []
                for fcu in list(rna.animation_data.drivers):
                    if not someMatch([":Hdo:", ":Tlo:"], fcu.data_path):
                        driver = Driver(fcu, False)
                        drivers.append(driver)
                    rna.animation_data.drivers.remove(fcu)

        self.drivers = {}
        storeDrivers(rig.data, "_RIG_")
        for ob in meshes:
            storeDrivers(ob.data.shape_keys, "_SKEY_%s" % ob.name)
            storeDrivers(ob, "_OB_%s" % ob.name)


    def restoreAllDrivers(self, rig, nrig, meshes, renamed):
        def restoreDrivers(rna, key, assoc):
            drivers = self.drivers.get(key, [])
            for driver in drivers:
                driver.createDirect(rna, assoc)

        assoc = {}
        for mbone,dbone in renamed.items():
            defbone = "DEF-%s" % mbone
            if defbone in rig.data.bones.keys():
                assoc[dbone] = defbone
            else:
                assoc[dbone] = mbone.replace(".bend.", ".").replace(".twist.", ".")
        restoreDrivers(rig.data, "_RIG_", assoc)
        if nrig:
            assoc = {}
        for ob in meshes:
            restoreDrivers(ob.data.shape_keys, "_SKEY_%s" % ob.name, assoc)
            restoreDrivers(ob, "_OB_%s" % ob.name, assoc)

#-------------------------------------------------------------
#  class for storing modifiers
#-------------------------------------------------------------

class ModStore:
    def __init__(self, mod):
        self.name = mod.name
        self.type = mod.type
        self.data = {}
        self.items = {}
        self.store(mod, self.data)
        self.settings = {}
        if hasattr(mod, "settings"):
            self.store(mod.settings, self.settings)
        self.collision_settings = {}
        if hasattr(mod, "collision_settings"):
            self.store(mod.collision_settings, self.collision_settings)


    def store(self, data, struct):
        for key in dir(data):
            if (key[0] == '_' or
                key == "name" or
                key == "type"):
                continue
            value = getattr(data, key)
            if (isSimpleType(value) or
                isinstance(value, (bpy.types.Object, bpy.types.NodeTree))):
                struct[key] = value
        try:
            for key,value in data.items():
                self.items[key] = value
        except TypeError:
            pass


    def restore(self, ob):
        mod = ob.modifiers.new(self.name, self.type)
        self.restoreData(self.data, mod)
        for key,value in self.items.items():
            mod[key] = value
        if self.settings:
            self.restoreData(self.settings, mod.settings)
        if self.collision_settings:
            self.restoreData(self.collision_settings, mod.collision_settings)


    def restoreData(self, struct, data):
        for key,value in struct.items():
            try:
                setattr(data, key, value)
            except:
                pass


def addModifierFirst(ob, modname, modtype):
    exclude = ['ARMATURE', 'MULTIRES']
    stores = []
    for mod in ob.modifiers:
        if mod.type not in exclude:
            stores.append(ModStore(mod))
            ob.modifiers.remove(mod)
    mod = ob.modifiers.new(modname, modtype)
    for store in stores:
        store.restore(ob)
    return mod
