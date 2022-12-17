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

#-------------------------------------------------------------
#   Global settings
#-------------------------------------------------------------

class GlobalSettings:

    def __init__(self):
        from sys import platform

        self.contentDirs = [
            self.fixPath("~/Documents/DAZ 3D/Studio/My Library"),
            "C:/Users/Public/Documents/My DAZ 3D Library",
        ]
        self.mdlDirs = [
            "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray",
        ]
        self.cloudDirs = []
        self.errorPath = self.fixPath("~/Documents/daz_importer_errors.txt")
        self.scanPath = self.fixPath("~/Documents/Scanned DAZ Database")
        self.settingsPath = self.fixPath("~/import-daz-settings-28x.json")
        self.absScanPath = self.fixPath("~/import_daz_scanned_absolute_paths.json")
        self.rootPaths = []
        self.absPaths = {}

        self.unitScale = 0.01
        self.verbosity = 2
        self.silentMode = False
        self.useDump = False
        self.zup = True
        self.unflipped = False
        self.useMakeHiddenSliders = False
        self.showHiddenObjects = False
        self.useIgnoreHiddenObjects = False

        self.materialMethod = 'SELECT'
        if bpy.app.version < (3,0,0):
            self.sssMethod = 'RANDOM_WALK'
        else:
            self.sssMethod = 'RANDOM_WALK_FIXED_RADIUS'
        self.viewportColors = 'GUESS'
        self.useQuaternions = False
        self.caseSensitivePaths = (platform not in ['win32', 'darwin'])
        self.rescanOnChange = True
        self.shellMethod = 'MATERIAL'
        self.usePruneNodes = True

        self.bumpFactor = 1.0
        self.useFakeCaustics = True
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"
        self.useSssSkin = False
        self.useSssFix = False
        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.useWorld = 'DOME'
        self.useLowerResFolders = True
        self.materialsByIndex = False
        self.imageInterpolation = 'Cubic'
        self.useGhostLight = False

        self.useStrengthAdjusters = False
        self.customMin = -1.0
        self.customMax = 1.0
        self.morphMultiplier = 1.0
        self.finalLimits = 'DAZ'
        self.sliderLimits = 'DAZ'
        self.showFinalProps = False
        self.showInTerminal = True
        self.useShapekeys = True
        self.useERC = False
        self.useStripCategory = False
        self.useModifiedMesh = False

        self.useArmature = True
        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.useInheritScale = False
        self.displayLimitRot = False
        self.useConnectClose = False

        self.useInstancing = True
        self.useHairGuides = False
        self.useHighDef = True
        self.keepBaseMesh = False
        self.useMultires = True
        self.useMultiUvLayers = True
        self.useMultiShapes = True
        self.useHDArmature = True
        self.useAutoSmooth = True
        self.maxSubdivs = 4
        self.useSimulation = True
        self.useScaleEyeMoisture = True
        self.onFaceMaps = 'NEVER'


    def getSSSMethod(self):
        if bpy.app.version < (3,0,0) and self.sssMethod == 'RANDOM_WALK_FIXED_RADIUS':
            return 'RANDOM_WALK'
        else:
            return self.sssMethod


    def defaultInherit(self):
        return ('FULL' if self.useInheritScale else 'NONE')


    SceneTable = {
        # General
        "DazUnitScale" : "unitScale",
        "DazVerbosity" : "verbosity",
        "DazErrorPath" : "errorPath",
        "DazScanPath" : "scanPath",
        "DazAbsScanPath" : "absScanPath",
        "DazCaseSensitivePaths" : "caseSensitivePaths",
        "DazRescanOnChange" : "rescanOnChange",

        # Debugging
        "DazDump" : "useDump",
        "DazZup" : "zup",
        "DazMakeHiddenSliders" : "useMakeHiddenSliders",
        "DazShowHiddenObjects" : "showHiddenObjects",
        "DazIgnoreHiddenObjects" : "useIgnoreHiddenObjects",
        "DazShellMethod" : "shellMethod",
        "DazPruneNodes" : "usePruneNodes",

        # Materials
        "DazMaterialMethod" : "materialMethod",
        "DazSSSMethod" : "sssMethod",
        "DazViewportColor" : "viewportColors",
        "DazUseWorld" : "useWorld",
        "DazLowerResFolders" : "useLowerResFolders",
        "DazMaterialsByIndex" : "materialsByIndex",
        "DazBumpFactor" : "bumpFactor",
        "DazFakeCaustics" : "useFakeCaustics",
        "DazHandleRenderSettings" : "handleRenderSettings",
        "DazHandleLightSettings" : "handleLightSettings",
        "DazUseSssSkin" : "useSssSkin",
        "DazUseSssFix" : "useSssFix",
        "DazUseDisplacement" : "useDisplacement",
        "DazUseEmission" : "useEmission",
        "DazUseReflection" : "useReflection",
        "DazGhostLights" : "useGhostLight",
        "DazImageInterpolation" : "imageInterpolation",

        # Properties
        "DazStrengthAdjusters" : "useStrengthAdjusters",
        "DazCustomMin" : "customMin",
        "DazCustomMax" : "customMax",
        "DazMorphMultiplier" : "morphMultiplier",
        "DazFinalLimits" : "finalLimits",
        "DazSliderLimits" : "sliderLimits",
        "DazShowFinalProps" : "showFinalProps",
        "DazShowInTerminal" : "showInTerminal",
        "DazUseShapekeys" : "useShapekeys",
        "DazUseERC" : "useERC",
        "DazStripCategory" : "useStripCategory",
        "DazUseModifiedMesh" : "useModifiedMesh",

        # Rigging
        "DazUseArmature" : "useArmature",
        "DazUnflipped" : "unflipped",
        "DazUseQuaternions" : "useQuaternions",
        "DazConnectClose" : "useConnectClose",
        "DazUseLockLoc" : "useLockLoc",
        "DazUseLimitLoc" : "useLimitLoc",
        "DazUseLockRot" : "useLockRot",
        "DazUseLimitRot" : "useLimitRot",
        "DazInheritScale" : "useInheritScale",
        "DazDisplayLimitRot" : "displayLimitRot",

        # Meshes
        "DazUseInstancing" : "useInstancing",
        "DazHairGuides" : "useHairGuides",
        "DazHighdef" : "useHighDef",
        "DazKeepBaseMesh" : "keepBaseMesh",
        "DazHDArmature" : "useHDArmature",
        "DazMultires" : "useMultires",
        "DazMultiUvLayers" : "useMultiUvLayers",
        "DazUseAutoSmooth" : "useAutoSmooth",
        "DazMaxSubdivs" : "maxSubdivs",
        "DazSimulation" : "useSimulation",
        "DazScaleEyeMoisture" : "useScaleEyeMoisture",
        "DazOnFaceMaps" : "onFaceMaps",
    }

    def fixPath(self, path):
        filepath = os.path.expanduser(path).replace("\\", "/")
        return filepath.rstrip("/ ")


    def getDazPaths(self):
        paths = self.contentDirs + self.mdlDirs + self.cloudDirs
        paths = [bpy.path.resolve_ncase(path) for path in paths]
        paths = [path for path in paths if os.path.exists(path)]
        return paths


    def fromScene(self, scn):
        def differ(list1, list2):
            if len(list1) != len(list2):
                return True
            for elt1,elt2 in zip(list1, list2):
                if elt1 != elt2:
                    return True
            return False

        caseOld = self.caseSensitivePaths
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(scn, prop)
                setattr(self, key, value)
            else:
                print("MIS", prop, key)
        contentOld = self.contentDirs
        mdlOld = self.mdlDirs
        cloudOld = self.cloudDirs
        self.contentDirs = self.pathsFromScene(scn.DazContentDirs)
        self.mdlDirs = self.pathsFromScene(scn.DazMDLDirs)
        self.cloudDirs = self.pathsFromScene(scn.DazCloudDirs)
        self.errorPath = self.fixPath(getattr(scn, "DazErrorPath"))
        self.scanPath = self.fixPath(getattr(scn, "DazScanPath"))
        self.absScanPath = self.fixPath(getattr(scn, "DazAbsScanPath"))
        self.eliminateDuplicates()
        if (differ(contentOld, self.contentDirs) or
            differ(mdlOld, self.mdlDirs) or
            differ(cloudOld, self.cloudDirs) or
            caseOld != self.caseSensitivePaths):
            if self.caseSensitivePaths and self.rescanOnChange:
                self.scanAbsPaths()


    def pathsFromScene(self, pgs):
        paths = []
        for pg in pgs:
            path = self.fixPath(pg.name)
            if os.path.exists(path):
                paths.append(path)
            else:
                print("Skip non-existent path:", path)
        return paths


    def pathsToScene(self, paths, pgs):
        pgs.clear()
        for path in paths:
            pg = pgs.add()
            pg.name = self.fixPath(path)


    def toScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(self, key)
                try:
                    setattr(scn, prop, value)
                except TypeError:
                    print("Type Error", prop, key, value)
            else:
                print("MIS", prop, key)
        self.pathsToScene(self.contentDirs, scn.DazContentDirs)
        self.pathsToScene(self.mdlDirs, scn.DazMDLDirs)
        self.pathsToScene(self.cloudDirs, scn.DazCloudDirs)
        path = self.fixPath(self.errorPath)
        setattr(scn, "DazErrorPath", path)
        path = self.fixPath(self.scanPath)
        setattr(scn, "DazScanPath", path)
        path = self.fixPath(self.absScanPath)
        setattr(scn, "DazAbsScanPath", path)


    def load(self, filepath):
        from .fileutils import openSettingsFile
        struct = openSettingsFile(filepath)
        if struct:
            print("Load settings from", filepath)
            self.readDazSettings(struct)


    def readDazSettings(self, struct):
        if "daz-settings" in struct.keys():
            settings = struct["daz-settings"]
            for prop,value in settings.items():
                if prop in self.SceneTable.keys():
                    key = self.SceneTable[prop]
                    setattr(self, key, value)
            self.contentDirs = self.readSettingsDirs("DazPath", settings)
            self.contentDirs += self.readSettingsDirs("DazContent", settings)
            self.mdlDirs = self.readSettingsDirs("DazMDL", settings)
            self.cloudDirs = self.readSettingsDirs("DazCloud", settings)
            self.eliminateDuplicates()
        else:
            raise DazError("Not a settings file   :\n'%s'" % filepath)


    def readSettingsDirs(self, prefix, settings):
        paths = []
        n = len(prefix)
        pathlist = [(key, path) for key,path in settings.items() if key[0:n] == prefix]
        pathlist.sort()
        for _prop,path in pathlist:
            path = self.fixPath(path)
            if os.path.exists(path):
                paths.append(path)
            else:
                print("No such path:", path)
        return paths


    def eliminateDuplicates(self):
        content = dict([(path,True) for path in self.contentDirs])
        mdl = dict([(path,True) for path in self.mdlDirs])
        cloud = dict([(path,True) for path in self.cloudDirs])
        for path in self.mdlDirs + self.cloudDirs:
            if path in content.keys():
                print("Remove duplicate path: %s" % path)
                del content[path]
        self.contentDirs = list(content.keys())
        self.mdlDirs = list(mdl.keys())
        self.cloudDirs = list(cloud.keys())


    def readDazPaths(self, struct, btn):
        self.contentDirs = []
        if btn.useContent:
            self.contentDirs = self.readAutoDirs("content", struct)
            self.contentDirs += self.readAutoDirs("builtin_content", struct)
        self.mdlDirs = []
        if btn.useMDL:
            self.mdlDirs = self.readAutoDirs("builtin_mdl", struct)
            self.mdlDirs += self.readAutoDirs("mdl_dirs", struct)
        self.cloudDirs = []
        if btn.useCloud:
            self.cloudDirs = self.readCloudDirs("cloud_content", struct)
        self.eliminateDuplicates()


    def readAutoDirs(self, key, struct):
        paths = []
        if key in struct.keys():
            folders = struct[key]
            if not isinstance(folders, list):
                folders = [folders]
            for path in folders:
                path = self.fixPath(path)
                if os.path.exists(path):
                    paths.append(path)
                else:
                    print("Path does not exist", path)
        return paths


    def readCloudDirs(self, key, struct):
        paths = []
        if key in struct.keys():
            folder = struct[key]
            if isinstance(folder, list):
                folder = folder[0]
            folder = self.fixPath(folder)
            if os.path.exists(folder):
                cloud = os.path.join(folder, "data", "cloud")
                if os.path.exists(cloud):
                    for file in os.listdir(cloud):
                        if file != "meta":
                            path = self.fixPath(os.path.join(cloud, file))
                            if os.path.isdir(path):
                                paths.append(path)
                            else:
                                print("Folder does not exist", folder)
        return paths


    def saveDirs(self, paths, prefix, struct):
        for n,path in enumerate(paths):
            struct["%s%03d" % (prefix, n+1)] = self.fixPath(path)


    def save(self, filepath):
        from .load_json import saveJson
        struct = {}
        for prop,key in self.SceneTable.items():
            value = getattr(self, key)
            if (isinstance(value, int) or
                isinstance(value, float) or
                isinstance(value, bool) or
                isinstance(value, str)):
                struct[prop] = value
        self.saveDirs(self.contentDirs, "DazContent", struct)
        self.saveDirs(self.mdlDirs, "DazMDL", struct)
        self.saveDirs(self.cloudDirs, "DazCloud", struct)
        filepath = os.path.expanduser(filepath)
        filepath = os.path.splitext(filepath)[0] + ".json"
        saveJson({"daz-settings" : struct}, filepath)
        print("Settings file %s saved" % filepath)


    def loadDefaults(self):
        self.load(self.settingsPath)


    def saveDefaults(self):
        self.save(self.settingsPath)


    def setRootPaths(self):
        from .error import DazError
        self.rootPaths = []
        for path in self.getDazPaths():
            if path:
                path = bpy.path.resolve_ncase(path)
                if not os.path.exists(path):
                    msg = ("The DAZ library path\n" +
                           "%s          \n" % path +
                           "does not exist. Check and correct the\n" +
                           "Paths to DAZ library section in the Settings panel." +
                           "For more details see\n" +
                           "http://diffeomorphic.blogspot.se/p/settings-panel_17.html.       ")
                    print(msg)
                    raise DazError(msg)
                else:
                    self.rootPaths.append(path)
                    if os.path.isdir(path):
                        for fname in os.listdir(path):
                            if "." not in fname:
                                numname = "".join(fname.split("_"))
                                if numname.isdigit():
                                    subpath = "%s/%s" % (path, fname)
                                    self.rootPaths.append(subpath)


    def scanAbsPaths(self):
        def scanPath(folder, path):
            lpath = path.lower()
            if lpath not in self.absPaths.keys():
                self.absPaths[lpath] = [folder]
            else:
                self.absPaths[lpath].append(folder)
            for file in os.listdir(folder):
                nfolder = "%s/%s" % (folder, file)
                if os.path.isdir(nfolder):
                    npath = "%s/%s" % (path, file)
                    scanPath(nfolder, npath)

        from .load_json import saveJson
        self.absPaths = {}
        for path in self.getDazPaths():
            print("Scanning", path)
            scanPath(path, "")
        struct = {
            "type" : "scanned_absolute_paths",
            "absolute_paths" : self.absPaths,
        }
        saveJson(struct, self.absScanPath)
        print("Scanned paths saved to %s" % self.absScanPath)


    def loadAbsPaths(self):
        self.absPaths = {}
        if os.path.exists(self.absScanPath):
            from .load_json import loadJson
            struct = loadJson(self.absScanPath)
            if struct.get("type") == "scanned_absolute_paths":
                self.absPaths = struct.get("absolute_paths", {})
                print("Absolute paths loaded from %s" % self.absScanPath)


    def getAbsPath(self, path):
        if self.caseSensitivePaths:
            folder = os.path.dirname(path)
            file = os.path.basename(path)
            lfile = file.lower()
            folders = self.absPaths.get(folder.lower(), [])
            for folder in folders:
                lfiles = [file.lower() for file in os.listdir(folder)]
                if lfile in lfiles:
                    return "%s/%s" % (folder, file)
        else:
            for folder in self.getDazPaths():
                filepath = "%s/%s" % (folder, path)
                filepath = filepath.replace("//", "/")
                if os.path.exists(filepath):
                    return filepath
                words = filepath.rsplit("/", 2)
                if len(words) == 3 and words[1].lower() == "hiddentemp":
                    filepath = "%s/%s" % (words[0], words[2])
                    if filepath:
                        return filepath
        return ""


    def getRelativePath(self, filepath):
        path = os.path.normpath(bpy.path.abspath(filepath)).replace("\\", "/")
        lpath = path.lower()
        for root in self.getDazPaths():
            n = len(root)
            if lpath[0:n] == root.lower():
                return path[n:]
        return filepath.replace("\\", "/")

#-------------------------------------------------------------
#   Local settings
#-------------------------------------------------------------

class LocalSettings:
    def __init__(self):
        self.theMessage = ""
        self.theErrorLines = []
        self.theFilePaths = []
        self.theDazPaths = []
        self.theAssets = {}
        self.theOtherAssets = {}
        self.theSources = {}
        self.theTrace = []

        self.scale = 0.1
        self.materialMethod = 'EXTENDED_PRINCIPLED'
        self.skinColor = None
        self.clothesColor = None
        self.fitFile = False
        self.autoMaterials = True
        self.morphStrength = 1.0

        self.useNodes = False
        self.useGeometries = False
        self.useImages = False
        self.useMaterials = False
        self.useModifiers = False
        self.useMorph = False
        self.useMorphOnly = False
        self.useFormulas = False
        self.useHDObjects = False
        self.useArmature = GS.useArmature
        self.applyMorphs = False
        self.useAnimations = False
        self.useUV = False
        self.useWorld = 'NEVER'

        self.collection = None
        self.hdcollection = None
        self.refColl = None
        self.refObjects = {}
        self.fps = 30
        self.integerFrames = True
        self.mappingNodes = []
        self.missingAssets = {}
        self.hasInstanceChildren = {}
        self.hdFailures = []
        self.hdWeights = []
        self.hdUvMissing = []
        self.hdUvMismatch = []
        self.partialMaterials = []
        self.triax = {}
        self.legacySkin = []
        self.invalidMeshes = []
        self.deflectors = {}
        self.materials = {}
        self.images = {}
        self.textures = {}
        self.gammas = {}
        self.customShapes = []
        self.singleUser = False
        self.scene = ""
        self.render = None
        self.hiddenMaterial = None
        self.shaders = {}
        self.targetCharacter = None

        self.nViewChildren = 0
        self.nRenderChildren = 0
        self.hairMaterialMethod = 'HAIR_BSDF'
        self.useSkullGroup = False

        self.usedFeatures = {
            "Bounces" : True,
            "Diffuse" : False,
            "Glossy" : False,
            "Transparent" : False,
            "SSS" : False,
            "Volume" : False,
        }

        self.rigname = None
        self.rigs = { None : [] }
        self.meshes = { None : [] }
        self.objects = { None : [] }
        self.hairs = { None : [] }
        self.hdmeshes = { None : [] }
        self.warning = False
        self.returnValue = {}


    def __repr__(self):
        string = "<Local Settings"
        for key in dir(self):
            if key[0] != "_":
                #attr = getattr(self, key)
                string += "\n  %s : %s" % (key, 0)
        return string + ">"


    def reset(self):
        GS.setRootPaths()
        self.useStrict = False
        self.scene = ""


    def fixMappingNodes(self):
        for node,data in self.mappingNodes:
            dx,dy,sx,sy,rz = data
            node.inputs["Location"].default_value = (dx,dy,0)
            node.inputs["Rotation"].default_value = (0,0,rz)
            node.inputs["Scale"].default_value = (sx,sy,1)


    def getMaterialSettings(self, btn):
        if GS.materialMethod == 'SELECT':
            self.materialMethod = btn.materialMethod
        else:
            self.materialMethod = GS.materialMethod
        if self.materialMethod  == 'BSDF':
            self.hairMaterialMethod = 'HAIR_BSDF'
        else:
            self.hairMaterialMethod = 'PRINCIPLED'
        self.skinColor = btn.skinColor
        self.clothesColor = btn.clothesColor


    def forImport(self, btn):
        self.__init__()
        self.reset()
        self.scale = GS.unitScale
        self.useNodes = True
        self.useGeometries = True
        self.useImages = True
        self.useMaterials = True
        self.useModifiers = True
        self.useUV = True
        self.useWorld = GS.useWorld

        self.getMaterialSettings(btn)
        self.useStrict = True
        self.singleUser = True
        if btn.fitMeshes == 'SHARED':
            self.singleUser = False
        elif btn.fitMeshes == 'UNIQUE':
            pass
        elif btn.fitMeshes == 'MORPHED':
            self.useMorph = True
            self.morphStrength = btn.morphStrength
        elif btn.fitMeshes == 'DBZFILE':
            self.fitFile = True


    def forAnimation(self, btn, ob):
        self.__init__()
        self.reset()
        self.scale = ob.DazScale
        self.useNodes = True
        if hasattr(btn, "fps"):
            self.fps = btn.fps
            self.integerFrames = btn.integerFrames


    def forMorphLoad(self, ob):
        self.__init__()
        self.reset()
        if ob:
            self.scale = ob.DazScale
        self.useMorph = True
        self.useMorphOnly = True
        self.useFormulas = True
        self.applyMorphs = False
        self.useModifiers = True


    def forUV(self, ob):
        self.__init__()
        self.reset()
        self.scale = ob.DazScale
        self.useUV = True


    def forMaterial(self, btn, ob):
        self.__init__()
        self.reset()
        self.scale = ob.DazScale
        self.useImages = True
        self.useMaterials = True
        self.useAnimations = True
        self.getMaterialSettings(btn)


    def forEngine(self):
        self.__init__()
        self.reset()


GS = GlobalSettings()
LS = LocalSettings()
LS.theTrace = []

