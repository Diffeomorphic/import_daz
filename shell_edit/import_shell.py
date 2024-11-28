# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from ..utils import *
from ..error import *
from ..main import MaterialLoader, DazImageFile, MultiFile

#------------------------------------------------------------------
#   Import Shell node groups
#------------------------------------------------------------------

class ImportShells(DazOperator, MaterialLoader, DazImageFile, MultiFile):
    bl_idname = "daz.import_shells"
    bl_label = "Import Shells"
    bl_description = "Load shell node groups from native DAZ file"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..cycles import CyclesMaterial
        from ..tree import pruneNodeTree
        from ..matsel import isShellNode
        GS.checkAbsPaths()
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        LS.forShells(self)
        for idx,filepath in enumerate(filepaths):
            bpy.ops.mesh.primitive_cube_add(size=30*GS.scale, location=(50*(idx+1)*GS.scale, 0, 0))
            cube = context.object
            cube.name = os.path.basename(os.path.splitext(filepath)[0])
            main = self.loadDazFile(filepath, context)
            for node,inst in main.nodes:
                inst.preprocess(context)
            for dmat in main.materials:
                dmat.build(context)
            taken = []
            for dmat in main.materials:
                dmat.mappingNodes = []
                dmat.postbuild()
                mat = dmat.rna
                if mat and mat.node_tree and mat not in taken:
                    cube.data.materials.append(mat)
                    pruneNodeTree(mat.node_tree, None)
                    taken.append(mat)
            nodegroups = {}
            for mat in cube.data.materials:
                for node in mat.node_tree.nodes:
                    if isShellNode(node):
                        gname = stripName(node.node_tree.name)
                        if gname in nodegroups.keys():
                            node.node_tree = nodegroups[gname]
                        else:
                            nodegroups[gname] = node.node_tree

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(ImportShells)

def unregister():
    bpy.utils.unregister_class(ImportShells)
