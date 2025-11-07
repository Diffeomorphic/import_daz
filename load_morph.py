# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import numpy as np
import bpy
from mathutils import Matrix
from .driver import DriverUser, setFloatProp
from .utils import *
from .error import reportError, DazError, addItem
from .load_json import JL

MAX_EXPRESSION_SIZE = 255
MAX_TERMS = 12
MAX_TERMS2 = 9
MAX_EXPR_LEN = 200

ALWAYS_BAKED = [
    "CTRLInitialGensShape01",
]

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

class LoadMorph(DriverUser):
    morphset = None
    bodypart = "Custom"
    onDrivers = 'RIG'
    isJcm = False
    stripPrefix = ""
    treatHD = 'ERROR'
    useAdjusters = False
    onMorphSuffix = 'NONE'
    useSearchAlias = True
    onlyProperties = False
    useMakeHiddenSliders = False
    defaultMultiplier = 1.0
    useMulti = False
    useVisible = False
    ignoreBakedMorphs = True
    disableErc = False
    useMakePosable = False
    # Previously defined in __init__ function

    def initLoadMorph(self):
        self.rig = None
        self.obj = None
        self.amt = None
        self.rig2 = None
        self.amt2 = None
        self.mesh = None
        self.meshes = []
        self.nverts = -1
        self.char = None
        self.chars = []
        self.modded = False
        self.assoc = {}
        self.inFigure = {}
        self.duplicates = []
        self.baked = []
        self.mult = []
        self.mults = {}
        self.adjustable = {}
        self.currentAsset = None
        self.origMorphset = ""
        self.initTmp()

    def __init__(self):
        self.initLoadMorph()

    def getAdjustProp(self):
        return None

    def addToMorphSet(self, prop, asset, hidden):
        return

    def usePropDrivers(self):
        return (self.obj and self.onDrivers in ('RIG', 'MESH'))

    def useRigDrivers(self):
        return (self.rig and self.onDrivers == 'RIG')

    def useShapeCats(self):
        return (self.onDrivers in ['MESH', 'CATEGORY'])


    def initRig(self, rig, rig2):
        self.rig = rig
        self.rig2 = rig2
        self.initAmt()


    def initAmt(self):
        self.amt = self.amt2 = None
        if self.onDrivers == 'RIG' and self.rig:
            self.obj = self.rig
            if self.rig.type == 'ARMATURE':
                self.amt = self.rig.data
            elif self.obj.data:
                self.amt = self.obj.data
                self.rig = None
            else:
                self.amt = self.obj
                self.rig = None
        elif self.onDrivers == 'MESH' and self.mesh:
            self.obj = self.mesh
            self.amt = self.mesh.data
            dazRna(self.mesh).DazMeshMorphs = True
            dazRna(self.mesh).DazMeshDrivers = True
        elif self.onDrivers == 'CATEGORY' and self.mesh:
            dazRna(self.mesh).DazMeshMorphs = True
            dazRna(self.mesh).DazMeshDrivers = False
        elif self.obj:
            self.amt = self.obj
        if self.rig2:
            self.amt2 = self.rig2.data


    def setupUniqueSuffix(self):
        self.uniqueSuffix = ""

    def getUniqueName(self, string):
        return string

    def addUrl(self, asset, aliases, filepath):
        pass

    def initAll(self):
        self.initTmp()
        self.alias = {}
        self.loaded = []
        self.referred = {}
        self.primary = {}
        self.visible = {}
        self.erc = False
        self.propDrivers = {}
        self.boneDrivers = {}
        self.hideDrivers = {}
        self.shapekeys = {}
        self.faceshapes = {}
        self.mults = {}
        self.sumdrivers = {}
        self.restdrivers = {}
        self.iked = []
        self.bakedSkipped = {}
        self.ercMorphs = {}
        self.initAmt()


    def isBaked(self, prop):
        return (self.bakedName(prop) in self.baked)


    def bakedName(self, prop):
        prop = prop.lower()
        words = prop.rsplit("-0x", 1)
        if len(words) == 2:
            return words[0]
        return prop


    def loadAllMorphs(self, namepaths):
        self.initAll()
        name = namepaths[0][0]
        if self.rig and self.ignoreBakedMorphs:
            self.baked = [self.bakedName(key) for key in dazRna(self.rig).DazBaked.keys()]

        if self.mesh:
            from .asset import normalizeRef
            me = self.mesh.data
            nverts = len(me.vertices)
            self.nverts = [len(me.vertices)]
            url = dazRna(self.mesh).DazUrl.rsplit("/",1)[0]
            self.graftdirs = [normalizeRef(url)]
            self.vassocs = [{}]
            self.graftnames = [""]
            if dazRna(me).DazFingerPrint and "DazVertex" in me.attributes:
                def findDuplicates(a):
                    taken = set()
                    return [x for x in a if x in taken or taken.add(x)]

                vdata = me.attributes["DazVertex"].data
                if "DazGraft" in me.attributes.keys():
                    gdata = me.attributes["DazGraft"].data
                else:
                    gdata = None
                if gdata:
                    pgs = dazRna(me).DazGraftData
                    self.nverts = [pg.i for pg in pgs]
                    dups = findDuplicates(self.nverts)
                    self.graftnames = [":%s" % pg.name for pg in pgs]
                    for n,nv in enumerate(self.nverts):
                        if nv not in dups:
                            self.graftnames[n] = ""
                    self.graftnames[0] = ""
                    self.graftdirs = [pg.s for pg in pgs]
                    self.vassocs = []
                    for gn in range(len(pgs)):
                        vassoc = dict([(vattr.value, vn)
                                        for vn,vattr in enumerate(vdata)
                                        if gdata[vn].value == gn])
                        self.vassocs.append(vassoc)
                else:
                    self.nverts = [int(dazRna(me).DazFingerPrint.split("-",1)[0])]
                    vassoc = dict([(vattr.value, vn)
                                    for vn,vattr in enumerate(vdata)])
                    self.vassocs = [vassoc]

        self.adjustable = {}
        self.origMorphset = self.morphset

        if (self.amt and
            hasattr(self.amt, "DazOptimizedDrivers") and
            dazRna(self.amt).DazOptimizedDrivers):
            raise DazError("Cannot add new morphs to an armature with optimized drivers")

        if GS.verbosity >= 3:
            print("Making morphs")
        self.makeAllMorphs(namepaths, True)
        adjustable = self.adjustable
        self.adjustable = {}
        self.bodypart = namepaths[0][2]
        self.makeMissingMorphs(0)
        self.adjustable = adjustable
        if self.obj:
            self.createTmp()
            try:
                self.buildDrivers()
                self.buildSumDrivers()
                self.buildRestDrivers()
                if self.isJcm and GS.onShapekeyDrivers == 'OPTIMIZE_JCMS':
                    self.optimizeJcmDrivers()
                self.correctScaleParents()
            finally:
                self.deleteTmp()
            self.obj.update_tag()
            if self.mesh:
                if self.ercMorphs:
                    meshes = getMeshChildren(self.rig)
                    self.transferErcShapes(bpy.context, self.mesh, meshes)
                    for ob in getMeshChildren(self.rig):
                        self.applyErcArmature(bpy.context, ob)
                        ob.update_tag()
                else:
                    self.mesh.update_tag()

    #------------------------------------------------------------------
    #   Make all morphs
    #------------------------------------------------------------------

    def makeAllMorphs(self, namepaths, force):
        def getAsset(name, assets):
            for asset in assets:
                if asset.name == name:
                    return asset
            if assets:
                return assets[0]

        from .files import parseAssetFile
        namepaths.sort()
        idx = 0
        npaths = len(namepaths)
        for name,filepath,bodypart in namepaths:
            showProgress(idx, npaths)
            idx += 1
            lname = name.lower()
            if self.isBaked(lname):
                if lname not in self.bakedSkipped.keys():
                    self.bakedSkipped[lname] = name
            else:
                struct = JL.load(filepath)
                assets = parseAssetFile(struct, multi=True)
                if assets is None:
                    assets = []
                aliases = self.getAliases(filepath)
                if self.useMulti:
                    for asset in assets:
                        char = self.makeSingleMorph(name, asset, bodypart, force)
                        self.addUrl(asset, aliases, filepath)
                        printName(char, asset.label)
                else:
                    asset = getAsset(name, assets)
                    if asset:
                        char = self.makeSingleMorph(name, asset, bodypart, force)
                        self.addUrl(asset, aliases, filepath)
                        printName(char, name)

                fileref = self.getFileRef(filepath)
                self.loaded.append(fileref)
                if force:
                    LS.returnValue[fileref] = name

    #------------------------------------------------------------------
    #   First pass: collect data
    #------------------------------------------------------------------

    def makeSingleMorph(self, name, asset, bodypart, force):
        from .modifier import Alias, ChannelAsset, FormulaAsset
        self.currentAsset = asset
        self.setupUniqueSuffix()
        if not force:
            if self.alreadyLoaded(asset):
                return " ."
        if not isinstance(asset, ChannelAsset):
            return " -"
        elif isinstance(asset, Alias) and self.useSearchAlias:
            return " _"
        prop = rawProp(self.getUniqueName(asset.getName()))
        if self.isBaked(prop):
            return " B"
        if asset.name != prop and self.obj:
            pgs = dazRna(self.obj).DazMorphNames
            pg = pgs.get(asset.name)
            if pg is None:
                pg = pgs.add()
                pg.name = asset.name
            pg.s = prop
        self.bodypart = bodypart
        skey,ok = self.buildShape(asset)
        if not ok:
            return " #"
        if self.usePropDrivers():
            self.ercBones = {}
            self.makeFormulas(asset, skey)
            if self.ercBones:
                self.makeErcMorphs()
        return " *"


    def alreadyLoaded(self, asset):
        raw = rawProp(self.getUniqueName(asset.getName()))
        final = finalProp(raw)
        parent = self.getGraftParent(asset)
        if parent:
            if not (parent.data.shape_keys and
                    raw in parent.data.shape_keys.key_blocks.keys()):
                return False
        if self.obj and raw in self.obj.keys() and final in self.amt.keys():
            self.adjustMults(raw, final)
            return True
        return False


    def getAliases(self, filepath):
        def getAliasFile(filepath):
            folder = os.path.dirname(filepath)
            file1 = os.path.basename(filepath)
            for file in os.listdir(folder):
                if (file[0:5] == "alias" and
                    file.endswith(file1)):
                    return os.path.join(folder, file)
            return None

        def loadAlias(filepath):
            struct = JL.load(filepath)
            aliases = {}
            if self.obj is None:
                return aliases
            elif "modifier_library" in struct.keys():
                for mod in struct["modifier_library"]:
                    if "channel" in mod.keys():
                        channel = mod["channel"]
                        if ("type" in channel.keys() and
                            channel["type"] == "alias"):
                            alias = channel["name"]
                            prop = channel["target_channel"].rsplit('#')[-1].split("?")[0]
                            if alias != prop:
                                self.setAlias(prop, alias)
                                aliases[alias] = prop
                                if "label" in channel.keys():
                                    self.setLabel(prop, channel["label"])
            return aliases

        if self.useSearchAlias:
            aliaspath = getAliasFile(filepath)
            if aliaspath is not None:
                return loadAlias(aliaspath)
        return {}


    def setAlias(self, prop, alias):
        if self.obj is None:
            return
        pgs = dazRna(self.obj).DazAlias
        if alias in pgs.keys():
            pg = pgs[alias]
            printName(" ==", "%s %s %s" % (prop, alias, pg.s))
        else:
            pg = addItem(pgs)
            pg.name = alias
            printName(" =", "%s %s" % (prop, alias))
            pg.s = prop


    def setLabel(self, prop, label):
        pgs = self.findPropGroup(prop)
        if pgs and prop in pgs.keys():
            item = pgs[prop]
            item.text = label


    def buildShape(self, asset, useBuild=True):
        from .modifier import Morph
        if not (isinstance(asset, Morph) and
                self.mesh and
                asset.deltas and
                not self.onlyProperties):
            return None,True

        from .driver import makePropDriver
        from .hd_data import addSkeyToUrls
        useBuild = True

        def getRightVAssoc(asset):
            for gn,graftdir in enumerate(self.graftdirs):
                if asset.id.startswith(graftdir):
                    return self.vassocs[gn], self.graftnames[gn]
            for gn,nverts in enumerate(self.nverts):
                if nverts == asset.vertex_count:
                    return self.vassocs[gn], self.graftnames[gn]
            return {}, ""

        parent = self.getGraftParent(asset)
        vassoc = {}
        suffix = ""
        if asset.vertex_count < 0:
            pass
        elif asset.vertex_count in self.nverts:
            vassoc,suffix = getRightVAssoc(asset)
        elif parent:
            pass
        else:
            from .finger import VertexCounts
            msg = ("Vertex count mismatch: %d not in %s" % (asset.vertex_count, self.nverts))
            if GS.verbosity > 2:
                print(msg)
            if asset.hd_url:
                if self.treatHD == 'CREATE':
                    useBuild = False
                elif self.treatHD == 'ACTIVE':
                    skey = self.getActiveShape(asset)
                else:
                    reportError(msg)
                    return None,False
            else:
                reportError(msg)
                if asset.vertex_count in VertexCounts.keys():
                    LS.targetCharacter = VertexCounts[asset.vertex_count]
                return None,False

        if not asset.rna:
            if parent:
                asset.buildMorph(parent, vassoc=vassoc, useBuild=useBuild)
            else:
                asset.buildMorph(self.mesh, vassoc=vassoc, useBuild=useBuild)
        skey = asset.rna[0]
        if skey:
            skey.name = "%s%s" % (skey.name, suffix)
            prop = rawProp(self.getUniqueName(unquote(skey.name)))
            self.alias[prop] = skey.name
            skey.name = prop
            self.setShapeLimits(skey, asset)
            self.shapekeys[prop] = skey
            if GS.ercMethod == 'TRANSLATION' and not self.disableErc:
                pass
            elif self.bodypart == "Face":
                self.faceshapes[skey.name] = True
            addSkeyToUrls(self.mesh, asset, skey)
            if self.usePropDrivers():
                final = self.addNewProp(prop)
                self.addShapeDriver(skey, final)
            pgs = dazRna(self.mesh.data).DazBodyPart
            if prop in pgs.keys():
                item = pgs[prop]
            else:
                item = addItem(pgs)
                item.name = prop
            item.s = self.bodypart
            return skey,True
        else:
            return None,True


    def getGraftParent(self, asset):
        from .modifier import Morph
        if (isinstance(asset, Morph) and
            self.mesh and
            dazRna(self.mesh.data).DazVertexCount == asset.vertex_count and
            dazRna(self.mesh.data).DazGraftGroup and
            self.rig):
            for ob in self.rig.children:
                if ob.type == 'MESH' and len(ob.data.vertices) == asset.vertex_count:
                    return ob
        return None


    def makeFormulas(self, asset, skey):
        from .formula import Formula, setFormulaExpr, ExprTarget
        from .modifier import Alias
        if asset.type in ["file"]:
            return False
        aname = (skey.name if skey else asset.getName())
        prop = rawProp(self.getUniqueName(aname))
        if prop != aname:
            self.setAlias(aname, prop)
        self.addNewProp(prop, asset, skey)
        self.adjustable[prop] = True
        if isinstance(asset, Formula):
            exprs,self.rig2 = asset.evalFormulas(self.obj, self.mesh, True)
        elif isinstance(asset, Alias):
            exprs = {}
            alias = asset.getAlias()
            if alias == prop:
                print("Alias is same: %s" % prop)
                return
            expr = setFormulaExpr(exprs, alias, "value", "value", 0)
            target = ExprTarget(prop, "value", -1)
            target.factor = 1
            expr.props.append(target)
        else:
            return False
        if not exprs:
            return False
        for output,data in exprs.items():
            for key,data1 in data.items():
                if key == "*fileref":
                    ref,channel = data1
                    if channel == "value" and len(ref) > 3:
                        self.referred[ref.lower()] = True
                    continue
                for idx,expr in data1.items():
                    if key == "value":
                        self.makeValueFormula(output, expr, self.propDrivers)
                    elif self.onlyProperties:
                        continue
                    elif key == "rotation":
                        self.makeRotFormula(output, idx, expr)
                    elif key == "translation":
                        self.makeTransFormula(output, idx, expr)
                    elif key == "scale":
                        self.makeScaleFormula(output, idx, expr)
                    elif key == "center_point":
                        self.erc = True
                        if GS.ercMethod == 'ALL':
                            self.makeOffsetFormula("HdOffset", output, idx, expr)
                        elif self.disableErc:
                            pass
                        elif GS.ercMethod == 'TRANSLATION':
                            self.makeErcFormula(output, idx, expr)
                        elif GS.ercMethod == 'ARMATURE':
                            self.makeOffsetFormula("HdOffset", output, idx, expr)
                    elif key == "extra/studio_node_channels/channels/Visible":
                        self.hideDrivers[output] = []
                        self.makeValueFormula(output, expr, self.hideDrivers)

        return True


    def addShapeDriver(self, skey, final, expr="x"):
        from .driver import makePropDriver
        path = propRef(final)
        makePropDriver(path, skey, "value", self.amt, "x")
        if GS.onShapekeyDrivers == 'MUTE_DRIVERS':
            makePropDriver(path, skey, "mute", self.amt, "abs(x)<0.0001")


    def getFileRef(self, filepath):
        from .fileutils import getCanonicalFilePath
        fileref = getCanonicalFilePath(filepath)
        if fileref:
            return fileref
        else:
            msg = ('Did not find file:\n"%s"' % filepath)
            raise DazError(msg)


    def addNewProp(self, raw, asset=None, skey=None):
        from .driver import setBoolProp, getPropMinMax
        from .selector import setActivated
        from .modifier import Alias, FormulaAsset
        final = finalProp(raw)
        if raw.startswith("CTRLMD"):
            return final
        if raw not in self.propDrivers.keys():
            self.propDrivers[raw] = []
            self.visible[raw] = False
            self.primary[raw] = False
        if asset:
            visible = (asset.visible or
                       self.stripPrefix or
                       self.useVisible or
                       self.useMakeHiddenSliders or
                       GS.useMakeHiddenSliders)
            self.visible[raw] = visible
            self.primary[raw] = True
            if isinstance(asset, Alias):
                alias = rawProp(asset.getAlias())
                if not alias:
                    return
                finalias = finalProp(alias)
                if finalias in self.amt.keys():
                    if final == finalias:
                        return
                    asset.min,asset.max,default,ovr = getPropMinMax(self.amt, finalias, False)
            elif (self.inFigure.get(raw) and
                  raw in self.obj.keys()):
                return final
            if skey and not visible:
                self.setFloatLimits(self.amt, final, asset, skey, False)
                return final
            if asset.type == "bool":
                setBoolProp(self.obj, raw, asset.value, True)
                setBoolProp(self.amt, final, asset.value, False)
            elif asset.type == "float" or asset.type == "alias":
                self.setFloatLimits(self.obj, raw, asset, None, True)
                self.setFloatLimits(self.amt, final, asset, skey, False)
            elif asset.type == "int":
                self.obj[raw] = asset.value
                self.amt[final] = asset.value
            elif asset.type == "string":
                pass
            else:
                self.setFloatLimits(self.obj, raw, asset, None, True)
                self.setFloatLimits(self.amt, final, asset, skey, False)
                reportError("BUG: Unknown asset type: %s.\nAsset: %s" % (asset.type, asset))
            if visible:
                setActivated(self.obj, raw, True)
                self.addToMorphSet(raw, asset, False)
        return final


    def setFloatLimits(self, rna, prop, asset, skey, ovr):
        value = asset.value
        baseprop = prop.split(":", 1)[0]
        if ((self.obj and baseprop in dazRna(self.obj).DazBaked.keys()) or
            baseprop in ALWAYS_BAKED):
            value = 0
            print("Baked %s = 0" % baseprop)
        if not GS.useDazLimits:
            min = max = None
        elif (not ovr and
              (GS.onStrengthAdjusters != 'NONE' or
               self.useAdjusters)):
            min = 10 * asset.min
            max = 10 * asset.max
        else:
            min = GS.sliderMultiplier * asset.min
            max = GS.sliderMultiplier * asset.max
        setFloatProp(rna, prop, value, min, max, ovr)
        if skey:
            self.setShapeLimits(skey, asset)


    def setShapeLimits(self, skey, asset):
        if (not GS.useDazLimits or
            GS.onStrengthAdjusters != 'NONE' or
            self.useAdjusters):
            skey.slider_min = -10
            skey.slider_max = 10
        else:
            skey.slider_min = GS.sliderMultiplier * asset.min
            skey.slider_max = GS.sliderMultiplier * asset.max


    def makeValueFormula(self, output, expr, drivers):
        output = self.getUniqueName(output)
        if expr.props:
            self.addNewProp(output)
            for target in expr.props:
                prop = self.getUniqueName(target.key)
                factor = target.getFactor(True)
                drivers[output].append((prop, target))
            target = expr.props[0]
            for mult in target.mults:
                if isinstance(mult, str):
                    mult = self.getUniqueName(mult)
                    self.addNewProp(mult)
                if output not in self.mults.keys():
                    self.mults[output] = []
                self.mults[output].append(mult)
        target = expr.bone
        if target:
            if output not in self.boneDrivers.keys():
                self.boneDrivers[output] = {}
            self.boneDrivers[output][target.key] = expr
            target2 = expr.bone2
            if target2:
                self.boneDrivers[output][target2.key] = expr



    def getBoneData(self, bname, expr):
        from .transform import Transform
        if bname is None:
            return
        elif bname == "RIG":
            pb = self.rig
        else:
            pb = self.rig.pose.bones[bname]
        target = expr.props[0]
        factor = target.getFactor(False)
        raw = rawProp(self.getUniqueName(target.key))
        final = self.addNewProp(raw)
        tfm = Transform()
        return tfm, pb, final, factor


    def makeRotFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setRot(factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeTransFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setTrans(factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeScaleFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setScale(factor, True, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeErcFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        self.ercMorphs[prop] = self.ercBones
        if pb.name not in self.ercBones.keys():
            tfm.setTrans(factor, prop, index=idx)
            self.ercBones[pb.name] = (tfm, tfm.trans)
            pb.lock_location = FFalse
            cns = getConstraint(pb, 'LIMIT_LOCATION')
            if cns:
                cns.mute = True
        else:
            tfm,trans = self.ercBones[pb.name]
            tfm.trans[idx] = factor


    def makeOffsetFormula(self, attr, bname, idx, expr):
        _tfm,pb,prop,factor = self.getBoneData(bname, expr)
        if attr not in pb.keys():
            setattr(pb, attr, Zero)
        vec = Vector((0,0,0))
        vec[idx] = factor
        self.setFcurves(pb, vec, prop, attr, "pose", useDrv=False)


    def makeErcMorphs(self):
        def getParentTrans(pb):
            parent = pb.parent
            while parent and parent.name not in self.ercBones.keys():
                parent = parent.parent
            if parent:
                return self.ercBones[parent.name][1]
            else:
                return Zero

        from .node import getTransformMatrices
        offsets = {}
        for pb in self.rig.pose.bones:
            tfm,trans = self.ercBones.get(pb.name, (None,None))
            if tfm:
                dmat,bmat,parent = getTransformMatrices(pb, self.rig, {})
                tfm.trans = trans - getParentTrans(pb)
                self.addPoseboneDriver(pb, tfm)


    def transferErcShapes(self, context, ob, meshes):
        from .morphing import transferShapesToMeshes
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        props = [baseProp(final) for final in self.ercMorphs.keys()]
        snames = [prop for prop in props if prop in skeys.key_blocks.keys()]
        print("Transfer ERC shapes")
        transferShapesToMeshes(context, ob, meshes, snames)


    def applyErcArmature(self, context, ob):
        from .apply import applyArmatureModifier
        from .modifier import getBasisShape, newArmatureModifier
        from .driver import getPropMinMax, Driver

        activateObject(context, ob)
        basis,skeys,new = getBasisShape(ob)
        drivers = []
        if skeys.animation_data:
            for fcu in list(skeys.animation_data.drivers):
                sname,channel = getShapeChannel(fcu)
                if channel == "mute":
                    drivers.append(Driver(fcu))
                    skeys.animation_data.drivers.remove(fcu)
        for skey in skeys.key_blocks:
            skey.mute = True
            skey.value = 0.0
        for final,ercBones in self.ercMorphs.items():
            ob.active_shape_key_index = 0
            prop = baseProp(final)
            fcus = []
            for fcu in self.rig.animation_data.drivers:
                bname,channel,cnsname = getBoneChannel(fcu)
                if bname and bname not in ercBones.keys() and cnsname is None:
                    fcus.append((fcu, fcu.mute))
                    fcu.mute = True
            for pb in self.rig.pose.bones:
                pb.matrix_basis = Matrix()
            self.rig[prop] = 1.0
            updateDrivers(self.amt)
            applyArmatureModifier(ob)
            name = self.rig.name
            newArmatureModifier(name, ob, self.rig)
            eskey = skeys.key_blocks[-1]
            earr = np.array([v.co for v in eskey.data])
            ob.shape_key_remove(eskey)
            skey = skeys.key_blocks.get(prop)
            if skey:
                bdata = skeys.key_blocks[0].data
                sdata = skey.data
                barr = np.array([v.co for v in bdata])
                sarr = np.array([v.co for v in sdata])
                arr = sarr + barr - earr
            else:
                vdata = ob.data.vertices
                varr = np.array([v.co for v in vdata])
                arr = 2*varr - earr
                skey = ob.shape_key_add(name=prop)
                self.addShapeDriver(skey, final)
                min,max,default,ovr = getPropMinMax(self.rig, prop, True)
                skey.slider_min = min
                skey.slider_max = max
                skey.mute = True
            for data,co in zip(skey.data, arr):
                data.co = co
            for fcu,mute in fcus:
                fcu.mute = mute
            self.rig[prop] = 0.0
        for skey in skeys.key_blocks:
            skey.mute = False
        for driver in drivers:
            driver.createDirect(skeys, {})
        updateDrivers(self.amt)

    #-------------------------------------------------------------
    #   Add posebone driver
    #-------------------------------------------------------------

    def addObjectDriver(self, tfm):
        success = False
        if tfm.scaleProp:
            self.setFcurves(self.obj, tfm.scale-One, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(self.obj, tfm.general-One, tfm.generalProp, "scale")
            success = True
        return success


    def addPoseboneDriver(self, pb, tfm):
        if pb == self.rig:
            return self.addObjectDriver(tfm)
        from .node import getBoneMatrix
        mat = getBoneMatrix(tfm, pb, self.rig)
        loc,quat,scale = mat.decompose()
        success = False
        if (tfm.transProp and loc.length > 0.01*GS.scale):
            self.setFcurves(pb, loc, tfm.transProp, "location")
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                quat[0] -= 1
                self.setFcurves(pb, quat, tfm.rotProp, "rotation_quaternion")
                success = True
            else:
                euler = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, euler, tfm.rotProp, "rotation_euler")
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, scale-One, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, scale-One, tfm.generalProp, "scale")
            success = True
        return success


    def setFcurves(self, pb, vec, prop, channel, pose="pose", useDrv=True):
        def getBoneFcurves(pb, channel):
            if isinstance(pb, bpy.types.Object):
                path = channel
            else:
                path = '%s.bones["%s"].%s' % (pose, pb.name, channel)
            fcustruct = {}
            if self.rig.animation_data:
                for fcu in self.rig.animation_data.drivers:
                    if path == fcu.data_path:
                        fcustruct[fcu.array_index] = fcu
            return fcustruct

        if useDrv and drvBone(pb.name) in self.rig.pose.bones.keys():
            pb = self.rig.pose.bones[drvBone(pb.name)]
        fcustruct = getBoneFcurves(pb, channel)
        for idx,factor in self.getFactors(vec):
            fcu = fcustruct.get(idx)
            bname,drivers = self.findSumDriver(pb, channel, idx, (pb, fcu, {}))
            if prop in drivers.keys():
                drivers[prop] += factor
            else:
                drivers[prop] = factor


    def getFactors(self, vec):
        maxfactor = max([abs(factor) for factor in vec])
        return [(idx,factor) for idx,factor in enumerate(vec) if abs(factor) > 0.01*maxfactor]


    def findSumDriver(self, pb, channel, idx, data):
        bname = pb.name
        if bname not in self.sumdrivers.keys():
            self.sumdrivers[bname] = {}
        if channel not in self.sumdrivers[bname].keys():
            self.sumdrivers[bname][channel] = {}
        if idx not in self.sumdrivers[bname][channel].keys():
            self.sumdrivers[bname][channel][idx] = data
        return bname, self.sumdrivers[bname][channel][idx][2]


    def clearProp(self, pgs, prop, idx):
        for n,pg in enumerate(pgs):
            if pg.name == prop and pg.index == idx:
                pgs.remove(n)
                return

    #------------------------------------------------------------------
    #   Second pass: Load missing morphs
    #------------------------------------------------------------------

    def makeMissingMorphs(self, level):
        newLine()
        if GS.verbosity >= 3:
            print("Making missing morphs level %d" % level)
        for fileref in self.loaded:
            self.referred[fileref] = False
        morphset = self.morphset
        namepaths = []
        groupedpaths,morphfiles = self.setupMorphGroups()
        someMissing = False
        for ref,unloaded in self.referred.items():
            if unloaded:
                someMissing = True
                path = GS.getAbsPath(ref)
                if path:
                    name = os.path.splitext(ref.rsplit("/",1)[-1])[0]
                    data = (name, path, self.bodypart)
                    mset = self.getPathMorphSet(path, morphfiles)
                    if mset:
                        groupedpaths[mset].append(data)
                    else:
                        namepaths.append(data)
        if someMissing:
            self.referred = {}
            if namepaths:
                self.makeAllMorphs(namepaths, False)
            for mset,namepaths in groupedpaths.items():
                if namepaths:
                    self.morphset = mset
                    self.makeAllMorphs(namepaths, False)
            if level < 5:
                self.makeMissingMorphs(level+1)
        self.morphset = morphset


    def setupMorphGroups(self):
        from .morphing import MP
        if self.char is None:
            return {}, {}
        morphrefs = {}
        groupedpaths = {}
        for morphset,paths in MP.getMorphPaths(self.char).items():
            groupedpaths[morphset] = []
            morphrefs[morphset] = [self.getFileRef(path) for path in paths]
        return groupedpaths, morphrefs


    def getPathMorphSet(self, path, morphrefs):
        ref = self.getFileRef(path)
        for morphset,refs in morphrefs.items():
            if ref in refs:
                return morphset
        return None

    #------------------------------------------------------------------
    #   Third pass: Build the drivers
    #------------------------------------------------------------------

    def buildDrivers(self):
        if GS.verbosity >= 3:
            print("Building drivers. PROP = %d, BONE = %d, HIDE = %d" % (len(self.propDrivers), len(self.boneDrivers), len(self.hideDrivers)))
        for output,drivers in self.propDrivers.items():
            if drivers:
                self.buildPropDriver(rawProp(output), drivers)
            elif self.visible[output] and not self.inFigure.get(output):
                self.buildPropDriver(rawProp(output), drivers)
            else:
                final = finalProp(output)
                if final not in self.amt.keys():
                    setFloatProp(self.amt, final, 0.0, None, None, True)
        for output,drivers in self.boneDrivers.items():
            if drivers:
                for bname,expr in drivers.items():
                    self.buildBoneDriver(output, bname, expr, False)
        for output,drivers in self.hideDrivers.items():
            if drivers and self.mesh:
                from .geonodes import addMaskFaceModifier
                mod = addMaskFaceModifier(self.mesh, "DazPolygonGroup", output, GS.useFaceGroupMasks)
                if mod:
                    self.buildGenericDriver(mod, "show_viewport", drivers)
                    self.buildGenericDriver(mod, "show_render", drivers)


    def isDriverType(self, dtype, drivers):
        for driver in drivers:
            if driver[0] == dtype:
                return True
        return False


    def buildPropDriver(self, raw, drivers):
        from .driver import getRnaDriver, Variable, removeModifiers
        rna,channel = self.getDrivenChannel(raw)
        bvars = []
        vvars = {}
        string = ""
        string0 = ""
        if "jcm" in raw.lower():
            fcu0 = None
        else:
            fcu0 = getRnaDriver(rna, channel, None)
        if fcu0 and fcu0.driver.type == 'SCRIPTED':
            if not self.primary[raw]:
                self.extendPropDriver(fcu0, raw, drivers)
                return
            vtargets,btargets = self.getVarBoneTargets(fcu0)
            string0 = fcu0.driver.expression
            if btargets:
                varname = btargets[-1][0]
                string = self.extractBoneExpression(string0, varname)
            for _,_,var0 in btargets:
                bvars.append(Variable(var0))
            for vname,_,var0 in vtargets:
                vvars[vname] = Variable(var0)

        rna.driver_remove(channel)
        fcu = rna.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)
        ok = self.buildNewPropDriver(fcu, rna, channel, string, raw, drivers, string0, vvars)
        if not ok:
            return
        self.addMissingVars(fcu, vvars)
        self.removeUnusedVars(fcu)
        self.inFigure[raw] = True


    def buildNewPropDriver(self, fcu, rna, channel, string, raw, drivers, string0, vvars):
        varname = "a"
        if self.visible[raw] or not self.primary[raw]:
            if self.useAdjusters and raw in self.adjustable.keys():
                adj = self.getAdjustProp()
                if adj:
                    self.addAdjuster(adj, fcu, "K")
                    string += "K*"
            if GS.onStrengthAdjusters in ['ALL', self.bodypart]:
                adj = "Adjust Morph Strength"
                self.addAdjuster(adj, fcu, "L")
                string += "L*"
            self.addPathVar(fcu, varname, self.obj, propRef(raw))
            if raw not in self.obj.keys():
                self.obj[raw] = 0.0
            string += varname

        string,rdrivers = self.addDriverVars(fcu, string, varname, drivers)
        if not string:
            if vvars:
                fcu.driver.expression = string0
                if GS.verbosity >= 3:
                    print("Keep old driver: %s" % raw)
                return True
            else:
                if GS.verbosity >= 3:
                    print("Remove driver: %s" % raw)
                rna.driver_remove(channel)
                return False
        if self.getMultipliers(raw):
            string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        if rdrivers:
            self.extendPropDriver(fcu, raw, rdrivers)
        return True


    def addAdjuster(self, adj, fcu, var):
        if adj not in self.obj.keys():
            setFloatProp(self.obj, adj, 1.0, 0.0, 10.0, True)
        self.addPathVar(fcu, var, self.obj, propRef(adj))


    def extractBoneExpression(self, string, varname):
        string = string.split("(", 1)[-1]
        mult = string.split(varname, 1)[0]
        if mult == "0" or mult == "0*":
            return ""
        if mult == "0":
            mult = "0*"
        return "%s%s+" % (mult, varname)


    def getFactorPoints(self, target, prop):
        from .formula import ExprTarget
        if isinstance(target, ExprTarget):
            return target.factor, target.points
        else:
            return target, []


    def getFactorPointsString(self, factor, points, varname):
        if points:
            points = [pt[0:2] for pt in points]
            vals = [pt[1] for pt in points]
            umax = max(vals)
            umin = min(vals)
            if abs(umin) > abs(umax):
                umax = umin
            return "+(%s)" % self.makeSplineString(points, varname, 1.0, 1/umax)
        else:
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "%+.3g*%s" % (factor, varname)


    def buildGenericDriver(self, rna, channel, drivers):
        from .driver import removeModifiers
        rna.driver_remove(channel)
        fcu = rna.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        string = ""
        string,rdrivers = self.addDriverVars(fcu, string, "a", drivers)
        if string[0] == "-":
            string = string[1:]
        fcu.driver.expression = string
        self.removeUnusedVars(fcu)


    def addDriverVars(self, fcu, string, varname, drivers):
        channels = [var.targets[0].data_path for var in fcu.driver.variables]
        for subraw,target in drivers[0:MAX_TERMS2]:
            factor,points = self.getFactorPoints(target, subraw)
            if factor == 0.0 and not points:
                continue
            subraw = rawProp(subraw)
            subfinal = finalProp(subraw)
            channel = propRef(subfinal)
            if channel in channels:
                continue
            varname = nextLetter(varname)
            string += self.getFactorPointsString(factor, points, varname)
            self.ensureExists(subraw, subfinal, 0.0)
            self.addPathVar(fcu, varname, self.amt, channel)
        if len(drivers) > MAX_TERMS2:
            return string, drivers[MAX_TERMS2:]
        else:
            return string, []


    def addMissingVars(self, fcu, vvars):
        if not fcu.driver:
            return
        vnames = [var.name for var in fcu.driver.variables]
        for vname,vvar in vvars.items():
            if vname not in vnames:
                var = fcu.driver.variables.new()
                vvar.create(var)


    def removeUnusedVars(self, fcu):
        for var in list(fcu.driver.variables):
            if var.name not in fcu.driver.expression:
                fcu.driver.variables.remove(var)


    def extendPropDriver(self, fcu, raw, drivers):
        string = fcu.driver.expression
        char = ""
        while string[-1] == ")":
            char += ")"
            string = string[:-1]
        if string[-1] == "R":
            rest = restProp(raw)
            self.addRestDrivers(rest, drivers)
            return
        else:
            string += "+R"
            rest = restProp(raw)
            self.amt[rest] = 0.0
            self.addPathVar(fcu, "R", self.amt, propRef(rest))
            self.addRestDrivers(rest, drivers)
        string += char
        if len(string) > MAX_EXPRESSION_SIZE:
            errtype = "Driving expressions too long for the following properties:"
            if errtype not in self.errors.keys():
                self.errors[errtype] = []
            self.errors[errtype].append(raw)
        else:
            fcu.driver.expression = string


    def addRestDrivers(self, rest, drivers):
        struct = self.restdrivers[rest] = {}
        for raw,factor in drivers:
            struct[finalProp(raw)] = factor


    def addPathVar(self, fcu, varname, rna, path):
        from .driver import addDriverVar
        addDriverVar(fcu, varname, path, rna)


    def getDrivenChannel(self, raw):
        rna = self.amt
        final = finalProp(raw)
        self.ensureExists(raw, final, 0.0)
        channel = propRef(final)
        return rna, channel


    def getMultipliers(self, raw):
        props = []
        if raw and raw in self.mults.keys():
            props = self.mults[raw]
        #self.mult = [prop for prop in props if not prop.lower().startswith(("fbm", "fhm"))]
        self.mult = props
        return self.mult


    def multiplyMults(self, fcu, string):
        if self.mult:
            mstring = ""
            if len(string) == 0:
                reportError("Trying to multiply empty string", trigger=(1,1))
            elif (len(string) > 1 and
                 string[1] == '*' and
                 string[0].isupper() and
                 string[0] not in ["K", "L"]):
                varname = nextLetter(string[0])
            else:
                varname = "M"
                string = "(%s)" % string
            targets = self.getDriverTargets(fcu)
            for mult in self.mult:
                if isinstance(mult, str):
                    multfinal = finalProp(mult)
                    if propRef(multfinal) not in targets:
                        mstring += "%s*" % varname
                        self.ensureExists(mult, multfinal, self.defaultMultiplier)
                        self.addPathVar(fcu, varname, self.amt, propRef(multfinal))
                        varname = nextLetter(varname)
                elif isinstance(mult, tuple):
                    from .driver import addTransformVar
                    bname,channel,idx = mult
                    ttypes = self.getTransformTypes(channel)
                    if ttypes and bname in self.rig.pose.bones:
                        pb = self.rig.pose.bones[bname]
                        idx2,sign = d2bBone(pb, channel, idx)
                        signchar = ("" if sign == 1 else "-")
                        mstring += "%s%s*" % (signchar, varname)
                        addTransformVar(fcu, varname, ttypes[idx2], self.rig, self.rig2, bname)
                        varname = nextLetter(varname)
            return "%s%s" % (mstring, string)
        else:
            return string


    def adjustMults(self, raw, final):
        from .driver import getRnaDriver
        if self.getMultipliers(raw):
            fcu = getRnaDriver(self.amt, propRef(final))
        else:
            return
        if fcu:
            string = self.multiplyMults(fcu, fcu.driver.expression)
            fcu.driver.expression = string


    def ensureExists(self, raw, final, default):
        from .driver import removeModifiers
        from .selector import setActivated
        if self.obj is None:
            return
        if raw not in self.obj.keys():
            self.obj[raw] = default
        if final not in self.amt.keys():
            self.amt[final] = default
            fcu = self.amt.driver_add(propRef(final))
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            fcu.driver.expression = "a"
            self.addPathVar(fcu, "a", self.obj, propRef(raw))


    def buildBoneDriver(self, raw, bname, expr, keep):
        def getSplinePoints(points, pb, comp):
            n = len(points)
            if (points[0][0] > points[n-1][0]):
                points.reverse()
            diff = points[n-1][0] - points[0][0]
            uvec = getBoneVector(unit/diff, comp, pb)
            xys = []
            for k in range(n):
                x = points[k][0]/diff
                y = points[k][1]
                xys.append((x, y))
            return uvec, xys

        pb = self.rig.pose.bones.get(bname)
        if pb is None:
            print("Cannot build driver for non-existing bone: %s" % bname)
            return
        rna,path = self.getDrivenChannel(raw)
        channel = expr.path
        target = expr.bone
        bname = target.key
        unit = 1/getUnit(target.type)
        self.getMultipliers(raw)
        if target.points:
            uvec,xys = getSplinePoints(target.points, pb, target.comp)
            self.makeSplineBoneDriver(channel, uvec, xys, rna, path, -1, bname, keep)
        else:
            uvec = unit*getBoneVector(target.factor, target.comp, pb)
            bname2 = None
            uvec2 = None
            target2 = expr.bone2
            if target2:
                bname2 = target2.key
                pb2 = self.rig.pose.bones.get(bname2)
                if pb2:
                    uvec2 = unit*getBoneVector(target2.factor, target2.comp, pb2)
            self.makeSimpleBoneDriver(channel, uvec, rna, path, -1, bname, keep, bname2, uvec2)

    #-------------------------------------------------------------
    #   Bone drivers
    #-------------------------------------------------------------

    def getVarData(self, uvec, bname, vname):
        vals = [(abs(x), n, x) for n,x in enumerate(uvec)]
        vals.sort()
        _,n,umax = vals[-1]
        vars = [(n, vname, bname)]
        return vname, vars, umax


    def makeSimpleBoneDriver(self, channel, vec, rna, path, idx, bname, keep, bname2=None, vec2=None):
        var,vars,umax = self.getVarData(vec, bname, "A")
        string = getMult(umax, var)
        if bname2:
            var2,vars2,umax2 = self.getVarData(vec2, bname2, "B")
            string2 = getMult(umax2, var2)
            vars = vars + vars2
            string = "%s+%s" % (string, string2)
        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeSplineString(self, points, var, umax, ufactor):
        def truncMinus(zstring):
            if zstring[0:2] == "+-":
                return zstring[1:]
            elif zstring[0:2] == "--":
                return "+%s" % zstring[2:]
            elif zstring in ["+0", "-0"]:
                return ""
            else:
                return zstring

        def linearSpline(var, lt):
            n = len(points)
            xi,yi = points[0]
            string = ""
            term = getPrint(yi)
            prev = "%s if %s%s %s" % (term, var, lt, getPrint(xi/umax))
            tie = ""
            for i in range(1, n):
                xj,yj = points[i]
                kij = (yj-yi)/(xj-xi)
                zs,zi = getSign((yi - kij*xi)/umax)
                zstring = ""
                if abs(zi) > 5e-4:
                    zstring = truncMinus("%s%s" % (zs, getPrint(zi*umax)))
                term1 = "%s%s" % (getMult(kij*umax, var), zstring)
                if term1 != term:
                    string += prev
                    term = term1
                    tie = " else "
                prev = ("%s%s if %s%s %s " % (tie, term, var, lt, getPrint(xj/umax)))
                xi,yi = xj,yj
            default = getPrint(yj)
            if default != term:
                string += prev
            return "(%s else %s)" % (string, default)

        def addFactorString(factor, zstring):
            if factor == 1:
                return "+%s" % zstring
            elif factor == -1:
                return "-%s" % zstring
            elif factor == 0:
                return "+0"
            else:
                return "+%s*%s" % (getPrint(factor), zstring)

        def splineSpline(var, lt):
            xi,yi = points[0]
            string = ""
            first = True
            for j,pt in enumerate(points[1:]):
                xj,yj = pt
                if yi == 0 and yj == 0:
                    xi = xj
                    continue
                ypj = getPrint(yj)
                xpi = getPrint(xi/umax)
                xpj = getPrint(xj/umax)
                factor = (yj-yi)*ufactor
                if first and yi != 0:
                    string += "+%s" % getPrint(yi)
                zstring = "smoothstep(%s,%s,%s)" % (xpi, xpj, var)
                string += addFactorString(factor, zstring)
                xi = xj
                yi = yj
                first = False
            return string[1:]

        lt = ("<" if umax > 0 else ">")
        string = splineSpline(var, lt)
        if len(string) > 254:
            string = linearSpline(var, lt)
        if len(string) > 254:
            msg = "String driver too long:\n"
            for n in range(5):
                msg += "%s         \n" % (string[30*n:30*(n+1)])
            reportError(msg)
            return ""
        return string


    def makeSplineBoneDriver(self, channel, uvec, points, rna, path, idx, bname, keep):
        var,vars,umax = self.getVarData(uvec, bname, "A")
        string = self.makeSplineString(points, var, umax, 1.0)
        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeBoneDriver(self, string, vars, channel, rna, path, idx, keep):
        from .driver import addTransformVar, Driver, Variable, getRnaDriver, removeModifiers
        bvars = []
        vvars = {}
        propDriver = None
        fcu0 = getRnaDriver(rna, path, None)
        if channel == "value":
            channel = "rotation"
            propDriver = Driver(fcu0)
        elif keep:
            if fcu0 and fcu0.driver.type == 'SCRIPTED':
                vtargets,btargets = self.getVarBoneTargets(fcu0)
                if btargets:
                    varname = btargets[-1][0]
                    string0 = self.extractBoneExpression(fcu0.driver.expression, varname)
                    for _,_,var0 in btargets:
                        bvars.append(Variable(var0))
                    nvars = []
                    vname = varname
                    for (n, varname, prop) in vars:
                        vname = nextLetter(vname)
                        string = string.replace(varname, vname)
                        nvars.append((n, vname, prop))
                    vars = nvars
                    string = string0 + string
                for vname,_,var0 in vtargets:
                    vvars[vname] = Variable(var0)

        rna.driver_remove(path, idx)
        fcu = rna.driver_add(path, idx)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)
        if propDriver:
            plus = ("" if string[0] == "-" else "+")
            string = "%s%s%s" % (propDriver.expression, plus, string)
            for var in propDriver.variables:
                var.create(fcu.driver.variables.new())
        if (not string.startswith(("clamp", "smoothstep")) and
            self.currentAsset and
            bpy.app.version >= (2,93,0)):
            words = string.split("else ")
            if len(words) == 3:
                words = words[1].split(" if")
                if len(words) == 2:
                    string = words[0]
            string = "clamp(%s,%g,%g)" % (string, self.currentAsset.min, self.currentAsset.max)
        if ((GS.useMakeHiddenSliders or
             self.useMakeHiddenSliders or
             self.stripPrefix) and
            isPath(path) and
            "u" not in vvars.keys()):
            final = unPath(path)
            if isFinal(final):
                raw = baseProp(final)
                if string[0] == "-":
                    string = "u%s" % string
                else:
                    string = "u+%s" % string
                self.obj[raw] = 0.0
                self.addPathVar(fcu, "u", self.obj, propRef(raw))
                self.addToMorphSet(raw, None, True)
        string = self.multiplyMults(fcu, string)
        if self.useAdjusters:
            adj = self.getAdjustProp()
            if adj:
                self.addAdjuster(adj, fcu, "K")
                string = "K*(%s)" % string
        fcu.driver.expression = string
        ttypes = self.getTransformTypes(channel)
        if ttypes is None:
            return None
        for j,vname,bname in vars:
            addTransformVar(fcu, vname, ttypes[j], self.obj, self.rig2, bname)
        self.addMissingVars(fcu, vvars)
        return fcu


    def getTransformTypes(self, channel):
        if channel == "rotation":
            return ["ROT_X", "ROT_Y", "ROT_Z"]
        elif channel == "translation":
            return ["LOC_X", "LOC_Y", "LOC_Z"]
        elif channel == "scale":
            return ["SCALE_X", "SCALE_Y", "SCALE_Z"]
        else:
            reportError("Unknown channel: %s" % channel)
            return None


    def addObjectDrivers(self, ob, exprs):
        from .driver import removeModifiers
        mappings = {
            "translation" : ("location", [0,2,1], [1,1,-1], GS.scale),
            "rotation" : ("rotation_euler", [0,2,1], [1,1,-1], D),
            "scale" : ("scale", [0,2,1], [1,1,1], 1.0),
        }

        if LS.useLoadBaked:
            return
        for key,mapping in mappings.items():
            moves = exprs.get(key)
            if moves:
                channel, bindex, flips, scale = mapping
                for idx,expr in moves.items():
                    idx2 = bindex[idx]
                    ob.driver_remove(channel, idx2)
                    fcu = ob.driver_add(channel, idx2)
                    fcu.driver.type = 'SCRIPTED'
                    removeModifiers(fcu)
                    prop = "%s:%d" % (channel, idx2)
                    vec = getattr(ob, channel)
                    ob[prop] = vec[idx2]
                    string = vname = "A"
                    self.addPathVar(fcu, vname, self.obj, propRef(prop))
                    for target in expr.props:
                        vname = nextLetter(vname)
                        factor = flips[idx] * scale * target.getFactor()
                        string += "+%g*%s" % (factor, vname)
                        prop = skipName(target.key)
                        if LS.useLoadBaked:
                            final = finalProp(prop)
                            self.addPathVar(fcu, vname, self.amt, propRef(final))
                        else:
                            self.addPathVar(fcu, vname, self.obj, propRef(prop))
                    fcu.driver.expression = beautify(string)

    #------------------------------------------------------------------
    #   Build sum drivers
    #   For Xin's non-python drivers
    #------------------------------------------------------------------

    def buildSumDrivers(self):
        if GS.verbosity >= 3:
            print("Building sum drivers")
        for bname,bdata in self.sumdrivers.items():
            for channel,cdata in bdata.items():
                for idx,idata in cdata.items():
                    pb,fcu0,drivers = idata
                    if pb in self.iked:
                        print("IKE", pb.name)
                        continue
                    pathids = {}
                    if channel == "rotation_quaternion" and idx == 0:
                        path = self.getConstant("Unity", 1.0, pb, idx)
                        pathids[path] = 'ARMATURE'
                    if fcu0:
                        if fcu0.driver.type == 'SUM':
                            self.recoverOldDrivers(fcu0, drivers)
                        elif channel == "scale":
                            fcu1 = self.findScaleSumDriver(fcu0)
                            if fcu1:
                                self.recoverOldDrivers(fcu1, drivers)
                                self.amt.driver_remove(fcu1.data_path, fcu1.array_index)
                        else:
                            path = self.getOrigo(fcu0, pb, channel, idx)
                            pathids[path] = 'ARMATURE'

                    pb.driver_remove(channel, idx)
                    prefix = self.getChannelPrefix(pb, channel, idx)
                    fcu = self.addSumDriver(prefix, drivers, pathids)
                    if channel == "scale":
                        self.ensureAnimData(self.amt)
                        sumfcu = self.amt.animation_data.drivers.from_existing(src_driver=fcu)
                        prop = self.getFinalScaleProp(pb, idx)
                        self.amt[prop] = 0.0
                        sumfcu.data_path = propRef(prop)
                        self.addScaleDriver(pb, idx)
                    else:
                        self.ensureAnimData(self.obj)
                        sumfcu = self.obj.animation_data.drivers.from_existing(src_driver=fcu)
                        sumfcu.data_path = 'pose.bones["%s"].%s' % (pb.name, channel)
                        sumfcu.array_index = idx
                    self.clearTmpDriver(0)
            if GS.verbosity >= 3:
                printName(" +", bname)


    def ensureAnimData(self, rna):
        if rna.animation_data is None:
            if GS.verbosity >= 3:
                print("Make dummy driver for %s" % rna)
            rna["Dummy"] = 0.0
            fcu = rna.driver_add(propRef("Dummy"))


    def getChannelPrefix(self, pb, channel, idx):
        key = channel[0:3].capitalize()
        bname = baseBone(pb.name)
        return "%s:%s:%s" % (bname[0:54], key, idx)


    def getFinalScaleProp(self, pb, idx):
        bname = baseBone(pb.name)
        return "%s:Sca:%d" % (bname[0:54], idx)


    def getTermDriverName(self, prefix, n):
        return ("%s:%02d" % (prefix[0:60], n))


    def buildRestDrivers(self):
        from .driver import getRnaDriver
        newLine()
        if GS.verbosity >= 3:
            if self.restdrivers:
                print("Building rest drivers")
            else:
                print("No rest drivers")
        for rest,drivers in self.restdrivers.items():
            self.amt[rest] = 0.0
            fcu = getRnaDriver(self.amt, propRef(rest))
            if fcu:
                self.recoverOldDrivers(fcu, drivers)
            self.amt.driver_remove(propRef(rest))
            fcu = self.addSumDriver(rest, drivers, {})
            self.ensureAnimData(self.amt)
            sumfcu = self.amt.animation_data.drivers.from_existing(src_driver=fcu)
            self.amt.driver_remove(rest)
            sumfcu.data_path = propRef(rest)
            self.clearTmpDriver(0)


    def findScaleSumDriver(self, fcu):
        from .driver import getRnaDriver
        for var in fcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'ARMATURE':
                return getRnaDriver(self.amt, trg.data_path)
        return None


    def recoverOldDrivers(self, sumfcu, drivers):
        def addToDrivers(tokens, sign):
            for token in tokens:
                words = token.split("*")
                varname = words[-1]
                if varname in targets.keys():
                    trg2 = targets[varname]
                    prop = unPath(trg2.data_path)
                    if prop not in drivers.keys():
                        factor = sign
                        fail = False
                        if len(words) == 2:
                            try:
                                factor *= float(words[0])
                            except ValueError:
                                fail = True
                        if fail:
                            msg = ("BUG recoverOldDrivers: %s not a float: %s\n" % (prop, word1) +
                                   "  FCU2 %s %d\n" % (fcu2.data_path, fcu2.array_index) +
                                   "  EXPR %s\n" % fcu2.driver.expression +
                                   "  TARGETS %s" % list(targets.keys()))
                            print(msg)
                            continue
                        drivers[prop] = factor

        from .driver import getRnaDriver
        for var in sumfcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'OBJECT':
                fcu2 = getRnaDriver(self.obj, trg.data_path)
            else:
                fcu2 = getRnaDriver(self.amt, trg.data_path)
            if fcu2:
                targets = {}
                for var2 in fcu2.driver.variables:
                    if var2.type == 'SINGLE_PROP':
                        trg2 = var2.targets[0]
                        targets[var2.name] = trg2
                string = fcu2.driver.expression
                while string and string[0] == "(":
                    string = string[1:-1]
                string = string.replace("e-", "e_")
                words = string.split("+")
                plus = [word.split("-")[0] for word in words if word]
                minus = flatten([word.split("-")[1:] for word in words if word])
                plus = [word.replace("e_", "e-") for word in plus]
                minus = [word.replace("e_", "e-") for word in minus]
                addToDrivers(plus, +1)
                addToDrivers(minus, -1)



    def getOrigo(self, fcu0, pb, channel, idx):
        from .driver import Driver, removeModifiers
        prefix = self.getChannelPrefix(pb, channel, idx)
        prop = self.getTermDriverName(prefix, 0)
        self.amt[prop] = 0.0
        fcu = self.amt.driver_add(propRef(prop))
        driver = Driver(fcu0)
        driver.fill(fcu)
        removeModifiers(fcu)
        return propRef(prop)


    def getConstant(self, prop, value, pb, idx):
        from .driver import getRnaDriver, removeModifiers
        self.amt[prop] = value
        path = propRef(prop)
        if not getRnaDriver(self.amt, path):
            fcu = self.amt.driver_add(path)
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            fcu.driver.expression = "%.1f" % value
        return path


    def optimizeJcmDrivers(self):
        if (GS.onShapekeyDrivers != 'OPTIMIZE_JCMS' or
            GS.useMakeHiddenSliders or
            self.useMakeHiddenSliders or
            self.rig is None or
            self.amt is None or
            self.amt.animation_data is None or
            self.mesh is None):
            return
        if GS.verbosity >= 2:
            print("Optimize JCM drivers")
        skeys = self.mesh.data.shape_keys
        if skeys is None or skeys.animation_data is None:
            return
        drivers = {}
        for fcu in self.amt.animation_data.drivers:
            if fcu.array_index == 0:
                drivers[fcu.data_path] = fcu

        def changeTarget(fcu, skeys):
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = baseProp(getProp(trg.data_path))
                    if (prop in skeys.key_blocks.keys() and
                        trg.id_type == 'ARMATURE' and
                        trg.id == self.amt):
                        trg.id_type = 'KEY'
                        trg.id = skeys
                        trg.data_path = 'key_blocks["%s"].value' % prop

        for prop in self.propDrivers.keys():
            skey = skeys.key_blocks.get(prop)
            if skey:
                final = finalProp(prop)
                fcu = drivers.get(propRef(final))
                if fcu:
                    changeTarget(fcu, skeys)
                    skey.driver_remove("value")
                    fcu2 = skeys.animation_data.drivers.from_existing(src_driver=fcu)
                    fcu2.data_path = 'key_blocks["%s"].value' % prop
                    self.obj.driver_remove(propRef(prop))
                    if prop in self.obj.keys():
                        del self.obj[prop]
                    self.amt.driver_remove(propRef(final))
                    if final in self.amt.keys():
                        del self.amt[final]


    def addScaleDriver(self, pb, idx):
        from .driver import removeModifiers
        pb.driver_remove("scale", idx)
        fcu = pb.driver_add("scale", idx)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        prop = self.getFinalScaleProp(pb, idx)
        if inheritsScale(pb):
            fcu.driver.expression = "(1+a)/parscale"
            self.addPathVar(fcu, "a", self.amt, propRef(prop))
            self.correctScaleFcurve(fcu, pb, idx)
        else:
            self.addPathVar(fcu, "a", self.amt, propRef(prop))
            fcu.driver.expression = "1+a"
        return fcu


    def correctScaleFcurve(self, fcu, pb, idx):
        var = fcu.driver.variables.new()
        var.name = "parscale"
        var.type = 'TRANSFORMS'
        trg = var.targets[0]
        trg.id = self.obj
        trg.bone_target = pb.parent.name
        trg.transform_type = 'SCALE_%s' % chr(ord('X')+idx)
        trg.transform_space = 'LOCAL_SPACE'


    def correctScaleParents(self):
        from .driver import getDriver, removeModifiers
        if self.rig is None:
            return
        for pb in self.rig.pose.bones:
            if inheritsScale(pb):
                parchannel = 'pose.bones["%s"].scale' % pb.parent.name
                channel = 'pose.bones["%s"].scale' % pb.name
                for idx in range(3):
                    if getDriver(self.rig, parchannel, idx):
                        fcu = getDriver(self.rig, channel, idx)
                        if fcu is None:
                            fcu = pb.driver_add("scale", idx)
                            fcu.driver.type = 'SCRIPTED'
                            removeModifiers(fcu)
                            fcu.driver.expression = "1/parscale"
                            self.correctScaleFcurve(fcu, pb, idx)


    def getBatches(self, drivers, prefix):
        batches = []
        string = ""
        nterms = 0
        varname = "a"
        vars = []
        bname = prefix[:-6]
        pb = self.rig.pose.bones.get(bname)
        for final,target in drivers.items():
            factor,points = self.getFactorPoints(target, final)
            if factor == 0.0 and not points:
                continue
            string += self.getFactorPointsString(factor, points, varname)
            nterms += 1
            vars.append((varname, final))
            varname = nextLetter(varname)
            if (nterms > MAX_TERMS or
                len(string) > MAX_EXPR_LEN):
                batches.append((string, vars))
                string = ""
                nterms = 0
                varname = "a"
                vars = []
        if vars:
            batches.append((string, vars))
        return batches


    def addSumDriver(self, prefix, drivers, pathids):
        batches = self.getBatches(drivers, prefix)
        sumfcu = self.getTmpDriver(0)
        sumfcu.driver.type = 'SUM'
        for n,batch in enumerate(batches):
            string,vars = batch
            drvprop = self.getTermDriverName(prefix, n+1)
            self.amt[drvprop] = 0.0
            path = propRef(drvprop)
            self.amt.driver_remove(path)
            fcu = self.getTmpDriver(1)
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = string
            for varname,final in vars:
                self.addPathVar(fcu, varname, self.amt, propRef(final))
            pathids[path] = 'ARMATURE'
            self.ensureAnimData(self.amt)
            fcu2 = self.amt.animation_data.drivers.from_existing(src_driver=fcu)
            fcu2.data_path = path
            self.clearTmpDriver(1)
        for n,data in enumerate(pathids.items()):
            path,id_type = data
            if id_type == 'OBJECT':
                rna = self.obj
            else:
                rna = self.amt
            self.addPathVar(sumfcu, "t%.02d" % n, rna, path)
        return sumfcu


    def getActiveShape(self, asset):
        ob = self.mesh
        sname = asset.name
        skey = None
        if ob.data.shape_keys:
            skey = ob.data.shape_keys.key_blocks[ob.active_shape_key_index]
            skey.name = sname
        return skey, ob, sname

#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, altmorphs, errors):
    def buildPath(exprs, pb, path):
        lm = LoadMorph()
        lm.initRig(rig2, rig)
        for idx,expr in exprs.items():
            target = expr.bone
            if target is None:
                continue
            bname = target.key
            factor = target.factor
            channel = expr.path
            comp = target.comp
            unit = getUnit(channel)/getUnit(target.type)
            pbDriver = rig.pose.bones.get(bname)
            if pbDriver:
                if pbDriver.parent == pb:
                    if path == "scale":
                        pbDriver.bone.inherit_scale = pb.bone.inherit_scale = 'FULL'
                    elif GS.verbosity >= 3:
                        print("Dependency loop: %s %s" % (pbDriver.name, pb.name))
                    continue
                if factor:
                    tvec,idx2 = getTransformVector(factor, path, comp, pbDriver, pb, idx)
                    if path == "rotation_quaternion" and idx2 == 1:
                        from .driver import removeModifiers, addTransformVar
                        lm.makeSimpleBoneDriver("rotation", tvec, pb, path, idx2+1, bname, False)
                        pb.driver_remove(path, 0)
                        fcu = pb.driver_add(path, 0)
                        fcu.driver.type = 'SCRIPTED'
                        fcu.driver.expression = "sqrt(1-%.4f*y*y)" % (factor**2)
                        removeModifiers(fcu)
                        addTransformVar(fcu, "y", "ROT_Y", rig, None, bname)
                    else:
                        lm.makeSimpleBoneDriver(channel, tvec, pb, path, idx2, bname, False)


    def canOptimizeScale(exprs, pb, rig):
        parent = pb.parent
        if parent:
            parents = [parent.name]
        else:
            return False
        while parent and parent.bone.inherit_scale == 'FULL':
            parent = parent.parent
            if parent:
                parents.append(parent.name)
        for idx,expr in exprs.items():
            if idx < 0 or expr.bone is None:
                continue
            ok = False
            for driver,path,comp in expr.bone.mults:
                if path == "scale" and driver in parents and comp == idx:
                    ok = True
                    break
            if not ok:
                return False
        return True


    def getTransformVector(factor, channel, comp, pbDriver, pb, idx):
        uvec = getBoneVector(factor, comp, pbDriver)
        dvec = getBoneVector(1.0, idx, pb)
        idx2,sign,x = getDrivenComp(dvec)
        if channel == "scale":
            tvec = Vector([abs(y) for y in uvec])
        else:
            tvec = sign*uvec
        return tvec, idx2


    def buildValueDriver(exprs, raw):
        lm = LoadMorph()
        lm.initRig(rig, rig)
        for idx,expr in exprs.items():
            if not expr.bone:
                continue
            bname = expr.bone.key
            if (bname not in rig.pose.bones.keys() and
                bname[-2:] == "-1"):
                bname = bname[:-2]
                print("TRY", bname)
            if bname not in rig.pose.bones.keys():
                print("Missing bone (buildValueDriver):", bname)
                continue
            final = finalProp(raw)
            if final not in rig.data.keys():
                rig.data[final] = 0.0
            lm.buildBoneDriver(raw, bname, expr, True)

    exprs,rig2 = asset.evalFormulas(rig, None, True)
    for driven,expr in exprs.items():
        if "rotation" in expr.keys():
            if driven in rig2.pose.bones.keys():
                pb = rig2.pose.bones[driven]
                if pb.rotation_mode == 'QUATERNION':
                    buildPath(expr["rotation"], pb, "rotation_quaternion")
                else:
                    buildPath(expr["rotation"], pb, "rotation_euler")
        if "translation" in expr.keys():
            if driven in rig2.pose.bones.keys():
                pb = rig2.pose.bones[driven]
                buildPath(expr["translation"], pb, "location")
        if "scale" in expr.keys() and not GS.useInheritScale:
            if driven in rig2.pose.bones.keys():
                pb = rig2.pose.bones[driven]
                if canOptimizeScale(expr["scale"], pb, rig2):
                    pb.bone.inherit_scale = 'FULL'
                else:
                    buildPath(expr["scale"], pb, "scale")

        if "value" in expr.keys():
            formulas = expr["value"]
            if driven in altmorphs.keys():
                for alt,factor in altmorphs[driven].items():
                    if factor != 1:
                        for idx,expr in formulas.items():
                            expr.multFactors(factor)
                    buildValueDriver(formulas, alt)
            else:
                buildValueDriver(formulas, driven)

#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def getBoneVector(factor, comp, pb):
    from .node import getTransformMatrix
    tmat = getTransformMatrix(pb, None)
    uvec = Vector((0,0,0))
    uvec[comp] = factor
    return uvec @ tmat


def d2bBone(pb, channel, idx):
    idx2 = dazRna(pb).DazAxes[idx]
    return idx2, (1 if channel == "scale" else dazRna(pb).DazFlips[idx2])


def printName(char, name):
    if GS.showInTerminal and not ES.easy:
        print(char, name)
    elif not ES.easy or GS.showInTerminal:
        sys.stdout.write(char)
        sys.stdout.flush()


def newLine():
    if GS.showInTerminal and not ES.easy:
        pass
    elif not ES.easy or GS.showInTerminal:
        print("")


def isPath(path):
    return (path[0:2] == '["')

def unPath(path):
    if path[0:2] == '["':
        return path[2:-2]
    elif path[0:6] == 'data["':
        return path[6,-2]
    else:
        return path

def getDrivenComp(vec):
    for n,x in enumerate(vec):
        if abs(x) > 0.1:
            return n, (1 if x >= 0 else -1), x

def getPrint(x):
    string = "%.3f" % x
    while (string[-1] == "0"):
        string = string[:-1]
    return string[:-1] if string[-1] == "." else string

def getMult(x, comp):
    xx = getPrint(x)
    if xx in ["0", "-0"]:
        return "0"
    elif xx == "1":
        return comp
    elif xx == "-1":
        return "-%s" % comp
    else:
        return "%s*%s" % (xx, comp)

def getSign(u):
    if u < 0:
        return "-", -u
    else:
        return "+", u

def getUnit(type):
    if type == "translation":
        return GS.scale
    elif type == "rotation":
        return D
    else:
        return 1

def beautify(string):
    return string.replace("+-", "-").replace("+1*", "+").replace("-1*", "-")