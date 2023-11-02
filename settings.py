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
import bpy
from urllib.parse import unquote

#-------------------------------------------------------------
#   Global settings
#-------------------------------------------------------------

class GlobalSettings:

    def __init__(self):
        if sys.platform == 'win32':
            self.defaultDir = self.fixPath("~/Documents/DAZ Importer")
            self.caseSensitivePaths = False
        elif sys.platform == 'darwin':
            self.defaultDir = self.fixPath("~/DAZ Importer")
            self.caseSensitivePaths = False
        else:
            self.defaultDir = self.fixPath("~/DAZ Importer")
            self.caseSensitivePaths = True

        self.contentDirs = [
            self.fixPath("~/Documents/DAZ 3D/Studio/My Library"),
            "C:/Users/Public/Documents/My DAZ 3D Library",
        ]
        self.mdlDirs = [
            "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray",
        ]
        self.cloudDirs = []
        self.errorPath = "%s/%s" % (self.defaultDir, "daz_importer_errors.txt")
        self.scanPath = "%s/%s" % (self.defaultDir, "Scanned DAZ Database")
        self.settingsPath = "%s/%s" % (self.defaultDir, "import_daz_settings.json")
        self.absScanPath = "%s/%s" % (self.defaultDir, "import_daz_scanned_absolute_paths.json")
        self.oldPath = self.fixPath("~/import-daz-settings-28x.json")
        self.rootPaths = []
        self.absPaths = {}

        self.unitScale = 0.01
        self.verbosity = 2
        self.rememberLastFolder = False
        self.silentMode = False
        self.useDump = False
        self.zup = True
        self.unflipped = False
        self.useMakeHiddenSliders = False
        self.useBakedMorphs = False
        self.showHiddenObjects = False
        self.useIgnoreHiddenObjects = False

        self.materialMethod = 'SELECT'
        self.sssMethod = 'BURLEY'
        self.viewportColors = 'GUESS'
        self.useQuaternions = False
        self.useDazOrientation = False
        self.useSubtractRestpose = True
        self.shellMethod = 'MATERIAL'
        self.usePruneNodes = True

        self.useFakeCaustics = False
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"
        self.useSssSkin = False
        self.useAltSss = False
        self.useVolume = True
        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.useWorld = 'DOME'
        self.useLowerResFolders = True
        self.useMaterialsByIndex = False
        self.useMaterialsByName = False
        self.imageInterpolation = 'Cubic'
        self.useGhostLight = False
        self.useUnusedTextures = False

        self.useStrengthAdjusters = 'NONE'
        self.customMin = -1.0
        self.customMax = 1.0
        self.morphMultiplier = 1.0
        self.finalLimits = 'DAZ'
        self.sliderLimits = 'DAZ'
        self.showFinalProps = False
        self.showInTerminal = True
        self.useShapekeys = True
        self.useMuteDrivers = False
        self.useERC = False
        self.useStripCategory = False
        self.useModifiedMesh = False
        self.useSubmeshes = True
        self.useDefaultDrivers = True
        self.useOptimizeJcms = False

        self.useArmature = True
        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.useInheritScale = False
        self.displayLimitRot = False

        self.useInstancing = True
        self.useHairGuides = False
        self.useHighDef = True
        self.useTriaxImprove = True
        self.useBulgeWeights = True
        self.keepTriaxWeights = False
        self.useTriaxApply = True
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


    def fixPath(self, path):
        filepath = os.path.expanduser(path).replace("\\", "/")
        return filepath.rstrip("/ ")


    def getDazPaths(self):
        paths = self.contentDirs + self.mdlDirs + self.cloudDirs
        paths = [bpy.path.resolve_ncase(path) for path in paths]
        paths = [path for path in paths if os.path.exists(path)]
        return paths


    def toDialog(self, btn):
        for attr in dir(self):
            value = getattr(self, attr)
            if attr in ["contentDirs", "cloudDirs", "mdlDirs"]:
                pgs = getattr(btn, attr)
                pgs.clear()
                for folder in value:
                    pg = pgs.add()
                    pg.name = folder
            elif attr[0] != "_":
                try:
                    setattr(btn, attr, value)
                except:
                    pass


    def fromDialog(self, btn):
        def getPaths(pgs):
            paths = []
            for pg in pgs:
                if pg.name:
                    path = self.fixPath(pg.name)
                    if os.path.exists(path):
                        paths.append(path)
                    else:
                        print("Skip non-existent path:", path)
            return paths

        for attr in dir(self):
            if (attr[0] != "_" and
                hasattr(btn, attr) and
                attr not in ["contentDirs", "cloudDirs", "mdlDirs", "errorPath", "scanPath", "absScanPath"]):
                setattr(self, attr, getattr(btn, attr))
        self.contentDirs = getPaths(btn.contentDirs)
        self.mdlDirs = getPaths(btn.mdlDirs)
        self.cloudDirs = getPaths(btn.cloudDirs)
        self.errorPath = self.fixPath(btn.errorPath)
        self.scanPath = self.fixPath(btn.scanPath)
        self.absScanPath = self.fixPath(btn.absScanPath)
        self.eliminateDuplicates()


    def toggleMorphArmatures(self, scn):
        from .runtime.morph_armature import onFrameChangeDaz, unregister
        unregister()
        if scn.DazAutoMorphArmatures and self.useERC:
            bpy.app.handlers.frame_change_post.append(onFrameChangeDaz)


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


    def loadSettings(self, filepath, strict=True):
        def readOldDirs(prefix, settings):
            n = len(prefix)
            paths = [(key, path) for key,path in settings.items() if key[0:n] == prefix]
            paths.sort()
            fixed = []
            for key,path in paths:
                path = self.fixPath(path)
                if os.path.exists(path):
                    fixed.append(path)
                else:
                    print("No such path:", path)
            return fixed

        def readNewDirs(key, settings):
            fixed = []
            for path in settings[key]:
                path = self.fixPath(path)
                if os.path.exists(path):
                    fixed.append(path)
                else:
                    print("No such path:", path)
            return fixed

        from .fileutils import openSettingsFile
        struct = openSettingsFile(filepath)
        if struct and "daz-settings" in struct.keys():
            print("Load settings from", filepath)
            settings = struct["daz-settings"]
            for attr,value in settings.items():
                if hasattr(self, attr) and isinstance(value, (float, int, bool, str)):
                    setattr(self, attr, value)
            if "contentDirs" in settings.keys():
                self.contentDirs = readNewDirs("contentDirs", settings)
                self.mdlDirs = readNewDirs("mdlDirs", settings)
                self.cloudDirs = readNewDirs("cloudDirs", settings)
            else:
                self.contentDirs = readOldDirs("DazPath", settings)
                self.contentDirs += readOldDirs("DazContent", settings)
                self.mdlDirs = readOldDirs("DazMDL", settings)
                self.cloudDirs = readOldDirs("DazCloud", settings)
            self.eliminateDuplicates()
            return True
        elif strict:
            from .error import DazError
            raise DazError("Not a settings file   :\n'%s'" % filepath)
        else:
            return False


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


    def saveSettings(self, filepath):
        def saveDirs(paths, prefix, struct):
            for n,path in enumerate(paths):
                struct["%s%03d" % (prefix, n+1)] = self.fixPath(path)

        from .load_json import saveJson
        struct = {}
        for attr in dir(self):
            value = getattr(self, attr)
            if attr[0] != "_" and isinstance(value, (int, float, bool, str)):
                struct[attr] = value
        for attr in ["contentDirs", "mdlDirs", "cloudDirs"]:
            paths = []
            for path in getattr(self, attr):
                if path:
                    paths.append(self.fixPath(path))
            struct[attr] = paths
        filepath = os.path.expanduser(filepath)
        filepath = "%s.json" % os.path.splitext(filepath)[0]
        saveJson({"daz-settings" : struct}, filepath, strict=False)
        print("Settings file %s saved" % filepath)


    def loadDefaults(self):
        if not self.loadSettings(self.settingsPath, False):
            self.loadSettings(self.oldPath, False)


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
        saveJson(struct, self.absScanPath, strict=False)
        print("Scanned paths saved to %s" % self.absScanPath)


    def loadAbsPaths(self):
        self.absPaths = {}
        if os.path.exists(self.absScanPath):
            from .load_json import loadJson
            struct = loadJson(self.absScanPath)
            if struct.get("type") == "scanned_absolute_paths":
                self.absPaths = struct.get("absolute_paths", {})
                print("Absolute paths loaded from %s" % self.absScanPath)


    def getAbsPath(self, ref):
        path = unquote(ref)
        if len(path) > 2 and path[0] == "/" and os.path.exists(path[1:]):
            # Absolute path
            return path[1:]
        elif os.path.exists(path):
            return path
        elif self.caseSensitivePaths:
            lfolder = os.path.dirname(path).lower()
            lfile = os.path.basename(path).lower()
            folders = self.absPaths.get(lfolder, [])
            for folder in folders:
                files = dict([(file.lower(),file) for file in os.listdir(folder)])
                file = files.get(lfile)
                if file:
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
        if not path.startswith("name:/@selection"):
            from .error import reportError
            LS.missingAssets[ref] = True
            msg = ("Did not find path:" +
                   '\nPath: "%s"' % path +
                   '\nRef: "%s"' % ref +
                   "\nCase-sensitive paths: %s" % self.caseSensitivePaths)
            if self.caseSensitivePaths:
                msg += ('\nFolder: "%s"' % lfolder +
                        "\nFolders:")
                for folder in folders:
                    msg += "\n  %s" % folder
            reportError(msg, trigger=(3,5))
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
        self.button = None
        self.boneCollections = {}
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
        self.useLoadBaked = False
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
        self.layeredGroups = {}
        self.missingAssets = {}
        self.hasInstanceChildren = {}
        self.hdFailures = []
        self.hdWeights = []
        self.hdUvMissing = []
        self.hdUvMismatch = []
        self.partialMaterials = []
        self.triax = {}
        self.otherRigBones = {}
        self.legacySkin = []
        self.invalidMeshes = []
        self.polyLines = {}
        self.deflectors = {}
        self.materials = {}
        self.images = {}
        self.protectedImages = {}
        self.layeredImages = {}
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
        self.bakedmorphs = {}
        self.warning = False
        self.returnValue = {}


    def __repr__(self):
        string = "<Local Settings"
        for key in dir(self):
            if key[0] != "_":
                #attr = getattr(self, key)
                string += "\n  %s : %s" % (key, 0)
        return string + ">"


    def reset(self, btn=None):
        GS.setRootPaths()
        self.useStrict = False
        self.scene = ""
        self.button = btn


    def getSettings(self):
        settings = {}
        for attr in dir(self):
            if attr[0] != "_":
                value = getattr(self, attr)
                if isinstance(value, (int, float, str, dict, list)):
                    settings[attr] = value
        return settings


    def restoreSettings(self, settings):
        for attr,value in settings.items():
            setattr(self, attr, value)


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
        self.reset(btn)
        self.scale = GS.unitScale
        self.useNodes = True
        self.useGeometries = True
        self.useImages = True
        self.useMaterials = True
        self.useModifiers = True
        self.useFormulas = True
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
            #self.useMorph = True
            self.useLoadBaked = True
            self.morphStrength = btn.morphStrength
        elif btn.fitMeshes == 'DBZFILE':
            self.fitFile = True


    def forAnimation(self, btn, ob):
        self.__init__()
        self.reset(btn)
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
        self.reset(btn)
        self.scale = ob.DazScale
        self.useImages = True
        self.useMaterials = True
        self.useAnimations = True
        self.getMaterialSettings(btn)


    def forEngine(self):
        self.__init__()
        self.reset()


class EasySettings:
    def __init__(self):
        self.easy = False



GS = GlobalSettings()
LS = LocalSettings()
LS.theTrace = []
ES = EasySettings()

