# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from ..utils import *
from ..error import *
from ..matsel import MaterialSelector, findUvlayers

#-------------------------------------------------------------
#   Replace material node tree
#-------------------------------------------------------------

def getAllMaterials(scn, context):
    return [(mat.name, mat.name, mat.name) for mat in bpy.data.materials]


class DAZ_OT_ReplaceMaterials(MaterialSelector, DazPropsOperator, IsMesh):
    bl_idname = "daz.replace_materials"
    bl_label = "Replace Materials"
    bl_description = "Replace selected materials with specified material.\nFor copying geograft base materials"
    bl_options = {'UNDO'}

    material : EnumProperty(
        items = getAllMaterials,
        name = "Material",
        description = "Use node tree from this material")

    def draw(self, context):
        MaterialSelector.draw(self, context)
        self.layout.prop(self, "material")

    def isDefaultActive(self, mat, ob):
        return True

    def run(self, context):
        from ..tree import copyNodeTree
        ob = context.object
        src = bpy.data.materials[self.material]
        uvlayers = {}
        findUvlayers(src, uvlayers)
        for uvname in uvlayers.keys():
            if uvname not in ob.data.uv_layers.keys():
                raise DazError("Required UV layer %s missing.\nRename or load" % uvname)
        for mat in ob.data.materials:
            if self.useMaterial(mat):
                copyNodeTree(src.node_tree, mat.node_tree)
                copyMaterialAttributes(src, mat)


def copyMaterialAttributes(src, trg):
    attributes = [
        'blend_method', 'shadow_method', 'alpha_threshold', 'show_transparent_back', 'use_backface_culling',
        'use_screen_refraction', 'use_sss_translucency', 'refraction_depth',
        'diffuse_color', 'specular_color', 'roughness', 'specular_intensity', 'metallic',
    ]
    for attr in attributes:
        setattr(trg, attr, getattr(src, attr))


#----------------------------------------------------------
#   Find missing textures
#----------------------------------------------------------

class DAZ_OT_FindMissingTextures(DazOperator, IsMesh):
    bl_idname = "daz.find_missing_textures"
    bl_label = "Find Missing Textures"
    bl_description = "Search for missing textures of selected meshes in the DAZ database"

    def run(self, context):
        def findMissingPath(path):
            path = normalizePath(path).lower()
            for folder,res in [("/textures/original/", ""),
                               ("/textures/res1/", "-res1"),
                               ("/textures/res2/", "-res2"),
                               ("/textures/res3/", "-res3"),
                               ("/textures/res4/", "-res4"),
                               ("/textures/", "")]:
                words = path.rsplit(folder, 1)
                if len(words) == 1:
                    continue
                if res:
                    file = words[1].replace(res, "")
                else:
                    file = words[1]
                newpath = GS.getAbsPath("runtime/textures/%s" % file)
                if newpath and os.path.exists(newpath):
                    print("New path: %s" % newpath)
                    return newpath,res
            return None,""

        def updateImage(img):
            path = bpy.path.abspath(img.filepath)
            if not os.path.exists(path):
                newpath,res = findMissingPath(path)
                if newpath:
                    img.filepath = newpath
                    if res:
                        img.name = img.name.replace(res, "")
                        node.name = node.name.replace(res, "")
                        node.label = node.label.replace(res, "")

        def findImage(node, found):
            from ..fileutils import findPathRecursive
            imgname = node.label
            img = found.get(imgname)
            if not img:
                pattern,ext = os.path.splitext(imgname)
                path = findPathRecursive(pattern, "Runtime/", ["Textures/"], useCheck=False, extensions=[ext])
                if path:
                    img = bpy.data.images.load(path)
                    img.name = imgname
                    found[imgname] = img
            if img:
                node.image = img

        for ob in getSelectedMeshes(context):
            found = {}
            for mat in ob.data.materials:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        if node.image:
                            updateImage(node.image)
                            found[node.label] = node.image
                        else:
                            findImage(node, found)

#----------------------------------------------------------
#   Activate diffuse texture
#----------------------------------------------------------

class DAZ_OT_ActivateDiffuse(DazOperator):
    bl_idname = "daz.activate_diffuse"
    bl_label = "Activate Diffuse"
    bl_description = "Activate diffuse texture node,\nto make textured view work correctly"

    def run(self, context):
        from ..cycles import findTextureNode
        for ob in getVisibleMeshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    nodes = mat.node_tree.nodes
                    for node in nodes:
                        node.select = False
                    links = self.findDiffuseLinks(nodes)
                    for link in links:
                        tex = findTextureNode(link.from_node)
                        if tex:
                            nodes.active = tex
                            tex.select = True

    def findDiffuseLinks(self, nodes):
        for node in nodes:
            if (node.type == 'GROUP' and
                node.node_tree.name.startswith("DAZ Diffuse")):
                return node.inputs["Color"].links
            elif node.type == 'BSDF_DIFFUSE':
                return node.inputs["Color"].links
            elif node.type == 'BSDF_PRINCIPLED':
                return node.inputs["Base Color"].links
        return []

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ReplaceMaterials,
    DAZ_OT_FindMissingTextures,
    DAZ_OT_ActivateDiffuse,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
