# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .utils import *
from .error import *
from .material import LocalTextureUser


#----------------------------------------------------------
#   Bake LIE
#----------------------------------------------------------

class DAZ_OT_BakeLie(DazPropsOperator, LocalTextureUser):
    bl_idname = "daz.bake_lie"
    bl_label = "Bake Layered Images"
    bl_description = "Bake layered images of selected meshes to simple textures"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.checkLocalTextures(context, ob)
            bakeLieGroups(ob)


def bakeLieGroups(ob):
    def bakeMaterial(tree):
        for node in tree.nodes:
            if (node.type == 'GROUP' and
                node.node_tree.name.startswith("LIE")):
                print("NN", node.name)

    for mat in ob.data.materials:
        if mat and mat.node_tree:
            bakeMaterial(mat.node_tree)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_BakeLie
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


