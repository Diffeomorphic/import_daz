#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import bpy

from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, JsonExportFile

#-------------------------------------------------------------
#   Silent mode
#-------------------------------------------------------------

class DAZ_OT_SetSilentMode(bpy.types.Operator):
    bl_idname = "daz.set_silent_mode"
    bl_label = "Silent Mode"
    bl_description = "Toggle silent mode on or off (error popups off or on)"

    def execute(self, context):
        GS.silentMode = (not GS.silentMode)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Scan absolute paths (for case-sensitive file systems)
#-------------------------------------------------------------

class DAZ_OT_ScanAbsolutePaths(bpy.types.Operator):
    bl_idname = "daz.scan_absolute_paths"
    bl_label = "Scan Absolute Paths"
    bl_description = "Scan the entire DAZ database.\nFor case-sensitive file systems"

    def execute(self, context):
        GS.scanAbsPaths()
        return {'FINISHED'}

#-------------------------------------------------------------
#   Settings popup
#-------------------------------------------------------------

class DAZ_OT_AddContentDir(bpy.types.Operator):
    bl_idname = "daz.add_content_dir"
    bl_label = "Add Content Directory"
    bl_description = "Add a content directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        global theGlobalDialog
        pg = theGlobalDialog.contentDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


class DAZ_OT_AddMDLDir(bpy.types.Operator):
    bl_idname = "daz.add_mdl_dir"
    bl_label = "Add MDL Directory"
    bl_description = "Add an MDL directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        global theGlobalDialog
        pg = theGlobalDialog.mdlDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


class DAZ_OT_AddCloudDir(bpy.types.Operator):
    bl_idname = "daz.add_cloud_dir"
    bl_label = "Add Cloud Directory"
    bl_description = "Add a cloud directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        global theGlobalDialog
        pg = theGlobalDialog.cloudDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}

#-------------------------------------------------------------
#   Settings File
#-------------------------------------------------------------

class DAZ_OT_SaveSettingsFile(bpy.types.Operator, SingleFile, JsonExportFile):
    bl_idname = "daz.save_settings_file"
    bl_label = "Save Settings File"
    bl_description = "Save current settings to file"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.saveSettings(context, self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.properties.filepath = GS.settingsDir
        return SingleFile.invoke(self, context, event)


class DAZ_OT_LoadFactorySettings(bpy.types.Operator):
    bl_idname = "daz.load_factory_settings"
    bl_label = "Load Factory Settings"
    bl_description = "Restore all global settings to factory defaults"
    bl_options = {'UNDO'}

    def execute(self, context):
        global theGlobalDialog
        GS.__init__()
        GS.toDialog(theGlobalDialog)
        return {'PASS_THROUGH'}

#-------------------------------------------------------------
#   Load Root Paths
#-------------------------------------------------------------

class DAZ_OT_LoadRootPaths(bpy.types.Operator, SingleFile, JsonFile):
    bl_idname = "daz.load_root_paths"
    bl_label = "Load Root Paths"
    bl_description = "Load DAZ root paths from file"
    bl_options = {'UNDO'}

    useContent : BoolProperty(
        name = "Load Content Directories",
        default = True)

    useMDL : BoolProperty(
        name = "Load MDL Directories",
        default = True)

    useCloud : BoolProperty(
        name = "Load Cloud Directories",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useContent")
        self.layout.prop(self, "useMDL")
        self.layout.prop(self, "useCloud")

    def execute(self, context):
        from .load_json import loadJson
        struct = loadJson(self.filepath)
        if struct:
            print("Load root paths from", self.filepath)
            GS.readDazPaths(struct, self)
            GS.saveSettings(context)
            try:
                global theGlobalDialog
                if theGlobalDialog:
                    GS.toDialog(theGlobalDialog)
            except ReferenceError:
                return {'FINISHED'}
        else:
            print("No root paths found in", self.filepath)
        return {'PASS_THROUGH'}

#-------------------------------------------------------------
#   Add content dirs
#-------------------------------------------------------------

class DAZ_OT_AddContentDirs(bpy.types.Operator, SingleFile):
    bl_idname = "daz.add_content_dirs"
    bl_label = "Add Content Directories"
    bl_description = "Add DAZ root paths in directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        scn = context.scene
        dirname = os.path.dirname(self.filepath)
        self.folders = []
        self.findContentDirs(dirname, 5)
        change = False
        for folder in self.folders:
            if folder not in GS.contentDirs:
                print("Add", folder)
                change = True
                GS.contentDirs.append(folder)
        GS.saveSettings(context)
        return {'FINISHED'}


    def findContentDirs(self, folder, level):
        folder = normalizePath(folder)
        if folder.lower().endswith("/content"):
            self.folders.append(folder)
            return
        if level == 0:
            return
        for file in os.listdir(folder):
            path = "%s/%s" % (folder, file)
            if os.path.isdir(path):
                self.findContentDirs(path, level-1)

#-------------------------------------------------------------
#   Load settings file
#-------------------------------------------------------------

class DAZ_OT_LoadSettingsFile(bpy.types.Operator, SingleFile, JsonFile):
    bl_idname = "daz.load_settings_file"
    bl_label = "Load Settings File"
    bl_description = "Load settings from file"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            GS.loadSettings(self.filepath)
            GS.saveSettings(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.properties.filepath = GS.settingsDir
        return SingleFile.invoke(self, context, event)

#-------------------------------------------------------------
#   Update settings file
#-------------------------------------------------------------

class DAZ_OT_UpdateSettings(bpy.types.Operator):
    bl_idname = "daz.update_settings"
    bl_label = "Update Settings"
    bl_description = "Update settings from file"

    def execute(self, context):
        try:
            GS.getSettingsDir(context)
            filepath = GS.getSettingsPath()
            GS.loadSettings(filepath)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


def showBox(scn, attr, layout):
    if not getattr(scn, attr):
        layout.prop(scn, attr, icon="RIGHTARROW", emboss=False)
        return False
    else:
        layout.prop(scn, attr, icon="DOWNARROW_HLT", emboss=False)
        return True


MaterialMethodItems = [
    ('BSDF', "BSDF (Cycles Only)", "Best IRAY materials, slow rendering.\nUses BSDF nodes with translucency and volume nodes.\nWorks with Cycles only when the Skin method is set to IRAY"),
    ('EXTENDED_PRINCIPLED', "Extended Principled", "Limited iray materials, fast rendering.\nUses principled plus bsdf nodes for extra features.\nWorks with Cycles and Eevee"),
    ('SINGLE_PRINCIPLED', "Single Principled", "Very limited iray materials, very fast rendering.\nUses only the principled node and works with Cycles and Eevee."),
    ('FBX_COMPATIBLE', "FBX Compatible", "Extremely limited iray materials, suitable for export to game engines"),
]

class DAZ_OT_GlobalSettings(DazPropsOperator):
    bl_idname = "daz.global_settings"
    bl_label = "Global Settings"
    bl_description = "Show or update global settings"
    bl_options = {'UNDO', 'PRESET'}

    contentDirs : CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ Content Directories",
        description = "Search paths for DAZ Studio content")

    mdlDirs : CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ MDL Directories",
        description = "Search paths for DAZ Studio MDL")

    cloudDirs : CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ Cloud Directories",
        description = "Search paths for DAZ Studio cloud content")

    settingsDir : StringProperty(
        name = "Settings Directory",
        description = "Path to settings directory")

    errorFile : StringProperty(
        name = "Error File",
        description = "Error report file")

    scanFile : StringProperty(
        name = "Scanned Database Path",
        description = "Path to scanned database")

    absScanFile : StringProperty(
        name = "Absolute Paths File",
        description = "File with scanned absolute paths")

    scale : FloatProperty(
        name = "Unit Scale",
        description = "Scale used to convert between DAZ and Blender units.\nDefault unit meters",
        default = 0.01,
        precision = 4,
        min = 1e-6)

    verbosity : IntProperty(
        name = "Verbosity",
        min=1, max = 5,
        description = (
            "Controls the number of warning messages when loading files\n" +
            "1: Silent mode.\n" +
            "2: Default. Warn about some problems.\n" +
            "3: Warn about all problems.\n" +
            "4: Warn about all problems and save a log file.\n" +
            "5: Like verbosity = 4 and trigger a Python error."))

    rememberLastFolder : BoolProperty(
        name = "Remember Last Folder",
        description = "Remember the directory of the last opened file,\ninstead of starting at default location",
        default = False)

    useStrengthAdjusters : EnumProperty(
        items = [('NONE', "None", "Never add adjusters"),
                 ('Face', "Face", "Add adjusters to face morphs"),
                 ('Body', "Body", "Add adjusters to body morphs.\nNot recommended because if affects JCMs"),
                 ('Custom', "Custom", "Add adjusters to custom morphs"),
                 ('ALL', "All", "Add adjusters to all morphs")],
        name = "Adjust Strength",
        description = "Add extra sliders to adjust the overall strength",
        default = 'NONE')

    useDazLimits : BoolProperty(
        name = "DAZ Limits",
        description = "Use DAZ limits for morphs")

    sliderMultiplier : FloatProperty(
        name = "Slider Multiplier",
        description = "Multiply the min and max values for sliders with this factor",
        min = 0.0, max = 10.0)

    showFinalProps : BoolProperty(
        name = "Show Final Morph Values",
        description = "Display the \"final\" values of morphs")

    showUsedPropsOnly : BoolProperty(
        name = "Show Used Morphs Only",
        description = "Only display morphs with nonzero \"final\" value")

    showInTerminal : BoolProperty(
        name = "Show In Terminal",
        description = "Display full morph names when loading and transferring morphs")

    useShapeCats : BoolProperty(
        name = "Shapekey Categories",
        description = "Display undriven shapekeys as categories")

    useMuteDrivers : BoolProperty(
        name = "Shapekey Mute Drivers",
        description = "Add drivers that mute shapekeys if shapekey value = 0.\nAffects JCMs, flexions and custom morphs")

    ercMethod : EnumProperty(
        items = [('NONE', "None", "ERC morphs are ignored"),
                 ('TRANSLATION', "Translation", "ERC morphs are translations"),
                 ('ARMATURE', "Armature Custom", "Custom ERC morphs change the rest pose"),
                 ('ALL', "Armature All", "All ERC morphs change the rest pose")],
        name = "ERC Method",
        description = "Support for ERC morphs that change the rest pose")

    useStripCategory : BoolProperty(
        name = "Strip Category",
        description = "Strip the category name from the beginning of the morph name if they are the same")

    useModifiedMesh : BoolProperty(
        name = "Import To Modified Meshes",
        description = "Import morphs to meshes that have been modified by merging geografts or lashes.\nWarning: can give incorrect shapekeys if meshes have been modified in edit mode")

    useDefaultDrivers : BoolProperty(
        name = "Default Drivers",
        description = "Create default drivers defined in the scene file")

    useOptimizeJcms : BoolProperty(
        name = "Optimize JCM Drivers",
        description = "Optimize drivers when loading JCMs and flexions. Experimental")

    useMakeHiddenSliders : BoolProperty(
        name = "Make Hidden Sliders",
        description = "Create properties for hidden morphs,\nso they can be displayed in the UI")

    useBakedMorphs : BoolProperty(
        name = "Baked Morphs",
        description = "Allow that baked morphs are imported,\nand display them in the Morphs panel")

    showHiddenObjects : BoolProperty(
        name = "Show Hidden Objects",
        description = "Don't hide objects which are hidden in DAZ Studio")

    ignoreHiddenObjects : BoolProperty(
        name = "Ignore Hidden Objects",
        description = "Don't build objects which are hidden in DAZ Studio")

    useBakedLocations : BoolProperty(
        name = "Baked Locations",
        description = "Use object locations baked in dbz files.\nThis sometimes improves object locations but distorts pivots of bone parented objects")

    useMeshDrivers : BoolProperty(
        name = "Mesh Drivers",
        description = "Drive shapekeys with mesh object properties")

    showPaths : BoolProperty(name = "Paths To DAZ Library", default = False)
    showContentDirs : BoolProperty(name = "Content Directories", default = True)
    showMDLDirs : BoolProperty(name = "MDL Directories", default = False)
    showCloudDirs : BoolProperty(name = "Cloud Directories", default = False)

    materialMethod : EnumProperty(
        items = [('SELECT', "Select On Load", "Select the material method when loading files")] + MaterialMethodItems,
        name = "Material Method",
        description = "Material Method",
        default = 'SELECT')

    enums = [('BURLEY', "Christensen-Burley", "Christensen-Burley"),
             ('RANDOM_WALK', "Random Walk", "Random walk")]
    if BLENDER3:
        enums.append(('RANDOM_WALK_FIXED_RADIUS', "Random Walk (Fixed Radius)", "Random Walk (Fixed Radius)"))
    else:
        enums.append(('RANDOM_WALK_SKIN', "Random Walk (Skin)", "Random Walk (Skin)"))
    sssMethod : EnumProperty(
        items = enums,
        name = "SSS",
        description = "Method for subsurface scattering")

    displacement_method : EnumProperty(
        items = [('BUMP', "Bump Only", "Bump"),
                 ('DISPLACEMENT', "Displacement Only", "Details are not visible if the subdivision is not enough, renders smooth"),
                 ('BOTH', "Displacement and Bump", "Fake details with a bump map if the subdivision is not enough, renders flat.")],
        name = "Displacement Method",
        description = "Displacement method")

    viewportColors : EnumProperty(
        items = [('ORIGINAL', "Original", "Original diffuse color"),
                 ('RANDOM', "Random", "Random colors for each material"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Viewport",
        description = "Method to display object in viewport")

    useWorld : EnumProperty(
        items = [('ALWAYS', "Always", "Always create world material"),
                 ('DOME', "Dome", "Create world material from dome"),
                 ('NEVER', "Never", "Never create world material")],
        name = "World",
        description = "When to create a world material")

    useMaterialsByIndex : BoolProperty(
        name = "Materials By Index",
        description = "Use index rather than name to identify materials.\nNeeded if multiple materials have identical names.\nThis only happens in files generated by the MikuMikuDance exporter")

    useMaterialsByName : BoolProperty(
        name = "Sort Materials Alphabetically",
        description = "Materials are sorted in alphabetical order.\nIf disabled the order in the duf file is used")

    handleRenderSettings : EnumProperty(
        items = [("IGNORE", "Ignore", "Ignore insufficient render settings"),
                 ("WARN", "Warn", "Warn about insufficient render settings"),
                 ("UPDATE", "Update", "Update insufficient render settings")],
        name = "Render Settings",
        default = "UPDATE"
    )

    handleLightSettings : EnumProperty(
        items = [("IGNORE", "Ignore", "Ignore insufficient light settings"),
                 ("WARN", "Warn", "Warn about insufficient light settings"),
                 ("UPDATE", "Update", "Update insufficient light settings")],
        name = "Light Settings",
        default = "UPDATE"
    )

    useLockLoc : BoolProperty(
        name = "Location Locks",
        description = "Use location locks")

    useLimitLoc : BoolProperty(
        name = "Location Limits",
        description = "Enable location limits")

    useLockRot : BoolProperty(
        name = "Rotation Locks",
        description = "Use rotation locks")

    useLimitRot : BoolProperty(
        name = "Rotation Limits",
        description = "Enable rotation limits")

    useInheritScale : BoolProperty(
        name = "Bones Inherit Scale",
        description = "Bones inherit scale from their parents (Blender default).\nDisable to mimic behaviour in DAZ Studio")

    displayLimitRot : BoolProperty(
        name = "Display Rotation Limits",
        description = "Display rotation limits as IK limits")

    useBoneColors : BoolProperty(
        name = "Bone Colors",
        description = "Colorize bones. For debugging in Blender 4")

    useDump : BoolProperty(
        name = "Dump Debug Info",
        description = "Dump debug info in the file\ndaz_importer_errors.text after loading file")

    zup : BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention.\nDisable for debugging only")

    unflipped : BoolProperty(
        name = "Unflipped Bones",
        description = "Don't flip bone axes.\nEnable for debugging only")

    useTriaxImprove : BoolProperty(
        name = "Improve Triax Weights",
        description = "Improve vertex groups for triax weights (Genesis/Genesis 2 only)")

    useBulgeWeights : BoolProperty(
        name = "Bulge Weights",
        description = "Add vertex groups for triax bulge weights")

    keepTriaxWeights : BoolProperty(
        name = "Keep Triax Weights",
        description = "Keep triax local weights")

    useTriaxApply : BoolProperty(
        name = "Triax Apply",
        description = "Apply triax vertex weight modifiers")

    useArmature : BoolProperty(
        name = "Armature",
        description = "Create armatures for imported figures")

    useQuaternions : BoolProperty(
        name = "Quaternions",
        description = "Use quaternions for ball-and-socket joints (shoulders and hips)")

    caseSensitivePaths : BoolProperty(
        name = "Case-Sensitive Paths",
        description = "Convert URLs to lowercase. Works best on Windows")

    useInstancing : BoolProperty(
        name = "Use Instancing",
        description = "Use instancing for DAZ instances")

    useHairGuides : BoolProperty(
        name = "Import All Hair Versions",
        description = "Import hair guides even if the corresponding PS hairs have also been generated.\nOnly for DBZ mesh fitting")

    useHighDef : BoolProperty(
        name = "Build HD Meshes",
        description = "Build HD meshes if included in .dbz file")

    keepBaseMesh : BoolProperty(
        name = "Keep Base Meshes",
        description = "Also keep base meshes if HD meshes are imported")

    useHDArmature : BoolProperty(
        name = "Add HD Armatures",
        description = "Add armature modifier and vertex groups to HD and multires meshes")

    useMultires : BoolProperty(
        name = "Add Multires",
        description = "Add multires modifier to HD meshes and rebuild lower subdivision levels")

    useAutoSmooth : BoolProperty(
        name = "Auto Smooth",
        description = (
            "Use auto smooth if this is done in DAZ Studio.\n" +
            "This is useful for objects with hard edges,\n" +
            "but may lead to poor performance for organic meshes"))

    maxSubdivs : IntProperty(
        name = "Max Subdivision Level",
        description = "The maximum subdivision level.\nToo high a value can cause Blender to crash",
        min = 1, max = 11)

    onFaceMaps : EnumProperty(
        items = [('NEVER', "Never", "Don't create maps groups"),
                 ('MATERIALS', "Materials", "Create face maps for materials"),
                 ('POLYGON_GROUPS', "Polygon Groups", "Create face maps for polygon groups"),
                ],
        name = "Face Maps",
        description = "Generate face maps on import")

    useScaleEyeMoisture : BoolProperty(
        name = "Scale Eye Moisture",
        description = "Scale eye moisture vertices to avoid dark rings when rendering eyes")

    useSimulation : BoolProperty(
        name = "Simulation",
        description = "Add influence (pinning) vertex groups for simulation")

    enums = [('MATERIAL', "Material", "Create material node groups")]
    if bpy.app.version >= (3,1,0):
        enums += [('GEONODES', "Geometry Nodes (Experimental)", "Create geometry node groups")]
    enums += [('IGNORE', "Ignore", "Ignore shells"),
              ('MESH', "Mesh (Debug)", "Create empty meshes. For debugging only")]
    shellMethod : EnumProperty(
        items = enums,
        name = "Shell Method",
        description = "Method for geometry shells")

    usePruneNodes : BoolProperty(
        name = "Prune Node Tree",
        description = "Prune material node-tree.\nDisable for debugging only")

    useFakeCaustics : BoolProperty(
        name = "Fake Caustics",
        description = "Use fake caustics")

    useDisplacement : BoolProperty(
        name = "Displacement",
        description = "Use displacement maps")

    useEmission : BoolProperty(
        name = "Emission",
        description = "Use emission")

    useGhostLights : BoolProperty(
        name = "Ghost Lights",
        description = "Mimics the iray ghost light bug, that is fixed in DS 4.20.\nDo not use to mimic DS 4.20")

    bumpMultiplier : FloatProperty(
        name = "Bump Multiplier",
        description = "Factor to multiply bump distance")

    skinMethod : EnumProperty(
        items = [('IRAY', "IRAY", "Use translucency and volume nodes.\nUsually the most accurate conversion of volumetric skin materials,\nbut only works with Cycles and the BSDF material method"),
                 ('SSS', "SSS", "Replace translucency and volume with subsurface scattering"),
                 ('AltSSS', "Alternative SSS", "Alternative handling of SSS suggested by Midnight Arrow")],
        name = "Skin Method",
        description = "Conversion method for volumetric skin materials")

    useVolume : BoolProperty(
        name = "Volume",
        description = "Use volume for volumetice materials")

    imageInterpolation : EnumProperty(
        items = [('Linear', "Linear", "Linear"),
                 ('Closest', "Closest", "Closest"),
                 ('Cubic', "Cubic", "Cubic"),
                 ('Smart', "Smart", "Smart")],
        name = "Interpolation",
        description = "Image interpolation")

    useUnusedTextures : BoolProperty(
        name = "Build Unused Textures",
        description = "Build texture found in unused channels")

    useShellDrivers : BoolProperty(
        name = "Shell Drivers",
        description = "Add drivers to shell influence")

    useLayeredInflu : BoolProperty(
        name = "Layered Image Influence",
        description = "Add layered image influence")

    useLayeredShells : BoolProperty(
        name = "Layered Images In Shells",
        description = "Use layered images in shells (experimental)")

    author : StringProperty(
        name = "Author",
        description = "Author info in preset files")

    email : StringProperty(
        name = "Email",
        description = "Email info in preset files")

    website : StringProperty(
        name = "Website",
        description = "Website info in preset files")

    def draw(self, context):
        split = self.layout.split(factor=0.33)
        col = split.column()
        row = col.row()
        row.operator("daz.load_root_paths")
        row.operator("daz.load_factory_settings")

        box = col.box()
        box.label(text = "DAZ Studio Root Directories")
        if showBox(self, "showContentDirs", box):
            for pg in self.contentDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_content_dir")
        if showBox(self, "showMDLDirs", box):
            for pg in self.mdlDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_mdl_dir")
        if showBox(self, "showCloudDirs", box):
            for pg in self.cloudDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_cloud_dir")

        box.separator()
        box.label(text = "Settings Directory: %s" % GS.settingsDir)
        box.prop(self, "errorFile")
        box.prop(self, "scanFile")
        box.prop(self, "absScanFile")

        col = split.column()
        box = col.box()
        box.label(text = "General")
        box.prop(self, "scale")
        box.prop(self, "verbosity")
        box.prop(self, "caseSensitivePaths")
        box.prop(self, "rememberLastFolder")

        box = col.box()
        box.label(text = "Meshes")
        box.prop(self, "shellMethod")
        box.prop(self, "useTriaxImprove")
        box.prop(self, "useBulgeWeights")
        box.prop(self, "useHighDef")
        box.prop(self, "useMultires")
        box.prop(self, "keepBaseMesh")
        box.prop(self, "useHDArmature")
        box.prop(self, "useHairGuides")
        box.prop(self, "useAutoSmooth")
        box.prop(self, "maxSubdivs")
        box.prop(self, "useInstancing")
        box.prop(self, "useScaleEyeMoisture")
        box.prop(self, "onFaceMaps")
        box.prop(self, "useSimulation")

        col = split.column()
        box = col.box()
        box.label(text = "Rigging")
        box.prop(self, "useArmature")
        box.prop(self, "useQuaternions")
        box.prop(self, "useLockLoc")
        box.prop(self, "useLimitLoc")
        box.prop(self, "useLockRot")
        box.prop(self, "useLimitRot")
        box.prop(self, "useInheritScale")
        box.prop(self, "displayLimitRot")
        box.prop(self, "useBoneColors")

        box = col.box()
        box.label(text = "Objects")
        box.prop(self, "showHiddenObjects")
        box.prop(self, "ignoreHiddenObjects")
        box.prop(self, "useBakedLocations")

        box = col.box()
        box.label(text = "Debugging")
        box.prop(self, "zup")
        box.prop(self, "unflipped")
        box.prop(self, "useDump")
        box.prop(self, "usePruneNodes")
        box.prop(self, "keepTriaxWeights")
        box.prop(self, "useTriaxApply")

        col = split.column()
        box = col.box()
        box.label(text = "Morphs")
        box.prop(self, "useStrengthAdjusters")
        box.prop(self, "useMakeHiddenSliders")
        box.prop(self, "useBakedMorphs")
        box.prop(self, "useDazLimits")
        box.prop(self, "sliderMultiplier")
        box.prop(self, "showFinalProps")
        box.prop(self, "showUsedPropsOnly")
        box.prop(self, "showInTerminal")
        box.prop(self, "useShapeCats")
        box.prop(self, "useMeshDrivers")
        box.prop(self, "useMuteDrivers")
        box.prop(self, "ercMethod")
        box.prop(self, "useStripCategory")
        box.prop(self, "useModifiedMesh")
        box.prop(self, "useDefaultDrivers")
        box.prop(self, "useOptimizeJcms")

        box = col.box()
        box.label(text = "Presets")
        box.prop(self, "author")
        box.prop(self, "email")
        box.prop(self, "website")

        col = split.column()
        box = col.box()
        box.label(text = "Materials")
        box.prop(self, "materialMethod")
        box.prop(self, "sssMethod")
        box.prop(self, "displacement_method")
        box.prop(self, "skinMethod")
        box.prop(self, "viewportColors")
        box.prop(self, "useWorld")
        box.prop(self, "useMaterialsByIndex")
        box.prop(self, "useMaterialsByName")
        if bpy.app.version < (3,4,0):
            box.prop(self, "useFakeCaustics")
        box.prop(self, "imageInterpolation")
        box.prop(self, "useUnusedTextures")
        box.prop(self, "useShellDrivers")
        box.prop(self, "useLayeredInflu")
        box.prop(self, "useLayeredShells")
        box.prop(self, "handleRenderSettings")
        box.prop(self, "handleLightSettings")
        box.separator()
        box.prop(self, "useDisplacement")
        box.prop(self, "useEmission")
        box.prop(self, "useVolume")
        box.prop(self, "useGhostLights")
        box.prop(self, "bumpMultiplier")


    def run(self, context):
        GS.fromDialog(self)
        GS.saveSettings(context)

    def invoke(self, context, event):
        global theGlobalDialog
        GS.getSettingsDir(context)
        theGlobalDialog = self
        GS.toDialog(self)
        wm = context.window_manager
        wm.invoke_props_dialog(self, width=1280)
        return {'RUNNING_MODAL'}


#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SetSilentMode,
    DAZ_OT_ScanAbsolutePaths,
    DAZ_OT_AddContentDir,
    DAZ_OT_AddMDLDir,
    DAZ_OT_AddCloudDir,
    DAZ_OT_LoadFactorySettings,
    DAZ_OT_LoadRootPaths,
    DAZ_OT_AddContentDirs,
    DAZ_OT_SaveSettingsFile,
    DAZ_OT_LoadSettingsFile,
    DAZ_OT_UpdateSettings,
    DAZ_OT_GlobalSettings,

    ErrorOperator
]

def getRootEnums(scn, context):
    return [(folder,folder,folder) for folder in GS.getDazPaths()]

def register():
    bpy.types.Scene.DazPreferredRoot = EnumProperty(
        items = getRootEnums,
        name = "Preferred Root Directory",
        description = "Preferred root directory used by some import tools")

    # Object properties

    bpy.types.Object.DazId = StringProperty(
        name = "ID",
        default = "")

    bpy.types.Object.DazUrl = StringProperty(
        name = "URL",
        default = "")

    bpy.types.Object.DazScene = StringProperty(
        name = "Scene",
        default = "")

    bpy.types.Object.DazRig = StringProperty(
        name = "Rig Type",
        default = "")

    bpy.types.Object.DazMesh = StringProperty(
        name = "Mesh Type",
        default = "")

    bpy.types.Object.DazScale = FloatProperty(
        name = "Unit Scale",
        default = 0.01,
        precision = 4)

    bpy.types.Material.DazScale = FloatProperty(default = 0)

    #bpy.types.Object.DazUnits = StringProperty(default = "")
    #bpy.types.Object.DazExpressions = StringProperty(default = "")
    #bpy.types.Object.DazVisemes = StringProperty(default = "")
    #bpy.types.Object.DazBodies = StringProperty(default = "")
    #bpy.types.Object.DazFlexions = StringProperty(default = "")
    #bpy.types.Object.DazCorrectives = StringProperty(default = "")

    bpy.types.Object.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.PoseBone.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.PoseBone.DazAxes = IntVectorProperty(size=3, default=(0,1,2))
    bpy.types.PoseBone.DazFlips = IntVectorProperty(size=3, default=(1,1,1))
    bpy.types.Object.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazCenter = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazAngle = FloatProperty(default=0)
    bpy.types.Bone.DazNormal = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazTranslation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazRotation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazRestRotation = FloatVectorProperty(size=3, default=(0,0,0))

    bpy.types.PoseBone.DazRotLocks = BoolVectorProperty(
        name = "Rotation Locks",
        size = 3,
        default = FFalse
    )

    bpy.types.PoseBone.DazLocLocks = BoolVectorProperty(
        name = "Location Locks",
        size = 3,
        default = FFalse
    )

    bpy.types.PoseBone.DazHeadLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.DazTailLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.HdOffset = bpy.props.FloatVectorProperty(size=3, default=(0,0,0))

    bpy.types.Armature.DazExtraFaceBones = BoolProperty(default = False)
    bpy.types.Armature.DazExtraDrivenBones = BoolProperty(default = False)

    bpy.types.Object.DazHasLocLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasLocLimits = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLimits = BoolProperty(default=False)

    bpy.types.Material.DazShader = StringProperty(default='NONE')

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

