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
import collections
import os

from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .formula import Formula

#-------------------------------------------------------------
#   External access
#-------------------------------------------------------------

def parseModifierAsset(asset, struct):
    if "skin" in struct.keys():
        return asset.parseTypedAsset(struct, SkinBinding)
    elif "legacy_skin" in struct.keys():
        return asset.parseTypedAsset(struct, LegacySkinBinding)
    elif "morph" in struct.keys():
        return asset.parseTypedAsset(struct, Morph)
    elif "formulas" in struct.keys():
        return asset.parseTypedAsset(struct, FormulaAsset)
    elif "dform" in struct.keys():
        return asset.parseTypedAsset(struct, DForm)
    elif "extra" in struct.keys():
        return asset.parseTypedAsset(struct, ExtraAsset)
    elif "channel" in struct.keys():
        return parseChannelAsset(asset, struct)
    else:
        #print("WARNING: Modifier asset %s not implemented" % asset.fileref)
        #asset = Modifier(asset.fileref)
        raise NotImplementedError("Modifier asset not implemented in file %s:\n  %s" %
            (asset.fileref, list(struct.keys())))


def parseChannelAsset(asset, struct):
    channel = struct["channel"]
    if channel["type"] == "alias":
        return asset.parseTypedAsset(struct, Alias)
    else:
        return asset.parseTypedAsset(struct, ChannelAsset)


def parseMorph(asset, struct, multi):
    morphs = []
    if "modifier_library" in struct.keys():
        for mstruct in struct["modifier_library"]:
            if "morph" in mstruct.keys():
                morph = asset.parseTypedAsset(mstruct, Morph)
            elif "formulas" in mstruct.keys():
                morph = asset.parseTypedAsset(mstruct, FormulaAsset)
            elif "channel" in mstruct.keys():
                morph = parseChannelAsset(asset, mstruct)
            else:
                continue
            if multi:
                morphs.append(morph)
            else:
                return morph
    if multi:
        return morphs

#-------------------------------------------------------------
#   Modifier Assets
#-------------------------------------------------------------

class Modifier(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.groups = []


    def parse(self, struct):
        Asset.parse(self, struct)
        if "groups" in struct.keys():
            self.groups = struct["groups"]


    def update(self, struct):
        Asset.update(self, struct)
        if "groups" in struct.keys():
            self.groups = struct["groups"]


    def __repr__(self):
        return ("<Modifier %s>" % (self.id))


    def preprocess(self, inst):
        pass


    def postbuild(self, context, inst):
        pass


    def getGeoRig(self, context, inst):
        from .geometry import GeoNode
        from .figure import FigureInstance
        if isinstance(inst, GeoNode):
            # This happens for normal scenes
            ob = inst.rna
            if ob:
                rig = ob.parent
            else:
                rig = None
            return ob, inst.hdobject, rig, inst
        elif isinstance(inst, FigureInstance):
            # This happens for library characters
            rig = inst.rna
            if inst.geometries:
                geonode = inst.geometries[0]
                ob = geonode.rna
            else:
                ob = geonode = None
            return ob, geonode.hdobject, rig, geonode
        else:
            msg = ("Expected geonode or figure but got:\n  %s" % inst)
            reportError(msg)
            return None,None,None,None

#-------------------------------------------------------------
#   DForm
#-------------------------------------------------------------

class DForm(Modifier):
    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.parent = None
        self.dform = {}


    def __repr__(self):
        return ("<Dform %s>" % (self.id))


    def parse(self, struct):
        Modifier.parse(self, struct)
        self.dform = struct["dform"]
        self.parent = self.getAsset(struct["parent"])


    def update(self, struct):
        Modifier.update(self, struct)


    def build(self, context, inst):
        ob,hdob,rig,geonode = self.getGeoRig(context, inst)
        if ob is None or ob.type != 'MESH':
            return
        if ("influence_vertex_count" in self.dform.keys() and
            "influence_weights"  in self.dform.keys()):
            vcount = self.dform["influence_vertex_count"]
            if vcount != len(ob.data.vertices) and vcount >= 0:
                msg = "Dform vertex count mismatch %d != %d" % (vcount, len(ob.data.vertices))
                reportError(msg)
            vgrp = ob.vertex_groups.new(name = "Dform " + self.name)
            for vn,w in self.dform["influence_weights"]["values"]:
                vgrp.add([vn], w, 'REPLACE')
        elif "mask_bone" in self.dform.keys():
            pass
        else:
            print("DFORM", self.dform.keys())

#-------------------------------------------------------------
#   Extra
#-------------------------------------------------------------

class ExtraAsset(Modifier, Channels):
    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        Channels.__init__(self)
        self.extras = {}
        self.type = None


    def __repr__(self):
        return ("<Extra %s %s p: %s>" % (self.id, list(self.extras.keys()), self.parent))


    def parse(self, struct):
        Modifier.parse(self, struct)
        Channels.parse(self, struct)
        extras = struct["extra"]
        if not isinstance(extras, list):
            extras = [extras]
        for extra in extras:
            if "type" in extra.keys():
                etype = extra["type"]
                self.extras[etype] = extra


    def update(self, struct):
        Modifier.update(self, struct)
        Channels.update(self, struct)
        if "extra" not in struct.keys():
            return
        extras = struct["extra"]
        if not isinstance(extras, list):
            extras = [extras]
        for extra in extras:
            if "type" in extra.keys():
                etype = extra["type"]
                if etype in self.extras.keys():
                    for key,value in extra.items():
                        self.extras[etype][key] = value
                else:
                    self.extras[etype] = extra


    def preprocess(self, inst):
        geonode = self.getGeoNode(inst)
        if geonode is None:
            return
        if "studio_modifier_channels" in self.extras.keys():
            #geonode.modifiers[self.name] = self
            modchannels = self.extras["studio_modifier_channels"]
            for cstruct in modchannels["channels"]:
                channel = cstruct["channel"]
                self.setChannel(channel)
        if "studio/modifier/push" in self.extras.keys():
            geonode.push = self.getValue(["Value"], 0)


    def build(self, context, inst):
        if inst is None:
            return
        for etype,extra in self.extras.items():
            #print("EE '%s' '%s' %s %s" % (inst.name, self.name, self.parent, etype))
            if etype == "studio/modifier/dynamic_generate_hair":
                from .dforce import DynGenHair
                inst.dyngenhair = DynGenHair(inst, self, extra)
            elif etype == "studio/modifier/dynamic_simulation":
                from .dforce import DynSim
                inst.dynsim = DynSim(inst, self, extra)
            elif etype == "studio/modifier/dynamic_hair_follow":
                from .dforce import DynHairFlw
                inst.dynhairflw = DynHairFlw(inst, self, extra)
            elif etype == "studio/modifier/line_tessellation":
                from .dforce import LinTess
                inst.lintess = LinTess(inst, self, extra)
            elif etype == "studio/simulation_settings/dynamic_simulation":
                from .dforce import SimSet
                simset = SimSet(inst, self, extra)
                inst.simsets.append(simset)
            elif etype == "studio/node/dform":
                print("DFORM", self)


    def getGeoNode(self, inst):
        from .node import Instance
        from .geometry import GeoNode
        if isinstance(inst, Instance):
            if inst.geometries:
                return inst.geometries[0]
            else:
                return None
        elif isinstance(inst, GeoNode):
            return inst
        else:
            return None

#-------------------------------------------------------------
#   ChannelAsset
#-------------------------------------------------------------

class ChannelAsset(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.type = "float"
        self.value = 0
        self.min = None
        self.max = None

    def __repr__(self):
        return ("<Channel %s %s %s>" % (self.id, self.type, self.value))

    def parse(self, struct):
        Modifier.parse(self, struct)
        channels = struct.get("channel", {})
        for key,value in channels.items():
            if key == "value":
                self.value = value
            elif key == "min":
                self.min = value
            elif key == "max":
                self.max = value
            elif key == "type":
                self.type = value
        if "current_value" in channels.keys():
            self.value = channels["current_value"]


    def update(self, struct):
        Modifier.update(self, struct)
        channels = struct.get("channel", {})
        if "current_value" in channels.keys():
            self.value = channels["current_value"]


def stripPrefix(prop):
    lprop = prop.lower()
    for prefix in [
        "ectrlv", "ectrl", "pctrl", "ctrl",
        "phm", "ephm", "pbm", "ppbm", "vsm",
        "pjcm", "ejcm", "jcm", "mcm",
        "dzu", "dze", "dzv", "dzb", "facs_",
        ]:
        n = len(prefix)
        if lprop[0:n] == prefix:
            return prop[n:]
    return prop


def getCanonicalKey(key):
    #key = stripPrefix(key)
    lkey = key.lower()
    if lkey[-5:] == "_div2":
        key = key[:-5]
        lkey = lkey[:-5]
    if lkey[-3:] == "_hd":
        key = key[:-3]
        lkey = lkey[:-3]
    if lkey[-2:] == "hd":
        key = key[:-2]
        lkey = lkey[:-2]
    if lkey[-4:-1] == "_hd":
        key = key[:-4] + key[-1]
        lkey = lkey[:-4] + lkey[-1]
    if lkey[-3:-1] == "hd":
        key = key[:-3] + key[-1]
        lkey = lkey[:-3] + lkey[-1]
    return key


class Alias(ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        self.target_channel = None
        self.parent = None
        self.min = 0.0
        self.max = 1.0

    def __repr__(self):
        return ("<Alias %s\n  %s\n  %s>" % (self.id, self.target_channel, self.parent))

    def parse(self, struct):
        ChannelAsset.parse(self, struct)
        channel = struct["channel"]
        self.parent = struct["parent"]
        self.target_channel = channel["target_channel"]

    def update(self, struct):
        ChannelAsset.update(self, struct)

    def build(self, context, inst):
        pass

    def getAlias(self):
        if self.target_channel:
            words = self.target_channel.rsplit("#",1)
            return words[-1].split("?")[0]
        else:
            return None

#-------------------------------------------------------------
#   Skin Binding
#-------------------------------------------------------------

class SkinBinding(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.parent = None
        self.skin = None
        self.hasTriax = False

    def __repr__(self):
        return ("<SkinBinding %s>" % (self.id))


    def parse(self, struct):
        from .geometry import Geometry
        from .figure import Figure
        Modifier.parse(self, struct)
        self.skin = struct["skin"]
        self.parent = self.getAsset(struct["parent"])
        if not (isinstance(self.parent, Geometry) or
                isinstance(self.parent, Figure)):
            msg = "Parent of %s\nshould be a geometry or a figure but is\n%s" % (self, self.parent)
            reportError(msg)


    def parseSource(self, url):
        asset = self.getAsset(url)
        if asset:
            if (self.parent is None or
                self.parent.type != asset.type):
                msg = ("SkinBinding source bug:\n" +
                       "URL: %s\n" % url +
                       "Skin: %s\n" % self +
                       "Asset: %s\n" % asset +
                       "Parent: %s\n" % self.parent)
                reportError(msg)
            if asset != self.parent:
                self.parent.source = asset
                asset.sourcing = self.parent
            LS.assets[url] = self.parent


    def build(self, context, inst):
        ob,hdob,rig,geonode = self.getGeoRig(context, inst)
        if ob is None or rig is None or ob.type != 'MESH':
            return
        if GS.verbosity >= 4:
            print("Build skinbinding %s" % self.name)

        makeArmatureModifier(self.name, context, ob, rig)
        self.addVertexGroups(ob, geonode, rig)
        hdob = geonode.hdobject
        if hdob and hdob != ob and hdob.data != ob.data and GS.useHDArmature:
            hdob.parent = ob.parent
            makeArmatureModifier(self.name, context, hdob, rig)
            if geonode.hdType == 'MULTIRES':
                ok,msg = copyVertexGroups(ob, hdob)
            else:
                ok = False
            if not ok:
                from .transfer import transferVertexGroups
                transferVertexGroups(context, ob, [hdob], 1e-3)


    Removes = {"genesis9" : ["l_upperarm", "r_upperarm"]}

    def addVertexGroups(self, ob, geonode, rig):
        for bone in rig.data.bones:
            bone.use_deform = False
        for joint in self.skin["joints"]:
            bname = joint["id"]
            if bname in geonode.figure.bones.keys():
                vgname = geonode.figure.bones[bname]
            else:
                vgname = bname

            weights = None
            if "node_weights" in joint.keys():
                weights = joint["node_weights"]
            elif "local_weights" in joint.keys():
                LS.triax[ob.name] = ob
                if GS.useTriaxImprove:
                    for comp in ["x", "y", "z"]:
                        lweights = joint["local_weights"].get(comp)
                        if lweights:
                            buildVertexGroup(ob, "%s:%s" % (vgname,comp), lweights["values"])
                            self.hasTriax = True
                else:
                    if bname in rig.data.bones.keys():
                        lweights = self.calcLocalWeights(bname, joint, rig)
                        weights = {"values": lweights}
                    else:
                        print("Local weights missing bone:", bname)
            elif "scale_weights" in joint.keys():
                weights = joint["scale_weights"]
            else:
                reportError("No weights for %s in %s" % (bname, ob.name), trigger=(3,5))
                continue
            if GS.useBulgeWeights:
                if "bulge_weights" in joint.keys():
                    for comp in ["x", "y", "z"]:
                        bweights = joint["bulge_weights"].get(comp, {})
                        if bweights:
                            pg = ob.data.DazBulges.add()
                            pg.name = "%s_%s" % (vgname, comp)
                            bvalues = {}
                            for bulge in bweights.get("bulges", []):
                                bid = bulge["id"].replace("-", "_")
                                setattr(pg, bid, bulge["value"])
                                bvalues[bid] =  bulge["value"]
                            left = bweights.get("left_map", {})
                            if left and (bvalues.get("positive_left") or bvalues.get("negative_left")):
                                buildVertexGroup(ob, "%s:left_%s" % (vgname,comp), left["values"])
                            right = bweights.get("right_map", {})
                            if right and (bvalues.get("positive_right") or bvalues.get("negative_right")):
                                buildVertexGroup(ob, "%s:right_%s" % (vgname,comp), right["values"])


            removes = self.Removes.get(rig.DazRig, [])
            if bname not in removes and weights:
                buildVertexGroup(ob, vgname, weights["values"])
                if bname in rig.data.bones.keys() and len(weights["values"]) > 0:
                    rig.data.bones[bname].use_deform = True



    def calcLocalWeights(self, bname, joint, rig):
        local_weights = joint["local_weights"]
        bone = rig.data.bones[bname]
        head = bone.head_local
        tail = bone.tail_local
        # find longitudinal axis of the bone and take the other two into consideration
        consider = []
        x_delta = abs(head[0] - tail[0])
        y_delta = abs(head[1] - tail[1])
        z_delta = abs(head[2] - tail[2])
        max_delta = max(x_delta, y_delta, z_delta)
        if x_delta < max_delta:
            consider.append("x")
        if y_delta < max_delta:
            consider.append("z")
        if z_delta < max_delta:
            consider.append("y")

        # create deques sorted in descending order
        weights = [collections.deque(local_weights[letter]["values"]) for letter in consider if
                   letter in local_weights]
        for w in weights:
            w.reverse()
        target = []
        calc_weights = []
        if len(weights) == 1:
            calc_weights = weights[0]
        elif len(weights) > 1:
            self.mergeWeights(weights[0], weights[1], target)
            calc_weights = target
        if len(weights) > 2:
            # this happens mostly with zero length bones
            calc_weights = []
            self.mergeWeights(target, weights[2], calc_weights)
        return calc_weights


    def mergeWeights(self, first, second, target):
        # merge the two local_weight groups and calculate arithmetic mean for vertices that are present in both groups
        while len(first) > 0 and len(second) > 0:
            a = first.pop()
            b = second.pop()
            if a[0] == b[0]:
                target.append([a[0], (a[1] + b[1]) / 2.0])
            elif a[0] < b[0]:
                target.append(a)
                second.append(b)
            else:
                target.append(b)
                first.append(a)
        while len(first) > 0:
            a = first.pop()
            target.append(a)
        while len(second) > 0:
            b = second.pop()
            target.append(b)


    TwistBones = {
        "lShldr" :  ("yxz", "YXZ", 'MUL'),
        "lForeArm" : ("yxz", "YZX", 'SET'),
        "lThigh" : ("xyz", "YZX", 'MUL'),
        "rShldr" :  ("yxz", "YXZ", 'MUL'),
        "rForeArm" : ("yxz", "YZX", 'SET'),
        "rThigh" : ("xyz", "YZX", 'MUL')
    }

    def postbuild(self, context, inst):
        from .mhx import deriveBone, copyRotation
        if not self.hasTriax or GS.keepTriaxWeights:
            return
        ob,hdob,rig,geonode = self.getGeoRig(context, inst)
        if ob is None or rig is None or ob.type != 'MESH':
            return
        twists = self.postTriax(context, ob, rig)
        if hdob:
            self.postTriax(context, hdob, rig)
        if activateObject(context, rig):
            print("Add triax twist bones: %s" % rig.name)
            setMode('EDIT')
            for bname in twists.keys():
                eb = rig.data.edit_bones[bname]
                twist = deriveBone("%s.twist" % bname, eb, rig, T_HIDDEN, eb.parent)
            setMode('OBJECT')
            for bname in twists.keys():
                data = self.TwistBones[bname]
                pb = rig.pose.bones[bname]
                twist = rig.pose.bones["%s.twist" % bname]
                twist.bone.use_deform = True
                twist.rotation_mode = data[1]
                cns = copyRotation(twist, pb, rig, space='LOCAL')
                setEulerOrder(cns, data[1])
                cns.use_y = False


    def postTriax(self, context, ob, rig):
        def getTriaxGroup(pb, m):
            return ob.vertex_groups.get("%s:%s" % (pb.name, chr(m+ord("x"))))

        def addWeightMix(ob, group_a, group_b, mix_mode):
            mod = ob.modifiers.new(group_a, 'VERTEX_WEIGHT_MIX')
            mod.vertex_group_a = group_a
            mod.vertex_group_b = group_b
            mod.mix_set = 'OR'
            mod.mix_mode = mix_mode
            mod.normalize = False
            return mod

        from .dforce import ModStore
        if not activateObject(context, ob):
            return
        stores = []
        multi = None
        for mod in list(ob.modifiers):
            if mod.type == 'MULTIRES':
                multi = mod
            else:
                stores.append(ModStore(mod))
                ob.modifiers.remove(mod)
        zgroups = []
        twists = {}
        for pb in rig.pose.bones:
            vgrp1 = vgrp2 = vgrp3 = None
            for m,n in enumerate(pb.DazAxes):
                if n == 0:
                    vgrp1 = getTriaxGroup(pb, m)
                elif n == 1:
                    vgrp2 = getTriaxGroup(pb, m)
                else:
                    vgrp3 = getTriaxGroup(pb, m)
            if vgrp1 or vgrp2 or vgrp3:
                pb.bone.use_deform = True
            else:
                continue
            data = self.TwistBones.get(pb.name)
            if data:
                if (vgrp1 or vgrp3) and vgrp2:
                    twists[pb.name] = True
                    twistname = "%s.twist" % pb.name
                    if vgrp1:
                        vgrp1.name = twistname
                    else:
                        vgrp3.name = twistname
                    vgrp2.name = pb.name
                elif vgrp1:
                    vgrp1.name = pb.name
                elif vgrp3:
                    vgrp3.name = pb.name
                elif vgrp2:
                    vgrp2.name = pb.name
            else:
                if vgrp1:
                    vgrp1.name = pb.name
                elif vgrp3:
                    vgrp3.name = pb.name
                if vgrp2:
                    zgroups.append(vgrp2.name)
            if vgrp1 and vgrp3:
                mod = addWeightMix(ob, vgrp1.name, vgrp3.name, 'AVG')
                if GS.useTriaxApply:
                    try:
                        zgroups.append(vgrp3.name)
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    except RuntimeError:
                        pass

        for bname in twists.keys():
            data = self.TwistBones[bname]
            mod = addWeightMix(ob, bname, "%s.twist" % bname, data[2])
            if GS.useTriaxApply:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    pass

        for bname,hname in [("lForeArm", "lHand"), ("rForeArm", "rHand")]:
            if not twists.get(bname):
                continue
            mod = ob.modifiers.new(bname, 'VERTEX_WEIGHT_MIX')
            mod.vertex_group_a = bname
            mod.vertex_group_b = "%s:x" % hname
            mod.mix_set = 'OR'
            mod.mix_mode = 'MUL'
            mod.normalize = False
            if GS.useTriaxApply:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    pass

        for store in stores:
            store.restore(ob)
        if multi:
            nmods = len(ob.modifiers)
        elif GS.useTriaxApply:
            for vgname in zgroups:
                vgrp = ob.vertex_groups.get(vgname)
                if vgrp:
                    ob.vertex_groups.remove(vgrp)
            print("Smooth triax weights: %s" % ob.name)
            setMode('WEIGHT_PAINT')
            bpy.ops.object.vertex_group_smooth(group_select_mode='ALL', factor=0.5, repeat=4, expand=0.0)
            setMode('OBJECT')
        return twists


def buildVertexGroup(ob, vgname, weights, default=None):
    if weights:
        if vgname in ob.vertex_groups.keys():
            print("Duplicate vertex group:\n  %s %s" % (ob.name, vgname))
            return ob.vertex_groups[vgname]
        else:
            vgrp = ob.vertex_groups.new(name=vgname)
        if default is None:
            for vn,w in weights:
                vgrp.add([vn], w, 'REPLACE')
        else:
            for vn in weights:
                vgrp.add([vn], default, 'REPLACE')
        return vgrp
    return None


def makeArmatureModifier(name, context, ob, rig):
    activateObject(context, ob)
    newArmatureModifier(name, ob, rig)
    ob.location = (0,0,0)
    ob.rotation_euler = (0,0,0)
    ob.scale = (1,1,1)
    ob.lock_location = TTrue
    ob.lock_rotation = TTrue
    ob.lock_scale = TTrue


def newArmatureModifier(name, ob, rig):
    mod = ob.modifiers.new("Armature %s" % name, "ARMATURE")
    mod.object = rig
    mod.use_deform_preserve_volume = True
    nmods = len(ob.modifiers)
    for n in range(nmods-1):
        bpy.ops.object.modifier_move_up(modifier=mod.name)


def copyVertexGroups(ob, hdob):
    def addVertexGroup(hdob, vgname, vnums):
        vgrp = hdob.vertex_groups.get(vgname)
        if vgrp:
            hdob.vertex_groups.remove(vgrp)
        vgrp = hdob.vertex_groups.new(name=vgname)
        for vn in vnums:
            vgrp.add([vn], 1.0, 'REPLACE')

    nverts = len(ob.data.vertices)
    nhdverts = len(hdob.data.vertices)
    if nverts != nhdverts:
        msg = ("%s => %s (%d != %d)" % (ob.name, hdob.name, nverts, nhdverts))
        return False, msg
    hdvgrps = {}
    for vgrp in ob.vertex_groups:
        hdvgrp = hdob.vertex_groups.new(name=vgrp.name)
        hdvgrps[vgrp.index] = hdvgrp
    for v in ob.data.vertices:
        vn = v.index
        for g in v.groups:
            hdvgrps[g.group].add([vn], g.weight, 'REPLACE')
    return True, ""


class LegacySkinBinding(SkinBinding):

    def __repr__(self):
        return ("<LegacySkinBinding %s %s>" % (self.id, self.getLabel()))

    def parse(self, struct):
        struct["skin"] = struct["legacy_skin"]
        SkinBinding.parse(self, struct)

    def build(self, context, inst):
        ob,hdob,rig,geonode = self.getGeoRig(context, inst)
        LS.legacySkin.append((ob, rig))
        SkinBinding.build(self, context, inst)

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class FormulaAsset(Formula, ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        Formula.__init__(self)
        self.group = ""
        self.parentRef = None


    def __repr__(self):
        return ("<Formula %s %f>" % (self.id, self.value))


    def parse(self, struct):
        Formula.parse(self, struct)
        ChannelAsset.parse(self, struct)
        if "group" in struct.keys():
            words = struct["group"].split("/")
            if (len(words) > 2 and
                words[0] == "" and
                words[1] == "Pose Controls"):
                self.group = words[2]
        if LS.useLoadBaked:
            LS.bakedmorphs[self.id] = self


    def getMorphParent(self):
        from .geometry import GeoNode, Geometry
        from .figure import Figure, FigureInstance
        from .node import Node, Instance
        msg = None
        if isinstance(self.parent, Geometry):
            parent = self.parent.nodes.get(self.parentRef)
            if parent:
                return parent
            else:
                msg = "Missing geonode %s" % self.parent.nodes.keys()
        elif isinstance(self.parent, GeoNode):
            return self.parent
        elif isinstance(self.parent, Figure):
            parent = self.parent.instances.get(self.parentRef)
            if parent:
                return parent
            else:
                msg = "Missing figure instances"
        elif isinstance(self.parent, FigureInstance):
            return self.parent
        elif isinstance(self.parent, Node):
            parent = self.parent.instances.get(self.parentRef)
            if parent:
                return parent
            else:
                msg = "Missing instances"
        else:
            msg = "Strange morph parent"
        msg = "%s: %s\n  %s\n  %s" % (msg, self.parentRef, self, self.parent)
        print(msg)
        return None


    def build(self, context, inst):
        if LS.useMorph:
            Formula.build(self, context, inst)


    def postbuild(self, context, inst):
        if LS.useMorphOnly:
            Formula.postbuild(self, context, inst)
        elif (LS.fitFile or LS.useMorph) and inst:
            self.buildBakedFormulas(context, inst)

#-------------------------------------------------------------
#   Morph
#-------------------------------------------------------------

class Morph(FormulaAsset):

    def __init__(self, fileref):
        FormulaAsset.__init__(self, fileref)
        self.vertex_count = 0
        self.deltas = []
        self.hd_url = None


    def __repr__(self):
        return ("<Morph %s %f %s>" % (self.name, self.value, self.url))


    def parse(self, struct):
        FormulaAsset.parse(self, struct)
        if not LS.useMorph:
            return
        morph = struct["morph"]
        if ("deltas" in morph.keys() and
            "values" in morph["deltas"].keys()):
            self.deltas = morph["deltas"]["values"]
        elif GS.verbosity > 2:
            print("Morph without deltas: %s" % self.name)
        if "vertex_count" in morph.keys():
            self.vertex_count = morph["vertex_count"]
        if "hd_url" in morph.keys():
            self.hd_url = morph["hd_url"]


    def parseSource(self, url):
        #print("Skip source", self)
        pass


    #def update(self, struct):
    #    FormulaAsset.update(self, struct)

    def build(self, context, inst, value=None):
        if not LS.useMorph:
            return self
        if len(self.deltas) == 0:
            if GS.verbosity > 2:
                print("Morph without deltas: %s" % self.name)
            return self
        Formula.build(self, context, inst)
        Modifier.build(self, context)

        from .geometry import GeoNode, Geometry
        from .figure import FigureInstance
        from .bone import BoneInstance

        if isinstance(inst, FigureInstance):
            geonodes = inst.geometries
        elif isinstance(inst, GeoNode):
            geonodes = [inst]
        elif isinstance(inst, BoneInstance):
            geonodes = inst.figure.geometries
        else:
            asset = self.getAsset(self.parent)
            print("BMO", inst)
            print("  ", asset)
            inst = None
            if asset:
                geonodes = list(asset.nodes.values())
                if len(geonodes) > 0:
                    inst = geonodes[0]

        if inst is None:
            msg = ("Morph not found:\n  %s\n  %s\n  %s" % (self.id, self.parent, asset))
            reportError(msg)
            return None

        for geonode in geonodes:
            ob = geonode.rna
            if value is not None:
                self.value = value
            if ob is None:
                continue
            elif LS.applyMorphs:
                self.addMorphToVerts(ob.data)
            else:
                skey = self.buildMorph(ob, strength=LS.morphStrength)
        return self


    def addMorphToVerts(self, me):
        if self.value == 0.0:
            return
        scale = self.value * GS.scale
        for delta in self.deltas:
            vn = delta[0]
            me.vertices[vn].co += scale * d2bu(delta[1:])


    def buildMorph(self, ob,
                   useBuild=True,
                   strength=1):

        def buildShapeKey(ob, skey, strength):
            #if strength != 1:
            #    scale = GS.scale
            #    GS.scale *= strength
            for v in ob.data.vertices:
                skey.data[v.index].co = v.co
            if GS.zup:
                if isModifiedMesh(ob):
                    pgs = ob.data.DazOrigVerts
                    for delta in self.deltas:
                        vn0 = delta[0]
                        vn = pgs[str(vn0)].a
                        if vn >= 0:
                            skey.data[vn].co += d2b90(delta[1:])
                else:
                    for delta in self.deltas:
                        vn = delta[0]
                        skey.data[vn].co += d2b90(delta[1:])
            else:
                for delta in self.deltas:
                    vn = delta[0]
                    skey.data[vn].co += d2b00(delta[1:])
            #if strength != 1:
            #    GS.scale = scale

        sname = self.getName()
        rig = ob.parent
        skey = addShapekey(ob, sname)
        if self.value < skey.slider_min:
            skey.slider_min = self.value
        if self.value > skey.slider_max:
            skey.slider_max = self.value
        skey.value = self.value
        self.rna = (skey, ob, sname)
        if useBuild:
            buildShapeKey(ob, skey, strength)


    def postbuild(self, context, inst):
        if inst is None:
            return
        elif LS.useMorphOnly:
            Formula.postbuild(self, context, inst)
        elif LS.fitFile or LS.useMorph:
            from .formula import buildBakedMorph
            buildBakedMorph(inst, self.id, self.value)
            self.buildBakedFormulas(context, inst)


def addShapekey(ob, sname):
    basic,skeys,new = getBasicShape(ob)
    if sname in ob.data.shape_keys.key_blocks.keys():
        skey = ob.data.shape_keys.key_blocks[sname]
        ob.shape_key_remove(skey)
    return ob.shape_key_add(name=sname)


def getBasicShape(ob):
    if not ob.data.shape_keys:
        basic = ob.shape_key_add(name="Basic")
        ob.data.shape_keys.name = "%s:KEYS" % ob.name
        new = True
    else:
        basic = ob.data.shape_keys.key_blocks[0]
        new = False
    return basic, ob.data.shape_keys, new
