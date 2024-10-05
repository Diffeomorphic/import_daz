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
import bmesh
import math
import numpy as np
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
    type = struct.get("type", None)
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
        Channels.__init__(self)
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
        self.inherits_scale = node.inherits_scale
        node.inherits_scale = True
        if "parent" in struct.keys() and node.parent is not None:
            self.parent = node.parent.getInstance(struct["parent"], node.caller)
            if self.parent == self:
                print("Self-parent", self)
                self.parent = None
            if self.parent:
                self.parent.children[self.id] = self
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
        self.nodeExtra = node.nodeExtra
        node.nodeExtra = {}
        self.channels = node.channels
        node.channels = {}
        self.isShell = False
        self.center = Vector((0,0,0))
        self.cpoint = Vector((0,0,0))
        self.wmat = self.wrot = self.wscale = Matrix()
        self.wtrans = Vector((0,0,0))
        self.lscale = Matrix()
        self.refcoll = None
        self.isGroupNode = False
        self.rigidFollow = None
        self.followTarget = None
        self.isStrandHair = False
        self.ignore = False
        self.instanceTarget = None
        self.instances = []
        self.shellNode = None
        self.hdobject = None
        #self.modifiers = {}
        self.attributes = copyElements(node.attributes)
        self.restdata = None
        self.mappingNode = None
        self.wsmat = self.U3
        self.lsmat = None
        self.rigtype = node.rigtype
        node.clearTransforms()
        SimNode.__init__(self)


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        return "<Instance %s L:%s %d N: %s P: %s R: %s>" % (self.id, self.label, self.index, self.node.name, pname, self.rna)

    def errorWrite(self, ref, fp):
        fp.write('  "%s": %s\n' % (ref, self))
        for geonode in self.geometries:
            geonode.errorWrite("     ", fp)

    def getSelfId(self):
        return self.id

    def getRig(self):
        return None

    def getNodeId(self):
        return unquote(self.node.id.rsplit("#", 1)[-1])

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
        for key,channel in self.channels.items():
            if key == "Instance Target":
                target = self.instanceTarget = self.getChannelInstance(channel)
                if target:
                    target.instances.append(self)
            elif key == "Shell Node":
                self.shellNode = self.getChannelInstance(channel)
            elif key == "Visible" and GS.ignoreHiddenObjects:
                self.ignore = (not getCurrentValue(channel))
            elif "type" not in channel.keys():
                continue
            elif channel["type"] == "bool":
                words = channel["id"].split("_")
                if len(words) > 2 and words[1] == "group" and words[-1] == "vis":
                    if words[0] == "material":
                        if "label" in channel.keys():
                            label = channel["label"]
                        else:
                            label = words[2]
                        value = getCurrentValue(channel)
                        for geonode in self.geometries:
                            geonode.data.material_group_vis[label] = value
                    elif words[0] == "facet":
                        pass

        for extra in self.extra:
            etype = extra.get("type")
            if etype == None:
                continue
            elif etype == "studio/node/shell":
                self.isShell = True
            elif etype == "studio/node/group_node":
                self.isGroupNode = True
            #elif etype == "studio/node/instance":
            #    self.isNodeInstance = True
            #elif etype == "studio/node/group_instance":
            #    self.isGroupInstance = True
            elif etype == "studio/node/strand_hair":
                self.isStrandHair = True
                for geonode in self.geometries:
                    geonode.isStrandHair = True
            elif etype == "studio/node/rigid_follow":
                self.rigidFollow = extra
            elif etype == "studio/node/environment":
                self.ignore = True
            elif etype == "studio/node/tone_mapper":
                self.ignore = True
            elif etype == "studio/scene_data/iray_decal":
                if self.parent:
                    parent = self.parent
                    geos = parent.geometries
                    while not geos and parent.parent:
                        parent = parent.parent
                        geos = parent.geometries
                    for geo in geos:
                        for dmat in geo.materials.values():
                            dmat.decals.append(self)

        self.updateMatrices()
        for geonode in self.geometries:
            geonode.preprocess(context, self)


    def getChannelInstance(self, channel):
        if "node" in channel.keys():
            ref = channel["node"]
            node = self.getAsset(ref)
            if node:
                return node.getInstance(ref)
        return None


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
            elif key == "Follow Target":
                self.followTarget = self.getChannelInstance(channel)


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
        from .cycles import findTexco
        self.parentObject(context, self.rna)
        for geonode in self.geometries:
            geonode.postbuild(context, self)
        if GS.useInstancing:
            self.buildNodeInstance(context)
        if self.mappingNode:
            x = self.getValue(["ClippingWidth"], 50)
            y = self.getValue(["ClippingDepth"], 50)
            z = self.getValue(["ClippingHeight"], 50)
            diag = 2*GS.scale*Matrix.Diagonal((x,y,z))
            texco = findTexco(self.mappingNode)
            empty = texco.object = self.rna
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 0.25
            empty.scale = diag@empty.scale


    def getRefColl(self, context):
        if self.refcoll:
            return self.refcoll
        ob = self.rna
        obname = ob.name

        if LS.refColl is None:
            LS.refColl = bpy.data.collections.new(name = "%s REFS" % LS.collection.name)
            LS.collection.children.link(LS.refColl)
        self.refcoll = bpy.data.collections.new(name = obname)
        LS.refColl.children.link(self.refcoll)
        if not isinstance(ob, bpy.types.Object):
            print("Trying to instance %s" % ob)
            return self.refcoll
        ob.name = "%s REF" % obname
        empty = bpy.data.objects.new(obname, None)
        empty.instance_type = 'COLLECTION'
        empty.instance_collection = self.refcoll
        LS.collection.objects.link(empty)
        LS.refObjects[ob.name] = (self, empty, self.refcoll)
        unlinkAll(ob, False)
        self.refcoll.objects.link(ob)
        return self.refcoll


    def linkRefChildren(self, refcoll, parent, context, wmats):
        for geonode in self.geometries:
            ob = geonode.rna
            if ob:
                unlinkAll(ob, False)
                refcoll.objects.link(ob)
        for child in self.children.values():
            ob = child.rna
            if isinstance(ob, bpy.types.PoseBone):
                wmats[ob.name] = ob.matrix.copy()
            elif isinstance(ob, bpy.types.Object):
                wmats[ob.name] = ob.matrix_world.copy()
            else:
                print("Ref Child not an object:\nP:%s\nS:%s\nC:%s" % (self.parent, self, child))
                continue
            if child.instanceTarget:
                coll = child.instanceTarget.getRefColl(context)
                child.linkRefChildren(coll, ob, context, wmats)
            elif ob:
                if ob.name in LS.refObjects.keys():
                    empty0 = LS.refObjects[ob.name][1]
                    empty = bpy.data.objects.new(empty0.name, None)
                    empty.instance_type = 'COLLECTION'
                    empty.instance_collection = empty0.instance_collection
                    refcoll.objects.link(empty)
                    wmats[empty.name] = ob.matrix_world.copy()
                    empty.parent = ob.parent
                    empty.parent_type = ob.parent_type
                elif child.hasInstanceChildren(refcoll):
                    if GS.verbosity >= 3:
                        print('Warning: "%s" has instance children' % ob.name)
                    LS.hasInstanceChildren[ob.name] = True
                elif isinstance(ob, bpy.types.PoseBone):
                    rig = ob.id_data
                    unlinkAll(rig, False)
                    refcoll.objects.link(rig)
                    child.linkRefChildren(refcoll, rig, context, wmats)
                else:
                    unlinkAll(ob, False)
                    refcoll.objects.link(ob)
                    child.linkRefChildren(refcoll, ob, context, wmats)


    def hasInstanceChildren(self, refcoll):
        if self.instanceTarget and self.instanceTarget.name == refcoll.name:
            if GS.verbosity >= 3:
                print('"%s" is an instance of "%s"' % (self.name, refcoll.name))
            return True
        for child in self.children.values():
            if child.hasInstanceChildren(refcoll):
                return True
        return False


    def refersTo(self, target):
        if self.instanceTarget:
            return (self.instanceTarget.id == target.id)
        else:
            for child in self.children.values():
                if child.refersTo(target):
                    return True
        return False


    def buildNodeInstance(self, context):
        if not self.instanceTarget:
            return
        items = self.nodeExtra.get("instance_items")
        coll = self.instanceTarget.getRefColl(context)
        empty = self.rna
        if empty is None:
            return
        if empty.name in coll.objects:
            print("Unlink '%s' from '%s'" % (empty.name, coll.name))
            coll.objects.unlink(empty)
        if items is None:
            empty.instance_type = 'COLLECTION'
            empty.instance_collection = coll
        else:
            for item in items:
                if item["label"]:
                    ename = item["label"]
                else:
                    ename = item["name"]
                emptyi = bpy.data.objects.new(ename, None)
                emptyi.parent = empty
                emptyi.rotation_mode = empty.rotation_mode
                LS.collection.objects.link(emptyi)
                emptyi.instance_type = 'COLLECTION'
                emptyi.instance_collection = coll
                mats = self.calcMatrices(item, self)
                wmat = mats[0]
                setWorldMatrix(emptyi, wmat)


    def poseRig(self, context):
        pass


    def finalize(self, context):
        ob = self.rna
        if ob is None:
            return
        for geonode in self.geometries:
            geonode.finalize(context, self)
        self.buildChannels(ob)

        target = None
        if self.followTarget:
            target = self.followTarget
        elif self.rigidFollow:
            from .bone import BoneInstance
            target = self.parent
            if isinstance(target, BoneInstance):
                target = target.figure

        def addFollower(target):
            mesh = target.geometries[0].rna
            if mesh and mesh.type == 'MESH':
                vcount = self.nodeExtra.get("vertex_count", -1)
                if len(mesh.data.vertices) != vcount and vcount >= 0:
                    print("Vertex count mismatch", mesh.name, vcount, len(mesh.data.vertices))
                    return
                riggrp = self.nodeExtra.get("rigidity_group")
                if riggrp:
                    refverts = riggrp.get("reference_vertices", {}).get("values", [])
                else:
                    refverts = []
                nverts = len(refverts)
                if nverts < 3:
                    refverts = []
                elif nverts > 3:
                    refverts = [refverts[0], refverts[nverts//2], refverts[-1]]
                follows = LS.rigidFollow.get(mesh.name)
                if follows is None:
                    follows = LS.rigidFollow[mesh.name] = (target, mesh, [])
                follows[2].append((ob, refverts))

        if target and target.geometries:
            addFollower(target)

        if self.dynsim:
            self.dynsim.build(context)
        if self.dyngenhair:
            self.dyngenhair.build(context)
        if self.dynhairflw:
            self.dynhairflw.build(context)


    def makeRigidFollow(self, context, mesh, data):
        if not data:
            return
        objects = [ob for ob,refverts in data]
        hides = unhide(objects)
        if activateObject(context, objects[0]):
            for ob in objects:
                ob.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        if activateObject(context, mesh):
            for ob,refverts in data:
                ob.select_set(True)
                if not refverts:
                    print("No refverts", ob.name, mesh.name)
                    bpy.ops.object.parent_set(type='VERTEX_TRI')
                else:
                    setMode('EDIT')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bm = bmesh.from_edit_mesh(mesh.data)
                    bm.verts.ensure_lookup_table()
                    for vn in refverts:
                        bm.verts[vn].select = True
                    bmesh.update_edit_mesh(mesh.data)
                    bm.free()
                    bpy.ops.object.vertex_parent_set()
                    setMode('OBJECT')
                ob.select_set(False)
        rehide(hides)

    def formulate(self, key, value):
        pass


    def updateMatrices(self):
        self.worldmat, self.wtrans, self.wrot, self.wscale, self.wmat, self.cpoint = self.calcMatrices(self.attributes, self.parent)


    def calcMatrices(self, attributes, parent):
        # From http://docs.daz3d.com/doku.php/public/dson_spec/object_definitions/node/start
        #
        # center_offset = center_point - parent.center_point
        # global_translation = parent.global_transform * (center_offset + translation)
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        # global_scale for nodes that inherit scale = parent.global_scale * orientation * scale * general_scale * (orientation)-1
        # global_scale for nodes = parent.global_scale * (parent.local_scale)-1 * orientation * scale * general_scale * (orientation)-1
        # global_transform = global_translation * global_rotation * global_scale

        from .bone import BoneInstance
        if self.rigidFollow and self.restdata:
            trans = d2b00(self.restdata.head)
            if parent:
                if parent.restdata:
                    trans -= d2b00(parent.restdata.head)
                else:
                    trans -= d2b00(parent.attributes["translation"])
        else:
            trans = d2b00(attributes["translation"])
        cpoint = d2b00(attributes["center_point"])
        rot = Vector(attributes["rotation"])*D
        gen = attributes["general_scale"]
        scale = Vector(attributes["scale"]) * gen
        orient = Vector(attributes["orientation"])*D

        lrot = Euler(rot, self.rotation_order).to_matrix().to_4x4()
        self.lscale = Matrix.Diagonal(scale).to_4x4()
        ormat = Euler(orient).to_matrix().to_4x4()

        if parent:
            coffset = cpoint - parent.cpoint
            wtrans = parent.wmat @ (coffset + trans)
            wrot = parent.wrot @ ormat @ lrot @ ormat.inverted()
            oscale = ormat @ self.lscale @ ormat.inverted()
            if self.inherits_scale:
                wscale = parent.wscale @ oscale
            else:
                try:
                    pscaleinv = parent.lscale.inverted()
                except ValueError:
                    pscaleinv = Matrix()
                wscale = parent.wscale @ pscaleinv @ oscale
        else:
            wtrans = cpoint + trans
            wrot = ormat @ lrot @ ormat.inverted()
            wscale = ormat @ self.lscale @ ormat.inverted()

        transmat = Matrix.Translation(wtrans)
        wmat = transmat @ wrot @ wscale
        if GS.zup:
            worldmat = self.RXP @ wmat @ self.RXN
        else:
            worldmat = wmat

        return worldmat, wtrans, wrot, wscale, wmat, cpoint


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
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        elif isinstance(self.parent, BoneInstance):
            if self.parent.figure is None:
                print("No figure found:", self.parent)
                return
            rig = self.parent.figure.rna
            ob.parent = rig
            if rig and rig.type == 'ARMATURE':
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
#   Collection utilities
#-------------------------------------------------------------

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


def createHiddenCollection(context, ob):
    parcoll = getCollection(context, ob)
    for coll in parcoll.children:
        if baseName(coll.name) == "Hidden":
            return coll
    coll = bpy.data.collections.new(name="Hidden")
    coll.hide_viewport = coll.hide_render = True
    parcoll.children.link(coll)
    layer = getLayerCollection(context, coll)
    if layer:
        layer.exclude = True
    return coll

#-------------------------------------------------------------
#   Final pass for node instances
#-------------------------------------------------------------

def finishNodeInstances(context):
    wmats = {}
    for inst,empty,refcoll in list(LS.refObjects.values()):
        ob = inst.rna
        wmats[empty.name] = ob.matrix_world.copy()
        inst.linkRefChildren(refcoll, inst.rna, context, wmats)

    for inst,empty,refcoll in LS.refObjects.values():
        ob = inst.rna
        empty.parent = ob.parent
        empty.parent_type = ob.parent_type
        ob.parent = None
        for child in ob.children:
            if child.name not in refcoll.objects:
                child.parent = empty

    unit = Matrix()
    for inst,empty,refcoll in LS.refObjects.values():
        ob = inst.rna
        setWorldMatrix(ob, unit)
        setWorldMatrix(empty, wmats[empty.name])
        for child in empty.children:
            if (child.name not in refcoll.objects and
                child.name in wmats.keys()):
                setWorldMatrix(child, wmats[child.name])

    for inst,empty,refcoll in LS.refObjects.values():
        inst.rna = empty

    if LS.refColl:
        layer = getLayerCollection(context, LS.refColl)
        layer.exclude = True
        for child in layer.children:
            child.exclude = True

#-------------------------------------------------------------
#   Node
#-------------------------------------------------------------

class Node(Asset, Formula, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Formula.__init__(self)
        Channels.__init__(self)
        self.instances = {}
        self.ninstances = 0
        self.count = 0
        self.data = None
        self.center = None
        self.geometries = []
        self.rotation_order = 'XYZ'
        self.inherits_scale = True
        self.attributes = self.defaultAttributes()
        self.origAttrs = self.defaultAttributes()
        self.figure = None
        self.rigtype = ""
        self.nodeExtra = {}


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
        return ("<Node %s %s %s>" % (self.id, self.label, self.instances.keys()))


    def errorWrite(self, ref, fp):
        Asset.errorWrite(self, ref, fp)
        for iref,inst in self.instances.items():
            inst.errorWrite(iref, fp)


    def postTransform(self):
        pass


    def makeInstance(self, fileref, struct):
        return Instance(fileref, self, struct)


    def getInstance(self, ref, caller=None):
        def getSelfInstance(ref, instances):
            iref = instRef(ref)
            if iref in instances.keys():
                return instances[iref]
            iref = unquote(iref)
            return instances.get(iref)

        if caller is None:
            caller = self
        iref = getSelfInstance(ref, caller.instances)
        if iref:
            return iref
        if caller.sourcing:
            iref = getSelfInstance(ref, caller.sourcing.instances)
            if iref:
                return iref
        msg = ("Node: Did not find instance %s in %s" % (instRef(ref), caller))
        reportError(msg, caller.instances)
        return None


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)

        for key,data in struct.items():
            if key == "formulas":
                self.formulas = data
            elif key == "inherits_scale":
                self.inherits_scale = data
            elif key == "rotation_order":
                self.rotation_order = data
            elif key in self.attributes.keys():
                self.setAttribute(key, data)

        for key in self.attributes.keys():
            self.origAttrs[key] = self.attributes[key]
        return self


    def setExtra(self, extra):
        for key,value in extra.items():
            if key in ["instance_items", "vertex_count", "rigidity_group"]:
                self.nodeExtra[key] = extra[key]


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
        from .geometry import GeoNode, Geometry, UnGeometry
        Asset.update(self, struct)
        Channels.update(self, struct)
        for channel,data in struct.items():
            if channel == "geometries":
                for geostruct in data:
                    etype = None
                    if "url" in geostruct.keys():
                        geo = self.parseUrlAsset(geostruct, Geometry)
                        geonode = GeoNode(self, geo, geostruct["id"], etype)
                    else:
                        extra = geostruct.get("extra")
                        if extra:
                            etype = extra[0].get("type")
                        if etype in ["studio_geometry_channels"]:
                            geo = UnGeometry(etype, self.fileref)
                            geo.parse(geostruct)
                        else:
                            print("No geometry URL")
                            geo = None
                        geonode = GeoNode(self, geo, geostruct["id"], etype)
                        self.saveAsset(geostruct, geonode)
                    geonode.parse(geostruct)
                    geonode.update(geostruct)
                    geonode.extra = self.extra
                    geonode.conform_target = struct.get("conform_target")
                    self.geometries.append(geonode)
            elif channel in self.attributes.keys():
                self.setAttribute(channel, data)
        if (LS.useMorph or LS.onLoadBaked) and "preview" in struct.keys():
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
        from .geometry import UnGeometry
        if GS.verbosity >= 4:
            print("Build object %s" % self.name)
        scn = context.scene
        ob2 = None
        obname = self.getObjectName(inst)
        if isinstance(self.data, UnGeometry):
            ob = bpy.data.objects.new(obname, None)
            self.data.fixMappingNodes(inst)
        elif isinstance(self.data, Asset):
            if self.data.isShell and GS.shellMethod == 'MATERIAL':
                return
            ob,ob2 = self.data.buildData(context, self, inst, center)
            if not isinstance(ob, bpy.types.Object):
                ob = bpy.data.objects.new(obname, self.data.rna)
        else:
            ob = bpy.data.objects.new(obname, self.data)
        self.rna = inst.rna = ob
        ob.empty_display_size = 10*GS.scale
        LS.objects[LS.rigname].append(ob)
        self.arrangeObject(ob, inst, context, center)
        self.subdivideObject(ob, inst, context)
        if ob2:
            LS.objects[LS.rigname].append(ob2)
            self.arrangeObject(ob2, inst, context, center)
            ob2.parent = ob
            ob2.empty_display_size = 10*GS.scale


    def getObjectName(self, inst):
        return noHDName(inst.name)


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
        LS.collection.objects.link(ob)
        if LS.hdcollection and ob.type != 'MESH':
            LS.hdcollection.link(ob)
        ob.DazId = self.id
        ob.DazUrl = unquote(self.url)
        ob.DazScene = LS.scene
        ob.DazScale = GS.scale
        ob.DazOrient = inst.attributes["orientation"]
        ob.DazCenter = inst.attributes["center_point"]
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


def getDazMatrix(bone):
    dmat = Euler(Vector(bone.DazOrient)*D, 'XYZ').to_matrix().to_4x4()
    dmat.col[3][0:3] = d2b00(bone.DazHead)
    return dmat


def getBlenderMatrix(bone):
    if GS.zup:
        return Matrix.Rotation(-90*D, 4, 'X') @ bone.matrix_local
    else:
        return bone.matrix_local


def getTransformMatrices(pb, rig, bonemap):
    def getParent(pb):
        for cns in pb.constraints:
            if (cns.type == 'COPY_TRANSFORMS' and
                cns.influence == 1 and
                not cns.mute):
                pb2 = rig.pose.bones.get(cns.subtarget)
                if pb2 and pb2 != pb:
                    return getParent(pb2)
        if pb.parent:
            if pb.parent.name in bonemap.values():
                return pb.parent
            else:
                return getParent(pb.parent)
        return pb.parent

    dmat = getDazMatrix(pb.bone)
    bmat = getBlenderMatrix(pb.bone)
    if bonemap:
        parent = getParent(pb)
    else:
        parent = pb.parent
    if parent:
        rmat = Matrix.Rotation(parent.bone.DazAngle, 4, parent.bone.DazNormal)
    else:
        rmat = Matrix()
    return dmat,bmat,rmat,parent


def getTransformMatrix(pb, rig):
    dmat,bmat,rmat,parent = getTransformMatrices(pb, rig, {})
    tmat = dmat.inverted() @ bmat
    return tmat.to_3x3()


def getBoneMatrix(tfm, pb, rig, bonemap={}):
    from .transform import roundMatrix
    dmat,bmat,rmat,parent = getTransformMatrices(pb, rig, bonemap)
    rotmat = tfm.getRotMat(pb)
    wmat = dmat @ rotmat @ tfm.getScaleMat() @ dmat.inverted()
    tmat = rmat.inverted() @ tfm.getTransMat() @ rmat
    mat = bmat.inverted() @ tmat @ wmat @ bmat
    roundMatrix(mat, 1e-4)
    return mat


TestBones = []

def getAngle(mat, xyz):
    return Vector(mat.to_euler(xyz))/D


def setBoneTransform(tfm, pb, rig, oldStyle=False, bonemap={}):
    mat = getBoneMatrix(tfm, pb, rig, bonemap)
    if tfm.trans is None or tfm.trans.length == 0.0:
        mat.col[3] = (0,0,0,1)
    if tfm.hasNoScale():
        trans = mat.col[3].copy()
        mat = mat.to_quaternion().to_matrix().to_4x4()
        mat.col[3] = trans
    if pb.name in TestBones:
        print("SBT", pb.name, tfm.rot)
        print("ROT", getAngle(tfm.getRotMat(pb), pb.DazRotMode))
        print("BBB", getAngle(mat, pb.rotation_mode))
        print(mat)
    pb.matrix_basis = mat


def flipAxes(vec, pb):
    fvec = Vector((0,0,0))
    for idx in range(3):
        idx2 = pb.DazAxes[idx]
        fvec[idx2] = pb.DazFlips[idx] * vec[idx]
    return fvec


def isUnitMatrix(mat):
    diff = mat - Matrix()
    maxelt = max([abs(diff[i][j]) for i in range(3) for j in range(4)])
    return (maxelt < 0.01*GS.scale)  # Ignore shifts < 0.1 mm


