# Copyright (c) 2016-2023, Thomas Larsson
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
import math
from mathutils import Vector
from urllib.parse import unquote
from bpy.props import *
from .settings import GS, LS

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
    try:
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        return True
    except:
        print("Could not activate", ob.name)
        return False


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


def unlinkAll(ob):
    for coll in bpy.data.collections:
        if ob in coll.objects.values():
            coll.objects.unlink(ob)
    coll = bpy.context.scene.collection
    if ob in coll.objects.values():
        coll.objects.unlink(ob)

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


def setattrOVR(rna, attr, value):
    setattr(rna, attr, value)
    rna[attr] = value
    setOverridable(rna, attr)

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
    selectObjects(context, objects)
    bpy.ops.object.delete(use_global=False)
    for ob in objects:
        unlinkAll(ob)
        if ob:
            del ob


def setWorldMatrix(ob, wmat):
    if ob.parent:
        if ob.parent_type in ['OBJECT', 'VERTEX', 'VERTEX_3', 'VERTEX_TRI']:
            ob.matrix_parent_inverse = ob.parent.matrix_world.inverted()
        elif ob.parent_type == 'BONE':
            pb = ob.parent.pose.bones.get(ob.parent_bone)
            if pb:
                ob.matrix_parent_inverse = pb.matrix.inverted()
    ob.matrix_world = wmat
    if Vector(ob.location).length < 1e-6:
        ob.location = Zero
    if Vector(ob.rotation_euler).length < 1e-6:
        ob.rotation_euler = Zero
    if (Vector(ob.scale) - One).length < 1e-6:
        ob.scale = One


def nonzero(vec):
    return (max([abs(x) for x in vec]) > 1e-6)


def getRigParent(ob):
    par = ob.parent
    while par and par.type != 'ARMATURE':
        par = par.parent
    return par


def getMeshChildren(rig):
    meshes = []
    for ob in rig.children:
        if ob.type == 'MESH':
            meshes.append(ob)
        else:
            meshes += getMeshChildren(ob)
    return meshes


def isModifiedMesh(ob):
    return (len(ob.data.DazOrigVerts) > 0)

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

def instRef(ref):
    return ref.rsplit("#",1)[-1]

def tolower(url):
    if not GS.caseSensitivePaths:
        return url.lower()
    else:
        return url

def clamp(value):
    return min(1, max(0, value))

def isVector(value):
    return (hasattr(value, "__len__") and len(value) >= 3)

def propRef(prop):
    return '["%s"]' % prop

def getProp(path):
    if path[0:2] == '["' and path[-2:] == '"]':
        return path[2:-2]
    else:
        return None


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

def finalProp(prop):
    return "%s(fin)" % prop

def restProp(prop):
    return "%s(rst)" % prop

def baseProp(string):
    if string[-5:] in ["(fin)", "(rst)"]:
        return string[:-5]
    return string

def isDrvBone(string):
    return string.endswith(("(drv)", "twist1", "twist2"))

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
    return chr(ord(char) + 1)

def isSimpleType(x):
    return (isinstance(x, int) or
            isinstance(x, float) or
            isinstance(x, str) or
            isinstance(x, bool) or
            x is None)

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

def hasObjectTransforms(ob):
    return (ob.location != Zero or
            Vector(ob.rotation_euler) != Zero or
            ob.scale != One)


def isLocationUnlocked(pb):
    if pb.bone.use_connect:
        return False
    return (pb.lock_location[0] == False or
            pb.lock_location[1] == False or
            pb.lock_location[2] == False)


def lockAllTransforms(pb):
    pb.lock_location = pb.lock_rotation = pb.lock_scale = (True,True,True)


def sorted(seq):
    slist = list(seq)
    slist.sort()
    return slist


def getModifier(ob, type):
    for mod in ob.modifiers:
        if mod.type == type:
            return mod
    return None

def getArmatureChildren(context, rig):
    children = []
    for ob in getVisibleMeshes(context):
        if ob.parent == rig:
            children.append(ob)
        else:
            mod = getModifier(ob, 'ARMATURE')
            if mod and mod.object == rig:
                children.append(ob)
    return children

def getConstraint(ob, type):
    for cns in ob.constraints:
        if cns.type == type:
            return cns
    return None


def inheritsScale(pb):
    return (isinstance(pb, bpy.types.PoseBone) and
            pb.bone.inherit_scale not in ['NONE', 'NONE_LEGACY'])


def hasPoseBones(rig, bnames):
    for bname in bnames:
        if bname not in rig.pose.bones.keys():
            return False
    return True


def getCurrentValue(struct, default=None):
    if "current_value" in struct.keys():
        return struct["current_value"]
    elif "value" in struct.keys():
        return struct["value"]
    else:
        return default

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
    return LS.scale*Vector((v[0], -v[2], v[1]))

def d2b90u(v):
    return Vector((v[0], -v[2], v[1]))

def d2b90s(v):
    return Vector((v[0], v[2], v[1]))


def d2b00(v):
    return LS.scale*Vector(v)

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


D2R = "%.6f*" % (math.pi/180)
D = math.pi/180



