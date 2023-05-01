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
from collections import OrderedDict
from .error import *
from .utils import *
from .fileutils import SingleFile, DufFile, DazExporter
from .selector import Selector, getRigFromObject
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


class DAZ_OT_SavePosePreset(HideOperator, DazExporter, SingleFile, DufFile, FrameConverter, IsArmature):
    bl_idname = "daz.save_pose_preset"
    bl_label = "Save Pose Preset"
    bl_description = "Save the active action as a pose preset,\nto be used in DAZ Studio"
    bl_options = {'UNDO', 'PRESET'}

    useConvert = False
    affectBones = True
    affectMorphs = False

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
        self.layout.prop(self, "useBones")
        if self.useBones:
            self.layout.prop(self, "useObject")
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


    def run(self, context):
        from math import pi
        self.Z = Matrix.Rotation(pi/2, 4, 'X')
        rig = context.object
        self.setupDriven(rig)
        self.setupConverter(rig)
        self.alias = dict([(key, pg.s) for key,pg in rig.DazAlias.items()])
        act = None
        self.morphs = {}
        self.locs = {}
        self.rots = {}
        self.quats = {}
        self.scales = {}
        if self.useAction:
            if rig.animation_data:
                act = rig.animation_data.action
            if act:
                self.getFcurves(rig, act)
        if not act:
            self.getFakeCurves(rig)
        if self.useBones:
            self.setupFlipper(rig)
            self.setupFrames(rig)
        self.saveFile(rig)


    def isLocUnlocked(self, pb, bname):
        bnames = ["lHand", "rHand", "lFoot", "rFoot",
                  "l_hand", "r_hand", "l_foot", "r_foot"]
        return (isLocationUnlocked(pb) and
                bname not in bnames)


    def getFcurves(self, rig, act):
        self.rots[""] = 3*[None]
        self.locs[""] = 3*[None]
        self.scales[""] = 3*[None]
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
            if words[0] == "pose.bones[" and self.useBones:
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
            elif words[0] == "[" and self.useMorphs:
                prop = words[1]
                if prop in rig.keys():
                    if self.isValidMorph(rig, prop):
                        self.morphs[prop] = fcu
            else:
                idx = fcu.array_index
                if channel == "location":
                    self.locs[""][idx] = fcu
                elif channel == "rotation_euler":
                    self.rots[""][idx] = fcu
                elif self.useScale and channel == "scale":
                    self.scales[""][idx] = fcu


    def isValidMorph(self, rig, prop):
        return (isinstance(rig[prop], float) and
                prop[0:3] not in ["Daz", "Mha", "Mhh"])


    def getFakeCurves(self, rig):
        if self.useBones:
            self.rots[""] = [FakeCurve(t) for t in rig.rotation_euler]
            self.locs[""] = [FakeCurve(t) for t in rig.location]
            self.scales[""] = [FakeCurve(t) for t in rig.scale]
            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
                    if pb.rotation_mode == 'QUATERNION':
                        self.quats[bname] = [FakeCurve(t) for t in pb.rotation_quaternion]
                    else:
                        self.rots[bname] = [FakeCurve(t) for t in pb.rotation_euler]
                    if self.useScale:
                        self.scales[bname] = [FakeCurve(t) for t in pb.scale]
                    if self.isLocUnlocked(pb, bname):
                        self.locs[bname] = [FakeCurve(t) for t in pb.location]
        if self.useMorphs:
            for prop in rig.keys():
                if self.isValidMorph(rig, prop):
                    self.morphs[prop]= FakeCurve(rig[prop])


    def setupFlipper(self, rig):
        self.F = {}
        self.Finv = {}
        self.idxs = {}
        self.loclocks = {}
        self.rotlocks = {}

        for pb in rig.pose.bones:
            euler = Euler(Vector(pb.bone.DazOrient)*D, 'XYZ')
            dmat = euler.to_matrix().to_4x4()
            dmat.col[3][0:3] = Vector(pb.bone.DazHead)*rig.DazScale
            Fn = pb.bone.matrix_local.inverted() @ self.Z @ dmat
            for bname in self.getBoneNames(pb.name):
                self.F[bname] = Fn
                self.Finv[bname] = Fn.inverted()
                idxs = self.idxs[bname] = []
                for n in range(3):
                    idx = ord(pb.DazRotMode[n]) - ord('X')
                    idxs.append(idx)
                self.rotlocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_rotation) @ Fn.to_3x3()]
                self.loclocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_location) @ Fn.to_3x3()]

    RootNames = ["Root", "master", "root"]

    def setupFrames(self, rig):
        def getRoot(rig):
            for bname in self.RootNames:
                if bname in rig.pose.bones.keys():
                    return rig.pose.bones[bname]
            return None

        self.Ls = {}
        for frame in range(self.first, self.last+1):
            L = self.Ls[frame] = {}
            smats = {}
            mat = self.getRigMatrix(rig, frame)
            root = getRoot(rig)
            if root and root.parent is None:
                rmat = self.getBoneMatrix(root, root.name, smats, frame)
                rmat = root.bone.matrix_local @ rmat @ root.bone.matrix_local.inverted()
                mat = mat @ rmat
            L[""] = self.Z.inverted() @ mat @ self.Z

            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
                    mat = self.getBoneMatrix(pb, bname, smats, frame)
                    if mat is None:
                        continue
                    L[bname] = self.Finv[bname] @ mat @ self.F[bname]


    def getRigMatrix(self, rig, frame):
        rot = rig.rotation_euler.copy()
        for idx,fcu in enumerate(self.rots[""]):
            if fcu:
                rot[idx] = fcu.evaluate(frame)
        mat = rot.to_matrix().to_4x4()
        if self.useScale:
            scale = rig.scale.copy()
            for idx,fcu in enumerate(self.scales[""]):
                if fcu:
                    scale[idx] = fcu.evaluate(frame)
            smat = Matrix.Diagonal(scale)
            mat = mat @ smat.to_4x4()
        loc = rig.location.copy()
        for idx,fcu in enumerate(self.locs[""]):
            if fcu:
                loc[idx] = fcu.evaluate(frame)
        return Matrix.Translation(loc) @ mat


    def getBoneMatrix(self, pb, bname, smats, frame):
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
                psmat = smats[pb.parent.name]
                smat = smat @ psmat
            mat = mat @ smat.to_4x4()
            smats[pb.name] = smat

        if bname in self.locs.keys():
            loc = pb.location.copy()
            for idx,fcu in enumerate(self.locs[bname]):
                if fcu:
                    loc[idx] = fcu.evaluate(frame)
            mat = Matrix.Translation(loc) @ mat
        return mat


    def setupDriven(self, rig):
        self.driven = {}
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
        self.conv = {}
        self.twists = []
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
                    bname = self.getDazName(pb)
                    if bname:
                        self.conv[pb.name] = [bname]
        else:
            roots = [pb for pb in rig.pose.bones if pb.parent is None]
            for pb in roots:
                self.setupConvBones(pb)


    def getDazName(self, pb):
        if isDrvBone(pb.name) or isFinal(pb.name):
            return None
        elif pb.name[-2:] == ".L":
            return "l%s%s" % (pb.name[0].upper(), pb.name[1:-2])
        elif pb.name[-2:] == ".R":
            return "r%s%s" % (pb.name[0].upper(), pb.name[1:-2])
        else:
            return pb.name


    def setupConvBones(self, pb):
        bname = self.getDazName(pb)
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


    def saveFile(self, rig):
        from .load_json import saveJson
        struct, filepath = self.makeDazStruct("preset_pose", self.filepath)
        struct["scene"] = {}
        struct["scene"]["animations"] = self.getAnimations(rig)
        saveJson(struct, filepath, binary=self.useCompress)
        print("Pose preset %s saved" % filepath)


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
        if self.useBones:
            for pb in rig.pose.bones:
                if pb.name in self.RootNames:
                    continue
                for bname in self.getBoneNames(pb.name):
                    Ls = [self.Ls[frame][bname] for frame in range(self.first, self.last+1)]
                    if self.isLocUnlocked(pb, bname):
                        locs = [L.to_translation() for L in Ls]
                        self.getTrans(bname, pb, locs, 1/rig.DazScale, anims)
                    rots = [L.to_euler(pb.DazRotMode) for L in Ls]
                    self.getRot(bname, pb, rots, 1/D, anims)
                    if self.useScale:
                        scales = [L.to_scale() for L in Ls]
                        self.getScale(bname, pb, scales, anims)

        if self.useObject:
            Ls = [self.Ls[frame][""] for frame in range(self.first, self.last+1)]
            locs = [L.to_translation() for L in Ls]
            self.getTrans("", rig, locs, 1/rig.DazScale, anims)

            rots = [L.to_euler(globalFlip[rig.rotation_mode]) for L in Ls]
            self.getRot("", rig, rots, 1/D, anims)
            if self.useScale:
                scales = [L.to_scale() for L in Ls]
                self.getScale("", rig, scales, anims)

        if self.useMorphs:
            for prop,fcu in self.morphs.items():
                self.getMorph(prop, fcu, anims)
        return anims


    def getMorph(self, prop, fcu, anims):
        from .asset import normalizeRef
        if prop in self.alias.keys():
            prop = self.alias[prop]
        anim = {}
        anim["url"] = "name://@selection#%s:?value/value" % prop
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


    def getTrans(self, bname, pb, vecs, factor, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("location"):
            return
        if bname == "":
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "name://@selection:?translation/%s/value" % (x)
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
                anim["url"] = "name://@selection/%s:?translation/%s/value" % (bname, x)
                locs = [vec[idx]*factor for vec in vecs]
                self.addKeys(locs, anim, 1e-5)
                anims.append(anim)


    def getRot(self, bname, pb, vecs, factor, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("rotation"):
            return
        if bname == "":
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "name://@selection:?rotation/%s/value" % (x)
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
                anim["url"] = "name://@selection/%s:?rotation/%s/value" % (bname, x)
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
                anim["url"] = "name://@selection/%s:?rotation/%s/value" % (twname, x)
                rots = [vec[idx]*factor for vec in vecs]
                rots = self.correct180(rots)
                self.addKeys(rots, anim, 1e-3)
                anims.append(anim)


    def getScale(self, bname, pb, vecs, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("scale"):
            return
        general = True
        for vec in vecs:
            if (abs(vec[0]-vec[1]) > 1e-5 or
                abs(vec[0]-vec[2]) > 1e-5 or
                abs(vec[1]-vec[2]) > 1e-5):
                general = False
                break
        if bname:
            bname = "/%s" % bname
        if general:
            anim = {}
            anim["url"] = "name://@selection%s:?scale/general/value" % bname
            scales = [vec[0] for vec in vecs]
            self.addKeys(scales, anim, 1e-4)
            anims.append(anim)
        else:
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "name://@selection%s:?scale/%s/value" % (bname, x)
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
#   Bake constraints
#-------------------------------------------------------------

class ConstraintBaker:
    useCurrentFrame : BoolProperty(
        name = "Current Frame",
        description = "Bake current frame only",
        default = True)

    firstFrame : IntProperty(
        name = "First Frame",
        default = 1)

    lastFrame : IntProperty(
        name = "Last Frame",
        default = 1)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig not in ["mhx", "rigify", "rigify2"])

    def draw(self, context):
        self.layout.prop(self, "useCurrentFrame")
        if self.useCurrentFrame:
            self.layout.prop(context.scene.tool_settings, "use_keyframe_insert_auto")
        else:
            self.layout.prop(self, "firstFrame")
            self.layout.prop(self, "lastFrame")

    def setAuto(self, context):
        self.auto = (context.scene.tool_settings.use_keyframe_insert_auto or not self.useCurrentFrame)

    def insertKeys(self, pb, frame, scale):
        pb.location = clearEpsilon(pb.location, Zero, 1e-3*scale)
        if isinstance(pb, bpy.types.Object):
            pb.rotation_euler = clearEpsilon(pb.rotation_euler, Zero, 1e-3)
        elif pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = clearEpsilon(pb.rotation_quaternion, (1,0,0,0), 1e-3)
        else:
            pb.rotation_euler = clearEpsilon(pb.rotation_euler, Zero, 1e-3)
        pb.scale = clearEpsilon(pb.scale, Zero, 1e-3)
        if self.auto:
            pb.keyframe_insert("location", frame=frame, group=pb.name)
            if isinstance(pb, bpy.types.Object):
                pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)
            elif pb.rotation_mode == 'QUATERNION':
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
            else:
                pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)
            pb.keyframe_insert("scale", frame=frame, group=pb.name)


class DAZ_OT_BakeCopyConstraints(ConstraintBaker, DazPropsOperator):
    bl_idname = "daz.bake_copy_constraints"
    bl_label = "Bake Copy Constraints"
    bl_description = "Bake poses to current rig and\ndisable copy location/rotation constraints"
    bl_options = {'UNDO'}

    useImposeLocks : BoolProperty(
        name = "Impose Locks",
        description = "Impose locks",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useImposeLocks")
        ConstraintBaker.draw(self, context)


    def run(self, context):
        rig = context.object
        gen = None
        scn = context.scene
        self.setAuto(context)
        self.frmats = []
        if self.useCurrentFrame:
            self.storeMatrices(rig)
        else:
            for frame in range(self.firstFrame, self.lastFrame+1):
                scn.frame_set(frame)
                updatePose()
                self.storeMatrices(rig)
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            cns.mute = True
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    cns.mute = True
                    gen = cns.target
        if self.useCurrentFrame:
            self.restoreMatrices(context, rig, self.frmats[0], scn.frame_current)
        else:
            for n,frmat in enumerate(self.frmats):
                frame = self.firstFrame + n
                scn.frame_set(frame)
                self.restoreMatrices(context, rig, frmat, frame)
        if gen:
            gen.hide_set(True)


    def storeMatrices(self, rig):
        wmat = rig.matrix_world.copy()
        mats = [pb.matrix.copy() for pb in rig.pose.bones]
        self.frmats.append((wmat,mats))


    def restoreMatrices(self, context, rig, frmat, frame):
        from .animation import imposeLocks
        wmat,mats = frmat
        setWorldMatrix(rig, wmat)
        updatePose()
        self.insertKeys(rig, frame, rig.DazScale)
        for pb,mat in zip(rig.pose.bones, mats):
            pb.matrix = mat
            if self.useImposeLocks:
                imposeLocks(pb)
            updatePose()
            self.insertKeys(pb, frame, rig.DazScale)

#-------------------------------------------------------------
#   Unbake Constraints
#-------------------------------------------------------------

class DAZ_OT_UnbakeCopyConstraints(ConstraintBaker, DazPropsOperator):
    bl_idname = "daz.unbake_copy_constraints"
    bl_label = "Unbake Copy Constraints"
    bl_description = "Clear poses and enable copy location/rotation constraints"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        gen = None
        scn = context.scene
        self.setAuto(context)
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type.startswith("COPY"):
                    cns.mute = False
                    gen = cns.target
        cns = getConstraint(rig, 'COPY_TRANSFORMS')
        if cns:
            cns.mute = False
            gen = cns.target
        if self.useCurrentFrame:
            self.clearMatrices(context, rig, scn.frame_current)
        else:
            for frame in range(self.firstFrame, self.lastFrame+1):
                scn.frame_set(frame)
                self.clearMatrices(context, rig, frame)
        if gen:
            gen.hide_set(False)


    def clearMatrices(self, context, rig, frame):
        unit = Matrix()
        rig.matrix_world = unit
        self.insertKeys(rig, frame, rig.DazScale)
        for pb in rig.pose.bones:
            pb.matrix_basis = unit
            self.insertKeys(pb, frame, rig.DazScale)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosePreset,
    DAZ_OT_SaveMorphPreset,
    DAZ_OT_BakeCopyConstraints,
    DAZ_OT_UnbakeCopyConstraints,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
