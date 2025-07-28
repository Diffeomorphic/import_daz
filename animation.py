# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .transform import Transform
from .fileutils import *
from .morphing import PosableMaker
from .load_json import JL
from .bone_data import BD

#-------------------------------------------------------------
#   Frame converter class
#-------------------------------------------------------------

class FrameConverter:
    trgRig = None

    def getConv(self, banims, rig):
        from .figure import getRigType
        from .convert import getConverter
        if self.useConvert:
            srctype = DF.SourceRigs[self.srcCharacter]
        elif self.trgRig and not dazRna(rig).DazRig.startswith("genesis"):
            srctype = self.trgRig
        else:
            srctype = getRigType(banims, False)
        if srctype:
            print("Auto-detected %s character in duf/dsf file" % srctype)
            return getConverter(srctype, rig)
        elif dazRna(rig).DazRig.startswith(("mhx", "rigify")):
            print("Convert to %s" % dazRna(rig).DazRig)
            return getConverter("genesis3", rig)
        else:
            print("Could not auto-detect character in duf/dsf file")
            return {}, {}


    def getRigifyLocks(self, rig, conv):
        locks = []
        if dazRna(rig).DazRig.startswith("rigify"):
            for bname in conv.keys():
                rname = self.getConvBone(conv[bname], rig)
                if (rname in rig.pose.bones.keys() and
                    rname not in ["torso"]):
                    pb = rig.pose.bones[rname]
                    locks.append((pb, tuple(pb.lock_location)))
                    pb.lock_location = TTrue
        return locks

    #-------------------------------------------------------------
    #   Convert animations
    #-------------------------------------------------------------

    def prepareAnimations(self, anims, oanims, rig, again):
        locks = []
        bonemap = {}
        if rig.type == 'ARMATURE' and self.affectBones and not again:
           bonemap,locks = self.setupBoneMap(anims, rig)
        nanims = []
        for anim,oanim in zip(anims, oanims):
            banim,vanim,xanim,interps = anim
            if again:
                nbanim = oanim[0]
            elif self.affectBones:
                nbanim = {}
                for bname,frames in banim.items():
                    nname = bonemap.get(bname)
                    if nname:
                        nbanim[nname] = frames
                    elif self.isObject(bname, rig):
                        nbanim[bname] = frames
            else:
                nbanim = banim
            nvanim = self.convertMorphAnim(vanim, rig, again)
            nanims.append((nbanim,nvanim,xanim,interps))
        if self.affectBones and not again:
            if self.useConvert:
                self.convertAllFrames(nanims, rig, bonemap)
        return nanims, locks, bonemap

    #-------------------------------------------------------------
    #   Convert bone animations
    #-------------------------------------------------------------

    def setupBoneMap(self, anims, rig):
        truenames = dict([(bone.name, bone.name) for bone in rig.data.bones])
        for bone in rig.data.bones:
            truename = dazRna(bone).DazTrueName
            if truename:
                truenames[truename] = bone.name
        conv,twists = self.getConv(anims[0][0], rig)
        bonemap = OrderedDict()
        locks = self.getRigifyLocks(rig, conv)
        missing = []
        for banim,vanim,xanim,interps in anims:
            for bname in banim.keys():
                if bname in conv.keys():
                    bonemap[bname] = self.getConvBone(conv[bname], rig)
                    continue
                if bname in truenames.keys():
                    bonemap[bname] = truenames[bname]
                    continue
                if len(bname) < 2:
                    bonemap[bname] = bname
                    continue
                elif bname[0] in ["l", "r"] and bname[1].isupper():
                    rname1 = "%s%s.%s" % (bname[1].lower(), bname[2:], bname[0].upper())
                    rname2 = "%s%s.%s" % (bname[1].lower(), bname[2:].lower(), bname[0].upper())
                    rname3 = "%s_%s" % (bname[0], bname[1:].lower())
                    if rname1 in rig.data.bones.keys():
                        bonemap[bname] = rname1
                        continue
                    elif rname2 in rig.data.bones.keys():
                        bonemap[bname] = rname2
                        continue
                    elif rname3 in rig.data.bones.keys():
                        bonemap[bname] = rname2
                        continue
                elif bname[0:2] in ["l_", "r_"]:
                    rname1 = "%s.%s" % (bname[2:], bname[0].upper())
                    rname2 = "%s%s%s" % (bname[0], bname[2].upper(), bname[3:])
                    if rname1 in rig.data.bones.keys():
                        bonemap[bname] = rname1
                        continue
                    elif rname2 in rig.data.bones.keys():
                        bonemap[bname] = rname2
                        continue
                elif bname[0].isupper():
                    rname1 = "%s%s" % (bname[0].lower(), bname[1:])
                    rname2 = bname.lower()
                    if rname1 in rig.data.bones.keys():
                        bonemap[bname] = rname1
                        continue
                    elif rname2 in rig.data.bones.keys():
                        bonemap[bname] = rname2
                        continue
                rname = bname.lower()
                if rname in rig.data.bones.keys():
                    bonemap[bname] = rname
                elif not self.isObject(bname, rig):
                    missing.append(bname)
        if missing:
            print("Missing bones:")
            print(missing)
        return bonemap, locks


    def getConvBone(self, bnames, rig):
        if isinstance(bnames, str):
            return bnames
        else:
            for bname in bnames:
                if bname in rig.pose.bones.keys():
                    return bname
            return bnames[0]


    def convertAllFrames(self, anims, rig, bonemap):
        if self.trgCharacter is None:
            return anims
        print("Convert from %s to %s" % (self.srcCharacter, self.trgCharacter))
        parents = DF.loadEntry(DF.ParentRigs[self.srcCharacter], "parents").get("parents")
        nparents = DF.loadEntry(self.trgCharacter, "parents").get("parents")
        core = {}
        for bname, parname in parents.items():
            if bname in ["head",
                "lHand", "lFoot", "l_hand", "l_foot",
                "rHand", "rFoot", "r_hand", "r_foot",
                ]:
                core[bname] = False
            elif parname:
                core[bname] = core[parname]
            else:
                core[bname] = True

        restmats = {}
        nrestmats = {}
        xyzs = {}
        nxyzs = {}
        for bname,nname in bonemap.items():
            if not core.get(bname):
                continue
            orient,xyzs[bname] = DF.getOrientation(self.srcCharacter, bname)
            if orient is not None:
                restmats[bname] = Euler(Vector(orient)*D, 'XYZ').to_matrix()
            if nname[0:6] == "TWIST-":
                continue
            if not nname:
                if bname[-5:] == "Twist":
                    nname = bonemap.get("%sBend" % bname[:-5], nname)
                elif bname[-5:] == "Upper":
                    nname = bonemap.get("%sLower" % bname[:-5], nname)
            pb = rig.pose.bones.get(nname)
            if pb:
                nxyzs[bname] = dazRna(pb).DazRotMode
                nrestmats[bname] = Euler(Vector(dazRna(pb.bone).DazOrient)*D, 'XYZ').to_matrix()
            else:
                print('Missing "%s" "%s"' % (bname, nname))

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

        def convertFrames(xyz, nxyz, frames):
            vecs = framesToVectors(frames)
            nvecs = {}
            for t,vec in vecs.items():
                mat = Euler(vec*D, xyz).to_matrix()
                nmat = mat @ trmat
                nvecs[t] = Vector(nmat.to_euler(nxyz))/D
            return vectorsToFrames(nvecs)

        for banim,vanim,xanim,interps in anims:
            nbanim = {}
            for bname,nname in bonemap.items():
                if not core.get(bname):
                    continue
                if (nname in banim.keys() and
                    bname in nrestmats.keys() and
                    bname in restmats.keys()):
                    frames = banim[nname]
                    if "rotation" in frames.keys():
                        parname = parents.get(bname)
                        if parname and parname[-5:] == "Twist":
                            parname = "%sBend" % parname[:-5]
                        if parname in nrestmats.keys():
                            trmat = restmats[bname] @ restmats[parname].inverted() @ nrestmats[parname] @ nrestmats[bname].inverted()
                        elif not parname:
                            trmat = restmats[bname] @ nrestmats[bname].inverted()
                        else:
                            continue
                        nframes = convertFrames(xyzs[bname], nxyzs[bname], frames["rotation"])
                        banim[nname]["rotation"] = nframes

    #-------------------------------------------------------------
    #   Convert morph animations
    #-------------------------------------------------------------

    def convertMorphAnim(self, vanim, rig, again):
        if not self.affectMorphs:
            return vanim

        struct = {}
        for prop,frames in vanim.items():
            struct[prop] = dict(frames)

        def zeroFrame(frames):
            return (len(frames) == 1 and list(frames.values())[0] == 0)

        nstruct = {}
        for prop,frames in struct.items():
            formulas,alias = self.getFormulas(rig, prop)
            if not formulas:
                if not zeroFrame(frames) or self.useLoadZero:
                    self.used[alias] = True
                    nstruct[alias] = frames
                continue
            for nprop,factor in formulas.items():
                if factor == 0 or not isinstance(factor, (int, float)):
                    continue
                factor *= self.multiplier
                if nprop not in nstruct.keys():
                    nstruct[nprop] = {}
                nframes = nstruct[nprop]
                if nprop in self.minmax.keys():
                    pmin,pmax = self.minmax[nprop]
                elif nprop in self.minmax2.keys():
                    pmin,pmax = self.minmax2[nprop]
                else:
                    pmin,pmax = -1e6,1e6
                for t,value in frames.items():
                    term = min(pmax, max(pmin, factor*value))
                    if t in nframes.keys():
                        nframes[t] += term
                    else:
                        nframes[t] = term

        nvanim = {}
        for nprop,nframes in nstruct.items():
            if not zeroFrame(nframes) or self.useLoadZero:
                self.used[nprop] = True
                nvanim[nprop] = nframes.items()
        return nvanim


    def getFormulas(self, rig, prop):
        alias = self.alias.get(prop)
        if prop in self.altmorphs.keys():
            altformula = self.altmorphs[prop]
            alt = list(altformula.keys())[0]
        else:
            alt = "*"
        if alias and alias in rig.keys() or alias in self.shapekeys.keys():
            formula = {alias : 1.0}
        elif alias and alias in self.formulas.keys():
            formula = self.formulas[alias]
        elif alias and alias in self.formulas2.keys():
            formula = self.formulas2[alias]
        elif prop in rig.keys() or prop in self.shapekeys.keys():
            formula = {prop : 1.0}
        elif alt in rig.keys() or alt in self.shapekeys.keys():
            formula = altformula
        elif prop in self.formulas.keys():
            formula = self.formulas[prop]
        elif prop in self.formulas2.keys():
            formula = self.formulas2[prop]
        else:
            formula = {}
        if alias:
            return formula, alias
        else:
            return formula, prop

#-------------------------------------------------------------
#   HideOperator class
#-------------------------------------------------------------

class HideOperator(DazOperator):
    def storeState(self, context):
        from .driver import muteDazFcurves
        DazOperator.storeState(self, context)
        self.layerColls = []
        self.obhides = []
        self.activeObject = context.object
        self.rig = getRigFromContext(context, strict=True)
        for ob in context.view_layer.objects:
            if ob != self.rig:
                self.obhides.append((ob, ob.hide_get()))
                ob.hide_set(False)
        if self.rig:
            if BLENDER3:
                self.boneLayers = list(self.rig.data.layers)
                self.rig.data.layers = 32*[True]
            else:
                self.boneLayers = dict([(coll.name,coll) for coll in self.rig.data.collections if coll.is_visible])
            #self.hideLayerColls(self.rig, context.view_layer.layer_collection)
            self.muted = muteDazFcurves(self.rig, True)
            context.view_layer.objects.active = self.rig


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
        if self.rig:
            if BLENDER3:
                self.rig.data.layers = self.boneLayers
            else:
                for coll in self.rig.data.collections:
                    coll.is_visible = (coll.name in self.boneLayers.keys())
            muteDazFcurves(self.rig, dazRna(self.rig).DazDriversDisabled, muted=self.muted)
        for layer in self.layerColls:
            layer.exclude = False
        for ob,hide in self.obhides:
            ob.hide_set(hide)
        context.view_layer.objects.active = self.activeObject
        DazOperator.restoreState(self, context)

#-------------------------------------------------------------
#   BoneOptions
#-------------------------------------------------------------

class BoneOptions:
    affectObject : BoolProperty(
        name = "Affect Object",
        description = "Animate object transformations",
        default = True)

    affectBones : BoolProperty(
        name = "Affect Bones",
        description = "Animate bones",
        default = True)

    useClearPose : BoolProperty(
        name = "Clear Pose",
        description = "Clear the pose before loading a new one",
        default = False)

    affectScale : BoolProperty(
        name = "Affect Scale",
        description = "Include bone scale in animation.\nObject scale is always included",
        default = False)

    affectSelectedOnly : BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones",
        default = False)

    useSnapIk : BoolProperty(
        name = "Snap To IK",
        description = "Snap final pose to IK.\nFor MHX and Simple IK rigs only",
        default = False)

    useConvert : BoolProperty(
        name = "Convert Poses",
        description = "Attempt to convert poses to the current rig.",
        default = False)

    srcCharacter : EnumProperty(
        items = DF.RestPoseItems,
        name = "Source Character",
        description = "Character this file was made for",
        default = "genesis_8_female")

    def drawProp(self, context):
        self.layout.prop(self, "affectObject")
        if self.affectObject:
            self.layout.prop(self, "useClearPose")

    def drawFigure(self, context):
        self.layout.prop(self, "affectObject")
        self.layout.prop(self, "affectBones")
        if self.affectBones or self.affectObject:
            self.layout.prop(self, "useClearPose")
        if self.affectBones:
            self.layout.prop(self, "affectScale")
            self.layout.prop(self, "affectSelectedOnly")
            self.layout.prop(self, "useSnapIk")
            self.layout.prop(self, "useConvert")
            if self.useConvert:
                self.layout.prop(self, "srcCharacter")

#-------------------------------------------------------------
#   MorphOptions
#-------------------------------------------------------------

def getGeograftItems(scn, context):
    enums = [("-", "-", "-")]
    rig = context.object
    for ob in rig.children:
        if dazRna(ob).DazMesh and ob.type == 'MESH':
            enums += [(key,key,key) for key in dazRna(ob.data).DazMergedGeografts.keys()]
            return enums
    return enums


class MorphOptions(PosableMaker):
    onMorphSuffix = 'NONE'

    affectMorphs : BoolProperty(
        name = "Affect Morphs",
        description = "Animate morph properties",
        default = True)

    useClearMorphs : BoolProperty(
        name = "Clear Morphs",
        description = "Clear all active morphs before loading new ones",
        default = False)

    useShapekeys : BoolProperty(
        name = "Load To Shapekeys",
        description = "Load morphs to mesh shapekeys instead of rig properties",
        default = False)

    multiplier : FloatProperty(
        name = "Multiplier",
        description = "Multiply all morphs with this factor",
        min = 0.1, max = 10.0,
        default = 1.0)

    useLoadMissing : BoolProperty(
        name = "Load Missing Morphs",
        description = "Load missing morphs",
        default = False)

    useLoadZero : BoolProperty(
        name = "Also Load Zero Morphs",
        description = "Also load missing morphs with zero value",
        default = False)

    category : StringProperty(
        name = "Category",
        description = "Add missing morphs to this category",
        default = "Loaded")

    useScanned : BoolProperty(
        name = "Use Scanned Database",
        description = "Use the scanned database to find morphs",
        default = True)

    affectGeograft : EnumProperty(
        items = getGeograftItems,
        name = "Affect Geograft",
        description = "Add morphs to this merged geograft")

    def drawMorphs(self, context):
        self.layout.prop(self, "affectMorphs")
        if self.affectMorphs:
            self.layout.prop(self, "useClearMorphs")
            if not self.isFigure:
                return
            self.layout.prop(self, "multiplier")
            self.layout.prop(self, "useShapekeys")
            if not self.useShapekeys:
                self.layout.prop(self, "useScanned")
                self.layout.prop(self, "useLoadMissing")
                if self.useLoadMissing:
                    self.layout.prop(self, "useLoadZero")
                    self.layout.prop(self, "category")
                    PosableMaker.draw(self, context)
            self.layout.prop(self, "affectGeograft")


    def loadMissingOld(self, context, rig, missing):
        global theMorphTables
        unfound = []
        if dazRna(rig).DazId in theMorphTables.keys():
            table = theMorphTables[dazRna(rig).DazId]
        else:
            table = theMorphTables[dazRna(rig).DazId] = self.setupMorphTable(rig)
        namepathTable = {}
        for mname in missing:
            lname = mname.lower()
            if lname in table.keys():
                path,morphset = table[lname]
                if morphset not in namepathTable.keys():
                    namepathTable[morphset] = []
                namepathTable[morphset].append((mname, path, morphset))
            else:
                unfound.append(mname)

        from .morphing import CustomMorphLoader, StandardMorphLoader
        hasLoaded = False
        for morphset in namepathTable.keys():
            if self.useLoadMissing:
                mloader = StandardMorphLoader()
                mloader.useMakePosable = self.useMakePosable
                mloader.getFingeredRigMeshes(context)
                mloader.morphset = morphset
                mloader.category = ""
                mloader.hideable = True
                print("\nLoading missing %s morphs" % morphset)
                mloader.getAllMorphs(namepathTable[morphset], context)
                hasLoaded = True
        if self.useLoadMissing and "Custom" in namepathTable.keys():
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
                mloader.useMakePosable = self.useMakePosable
                dazRna(rig).DazCustomMorphs = True
                mloader.getFingeredRigMeshes(context)
                mloader.morphset = "Custom"
                mloader.category = cat
                mloader.hideable = True
                print("\nLoading morphs in category %s" % cat)
                mloader.getAllMorphs(namepaths, context)
                hasLoaded = True
        if hasLoaded:
            self.setupAlias(rig)
        return unfound


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

        from .fileutils import getFoldersFromObject
        from .morphing import MP
        folders = getFoldersFromObject(rig, [""], match81=True)
        table = {}
        mpaths = MP.getMorphPaths(dazRna(rig).DazMesh)
        mtypes = {}
        if mpaths:
            for morphset,paths in mpaths.items():
                for path in paths:
                    mtypes[os.path.basename(path)] = morphset
        print("Setting up morph table for %s" % dazRna(rig).DazMesh)
        for folder in folders:
            setupTable(folder, table, mtypes)
        return table


    def handleMissingMorphs(self, context, rig):
        if self.useShapekeys or not self.useLoadMissing or not self.used:
            return False

        def isRigProp(prop, rig):
            if prop in rig.keys():
                return True
            altformula = self.altmorphs.get(prop)
            if altformula:
                alt = list(altformula.keys())[0]
                return (alt in rig.keys())
            return False

        missing = []
        for prop in self.used:
            if isRigProp(prop, rig):
                continue
            pg2 = dazRna(rig).DazMorphNames.get(prop)
            if pg2 and isRigProp(pg2.s, rig):
                continue
            missing.append(prop)
        if not missing:
            return False
        elif self.useScanned:
            from .scan import loadMissingMorphs
            if loadMissingMorphs(self, context, rig, missing, self.category):
                return True
        unfound = self.loadMissingOld(context, rig, missing)
        if unfound:
            print("Missing morphs not found:\n  %s" % unfound)
        return True


theMorphTables = {}

#-------------------------------------------------------------
#   ActionOptions
#-------------------------------------------------------------

class ActionOptions:
    makeNewAction : BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName : StringProperty(
        name = "Action Name",
        description = "Name of loaded action.\nUse file name if blank",
        default = "")

    fps : FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in Daz Studio",
        default = 30)

    integerFrames : BoolProperty(
        name = "Integer Frames",
        description = "Round all keyframes to intergers",
        default = False)

    atFrameOne : BoolProperty(
        name = "Start At Frame 1",
        description = "Always start new actions at frame 1",
        default = True)

    firstFrame : IntProperty(
        name = "First Frame",
        description = "Start import with this frame",
        default = 1)

    lastFrame : IntProperty(
        name = "Last Frame",
        description = "Finish import with this frame",
        default = 250)

    usePruneAction : BoolProperty(
        name = "Prune Action",
        description = "Prune the imported action",
        default = False)

    def draw(self, context):
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
            self.layout.prop(self, "atFrameOne")
        self.layout.prop(self, "fps")
        self.layout.prop(self, "integerFrames")
        self.layout.prop(self, "firstFrame")
        self.layout.prop(self, "lastFrame")
        self.layout.prop(self, "usePruneAction")


    def clearAnimation(self, ob):
        if self.makeNewAction and ob.animation_data:
            ob.animation_data.action = None


    def nameAnimation(self, ob, dazfiles):
        if self.makeNewAction and ob.animation_data:
            act = ob.animation_data.action
            if act is None:
                pass
            elif self.actionName:
                act.name = self.actionName
            elif dazfiles:
                act.name = os.path.splitext(os.path.basename(dazfiles[0]))[0]
            else:
                act.name = "Action"

#-------------------------------------------------------------
#   AnimatorBase
#-------------------------------------------------------------

class AnimatorBase(MultiFile, DazImageFile, FrameConverter, BoneOptions, MorphOptions):
    lockMeshes = False

    def draw(self, context):
        if self.isFigure:
            self.drawFigure(context)
        else:
            self.drawProp(context)
        self.layout.separator()
        self.drawMorphs(context)


    def invoke(self, context, event):
        rig = getRigFromContext(context, strict=False)
        self.isFigure = (rig.type == 'ARMATURE')
        self.setPreferredFolder(context.object, [], self.preferredFolders, True)
        return MultiFile.invoke(self, context, event)


    def getSingleAnimation(self, filepath, context, offset):
        from .convert import getCharacterFromRig
        if filepath is None:
            return offset,None
        rig = getRigFromContext(context, strict=False, activate=True)
        scn = context.scene
        ext = os.path.splitext(filepath)[1]
        if ext in [".duf", ".dsf"]:
            struct = JL.load(filepath, False)
        else:
            raise DazError("Wrong type of file: %s" % filepath)
        self.assetType = struct.get("asset_info", {}).get("type", "preset_pose")
        if self.assetType == "preset_camera" and rig.type != 'CAMERA':
            print("Not a camera: %s" % rig.name)
            return offset,None
        elif self.assetType == "preset_light" and rig.type != 'LIGHT':
            print("Not a light: %s" % rig.name)
            return offset,None
        elif "scene" not in struct.keys():
            return offset,None
        self.trgCharacter = getCharacterFromRig(rig)
        anims = self.parseScene(struct["scene"], rig)
        if rig.type == 'ARMATURE':
            setMode('OBJECT')
            self.prepareRig(rig, scn.frame_current)
        nanims,locks,self.bonemap = self.prepareAnimations(anims, anims, rig, False)
        again = self.handleMissingMorphs(context, rig)
        if again:
            self.makePosable(context, rig, useActivate=False)
            if rig.type == 'MESH':
                skeys = rig.data.shape_keys
                if skeys and self.shapekeys != skeys.key_blocks:
                    self.shapekeys = skeys.key_blocks
            nanims,_,_ = self.prepareAnimations(anims, nanims, rig, True)
        self.clearPose(rig, offset)
        prop = None
        result = self.animateBones(context, nanims, offset, prop, filepath)
        for pb,lock in locks:
            pb.lock_location = lock
        updateDrivers(rig)
        updateScene(context)
        self.updateWinders(rig, scn.frame_current)
        setMode('OBJECT')
        return result


    def clearAnimation(self, ob):
        pass


    def nameAnimation(self, ob, dazfiles):
        pass


    def prepareRig(self, rig, frame):
        if not self.affectBones:
            return
        elif rig.data.get("rig_id"):
            from .rigify_tools import setRigifyFkIk, setRigifyLayers, clearOtherRigify
            setRigifyFkIk(rig, 1.0, self.useInsertKeys, frame)
            setRigifyLayers(rig, True, self.boneLayers)
            clearOtherRigify(rig, True, frame)
        elif rig.get("MhxRig") or dazRna(rig).DazRig == "mhx":
            from .mhx_tools import setMhxToFk
            self.boneLayers = setMhxToFk(rig, self.boneLayers, self.useInsertKeys, frame)
        elif rig.get("DazSimpleIK"):
            from .simple_ik_tools import setSimpleToFk
            self.boneLayers = setSimpleToFk(rig, self.boneLayers, self.useInsertKeys, frame)


    def snapIk(self, context, rig, frame):
        if not self.affectBones or self.snapError:
            return

        scn = context.scene
        scn.frame_current = int(frame)

        def setAuto(scn, useInsertKeys):
            auto = scn.tool_settings.use_keyframe_insert_auto
            scn.tool_settings.use_keyframe_insert_auto = useInsertKeys
            return auto

        if rig.get("MhxRig") or dazRna(rig).DazRig == "mhx":
            from .mhx_tools import setMhxToFk
            try:
                auto = setAuto(scn, self.useInsertKeys)
                bpy.ops.mhx.snap_ik_all()
                setAuto(scn, auto)
                self.boneLayers = setMhxToFk(rig, self.boneLayers, False, frame)
            except AttributeError:
                self.snapError = True
        elif rig.data.get("rig_id"):
            from .rigify_tools import setRigifyFkIk
            try:
                auto = setAuto(scn, self.useInsertKeys)
                bpy.ops.daz.rigify_snap_ik_all()
                setAuto(scn, auto)
                setRigifyFkIk(rig, 1.0, False, frame)
            except KeyError:    #AttributeError:
                self.snapError = True
        elif rig.get("DazSimpleIK"):
            from .simple_ik_tools import setSimpleToFk
            try:
                auto = setAuto(scn, self.useInsertKeys)
                bpy.ops.daz.snap_all_simple_ik()
                setAuto(scn, auto)
                self.boneLayers = setSimpleToFk(rig, self.boneLayers, False, frame)
            except AttributeError:
                self.snapError = True


    def enableIk(self, rig):
        if self.snapError:
            return
        if rig.animation_data and rig.animation_data.action:
            fcurves = getActionBag(rig.animation_data.action).fcurves
        else:
            fcurves = []

        def removeFcurves(paths):
            for fcu in list(fcurves):
                if fcu.data_path in paths:
                    fcurves.remove(fcu)

        if rig.get("MhxRig") or dazRna(rig).DazRig == "mhx":
            props = ["MhaArmIk_L", "MhaArmIk_R", "MhaLegIk_L", "MhaLegIk_R"]
            removeFcurves(props)
            for prop in props:
                rig[prop] = 1.0
            from .mhx_tools import setMhxLayers
            self.boneLayers = setMhxLayers(rig, self.boneLayers, True)
        elif rig.data.get("rig_id"):
            from .rigify_tools import setRigifyLayers
            setRigifyLayers(rig, False, self.boneLayers)
        elif rig.get("DazSimpleIK"):
            props = ["DazArmIK_L", "DazArmIK_R", "DazLegIK_L", "DazLegIK_R"]
            paths = [propRef(prop) for prop in props]
            removeFcurves(paths)
            for prop in props:
                rig[prop] = 1.0
            from .simple_ik_tools.simple import setSimpleLayers
            self.boneLayers = setSimpleLayers(rig, self.boneLayers, True)


    def updateWinders(self, rig, frame):
        if not self.affectBones:
            return
        if rig.get("MhxRig") or dazRna(rig).DazRig == "mhx":
            from .mhx_tools import mhx
            mhx.updateMhxWinders(rig, frame)
        elif rig.get("DazSimpleIK"):
            pass


    def parseScene(self, struct, rig):
        anims = []
        banims = OrderedDict()
        vanims = {}
        xanims = {}
        interps = {}
        self.parseAnimations(struct, banims, vanims, xanims, interps, rig)
        self.completeAnimations(banims)
        blist = list(banims.items())
        blist.reverse()
        banims = OrderedDict(blist)
        anims.append((banims, vanims, xanims, interps))
        return anims

    #-------------------------------------------------------------
    #
    #-------------------------------------------------------------

    def parseAnimations(self, struct, banims, vanims, xanims, interps, rig):
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
            key = unquote(key)
            words = url.rsplit("?", 2)
            if len(words) != 2:
                return None,None,None
            words = words[1].split("/")
            if len(words) in [2,3]:
                channel = words[0]
                comp = words[1]
                return key,channel,comp
            elif words[0] == "extra":
                channel = unquote(words[-2])
                comp = words[-1]
                return "extra",channel,comp
            else:
                return None,None,None

        def getAnimKeys(anim):
            return [key[0:2] for key in anim["keys"]]

        def getInterpolation(anim):
            key = anim["keys"][0]
            return ('BEZIER' if len(key) == 2 else
                    'LINEAR' if 'LINEAR' in key[2] else
                    'CONSTANT' if 'CONSTANT' in key[2] else
                    'BEZIER')

        blendkeys = {
            "translation" : "location",
            "rotation" : "rotation_euler",
            "scale" : "scale",
        }

        if "animations" in struct.keys():
            for anim in struct["animations"]:
                if "url" in anim.keys():
                    key,channel,comp = getChannel(anim["url"])
                    if channel is None:
                        continue
                    elif channel == "value":
                        if self.affectMorphs:
                            vanims[key] = getAnimKeys(anim)
                            interps[key] = getInterpolation(anim)
                    elif channel in ["translation", "rotation", "scale"]:
                        if key not in banims.keys():
                            banims[key] = {
                                "translation" : {},
                                "rotation" : {},
                                "scale" : {},
                                "general_scale" : {},
                                }
                        idx = getIndex(comp)
                        if idx >= 0:
                            banims[key][channel][idx] = getAnimKeys(anim)
                        else:
                            banims[key]["general_scale"][0] = getAnimKeys(anim)
                        bchannel = blendkeys.get(channel)
                        if bchannel is None:
                            print("Unknown channel", channel)
                        elif self.isObject(key, rig):
                            interps[bchannel] = getInterpolation(anim)
                        else:
                            interps['pose.bones["%s"].%s' % (key, bchannel)] = getInterpolation(anim)
                    elif key == "extra":
                        xanims[channel] = getAnimKeys(anim)
                        interps[channel] = getInterpolation(anim)
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


    def completeAnimations(self, banims):
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
        for bname in banims.keys():
            for channel in banims[bname].keys():
                for idx in banims[bname][channel].keys():
                    for t,y in banims[bname][channel][idx]:
                        frames[t] = True
        if not frames:
            return
        frames = list(frames)
        frames.sort()
        for bname in banims.keys():
            for channel in banims[bname].keys():
                for idx,anim in banims[bname][channel].items():
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
                    banims[bname][channel][idx] = anim


    def isAvailable(self, pb, rig):
        if pb.name == self.getMasterBone(rig):
            return False
        elif self.affectSelectedOnly:
            if pb.bone.select:
                if BLENDER3:
                    for rlayer,blayer in zip(self.boneLayers, pb.bone.layers):
                        if rlayer and blayer:
                            return True
                else:
                    for coll in self.boneLayers.values():
                        if pb.bone.name in coll.bones:
                            return True
            return False
        else:
            return True


    def getMasterBone(self, rig):
        if dazRna(rig).DazRig == "mhx":
            master = "master"
        elif dazRna(rig).DazRig.startswith("rigify"):
            master = "root"
        elif rig.get("DazSimpleIK"):
            master = "Root"
        else:
            return None
        if master in rig.pose.bones.keys():
            return master

    #-------------------------------------------------------------
    #   Clear pose
    #-------------------------------------------------------------

    def clearPose(self, rig, frame):
        def clearShapes(ob):
            if ob.type == 'MESH' and ob.data.shape_keys:
                for skey in ob.data.shape_keys.key_blocks:
                    skey.value = 0.0
                    if self.useInsertKeys:
                        skey.keyframe_insert("value", frame=frame)

        self.worldMatrix = rig.matrix_world.copy()
        tfm = Transform()
        if self.useClearPose and self.affectObject:
            tfm.setObject(rig)
            if self.useInsertKeys:
                insertKeys(rig, None, frame, self)
        if self.useClearMorphs and self.useShapekeys and self.affectMorphs:
            clearShapes(rig)
        if rig.type != 'ARMATURE':
            return
        if self.useClearPose and self.affectBones and rig.pose:
            for pb in rig.pose.bones:
                if self.isAvailable(pb, rig):
                    scale = pb.scale.copy()
                    pb.matrix_basis = Matrix()
                    if not self.affectScale:
                        pb.scale = scale
                    if self.useInsertKeys:
                        insertKeys(pb, rig, frame, self)
            setChildofInverses(rig)
        if self.useClearMorphs and self.affectMorphs:
            if self.useShapekeys:
                for ob in rig.children:
                    clearShapes(ob)
            else:
                from .morphing import clearAllMorphs
                clearAllMorphs(rig, frame, self.useInsertKeys)


    def isObject(self, bname, ob):
        KnownRigs = [
            "@selection",
            "Genesis",
            "GenesisFemale",
            "GenesisMale",
            "Genesis2",
            "Genesis2Female",
            "Genesis2Male",
            "Genesis3",
            "Genesis3Female",
            "Genesis3Male",
            "Genesis8",
            "Genesis8Female",
            "Genesis8Male",
            "Genesis9",
        ]
        if bname in KnownRigs:
            return True
        else:
            return (bname != "_XTRA_" and
                    self.assetType in ["preset_camera", "preset_light"])

    #-------------------------------------------------------------
    #   Animate bones
    #-------------------------------------------------------------

    def getDefaultTranslation(self, rig, bname):
        return Zero


    def getDefaultRotation(self, rig, bname):
        return Zero


    def getDefaultScale(self, rig, bname):
        return One


    def animateBones(self, context, anims, offset, prop, filepath):
        rig = context.object
        errors = {}
        for banim,vanim,xanim,interps in anims:
            frames = {}
            n = -1
            for bname, channels in banim.items():
                for key,channel in channels.items():
                    if key == "translation":
                        default = self.getDefaultTranslation(rig, bname)
                        self.addFrames(bname, channel, 3, key, frames, default=default)
                    elif key == "rotation":
                        default = self.getDefaultRotation(rig, bname)
                        self.addFrames(bname, channel, 3, key, frames, default=default)
                    elif key == "scale":
                        default = self.getDefaultScale(rig, bname)
                        self.addFrames(bname, channel, 3, key, frames, default=default)
                    elif key == "general_scale":
                        self.addFrames(bname, channel, 1, key, frames)

            for vname, channels in vanim.items():
                self.addFrames(vname, {0: channels}, 1, "value", frames)
            for xname, channels in xanim.items():
                self.addFrames("_XTRA_", {0: channels}, 1, xname, frames)

            if not frames:
                continue
            lframes = list(frames.items())
            lframes.sort()
            self.clearScales(rig, lframes[0][0]+offset)
            self.olddata = {}
            self.dataRnas = set()
            for n,frame in lframes:
                twists = {}
                self.addTwists(frame)
                for bname,bframe in frame.items():
                    tfm = Transform()
                    value = 0.0
                    for key in bframe.keys():
                        if key == "translation":
                            tfm.setTrans(bframe["translation"], prop)
                        elif key == "rotation":
                            tfm.setRot(bframe["rotation"], prop)
                        elif key == "scale":
                            if self.affectScale or self.isObject(bname, rig):
                                tfm.setScale(bframe["scale"], False, prop)
                        elif key == "general_scale":
                            if self.affectScale or self.isObject(bname, rig):
                                tfm.setGeneral(bframe["general_scale"], False, prop)
                        elif key == "value" and self.affectMorphs:
                            value = bframe["value"][0]
                            self.makeValueFrame(bname, rig, bframe, value, n, offset)
                        elif bname != "_XTRA_":
                            print("Unknown key:", bname, key)
                    if self.isObject(bname, rig):
                        self.makeObjectFrame(bname, rig, bframe, tfm, n, offset)
                    elif bname == "_XTRA_":
                        self.makeDataFrame(rig, bframe, n, offset)
                    elif rig.type == 'ARMATURE':
                        self.makeBoneFrame(bname, rig, bframe, tfm, n, offset, twists)
                self.correctTwists(twists, rig, n, offset)
                self.saveScales(rig, n+offset)
                if self.useSnapIk:
                    self.snapIk(context, rig, n+offset)

            self.fixScales(rig)
            self.fixInterpolation(rig, anims)
            self.addToAsset(rig, filepath)
            offset += n + 1
        if self.useSnapIk:
            self.enableIk(rig)
        return offset,prop


    def makeObjectFrame(self, bname, rig, bframe, tfm, n, offset):
        if not self.affectObject:
            pass
        else:
            tfm.setObject(rig)
            if rig.type in ['LIGHT', 'CAMERA'] and GS.zup:
                rig.rotation_euler[0] += pi/2
            if self.useInsertKeys:
                insertKeys(rig, None, n+offset, self, tfm)


    def makeBoneFrame(self, bname, rig, bframe, tfm, n, offset, twists):
        if bname in rig.data.bones.keys():
            self.transformBone(rig, bname, tfm, n, offset, False)
            if bname.endswith(("Bend", "Twist")):
                twists[bname] = tfm
        elif bname[0:6] == "TWIST-":
            twists[bname[6:]] = tfm


    def makeValueFrame(self, bname, rig, bframe, value, n, offset):
        def setRigProp(rig, key, value, n, offset):
            if key:
                rig[key] = castValue(value, rig[key])
                if self.useInsertKeys:
                    rig.keyframe_insert(propRef(key), frame=n+offset, group="Morphs")

        def setShapeValue(ob, key, value, n, offset):
            if ob.type == 'MESH' and ob.data.shape_keys:
               skey = ob.data.shape_keys.key_blocks.get(key)
               if skey:
                   skey.value = value
                   if self.useInsertKeys:
                        skey.keyframe_insert("value", frame=n+offset)

        prop = unquote(bname)
        if rig.type == 'MESH':
            setShapeValue(rig, prop, value, n, offset)
        elif rig.type == 'ARMATURE':
            key = self.getRigKey(prop, rig, value)
            final = finalProp(prop)
            if self.useShapekeys:
                for ob in rig.children:
                    setShapeValue(ob, prop, value, n, offset)
            elif key:
                setRigProp(rig, key, value, n, offset)
            elif final in rig.data.keys():
                setRigProp(rig.data, final, value, n, offset)
            else:
                for ob in rig.children:
                    setShapeValue(ob, prop, value, n, offset)


    def makeDataFrame(self, ob, dazdata, n, offset):
        if self.assetType == "preset_camera":
            from .camera import getBlenderData
            dtype = 'CAMERA'
        elif self.assetType == "preset_light":
            from .light import getBlenderData
            dtype = 'LIGHT'
        else:
            return
        bdata = getBlenderData(ob.data, dazdata, self, n+offset)
        for attrs,value in bdata.items():
            rna = ob.data
            self.dataRnas.add((rna, dtype))
            words = attrs.split(".")
            for attr in words[:-1]:
                if hasattr(rna, attr):
                    rna = getattr(rna, attr)
                    if hasattr(rna, "animation_data"):
                        self.dataRnas.add((rna, dtype))
            attr = words[-1]
            if hasattr(rna, attr):
                setattr(rna, attr, value)
                if self.useInsertKeys:
                    rna.keyframe_insert(attr, frame=n+offset)


    def fixInterpolation(self, ob, anims):
        def fixFcurves(rna, id_type, interps):
            if rna.animation_data and rna.animation_data.action:
                fcurves = getActionBag(rna.animation_data.action, id_type).fcurves
                for fcu in fcurves:
                    path = dazkeys.get(fcu.data_path, fcu.data_path)
                    interp = interps.get(path)
                    if interp:
                        for kp in fcu.keyframe_points:
                            kp.interpolation = interp

        if self.assetType == "preset_camera":
            from .camera import getDazKeys
            dazkeys = getDazKeys()
        elif self.assetType == "preset_light":
            from .light import getDazKeys
            dazkeys = getDazKeys()
        else:
            dazkeys = {}
        for banim,vanim,xanim,interps in anims:
            fixFcurves(ob, 'OBJECT', interps)
            for rna,id_type in self.dataRnas:
                fixFcurves(rna, id_type, interps)


    def addToAsset(self, rig, filepath):
        pass

    #-------------------------------------------------------------
    #   Add frames
    #-------------------------------------------------------------

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
                    self.setFrameComp(bframe, cname, comp, y)


    def setFrameComp(self, bframe, cname, comp, y):
        bframe[cname][comp] = y


    def clearScales(self, rig, frame):
        if not self.affectScale or rig.type != 'ARMATURE':
            return
        self.scales = {}
        for pb in rig.pose.bones:
            if self.isAvailable(pb, rig):
                pb.scale = One
                if self.useInsertKeys:
                    pb.keyframe_insert("scale", frame=frame, group=pb.name)


    def saveScales(self, rig, frame):
        if not self.affectScale or rig.type != 'ARMATURE':
            return
        self.scales[frame] = dict([(pb.name, Matrix.Diagonal(pb.scale)) for pb in rig.pose.bones])


    def fixScales(self, rig):
        if not self.affectScale or rig.type != 'ARMATURE':
            return
        for frame,smats in self.scales.items():
            for pb in rig.pose.bones:
                if inheritsScale(pb) and self.isAvailable(pb, rig):
                    smat = smats[pb.name] @ smats[pb.parent.name].inverted()
                    pb.scale = smat.to_scale()
                    if self.useInsertKeys:
                        pb.keyframe_insert("scale", frame=frame, group=pb.name)


    def getRigKey(self, prop, rig, value):
        if self.affectGeograft != "-":
            prop2 = "%s:%s" % (prop, self.affectGeograft)
            if prop2 in rig.keys():
                return prop2
        if prop in rig.keys():
            return prop
        pg = dazRna(rig).DazMorphNames.get(prop)
        if pg and pg.s in rig.keys():
            return pg.s
        return None


    def transformBone(self, rig, bname, tfm, n, offset, useTwist):
        from .node import setBoneTransform

        if not self.affectBones:
            return
        pb = rig.pose.bones[bname]
        if self.isAvailable(pb, rig):
            if useTwist:
                self.setBoneTwist(tfm, pb, rig)
            else:
                if not self.affectScale:
                    tfm.setScale(pb.scale, False)
                oldStyle = (self.useConvert or
                            not dazRna(rig.data).DazHasAxes or
                            dazRna(rig).DazRig.startswith("rigify"))
                setBoneTransform(tfm, pb, rig, bonemap=self.bonemap, oldStyle=oldStyle)
            imposeLocks(pb)
            if self.useInsertKeys:
                insertKeys(pb, rig, n+offset, self, tfm)


    def setBoneTwist(self, tfm, pb, rig):
        def newEuler(pb, y):
            if pb.rotation_mode == 'QUATERNION':
                xyz = BD.getDefaultMode(pb)
                euler = pb.matrix_basis.to_3x3().to_euler(xyz)
                euler.y = y*D
            else:
                euler = pb.matrix_basis.to_3x3().to_euler(pb.rotation_mode)
                euler.y = y*D
            return euler

        if pb.name not in BD.BoneTwistInfo.keys():
            print("Not a twist bone: %s" % pb.name)
            return
        idx,sign = BD.BoneTwistInfo[pb.name]
        y = sign*tfm.rot[idx]
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = newEuler(pb, y).to_quaternion()
        elif pb.lock_rotation[1] and pb.name.startswith("forearm") and pb.children:
            hand = pb.children[0]
            if hand.name.startswith("hand"):
                hand.rotation_euler = newEuler(hand, y)
            else:
                pb.rotation_euler = newEuler(pb, y)
        else:
            pb.rotation_euler = newEuler(pb, y)


    def addTwists(self, frame):
        for prefix in ["l", "r"]:
            for bname,idx in [("Shldr",0), ("Forearm",0), ("Thigh",1)]:
                bendname = self.bonemap.get("%s%sBend" % (prefix, bname))
                twistname = self.bonemap.get("%s%sTwist" % (prefix, bname))
                bendframe = frame.get(bendname, {})
                bendrot = bendframe.get("rotation", Zero)
                ybend = bendrot[idx]
                if abs(ybend) > 1e-5:
                    twistframe = frame.get(twistname)
                    if twistframe is None:
                        twistframe = frame[twistname] = {}
                    twistrot = twistframe.get("rotation", Vector((0,0,0)))
                    twistrot[idx] += ybend
                    twistframe["rotation"] = twistrot
                    bendrot[idx] = 0


    def correctTwists(self, twists, rig, n, offset):
        for bname,tfm in twists.items():
            if bname[-4:] == "Bend":
                bend = rig.pose.bones[bname]
                if bend.rotation_mode == 'QUATERNION':
                    xyz = BD.getDefaultMode(bend)
                    euler = bend.rotation_quaternion.to_euler(xyz)
                else:
                    euler = bend.rotation_euler
                if abs(euler[1]) < 1e-4:
                    continue
                twist = rig.pose.bones.get("%sTwist" % bname[:-4])
                if twist and abs(twist.rotation_euler[1]) < 1e-4:
                    twist.rotation_euler = (0, euler[1], 0)
                    if self.useInsertKeys:
                        insertKeys(twist, rig, n+offset, self)
                euler[1] = 0
                if bend.rotation_mode == 'QUATERNION':
                    bend.rotation_quaternion = euler.to_quaternion()
                else:
                    bend.rotation_euler = euler
                if self.useInsertKeys:
                    insertKeys(bend, rig, n+offset, self)
            elif bname[-5:] == "Twist":
                twist = rig.pose.bones[bname]
                twist.rotation_euler[0] = twist.rotation_euler[2] = 0
                if self.useInsertKeys:
                    insertKeys(twist, rig, n+offset, self)
            else:
                self.transformBone(rig, bname, tfm, n, offset, True)


    def findDrivers(self, rig):
        transforms = [
            "rotation_euler",
            "rotation_quaternion",
            "location",
            "scale",
        ]
        self.driven = {}
        if (rig.animation_data and
            rig.animation_data.drivers):
            for fcu in rig.animation_data.drivers:
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname and channel in transforms:
                    if bname not in self.driven.keys():
                        self.driven[bname] = []
                    self.driven[bname].append(channel)

#-------------------------------------------------------------
#
#-------------------------------------------------------------


class StandardAnimation:

    def run(self, context):
        from .uilist import updateScrollbars
        from .scan import getCharData, initScannedInfo, loadScannedInfo, checkNeedUpdates
        dazfiles = self.getMultiFiles(["dsf", "duf"])
        nfiles = len(dazfiles)
        if nfiles == 0:
            raise DazError("No corresponding DAZ file selected")
        self.verbose = (nfiles == 1)

        rig, mesh, name, relpath = getCharData(context, False)
        if rig is None:
            rig = context.object
        if rig is None:
            raise DazError("No object selected")
        initScannedInfo(self)
        self.shapekeys = {}
        self.altmorphs = {}
        if self.affectMorphs:
            if mesh and mesh.data.shape_keys:
                self.shapekeys = mesh.data.shape_keys.key_blocks
            elif rig:
                for ob in rig.children:
                    if ob.type == 'MESH' and ob.data.shape_keys:
                        for sname in ob.data.shape_keys.key_blocks.keys():
                            self.shapekeys[sname] = True
            self.altmorphs = loadAltMorphs(rig)
        found = False
        if self.affectMorphs and self.useScanned and rig and not self.useShapekeys:
            found = loadScannedInfo(self, name, rig, relpath)
        if not found and rig.type == 'ARMATURE':
            self.setupAlias(rig)
        scn = context.scene
        if scn.tool_settings.use_keyframe_insert_auto:
            self.useInsertKeys = True
        else:
            self.useInsertKeys = self.useAction

        if not self.affectSelectedOnly:
            selected = self.selectAll(rig, True)
        LS.forAnimation(self, rig)
        self.findDrivers(rig)
        self.clearAnimation(rig)
        self.missing = {}
        self.used = {}
        self.snapError = False
        startframe = offset = scn.frame_current
        props = []
        t1 = perf_counter()
        print("\n--------------------")

        for filepath in dazfiles:
            if self.atFrameOne and self.makeNewAction and len(dazfiles) == 1:
                offset = 1
            print("*", os.path.basename(filepath), offset)
            offset,prop = self.getSingleAnimation(filepath, context, offset)
            if prop:
                props.append(prop)

        if self.usePruneAction and self.useInsertKeys:
            if rig and rig.animation_data and rig.animation_data.action:
                pruneAction(rig.animation_data.action, rig, GS.scale)

        t2 = perf_counter()
        if self.snapError:
            print("MHX/Simple IK module not enabled")
        print("File %s imported in %.3f seconds" % (self.filepath, t2-t1))
        scn.frame_current = startframe
        updateScrollbars(context)
        self.nameAnimation(rig, dazfiles)
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


    def setupAlias(self, rig):
        from .driver import getPropMinMax
        from .scan import normKey
        alias1 = [(key, pg.s) for key,pg in dazRna(rig).DazAlias.items()]
        alias2 = [(pg.s, key) for key,pg in dazRna(rig).DazAlias.items()]
        self.alias = dict(alias1 + alias2)
        for prop in rig.data.keys():
            if isFinal(prop):
                key = normKey(baseProp(prop))
                self.minmax[key] = getPropMinMax(rig.data, prop, False)[0:2]


def loadAltMorphs(rig):
    if rig is None:
        return {}
    char = dazRna(rig).DazMesh.split("-",1)[0].lower()
    struct = DF.loadEntry(char, "altmorphs", False)
    if struct:
        return struct["morphs"]
    else:
        return {}

#-------------------------------------------------------------
#   Import Node Pose
#-------------------------------------------------------------

class NodePose:
    def getId(self, ob):
        return dazRna(ob).DazUrl.rsplit("#",1)[-1]


    def setFrameComp(self, bframe, cname, comp, y):
        if cname in ("translation", "rotation") and y == 0:
            return
        bframe[cname][comp] = y


    def getDefaultTranslation(self, rig, bname):
        if not self.isObject(bname, rig) and rig.type == 'ARMATURE':
            pb = rig.pose.bones.get(bname)
            if pb:
                return Vector(dazRna(pb).DazTranslation)
        return Zero


    def getDefaultRotation(self, rig, bname):
        if not self.isObject(bname, rig) and rig.type == 'ARMATURE':
            pb = rig.pose.bones.get(bname)
            if pb:
                return Vector(dazRna(pb).DazRotation)
        return Zero


    def parseAnimations(self, struct, banims, vanims, xanims, interps, rig):
        rigid = self.getId(rig)
        active = False
        if "nodes" in struct.keys() and self.affectBones and rig and rig.pose:
            for node in struct["nodes"]:
                key = node["id"]
                if key == rigid:
                    active = True
                    key = "@selection"
                elif not active:
                    continue
                elif node.get("geometries"):
                    break
                key = skipName(key)
                self.addTransform(node, "translation", banims, key, Zero)
                self.addTransform(node, "rotation", banims, key, Zero)
                self.addTransform(node, "scale", banims, key, One)
                #self.addTransform(node, "general_scale", banims, key)
        elif self.verbose:
            print("No nodes in this file")

        meshids = []
        for ob in getMeshChildren(rig):
            meshid = self.getId(ob)
            meshids.append("#%s" % meshid)
        if "modifiers" in struct.keys() and self.affectMorphs:
            for mod in struct["modifiers"]:
                key = unquote(mod.get("id", ""))
                value = mod.get("channel", {}).get("current_value")
                if mod.get("parent") in meshids and value is not None:
                    vanims[key] = [[0, value]]


    def addTransform(self, node, channel, banims, key, default):
        if key not in banims.keys():
            banims[key] = {}
        banim = banims[key]
        if channel not in banim.keys():
            banim[channel] = {
                0: [[0, default[0]]],
                1: [[0, default[1]]],
                2: [[0, default[2]]]
            }
        for struct in node.get(channel, []):
            comp = struct["id"]
            value = struct["current_value"]
            banim[channel][getIndex(comp)] = [[0, value]]

#-------------------------------------------------------------
#   Import Action
#-------------------------------------------------------------

class DAZ_OT_ImportAction(HideOperator, ActionOptions, AnimatorBase, StandardAnimation, IsObject):
    bl_idname = "daz.import_action"
    bl_label = "Import Action"
    bl_description = "Import poses from DAZ pose preset file(s) to action"
    bl_options = {'UNDO', 'PRESET'}

    verbose = False
    useAction = True
    useAsset = False
    preferredFolders = ["Poses/"]

    def draw(self, context):
        AnimatorBase.draw(self, context)
        self.layout.separator()
        ActionOptions.draw(self, context)

    def run(self, context):
        StandardAnimation.run(self, context)

#-------------------------------------------------------------
#   Import Asset
#-------------------------------------------------------------

class DAZ_OT_ImportAsset(HideOperator, ActionOptions, AnimatorBase, StandardAnimation, IsArmature):
    bl_idname = "daz.import_asset"
    bl_label = "Import Asset"
    bl_description = "Import poses and morphs from DAZ pose preset file(s) to Blender assets"
    bl_options = {'UNDO', 'PRESET'}

    verbose = False
    useAction = True
    useAsset = True
    preferredFolders = ["Poses/"]

    if bpy.app.version < (3,3,0):
        useAssetBrowser = False

        makeNewPoselib : BoolProperty(
            name = "New PoseLib",
            description = "Unlink current pose library and make a new one",
            default = True)

        poselibName : StringProperty(
            name = "PoseLib Name",
            description = "Name of loaded poselib",
            default = "PoseLib")
    else:
        useAssetBrowser = True
        makeNewPoselib = False
        poselibName = ""

        usePreviewImages : BoolProperty(
            name = "Import Previews",
            description = "Import preview images for imported poses",
            default = True)

        assetTags : StringProperty(
            name = "Tags",
            description = "List of tags to add to the imported Poses",
            default = "")

        assetAuthor : StringProperty(name = "Author")
        assetDescription : StringProperty(name = "Description")
        assetLicense : StringProperty(name = "License")
        assetCopyright : StringProperty(name = "Copyright")


    def draw(self, context):
        AnimatorBase.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "usePruneAction")
        if self.useAssetBrowser:
            self.layout.prop(self, "usePreviewImages")
            self.layout.prop(self, "assetTags")
            self.layout.prop(self, "assetAuthor")
            self.layout.prop(self, "assetDescription")
            self.layout.prop(self, "assetLicense")
            self.layout.prop(self, "assetCopyright")
        else:
            self.layout.prop(self, "makeNewPoselib")
            if self.makeNewPoselib:
                self.layout.prop(self, "poseLibName")


    def clearAnimation(self, ob):
        if self.makeNewPoselib and ob.pose_library:
            ob.pose_library = None


    def nameAnimation(self, ob, dazfiles):
        if self.makeNewPoselib and ob.pose_library:
            ob.pose_library.name = self.poseLibName


    def addToAsset(self, rig, filepath):
        if rig.type != 'ARMATURE' or rig.animation_data is None:
            return
        setMode('POSE')
        name = os.path.splitext(os.path.basename(filepath))[0]
        if self.useAssetBrowser:
            self.addToAssetBrowser(rig, filepath, name)
        else:
            self.addToOldAsset(rig, filepath, name)


    def addToAssetBrowser(self, rig, filepath, name):
        if rig and rig.animation_data:
            act = rig.animation_data.action
        elif self.useAction:
            raise DazError("No action generated for %s" % name)
        setMode('OBJECT')
        if hasattr(act, "asset_mark"):
            act.asset_mark()
            act.name = name
            rig.animation_data.action = None
        else:
            try:
                bpy.ops.poselib.create_pose_asset(pose_name=name, activate_new_action=True)
            except RuntimeError as err:
                words = str(err).split("()")
                msg = "()\n".join(words)
                raise DazError(msg)
            act = rig.animation_data.action
            if act is None:
                return
        keep = ["location", "rotation_euler", "rotation_quaternion"]
        if self.affectScale:
            keep.append("scale")
        fcurves = getActionBag(act).fcurves
        for fcu in list(fcurves):
            if not isPropRef(fcu.data_path):
                words = fcu.data_path.rsplit(".", 1)
                if words[-1] not in keep:
                    fcurves.remove(fcu)
        if self.usePreviewImages:
            previewFile = self.getPreviewFile(filepath, name)
        else:
            previewFile = None
        with bpy.context.temp_override(id=act):
            if previewFile:
                bpy.ops.ed.lib_id_load_custom_preview(filepath=previewFile)
            else:
                bpy.ops.ed.lib_id_generate_preview()

        assetdata = act.id_data.asset_data
        if self.assetTags:
            tagList=self.assetTags.split(",")
            for newTag in tagList:
                assetdata.tags.new(newTag)
        if self.assetAuthor:
            assetdata.author=self.assetAuthor
        if self.assetDescription:
            assetdata.description=self.assetDescription
        if self.assetLicense:
            assetdata.license=self.assetLicense
        if self.assetCopyright:
            assetdata.copyright=self.assetCopyright


    def addToOldAsset(self, rig, filepath, name):
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
        setMode('OBJECT')


    def getPreviewFile(self, filepath, name):
        from .fileutils import theImageExtensions
        basename,ext = os.path.splitext(filepath)
        for ext in theImageExtensions:
            for pathname in ["%s.tip" % basename, filepath, basename]:
                path = "%s.%s" % (pathname, ext)
                if os.path.exists(path):
                    return path
        print("No preview file found for %s" % name)


    def run(self, context):
        StandardAnimation.run(self, context)

#-------------------------------------------------------------
#   Import Single Pose
#-------------------------------------------------------------

class PoseBase(AnimatorBase):
    verbose = False
    useAction = False
    useAsset = False
    atFrameOne = False
    firstFrame = -1000
    lastFrame = 1000
    usePruneAction = False

    def draw(self, context):
        AnimatorBase.draw(self, context)
        toolset = context.scene.tool_settings
        self.layout.prop(toolset, "use_keyframe_insert_auto")


class DAZ_OT_ImportPose(HideOperator, PoseBase, StandardAnimation, IsObject):
    bl_idname = "daz.import_pose"
    bl_label = "Import Pose"
    bl_description = "Import a pose from DAZ pose preset file(s)"
    bl_options = {'UNDO', 'PRESET'}

    preferredFolders = ["Poses/"]

    def invoke(self, context, event):
        self.affectMorphs = False
        return AnimatorBase.invoke(self, context, event)

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportExpression(HideOperator, PoseBase, StandardAnimation, IsMeshArmature):
    bl_idname = "daz.import_expression"
    bl_label = "Import Expression"
    bl_description = "Import an expression from DAZ pose preset file(s)"
    bl_options = {'UNDO', 'PRESET'}

    preferredFolders = ["Expressions/"]

    def invoke(self, context, event):
        self.affectBones = False
        self.affectObject = False
        return AnimatorBase.invoke(self, context, event)

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportNodePose(NodePose, HideOperator, PoseBase, StandardAnimation, IsMeshArmature):
    bl_idname = "daz.import_node_pose"
    bl_label = "Import Pose From Scene"
    bl_description = "Import a pose from DAZ scene file(s) (not pose preset files)"
    bl_options = {'UNDO', 'PRESET'}

    preferredFolders = []

    def storeState(self, context):
        self.selObjects = getSelectedObjects(context)
        HideOperator.storeState(self, context)

    def hideLayerColls(self, rig, layer):
        pass

    def invoke(self, context, event):
        self.affectMorphs = True
        return AnimatorBase.invoke(self, context, event)

    def run(self, context):
        for ob in getSelectedObjects(context):
            activateObject(context, ob)
            StandardAnimation.run(self, context)

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

class DAZ_OT_ClearPose(DazOperator, IsObject):
    bl_idname = "daz.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Clear all bones and object transformations"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        scn = context.scene
        for ob in getSelectedObjects(context):
            rig = getRigFromMesh(ob)
            if rig:
                ob = rig
            clearPose(ob, scn.frame_current, scn.tool_settings.use_keyframe_insert_auto)


def clearPose(rig, frame, auto):
    unit = Matrix()
    setWorldMatrix(rig, unit)
    if auto:
        insertKeys(rig, None, frame)
    if rig.pose:
        for pb in rig.pose.bones:
            pb.matrix_basis = unit
            if auto:
                insertKeys(pb, rig, frame)
        setChildofInverses(rig)


def insertKeys(pb, rig, frame, btn=None, tfm=None):
    if rig:
        if (isDrvBone(pb.name) or
            pb.name.startswith(("DEF-", "MCH-", "ORG-")) or
            isInNumLayer(pb, rig, ("Help", "Help 2", "Hidden"))):
            return
    driven = []
    if btn:
        driven = btn.driven.get(pb.name, [])
    if ((tfm is None or tfm.trans) and
        (rig is None or not isLocationLocked(pb)) and
        "location" not in driven):
        pb.keyframe_insert("location", group=pb.name, frame=frame)
    if tfm is None or tfm.rot:
        if pb.rotation_mode != 'QUATERNION':
            if "rotation_euler" not in driven:
                pb.keyframe_insert("rotation_euler", group=pb.name, frame=frame)
        else:
            if "rotation_quaternion" not in driven:
                pb.keyframe_insert("rotation_quaternion", group=pb.name, frame=frame)
    if ((tfm is None or tfm.scale) and
        "scale" not in driven):
        pb.keyframe_insert("scale", group=pb.name, frame=frame)


def setChildofInverses(rig):
    for pb in rig.pose.bones:
        for cns in pb.constraints:
            if cns.type == 'CHILD_OF':
                rig.data.bones.active = pb.bone
                print("SET INV", pb.name, cns.name)
                bpy.ops.constraint.childof_set_inverse(constraint=cns.name, owner='BONE')
                print("DONE")


def imposeLocks(pb):
    for n in range(3):
        if pb.lock_location[n]:
            pb.location[n] = 0
        if pb.lock_scale[n]:
            pb.scale[n] = 1
    if pb.rotation_mode == 'QUATERNION':
        if pb.lock_rotation_w:
            pb.rotation_quaternion[0] = 1
        for n in range(3):
            if pb.lock_rotation[n]:
                pb.rotation_quaternion[n+1] = 0
    else:
        for n in range(3):
            if pb.lock_rotation[n]:
                pb.rotation_euler[n] = 0

#----------------------------------------------------------
#   Prune action
#----------------------------------------------------------

def pruneAction(act, ob, cm):
    def matchAll(kpts, default, eps):
        for kp in kpts:
            if abs(kp.co[1] - default) > eps:
                return False
        return True

    deletes = []
    fcurves = getActionBag(act).fcurves
    for fcu in fcurves:
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
        fcurves.remove(fcu)


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
        pruneAction(ob.animation_data.action, ob, GS.scale)

#----------------------------------------------------------
#   FrameRange
#----------------------------------------------------------

class FrameRange(DazPropsOperator):
    startFrame : IntProperty(
        name = "Start Frame",
        description = "Starting frame for the animation",
        default = 1)

    endFrame : IntProperty(
        name = "Last Frame",
        description = "Last frame for the animation",
        default = 250)

    def draw(self, context):
        if self.auto:
            self.layout.prop(self, "startFrame")
            self.layout.prop(self, "endFrame")
        else:
            scn = context.scene
            self.layout.prop(scn.tool_settings, "use_keyframe_insert_auto")

    def getActiveFrames(self):
        def getActiveFrames0(rig):
            active = {}
            if rig.animation_data is None or rig.animation_data.action is None:
                return active
            fcurves = getActionBag(rig.animation_data.action).fcurves
            for fcu in fcurves:
                for kp in fcu.keyframe_points:
                    active[kp.co[0]] = True
            return active

        active = getActiveFrames0(self.rig)
        frames = list(active.keys())
        if not frames:
            return frames
        frames.sort()
        while frames[0] < self.startFrame:
            frames = frames[1:]
        frames.reverse()
        while frames[0] > self.endFrame:
            frames = frames[1:]
        frames.reverse()
        return frames


    def invoke(self, context, event):
        rig = context.object
        scn = context.scene
        if rig.animation_data and rig.animation_data.action:
            fcurves = getActionBag(rig.animation_data.action).fcurves
            self.auto = True
            tmin = tmax = 1
            for fcu in fcurves:
                times = [kp.co[0] for kp in fcu.keyframe_points]
                if times:
                    tmin = min(int(min(times)), tmin)
                    tmax = max(int(max(times)), tmax)
            self.startFrame = tmin
            self.endFrame = tmax
        else:
            self.auto = scn.tool_settings.use_keyframe_insert_auto
            self.startFrame = self.endFrame = context.scene.frame_current
        return DazPropsOperator.invoke(self, context, event)


    def setInterpolation(self):
        if self.rig.animation_data and self.rig.animation_data.action:
            fcurves = getActionBag(self.rig.animation_data.action).fcurves
            for fcu in fcurves:
                for pt in fcu.keyframe_points:
                    pt.interpolation = 'LINEAR'
                fcu.extrapolation = 'CONSTANT'

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
        self.locks = {"location" : {}, "rotation_euler" : {}, "rotation_quaternion" : {}, "scale" : {}}
        self.limits = {"location" : {}, "rotation_euler" : {}, "scale" : {}}
        for pb in rig.pose.bones:
            self.locks["location"][pb.name] = list(pb.lock_location)
            self.locks["rotation_euler"][pb.name] = list(pb.lock_rotation)
            self.locks["rotation_quaternion"][pb.name] = [pb.lock_rotation_w] + list(pb.lock_rotation)
            self.locks["scale"][pb.name] = list(pb.lock_scale)
            self.getLimits(self.limits["location"], pb, 'LIMIT_LOCATION', -1e10, 1e10)
            self.getLimits(self.limits["rotation_euler"], pb, 'LIMIT_ROTATION', -pi, pi)
            self.getLimits(self.limits["scale"], pb, 'LIMIT_SCALE', -1e10, 1e10)

        if rig.animation_data and rig.animation_data.action:
            fcurves = getActionBag(self.rig.animation_data.action).fcurves
            deletes = []
            for fcu in fcurves:
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname:
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
                fcurves.remove(fcu)

        defaults = {
            "location" : (0,0,0),
            "rotation_euler" : (0,0,0),
            "rotation_quaternion" : (1,0,0,0),
            "scale" : (1,1,1)
        }
        for pb in rig.pose.bones:
            for channel,vec0 in defaults.items():
                vec = getattr(pb, channel)
                lock = self.locks[channel][pb.name]
                for idx,default in enumerate(vec0):
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
    DAZ_OT_ImportAsset,
    DAZ_OT_ImportPose,
    DAZ_OT_ImportExpression,
    DAZ_OT_ImportNodePose,
    DAZ_OT_ClearPose,
    DAZ_OT_PruneAction,
    DAZ_OT_ImposeLocksLimits,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
