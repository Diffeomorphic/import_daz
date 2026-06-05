# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
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
        meshes = getSelectedMeshes(context)
        bake = None
        for ob in meshes:
            self.checkLocalTextures(context, ob)
            bake = bakeLieGroups(context, ob, bake)
        if bake:
            plane = bake[0]
            deleteObjects(context, [plane])


def bakeLieGroups(context, ob, bake):
    def findTexImage(tree):
        for node in tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                return node, node.image

    def makeBakeImage(node, img, folder):
        width,height = img.size
        bakeimg = bpy.data.images.new(node.name, width, height)
        bakeimg.colorspace_settings.name = img.colorspace_settings.name
        words = os.path.splitext(img.filepath)
        if len(words) == 2:
            ext = words[1]
        else:
            ext = ".png"
        bakeimg.filepath = os.path.join(folder, "%s%s" % (bakeimg.name, ext))
        return bakeimg

    def makeBakeTree(node, baketree, bakeimg):
        baketree.nodes.clear()
        lie = baketree.nodes.new(type="ShaderNodeGroup")
        lie.location = (0,0)
        lie.node_tree = node.node_tree
        emission = baketree.nodes.new(type="ShaderNodeEmission")
        emission.location = (200, 0)
        baketree.links.new(lie.outputs["Color"], emission.inputs["Color"])
        output = baketree.nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (400, 0)
        baketree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
        tex = baketree.nodes.new(type="ShaderNodeTexImage")
        tex.location = (0, -200)
        tex.image = bakeimg
        tex.interpolation = "Linear"
        tex.projection = 'FLAT'
        tex.extension = 'CLIP'
        baketree.nodes.active = tex

    def bakeMaterial(tree, baketree, folder):
        lies = []
        for node in tree.nodes:
            if (node.type == 'GROUP' and
                node.node_tree.name.startswith("LIE")):
                tex,img = findTexImage(node.node_tree)
                if img:
                    bakeimg = makeBakeImage(node, img, folder)
                    makeBakeTree(node, baketree, bakeimg)
                    print('Bake %s %s image\n  "%s"' %
                        (tuple(bakeimg.size), bakeimg.colorspace_settings.name, bakeimg.filepath))
                    width,height = img.size
                    bpy.ops.object.bake(type='EMIT', width=width, height=height)
                    bakeimg.save()
                    lies.append((node, tex, img, bakeimg))
        for node,tex,img,bakeimg in lies:
            newTex = tree.nodes.new(type="ShaderNodeTexImage")
            newTex.location = node.location
            newTex.image = bakeimg
            newTex.interpolation = tex.interpolation
            newTex.projection = tex.projection
            newTex.extension = tex.extension
            for link in node.inputs["Vector"].links:
                tree.links.new(link.from_socket, newTex.inputs["Vector"])
            for slot in ["Color", "Alpha"]:
                for link in list(node.outputs[slot].links):
                    tree.links.new(newTex.outputs[slot], link.to_socket)
            newTex.hide = True
            tree.nodes.remove(node)

    if bake is None:
        bpy.ops.mesh.primitive_plane_add(size=1)
        plane = context.object
        activateObject(context, plane)
        bakemat = bpy.data.materials.new("LIE Bake")
        plane.data.materials.append(bakemat)
        bake = (plane, bakemat)
    else:
        plane, bakemat = bake

    folder = os.path.join(os.path.dirname(bpy.data.filepath), "textures", "LIE")
    scn = context.scene
    scn.cycles.bake_type = 'EMIT'
    scn.render.bake.view_from = 'ABOVE_SURFACE'
    scn.render.bake.target = 'IMAGE_TEXTURES'
    scn.render.bake.use_clear = True

    for mat in ob.data.materials:
        if mat and mat.node_tree:
            bakeMaterial(mat.node_tree, bakemat.node_tree, folder)

    return bake

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


