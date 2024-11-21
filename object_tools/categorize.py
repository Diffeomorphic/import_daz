# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..utils import *
from ..error import *

#-------------------------------------------------------------
#   Categorize
#-------------------------------------------------------------

class DAZ_OT_CategorizeObjects( DazOperator, IsMeshArmature):
    bl_idname = "daz.categorize_objects"
    bl_label = "Categorize Objects"
    bl_description = "Move unparented objects and their children to separate categories"

    def run(self, context):
        def linkObjects(ob, coll):
            for coll1 in bpy.data.collections:
                if ob.name in coll1.objects:
                    coll1.objects.unlink(ob)
            coll.objects.link(ob)
            for child in ob.children:
                linkObjects(child, coll)

        roots = []
        for ob in getSelectedObjects(context):
            if ob.parent is None and ob.type in ['MESH', 'ARMATURE']:
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
