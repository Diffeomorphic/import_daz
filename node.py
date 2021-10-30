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
import math
from mathutils import Matrix, Vector, Euler
from collections import OrderedDict
from .asset import Accessor, Asset
from .channels import Channels
from .formula import Formula
from .error import *
from .utils import *

#-------------------------------------------------------------
#   External access
#-------------------------------------------------------------

def parseNode(asset, struct):
    from .figure import Figure, LegacyFigure
    from .bone import Bone
    from .camera import Camera
    from .light import Light
    try:
        type = struct["type"]
    except KeyError:
        type = None

    if type == "figure":
        return asset.parseTypedAsset(struct, Figure)
    elif type == "legacy_figure":
        return asset.parseTypedAsset(struct, LegacyFigure)
    elif type == "bone":
        return asset.parseTypedAsset(struct, Bone)
    elif type == "node":
        return asset.parseTypedAsset(struct, Node)
    elif type == "camera":
        return asset.parseTypedAsset(struct, Camera)
    elif type == "light":
        return asset.parseTypedAsset(struct, Light)
    else:
        msg = "Not implemented node asset type %s" % type
        print(msg)
        #raise NotImplementedError(msg)
        return None

#-------------------------------------------------------------
#   SimNode, also used by GeoNode
#-------------------------------------------------------------

class SimNode:
    def __init__(self):
        self.dyngenhair = None
        self.dynsim = None
        self.dynhairflw = None
        self.lintess = None
        self.simsets = []

#-------------------------------------------------------------
#   Instance
#-------------------------------------------------------------

def copyElements(struct):
    nstruct = {}
    for key,value in struct.items():
        if isinstance(value, dict):
            nstruct[key] = value.copy()
        else:
            nstruct[key] = value
    return nstruct


def getChannelIndex(key):
    if key == "scale/general":
        channel = "general_scale"
        idx = -1
    else:
        channel,comp = key.split("/")
        idx = getIndex(comp)
    return channel, idx


class Instance(Accessor, Channels, SimNode):

    U3 = Matrix().to_3x3()

    def __init__(self, fileref, node, struct):
        from .asset import normalizeRef

        Accessor.__init__(self, fileref)
        self.node = node
        self.index = node.ninstances
        node.ninstances += 1
        self.figure = None
        self.id = normalizeRef(struct["id"])
        self.id = self.getSelfId()
        self.label = node.label
        node.label = None
        self.name = node.getLabel(self)
        node.instances[self.id] = self
        node.instances[self.name] = self
        self.geometries = node.geometries
        node.geometries = []
        self.rotation_order = node.rotation_order
        self.collection = LS.collection
        if "parent" in struct.keys() and node.parent is not None:
            self.parent = node.parent.getInstance(struct["parent"], node.caller)
            if self.parent == self:
                print("Self-parent", self)
                self.parent = None
            if self.parent:
                self.parent.children[self.id] = self
                self.collection = self.parent.collection
        else:
            self.parent = None
        node.parent = None
        self.children = {}
        self.target = None
        if "target" in struct.keys():
            self.target = struct["target"]
        self.visible = node.visible
        node.visible = True
        self.extra = node.extra
        node.extra = []
        self.channels = node.channels
        node.channels = {}
        self.shstruct = {}
        self.center = Vector((0,0,0))
        self.cpoint = Vector((0,0,0))
        self.wmat = self.wrot = self.wscale = Matrix()
        self.refcoll = None
        self.isGroupNode = False
        self.isStrandHair = False
        self.ignore = False
        self.isNodeInstance = False
        self.node2 = None
        self.hdobject = None
        self.modifiers = {}
        self.attributes = copyElements(node.attributes)
        self.restdata = None
        self.wsmat = self.U3
        self.lsmat = None
        self.rigtype = node.rigtype
        node.clearTransforms()
        SimNode.__init__(self)


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        return "<Instance %s %d N: %s P: %s R: %s>" % (self.label, self.index, self.node.name, pname, self.rna)


    def errorWrite(self, ref, fp):
        fp.write('  "%s": %s\n' % (ref, self))
        for geonode in self.geometries:
            geonode.errorWrite("     ", fp)


    def getSelfId(self):
        return self.id


    def isMainFigure(self, level):
        from .figure import FigureInstance
        par = self.parent
        while par and not isinstance(par, FigureInstance):
            par = par.parent
        if par is None:
            return True
        else:
            return False


    def preprocess(self, context):
        self.updateMatrices()
        for channel in self.channels.values():
            if "type" not in channel.keys():
                continue
            elif channel["type"] == "node" and "node" in channel.keys():
                ref = channel["node"]
                node = self.getAsset(ref)
                if node:
                    self.node2 = node.getInstance(ref)
            elif channel["type"] == "bool":
                words = channel["id"].split("_")
                if len(words) > 2 and words[1] == "group" and words[-1] == "vis":
                    if words[0] == "material" and "label" in channel.keys():
                        label = channel["label"]
                        value = getCurrentValue(channel)
                        for geonode in self.geometries:
                            geonode.data.material_group_vis[label] = value
                    elif words[0] == "facet":
                        pass

        for extra in self.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/shell":
                self.shstruct = extra
            elif extra["type"] == "studio/node/group_node":
                self.addGroupNode(context)
            elif extra["type"] == "studio/node/instance":
                self.isNodeInstance = True
            elif extra["type"] == "studio/node/strand_hair":
                self.isStrandHair = True
                for geonode in self.geometries:
                    geonode.isStrandHair = True
            elif extra["type"] == "studio/node/environment":
                self.ignore = True
            elif extra["type"] == "studio/node/tone_mapper":
                self.ignore = True

        for geonode in self.geometries:
            geonode.preprocess(context, self)


    def preprocess2(self, context):
        pass


    def addGroupNode(self, context):
        print("AGG", self.label, self.parent, self.collection.name)
        coll = bpy.data.collections.new(name=self.label)
        if self.parent is None:
            self.collection.children.link(coll)
        self.collection = coll
        self.groupChildren(coll)


    def groupChildren(self, coll):
        for child in self.children.values():
            child.collection = coll
            child.groupChildren(coll)


    def buildChannels(self, ob):
        for channel in self.channels.values():
            if self.ignoreChannel(channel):
                continue
            key = channel["id"]
            value = getCurrentValue(channel)
            if key == "Visible in Viewport":
                self.hideViewport(value, ob)
            elif key == "Renderable":
                self.hideRender(value, ob)
            elif key == "Visible":
                self.hideViewport(value, ob)
                self.hideRender(value, ob)
            elif key == "Selectable":
                self.hideSelect(value, ob)
            elif key == "Visible in Simulation":
                ob.DazCollision = value
            elif key == "Cast Shadows":
                pass
            elif key == "Instance Mode":
                #print("InstMode", ob.name, value)
                pass
            elif key == "Instance Target":
                #print("InstTarg", ob.name)
                pass
            elif key == "Point At":
                pass


    def hideViewport(self, value, ob):
        if not (value or GS.showHiddenObjects):
            ob.hide_set(True)
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_set(True)


    def hideRender(self, value, ob):
        if not (value or GS.showHiddenObjects):
            ob.hide_render = True
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_render = True


    def hideSelect(self, value, ob):
        if not (value or GS.showHiddenObjects):
            ob.hide_select = True
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_select = True


    def ignoreChannel(self, channel):
        return ("id" not in channel.keys() or
                ("visible" in channel.keys() and not channel["visible"]))


    def buildExtra(self, context):
        for extra in self.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/environment":
                if LS.useWorld != 'NEVER':
                    if not LS.render:
                        from .render import RenderOptions
                        LS.render = RenderOptions(self.fileref)
                        LS.render.channels = self.channels
                    else:
                        LS.render.copyChannels(self.channels)


    def postbuild(self, context):
        self.parentObject(context, self.rna)
        for geonode in self.geometries:
            geonode.postbuild(context, self)


    def buildInstance(self, context):
        if self.isNodeInstance and GS.useInstancing:
            if self.node2 is None:
                print('Instance "%s" has no node' % self.name)
            elif self.rna is None:
                print('Instance "%s" has not been built' % self.name)
            elif self.rna.type != 'EMPTY':
                print('Instance "%s" is not an empty' % self.name)
            elif self.node2.rna is None:
                print('Instance "%s" node2 "%s" not built' % (inst.name, inst.node2.name))
            else:
                self.buildNodeInstance(context)


    def buildNodeInstance(self, context):
        parent = self.node2
        ob = parent.rna
        if parent.refcoll:
            refcoll = parent.refcoll
        else:
            refcoll = self.getInstanceColl(ob)
        if refcoll is None:
            refcoll = self.makeNewRefColl(context, ob, parent.collection)
            parent.refcoll = refcoll
        empty = self.rna
        empty.instance_type = 'COLLECTION'
        empty.instance_collection = refcoll
        #addToCollection(empty, parent.collection)


    def makeNewRefColl(self, context, ob, parcoll):
        refname = "%s REF" % ob.name
        refcoll = bpy.data.collections.new(name=refname)
        if LS.refColls is None:
            LS.refColls = bpy.data.collections.new(name = "%s REFS" % LS.collection.name)
            context.scene.collection.children.link(LS.refColls)
        LS.refColls.children.link(refcoll)
        LS.duplis[refname] = Dupli(ob, refcoll, parcoll)
        return refcoll


    def getInstanceColl(self, ob):
        if ob.instance_type == 'COLLECTION':
            #for ob1 in ob.instance_collection.objects:
            #    coll = self.getInstanceColl(ob1)
            #    if coll:
            #        return coll
            return ob.instance_collection
        return None


    def poseRig(self, context):
        pass


    def finalize(self, context):
        ob = self.rna
        if ob is None:
            return
        for geonode in self.geometries:
            geonode.finalize(context, self)
        self.buildChannels(ob)
        if self.dynsim:
            self.dynsim.build(context)
        if self.dyngenhair:
            self.dyngenhair.build(context)
        if self.dynhairflw:
            self.dynhairflw.build(context)


    def formulate(self, key, value):
        pass


    def updateMatrices(self):
        # From http://docs.daz3d.com/doku.php/public/dson_spec/object_definitions/node/start
        #
        # center_offset = center_point - parent.center_point
        # global_translation = parent.global_transform * (center_offset + translation)
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        # global_scale for nodes that inherit scale = parent.global_scale * orientation * scale * general_scale * (orientation)-1
        # global_scale for nodes = parent.global_scale * (parent.local_scale)-1 * orientation * scale * general_scale * (orientation)-1
        # global_transform = global_translation * global_rotation * global_scale

        trans = d2b00(self.attributes["translation"])
        rotation = Vector(self.attributes["rotation"])*D
        genscale = self.attributes["general_scale"]
        scale = Vector(self.attributes["scale"]) * genscale
        orientation = Vector(self.attributes["orientation"])*D
        self.cpoint = d2b00(self.attributes["center_point"])

        lrot = Euler(rotation, self.rotation_order).to_matrix().to_4x4()
        self.lscale = Matrix()
        for i in range(3):
            self.lscale[i][i] = scale[i]
        orient = Euler(orientation).to_matrix().to_4x4()

        par = self.parent
        if par:
            coffset = self.cpoint - self.parent.cpoint
            self.wtrans = par.wmat @ (coffset + trans)
            self.wrot = par.wrot @ orient @ lrot @ orient.inverted()
            oscale = orient @ self.lscale @ orient.inverted()
            if True:  # self.inherits_scale:
                self.wscale = par.wscale @ oscale
            else:
                self.wscale = par.wscale @ par.lscale.inverted() @ oscale
        else:
            self.wtrans = self.cpoint + trans
            self.wrot = orient @ lrot @ orient.inverted()
            self.wscale = orient @ self.lscale @ orient.inverted()

        transmat = Matrix.Translation(self.wtrans)
        self.wmat = transmat @ self.wrot @ self.wscale
        if GS.zup:
            self.worldmat = self.RXP @ self.wmat @ self.RXN
        else:
            self.worldmat = self.wmat

    RXP = Matrix.Rotation(math.pi/2, 4, 'X')
    RXN = Matrix.Rotation(-math.pi/2, 4, 'X')


    def parentObject(self, context, ob):
        from .figure import FigureInstance
        from .bone import BoneInstance

        if ob is None:
            return

        if self.parent is None:
            ob.parent = None
        elif self.parent.rna == ob:
            print("Warning: Trying to parent %s to itself" % ob)
            ob.parent = None
        elif isinstance(self.parent, FigureInstance):
            for geonode in self.geometries:
                geonode.setHideInfo()
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        elif isinstance(self.parent, BoneInstance):
            if self.parent.figure is None:
                print("No figure found:", self.parent)
                return
            rig = self.parent.figure.rna
            ob.parent = rig
            bname = self.parent.node.name
            if bname in rig.pose.bones.keys():
                ob.parent_bone = bname
                ob.parent_type = 'BONE'
        elif isinstance(self.parent, Instance):
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        else:
            raise RuntimeError("Unknown parent %s %s" % (self, self.parent))

        setWorldMatrix(ob, self.worldmat)
        self.node.postTransform()


    def getLocalMatrix(self, wsmat, orient):
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        lsmat = self.wsmat = wsmat
        if self.parent:
            try:
                lsmat = self.parent.wsmat.inverted() @ wsmat
            except ValueError:
                print("Failed to invert parent matrix")
        return orient.inverted() @ lsmat @ orient

#-------------------------------------------------------------
#   Dupli
#-------------------------------------------------------------

class Dupli:
    def __init__(self, ob, refcoll, parcoll):
        self.object = ob
        self.refcoll = refcoll
        self.parcoll = parcoll
        obname = ob.name
        ob.name = refcoll.name
        self.empty = bpy.data.objects.new(obname, None)
        self.empty.instance_type = 'COLLECTION'
        self.empty.instance_collection = self.refcoll
        parcoll.objects.link(self.empty)
        print("DUP", self.empty.name, parcoll.name)


    def addToRefColl(self, ob):
        if ob.name in self.parcoll.objects:
            self.parcoll.objects.unlink(ob)
        addToCollection(ob, self.refcoll)
        for child in ob.children:
            self.addToRefColl(child)


    def excludeRefColl(self, toplayer):
        layer = findLayerCollection(toplayer, self.refcoll)
        layer.exclude = True


    def storeTransforms(self, wmats):
        ob = self.object
        wmat = ob.matrix_world.copy()
        wmats[ob.name] = (ob, wmat)
        for child in ob.children:
            wmat = child.matrix_world.copy()
            wmats[child.name] = (child, wmat)


    def transformEmpty(self):
        ob = self.object
        wmat = ob.matrix_world.copy()
        self.empty.parent = ob.parent
        setWorldMatrix(self.empty, wmat)
        ob.parent = None
        ob.matrix_world = Matrix()


def transformDuplis(context):
    wmats = {}
    for dupli in LS.duplis.values():
        dupli.storeTransforms(wmats)
    for dupli in LS.duplis.values():
        dupli.transformEmpty()
    for dupli in LS.duplis.values():
        dupli.addToRefColl(dupli.object)
    toplayer = context.view_layer.layer_collection
    for dupli in LS.duplis.values():
        dupli.excludeRefColl(toplayer)


def copyCollections(src, trg):
    for coll in bpy.data.collections:
        if (src.name in coll.objects and
            trg.name not in coll.objects):
            coll.objects.link(trg)


def addToCollection(ob, coll):
    if ob.name not in coll.objects:
        try:
            coll.objects.link(ob)
        except RuntimeError:
            pass
        #    print("Cannot link '%s' to '%s'" % (ob.name, coll.name))


def findLayerCollection(layer, coll):
    if layer.collection == coll:
        return layer
    for child in layer.children:
        clayer = findLayerCollection(child, coll)
        if clayer:
            return clayer
    return None


def createHiddenCollection(context, ob):
    parcoll = getCollection(ob)
    for coll in parcoll.children:
        if coll.name.startswith("Hidden"):
            return coll
    coll = bpy.data.collections.new(name="Hidden")
    parcoll.children.link(coll)
    layer = findLayerCollection(context.view_layer.layer_collection, coll)
    if layer:
        layer.exclude = True
    return coll

#-------------------------------------------------------------
#   Node
#-------------------------------------------------------------

class Node(Asset, Formula, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Formula.__init__(self)
        Channels.__init__(self)
        self.classType = Node
        self.instances = {}
        self.ninstances = 0
        self.count = 0
        self.data = None
        self.center = None
        self.geometries = []
        self.rotation_order = 'XYZ'
        self.attributes = self.defaultAttributes()
        self.origAttrs = self.defaultAttributes()
        self.figure = None
        self.rigtype = ""


    def defaultAttributes(self):
        return {
            "center_point": Vector((0,0,0)),
            "end_point": Vector((0,0,0)),
            "orientation": Vector((0,0,0)),
            "translation": Vector((0,0,0)),
            "rotation": Vector((0,0,0)),
            "scale": Vector((1,1,1)),
            "general_scale": 1
        }


    def clearTransforms(self):
        default = self.defaultAttributes()
        for key in ["translation", "rotation", "scale", "general_scale"]:
            self.attributes[key] = default[key]


    def __repr__(self):
        pid = (self.parent.id if self.parent else None)
        return ("<Node %s %s P: %s G: %s>" % (self.id, self.label, pid, self.geometries))


    def errorWrite(self, ref, fp):
        Asset.errorWrite(self, ref, fp)
        for iref,inst in self.instances.items():
            inst.errorWrite(iref, fp)


    def postTransform(self):
        pass


    def makeInstance(self, fileref, struct):
        return Instance(fileref, self, struct)


    def getInstance(self, ref, caller=None):
        if caller is None:
            caller = self
        iref = instRef(ref)
        if iref in caller.instances.keys():
            return caller.instances[iref]
        iref = unquote(iref)
        if iref in caller.instances.keys():
            return caller.instances[iref]
        else:
            msg = ("Node: Did not find instance %s in %s" % (iref, caller))
            insts = caller.instances
            reportError(msg, insts, trigger=(2,4))
        return None


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)

        for key,data in struct.items():
            if key == "formulas":
                self.formulas = data
            elif key == "inherits_scale":
                pass
            elif key == "rotation_order":
                self.rotation_order = data
            elif key in self.attributes.keys():
                self.setAttribute(key, data)

        for key in self.attributes.keys():
            self.origAttrs[key] = self.attributes[key]
        return self


    def setExtra(self, extra):
        pass


    Indices = { "x": 0, "y": 1, "z": 2 }

    def setAttribute(self, channel, data):
        if isinstance(data, list):
            for comp in data:
                idx = self.Indices[comp["id"]]
                value = getCurrentValue(comp)
                if value is not None:
                    self.attributes[channel][idx] = value
        else:
            self.attributes[channel] = getCurrentValue(data)


    def update(self, struct):
        from .geometry import GeoNode, Geometry
        Asset.update(self, struct)
        Channels.update(self, struct)
        for channel,data in struct.items():
            if channel == "geometries":
                for geostruct in data:
                    if "url" in geostruct.keys():
                        geo = self.parseUrlAsset(geostruct, Geometry)
                        geonode = GeoNode(self, geo, geostruct["id"])
                    else:
                        print("No geometry URL")
                        geonode = GeoNode(self, None, geostruct["id"])
                        self.saveAsset(geostruct, geonode)
                    geonode.parse(geostruct)
                    geonode.update(geostruct)
                    geonode.extra = self.extra
                    self.geometries.append(geonode)
            elif channel in self.attributes.keys():
                self.setAttribute(channel, data)
        if LS.useMorph and "preview" in struct.keys():
            preview = struct["preview"]
            pcenter = Vector(preview["center_point"])
            pend = Vector(preview["end_point"])
            bcenter = self.attributes["center_point"]
            bend = self.attributes["end_point"]
            self.attributes["center_point"] = bcenter + LS.morphStrength*(pcenter-bcenter)
            self.attributes["end_point"] = bend + LS.morphStrength*(pend-bend)
        self.count += 1


    def build(self, context, inst):
        center = d2b(inst.attributes["center_point"])
        if inst.ignore:
            print("Ignore", inst)
        elif inst.geometries:
            for geonode in inst.geometries:
                geonode.buildObject(context, inst, center)
                inst.rna = geonode.rna
        else:
            self.buildObject(context, inst, center)
        if inst.extra:
            inst.buildExtra(context)


    def buildObject(self, context, inst, center):
        scn = context.scene
        if isinstance(self.data, Asset):
            if self.data.shstruct and GS.mergeShells:
                return
            ob = self.data.buildData(context, self, inst, center)
            if not isinstance(ob, bpy.types.Object):
                ob = bpy.data.objects.new(inst.name, self.data.rna)
        else:
            ob = bpy.data.objects.new(inst.name, self.data)
        self.rna = inst.rna = ob
        LS.objects[LS.rigname].append(ob)
        self.arrangeObject(ob, inst, context, center)
        self.subdivideObject(ob, inst, context)


    def arrangeObject(self, ob, inst, context, center):
        blenderRotMode = {
            'XYZ' : 'XZY',
            'XZY' : 'XYZ',
            'YXZ' : 'ZXY',
            'YZX' : 'ZYX',
            'ZXY' : 'YXZ',
            'ZYX' : 'YZX',
        }
        ob.rotation_mode = blenderRotMode[self.rotation_order]
        ob.DazRotMode = self.rotation_order
        ob.DazMorphPrefixes = False
        inst.collection.objects.link(ob)
        print("ARR", ob.name, inst.collection.name)
        ob.DazId = self.id
        ob.DazUrl = unquote(self.url)
        ob.DazScene = LS.scene
        ob.DazScale = LS.scale
        ob.DazOrient = inst.attributes["orientation"]
        self.subtractCenter(ob, inst, center)


    def subtractCenter(self, ob, inst, center):
        ob.location = -center
        inst.center = center


    def subdivideObject(self, ob, inst, context):
        pass

#-------------------------------------------------------------
#   Transform matrix
#
#   dmat = Daz bone orientation, in Daz world space
#   bmat = Blender bone rest matrix, in Blender world space
#   rotmat = Daz rotation matrix, in Daz local space
#   trans = Daz translation vector, in Daz world space
#   wmat = Full transformation matrix, in Daz world space
#   mat = Full transformation matrix, in Blender local space
#
#-------------------------------------------------------------

def setParent(context, ob, rig, bname=None, update=True):
    if update:
        updateScene(context)
    if ob.parent != rig:
        wmat = ob.matrix_world.copy()
        ob.parent = rig
        if bname:
            ob.parent_bone = bname
            ob.parent_type = 'BONE'
        else:
            ob.parent_type = 'OBJECT'
        setWorldMatrix(ob, wmat)


def reParent(context, ob, rig):
    if ob.parent_type == 'BONE':
        bname = ob.parent_bone
    else:
        bname = None
    setParent(context, ob, rig, bname, False)


def clearParent(ob):
    wmat = ob.matrix_world.copy()
    ob.parent = None
    setWorldMatrix(ob, wmat)


def getTransformMatrices(pb):
    dmat = Euler(Vector(pb.bone.DazOrient)*D, 'XYZ').to_matrix().to_4x4()
    dmat.col[3][0:3] = d2b00(pb.bone.DazHead)

    parbone = pb.bone.parent
    if parbone and parbone.DazAngle != 0:
        rmat = Matrix.Rotation(parbone.DazAngle, 4, parbone.DazNormal)
    else:
        rmat = Matrix()

    if GS.zup:
        bmat = Matrix.Rotation(-90*D, 4, 'X') @ pb.bone.matrix_local
    else:
        bmat = pb.bone.matrix_local

    return dmat,bmat,rmat


def getTransformMatrix(pb):
    dmat,bmat,rmat = getTransformMatrices(pb)
    tmat = dmat.inverted() @ bmat
    return tmat.to_3x3()


def getBoneMatrix(tfm, pb, test=False):
    from .transform import roundMatrix
    dmat,bmat,rmat = getTransformMatrices(pb)
    wmat = dmat @ tfm.getRotMat(pb) @ tfm.getScaleMat() @ dmat.inverted()
    wmat = rmat.inverted() @ tfm.getTransMat() @ rmat @ wmat
    mat = bmat.inverted() @ wmat @ bmat
    roundMatrix(mat, 1e-4)

    if test:
        print("GGT", pb.name)
        print("D", dmat)
        print("B", bmat)
        print("R", tfm.rotmat)
        print("RR", rmat)
        print("W", wmat)
        print("M", mat)
    return mat


def setBoneTransform(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    if tfm.trans is None or tfm.trans.length == 0.0:
        mat.col[3] = (0,0,0,1)
    if tfm.hasNoScale():
        trans = mat.col[3].copy()
        mat = mat.to_quaternion().to_matrix().to_4x4()
        mat.col[3] = trans
    pb.matrix_basis = mat


def setBoneTwist(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    _,quat,_ = mat.decompose()
    euler = pb.matrix_basis.to_3x3().to_euler('YZX')
    euler.y += quat.to_euler('YZX').y
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = euler.to_quaternion()
    else:
        pb.rotation_euler = euler


def isUnitMatrix(mat):
    diff = mat - Matrix()
    maxelt = max([abs(diff[i][j]) for i in range(3) for j in range(4)])
    return (maxelt < 0.01*LS.scale)  # Ignore shifts < 0.1 mm


