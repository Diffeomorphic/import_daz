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
import numpy as np

from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from .error import *
from .utils import *
from .selector import Selector
from .fileutils import SingleFile, MultiFile, DazImageFile, JsonFile, ensureExt
from .propgroups import DazTextGroup, DazFloatGroup, DazStringGroup, DazMorphInfoGroup
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
        self.JCMs = ["Jcms", "Flexions"]
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

        from collections import OrderedDict
        from .load_json import loadJson

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
            struct = loadJson(path)
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

                for dazpath in GS.getDazPaths():
                    folderpath = "%s/%s" % (dazpath, folder)
                    folderpath = bpy.path.resolve_ncase(folderpath)
                    if os.path.exists(folderpath):
                        files = list(os.listdir(folderpath))
                        files.sort()
                        for file in files:
                            fname,ext = os.path.splitext(file)
                            if ext not in [".duf", ".dsf"]:
                                continue
                            isright,name = self.isRightType(fname, prefixes, strips, includes, excludes)
                            key = fname.lower()
                            if isright and key not in typeNames.keys():
                                string = "%s/%s" % (folderpath, file)
                                string = string.replace("//", "/")
                                typeFiles[name] = bpy.path.resolve_ncase(string)
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
        from .load_json import loadJson
        from .files import parseAssetFile
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
            struct = loadJson(filepath)
            proj = None
            if struct:
                deltas = struct["modifier_library"][0]["morph"]["deltas"]["values"]
                scale = self.projectionFactor.get(char, 1.0) * ob.DazScale
                proj = np.zeros((len(ob.data.vertices), 3), float)
                vnums = np.array([delta[0] for delta in deltas])
                offsets = np.array([scale * d2bu(delta[1:]) for delta in deltas])
                proj[vnums] = offsets
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
            scn["Daz"+name] = self.value

#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class MorphSuffix:
    onMorphSuffix : EnumProperty(
        items = [('NONE', "None", "Don't add morph suffixes"),
                 ('GEOGRAFT', "Geografts", "Add suffixes to geograft morphs based on the geograft name"),
                 ('ALL', "All", "Add custom morph suffixes to all morphs")],
        name = "Use Suffix",
        description = "Add morph suffixes",
        default = 'GEOGRAFT')

    morphSuffix : StringProperty(
        name = "Suffix",
        description = "Morph suffix",
        default = "")

    def draw(self, context):
        self.layout.prop(self, "onMorphSuffix")
        if self.onMorphSuffix == 'ALL':
            self.layout.prop(self, "morphSuffix")

    def setupUniqueSuffix(self, path):
        if self.onMorphSuffix == 'NONE' or self.mesh is None:
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


class MorphLoader(LoadMorph):
    category = ""
    adjuster = None
    bodypart = None

    useAdjusters : BoolProperty(
        name = "Use Adjusters",
        description = ("Add an adjuster for the morph type.\n" +
                       "Dependence on FBM and FHM morphs is ignored.\n" +
                       "Useful if the character is baked"),
        default = False)

    useMakePosable : BoolProperty(
        name = "Make All Bones Posable",
        description = "Make all bones posable after the morphs have been loaded",
        default = False)

    useTransferFace : BoolProperty(
        name = "Transfer To Face Meshes",
        description = "Automatically transfer shapekeys to face meshes\nlike eyelashes, tears, brows and beards",
        default = True)

    def getFingeredRigMeshes(self, context):
        from .finger import getFingeredCharacters
        ob = context.object
        self.rig, self.meshes, self.chars, self.modded = getFingeredCharacters(ob, GS.useModifiedMesh)
        if ob.type == 'MESH':
            self.meshes = [ob]
        elif self.rig and not self.meshes:
            self.meshes = getMeshChildren(self.rig)

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
        LS.forMorphLoad(ob)
        if not self.usePropDrivers:
            self.rig = None
        self.errors = {}
        t1 = perf_counter()
        if namepaths:
            path = namepaths[0][0]
            folder = os.path.dirname(path)
        else:
            raise DazError("No morphs selected")
        self.loadAllMorphs(namepaths)
        self.finishLoading(namepaths, context, t1)


    def finishLoading(self, namepaths, context, t1):
        if not namepaths:
            return
        t2 = perf_counter()
        folder = os.path.dirname(namepaths[0][0])
        print("Folder %s loaded in %.3f seconds" % (folder, t2-t1))
        if LS.targetCharacter:
            msg = "Morphs made for %s" % LS.targetCharacter
        elif self.errors and GS.verbosity >= 3:
            msg = "Morphs loaded with errors."
            for err,props in self.errors.items():
                msg += "\n%s:    \n" % err
                for prop in props:
                    msg += "    %s\n" % prop
        elif self.erc and GS.verbosity >= 3:
            msg = "Found morphs that want to\nchange the rest pose"
        else:
            msg = None
        if self.useMakePosable and self.rig and activateObject(context, self.rig):
            print("Make all bones posable")
            bpy.ops.daz.make_all_bones_posable()
        if self.faceshapes and self.useTransferFace and self.rig and self.mesh:
            self.transferToFaceMeshes(context)
        if msg:
            print(msg)
        return msg


    def addToMorphSet(self, prop, asset, hidden, protected):
        from .modifier import getCanonicalKey
        pgs = self.findPropGroup(prop)
        if pgs is None:
            return
        if prop in pgs.keys():
            item = pgs[prop]
        else:
            item = addItem(pgs)
            item.name = prop
        if asset:
            if asset.label:
                label = asset.label
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
        meshes = getFaceMeshes(self.rig, self.mesh)
        if meshes:
            print("Transfer shapekeys to %s" % [mesh.name for mesh in meshes])
            activateObject(context, self.mesh)
            for mesh in meshes:
                selectSet(mesh, True)
            theFilePaths = LS.theFilePaths
            try:
                LS.theFilePaths = self.faceshapes.keys()
                bpy.ops.daz.transfer_shapekeys()
            finally:
                LS.theFilePaths = theFilePaths

#------------------------------------------------------------------
#   Load standard morphs
#------------------------------------------------------------------

class StandardMorphLoader(MorphLoader, MorphSuffix):
    suppressError = True
    ignoreHD = False
    hideable = True
    useMakePosable = False

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
        return getattr(self.rig, "Daz"+self.morphset)

    def getPaths(self, context):
        return


    def run(self, context):
        if self.rig is None and not self.meshes:
            self.setupCharacter(context)
            MP.setupMorphPaths(False)
            self.morphFiles,msg = MP.getAllMorphFiles(self.chars, self.morphset)
        else:
            MP.setupMorphPaths(False)
        self.errors = {}
        self.faceshapes = {}
        self.meshes.reverse()
        t1 = perf_counter()
        namepaths = self.loadStandardMorphs()
        self.finishLoading(namepaths, context, t1)


    def loadStandardMorphs(self):
        if self.rig:
            self.rig.DazMorphPrefixes = False
            self.findIked()
        self.adjuster = MS.Adjusters[self.morphset]
        namepaths = []
        for mesh in self.meshes:
            self.mesh = mesh
            self.char = mesh.DazMesh
            namepaths = self.getActiveMorphFiles()
            print("Load %d morphs to %s" % (len(namepaths), mesh.name))
            LS.forMorphLoad(mesh)
            if namepaths:
                self.loadAllMorphs(namepaths)
        return namepaths


    def isHdOk(self, string):
        return True


    def getActiveMorphFiles(self):
        namepaths = []
        morphFiles = self.morphFiles.get(self.char)
        if morphFiles is None:
            return []
        elif LS.theFilePaths:
            for path in LS.theFilePaths:
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
        return self.isHdOk(item.text)

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
    safe = ["Breast", "Finger", "Thumb", "Index", "Mid", "Ring", "Pinky"]
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


class DAZ_OT_ImportJCMs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_jcms"
    bl_label = "Import JCMs"
    bl_description = "Import selected joint corrective morphs"
    bl_options = {'UNDO'}

    morphset = "Jcms"
    bodypart = "Body"
    hideable = False
    useMuteDrivers = True


class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    morphset = "Flexions"
    bodypart = "Body"
    hideable = False
    useMuteDrivers = True

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

    useFlexions : BoolProperty(
        name = "Flexions",
        description = "Import all flexions",
        default = False)


    def draw(self, context):
        self.layout.prop(self, "useUnits")
        self.layout.prop(self, "useExpressions")
        self.layout.prop(self, "useVisemes")
        self.layout.prop(self, "useHead")
        self.layout.prop(self, "useFacs")
        self.layout.prop(self, "useFacsdetails")
        self.layout.prop(self, "useFacsexpr")
        self.layout.prop(self, "useBody")
        if self.useBody and self.isMhxAware:
            self.subprop("useMhxOnly")
        self.layout.prop(self, "useJcms")
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
        self.layout.prop(self, "useMakePosable")

    def invoke(self, context, event):
        if not self.setupCharacter(context):
            return {'FINISHED'}
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        if not self.setupCharacter(context):
            return
        MP.setupMorphPaths(False)
        self.errors = {}
        self.allfaceshapes = {}
        self.meshes.reverse()
        if self.rig:
            self.rig.DazMorphPrefixes = False
        self.message = None
        self.useMuteDrivers = False
        self.loadMorphType(context, self.useUnits, "Units", "Face")
        self.loadMorphType(context, self.useHead, "Head", "Face")
        self.loadMorphType(context, self.useExpressions, "Expressions", "Face")
        self.loadMorphType(context, self.useVisemes, "Visemes", "Face")
        self.loadMorphType(context, self.useFacs, "Facs", "Face")
        self.loadMorphType(context, self.useFacsdetails, "Facsdetails", "Face")
        self.loadMorphType(context, self.useFacsexpr, "Facsexpr", "Face")
        self.loadMorphType(context, self.useBody, "Body", "Body")
        self.useMuteDrivers = True
        self.loadMorphType(context, self.useJcms, "Jcms", "Body")
        self.loadMorphType(context, self.useFlexions, "Flexions", "Body")
        if self.useMakePosable and self.rig and activateObject(context, self.rig):
            print("Make all bones posable")
            bpy.ops.daz.make_all_bones_posable()
        self.faceshapes = self.allfaceshapes
        if self.faceshapes and self.useTransferFace and self.rig and self.mesh:
            self.transferToFaceMeshes(context)
        if self.message:
            raise DazError(self.message, warning=True)


    def loadMorphType(self, context, use, morphset, bodypart):
        if use:
            self.morphset = morphset
            self.bodypart = bodypart
            self.faceshapes = {}
            print("Load %s" % morphset)
            self.morphFiles,msg = MP.getAllMorphFiles(self.chars, self.morphset)
            self.loadStandardMorphs()
            for key,value in self.faceshapes.items():
                self.allfaceshapes[key] = value


    def getActiveMorphFiles(self):
        namepaths = []
        morphFiles = self.morphFiles.get(self.char)
        if morphFiles is None:
            return []
        else:
            if self.morphset == "Body" and self.useMhxOnly:
                morphFiles = self.selectMhxMorphs(morphFiles)
            for key,path in morphFiles.items():
                if self.isHdOk(key):
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
        self.hideable = (self.morphset in ["Jcms", "Flexions"])
        StandardMorphLoader.addToMorphSet(self, prop, asset, hidden, protected)

#------------------------------------------------------------------------
#   Custom Morph Loader
#------------------------------------------------------------------------

class CustomMorphLoader(MorphLoader, MorphSuffix):
    morphset = "Custom"
    hideable = True
    category = ""
    useMakePosable = False

    def findPropGroup(self, prop):
        if self.rig is None:
            return None
        if self.morphset != "Custom":
            return getattr(self.rig, "Daz"+self.morphset)
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

    useMuteDrivers : BoolProperty(
        name = "Shapekey Mute Drivers",
        description = "Add drivers that mute shapekeys if shapekey value = 0",
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
            self.layout.prop(self, "useMuteDrivers")
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
            addToCategories(self.mesh, props, None, self.category)
            self.mesh.DazMeshMorphs = True

#------------------------------------------------------------------------
#   Import custom morphs
#------------------------------------------------------------------------

class DAZ_OT_ImportCustomMorphs(DazOperator, PropDrivers, CustomMorphLoader, DazImageFile, MultiFile, IsMeshArmature):
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

    def draw(self, context):
        PropDrivers.draw(self, context)
        MorphSuffix.draw(self, context)
        self.layout.prop(self, "bodypart")
        if self.bodypart == "Face":
            self.layout.prop(self, "useTransferFace")
        self.layout.prop(self, "onlyProperties")
        self.layout.prop(self, "useProtected")
        self.layout.prop(self, "treatHD")
        self.layout.prop(self, "useMakePosable")


    def invoke(self, context, event):
        self.getFingeredRigMeshes(context)
        if not self.meshes:
            msg = ('No mesh associated with "%s"' % context.object.name)
            invokeErrorMessage(msg)
            return {'FINISHED'}
        self.setPreferredFolder(self.rig, self.meshes, ["Morphs/"], False)
        return MultiFile.invoke(self, context, event)


    def run(self, context):
        from .finger import replaceHomeDir
        self.findIked()
        self.errors = {}
        t1 = perf_counter()
        if not self.meshes:
            self.getFingeredRigMeshes(context)
        namepaths0 = self.getNamePaths()
        mesh0 = self.meshes[0]
        char0 = mesh0.DazMesh
        meshlist = list(enumerate(self.meshes))
        meshlist.reverse()
        for n,mesh in meshlist:
            self.mesh = mesh
            self.char = mesh.DazMesh
            if n == 0:
                namepaths = namepaths0
            else:
                namepaths = []
                for key,path0,bodypart in namepaths0:
                    path = replaceHomeDir(path0, char0, self.char)
                    if path:
                        namepaths.append((key, path, bodypart))
            print("Load %d morphs to %s" % (len(namepaths), mesh.name))
            LS.forMorphLoad(mesh)
            if namepaths:
                self.loadAllMorphs(namepaths)

        self.addPropDrivers()
        self.finishLoading(namepaths, context, t1)
        updateScrollbars(context)


    def getNamePaths(self):
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

    def invoke(self, context, event):
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        rig = self.rig = getRigFromContext(context)
        struct = { "filetype" : "favo_morphs" }
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
        from urllib.parse import quote
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
            data = (quote(item.name), item.text, item.bodypart)
            if data not in mstruct[key]:
                mstruct[key].append(data)


class FavoOptions:
    ignoreUrl : BoolProperty(
        name = "Ignore URL",
        description = ("Ignore the mesh URL and only use the fingerprint to identify the mesh.\n" +
                       "Use this to load Genesis 8 morphs to Genesis 8.1 figures and vice versa"),
        default = True)

    ignoreFinger : BoolProperty(
        name = "Ignore Fingerprint",
        description = "Ignore the mesh fingerprint which describes the mesh topology",
        default = False)


class DAZ_OT_LoadFavoMorphs(DazOperator, MorphLoader, MorphSuffix, FavoOptions, SingleFile, JsonFile, IsMeshArmature):
    bl_idname = "daz.load_favo_morphs"
    bl_label = "Load Favorite Morphs"
    bl_description = "Load favorite morphs"
    bl_options = {'UNDO'}

    def draw(self, context):
        MorphSuffix.draw(self, context)
        self.layout.prop(self, "ignoreUrl")
        self.layout.prop(self, "ignoreFinger")
        self.layout.prop(self, "useAdjusters")
        self.layout.prop(self, "useMakePosable")

    def invoke(self, context, event):
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from .load_json import loadJson
        filepath = ensureExt(self.filepath, ".json")
        struct = loadJson(filepath)
        if ("filetype" not in struct.keys() or
            struct["filetype"] != "favo_morphs"):
            raise DazError("This file does not contain favorite morphs")
        self.useTransferFace = False
        rig = self.rig = getRigFromContext(context)
        rig.DazMorphUrls.clear()
        self.loadPreset(rig, rig, struct, context)
        for ob in getMeshChildren(rig):
            self.loadPreset(ob, rig, struct, context)
        updateScrollbars(context)


    def loadPreset(self, ob, rig, struct, context):
        from urllib.parse import quote
        from .finger import getFingeredCharacters
        if ob.type != 'MESH':
            return
        _,_,self.chars,self.modded = getFingeredCharacters(ob, False, verbose=False)
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
        if self.useMakePosable and rig and activateObject(context, rig):
            print("Make all bones posable")
            bpy.ops.daz.make_all_bones_posable()


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
            namepaths = [(name, unquote(ref), bodypart) for ref,name,bodypart in infos]
            self.getAllMorphs(namepaths, context)


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
            return getattr(self.rig, "Daz"+self.morphset)

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
        self.namepaths = {}
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
                        self.addPath(path, cat, "Face")
                    elif self.useFacs and match(["facs"]):
                        self.addPath(path, cat, "Face")
                    elif self.useJcms and match(["pjcm", "body_cbs", "ctrlmd_n"]):
                        self.addPath(path, cat, "Body")
        for cat,namepaths in self.namepaths.items():
            print("Load %s corrections" % cat)
            self.setCategory(cat)
            self.getAllMorphs(namepaths, context)
        updateScrollbars(context)


    def addPath(self, path, cat, bodypart):
        if cat not in self.namepaths.keys():
            self.namepaths[cat] = []
        text = os.path.splitext(os.path.basename(path))[0]
        self.namepaths[cat].append((text, path, bodypart))

#-------------------------------------------------------------
#   ScanFinder class
#-------------------------------------------------------------

class ScanFinder:
    useSearchAlias = False

    def setupUniqueSuffix(self, path):
        self.uniqueSuffix = ""


    def setupScanned(self, ob):
        from .fileutils import AF
        name = ob.DazUrl.rsplit("#", 1)[-1]
        struct = AF.loadEntry(name, "scanned", False)
        self.directory = struct.get("directory")
        self.defs = struct.get("definitions", {})
        self.alias = struct.get("alias", {})
        self.formulas = struct.get("formulas", {})
        self.geograft = struct.get("geograft", {})
        self.namepaths = []
        self.parpaths = []


    def findMorphs(self, morph, ob):
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
                path = self.geograft["definitions"].get(morph)
                self.addNamePath(morph, path, self.parpaths)
            exprs = self.formulas.get(morph, {})
            for prop,factor in exprs.items():
                path = self.getDefinedPath(prop)
                self.addNamePath(prop, path, self.namepaths)
        if not self.found:
            morph = unquote(morph)
            path = findPathRecursiveFromObject(morph, ob, ["Morphs/", "Base/Morphs/"])
            self.addNamePath(morph, path, self.namepaths)


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
                self.found = True
                namepaths.append((unquote(morph), path, "Custom"))


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
            self.getAllMorphs(self.namepaths, context)


    def loadParentMorphs(self, context, ob):
        if self.parpaths:
            parent = self.getParent(ob, self.geograft["url"])
            if parent:
                self.mesh = parent
                self.meshes = [parent]
                self.getAllMorphs(self.parpaths, context)

#-------------------------------------------------------------
#   Import DAZ Favorites
#-------------------------------------------------------------

class DAZ_OT_ImportDazFavoMorphs(DazOperator, ScanFinder, CustomMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_daz_favorites"
    bl_label = "Import DAZ Favorites"
    bl_description = "Import custom morphs marked as favorites in DAZ Studio"

    def run(self, context):
        self.rig = getRigFromContext(context)
        if self.rig:
            for ob in getMeshChildren(self.rig):
                self.addFavoMorphs(ob, context)
        else:
            for ob in getSelectedMeshes(context):
                self.addFavoMorphs(ob, context)
        updateScrollbars(context)


    def addFavoMorphs(self, ob, context):
        if len(ob.data.DazFavorites) > 0:
            self.setupScanned(ob)
            for favo in ob.data.DazFavorites.keys():
                morph = favo.split("/",1)[0]
                self.findMorphs(morph, ob)
            self.setCategory("Favorites %s" % ob.name)
            self.loadOwnMorphs(context, ob)
            self.loadParentMorphs(context, ob)

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
    DAZ_OT_ImportFlexions,
    DAZ_OT_ImportStandardMorphs,
    DAZ_OT_ImportCustomMorphs,
    DAZ_OT_ImportJCMs,

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

    bpy.types.Object.DazMorphPrefixes = BoolProperty(default = True)
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
    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items = [],
        name = "Morph")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name = "New Name",
        default = "Name")

    folder = os.path.expanduser("~/Documents")
    if not os.path.exists(folder):
        folder = os.path.expanduser("~")
    bpy.types.Scene.DazMorphPath = StringProperty(
        name = "Morph Path",
        description = "Path to morphs",
        subtype = 'DIR_PATH',
        default = folder.replace("\\","/"))


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


