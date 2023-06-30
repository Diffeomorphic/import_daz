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


import os
import bpy
from mathutils import *
from math import pi
from collections import OrderedDict
from .error import *
from .utils import *
from .fileutils import SingleFile, DufFile, DazExporter
from .selector import Selector
from .animation import HideOperator, FrameConverter
from .bone_data import BD

#----------------------------------------------------------
#   Save pose preset
#----------------------------------------------------------

class FakeCurve:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "%g" % self.value

    def evaluate(self, frame):
        return self.value


class DAZ_OT_SavePosePreset(HideOperator, DazExporter, SingleFile, DufFile, FrameConverter, IsObject):
    bl_idname = "daz.save_pose_preset"
    bl_label = "Save Pose Preset"
    bl_description = "Save the active action as a pose preset,\nto be used in DAZ Studio"
    bl_options = {'UNDO', 'PRESET'}

    useConvert = False
    affectBones = True
    affectMorphs = False

    useHierarchial : BoolProperty(
        name = "Hierarchial Pose",
        description = "Save a hierarchial pose preset",
        default = False)

    useAction : BoolProperty(
        name = "Use Action",
        description = "Save action instead of single pose",
        default = True)

    useObject : BoolProperty(
        name = "Use Object",
        description = "Include object in the pose preset",
        default = True)

    useBones : BoolProperty(
        name = "Use Bones",
        description = "Include bones in the pose preset",
        default = True)

    includeLocks : BoolProperty(
        name = "Include Locked Channels",
        description = "Include locked bone channels in the pose preset",
        default = False)

    useScale : BoolProperty(
        name = "Use Scale",
        description = "Include bone scale transforms in the pose preset",
        default = True)

    useFaceBones : BoolProperty(
        name = "Use Face Bones",
        description = "Include face bones in the pose preset",
        default = True)

    useMorphs : BoolProperty(
        name = "Use Morphs",
        description = "Include morphs in the pose preset",
        default = True)

    useUnusedMorphs : BoolProperty(
        name = "Save Unused Morphs",
        description = "Include morphs that are constantly zero",
        default = False)

    first : IntProperty(
        name = "Start",
        description = "First frame",
        default = 1)

    last : IntProperty(
        name = "End",
        description = "Last frame",
        default = 1)

    fps : FloatProperty(
        name = "FPS",
        description = "Frames per second",
        min = 1, max = 120,
        default = 30)

    def draw(self, context):
        DazExporter.draw(self, context)
        self.layout.prop(self, "useHierarchial")
        if not self.useHierarchial:
            self.layout.prop(self, "useObject")
            if self.isFigure:
                self.layout.prop(self, "useBones")
                if self.useBones:
                    self.layout.prop(self, "includeLocks")
                    self.layout.prop(self, "useScale")
                    self.layout.prop(self, "useFaceBones")
            self.layout.prop(self, "useMorphs")
            if self.useMorphs:
                self.layout.prop(self, "useUnusedMorphs")
        self.layout.prop(self, "useAction")
        if self.useAction:
            self.layout.prop(self, "first")
            self.layout.prop(self, "last")
            self.layout.prop(self, "fps")


    def invoke(self, context, event):
        rig = getRigFromContext(context, strict=False)
        self.isFigure = (rig.type == 'ARMATURE')
        return SingleFile.invoke(self, context, event)


    def run(self, context):
        self.Z = Matrix.Rotation(pi/2, 4, 'X')
        rig = getRigFromContext(context, strict=False, activate=True)
        self.initData()
        if self.useBones or self.useHierarchial:
            self.setupDriven(rig)
            self.setupConverter(rig)
        for bname,pg in rig.DazAlias.items():
            self.alias[bname] = pg.s
        act = None
        if self.useAction and rig.animation_data:
            act = rig.animation_data.action
        if act:
            self.getFcurves(rig, act)
        else:
            self.getFakeCurves(rig)

        if self.useMorphs and not self.useHierarchial and rig.type == 'MESH':
            skeys = rig.data.shape_keys
            if skeys:
                act = None
                if self.useAction and skeys.animation_data:
                    act = skeys.animation_data.action
                if act:
                    self.getShapeFcurves(act)
                else:
                    self.getShapeFakeCurves(skeys)

        if self.useBones or self.useHierarchial:
            self.setupFlipper(rig)
            self.setupBoneFrames(rig)
        elif self.useObject or self.useHierarchial:
            self.setupObjectFrames(rig)
        if self.useHierarchial:
            self.saveHierarchialPreset(rig)
        else:
            self.savePosePreset(rig)


    def initData(self):
        self.driven = {}
        self.alias = {}
        self.conv = {}
        self.twists = []
        self.morphs = {}
        self.locs = {}
        self.rots = {}
        self.quats = {}
        self.scales = {}
        self.Ls = dict([(frame, {}) for frame in range(self.first, self.last+1)])
        self.F = {}
        self.Finv = {}
        self.idxs = {}
        self.loclocks = {}
        self.rotlocks = {}


    def isLocUnlocked(self, pb, bname):
        bnames = ["lHand", "rHand", "lFoot", "rFoot",
                  "l_hand", "r_hand", "l_foot", "r_foot"]
        return (isLocationUnlocked(pb) and
                bname not in bnames)


    def getFcurves(self, rig, act):
        objkey = self.getDazObject(rig)
        self.rots[objkey] = 3*[None]
        self.locs[objkey] = 3*[None]
        self.scales[objkey] = 3*[None]
        if rig.type == 'ARMATURE':
            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
                    if pb.rotation_mode == 'QUATERNION':
                        self.quats[bname] = 4*[None]
                    else:
                        self.rots[bname] = 3*[None]
                    self.scales[bname] = 3*[None]
                    if self.isLocUnlocked(pb, bname):
                        self.locs[bname] = 3*[None]

        for fcu in act.fcurves:
            channel = fcu.data_path.rsplit(".",1)[-1]
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[" and (self.useBones or self.useHierarchial):
                idx = fcu.array_index
                for bname in self.getBoneNames(words[1]):
                    if channel == "location" and bname in self.locs.keys():
                        self.locs[bname][idx] = fcu
                    elif channel == "rotation_euler" and bname in self.rots.keys():
                        self.rots[bname][idx] = fcu
                    elif channel == "rotation_quaternion" and bname in self.quats.keys():
                        self.quats[bname][idx] = fcu
                    elif self.useScale and channel == "scale" and bname in self.scales.keys():
                        self.scales[bname][idx] = fcu
            elif words[0] == "[" and self.useMorphs and not self.useHierarchial:
                prop = words[1]
                if prop in rig.keys():
                    if self.isValidMorph(rig, prop):
                        self.morphs[prop] = fcu
            else:
                idx = fcu.array_index
                if channel == "location":
                    self.locs[objkey][idx] = fcu
                elif channel == "rotation_euler":
                    self.rots[objkey][idx] = fcu
                elif self.useScale and channel == "scale":
                    self.scales[objkey][idx] = fcu


    def getShapeFcurves(self, act):
        for fcu in act.fcurves:
            words = fcu.data_path.split('"')
            if words[0] == "key_blocks[" and words[1] != "Basic":
                self.morphs[words[1]] = fcu


    def isValidMorph(self, rig, prop):
        return (isinstance(rig[prop], float) and
                prop[0:3] not in ["Daz", "Mha", "Mhh"])


    def getFakeCurves(self, rig):
        if self.useObject or self.useHierarchial:
            objkey = self.getDazObject(rig)
            self.rots[objkey] = [FakeCurve(t) for t in rig.rotation_euler]
            self.locs[objkey] = [FakeCurve(t) for t in rig.location]
            self.scales[objkey] = [FakeCurve(t) for t in rig.scale]
        if self.useBones or self.useHierarchial:
            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
                    bname = self.getDazBone(bname, pb)
                    if pb.rotation_mode == 'QUATERNION':
                        self.quats[bname] = [FakeCurve(t) for t in pb.rotation_quaternion]
                    else:
                        self.rots[bname] = [FakeCurve(t) for t in pb.rotation_euler]
                    if self.useScale:
                        self.scales[bname] = [FakeCurve(t) for t in pb.scale]
                    if self.isLocUnlocked(pb, bname):
                        self.locs[bname] = [FakeCurve(t) for t in pb.location]
        if self.useMorphs and not self.useHierarchial and rig.type == 'ARMATURE':
            for prop in rig.keys():
                if self.isValidMorph(rig, prop):
                    self.morphs[prop]= FakeCurve(rig[prop])


    def getShapeFakeCurves(self, skeys):
        for skey in skeys.key_blocks:
            if skey.name != "Basic":
                self.morphs[skey.name] = FakeCurve(skey.value)


    def setupFlipper(self, rig):
        for pb in rig.pose.bones:
            euler = Euler(Vector(pb.bone.DazOrient)*D, 'XYZ')
            dmat = euler.to_matrix().to_4x4()
            dmat.col[3][0:3] = Vector(pb.bone.DazHead)*rig.DazScale
            Fn = pb.bone.matrix_local.inverted() @ self.Z @ dmat
            for bname in self.getBoneNames(pb.name):
                bname = self.getDazBone(bname, pb)
                self.F[bname] = Fn
                self.Finv[bname] = Fn.inverted()
                idxs = self.idxs[bname] = []
                for n in range(3):
                    idx = ord(pb.DazRotMode[n]) - ord('X')
                    idxs.append(idx)
                self.rotlocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_rotation) @ Fn.to_3x3()]
                self.loclocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_location) @ Fn.to_3x3()]


    def setupObjectFrames(self, rig):
        objkey = self.getDazObject(rig)
        for frame in range(self.first, self.last+1):
            L = self.Ls[frame] = {}
            mat = self.getRigMatrix(rig, frame)
            L[objkey] = self.Z.inverted() @ mat @ self.Z


    RootNames = ["Root", "master", "root"]

    def setupBoneFrames(self, rig):
        def getRoot(rig):
            for bname in self.RootNames:
                if bname in rig.pose.bones.keys():
                    return rig.pose.bones[bname]
            return None

        objkey = self.getDazObject(rig)
        for frame in range(self.first, self.last+1):
            L = self.Ls[frame]
            smats = {}
            mat = self.getRigMatrix(rig, frame)
            root = getRoot(rig)
            if root and root.parent is None:
                rmat = self.getBoneMatrix(root, root.name, smats, rig, frame)
                rmat = root.bone.matrix_local @ rmat @ root.bone.matrix_local.inverted()
                mat = mat @ rmat
            L[objkey] = self.Z.inverted() @ mat @ self.Z

            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
                    mat = self.getBoneMatrix(pb, bname, smats, rig, frame)
                    if mat is None:
                        print("NOMAT", pb.name, bname)
                        continue
                    bname = self.getDazBone(bname, pb)
                    L[bname] = self.Finv[bname] @ mat @ self.F[bname]


    def getRigMatrix(self, rig, frame):
        objkey = self.getDazObject(rig)
        rot = rig.rotation_euler.copy()
        for idx,fcu in enumerate(self.rots[objkey]):
            if fcu:
                rot[idx] = fcu.evaluate(frame)
        mat = rot.to_matrix().to_4x4()
        if self.useScale:
            scale = rig.scale.copy()
            for idx,fcu in enumerate(self.scales[objkey]):
                if fcu:
                    scale[idx] = fcu.evaluate(frame)
            smat = Matrix.Diagonal(scale)
            mat = mat @ smat.to_4x4()
        loc = rig.location.copy()
        for idx,fcu in enumerate(self.locs[objkey]):
            if fcu:
                loc[idx] = fcu.evaluate(frame)
        return Matrix.Translation(loc) @ mat


    def getBoneMatrix(self, pb, bname, smats, rig, frame):
        if bname in self.quats.keys():
            quat = pb.rotation_quaternion.copy()
            for idx,fcu in enumerate(self.quats[bname]):
                if fcu:
                    quat[idx] = fcu.evaluate(frame)
            mat = quat.to_matrix().to_4x4()
        elif bname in self.rots.keys():
            rot = pb.rotation_euler.copy()
            for idx,fcu in enumerate(self.rots[bname]):
                if fcu:
                    rot[idx] = fcu.evaluate(frame)
            mat = rot.to_matrix().to_4x4()
        else:
            return None

        if self.useScale and bname in self.scales.keys():
            scale = pb.scale.copy()
            for idx,fcu in enumerate(self.scales[bname]):
                if fcu:
                    scale[idx] = fcu.evaluate(frame)
            smat = Matrix.Diagonal(scale)
            if (pb.parent and
                pb.parent.name in smats.keys() and
                inheritsScale(pb)):
                parname = self.getDazBone(pb.parent.name, pb.parent)
                psmat = smats[parname]
                smat = smat @ psmat
            mat = mat @ smat.to_4x4()
            smats[bname] = smat

        if bname in self.locs.keys():
            loc = pb.location.copy()
            for idx,fcu in enumerate(self.locs[bname]):
                if fcu:
                    loc[idx] = fcu.evaluate(frame)
            mat = Matrix.Translation(loc) @ mat
        return mat


    def setupDriven(self, rig):
        if rig.animation_data:
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if words[0] == "pose.bones[":
                    bname = words[1]
                    if bname not in self.driven.keys():
                        self.driven[bname] = {}
                    channel = words[2][2:]
                    if channel in ["rotation_euler", "rotation_quaternion"]:
                        self.driven[bname]["rotation"] = True
                    elif channel in ["location", "scale"]:
                        self.driven[bname][channel] = True


    def setupConverter(self, rig):
        conv,twists = self.getConv(rig, rig)
        bonemap = OrderedDict()
        if conv:
            self.twists = twists
            for mbone,dbone in conv.items():
                if dbone not in self.conv.keys():
                    self.conv[dbone] = []
                self.conv[dbone].append(mbone)
            for root in ["head", "DEF-spine.007"]:
                if root in rig.pose.bones.keys():
                    pb = rig.pose.bones[root]
                    if self.useFaceBones:
                        self.setupConvBones(pb)
                    else:
                        self.removeConvChildren(pb, list(self.conv.keys()))
            if rig.DazRig == "mhx":
                from .layers import L_CUSTOM
                customLayer = L_CUSTOM
            elif rig.DazRig[0:6] == "rigify":
                from .rigify import R_CUSTOM
                customLayer = R_CUSTOM
            else:
                return
            for pb in rig.pose.bones:
                if pb.bone.layers[customLayer]:
                    bname = self.getPrefixName(pb)
                    if bname:
                        self.conv[pb.name] = [bname]
        else:
            roots = [pb for pb in rig.pose.bones if pb.parent is None]
            for pb in roots:
                self.setupConvBones(pb)


    def getPrefixName(self, pb):
        if isDrvBone(pb.name) or isFinal(pb.name):
            return None
        elif pb.name[-2:] == ".L":
            return "l%s%s" % (pb.name[0].upper(), pb.name[1:-2])
        elif pb.name[-2:] == ".R":
            return "r%s%s" % (pb.name[0].upper(), pb.name[1:-2])
        else:
            return pb.name


    def setupConvBones(self, pb):
        bname = self.getPrefixName(pb)
        if bname:
            self.conv[pb.name] = [bname]
        if bname != "head" or self.useFaceBones:
            for child in pb.children:
                self.setupConvBones(child)


    def removeConvChildren(self, pb, conv):
        for child in pb.children:
            if child.name in conv:
                del self.conv[child.name]
            self.removeConvChildren(child, conv)


    def getBoneNames(self, bname):
        if bname in self.conv.keys():
            return self.conv[bname]
        elif bname in self.RootNames:
            return [bname]
        else:
            return []


    def getTwistBone(self, bname):
        if "TWIST-" + bname in self.conv.keys():
            twname = self.conv["TWIST-" + bname][0]
            if twname in BD.TwistDxs.keys():
                return twname, BD.TwistDxs[twname]
        return None, 0


    def getDazObject(self, rig):
        return ""


    def getDazBone(self, bname, pb):
        idx = pb.bone.get("DazRigIndex", 0)
        if idx == 0:
            return bname
        else:
            return "%s-%d" % (bname, idx)


    def getNodes(self, rig):
        nodes = {}
        self.ancestors = {}
        figure = rig.DazUrl.rsplit("#",1)[1]
        node = {
            "id" : figure,
            "url" : "name://@selection/%s:" % quote(figure),
        }
        self.ancestors[figure] = True
        if rig.parent:
            if rig.parent_type == 'OBJECT':
                parent = rig.parent.DazUrl.rsplit("#",1)[1]
                node["parent"] = "#%s" % quote(parent)
            elif rig.parent_type == 'BONE':
                node["parent"] = "#%s" % quote(rig.parent_bone)
        nodes[0] = [node]
        for pb in rig.pose.bones:
            if isDrvBone(pb.name) or isFinal(pb.name):
                continue
            idx = pb.bone.get("DazRigIndex", 0)
            if idx not in nodes.keys():
                nodes[idx] = []
            nodes[idx] += self.getAncestors(pb, rig, idx, figure)
        nodelist = []
        for idx in range(len(rig.data.DazMergedRigs)):
            nodelist += nodes.get(idx, [])
        return nodelist


    def getAncestors(self, pb, rig, idx, figure):
        pg = rig.data.DazMergedRigs[str(idx)]
        path,figure2 = pg.s.rsplit("#",1)
        parent = pb.parent
        nodes = []
        if parent:
            parname = self.getDazBone(parent.name, pb)
        while parent and parname not in self.ancestors.keys():
            self.ancestors[parname] = True
            node = {
                "id" : parname,
                "url" : "name://@selection/%s:" % quote(parent.name)
            }
            parent = parent.parent
            if parent:
                parname = self.getDazBone(parent.name, pb)
                node["parent"] = "#%s" % quote(parname)
            else:
                node["parent"] = "#%s" % quote(figure2)
            nodes.append(node)
        if figure2 not in self.ancestors.keys():
            node = {
                "id" : figure2,
                "url" : "name://@selection/%s:" % quote(figure2),
                "parent" : "#%s" % quote(figure)
            }
            nodes.append(node)
            self.ancestors[figure2] = True
        nodes.reverse()
        return nodes


    def saveHierarchialPreset(self, rig):
        from .load_json import saveJson
        struct, filepath = self.makeDazStruct("preset_hierarchical_pose", self.filepath)
        struct["scene"] = {}
        struct["scene"]["nodes"] = self.getNodes(rig)
        struct["scene"]["animations"] = self.getAnimations(rig)
        saveJson(struct, filepath, binary=self.useCompress)
        print("Pose preset %s saved" % filepath)


    def savePosePreset(self, rig):
        from .load_json import saveJson
        struct, filepath = self.makeDazStruct("preset_pose", self.filepath)
        struct["scene"] = {}
        struct["scene"]["animations"] = self.getAnimations(rig)
        saveJson(struct, filepath, binary=self.useCompress)
        print("Pose preset %s saved" % filepath)


    def getBoneUrl(self, bname, pb, rig):
        if self.useHierarchial:
            if pb == rig:
                path,figure = rig.DazId.rsplit("#", 1)
                figure = quote(figure)
                path = quote(path)
                return "%s:%s#%s" % (figure, path, figure)
            else:
                idx = pb.bone.get("DazRigIndex", 0)
                pg = rig.data.DazMergedRigs[str(idx)]
                path,figure = pg.s.rsplit("#",1)
                id = pb.bone.get("DazTrueName", pb.name)
                return"%s:%s#%s" % (quote(bname), quote(path), quote(id))
        else:
            if pb == rig:
                return "name://@selection:"
            else:
                id = pb.bone.get("DazTrueName", pb.name)
                return "name://@selection/%s" % quote(id)


    def getAnimations(self, rig):
        from collections import OrderedDict
        globalFlip = {
            'XYZ' : 'XZY',
            'XZY' : 'XYZ',
            'YXZ' : 'ZXY',
            'YZX' : 'ZYX',
            'ZXY' : 'YXZ',
            'ZYX' : 'YZX',
        }
        anims = []
        if self.useObject or self.useHierarchial:
            objkey = self.getDazObject(rig)
            Ls = [self.Ls[frame][objkey] for frame in range(self.first, self.last+1)]
            locs = [L.to_translation() for L in Ls]
            self.getTrans("", rig, rig, locs, 1/rig.DazScale, anims)

            rots = [L.to_euler(globalFlip[rig.rotation_mode]) for L in Ls]
            self.getRot("", rig, rig, rots, 1/D, anims)
            if self.useScale:
                scales = [L.to_scale() for L in Ls]
                self.getScale("", rig, rig, scales, anims)

        if (self.useBones or self.useHierarchial) and rig.type == 'ARMATURE':
            for pb in rig.pose.bones:
                if pb.name in self.RootNames:
                    continue
                for bname in self.getBoneNames(pb.name):
                    bname = self.getDazBone(bname, pb)
                    Ls = [self.Ls[frame][bname] for frame in range(self.first, self.last+1)]
                    if self.isLocUnlocked(pb, bname):
                        locs = [L.to_translation() for L in Ls]
                        self.getTrans(bname, pb, rig, locs, 1/rig.DazScale, anims)
                    rots = [L.to_euler(pb.DazRotMode) for L in Ls]
                    self.getRot(bname, pb, rig, rots, 1/D, anims)
                    if self.useScale:
                        scales = [L.to_scale() for L in Ls]
                        self.getScale(bname, pb, rig, scales, anims)

        if self.useMorphs and not self.useHierarchial:
            for prop,fcu in self.morphs.items():
                self.getMorph(prop, fcu, anims)
        return anims


    def getMorph(self, prop, fcu, anims):
        from .asset import normalizeRef
        if prop in self.alias.keys():
            prop = self.alias[prop]
        anim = {}
        anim["url"] = "name://@selection#%s:?value/value" % normalizeRef(prop)
        vals = [fcu.evaluate(frame) for frame in range(self.first, self.last+1)]
        maxval = max(vals)
        minval = min(vals)
        if maxval-minval < 1e-4:
            if abs(maxval) < 5e-5:
                if self.useUnusedMorphs:
                    anim["keys"] = [(0, 0)]
                    anims.append(anim)
            else:
                anim["keys"] = [(0, (maxval+minval)/2)]
                anims.append(anim)
        else:
            anim["keys"] = [(n/self.fps, val) for n,val in enumerate(vals)]
            anims.append(anim)


    def addKeys(self, xs, anim, eps):
        if len(xs) == 0:
            return
        maxdiff = max([abs(x-xs[0]) for x in xs])
        if maxdiff < eps:
            anim["keys"] = [(0, xs[0])]
        else:
            anim["keys"] = [(n/self.fps, x) for n,x in enumerate(xs)]


    def getTrans(self, bname, pb, rig, vecs, factor, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("location"):
            return
        if pb == rig:
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "%s?translation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                locs = [vec[idx]*factor for vec in vecs]
                self.addKeys(locs, anim, 1e-5)
                anims.append(anim)
        else:
            for idx,x in enumerate(["x","y","z"]):
                if (not self.includeLocks and
                    pb.name in self.loclocks.keys() and
                    self.loclocks[pb.name][idx]):
                    continue
                anim = {}
                anim["url"] = "%s:?translation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                locs = [vec[idx]*factor for vec in vecs]
                self.addKeys(locs, anim, 1e-5)
                anims.append(anim)


    def getRot(self, bname, pb, rig, vecs, factor, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("rotation"):
            return
        if pb == rig:
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "%s:?rotation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                rots = [vec[idx]*factor for vec in vecs]
                rots = self.correct180(rots)
                self.addKeys(rots, anim, 1e-3)
                anims.append(anim)
        else:
            twname,twidx = self.getTwistBone(pb.name)
            for idx,x in enumerate(["x","y","z"]):
                if ((not self.includeLocks and
                     pb.name in self.rotlocks.keys() and
                     self.rotlocks[pb.name][idx]) or
                    (twname and idx == twidx)):
                    continue
                anim = {}
                anim["url"] = "%s:?rotation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                rots = [vec[idx]*factor for vec in vecs]
                rots = self.correct180(rots)
                self.addKeys(rots, anim, 1e-3)
                anims.append(anim)
            if twname is None:
                return
            for idx,x in enumerate(["x","y","z"]):
                if idx != twidx:
                    continue
                anim = {}
                anim["url"] = "%s:?rotation/%s/value" % (self.getBoneUrl(twname, pb, rig), x)
                rots = [vec[idx]*factor for vec in vecs]
                rots = self.correct180(rots)
                self.addKeys(rots, anim, 1e-3)
                anims.append(anim)


    def getScale(self, bname, pb, rig, vecs, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("scale"):
            return
        general = True
        for vec in vecs:
            if (abs(vec[0]-vec[1]) > 1e-5 or
                abs(vec[0]-vec[2]) > 1e-5 or
                abs(vec[1]-vec[2]) > 1e-5):
                general = False
                break
        #if bname:
        #    bname = "/%s" % bname
        if general:
            anim = {}
            anim["url"] = "%s:?scale/general/value" % self.getBoneUrl(bname, pb, rig)
            scales = [vec[0] for vec in vecs]
            self.addKeys(scales, anim, 1e-4)
            anims.append(anim)
        else:
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "%s:?scale/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                scales = [vec[idx] for vec in vecs]
                self.addKeys(scales, anim, 1e-4)
                anims.append(anim)


    def correct180(self, rots):
        prev = 0
        nrots = []
        offset = 0
        for rot in rots:
            nrot = rot + offset
            if nrot - prev > 180:
                offset -= 360
                nrot -= 360
            elif nrot - prev < -180:
                offset += 360
                nrot += 360
            prev = nrot
            nrots.append(nrot)
        return nrots

#-------------------------------------------------------------
#   Save morph presets
#-------------------------------------------------------------

class DAZ_OT_SaveMorphPreset(DazOperator, DazExporter, Selector, IsMesh):
    bl_idname = "daz.save_morph_preset"
    bl_label = "Save Morph Preset"
    bl_description = "Save selected shapekeys as a morph preset"

    directory: StringProperty(
        name = "Directory",
        description = "Directory")

    presentation: EnumProperty(
        items = [("Modifier/Pose", "Pose Control", "Pose control"),
                 ("Modifier/Shape", "Shape", "Shape")],
        name = "Presentation",
        description = "Presentation",
        default = "Modifier/Pose")

    def draw(self, context):
        self.layout.prop(self, "directory")
        Selector.draw(self, context)
        #DazExporter.draw(self, context)
        #self.layout.prop(self, "presentation")

    def getKeys(self, rig, ob):
        keys = []
        for skey in ob.data.shape_keys.key_blocks[1:]:
            keys.append((skey.name, skey.name, "All"))
        return keys

    def invoke(self, context, event):
        ob = context.object
        if ob.data.shape_keys is None:
            msg = "Object %s has no shapekeys" % ob.name
            invokeErrorMessage(msg)
            return {'CANCELLED'}
        self.directory = context.scene.DazMorphPath
        return Selector.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        from .asset import normalizeUrl
        ob = context.object
        rig = ob.parent
        parent = None
        if rig:
            parent = normalizeUrl(rig.DazUrl)
        for item in self.getSelectedItems():
            filename = ("%s.duf" % item.name).replace(" ", "_")
            filepath = os.path.join(self.directory, filename)
            struct,filepath = self.makeDazStruct("modifier", filepath)
            modlib = struct["modifier_library"] = []
            skey = ob.data.shape_keys.key_blocks[item.name]
            mstruct = self.addLibModifier(skey, ob, parent)
            modlib.append(mstruct)
            modlist = []
            struct["scene"] = {"modifiers" : modlist}
            mname = item.name.replace(" ", "_")
            mstruct = {"id" : "%s-1" % mname, "url" : normalizeUrl(mname)}
            modlist.append(mstruct)
            saveJson(struct, filepath, binary=self.useCompress)
            print("Morph preset %s saved" % filepath)


    def addLibModifier(self, skey, ob, parent):
        from collections import OrderedDict
        mname = skey.name.replace(" ", "_")
        struct = OrderedDict()
        struct["id"] = mname
        struct["name"] = mname
        if parent:
            struct["parent"] = parent
        struct["presentation"] = {
            "type" : self.presentation,
            "label" : skey.name,
            "description" : "",
            "icon_large" : "",
            "colors" : [ [ 0.1607843, 0.1607843, 0.1607843 ], [ 0.4980392, 0, 0 ] ]
        }
        struct["channel"] = {
            "id" : "value",
            "type" : "float",
            "name" : mname,
            "label" : skey.name,
            "auto_follow" : True,
            "value" : 0,
            "min" : 0,
            "max" : 1,
            "clamped" : True,
            "display_as_percent" : True,
            "step_size" : 0.01
        }
        if self.presentation == "Modifier/Pose":
            struct["group"] = "/Pose Controls"
        elif self.presentation == "Modifier/Shape":
            struct["region"] = "Actor"
            struct["group"] = "/Full Body/People"
        nverts = len(ob.data.vertices)
        mstruct = struct["morph"] = OrderedDict()
        mstruct["vertex_count"] = nverts
        dstruct = mstruct["deltas"] = OrderedDict()
        factor = 1/ob.DazScale
        eps = 0.001 # 0.01 mm
        diffs = [factor*(skey.data[vn].co - v.co) for vn,v in enumerate(ob.data.vertices)]
        deltas = [[vn, delta[0], delta[2], -delta[1]] for vn,delta in enumerate(diffs) if delta.length > eps]
        dstruct["count"] = len(deltas)
        dstruct["values"] = deltas
        return struct

#-------------------------------------------------------------
#   Bake deform rig
#-------------------------------------------------------------

class Framer:
    frame_start : IntProperty(
        name = "Start",
        default = 1)

    frame_end : IntProperty(
        name = "End",
        default = 1)

    def draw(self, context):
        self.layout.prop(self, "frame_start")
        self.layout.prop(self, "frame_end")

    def bakeShapekeys(self, context, meshes, actname):
        scn = context.scene
        for ob in meshes:
            if ob.animation_data:
                ob.animation_data.action = None
        for frame in range(self.frame_start, self.frame_end+1):
            scn.frame_current = frame
            updateScene(context)
            for ob in meshes:
                for skey in ob.data.shape_keys.key_blocks:
                    skey.value = skey.value
                    if abs(skey.value) < 1e-4:
                        skey.value = 0
                    skey.keyframe_insert("value", frame=frame)
        for ob in meshes:
            if ob.data.shape_keys:
                act = getCurrentAction(ob.data.shape_keys)
                if act:
                    act.name = "%s:%s" % (actname[0:33], ob.name[0:30])


class ControlRigMuter:
    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Mute/unmute shapekeys too",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useShapekeys")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig not in ["mhx", "rigify", "rigify2"])

    def getProps(self, rig, gen):
        props = {}
        for prop in rig.keys():
            final = finalProp(prop)
            if final in gen.data.keys():
                props[prop] = gen.data[final]
        return props

    def muteConstraints(self, rig, mute):
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    cns.mute = mute
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            cns.mute = mute

    def getControlRig(self, rig):
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            return cns.target
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    return cns.target
        raise DazError("No control rig found")


def getCurrentAction(rna):
    if rna and rna.animation_data:
        return rna.animation_data.action
    return None

#-------------------------------------------------------------
#   Bake shapekeys
#-------------------------------------------------------------

class DAZ_OT_BakeShapekeys(Framer, DazPropsOperator, IsMesh):
    bl_idname = "daz.bake_shapekeys"
    bl_label = "Bake Shapekeys"
    bl_description = "Bake shapekey values to current action.\nMute control rig afterwards"
    bl_options = {'UNDO'}

    def run(self, context):
        meshes = getSelectedMeshes(context)
        self.bakeShapekeys(context, meshes, "Shapes")

#-------------------------------------------------------------
#   Mute control rig
#-------------------------------------------------------------

class DAZ_OT_MuteControlRig(ControlRigMuter, Framer, DazPropsOperator):
    bl_idname = "daz.mute_control_rig"
    bl_label = "Mute Deform Rig"
    bl_description = "Disable drivers and copy location/rotation constraints"
    bl_options = {'UNDO'}

    useBake : BoolProperty(
        name = "Bake action",
        description = "Bake visual transform to an action",
        default = True)

    def draw(self, context):
        ControlRigMuter.draw(self, context)
        self.layout.prop(self, "useBake")
        if self.useBake:
            Framer.draw(self, context)

    def run(self, context):
        rig = context.object
        gen = self.getControlRig(rig)
        act = getCurrentAction(gen)
        if act:
            actname = act.name
        else:
            actname = "Action"
        meshes = getShapeChildren(rig)
        if self.useBake:
            bpy.ops.nla.bake(frame_start=self.frame_start, frame_end=self.frame_end, only_selected=False, visual_keying=True, bake_types={'OBJECT', 'POSE'})
            act = getCurrentAction(rig)
            if act:
                act.name = "%s:BAKED" % actname[0:58]
            if self.useShapekeys:
                self.bakeShapekeys(context, meshes, actname)
        if self.useShapekeys:
            for ob in meshes:
                for skey in ob.data.shape_keys.key_blocks:
                    skey.driver_remove("value")
        self.muteConstraints(rig, True)
        gen.hide_set(True)
        props = self.getProps(rig, gen)
        fcurves = self.getFcurves(gen, props)
        for prop,value in props.items():
            rig.driver_remove(propRef(prop))
            rig[prop] = value
        if self.useBake and not self.useShapekeys:
            for prop,fcu in fcurves.items():
                self.setFcurve(rig, propRef(prop), fcu)

    def getFcurves(self, gen, props):
        fcurves = {}
        act = getCurrentAction(gen)
        if act:
            for fcu in act.fcurves:
                prop = getProp(fcu.data_path)
                if prop in props:
                    fcurves[prop] = fcu
        return fcurves

    def setFcurve(self, rna, path, fcu):
        rna.keyframe_insert(path)
        act = rna.animation_data.action
        fcu2 = act.fcurves.find(path)
        fcu2.keyframe_points.clear()
        for frame in range(self.frame_start, self.frame_end+1):
            value = fcu.evaluate(frame)
            fcu2.keyframe_points.insert(frame, value, options={'FAST'})

    def removePropFcurves(self, act):
        for fcu in list(act.fcurves):
            if isPropRef(fcu.data_path):
                act.fcurves.remove(fcu)

#-------------------------------------------------------------
#   Unmute control rig
#-------------------------------------------------------------

class DAZ_OT_UnmuteControlRig(ControlRigMuter, Framer, DazPropsOperator):
    bl_idname = "daz.unmute_control_rig"
    bl_label = "Unmute Deform Rig"
    bl_description = "Enable drivers and copy location/rotation constraints"
    bl_options = {'UNDO'}

    useClear : BoolProperty(
        name = "Clear action",
        description = "Clear the current action",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useClear")

    def run(self, context):
        from .driver import addDriver
        rig = context.object
        gen = self.getControlRig(rig)
        if gen is None:
            raise DazError("No control rig found")
        gen.hide_set(False)
        self.muteConstraints(rig, False)
        meshes = getShapeChildren(rig)
        props = self.getProps(rig, gen)
        if self.useClear and rig.animation_data:
            rig.animation_data.action = None
            unit = Matrix()
            rig.matrix_world = unit
            for pb in rig.pose.bones:
                pb.matrix_basis = unit
        for prop in props.keys():
            final = finalProp(prop)
            addDriver(rig, propRef(prop), gen, propRef(prop), "x")
        if self.useShapekeys:
            for ob in meshes:
                skeys = ob.data.shape_keys
                if self.useClear and skeys.animation_data:
                    skeys.animation_data.action = None
                for skey in skeys.key_blocks:
                    final = finalProp(skey.name)
                    if final in rig.data.keys():
                        addDriver(skeys, 'key_blocks["%s"].value' % skey.name, rig.data, propRef(final), "x")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosePreset,
    DAZ_OT_SaveMorphPreset,
    DAZ_OT_BakeShapekeys,
    DAZ_OT_MuteControlRig,
    DAZ_OT_UnmuteControlRig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
