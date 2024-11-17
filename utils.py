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
import math
from mathutils import Vector, Euler
from urllib.parse import quote, unquote
from bpy.props import *
from .settings import GS, LS, ES

BLENDER3 = (bpy.app.version < (4,0,0))
USE_ATTRIBUTES = (bpy.app.version >= (3,0,0))

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

    def setBoneLayers(bone, rig, layers):
        bone.layers = layers

    def setBoneNumLayers(bone, rig, layers):
        bone.layers = layers

    def copyBoneLayers(src, trg, rig):
        trg.layers = list(src.layers)

    def isInNumLayer(bone, rig, layer):
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

    def setBoneLayers(bone, rig, colls):
        for coll in colls:
            coll.assign(bone)

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
        if GS.useBoneColors:
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
    T_HIDDEN = 31
else:
    T_BONES = "Bones"
    T_CUSTOM = "Custom"
    T_TWEAK = "Tweak"
    T_WIDGETS = "Widgets"
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


def setEulerOrder(cns, xyz):
    if hasattr(cns, "euler_order"):
        cns.euler_order = xyz

#-------------------------------------------------------------
#   Overridable properties
#-------------------------------------------------------------

if bpy.app.version < (2,90,0):
    def BoolPropOVR(name="", default=False, description="", update=None):
        return bpy.props.BoolProperty(name=name, default=default, description=description, update=update)

    def FloatPropOVR(default, name, description="", precision=2, min=0, max=1, update=None):
        return bpy.props.FloatProperty(name=name, default=default, description=description, precision=precision, min=min, max=max, update=update)

    def setOverridable(rna, attr):
        pass
else:
    def BoolPropOVR(name="", default=False, description="", update=None):
        return bpy.props.BoolProperty(name=name, default=default, description=description, update=update, override={'LIBRARY_OVERRIDABLE'})

    def FloatPropOVR(default, name, description="", precision=2, min=0, max=1, update=None):
        return bpy.props.FloatProperty(name=name, default=default, description=description, precision=precision, min=min, max=max, update=update, override={'LIBRARY_OVERRIDABLE'})

    def setOverridable(rna, attr):
        rna.property_overridable_library_set(propRef(attr), True)

#-------------------------------------------------------------
#   Utility functions
#-------------------------------------------------------------

def deselectAllVerts(ob):
    for f in ob.data.polygons:
        f.select = False
    for e in ob.data.edges:
        e.select = False
    for v in ob.data.vertices:
        v.select = False


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
    if Vector(ob.location).length < 1e-6:
        ob.location = Zero
    if Vector(ob.rotation_euler).length < 1e-6:
        ob.rotation_euler = Zero
    if (Vector(ob.scale) - One).length < 1e-6:
        ob.scale = One


def nonzero(vec):
    return (max([abs(x) for x in vec]) > 1e-6)


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
        return words[1], words[-1].split(".")[-1]
    else:
        return None, None


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

def updatePose():
    bpy.context.view_layer.update()

#-------------------------------------------------------------
#   More utility functions
#-------------------------------------------------------------

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
    return prop[0:57]

def finalProp(prop):
    return "%s(fin)" % prop[0:57]

def restProp(prop):
    return "%s(rst)" % prop[0:57]

def baseProp(string):
    if string[-5:] in ["(fin)", "(rst)"]:
        return string[:-5]
    return string

def normKey(key):
    if key is None:
        return None
    else:
        return unquote(key.lower())

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
    #return isHDName(ob.name)
    return ob.get("DazHDMesh", False)

def isDrvBone(string):
    return string.endswith("(drv)")

def baseBone(string):
    if string[-5:] in ["(fin)", "(drv)"]:
        return string[:-5]
    return string

def isFinal(string):
    return (string[-5:] == "(fin)")

def isRest(string):
    return (string[-5:] == "(rst)")

def drvBone(string):
    if isDrvBone(string):
        return string
    return string + "(drv)"

def nextLetter(char):
    return ("f" if char == "d" else chr(ord(char) + 1))

def isSimpleType(x):
    return (isinstance(x, int) or
            isinstance(x, float) or
            isinstance(x, str) or
            isinstance(x, bool) or
            x is None)

def clearProp(rna, prop):
    value = rna.get(prop)
    if value is None or isinstance(value, float):
        rna[prop] = 0.0
    elif isinstance(value, bool):
        rna[prop] = False
    elif isinstance(value, int):
        rna[prop] = 0

def setProp(rna, prop):
    value = rna.get(prop)
    if value is None or isinstance(value, float):
        rna[prop] = 1.0
    elif isinstance(value, bool):
        rna[prop] = True
    elif isinstance(value, int):
        rna[prop] = 1

def addToStruct(struct, key, prop, value):
    if key not in struct.keys():
        struct[key] = {}
    struct[key][prop] = value

def averageColor(value):
    if isVector(value):
        x,y,z = value
        return (x+y+z)/3
    else:
        return value

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

#-------------------------------------------------------------
#   Profiling
#-------------------------------------------------------------

from time import perf_counter

class Timer:
    def __init__(self):
        self.t = perf_counter()

    def print(self, msg):
        t = perf_counter()
        print("%8.6f: %s" % (t-self.t, msg))
        self.t = t

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


D2R = "%.6f*" % (math.pi/180)
D = math.pi/180



