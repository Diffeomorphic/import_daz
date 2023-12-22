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
import sys
import numpy as np
import bpy
from .driver import DriverUser
from .utils import *
from .error import reportError, DazError, addItem
from .load_json import JL

MAX_EXPRESSION_SIZE = 255
MAX_TERMS = 12
MAX_TERMS2 = 9
MAX_EXPR_LEN = 240

ALWAYS_BAKED = [
    "CTRLInitialGensShape01",
]

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

class LoadMorph(DriverUser):
    morphset = None
    bodypart = "Custom"
    usePropDrivers = True
    isJcm = False
    treatHD = 'ERROR'
    useAdjusters = False
    onMorphSuffix = 'NONE'
    useSearchAlias = True
    onlyProperties = False
    useProtected = False
    defaultMultiplier = 1.0
    useMulti = False
    disableErc = False

    def __init__(self):
        self.rig = None
        self.amt = None
        self.mesh = None
        self.meshes = []
        self.char = None
        self.chars = []
        self.modded = False
        self.duplicates = []
        self.baked = []
        self.mult = []
        self.mults = {}
        self.adjustable = {}
        self.currentAsset = None
        self.origMorphset = ""
        self.trivial = {}


    def getAdjustProp(self):
        return None


    def addToMorphSet(self, prop, asset, hidden, protected):
        return


    def initRig(self, rig):
        self.rig = rig
        self.initAmt()


    def initAmt(self):
        if self.rig:
            self.amt = self.rig.data
        else:
            self.amt = None

    def setupUniqueSuffix(self):
        self.uniqueSuffix = ""

    def getUniqueName(self, string):
        return string

    def addUrl(self, asset, aliases, filepath):
        pass

    def initAll(self):
        DriverUser.__init__(self)
        self.alias = {}
        self.loaded = []
        self.referred = {}
        self.primary = {}
        self.visible = {}
        self.erc = False
        self.drivers = {}
        self.shapekeys = {}
        self.faceshapes = {}
        self.mults = {}
        self.sumdrivers = {}
        self.restdrivers = {}
        self.iked = []
        self.origRestored = []
        self.bakedSkipped = {}
        self.ercMorphs = {}
        self.initAmt()


    def loadAllMorphs(self, namepaths):
        name = namepaths[0][0]
        self.initAll()
        if self.rig:
            self.baked = [key.lower() for key in self.rig.DazBaked.keys()]
        self.adjustable = {}
        self.origMorphset = self.morphset

        if self.amt and self.amt.DazOptimizedDrivers:
            raise DazError("Cannot add new morphs to an armature with optimized drivers")

        if GS.verbosity >= 3:
            print("Making morphs")
        self.makeAllMorphs(namepaths, True)
        adjustable = self.adjustable
        self.adjustable = {}
        self.bodypart = namepaths[0][2]
        self.makeMissingMorphs(0)
        self.adjustable = adjustable
        if self.rig:
            self.createTmp()
            try:
                self.buildDrivers()
                self.buildSumDrivers()
                self.buildRestDrivers()
                if self.isJcm and not GS.useMuteDrivers:
                    self.optimizeJcmDrivers()
                self.correctScaleParents()
            finally:
                self.deleteTmp()
            self.rig.update_tag()
            if self.mesh:
                if self.ercMorphs:
                    meshes = getMeshChildren(self.rig)
                    self.transferErcShapes(bpy.context, self.mesh, meshes)
                    for ob in getMeshChildren(self.rig):
                        self.applyErcArmature(bpy.context, ob)
                        ob.update_tag()
                else:
                    self.mesh.update_tag()
        if self.origRestored:
            from .geometry import clearMeshProps
            for ob in self.origRestored:
                clearMeshProps(ob)
            self.origRestored = []

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
            if lname in self.baked and not GS.useBakedMorphs:
                if lname not in self.bakedSkipped.keys():
                    self.bakedSkipped[lname] = name
            else:
                struct = JL.load(filepath)
                assets = parseAssetFile(struct, multi=True)
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
        from .modifier import Alias, ChannelAsset
        self.currentAsset = asset
        self.setupUniqueSuffix()
        if not force:
            if self.alreadyLoaded(asset):
                return " ."
        if not isinstance(asset, ChannelAsset):
            return " -"
        elif isinstance(asset, Alias) and self.useSearchAlias:
            return " _"
        self.bodypart = bodypart
        skey,ok = self.buildShape(asset)
        if skey:
            self.trivial[name] = False
        if not ok:
            return " #"
        elif self.rig and self.usePropDrivers:
            self.ercBones = {}
            if self.makeFormulas(asset, skey):
                self.trivial[name] = False
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
        if self.rig and raw in self.rig.keys() and final in self.amt.keys():
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
            if self.rig is None:
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
        pgs = self.rig.DazAlias
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
                GS.useShapekeys and
                not self.onlyProperties):
            return None,True

        from .driver import makePropDriver
        from .hdmorphs import addSkeyToUrls
        useBuild = True
        nverts = len(self.mesh.data.vertices)

        if GS.useModifiedMesh and self.modded:
            from .geometry import restoreOrigVerts
            hasOrig, restored = restoreOrigVerts(self.mesh, asset.vertex_count)
            if restored and self.mesh not in self.origRestored:
                self.origRestored.append(self.mesh)
            if hasOrig:
                finger = self.mesh.data.DazFingerPrint
                nverts = int(finger.split("-")[0])

        parent = self.getGraftParent(asset)
        if (asset.vertex_count < 0 or
            asset.vertex_count == nverts or
            parent):
            pass
        else:
            from .finger import VertexCounts
            msg = ("Vertex count mismatch: %d != %d" % (asset.vertex_count, len(self.mesh.data.vertices)))
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
                asset.buildMorph(parent, useBuild=useBuild)
            else:
                asset.buildMorph(self.mesh, useBuild=useBuild)
        skey,_,sname = asset.rna
        if skey:
            prop = rawProp(self.getUniqueName(unquote(skey.name)))
            self.alias[prop] = skey.name
            skey.name = prop
            self.setShapeLimits(GS.finalLimits, skey, asset)
            self.shapekeys[prop] = skey
            if GS.ercMethod == 'TRANSLATION' and not self.disableErc:
                pass
            elif self.bodypart == "Face":
                self.faceshapes[skey.name] = True
            addSkeyToUrls(self.mesh, asset, skey)
            if self.rig and self.usePropDrivers:
                final = self.addNewProp(prop)
                self.addShapeDriver(skey, final)
            pgs = self.mesh.data.DazBodyPart
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
            self.mesh.data.DazVertexCount == asset.vertex_count and
            self.mesh.data.DazGraftGroup and
            self.rig):
            for ob in self.rig.children:
                if len(ob.data.vertices) == asset.vertex_count:
                    return ob
        return None


    def makeFormulas(self, asset, skey):
        from .formula import Formula, setFormulaExpr
        from .modifier import Alias
        prop = rawProp(self.getUniqueName(asset.getName()))
        if prop != asset.name:
            self.setAlias(asset.name, prop)
        self.addNewProp(prop, asset, skey)
        self.adjustable[prop] = True
        if isinstance(asset, Formula):
            exprs = asset.evalFormulas(self.rig, self.mesh, True)
        elif isinstance(asset, Alias):
            exprs = {}
            alias = asset.getAlias()
            if alias == prop:
                print("Alias is same: %s" % prop)
                return
            expr = setFormulaExpr(exprs, alias, "value", "value", 0)
            expr["prop"] = prop
            expr["factor"] = 1
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
                        self.makeValueFormula(output, expr)
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
                        if self.disableErc:
                            pass
                        elif GS.ercMethod == 'TRANSLATION':
                            self.makeErcFormula(output, idx, expr)
                        elif GS.ercMethod == 'ARMATURE':
                            self.makeOffsetFormula("HdOffset", output, idx, expr)
                    elif key == "end_point":
                        self.erc = True
                        if self.disableErc:
                            pass
                        elif GS.ercMethod == 'ARMATURE':
                            self.makeOffsetFormula("TlOffset", output, idx, expr)
        return True


    def getTypeAdjuster(self, raw):
        if self.useAdjusters and raw in self.adjustable.keys():
            adj = self.getAdjustProp()
            return self.getAdjuster(adj)
        else:
            return None


    def getStrengthAdjuster(self):
        if (GS.useStrengthAdjusters == 'ALL' or
            GS.useStrengthAdjusters == self.bodypart):
            adj = "Adjust Morph Strength"
            return self.getAdjuster(adj)
        else:
            return None


    def getAdjuster(self, adj):
        from .driver import setFloatProp, makePropDriver
        if adj and adj not in self.rig.keys():
            final = finalProp(adj)
            setFloatProp(self.rig, adj, 1.0, 0.0, 1000.0, True)
            setFloatProp(self.amt, final, 1.0, 0.0, 1000.0, False)
            makePropDriver(propRef(adj), self.amt, propRef(final), self.rig, "x")
        return adj


    def addShapeDriver(self, skey, final, expr="a"):
        from .driver import removeModifiers

        def addDriver(channel):
            skey.driver_remove(channel)
            fcu = skey.driver_add(channel)
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            self.addPathVar(fcu, "a", self.amt, propRef(final))
            fcu.driver.expression = expr
            return fcu

        fcu = addDriver("value")
        if GS.useMuteDrivers:
            fcu = addDriver("mute")
            fcu.driver.expression = "abs(%s)<0.0001" % fcu.driver.expression


    def adjustStrength(self, adj, pb, string, vars):
        if pb is None or adj is None:
            return string
        vars.append(("L", finalProp(adj)))
        return "L*(%s)" % string


    def getFileRef(self, filepath):
        fileref = getCanonicalFilePath(filepath)
        if fileref:
            return fileref
        else:
            msg = ('Did not find file:\n"%s"' % filepath)
            raise DazError(msg)


    def addNewProp(self, raw, asset=None, skey=None):
        from .driver import setBoolProp, getPropMinMax, setProtected
        from .selector import setActivated
        from .modifier import Alias
        final = finalProp(raw)
        if raw not in self.drivers.keys():
            self.drivers[raw] = []
            self.visible[raw] = False
            self.primary[raw] = False
        if asset:
            visible = (asset.visible or GS.useMakeHiddenSliders)
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
            if skey and not visible:
                return final
            elif asset.type == "bool":
                setBoolProp(self.rig, raw, asset.value, True)
                setBoolProp(self.amt, final, asset.value, False)
            elif asset.type == "float" or asset.type == "alias":
                self.setFloatLimits(self.rig, raw, GS.sliderLimits, asset, None, True)
                self.setFloatLimits(self.amt, final, GS.finalLimits, asset, skey, False)
            elif asset.type == "int":
                self.rig[raw] = asset.value
                self.amt[final] = asset.value
            else:
                self.setFloatLimits(self.rig, raw, GS.sliderLimits, asset, None, True)
                self.setFloatLimits(self.amt, final, GS.finalLimits, asset, skey, False)
                reportError("BUG: Unknown asset type: %s.\nAsset: %s" % (asset.type, asset))
            if visible:
                if self.useProtected:
                    setProtected(self.rig, raw, True)
                setActivated(self.rig, raw, (not self.useProtected))
                self.addToMorphSet(raw, asset, False, self.useProtected)
        return final


    def setFloatLimits(self, rna, prop, limits, asset, skey, ovr):
        value = asset.value
        baseprop = prop.split(":", 1)[0]
        if ((self.rig and baseprop in self.rig.DazBaked.keys()) or
            baseprop in ALWAYS_BAKED):
            value = 0
            print("Baked %s = 0" % baseprop)
        from .driver import setFloatProp
        if limits == 'DAZ':
            min = GS.morphMultiplier * asset.min
            max = GS.morphMultiplier * asset.max
            setFloatProp(rna, prop, value, min, max, ovr)
        elif limits == 'CUSTOM':
            setFloatProp(rna, prop, value, GS.customMin, GS.customMax, ovr)
        else:
            setFloatProp(rna, prop, value, None, None, ovr)
        if skey:
            self.setShapeLimits(limits, skey, asset)


    def setShapeLimits(self, limits, skey, asset):
        if limits == 'DAZ':
            skey.slider_min = GS.morphMultiplier * asset.min
            skey.slider_max = GS.morphMultiplier * asset.max
        elif limits == 'CUSTOM':
            skey.slider_min = GS.customMin
            skey.slider_max = GS.customMax
        else:
            skey.slider_min = -10
            skey.slider_max = 10


    def makeValueFormula(self, output, expr):
        output = self.getUniqueName(output)
        if expr["prop"]:
            self.addNewProp(output)
            prop = self.getUniqueName(expr["prop"])
            factor = expr["factor"]
            if "points" in expr.keys():
                factor = self.cheatSplineTCB(expr["points"], factor)
            self.drivers[output].append(("PROP", prop, factor))
            if expr["prop2"]:
                prop2 = self.getUniqueName(expr["prop2"])
                factor2 = expr["factor2"]
                self.drivers[output].append(("PROP", prop2, factor2))
        for mult in expr["mults"]:
            if isinstance(mult, str):
                mult = self.getUniqueName(mult)
                self.addNewProp(mult)
            if output not in self.mults.keys():
                self.mults[output] = []
            self.mults[output].append(mult)
        if expr["bone"]:
            bname = expr["bone"]
            if output not in self.drivers.keys():
                self.drivers[output] = []
            self.drivers[output].append(("BONE", bname, expr))


    def getBoneData(self, bname, expr):
        from .transform import Transform
        if bname is None:
            return
        elif bname == "RIG":
            pb = self.rig
        else:
            pb = self.rig.pose.bones[bname]
        factor = expr["factor"]
        if "points" in expr.keys():
            factor = self.cheatSplineTCB(expr["points"], factor)
        raw = rawProp(self.getUniqueName(expr["prop"]))
        final = self.addNewProp(raw)
        tfm = Transform()
        return tfm, pb, final, factor


    def cheatSplineTCB(self, points, factor):
        x0 = y0 = None
        for n,point in enumerate(points):
            x,y = point[0:2]
            if x == 0 and y == 0:
                x0 = x
                y0 = y
                n0 = n
                break
        if x0 is None:
            return factor
        if n0 == 0:
            x1,y1 = points[-1][0:2]
        else:
            x1,y1 = points[0][0:2]
        factor = (y1-y0)/(x1-x0)
        return factor


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
        self.setFcurves(pb, vec, prop, attr, "pose")


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
        from mathutils import Matrix
        offsets = {}
        for pb in self.rig.pose.bones:
            tfm,trans = self.ercBones.get(pb.name, (None,None))
            if tfm:
                offset = trans - getParentTrans(pb)
                dmat,bmat,rmat,parent = getTransformMatrices(pb, self.rig, {})
                tmat = rmat.inverted() @ Matrix.Translation(offset) @ rmat
                tfm.trans = tmat.to_translation()
                self.addPoseboneDriver(pb, tfm)


    def transferErcShapes(self, context, ob, meshes):
        from .morphing import transferShapesToMeshes
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        props = [baseProp(final) for final in self.ercMorphs.keys()]
        snames = [prop for prop in props if prop in skeys.key_blocks.keys()]
        transferShapesToMeshes(context, ob, meshes, snames)


    def applyErcArmature(self, context, ob):
        from .merge import applyArmatureModifier
        from .modifier import getBasicShape, newArmatureModifier
        from .driver import getPropMinMax

        activateObject(context, ob)
        basic,skeys,new = getBasicShape(ob)
        for skey in skeys.key_blocks:
            skey.mute = True
            skey.value = 0.0
        for final,ercBones in self.ercMorphs.items():
            prop = baseProp(final)
            fcus = []
            for fcu in self.rig.animation_data.drivers:
                bname,channel = getBoneChannel(fcu)
                if bname and bname not in ercBones.keys():
                    fcus.append((fcu, fcu.mute))
                    fcu.mute = True
            self.rig[prop] = 1.0
            updateDrivers(self.amt)
            applyArmatureModifier(ob)
            self.rig[prop] = 0.0
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
        for skey in skeys.key_blocks:
            skey.mute = False
        updateDrivers(self.amt)

    #-------------------------------------------------------------
    #   Add posebone driver
    #-------------------------------------------------------------

    def addObjectDriver(self, tfm):
        success = False
        if tfm.scaleProp:
            self.setFcurves(self.rig, tfm.scale-One, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(self.rig, tfm.general-One, tfm.generalProp, "scale")
            success = True
        return success


    def addPoseboneDriver(self, pb, tfm):
        if pb == self.rig:
            return self.addObjectDriver(tfm)
        from .node import getBoneMatrix
        mat = getBoneMatrix(tfm, pb, self.rig)
        loc,quat,scale = mat.decompose()
        success = False
        if (tfm.transProp and loc.length > 0.01*self.rig.DazScale):
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


    def setFcurves(self, pb, vec, prop, channel, pose="pose"):
        def getBoneFcurves(pb, channel):
            if isinstance(pb, bpy.types.Object):
                path = channel
            else:
                path = '%s.bones["%s"].%s' % (pose, pb.name, channel)
            fcurves = {}
            if self.rig.animation_data:
                for fcu in self.rig.animation_data.drivers:
                    if path == fcu.data_path:
                        fcurves[fcu.array_index] = fcu
            return fcurves

        if drvBone(pb.name) in self.rig.pose.bones.keys():
            pb = self.rig.pose.bones[drvBone(pb.name)]
        fcurves = getBoneFcurves(pb, channel)
        for idx,factor in self.getFactors(vec):
            if idx in fcurves.keys():
                fcu = fcurves[idx]
            else:
                fcu = None
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
        #if drvBone(bname) in self.rig.data.bones.keys():
        #    bname = drvBone(bname)
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
        protected = self.useProtected
        self.useProtected = False
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
                    morphset = self.getPathMorphSet(path, morphfiles)
                    if morphset:
                        groupedpaths[morphset].append(data)
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
        self.useProtected = protected


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
            print("Building drivers")
        for output,drivers in self.drivers.items():
            if drivers:
                if self.isDriverType('BONE', drivers):
                    for dtype,bname,expr in drivers:
                        if dtype == 'BONE':
                            self.buildBoneDriver(output, bname, expr, False)
                elif self.isDriverType('PROP', drivers):
                    self.buildPropDriver(rawProp(output), drivers)
            elif self.visible[output]:
                self.buildPropDriver(rawProp(output), drivers)
            else:
                final = finalProp(output)
                if final not in self.amt.keys():
                    self.amt[final] = 0.0


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


    def buildNewPropDriver(self, fcu, rna, channel, string, raw, drivers, string0, vvars):
        varname = "a"
        if self.visible[raw] or not self.primary[raw]:
            string += varname
            self.addPathVar(fcu, varname, self.rig, propRef(raw))
            if raw not in self.rig.keys():
                self.rig[raw] = 0.0
        string,rdrivers = self.addDriverVars(fcu, string, varname, raw, drivers)
        if not string:
            if vvars:
                fcu.driver.expression = string0
                print("Keep old driver: %s" % raw)
                return True
            else:
                print("Remove driver: %s" % raw)
                rna.driver_remove(channel)
                return False
        if self.getMultipliers(raw):
            string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        if rdrivers:
            self.extendPropDriver(fcu, raw, rdrivers)
        return True


    def extractBoneExpression(self, string, varname):
        string = string.split("(", 1)[-1]
        mult = string.split(varname, 1)[0]
        if mult == "0" or mult == "0*":
            return ""
        if mult == "0":
            mult = "0*"
        return "%s%s+" % (mult, varname)


    def addDriverVars(self, fcu, string, varname, raw, drivers):
        def multiply(factor, varname):
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "%+g*%s" % (factor, varname)

        channels = [var.targets[0].data_path for var in fcu.driver.variables]
        for dtype,subraw,factor in drivers[0:MAX_TERMS2]:
            if dtype != 'PROP' or factor == 0.0:
                continue
            subraw = rawProp(subraw)
            subfinal = finalProp(subraw)
            channel = propRef(subfinal)
            if channel in channels:
                continue
            varname = nextLetter(varname)
            string += multiply(factor, varname)
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
        for dtype,raw,factor in drivers:
            if dtype == 'PROP':
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
        adjs = []
        adj = self.getTypeAdjuster(raw)
        if adj:
            adjs.append(adj)
        adj = self.getStrengthAdjuster()
        if adj:
            adjs.append(adj)
        if adjs:
            self.mult = adjs + [prop for prop in props if prop[0:3].lower() not in ["fbm", "fhm"]]
        else:
            self.mult = props
        return self.mult


    def multiplyMults(self, fcu, string):
        if self.mult:
            mstring = ""
            if len(string) == 0:
                reportError("Trying to multiply empty string", trigger=(1,1))
            elif len(string) > 1 and string[1] == '*' and string[0].isupper():
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
                        addTransformVar(fcu, varname, ttypes[idx2], self.rig, bname)
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
        from .driver import removeModifiers, setProtected
        from .selector import setActivated
        if self.rig is None:
            return
        if raw not in self.rig.keys():
            self.rig[raw] = default
        if final not in self.amt.keys():
            self.amt[final] = default
            fcu = self.amt.driver_add(propRef(final))
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            fcu.driver.expression = "a"
            self.addPathVar(fcu, "a", self.rig, propRef(raw))


    def buildBoneDriver(self, raw, bname, expr, keep):
        def getSplinePoints(expr, pb, comp):
            points = expr["points"]
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
        rna,channel = self.getDrivenChannel(raw)
        #rna.driver_remove(channel)
        path = expr["path"]
        comp = expr["comp"]
        unit = getUnit(path, self.rig)
        self.getMultipliers(raw)
        if "points" in expr.keys():
            uvec,xys = getSplinePoints(expr, pb, comp)
            self.makeSplineBoneDriver(path, uvec, xys, rna, channel, -1, bname, keep)
        else:
            factor = expr["factor"]
            uvec = unit*getBoneVector(factor, comp, pb)
            bname2 = expr.get("bone2")
            uvec2 = None
            if bname2 and bname2 in self.rig.pose.bones.keys():
                pb2 = self.rig.pose.bones[bname2]
                factor2 = expr["factor2"]
                comp2 = expr["comp2"]
                uvec2 = unit*getBoneVector(factor2, comp2, pb2)
            self.makeSimpleBoneDriver(path, uvec, rna, channel, -1, bname, keep, bname2, uvec2)

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


    def makeSplineBoneDriver(self, channel, uvec, points, rna, path, idx, bname, keep):
        # Only make spline for one component
        #[1 if x< -1.983 else -x-0.983 if x< -0.983  else 0 for x in [+0.988*A]][0]
        #1 if A< -1.983/0.988 else -0.988*A-0.983 if A< -0.983/0.988  else 0

        var,vars,umax = self.getVarData(uvec, bname, "A")
        lt = ("<" if umax > 0 else ">")

        n = len(points)
        xi,yi = points[0]
        string = "("
        term = getPrint(yi)
        prev = "%s if %s%s %s" % (term, var, lt, getPrint(xi/umax))
        tie = ""
        for i in range(1, n):
            xj,yj = points[i]
            kij = (yj-yi)/(xj-xi)
            zs,zi = getSign((yi - kij*xi)/umax)
            zstring = ""
            if abs(zi) > 5e-4:
                zstring = ("%s%s" % (zs, getPrint(zi*umax)))
                if zstring[0:2] == "+-":
                    zstring = zstring[1:]
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
        string += " else %s)" % default

        if len(string) > 254:
            msg = "String driver too long:\n"
            for n in range(5):
                msg += "%s         \n" % (string[30*n, 30*(n+1)])
            raise DazError(msg)

        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeBoneDriver(self, string, vars, channel, rna, path, idx, keep):
        from .driver import addTransformVar, Variable, getRnaDriver, removeModifiers
        bvars = []
        vvars = {}
        if keep:
            fcu0 = getRnaDriver(rna, path, None)
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
        if string[0:5] != "clamp" and self.currentAsset and bpy.app.version >= (2,93,0):
            words = string.split("else ")
            if len(words) == 3:
                words = words[1].split(" if")
                if len(words) == 2:
                    string = words[0]
            string = "clamp(%s,%g,%g)" % (string, self.currentAsset.min, self.currentAsset.max)
        if GS.useMakeHiddenSliders and isPath(path) and "u" not in vvars.keys():
            final = unPath(path)
            if isFinal(final):
                raw = baseProp(final)
                if string[0] == "-":
                    string = "u%s" % string
                else:
                    string = "u+%s" % string
                self.rig[raw] = 0.0
                self.addPathVar(fcu, "u", self.rig, propRef(raw))
                self.addToMorphSet(raw, None, True, self.useProtected)
        string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        ttypes = self.getTransformTypes(channel)
        if ttypes is None:
            return None
        for j,vname,bname in vars:
            addTransformVar(fcu, vname, ttypes[j], self.rig, bname)
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
                        self.ensureAnimData(self.rig)
                        sumfcu = self.rig.animation_data.drivers.from_existing(src_driver=fcu)
                        sumfcu.data_path = 'pose.bones["%s"].%s' % (pb.name, channel)
                        sumfcu.array_index = idx
                    self.clearTmpDriver(0)
            printName(" +", bname)


    def ensureAnimData(self, rna):
        if rna.animation_data is None:
            print("Make dummy driver for %s" % rna)
            rna["Dummy"] = 0.0
            fcu = rna.driver_add(propRef("Dummy"))


    def getChannelPrefix(self, pb, channel, idx):
        key = channel[0:3].capitalize()
        return "%s:%s:%s" % (pb.name[0:54], key, idx)


    def getFinalScaleProp(self, pb, idx):
        return "%s:Sca:%d" % (pb.name[0:54], idx)


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
        from .driver import getRnaDriver
        for var in sumfcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'OBJECT':
                fcu2 = getRnaDriver(self.rig, trg.data_path)
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
                words = string.split("*")
                word1 = words[0]
                for word2 in words[1:]:
                    varname = word2[0]
                    if varname in targets.keys():
                        trg2 = targets[varname]
                        prop = unPath(trg2.data_path)
                        if prop not in drivers.keys():
                            try:
                                factor = float(word1)
                            except ValueError:
                                msg = ("BUG recoverOldDrivers: not a float\n" +
                                       "FCU2 %s %d" % (fcu2.data_path, fcu2.array_index) +
                                       "EXPR %s" % fcu2.driver.expression +
                                       "TARGETS %s" % list(targets.keys()))
                                reportError(msg, trigger=(0,0))
                            drivers[prop] = factor
                    word1 = word2[1:]


    def getOrigo(self, fcu0, pb, channel, idx):
        from .driver import Driver, removeModifiers
        prefix = self.getChannelPrefix(pb, channel, idx)
        prop = self.getTermDriverName(prefix, 0)
        self.amt[prop] = 0.0
        fcu = self.amt.driver_add(propRef(prop))
        driver = Driver(fcu0, True)
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
        if (not GS.useOptimizeJcms or
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
        for prop in self.drivers.keys():
            skey = skeys.key_blocks.get(prop)
            if skey:
                final = finalProp(prop)
                fcu = drivers.get(propRef(final))
                if fcu:
                    skey.driver_remove("value")
                    fcu2 = skeys.animation_data.drivers.from_existing(src_driver=fcu)
                    fcu2.data_path = 'key_blocks["%s"].value' % prop
                    self.rig.driver_remove(propRef(prop))
                    if prop in self.rig.keys():
                        del self.rig[prop]
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
        if inheritsScale(pb) and pb.parent:
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
        trg.id = self.rig
        trg.bone_target = pb.parent.name
        trg.transform_type = 'SCALE_%s' % chr(ord('X')+idx)
        trg.transform_space = 'LOCAL_SPACE'


    def correctScaleParents(self):
        from .driver import getDriver, removeModifiers
        for pb in self.rig.pose.bones:
            if inheritsScale(pb) and pb.parent:
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
        adj = None
        pb = None
        bname = prefix[:-6]
        if (bname in self.rig.pose.bones.keys()
            # and prefix[-6:-1] in [":Loc:", ":Hdo:", ":Tlo:"]
            ):
            adj = self.getStrengthAdjuster()
            pb = self.rig.pose.bones[bname]
        for final,factor in drivers.items():
            if factor == 0.0:
                continue
            string += "%+.4g*%s" % (factor, varname)
            nterms += 1
            vars.append((varname, final))
            varname = nextLetter(varname)
            if (nterms > MAX_TERMS or
                len(string) > MAX_EXPR_LEN):
                string = self.adjustStrength(adj, pb, string, vars)
                batches.append((string, vars))
                string = ""
                nterms = 0
                varname = "a"
                vars = []
        if vars:
            string = self.adjustStrength(adj, pb, string, vars)
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
            path,idtype = data
            if idtype == 'OBJECT':
                rna = self.rig
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
    def buildChannel(exprs, pb, channel):
        lm = LoadMorph()
        lm.initRig(rig)
        for idx,expr in exprs.items():
            driver = expr["bone"]
            if driver:
                factor = expr["factor"]
                path = expr["path"]
                comp = expr["comp"]
            elif expr["mults"]:
                driver,path,comp = expr["mults"][0]
                factor = 1.0
            else:
                continue
            unit = getUnit(path, rig)
            if driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pb:
                    if channel == "scale":
                        pbDriver.bone.inherit_scale = pb.bone.inherit_scale = 'FULL'
                    elif GS.verbosity >= 3:
                        print("Dependency loop: %s %s" % (pbDriver.name, pb.name))
                    continue
                if factor:
                    tvec,idx2 = getTransformVector(factor, channel, comp, pbDriver, pb, idx)
                    lm.makeSimpleBoneDriver(path, tvec, pb, channel, idx2, driver, False)


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
            if idx < 0:
                pass
            elif not expr["bone"] and expr["mults"]:
                driver,path,comp = expr["mults"][0]
                if not (driver in parents and path == "scale" and comp == idx):
                    return False
            else:
                return False
        return True


    def getTransformVector(factor, channel, comp, pbDriver, pb, idx):
        if (not GS.useDazOrientation or
            pb.rotation_mode == 'QUATERNION'):
            uvec = getBoneVector(factor, comp, pbDriver)
            dvec = getBoneVector(1.0, idx, pb)
            idx2,sign,x = getDrivenComp(dvec)
            if channel == "scale":
                tvec = Vector([abs(y) for y in uvec])
            else:
                tvec = sign*uvec
        else:
            tvec = Vector((0,0,0))
            idx2,sign = d2bBone(pb, channel, idx)
            tvec[idx2] = factor*sign
        return tvec, idx2


    def buildValueDriver(exprs, raw):
        lm = LoadMorph()
        lm.initRig(rig)
        for idx,expr in exprs.items():
            bname = expr["bone"]
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

    def correctExprs(exprs, factor):
        for idx,expr in exprs.items():
            expr["factor"] *= factor

    exprs = asset.evalFormulas(rig, None, True)
    for driven,expr in exprs.items():
        if "rotation" in expr.keys():
            if driven in rig.pose.bones.keys():
                pb = rig.pose.bones[driven]
                buildChannel(expr["rotation"], pb, "rotation_euler")
        if "translation" in expr.keys():
            if driven in rig.pose.bones.keys():
                pb = rig.pose.bones[driven]
                buildChannel(expr["translation"], pb, "location")
        if "scale" in expr.keys() and not GS.useInheritScale:
            if driven in rig.pose.bones.keys():
                pb = rig.pose.bones[driven]
                if canOptimizeScale(expr["scale"], pb, rig):
                    pb.bone.inherit_scale = 'FULL'
                else:
                    buildChannel(expr["scale"], pb, "scale")

        if "value" in expr.keys():
            formulas = expr["value"]
            if driven in altmorphs.keys():
                for alt,factor in altmorphs[driven].items():
                    if factor != 1:
                        correctExprs(formulas, factor)
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
    idx2 = pb.DazAxes[idx]
    return idx2, (1 if channel == "scale" else pb.DazFlips[idx2])


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


def getCanonicalFilePath(filepath):
    filepath = normalizePath(filepath).lower()
    words = filepath.rsplit("/data/",1)
    if len(words) == 2:
        return "/data/%s" % words[1]
    elif filepath[1:3] == ":/":
        return filepath
    else:
        return None


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

def getUnit(path, rig):
    if path == "translation":
        return 1/rig.DazScale
    elif path == "rotation":
        return 1/D
    else:
        return 1
