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
        active = context.object
        meshes = getSelectedMeshes(context)
        bpy.ops.mesh.primitive_plane_add(size=1)
        plane = context.object
        activateObject(context, plane)
        bakemat = bpy.data.materials.new("LIE Bake")
        plane.data.materials.append(bakemat)

        folder = os.path.join(os.path.dirname(bpy.data.filepath), "textures", "LIE")
        scn = context.scene
        scn.cycles.bake_type = 'EMIT'
        scn.render.bake.view_from = 'ABOVE_SURFACE'
        scn.render.bake.target = 'IMAGE_TEXTURES'
        scn.render.bake.use_clear = True

        for ob in meshes:
            self.checkLocalTextures(context, ob)
            bakeLieGroups(scn, ob, bakemat.node_tree, folder)
        #context.view_layer.objects.active = active


def bakeLieGroups(scn, ob, baketree, folder):
    def makeBakeTree(node, baketree):
        print("NN", node.name)
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
        img = bpy.data.images.new(node.name, 2048, 2048)
        tex.image = img
        tex.interpolation = "Linear"
        tex.projection = 'FLAT'
        tex.extension = 'CLIP'
        baketree.nodes.active = tex
        return img

    def bakeMaterial(tree, baketree, folder):
        lies = []
        for node in tree.nodes:
            if (node.type == 'GROUP' and
                node.node_tree.name.startswith("LIE")):
                img = makeBakeTree(node, baketree)
                img.filepath_raw = os.path.join(folder, "%s.png" % img.name)
                print('Bake "%s"' % img.filepath_raw)
                print("ACT", bpy.context.object)
                bpy.ops.object.bake_image()
                img.save()
                img.buffers_free()
                lies.append((node, img))
        for node,img in lies:
            tex = tree.nodes.new(type="ShaderNodeTexImage")
            tex.location = node.location
            tex.image = img
            tex.interpolation = "Linear"
            tex.projection = 'FLAT'
            tex.extension = 'CLIP'
            for link in node.inputs["Vector"].links:
                tree.links.new(link.from_socket, tex.inputs["Vector"])
            for slot in ["Color", "Alpha"]:
                for link in list(node.outputs[slot].links):
                    tree.links.new(tex.outputs[slot], link.to_socket)
            tree.nodes.remove(node)

    for mat in ob.data.materials:
        if mat and mat.node_tree:
            bakeMaterial(mat.node_tree, baketree, folder)

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


