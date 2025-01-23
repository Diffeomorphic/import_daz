# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
#   Bone
#-------------------------------------------------------------

class DazImporterBone(bpy.types.PropertyGroup):
    DazHead : FloatVectorProperty(size=3, default=(0,0,0))
    DazOrient : FloatVectorProperty(size=3, default=(0,0,0))
    DazNormal : FloatVectorProperty(size=3, default=(0,0,0))
    DazAngle : FloatProperty()
    DazTrueName : StringProperty()
    DazExtraBone : StringProperty()


class DazImporterPoseBone(bpy.types.PropertyGroup):
    DazRotMode : StringProperty(default='XYZ')
    DazAxes : IntVectorProperty(size=3, default=(0,1,2))
    DazFlips : IntVectorProperty(size=3, default=(1,1,1))
    DazTranslation : FloatVectorProperty(size=3, default=(0,0,0))
    DazRotation : FloatVectorProperty(size=3, default=(0,0,0))
    DazRestRotation : FloatVectorProperty(size=3, default=(0,0,0))
    DazRotLocks : BoolVectorProperty(size=3, default=FFalse)
    DazLocLocks : BoolVectorProperty(size=3, default=FFalse)
    DazScaleLocks : BoolVectorProperty(size=3, default=FFalse)
    #DazHeadLocal : bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    #DazTailLocal : bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    #HdOffset : bpy.props.FloatVectorProperty(size=3, default=(0,0,0))


class DazImporterObject(bpy.types.PropertyGroup):
    DazId : StringProperty()
    DazUrl : StringProperty()
    DazFigure : StringProperty()
    DazScene : StringProperty()
    DazRig : StringProperty()
    DazMesh : StringProperty()
    DazScale : FloatProperty(default=0.01, precision=4)
    DazOrient : FloatVectorProperty(size=3, default=(0,0,0))
    DazCenter : FloatVectorProperty(size=3, default=(0,0,0))
    DazRotMode : StringProperty(default='XYZ')
    DazHasLocLocks : BoolProperty()
    DazHasRotLocks : BoolProperty()
    DazHasLocLimits : BoolProperty()
    DazHasRotLimits : BoolProperty()
    DazUDimsCollapsed : BoolProperty()
    DazCollision : BoolProperty()
    DazCloth : BoolProperty()
    DazConforms : BoolProperty(default=True)
    DazCloth : BoolProperty()
    DazSimpleIK : BoolProperty()
    DazInheritScale : BoolProperty()
    DazDriversDisabled : BoolProperty()
    DazCustomMorphs : BoolProperty()
    DazMeshMorphs : BoolProperty()
    DazMeshDrivers : BoolProperty()
    DazMorphAuto : BoolProperty()
    DazBakedFiles : CollectionProperty(type = DazFloatGroup)
    DazMorphUrls : CollectionProperty(type = DazMorphInfoGroup)
    DazAutoFollow : CollectionProperty(type = DazTextGroup)
    DazAlias : CollectionProperty(type = DazStringGroup)
    DazActivated : CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
    DazMorphCats : CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})


class DazImporterMaterial(bpy.types.PropertyGroup):
    DazScale : FloatProperty(default=0.01)
    DazShader : StringProperty(default='NONE')
    DazUDimsCollapsed : BoolProperty()
    DazUDim : IntProperty()
    DazVDim : IntProperty()


class DazImporterArmature(bpy.types.PropertyGroup):
    DazExtraFaceBones : BoolProperty()
    DazExtraDrivenBones : BoolProperty()
    DazUnflipped : BoolProperty()
    DazHasAxes : BoolProperty()
    DazBoneMap : CollectionProperty(type=DazStringGroup)
    DazMergedRigs : CollectionProperty(type = DazStringBoolGroup)


class DazImporterMesh(bpy.types.PropertyGroup):
    DazRigidityGroups : CollectionProperty(type = DazRigidityGroup)
    DazFingerPrint : StringProperty(name = "Original Fingerprint", default="")
    DazGraftGroup : CollectionProperty(type = DazPairGroup)
    DazMaskGroup : CollectionProperty(type = DazIntGroup)
    DazPolylineMaterials : CollectionProperty(type = DazIntGroup)
    DazVertexCount : IntProperty(default=0)
    DazMaterialSets : CollectionProperty(type = DazStringStringGroup)
    DazHDMaterials : CollectionProperty(type = DazTextGroup)
    DazMergedGeografts : CollectionProperty(type = bpy.types.PropertyGroup)
    DazHairType : StringProperty(default = 'SHEET')
    DazDhdmFiles : CollectionProperty(type = DazStringBoolGroup)
    DazMorphFiles : CollectionProperty(type = DazStringBoolGroup)
    DazPolygonGroup : CollectionProperty(type = bpy.types.PropertyGroup)
    DazMaterialGroup : CollectionProperty(type = bpy.types.PropertyGroup)
    DazFavorites : CollectionProperty(type = bpy.types.PropertyGroup)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DazIntGroup,
    DazBoolGroup,
    DazFloatGroup,
    DazStringGroup,
    DazStringBoolGroup,
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

    DazImporterBone,
    DazImporterPoseBone,
    DazImporterObject,
    DazImporterArmature,
    DazImporterMaterial,
    DazImporterMesh,
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    from .morphing import MS
    for morphset in MS.Morphsets:
        setattr(DazImporterObject, "Daz%s" % morphset, CollectionProperty(type = DazTextGroup))
        setattr(DazImporterArmature, "DazIndex%s" % morphset, IntProperty(default=0))

    bpy.types.Bone.daz_importer = PointerProperty(type=DazImporterBone)
    bpy.types.PoseBone.daz_importer = PointerProperty(type=DazImporterPoseBone)
    bpy.types.Object.daz_importer = PointerProperty(type=DazImporterObject)
    bpy.types.Armature.daz_importer = PointerProperty(type=DazImporterArmature)
    bpy.types.Mesh.daz_importer = PointerProperty(type=DazImporterMesh)
    bpy.types.Material.daz_importer = PointerProperty(type=DazImporterMaterial)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
