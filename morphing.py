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
from .fileutils import SingleFile, MultiFile, DazImageFile, DatFile, JsonFile
from .animation import ActionOptions
from .propgroups import DazTextGroup, DazFloatGroup, DazStringGroup, DazMorphInfoGroup
from .load_morph import LoadMorph
from .driver import DriverUser
from .fileutils import DazExporter

#-------------------------------------------------------------
#   Morph sets
#-------------------------------------------------------------

class MorphSets:
    def __init__(self):
        self.Standards = ["Standard", "Units", "Expressions", "Head", "Visemes", "Head", "Facs", "Facsdetails", "Facsexpr", "Body"]
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


def getAllLowerMorphNames(rig):
    props = []
    for cat in rig.DazMorphCats:
        props += [morph.name.lower() for morph in cat.morphs]
    for morphset in MS.Standards:
        pg = getattr(rig, "Daz"+morphset)
        props += [prop.lower() for prop in pg.keys()]
    return [prop for prop in props if "jcm" not in prop]


def clearAllMorphs(rig, frame, useInsertKeys):
    lprops = getAllLowerMorphNames(rig)
    for prop in rig.keys():
        if (prop.lower() in lprops and
            isinstance(rig[prop], float)):
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

#-------------------------------------------------------------
#   Classes
#-------------------------------------------------------------

class MorphGroup:
    morphset : StringProperty(default = "All")
    category : StringProperty(default = "")
    prefix : StringProperty(default = "")
    ftype : StringProperty(default = "")

    def init(self, morphset, category, prefix, ftype):
        self.morphset = morphset
        self.category = category
        self.prefix = prefix
        self.ftype = ftype


    def getFiltered(self):
        from .uilist import theFilterFlags, theFilterInvert
        if self.ftype in theFilterFlags.keys():
            if theFilterInvert[self.ftype]:
                return [(f == 0) for f in theFilterFlags[self.ftype]]
            else:
                return theFilterFlags[self.ftype]
        else:
            return 50*[True]


    def getRelevantMorphs(self, scn, rig, adjusters=False):
        filtered = self.getFiltered()
        morphs = []
        if rig is None:
            return morphs
        if self.morphset == "Custom":
            return self.getCustomMorphs(scn, rig)
        elif rig.DazMorphPrefixes:
            for key in rig.keys():
                if key[0:2] == "Dz":
                    raise DazError("OLD morphs", rig, key)
        elif self.morphset == "All":
            if adjusters:
                adj = "Adjust Morph Strength"
                if adj in rig.keys():
                    morphs.append(adj)
            for mset in MS.Standards:
                pgs = getattr(rig, "Daz%s" % mset)
                morphs += [key for key in pgs.keys()]
            for cat in rig.DazMorphCats:
                morphs += [morph.name for morph in cat.morphs]
        else:
            if adjusters:
                adj = "Adjust %s" % self.morphset
                if adj in rig.keys():
                    morphs.append(adj)
            pgs = getattr(rig, "Daz%s" % self.morphset)
            morphs += [key for key,on in zip(pgs.keys(), filtered) if on]
        return morphs


    def getCustomMorphs(self, scn, ob):
        filtered = self.getFiltered()
        morphs = []
        if self.category:
            for cat in ob.DazMorphCats:
                if cat.name == self.category:
                    morphs = [morph.name for morph,on in zip(cat.morphs, filtered) if on]
                    return morphs
        else:
            for cat in ob.DazMorphCats:
                morphs += [morph.name for morph,on in zip(cat.morphs, filtered) if on]
        return morphs


    def getRelevantShapes(self, ob):
        filtered = self.getFiltered()
        if self.category:
            cats = [ob.DazMorphCats[self.category]]
        else:
            cats = ob.DazMorphCats
        morphs = []
        for cat in cats:
            morphs += [morph for morph,on in zip(cat.morphs, filtered) if on]
        return morphs


class CategoryString:
    category : StringProperty(
        name = "Category",
        description = "Add morphs to this category of custom morphs",
        default = "Shapes"
        )


def getActiveCategories(scn, context):
    ob = context.object
    cats = [(cat.name,cat.name,cat.name) for cat in ob.DazMorphCats]
    cats.sort()
    return [("All", "All", "All")] + cats


class CustomEnums:
    custom : EnumProperty(
        items = getActiveCategories,
        name = "Category")


class DazSelectGroup(bpy.types.PropertyGroup):
    text : StringProperty()
    category : StringProperty()
    index : IntProperty()
    select : BoolProperty()

    def __lt__(self, other):
        return (self.text < other.text)


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

#-------------------------------------------------------------
#   Morph selector
#-------------------------------------------------------------

def getSelector():
    global theSelector
    return theSelector

def setSelector(selector):
    global theSelector
    theSelector = selector


class DAZ_OT_SelectAll(bpy.types.Operator):
    bl_idname = "daz.select_all"
    bl_label = "All"
    bl_description = "Select all"

    def execute(self, context):
        getSelector().selectAll(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectNone(bpy.types.Operator):
    bl_idname = "daz.select_none"
    bl_label = "None"
    bl_description = "Select none"

    def execute(self, context):
        getSelector().selectNone(context)
        return {'PASS_THROUGH'}


class Selector():
    selection : CollectionProperty(type = DazSelectGroup)

    filter : StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
        )

    defaultSelect = False
    columnWidth = 180
    ncols = 6
    nrows = 20
    mincols = 3

    def draw(self, context):
        scn = context.scene
        self.drawSelectionRow()
        self.layout.prop(self, "filter", icon='VIEWZOOM', text="")
        self.drawExtra(context)
        self.layout.separator()
        items = [item for item in self.selection if self.isSelected(item)]
        items.sort()
        nitems = len(items)
        ncols = self.ncols
        nrows = self.nrows
        if nitems > ncols*nrows:
            nrows = nitems//ncols + 1
        else:
            ncols = nitems//nrows + 1
            if ncols < self.mincols:
                ncols = self.mincols
                nrows = (nitems-1)//ncols + 1
        cols = []
        for n in range(ncols):
            cols.append(items[0:nrows])
            items = items[nrows:]
        for m in range(nrows):
            row = self.layout.row()
            for col in cols:
                if m < len(col):
                    item = col[m]
                    row.prop(item, "select", text="")
                    row.label(text=item.text)
                else:
                    row.label(text="")


    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")


    def drawExtra(self, context):
        pass


    def selectAll(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = True


    def selectNone(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = False


    def isSelected(self, item):
        return (self.selectCondition(item) and self.filtered(item))


    def selectCondition(self, item):
        return True


    def filtered(self, item):
        return (not self.filter or self.filter.lower() in item.text.lower())


    def getSelectedItems(self):
        return [item for item in self.selection if item.select and self.isSelected(item)]


    def getSelectedProps(self):
        if LS.theFilePaths:
            return LS.theFilePaths
        else:
            return [item.name for item in self.getSelectedItems()]


    def invokeDialog(self, context):
        setSelector(self)
        LS.theFilePaths = []
        wm = context.window_manager
        ncols = len(self.selection)//self.nrows + 1
        if ncols > self.ncols:
            ncols = self.ncols
        elif ncols < self.mincols:
            ncols = self.mincols
        wm.invoke_props_dialog(self, width=ncols*self.columnWidth)
        return {'RUNNING_MODAL'}


    def invoke(self, context, event):
        scn = context.scene
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        self.selection.clear()
        for idx,data in enumerate(self.getKeys(rig, ob)):
            prop,text,cat = data
            item = self.selection.add()
            item.name = prop
            item.text = text
            item.category = cat
            item.index = idx
            item.select = self.defaultSelect
        return self.invokeDialog(context)


theMorphEnums = []
theCatEnums = []

def getMorphEnums(scn, context):
    return theMorphEnums

def getCatEnums(scn, context):
    return theCatEnums

class GeneralMorphSelector(Selector):
    morphset : EnumProperty(
        items = getMorphEnums,
        name = "Type")

    category : EnumProperty(
        items = getCatEnums,
        name = "Category")

    invoked = False

    def selectCondition(self, item):
        if self.morphset == "Custom":
            return (item.name in self.catnames[self.category])
        else:
            return (item.name in self.morphnames[self.morphset])

    def draw(self, context):
        self.layout.prop(self, "morphset")
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def getKeys(self, rig, ob):
        morphs = getMorphList(rig, self.morphset, sets=MS.Standards)
        keys = [(item.name, item.text, "All") for item in morphs]
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


    def specialKey(self, key):
        if (key[0:3] == "Daz" or
            key[0:6] == "Adjust"):
            return True
        return False


    def invoke(self, context, event):
        global theMorphEnums, theCatEnums
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        self.invoked = True
        theMorphEnums = [("All", "All", "All")]
        theCatEnums = [("All", "All", "All")]
        self.morphset = "All"
        self.morphnames = {}
        self.morphnames["All"] = []
        for morphset in MS.Standards:
            theMorphEnums.append((morphset, morphset, morphset))
            pg = getattr(self.rig, "Daz"+morphset)
            self.morphnames["All"] += list(pg.keys())
            self.morphnames[morphset] = pg.keys()
        theMorphEnums.append(("Custom", "Custom", "Custom"))
        self.catnames = {}
        self.catnames["All"] = []
        for cat in rig.DazMorphCats:
            theCatEnums.append((cat.name, cat.name, cat.name))
            self.morphnames["All"] += list(cat.morphs.keys())
            self.catnames["All"] += list(cat.morphs.keys())
            self.catnames[cat.name] = cat.morphs.keys()
        return Selector.invoke(self, context, event)


class CustomSelector(Selector, CustomEnums):

    def selectCondition(self, item):
        return (self.custom == "All" or item.category == self.custom)

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        keys = []
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


class JCMSelector(Selector):
    bodypart : EnumProperty(
        items = [("All", "All", "All. Easy import transfers these shapekeys to all meshes"),
                 ("Face", "Face", "Face. Easy import transfers these shapekeys to lashes"),
                 ("Body", "Body", "Body. Easy import transfers these shapekeys to clothes and geografts"),
                 ("Custom", "Custom", "Custom. Easy import does not transfer these shapekeys")],
        name = "Body part",
        description = "Part of character that the morphs affect",
        default = "All")

    def selectCondition(self, item):
        return (self.bodypart == "All" or item.category == self.bodypart)

    def drawSelectionRow(self):
        row = self.layout.row()
        row.prop(self, "bodypart")
        row.operator("daz.select_all")
        row.operator("daz.select_none")

    def getKeys(self, rig, ob):
        keys = []
        skeys = ob.data.shape_keys
        for skey in skeys.key_blocks[1:]:
            keys.append((skey.name, skey.name, self.bodyparts[skey.name]))
        return keys

    def invoke(self, context, event):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            print("Object %s has no shapekeys")
            return {'FINISHED'}
        self.bodyparts = classifyShapekeys(ob, skeys)
        return Selector.invoke(self, context, event)


def classifyShapekeys(ob, skeys):
    morphs = {}
    bodyparts = {}
    pgs = ob.data.DazBodyPart
    for skey in skeys.key_blocks[1:]:
        if skey.name in pgs.keys():
            item = pgs[skey.name]
            if item.s not in morphs.keys():
                morphs[item.s] = []
            morphs[item.s].append(skey.name)
            bodyparts[skey.name] = item.s
        else:
            bodyparts[skey.name] = "Custom"
    return bodyparts

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
        from .modifier import getCanonicalKey

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
        default = 'NONE')

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
            self.meshes = [ob for ob in self.rig.children if ob.type == 'MESH']


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
            item = pgs.add()
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
            item = pgs.add()
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
        if GS.useStripCategory and self.category and label[0:n] == self.category:
            label = label[n:]
        if protected:
            item.text = "* %s" % label
        elif self.hideable and (hidden or not visible):
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


class DAZ_OT_SelectMhxCompatible(bpy.types.Operator):
    bl_idname = "daz.select_mhx_compatible"
    bl_label = "MHX Compatible"
    bl_description = "Select MHX compatible body morphs"

    def execute(self, context):
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


class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    morphset = "Flexions"
    bodypart = "Body"
    hideable = False

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
        self.loadMorphType(context, self.useUnits, "Units", "Face")
        self.loadMorphType(context, self.useHead, "Head", "Face")
        self.loadMorphType(context, self.useExpressions, "Expressions", "Face")
        self.loadMorphType(context, self.useVisemes, "Visemes", "Face")
        self.loadMorphType(context, self.useFacs, "Facs", "Face")
        self.loadMorphType(context, self.useFacsdetails, "Facsdetails", "Face")
        self.loadMorphType(context, self.useFacsexpr, "Facsexpr", "Face")
        self.loadMorphType(context, self.useBody, "Body", "Body")
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
#   Import general morph or driven pose
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


class DAZ_OT_ImportCustomMorphs(DazOperator, CustomMorphLoader, DazImageFile, MultiFile, IsMeshArmature):
    bl_idname = "daz.import_custom_morphs"
    bl_label = "Import Custom Morphs"
    bl_description = "Import selected morphs from native DAZ files (*.duf, *.dsf)"
    bl_options = {'UNDO', 'PRESET'}

    category : StringProperty(
        name = "Category",
        default = "Shapes")

    usePropDrivers : BoolProperty(
        name = "Use Rig Property Drivers",
        description = "Drive shapekeys with rig properties",
        default = True)

    useMeshCats : BoolProperty(
        name = "Use Mesh Categories",
        description = "Mesh categories",
        default = False)

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
        self.layout.prop(self, "usePropDrivers")
        if self.usePropDrivers:
            self.layout.prop(self, "category")
            self.layout.prop(self, "useAdjusters")
        else:
            self.layout.prop(self, "useMeshCats")
            if self.useMeshCats:
                self.layout.prop(self, "category")
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
        from .uilist import updateScrollbars
        from .finger import replaceHomeDir
        self.findIked()
        self.errors = {}
        t1 = perf_counter()
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

        if self.usePropDrivers and self.rig:
            self.rig.DazCustomMorphs = True
        elif self.useMeshCats and self.shapekeys:
            props = self.shapekeys.keys()
            addToCategories(self.mesh, props, self.category)
            self.mesh.DazMeshMorphs = True
        updateScrollbars(context.scene)
        self.finishLoading(namepaths, context, t1)


    def getNamePaths(self):
        namepaths = []
        folder = ""
        for path in self.getMultiFiles(["duf", "dsf"]):
            name = os.path.splitext(os.path.basename(path))[0]
            namepaths.append((name,path,self.bodypart))
        return namepaths


    def getAdjustProp(self):
        self.rig.DazCustomMorphs = True
        if self.category not in self.rig.DazMorphCats.keys():
            cat = self.rig.DazMorphCats.add()
            cat.name = self.category
        return "Adjust Custom/%s" % self.category

#------------------------------------------------------------------------
#   Categories
#------------------------------------------------------------------------

def addToCategories(ob, props, category):
    from .driver import setBoolProp
    from .modifier import getCanonicalKey

    if props and ob is not None:
        cats = dict([(cat.name,cat) for cat in ob.DazMorphCats])
        if category not in cats.keys():
            cat = ob.DazMorphCats.add()
            cat.name = category
        else:
            cat = cats[category]
        setBoolProp(cat, "active", True, True)
        for prop in props:
            if prop not in cat.morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = cat.morphs[prop]
            morph.name = prop
            morph.text = getCanonicalKey(prop)
            setBoolProp(morph, "active", True, True)

#------------------------------------------------------------------------
#   Rename category
#------------------------------------------------------------------------

class DAZ_OT_RenameCategory(DazPropsOperator, CustomEnums, CategoryString, IsMeshArmature):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def draw(self, context):
       self.layout.prop(self, "custom")
       self.layout.prop(self, "category", text="New Name")

    def run(self, context):
        rig = context.object
        if self.custom == "All":
            raise DazError("Cannot rename all categories")
        cat = rig.DazMorphCats[self.custom]
        cat.name = self.category


def removeFromPropGroup(pgs, prop):
    idxs = []
    for n,item in enumerate(pgs):
        if item.name == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgs.remove(n)


def removeFromAllMorphsets(rig, prop):
    for morphset in MS.Standards:
        pgs = getattr(rig, "Daz" + morphset)
        removeFromPropGroup(pgs, prop)
    for cat in rig.DazMorphCats.values():
        removeFromPropGroup(cat.morphs, prop)

#------------------------------------------------------------------------
#   Remove category or morph type
#------------------------------------------------------------------------

class MorphRemover:
    useDeleteShapekeys : BoolProperty(
        name = "Delete Shapekeys",
        description = "Delete both drivers and shapekeys",
        default = True)

    useDeleteProps : BoolProperty(
        name = "Delete Properties",
        description = "Delete object and armature properties associated with this morph",
        default = True)

    useDeleteDrivers : BoolProperty(
        name = "Delete Drivers",
        description = "Delete drivers associated with this morph",
        default = True)

    def drawExtra(self, context):
        self.layout.prop(self, "useDeleteShapekeys")
        self.layout.prop(self, "useDeleteDrivers")
        if self.useDeleteDrivers:
            self.layout.prop(self, "useDeleteProps")


    def removeRigProp(self, rig, raw):
        amt = rig.data
        final = finalProp(raw)
        rest = restProp(raw)
        if self.useDeleteDrivers:
            self.removePropDrivers(rig, raw, rig)
            self.removePropDrivers(amt, final, amt)
            self.removePropDrivers(amt, rest, amt)
        for ob in rig.children:
            if ob.type == 'MESH':
                skeys = ob.data.shape_keys
                self.removePropDrivers(skeys, raw, rig)
                self.removePropDrivers(skeys, final, amt)
                if ob.data.shape_keys:
                    if raw in skeys.key_blocks.keys():
                        skey = skeys.key_blocks[raw]
                        if self.useDeleteShapekeys or self.useDeleteDrivers:
                            skey.driver_remove("value")
                            skey.driver_remove("slider_min")
                            skey.driver_remove("slider_max")
                        if self.useDeleteShapekeys:
                            ob.shape_key_remove(skey)
        if raw in rig.keys():
            self.removeFromPropGroups(rig, raw)
        if self.useDeleteProps and self.useDeleteDrivers:
            if raw in rig.keys():
                rig[raw] = 0.0
                del rig[raw]
            if final in amt.keys():
                amt[final] = 0.0
                del amt[final]
            if rest in amt.keys():
                amt[rest] = 0.0
                del amt[rest]


    def removePropDrivers(self, rna, prop, rig):
        def matchesPath(var, path, rig):
            if var.type == 'SINGLE_PROP':
                trg = var.targets[0]
                return (trg.id == rig and trg.data_path == path)
            return False

        def removeVar(vname, string):
            string = string.replace("+%s" % vname, "").replace("-%s" % vname, "")
            words = string.split("*%s" % vname)
            nwords = []
            for word in words:
                n = len(word)-1
                while n >= 0 and (word[n].isdigit() or word[n] == "."):
                    n -= 1
                if n >= 0 and word[n] in ["+", "-"]:
                    n -= 1
                if n >= 0:
                    nwords.append(word[:n+1])
            string = "".join(nwords)
            return string.replace("()", "0")

        if rna is None or rna.animation_data is None:
            return
        path = propRef(prop)
        fcus = []
        for fcu in rna.animation_data.drivers:
            if fcu.data_path == path:
                fcus.append(fcu)
                continue
            vars = []
            keep = False
            for var in fcu.driver.variables:
                if matchesPath(var, path, rig):
                    vars.append(var)
                else:
                    keep = True
            if keep:
                if fcu.driver.type == 'SCRIPTED':
                    string = fcu.driver.expression
                    for var in vars:
                        string = removeVar(var.name, string)
                    fcu.driver.expression = string
                for var in vars:
                    fcu.driver.variables.remove(var)
            else:
                fcus.append(fcu)
        props = {}
        props[prop] = True
        for fcu in fcus:
            prop = getProp(fcu.data_path)
            if prop:
                props[prop] = True
            try:
                rna.driver_remove(fcu.data_path, fcu.array_index)
            except TypeError:
                pass
        for prop in props.keys():
            if prop in rna.keys():
                rna[prop] = 0.0


    def removeFromPropGroups(self, rig, prop):
        for morphset in MS.Standards:
            pgs = getattr(rig, "Daz%s" % morphset)
            removeFromPropGroup(pgs, prop)


    def removePropGroup(self, pgs):
        idxs = list(range(len(pgs)))
        idxs.reverse()
        for idx in idxs:
            pgs.remove(idx)


    def selectCondition(self, item):
        return True


    def getKeys(self, rig, ob):
        keys = []
        for cat in ob.DazMorphCats:
            key = cat.name
            keys.append((key,key,key))
        return keys

#------------------------------------------------------------------------
#   Remove standard morphs
#------------------------------------------------------------------------

class DAZ_OT_RemoveStandardMorphs(DazPropsOperator, MorphTypeOptions, MorphRemover, IsArmature):
    bl_idname = "daz.remove_standard_morphs"
    bl_label = "Remove Standard Morphs"
    bl_description = "Remove selected standard morphs and associated drivers"
    bl_options = {'UNDO'}

    isMhxAware = False

    def run(self, context):
        rig = context.object
        self.removeMorphType(rig, self.useUnits, "Units")
        self.removeMorphType(rig, self.useExpressions, "Expressions")
        self.removeMorphType(rig, self.useVisemes, "Visemes")
        self.removeMorphType(rig, self.useHead, "Head")
        self.removeMorphType(rig, self.useFacs, "Facs")
        self.removeMorphType(rig, self.useFacsdetails, "Facsdetails")
        self.removeMorphType(rig, self.useFacsexpr, "Facsexpr")
        self.removeMorphType(rig, self.useBody, "Body")
        self.removeMorphType(rig, self.useJcms, "Jcms")
        self.removeMorphType(rig, self.useFlexions, "Flexions")

    def removeMorphType(self, rig, use, morphset):
        if not use:
            return
        pgs = getattr(rig, "Daz%s" % morphset)
        props = [pg.name for pg in pgs]
        for prop in props:
            self.removeRigProp(rig, prop)
        self.removePropGroup(pgs)

#------------------------------------------------------------------------
#   Remove category
#------------------------------------------------------------------------

class DAZ_OT_RemoveCategories(DazOperator, Selector, MorphRemover, IsArmature):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    def run(self, context):
        items = [(item.index, item.name) for item in self.getSelectedItems()]
        items.sort()
        items.reverse()
        ob = context.object
        if ob.type == 'ARMATURE':
            self.runRig(context, ob, items)
        elif ob.type == 'MESH':
            self.runMesh(context, ob, items)


    def runRig(self, context, rig, items):
        for idx,key in items:
            cat = rig.DazMorphCats[key]
            for pg in cat.morphs:
                self.removeRigProp(rig, pg.name)
            rig.DazMorphCats.remove(idx)
        if len(rig.DazMorphCats) == 0:
            rig.DazCustomMorphs = False


    def runMesh(self, context, ob, items):
        for idx,key in items:
            cat = ob.DazMorphCats[key]
            ob.DazMorphCats.remove(idx)
        if len(ob.DazMorphCats) == 0:
            ob.DazMeshMorphs = False

#------------------------------------------------------------------------
#   Apply morphs
#------------------------------------------------------------------------

def getShapeKeyCoords(ob):
    coords = [v.co for v in ob.data.vertices]
    skeys = []
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if abs(skey.value) > 1e-4:
                coords = [co + skey.value*(skey.data[n].co - ob.data.vertices[n].co) for n,co in enumerate(coords)]
            skeys.append(skey)
    return skeys,coords


def applyMorphs(rig, props):
    for ob in rig.children:
        basic = ob.data.shape_keys.key_blocks[0]
        skeys,coords = getShapeKeyCoords(ob)
        for skey in skeys:
            path = 'key_blocks["%s"].value' % skey.name
            getDrivingProps(ob.data.shape_keys, path, props)
            ob.shape_key_remove(skey)
        basic = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(basic)
        for vn,co in enumerate(coords):
            ob.data.vertices[vn].co = co
    print("Morphs applied")


def getDrivingProps(rna, channel, props):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = trg.data_path.split('"')[1]
                    props[prop] = trg.id


def removeDrivingProps(rig, props):
    for prop,id in props.items():
        if rig == id:
            del rig[prop]
    for cat in rig.DazCategories:
        rig.DazCategories.remove(cat)

#------------------------------------------------------------------------
#   Select and unselect all
#------------------------------------------------------------------------

class Activator(MorphGroup):
    useMesh : BoolProperty(default=False)

    def run(self, context):
        scn = context.scene
        if self.useMesh:
            ob = context.object
            props = self.getCustomMorphs(scn, ob)
        else:
            ob = getRigFromObject(context.object)
            props = self.getRelevantMorphs(scn, ob)
        for prop in props:
            activate = self.getActivate(ob, prop)
            setActivated(ob, prop, activate)


def setActivated(ob, key, value):
    from .driver import setBoolProp
    if ob is None:
        return
    pg = getActivateGroup(ob, key)
    setBoolProp(pg, "active", value, True)


def getActivated(ob, rna, key, force=False):
    if key not in rna.keys():
        return False
    elif force:
        return True
    else:
        pg = getActivateGroup(ob, key)
        return pg.active


def getExistingActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        return None


def getActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        try:
            pg = rig.DazActivated.add()
            pg.name = key
            return pg
        except TypeError as err:
            msg = "Failed to load morph, because\n%s" % err
        raise DazError(msg)


class DAZ_OT_ActivateAll(DazOperator, Activator):
    bl_idname = "daz.activate_all"
    bl_label = "All"
    bl_description = "Activate all unprotected morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        from .driver import isProtected
        return (not isProtected(ob, prop))


class DAZ_OT_ActivateProtected(DazOperator, Activator):
    bl_idname = "daz.activate_protected"
    bl_label = "Protected"
    bl_description = "Activate all protected morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        from .driver import isProtected
        return isProtected(ob, prop)


class DAZ_OT_DeactivateAll(DazOperator, Activator):
    bl_idname = "daz.deactivate_all"
    bl_label = "None"
    bl_description = "Deactivate all morphs of this type"
    bl_options = {'UNDO'}

    def getActivate(self, ob, prop):
        return False

#------------------------------------------------------------------
#   Clear morphs
#------------------------------------------------------------------

def setMorphs(value, rig, mgrp, scn, frame, force):
    morphs = mgrp.getRelevantMorphs(scn, rig)
    for morph in morphs:
        if (getActivated(rig, rig, morph, force) and
            isinstance(rig[morph], float)):
            rig[morph] = value
            autoKeyProp(rig, morph, scn, frame, force)


def setShapes(value, ob, mgrp, scn, frame):
    skeys = ob.data.shape_keys
    if skeys is None:
        return
    morphs = mgrp.getRelevantShapes(ob)
    for morph in morphs:
        if getActivated(ob, skeys.key_blocks, morph.name):
            skeys.key_blocks[morph.name].value = value
            autoKeyShape(skeys, morph.name, scn, frame)


class DAZ_OT_ClearMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear Morphs"
    bl_description = "Set all selected morphs of specified type to zero.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            setMorphs(0.0, rig, self, scn, scn.frame_current, False)
            updateRigDrivers(context, rig)


class DAZ_OT_SetMorphs(DazPropsOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.set_morphs"
    bl_label = "Set Morphs"
    bl_description = "Set all selected morphs of specified type to given value.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    value : FloatProperty(
        name = "Value",
        description = "Set all selected morphs to this value",
        default = 1.0)

    useKeys : BoolProperty(
        name = "Set Keys",
        description = "Set keyframes even if auto keying is off",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "value")
        self.layout.prop(self, "useKeys")

    def storeState(self, context):
        if self.useKeys:
            scn = context.scene
            self.useAuto = scn.tool_settings.use_keyframe_insert_auto
            scn.tool_settings.use_keyframe_insert_auto = True

    def restoreState(self, context):
        if self.useKeys:
            context.scene.tool_settings.use_keyframe_insert_auto = self.useAuto

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            setMorphs(self.value, rig, self, scn, scn.frame_current, False)
            updateRigDrivers(context, rig)


class DAZ_OT_ClearShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.clear_shapes"
    bl_label = "Clear Shapes"
    bl_description = "Set all selected shapekey values of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        setShapes(0.0, context.object, self, scn, scn.frame_current)


class DAZ_OT_SetShapes(DazPropsOperator, MorphGroup, IsMesh):
    bl_idname = "daz.set_shapes"
    bl_label = "Set Shapes"
    bl_description = "Set all selected shapekey values of specified type to given value.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    value : FloatProperty(
        name = "Value",
        description = "Set all selected shapekeys to this value",
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "value")

    def run(self, context):
        scn = context.scene
        setShapes(self.value, context.object, self, scn, scn.frame_current)

#------------------------------------------------------------------
#   Add morphs to keyset
#------------------------------------------------------------------

class DAZ_OT_AddKeysets(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add selected morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            aksi = scn.keying_sets.active_index
            if aksi <= -1:
                aks = scn.keying_sets.new(idname = "daz_morphs", name = "daz_morphs")
            aks = scn.keying_sets.active
            morphs = self.getRelevantMorphs(scn, rig)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    aks.paths.add(rig.id_data, propRef(morph))
            updateRigDrivers(context, rig)

#------------------------------------------------------------------
#   Set morph keys
#------------------------------------------------------------------

class DAZ_OT_KeyMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            morphs = self.getRelevantMorphs(scn, rig, adjusters=True)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    keyProp(rig, morph, scn.frame_current)
            updateRigDrivers(context, rig)


class DAZ_OT_KeyShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.key_shapes"
    bl_label = "Set Keys"
    bl_description = "Set keys for all shapes of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys:
            scn = context.scene
            morphs = self.getRelevantShapes(ob)
            for morph in morphs:
                if getActivated(ob, skeys.key_blocks, morph.name):
                    keyShape(skeys, morph.name, scn.frame_current)

#------------------------------------------------------------------
#   Remove morph keys
#------------------------------------------------------------------

class DAZ_OT_UnkeyMorphs(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig and rig.animation_data and rig.animation_data.action:
            scn = context.scene
            morphs = self.getRelevantMorphs(scn, rig, adjusters=True)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    unkeyProp(rig, morph, scn.frame_current)
            updateRigDrivers(context, rig)


class DAZ_OT_UnkeyShapes(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.unkey_shapes"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all shapekeys of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and skeys.animation_data and skeys.animation_data.action:
            scn = context.scene
            morphs = self.getRelevantShapes(ob)
            for morph in morphs:
                if getActivated(ob, skeys.key_blocks, morph.name):
                    unkeyShape(skeys, morph.name, scn.frame_current)

#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

class DAZ_OT_UpdateSliderLimits(DazOperator, GeneralMorphSelector, IsMeshArmature):
    bl_idname = "daz.update_slider_limits"
    bl_label = "Update Slider Limits"
    bl_description = "Update selected slider min and max values.\nAll slider limits are selected when called from script"
    bl_options = {'UNDO'}

    min : FloatProperty(
        name = "Min",
        description = "Minimum slider value",
        default = 0.0)

    max : FloatProperty(
        name = "Max",
        description = "Maximum slider value",
        default = 1.0)

    useSliders : BoolProperty(
        name = "Sliders",
        description = "Update min and max for slider values",
        default = True)

    useFinal : BoolProperty(
        name = "Final",
        description = "Update min and max for final values",
        default = True)

    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Update min and max for shapekeys",
        default = True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "min")
        row.prop(self, "max")
        row = self.layout.row()
        row.prop(self, "useSliders")
        row.prop(self, "useFinal")
        row.prop(self, "useShapekeys")
        GeneralMorphSelector.draw(self, context)


    def run(self, context):
        ob = context.object
        rig = getRigFromObject(ob)
        if self.invoked:
            self.props = [item.name.lower() for item in self.getSelectedItems()]
        if rig:
            if not self.invoked:
                self.props = [key.lower() for key in rig.keys() if not self.specialKey(key)]
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)


    def updatePropLimits(self, rig, context):
        from .driver import setFloatProp
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys and self.useShapekeys:
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in self.props:
                        skey.slider_min = self.min
                        skey.slider_max = self.max
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in self.props:
                if self.useSliders:
                    setFloatProp(rig, raw, rig[raw], self.min, self.max, True)
                if self.useFinal:
                    final = finalProp(raw)
                    if final in amt.keys():
                        setFloatProp(amt, final, amt[final], self.min, self.max, False)
        updateRigDrivers(context, rig)
        print("Slider limits updated")

#------------------------------------------------------------------
#   Remove all morph drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllDrivers(DazPropsOperator, MorphRemover, DriverUser, IsMeshArmature):
    bl_idname = "daz.remove_all_drivers"
    bl_label = "Remove All Drivers"
    bl_description = "Remove all drivers from selected objects"
    bl_options = {'UNDO'}

    useDeleteDrivers = True

    def draw(self, context):
        self.layout.prop(self, "useDeleteProps")
        if self.useDeleteProps:
            self.layout.prop(self, "useDeleteShapekeys")

    def run(self, context):
        self.targets = {}
        meshes = getSelectedMeshes(context)
        rigs = getSelectedArmatures(context)
        for rig in rigs:
            for ob in rig.children:
                if ob.type == 'MESH' and ob not in meshes:
                    meshes.append(ob)
        for ob in meshes:
            skeys = ob.data.shape_keys
            if skeys:
                self.removeDrivers(skeys)
                if self.useDeleteShapekeys:
                    skeylist = list(skeys.key_blocks)
                    skeylist.reverse()
                    for skey in skeylist:
                        ob.shape_key_remove(skey)

        for rig in rigs:
            self.removeDrivers(rig.data)
            self.removeDrivers(rig)

        if not self.useDeleteProps:
            return

        for path,rna in self.targets.items():
            words = path.split('"')
            if len(words) == 5 and words[0] == "pose.bones[" and words[4] == "]":
                bname = words[1]
                prop = words[3]
                pb = rna.pose.bones[bname]
                if prop in pb.keys():
                    del pb[prop]
            elif len(words) == 3 and words[2] == "]":
                prop = words[1]
                if prop in rna.keys():
                    del rna[prop]

        for rig in rigs:
            for morphset in MS.Morphsets:
                pgs = getattr(rig, "Daz%s" % morphset)
                props = [pg.name for pg in pgs]
                for prop in props:
                    self.removeRigProp(rig, prop)
                self.removePropGroup(pgs)
            for cat in rig.DazMorphCats.values():
                for pg in cat.morphs:
                    self.removeRigProp(rig, pg.name)
            self.removePropGroup(rig.DazMorphCats)
            rig.DazCustomMorphs = False
            for prop in list(rig.keys()):
                if prop.lower().startswith(("ectrl", "ejcm", "pbm", "phm")):
                    del rig[prop]


    def removeDrivers(self, rna):
        if not rna.animation_data:
            return
        for fcu in list(rna.animation_data.drivers):
            if fcu.driver:
                if getProp(fcu.data_path):
                    self.targets[fcu.data_path] = rna
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        self.targets[trg.data_path] = trg.id
            idx = self.getArrayIndex(fcu)
            self.removeDriver(rna, fcu.data_path, idx)

#-------------------------------------------------------------
#   Add driven value nodes
#-------------------------------------------------------------

class DAZ_OT_AddDrivenValueNodes(DazOperator, Selector, DriverUser, IsMesh):
    bl_idname = "daz.add_driven_value_nodes"
    bl_label = "Add Driven Value Nodes"
    bl_description = "Add driven value nodes"
    bl_options = {'UNDO'}

    allSets = MS.Morphsets

    def getKeys(self, rig, ob):
        skeys = ob.data.shape_keys
        if skeys:
            return [(sname, sname, "All") for sname in skeys.key_blocks.keys()]
        else:
            return []


    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text = "Active material: %s" % mat.name)
        Selector.draw(self, context)


    def run(self, context):
        from .driver import getShapekeyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromObject(ob)
        mat = ob.data.materials[ob.active_material_index]
        props = self.getSelectedProps()
        nprops = len(props)
        for n,prop in enumerate(props):
            skey = skeys.key_blocks[prop]
            fcu = getShapekeyDriver(skeys, prop)
            node = mat.node_tree.nodes.new(type="ShaderNodeValue")
            node.name = node.label = skey.name
            node.location = (-1100, 250-250*n)
            if fcu:
                channel = ('nodes["%s"].outputs[0].default_value' % node.name)
                fcu2 = mat.node_tree.driver_add(channel)
                fcu2 = self.copyFcurve(fcu, fcu2)

#-------------------------------------------------------------
#   Add and remove driver
#-------------------------------------------------------------

class AddRemoveDriver:

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            for sname in self.getSelectedProps():
                self.handleShapekey(sname, rig, ob)
            updateRigDrivers(context, rig)
        updateDrivers(ob.data.shape_keys)


    def invoke(self, context, event):
        self.selection.clear()
        ob = context.object
        rig = ob.parent
        if (rig and rig.type != 'ARMATURE'):
            rig = None
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks[1:]:
                if self.includeShapekey(skeys, skey.name):
                    item = self.selection.add()
                    item.name = item.text = skey.name
                    item.category = self.getCategory(rig, ob, skey.name)
                    item.select = False
        return self.invokeDialog(context)


    def createRawFinPair(self, rig, raw, rna, channel, value, min, max):
        from .driver import addDriverVar, setFloatProp, removeModifiers
        final = finalProp(raw)
        setFloatProp(rig, raw, value, min, max, True)
        setFloatProp(rig.data, final, value, min, max, False)
        fcu = rig.data.driver_add(propRef(final))
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", propRef(raw), rig)
        fcu.driver.expression = "a"
        fcu = rna.driver_add(channel)
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", propRef(final), rig.data)
        fcu.driver.expression = "a"


class DAZ_OT_AddShapeToCategory(DazOperator, AddRemoveDriver, Selector, CustomEnums, CategoryString, IsMesh):
    bl_idname = "daz.add_shape_to_category"
    bl_label = "Add Shapekey To Category"
    bl_description = "Add selected shapekeys to mesh category"
    bl_options = {'UNDO'}

    makenew : BoolProperty(
        name = "New Category",
        description = "Create a new category",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "makenew")
        if self.makenew:
            self.layout.prop(self, "category")
        else:
            self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        if self.makenew:
            cat = self.category
        elif self.custom == "All":
            raise DazError("Cannot add to all categories")
        else:
            cat = self.custom
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            addToCategories(ob, [sname], cat)
            ob.DazMeshMorphs = True


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, CategoryString, IsMesh):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def handleShapekey(self, sname, rig, ob):
        from .driver import getShapekeyDriver
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        if getShapekeyDriver(skeys, skey.name):
            raise DazError("Shapekey %s is already driven" % skey.name)
        self.createRawFinPair(rig, sname, skey, "value", skey.value, skey.slider_min, skey.slider_max)
        addToCategories(rig, [sname], self.category)
        rig.DazCustomMorphs = True


    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return (not getShapekeyDriver(skeys, sname))


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_RemoveShapeFromCategory(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shape_from_category"
    bl_label = "Remove Shapekey From Category"
    bl_description = "Remove selected shapekeys from mesh category"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        snames = []
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in ob.DazMorphCats:
                self.removeFromCategory(ob, snames, cat.name)
        else:
            self.removeFromCategory(ob, snames, self.custom)
        updateDrivers(ob.data.shape_keys)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


    def removeFromCategory(self, ob, props, category):
        if category in ob.DazMorphCats.keys():
            cat = ob.DazMorphCats[category]
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)


class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shapekey_drivers"
    bl_label = "Remove Shapekey Drivers"
    bl_description = "Remove rig drivers from shapekeys"
    bl_options = {'UNDO'}

    def handleShapekey(self, sname, rig, ob):
        skey = ob.data.shape_keys.key_blocks[sname]
        skey.driver_remove("value")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        removeShapeDriversAndProps(ob.parent, sname)

    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return getShapekeyDriver(skeys, sname)

    def getCategory(self, rig, ob, sname):
        if rig is None:
            return ""
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


def removeShapeDriversAndProps(rig, sname):
    if rig and rig.type == 'ARMATURE':
        final = finalProp(sname)
        rig.data.driver_remove(propRef(final))
        if final in rig.data.keys():
            del rig.data[final]
        if sname in rig.keys():
            del rig[sname]
        removeFromAllMorphsets(rig, sname)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getRigFromObject(ob, useMesh=False):
    if ob.type == 'ARMATURE':
        return ob
    elif useMesh and ob.type == 'MESH':
        return ob
    else:
        ob = ob.parent
        if ob is None or ob.type != 'ARMATURE':
            return None
        return ob


class DAZ_OT_ToggleAllCats(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    useMesh : BoolProperty(default=False)
    useOpen : BoolProperty()

    def run(self, context):
        rig = getRigFromObject(context.object, self.useMesh)
        if rig:
            for cat in rig.DazMorphCats:
                cat["active"] = self.useOpen

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def keyProp(rig, key, frame):
    rig.keyframe_insert(propRef(key), frame=frame)


def keyShape(skeys, key, frame):
    skeys.keyframe_insert('key_blocks["%s"].value' % key, frame=frame)


def unkeyProp(rig, key, frame):
    try:
        rig.keyframe_delete(propRef(key), frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def unkeyShape(skeys, key, frame):
    try:
        skeys.keyframe_delete('key_blocks["%s"].value' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = propRef(key)
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def autoKeyShape(skeys, key, scn, frame):
    if scn.tool_settings.use_keyframe_insert_auto:
        keyShape(skeys, key, frame)


def pinProp(rig, scn, key, mgrp, frame, value=1.0):
    if rig:
        setMorphs(0.0, rig, mgrp, scn, frame, True)
        rig[key] = value
        autoKeyProp(rig, key, scn, frame, True)


def pinShape(ob, scn, key, mgrp, frame):
    skeys = ob.data.shape_keys
    if skeys:
        setShapes(0.0, ob, mgrp, scn, frame)
        skeys.key_blocks[key].value = 1.0
        autoKeyShape(skeys, key, scn, frame)


class DAZ_OT_PinProp(DazOperator, MorphGroup, IsMeshArmature):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        rig = getRigFromObject(context.object)
        scn = context.scene
        MP.setupMorphPaths(False)
        pinProp(rig, scn, self.key, self, scn.frame_current)
        updateRigDrivers(context, rig)


class DAZ_OT_PinShape(DazOperator, MorphGroup, IsMesh):
    bl_idname = "daz.pin_shape"
    bl_label = ""
    bl_description = "Pin shapekey value"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        ob = context.object
        scn = context.scene
        pinShape(ob, scn, self.key, self, scn.frame_current)

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

class DAZ_OT_LoadMoho(DazOperator, DatFile, ActionOptions, SingleFile, IsMeshArmature):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

    phonemeSet : EnumProperty(
        items = [("Preston-Blair", "Preston-Blair", "Preston-Blair"),
                 ("Fleming-Dobbs", "Fleming-Dobbs",  "Fleming-Dobbs"),
                 ("Rhubarb", "Rhubarb", "Rhubarb"),
                 ("CMU_39", "CMU_39", "CMU_39")],
        name = "Phoneme Set",
        description = "Phoneme Set",
        default = "Preston-Blair")

    emphasis: FloatProperty(
        name = "Emphasis",
        description = "Speech strength",
        min = 0.2, max = 5.0,
        default = 1.0)

    useUpdateLimits : BoolProperty(
        name = "Update Limits",
        description = "Update limits of open vowels to account for emphasis",
        default = True)

    useRelax : BoolProperty(
        name = "Relax Animation",
        description = "Relax the Moho animation to make it more natural",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "phonemeSet")
        self.layout.prop(self, "useRelax")
        if self.useRelax:
            self.layout.prop(self, "emphasis")
            self.layout.prop(self, "useUpdateLimits")
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "atFrameOne")


    def storeState(self, context):
        scn = context.scene
        self.auto = scn.tool_settings.use_keyframe_insert_auto
        scn.tool_settings.use_keyframe_insert_auto = True
        DazOperator.storeState(self, context)


    def restoreState(self, context):
        scn = context.scene
        scn.tool_settings.use_keyframe_insert_auto = self.auto
        DazOperator.restoreState(self, context)

    openVowels = ["AI", "E", "O"]
    silentVowels = ["FV", "MBP", "WQ"]

    phonemeConverters = {
        "Preston-Blair" : {
            "AI": "AA",
            "E": "EH",
            "etc": "K",
            "FV": "F",
            "L": "L",
            "MBP": "M",
            "O": "OW",
            "rest": "Rest",
            "U": "UW",
            "WQ": "W"
        },
        "Fleming-Dobbs" : {
            "AA": "AA",
            "EHSZ": "W",
            "FV": "F",
            "GK": "W",
            "IY": "OW",
            "MBP": "K",
            "NLTDR": "EH",
            "O": "Rest",
            "rest": "L",
            "SH": "F",
            "TH": "EH"
        },
        "Rhubarb" : {
            "A": "K",
            "B": "OW",
            "C": "W",
            "D": "AA",
            "E": "W",
            "F": "Rest",
            "G": "F",
            "H": "EH",
            "rest": "L"
        },
        "CMU_39" : {
            "AA": "AA",
            "AE": "AA",
            "AH": "EH",
            "AO": "OW",
            "AW": "M",
            "AY": "AA",
            "B": "K",
            "CH": "F",
            "D": "W",
            "DH": "EH",
            "EH": "W",
            "ER": "M",
            "EY": "W",
            "F": "F",
            "G": "W",
            "H": "W",
            "HH": "W",
            "IH": "W",
            "IY": "W",
            "JH": "M",
            "K": "W",
            "L": "EH",
            "M": "K",
            "N": "K",
            "NG": "W",
            "OW": "Rest",
            "OY": "Rest",
            "P": "K",
            "R": "EH",
            "rest": "L",
            "S": "F",
            "SH": "W",
            "T": "AA",
            "TH": "W",
            "UH": "UW",
            "UW": "UW",
            "V": "F",
            "W": "M",
            "Y": "W",
            "Z": "OW",
            "ZH": "OW"
        },
    }


    def run(self, context):
        scn = context.scene
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No armature found")
        self.phonemes = self.phonemeConverters[self.phonemeSet]
        self.clearAnimation(rig)
        if self.atFrameOne:
            frame0 = 0
        else:
            frame0 = scn.frame_current-1
        frames = self.readMoho()
        if self.useRelax:
            frames = self.improveMoho(frames)
            if self.useUpdateLimits:
                self.updateLimits(rig)
        mgrp = MorphGroup()
        mgrp.init("Visemes", "", "", "DazVisemes")
        for frame,moho,value in frames:
            if moho == "rest":
                setMorphs(0.0, rig, mgrp, scn, frame, True)
            else:
                prop = self.getMohoKey(moho, rig)
                pinProp(rig, scn, prop, mgrp, frame+frame0, value=value)
        self.nameAnimation(rig)
        print("Moho file %s loaded" % self.filepath)


    def updateLimits(self, rig):
        from .driver import getPropMinMax, setPropMinMax
        for moho in self.openVowels:
            prop = self.getMohoKey(moho, rig)
            min,max,default,ovr = getPropMinMax(rig, prop, True)
            if max < self.emphasis:
                setPropMinMax(rig, prop, default, min, self.emphasis, True)
            final = finalProp(prop)
            if final in rig.data.keys():
                min,max,default,ovr = getPropMinMax(rig.data, final, False)
                if max < self.emphasis:
                    setPropMinMax(rig.data, final, default, min, self.emphasis, False)


    def readMoho(self):
        from .fileutils import safeOpen
        frames = []
        with safeOpen(self.filepath, "r") as fp:
            for n,line in enumerate(fp):
                words= line.split()
                if len(words) >= 2 and words[0].isdigit():
                    frames.append((int(words[0]), n, words[1]))
        frames.sort()
        return [(t,key,1.0) for t,n,key in frames]


    def improveMoho(self, frames):
        first,frames = self.splitBeginning(frames)
        frames.reverse()
        last,frames = self.splitBeginning(frames)
        last.reverse()
        frames.reverse()
        key0 = "etc"
        emp = self.emphasis
        nframes = self.pruneRest(first)
        for n,frame in enumerate(frames[:-1]):
            t,key,y = frame
            t1,key1,y1 = frames[n+1]
            if key == "etc":
                if key0 == key1 and key0 in self.openVowels:
                    nframe = (t, key0, 0.5*emp)
                    nframes.append(nframe)
            elif key in self.openVowels:
                if key0 == key1 and key0 in self.silentVowels:
                    nframe = (t, key, 0.5*emp)
                elif key1 in self.silentVowels and t1-t <= 3:
                    nframe = (t, key, 0.5*emp)
                else:
                    nframe = (t, key, emp)
                nframes.append(nframe)
            else:
                nframes.append(frame)
            key0 = key
        nframes.append(frames[-1])
        last = self.pruneRest(last)
        return nframes + last


    def splitBeginning(self, frames):
        first = []
        for frame in frames:
            if frame[1] in ("rest", "etc"):
                first.append(frame)
            else:
                break
        n = len(first)
        return first, frames[n:]


    def pruneRest(self, frames):
        for frame in frames:
            if frame[1] == "rest":
                return [frame]
        return []


    def getMohoKey(self, moho, rig):
        if moho in self.phonemes.keys():
            daz = self.phonemes[moho]
            for item in rig.DazVisemes:
                if item.text == daz:
                    prop = item.name
                    if prop in rig.keys():
                        return prop
            msg = "Missing viseme: %s (%s)\n" % (daz, moho)
        else:
            msg = ("Missing viseme: %s\n" % moho +
                   "Choose different phoneme set")
        raise DazError(msg)

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_ConvertMorphsToShapes(DazOperator, GeneralMorphSelector, IsMesh):
    bl_idname = "daz.convert_morphs_to_shapekeys"
    bl_label = "Convert Morphs To Shapekeys"
    bl_description = "Convert selected morphs to shapekeys.\nAll morphs are converted when called from script"
    bl_options = {'UNDO'}

    useLabels : BoolProperty(
        name = "Labels As Names",
        description = "Use the morph labels instead of morph names as shapekey names",
        default = False)

    useDelete : BoolProperty(
        name = "Delete Existing Shapekeys",
        description = "Delete shapekeys that already exists",
        default = False)

    def draw(self, context):
        GeneralMorphSelector.draw(self, context)
        row = self.layout.row()
        row.prop(self, "useLabels")
        row.prop(self, "useDelete")

    def run(self, context):
        ob = context.object
        mod = getModifier(ob, 'ARMATURE')
        rig = ob.parent
        if (rig is None or rig.type != 'ARMATURE' or mod is None):
            raise DazError("No armature found")
        if rig.DazDriversDisabled:
            raise DazError("Drivers are disabled")
        if self.invoked:
            if self.useLabels:
                items = [(item.name, item.text) for item in self.getSelectedItems()]
            else:
                items = [(item.name, item.name) for item in self.getSelectedItems()]
        else:
            items = [(key, key) for key in rig.keys() if not self.specialKey(self, key)]
        nitems = len(items)
        skeys = ob.data.shape_keys
        existing = {}
        if self.useDelete and skeys:
            for skey in skeys.key_blocks[1:]:
                existing[skey.name] = skey
                skey.driver_remove("value")
                skey.driver_remove("slider_min")
                skey.driver_remove("slider_max")
        startProgress("Convert morphs to shapekeys")
        t1 = t = perf_counter()
        for n,item in enumerate(items):
            t0 = t
            key,mname = item
            showProgress(n, nitems)
            rig[key] = 0.0
            if skeys and mname in skeys.key_blocks.keys():
                print("Skip", mname)
                if mname in existing.keys():
                    del existing[mname]
                continue
            if mname:
                rig[key] = 1.0
                updateRigDrivers(context, rig)
                mod = self.applyArmature(ob, rig, mod, mname)
                rig[key] = 0.0
                t = perf_counter()
                print("Converted %s in %g seconds" % (mname, t-t0))
        updateRigDrivers(context, rig)
        for skey in existing.values():
            ob.shape_key_remove(skey)
        t2 = perf_counter()
        print("%d morphs converted in %g seconds" % (nitems, t2-t1))


    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        if bpy.app.version < (2,90,0):
            bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        else:
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[mname]
        skey.value = 0.0
        offsets = [(skey.data[vn].co - v.co).length for vn,v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * ob.DazScale    # eps = 0.1 mm
        if abs(omax) < eps and abs(omin) < eps:
            #idx = skeys.key_blocks.keys().index(skey.name)
            #ob.active_shape_key_index = idx
            ob.shape_key_remove(skey)
            #ob.active_shape_key_index = 0
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)
        return nmod

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_TransferAnimationToShapekeys(DazOperator, IsMeshArmature):
    bl_idname = "daz.transfer_animation_to_shapekeys"
    bl_label = "Transfer Animation To Shapekeys"
    bl_description = (
        "Transfer the armature action to actions for shapekeys.\n" +
        "From active armature to selected meshes.\n" +
        "Transferred morph F-curves are removed from the armature action")
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if not (rig and rig.animation_data and rig.animation_data.action):
            raise DazError("No action found")
        actrig = rig.animation_data.action
        meshes = [ob for ob in rig.children if ob.type == 'MESH' and ob.data.shape_keys]
        if not meshes:
            raise DazError("No meshes with shapekeys selected")

        self.morphnames = {}
        for morphset in MS.Standards:
            pgs = getattr(rig, "Daz"+morphset)
            for pg in pgs:
                self.morphnames[pg.name] = pg.text
        for cat in rig.DazMorphCats:
            for pg in cat.morphs:
                self.morphnames[pg.name] = pg.text

        for ob in meshes:
            skeys = ob.data.shape_keys
            act = None
            fcurves = {}
            for fcurig in actrig.fcurves:
                prop = getProp(fcurig.data_path)
                if prop:
                    skey = self.getShape(prop, skeys)
                    if skey:
                        channel = 'key_blocks["%s"].value' % skey.name
                        if skeys.animation_data is None:
                            skeys.animation_data_create()
                        skey.keyframe_insert("value")
                        if act is None:
                            act = skeys.animation_data.action
                            act.name = "%s:%s" % (ob.name, actrig.name)
                        fcu = act.fcurves.find(channel)
                        self.copyFcurve(fcurig, fcu)
                        fcurves[fcurig.data_path] = fcurig
            for fcu in fcurves.values():
                actrig.fcurves.remove(fcu)


    def getShape(self, prop, skeys):
        if prop in skeys.key_blocks.keys():
            return skeys.key_blocks[prop]
        sname = self.morphnames.get(prop)
        if sname in skeys.key_blocks.keys():
            return skeys.key_blocks[sname]
        return None


    def copyFcurve(self, fcu1, fcu2):
        for kp in list(fcu2.keyframe_points):
            fcu2.keyframe_points.remove(kp, fast=True)
        for kp in fcu1.keyframe_points:
            fcu2.keyframe_points.insert(kp.co[0], kp.co[1], options={'FAST'})
        for attr in ['color', 'color_mode', 'extrapolation', 'hide', 'lock', 'mute', 'select']:
            setattr(fcu2, attr, getattr(fcu1, attr))

#-------------------------------------------------------------
#   Transfer verts to shapekeys
#-------------------------------------------------------------

class DAZ_OT_MeshToShape(DazOperator, IsMesh):
    bl_idname = "daz.transfer_mesh_to_shape"
    bl_label = "Transfer Mesh To Shapekey"
    bl_description = "Transfer selected mesh to active shapekey"
    bl_options = {'UNDO'}

    def run(self, context):
        trg = context.object
        skeys = trg.data.shape_keys
        if skeys is None:
            raise DazError("Target mesh must have shapekeys")
        idx = trg.active_shape_key_index
        if idx == 0:
            raise DazError("Cannot transfer to Basic shapekeys")
        objects = [ob for ob in getSelectedMeshes(context) if ob != trg]
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected")
        src = objects[0]
        nsverts = len(src.data.vertices)
        ntverts = len(trg.data.vertices)
        if nsverts != ntverts:
            raise DazError("Vertex count mismatch:  \n%d != %d" % (nsverts, ntverts))
        skey = skeys.key_blocks[idx]
        for v in src.data.vertices:
            skey.data[v.index].co = v.co

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
        rig = self.rig = getRigFromObject(context.object)
        struct = { "filetype" : "favo_morphs" }
        self.addMorphUrls(rig, struct)
        for ob in rig.children:
            self.addMorphUrls(ob, struct)
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
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
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
        struct = loadJson(filepath)
        if ("filetype" not in struct.keys() or
            struct["filetype"] != "favo_morphs"):
            raise DazError("This file does not contain favorite morphs")
        self.useTransferFace = False
        rig = self.rig = getRigFromObject(context.object)
        rig.DazMorphUrls.clear()
        self.loadPreset(rig, rig, struct, context)
        for ob in rig.children:
            if ob.type == 'MESH':
                self.loadPreset(ob, rig, struct, context)


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
#   Import baked
#-------------------------------------------------------------

class DAZ_OT_ImportCorrections(DazPropsOperator, MorphLoader, MorphSuffix, IsArmature):
    bl_idname = "daz.import_corrections"
    bl_label = "Import Corrections"
    bl_description = "Import all custom corrections for baked morphs"

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

    def run(self, context):
        self.getFingeredRigMeshes(context)
        used = []
        self.namepaths = {}
        for path,pg in self.rig.DazBakedFiles.items():
            folder = os.path.dirname(path)
            lfolder = folder.lower()
            if lfolder in used:
                continue
            used.append(lfolder)
            cat = folder.rsplit("/", 1)[-1]
            absfolder = GS.getAbsPath(folder)
            if not absfolder:
                print("Folder not found: %s" % folder)
                continue
            print("CAT", cat, folder)
            for file in os.listdir(absfolder):
                print(" * ", file)
                lfile = file.lower()
                if os.path.splitext(file)[-1] in [".dsf", ".duf"]:
                    path = "%s/%s" % (absfolder, file)
                    if self.useExpressions and lfile.startswith("ejcm"):
                        self.addPath(path, cat, "Face")
                    elif self.useFacs and lfile.startswith("facs"):
                        self.addPath(path, cat, "Face")
                    elif self.useJcms and lfile.startswith(("pjcm", "jcm")):
                        self.addPath(path, cat, "Body")
        for cat,namepaths in self.namepaths.items():
            print("Load %s corrections" % cat)
            self.morphset = "Custom"
            self.category = cat
            self.hideable = False
            self.getAllMorphs(namepaths, context)


    def addPath(self, path, cat, bodypart):
        if cat not in self.namepaths.keys():
            self.namepaths[cat] = []
        text = os.path.splitext(os.path.basename(path))[0]
        self.namepaths[cat].append((text, path, bodypart))

#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DazSelectGroup,
    DazActiveGroup,
    DazCategory,

    DAZ_OT_SelectAll,
    DAZ_OT_SelectNone,
    DAZ_OT_SelectMhxCompatible,

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
    DAZ_OT_AddShapeToCategory,
    DAZ_OT_RemoveShapeFromCategory,
    DAZ_OT_RenameCategory,
    DAZ_OT_RemoveStandardMorphs,
    DAZ_OT_RemoveCategories,
    DAZ_OT_ActivateAll,
    DAZ_OT_ActivateProtected,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_SetMorphs,
    DAZ_OT_ClearShapes,
    DAZ_OT_SetShapes,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_KeyShapes,
    DAZ_OT_UnkeyShapes,
    DAZ_OT_UpdateSliderLimits,
    DAZ_OT_AddDrivenValueNodes,
    DAZ_OT_RemoveAllDrivers,
    DAZ_OT_AddShapekeyDrivers,
    DAZ_OT_RemoveShapekeyDrivers,
    DAZ_OT_ToggleAllCats,
    DAZ_OT_PinProp,
    DAZ_OT_PinShape,
    DAZ_OT_LoadMoho,
    DAZ_OT_ConvertMorphsToShapes,
    DAZ_OT_TransferAnimationToShapekeys,
    DAZ_OT_MeshToShape,
    DAZ_OT_SaveFavoMorphs,
    DAZ_OT_LoadFavoMorphs,
    DAZ_OT_SaveMorphPreset,
    DAZ_OT_ImportCorrections,
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


