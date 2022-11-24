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


import os
import bpy
from .error import *
from .utils import *
from .fileutils import SingleFile, MultiFile, DazFile, DazImageFile
from .morphing import MorphSuffix, MorphTypeOptions, FavoOptions
from .merge import MergeRigsOptions, MergeGeograftOptions
from .dforce import SoftbodyOptions
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

class FitOptions:
    fitMeshes : EnumProperty(
        items = [('SHARED', "Unmorphed Shared (Environments)", "Don't fit meshes. All objects share the same mesh.\nFor environments with identical objects like leaves"),
                 ('UNIQUE', "Unmorped Unique (Environments)", "Don't fit meshes. Each object has unique mesh instance.\nFor environments with objects with same mesh but different materials, like paintings"),
                 ('MORPHED', "Morphed (Characters)", "Don't fit meshes, but load shapekeys.\nNot all shapekeys are found.\nShapekeys are not transferred to clothes"),
                 ('DBZFILE', "DBZ File (Characters)", "Use exported .dbz (.json) file to fit meshes. Must exist in same directory.\nFor characters and other objects with morphs"),
                ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'DBZFILE')

    morphStrength : FloatProperty(
        name = "Morph Strength",
        description = "Morph strength",
        default = 1.0)

    def draw(self, context):
        box = self.layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)
        if self.fitMeshes == 'MORPHED':
            box.prop(self, "morphStrength")
        self.layout.separator()

#------------------------------------------------------------------
#   DAZ Loader
#------------------------------------------------------------------

class DazLoader:
    def loadDazFile(self, filepath, context):
        from time import perf_counter
        from .objfile import getFitFile, fitToFile

        LS.scene = filepath
        if bpy.app.version < (3,1,0) and GS.shellMethod == 'GEONODES':
            GS.shellMethod = 'MATERIAL'
        t1 = perf_counter()
        startProgress("\nLoading %s" % filepath)
        if LS.fitFile:
            getFitFile(filepath)

        from .load_json import loadJson
        struct = loadJson(filepath)
        showProgress(10, 100)

        if LS.useNodes:
            grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
            LS.collection = makeRootCollection(grpname, context)

        print("Parsing data")
        from .files import parseAssetFile
        main = parseAssetFile(struct, toplevel=True)
        if main is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)
        showProgress(20, 100)

        print("Preprocessing...")
        for asset,inst in main.nodes:
            inst.preprocess(context)

        if LS.fitFile:
            fitToFile(filepath, main.nodes)
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
        for asset in main.materials:
            asset.postbuild()

        for asset,inst in main.modifiers:
            asset.postbuild(context, inst)
        for _,inst in main.nodes:
            inst.finalize(context)

        from .node import finishNodeInstances
        finishNodeInstances(context)

        t2 = perf_counter()
        print('File "%s" loaded in %.3f seconds' % (filepath, t2-t1))
        return main

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(DazOperator, DazLoader, ColorOptions, FitOptions, DazImageFile, MultiFile):
    """Load a DAZ File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ"
    bl_description = "Load a native DAZ file"
    bl_options = {'UNDO', 'PRESET'}

    def draw(self, context):
        FitOptions.draw(self, context)
        ColorOptions.draw(self, context)
        self.layout.separator()
        box = self.layout.box()
        box.label(text = "For more options, see Global Settings.")

    def storeState(self, context):
        pass

    def restoreState(self, context):
        pass

    def run(self, context):
        from time import perf_counter
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        elif len(filepaths) > 1:
            t1 = perf_counter()
        LS.forImport(self)
        for filepath in filepaths:
            self.loadDazFile(filepath, context)
        if LS.render:
            LS.render.build(context)
        if GS.useDump:
            from .error import dumpErrors
            dumpErrors(filepath)
        if len(filepaths) > 1:
            t2 = perf_counter()
            print("Total load time: %.3f seconds" % (t2-t1))

        LS.fixMappingNodes()

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
            self.msg += "Invalid meshes found:\n"
            self.addItems(LS.invalidMeshes)
        if LS.triax:
            self.msg += "Meshes with triax weights found. Consider converting to general weights in DAZ Studio.\n"
            self.addItems(LS.triax.keys())
        if LS.hasInstanceChildren:
            self.msg += ("The following objects have instance children.\n" +
                   "The result may be incorrect.\n")
            self.addItems(LS.hasInstanceChildren.keys())
        if LS.partialMaterials:
            self.msg += "The following materials are only partial:\n"
            self.addItems(LS.partialMaterials)
        if LS.shaders:
            self.msg += "Unsupported shaders found:\n"
            self.addItems(LS.shaders.keys())
        if LS.hdFailures:
            self.msg += "Could not rebuild subdivisions for the following HD objects:       \n"
            self.addItems(LS.hdFailures)
        if LS.hdWeights:
            self.msg += "Could not copy vertex weights to the following HD objects:         \n"
            self.addItems(LS.hdWeights)
        if LS.hdUvMissing:
            self.msg += "HD objects missing UV layers:\n"
            self.addItems(LS.hdUvMissing)
            self.msg += "Export from DAZ Studio with Multires disabled.        \n"
        if LS.hdUvMismatch:
            self.msg += "HD objects with UV mismatch:\n"
            self.addItems(LS.hdUvMismatch)
            self.msg += "Enter Geometry editor before exporting HD meshes with geografts"
        if self.msg:
            clearErrorMessage()
            handleDazError(context, warning=True, dump=True)
            print(self.msg)
            LS.warning = True
            raise DazError(self.msg, warning=True)

        from .material import checkRenderSettings
        self.msg = checkRenderSettings(context, False)
        if self.msg:
            LS.warning = True
            raise DazError(self.msg, warning=True)
        LS.reset()


    def addItems(self, items):
        for item in list(items)[0:10]:
            self.msg += "  %s\n" % unquote(item)
        if len(items) > 10:
            self.msg += "  ... and %d more\n" % (len(items)-10)

#------------------------------------------------------------------
#   Import DAZ Materials
#------------------------------------------------------------------

class ImportDAZMaterials(DazOperator, ColorOptions, DazImageFile, MultiFile, IsMesh):
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

    def draw(self, context):
        ColorOptions.draw(self, context)
        self.layout.prop(self, "useReplaceSlots")
        if self.useReplaceSlots:
            self.layout.prop(self, "useMatchNames")
        self.layout.prop(self, "useAddSlots")

    def run(self, context):
        from .cycles import CyclesMaterial
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
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
            if main.materials:
                for dmat in main.materials:
                    basename = self.getMatName(dmat.name)
                    anim = anims.get(basename)
                    if anim:
                        self.setPartial(dmat, anim)
                        self.fixMaterial(dmat, anims[basename])
                        taken[basename] = True
            for mname,anim in anims.items():
                basename = self.getMatName(mname)
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
                    if self.useMatchNames:
                        idx,mat = self.getMatch(dmat, ob.data.materials)
                        if mat:
                            matches.append((idx, mat, dmat))
                        elif dmat.name not in ["PBRSkin"]:
                            unmatched.append(dmat)
                    else:
                        matches.append((n, mat, dmat))
            else:
                unmatched = main.materials

            for idx,mat,dmat in matches:
                dmat.mesh = ob
                if dmat.partial:
                    self.updateMaterial(context, idx, mat, dmat)
                else:
                    dmat.build(context)
                    dmat.postbuild()
                    ob.data.materials[idx] = dmat.rna
            if self.useAddSlots:
                for dmat in unmatched:
                    dmat.build(context)
                    dmat.postbuild()
                    ob.data.materials.append(dmat.rna)

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
        if GS.pruneNodes:
            pruneNodeTree(mat.node_tree)


    def loadDazFile(self, filepath, context):
        from .load_json import loadJson
        LS.scene = filepath
        struct = loadJson(filepath)
        print("Parsing data")
        from .files import parseAssetFile
        main = parseAssetFile(struct, toplevel=True)
        if main is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)
        return main


    def getMatch(self, dmat, mats):
        dmname = self.getMatName(dmat.name)
        for n,mat in enumerate(mats):
            mname = self.getMatName(mat.name)
            if dmname == mname:
                return n,mat
        return 0,None


    def getMatName(self, mname):
        mname = baseName(mname)
        if len(mname) > 2 and mname[-2] == "-" and mname[-1].isdigit():
            return mname[:-2]
        else:
            return mname


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
                        halt
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

class EasyImportDAZ(DazOperator, ColorOptions, FitOptions, MergeGeograftOptions, MergeRigsOptions, MorphTypeOptions, MorphSuffix, FavoOptions, SoftbodyOptions, DazImageFile, MultiFile):
    """Load a DAZ File and perform the most common opertations"""
    bl_idname = "daz.easy_import_daz"
    bl_label = "Easy Import DAZ"
    bl_description = "Load a native DAZ file and perform the most common operations"
    bl_options = {'UNDO', 'PRESET'}

    rigType : EnumProperty(
        items = [('DAZ', "DAZ", "Original DAZ rig"),
                 ('CUSTOM', "Custom Shapes", "Original DAZ rig with custom shapes"),
                 ('MHX', "MHX", "MHX rig"),
                 ('RIGIFY', "Rigify", "Rigify")],
        name = "Rig Type",
        description = "Convert the main rig to a more animator-friendly rig",
        default = 'DAZ')

    mannequinType : EnumProperty(
        items = [('NONE', "None", "Don't make mannequins"),
                 ('NUDE', "Nude", "Make mannequin for main mesh only"),
                 ('ALL', "All", "Make mannequin from all meshes")],
        name = "Mannequin Type",
        description = "Add mannequin to meshes of this type",
        default = 'NONE')

    useEliminateEmpties : BoolProperty(
        name = "Eliminate Empties",
        description = "Delete non-hidden empties, parenting its children to its parent instead",
        default = True)

    useMergeRigs : BoolProperty(
        name = "Merge Rigs",
        description = "Merge all rigs to the main character rig",
        default = True)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge identical materials",
        default = True)

    useMergeToes : BoolProperty(
        name = "Merge Toes",
        description = "Merge separate toes into a single toe bone",
        default = False)

    useTransferShapes : BoolProperty(
        name = "Transfer Shapekeys",
        description = "Transfer shapekeys from character to clothes",
        default = True)

    useSoftbody : BoolProperty(
        name = "Add Softbody",
        description = "Add softbody simultation",
        default = False)

    useMergeGeografts : BoolProperty(
        name = "Merge Geografts",
        description = "Merge selected geografts to active object.\nDoes not work with nested geografts.\nShapekeys are always transferred first",
        default = False)

    useMergeFaceMeshes : BoolProperty(
        name = "Merge Face Meshes",
        description = "Merge separate face meshes (eyelash, brow, tear, beard) to character.\nIneffective if there are unmerged geografts.\nShapekeys are always transferred first",
        default = False)

    useLashes : BoolProperty(
        name = "Lashes",
        default = True)

    useTear : BoolProperty(
        name = "Tear",
        default = False)

    useBrows : BoolProperty(
        name = "Brows",
        default = False)

    useBeard : BoolProperty(
        name = "Beard",
        default = False)

    useConvertWidgets : BoolProperty(
        name = "Convert To Widgets",
        description = "Convert widget mesh to bone custom shapes",
        default = False)

    useMakeAllBonesPosable : BoolProperty(
        name = "Make All Bones Posable",
        description = "Add an extra layer of driven bones, to make them posable",
        default = True)

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

    useTransferFace : BoolProperty(
        name = "Transfer To Face Meshes",
        description = (
            "Automatically transfer shapekeys to face meshes\n" +
            "like eyelashes, tears, brows and beards.\n" +
            "Can be disabled if face meshes will be converted to particle hair"),
        default = True)

    useConvertHair : BoolProperty(
        name = "Convert Hair",
        description = "Convert strand-based hair to particle hair",
        default = False)

    addTweakBones : BoolProperty(
        name = "Tweak Bones",
        description = "Add tweak bones",
        default = True)

    useFingerIk : BoolProperty(
        name = "Finger IK",
        description = "Generate IK controls for fingers",
        default = False)

    useOptimizePose : BoolProperty(
        name = "Optimize Pose For IK",
        description = "Optimize pose for IK.\nIncompatible with pose loading and body morphs",
        default = False)

    def draw(self, context):
        FitOptions.draw(self, context)
        ColorOptions.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "useEliminateEmpties")
        self.layout.prop(self, "useMergeRigs")
        if self.useMergeRigs:
            self.subprop("useCreateDuplicates")
            self.subprop("useMergeNonConforming")
        self.layout.prop(self, "useMakeAllBonesPosable")
        self.layout.prop(self, "useMergeToes")
        self.layout.separator()
        self.layout.prop(self, "useFavoMorphs")
        if self.useFavoMorphs:
            self.subprop("favoPath")
            self.subprop("ignoreUrl"),
            self.subprop("ignoreFinger")
            self.subprop("onMorphSuffix")
            if self.onMorphSuffix == 'ALL':
                self.subprop("morphSuffix")
        MorphTypeOptions.draw(self, context)
        self.layout.prop(self, "useAdjusters")
        if (self.useFavoMorphs or
            self.facs or
            self.facsdetails or
            self.facsexpr or
            self.jcms or
            self.flexions):
            self.layout.prop(self, "useTransferFace")
            self.layout.prop(self, "useTransferShapes")
        self.layout.separator()
        self.layout.prop(self, "useSoftbody")
        if self.useSoftbody:
            self.subprop("useChest")
            self.subprop("useBelly")
            self.subprop("useGlutes")
            self.subprop("useArms")
            self.subprop("useLegs")
        self.layout.prop(self, "useMergeGeografts")
        if self.useMergeGeografts:
            self.subprop("useMergeUvs")
            self.subprop("useGeoNodes")
        self.layout.prop(self, "useMergeFaceMeshes")
        if self.useMergeFaceMeshes:
            self.subprop("useLashes")
            self.subprop("useTear")
            self.subprop("useBrows")
            self.subprop("useBeard")
        self.layout.prop(self, "useConvertWidgets")
        self.layout.prop(self, "useConvertHair")
        self.layout.prop(self, "useOptimizePose")
        self.layout.prop(self, "rigType")
        if self.rigType == 'MHX':
            self.subprop("addTweakBones")
            self.subprop("useFingerIk")
        elif self.rigType == 'RIGIFY':
            self.subprop("useFingerIk")
        self.layout.prop(self, "mannequinType")

    def invoke(self, context, event):
        self.favoPath = context.scene.DazFavoPath
        self.useFavoMorphs = (self.favoPath != "")
        return MultiFile.invoke(self, context, event)

    def storeState(self, context):
        pass

    def restoreState(self, context):
        pass


    def run(self, context):
        from .fileutils import getExistingFilePath
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        if self.useFavoMorphs:
            self.favoPath = getExistingFilePath(self.favoPath, ".json")
        theFilePaths = LS.theFilePaths
        for filepath in filepaths:
            LS.theFilePaths = [filepath]
            try:
                self.easyImport(context)
            except DazError as msg:
                raise DazError(msg)
            finally:
                LS.theFilePaths = theFilePaths


    def easyImport(self, context):
        from time import perf_counter
        time1 = perf_counter()
        bpy.ops.daz.import_daz(
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

        if self.useEliminateEmpties:
            bpy.ops.object.select_all(action='DESELECT')
            for objects in LS.objects.values():
                for ob in objects:
                    selectSet(ob, True)
            bpy.ops.daz.eliminate_empties()

        for rigname in self.rigs.keys():
            self.treatRig(context, rigname)
        GS.silentMode = False
        context.scene.DazFavoPath = self.favoPath
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
        if hdmeshes and not GS.keepBaseMesh:
            meshes = hdmeshes
            hdmeshes = []
        if len(rigs) > 0:
            mainRig = rigs[0]
        else:
            mainRig = None
        if meshes and meshes[0].DazMesh.startswith("Genesis"):
            mainMesh = meshes[0]
        else:
            mainMesh = None
        if mainRig:
            mainChar = isGenesis(mainRig)
        else:
            mainChar = None
        if mainChar:
            print("Main character: %s" % mainChar)
        elif mainMesh:
            try:
                msg = ("Main mesh: %s" % mainMesh.name)
            except ReferenceError:
                msg = ("Main mesh has been deleted")
                mainMesh = None
            print(msg)

        geografts = {}
        lashes = []
        clothes = []
        widgetMesh = None
        if mainMesh:
            if mainRig:
                lmeshes = self.getLashes(mainRig, mainMesh)
            else:
                lmeshes = []
            for ob in meshes[1:]:
                finger = getFingerPrint(ob)
                if ob.data.DazGraftGroup:
                    cob = self.getGraftParent(ob, meshes)
                    if cob:
                        if cob.name not in geografts.keys():
                            geografts[cob.name] = ([], cob)
                        geografts[cob.name][0].append(ob)
                    else:
                        clothes.append(ob)
                elif self.useConvertWidgets and finger == "1778-3059-1366":
                    widgetMesh = ob
                elif ob in lmeshes:
                    lashes.append(ob)
                else:
                    clothes.append(ob)

        if mainRig and activateObject(context, mainRig):
            # Merge rigs
            for rig in rigs[1:]:
                selectSet(rig, True)
            if self.useMergeRigs and len(rigs) > 1:
                print("Merge rigs")
                bpy.ops.daz.merge_rigs(
                    useSubrigsOnly = True,
                    useCreateDuplicates = self.useCreateDuplicates,
                    useMergeNonConforming = self.useMergeNonConforming)
                mainRig = context.object
                rigs = [mainRig]

            # Merge toes
            if activateObject(context, mainRig):
                if self.useMergeToes:
                    print("Merge toes")
                    bpy.ops.daz.merge_toes()

        if self.useMergeMaterials and mainMesh and activateObject(context, mainMesh):
            # Merge materials
            for ob in meshes[1:]:
                selectSet(ob, True)
            print("Merge materials")
            bpy.ops.daz.merge_materials()

        if mainChar and mainRig and mainMesh:
            if self.useFavoMorphs:
                if activateObject(context, mainRig) and self.favoPath:
                    bpy.ops.daz.load_favo_morphs(
                        filepath = self.favoPath,
                        onMorphSuffix = self.onMorphSuffix,
                        morphSuffix = self.morphSuffix,
                        useAdjusters = self.useAdjusters,
                        useTransferFace = self.useTransferFace)
            if (self.units or
                  self.expressions or
                  self.visemes or
                  self.head or
                  self.facs or
                  self.facsdetails or
                  self.facsexpr or
                  self.body or
                  self.jcms or
                  self.flexions):
                if activateObject(context, mainRig):
                    bpy.ops.daz.import_standard_morphs(
                        units = self.units,
                        expressions = self.expressions,
                        visemes = self.visemes,
                        head = self.head,
                        facs = self.facs,
                        facsdetails = self.facsdetails,
                        facsexpr = self.facsexpr,
                        body = self.body,
                        useMhxOnly = self.useMhxOnly,
                        jcms = self.jcms,
                        flexions = self.flexions,
                        useAdjusters = self.useAdjusters,
                        useTransferFace = self.useTransferFace)

        # Add softbody simulation
        if self.useSoftbody and mainRig and mainMesh and activateObject(context, mainMesh):
            # Merge materials
            for ob in meshes[1:]:
                selectSet(ob, True)
            print("Add softbody")
            bpy.ops.daz.add_softbody(
                useChest = self.useChest,
                useBelly = self.useBelly,
                useGlutes = self.useGlutes,
                useArms = self.useArms,
                useLegs = self.useLegs
                )

        # Merge geografts
        if geografts:
            if self.useTransferShapes or self.useMergeGeografts:
                for aobs,cob in geografts.values():
                    if cob == mainMesh:
                        self.transferShapes(context, cob, aobs, self.useMergeGeografts, "Body", True)
                for aobs,cob in geografts.values():
                    if cob != mainMesh:
                        self.transferShapes(context, cob, aobs, self.useMergeGeografts, "All", True)
            if self.useMergeGeografts and activateObject(context, mainMesh):
                for aobs,cob in geografts.values():
                    for aob in aobs:
                        selectSet(aob, True)
                print("Merge geografts")
                bpy.ops.daz.merge_geografts(useMergeUvs = self.useMergeUvs, useGeoNodes = self.useGeoNodes)
                if GS.viewportColors == 'GUESS':
                    from .guess import guessMaterialColor
                    LS.skinColor = self.skinColor
                    for mat in mainMesh.data.materials:
                        guessMaterialColor(mat, 'GUESS', True, LS.skinColor)

        # Merge lashes
        if lashes:
            #if self.useTransferShapes or self.useMergeFaceMeshes:
            #    self.transferShapes(context, mainMesh, lashes, self.useMergeFaceMeshes, "Face", True)
            if self.useMergeFaceMeshes and activateObject(context, mainMesh):
                for ob in lashes:
                    selectSet(ob, True)
                print("Merge lashes")
                bpy.ops.daz.merge_meshes(useMergeUvs=True)

        # Transfer shapekeys to clothes
        if self.useTransferShapes:
            self.transferShapes(context, mainMesh, clothes, False, "Body", False)

        # Convert widget mesh to widgets
        if widgetMesh and mainRig and activateObject(context, widgetMesh):
            print("Convert to widgets")
            bpy.ops.daz.convert_widgets()

        if mainRig and activateObject(context, mainRig):
            # Make all bones posable
            if self.useMakeAllBonesPosable:
                print("Make all bones posable")
                bpy.ops.daz.make_all_bones_posable()

        # Convert hairs
        if (hairs and
            mainMesh and
            self.useConvertHair and
            activateObject(context, mainMesh)):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            for hair in hairs:
                if activateObject(context, hair):
                    selectSet(mainMesh, True)
                    bpy.ops.daz.make_hair(strandType='TUBE')

        # Change rig
        if mainRig and activateObject(context, mainRig):
            if self.useOptimizePose:
                bpy.ops.daz.optimize_pose(useApplyRestPose=True)

            if self.rigType == 'CUSTOM':
                print("Add custom shapes")
                bpy.ops.daz.add_custom_shapes()
            elif self.rigType == 'MHX':
                print("Convert to MHX")
                bpy.ops.daz.convert_to_mhx(
                    addTweakBones = self.addTweakBones,
                    useFingerIk = self.useFingerIk,
                )
            elif self.rigType == 'RIGIFY':
                bpy.ops.daz.convert_to_rigify(
                    useDeleteMeta = True,
                    useFingerIk = self.useFingerIk)
                mainRig = context.object

        # Make mannequin
        if (mainRig and
            mainMesh and
            self.mannequinType != 'NONE' and
            activateObject(context, mainMesh)):
            if self.mannequinType == 'ALL':
                for ob in clothes:
                    selectSet(ob, True)
            print("Make mannequin")
            bpy.ops.daz.add_mannequin(useGroup=True, group="%s Mannequin" % mainRig.name)

        if mainMesh:
            mainMesh.update_tag()
        if mainRig:
            mainRig.update_tag()
            activateObject(context, mainRig)
        updateAll(context)


    def getGraftParent(self, ob, meshes):
        for cob in meshes:
            if len(cob.data.vertices) == ob.data.DazVertexCount:
                return cob
        return None


    def transferShapes(self, context, ob, meshes, skipDrivers, bodypart, force):
        if not (ob and meshes):
            return
        from .morphing import classifyShapekeys
        skeys = ob.data.shape_keys
        if skeys:
            bodyparts = classifyShapekeys(ob, skeys)
            if bodypart == "All":
                snames = [sname for sname,bpart in bodyparts.items()]
            else:
                snames = [sname for sname,bpart in bodyparts.items() if bpart in [bodypart, "All"]]
            if not snames:
                return
            activateObject(context, ob)
            selected = False
            for mesh in meshes:
                if force or self.useTransferTo(mesh):
                    selectSet(mesh, True)
                    selected = True
            if not selected:
                return
            LS.theFilePaths = snames
            bpy.ops.daz.transfer_shapekeys(useDrivers=(not skipDrivers))


    def useTransferTo(self, mesh):
        if not getModifier(mesh, 'ARMATURE'):
            return False
        ishair = ("head" in mesh.vertex_groups.keys() and
                  "lSldrBend" not in mesh.vertex_groups.keys())
        return not ishair


    def getLashes(self, rig, ob):
        keys = []
        if self.useLashes:
            keys.append("eyelash")
        if self.useTear:
            keys.append("tear")
        if self.useBrows:
            keys.append("brow")
            keys.append("hair cap")
        if self.useBeard:
            keys.append("beard")
        return getMatchingMeshes(rig, ob, "head", keys)


def getMatchingMeshes(rig, ob, bname, keys):
    def isDeformBone(bone, mesh):
        if bone.name in mesh.vertex_groups.keys():
            return True
        else:
            for child in bone.children:
                if isDeformBone(child, mesh):
                    return True
        return False

    bone = rig.data.bones.get(bname)
    if bone is None:
        return []
    matches = []
    for mesh in getMeshChildren(rig):
        if mesh != ob:
            for key in keys:
                if key in mesh.name.lower():
                    if isDeformBone(bone, mesh):
                        matches.append(mesh)
    return matches

#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def makeRootCollection(grpname, context):
    root = bpy.data.collections.new(name=grpname)
    root.name = grpname
    context.scene.collection.children.link(root)
    return root

#------------------------------------------------------------------
#   Decode file
#------------------------------------------------------------------

class DAZ_OT_DecodeFile(DazOperator, DazFile, SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf, *.dbz) to a text file"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        import gzip
        from .asset import getDazPath
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

        newfile = self.filepath + ".txt"
        with safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)

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
    self.layout.operator(ImportDAZ.bl_idname, text="DAZ (.duf, .dsf)")
    self.layout.operator(EasyImportDAZ.bl_idname, text="Easy DAZ (.duf, .dsf)")


classes = [
    ImportDAZ,
    ImportDAZMaterials,
    EasyImportDAZ,
    DAZ_OT_DecodeFile,
    DAZ_OT_Quote,
    DAZ_OT_Unquote,
    DAZ_OT_QuoteUnquote,
]

def register():
    bpy.types.Scene.DazFavoPath = StringProperty(
        name = "Favorite Morphs",
        description = "Path to favorite morphs",
        subtype = 'FILE_PATH',
        default = "")

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
