# Copyright (c) 2016-2021, Thomas Larsson
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
from . import globvars as G

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
        self.settingsPath = self.fixPath("~/import-daz-settings-28x.json")
        self.rootPath = self.fixPath("~/import-daz-paths.json")

        self.unitScale = 0.01
        self.verbosity = 2
        self.useDump = False
        self.zup = True
        self.unflipped = False
        self.useMakeHiddenSliders = False
        self.showHiddenObjects = False

        if bpy.app.version < (3,0,0):
            self.sssMethod = 'RANDOM_WALK'
        else:
            self.sssMethod = 'RANDOM_WALK_FIXED_RADIUS'
        self.viewportColors = 'GUESS'
        self.useQuaternions = False
        self.caseSensitivePaths = (platform != 'win32')
        self.mergeShells = True
        self.pruneNodes = True

        self.bumpFactor = 1.0
        self.useFakeCaustics = True
        self.useFakeTranslucencyTexture = False
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"
        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.useVolume = True
        self.useWorld = 'DOME'
        self.reuseMaterials = False
        self.hairMaterialMethod = 'HAIR_BSDF'
        self.imageInterpolation = 'Cubic'

        self.useStrengthAdjusters = False
        self.customMin = -1.0
        self.customMax = 1.0
        self.morphMultiplier = 1.0
        self.finalLimits = 'DAZ'
        self.sliderLimits = 'DAZ'
        self.showFinalProps = False
        self.useShapekeys = True
        self.useERC = False
        self.useStripCategory = False
        self.useModifiedMesh = False

        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.displayLimitRot = False
        self.useConnectClose = False

        self.useInstancing = True
        self.useHighDef = True
        self.useMultires = True
        self.useMultiUvLayers = True
        self.useMultiShapes = True
        self.useAutoSmooth = True
        self.useSimulation = True
        self.useScaleEyeMoisture = True


    def getSSSMethod(self):
        if bpy.app.version < (3,0,0) and self.sssMethod == 'RANDOM_WALK_FIXED_RADIUS':
            return 'RANDOM_WALK'
        else:
            return self.sssMethod


    SceneTable = {
        # General
        "DazUnitScale" : "unitScale",
        "DazVerbosity" : "verbosity",
        "DazErrorPath" : "errorPath",
        "DazCaseSensitivePaths" : "caseSensitivePaths",

        # Debugging
        "DazDump" : "useDump",
        "DazZup" : "zup",
        "DazMakeHiddenSliders" : "useMakeHiddenSliders",
        "DazShowHiddenObjects" : "showHiddenObjects",
        "DazMergeShells" : "mergeShells",
        "DazPruneNodes" : "pruneNodes",

        # Materials
        # "DazMaterialMethod" : "materialMethod",
        "DazSSSMethod" : "sssMethod",
        "DazHairMaterialMethod" : "hairMaterialMethod",
        "DazViewportColor" : "viewportColors",
        "DazUseWorld" : "useWorld",
        "DazReuseMaterials" : "reuseMaterials",
        "DazBumpFactor" : "bumpFactor",
        "DazFakeCaustics" : "useFakeCaustics",
        "DazFakeTranslucencyTexture" : "useFakeTranslucencyTexture",
        "DazHandleRenderSettings" : "handleRenderSettings",
        "DazHandleLightSettings" : "handleLightSettings",
        "DazUseDisplacement" : "useDisplacement",
        "DazUseEmission" : "useEmission",
        "DazUseReflection" : "useReflection",
        "DazUseVolume" : "useVolume",
        "DazImageInterpolation" : "imageInterpolation",

        # Properties
        "DazStrengthAdjusters" : "useStrengthAdjusters",
        "DazCustomMin" : "customMin",
        "DazCustomMax" : "customMax",
        "DazMorphMultiplier" : "morphMultiplier",
        "DazFinalLimits" : "finalLimits",
        "DazSliderLimits" : "sliderLimits",
        "DazShowFinalProps" : "showFinalProps",
        "DazUseShapekeys" : "useShapekeys",
        "DazUseERC" : "useERC",
        "DazStripCategory" : "useStripCategory",
        "DazUseModifiedMesh" : "useModifiedMesh",

        # Rigging
        "DazUnflipped" : "unflipped",
        "DazUseQuaternions" : "useQuaternions",
        "DazConnectClose" : "useConnectClose",
        "DazUseLockLoc" : "useLockLoc",
        "DazUseLimitLoc" : "useLimitLoc",
        "DazUseLockRot" : "useLockRot",
        "DazUseLimitRot" : "useLimitRot",
        "DazDisplayLimitRot" : "displayLimitRot",

        # Meshes
        "DazUseInstancing" : "useInstancing",
        "DazHighdef" : "useHighDef",
        "DazMultires" : "useMultires",
        "DazMultiUvLayers" : "useMultiUvLayers",
        "DazUseAutoSmooth" : "useAutoSmooth",
        "DazSimulation" : "useSimulation",
        "DazScaleEyeMoisture" : "useScaleEyeMoisture",
    }

    def fixPath(self, path):
        filepath = os.path.expanduser(path).replace("\\", "/")
        return filepath.rstrip("/ ")


    def getDazPaths(self):
        paths = self.contentDirs + self.mdlDirs + self.cloudDirs
        return paths


    def fromScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(scn, prop)
                setattr(self, key, value)
            else:
                print("MIS", prop, key)
        self.contentDirs = self.pathsFromScene(scn.DazContentDirs)
        self.mdlDirs = self.pathsFromScene(scn.DazMDLDirs)
        self.cloudDirs = self.pathsFromScene(scn.DazCloudDirs)
        self.errorPath = self.fixPath(getattr(scn, "DazErrorPath"))
        self.eliminateDuplicates()


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

#-------------------------------------------------------------
#   Local settings
#-------------------------------------------------------------

class LocalSettings:
    def __init__(self):
        self.scale = 0.1
        self.materialMethod = 'BSDF'
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
        self.missingAssets = {}
        self.hasInstanceChildren = {}
        self.hdFailures = []
        self.hdWeights = []
        self.hdUvMissing = []
        self.partialMaterials = []
        self.legacySkin = []
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
        self.targetCharacter = None

        self.nViewChildren = 0
        self.nRenderChildren = 0
        self.hairMaterialMethod = GS.hairMaterialMethod
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
        from .asset import setDazPaths
        G.theTrace = []
        G.theAssets = {}
        G.theOtherAssets = {}
        G.theSources = {}
        setDazPaths()
        self.useStrict = False
        self.scene = ""


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

        self.materialMethod = btn.materialMethod
        self.skinColor = btn.skinColor
        self.clothesColor = btn.clothesColor

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
        self.materialMethod = btn.materialMethod
        self.skinColor = btn.skinColor
        self.clothesColor = btn.clothesColor


    def forEngine(self):
        self.__init__()
        self.reset()


GS = GlobalSettings()
LS = LocalSettings()
G.theTrace = []

