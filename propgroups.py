# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Property groups
#-------------------------------------------------------------

class DazIntGroup(bpy.types.PropertyGroup):
    a : IntProperty()

class DazBoolGroup(bpy.types.PropertyGroup):
    t : BoolProperty()

class DazFloatGroup(bpy.types.PropertyGroup):
    f : FloatProperty()

class DazStringGroup(bpy.types.PropertyGroup):
    s : StringProperty()

class DazStringIntGroup(bpy.types.PropertyGroup):
    s : StringProperty()
    i : IntProperty()

class DazStringBoolGroup(bpy.types.PropertyGroup):
    s : StringProperty()
    b : BoolProperty()

class DazPairGroup(bpy.types.PropertyGroup):
    a : IntProperty()
    b : IntProperty()

class DazStringStringGroup(bpy.types.PropertyGroup):
    names : CollectionProperty(type = bpy.types.PropertyGroup)


class DazTextGroup(bpy.types.PropertyGroup):
    text : StringProperty()

    def __lt__(self, other):
        return (self.text < other.text)

    def __repr__(self):
        return "(%s, %s)" % (self.name, self.text)


class DazMorphInfoGroup(bpy.types.PropertyGroup):
    morphset : StringProperty()
    text : StringProperty()
    bodypart : StringProperty()
    category : StringProperty()

class DazBulgeGroup(bpy.types.PropertyGroup):
    positive_left : FloatProperty()
    positive_right : FloatProperty()
    negative_left : FloatProperty()
    negative_right : FloatProperty()

#-------------------------------------------------------------
#   Rigidity groups
#-------------------------------------------------------------

class DazRigidityGroup(bpy.types.PropertyGroup):
    id : StringProperty()
    rotation_mode : StringProperty()
    scale_modes : StringProperty()
    reference_vertices : StringProperty()
    mask_vertices : StringProperty()
    use_transform_bones_for_scale : BoolProperty()

#------------------------------------------------------------------
#   Geograft-scaling morph armature support
#------------------------------------------------------------------

class DazAffectedBone(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Bone name",  default="Unknown")
    weight: bpy.props.FloatProperty(name="Average Rigidty Map Weight",  default=0)

class DazShapekeyScaleFactor(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Shapekey name",  default="Unknown")
    shapekey_center_coord: bpy.props.FloatVectorProperty(name="Center of shapekey shape Rigidity Reference vertices",default=Vector((0,0,0)),subtype="XYZ")
    scale: bpy.props.FloatVectorProperty(name="Scale Factor", description="Scale factor is calculated when transfer shapekey to the geograft that has defined Rigidity Group",subtype="MATRIX",size=9)

class DazRigidityScaleFactor(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name of object (eg. Geograft) that Rigidity Group originaly came from",  default="Unknown")
    base_center_coord: bpy.props.FloatVectorProperty(name="Center of basis shape Rigidity Reference vertices",default=Vector((0,0,0)),subtype="XYZ")
    shapekeys: bpy.props.CollectionProperty(type=DazShapekeyScaleFactor)
    affected_bones: bpy.props.CollectionProperty(type=DazAffectedBone)

#-------------------------------------------------------------
#   Edit Slot group
#-------------------------------------------------------------

class EditSlotGroup(bpy.types.PropertyGroup):
    ncomps : IntProperty(default = 0)

    color : FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0, max = 1.0,
        default = (1,1,1,1)
    )

    vector : FloatVectorProperty(
        name = "Vector",
        size = 3,
        precision = 4,
        min = 0.0,
        default = (0,0,0)
    )

    number : FloatProperty(default = 0.0, precision=4)
    new : BoolProperty()

#-------------------------------------------------------------
#   Morphing
#-------------------------------------------------------------

class DazCategory(bpy.types.PropertyGroup):
    custom : StringProperty()
    morphs : CollectionProperty(type = DazTextGroup)
    active : BoolProperty(default=False, override={'LIBRARY_OVERRIDABLE'})
    index : IntProperty(default=0)

class DazActiveGroup(bpy.types.PropertyGroup):
    active : BoolProperty(default=True, override={'LIBRARY_OVERRIDABLE'})

#-------------------------------------------------------------
#   DAZ props
#-------------------------------------------------------------

propsclasses = []

def getRootEnums(scn, context):
    return [(folder,folder,folder) for folder in GS.getDazPaths()]

def toggleMorphArmatures(self, context):
    GS.toggleMorphArmatures(context.scene)

if DAZ_PROPS:
    class DazImporterGroup(bpy.types.PropertyGroup):
        legacy : BoolProperty(default=True)

    class DazImporterBone(DazImporterGroup):
        DazHead : FloatVectorProperty(size=3, default=(0,0,0))
        DazOrient : FloatVectorProperty(size=3, default=(0,0,0))
        DazTrueName : StringProperty()
        DazRigIndex : IntProperty(default=0)
        DazBoneParentRig : IntProperty(default=-1)


    class DazImporterPoseBone(DazImporterGroup):
        DazRotMode : StringProperty(default='XYZ')
        DazAxes : IntVectorProperty(size=3, default=(0,1,2))
        DazFlips : IntVectorProperty(size=3, default=(1,1,1))
        DazTranslation : FloatVectorProperty(size=3, default=(0,0,0))
        DazRotation : FloatVectorProperty(size=3, default=(0,0,0))
        DazRestRotation : FloatVectorProperty(size=3, default=(0,0,0))
        DazRotLocks : BoolVectorProperty(size=3, default=FFalse)
        DazLocLocks : BoolVectorProperty(size=3, default=FFalse)
        DazScaleLocks : BoolVectorProperty(size=3, default=FFalse)
        DazShellMap : BoolProperty()
        DazSharedBone : BoolProperty()

    class DazImporterObject(DazImporterGroup):
        DazId : StringProperty()
        DazUrl : StringProperty()
        DazFigure : StringProperty()
        DazScene : StringProperty()
        DazRig : StringProperty()
        DazMesh : StringProperty()
        DazParentBone : StringProperty()
        DazScale : FloatProperty(default=0.01, precision=4)
        DazOrient : FloatVectorProperty(size=3, default=(0,0,0))
        DazCenter : FloatVectorProperty(size=3, default=(0,0,0))
        DazRotMode : StringProperty(default='XYZ')
        DazHasLocLocks : BoolProperty()
        DazHasRotLocks : BoolProperty()
        DazHasScaleLocks : BoolProperty()
        DazHasLocLimits : FloatProperty()
        DazHasRotLimits : FloatProperty()
        DazHasScaleLimits : FloatProperty()
        DazUDimsCollapsed : BoolProperty()
        DazCollision : BoolProperty()
        DazCloth : BoolProperty()
        DazHDMesh : BoolProperty()
        DazConforms : BoolProperty(default=True)
        DazInheritScale : BoolProperty()
        DazDriversDisabled : BoolProperty()
        DazCustomMorphs : BoolProperty()
        DazMeshMorphs : BoolProperty()
        DazMeshDrivers : BoolProperty()
        DazMorphAuto : BoolProperty()
        DazMorphNames : CollectionProperty(type = DazStringGroup)
        DazBakedFiles : CollectionProperty(type = DazFloatGroup)
        DazMorphUrls : CollectionProperty(type = DazMorphInfoGroup)
        DazAutoFollow : CollectionProperty(type = DazTextGroup)
        DazAlias : CollectionProperty(type = DazStringGroup)
        DazActivated : CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
        DazMorphCats : CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})
        DazLocalTextures : BoolProperty()
        DazVisibilityDrivers : BoolProperty()
        DazVisibilityCollections : BoolProperty()
        DazTiedRig : StringProperty()
        DazOptimizedDrivers : BoolProperty()


    class DazImporterMaterial(DazImporterGroup):
        DazScale : FloatProperty(default=0.01)
        DazShader : StringProperty(default='NONE')
        DazUDimsCollapsed : BoolProperty()
        DazUDim : IntProperty()
        DazVDim : IntProperty()
        DazSlots : CollectionProperty(type = EditSlotGroup)
        DazMaterialType : StringProperty()
        DazShellMap : StringProperty()


    class DazImporterArmature(DazImporterGroup):
        DazExtraFaceBones : BoolProperty()
        DazExtraDrivenBones : BoolProperty()
        DazUnflipped : BoolProperty()
        DazHasAxes : BoolProperty()
        DazOptimizedDrivers : BoolProperty()
        DazFinalized  : BoolProperty()
        DazBoneMap : CollectionProperty(type=DazStringGroup)
        DazMergedRigs : CollectionProperty(type = DazStringBoolGroup)
        DazRigidityScaleFactors : bpy.props.CollectionProperty(type=DazRigidityScaleFactor)


    class DazImporterMesh(DazImporterGroup):
        DazRigidityGroups : CollectionProperty(type = DazRigidityGroup)
        DazFingerPrint : StringProperty(name = "Original Fingerprint", default="")
        DazGraftGroup : CollectionProperty(type = DazPairGroup)
        DazMaskGroup : CollectionProperty(type = DazIntGroup)
        DazPolylineMaterials : CollectionProperty(type = DazIntGroup)
        DazVertexCount : IntProperty(default=0)
        DazGraftData : CollectionProperty(type = DazStringIntGroup)
        DazMaterialSets : CollectionProperty(type = DazStringStringGroup)
        DazHDMaterials : CollectionProperty(type = DazTextGroup)
        DazMergedGeografts : CollectionProperty(type = bpy.types.PropertyGroup)
        DazHairType : StringProperty(default = 'SHEET')
        DazDhdmFiles : CollectionProperty(type = DazStringBoolGroup)
        DazMorphFiles : CollectionProperty(type = DazStringBoolGroup)
        DazPolygonGroup : CollectionProperty(type = DazIntGroup)
        DazMaterialGroup : CollectionProperty(type = DazIntGroup)
        DazFavorites : CollectionProperty(type = bpy.types.PropertyGroup)
        DazBodyPart : CollectionProperty(type = DazStringGroup)
        DazFullyRigid : BoolProperty()
        DazOptimizedDrivers : BoolProperty()
        DazBulges : CollectionProperty(type = DazBulgeGroup)


    class DazImporterScene(DazImporterGroup):
        DazPreferredRoot : EnumProperty(
            items = getRootEnums,
            name = "Preferred Root Directory",
            description = "Preferred root directory used by some import tools")

        DazAutoMorphArmatures : BoolProperty(
            name = "Auto Morph Armatures",
            description = "Automatically morph armatures on frame change",
            default = False,
            update = toggleMorphArmatures)

        DazFavoPath : StringProperty(
            name = "Favorite Morphs",
            description = "Path to favorite morphs",
            subtype = 'FILE_PATH',
            default = "")

        DazFilter : StringProperty(
            name = "Filter",
            description = "Show only items containing this string",
            default = ""
        )

        DazUsedPropsOnly : BoolProperty(
            name = "Show Used Morphs Only",
            description = "Only display morphs with nonzero \"final\" value",
            default = False)

        DazMorphFactor : FloatProperty(
            name = "Factor",
            description = "Multiply all morphs in this section with this",
            min = 0.1, max = 10,
            default = 1.0)

        DazDecalMask : StringProperty(
            name = "Decal Mask",
            description = "Path to decal mask texture",
            subtype = 'FILE_PATH',
            default = "")


    class DAZ_OT_UpdateDazProperties(DazPropsOperator):
        bl_idname = "daz.update_daz_properties"
        bl_label = "Update DAZ Properties"
        bl_description = "Update DAZ properties"
        bl_options = {'UNDO'}

        useScene : BoolProperty(
            name = "Scene",
            description = "Update scene properties",
            default = True)

        useObjects : BoolProperty(
            name = "Objects",
            description = "Update object properties",
            default = True)

        useAllProps : BoolProperty(
            name = "All Properties",
            description = "Update all properties in scene rather than selected objects only",
            default = True)

        def draw(self, context):
            self.layout.prop(self, "useScene")
            self.layout.prop(self, "useObjects")
            if self.useObjects:
                self.layout.prop(self, "useAllProps")


        def run(self, context):
            def updateProps(rna):
                def setCollProp(group, prop, value, pgs2):
                    if len(value) == 0:
                        pass
                    elif isinstance(value, str):
                        setattr(group, prop, value)
                    elif isinstance(value[0], (bool, int, float)):
                        setattr(group, prop, value)
                    else:
                        pgs1 = value
                        for pg1 in pgs1:
                            pg2 = pgs2.add()
                            for key in dir(pg2):
                                if key[0] == "_" or key in ["rna_type", "bl_rna"]:
                                    pass
                                elif key in ["names", "shapekeys", "affected_bones", "morphs"]:
                                    value1 = getattr(pg1, key)
                                    value2 = getattr(pg2, key)
                                    setCollProp(pg2, key, value1, value2)
                                else:
                                    value = getattr(pg1, key)
                                    try:
                                        setattr(pg2, key, value)
                                    except AttributeError:
                                        print("ILLEGAL", key, value)

                for prop in dir(rna.daz_importer):
                    if (prop.startswith("Daz") and
                        prop in rna.keys() and
                        hasattr(rna, prop)):
                        value = getattr(rna, prop)
                        if hasattr(value, "__len__"):
                            pgs2 = getattr(rna.daz_importer, prop)
                            setCollProp(rna.daz_importer, prop, value, pgs2)
                        else:
                            setattr(rna.daz_importer, prop, value)
                        del rna[prop]
                setModernProps(rna)


            registerDazProperties()
            if self.useScene:
                updateProps(context.scene)
            if not self.useObjects:
                return
            elif self.useAllProps:
                objects = context.view_layer.objects
            else:
                objects = getSelectedObjects(context)
            for ob in objects:
                print("Update %s %s" % (ob.type, ob.name))
                updateProps(ob)
                setModernProps(ob)
                if ob.type == 'MESH':
                    updateProps(ob.data)
                    setModernProps(ob.data)
                    for mat in ob.data.materials:
                        if mat:
                            updateProps(mat)
                            setModernProps(mat)
                elif ob.type == 'ARMATURE':
                    updateProps(ob.data)
                    setModernProps(ob.data)
                    for pb in ob.pose.bones:
                        updateProps(pb.bone)
                        setModernProps(pb.bone)
                        updateProps(pb)
                        setModernProps(pb)


    class DAZ_OT_SelectLegacyPosebones(DazOperator, IsArmature):
        bl_idname = "daz.select_legacy_posebones"
        bl_label = "Select Legacy Posebones"
        bl_options = {'UNDO'}

        def run(self, context):
            for rig in getSelectedArmatures(context):
                for pb in rig.pose.bones:
                    pb.bone.select = (pb.daz_importer.legacy or pb.bone.daz_importer.legacy)


    propsclasses = [
        DazImporterBone,
        DazImporterPoseBone,
        DazImporterObject,
        DazImporterArmature,
        DazImporterMaterial,
        DazImporterMesh,
        DazImporterScene,
        DAZ_OT_UpdateDazProperties,
        DAZ_OT_SelectLegacyPosebones
        ]

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DazIntGroup,
    DazBoolGroup,
    DazFloatGroup,
    DazStringGroup,
    DazStringBoolGroup,
    DazStringIntGroup,
    DazPairGroup,
    DazRigidityGroup,
    DazAffectedBone,
    DazShapekeyScaleFactor,
    DazRigidityScaleFactor,
    DazStringStringGroup,
    DazTextGroup,
    DazMorphInfoGroup,
    DazBulgeGroup,
    DazActiveGroup,
    DazCategory,
    EditSlotGroup,
]

def register():
    for cls in classes + propsclasses:
        bpy.utils.register_class(cls)

    from .morphing import MS
    bpy.types.PoseBone.DazHeadLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.DazTailLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.HdOffset = bpy.props.FloatVectorProperty(size=3, default=(0,0,0))

    if DAZ_PROPS:
        for morphset in MS.Morphsets:
            setattr(DazImporterObject, "Daz%s" % morphset, CollectionProperty(type = DazTextGroup))
            setattr(DazImporterArmature, "DazIndex%s" % morphset, IntProperty(default=0))

        bpy.types.Bone.daz_importer = PointerProperty(type=DazImporterBone)
        bpy.types.PoseBone.daz_importer = PointerProperty(type=DazImporterPoseBone)
        bpy.types.Object.daz_importer = PointerProperty(type=DazImporterObject)
        bpy.types.Armature.daz_importer = PointerProperty(type=DazImporterArmature)
        bpy.types.Mesh.daz_importer = PointerProperty(type=DazImporterMesh)
        bpy.types.Material.daz_importer = PointerProperty(type=DazImporterMaterial)
        bpy.types.Scene.daz_importer = PointerProperty(type=DazImporterScene)

    registerDazProperties()


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
    bpy.types.Object.DazBakedFiles = CollectionProperty(type = DazFloatGroup)
    bpy.types.Object.DazMorphUrls = CollectionProperty(type = DazMorphInfoGroup)
    bpy.types.Object.DazAutoFollow = CollectionProperty(type = DazTextGroup)
    bpy.types.Object.DazAlias = CollectionProperty(type = DazStringGroup)
    bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
    bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})
    bpy.types.Object.DazLocalTextures = BoolProperty()
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
    bpy.types.Armature.DazOptimizedDrivers = BoolProperty()
    bpy.types.Armature.DazFinalized = BoolProperty()
    bpy.types.Armature.DazBoneMap = CollectionProperty(type=DazStringGroup)
    bpy.types.Armature.DazMergedRigs = CollectionProperty(type = DazStringBoolGroup)
    bpy.types.Armature.DazRigidityScaleFactors = bpy.props.CollectionProperty(type=DazRigidityScaleFactor)

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
    bpy.types.Mesh.DazFavorites = CollectionProperty(type = bpy.types.PropertyGroup)
    bpy.types.Mesh.DazBodyPart = CollectionProperty(type = DazStringGroup)
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
        description = "Path to favorite morphs",
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


def unregister():
    for cls in classes + propsclasses:
        bpy.utils.unregister_class(cls)
