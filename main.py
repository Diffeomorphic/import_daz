# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import bpy
from mathutils import Matrix
from .error import *
from .utils import *
from .fileutils import SingleFile, MultiFile, DazFile, DazImageFile
from .morphing import MorphSuffix, MorphTypeOptions, FavoOptions, PosableMaker
from .merge_rigs import MergeRigsOptions
from .merge_grafts import MergeGeograftOptions
from .merge_uvs import UVLayerMergerOptions
from .daz import MaterialMethodItems

#------------------------------------------------------------------
#   Color options
#------------------------------------------------------------------

class ColorOptions:
    skinColor : FloatVectorProperty(
        name = 'SKIN',
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.6, 0.4, 0.25, 1.0)
    )

    clothesColor : FloatVectorProperty(
        name = "Clothes",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.09, 0.01, 0.015, 1.0)
    )

    materialMethod : EnumProperty(
        items = MaterialMethodItems,
        name = "Material Method",
        description = "Material Method",
        default = 'EXTENDED_PRINCIPLED')

    def draw(self, context):
        if GS.materialMethod == 'SELECT':
            box = self.layout.box()
            box.label(text = "Material Method")
            box.prop(self, "materialMethod", expand=True)
        box = self.layout.box()
        box.label(text = "Viewport Color")
        if GS.viewportColors == 'GUESS':
            row = box.row()
            row.prop(self, "skinColor")
            row.prop(self, "clothesColor")
        else:
            box.label(text = GS.viewportColors)

#------------------------------------------------------------------
#   Fit options
#------------------------------------------------------------------

class FitOptions(MultiFile):
    filename_ext = ".dbz"
    filter_glob : StringProperty(default="*.duf;*.dsf;*.dbz;*.png;*.jpeg;*.jpg;*.bmp", options={'HIDDEN'})

    fitMeshes : EnumProperty(
        items = [('SHARED', "Unmorphed Shared (Environments)", "Don't fit meshes. All objects share the same mesh.\nFor environments with identical objects like leaves"),
                 ('UNIQUE', "Unmorped Unique (Environments)", "Don't fit meshes. Each object has unique mesh instance.\nFor environments with objects with same mesh but different materials, like paintings"),
                 ('TRANSFORMED', "Unmorphed Transformed (Environments)", "Don't fit meshes, but load formulas for object transformations"),
                 ('MORPHED', "Morphed (Characters)", "Don't fit meshes, but load morphs.\nIncompatible with ERC morphs"),
                 ('DBZFILE', "DBZ File (Characters)", "Use exported .dbz (.json) file to fit meshes. Must exist in same directory.\nFor characters and other objects with morphs"),
                ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'DBZFILE')

    def draw(self, context):
        if not GS.onlyDbz:
            box = self.layout.box()
            box.label(text = "Mesh Fitting")
            box.prop(self, "fitMeshes", expand=True)
            self.layout.separator()


    def invoke(self, context, event):
        if GS.onlyDbz:
            self.filename_ext = ".dbz"
            self.filter_glob = "*.dbz"
            self.fitMeshes = 'DBZFILE'
        else:
            self.filename_ext = ".dsf;.duf"
            self.filter_glob = "*.duf;*.dsf;*.png;*.jpeg;*.jpg;*.bmp"
        return MultiFile.invoke(self, context, event)

#------------------------------------------------------------------
#   DAZ Loader
#------------------------------------------------------------------

class DazLoader:
    def loadDazFile(self, filepath, context):
        from .dbzfile import getFitFile, fitToFile

        if os.path.splitext(filepath)[-1] == ".dbz":
            filepath = self.loadDbzInfo(filepath)

        LS.scene = filepath
        if bpy.app.version < (3,1,0) and GS.shellMethod == 'GEONODES':
            GS.shellMethod = 'MATERIAL'
        t1 = perf_counter()
        startProgress("\nLoading %s" % filepath)
        if LS.fitFile:
            getFitFile(filepath)

        from .load_json import JL
        struct = JL.load(filepath)
        showProgress(10, 100)

        if LS.useNodes:
            grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
            LS.collection = bpy.data.collections.new(name=grpname)
            context.collection.children.link(LS.collection)

        print("Parsing data")
        from .files import parseAssetFile
        main = parseAssetFile(struct, toplevel=True)
        if main is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)
        showProgress(20, 100)

        if LS.fitFile:
            fitToFile(filepath, main.nodes)

        print("Preprocessing...")
        for asset,inst in main.nodes:
            inst.preprocess(context)

        showProgress(30, 100)

        for asset,inst in main.modifiers:
            asset.preprocess(inst)

        print("Building objects...")
        for asset in main.materials:
            asset.build(context)
        showProgress(50, 100)

        nnodes = len(main.nodes)
        idx = 0
        for asset,inst in main.nodes:
            showProgress(50 + int(idx*30/nnodes), 100)
            idx += 1
            asset.build(context, inst)      # Builds armature
        showProgress(80, 100)

        nmods = len(main.modifiers)
        idx = 0
        for asset,inst in main.modifiers:
            showProgress(80 + int(idx*10/nmods), 100)
            idx += 1
            asset.build(context, inst)      # Builds morphs 1
        showProgress(90, 100)

        for _,inst in main.nodes:
            inst.poseRig(context)
        for asset,inst in main.nodes:
            inst.postbuild(context)

        # Need to update scene before calculating object areas
        updateScene(context)
        for asset,inst in main.modifiers:
            asset.postbuild(context, inst)
        for _,inst in main.nodes:
            inst.finalize(context)
        for asset in main.materials:
            asset.postbuild()

        for inst,mesh,objects in LS.rigidFollow.values():
            inst.makeRigidFollow(context, mesh, objects)

        from .node import finishNodeInstances
        finishNodeInstances(context)

        if LS.onLoadBaked:
            from .baked import postloadMorphs
            settings = LS.getSettings()
            try:
                postloadMorphs(context, filepath)
                for _,inst in main.nodes:
                    inst.setConformProps(context)
                updateAll(context)
            finally:
                LS.restoreSettings(settings)

        # Do this at the very end, because it deletes nodes
        if GS.usePruneNodes:
            from .tree import pruneNodeTree
            from .geometry import getActiveUvLayer
            for obs in LS.meshes.values():
                for ob in obs:
                    active = getActiveUvLayer(ob)
                    for mat in ob.data.materials:
                        if mat:
                            pruneNodeTree(mat.node_tree, active)

        t2 = perf_counter()
        print('File "%s" loaded in %.3f seconds' % (filepath, t2-t1))
        return main


    def loadDbzInfo(self, filepath):
        def checkedDufPath(dufpath):
            if os.path.exists(dufpath):
                print('DUF path: "%s"' % dufpath)
                return dufpath
            else:
                raise DazError('DBZ file lacks info about file path and root paths:\n  "%s"' % filepath)

        def checkExist(paths):
            for path in paths:
                if not os.path.exists(path):
                    return False
            return True

        from .load_json import JL
        struct = JL.load(filepath)
        dufpath = struct.get("filepath")
        if dufpath is None:
            dufpath = "%s.duf" % os.path.splitext(filepath)[0]
            return checkedDufPath(dufpath)

        pstruct = struct.get("rootpaths")
        if self.rootPaths and pstruct:
            paths = ([pstruct["cloud_content"]] +
                      pstruct["content"] +
                      pstruct["mdl_dirs"])
            if checkExist(paths):
                GS.readDazPaths(struct["rootpaths"], None, True)
                if GS.rootsFromDbz:
                    self.rootPaths = None

        return checkedDufPath(dufpath)

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZManually(DazOperator, ColorOptions, FitOptions, DazLoader):
    """Load a DAZ File"""
    bl_idname = "daz.import_daz_manually"
    bl_label = "Import DAZ Manually"
    bl_description = "Load a native DAZ file.\nFurther operations must be done manually.\nThis tool is mainly for debugging"
    bl_options = {'UNDO', 'PRESET'}

    def draw(self, context):
        FitOptions.draw(self, context)
        ColorOptions.draw(self, context)
        self.layout.separator()
        box = self.layout.box()
        box.label(text = "For more options, see Global Settings.")


    def storeState(self, context):
        self.rootPaths = (GS.contentDirs.copy(), GS.mdlDirs.copy(), GS.cloudDirs.copy())


    def restoreState(self, context):
        if self.rootPaths:
            GS.contentDirs, GS.mdlDirs, GS.cloudDirs = self.rootPaths


    def run(self, context):
        GS.checkAbsPaths()
        filepaths = self.getMultiFiles(["dbz", "duf", "dsf"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        if len(filepaths) > 1:
            t1 = perf_counter()
        LS.forImport(self)
        LS.activeObject = context.object
        for filepath in filepaths:
            self.loadDazFile(filepath, context)
        if LS.render:
            LS.render.build(context)
        if LS.toons:
            from .toon import addToons
            addToons(context)
        if GS.useDump or GS.verbosity >= 4:
            from .error import dumpErrors
            dumpErrors(filepath)
        if len(filepaths) > 1:
            t2 = perf_counter()
            print("Total load time: %.3f seconds" % (t2-t1))

        self.msg = ""
        if LS.legacySkin:
            self.msg += ("Objects with legacy skin binding found:\n" +
                   "Vertex groups are missing.\n" +
                   "Consider converting the figures to props in DAZ Studio.   \n")
            for ob,rig in LS.legacySkin:
                self.msg += '  Mesh: "%s", Rig: "%s"\n' % (ob.name, rig.name)
        if LS.missingAssets:
            self.msg += "Some assets were not found. Check that all DAZ root paths have been set up correctly.        \n"
            self.addItems(LS.missingAssets.keys())
        if LS.invalidMeshes:
            self.msg += "Invalid meshes found and corrected. Importing morphs may not work:\n"
            self.addItems(LS.invalidMeshes)
        if LS.polyLines:
            self.msg += "Found meshes without faces. Should probably be converted to hair:\n"
            obnames = []
            for geo in LS.polyLines.values():
                obnames += [noMeshName(geonode.rna.name)
                            for geonode in geo.nodes.values() if geonode.rna]
            self.addItems(obnames)
        if LS.otherRigBones:
            self.msg += "Found formulas for other rigs:\n"
            self.addItems(LS.otherRigBones.keys())
        if LS.triax:
            self.msg += "Triax approximation used for the following meshes:\n"
            self.addItems(LS.triax.keys())
        if LS.hasInstanceChildren:
            self.msg += ("The following objects have instance children. The result may be incorrect.\n")
            self.addItems(LS.hasInstanceChildren.keys())
        if LS.partialMaterials:
            self.msg += "The following materials are only partial:\n"
            self.addItems(LS.partialMaterials)
        if LS.shaders:
            self.msg += "Unsupported or partially supported shaders found:\n"
            self.addItems(LS.shaders.keys())
        if LS.hdFailures:
            self.msg += "Could not rebuild subdivisions for the following HD objects:       \n"
            self.addItems(LS.hdFailures)
        if LS.hdMismatch:
            self.msg += "Multires vertex count mismatch. Vertex groups transferred from base objects.     \n"
            self.addItems(LS.hdMismatch)
        if LS.hdUvMissing:
            self.msg += "HD objects missing exported UV layers. UVs transferred from base objects:\n"
            self.addItems(LS.hdUvMissing)

        from .material import checkRenderSettings
        self.msg += checkRenderSettings(context, False)
        if self.msg:
            clearErrorMessage()
            self.raiseWarning(self.msg)
            handleDazError(context, warning=True, dump=True)
        LS.reset()


    def addItems(self, items):
        for item in list(items)[0:10]:
            self.msg += "  %s\n" % unquote(item)
        if len(items) > 10:
            self.msg += "  ... and %d more\n" % (len(items)-10)

#------------------------------------------------------------------
#   Import DAZ Materials
#------------------------------------------------------------------

class MaterialLoader(ColorOptions):
    def loadDazFile(self, filepath, context):
        from .load_json import JL
        LS.scene = filepath
        struct = JL.load(filepath)
        print("Parsing data")
        from .files import parseAssetFile
        main = parseAssetFile(struct, toplevel=True)
        if main is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)
        return main


class ImportDAZMaterials(DazOperator, MaterialLoader, DazImageFile, MultiFile, IsMesh):
    bl_idname = "daz.import_daz_materials"
    bl_label = "Import DAZ Materials"
    bl_description = "Load materials from a native DAZ file to the active mesh"
    bl_options = {'UNDO', 'PRESET'}

    useReplaceSlots : BoolProperty(
        name = "Replace Slots",
        description = "Replace existing material slots with first materials",
        default = True)

    useAddSlots : BoolProperty(
        name = "Add Slots",
        description = "Add extra materials after existing material slots",
        default = False)

    useMatchNames : BoolProperty(
        name = "Match Names",
        description = "Match material names",
        default = True)

    useReassign : BoolProperty(
        name = "Reassign Material Numbers",
        description = "Use stored material numbers",
        default = True)

    def draw(self, context):
        ColorOptions.draw(self, context)
        self.layout.prop(self, "useReplaceSlots")
        if self.useReplaceSlots:
            self.layout.prop(self, "useReassign")
            if not self.useReassign:
                self.layout.prop(self, "useMatchNames")
        self.layout.prop(self, "useAddSlots")

    def run(self, context):
        from .cycles import CyclesMaterial
        GS.checkAbsPaths()
        filepaths = self.getMultiFiles(["duf", "dsf"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        ob = context.object
        LS.forMaterial(self, ob)
        for filepath in filepaths:
            main = self.loadDazFile(filepath, context)
            anims = {}
            for url,frames in main.animations.items():
                mname,key,type,mod = self.splitUrl(url)
                if mname is None:
                    continue
                if mname not in anims.keys():
                    anims[mname] = []
                anims[mname].append((key, type, mod, frames))
            taken = {}
            for dmat in main.materials:
                basename = stripName(dmat.name)
                anim = anims.get(basename)
                if anim:
                    self.setPartial(dmat, anim)
                    self.fixMaterial(dmat, anim)
                    taken[basename] = True
            for mname,anim in anims.items():
                basename = stripName(mname)
                if basename not in taken.keys():
                    dmat = CyclesMaterial(main.fileref)
                    mstruct = {"id" : mname}
                    dmat.parse(mstruct)
                    self.setPartial(dmat, anim)
                    dmat.update(mstruct)
                    self.fixMaterial(dmat, anim)
                    main.materials.append(dmat)

            matches = []
            if self.useReplaceSlots:
                unmatched = []
                for n,dmat in enumerate(main.materials):
                    if self.useMatchNames and not self.useReassign:
                        idx,mat = self.getMatch(dmat, ob.data.materials)
                        if mat:
                            matches.append((idx, mat, dmat))
                        elif dmat.name not in ["PBRSkin"]:
                            unmatched.append(dmat)
                    else:
                        matches.append((n, None, dmat))
            else:
                unmatched = main.materials

            for idx,mat,dmat in matches:
                dmat.mesh = ob
                if dmat.partial and mat:
                    self.updateMaterial(context, idx, mat, dmat)
                else:
                    dmat.build(context)
                    dmat.postbuild()
                    if idx < len(ob.data.materials):
                        ob.data.materials[idx] = dmat.rna
                    else:
                        ob.data.materials.append(dmat.rna)
            if self.useAddSlots:
                for dmat in unmatched:
                    dmat.build(context)
                    dmat.postbuild()
                    ob.data.materials.append(dmat.rna)
            if USE_ATTRIBUTES and self.useReassign:
                attr = ob.data.attributes.get("DazMaterialGroup")
                if attr:
                    for f in ob.data.polygons:
                        f.material_index = attr.data[f.index].value

        if LS.render:
            LS.render.build(context)


    def updateMaterial(self, context, idx, mat, dmat):
        from .tree import pruneNodeTree
        dmat.getFromMaterial(context, mat)
        tree = dmat.tree
        if tree.getValue(["Makeup Enable"], False):
            cycles = tree.getOutputs(["DAZ Makeup", "DAZ Dual Lobe PBR", "DAZ Top Coat"])
            tree.buildMakeup()
            tree.linkToOutputs(cycles)
        if tree.getValue(["Metallicity Enable"], False):
            if dmat.shader == 'UBER_IRAY':
                cycles = tree.getOutputs(["DAZ Metal", "DAZ Top Coat"])
            elif dmat.shader == 'PBRSKIN':
                cycles = tree.getOutputs(["DAZ Metal PBR", "DAZ Top Coat"])
            tree.buildMetal()
            tree.linkToOutputs(cycles)
        if tree.getValue(["Diffuse Overlay Weight"], 0):
            cycles = tree.getOutputs(["DAZ Overlay"])
            tree.buildOverlay()
            tree.linkToOutputs(cycles)
        if GS.usePruneNodes:
            pruneNodeTree(mat.node_tree)


    def getMatch(self, dmat, mats):
        dmname = stripName(dmat.name).lower()
        for n,mat in enumerate(mats):
            mname = stripName(mat.name).lower()
            if dmname == mname:
                return n,mat
        return 0,None


    def splitUrl(self, url):
        words = url.split(":?extra/studio_material_channels/channels/")
        if len(words) != 2:
            words = url.split(":?")
        words2 = words[0].split("#materials/")
        if len(words) != 2 or len(words2) != 2:
            return None, None, None, None
        mname = words2[1]
        mod = None
        if words[1].endswith("value"):
            channel = words[1][:-6]
            type = "value"
        elif words[1].endswith("image"):
            channel = words[1][:-6]
            type = "image"
        elif words[1].endswith("image_file"):
            channel = words[1][:-11]
            type = "image_file"
        elif "image_modification" in words[1]:
            channel,mod = words[1].split("/image_modification/")
            type = "image_modification"
        elif words[1] in ["uv_set"]:
            return None, None, None, None
        else:
            raise RuntimeError("Unexpected URL: %s" % url)
        return mname, unquote(channel), type, mod


    def setPartial(self, dmat, anim):
        def getKey(anim, keys):
            for key,_,_,_ in anim:
                if key in keys:
                   return True
            return False

        dmat.partial = False
        if getKey(anim, ["Makeup Weight"]):
            dmat.shader = 'PBRSKIN'
            if not getKey(anim, ["diffuse", "Diffuse Color"]):
                dmat.partial = True
        elif getKey(anim, ["Diffuse Overlay Weight"]):
            dmat.shader = 'UBER_IRAY'
            if not getKey(anim, ["diffuse", "Diffuse Color"]):
                dmat.partial = True


    def fixMaterial(self, dmat, anim):
        table = {
            "Diffuse Color" : "diffuse",
        }
        for key,type,mod,frames in anim:
            value = frames[0][1]
            channel = dmat.channels.get(key)
            if channel is None and key in table.keys():
                channel = dmat.channels.get(table[key])
            if channel is None:
                channel = dmat.channels[key] = {"id" : key, "type" : None}
            if type == "value":
                channel["current_value"] = channel["value"] = value
                if channel["type"] is None:
                    if isinstance(value, float):
                        channel["type"] = "float"
                    elif isinstance(value, int):
                        channel["type"] = "integer"
                    elif isinstance(value, list):
                        channel["type"] = "color"
                    elif isinstance(value, str):
                        channel["type"] = "string"
                    else:
                        print("UV '%s'" % value)
            elif type == "image":
                channel["image"] = value
            elif type == "image_file":
                channel["image_file"] = value
            elif type == "image_modification":
                if "image_modification" not in channel.keys():
                    channel["image_modification"] = {}
                channel["image_modification"][mod] = value

#------------------------------------------------------------------
#   Easy Import
#------------------------------------------------------------------

class EasyImportDAZ(DazOperator, ColorOptions, FitOptions, MergeGeograftOptions, UVLayerMergerOptions, MergeRigsOptions, MorphTypeOptions, MorphSuffix, FavoOptions, PosableMaker):
    """Load a DAZ File and perform the most common opertations"""
    bl_idname = "daz.easy_import_daz"
    bl_label = "Easy Import DAZ"
    bl_description = "Load a native DAZ file and perform the most common operations"
    bl_options = {'UNDO', 'PRESET'}

    useEliminateEmpties : BoolProperty(
        name = "Eliminate Empties",
        description = "Delete non-hidden empties, parenting its children to its parent instead",
        default = True)

    useMergeRigs : BoolProperty(
        name = "Merge Rigs",
        description = "Merge all rigs to the main character rig",
        default = True)

    useApplyTransforms : BoolProperty(
        name = "Apply Transforms",
        description = "Apply all transforms to objects that are not bone parented",
        default = False)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge identical materials",
        default = True)

    useMergeToes : BoolProperty(
        name = "Merge Toes",
        description = "Merge separate toes into a single toe bone",
        default = False)

    useBakedCorrectives : BoolProperty(
        name = "Baked Correctives",
        description = "Import all custom correctives for baked morphs",
        default = False)

    useDazFavorites : BoolProperty(
        name = "DAZ Favorites",
        description = "Import DAZ favorite morphs",
        default = False)

    useTransferClothes : BoolProperty(
        name = "Transfer To Clothes",
        description = "Transfer shapekeys from character to clothes",
        default = True)

    useTransferGeografts : BoolProperty(
        name = "Transfer To Geografts",
        description = "Transfer shapekeys from character to geografts.\nAlways enabled if geografts are merged",
        default = True)

    useTransferFace : BoolProperty(
        name = "Transfer To Face Meshes",
        description = (
            "Transfer shapekeys from character to face meshes\n" +
            "like eyelashes, tears, brows and beards.\n" +
            "Can be disabled if face meshes will be converted to particle hair"),
        default = True)

    useTransferHair : BoolProperty(
        name = "Transfer To Hair",
        description = "Transfer shapekeys from character to hair meshes",
        default = False)

    useTransferHD : BoolProperty(
        name = "Transfer To HD Meshes",
        description = "Transfer shapekeys from character to HD meshes",
        default = True)

    useMergeGeografts : BoolProperty(
        name = "Merge Geografts",
        description = "Merge selected geografts to active object.\nGeometry nodes are not used.\nDoes not work with nested geografts.\nShapekeys are always transferred first",
        default = False)

    useFavoMorphs : BoolProperty(
        name = "Use Favorite Morphs",
        description = "Load a favorite morphs instead of loading standard morphs",
        default = False)

    favoPath : StringProperty(
        name = "Favorite Morphs",
        description = "Path to favorite morphs")

    useAdjusters : BoolProperty(
        name = "Use Adjusters",
        description = ("Add an adjuster for the morph type.\n" +
                       "Dependence on FBM and FHM morphs is ignored.\n" +
                       "Useful if the character is baked"),
        default = False)

    useFinalOptimization : BoolProperty(
        name = "Final Optimizations",
        description = "Make final optimizations to the rig and mesh",
        default = False)

    def draw(self, context):
        FitOptions.draw(self, context)
        ColorOptions.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "useEliminateEmpties")
        self.layout.prop(self, "useMergeRigs")
        if self.useMergeRigs:
            self.subprop("duplicateDistance")
            self.subprop("useMergeNonConforming")
            self.subprop("useConvertWidgets")
            self.subprop("useTieRigs")
        self.layout.prop(self, "useApplyTransforms")
        self.layout.prop(self, "useMergeToes")
        self.layout.separator()
        self.layout.prop(self, "useFavoMorphs")
        if self.useFavoMorphs:
            self.subprop("favoPath")
            self.subprop("ignoreUrl"),
            self.subprop("ignoreFinger")
        MorphTypeOptions.draw(self, context)
        self.layout.prop(self, "useBakedCorrectives")
        self.layout.prop(self, "useDazFavorites")
        self.layout.separator()
        self.layout.prop(self, "useAdjusters")
        self.layout.prop(self, "onMorphSuffix")
        if self.onMorphSuffix == 'ALL':
            self.layout.prop(self, "morphSuffix")
        self.layout.prop(self, "useTransferFace")
        self.layout.prop(self, "useTransferHair")
        self.layout.prop(self, "useTransferGeografts")
        self.layout.prop(self, "useTransferClothes")
        self.layout.prop(self, "useTransferHD")
        self.layout.separator()
        self.layout.prop(self, "useMergeGeografts")
        if self.useMergeGeografts:
            self.subprop("useMergeUvs")
            self.subprop("keepOriginal")
        PosableMaker.draw(self, context)
        self.layout.prop(self, "useFinalOptimization")


    def invoke(self, context, event):
        scn = context.scene
        self.favoPath = dazRna(scn).DazFavoPath
        self.useFavoMorphs = (self.favoPath != "")
        return FitOptions.invoke(self, context, event)


    def storeState(self, context):
        ES.easy = True
        ES.message = ""


    def restoreState(self, context):
        ES.easy = False
        ES.message = ""


    def run(self, context):
        from .fileutils import getExistingFilePath
        GS.checkAbsPaths()
        filepaths = self.getMultiFiles(["dbz", "duf", "dsf"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        if self.useFavoMorphs:
            self.favoPath = getExistingFilePath(self.favoPath, ".json")
        active = context.object
        vly = context.view_layer
        for filepath in filepaths:
            vly.objects.active = active
            try:
                self.easyImport(context, filepath)
            except DazError as msg:
                ES.message = msg
        if ES.message:
            ES.easy = False
            msg = ES.message[:-1]
            if ES.error:
                ES.error = False
                raise DazError(msg)
            else:
                self.raiseWarning(msg)


    def easyImport(self, context, filepath):
        time1 = perf_counter()
        bpy.ops.daz.import_daz_manually(
            directory = os.path.dirname(filepath),
            files = [{"name" : os.path.basename(filepath)}],
            materialMethod = self.materialMethod,
            skinColor = self.skinColor,
            clothesColor = self.clothesColor,
            fitMeshes = self.fitMeshes)

        if not LS.objects:
            raise DazError("No objects found")
        GS.silentMode = True
        visibles = getVisibleObjects(context)
        self.rigs = self.getTypedObjects(visibles, LS.rigs)
        self.meshes = self.getTypedObjects(visibles, LS.meshes)
        self.objects = self.getTypedObjects(visibles, LS.objects)
        self.hdmeshes = self.getTypedObjects(visibles, LS.hdmeshes)
        self.hairs = self.getTypedObjects(visibles, LS.hairs)
        for rigname in self.rigs.keys():
            self.treatRig(context, rigname)
        GS.silentMode = False
        scn = context.scene
        dazRna(scn).DazFavoPath = self.favoPath
        time2 = perf_counter()
        print("File %s loaded in %.3f seconds" % (self.filepath, time2-time1))


    def getTypedObjects(self, visibles, struct):
        nstruct = {}
        for key,objects in struct.items():
            nstruct[key] = [ob for ob in objects if (ob and ob in visibles)]
        return nstruct


    def treatRig(self, context, rigname):
        from .finger import isGenesis, getFingerPrint
        rigs = self.rigs[rigname]
        meshes = self.meshes[rigname]
        objects = self.objects[rigname]
        hdmeshes = self.hdmeshes[rigname]
        hairs = self.hairs[rigname]
        if len(rigs) > 0:
            mainRig = rigs[0]
        else:
            mainRig = None
        basecoll = LS.collection
        hdcoll = LS.hdcollection
        firstMesh = (meshes[0] if meshes else None)
        mainMesh = (firstMesh if firstMesh and dazRna(firstMesh).DazMesh.startswith("Genesis") else None)
        mainChar = (isGenesis(mainRig) if mainRig else None)
        if mainChar:
            print("Main character: %s" % mainChar)
        elif mainMesh:
            try:
                msg = ("Main mesh: %s" % mainMesh.name)
            except ReferenceError:
                msg = ("Main mesh has been deleted")
                mainMesh = None
            print(msg)

        if mainRig and activateObject(context, mainRig):
            if self.useEliminateEmpties:
                bpy.ops.daz.eliminate_empties(useAllEmpties = False)

            # Merge rigs
            # Rigs must be merged before finding face meshes
            for rig in rigs[1:]:
                selectSet(rig, True)
            if self.useMergeRigs and len(rigs) > 1:
                print("Merge rigs")
                bpy.ops.daz.merge_rigs(
                    useOnlySelected = True,
                    duplicateDistance = self.duplicateDistance,
                    useMergeNonConforming = self.useMergeNonConforming,
                    useTieRigs = self.useTieRigs)
                mainRig = context.object
                rigs = [mainRig]

            # Merge toes
            if activateObject(context, mainRig):
                if self.useMergeToes:
                    print("Merge toes")
                    bpy.ops.daz.merge_toes()

        geografts = {}
        hairs = []
        lashes = []
        clothes = []
        if mainMesh:
            if mainRig:
                lmeshes = getFaceMeshes(mainRig, mainMesh)
            else:
                lmeshes = []
            for ob in meshes[1:]:
                finger = getFingerPrint(ob)
                if dazRna(ob.data).DazGraftGroup:
                    hum = self.getGraftParent(ob, meshes)
                    if hum:
                        if hum.name not in geografts.keys():
                            geografts[hum.name] = ([], hum)
                        geografts[hum.name][0].append(ob)
                    else:
                        clothes.append(ob)
                elif ob in lmeshes:
                    lashes.append(ob)
                elif isHair(ob):
                    hairs.append(ob)
                else:
                    clothes.append(ob)

        def getBaseMesh(hdob, meshes):
            basename = noHDName(hdob.name)
            meshname = "%s Mesh" % basename
            for ob in meshes:
                if ob.name in (basename, meshname):
                    return ob

        isSingleHD = False
        if GS.useHDArmature:
            from .hd_data import copyGraftGroups
            for hdob in hdmeshes:
                baseob = getBaseMesh(hdob, meshes)
                if baseob:
                    if baseob.name in geografts.keys():
                        grafts,hum = geografts[baseob.name]
                        isSingleHD = copyGraftGroups(context, hdob, baseob, grafts)

        tied = []
        if self.useApplyTransforms:
            from .apply import applyTransforms
            applyTransforms(objects)

        if mainChar and mainRig and mainMesh:
            if (  self.useUnits or
                  self.useExpressions or
                  self.useVisemes or
                  self.useHead or
                  self.useFacs or
                  self.useFacsdetails or
                  self.useFacsexpr or
                  self.useAnime or
                  self.usePowerpose or
                  self.useBody or
                  self.useJcms or
                  self.useMasculine or
                  self.useFeminine or
                  self.useFlexions or
                  self.useBulges):
                if activateObject(context, mainRig):
                    bpy.ops.daz.import_standard_morphs(
                        useUnits = self.useUnits,
                        useExpressions = self.useExpressions,
                        useVisemes = self.useVisemes,
                        useHead = self.useHead,
                        useFacs = self.useFacs,
                        useFacsdetails = self.useFacsdetails,
                        useFacsexpr = self.useFacsexpr,
                        useAnime = self.useAnime,
                        usePowerpose = self.usePowerpose,
                        useBody = self.useBody,
                        useMhxOnly = self.useMhxOnly,
                        useJcms = self.useJcms,
                        useMasculine = self.useMasculine,
                        useFeminine = self.useFeminine,
                        useFlexions = self.useFlexions,
                        useBulges = self.useBulges,
                        useAdjusters = self.useAdjusters,
                        ignoreFingers = self.ignoreFingers,
                        ignoreHdMorphs = self.ignoreHdMorphs,
                        useTransferFace = False,
                        useMakePosable=False)
            if self.useBakedCorrectives and activateObject(context, mainRig):
                useExpressions = (self.useUnits or self.useExpressions or self.useVisemes)
                if (useExpressions or self.useFacs or self.useJcms):
                    bpy.ops.daz.import_baked_correctives(
                        onMorphSuffix = self.onMorphSuffix,
                        morphSuffix = self.morphSuffix,
                        useExpressions = useExpressions,
                        useFacs = self.useFacs,
                        useJcms = self.useJcms,
                        useTransferFace = False)
            if self.useFavoMorphs:
                if activateObject(context, mainRig) and self.favoPath:
                    bpy.ops.daz.load_favo_morphs(
                        filepath = self.favoPath,
                        onMorphSuffix = self.onMorphSuffix,
                        morphSuffix = self.morphSuffix,
                        useAdjusters = self.useAdjusters,
                        useTransferFace = False,
                        useMakePosable=False)

        # Import DAZ favorites
        if self.useDazFavorites and firstMesh:
            if mainRig:
                activateObject(context, mainRig)
            else:
                activateObject(context, firstMesh)
            for ob in meshes[1:]:
                selectSet(ob, True)
            bpy.ops.daz.import_daz_favorites(
                useTransferOthers=False,
                useAdjusters = self.useAdjusters,
                useMakePosable=False)

        # Transfer to HD meshes
        if self.useTransferHD and firstMesh:
            print("Transfer from %s to HD meshes" % firstMesh.name)
            self.transferShapes(context, firstMesh, hdmeshes, True, "All", useShapeAsDriver=False)
            if isSingleHD and geografts and hdmeshes:
                print("Single HD %s, transfer geografts" % hdmeshes[0].name)
                from .hd_data import getHDMaterialVertNums
                hdmesh = hdmeshes[0]
                hdverts = hdmesh.data.vertices
                for grafts,hum in geografts.values():
                    for graft in grafts:
                        vnums = getHDMaterialVertNums(graft.data, hdmesh.data)
                        if vnums and activateObject(context, hdmesh):
                            setMode('EDIT')
                            bpy.ops.mesh.select_all(action='DESELECT')
                            setMode('OBJECT')
                            for vn in vnums:
                                hdverts[vn].select = True
                            self.transferShapes(context, graft, [hdmesh], True, "All", useSelectedOnly=True, useShapeAsDriver=False)

        # Merge material slots
        # Must be done after shapekeys have been transferred to HD.
        if (self.useMergeMaterials and
            meshes and
            activateObject(context, meshes[0])):
            for ob in meshes[1:]:
                selectSet(ob, True)
            for ob in hdmeshes:
                selectSet(ob, True)
            print("Merge materials")
            bpy.ops.daz.merge_materials()

        # Merge geografts
        hdgrafts = []
        if geografts:
            if not isSingleHD and firstMesh.name in geografts.keys():
                hdgraftNames = []
                for grafts,hum in geografts.values():
                    hdgraftNames += [HDName(graft.name) for graft in grafts]
                for hdob in list(hdmeshes):
                    if baseName(hdob.name) in hdgraftNames:
                        hdgrafts.append(hdob)

            if self.useTransferGeografts or self.useMergeGeografts:
                print("Transfer to geografts")
                for grafts,hum in geografts.values():
                    if hum == firstMesh:
                        self.transferShapes(context, hum, grafts, (not self.useMergeGeografts), "NoFace")
                for grafts,hum in geografts.values():
                    if hum != firstMesh:
                        self.transferShapes(context, hum, grafts, (not self.useMergeGeografts), "All")

            if self.useMergeGeografts:
                def mergeGeografts(context, hum, grafts, meshes):
                    if not activateObject(context, hum):
                        return
                    for graft in grafts:
                        selectSet(graft, True)
                        meshes.remove(graft)
                    print("Merge geografts")
                    bpy.ops.daz.merge_geografts(
                        useMergeUvs = self.useMergeUvs,
                        keepOriginal = self.keepOriginal)
                    if GS.viewportColors == 'GUESS':
                        from .guess import guessMaterialColor
                        LS.skinColor = self.skinColor
                        for mat in firstMesh.data.materials:
                            guessMaterialColor(mat, 'GUESS', True, LS.skinColor)

                grafts = []
                for grafts0,hum in geografts.values():
                    grafts += grafts0
                mergeGeografts(context, firstMesh, grafts, meshes)
                geografts = {}
                if hdgrafts:
                    hdmain = hdmeshes[0]
                    mergeGeografts(context, hdmain, hdgrafts, hdmeshes)
                    hdgrafts = []

        # Transfer shapekeys to clothes and lashes
        if self.useTransferClothes:
            print("Transfer to clothes")
            self.transferShapes(context, firstMesh, clothes, True, "NoFace")
        if self.useTransferHair:
            print("Transfer to hair meshes")
            self.transferShapes(context, firstMesh, hairs, True, "All")
        if self.useTransferFace:
            print("Transfer to face meshes")
            self.transferShapes(context, firstMesh, lashes, True, "All")

        # Make all bones posable and final optimization
        if mainRig and activateObject(context, mainRig):
            if self.useFinalOptimization:
                bpy.ops.daz.finalize_meshes()
            self.makePosable(context, mainRig, useActivate=False, useEasy=True)
            if self.useFinalOptimization:
                #bpy.ops.daz.optimize_drivers()
                bpy.ops.daz.finalize_armature()

        # Delete base meshes and rig
        deletes = tied
        if not GS.keepBaseMesh and hdmeshes and meshes:
            firstMesh = hdmeshes[0]
            activateObject(context, firstMesh)
            deletes += [ob for ob in meshes if ob not in hdmeshes]
            mainMesh = None
            meshes = []
            if not GS.useHDArmature and mainRig:
                deletes.append(mainRig)
                mainRig = None

        if deletes:
            deletes = set(deletes)
            print("Deleting objects: %s" % [ob.name for ob in deletes])
            deleteObjects(context, deletes)
            print("Unlinking base collection")
            if basecoll is None:
                print("No base collection")
            else:
                for ob in basecoll.objects:
                    basecoll.objects.unlink(ob)
                scncoll = context.scene.collection
                if basecoll.name in scncoll.children:
                    scncoll.children.unlink(basecoll)

        if firstMesh:
            firstMesh.update_tag()
        if mainRig:
            enableRigNumLayers(mainRig, [T_BONES, T_WIDGETS])
            mainRig.update_tag()
            activateObject(context, mainRig)
        updateAll(context)


    def getGraftParent(self, ob, meshes):
        for hum in meshes:
            if len(hum.data.vertices) == dazRna(ob.data).DazVertexCount:
                return hum
        return None


    def transferShapes(self, context, ob, meshes, useDrivers, bodypart,
                       useSelectedOnly=False,
                       useShapeAsDriver=False):
        if not (ob and meshes):
            return
        from .selector import classifyShapekeys
        from .morphing import getBulgeBone, transferShapesToMeshes
        meshes1 = []
        for mesh in meshes:
            if mesh.parent and mesh.parent_type == 'BONE':
                pass
            elif mesh.data != ob.data:
                meshes1.append(mesh)
        meshes = meshes1
        if not meshes:
            print("No valid meshes to transfer from %s" % ob.name)
            return
        skeys = ob.data.shape_keys
        if skeys:
            bodyparts = classifyShapekeys(ob, skeys)
            if bodypart == "All":
                snames = [sname for sname,bpart in bodyparts.items()]
            elif bodypart == "NoFace":
                snames = [sname for sname,bpart in bodyparts.items() if bpart != "Face"]
            else:
                snames = [sname for sname,bpart in bodyparts.items() if bpart != bodypart]
            snames = [sname for sname in snames if not getBulgeBone(sname)]
            transferShapesToMeshes(context, ob, meshes, snames,
                useDrivers=useDrivers,
                useOverwrite=False,
                useSelectedOnly=useSelectedOnly,
                useShapeAsDriver=useShapeAsDriver)

#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def getFaceMeshes(rig, ob):
    def isDeformBone(bone, mesh):
        if bone.name in mesh.vertex_groups.keys():
            return True
        else:
            for child in bone.children:
                if isDeformBone(child, mesh):
                    return True
        return False

    def hasFaceName(mesh):
        for key in ["eye", "tear", "brow", "mouth", "hair cap", "beard", "shadow plane"]:
            if key in mesh.name.lower():
                return True
        return False

    head = rig.data.bones.get("head")
    if head is None:
        return []
    matches = []
    for mesh in getMeshChildren(rig):
        if mesh != ob and isDeformBone(head, mesh):
            if hasFaceName(mesh):
                matches.append(mesh)
            elif not isHair(mesh):
                for child in head.children:
                    if isDeformBone(child, mesh):
                        matches.append(mesh)
                        break
    return matches


def isHair(ob):
    for key in ["hair", "ponytail", "pigtail", "braid"]:
        if key in ob.name.lower():
            return True
    return ob.name in ["ToulouseHR"]


def makeRootCollection(grpname, context):
    root = bpy.data.collections.new(name=grpname)
    context.collection.children.link(root)
    return root

#------------------------------------------------------------------
#   Decode file
#------------------------------------------------------------------

class DAZ_OT_DecodeFile(DazOperator, DazFile, SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf, *.dbz) to a text file"
    bl_options = {'UNDO'}

    useSaveFile : BoolProperty(
        name = "Save To File",
        description = 'Save to a file with extra ".txt"',
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useSaveFile")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        import gzip
        from .fileutils import safeOpen

        print("Decode",  self.filepath)
        try:
            with gzip.open(self.filepath, 'rb') as fp:
                bytes = fp.read()
        except IOError as err:
            msg = ("Cannot decode:\n%s" % self.filepath +
                   "Error: %s" % err)
            print(msg)
            raise DazError(msg)

        try:
            string = bytes.decode("utf-8-sig")
        except UnicodeDecodeError as err:
            msg = ('Unicode error while reading zipped file\n"%s"\n%s' % (self.filepath, err))
            print(msg)
            raise DazError(msg)

        if self.useSaveFile:
            newfile = self.filepath + ".txt"
            with safeOpen(newfile, "w") as fp:
                fp.write(string)
            print("%s written" % newfile)
        else:
            text = bpy.data.texts.new(self.filepath)
            text.from_string(string)

#------------------------------------------------------------------
#   Launch quoter
#------------------------------------------------------------------

class DAZ_OT_Quote(DazOperator):
    bl_idname = "daz.quote"
    bl_label = "Quote"

    def execute(self, context):
        from .asset import normalizeRef
        global theQuoter
        theQuoter.Text = normalizeRef(theQuoter.Text)
        return {'PASS_THROUGH'}


class DAZ_OT_Unquote(DazOperator):
    bl_idname = "daz.unquote"
    bl_label = "Unquote"

    def execute(self, context):
        global theQuoter
        theQuoter.Text = unquote(theQuoter.Text)
        return {'PASS_THROUGH'}


class DAZ_OT_QuoteUnquote(bpy.types.Operator):
    bl_idname = "daz.quote_unquote"
    bl_label = "Quote/Unquote"
    bl_description = "Quote or unquote specified text"

    Text : StringProperty(description = "Type text to quote or unquote")

    def draw(self, context):
        self.layout.prop(self, "Text", text="")
        row = self.layout.row()
        row.operator("daz.quote")
        row.operator("daz.unquote")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        global theQuoter
        theQuoter = self
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=800)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def menu_func_import(self, context):
    self.layout.operator(EasyImportDAZ.bl_idname, text="DAZ (.duf, .dsf)")


classes = [
    ImportDAZManually,
    ImportDAZMaterials,
    EasyImportDAZ,
    DAZ_OT_DecodeFile,
    DAZ_OT_Quote,
    DAZ_OT_Unquote,
    DAZ_OT_QuoteUnquote,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    from .fileutils import copyPresets
    copyPresets("easy_import_daz", "easy_import_daz")
    copyPresets("convert_to_mhx", "convert_to_mhx")


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
