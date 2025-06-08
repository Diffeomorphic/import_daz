# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..framer import Framer
from ..animation import HideOperator, FrameConverter
from ..bone_data import BD
from ..rig_utils import copyTransform
from .preset import *

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


class DAZ_OT_SavePosePreset(HideOperator, Preset, SingleFile, DufFile, FrameConverter, Framer, IsObject):
    bl_idname = "daz.save_pose_preset"
    bl_label = "Save Pose Preset"
    bl_description = "Save the active action as a pose preset,\nto be used in DAZ Studio"
    bl_options = {'UNDO', 'PRESET'}

    useConvert = False
    trgRig = "genesis"
    affectBones = True
    affectMorphs = False

    type : EnumProperty(
        items = [
            ('POSE', "Pose", "Pose preset"),
            ('MORPH', "Morph", "Morph preset"),
            ('HIERARCHICAL', "Hierarchical", "Hierarchical pose preset"),
            ('POSE_MORPH', "Pose And Morph", "Combined pose and morph preset"),
        ],
        name = "Preset Type",
        description = "Preset type",
        default = 'POSE')

    useAction : BoolProperty(
        name = "Use Action",
        description = "Save action instead of single pose",
        default = True)

    useObject : BoolProperty(
        name = "Use Object",
        description = "Include object in the pose preset",
        default = True)

    includeLocks : BoolProperty(
        name = "Include Locked Channels",
        description = "Include locked bone channels in the pose preset",
        default = True)

    useScale : BoolProperty(
        name = "Use Scale",
        description = "Include bone scale transforms in the pose preset",
        default = True)

    useFaceBones : BoolProperty(
        name = "Use Face Bones",
        description = "Include face bones in the pose preset",
        default = True)

    useUnusedMorphs : BoolProperty(
        name = "Save Unused Morphs",
        description = "Include morphs that are constantly zero",
        default = True)

    useFinalMorphs : BoolProperty(
        name = "Export Final Morph Values",
        default = False)

    fps : FloatProperty(
        name = "FPS",
        description = "Frames per second",
        min = 1, max = 120,
        default = 30)

    def draw(self, context):
        Preset.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "type")
        self.useBones = self.type in ['POSE', 'POSE_MORPH', 'HIERARCHICAL']
        self.useHierarchical = self.type == 'HIERARCHICAL'
        self.useMorphs = self.type in ['MORPH', 'POSE_MORPH']
        self.useBones = (self.useBones and self.isFigure)
        if not self.useHierarchical:
            self.layout.prop(self, "useObject")
        if self.useBones:
            self.layout.prop(self, "includeLocks")
            self.layout.prop(self, "useScale")
            self.layout.prop(self, "useFaceBones")
        if self.useMorphs:
            self.layout.prop(self, "useUnusedMorphs")
            self.layout.prop(self, "useFinalMorphs")
        self.layout.prop(self, "useAction")
        if self.useAction:
            Framer.draw(self, context)
            self.layout.prop(self, "fps")

    Folders = {
        "Genesis" : "People/Genesis/",
        "Genesis2-female" : "People/Genesis 2 Female/",
        "Genesis2-male" : "People/Genesis 2 Male/",
        "Genesis3-female" : "People/Genesis 3 Female/",
        "Genesis3-male" : "People/Genesis 3 Male/",
        "Genesis8-female" : "People/Genesis 8 Female/",
        "Genesis8-male" : "People/Genesis 8 Male/",
        "Genesis9" : "People/Genesis 9/",
    }

    def getDefaultDirectory(self, ob):
        folder = self.Folders.get(dazRna(ob).DazMesh, "")
        return "%sPoses/%s" % (folder, GS.author)


    def invoke(self, context, event):
        self.useMorphs = self.useBones = self.useHierarchical = False
        rig = getRigFromContext(context, strict=False)
        self.isFigure = (rig.type == 'ARMATURE')
        self.setActiveRange(context, rig)
        self.setDefaultFilepath(rig, context.scene, "my_pose")
        return SingleFile.invoke(self, context, event)


    def run(self, context):
        self.Z = Matrix.Rotation(pi/2, 4, 'X')
        rig = getRigFromContext(context, strict=False, activate=True)
        if self.useHierarchical:
            if (dazRna(rig).DazRig.startswith(("mhx", "rigify")) or
                not dazRna(rig).DazUrl):
                msg = "Hierarchical pose presets can only be made for original DAZ rigs.\nConsider generating %s rig with Keep DAZ Rig enabled" % dazRna(rig).DazRig
                raise DazError(msg)
        self.initData()
        if self.useBones:
            self.setupDriven(rig)
            self.setupConverter(rig)
        for bname,pg in dazRna(rig).DazAlias.items():
            self.alias[bname] = pg.s
        act = None
        if self.useAction and rig.animation_data:
            act = rig.animation_data.action
        if act:
            self.getFcurves(rig, act)
        else:
            self.getFakeCurves(rig)

        if self.useMorphs and rig.type == 'MESH':
            skeys = rig.data.shape_keys
            if skeys:
                act = None
                if self.useAction and skeys.animation_data:
                    act = skeys.animation_data.action
                if act:
                    self.getShapeFcurves(act, skeys)
                else:
                    self.getShapeFakeCurves(skeys)

        if self.useBones:
            self.setupFlipper(rig)
            self.setupBoneFrames(rig)
        elif self.useObject:
            self.setupObjectFrames(rig)
        if self.useHierarchical:
            self.saveHierarchicalPreset(context, rig)
        else:
            self.savePosePreset(context, rig)


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
        self.Ls = dict([(frame, {}) for frame in range(self.frame_start, self.frame_end+1)])
        self.F = {}
        self.Finv = {}
        self.loclocks = {}
        self.rotlocks = {}


    def isLocUnlocked(self, pb, bname):
        bnames = ["lHand", "rHand", "lFoot", "rFoot",
                  "l_hand", "r_hand", "l_foot", "r_foot"]
        return (self.includeLocks or
                (not isLocationLocked(pb) and bname not in bnames))


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

        fcurves = getActionBag(act).fcurves
        for fcu in fcurves:
            channel = fcu.data_path.rsplit(".",1)[-1]
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[" and self.useBones:
                idx = fcu.array_index
                bname0 = words[1]
                if self.isCopyTransformed(bname0, rig):
                    continue
                for bname in self.getBoneNames(bname0):
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
                    self.locs[objkey][idx] = fcu
                elif channel == "rotation_euler":
                    self.rots[objkey][idx] = fcu
                elif self.useScale and channel == "scale":
                    self.scales[objkey][idx] = fcu


    def getShapeFcurves(self, act, skeys):
        if len(skeys.key_blocks) == 0:
            return
        basename = skeys.key_blocks[0].name
        fcurves = getActionBag(act, 'KEY').fcurves
        for fcu in fcurves:
            sname,channel = getShapeChannel(fcu)
            if sname and sname != basename:
                self.morphs[sname] = fcu


    def isValidMorph(self, rig, prop):
        return (isinstance(rig[prop], float) and
                prop[0:3] not in ["Daz", "Mha", "Mhh"])


    def getFakeCurves(self, rig):
        objkey = self.getDazObject(rig)
        self.rots[objkey] = [FakeCurve(t) for t in rig.rotation_euler]
        self.locs[objkey] = [FakeCurve(t) for t in rig.location]
        self.scales[objkey] = [FakeCurve(t) for t in rig.scale]
        if self.useBones:
            for pb in rig.pose.bones:
                if self.isCopyTransformed(pb.name, rig):
                    continue
                for bname in self.getBoneNames(pb.name):
                    if pb.rotation_mode == 'QUATERNION':
                        self.quats[bname] = [FakeCurve(t) for t in pb.rotation_quaternion]
                    else:
                        self.rots[bname] = [FakeCurve(t) for t in pb.rotation_euler]
                    if self.useScale:
                        self.scales[bname] = [FakeCurve(t) for t in pb.scale]
                    if self.isLocUnlocked(pb, bname):
                        self.locs[bname] = [FakeCurve(t) for t in pb.location]
        if self.useMorphs and rig.type == 'ARMATURE':
            for prop in rig.keys():
                if self.isValidMorph(rig, prop):
                    value = rig[prop]
                    if self.useFinalMorphs and self.isSubMorph(prop, rig, value):
                        value = rig.data.get(finalProp(prop), value)
                    self.morphs[prop]= FakeCurve(value)


    def isCopyTransformed(self, bname, rig):
        if bname in rig.pose.bones.keys():
            pb = rig.pose.bones[bname]
            cns = getConstraint(pb, 'COPY_TRANSFORM')
            return (cns and not cns.mute and cns.influence == 1.0)


    def isSubMorph(self, prop, rig, value):
        SpecialMorphs = ["facs_bs_JawOpen"]
        if "ctrl" in prop:
            prop2 = prop.replace("Left", "").replace("Right", "")
            final2 = finalProp(prop2)
            if prop2 != prop and rig.data.get(final2) == value:
                return False
            return True
        else:
            return (prop in SpecialMorphs)


    def getShapeFakeCurves(self, skeys):
        for skey in skeys.key_blocks[1:]:
            self.morphs[skey.name] = FakeCurve(skey.value)


    def setupFlipper(self, rig):
        for pb in rig.pose.bones:
            euler = Euler(Vector(dazRna(pb.bone).DazOrient)*D, 'XYZ')
            dmat = euler.to_matrix().to_4x4()
            dmat.col[3][0:3] = Vector(dazRna(pb.bone).DazHead)*GS.scale
            Fn = pb.bone.matrix_local.inverted() @ self.Z @ dmat
            Fn = Fn.to_quaternion().to_matrix().to_4x4()
            for bname in self.getBoneNames(pb.name):
                bname = self.getDazBone(bname, pb)
                self.F[bname] = Fn
                self.Finv[bname] = Fn.inverted()
                self.rotlocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_rotation) @ Fn.to_3x3()]
                self.loclocks[bname] = [int(round(abs(f))) for f in Vector(pb.lock_location) @ Fn.to_3x3()]


    def setupObjectFrames(self, rig):
        objkey = self.getDazObject(rig)
        for frame in range(self.frame_start, self.frame_end+1):
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
        for frame in range(self.frame_start, self.frame_end+1):
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
        for idx,fcu in enumerate(self.rots.get(objkey,[])):
            if fcu:
                rot[idx] = fcu.evaluate(frame)
        # reverse postTransform for cameras and lights before saving pose preset
        if GS.zup and rig.type in ['CAMERA', 'LIGHT']:
            rot.x -= pi/2
        mat = rot.to_matrix().to_4x4()
        if self.useScale:
            scale = rig.scale.copy()
            for idx,fcu in enumerate(self.scales.get(objkey,[])):
                if fcu:
                    scale[idx] = fcu.evaluate(frame)
            smat = Matrix.Diagonal(scale)
            mat = mat @ smat.to_4x4()
        loc = rig.location.copy()
        for idx,fcu in enumerate(self.locs.get(objkey,[])):
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
            if pb.parent and inheritsScale(pb):
                parname = self.getDazBone(pb.parent.name, pb.parent)
                psmat = smats.get(parname)
                if psmat:
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
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname and cnsname is None:
                    if bname not in self.driven.keys():
                        self.driven[bname] = {}
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
            if dazRna(rig).DazRig == "mhx":
                from ..mhx_tools import L_CUSTOM
                customLayer = L_CUSTOM
            elif dazRna(rig).DazRig.startswith("rigify"):
                from ..rigify_tools import R_CUSTOM
                customLayer = R_CUSTOM
            else:
                return
            for pb in rig.pose.bones:
                if isInNumLayer(pb.bone, rig, customLayer):
                    bname = self.getPrefixName(pb)
                    if bname:
                        self.conv[pb.name] = [bname]
        else:
            roots = [pb for pb in rig.pose.bones if pb.parent is None]
            for pb in roots:
                self.setupConvBones(pb)


    def getPrefixName(self, pb):
        if self.skipBone(pb):
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


    def getDazBone(self, bname, pb, idx=None):
        if not (self.useHierarchical and isinstance(pb, bpy.types.PoseBone)):
            return bname
        if idx is None:
            idx = dazRna(pb.bone).DazRigIndex
        if idx == 0:
            return bname
        else:
            return "%s-%d" % (bname, idx)


    def getNodes(self, rig):
        nodes = {}
        self.ancestors = {0 : {}}
        figure = dazRna(rig).DazUrl.rsplit("#",1)[1]
        node = {
            "id" : figure,
            "url" : "name://@selection/%s:" % quote(figure),
        }
        self.ancestors[0][figure] = True
        if rig.parent:
            if rig.parent_type == 'OBJECT':
                parent = dazRna(rig.parent).DazUrl.rsplit("#",1)[-1]
                if parent:
                    node["parent"] = "#%s" % quote(parent)
            elif rig.parent_type == 'BONE':
                node["parent"] = "#%s" % quote(rig.parent_bone)
        nodes[0] = [node]
        if rig.type != 'ARMATURE':
            return nodes
        for pb in rig.pose.bones:
            if self.skipBone(pb):
                continue
            idx = dazRna(pb.bone).DazRigIndex
            if idx not in nodes.keys():
                nodes[idx] = []
            nodes[idx] += self.getAncestors(pb, rig, idx, figure)
        nodelist = []
        nrigs = max(1, len(dazRna(rig.data).DazMergedRigs))
        for idx in range(nrigs):
            nodelist += nodes.get(idx, [])
        return nodelist


    def getAncestors(self, pb, rig, idx, figure):
        def getParent(pb, idx):
            parent = pb.parent
            if parent and self.skipBone(parent):
                parent = parent.parent
            if parent:
                parname = self.getDazBone(parent.name, parent, idx)
                return parent, parname
            else:
                return None, figure2

        def addNode(pb, parname, idx):
            bname = self.getDazBone(pb.name, pb, idx)
            node = {
                "id" : bname,
                "url" : "name://@selection/%s:" % quote(pb.name),
                "parent" : "#%s" % quote(parname)
            }
            self.ancestors[idx][bname] = True
            return node

        def addFigure(figure2, figure, idx):
            node = {
                "id" : figure2,
                "url" : "name://@selection/%s:" % quote(figure2),
                "parent" : "#%s" % quote(figure)
            }
            self.ancestors[idx][figure2] = True
            return node

        path2,figure2 = self.getPathFigure(rig, idx)
        if idx not in self.ancestors.keys():
            self.ancestors[idx] = {}
        paridx = dazRna(pb.bone).DazBoneParentRig
        if paridx >= 0:
            parent,parname = getParent(pb, None)
            node = addNode(pb, figure2, idx)
            nodes = [node]
            if figure2 not in self.ancestors[idx].keys():
                node = addFigure(figure2, parname, idx)
                nodes.append(node)
        else:
            parent,parname = getParent(pb, idx)
            node = addNode(pb, parname, idx)
            nodes = [node]
            while parent and parname not in self.ancestors[idx].keys():
                pb = parent
                parent,parname = getParent(parent, idx)
                node = addNode(pb, parname, idx)
                nodes.append(node)
            if figure2 not in self.ancestors[idx].keys():
                node = addFigure(figure2, figure, idx)
                nodes.append(node)
        nodes.reverse()
        return nodes


    def getPathFigure(self, rig, idx):
        pg = dazRna(rig.data).DazMergedRigs.get(str(idx))
        if pg:
            string = pg.s
        else:
            string = dazRna(rig).DazUrl
        path,figure = string.rsplit("#",1)
        return path, figure


    def skipBone(self, pb):
        return (isDrvBone(pb.name) or
                isFinal(pb.name) or
                pb.name in ["Root"])


    def saveHierarchicalPreset(self, context, rig):
        filepath = self.getFilepath(context)
        struct, filepath = self.makeDazStruct("preset_hierarchical_pose", filepath)
        struct["scene"] = {}
        struct["scene"]["nodes"] = self.getNodes(rig)
        struct["scene"]["animations"] = self.getAnimations(rig)
        saveJson(struct, filepath, binary=self.useCompress, strict=False)
        print("Pose preset %s saved" % filepath)


    def savePosePreset(self, context, rig):
        filepath = self.getFilepath(context)
        struct, filepath = self.makeDazStruct("preset_pose", filepath)
        struct["scene"] = {}
        struct["scene"]["animations"] = self.getAnimations(rig)
        saveJson(struct, filepath, binary=self.useCompress, strict=False)
        print("Pose preset %s saved" % filepath)


    def getBoneUrl(self, bname, pb, rig):
        if self.useHierarchical:
            if pb == rig:
                path,figure = dazRna(rig).DazId.rsplit("#", 1)
                figure = quote(figure)
                path = quote(path)
                return "%s:%s#%s" % (figure, path, figure)
            else:
                idx = dazRna(pb.bone).DazRigIndex
                path,figure = self.getPathFigure(rig, idx)
                id = dazRna(pb.bone).DazTrueName
                if not id:
                    id = pb.name
                return"%s:%s#%s" % (quote(bname), quote(path), quote(id))
        else:
            if pb == rig:
                return "name://@selection"
            else:
                return "name://@selection/%s" % quote(bname)


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
        if self.useObject or self.useHierarchical:
            objkey = self.getDazObject(rig)
            Ls = [self.Ls[frame][objkey] for frame in range(self.frame_start, self.frame_end+1)]
            locs = [L.to_translation() for L in Ls]
            self.getTrans("", rig, rig, locs, 1/GS.scale, anims)

            rots = [L.to_euler(globalFlip[rig.rotation_mode]) for L in Ls]
            self.getRot("", rig, rig, rots, 1/D, anims)
            if self.useScale:
                scales = [L.to_scale() for L in Ls]
                self.getScale("", rig, rig, scales, anims)

        if self.useBones and rig.type == 'ARMATURE':
            for pb in rig.pose.bones:
                if pb.name in self.RootNames:
                    continue
                for bname in self.getBoneNames(pb.name):
                    bname = self.getDazBone(bname, pb)
                    Ls = [self.Ls[frame][bname] for frame in range(self.frame_start, self.frame_end+1)]
                    if self.isLocUnlocked(pb, bname):
                        locs = [L.to_translation() for L in Ls]
                        self.getTrans(bname, pb, rig, locs, 1/GS.scale, anims)
                    rots = [L.to_euler(dazRna(pb).DazRotMode) for L in Ls]
                    self.getRot(bname, pb, rig, rots, 1/D, anims)
                    if self.useScale:
                        scales = [L.to_scale() for L in Ls]
                        self.getScale(bname, pb, rig, scales, anims)

        if self.useMorphs:
            for prop,fcu in self.morphs.items():
                self.getMorph(prop, fcu, anims)
        return anims


    def getMorph(self, prop, fcu, anims):
        if prop in self.alias.keys():
            prop = self.alias[prop]
        anim = {}
        anim["url"] = "name://@selection#%s:?value/value" % normalizeRef(prop)
        vals = [fcu.evaluate(frame) for frame in range(self.frame_start, self.frame_end+1)]
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
        def nullify(x):
            return (0 if abs(x) < eps else x)

        if len(xs) == 0:
            return
        maxdiff = max([abs(x-xs[0]) for x in xs])
        if maxdiff < eps:
            anim["keys"] = [(0, nullify(xs[0]))]
        else:
            anim["keys"] = [(n/self.fps, nullify(x)) for n,x in enumerate(xs)]


    def getTrans(self, bname, pb, rig, vecs, factor, anims):
        if self.driven.get(pb.name) and self.driven[pb.name].get("location"):
            return
        if pb == rig:
            center = dazRna(rig).DazCenter
            for idx,x in enumerate(["x","y","z"]):
                anim = {}
                anim["url"] = "%s:?translation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                locs = [vec[idx]*factor - center[idx] for vec in vecs]
                self.addKeys(locs, anim, 0.01)
                anims.append(anim)
        else:
            from ..node import getTransformMatrices
            dmat,bmat,parent = getTransformMatrices(pb, rig, {})
            if parent:
                dinv = dmat.inverted()
                tmats = [dmat @ Matrix.Translation(vec) @ dinv for vec in vecs]
                vecs = [tmat.to_translation() for tmat in tmats]
            for idx,x in enumerate(["x","y","z"]):
                if (not self.includeLocks and
                    pb.name in self.loclocks.keys() and
                    self.loclocks[pb.name][idx]):
                    continue
                anim = {}
                anim["url"] = "%s:?translation/%s/value" % (self.getBoneUrl(bname, pb, rig), x)
                locs = [vec[idx]*factor for vec in vecs]
                self.addKeys(locs, anim, 0.01)
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
                self.addKeys(rots, anim, 0.01)
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
                self.addKeys(rots, anim, 0.01)
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
                self.addKeys(rots, anim, 0.02)
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
#   Make Control Rig
#-------------------------------------------------------------

class DAZ_OT_MakeControlRig(DazOperator, IsArmature):
    bl_idname = "daz.make_control_rig"
    bl_label = "Make Control Rig"
    bl_description = "Make the active rig the control rig of its children.\nAn alternative to merging rigs"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        children = [ob for ob in rig.children if ob.type == 'ARMATURE' and ob.parent_type != 'BONE']
        for ob in children:
            ob.select_set(True)
        setMode('EDIT')
        for ob in children:
            for eb in ob.data.edit_bones:
                rb = rig.data.edit_bones.get(eb.name)
                if rb:
                    eb.matrix = rb.matrix
        setMode('OBJECT')
        for ob in children:
            for pb in ob.pose.bones:
                rb = rig.pose.bones.get(pb.name)
                if rb:
                    for cns in pb.constraints:
                        if cns.type.startswith("LIMIT"):
                            cns.mute = True
                    copyTransform(pb, rb, rig)
                    dazRna(pb).DazSharedBone = True
                    enableBoneNumLayer(pb.bone, ob, T_HIDDEN)
            enableRigNumLayer(ob, T_HIDDEN, False)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SavePosePreset,
    DAZ_OT_MakeControlRig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
