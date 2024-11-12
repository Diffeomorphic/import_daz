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

from .error import *
from .utils import *

#-------------------------------------------------------------
#   Temp object for faster drivers
#-------------------------------------------------------------

class DriverUser:
    def __init__(self):
        self.tmp = None

    def createTmp(self):
        if self.tmp is None:
            self.tmp = bpy.data.objects.new("Tmp", None)


    def deleteTmp(self):
        if self.tmp:
            bpy.data.objects.remove(self.tmp)
            del self.tmp
            self.tmp = None


    def getTmpDriver(self, idx):
        self.tmp.driver_remove("rotation_euler", idx)
        fcu = self.tmp.driver_add("rotation_euler", idx)
        removeModifiers(fcu)
        return fcu


    def clearTmpDriver(self, idx):
        self.tmp.driver_remove("rotation_euler", idx)


    def getArrayIndex(self, fcu):
        if (not fcu.data_path or
            fcu.data_path[-1] == "]" or
            fcu.data_path.endswith("value")):
            return -1
        else:
            return fcu.array_index


    def removeDriver(self, rna, path, idx=-1):
        if idx < 0:
            rna.driver_remove(path)
        else:
            rna.driver_remove(path, idx)


    def copyDriver(self, fcu, rna, old=None, new=None, assoc=None):
        channel = fcu.data_path
        bname = getBoneChannel(fcu)[0]
        if bname and bname in assoc.keys():
            channel = channel.replace(bname, assoc[bname])
        idx = self.getArrayIndex(fcu)
        if rna.animation_data is None:
            try:
                if idx > 0:
                    rna.driver_add(channel, idx)
                else:
                    rna.driver_add(channel)
            except TypeError:
                return
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if old or assoc:
            self.setId(fcu2, old, new, assoc)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
        fcu3.data_path = channel
        if idx >= 0:
            fcu3.array_index = idx
        removeModifiers(fcu3)
        self.clearTmpDriver(0)
        return fcu3


    def copyFcurve(self, fcu1, fcu2):
        fcu2.driver.type = fcu1.driver.type
        fcu2.driver.use_self = fcu1.driver.use_self
        fcu2.driver.expression = fcu1.driver.expression
        for var1 in fcu1.driver.variables:
            var2 = fcu2.driver.variables.new()
            self.copyVariable(var1, var2)


    def copyVariable(self, var1, var2):
        var2.type = var1.type
        var2.name = var1.name
        for n,trg1 in enumerate(var1.targets):
            if n > 1:
                trg2 = var2.targets.add()
            else:
                trg2 = var2.targets[0]
            if trg1.id_type != 'OBJECT':
                trg2.id_type = trg1.id_type
            trg2.id = trg1.id
            trg2.bone_target = trg1.bone_target
            trg2.data_path = trg1.data_path
            trg2.transform_type = trg1.transform_type
            trg2.rotation_mode = trg1.rotation_mode
            trg2.transform_space = trg1.transform_space


    def setId(self, fcu, old, new, assoc=None):
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT' and trg.id == old:
                    trg.id = new
                elif trg.id_type == 'ARMATURE' and trg.id == old.data:
                    trg.id = new.data
                if assoc and var.type == 'TRANSFORMS':
                    if trg.bone_target in assoc.keys():
                        trg.bone_target = assoc[trg.bone_target]
                    else:
                        basebone = baseBone(trg.bone_target)
                        if basebone in assoc.keys():
                            trg.bone_target = assoc[basebone]
                        else:
                            print("Miss Id", trg.bone_target)


    def getTargetBones(self, fcu):
        targets = {}
        for var in fcu.driver.variables:
            if var.type == 'TRANSFORMS':
                for trg in var.targets:
                    targets[trg.bone_target] = True
        return targets.keys()


    def getVarBoneTargets(self, fcu):
        if not fcu.driver:
            return [], []
        vstruct = {}
        bstruct = {}
        for var in fcu.driver.variables:
            if var.type == 'TRANSFORMS':
                for trg in var.targets:
                    bstruct[var.name] = (trg.bone_target, var)
            elif var.type == 'SINGLE_PROP':
                for trg in var.targets:
                    vstruct[var.name] = (trg.data_path, var)
        vtargets = [(key,data[0],data[1]) for key,data in vstruct.items()]
        btargets = [(key,data[0],data[1]) for key,data in bstruct.items()]
        vtargets.sort()
        btargets.sort()
        return vtargets, btargets


    def getDriverTargets(self, fcu):
        return [var.targets[0].data_path for var in fcu.driver.variables]


    def setBoneTarget(self, fcu, bname):
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.bone_target:
                    trg.bone_target = bname


    def getShapekeyDrivers(self, ob, drivers={}):
        if (ob.data.shape_keys is None or
            ob.data.shape_keys.animation_data is None):
            #print(ob, ob.data.shape_keys, ob.data.shape_keys.animation_data)
            return drivers

        for fcu in ob.data.shape_keys.animation_data.drivers:
            sname,channel = getShapeChannel(fcu)
            if sname:
                drivers["%s:%s" % (sname,channel)] = fcu

        return drivers


    def copyShapeKeyDrivers(self, ob, drivers):
        skeys = ob.data.shape_keys
        if (skeys is None or not drivers):
            return
        self.createTmp()
        try:
            for key,fcu in drivers.items():
                sname,channel = key.rsplit(":", 1)
                if (getShapekeyDriver(skeys, sname, channel) or
                    sname not in skeys.key_blocks.keys()):
                    continue
                #skey = skeys.key_blocks[sname]
                self.copyDriver(fcu, skeys)
        finally:
            self.deleteTmp()


    def copyAssocDrivers(self, src, trg, old, new, assoc):
        if src.animation_data is None:
            return
        self.createTmp()
        try:
            for fcu in src.animation_data.drivers:
                self.copyDriver(fcu, trg, old, new, assoc)
        finally:
            self.deleteTmp()

#-------------------------------------------------------------
#   Check if RNA is driven
#-------------------------------------------------------------

def getDriver(rna, channel, idx):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            if fcu.data_path == channel and fcu.array_index == idx:
                return fcu
    return None


def getDrivenBoneFcurves(rig, useRigifySafe=False):
    driven = {}
    if useRigifySafe:
        for pb in rig.pose.bones:
            if pb.name.startswith(("DEF-", "ORG-", "MCH-")):
                driven[pb.name] = []
    if rig.animation_data:
        skip = ["HdOffset", "TlOffset"]
        for fcu in rig.animation_data.drivers:
            bname,channel = getBoneChannel(fcu)
            if channel not in skip:
                if bname not in driven.keys():
                    driven[bname] = []
                driven[bname].append(fcu)
    return driven


def getPropDrivers(rig):
    if rig.animation_data:
        return [fcu for fcu in rig.animation_data.drivers
                if fcu.data_path[0] == '[']
    else:
        return []


def getDrivingBone(fcu, rig):
    for var in fcu.driver.variables:
        if var.type == 'TRANSFORMS':
            trg = var.targets[0]
            if trg.id == rig:
                return trg.bone_target
    return None


def getShapekeyDriver(skeys, sname, channel = "value"):
    return getRnaDriver(skeys, 'key_blocks["%s"].%s' % (sname, channel), None)


def getShapekeyPropDriver(skeys, sname, channel = "value"):
    return getRnaDriver(skeys, 'key_blocks["%s"].%s' % (sname, channel), 'SINGLE_PROP')


def getRnaDriver(rna, path, type=None):
    if (rna and
        not isinstance(rna, bpy.types.PoseBone) and
        rna.animation_data):
        for fcu in rna.animation_data.drivers:
            if path == fcu.data_path:
                if not type:
                    return fcu
                for var in fcu.driver.variables:
                    if var.type == type:
                        return fcu
    return None

#-------------------------------------------------------------
#   Classes for storing drivers
#-------------------------------------------------------------

class Driver:
    def __init__(self, fcu, isArray):
        drv = fcu.driver
        self.data_path = fcu.data_path
        if isArray:
            self.array_index = fcu.array_index
        else:
            self.array_index = -1
        self.type = drv.type
        self.use_self = drv.use_self
        self.expression = drv.expression
        self.variables = []
        for var in drv.variables:
            self.variables.append(Variable(var))


    def __repr__(self):
        string = "<Driver %s %d %s" % (self.data_path, self.array_index, self.type)
        for var in self.variables:
            string += "\n  %s" % var
        return string + ">"


    def getChannel(self):
        words = self.data_path.split('"')
        if words[0] == "pose.bones[" and len(words) == 5:
            bname = words[1]
            channel = words[3]
            self.data_path = self.data_path.replace(propRef(bname), propRef(drvBone(bname)))
            self.array_index = -1
            return propRef(channel), -1
        else:
            words = self.data_path.rsplit(".",1)
            if len(words) == 2:
                channel = words[1]
            else:
                raise RuntimeError("BUG: Cannot create channel\n%s" % self.data_path)
            return channel, self.array_index


    def create(self, rna, fixDrv=False):
        channel,idx = self.getChannel()
        fcu = rna.driver_add(channel, idx)
        removeModifiers(fcu)
        return self.fill(fcu, fixDrv)


    def createDirect(self, rna, assoc):
        try:
            fcu = rna.driver_add(self.data_path, self.array_index)
            removeModifiers(fcu)
            return self.fill(fcu, False, assoc)
        except (TypeError, AttributeError):
            print("Missing driver: %s, %s, %s" % (rna.name, self.data_path, self.array_index))
            return None


    def fill(self, fcu, fixDrv=False, assoc={}):
        drv = fcu.driver
        drv.type = self.type
        drv.use_self = self.use_self
        drv.expression = self.expression
        for var in self.variables:
            var.create(drv.variables.new(), fixDrv, assoc)
        return fcu


    def getNextVar(self, prop):
        varname = "a"
        for var in self.variables:
            if var.target.name == prop:
                return var.name,False
            elif ord(var.name) > ord(varname):
                varname = var.name
        return nextLetter(varname),True


class Variable:
    def __init__(self, var):
        self.type = var.type
        self.name = var.name
        self.targets = []
        for trg in var.targets:
            self.targets.append(Target(trg))

    def __repr__(self):
        string = "<Var %s %s" % (self.name,self.type)
        for trg in self.targets:
            string += "\n    %s" % trg
        return string + ">"

    def create(self, var, fixDrv=False, assoc={}):
        var.name = self.name
        var.type = self.type
        self.targets[0].create(var.targets[0], fixDrv, assoc)
        for target in self.targets[1:]:
            trg = var.targets.new()
            target.create(trg, fixDrv)


class Target:
    def __init__(self, trg):
        self.id_type = trg.id_type
        self.id = trg.id
        self.bone_target = trg.bone_target
        self.transform_type = trg.transform_type
        self.rotation_mode = trg.rotation_mode
        self.transform_space = trg.transform_space
        self.data_path = trg.data_path
        words = trg.data_path.split('"')
        if len(words) > 1:
            self.name = words[1]
        else:
            self.name = words[0]

    def __repr__(self):
        string = "<Trg %s %s %s>" % (self.id_type, self.id.name, self.transform_type)
        return string

    def create(self, trg, fixDrv=False, assoc={}):
        if self.id_type != 'OBJECT':
            trg.id_type = self.id_type
        trg.id = self.id
        trg.bone_target = assoc.get(self.bone_target, self.bone_target)
        trg.transform_type = self.transform_type
        trg.rotation_mode = self.rotation_mode
        trg.transform_space = self.transform_space
        if fixDrv:
            words = self.data_path.split('"')
            if words[0] == "pose.bones[":
                words[1] = drvBone(words[1])
                self.data_path = '"'.join(words)
        trg.data_path = self.data_path

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def addTransformVar(fcu, vname, ttype, rig, rig2, bname):
    from .bone_data import BD
    pb = rig.pose.bones.get(bname)
    if pb is None:
        pb = rig2.pose.bones.get(bname)
        rig = rig2
    var = fcu.driver.variables.new()
    var.type = 'TRANSFORMS'
    var.name = vname
    trg = var.targets[0]
    trg.id = rig
    trg.bone_target = bname
    if GS.useAutoEuler:
        trg.rotation_mode = 'AUTO'
    elif pb is None:
        trg.rotation_mode = 'XYZ'
    elif pb.rotation_mode == 'QUATERNION':
        trg.rotation_mode = BD.RotationModes.get(pb.name, 'QUATERNION')
    else:
        trg.rotation_mode = pb.rotation_mode
    trg.transform_type = ttype
    trg.transform_space = 'LOCAL_SPACE'

#-------------------------------------------------------------
#   Prop drivers
#-------------------------------------------------------------

def makePropDriver(path, rna, channel, ob, expr):
    rna.driver_remove(channel)
    fcu = rna.driver_add(channel)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = expr
    removeModifiers(fcu)
    addDriverVar(fcu, "x", path, ob)


def removeModifiers(fcu):
    for mod in list(fcu.modifiers):
        fcu.modifiers.remove(mod)

#-------------------------------------------------------------
#   Property UI
#-------------------------------------------------------------

if bpy.app.version < (3,0,0):
    def getRnaUi(rna):
        rna_ui = rna.get('_RNA_UI')
        if rna_ui is None:
            rna_ui = rna['_RNA_UI'] = {}
        return rna_ui

    def setPropMinMax(rna, prop, default, min, max, ovr, soft=None):
        rna_ui = getRnaUi(rna)
        struct = { "min": min, "max": max, "soft_min": min, "soft_max": max}
        rna_ui[prop] = struct

    def getPropUi(rna, prop):
        rna_ui = getRnaUi(rna)
        return rna_ui.get(prop, {})

    def setProtected(rna, prop, on):
        rna_ui = getRnaUi(rna)
        struct = rna_ui.get(prop, {})
        struct["description"] = ("***" if on else "")
        rna_ui[prop] = struct

else:
    def setPropMinMax(rna, prop, default, min, max, ovr, soft=None):
        if soft is None:
            soft = ovr
        if prop not in rna.keys():
            rna[prop] = default
        ui = rna.id_properties_ui(prop)
        if isinstance(default, bool):
            ui.update(default=default)
        elif isinstance(default, (int, float)):
            if soft:
                ui.update(default=default, soft_min=min, soft_max=max)
            else:
                ui.update(default=default, min=min, max=max)
        rna.property_overridable_library_set(propRef(prop), ovr)


    def getPropUi(rna, prop):
        try:
            ui = rna.id_properties_ui(prop)
            return ui.as_dict()
        except KeyError:
            return {}


    def setProtected(rna, prop, on):
        try:
            ui = rna.id_properties_ui(prop)
            desc = ("***" if on else "")
            ui.update(description = desc)
        except KeyError:
            pass


def isProtected(rna, prop):
    if isinstance(rna, bpy.types.Object) and rna.type != 'ARMATURE':
        return False
    elif isinstance(rna[prop], float):
        ui = getPropUi(rna, prop)
        return (ui.get("description") == "***")
    else:
        return True

#-------------------------------------------------------------
#   Properties
#-------------------------------------------------------------

def getPropMinMax(rna, prop, ovr=False):
    struct = getPropUi(rna, prop)
    min = 0.0
    max = 1.0
    default = 0.0
    if struct:
        if "soft_min" in struct.keys():
            min = struct["soft_min"]
        elif "min" in struct.keys():
            min = struct["min"]
        if "soft_max" in struct.keys():
            max = struct["soft_max"]
        elif "max" in struct.keys():
            max = struct["max"]
        if "default" in struct.keys():
            default = struct["default"]
        if "overridable" in struct.keys():
            ovr = struct["overridable"]
    return min,max,default,ovr


def copyProp(prop, src, trg, ovr):
    if (prop[0] == "_" or
        prop in trg.keys()):
        return
    if hasattr(src, prop):
        try:
            setattr(trg, prop, getattr(src, prop))
            ok = True
        except AttributeError:
            ok = False
        if not ok:
            trg[prop] = src[prop]
        return
    value = src[prop]
    if isinstance(value,float):
        min,max,default,ovr = getPropMinMax(src, prop, ovr)
        setFloatProp(trg, prop, value, min, max, ovr)
    elif isinstance(value,int):
        min,max,default,ovr = getPropMinMax(src, prop, ovr)
        setPropMinMax(trg, prop, value, min, max, ovr)
        trg[prop] = value
    elif isinstance(value,bool):
        setBoolProp(trg, prop, value, ovr)
    elif isinstance(value,str):
        trg[prop] = value
    setProtected(trg, prop, isProtected(src, prop))


def truncateProp(prop):
    if len(prop) > 63:
        print('Truncate property "%s"' % prop)
        return prop[:63]
    else:
        return prop


def setFloatProp(rna, prop, value, min, max, ovr, soft=None):
    value = float(value)
    prop = truncateProp(prop)
    rna[prop] = value
    if min is not None:
        min = float(min)
        max = float(max)
        setPropMinMax(rna, prop, value, min, max, ovr, soft)
        if ovr and bpy.app.version < (3,0,0):
            setOverridable(rna, prop)
            setPropMinMax(rna, prop, value, min, max, ovr, soft)
    elif ovr:
        setOverridable(rna, prop)
    rna[prop] = value


def setBoolProp(rna, prop, value, ovr, desc=""):
    prop = truncateProp(prop)
    setPropMinMax(rna, prop, value, 0, 1, ovr, False)
    if False and ovr and bpy.app.version < (3,0,0):
        setOverridable(rna, prop)
        setPropMinMax(rna, prop, value, 0, 1, ovr, False)
    rna[prop] = value

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def addDriver(rna, channel, rig, prop, expr, index=-1):
    fcu = rna.driver_add(channel, index)
    fcu.driver.type = 'SCRIPTED'
    if isinstance(prop, str):
        fcu.driver.expression = expr
        addDriverVar(fcu, "x", prop, rig)
    else:
        prop1,prop2 = prop
        fcu.driver.expression = expr
        addDriverVar(fcu, "x1", prop1, rig)
        addDriverVar(fcu, "x2", prop2, rig)


def addGeneralDriver(rna, channel, rig, path, expr, index=-1):
    fcu = rna.driver_add(channel, index)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = expr
    addDriverVar(fcu, "x", path, rig)


def addDriverVar(fcu, vname, path, rna, vartype='SINGLE_PROP'):
    var = fcu.driver.variables.get(vname)
    if var is None:
        var = fcu.driver.variables.new()
    var.name = vname
    var.type = vartype
    trg = var.targets[0]
    trg.id_type = getIdType(rna)
    trg.id = rna
    trg.data_path = path
    return trg


def getIdType(rna):
    if isinstance(rna, bpy.types.Armature):
        return 'ARMATURE'
    elif isinstance(rna, bpy.types.Object):
        return 'OBJECT'
    elif isinstance(rna, bpy.types.Mesh):
        return 'MESH'
    elif isinstance(rna, bpy.types.Key):
        return 'KEY'
    else:
        raise RuntimeError("BUG addDriverVar", rna)


def hasDriverVar(fcu, dname, rig):
    path = propRef(dname)
    for var in fcu.driver.variables:
        trg = var.targets[0]
        if trg.id == rig and trg.data_path == path:
            return True
    return False


def getDriverPaths(fcu, rig):
    paths = {}
    for var in fcu.driver.variables:
        trg = var.targets[0]
        if trg.id == rig:
            paths[var.name] = trg.data_path
    return paths


def isNumber(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


def removeDriverFCurves(fcus, rig):
    for fcu in flatten(fcus):
        try:
            rig.driver_remove(fcu.data_path, fcu.array_index)
        except TypeError:
            pass


def isPropDriver(fcu):
    vars = fcu.driver.variables
    return (len(vars) > 0 and vars[0].type == 'SINGLE_PROP')


#----------------------------------------------------------
#   Bone sum drivers
#----------------------------------------------------------

def getAllBoneSumDrivers(rig, bnames):
    from collections import OrderedDict
    boneFcus = OrderedDict()
    sumFcus = OrderedDict()
    if rig.animation_data is None:
        return boneFcus, sumFcus
    for fcu in rig.animation_data.drivers:
        words = fcu.data_path.split('"', 2)
        if words[0] == "pose.bones[":
            bname = baseBone(words[1])
            if bname not in bnames:
                continue
        else:
            if GS.verbosity >= 3 and words[0] != "[":
                print("MISS", words)
            continue
        if fcu.driver.type == 'SCRIPTED':
            if bname not in boneFcus.keys():
                boneFcus[bname] = []
            boneFcus[bname].append(fcu)
        elif fcu.driver.type == 'SUM':
            if bname not in sumFcus.keys():
                sumFcus[bname] = []
            sumFcus[bname].append(fcu)
    return boneFcus, sumFcus


def removeBoneSumDrivers(rig, bones):
    boneFcus, sumFcus = getAllBoneSumDrivers(rig, bones)
    removeDriverFCurves(boneFcus.values(), rig)
    removeDriverFCurves(sumFcus.values(), rig)

#----------------------------------------------------------
#   Copy drivers
#----------------------------------------------------------

class DAZ_OT_CopyDrivers(DazPropsOperator, IsArmature):
    bl_idname = "daz.copy_drivers"
    bl_label = "Copy Drivers"
    bl_description = "Copy drivers from active armature to selected armatures"
    bl_options = {'UNDO'}

    useShapekeys : BoolProperty(
        name = "Retarget Shapekeys",
        description = "Retarget shapekeys of child meshes",
        default = True)

    useMorphsets : BoolProperty(
        name = "Copy Morphsets",
        description = "Copy user interface",
        default = True)

    useOverride : BoolProperty(
        name = "Override Existing Drivers",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useShapekeys")
        self.layout.prop(self, "useMorphsets")
        self.layout.prop(self, "useOverride")

    def run(self, context):
        from .morphing import copyMorphsets
        rig1 = context.object
        for rig2 in getSelectedObjects(context):
            if rig2.type == 'ARMATURE' and rig2 != rig1:
                if self.useMorphsets:
                    copyMorphsets(rig1, rig2)
                self.copyDrivers(rig1, rig2, rig1, rig2, True)
                self.copyDrivers(rig1.data, rig2.data, rig1, rig2, False)
                if self.useShapekeys:
                    for ob in getShapeChildren(rig2):
                        retargetDrivers(ob.data.shape_keys, rig1, rig2)


    def copyDrivers(self, rna1, rna2, rig1, rig2, ovr):
        def fcukey(fcu):
            return "%s:%d" % (fcu2.data_path, fcu2.array_index)

        if rna1.animation_data is None:
            return
        if rna2.animation_data is None:
            rna2["Dummy"] = 0
            rna2.driver_add(propRef("Dummy"))
            dummy = True
        else:
            dummy = False
        existing = {}
        for fcu2 in rna2.animation_data.drivers:
            existing[fcukey(fcu2)] = fcu2
        for fcu1 in rna1.animation_data.drivers:
            key = fcukey(fcu1)
            if key in existing.keys():
                if self.useOverride:
                    fcu2 = existing[key]
                    rna2.animation_data.drivers.remove(fcu2)
                    del existing[key]
                else:
                    continue
            bname,channel = getBoneChannel(fcu1)
            if bname and bname not in rig2.data.bones.keys():
                continue
            ensureProp(fcu1, rna1, rna2, ovr)
            fcu2 = rna2.animation_data.drivers.from_existing(src_driver=fcu1)
            retargetFcurve(fcu2, rig1, rig2)
        if dummy:
            rna2.driver_remove(propRef("Dummy"))
            del rna2["Dummy"]

#----------------------------------------------------------
#   Retargeting
#----------------------------------------------------------

def ensureProp(fcu, rna1, rna2, ovr):
    if isPropRef(fcu.data_path):
        prop = getProp(fcu.data_path)
        if prop and prop not in rna2.keys():
            rna2[prop] = rna1.get(prop, 0.0)
            ui = getPropUi(rna1, prop)
            min = ui.get("min", -1e6)
            max = ui.get("max", 1e6)
            default = ui.get("default", 0.0)
            setPropMinMax(rna2, prop, default, min, max, ovr)


def retargetFcurve(fcu, rig1, rig2, force=False):
    for var in fcu.driver.variables:
        for trg in var.targets:
            if trg.id_type == 'OBJECT':
                if trg.id == rig1:
                    ensureProp(trg, rig1, rig2, True)
                    trg.id = rig2
            elif trg.id_type == 'ARMATURE':
                if trg.id == rig1.data:
                    ensureProp(trg, rig1.data, rig2.data, False)
                    trg.id = rig2.data
            elif trg.id_type not in ['KEY']:
                print("Unexpected id: %s %s" % (trg.id_type, trg.id))


def retargetDrivers(rna, rig1, rig2, force=False):
    if rna.animation_data is None:
        return
    for fcu in rna.animation_data.drivers:
        fcu.mute = False
        retargetFcurve(fcu, rig1, rig2, force)

#----------------------------------------------------------
#   Optimize drivers
#----------------------------------------------------------

class DAZ_OT_OptimizeDrivers(DazPropsOperator, IsArmature):
    bl_idname = "daz.optimize_drivers"
    bl_label = "Optimize Drivers"
    bl_description = "Optimize the web of drivers.\nNew morphs can not be loaded afterwards"
    bl_options = {'UNDO'}

    useRemoveMultipliers : BoolProperty(
        name = "Remove Multipliers",
        description = "Remove multipliers from drivers.\nCan change how drivers work",
        default = False)

    useRemoveHiddenSliders : BoolProperty(
        name = "Remove Hidden Sliders",
        description = "Remove sliders for hidden variables from drivers.\nCan change how drivers work",
        default = True)

    useRemoveERC : BoolProperty(
        name = "Remove ERC Morphs",
        description = "Remove ERC morphs from drivers.\nArmatures can no longer be morphed",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useRemoveMultipliers")
        self.layout.prop(self, "useRemoveHiddenSliders")
        self.layout.prop(self, "useRemoveERC")

    def run(self, context):
        self.rig = context.object
        self.amt = self.rig.data
        self.collectHidden()
        if self.useRemoveHiddenSliders:
            self.removeHiddenVars(self.amt)
        if self.useRemoveMultipliers:
            self.removeMultipliers(self.amt)
        if self.useRemoveHiddenSliders:
            self.removeHiddenVars(self.amt)
            self.removeHiddenSliders()
        self.obskeys = [(ob, ob.data.shape_keys) for ob in getShapeChildren(self.rig)]
        self.modernizeShapekeys()
        self.ndeleted = 0
        ndrivers = len(self.amt.animation_data.drivers)
        self.sumdrivers = {}
        self.findrivers = {}
        self.restdrivers = {}
        self.deldrivers = {}
        self.collectDrivers(self.amt)
        self.replaceTargets(self.rig)
        self.replaceTargets(self.amt)
        for ob,skeys in self.obskeys:
            self.replaceTargets(skeys)
        self.deleteDrivers(self.amt)
        self.removeInvalid(self.amt)
        msg = "Deleted %d out of %d drivers from %s" % (self.ndeleted, ndrivers, self.rig.name)
        if ES.easy:
            print(msg)
        else:
            self.raiseWarning(msg)


    def collectHidden(self):
        def collect(pg, pgname):
            self.hiddenGroups[pgname] = pg
            for item in pg:
                if item.text[0] == "[" and item.text[-1] == "]":
                    self.hidden[item.name] = pgname

        from .morphing import MS
        self.hidden = {}
        self.hiddenGroups = {}
        for morphset in MS.Standards:
            pgname = "Daz%s" % morphset
            pg = getattr(self.rig, pgname)
            collect(pg, pgname)
        for morphset in MS.JCMs:
            pgname = "Daz%s" % morphset
            pg = getattr(self.rig, pgname)
            collect(pg, pgname)
        for cat in self.rig.DazMorphCats:
            collect(cat.morphs, cat.name)


    def removeHiddenSliders(self):
        for pgname,pg in self.hiddenGroups.items():
            props = [prop for prop,name in self.hidden.items() if name == pgname]
            idxs = [n for n,item in enumerate(pg.values()) if item.name in props]
            if idxs:
                print("Prune %s" % pgname)
                idxs.reverse()
                for idx in idxs:
                    pg.remove(idx)
            for prop in props:
                if prop in self.rig.keys():
                    del self.rig[prop]


    def getDrivers(self, rna):
        self.drivers = {}
        if rna is None or rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            prop = getProp(fcu.data_path)
            if prop and fcu.driver.type == 'SCRIPTED':
                self.drivers[prop] = fcu


    def collectDrivers(self, rna):
        if rna is None or rna.animation_data is None:
            print("No drivers: %s" % rna)
            return
        for fcu in rna.animation_data.drivers:
            prop = getProp(fcu.data_path)
            if not prop:
                continue
            elif someMatch([":Loc:", ":Rot:", ":Sca:", ":Hdo:", ":Tlo:"], fcu.data_path):
                self.sumdrivers[fcu.data_path] = fcu, prop
            elif prop.endswith("(rst):01"):
                self.restdrivers[propRef(prop[:-3])] = fcu, prop
            elif isFinal(prop):
                trg = self.getScriptedTarget(fcu.driver)
                if trg:
                    raw = getProp(trg.data_path)
                    if raw == baseProp(prop) and trg.id == self.rig:
                        self.findrivers[propRef(prop)] = fcu, raw
                        self.deldrivers[prop] = fcu
            if self.useRemoveERC and someMatch([":Hdo:", ":Tlo:"], fcu.data_path):
                self.deldrivers[prop] = fcu


    def getSumTarget(self, drv):
        if (drv.type == 'SUM' and
            len(drv.variables) == 1):
            var = drv.variables[0]
            if len(var.targets) == 1:
                return var.targets[0]
        return None


    def getScriptedTarget(self, drv):
        if (drv.type == 'SCRIPTED' and
            len(drv.variables) == 1 and
            drv.expression in ["a", "+b"]):
            var = drv.variables[0]
            if len(var.targets) == 1:
                return var.targets[0]
        return None


    def modernizeShapekeys(self):
        def isModern(skeys):
            if skeys.animation_data is None:
                return True
            for fcu in skeys.animation_data.drivers:
                sname,channel = getShapeChannel(fcu)
                if sname:
                    for var in fcu.driver.variables:
                        for trg in var.targets:
                            if trg.id_type in ['KEY', 'OBJECT']:
                                return True
                            elif trg.id_type == 'ARMATURE':
                                return False
                            else:
                                msg = 'Unexpected target type: %s\n"%s"\n%s' % (trg.id_type, ob.name, trg.id)
                                raise DazError(msg)

        hum = None
        for ob,skeys in self.obskeys:
            if ob.DazMesh.startswith("Genesis"):
                hum = ob
                hskeys = skeys
                break
        if hum is None:
            print("No main mesh")
            return
        for ob,skeys in self.obskeys:
            if ob != hum and not isModern(skeys):
                for skey in skeys.key_blocks:
                    hskey = hskeys.key_blocks.get(skey.name)
                    if hskey:
                        skey.driver_remove("value")
                        skey.driver_remove("mute")
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
                        addGeneralDriver(skey, "value", hskeys, 'key_blocks["%s"].value' % hskey.name, "x")


    def replaceTargets(self, rna):
        if rna is None or rna.animation_data is None:
            return
        for fcu in list(rna.animation_data.drivers):
            drv = fcu.driver
            if drv.type == 'SUM' and len(drv.variables) == 1:
                var = drv.variables[0]
                trg = var.targets[0]
                if trg.data_path in self.sumdrivers.keys():
                    srcfcu,prop = self.sumdrivers[trg.data_path]
                elif fcu.data_path in self.restdrivers.keys():
                    srcfcu,prop = self.restdrivers[fcu.data_path]
                else:
                    continue
                path,idx = fcu.data_path, fcu.array_index
                rna.driver_remove(fcu.data_path, fcu.array_index)
                nfcu = rna.animation_data.drivers.from_existing(src_driver=srcfcu)
                nfcu.data_path = path
                nfcu.array_index = idx
                self.deldrivers[prop] = srcfcu

        for fcu in rna.animation_data.drivers:
            for var in list(fcu.driver.variables):
                trg = var.targets[0]
                if trg.id == self.amt and trg.data_path in self.findrivers.keys():
                    vname = var.name
                    fcu.driver.variables.remove(var)
                    prop = self.findrivers[trg.data_path][1]
                    addDriverVar(fcu, vname, propRef(prop), self.rig)


    def deleteDrivers(self, rna):
        for prop,fcu in self.deldrivers.items():
            if fcu.data_path:
                rna.animation_data.drivers.remove(fcu)
                if prop in rna.keys():
                    del rna[prop]
        rna["DazOptimizedDrivers"] = True
        self.ndeleted += len(self.deldrivers)
        print("Deleted %d drivers from %s" % (len(self.deldrivers), rna.name))


    def removeInvalid(self, rna):
        if rna is None or rna.animation_data is None:
            return
        ninvalids = 0
        for fcu in list(rna.animation_data.drivers):
            prop = getProp(fcu.data_path)
            if prop and prop not in self.amt.keys():
                self.amt.animation_data.drivers.remove(fcu)
                ninvalids += 1
        self.ndeleted += ninvalids
        print("Removed %d invalid drivers" % ninvalids)


    def removeMultipliers(self, rna):
        if rna is None or rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            drv = fcu.driver
            if drv.type == 'SCRIPTED':
                vars = []
                string = drv.expression
                while len(string) > 2 and string[1] == "*":
                    vars.append(string[0])
                    string = string[2:]
                if vars:
                    while string[0] == "(" and string[-1] == ")":
                        string = string[1:-1]
                    if string[0] == "+":
                        string = string[1:]
                    drv.expression = string
                    for var in list(drv.variables):
                        if var.name in vars:
                            drv.variables.remove(var)


    def removeHiddenVars(self, rna):
        def removeVar(drv):
            for var in list(drv.variables):
                if var.name == "u":
                    trg = var.targets[0]
                    prop = getProp(trg.data_path)
                    if prop in self.hidden.keys():
                        drv.variables.remove(var)
                        string = drv.expression
                        n = (1 if string[1] == "-" else 2)
                        drv.expression = string[n:]
                    return

        if rna is None or rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            if (fcu.driver.type == 'SCRIPTED' and
                fcu.driver.expression[0:2] in ["u+", "u-"]):
                removeVar(fcu.driver)


    def replaceDrivers(self, rna):
        if rna is None or rna.animation_data is None:
            return
        for fcu in rna.animation_data.drivers:
            trg = self.getScriptedTarget(fcu.driver)
            if trg:
                prop = getProp(trg.data_path)
                fcu2 = self.drivers.get(prop)
                if fcu2:
                    path = fcu.data_path
                    rna.driver_remove(path)
                    fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
                    fcu3.data_path = path
                    removeModifiers(fcu3)
                    self.deldrivers[prop] = fcu2

#----------------------------------------------------------
#   Update button
#----------------------------------------------------------

class DAZ_OT_UpdateAll(DazOperator):
    bl_idname = "daz.update_all"
    bl_label = "Update All"
    bl_description = "Update everything. Try this if driven bones are messed up"
    bl_options = {'UNDO'}

    def run(self, context):
        updateAll(context)

#----------------------------------------------------------
#   Disable and enable drivers
#----------------------------------------------------------

def muteDazFcurves(rig, mute, useLocation=True, useRotation=True, useScale=True, useShapekeys=True, muted=[]):
    def isDazFcurve(path):
        for string in ["(fin)", "(rst)", ":Loc:", ":Rot:", ":Sca:", ":Hdo:", ":Tlo:"]:
            if string in path:
                return True
        return False

    if rig and rig.data.animation_data:
        for fcu in rig.data.animation_data.drivers:
            if isDazFcurve(fcu.data_path):
                fcu.mute = mute

    if rig and rig.animation_data:
        for fcu in rig.animation_data.drivers:
            bname,channel = getBoneChannel(fcu)
            if bname:
                if ((channel in ["rotation_euler", "rotation_quaternion"] and useRotation) or
                    (channel == "location" and useLocation) or
                    (channel == "scale" and useScale) or
                    channel in ["HdOffset", "TlOffset"]):
                    fcu.mute = mute

    if not useShapekeys:
        return muted
    for ob in getShapeChildren(rig):
        skeys = ob.data.shape_keys
        if skeys.animation_data:
            for fcu in skeys.animation_data.drivers:
                sname,channel = getShapeChannel(fcu)
                if sname:
                    fcu.mute = mute
                    if sname in skeys.key_blocks.keys():
                        skey = skeys.key_blocks[sname]
                        key = "%s:%s" % (ob.name, sname)
                        if skey.mute and mute:
                            muted.append(key)
                        if key not in muted:
                            skey.mute = mute
    return muted


class DAZ_OT_DisableDrivers(DazOperator):
    bl_idname = "daz.disable_drivers"
    bl_label = "Disable Drivers"
    bl_description = "Disable all drivers to improve performance"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        rig = getRigFromContext(context)
        return (rig and not rig.DazDriversDisabled)

    def run(self, context):
        setMode('OBJECT')
        rig = getRigFromContext(context)
        rigs = getSelectedArmatures(context)
        rigs.append(rig)
        for rig in set(rigs):
            muteDazFcurves(rig, True)
            rig.DazDriversDisabled = True


class DAZ_OT_EnableDrivers(DazOperator):
    bl_idname = "daz.enable_drivers"
    bl_label = "Enable Drivers"
    bl_description = "Enable all drivers"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        rig = getRigFromContext(context)
        return (rig and rig.DazDriversDisabled)

    def run(self, context):
        setMode('OBJECT')
        rig = getRigFromContext(context)
        rigs = getSelectedArmatures(context)
        rigs.append(rig)
        for rig in set(rigs):
            muteDazFcurves(rig, False)
            rig.DazDriversDisabled = False

#----------------------------------------------------------
#   Clean drivers
#----------------------------------------------------------

class DAZ_OT_RemoveCorruptDrivers(DazOperator, IsMeshArmature):
    bl_idname = "daz.remove_corrupt_drivers"
    bl_label = "Remove Corrupt Drivers"
    bl_description = "Remove corrupt drivers and drivers leading to dependencey loops"
    bl_options = {'UNDO'}

    def run(self, context):
        cleanAllDrivers(context.object)


def cleanAllDrivers(rig):
    if rig.type == 'ARMATURE':
        cleanDrivers(rig)
        cleanDrivers(rig.data)
        for ob in getMeshChildren(rig):
            cleanDrivers(ob)
            cleanDrivers(ob.data.shape_keys)
    elif rig.type == 'MESH':
        cleanDrivers(rig)
        cleanDrivers(rig.data.shape_keys)


def cleanDrivers(rna):
    def illegal(fcu):
        if fcu.driver is None:
            return True
        words = fcu.data_path.split('"')
        if words[0] == "modifiers[":
            mod = rna.modifiers.get(words[1])
            return (mod is None)
        elif words[0] == "key_blocks[":
            if words[1] not in rna.key_blocks.keys():
                return True
            for var in fcu.driver.variables:
                for trg in var.targets:
                    if trg.id == rna:
                        return True
        else:
            prop = getProp(fcu.data_path)
            if prop and prop not in rna.keys():
                return True
        return False

    if rna and rna.animation_data:
        deletes = []
        for fcu in rna.animation_data.drivers:
            if illegal(fcu):
                deletes.append(fcu)
            else:
                for var in fcu.driver.variables:
                    if var.type == 'SINGLE_PROP':
                        for trg in var.targets:
                            prop = getProp(trg.data_path)
                            if (trg.id is None or
                                (isPropRef(trg.data_path) and prop not in trg.id.keys())):
                                deletes.append(fcu)
        if deletes:
            print("Delete %d corrupt drivers from %s" % (len(deletes), rna.name))
        for fcu in deletes:
            try:
                rna.animation_data.drivers.remove(fcu)
            except RuntimeError:
                pass

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_UpdateAll,
    DAZ_OT_DisableDrivers,
    DAZ_OT_EnableDrivers,
    DAZ_OT_OptimizeDrivers,
    DAZ_OT_CopyDrivers,
    DAZ_OT_RemoveCorruptDrivers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.DazDriversDisabled = BoolProperty(default=False)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
