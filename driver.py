# Copyright (c) 2016-2021, Thomas Larsson
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
        idx = self.getArrayIndex(fcu)
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if old or assoc:
            self.setId(fcu2, old, new, assoc)
        if rna.animation_data is None:
            if idx > 0:
                rna.driver_add(channel, idx)
            else:
                rna.driver_add(channel)
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
            words = fcu.data_path.split('"')
            if (words[0] == "key_blocks[" and
                len(words) == 3 and
                words[2] == "].value"):
                drivers[words[1]] = fcu

        return drivers


    def copyShapeKeyDrivers(self, ob, drivers):
        if not drivers:
            return
        skeys = ob.data.shape_keys
        self.createTmp()
        try:
            for sname,fcu in drivers.items():
                if (getShapekeyDriver(skeys, sname) or
                    sname not in skeys.key_blocks.keys()):
                    continue
                #skey = skeys.key_blocks[sname]
                self.copyDriver(fcu, skeys)
        finally:
            self.deleteTmp()


    def copyDrivers(self, src, trg, old, new):
        if src.animation_data is None:
            return
        self.createTmp()
        try:
            for fcu in src.animation_data.drivers:
                self.copyDriver(fcu, trg, old, new)
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


def isBoneDriven(rig, pb):
    return (getBoneDrivers(rig, pb) != [])


def getBoneDrivers(rig, pb):
    if rig.animation_data:
        path = 'pose.bones["%s"]' % pb.name
        return [fcu for fcu in rig.animation_data.drivers
                if (fcu.data_path.startswith(path) and
                    not fcu.data_path.endswith(("HdOffset","TlOffset")))]
    else:
        return []


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


def isFaceBoneDriven(rig, pb):
    if isBoneDriven(rig, pb):
        return True
    else:
        par = pb.parent
        return (par and isDrvBone(par.name) and isBoneDriven(rig, par))


def getShapekeyDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), None)


def getShapekeyPropDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), 'SINGLE_PROP')


def getRnaDriver(rna, path, type=None):
    if rna and rna.animation_data:
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


    def fill(self, fcu, fixDrv=False):
        drv = fcu.driver
        drv.type = self.type
        drv.use_self = self.use_self
        drv.expression = self.expression
        for var in self.variables:
            var.create(drv.variables.new(), fixDrv)
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

    def create(self, var, fixDrv=False):
        var.name = self.name
        var.type = self.type
        self.targets[0].create(var.targets[0], fixDrv)
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

    def create(self, trg, fixDrv=False):
        if self.id_type != 'OBJECT':
            trg.id_type = self.id_type
        trg.id = self.id
        trg.bone_target = self.bone_target
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

def addTransformVar(fcu, vname, ttype, rig, bname):
    pb = rig.pose.bones[bname]
    var = fcu.driver.variables.new()
    var.type = 'TRANSFORMS'
    var.name = vname
    trg = var.targets[0]
    trg.id = rig
    trg.bone_target = bname
    if pb.rotation_mode == 'QUATERNION':
        trg.rotation_mode = 'AUTO'
    else:
        trg.rotation_mode = pb.rotation_mode
    trg.transform_type = ttype
    trg.transform_space = 'LOCAL_SPACE'

#-------------------------------------------------------------
#   Prop drivers
#-------------------------------------------------------------

def makePropDriver(path, rna, channel, rig, expr):
    rna.driver_remove(channel)
    fcu = rna.driver_add(channel)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = expr
    removeModifiers(fcu)
    addDriverVar(fcu, "x", path, rig)


def removeModifiers(fcu):
    for mod in list(fcu.modifiers):
        fcu.modifiers.remove(mod)

#-------------------------------------------------------------
#   Overridable properties
#-------------------------------------------------------------

def setPropMinMax(rna, prop, default, min, max, ovr):
    if bpy.app.version < (3,0,0):
        rna_ui = rna.get('_RNA_UI')
        if rna_ui is None:
            rna_ui = rna['_RNA_UI'] = {}
        struct = { "min": min, "max": max, "soft_min": min, "soft_max": max}
        rna_ui[prop] = struct
    else:
        from rna_prop_ui import rna_idprop_ui_create
        rna_idprop_ui_create(rna, prop, default=default, min=min, max=max, soft_min=min, soft_max=max, description=None, overridable=ovr)


def getPropMinMax(rna, prop):
    struct = None
    if bpy.app.version < (3,0,0):
        rna_ui = rna.get('_RNA_UI')
        if rna_ui:
            struct = rna_ui.get(prop)
    else:
        try:
            prop_ui = rna.id_properties_ui(prop)
        except KeyError:
            prop_ui = None
        if prop_ui:
            struct = prop_ui.as_dict()
    min = GS.customMin
    max = GS.customMax
    default = 0.0
    ovr = True
    if struct:
        if "min" in struct.keys():
            min = struct["min"]
        if "max" in struct.keys():
            max = struct["max"]
        if "default" in struct.keys():
            max = struct["default"]
        if "overridable" in struct.keys():
            ovr = struct["overridable"]
    return min,max,default,ovr


def truncateProp(prop):
    if len(prop) > 63:
        print('Truncate property "%s"' % prop)
        return prop[:63]
    else:
        return prop


def setFloatProp(rna, prop, value, min, max, ovr):
    value = float(value)
    prop = truncateProp(prop)
    rna[prop] = value
    if min is not None:
        min = float(min)
        max = float(max)
        setPropMinMax(rna, prop, value, min, max, ovr)
        if ovr and bpy.app.version < (3,0,0):
            setOverridable(rna, prop)
            setPropMinMax(rna, prop, value, min, max, ovr)
    elif ovr:
        setOverridable(rna, prop)


def setBoolProp(rna, prop, value, ovr, desc=""):
    prop = truncateProp(prop)
    rna[prop] = value
    setPropMinMax(rna, prop, value, 0, 1, ovr)
    if ovr and bpy.app.version < (3,0,0):
        setOverridable(rna, prop)
        setPropMinMax(rna, prop, value, 0, 1, ovr)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def addDriverVar(fcu, vname, path, rna):
    var = fcu.driver.variables.new()
    var.name = vname
    var.type = 'SINGLE_PROP'
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
    def flatten(lists):
        flat = []
        for list in lists:
            flat.extend(list)
        return flat

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
            if words[0] != "[":
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
#   Copy props
#----------------------------------------------------------

class DAZ_OT_CopyProps(DazOperator, IsObject):
    bl_idname = "daz.copy_props"
    bl_label = "Copy Props"
    bl_description = "Copy properties from selected objects to active object"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in getSelectedObjects(context):
            if ob != rig:
                for key in ob.keys():
                    if key not in rig.keys():
                        rig[key] = ob[key]

#----------------------------------------------------------
#   Copy drivers
#----------------------------------------------------------

class DAZ_OT_CopyBoneDrivers(DazOperator, DriverUser, IsArmature):
    bl_idname = "daz.copy_bone_drivers"
    bl_label = "Copy Bone Drivers"
    bl_description = "Copy bone drivers from selected rig to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in getSelectedArmatures(context):
            if ob != rig:
                self.createTmp()
                try:
                    self.copyBoneDrivers(ob, rig)
                finally:
                    self.deleteTmp()
                return
        raise DazError("Need two selected armatures")


    def copyBoneDrivers(self, rig1, rig2):
        if rig1.animation_data:
            struct = {}
            for fcu in rig1.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (len(words) == 3 and
                    words[0] == "pose.bones["):
                    bname = words[1]
                    if bname not in rig2.data.bones.keys():
                        print("Missing bone (copyBoneDrivers):", bname)
                        continue
                    fcu2 = self.copyDriver(fcu, rig2)
                    self.setId(fcu2, rig1, rig2)

#----------------------------------------------------------
#   Disable and enable drivers
#----------------------------------------------------------

def muteDazFcurves(rig, mute):
    def isDazFcurve(path):
        for string in ["(fin)", "(rst)", ":Loc:", ":Rot:", ":Sca:"]:
            if string in path:
                return True
        return False

    if rig and rig.data.animation_data:
        for fcu in rig.data.animation_data.drivers:
            if isDazFcurve(fcu.data_path):
                fcu.mute = mute
    for ob in rig.children:
        if ob.type == 'MESH':
            skeys = ob.data.shape_keys
            if skeys and skeys.animation_data:
                for fcu in skeys.animation_data.drivers:
                    words = fcu.data_path.split('"')
                    if words[0] == "key_blocks[":
                        fcu.mute = mute
                        sname = words[1]
                        if sname in skeys.key_blocks.keys():
                            skey = skeys.key_blocks[sname]
                            skey.mute = mute


class DAZ_OT_DisableDrivers(DazOperator):
    bl_idname = "daz.disable_drivers"
    bl_label = "Disable Drivers"
    bl_description = "Disable all drivers to improve performance"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazDriversDisabled)

    def run(self, context):
        setMode('OBJECT')
        for rig in getSelectedArmatures(context):
            muteDazFcurves(rig, True)
            rig.DazDriversDisabled = True


class DAZ_OT_EnableDrivers(DazOperator):
    bl_idname = "daz.enable_drivers"
    bl_label = "Enable Drivers"
    bl_description = "Enable all drivers"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazDriversDisabled)

    def run(self, context):
        setMode('OBJECT')
        for rig in getSelectedArmatures(context):
            muteDazFcurves(rig, False)
            rig.DazDriversDisabled = False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CopyProps,
    DAZ_OT_CopyBoneDrivers,
    DAZ_OT_UpdateAll,
    DAZ_OT_DisableDrivers,
    DAZ_OT_EnableDrivers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.DazDriversDisabled = BoolProperty(default=False)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
