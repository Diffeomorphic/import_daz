# Copyright (c) 2016-2024, Thomas Larsson
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
import numpy as np
from collections import OrderedDict

from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from .error import *
from .utils import *
from .load_json import JL
from .selector import Selector
from .fileutils import SingleFile, MultiFile, DazFile, JsonFile, ensureExt
from .propgroups import DazTextGroup, DazFloatGroup, DazStringGroup, DazMorphInfoGroup, DazBulgeGroup
from .load_morph import LoadMorph
from .driver import isProtected
from .uilist import updateScrollbars

#-------------------------------------------------------------
#   Morph sets
#-------------------------------------------------------------

class MorphSets:
    def __init__(self):
        self.Standards = ["Standard", "Units", "Expressions", "Visemes", "Head", "Facs", "Facsdetails", "Facsexpr", "Body"]
        self.Customs = ["Custom", "Baked"]
        self.JCMs = ["Jcms", "Masculine", "Feminine", "Flexions"]
        self.Morphsets = self.Standards + self.Customs + self.JCMs + ["Visibility"]

        self.Adjusters = {
            "Standard" : "Adjust Standard",
            "Custom" : "Adjust Custom",
            "Baked" : "Adjust Baked",
            "Units" : "Adjust Units",
            "Expressions" : "Adjust Expressions",
            "Head" : "Adjust Head",
            "Visemes" : "Adjust Visemes",
            "Facs" : "Adjust FACS",
            "Facsdetails" : "Adjust FACS Details",
            "Facsexpr" : "Adjust FACS Expressions",
            "Body" : "Adjust Body Morphs",
            "Head" : "Adjust Head Morphs",
            "Jcms" : "Adjust JCMs",
            "Masculine" : "Adjust JCMs",
            "Feminine" : "Adjust JCMs",
            "Flexions" : "Adjust Flexions",
        }


MS = MorphSets()

def getMorphs0(ob, morphset, sets, category):
    if morphset == "All":
        return getMorphs0(ob, sets, None, category)
    elif isinstance(morphset, list):
        pgs = []
        for mset in morphset:
            pgs += getMorphs0(ob, mset, sets, category)
        return pgs
    elif sets is None or morphset in sets:
        if morphset == "Custom":
            if category:
                if isinstance(category, list):
                    cats = category
                elif isinstance(category, str):
                    cats = [category]
                else:
                    raise DazError("Category must be a string or list but got '%s'" % category)
                pgs = [cat.morphs for cat in ob.DazMorphCats if cat.name in cats]
            else:
                pgs = [cat.morphs for cat in ob.DazMorphCats]
            return pgs
        else:
            pg = getattr(ob, "Daz"+morphset)
            prunePropGroup(ob, pg, morphset)
            return [pg]
    else:
        raise DazError("BUG get_morphs: %s %s" % (morphset, sets))


def prunePropGroup(ob, pg, morphset):
    if morphset in MS.JCMs:
        return
    idxs = [n for n,item in enumerate(pg.values()) if item.name not in ob.keys()]
    if idxs:
        print("Prune", idxs, [item.name for item in pg.values()])
        idxs.reverse()
        for idx in idxs:
            pg.remove(idx)


def clearAllMorphs(rig, frame, useInsertKeys):
    def getAllLowerMorphNames(rig):
        props = []
        for cat in rig.DazMorphCats:
            props += [morph.name.lower() for morph in cat.morphs]
        for morphset in MS.Standards:
            pg = getattr(rig, "Daz"+morphset)
            props += [prop.lower() for prop in pg.keys()]
        return [prop for prop in props if "jcm" not in prop]

    lprops = getAllLowerMorphNames(rig)
    for prop in rig.keys():
        if (prop.lower() in lprops and
            not isProtected(rig, prop)):
            rig[prop] = 0.0
            if useInsertKeys:
                rig.keyframe_insert(propRef(prop), frame=frame, group=prop)


def getMorphList(ob, morphset, sets=None):
    pgs = getMorphs0(ob, morphset, sets, None)
    mlist = []
    for pg in pgs:
        mlist += list(pg.values())
    mlist.sort()
    return mlist


def getMorphsExternal(ob, morphset, category, activeOnly):
    def isActiveKey(key, rig):
        if rig:
            return (key in rig.DazActivated.keys() and
                    rig.DazActivated[key].active)
        else:
            return True

    if not isinstance(ob, bpy.types.Object):
        raise DazError("get_morphs: First argument must be a Blender object, but got '%s'" % ob)
    morphset = morphset.capitalize()
    if morphset == "All":
        morphset = MS.Morphsets
    elif morphset not in MS.Morphsets:
        raise DazError("get_morphs: Morphset must be 'All' or one of %s, not '%s'" % (MS.Morphsets, morphset))
    pgs = getMorphs0(ob, morphset, None, category)
    mdict = {}
    rig = None
    if ob.type == 'ARMATURE':
        if activeOnly:
            rig = ob
        #if morphset in MS.JCMs:
        #    raise DazError("JCM morphs are stored in the mesh object")
        for pg in pgs:
            for key in pg.keys():
                if key in ob.keys() and isActiveKey(key, rig):
                    mdict[key] = ob[key]
    elif ob.type == 'MESH':
        if activeOnly:
            rig = ob.parent
        #if morphset not in MS.JCMs:
        #    raise DazError("Only JCM morphs are stored in the mesh object")
        skeys = ob.data.shape_keys
        if skeys is None:
            return mdict
        for pg in pgs:
            for key in pg.keys():
                if key in skeys.key_blocks.keys() and isActiveKey(key, rig):
                    mdict[key] = skeys.key_blocks[key].value
    return mdict

#------------------------------------------------------------------------
#
#------------------------------------------------------------------------

if bpy.app.version < (2,90,0):
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False)
        index : IntProperty(default=0)

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True)
else:
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False, override={'LIBRARY_OVERRIDABLE'})
        index : IntProperty(default=0)

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True, override={'LIBRARY_OVERRIDABLE'})

#------------------------------------------------------------------
#   Global lists of morph paths
#------------------------------------------------------------------

def copyMorphsets(rig1, rig2):
    def copyMorphset(pg1, pg2):
        if len(pg1) > 0:
            for item1 in pg1:
                if item1.name not in pg2.keys():
                    item2 = pg2.add()
                    item2.name = item1.name
                    item2.text = item1.text

    for morphset in MS.Standards:
        pg1 = getMorphs0(rig1, morphset, None, None)[0]
        pg2 = getMorphs0(rig2, morphset, None, None)[0]
        copyMorphset(pg1, pg2)
    cats1 = rig1.DazMorphCats
    cats2 = rig2.DazMorphCats
    for cat1 in cats1:
        if cat1.name not in cats2.keys():
            cat2 = cats2.add()
            cat2.name = cat1.name
        else:
            cat2 = cats2[cat1.name]
        copyMorphset(cat1.morphs, cat2.morphs)

#------------------------------------------------------------------
#   Global lists of morph paths
#------------------------------------------------------------------

class MorphPaths:
    ShortForms = {
        "phmunits" : ["phmbrow", "phmcheek", "phmeye", "phmjaw", "phmlip", "phmmouth", "phmnos", "phmteeth", "phmtongue"],
        "ctrlunits" : ["ctrlbrow", "ctrlcheek", "ctrleye", "ctrljaw", "ctrllip", "ctrlmouth", "ctrlnos", "ctrlteeth", "ctrltongue"],
        "ectrlunits" : ["ectrlbrow", "ectrlcheek", "ectrleye", "ectrljaw", "ectrllip", "ectrlmouth", "ectrlnos", "ectrlteeth", "ectrltongue"],
        "ctrlbody" : ["ctrlarm", "ctrlbreast", "ctrlhip", "ctrlleg", "ctrlneck", "ctrlshld", "ctrlshould", "ctrltoe", "ctrlwaist",
                      "ctrllarm", "ctrllbreast", "ctrllfing", "ctrllfoot", "ctrllhand", "ctrllleg", "ctrllthumb", "ctrllindex", "ctrllmid", "ctrllring", "ctrllpinky", "ctrlltoe", "ctrllbigtoe",
                      "ctrlrarm", "ctrlrbreast", "ctrlrfing", "ctrlrfoot", "ctrlrhand", "ctrlrleg", "ctrlrthumb", "ctrlrindex", "ctrlrmid", "ctrlrring", "ctrlrpinky", "ctrlrtoe", "ctrlrbigtoe",
                      ],
    }

    def __init__(self):
        self.morphFiles = {}
        self.morphNames = {}
        self.ShortForms["units"] = self.ShortForms["ctrlunits"] + self.ShortForms["ectrlunits"] + self.ShortForms["phmunits"]


    def getMorphPaths(self, char):
        self.setupMorphPaths(False)
        morphpaths = {}
        if char in self.morphFiles.keys():
            for morphset,pgs in self.morphFiles[char].items():
                morphpaths[morphset] = pgs.values()
        return morphpaths


    def setupMorphPaths(self, force):
        def getShortformList(item):
            if isinstance(item, list):
                return item
            else:
                return self.ShortForms[item]

        if self.morphFiles and not force:
            return
        self.morphFiles = {}
        self.morphNames = {}
        self.projectionFiles = {}
        self.projection = {}
        self.projectionFactor = {}

        folder = os.path.join(os.path.dirname(__file__), "data/paths/")
        charPaths = {}
        files = list(os.listdir(folder))
        files.sort()
        for file in files:
            path = os.path.join(folder, file)
            struct = JL.load(path)
            charPaths[struct["name"]] = struct

        for char in charPaths.keys():
            charFiles = self.morphFiles[char] = {}
            typeNames = self.morphNames[char] = {}

            for key,struct in charPaths[char].items():
                if key in ["name", "hd-morphs"]:
                    continue
                elif key == "projection":
                    self.projectionFiles[char] = struct
                    continue
                elif key == "factor":
                    self.projectionFactor[char] = struct
                    continue
                type = key.capitalize()
                if type not in charFiles.keys():
                    charFiles[type] = OrderedDict()
                typeFiles = charFiles[type]
                if type not in typeNames.keys():
                    typeNames[type] = OrderedDict()

                if isinstance(struct["prefix"], list):
                    prefixes = struct["prefix"]
                else:
                    prefixes = [struct["prefix"]]
                if "strip" in struct.keys():
                    strips = struct["strip"]
                else:
                    strips = prefixes
                folder = struct["path"]
                includes = getShortformList(struct["include"])
                excludes = getShortformList(struct["exclude"])
                if "exclude2" in struct.keys():
                    excludes = excludes + getShortformList(struct["exclude2"])
                if "exclude3" in struct.keys():
                    excludes = excludes + getShortformList(struct["exclude3"])

                for abspath in GS.getAbsPaths(folder):
                    files = list(os.listdir(abspath))
                    files.sort()
                    for file in files:
                        fname,ext = os.path.splitext(file)
                        if ext not in [".duf", ".dsf"]:
                            continue
                        isright,name = self.isRightType(fname, prefixes, strips, includes, excludes)
                        key = fname.lower()
                        if isright and key not in typeNames.keys():
                            typeFiles[name] = canonicalPath("%s/%s" % (abspath, file))
                            typeNames[key] = name


    def isRightType(self, fname, prefixes, strips, includes, excludes):
        string = fname.lower()
        ok = False
        for prefix in prefixes:
            n = len(prefix)
            if string[0:n] == prefix:
                ok = True
                if prefix in strips:
                    name = fname[n:]
                else:
                    name = fname
                break
        if not ok:
            return False, fname

        if includes == []:
            for exclude in excludes:
                if exclude in string:
                    return False, name
            return True, name

        for include in includes:
            if (include in string or
                string[0:len(include)-1] == include[1:]):
                for exclude in excludes:
                    if (exclude in string or
                        string[0:len(exclude)-1] == exclude[1:]):
                        return False, name
                return True, name
        return False, name


    def getAllMorphFiles(self, chars, morphset, strict=False):
        files = {}
        for char in chars:
            if (char in self.morphFiles.keys() and
                morphset in self.morphFiles[char].keys()):
                files[char] = self.morphFiles[char][morphset]
        if files:
            return files,""
        msg = ("Characters %s does not support feature %s" % (chars, morphset))
        if strict:
            raise DazError(msg)
        return files,msg


    def getProjection(self, ob):
        from .finger import getCharacter
        char = getCharacter(ob)
        if not char:
            return None
        self.setupMorphPaths(False)
        relpath = self.projectionFiles.get(char)
        if not relpath:
            return None
        if char not in self.projection.keys():
            filepath = GS.getAbsPath(relpath)
            if not filepath:
                return None
            struct = JL.load(filepath)
            proj = None
            if struct:
                deltas = struct["modifier_library"][0]["morph"]["deltas"]["values"]
                scale = self.projectionFactor.get(char, 1.0) * ob.DazScale
                proj = np.zeros((len(ob.data.vertices), 3), float)
                vnums = np.array([delta[0] for delta in deltas])
                offsets = np.array([scale * d2bu(delta[1:]) for delta in deltas])
                proj[vnums] = offsets
                if not ES.easy:
                    print("Projection file %s loaded" % relpath)
            self.projection[char] = proj
        return self.projection[char]


MP = MorphPaths()

#------------------------------------------------------------------
#
#------------------------------------------------------------------

class DAZ_OT_Update(DazOperator):
    bl_idname = "daz.update_morph_paths"
    bl_label = "Update Morph Paths"
    bl_description = "Update paths to predefined morphs"
    bl_options = {'UNDO'}

    def run(self, context):
        MP.setupMorphPaths(True)


class DAZ_OT_SelectAllMorphs(DazOperator):
    bl_idname = "daz.select_all_morphs"
    bl_label = "Select All"
    bl_description = "Select/Deselect all morphs in this section"
    bl_options = {'UNDO'}

    type : StringProperty()
    value : BoolProperty()

    def run(self, context):
        scn = context.scene
        names = MP.morphNames[self.morphset]
        for name in names.values():
            scn["Daz%s" % name] = self.value

#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class MorphSuffix:
    onMorphSuffix : EnumProperty(
        items = [('NONE', "None", "Don't add morph suffixes"),
                 ('SMART', "Smart", "Add suffixes to duplicate meshes,\ni.e. if the rig has several meshes with the same topology"),
                 ('GEOGRAFT', "Geografts", "Add suffixes to geograft morphs based on the geograft name"),
                 ('ALL', "All", "Add custom morph suffixes to all morphs")],
        name = "Use Suffix",
        description = "Add morph suffixes",
        default = 'SMART')

    morphSuffix : StringProperty(
        name = "Suffix",
        description = "Morph suffix",
        default = "")

    def draw(self, context):
        self.layout.prop(self, "onMorphSuffix")
        if self.onMorphSuffix == 'ALL':
            self.layout.prop(self, "morphSuffix")


    def setupUniqueSuffix(self):
        if self.onMorphSuffix == 'NONE' or self.mesh is None:
            self.uniqueSuffix = ""
        elif self.onMorphSuffix == 'SMART':
            if self.mesh in self.duplicates:
                self.uniqueSuffix = ":%s" % self.mesh.name
            else:
                self.uniqueSuffix = ""
        elif self.onMorphSuffix == 'GEOGRAFT' and self.mesh.data.DazGraftGroup:
            self.uniqueSuffix = ":%s" % self.mesh.name
        elif self.onMorphSuffix == 'ALL':
            self.uniqueSuffix = ":%s" % self.morphSuffix
        else:
            self.uniqueSuffix = ""


    def getUniqueName(self, string):
        if self.uniqueSuffix:
            if string.endswith(self.uniqueSuffix):
                return string
            else:
                string = "%s%s" % (string, self.uniqueSuffix)
                return string[:57]      # 64-character limit
        else:
            return string


class PosableMaker:
    caller = None

    useMakePosable : BoolProperty(
        name = "Make All Bones Posable",
        description = "Make all bones posable after the morphs have been loaded",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useMakePosable")

    def makePosable(self, context, rig, useActivate=True, useEasy=False):
        if (self.useMakePosable and
            (useEasy or not ES.easy) and
            rig and
            rig.type == 'ARMATURE' and
            (not useActivate or activateObject(context, rig))):
            print("Make all bones posable")
            bpy.ops.daz.make_all_bones_posable(errorOnFail=False)


class MorphLoader(LoadMorph, PosableMaker):
    category = ""
    adjuster = None
    bodypart = "Face"

    useAdjusters : BoolProperty(
        name = "Use Adjusters",
        description = ("Add an adjuster for the morph type.\n" +
                       "Dependence on FBM and FHM morphs is ignored.\n" +
                       "Useful if the character is baked"),
        default = False)

    useTransferFace : BoolProperty(
        name = "Transfer To Face Meshes",
        description = "Automatically transfer shapekeys to face meshes\nlike eyelashes, tears, brows and beards",
        default = True)

    def __init__(self, useMakePosable=None):
        LoadMorph.__init__(self)
        if useMakePosable is not None:
            self.useMakePosable = useMakePosable

    def draw(self, context):
        LoadMorph.draw(self, context)
        PosableMaker.draw(self, context)


    def getFingeredRigMeshes(self, context):
        from .finger import getFingeredCharacters, getCharacter
        ob = context.object
        self.rig, self.meshes, self.chars, self.modded = getFingeredCharacters(ob, GS.useModifiedMesh, useGenesis=False)
        if ob.type == 'MESH':
            self.meshes = [ob]
            self.chars = [getCharacter(ob)]
        elif self.rig and not self.meshes:
            self.meshes = getMeshChildren(self.rig)
            self.chars = len(self.meshes)*[None]

    def getMorphSet(self, asset):
        return self.morphset

    def getAdjustProp(self):
        return self.adjuster

    def findPropGroup(self, prop):
        return None

    def addUrl(self, asset, aliases, filepath):
        if self.mesh:
            pgs = self.mesh.DazMorphUrls
        elif self.rig:
            pgs = self.rig.DazMorphUrls
        else:
            return
        if filepath not in pgs.keys():
            item = addItem(pgs)
            item.name = filepath
            item.morphset = self.getMorphSet(asset)
            if asset.name in aliases.keys():
                item.text = aliases[asset.name]
            else:
                item.text = asset.name
            item.category = self.category
            item.bodypart = self.bodypart


    def getAllMorphs(self, namepaths, context):
        self.char = None
        if self.meshes:
            ob = self.mesh = self.meshes[0]
            if self.chars:
                self.char = self.chars[0]
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        self.setupDuplicates()
        LS.forMorphLoad(ob)
        if not self.usePropDrivers:
            self.rig = None
        self.errors = {}
        t1 = perf_counter()
        if namepaths:
            path = namepaths[0][0]
            folder = os.path.dirname(path)
        else:
            reportError('No morphs selected for "%s"' % ob.name)
            return
        self.loadAllMorphs(namepaths)
        return self.finishLoading(namepaths, context, t1)


    def loadToMesh(self, mesh, char):
        mesh0 = self.mesh
        char0 = self.char
        morphset0 = self.morphset
        self.mesh = mesh
        self.char = char
        namepaths = []
        namepaths = self.getActiveMorphFiles()
        print("Load %s to %s (%d morphs)" % (self.morphset, self.mesh.name, len(namepaths)))
        if namepaths:
            LS.forMorphLoad(self.mesh)
            self.loadAllMorphs(namepaths)
        self.mesh = mesh0
        self.char = char0
        self.morphset = morphset0
        return namepaths


    def setupDuplicates(self):
        self.duplicates = []
        if self.rig is None:
            return
        from .finger import getFingerPrint
        fingers = {}
        for ob in getMeshChildren(self.rig):
            key = getFingerPrint(ob)
            if key not in fingers.keys():
                fingers[key] = []
            fingers[key].append(ob)
        for key,meshes in fingers.items():
            if len(meshes) > 1:
                self.duplicates += meshes


    def finishLoading(self, namepaths, context, t1):
        if not namepaths:
            return
        t2 = perf_counter()
        folder = os.path.dirname(namepaths[0][0])
        if not ES.easy:
            print("Folder %s loaded in %.3f seconds" % (folder, t2-t1))
        msg = ""
        if LS.targetCharacter:
            msg = "Morphs made for %s.\n" % LS.targetCharacter
        if self.bakedSkipped:
            msg += "\nThe following morphs were not imported because baked in the dbz.\nThey have to be zero in DAZ Studio when exporting,\nor turn on Baked Morphs in the global settings:\n  "
            msg += ", ".join(list(self.bakedSkipped.values()))
        if self.errors and GS.verbosity >= 3:
            msg += "\nMorphs loaded with errors."
            for err,props in self.errors.items():
                msg += "\n%s:    \n" % err
                for prop in props:
                    msg += "    %s\n" % prop
        elif self.erc and GS.verbosity >= 3:
            msg += "\nFound morphs that want to\nchange the rest pose."
        self.makePosable(context, self.rig)
        if self.faceshapes and self.useTransferFace and self.rig and self.meshes:
            self.transferToFaceMeshes(context)
        if msg:
            if msg[0] == "\n":
                msg = msg[1:]
            print(msg)
        return msg


    def addToMorphSet(self, prop, asset, hidden, protected):
        from .modifier import getCanonicalKey
        pgs = self.findPropGroup(prop)
        if pgs is None:
            return
        if prop in pgs.keys():
            item = pgs[prop]
            old = True
        else:
            item = addItem(pgs)
            item.name = prop
            old = False
        if asset:
            if asset.label:
                label = asset.label
            elif old:
                label = item.text
            elif asset.name:
                label = asset.name
            else:
                label = getCanonicalKey(prop)
            visible = asset.visible
        else:
            label = getCanonicalKey(prop)
            visible = True
        n = len(self.category)
        if self.hideable and (hidden or not visible) and not protected:
            item.text = "[%s]" % label
        else:
            item.text = label
        return prop


    def findIked(self):
        self.iked = []
        if self.rig and self.rig.DazSimpleIK:
            for pb in self.rig.pose.bones:
                cns = getConstraint(pb, 'IK')
                if cns:
                    par = pb
                    for n in range(cns.chain_count):
                        if par is None:
                            break
                        self.iked.append(par)
                        par = par.parent


    def transferToFaceMeshes(self, context):
        from .main import getFaceMeshes
        ob = self.meshes[0]
        meshes = getFaceMeshes(self.rig, ob)
        transferShapesToMeshes(context, ob, meshes, self.faceshapes.keys())


def transferShapesToMeshes(context, ob, meshes, snames,
                           useDrivers=True,
                           useOverwrite=True,
                           useSelectedOnly=False):
    if not snames:
        return
    activateObject(context, ob)
    for mesh in meshes:
        selectSet(mesh, True)
    theFilePaths = LS.filepaths
    LS.filepaths = snames
    try:
        bpy.ops.daz.transfer_shapekeys(
            useDrivers=useDrivers,
            useOverwrite=useOverwrite,
            useSelectedOnly=useSelectedOnly,
            needsTarget=False)
    except DazError:
        pass
    finally:
        LS.filepaths = theFilePaths

#------------------------------------------------------------------
#
#------------------------------------------------------------------

class BakedMorphLoader(MorphLoader):
    useAdjusters = False
    useMakePosable = False
    useTransferFace = False
    morphset = "Baked"

    def getFingeredRigMeshes(self, context):
        self.chars = []
        self.modded = []

    def finishLoading(self, namepaths, context, t1):
        pass


#------------------------------------------------------------------
#   Load standard morphs
#------------------------------------------------------------------

class StandardMorphLoader(MorphSuffix, MorphLoader):
    suppressError = True
    ignoreHD = False
    hideable = True
    disableErc = True

    def drawOptions(self, layout):
        layout.prop(self, "useMakePosable")
        if self.bodypart == "Face":
            layout.prop(self, "useTransferFace")
        layout.prop(self, "useAdjusters")
        layout.prop(self, "onMorphSuffix")
        if self.onMorphSuffix == 'ALL':
            layout.prop(self, "morphSuffix")
        else:
            layout.label(text="")

    def setupCharacter(self, context):
        self.getFingeredRigMeshes(context)
        ob = context.object
        msg = ""
        if not self.meshes:
            msg = ('No mesh associated with "%s"' % context.object.name)
        elif not self.chars:
            msg = ("Can not add morphs to this mesh:\n %s" % ob.name)
        if msg:
            invokeErrorMessage(msg)
            return False
        return True

    def findPropGroup(self, prop):
        return getattr(self.rig, "Daz%s" % self.morphset)

    def getPaths(self, context):
        return


    def run(self, context):
        if self.rig is None and not self.meshes:
            self.setupCharacter(context)
        MP.setupMorphPaths(False)
        self.morphFiles,msg = MP.getAllMorphFiles(self.chars, self.morphset)
        self.errors = {}
        self.faceshapes = {}
        t1 = perf_counter()
        namepaths = self.loadStandardMorphs()
        msg = self.finishLoading(namepaths, context, t1)
        if msg:
            raise DazError(msg, warning=True)


    def loadStandardMorphs(self):
        if self.rig:
            self.findIked()
        self.adjuster = MS.Adjusters[self.morphset]
        morphset = self.morphset
        namepaths = self.loadToMesh(self.meshes[0], self.chars[0])
        faceshapes = self.faceshapes
        for mesh, char in zip(self.meshes[1:], self.chars[1:]):
            self.morphset = morphset
            self.loadToMesh(mesh, char)
        self.faceshapes = faceshapes
        return namepaths


    def getActiveMorphFiles(self):
        namepaths = []
        morphFiles = self.morphFiles.get(self.char)
        if morphFiles is None:
            return []
        elif LS.filepaths:
            for path in LS.filepaths:
                text = os.path.splitext(os.path.basename(path))[0]
                namepaths.append((text, path, self.bodypart))
        else:
            for item in self.getSelectedItems():
                key = item.name
                path = morphFiles.get(key)
                if path:
                    namepaths.append((item.text, path, self.bodypart))
        return namepaths

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class StandardMorphSelector(Selector):
    def draw(self, context):
        Selector.draw(self, context)
        row = self.layout.row()
        self.drawOptions(row)

    def isActive(self, name, scn):
        return True

    def selectCondition(self, item):
        return True

    def invoke(self, context, event):
        scn = context.scene
        self.selection.clear()
        if not self.setupCharacter(context):
            return {'FINISHED'}
        MP.setupMorphPaths(False)
        self.morphFiles,msg = MP.getAllMorphFiles(self.chars, self.morphset)
        if not self.morphFiles:
            invokeErrorMessage(msg)
            return {'CANCELLED'}
        for char,struct in self.morphFiles.items():
            for key,path in struct.items():
                if key not in self.selection.keys():
                    item = self.selection.add()
                    item.name = key
                    item.text = key
                    item.category = self.morphset
                    item.select = True
        return self.invokeDialog(context)


class DAZ_OT_ImportUnits(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_units"
    bl_label = "Import Units"
    bl_description = "Import selected face unit morphs"
    bl_options = {'UNDO'}

    morphset = "Units"
    bodypart = "Face"


class DAZ_OT_ImportExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_expressions"
    bl_label = "Import Expressions"
    bl_description = "Import selected expression morphs"
    bl_options = {'UNDO'}

    morphset = "Expressions"
    bodypart = "Face"


class DAZ_OT_ImportVisemes(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_visemes"
    bl_label = "Import Visemes"
    bl_description = "Import selected visemes morphs"
    bl_options = {'UNDO'}

    morphset = "Visemes"
    bodypart = "Face"


class DAZ_OT_ImportHead(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_head"
    bl_label = "Import Head"
    bl_description = "Import selected head morphs"
    bl_options = {'UNDO'}

    morphset = "Head"
    bodypart = "Face"


class DAZ_OT_ImportFacs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs"
    bl_label = "Import FACS"
    bl_description = "Import selected FACS morphs"
    bl_options = {'UNDO'}

    morphset = "Facs"
    bodypart = "Face"


class DAZ_OT_ImportFacsDetails(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs_details"
    bl_label = "Import FACS Details"
    bl_description = "Import selected FACS details morphs"
    bl_options = {'UNDO'}

    morphset = "Facsdetails"
    bodypart = "Face"


class DAZ_OT_ImportFacsExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs_expressions"
    bl_label = "Import FACS Expressions"
    bl_description = "Import selected FACS expression morphs"
    bl_options = {'UNDO'}

    morphset = "Facsexpr"
    bodypart = "Face"


class DAZ_OT_SelectMhxCompatible(bpy.types.Operator):
    bl_idname = "daz.select_mhx_compatible"
    bl_label = "MHX Compatible"
    bl_description = "Select MHX compatible body morphs"

    def execute(self, context):
        from .selector import getSelector
        getSelector().selectMhxCompatible(context)
        return {'PASS_THROUGH'}


class DAZ_OT_ImportBodyMorphs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_body_morphs"
    bl_label = "Import Body Morphs"
    bl_description = "Import selected body morphs"
    bl_options = {'UNDO'}

    morphset = "Body"
    bodypart = "Body"

    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_mhx_compatible")
        row.operator("daz.select_none")

    def selectMhxCompatible(self, context):
        safe,unsafe = getMhxSafe(self.rig)
        for item in self.selection:
            item.select = False
            for string in safe:
                if string in item.text:
                    item.select = True
            for string in unsafe:
                if string in item.text:
                    item.select = False


    def run(self, context):
        StandardMorphLoader.run(self, context)


def getMhxSafe(rig):
    safe = ["Breast", "Hand", "Finger", "Thumb", "Index", "Mid", "Ring", "Pinky"]
    if rig:
        if ("lBigToe" in rig.data.bones.keys() or
            "l_bigtoe1" in rig.data.bones.keys()):
            safe.append("Toe")
            unsafe = ["Foot"]
        else:
            unsafe = ["Toe"]
    else:
        safe = unsafe = []
    return safe,unsafe

#------------------------------------------------------------------------
#   Body morphs
#------------------------------------------------------------------------

class FingerSkip:
    def deselectFingers(self, context):
        for item in self.selection:
            item.select = (not isFingerShape(item.text))

    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.all_but_fingers")
        row.operator("daz.select_none")


def isFingerShape(text):
    text = text.lower()
    for string in ["thumb", "index", "ring", "mid", "pinky", "toe"]:
        if string in text:
            return True



class DAZ_OT_AllButFingers(bpy.types.Operator):
    bl_idname = "daz.all_but_fingers"
    bl_label = "All But Fingers"
    bl_description = "Deselect morphs for fingers and toes"

    def execute(self, context):
        from .selector import getSelector
        getSelector().deselectFingers(context)
        return {'PASS_THROUGH'}


class DAZ_OT_ImportJCMs(DazOperator, FingerSkip, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_jcms"
    bl_label = "Import JCMs"
    bl_description = "Import selected joint corrective morphs"
    bl_options = {'UNDO'}

    morphset = "Jcms"
    bodypart = "Body"
    hideable = False
    isJcm = True


class DAZ_OT_ImportMasculine(DazOperator, FingerSkip, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_masculine"
    bl_label = "Import Masculine"
    bl_description = "Import selected masculine JCMs"
    bl_options = {'UNDO'}

    morphset = "Masculine"
    bodypart = "Body"
    hideable = False
    isJcm = True


class DAZ_OT_ImportFeminine(DazOperator, FingerSkip, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_feminine"
    bl_label = "Import Feminine"
    bl_description = "Import selected import_feminine JCMs"
    bl_options = {'UNDO'}

    morphset = "Feminine"
    bodypart = "Body"
    hideable = False
    isJcm = True


class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    morphset = "Flexions"
    bodypart = "Body"
    hideable = False
    isJcm = True

#------------------------------------------------------------------------
#   Import all standard morphs in one bunch, for performance
#------------------------------------------------------------------------

class DAZ_OT_CreateBulges(DazOperator, FingerSkip, Selector):
    bl_idname = "daz.create_bulges"
    bl_label = "Create Bulges"
    bl_description = "Create bulge morphs.\nOnly for Genesis and Genesis 2 character"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.data.DazBulges) > 0)

    def invoke(self, context, event):
        ob = context.object
        self.selection.clear()
        for vgrp in ob.vertex_groups:
            bname = getBulgeBone(vgrp.name)
            if bname and bname not in self.selection.keys():
                item = self.selection.add()
                item.name = bname
                item.text = bname
                item.select = True
        return self.invokeDialog(context)

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if not rig:
            raise DazError("No armature found")
        createBulges(ob, rig, self.selection)


def getBulgeBone(string):
    words = string.rsplit(":",1)
    if len(words) == 2 and words[-1].startswith(("left_", "right_")):
        return words[0]


def createBulges(ob, rig, selection=None, ignoreFingers=True):
    from .driver import removeModifiers, addTransformVar
    from .dforce import ModStore
    stores = []
    for mod in list(ob.modifiers):
        stores.append(ModStore(mod))
        ob.modifiers.remove(mod)
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basic")

    bulges = []
    vgrps = list(ob.vertex_groups)
    vgrps.reverse()
    for vgrp in vgrps:
        bname = getBulgeBone(vgrp.name)
        if bname:
            if selection:
                item = selection.get(bname)
                if item is None or not item.select:
                    ob.vertex_groups.remove(vgrp)
                    continue
            elif ignoreFingers and isFingerShape(vgrp.name):
                ob.vertex_groups.remove(vgrp)
                continue
            mod = ob.modifiers.new(vgrp.name, 'DISPLACE')
            mod.strength = -2*ob.DazScale
            mod.mid_level = 0
            mod.vertex_group = vgrp.name
            mod.show_viewport = False
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mod.name)
            skey = ob.data.shape_keys.key_blocks[-1]
            skey.slider_min = -5
            skey.slider_max = 5
            bulges.append((vgrp.name, skey))
            ob.vertex_groups.remove(vgrp)

    factor = 0.2/math.pi
    rottypes = ["ROT_X", "ROT_Y", "ROT_Z"]
    for vgname,skey in bulges:
        bname,channel = vgname.rsplit(":",1)
        pb = rig.pose.bones.get(bname)
        if pb is None:
            continue
        lr,comp = channel.split("_")
        pg = ob.data.DazBulges.get("%s_%s" % (bname, comp))
        if pg is None:
            continue
        idx0 = ord(comp) - ord("x")
        idx = pb.DazAxes[idx0]
        flip = pb.DazFlips[idx0]
        if lr == "left":
            pos = -factor*pg["positive_left"]
            neg = factor*pg["negative_left"]
        else:
            pos = -factor*pg["positive_right"]
            neg = factor*pg["negative_right"]
        if flip == -1:
            tmp = pos
            pos = -neg
            neg = -tmp
        fcu = skey.driver_add("value")
        fcu.driver.type = 'SCRIPTED'
        fcu.driver.expression = "%.4f*x if x > 0 else %.4f*x" % (pos, neg)
        addTransformVar(fcu, "x", rottypes[idx], rig, rig, bname)
        removeModifiers(fcu)

    ob.data.DazBulges.clear()
    for store in stores:
        store.restore(ob)

#------------------------------------------------------------------------
#   Import all standard morphs in one bunch, for performance
#------------------------------------------------------------------------

class MorphTypeOptions:
    isMhxAware = True

    useUnits : BoolProperty(
        name = "Face Units",
        description = "Import all face units",
        default = False)

    useExpressions : BoolProperty(
        name = "Expressions",
        description = "Import all expressions",
        default = False)

    useVisemes : BoolProperty(
        name = "Visemes",
        description = "Import all visemes",
        default = False)

    ignoreHdMorphs : BoolProperty(
        name = "Ignore HD Morphs",
        description = "Don't import HD morphs for units, expressions, visemes",
        default = False)

    useHead : BoolProperty(
        name = "Head",
        description = "Import all head morphs",
        default = False)

    useFacs : BoolProperty(
        name = "FACS",
        description = "Import all FACS morphs",
        default = False)

    useFacsdetails : BoolProperty(
        name = "FACS Details",
        description = "Import all FACS details",
        default = False)

    useFacsexpr : BoolProperty(
        name = "FACS Expressions",
        description = "Import all FACS expressions",
        default = False)

    useBody : BoolProperty(
        name = "Body",
        description = "Import all body morphs",
        default = False)

    useMhxOnly : BoolProperty(
        name = "MHX Compatible Only",
        description = "Only import MHX compatible body morphs",
        default = False)

    useJcms : BoolProperty(
        name = "JCMs",
        description = "Import all JCMs",
        default = False)

    useMasculine : BoolProperty(
        name = "Masculine",
        description = "Import all maskuline JCMs",
        default = False)

    useFeminine : BoolProperty(
        name = "Feminine",
        description = "Import all feminine JCMs",
        default = False)

    useFlexions : BoolProperty(
        name = "Flexions",
        description = "Import all flexions",
        default = False)

    useBulges : BoolProperty(
        name = "Bulges",
        description = "Make all bulges (Genesis and Genesis 2)",
        default = False)

    ignoreFingers : BoolProperty(
        name = "Ignore Finger Morphs",
        description = "Don't create morphs for fingers and toes",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useUnits")
        self.layout.prop(self, "useExpressions")
        self.layout.prop(self, "useVisemes")
        if self.useUnits or self.useExpressions or self.useVisemes:
            self.subprop("ignoreHdMorphs")
        self.layout.prop(self, "useHead")
        self.layout.prop(self, "useFacs")
        self.layout.prop(self, "useFacsdetails")
        self.layout.prop(self, "useFacsexpr")
        self.layout.prop(self, "useBody")
        if self.useBody and self.isMhxAware:
            self.subprop("useMhxOnly")
        self.layout.prop(self, "useBulges")
        self.layout.prop(self, "useJcms")
        if self.useJcms or self.useBulges:
            self.subprop("ignoreFingers")
        self.layout.prop(self, "useMasculine")
        self.layout.prop(self, "useFeminine")
        self.layout.prop(self, "useFlexions")


    def subprop(self, prop):
        split = self.layout.split(factor=0.05)
        split.label(text="")
        split.prop(self, prop)


class DAZ_OT_ImportStandardMorphs(DazPropsOperator, StandardMorphLoader, MorphTypeOptions, IsMeshArmature):
    bl_idname = "daz.import_standard_morphs"
    bl_label = "Import Standard Morphs"
    bl_description = "Import all standard morphs of selected types.\nDoing this once is faster than loading individual types"
    bl_options = {'UNDO', 'PRESET'}

    morphset = "Standard"

    def draw(self, context):
        MorphTypeOptions.draw(self, context)
        MorphSuffix.draw(self, context)
        self.layout.prop(self, "useTransferFace")
        self.layout.prop(self, "useAdjusters")
        PosableMaker.draw(self, context)

    def invoke(self, context, event):
        if not self.setupCharacter(context):
            return {'FINISHED'}
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        ob = context.object
        if not self.setupCharacter(context):
            return
        MP.setupMorphPaths(False)
        self.errors = {}
        self.allfaceshapes = {}
        self.message = None
        self.isJcm = False
        useShapekeys = GS.useShapekeys
        GS.useShapekeys = (not self.ignoreHdMorphs)
        try:
            self.loadMorphType(context, self.useUnits, "Units", "Face", ignoreHdMorphs=self.ignoreHdMorphs)
            self.loadMorphType(context, self.useExpressions, "Expressions", "Face", ignoreHdMorphs=self.ignoreHdMorphs)
            self.loadMorphType(context, self.useVisemes, "Visemes", "Face", ignoreHdMorphs=self.ignoreHdMorphs)
        finally:
            GS.useShapekeys = useShapekeys
        self.loadMorphType(context, self.useHead, "Head", "Face")
        self.loadMorphType(context, self.useFacs, "Facs", "Face")
        self.loadMorphType(context, self.useFacsdetails, "Facsdetails", "Face")
        self.loadMorphType(context, self.useFacsexpr, "Facsexpr", "Face")
        self.loadMorphType(context, self.useBody, "Body", "Body")
        self.isJcm = True
        self.loadMorphType(context, self.useJcms, "Jcms", "Body", ignoreFingers=self.ignoreFingers)
        self.loadMorphType(context, self.useMasculine, "Masculine", "Body")
        self.loadMorphType(context, self.useFeminine, "Feminine", "Body")
        self.loadMorphType(context, self.useFlexions, "Flexions", "Body")
        if self.useBulges:
            if ob.type == 'MESH':
                meshes = [ob]
            elif self.rig:
                meshes = getMeshChildren(self.rig)
            for mesh in meshes:
                if len(mesh.data.DazBulges) > 0 and activateObject(context, mesh):
                    createBulges(mesh, self.rig, ignoreFingers=self.ignoreFingers)
        self.makePosable(context, self.rig)
        self.faceshapes = self.allfaceshapes
        if self.faceshapes and self.useTransferFace and self.rig and self.meshes:
            self.transferToFaceMeshes(context)
        if self.message:
            raise DazError(self.message, warning=True)


    def loadMorphType(self, context, use, morphset, bodypart, ignoreFingers=False, ignoreHdMorphs=False):
        if use:
            t1 = perf_counter()
            self.morphset = morphset
            self.bodypart = bodypart
            self.faceshapes = {}
            self.morphFiles,msg = MP.getAllMorphFiles(self.chars, self.morphset)
            if ignoreFingers:
                for char,struct in list(self.morphFiles.items()):
                    mlist = [data for data in struct.items() if not isFingerShape(data[0])]
                    self.morphFiles[char] = OrderedDict(mlist)
            if ignoreHdMorphs:
                for char,struct in list(self.morphFiles.items()):
                    mlist = [data for data in struct.items() if not data[0].endswith("_div2")]
                    self.morphFiles[char] = OrderedDict(mlist)
            self.loadStandardMorphs()
            for key,value in self.faceshapes.items():
                self.allfaceshapes[key] = value
            t2 = perf_counter()
            print("%s loaded in %.1f seconds" % (morphset, t2-t1))


    def getActiveMorphFiles(self):
        namepaths = []
        morphFiles = self.morphFiles.get(self.char)
        if morphFiles is None:
            return []
        else:
            if self.morphset == "Body" and self.useMhxOnly:
                morphFiles = self.selectMhxMorphs(morphFiles)
            for key,path in morphFiles.items():
                namepaths.append((key, path, self.bodypart))
        return namepaths


    def selectMhxMorphs(self, struct):
        safe,unsafe = getMhxSafe(self.rig)
        nstruct = {}
        for key,path in struct.items():
            for string in unsafe:
                if string in key:
                    continue
            for string in safe:
                if string in key:
                    nstruct[key] = path
        return nstruct


    def addToMorphSet(self, prop, asset, hidden, protected):
        self.hideable = (self.morphset in MS.JCMs)
        StandardMorphLoader.addToMorphSet(self, prop, asset, hidden, protected)

#------------------------------------------------------------------------
#   Custom Morph Loader
#------------------------------------------------------------------------

class CustomMorphLoader(MorphSuffix, MorphLoader):
    morphset = "Custom"
    hideable = True
    category = ""

    def findPropGroup(self, prop):
        if self.rig is None:
            return None
        if self.morphset != "Custom":
            return getattr(self.rig, "Daz%s" % self.morphset)
        cats = self.rig.DazMorphCats
        if self.category not in cats.keys():
            cat = cats.add()
            cat.name = self.category
        else:
            cat = cats[self.category]
        return cat.morphs


    def setCategory(self, cat):
        self.morphset = "Custom"
        self.category = cat
        if self.rig:
            if cat not in self.rig.DazMorphCats.keys():
                pg = self.rig.DazMorphCats.add()
                pg.name = cat
            self.rig.DazCustomMorphs = True

#------------------------------------------------------------------------
#   PropDrivers
#------------------------------------------------------------------------

class PropDrivers:
    hasAdjusters = True

    category : StringProperty(
        name = "Category",
        default = "Shapes")

    usePropDrivers : BoolProperty(
        name = "Rig Property Drivers",
        description = "Drive shapekeys with rig properties",
        default = True)

    useMeshCats : BoolProperty(
        name = "Mesh Categories",
        description = "Mesh categories",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "usePropDrivers")
        if self.usePropDrivers:
            self.layout.prop(self, "category")
            if self.hasAdjusters:
                self.layout.prop(self, "useAdjusters")
        else:
            self.layout.prop(self, "useMeshCats")
            if self.useMeshCats:
                self.layout.prop(self, "category")

    def addPropDrivers(self):
        if self.usePropDrivers and self.rig:
            self.rig.DazCustomMorphs = True
        elif self.useMeshCats and self.shapekeys:
            from .category import addToCategories
            props = self.shapekeys.keys()
            for mesh in self.meshes:
                addToCategories(mesh, props, None, self.category)
                mesh.DazMeshMorphs = True

#------------------------------------------------------------------------
#   Import custom morphs
#------------------------------------------------------------------------

class DAZ_OT_ImportCustomMorphs(DazOperator, PropDrivers, CustomMorphLoader, DazFile, MultiFile, IsMeshArmature):
    bl_idname = "daz.import_custom_morphs"
    bl_label = "Import Custom Morphs"
    bl_description = "Import selected morphs from native DAZ files (*.duf, *.dsf)"
    bl_options = {'UNDO', 'PRESET'}

    bodypart : EnumProperty(
        items = [("Face", "Face", "Face"),
                 ("Body", "Body", "Body"),
                 ("Custom", "Custom", "Custom")],
        name = "Body part",
        description = "Part of character that the morphs affect",
        default = "Custom")

    treatHD : EnumProperty(
        items = [('ERROR', "Error", "Raise error"),
                 ('CREATE', "Create Shapekey", "Create empty shapekeys"),
                 ('ACTIVE', "Active Shapekey", "Drive active shapekey")],
        name = "Treat HD Mismatch",
        description = "How to deal with vertex count mismatch for HD morphs",
        default = 'ERROR'
    )

    useProtected : BoolProperty(
        name = "Protect Morphs",
        description = "Protect rig properties from being accidentally set",
        default = False)

    onlyProperties : BoolProperty(
        name = "Only Properties",
        description = "Only load properties and property drivers",
        default = False)

    useSearchAlias = False
    useMulti = True

    def draw(self, context):
        PropDrivers.draw(self, context)
        MorphSuffix.draw(self, context)
        self.layout.prop(self, "bodypart")
        if self.bodypart == "Face":
            self.layout.prop(self, "useTransferFace")
        self.layout.prop(self, "onlyProperties")
        self.layout.prop(self, "useProtected")
        self.layout.prop(self, "treatHD")
        PosableMaker.draw(self, context)


    def invoke(self, context, event):
        self.getFingeredRigMeshes(context)
        if not self.meshes:
            msg = ('No mesh associated with "%s"' % context.object.name)
            invokeErrorMessage(msg)
            return {'FINISHED'}
        self.setPreferredFolder(self.rig, self.meshes, ["Morphs/"], False)
        return MultiFile.invoke(self, context, event)


    def run(self, context):
        self.findIked()
        self.errors = {}
        self.faceshapes = {}
        t1 = perf_counter()
        if not self.meshes:
            self.getFingeredRigMeshes(context)
        namepaths = self.loadToMesh(self.meshes[0], self.chars[0])
        self.addPropDrivers()
        msg = self.finishLoading(namepaths, context, t1)
        updateScrollbars(context)
        if msg:
            raise DazError(msg, warning=True)


    def getActiveMorphFiles(self):
        from .finger import replaceHomeDir
        char0 = self.chars[0]
        namepaths = []
        folder = ""
        for path in self.getMultiFiles(["duf", "dsf"]):
            name = os.path.splitext(os.path.basename(path))[0]
            namepaths.append((name,path,self.bodypart))
        return namepaths


    def getAdjustProp(self):
        self.setCategory(self.category)
        return "Adjust Custom/%s" % self.category

#-------------------------------------------------------------
#   Save and load morph presets
#-------------------------------------------------------------

class DAZ_OT_SaveFavoMorphs(DazOperator, SingleFile, JsonFile, IsMeshArmature):
    bl_idname = "daz.save_favo_morphs"
    bl_label = "Save Favorite Morphs"
    bl_description = "Save favorite morphs"

    useCompact: BoolProperty(
        name = "Compact View",
        description = "Spread each category on multiple lines.\nUseful for manual editing of json files",
        default = True)

    useRemoveDuplicates : BoolProperty(
        name = "Remove Duplicates",
        description = "Remove morphs from extra categories",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useCompact")
        self.layout.prop(self, "useRemoveDuplicates")


    def run(self, context):
        from .load_json import saveJson
        rig = self.rig = getRigFromContext(context)
        struct = {
            "filetype" : "favo_morphs",
            "root_paths" : list(GS.getDazPaths()),
        }
        self.addMorphUrls(rig, struct)
        for ob in getMeshChildren(rig):
            self.addMorphUrls(ob, struct)
        filepath = ensureExt(self.filepath, ".json")
        saveJson(struct, filepath)


    def addMorphUrls(self, ob, struct):
        if len(ob.DazMorphUrls) == 0:
            return
        else:
            print(ob.name)
        from .finger import getFingerPrint
        url = quote(ob.DazUrl)
        if url not in struct.keys():
            struct[url] = {}
        ostruct = struct[url]
        if ob.type == 'MESH':
            if ob.data.DazFingerPrint:
                ostruct["finger_print"] = ob.data.DazFingerPrint
            else:
                ostruct["finger_print"] = getFingerPrint(ob)
        if "morphs" not in ostruct.keys():
            ostruct["morphs"] = {}
        mstruct = ostruct["morphs"]
        for item in ob.DazMorphUrls:
            if item.morphset == "Custom":
                key = "Custom/%s" % item.category
            else:
                key = item.morphset
            if key not in mstruct.keys():
                mstruct[key] = []
            path = GS.getRelativePath(item.name)
            data = (quote(path), item.text, item.bodypart)
            if data not in mstruct[key]:
                mstruct[key].append(data)

        if self.useRemoveDuplicates:
            def removeDuplicates(datas, taken):
                ndatas = []
                datas.sort()
                datas.reverse()     # alias last
                for data in datas:
                    path,prop,bodypart = data
                    if prop not in taken.keys():
                        ndatas.append(data)
                        taken[prop] = True
                ndatas.reverse()
                return ndatas

            taken = {}
            for key,datas in list(mstruct.items()):
                if not key.startswith("Custom/"):
                    mstruct[key] = removeDuplicates(datas, taken)
            for key,datas in list(mstruct.items()):
                if key.startswith("Custom/"):
                    mstruct[key] = removeDuplicates(datas, taken)

        if not self.useCompact:
            for key,datas in list(mstruct.items()):
                mstruct[key] = [list(data) for data in datas]


class FavoOptions:
    ignoreUrl : BoolProperty(
        name = "Ignore URL",
        description = ("Ignore the mesh URL and only use the fingerprint to identify the mesh.\n" +
                       "Use this to load Genesis 8 morphs to Genesis 8.1 figures and vice versa"),
        default = False)

    ignoreFinger : BoolProperty(
        name = "Ignore Fingerprint",
        description = "Ignore the mesh fingerprint which describes the mesh topology",
        default = False)


class DAZ_OT_LoadFavoMorphs(DazOperator, MorphSuffix, MorphLoader, FavoOptions, SingleFile, JsonFile, IsMeshArmature):
    bl_idname = "daz.load_favo_morphs"
    bl_label = "Load Favorite Morphs"
    bl_description = "Load favorite morphs"
    bl_options = {'UNDO'}

    def draw(self, context):
        MorphSuffix.draw(self, context)
        self.layout.prop(self, "ignoreUrl")
        self.layout.prop(self, "ignoreFinger")
        self.layout.prop(self, "useAdjusters")
        PosableMaker.draw(self, context)

    def invoke(self, context, event):
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        filepath = ensureExt(self.filepath, ".json")
        struct = JL.load(filepath)
        if ("filetype" not in struct.keys() or
            struct["filetype"] != "favo_morphs"):
            raise DazError("This file does not contain favorite morphs")
        self.useTransferFace = False
        rig = self.rig = getRigFromContext(context)
        rig.DazMorphUrls.clear()
        self.loadPreset(rig, rig, struct, context)
        for ob in getMeshChildren(rig):
            if not baseName(ob.name).endswith("_HD"):
                self.loadPreset(ob, rig, struct, context)
        updateScrollbars(context)


    def loadPreset(self, ob, rig, struct, context):
        from .finger import getFingeredCharacters
        if ob.type != 'MESH':
            return
        _,_,self.chars,self.modded = getFingeredCharacters(ob, False, useGenesis=True, verbose=False)
        self.char = None
        if self.chars:
            self.char = self.chars[0]
        self.meshes = [ob]
        self.mesh = ob
        if self.ignoreUrl:
            for ustruct in struct.values():
                if isinstance(ustruct, dict):
                    self.loadSinglePreset(ob, rig, ustruct, context)
        else:
            url = quote(ob.DazUrl).lower()
            lstruct = dict([(key.lower(),value) for key,value in struct.items()])
            if url not in lstruct.keys():
                return
            self.loadSinglePreset(ob, rig, lstruct[url], context)
        self.makePosable(context, rig)


    def loadSinglePreset(self, ob, rig, ustruct, context):
        from .finger import getFingerPrint
        if ("finger_print" in ustruct.keys() and
            (self.ignoreUrl or not self.ignoreFinger)):
            if ob.data.DazFingerPrint:
                finger = ob.data.DazFingerPrint
            else:
                finger = getFingerPrint(ob)
            if finger != ustruct["finger_print"]:
                if not self.ignoreUrl:
                    print("Fingerprint mismatch:\n%s != %s" % (finger, ustruct["finger_print"]))
                return
        useSuffix = self.onMorphSuffix
        self.onMorphSuffix = 'NONE'
        for morphset in MS.Standards:
            self.adjuster = MS.Adjusters[morphset]
            self.loadMorphSet(context, morphset, ustruct, morphset, "", True)
        for morphset in MS.JCMs:
            self.adjuster = MS.Adjusters[morphset]
            self.loadMorphSet(context, morphset, ustruct, morphset, "", False)
        self.onMorphSuffix = useSuffix
        for key in ustruct["morphs"].keys():
            if key[0:7] == "Custom/":
                rig.DazCustomMorphs = True
                self.adjuster = "Adjust %s" % key
                self.loadMorphSet(context, key, ustruct, "Custom", key[7:], True)


    def loadMorphSet(self, context, key, ustruct, morphset, cat, hide):
        if key in ustruct["morphs"].keys():
            infos = ustruct["morphs"][key]
            if not infos:
                return
            self.morphset = morphset
            self.category = cat
            self.hideable = hide
            namepaths = []
            for ref,name,bodypart in infos:
                path = GS.getAbsPath(ref)
                if path:
                    namepaths.append((name, path, bodypart))
            msg = self.getAllMorphs(namepaths, context)


    def findPropGroup(self, prop):
        if self.rig is None:
            return None
        elif self.morphset == "Custom":
            cats = self.rig.DazMorphCats
            if self.category not in cats.keys():
                cat = cats.add()
                cat.name = self.category
            else:
                cat = cats[self.category]
            return cat.morphs
        else:
            return getattr(self.rig, "Daz%s" % self.morphset)

#-------------------------------------------------------------
#   Import baked
#-------------------------------------------------------------

class DAZ_OT_ImportBakedCorrectives(DazPropsOperator, CustomMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_baked_correctives"
    bl_label = "Import Baked Correctives"
    bl_description = "Import all custom correctives for baked morphs"

    defaultMultiplier = 0.0

    useExpressions : BoolProperty(
        name = "Expressions",
        description = "Import eJCM files",
        default = True)

    useFacs : BoolProperty(
        name = "FACS",
        description = "Import FACS files",
        default = True)

    useJcms : BoolProperty(
        name = "JCMs",
        description = "Import pJCM files",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useExpressions")
        self.layout.prop(self, "useFacs")
        self.layout.prop(self, "useJcms")
        MorphSuffix.draw(self, context)

    excluded = [folder.lower() for folder in []]
        #["/data/DAZ 3D/Genesis 9/Base/Morphs/DAZ 3D/Base Proportion"]]

    def run(self, context):
        def match(strings):
            for string in strings:
                if string in lfile:
                    return True
            return False

        self.getFingeredRigMeshes(context)
        used = []
        facepaths = {}
        bodypaths = {}
        for path,pg in self.rig.DazBakedFiles.items():
            folder = os.path.dirname(path)
            lfolder = folder.lower()
            if lfolder in used:
                continue
            used.append(lfolder)
            if lfolder in self.excluded:
                continue
            cat = folder.rsplit("/", 1)[-1]
            absfolder = GS.getAbsPath(folder)
            if not absfolder:
                print("Folder not found: %s" % folder)
                continue
            for file in os.listdir(absfolder):
                lfile = file.lower()
                if os.path.splitext(file)[-1] in [".dsf", ".duf"]:
                    path = "%s/%s" % (absfolder, file)
                    if self.useExpressions and match(["ejcm"]):
                        self.addPath(path, cat, "Face", facepaths)
                    elif self.useFacs and match(["facs"]):
                        self.addPath(path, cat, "Face", facepaths)
                    elif self.useJcms and match(["pjcm", "body_cbs", "ctrlmd_n", "basemasculine_body_cbs", "basefeminine_body_cbs"]):
                        self.addPath(path, cat, "Body", bodypaths)
        self.isJcm = False
        for cat,namepaths in facepaths.items():
            print("Load %s face corrections" % cat)
            self.setCategory(cat)
            self.getAllMorphs(namepaths, context)
        self.isJcm = True
        for cat,namepaths in bodypaths.items():
            print("Load %s body corrections" % cat)
            self.setCategory(cat)
            self.getAllMorphs(namepaths, context)
        updateScrollbars(context)


    def addPath(self, path, cat, bodypart, namepaths):
        if cat not in namepaths.keys():
            namepaths[cat] = []
        text = os.path.splitext(os.path.basename(path))[0]
        namepaths[cat].append((text, path, bodypart))

#-------------------------------------------------------------
#   ScanFinder class
#-------------------------------------------------------------

class ScanFinder:
    useSearchAlias = False

    def setupScanned(self, ob):
        from .fileutils import DF
        name = ob.DazUrl.rsplit("#", 1)[-1]
        struct = DF.loadEntry(name, "scanned", False)
        self.directory = struct.get("directory")
        self.defs = struct.get("definitions", {})
        self.alias = struct.get("alias", {})
        self.formulas = struct.get("formulas", {})
        self.geograft = struct.get("geograft", {})
        self.namepaths = {}
        self.parpaths = {}


    def findMorphs(self, morph, ob):
        formulas = self.formulas.get(morph)
        if formulas:
            for morph1,value1 in formulas.items():
                self.findMorphs1(morph1, ob)
            return True
        else:
            return self.findMorphs1(morph, ob)


    def findMorphs1(self, morph, ob):
        from .fileutils import findPathRecursiveFromObject
        self.found = False
        if self.defs:
            path = self.getDefinedPath(morph)
            self.addNamePath(morph, path, self.namepaths)
            alias = self.alias.get(morph)
            if alias:
                path = self.getDefinedPath(alias)
                self.addNamePath(alias, path, self.namepaths)
                morph = alias
            if self.geograft:
                graftFormulas = self.geograft.get("formulas", {})
                graftDefs = self.geograft.get("definitions", {})
                formulas = graftFormulas.get(morph)
                if formulas:
                    pmorphs = formulas.keys()
                else:
                    pmorphs = [morph]
                for pmorph in pmorphs:
                    path = graftDefs.get(pmorph)
                    self.addNamePath(pmorph, path, self.parpaths)
            exprs = self.formulas.get(morph, {})
            for prop,factor in exprs.items():
                path = self.getDefinedPath(prop)
                self.addNamePath(prop, path, self.namepaths)
        if not self.found:
            morph = unquote(morph)
            path = findPathRecursiveFromObject(morph, ob, ["Morphs/", "Base/Morphs/"])
            if path:
                self.addNamePath(morph, path, self.namepaths)
                return True
            else:
                return False


    def getDefinedPath(self, morph):
        path = self.defs.get(morph)
        if path:
            return path
        elif self.directory:
            path = "%s/%s.dsf" % (self.directory, unquote(morph))
            return path
        return None


    def addNamePath(self, morph, path, namepaths):
        if path:
            path = GS.getAbsPath(path)
            if path:
                morph = unquote(morph)
                self.found = True
                namepaths[morph] = (morph, path, "Custom")


    def getParent(self, ob, url):
        rig = getRigFromMesh(ob)
        for child in rig.children:
            if child.DazUrl == url:
                return child
        return None


    def loadOwnMorphs(self, context, ob):
        if self.namepaths:
            self.mesh = ob
            self.meshes = [ob]
            msg = self.getAllMorphs(list(self.namepaths.values()), context)


    def loadParentMorphs(self, context, ob):
        if self.parpaths:
            parent = self.getParent(ob, self.geograft["url"])
            if parent:
                self.mesh = parent
                self.meshes = [parent]
                msg = self.getAllMorphs(list(self.parpaths.values()), context)

#-------------------------------------------------------------
#   Import DAZ Favorites
#-------------------------------------------------------------

class RigidTransfer:
    useTransferOthers : BoolProperty(
        name = "Transfer To Other Meshes",
        description = "Transfer shapekeys from main mesh to other meshes",
        default = True)

    useNonConforming: BoolProperty(
        name = "Non-conforming Meshes",
        description = "Transfer shapekeys to non-conforming meshes",
        default = False)

    ignoreRigidity : BoolProperty(
        name = "Ignore Rigidity",
        description = "Ignore rigidity groups when auto-transfer morphs.\nMorphs may differ from DAZ Studio",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useTransferOthers")
        if self.useTransferOthers:
            self.layout.prop(self, "useNonConforming")
            self.layout.prop(self, "ignoreRigidity")


class DAZ_OT_ImportDazFavoMorphs(DazPropsOperator, ScanFinder, CustomMorphLoader, RigidTransfer, IsMeshArmature):
    bl_idname = "daz.import_daz_favorites"
    bl_label = "Import DAZ Favorites"
    bl_description = "Import custom morphs marked as favorites in DAZ Studio"

    def draw(self, context):
        MorphSuffix.draw(self, context)
        RigidTransfer.draw(self, context)
        PosableMaker.draw(self, context)

    def run(self, context):
        self.rig = getRigFromContext(context)
        self.setupDuplicates()
        self.missing = []
        if self.rig:
            loaded = []
            for ob in getMeshChildren(self.rig):
                if baseName(ob.name).endswith("_HD"):
                    continue
                skeys = ob.data.shape_keys
                if skeys:
                    oldkeynames = list(skeys.key_blocks.keys())
                else:
                    oldkeynames = ["Basic"]
                if self.addFavoMorphs(ob, context):
                    skeys = ob.data.shape_keys
                    if skeys:
                        keynames = [skey.name for skey in skeys.key_blocks
                                    if skey.name not in oldkeynames]
                        loaded.append((ob, keynames))
            if self.useTransferOthers and len(loaded) == 1:
                src,keynames = loaded[0]
                if activateObject(context, src):
                    for ob in getMeshChildren(self.rig):
                        ob.select_set(True)
                    filepaths = LS.filepaths
                    LS.filepaths = keynames
                    try:
                        bpy.ops.daz.transfer_shapekeys(
                            useNonConforming = self.useNonConforming,
                            ignoreRigidity = self.ignoreRigidity)
                    finally:
                        LS.filepaths = filepaths
            self.makePosable(context, self.rig)
        else:
            for ob in getSelectedMeshes(context):
                if not baseName(ob.name).endswith("_HD"):
                    self.addFavoMorphs(ob, context)
        updateScrollbars(context)
        if self.missing:
            msg = "Favorites not found:\n  %s" % self.missing
            raise DazError(msg, warning=True)



    def addFavoMorphs(self, ob, context):
        if len(ob.data.DazFavorites) > 0:
            self.setupScanned(ob)
            for favo in ob.data.DazFavorites.keys():
                favo = favo.split("/",1)[0]
                morph = normKey(favo)
                if not self.findMorphs(morph, ob):
                    #self.missing.append(favo)
                    self.addNamePath(morph, ob.DazScene, self.namepaths)
            self.setCategory("Favorites %s" % truncString(ob.name, "Mesh"))
            self.loadOwnMorphs(context, ob)
            self.loadParentMorphs(context, ob)
            return True
        return False

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DazActiveGroup,
    DazCategory,

    DAZ_OT_Update,
    DAZ_OT_SelectAllMorphs,
    DAZ_OT_ImportUnits,
    DAZ_OT_ImportExpressions,
    DAZ_OT_ImportVisemes,
    DAZ_OT_ImportHead,
    DAZ_OT_ImportFacs,
    DAZ_OT_ImportFacsDetails,
    DAZ_OT_ImportFacsExpressions,
    DAZ_OT_ImportBodyMorphs,
    DAZ_OT_SelectMhxCompatible,
    DAZ_OT_ImportFlexions,
    DAZ_OT_CreateBulges,
    DAZ_OT_AllButFingers,
    DAZ_OT_ImportStandardMorphs,
    DAZ_OT_ImportCustomMorphs,
    DAZ_OT_ImportJCMs,
    DAZ_OT_ImportMasculine,
    DAZ_OT_ImportFeminine,

    DAZ_OT_SaveFavoMorphs,
    DAZ_OT_LoadFavoMorphs,
    DAZ_OT_ImportBakedCorrectives,
    DAZ_OT_ImportDazFavoMorphs,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazCustomMorphs = BoolProperty(default = False)
    bpy.types.Object.DazMeshMorphs = BoolProperty(default = False)
    bpy.types.Object.DazMorphAuto = BoolProperty(default = False)

    for morphset in MS.Morphsets:
        setattr(bpy.types.Object, "Daz%s" % morphset, CollectionProperty(type = DazTextGroup))
        setattr(bpy.types.Armature, "DazIndex%s" % morphset, IntProperty(default=0))
    bpy.types.Object.DazBakedFiles = CollectionProperty(type = DazFloatGroup)
    bpy.types.Object.DazMorphUrls = CollectionProperty(type = DazMorphInfoGroup)
    bpy.types.Object.DazAutoFollow = CollectionProperty(type = DazTextGroup)
    bpy.types.Object.DazAlias = CollectionProperty(type = DazStringGroup)
    bpy.types.Mesh.DazFavorites = CollectionProperty(type = bpy.types.PropertyGroup)

    if bpy.app.version < (2,90,0):
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup)
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory)
    else:
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Mesh.DazBodyPart = CollectionProperty(type = DazStringGroup)
    bpy.types.Mesh.DazBulges = CollectionProperty(type = DazBulgeGroup)
    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items = [],
        name = "Morph")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name = "New Name",
        default = "Name")

    folder = os.path.expanduser("~/Documents")
    if not os.path.exists(folder):
        folder = os.path.expanduser("~")


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


