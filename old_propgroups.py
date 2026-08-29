# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .propgroups import *

def registerDazProperties():
    from .morphing import MS

    for morphset in MS.Morphsets:
        setattr(bpy.types.Object, "Daz%s" % morphset, CollectionProperty(type = DazTextGroup))
        setattr(bpy.types.Armature, "DazIndex%s" % morphset, IntProperty(default=0))

    bpy.types.Bone.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazTrueName = StringProperty()
    bpy.types.Bone.DazRigIndex = IntProperty(default=0)
    bpy.types.Bone.DazBoneParentRig = IntProperty(default=-1)

    bpy.types.PoseBone.DazRotMode = StringProperty(default='XYZ')
    bpy.types.PoseBone.DazAxes = IntVectorProperty(size=3, default=(0,1,2))
    bpy.types.PoseBone.DazFlips = IntVectorProperty(size=3, default=(1,1,1))
    bpy.types.PoseBone.DazTranslation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazRotation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazGeneralScale = FloatProperty(default=1.0)
    bpy.types.PoseBone.DazRestRotation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.PoseBone.DazRotLocks = BoolVectorProperty(size=3, default=FFalse)
    bpy.types.PoseBone.DazLocLocks = BoolVectorProperty(size=3, default=FFalse)
    bpy.types.PoseBone.DazScaleLocks = BoolVectorProperty(size=3, default=FFalse)
    bpy.types.PoseBone.DazShellMap = BoolProperty()
    bpy.types.PoseBone.DazSharedBone = BoolProperty()

    bpy.types.Object.DazId = StringProperty()
    bpy.types.Object.DazUrl = StringProperty()
    bpy.types.Object.DazFigure = StringProperty()
    bpy.types.Object.DazScene = StringProperty()
    bpy.types.Object.DazRig = StringProperty()
    bpy.types.Object.DazOriginalRig = StringProperty()
    bpy.types.Object.DazMesh = StringProperty()
    bpy.types.Object.DazParentBone = StringProperty()
    bpy.types.Object.DazScale = FloatProperty(default=0.01, precision=4)
    bpy.types.Object.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazCenter = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazRotMode = StringProperty(default='XYZ')
    bpy.types.Object.DazHasLocLocks = BoolProperty()
    bpy.types.Object.DazHasRotLocks = BoolProperty()
    bpy.types.Object.DazHasScaleLocks = BoolProperty()
    bpy.types.Object.DazHasLocLimits = FloatProperty()
    bpy.types.Object.DazHasRotLimits = FloatProperty()
    bpy.types.Object.DazHasScaleLimits = FloatProperty()
    bpy.types.Object.DazUDimsCollapsed = BoolProperty()
    bpy.types.Object.DazCollision = BoolProperty()
    bpy.types.Object.DazCloth = BoolProperty()
    bpy.types.Object.DazHDMesh = BoolProperty()
    bpy.types.Object.DazConforms = BoolProperty(default=True)
    bpy.types.Object.DazInheritScale = BoolProperty()
    bpy.types.Object.DazDriversDisabled = BoolProperty()
    bpy.types.Object.DazCustomMorphs = BoolProperty()
    bpy.types.Object.DazMeshMorphs = BoolProperty()
    bpy.types.Object.DazMeshDrivers = BoolProperty()
    bpy.types.Object.DazMorphAuto = BoolProperty()
    bpy.types.Object.DazMorphNames = CollectionProperty(type = DazStringGroup)
    bpy.types.Object.DazBaked = CollectionProperty(type = DazTextGroup)
    bpy.types.Object.DazBakedValue = CollectionProperty(type = DazFloatGroup)
    bpy.types.Object.DazBakedFiles = CollectionProperty(type = DazFloatGroup)
    bpy.types.Object.DazMorphUrls = CollectionProperty(type = DazMorphInfoGroup)
    bpy.types.Object.DazAutoFollow = CollectionProperty(type = DazTextGroup)
    bpy.types.Object.DazAlias = CollectionProperty(type = DazStringGroup)
    bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
    bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})
    bpy.types.Object.DazVisibilityDrivers = BoolProperty()
    bpy.types.Object.DazVisibilityCollections = BoolProperty()
    bpy.types.Object.DazTiedRig = StringProperty()
    bpy.types.Object.DazOptimizedDrivers = BoolProperty()

    bpy.types.Material.DazScale = FloatProperty(default=0.01)
    bpy.types.Material.DazShader = StringProperty(default='NONE')
    bpy.types.Material.DazUDimsCollapsed = BoolProperty()
    bpy.types.Material.DazUDim = IntProperty()
    bpy.types.Material.DazVDim = IntProperty()
    bpy.types.Material.DazMaterialType = StringProperty()
    bpy.types.Material.DazShellMap = StringProperty()

    bpy.types.Armature.DazExtraFaceBones = BoolProperty()
    bpy.types.Armature.DazExtraDrivenBones = BoolProperty()
    bpy.types.Armature.DazUnflipped = BoolProperty()
    bpy.types.Armature.DazHasAxes = BoolProperty()
    bpy.types.Armature.DazErcStatus = IntProperty()
    bpy.types.Armature.DazOptimizedDrivers = BoolProperty()
    bpy.types.Armature.DazFinalized = BoolProperty()
    bpy.types.Armature.DazBoneMap = CollectionProperty(type=DazStringGroup)
    bpy.types.Armature.DazMergedRigs = CollectionProperty(type = DazStringBoolGroup)
    bpy.types.Armature.DazRigidityScaleFactors = bpy.props.CollectionProperty(type=DazRigidityScaleFactor)

    bpy.types.Mesh.DazTexLevel = IntProperty(min=0, max=3)
    bpy.types.Mesh.DazRigidityGroups = CollectionProperty(type = DazRigidityGroup)
    bpy.types.Mesh.DazFingerPrint = StringProperty(name = "Original Fingerprint", default="")
    bpy.types.Mesh.DazGraftGroup = CollectionProperty(type = DazPairGroup)
    bpy.types.Mesh.DazMaskGroup = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazPolylineMaterials = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazVertexCount = IntProperty(default=0)
    bpy.types.Mesh.DazGraftData = CollectionProperty(type = DazStringIntGroup)
    bpy.types.Mesh.DazMaterialSets = CollectionProperty(type = DazStringStringGroup)
    bpy.types.Mesh.DazHDMaterials = CollectionProperty(type = DazTextGroup)
    bpy.types.Mesh.DazMergedGeografts = CollectionProperty(type = bpy.types.PropertyGroup)
    bpy.types.Mesh.DazHairType = StringProperty(default = 'SHEET')
    bpy.types.Mesh.DazDhdmFiles = CollectionProperty(type = DazStringBoolGroup)
    bpy.types.Mesh.DazMorphFiles = CollectionProperty(type = DazStringBoolGroup)
    bpy.types.Mesh.DazPolygonGroup = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazMaterialGroup = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazCondGraftGroup = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazFavorites = CollectionProperty(type = bpy.types.PropertyGroup)
    bpy.types.Mesh.DazBodyPart = CollectionProperty(type = DazStringGroup)
    bpy.types.Mesh.DazMorphNames = CollectionProperty(type = DazStringGroup)
    bpy.types.Mesh.DazFullyRigid = BoolProperty()
    bpy.types.Mesh.DazOptimizedDrivers = BoolProperty()
    bpy.types.Mesh.DazBulges = CollectionProperty(type = DazBulgeGroup)

    bpy.types.Scene.DazPreferredRoot = EnumProperty(
        items = getRootEnums,
        name = "Preferred Root Directory",
        description = "Preferred root directory used by some import tools")

    bpy.types.Scene.DazAutoMorphArmatures = BoolProperty(
        name = "Auto Morph Armatures",
        description = "Automatically morph armatures on frame change",
        default = False,
        update = toggleMorphArmatures)

    bpy.types.Scene.DazFavoPath = StringProperty(
        name = "Favorite Morphs",
        description = "Path to JSON file with favorite morphs",
        subtype = 'FILE_PATH',
        default = "")

    bpy.types.Scene.DazFilter = StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
    )

    bpy.types.Scene.DazUsedPropsOnly = BoolProperty(
        name = "Show Used Morphs Only",
        description = "Only display morphs with nonzero \"final\" value",
        default = False)

    bpy.types.Scene.DazMorphFactor = FloatProperty(
        name = "Factor",
        description = "Multiply all morphs in this section with this",
        min = 0.1, max = 10,
        default = 1.0)

    bpy.types.Scene.DazDecalMask = StringProperty(
        name = "Decal Mask",
        description = "Path to decal mask texture",
        subtype = 'FILE_PATH',
        default = "")

    bpy.types.Scene.DazLastImportedPose = StringProperty()
    bpy.types.Scene.DazLastImportedExpression = StringProperty()

