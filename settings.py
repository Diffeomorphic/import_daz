# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
from collections import OrderedDict
import bpy
from urllib.parse import quote, unquote

#-------------------------------------------------------------
#   Global settings
#-------------------------------------------------------------

class GlobalSettings:
    def __init__(self):
        if sys.platform == 'win32':
            self.settingsDir = self.fixPath("~/Documents/DAZ Importer")
            self.caseSensitivePaths = False
        elif sys.platform == 'darwin':
            self.settingsDir = self.fixPath("~/DAZ Importer")
            self.caseSensitivePaths = False
        else:
            self.settingsDir = self.fixPath("~/DAZ Importer")
            self.caseSensitivePaths = True

        self.errorFile = "daz_importer_errors.txt"
        self.scanFile = "Scanned DAZ Database"
        self.settingsFile = "import_daz_settings.json"

        self.contentDirs = [
            self.fixPath("~/Documents/DAZ 3D/Studio/My Library"),
            "C:/Users/Public/Documents/My DAZ 3D Library",
        ]
        self.mdlDirs = [
            "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray",
        ]
        self.cloudDirs = []
        self.oldPath = self.fixPath("~/import-daz-settings-28x.json")
        self.rootPaths = []

        self.onlyDbz = False
        self.scale = 0.01
        self.verbosity = 2
        self.rememberLastFolder = False
        self.silentMode = False
        self.useDump = False
        self.zup = True
        self.unflipped = False
        self.useMakeHiddenSliders = False
        self.showHiddenObjects = False
        self.ignoreHiddenObjects = False

        self.author = "Myself"
        self.email = ""
        self.website = ""

        self.materialMethod = 'SELECT'
        self.sssMethod = 'BURLEY'
        self.displacementMethod = 'BOTH'
        self.toonMethod = 'FREESTYLE'
        self.skinMethod = 'IRAY'
        self.viewportColors = 'GUESS'
        self.skinColor0 = 0.6
        self.skinColor1 = 0.4
        self.skinColor2 = 0.25
        self.skinColor3 = 1.0
        self.clothesColor0 = 0.09
        self.clothesColor1 = 0.01
        self.clothesColor2 = 0.015
        self.clothesColor3 = 1.0
        self.shellMethod = 'MATERIAL'
        self.usePruneNodes = True

        self.useFakeCaustics = False
        self.onRenderSettings = "UPDATE"
        self.onLightSettings = "WARN"
        self.useVolume = True
        self.useBump = True
        self.useNormalMap = True
        self.useDisplacement = True
        self.useEmission = True
        self.bumpMultiplier = 1.0
        self.worldMethod = 'DOME'
        self.useLowerResFolders = True
        self.useMaterialsByIndex = False
        self.useMaterialsByName = False
        self.imageInterpolation = 'Cubic'
        self.useGhostLights = False
        self.useUnusedTextures = False
        self.onHairMaterial = 'SMART'
        self.useShellDrivers = True
        self.useLayeredInflu = False
        self.useLayeredShells = True
        self.useStoreMaterialMapping = False

        self.onStrengthAdjusters = 'NONE'
        self.useDazLimits = True
        self.sliderMultiplier = 1.0
        self.showFinalProps = False
        self.showInTerminal = True
        self.driverRotationMode = 'NATIVE'
        self.ercMethod = 'NONE'
        self.useBakedMorphs = False
        self.useStripCategory = False
        self.useDefaultDrivers = True
        self.usePropDrivers = True
        self.onShapekeyDrivers = 'REGULAR'
        self.useRigidityAttributes = True
        self.useFaceGroupMasks = False

        self.useArmature = True
        self.useQuaternions = False
        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.useInheritScale = False
        self.displayLimitRot = False
        self.useBoneColors = True
        self.ignoreG9TwistBones = False

        self.useInstancing = True
        self.useHairGuides = False
        self.useHighDef = True
        self.useTriaxImprove = True
        self.useBulgeWeights = True
        self.keepTriaxWeights = False
        self.useTriaxApply = True
        self.useMultires = True
        self.useMultiShapes = True
        self.keepBaseMesh = True
        self.useHDArmature = True
        self.useSharpEdges = True
        self.maxSubdivs = 4
        self.useSimulation = True
        self.onScaleEyeMoisture = 'APPLY'


    def getSkinColor(self):
        return (self.skinColor0, self.skinColor1, self.skinColor2, self.skinColor3)

    def getClothesColor(self):
        return (self.clothesColor0, self.clothesColor1, self.clothesColor2, self.clothesColor3)

    def setSkinColor(self, color):
        self.skinColor0, self.skinColor1, self.skinColor2, self.skinColor3 = color

    def setClothesColor(self, color):
        self.clothesColor0, self.clothesColor1, self.clothesColor2, self.clothesColor3 = color


    def getSettingsDir(self, context):
        if context:
            name = __name__.rsplit(".", 1)[0]
            addon = context.preferences.addons.get(name)
            if addon and addon.preferences:
                prefs = addon.preferences
                if prefs:
                    self.settingsDir = self.fixPath(prefs.settingsDir)
                    print("Settings directory: %s" % self.settingsDir)


    def fixPath(self, path):
        filepath = os.path.expanduser(unquote(path)).replace("\\", "/")
        return filepath.rstrip("/ ")


    def getDazSettingsPath(self, file):
        return os.path.join(self.settingsDir, file)


    def getSettingsPath(self):
        return self.getDazSettingsPath(self.settingsFile)


    def getErrorPath(self):
        return self.getDazSettingsPath(self.errorFile)


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
                    print("TO", attr, value)
                    pass
        btn.skinColor = self.getSkinColor()
        btn.clothesColor = self.getClothesColor()


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
                attr not in ["contentDirs", "cloudDirs", "mdlDirs", "errorFile", "scanFile"]):
                setattr(self, attr, getattr(btn, attr))
        self.setSkinColor(btn.skinColor)
        self.setClothesColor(btn.clothesColor)
        self.contentDirs = getPaths(btn.contentDirs)
        self.mdlDirs = getPaths(btn.mdlDirs)
        self.cloudDirs = getPaths(btn.cloudDirs)
        self.errorFile = btn.errorFile
        self.scanFile = btn.scanFile
        self.eliminateDuplicates()


    def toggleMorphArmatures(self, scn):
        from .runtime.morph_armature import onFrameChangeDaz, unregister
        unregister()
        from .utils import dazRna
        if dazRna(scn).DazAutoMorphArmatures and self.ercMethod in ('ARMATURE', 'ALL'):
            bpy.app.handlers.frame_change_post.append(onFrameChangeDaz)


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

        from .load_json import loadJson
        struct = loadJson(filepath)
        if struct and "daz-settings" in struct.keys():
            print("Load settings from %s" % filepath)
            settings = struct["daz-settings"]
            for attr,value in settings.items():
                if hasattr(self, attr) and attr not in ["settingsDir"]:
                    if isinstance(value, (float, int, bool)):
                        setattr(self, attr, value)
                    elif isinstance(value, str):
                        setattr(self, attr, unquote(value))
                    elif attr.endswith("Color"):
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
            print("Settings loaded from %s" % filepath)
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


    def readDazPaths(self, struct, btn, useAll=False):
        self.contentDirs = []
        if useAll or btn.useContent:
            self.contentDirs = self.readAutoDirs("content", struct)
            self.contentDirs += self.readAutoDirs("builtin_content", struct)
        self.mdlDirs = []
        if useAll or btn.useMDL:
            self.mdlDirs = self.readAutoDirs("builtin_mdl", struct)
            self.mdlDirs += self.readAutoDirs("mdl_dirs", struct)
        self.cloudDirs = []
        if useAll or btn.useCloud:
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


    def saveSettings(self, context, filepath=None):
        def quoteString(string):
            return quote(string).replace("%20", " ").replace("%3A", ":")

        def saveDirs(paths, prefix, struct):
            for n,path in enumerate(paths):
                struct["%s%03d" % (prefix, n+1)] = quoteString(self.fixPath(path))

        from .load_json import saveJson
        self.getSettingsDir(context)
        if filepath is None:
            filepath = GS.getSettingsPath()
        struct = {}
        for attr in dir(self):
            value = getattr(self, attr)
            if attr[0] != "_":
                if isinstance(value, (int, float, bool)):
                    struct[attr] = value
                elif isinstance(value, str):
                    struct[attr] = quoteString(value)
        for attr in ["contentDirs", "mdlDirs", "cloudDirs"]:
            paths = []
            for path in getattr(self, attr):
                if path:
                    paths.append(quoteString(self.fixPath(path)))
            struct[attr] = paths
        filepath = os.path.expanduser(filepath)
        filepath = "%s.json" % os.path.splitext(filepath)[0]
        saveJson({"daz-settings" : struct}, filepath, strict=False)
        print("Settings file %s saved" % filepath)


    def loadDefaults(self):
        if not self.loadSettings(self.getSettingsPath(), False):
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


    def getAbsPaths(self, path):
        def findAbsPaths(folder, files, abspaths):
            if files:
                for file in os.listdir(folder):
                    if file.lower() == files[0]:
                        path = os.path.join(folder, file)
                        if files[1:]:
                            findAbsPaths(path, files[1:], abspaths)
                        else:
                            abspaths.append(path)

        if self.caseSensitivePaths:
            abspaths = []
            files = path.lower().replace("\\", "/").split("/")
            files = [file for file in files if file]
            for folder in self.getDazPaths():
                findAbsPaths(folder, files, abspaths)
            return abspaths
        else:
            abspaths = [
                ("%s/%s" % (folder, path)).replace("//", "/")
                for folder in self.getDazPaths()]
            return [abspath for abspath in abspaths if os.path.exists(abspath)]


    def getBasePath(self, abspath):
        for path in self.getDazPaths():
            if abspath.startswith(path):
                return path
        return ""


    def getAbsPath(self, ref):
        path = unquote(ref)
        if len(path) > 2 and path[0] == "/" and os.path.exists(path[1:]):
            # Absolute path
            return path[1:]
        elif self.caseSensitivePaths:
            abspaths = self.getAbsPaths(path)
            if abspaths:
                return abspaths[0]
        elif os.path.exists(path):
            return path
        else:
            for folder in self.getDazPaths():
                filepath = "%s/%s" % (folder, path)
                filepath = filepath.replace("//", "/")
                if os.path.exists(filepath):
                    return filepath
                words = filepath.rsplit("/", 2)
                if len(words) == 3 and words[1].lower() == "hiddentemp":
                    filepath = "%s/%s" % (words[0], words[2])
                    if filepath and os.path.exists(abspath):
                        return filepath
        if not path.startswith("name:/@selection"):
            from .error import reportError
            LS.missingAssets[ref] = True
            msg = ("Did not find path:" +
                   '\nPath: "%s"' % path +
                   '\nRef: "%s"' % ref +
                   "\nCase-sensitive paths: %s" % self.caseSensitivePaths)
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
        self.message = ""
        self.errorLines = []
        self.selection = []
        self.assets = {}
        self.otherAssets = {}
        self.sources = {}
        self.trace = []
        self.error = False
        self.activeObject = None

        self.materialMethod = 'EXTENDED_PRINCIPLED'
        self.skinColor = None
        self.clothesColor = None
        self.fitFile = False
        self.autoMaterials = True

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
        self.applyMorphs = False
        self.useAnimations = False
        self.useUV = False
        self.worldMethod = 'NEVER'

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
        self.hdMismatch = []
        self.hdUvMissing = []
        self.partialMaterials = []
        self.triax = {}
        self.otherRigBones = {}
        self.legacySkin = []
        self.invalidMeshes = []
        self.polyLines = {}
        self.rigidFollow = {}
        self.deflectors = {}
        self.materials = OrderedDict()
        self.images = {}
        self.protectedImages = {}
        self.protectedGroups = set()
        self.gammas = {}
        self.customShapes = []
        self.toons = []
        self.rimtoons = []
        self.distantLight = None
        self.shellUvs = {}
        self.singleUser = False
        self.mappingNodes = []
        self.scene = ""
        self.render = None
        self.hiddenMaterial = None
        self.shaders = {}
        self.targetCharacter = None
        self.headbones = {}
        self.tailbones = {}

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
        self.bakedMorphs = {}
        self.returnValue = {}

        if bpy.app.version < (4,0,0):
            if GS.sssMethod == 'RANDOM_WALK_SKIN':
                GS.sssMethod = 'RANDOM_WALK'
        else:
            if GS.sssMethod == 'RANDOM_WALK_FIXED_RADIUS':
                GS.sssMethod = 'RANDOM_WALK'


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
        GS.setSkinColor(btn.skinColor)
        GS.setClothesColor(btn.clothesColor)


    def forImport(self, btn):
        self.__init__()
        self.reset(btn)
        self.useNodes = True
        self.useGeometries = True
        self.useImages = True
        self.useMaterials = True
        self.useModifiers = True
        self.useFormulas = True
        self.useUV = True
        self.worldMethod = GS.worldMethod

        self.getMaterialSettings(btn)
        self.useStrict = True
        self.singleUser = True
        if btn.fitMeshes == 'SHARED':
            self.singleUser = False
        elif btn.fitMeshes == 'UNIQUE':
            pass
        elif btn.fitMeshes == 'MORPHED':
            self.useLoadBaked = True
        elif btn.fitMeshes == 'DBZFILE':
            self.fitFile = True


    def forAnimation(self, btn, ob):
        self.__init__()
        self.reset(btn)
        self.useNodes = True
        if hasattr(btn, "fps"):
            self.fps = btn.fps
            self.integerFrames = btn.integerFrames


    def forMorphLoad(self, ob):
        self.__init__()
        self.reset()
        self.useMorph = True
        self.useMorphOnly = True
        self.useFormulas = True
        self.applyMorphs = False
        self.useModifiers = True


    def forUV(self, ob):
        self.__init__()
        self.reset()
        self.useUV = True


    def forMaterial(self, btn):
        self.__init__()
        self.reset(btn)
        self.useImages = True
        self.useMaterials = True
        self.useAnimations = True
        self.getMaterialSettings(btn)


    def forShells(self, btn):
        self.__init__()
        self.reset(btn)
        self.useNodes = True
        self.useGeometries = True
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
        self.message = ""
        self.error = False



GS = GlobalSettings()
LS = LocalSettings()
ES = EasySettings()

