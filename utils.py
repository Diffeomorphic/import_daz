# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import math
from math import pi
from mathutils import Vector, Euler, Matrix
from urllib.parse import quote, unquote
from time import perf_counter
from bpy.props import *
from .settings import GS, LS, ES

BLENDER3 = (bpy.app.version < (4,0,0))
BLENDER4 = (bpy.app.version < (5,0,0))
BLENDER5 = (bpy.app.version < (6,0,0))
DAZ_PROPS = True

#-------------------------------------------------------------
#   Blender 5
#-------------------------------------------------------------

if BLENDER4:
    def P2B(pb):
        return pb.bone

    def get_uv(uvlayer, n):
        return uvlayer.data[n].uv

    def set_uv(uvlayer, n, uv):
        uvlayer.data[n].uv = uv

    def foreach_get_uv(uvlayer, array):
        uvlayer.data.foreach_get("uv", array)

    def foreach_set_uv(uvlayer, array):
        uvlayer.data.foreach_set("uv", array)

    def uv_length(uvlayer):
        return len(uvlayer.data)
else:
    def P2B(pb):
        return pb

    def get_uv(uvlayer, n):
        return uvlayer.uv[n].vector

    def set_uv(uvlayer, n, uv):
        uvlayer.uv[n].vector = uv

    def foreach_get_uv(uvlayer, array):
        uvlayer.uv.foreach_get("vector", array)

    def foreach_set_uv(uvlayer, array):
        uvlayer.uv.foreach_set("vector", array)

    def uv_length(uvlayer):
        return len(uvlayer.uv)

#-------------------------------------------------------------
#   Action slots
#-------------------------------------------------------------

if bpy.app.version < (4,4,0):

    def getActionBag(act, id_type='OBJECT'):
        return act

    def getActionFcurves(act, id_type='OBJECT'):
        if act:
            return act.fcurves
        else:
            return []

    def getRnaFcurves(rna, id_type='OBJECT'):
        if rna.animation_data and rna.animation_data.action:
            return rna.animation_data.action.fcurves
        else:
            return []

    def setNewAction(rna, aname):
        if rna.animation_data is None:
            rna.animation_data_create()
        act = bpy.data.actions.new(name=aname)
        rna.animation_data.action = act
        return act

else:

    def getActionBag(act, id_type='OBJECT'):
        if act and act.layers:
            strip = act.layers[0].strips[0]
            for slot in act.slots:
                if slot.target_id_type == id_type:
                    return strip.channelbag(slot, ensure=True)

    def getActionFcurves(act, id_type='OBJECT'):
        bag = getActionBag(act, id_type)
        if bag:
            return bag.fcurves
        else:
            return []

    def getRnaFcurves(rna):
        if rna.animation_data and rna.animation_data.action:
            return getActionFcurves(rna.animation_data.action, rna.id_type)
        else:
            return []

    def setNewAction(rna, aname):
        if rna.animation_data is None:
            rna.animation_data_create()
        act = bpy.data.actions.new(name=aname)
        rna.animation_data.action = act
        if rna.id_type == 'OBJECT':
            path = "location"
        elif rna.id_type == 'KEY':
            path = 'key_blocks[0].value'
        rna.keyframe_insert(path)
        rna.keyframe_delete(path)
        return act

#-------------------------------------------------------------
#   Bone layers
#-------------------------------------------------------------

if BLENDER3:
    def enableBoneNumLayer(bone, rig, layer):
        bone.layers = layer*[False] + [True] + (31-layer)*[False]

    def setBoneNumLayer(bone, rig, layer, value=True):
        bone.layers[layer] = value

    def getBoneLayers(bone, rig):
        return list(bone.layers)

    def setBoneNumLayers(bone, rig, layers):
        bone.layers = layers

    def copyBoneLayers(src, trg, rig):
        trg.layers = list(src.layers)

    def isInNumLayer(bone, rig, layer):
        if isinstance(layer, tuple):
            return False
        return bone.layers[layer]

    def getRigLayers(rig):
        return list(rig.data.layers)

    def setRigLayers(rig, layers):
        rig.data.layers = layers

    def enableRigNumLayers(rig, layers):
        rig.data.layers = 31*[False] + [True]
        for idx in layers:
            rig.data.layers[idx] = True
        rig.data.layers[31] = False

    def enableAllRigLayers(rig, value=True):
        rig.data.layers = 32*[value]

    def enableRigNumLayer(rig, layer, value=True):
        rig.data.layers[layer] = value

    def makeBoneCollections(rig, table):
        return

    def clearBoneCollections(rig, cnames):
        pass

    def assignOtherBones(rig, layer):
        pass

    def setBonegroup(pb, rig, bgname, color):
        pb.bone_group = rig.pose.bone_groups[bgname]

else:
    def enableBoneNumLayer(bone, rig, layer):
        for coll in rig.data.collections:
            coll.unassign(bone)
        coll = rig.data.collections.get(layer)
        if coll is None:
            coll = rig.data.collections.new(layer)
        coll.assign(bone)

    def setBoneNumLayer(bone, rig, layer, value=True):
        coll = rig.data.collections.get(layer)
        if coll is None:
            coll = rig.data.collections.new(layer)
        if value:
            coll.assign(bone)
        else:
            coll.unassign(bone)

    def getBoneLayers(bone, rig):
        return [coll for coll in rig.data.collections if bone.name in coll.bones]

    def setBoneNumLayers(bone, rig, layers):
        for coll in rig.data.collections:
            coll.unassign(bone)
        for coll in rig.data.collections.get(layer, []):
            if layers.get(layer):
                coll.assign(bone)

    def copyBoneLayers(src, trg, rig):
        for coll in rig.data.collections:
            if src.name in coll.bones:
                coll.assign(trg)

    def isInNumLayer(bone, rig, layer):
        if isinstance(layer, tuple):
            for cname in layer:
                coll = rig.data.collections.get(cname)
                if (coll and bone.name in coll.bones):
                    return True
            return False
        coll = rig.data.collections.get(layer)
        return (coll and bone.name in coll.bones)

    def getRigLayers(rig):
        return [(coll,coll.is_visible) for coll in rig.data.collections]

    def setRigLayers(rig, layers):
        for coll,vis in layers:
            coll.is_visible = vis

    def enableRigNumLayers(rig, layers):
        for coll in rig.data.collections:
            coll.is_visible = False
        for layer in layers:
            coll = rig.data.collections.get(layer)
            if coll is None:
                coll = rig.data.collections.new(layer)
            coll.is_visible = True

    def enableAllRigLayers(rig, value=True):
        for coll in rig.data.collections:
            coll.is_visible = value

    def enableRigNumLayer(rig, layer, value=True):
        coll = rig.data.collections.get(layer)
        if coll:
            coll.is_visible = value

    def makeBoneCollections(rig, table):
        for cname in table.keys():
            coll = rig.data.collections.get(cname)
            if coll is None:
                coll = rig.data.collections.new(cname)
                coll.is_visible = True

    def assignOtherBones(rig, layer):
        taken = {}
        for coll in rig.data.collections:
            for bone in rig.data.bones:
                if bone.name in coll.bones:
                    taken[bone.name] = True
        coll = rig.data.collections.get(layer)
        if coll:
            for bone in rig.data.bones:
                if not taken.get(bone.name):
                    coll.assign(bone)

    def clearBoneCollections(rig, cnames):
        for coll in list(rig.data.collections):
            if coll is None:
                print("What?", list(rig.data.collections))
            elif coll.name in cnames or coll.name.startswith("Layer"):
                rig.data.collections.remove(coll)

    def setBonegroup(pb, rig, bgname, color):
        if GS.useBoneColors and hasattr(pb, "color"):
            pb.color.palette = 'CUSTOM'
            pb.color.custom.normal = color
            pb.color.custom.select = (0.6, 0.9, 1.0)
            pb.color.custom.active = (1.0, 1.0, 0.8)

#-------------------------------------------------------------
#   Standard layers
#-------------------------------------------------------------

if BLENDER3:
    T_BONES = 0
    T_CUSTOM = 1
    T_TWEAK = 2
    T_WIDGETS = 3
    T_ERC = 4
    T_HIDDEN = 31
else:
    T_BONES = "Bones"
    T_CUSTOM = "Custom"
    T_TWEAK = "Tweak"
    T_WIDGETS = "Widgets"
    T_ERC = "ERC"
    T_HIDDEN = "Hidden"

#-------------------------------------------------------------
#   Blender 2.8 compatibility
#-------------------------------------------------------------

def getHideViewport(ob):
    return (ob.hide_get() or ob.hide_viewport)

def getVisibleObjects(context):
    return [ob for ob in context.view_layer.objects
        if not (ob.hide_get() or ob.hide_viewport)]

def getVisibleMeshes(context):
    return [ob for ob in context.view_layer.objects
        if ob.type == 'MESH' and not (ob.hide_get() or ob.hide_viewport)]

def getVisibleArmatures(context):
    return [ob for ob in context.view_layer.objects
        if ob.type == 'ARMATURE' and not (ob.hide_get() or ob.hide_viewport)]

def getSelectedObjects(context):
    return [ob for ob in context.view_layer.objects
        if ob.select_get() and not (ob.hide_get() or ob.hide_viewport)]

def getSelectedMeshes(context):
    return [ob for ob in context.view_layer.objects
            if ob.select_get() and ob.type == 'MESH' and not (ob.hide_get() or ob.hide_viewport)]

def getSelectedArmatures(context):
    return [ob for ob in context.view_layer.objects
            if ob.select_get() and ob.type == 'ARMATURE' and not (ob.hide_get() or ob.hide_viewport)]

def getActiveObject(context):
    return context.view_layer.objects.active

def setActiveObject(context, ob):
    try:
        context.view_layer.objects.active = ob
        return True
    except:
        return False


def getLayerCollection(context, coll):
    def getColl(layer, coll):
        if layer.collection == coll:
            return layer
        for child in layer.children:
            clayer = getColl(child, coll)
            if clayer:
                return clayer
        return None

    return getColl(context.view_layer.layer_collection, coll)


def getCollection(context, ob):
    for coll in bpy.data.collections:
        if ob.name in coll.objects.keys():
            return coll
    return context.scene.collection


def activateObject(context, ob):
    if ob is None:
        return False
    try:
        ob.hide_viewport = False
        ob.hide_set(False)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        return True
    except:
        print("Could not activate", ob.name)
        return False


def unhide(objects):
    hides = [(ob, ob.hide_get(), ob.hide_viewport) for ob in objects]
    for ob in objects:
        ob.hide_viewport = False
        ob.hide_set(False)
    return hides


def rehide(hides):
    for ob, hide1, hide2 in hides:
        ob.hide_set(hide1)
        ob.hide_viewport = hide2


def selectSet(ob, value):
    try:
        ob.select_set(value)
        return True
    except:
        return False


def setMode(mode):
    try:
        bpy.ops.object.mode_set(mode=mode)
    except RuntimeError as err:
        from .error import DazError
        raise DazError(str(err))


def selectObjects(context, objects):
    if context.object:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        selectSet(ob, True)


def unlinkAll(ob, clearParent):
    if clearParent:
        try:
            ob.parent = None
        except ReferenceError:
            pass
    for coll in bpy.data.collections:
        if ob in coll.objects.values():
            coll.objects.unlink(ob)
    coll = bpy.context.scene.collection
    if ob in coll.objects.values():
        coll.objects.unlink(ob)

#-------------------------------------------------------------
#   Overridable properties
#   Blender 2.90 support dropped
#-------------------------------------------------------------

def setOverridable(rna, attr):
    rna.property_overridable_library_set(propRef(attr), True)

#-------------------------------------------------------------
#   Utility functions
#-------------------------------------------------------------

def getattrib(rna, attr):
    if hasattr(rna, attr):
        return getattr(rna, attr)


def deleteObjects(context, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        if ob:
            dtype = ob.type
            if ob.data:
                data = ob.data
                users = ob.data.users
            else:
                users = 0
            unlinkAll(ob, True)
            bpy.data.objects.remove(ob)
            if users == 1:
                if dtype == 'MESH':
                    bpy.data.meshes.remove(data)
                elif dtype == 'ARMATURE':
                    bpy.data.armatures.remove(data)
                elif dtype == 'CURVES':
                    bpy.data.curves.remove(data)


def setWorldMatrix(ob, wmat):
    if ob.parent:
        if ob.parent_type == 'BONE':
            pb = ob.parent.pose.bones.get(ob.parent_bone)
            if pb:
                ob.matrix_parent_inverse = pb.matrix.inverted()
        else:
            ob.matrix_parent_inverse = ob.parent.matrix_world.inverted()
    ob.matrix_world = wmat
    trunc2Default(ob, "location", 0, GS.scale*1e-4)
    trunc2Default(ob, "rotation_euler", 0, 1e-4)
    trunc2Default(ob, "scale", 1, 1e-4)


def trunc2Default(ob, attr, default, eps):
    vec = [(x if abs(x - default) > eps else default) for x in getattr(ob, attr)]
    setattr(ob, attr, vec)


def getEpsilon(channel):
    if channel == "location":
        return GS.scale * 1e-4
    else:
        return 1e-4


def nonzero(vec, channel=None):
    return (max([abs(x) for x in vec]) > getEpsilon(channel))


def getEulerMatrix(vec, xyz):
    return Euler(Vector(vec)*D, xyz).to_matrix().to_4x4()


def getRigParent(ob):
    par = ob.parent
    while par and par.type != 'ARMATURE':
        par = par.parent
    return par


def getBoneChannel(fcu):
    words = fcu.data_path.split('"')
    if words[0] == "pose.bones[":
        bname = words[1]
        channel = words[-1].split(".")[-1]
        if words[2] == "].constraints[":
            cnsname = words[3]
        else:
            cnsname = None
        return bname, channel, cnsname
    else:
        return None, None, None


def getShapeChannel(fcu):
    words = fcu.data_path.split('"')
    if words[0] == "key_blocks[":
        return words[1], words[-1].split(".")[-1]
    else:
        return None, None


#-------------------------------------------------------------
#   Updating
#-------------------------------------------------------------

def updateScene(context):
    dg = context.evaluated_depsgraph_get()
    dg.update()

def updateObject(context, ob):
    dg = context.evaluated_depsgraph_get()
    return ob.evaluated_get(dg)

def updateDrivers(rna):
    if rna:
        rna.update_tag()
        if rna.animation_data:
            for fcu in rna.animation_data.drivers:
                if fcu.driver.type == 'SCRIPTED':
                    fcu.driver.expression = str(fcu.driver.expression)

def updateRigDrivers(context, rig):
    updateScene(context)
    if rig:
        updateDrivers(rig.data)
        updateDrivers(rig)

def updateAll(context):
    updateScene(context)
    for ob in context.scene.collection.all_objects:
        updateDrivers(ob)

#-------------------------------------------------------------
#   More utility functions
#-------------------------------------------------------------

def getVertexWeights(ob, idx):
    return [(v, g.weight) for v in ob.data.vertices for g in v.groups if g.group == idx]

def getFigure(ob):
    if dazRna(ob).DazFigure:
        return dazRna(ob).DazFigure
    elif ob.parent:
        return dazRna(ob.parent).DazUrl
    else:
        return None

def instRef(ref):
    return ref.rsplit("#",1)[-1]

def clamp(value):
    return min(1, max(0, value))

def isVector(value):
    return (not isinstance(value, str) and hasattr(value, "__len__") and len(value) >= 3)

def propRef(prop):
    return '["%s"]' % prop

def isPropRef(path):
    return (path[0:2] == '["' and path[-2:] == '"]')

def getProp(path):
    if isPropRef(path):
        return path[2:-2]
    else:
        return ""

def baseName(name):
    words = name.rsplit(".",1)
    if len(words) == 2 and len(words[1]) >= 3 and words[1].isdigit():
        return words[0]
    else:
        return name

def skipName(name):
    words = name.rsplit("-",1)
    if len(words) == 2 and words[1].isdigit():
        return words[0]
    else:
        return name

def stripName(name):
    return skipName(baseName(name))

def normalizePath(path):
    return path.replace("\\", "/")

def rawProp(prop):
    return unquote(prop[0:57])

def finalProp(prop):
    return "%s(fin)" % unquote(prop[0:57])

def restProp(prop):
    return "%s(rst)" % unquote(prop[0:57])

def baseProp(string):
    if string[-5:] in ["(fin)", "(rst)"]:
        return string[:-5]
    return string

def noMeshName(string):
    string = baseName(string)
    if string.endswith(" Mesh"):
        string = string[:-5]
    if string.endswith(" HD"):
        string = string[:-3]
    return string

def HDName(string):
    return "%s HD" % noMeshName(string)

def noHDName(string):
    string = baseName(string)
    if string.endswith(" HD"):
        string = string[:-3]
    return string

def isHDName(string):
    return baseName(string).endswith("HD")

def isHDMesh(ob):
    return dazRna(ob).DazHDMesh

def isDrvBone(string):
    return string.endswith("(drv)")

def isDefBone(string):
    return string.endswith("(def)")

def isDspBone(string):
    return string.endswith("(dsp)")

def isBaseBone(string):
    return (not string.endswith(("(drv)", "(fin)", "(erc)", "(def)")))

def baseBone(string):
    if string[-5:] in ["(fin)", "(drv)"]:
        return string[:-5]
    return string

def ercBase(string):
    if string[-5:] in ["(erc)", "(def)"]:
        return string[:-5]
    return string

def isFinal(string):
    return (string[-5:] == "(fin)")

def isRest(string):
    return (string[-5:] == "(rst)")

def isErcBone(string):
    return string.endswith("(erc)")

def ercBone(string):
    return "%s(erc)" % string

def defBone(string):
    return "%s(def)" % string

def drvBone(string, strict=False):
    if isDrvBone(string) and not strict:
        return string
    return "%s(drv)" % string

def dspBone(string):
    return "%s(dsp)" % string

def nextLetter(char):
    if char == "Z":
        return "a"
    elif char == "d":
        return "f"
    else:
        return chr(ord(char) + 1)

def isSimpleType(x):
    return (isinstance(x, (int, float, str, bool)) or x is None)

def castValue(value, model):
    if isinstance(model, bool):
        return bool(int(value))
    elif isinstance(model, int):
        return int(value)
    elif isinstance(model, float):
        return float(value)
    else:
        return value

def clearProp(rna, prop):
    model = rna.get(prop)
    rna[prop] = castValue(0.0, model)

def setProp(rna, prop):
    model = rna.get(prop)
    rna[prop] = castValue(1.0, model)


def addToStruct(struct, key, prop, value):
    if key not in struct.keys():
        struct[key] = {}
    struct[key][prop] = value

Zero = Vector((0,0,0))
One = Vector((1,1,1))
TTrue = (True, True, True)
FFalse = (False, False, False)

def isLocationLocked(pb):
    if pb.bone.use_connect:
        return True
    return (pb.lock_location[0] and pb.lock_location[1] and pb.lock_location[2])


def lockAllTransforms(pb):
    pb.lock_location = pb.lock_rotation = pb.lock_scale = TTrue


def flatten(xss):
    return [x for xs in xss for x in xs]


def setCustomShapeTransform(pb, scale, trans=None, rot=None):
    if hasattr(pb, "custom_shape_scale_xyz"):
        if isinstance(scale, (int,float)):
            scale = (scale, scale, scale)
        pb.custom_shape_scale_xyz = scale
    elif hasattr(pb, "custom_shape_scale"):
        if isinstance(scale, (int,float)):
            pb.custom_shape_scale = scale
        else:
            x,y,z = scale
            pb.custom_shape_scale = (x+y+z)/3
    if trans and hasattr(pb, "custom_shape_translation"):
        if isinstance(trans, (int,float)):
            trans = (0, trans, 0)
        pb.custom_shape_translation = trans
    if rot and hasattr(pb, "custom_shape_rotation_euler"):
        pb.custom_shape_rotation_euler = rot


def getModifier(ob, type):
    for mod in ob.modifiers:
        if mod.type == type:
            return mod
    return None


def getRigFromMesh(ob):
    if ob and ob.type == 'MESH':
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            return mod.object
    return None


def getRigFromContext(context, useMesh=False, strict=True, activate=False):
    ob = context.object
    if ob is None:
        return None
    elif ob.type == 'ARMATURE':
        return ob
    elif ob.type == 'MESH':
        if useMesh:
            return ob
        rig = getRigFromMesh(ob)
        if rig and (not activate or activateObject(context, rig)):
            return rig
    if strict:
        return None
    else:
        return ob


def getRigsFromContext(context):
    rigs = {}
    for ob in getSelectedObjects(context):
        if ob.type == 'MESH':
            rig = getRigFromMesh(ob)
        elif ob.type == 'ARMATURE':
            rig = ob
        else:
            continue
        if rig.name not in rigs.keys():
            rigs[rig.name] = rig
    return rigs.values()


def getMeshChildren(rig):
    return [ob for ob in rig.children if ob.type == 'MESH' and ob.parent_type != 'BONE']

def getShapeChildren(rig):
    return [ob for ob in rig.children if ob.type == 'MESH' and ob.data.shape_keys]

def getConstraint(ob, type):
    for cns in ob.constraints:
        if cns.type == type:
            return cns
    return None


def inheritsScale(pb):
    return (pb.parent and
            isinstance(pb, bpy.types.PoseBone) and
            pb.bone.inherit_scale not in ['NONE', 'NONE_LEGACY'])


def hasPoseBones(rig, bnames):
    for bname in bnames:
        if bname not in rig.pose.bones.keys():
            return False
    return True


def getCurrentValue(struct, default=None):
    if not struct.get("visible", True) and default is not None:
        return default
    elif "current_value" in struct.keys():
        return struct["current_value"]
    else:
        return struct.get("value", default)


def someMatch(keys, string):
    for key in keys:
        if key in string:
            return True
    return False


def canonicalPath(path):
    return path.replace("//", "/")


def applyModifier(mname):
    try:
        bpy.ops.object.modifier_apply(modifier=mname)
    except RuntimeError as err:
        print(err)


def applyModifierAsShape(mname):
    try:
        bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
    except RuntimeError as err:
        print(err)



#-------------------------------------------------------------
#   DAZ props
#-------------------------------------------------------------

if DAZ_PROPS:
    def dazRna(rna):
        return (rna if rna.daz_importer.legacy else rna.daz_importer)

    def setModernProps(rna):
        rna.daz_importer.legacy = False

    def hasLegacyProps(rna):
        return False
        return rna.daz_importer.legacy

    def modernizeBones(rig):
        for pb in rig.pose.bones:
            modernizeBone(pb)

    def modernizeBone(pb):
        setModernProps(pb)
        setModernProps(pb.bone)
else:
    def dazRna(rna):
        return rna

    def setModernProps(rna):
        pass

    def hasLegacyProps(rna):
        return True

    def modernizeBones(rig):
        pass

    def modernizeBone(pb):
        pass

#-------------------------------------------------------------
#   Progress
#-------------------------------------------------------------

def startProgress(string):
    print(string)
    wm = bpy.context.window_manager
    wm.progress_begin(0, 100)

def endProgress():
    wm = bpy.context.window_manager
    wm.progress_update(100)
    wm.progress_end()

def showProgress(n, total, string=None):
    if not ES.easy:
        pct = (100.0*n)/total
        wm = bpy.context.window_manager
        wm.progress_update(int(pct))
        if string:
            print(string)

#-------------------------------------------------------------
#   Coords
#-------------------------------------------------------------

def getIndex(id):
    if id == "x": return 0
    elif id == "y": return 1
    elif id == "z": return 2
    else: return -1


def getCoord(p):
    co = Zero
    for c in p:
        co[getIndex(c["id"])] = c["value"]
    return d2b(co)

def d2b90(v):
    return GS.scale*Vector((v[0], -v[2], v[1]))

def d2b90u(v):
    return Vector((v[0], -v[2], v[1]))

def d2b90s(v):
    return Vector((v[0], v[2], v[1]))


def d2b00(v):
    return GS.scale*Vector(v)

def d2b00u(v):
    return Vector(v)

def d2b00s(v):
    return Vector(v)


def d2b(v):
    if GS.zup:
        return d2b90(v)
    else:
        return d2b00(v)

def d2bu(v):
    if GS.zup:
        return d2b90u(v)
    else:
        return d2b00u(v)

def d2bs(v):
    if GS.zup:
        return d2b90s(v)
    else:
        return d2b00s(v)


def b2d(v):
    return Vector((v[0], v[2], -v[1]))/GS.scale

#-------------------------------------------------------------
#   Global rotation matrices
#-------------------------------------------------------------

RXP = Matrix.Rotation(pi/2, 4, 'X')
RXN = Matrix.Rotation(-pi/2, 4, 'X')
FX = Matrix.Rotation(pi, 4, 'X')
FZ = Matrix.Rotation(pi, 4, 'Z')

D2R = "%.6f*" % (pi/180)
D = pi/180



