# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *

#-------------------------------------------------------------
#   Categorize
#-------------------------------------------------------------

class DAZ_OT_CategorizeObjects( DazPropsOperator, IsObject):
    bl_idname = "daz.categorize_objects"
    bl_label = "Categorize Objects"
    bl_description = "Move selected unparented objects and their children to separate categories"

    useMeshes : BoolProperty(
        name = "Meshes",
        default = True)

    useArmatures : BoolProperty(
        name = "Armatures",
        default = True)

    useEmpties : BoolProperty(
        name = "Empties",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useMeshes")
        self.layout.prop(self, "useArmatures")
        self.layout.prop(self, "useEmpties")

    def run(self, context):
        def linkObjects(ob, coll):
            for coll1 in bpy.data.collections:
                if ob.name in coll1.objects:
                    coll1.objects.unlink(ob)
            coll.objects.link(ob)
            for child in ob.children:
                linkObjects(child, coll)

        types = []
        if self.useMeshes:
            types.append('MESH')
        if self.useArmatures:
            types.append('ARMATURE')
        if self.useEmpties:
            types.append('EMPTY')
        roots = []
        for ob in getSelectedObjects(context):
            if ob.parent is None and ob.type in types:
                roots.append(ob)
        print("Roots", roots)
        parcoll = context.collection
        for root in roots:
            coll = bpy.data.collections.new(root.name)
            parcoll.children.link(coll)
            linkObjects(root, coll)


#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_CategorizeObjects,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
