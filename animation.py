# Copyright (c) 2016-2022, Thomas Larsson
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
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .transform import Transform
from .fileutils import MultiFile, SingleFile, DufFile, DazExporter

#-------------------------------------------------------------
#   Alias
#-------------------------------------------------------------

def getAlias(prop, rig):
    if prop in rig.DazAlias.keys():
        return rig.DazAlias[prop].s
    else:
        return prop

#-------------------------------------------------------------
#   Convert between frames and vectors
#-------------------------------------------------------------

def framesToVectors(frames):
    vectors = {}
    for idx in frames.keys():
        for t,y in frames[idx]:
            if t not in vectors.keys():
                vectors[t] = Vector((0,0,0))
            vectors[t][idx] = y
    return vectors


def vectorsToFrames(vectors):
    frames = {}
    for idx in range(3):
        frames[idx] = [[t,vectors[t][idx]] for t in vectors.keys()]
    return frames

#-------------------------------------------------------------
#   Animations
#-------------------------------------------------------------

def extendFcurves(rig, frame0, frame1):
    act = rig.animation_data.action
    if act is None:
        return
    for fcu in act.fcurves:
        if fcu.keyframe_points:
            value = fcu.evaluate(frame0)
            print(fcu.data_path, fcu.array_index, value)
            for frame in range(frame0, frame1):
                fcu.keyframe_points.insert(frame, value, options={'FAST'})


def getChannel(url):
    words = url.split(":")
    if len(words) == 2:
        key = words[0]
    elif len(words) == 3:
        words = words[1].rsplit("/",1)
        if len(words) == 2:
            key = words[1].rsplit("#")[-1]
        else:
            return None,None,None
    else:
        return None,None,None

    words = url.rsplit("?", 2)
    if len(words) != 2:
        return None,None,None
    words = words[1].split("/")
    if len(words) in [2,3]:
        channel = words[0]
        comp = words[1]
        return key,channel,comp
    else:
        return None,None,None

#-------------------------------------------------------------
#   Frame converter class
#-------------------------------------------------------------

class FrameConverter:

    def getConv(self, bones, rig):
        from .figure import getRigType
        from .convert import getConverter, SourceRig
        stype = None
        conv = {}
        twists = {}
        if self.convertPoses:
            stype = SourceRig[self.srcCharacter]
        elif (rig.DazRig == "mhx" or
            rig.DazRig[0:6] == "rigify"):
            stype = "genesis8"
        else:
            stype = getRigType(bones, False)
        if stype:
            print("Auto-detected %s character in duf/dsf file" % stype)
            conv,twists = getConverter(stype, rig)
            if not conv:
                conv = {}
        else:
            print("Could not auto-detect character in duf/dsf file")
        bonemap = OrderedDict()
        return conv, twists, bonemap


    def getRigifyLocks(self, rig, conv):
        locks = []
        if rig.DazRig[0:6] == "rigify":
            for bname in conv.values():
                if (bname in rig.pose.bones.keys() and
                    bname not in ["torso"]):
                    pb = rig.pose.bones[bname]
                    locks.append((pb, tuple(pb.lock_location)))
                    pb.lock_location = (True, True, True)
        return locks


    def convertAnimations(self, anims, rig):
        if rig.type != 'ARMATURE':
            return anims, []
        conv,twists,bonemap = self.getConv(anims[0][0], rig)
        locks = self.getRigifyLocks(rig, conv)

        for banim,vanim in anims:
            bonenames = list(banim.keys())
            bonenames.reverse()
            for bname in bonenames:
                if bname in rig.data.bones.keys():
                    bonemap[bname] = bname
                elif bname in conv.keys():
                    bonemap[bname] = conv[bname]
                else:
                    bonemap[bname] = bname

        nanims = []
        for banim,vanim in anims:
            nbanim = {}
            for bname,frames in banim.items():
                nbanim[bonemap[bname]] = frames
            nanims.append((nbanim,vanim))

        if self.convertPoses:
            self.convertAllFrames(nanims, rig, bonemap)
        return nanims, locks


    def convertAllFrames(self, anims, rig, bonemap):
        from .convert import getCharacter, getParent

        trgCharacter = getCharacter(rig)
        if trgCharacter is None:
            return anims

        restmats = {}
        nrestmats = {}
        transmats = {}
        ntransmats = {}
        xyzs = {}
        nxyzs = {}
        for bname,nname in bonemap.items():
            bparname = getParent(self.srcCharacter, bname)
            self.getMatrices(bname, None, self.srcCharacter, bparname, restmats, transmats, xyzs)
            if nname[0:6] == "TWIST-":
                continue
            if bparname in bonemap.keys():
                nparname = bonemap[bparname]
                if nparname[0:6] == "TWIST-":
                    nparname = nparname[6:]
            elif bparname is None:
                nparname = None
            else:
                continue
            self.getMatrices(nname, rig, trgCharacter, nparname, nrestmats, ntransmats, nxyzs)

        for banim,vanim in anims:
            nbanim = {}
            for bname,nname in bonemap.items():
                if nname in banim.keys() and nname in ntransmats.keys() and bname in transmats.keys():
                    frames = banim[nname]
                    if "rotation" in frames.keys():
                        amat = ntransmats[nname].inverted()
                        bmat = transmats[bname]
                        nframes = self.convertFrames(amat, bmat, xyzs[bname], nxyzs[nname], frames["rotation"])
                        banim[nname]["rotation"] = nframes


    def getMatrices(self, bname, rig, char, parname, restmats, transmats, xyzs):
        from .convert import getOrientation

        orient,xyzs[bname] = getOrientation(char, bname, rig)
        if orient is None:
            return
        restmats[bname] = Euler(Vector(orient)*D, 'XYZ').to_matrix()

        orient = None
        if parname:
            orient,xyz = getOrientation(char, parname, rig)
            if orient:
                parmat = Euler(Vector(orient)*D, 'XYZ').to_matrix()
                transmats[bname] = restmats[bname] @ parmat.inverted()
        if orient is None:
            transmats[bname] = Matrix().to_3x3()


    def convertFrames(self, amat, bmat, xyz, nxyz, frames):
        vecs = framesToVectors(frames)
        nvecs = {}
        for t,vec in vecs.items():
            mat = Euler(vec*D, xyz).to_matrix()
            nmat = amat @ mat @ bmat
            nvecs[t] = Vector(nmat.to_euler(nxyz))/D
        return vectorsToFrames(nvecs)

#-------------------------------------------------------------
#   HideOperator class
#-------------------------------------------------------------

class HideOperator(DazOperator, IsArmature):
    def storeState(self, context):
        from .driver import muteDazFcurves
        DazOperator.storeState(self, context)
        rig = context.object
        amt = rig.data
        if amt.DazSimpleIK:
            amt.DazArmIK_L = amt.DazArmIK_R = amt.DazLegIK_L = amt.DazLegIK_R = 0.0
        self.boneLayers = list(rig.data.layers)
        rig.data.layers = 32*[True]
        self.layerColls = []
        self.obhides = []
        for ob in context.view_layer.objects:
            self.obhides.append((ob, ob.hide_get()))
            ob.hide_set(False)
        self.hideLayerColls(rig, context.view_layer.layer_collection)
        muteDazFcurves(rig, True)


    def hideLayerColls(self, rig, layer):
        if layer.exclude:
            return True
        ok = True
        for ob in layer.collection.objects:
            if ob == rig:
                ok = False
        for child in layer.children:
            ok = (self.hideLayerColls(rig, child) and ok)
        if ok:
            self.layerColls.append(layer)
            layer.exclude = True
        return ok


    def restoreState(self, context):
        from .driver import muteDazFcurves
        DazOperator.restoreState(self, context)
        rig = context.object
        rig.data.layers = self.boneLayers
        for layer in self.layerColls:
            layer.exclude = False
        for ob,hide in self.obhides:
            ob.hide_set(hide)
        muteDazFcurves(rig, rig.DazDriversDisabled)

#-------------------------------------------------------------
#   AnimatorBase class
#-------------------------------------------------------------

class ConvertOptions:
    convertPoses : BoolProperty(
        name = "Convert Poses",
        description = "Attempt to convert poses to the current rig.",
        default = False)

    srcCharacter : EnumProperty(
        items = G.theRestPoseItems,
        name = "Source Character",
        description = "Character this file was made for",
        default = "genesis_3_female")


def getGeograftItems(scn, context):
    enums = [("-", "-", "-")]
    rig = context.object
    for ob in rig.children:
        if ob.DazMesh and ob.type == 'MESH':
            enums += [(key,key,key) for key in ob.data.DazMergedGeografts.keys()]
            return enums
    return enums


class AffectOptions:
    affectBones : BoolProperty(
        name = "Affect Bones",
        description = "Animate bones.",
        default = True)

    affectDrivenBones : BoolProperty(
        name = "Affect Driven Bones",
        description = "Animate bones with a Drv parent",
        default = True)

    affectMorphs : BoolProperty(
        name = "Affect Morphs",
        description = "Animate morph properties",
        default = True)

    onMorphSuffix = 'NONE'

    clearMorphs : BoolProperty(
        name = "Clear Morphs",
        description = "Clear all morph properties before loading new ones",
        default = True)

    affectGeograft : EnumProperty(
        items = getGeograftItems,
        name = "Affect Geograft",
        description = "Add morphs to this merged geograft")

    affectObject : EnumProperty(
        items = [('OBJECT', "Object", "Animate global object transformation"),
                 ('MASTER', "Master Bone", "Object transformations affect master/root bone instead of object.\nOnly for MHX and Rigify"),
                 ('NONE', "None", "Don't animate global object transformations"),
                ],
        name = "Affect Object",
        description = "How to animate global object transformation",
        default = 'OBJECT')

    onMissingMorphs : EnumProperty(
        items = [('IGNORE', "Ignore", "Ignore missing morphs"),
                 ('REPORT', "Report", "Report missing morphs"),
                 ('LOAD_FACE', "Load Face", "Load missing face morphs but not body morphs"),
                 ('LOAD_ALL', "Load All", "Load all missing morphs")],
        name = "Missing Morphs",
        description = "What to do with missing morphs",
        default = 'IGNORE')

    useMakePoseable : BoolProperty(
        name = "Make All Bones Poseable",
        description = "Make all bones poseable after the morphs have been loaded",
        default = False)

    affectSelectedOnly : BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones",
        default = False)

    affectScale : BoolProperty(
        name = "Affect Scale",
        description = "Include bone scale in animation",
        default = False)


class ActionOptions:
    makeNewAction : BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName : StringProperty(
        name = "Action Name",
        description = "Name of loaded action",
        default = "Action")

    fps : FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in Daz Studio",
        default = 30)

    integerFrames : BoolProperty(
        name = "Integer Frames",
        description = "Round all keyframes to intergers",
        default = True)

    atFrameOne : BoolProperty(
        name = "Start At Frame 1",
        description = "Always start actions at frame 1",
        default = True)

    firstFrame : IntProperty(
        name = "First Frame",
        description = "Start import with this frame",
        default = 1)

    lastFrame : IntProperty(
        name = "Last Frame",
        description = "Finish import with this frame",
        default = 250)

    def draw(self, context):
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "fps")
        self.layout.prop(self, "integerFrames")
        self.layout.prop(self, "atFrameOne")
        self.layout.prop(self, "firstFrame")
        self.layout.prop(self, "lastFrame")

    def clearAnimation(self, ob):
        if self.makeNewAction and ob.animation_data:
            ob.animation_data.action = None

    def nameAnimation(self, ob):
        if self.makeNewAction and ob.animation_data:
            act = ob.animation_data.action
            if act:
                act.name = self.actionName


class PoseLibOptions:
    makeNewPoseLib : BoolProperty(
        name = "New Pose Library",
        description = "Unlink current pose library and make a new one",
        default = True)

    poseLibName : StringProperty(
        name = "Pose Library Name",
        description = "Name of loaded pose library",
        default = "PoseLib")

    useAssetBrowser : BoolProperty(
        name = "Asset Browser",
        description = "Create asset browser library",
        default = True)


class AnimatorBase(MultiFile, FrameConverter, ConvertOptions, AffectOptions, IsMeshArmature):
    filename_ext = ".duf"
    filter_glob : StringProperty(default = G.theDazDefaults + G.theImagedDefaults, options={'HIDDEN'})
    lockMeshes = False

    def __init__(self):
        pass

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "affectBones")
        if self.affectBones:
            layout.prop(self, "affectScale")
            layout.prop(self, "affectSelectedOnly")
            layout.prop(self, "affectDrivenBones")
        layout.label(text="Object Transformations Affect:")
        layout.prop(self, "affectObject", expand=True)
        layout.prop(self, "affectMorphs")
        if self.affectMorphs:
            layout.prop(self, "clearMorphs")
            layout.prop(self, "affectGeograft")
            layout.prop(self, "onMissingMorphs")
            if self.onMissingMorphs == 'LOAD_ALL':
                layout.prop(self, "useMakePoseable")
        layout.prop(self, "convertPoses")
        if self.convertPoses:
            layout.prop(self, "srcCharacter")


    def getSingleAnimation(self, filepath, context, offset):
        from .load_json import loadJson
        if filepath is None:
            return offset,None
        ext = os.path.splitext(filepath)[1]
        if ext in [".duf", ".dsf"]:
            struct = loadJson(filepath, False)
        else:
            raise DazError("Wrong type of file: %s" % filepath)
        if "scene" not in struct.keys():
            return offset,None
        animations = self.parseScene(struct["scene"])
        rig = context.object
        if rig.type == 'ARMATURE':
            setMode('POSE')
            self.prepareRig(rig)
        self.clearPose(rig, offset)
        animations,locks = self.convertAnimations(animations, rig)
        prop = None
        result = self.animateBones(context, animations, offset, prop, filepath)
        for pb,lock in locks:
            pb.lock_location = lock
        updateDrivers(rig)
        setMode('OBJECT')
        self.mergeHipObject(rig)
        return result

    def clearAnimation(self, ob):
        pass

    def nameAnimation(self, ob):
        pass

    def prepareRig(self, rig):
        if not self.affectBones:
            return
        if rig.DazRig == "rigify":
            from .rigify import setFkIk1
            self.boneLayers = setFkIk1(rig, False, self.boneLayers)
        elif rig.DazRig == "rigify2":
            from .rigify import setFkIk2
            self.boneLayers = setFkIk2(rig, True, self.boneLayers)
        elif rig.MhxRig or rig.DazRig == "mhx":
            from .mhx import setToFk
            self.boneLayers = setToFk(rig, self.boneLayers)


    def parseScene(self, struct):
        animations = []
        bones = {}
        values = {}
        animations.append((bones, values))
        self.parseAnimations(struct, bones, values)
        self.completeAnimations(bones)
        return animations


    def parseAnimations(self, struct, bones, values):
        if "animations" in struct.keys():
            for anim in struct["animations"]:
                if "url" in anim.keys():
                    key,channel,comp = getChannel(anim["url"])
                    if channel is None:
                        continue
                    elif channel == "value":
                        if self.affectMorphs:
                            values[key] = getAnimKeys(anim)
                    elif channel in ["translation", "rotation", "scale"]:
                        if key not in bones.keys():
                            bone = bones[key] = {
                                "translation" : {},
                                "rotation" : {},
                                "scale" : {},
                                "general_scale" : {},
                                }
                        idx = getIndex(comp)
                        if idx >= 0:
                            bones[key][channel][idx] = getAnimKeys(anim)
                        else:
                            bones[key]["general_scale"][0] = getAnimKeys(anim)
                    else:
                        print("Unknown channel:", channel)
        elif "extra" in struct.keys():
            for extra in struct["extra"]:
                if extra["type"] == "studio/scene_data/aniMate":
                    msg = ("Animation with aniblocks.\n" +
                           "In aniMate Lite tab, right-click         \n" +
                           "and Bake To Studio Keyframes.")
                    print(msg)
                    raise DazError(msg)
        elif self.verbose:
            print("No animations in this file")


    def completeAnimations(self, bones):
        def addMissing(t, y, y0, miss, anim):
            if miss:
                if y0 is None:
                    for t1 in miss:
                        anim.append((t1,y))
                else:
                    k = (y-y0)/(t-t0)
                    for t1 in miss:
                        y1 = y0 + k*(t1-t0)
                        anim.append((t1,y1))

        frames = {}
        for bname in bones.keys():
            for channel in bones[bname].keys():
                for idx in bones[bname][channel].keys():
                    for t,y in bones[bname][channel][idx]:
                        frames[t] = True
        if not frames:
            return
        frames = list(frames)
        frames.sort()
        for bname in bones.keys():
            for channel in bones[bname].keys():
                for idx,anim in bones[bname][channel].items():
                    if len(anim) == len(frames):
                        continue
                    kpts = dict(anim)
                    anim = []
                    miss = []
                    t0 = 0.0
                    y0 = None
                    for t in frames:
                        if t in kpts.keys():
                            y = kpts[t]
                            addMissing(t, y, y0, miss, anim)
                            anim.append((t,y))
                            miss = []
                            t0 = t
                            y0 = y
                        else:
                            miss.append(t)
                    if miss:
                        y = anim[-1][1]
                        for t1 in miss:
                            anim.append((t1,y))
                    bones[bname][channel][idx] = anim


    def isAvailable(self, pb, rig):
        if (pb.parent and
              isDrvBone(pb.parent.name) and
              not self.affectDrivenBones):
            return False
        elif (pb.name == self.getMasterBone(rig) and
              self.affectObject != 'MASTER'):
            return False
        elif self.affectSelectedOnly:
            if pb.bone.select:
                for rlayer,blayer in zip(self.boneLayers, pb.bone.layers):
                    if rlayer and blayer:
                        return True
            return False
        else:
            return True


    def getMasterBone(self, rig):
        if rig.DazRig == "mhx":
            return "master"
        elif rig.DazRig[0:6] == "rigify":
            return "root"
        else:
            return None


    def clearPose(self, rig, frame):
        self.worldMatrix = rig.matrix_world.copy()
        tfm = Transform()
        if self.affectObject == 'OBJECT':
            if not self.affectScale:
                tfm.setScale(rig.scale, False)
            tfm.setRna(rig)
            if self.useInsertKeys:
                tfm.insertKeys(rig, None, frame, rig.name, self)
        if rig.type != 'ARMATURE':
            return
        if self.affectBones:
            for pb in rig.pose.bones:
                if self.isAvailable(pb, rig):
                    scale = pb.scale.copy()
                    pb.matrix_basis = Matrix()
                    if not self.affectScale:
                        pb.scale = scale
                    if self.useInsertKeys:
                        tfm.insertKeys(rig, pb, frame, pb.name, self)
            setChildofInverses(rig)
        if self.affectMorphs and self.clearMorphs:
            from .morphing import getAllLowerMorphNames
            lprops = getAllLowerMorphNames(rig)
            for prop in rig.keys():
                if (prop.lower() in lprops and
                    isinstance(rig[prop], float)):
                    rig[prop] = 0.0
                    if self.useInsertKeys:
                        rig.keyframe_insert(propRef(prop), frame=frame, group=prop)

    KnownRigs = [
        "Genesis",
        "GenesisFemale",
        "GenesisMale",
        "Genesis2",
        "Genesis2Female",
        "Genesis2Male",
        "Genesis3",
        "Genesis3Female",
        "Genesis3Male",
    ]

    def animateBones(self, context, animations, offset, prop, filepath):
        rig = context.object
        errors = {}
        for banim,vanim in animations:
            frames = {}
            n = -1
            for bname, channels in banim.items():
                for key,channel in channels.items():
                    if key in ["rotation", "translation"]:
                        self.addFrames(bname, channel, 3, key, frames, default=(0,0,0))
                    elif key == "scale" and self.affectScale:
                        self.addFrames(bname, channel, 3, key, frames, default=(1,1,1))
                    elif key == "general_scale" and self.affectScale:
                        self.addFrames(bname, channel, 1, key, frames)

            for vname, channels in vanim.items():
                self.addFrames(vname, {0: channels}, 1, "value", frames)

            if not frames:
                continue
            lframes = list(frames.items())
            lframes.sort()
            self.clearScales(rig, lframes[0][0]+offset)
            for n,frame in lframes:
                twists = []
                for bname in frame.keys():
                    bframe = frame[bname]
                    tfm = Transform()
                    value = 0.0
                    for key in bframe.keys():
                        if key == "translation":
                            tfm.setTrans(bframe["translation"], prop)
                        elif key == "rotation":
                            tfm.setRot(bframe["rotation"], prop)
                        elif key == "scale":
                            if self.affectScale:
                                tfm.setScale(bframe["scale"], False, prop)
                        elif key == "general_scale":
                            if self.affectScale:
                                tfm.setGeneral(bframe["general_scale"], False, prop)
                        elif key == "value":
                            value = bframe["value"][0]
                        else:
                            print("Unknown key:", bname, key)

                    if (bname == "@selection" or
                        bname in self.KnownRigs):
                        master = self.getMasterBone(rig)
                        if self.affectObject == 'NONE':
                            pass
                        elif (self.affectObject == 'MASTER' and
                              master and
                              master in rig.pose.bones.keys()):
                            self.transformBone(rig, master, tfm, value, n, offset, False)
                        else:
                            if not self.affectScale:
                                tfm.setScale(rig.scale, False)
                            tfm.setRna(rig)
                            if self.useInsertKeys:
                                tfm.insertKeys(rig, None, n+offset, rig.name, self)
                    elif rig.type != 'ARMATURE':
                        continue
                    elif bname in rig.data.bones.keys():
                        self.transformBone(rig, bname, tfm, value, n, offset, False)
                    elif bname[0:6] == "TWIST-":
                        twists.append((bname[6:], tfm, value))
                    elif "value" in bframe.keys():
                        if self.affectMorphs:
                            key = self.getRigKey(bname, rig, value)
                            if key:
                                oldval = rig[key]
                                if isinstance(oldval, int):
                                    value = int(value)
                                elif isinstance(oldval, float):
                                    value = float(value)
                                rig[key] = value
                                if self.useInsertKeys:
                                    rig.keyframe_insert(propRef(key), frame=n+offset, group="Morphs")

                for (bname, tfm, value) in twists:
                    self.transformBone(rig, bname, tfm, value, n, offset, True)

                if ((rig.DazRig == "mhx" or rig.MhxRig) and self.affectBones and False):
                    for suffix in ["L", "R"]:
                        forearm = rig.pose.bones["forearm.fk."+suffix]
                        hand = rig.pose.bones["hand.fk."+suffix]
                        foot = rig.pose.bones["foot.fk."+suffix]
                        hand.location = foot.location = Zero
                        self.fixForearmFollow("MhaForearmFollow_" + suffix, rig, hand, forearm)
                        if self.useInsertKeys:
                            tfm.insertKeys(rig, forearm, n+offset, forearm.name, self)
                            tfm.insertKeys(rig, hand, n+offset, hand.name, self)
                            tfm.insertKeys(rig, foot, n+offset, foot.name, self)

                self.saveScales(rig, n+offset)

            self.fixScales(rig)
            self.addToPoseLib(rig, filepath)
            offset += n + 1
        return offset,prop


    def addToPoseLib(self, rig, filepath):
        pass


    def fixForearmFollow(self, prop, rig, hand, forearm):
        if "MhaForearmsFollow" in rig.data.keys():
            fix = rig.data["MhaForearmsFollow"]
        elif prop in rig.data.key():
            fix = rig.data[prop]
        else:
            fix = True
        if fix:
            hand.rotation_euler[1] = forearm.rotation_euler[1]
            forearm.rotation_euler[1] = 0


    def addFrames(self, bname, channel, nmax, cname, frames, default=None):
        for comp in range(nmax):
            if comp not in channel.keys():
                continue
            for t,y in channel[comp]:
                n = t*LS.fps
                if LS.integerFrames:
                    n = int(round(n))
                if n < self.firstFrame-1:
                    continue
                if n >= self.lastFrame:
                    break
                if n not in frames.keys():
                    frame = frames[n] = {}
                else:
                    frame = frames[n]
                if bname not in frame.keys():
                    bframe = frame[bname] = {}
                else:
                    bframe = frame[bname]
                if cname == "value":
                    bframe[cname] = {0: y}
                elif nmax == 1:
                    bframe[cname] = y
                elif nmax == 3:
                    if cname not in bframe.keys():
                        bframe[cname] = Vector(default)
                    bframe[cname][comp] = y


    def clearScales(self, rig, frame):
        if not self.affectScale:
            return
        self.scales = {}
        for pb in rig.pose.bones:
            if self.isAvailable(pb, rig):
                pb.scale = One
                if self.useInsertKeys:
                    pb.keyframe_insert("scale", frame=frame, group=pb.name)


    def saveScales(self, rig, frame):
        if not self.affectScale:
            return
        self.scales[frame] = dict([(pb.name, Matrix.Diagonal(pb.scale)) for pb in rig.pose.bones])


    def fixScales(self, rig):
        if not self.affectScale:
            return
        for frame,smats in self.scales.items():
            for pb in rig.pose.bones:
                if pb.parent and inheritScale(pb) and self.isAvailable(pb, rig):
                    smat = smats[pb.name] @ smats[pb.parent.name].inverted()
                    pb.scale = smat.to_scale()
                    if self.useInsertKeys:
                        pb.keyframe_insert("scale", frame=frame, group=pb.name)


    def getRigKey(self, key, rig, value):
        prop = unquote(key)
        if self.affectGeograft != "-":
            prop2 = "%s:%s" % (prop, self.affectGeograft)
            if prop2 in rig.keys():
                return prop2
        if prop in rig.keys():
            return prop
        if prop in self.alias.keys():
            prop = self.alias[prop]
            if prop in rig.keys():
                return prop
        if prop not in self.missing.keys():
            self.missing[prop] = float(value)
            if self.onMissingMorphs in ['LOAD_FACE', 'LOAD_ALL']:
                rig[prop] = float(value)
                return prop
        return None


    def transformBone(self, rig, bname, tfm, value, n, offset, useTwist):
        from .node import setBoneTransform, setBoneTwist
        from .driver import isFaceBoneDriven

        if not self.affectBones:
            return
        pb = rig.pose.bones[bname]
        if self.isAvailable(pb, rig):
            if useTwist:
                setBoneTwist(tfm, pb)
            else:
                if not self.affectScale:
                    tfm.setScale(pb.scale, False)
                setBoneTransform(tfm, pb)
                self.imposeLocks(pb)
            if self.useInsertKeys:
                tfm.insertKeys(rig, pb, n+offset, bname, self)
        else:
            pass


    def imposeLocks(self, pb):
        for n in range(3):
            if pb.lock_location[n]:
                pb.location[n] = 0
            if pb.lock_scale[n]:
                pb.scale[n] = 1
        if pb.rotation_mode == 'QUATERNION':
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_quaternion[n+1] = 0
        else:
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_euler[n] = 0


    def mergeHipObject(self, rig):
        if self.affectObject == 'MASTER' and self.affectBones:
            master = self.getMasterBone(rig)
            if master in rig.pose.bones.keys():
                pb = rig.pose.bones[master]
                wmat = rig.matrix_world.copy()
                setWorldMatrix(rig, self.worldMatrix)
                pb.matrix_basis = self.worldMatrix.inverted() @ wmat


    def findDrivers(self, rig):
        driven = {}
        if (rig.animation_data and
            rig.animation_data.drivers):
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (words[0] == "pose.bones[" and
                    words[2] not in ["].constraints[", "].HdOffset", "].TlOffset"]):
                    driven[words[1]] = True
        self.driven = list(driven.keys())

#-------------------------------------------------------------
#
#-------------------------------------------------------------


def getAnimKeys(anim):
    return [key[0:2] for key in anim["keys"]]


class StandardAnimation:

    def run(self, context):
        from time import perf_counter
        scn = context.scene
        rig = context.object
        if scn.tool_settings.use_keyframe_insert_auto:
            self.useInsertKeys = True
        else:
            self.useInsertKeys = self.useAction
        self.loadAnimation(context)
        hasError = False
        if self.missing:
            if self.onMissingMorphs == 'REPORT':
                missing = list(self.missing.keys())
                missing.sort()
                print("Missing morphs:\n  %s" % missing)
                hasError = True
            elif self.onMissingMorphs in ['LOAD_FACE', 'LOAD_ALL']:
                self.unfound = []
                self.loadMissingMorphs(context, rig)
                if self.unfound:
                    print("Missing morphs not found:\n  %s" % self.unfound)
                    hasError = True
            if self.useMakePoseable and self.onMissingMorphs == 'LOAD_ALL':
                print("Make all bones poseable")
                bpy.ops.daz.make_all_bones_poseable()
                print("Reloading animation")
                self.loadAnimation(context)
        if hasError:
            raise DazError(
                "Animation loaded but some morphs were missing.     \n"+
                "See list in terminal window.", warning=True)


    def loadAnimation(self, context):
        rig = context.object
        scn = context.scene
        if not self.affectSelectedOnly:
            selected = self.selectAll(rig, True)
        LS.forAnimation(self, rig)
        self.findDrivers(rig)
        self.clearAnimation(rig)
        self.missing = {}
        self.alias = dict([(getAlias(prop, rig), prop) for prop in rig.keys()])
        startframe = offset = scn.frame_current
        props = []
        t1 = perf_counter()
        print("\n--------------------")

        dazfiles = self.getMultiFiles(G.theDazExtensions)
        nfiles = len(dazfiles)
        if nfiles == 0:
            raise DazError("No corresponding DAZ file selected")
        self.verbose = (nfiles == 1)

        for filepath in dazfiles:
            if self.atFrameOne and len(dazfiles) == 1:
                offset = 1
            print("*", os.path.basename(filepath), offset)
            offset,prop = self.getSingleAnimation(filepath, context, offset)
            if prop:
                props.append(prop)

        t2 = perf_counter()
        print("File %s imported in %.3f seconds" % (self.filepath, t2-t1))
        scn.frame_current = startframe
        self.nameAnimation(rig)
        if not self.affectSelectedOnly:
            self.selectAll(rig, selected)


    def selectAll(self, rig, select):
        if rig.type != 'ARMATURE':
            return
        selected = []
        for bone in rig.data.bones:
            if bone.select:
                selected.append(bone.name)
            if select == True:
                bone.select = True
            else:
                bone.select = (bone.name in select)
        return selected


    def loadMissingMorphs(self, context, rig):
        global theMorphTables
        if rig.DazId in theMorphTables.keys():
            table = theMorphTables[rig.DazId]
        else:
            table = theMorphTables[rig.DazId] = self.setupMorphTable(rig)
        namepathTable = {}
        for mname in self.missing.keys():
            lname = mname.lower()
            if lname in table.keys():
                path,morphset = table[lname]
                if morphset not in namepathTable.keys():
                    namepathTable[morphset] = []
                namepathTable[morphset].append((mname, path, morphset))
            else:
                self.unfound.append(mname)

        from .morphing import CustomMorphLoader, StandardMorphLoader
        for morphset in namepathTable.keys():
            if ((self.onMissingMorphs == 'LOAD_FACE' and morphset not in ["Body","Custom"]) or
                (self.onMissingMorphs == 'LOAD_ALL' and morphset != "Custom")):
                mloader = StandardMorphLoader()
                mloader.morphset = morphset
                mloader.category = ""
                mloader.hideable = True
                print("\nLoading missing %s morphs" % morphset)
                mloader.getAllMorphs(namepathTable[morphset], context, True)
        if "Custom" in namepathTable.keys():
            customs = {}
            for namepath in namepathTable["Custom"]:
                mname,path,morphset = namepath
                folder = os.path.dirname(path)
                cat = os.path.split(folder)[-1]
                if cat not in customs.keys():
                    customs[cat] = []
                customs[cat].append(namepath)
            for cat, namepaths in customs.items():
                mloader = CustomMorphLoader()
                rig.DazCustomMorphs = True
                mloader.morphset = "Custom"
                mloader.category = cat
                mloader.hideable = True
                print("\nLoading morphs in category %s" % cat)
                mloader.getAllMorphs(namepaths, context, True)
        for mname,value in self.missing.items():
            rig[mname] = value


    def setupMorphTable(self, rig):
        def setupTable(folder, table, mtypes):
            for file in os.listdir(folder):
                path = os.path.join(folder, file)
                if os.path.isdir(path):
                    setupTable(path, table, mtypes)
                elif file[0:5] != "alias":
                    words = os.path.splitext(file)
                    if words[-1] in [".dsf", ".duf"]:
                        mname = words[0].lower()
                        if file in mtypes.keys():
                            morphset = mtypes[file]
                        else:
                            morphset = "Custom"
                        table[mname] = (path, morphset)
                        if mname[0:5] == "pctrl":
                            table[mname[1:]] = (path, morphset)
                        elif mname[0:4] == "ctrl":
                            table["p%s" % mname] = (path, morphset)

        from .fileutils import getFolders
        from .morphing import getMorphPaths
        folders = getFolders(rig, ["Morphs/", ""])
        table = {}
        mpaths = getMorphPaths(rig.DazMesh)
        mtypes = {}
        if mpaths:
            for morphset,paths in mpaths.items():
                for path in paths:
                    mtypes[os.path.basename(path)] = morphset
        print("Setting up morph table for %s" % rig.DazMesh)
        for folder in folders:
            setupTable(folder, table, mtypes)
        return table

theMorphTables = {}

#-------------------------------------------------------------
#   Import Node Pose
#-------------------------------------------------------------

class NodePose:
    def parseAnimations(self, struct, bones, values):
        if "nodes" in struct.keys() and self.affectBones:
            for node in struct["nodes"]:
                key = node["id"]
                self.addTransform(node, "translation", bones, key)
                self.addTransform(node, "rotation", bones, key)
                self.addTransform(node, "scale", bones, key)
                #self.addTransform(node, "general_scale", bones, key)
        elif self.verbose:
            print("No nodes in this file")
        if "modifiers" in struct.keys() and self.affectMorphs:
            for mod in struct["modifiers"]:
                key = mod.get("id")
                channel = mod.get("channel")
                if key and channel:
                    value = channel.get("current_value")
                    if value is not None:
                        values[key] = [[0, value]]


    def addTransform(self, node, channel, bones, key):
        if channel in node.keys():
            if key not in bones.keys():
                bone = bones[key] = {}
            else:
                bone = bones[key]
            if channel not in bone.keys():
                bone[channel] = {}
            for struct in node[channel]:
                comp = struct["id"]
                value = struct["current_value"]
                bone[channel][getIndex(comp)] = [[0, value]]

#-------------------------------------------------------------
#   Import Action
#-------------------------------------------------------------

class ActionBase(ActionOptions, AnimatorBase):
    verbose = False
    useAction = True
    usePoseLib = False

    def draw(self, context):
        AnimatorBase.draw(self, context)
        ActionOptions.draw(self, context)


class DAZ_OT_ImportAction(HideOperator, ActionBase, StandardAnimation):
    bl_idname = "daz.import_action"
    bl_label = "Import Action"
    bl_description = "Import poses from DAZ pose preset file(s) to action"
    bl_options = {'UNDO', 'PRESET'}

    def run(self, context):
        StandardAnimation.run(self, context)

#-------------------------------------------------------------
#   Import Poselib
#-------------------------------------------------------------

class PoselibBase(PoseLibOptions, AnimatorBase):
    verbose = False
    useAction = False
    usePoseLib = True
    atFrameOne = False
    firstFrame = -1000
    lastFrame = 1000

    usePreviewImages : BoolProperty(
        name = "Import Previews",
        description = "Import preview images for imported poses",
        default = False)

    assetTags : StringProperty(
        name = "Tags",
        description = "List of tags to add to the imported Poses",
        default = "")

    assetAuthor : StringProperty(
        name = "Author",
        description = "Name of the Author",
        default = "")

    assetDescription : StringProperty(
        name = "Description",
        description = "Description to add to all Poses",
        default = "")

    def draw(self, context):
        AnimatorBase.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "makeNewPoseLib")
        if self.makeNewPoseLib:
            self.layout.prop(self, "poseLibName")
        if bpy.app.version >= (3,0,0):
            self.layout.prop(self, "useAssetBrowser")
            self.layout.prop(self, "usePreviewImages")
            self.layout.prop(self, "assetTags")
            self.layout.prop(self, "assetAuthor")
            self.layout.prop(self, "assetDescription")


    def clearAnimation(self, ob):
        if self.makeNewPoseLib:
            if bpy.app.version >= (3,0,0) and self.useAssetBrowser:
                pass
                #bpy.ops.asset.catalog_new(parent_path='')
            elif ob.pose_library:
                ob.pose_library = None


    def nameAnimation(self, ob):
        if self.makeNewPoseLib:
            if bpy.app.version >= (3,0,0) and self.useAssetBrowser:
                pass
            elif ob.pose_library:
                ob.pose_library.name = self.poseLibName


    def addToPoseLib(self, rig, filepath):
        name = os.path.splitext(os.path.basename(filepath))[0]
        if bpy.app.version >= (3,0,0) and self.useAssetBrowser:
            bpy.ops.poselib.create_pose_asset(pose_name=name, activate_new_action=True)
            act = rig.animation_data.action
            if self.usePreviewImages:
                previewFile = self.getPreviewFile(filepath, name)
                if previewFile:
                    bpy.ops.ed.lib_id_load_custom_preview({"id": act}, filepath=previewFile)
                else:
                    act.asset_generate_preview()
            else:
                act.asset_generate_preview()
            if self.assetTags:
                tagList=self.assetTags.split(",")
                for newTag in tagList:
                    act.id_data.asset_data.tags.new(newTag)
            if self.assetAuthor:
                act.id_data.asset_data.author=self.assetAuthor
            if self.assetDescription:
                act.id_data.asset_data.description=self.assetDescription
        else:
            if rig.pose_library:
                pmarkers = rig.pose_library.pose_markers
                frame = 0
                for pmarker in pmarkers:
                    if pmarker.frame >= frame:
                        frame = pmarker.frame + 1
            else:
                frame = 0
            bpy.ops.poselib.pose_add(frame=frame)
            pmarker = rig.pose_library.pose_markers.active
            pmarker.name = name


    def getPreviewFile(self, filepath, name):
        basename3,ext3 = os.path.splitext(filepath)
        for path in ["%s.tip.png" % basename3, "%s.png" % filepath, "%s.png" % basename3]:
            if os.path.exists(path):
                return path
        print("No preview file found for %s" % name)


class DAZ_OT_ImportPoseLib(HideOperator, PoselibBase, StandardAnimation):
    bl_idname = "daz.import_poselib"
    bl_label = "Import Pose Library"
    bl_description = "Import poses from DAZ pose preset file(s) to pose library"
    bl_options = {'UNDO', 'PRESET'}

    def run(self, context):
        StandardAnimation.run(self, context)

#-------------------------------------------------------------
#   Import Single Pose
#-------------------------------------------------------------

class PoseBase(AnimatorBase):
    verbose = False
    useAction = False
    usePoseLib = False
    atFrameOne = False
    firstFrame = -1000
    lastFrame = 1000


class DAZ_OT_ImportPose(HideOperator, PoseBase, StandardAnimation):
    bl_idname = "daz.import_pose"
    bl_label = "Import Pose"
    bl_description = "Import a pose from DAZ pose preset file(s)"
    bl_options = {'UNDO', 'PRESET'}

    def draw(self, context):
        PoseBase.draw(self, context)
        toolset = context.scene.tool_settings
        self.layout.prop(toolset, "use_keyframe_insert_auto")

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportNodePose(HideOperator, NodePose, PoseBase, StandardAnimation):
    bl_idname = "daz.import_node_pose"
    bl_label = "Import Pose From Scene"
    bl_description = "Import a pose from DAZ scene file(s) (not pose preset files)"
    bl_options = {'UNDO', 'PRESET'}

    def draw(self, context):
        PoseBase.draw(self, context)
        toolset = context.scene.tool_settings
        self.layout.prop(toolset, "use_keyframe_insert_auto")

    def run(self, context):
        StandardAnimation.run(self, context)

    def parseAnimations(self, struct, bones, values):
        NodePose.parseAnimations(self, struct, bones, values)

#-------------------------------------------------------------
#   Save current frame
#-------------------------------------------------------------

def actionFrameName(ob, frame):
    return ("%s_%s" % (ob.name, frame))


def findAction(aname):
    for act in bpy.data.actions:
        if act.name == aname:
            return act
    return None


#----------------------------------------------------------
#   Clear pose
#----------------------------------------------------------

class DAZ_OT_ClearPose(DazOperator, IsMeshArmature):
    bl_idname = "daz.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Clear all bones and object transformations"
    bl_options = {'UNDO'}

    def run(self, context):
        from .morphing import getRigFromObject
        rig = getRigFromObject(context.object)
        unit = Matrix()
        setWorldMatrix(rig, unit)
        for pb in rig.pose.bones:
            pb.matrix_basis = unit
        setChildofInverses(rig)


def setChildofInverses(rig):
    for pb in rig.pose.bones:
        for cns in pb.constraints:
            if cns.type == 'CHILD_OF':
                rig.data.bones.active = pb.bone
                print("SET INV", pb.name, cns.name)
                bpy.ops.constraint.childof_set_inverse(constraint=cns.name, owner='BONE')
                print("DONE")

#----------------------------------------------------------
#   Prune action
#----------------------------------------------------------

def pruneAction(act, cm):
    def matchAll(kpts, default, eps):
        for kp in kpts:
            if abs(kp.co[1] - default) > eps:
                return False
        return True

    deletes = []
    for fcu in act.fcurves:
        kpts = fcu.keyframe_points
        channel = fcu.data_path.rsplit(".", 1)[-1]
        if len(kpts) == 0:
            deletes.append(fcu)
        else:
            default = 0
            eps = 0
            if channel == "scale":
                default = 1
                eps = 0.001
            elif (channel == "rotation_quaternion" and
                fcu.array_index == 0):
                default = 1
                eps = 1e-4
            elif channel == "rotation_quaternion":
                eps = 1e-4
            elif channel == "rotation_euler":
                eps = 1e-4
            elif channel == "location":
                eps = 0.001*cm
            if matchAll(kpts, default, eps):
                deletes.append(fcu)

    for fcu in deletes:
        act.fcurves.remove(fcu)


class DAZ_OT_PruneAction(DazOperator):
    bl_idname = "daz.prune_action"
    bl_label = "Prune Action"
    bl_description = "Remove F-curves with zero keys only"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.animation_data and ob.animation_data.action)

    def run(self, context):
        ob = context.object
        pruneAction(ob.animation_data.action, ob.DazScale)

#----------------------------------------------------------
#   Save pose preset
#----------------------------------------------------------

class FakeCurve:
    def __init__(self, value):
        self.value = value

    def evaluate(self, frame):
        return self.value


class DAZ_OT_SavePosePreset(HideOperator, DazExporter, SingleFile, DufFile, FrameConverter, IsArmature):
    bl_idname = "daz.save_pose_preset"
    bl_label = "Save Pose Preset"
    bl_description = "Save the active action as a pose preset,\nto be used in DAZ Studio"
    bl_options = {'UNDO', 'PRESET'}

    convertPoses = False

    useAction : BoolProperty(
        name = "Use Action",
        description = "Import action instead of single pose",
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
        self.alias = dict([(prop, getAlias(prop, rig)) for prop in rig.keys()])
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
        return (isLocationUnlocked(pb) and
                bname not in ["lHand", "rHand", "lFoot", "rFoot"])


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

        Fn = rig.matrix_local.inverted() @ self.Z
        self.F[""] = Fn
        self.Finv[""] = Fn.inverted()

        for pb in rig.pose.bones:
            bone = pb.bone
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


    def setupFrames(self, rig):
        self.Ls = {}
        for frame in range(self.first, self.last+1):
            L = self.Ls[frame] = {}
            smats = {}

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
            mat.col[3][0:3] = loc
            L[""] = self.Finv[""] @ mat @ self.F[""]

            for pb in rig.pose.bones:
                for bname in self.getBoneNames(pb.name):
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
                        continue

                    if self.useScale and bname in self.scales.keys():
                        scale = pb.scale.copy()
                        for idx,fcu in enumerate(self.scales[bname]):
                            if fcu:
                                scale[idx] = fcu.evaluate(frame)
                        smat = Matrix.Diagonal(scale)
                        if (pb.parent and
                            pb.parent.name in smats.keys() and
                            inheritScale(pb)):
                            psmat = smats[pb.parent.name]
                            smat = smat @ psmat
                        mat = mat @ smat.to_4x4()
                        smats[pb.name] = smat

                    if bname in self.locs.keys():
                        loc = pb.location.copy()
                        for idx,fcu in enumerate(self.locs[bname]):
                            if fcu:
                                loc[idx] = fcu.evaluate(frame)
                        mat.col[3][0:3] = loc
                    L[bname] = self.Finv[bname] @ mat @ self.F[bname]


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
        conv,twists,bonemap = self.getConv(rig, rig)
        self.conv = {}
        self.twists = []
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
                from .mhx import L_CUSTOM
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
        else:
            return []


    def getTwistBone(self, bname):
        if "TWIST-" + bname in self.conv.keys():
            twidxs = {
                "lShldrTwist" : 0,
                "lForearmTwist" : 0,
                "lThighTwist" : 1,
                "rShldrTwist" : 0,
                "rForearmTwist" : 0,
                "rThighTwist" : 1,
            }
            twname = self.conv["TWIST-" + bname][0]
            return twname, twidxs[twname]
        else:
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
        if general:
            anim = {}
            anim["url"] = "name://@selection/%s:?scale/general/value" % bname
            scales = [vec[0] for vec in vecs]
            self.addKeys(scales, anim, 1e-4)
            anims.append(anim)
        else:
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "name://@selection/%s:?scale/%s/value" % (bname, x)
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

#----------------------------------------------------------
#   Bake to FK
#----------------------------------------------------------

class DAZ_OT_BakeToFkRig(HideOperator):
    bl_idname = "daz.bake_pose_to_fk_rig"
    bl_label = "Bake Pose To FK Rig"
    bl_description = "Bake pose to the FK rig before saving pose preset.\nIK arms and legs must be baked separately"
    bl_options = {'UNDO'}

    BakeBones = {
        "rigify2" : {
            "chest" : ["spine_fk.001", "spine_fk.002", "spine_fk.003", "spine_fk.004"],
            "thumb.01_master.L" : ["thumb.02.L", "thumb.03.L"],
            "f_index.01_master.L" : ["f_index.01.L", "f_index.02.L", "f_index.03.L"],
            "f_middle.01_master.L" : ["f_middle.01.L", "f_middle.02.L", "f_middle.03.L"],
            "f_ring.01_master.L" : ["f_ring.01.L", "f_ring.02.L", "f_ring.03.L"],
            "f_pinky.01_master.L" : ["f_pinky.01.L", "f_pinky.02.L", "f_pinky.03.L"],
            "thumb.01_master.R" : ["thumb.02.R", "thumb.03.R"],
            "f_index.01_master.R" : ["f_index.01.R", "f_index.02.R", "f_index.03.R"],
            "f_middle.01_master.R" : ["f_middle.01.R", "f_middle.02.R", "f_middle.03.R"],
            "f_ring.01_master.R" : ["f_ring.01.R", "f_ring.02.R", "f_ring.03.R"],
            "f_pinky.01_master.R" : ["f_pinky.01.R", "f_pinky.02.R", "f_pinky.03.R"],
        },
        "mhx" : {
            "back" : ["spine", "spine-1", "chest", "chest-1"],
            "neckhead" : ["neck", "neck-1", "head"],
            "thumb.L" : ["thumb.02.L", "thumb.03.L"],
            "index.L" : ["f_index.01.L", "f_index.02.L", "f_index.03.L"],
            "middle.L" : ["f_middle.01.L", "f_middle.02.L", "f_middle.03.L"],
            "ring.L" : ["f_ring.01.L", "f_ring.02.L", "f_ring.03.L"],
            "pinky.L" : ["f_pinky.01.L", "f_pinky.02.L", "f_pinky.03.L"],
            "thumb.R" : ["thumb.02.R", "thumb.03.R"],
            "index.R" : ["f_index.01.R", "f_index.02.R", "f_index.03.R"],
            "middle.R" : ["f_middle.01.R", "f_middle.02.R", "f_middle.03.R"],
            "ring.R" : ["f_ring.01.R", "f_ring.02.R", "f_ring.03.R"],
            "pinky.R" : ["f_pinky.01.R", "f_pinky.02.R", "f_pinky.03.R"],
        },
    }

    def run(self, context):
        rig = context.object
        scn = context.scene
        if rig.DazRig in self.BakeBones.keys():
            self.bones = {}
            for baker,baked in self.BakeBones[rig.DazRig].items():
                self.getBones(rig, baker, baked)
            if rig.animation_data and rig.animation_data.action:
                act = rig.animation_data.action
                self.removeFromAction(act, rig)
                first,last = self.getRange(act)
                print("RANGE", first, last)
                matrices = []
                for frame in range(first, last+1):
                    scn.frame_current = frame
                    updateScene(context)
                    matrices.append((frame, self.addMats()))
                for frame,mats in matrices:
                    scn.frame_current = frame
                    updateScene(context)
                    self.bake(mats, act, context)
            else:
                for bname in list(self.bones.keys()):
                    self.removeFromPose(bname, rig)
                mats = self.addMats()
                self.bake(mats, None, context)
        else:
            print("Nothing to bake for %s rig" % rig.DazRig)


    def getBones(self, rig, baker, baked):
        if baker in rig.pose.bones.keys():
            pb = rig.pose.bones[baker]
            bakedBones = []
            self.bones[baker] = (pb, bakedBones)
        else:
            print("Missing bone:", baker)
            return
        for bname in baked:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                bakedBones.append(pb)


    def getRange(self, act):
        maxs = []
        mins = []
        for fcu in act.fcurves:
            times = [kp.co[0] for kp in fcu.keyframe_points]
            maxs.append(max(times))
            mins.append(min(times))
        return int(min(mins)), int(max(maxs))


    def addMats(self):
        mats = []
        for bname,bones in self.bones.items():
            bmats = []
            mats.append((bones[0], bmats))
            for pb in bones[1]:
                bmats.append((pb, pb.matrix.copy()))
        return mats


    def removeFromPose(self, bname, rig):
        pb = rig.pose.bones[bname]
        diff = pb.matrix_basis - Matrix()
        maxdiff = max([row.length for row in diff])
        if maxdiff < 1e-5:
            del self.bones[bname]
            print("REM", bname)


    def removeFromAction(self, act, rig):
        used = {}
        for fcu in act.fcurves:
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[":
                used[words[1]] = True
        for bname in list(self.bones.keys()):
            if bname not in used.keys():
                self.removeFromPose(bname, rig)


    def bake(self, mats, act, context):
        for pb,bmats in mats:
            pb.matrix_basis = Matrix()
            if act:
                self.insertKeys(pb)
            context.view_layer.update()
            for pb,mat in bmats:
                pb.matrix = mat
                if act:
                    self.insertKeys(pb)
                context.view_layer.update()
                if not isLocationUnlocked(pb):
                    pb.location = Zero


    def insertKeys(self, pb):
        if isLocationUnlocked(pb):
            pb.keyframe_insert("location", group=pb.name)
        if pb.rotation_mode == 'QUATERNION':
            pb.keyframe_insert("rotation_quaternion", group=pb.name)
        else:
            pb.keyframe_insert("rotation_euler", group=pb.name)
        pb.keyframe_insert("scale", group=pb.name)

#----------------------------------------------------------
#   Import locks and limits
#----------------------------------------------------------

class DAZ_OT_ImposeLocksLimits(DazOperator, IsArmature):
    bl_idname = "daz.impose_locks_limits"
    bl_label = "Impose Locks And Limits"
    bl_description = "Impose locks and limits for current pose"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        self.locks = {"location" : {}, "rotation_euler" : {}, "scale" : {}}
        self.limits = {"location" : {}, "rotation_euler" : {}, "scale" : {}}
        for pb in rig.pose.bones:
            self.locks["location"][pb.name] = list(pb.lock_location)
            self.locks["rotation_euler"][pb.name] = list(pb.lock_rotation)
            self.locks["scale"][pb.name] = list(pb.lock_scale)
            self.getLimits(self.limits["location"], pb, 'LIMIT_LOCATION', -1e10, 1e10)
            self.getLimits(self.limits["rotation_euler"], pb, 'LIMIT_ROTATION', -math.pi, math.pi)
            self.getLimits(self.limits["scale"], pb, 'LIMIT_SCALE', -1e10, 1e10)

        if rig.animation_data and rig.animation_data.action:
            act = rig.animation_data.action
            deletes = []
            for fcu in act.fcurves:
                words = fcu.data_path.split('"')
                if words[0] == "pose.bones[":
                    bname = words[1]
                    channel = words[2].split(".")[-1]
                    if (channel in self.locks.keys() and
                        bname in self.locks[channel].keys()):
                        lock = self.locks[channel][bname]
                        if lock[fcu.array_index]:
                            deletes.append(fcu)
                            continue
                    if (channel in self.limits.keys() and
                        bname in self.limits[channel].keys()):
                        limit = self.limits[channel][bname]
                        self.limitFcurve(fcu, limit[fcu.array_index])
            for fcu in deletes:
                act.fcurves.remove(fcu)

        for pb in rig.pose.bones:
            for channel,default in [("location", 0.0), ("rotation_euler", 0.0), ("scale", 1.0)]:
                vec = getattr(pb, channel)
                lock = self.locks[channel][pb.name]
                for idx in range(3):
                    if lock[idx]:
                        vec[idx] = default

            for channel in ["location", "rotation_euler", "scale"]:
                vec = getattr(pb, channel)
                limit = self.limits[channel][pb.name]
                for idx in range(3):
                    min,max = limit[idx]
                    if vec[idx] < min:
                        vec[idx] = min
                    elif vec[idx] > max:
                        vec[idx] = max


    def getLimits(self, limits, pb, cnstype, min, max):
        limit = limits[pb.name] = 3*[(min,max)]
        cns = getConstraint(pb, cnstype)
        if cns:
            if cnstype == 'LIMIT_ROTATION':
                for idx,char in enumerate(["x", "y", "z"]):
                    if getattr(cns, "use_limit_%s" % char):
                        cmin = getattr(cns, "min_%s" % char)
                        cmax = getattr(cns, "max_%s" % char)
                        limit[idx] = (cmin, cmax)
            elif cnstype == 'LIMIT_LOCATION':
                for idx,char in enumerate(["x", "y", "z"]):
                    cmin,cmax = min,max
                    if getattr(cns, "use_min_%s" % char):
                        cmin = getattr(cns, "min_%s" % char)
                    if getattr(cns, "use_max_%s" % char):
                        cmax = getattr(cns, "max_%s" % char)
                    limit[idx] = (cmin, cmax)


    def limitFcurve(self, fcu, limit):
        min,max = limit
        for kp in fcu.keyframe_points:
            diff = 0
            if kp.co[1] < min:
                diff = min - kp.co[1]
                kp.co[1] = min
                kp.handle_left[1] += diff
                kp.handle_right[1] += diff
            elif kp.co[1] > max:
                diff = max - kp.co[1]
                kp.co[1] = max
                kp.handle_left[1] += diff
                kp.handle_right[1] += diff

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportAction,
    DAZ_OT_ImportPoseLib,
    DAZ_OT_ImportPose,
    DAZ_OT_ImportNodePose,
    DAZ_OT_ClearPose,
    DAZ_OT_PruneAction,
    DAZ_OT_BakeToFkRig,
    DAZ_OT_SavePosePreset,
    DAZ_OT_ImposeLocksLimits,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
