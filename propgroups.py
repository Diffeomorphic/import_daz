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
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
