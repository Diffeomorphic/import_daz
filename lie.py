# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import bpy
from .utils import *
from .error import *
from .localtex import LocalTextureUser

#----------------------------------------------------------
#   Bake LIE
#----------------------------------------------------------

class DAZ_OT_BakeLie(DazPropsOperator, LocalTextureUser):
    bl_idname = "daz.bake_lie"
    bl_label = "Bake Layered Images"
    bl_description = "Bake layered images of selected meshes to simple textures"
    bl_options = {'UNDO'}

    subdir = "/textures/LIE"

    def storeState(self, context):
        DazPropsOperator.storeState(self, context)
        scn = context.scene
        self.bake_type = scn.cycles.bake_type
        self.view_from = scn.render.bake.view_from
        self.bake_target = scn.render.bake.target
        self.bake_use_clear = scn.render.bake.use_clear
        scn.cycles.bake_type = 'EMIT'
        scn.render.bake.view_from = 'ABOVE_SURFACE'
        scn.render.bake.target = 'IMAGE_TEXTURES'
        scn.render.bake.use_clear = True


    def restoreState(self, context):
        scn = context.scene
        scn.cycles.bake_type = self.bake_type
        scn.render.bake.view_from = self.view_from
        scn.render.bake.target = self.bake_target
        scn.render.bake.use_clear = self.bake_use_clear
        DazPropsOperator.restoreState(self, context)


    def run(self, context):
        self.initLocalImages()
        self.saveLocalTextures(context)
        meshes = getSelectedMeshes(context)
        bpy.ops.mesh.primitive_plane_add(size=1)
        bakeplane = context.object
        activateObject(context, bakeplane)
        bakemat = bpy.data.materials.new("LIE Bake")
        if BLENDER5:
            bakemat.use_nodes = True
        bakeplane.data.materials.append(bakemat)
        try:
            for ob in meshes:
                self.bakeLieGroups(context, ob, bakeplane, bakemat)
        finally:
            deleteObjects(context, [bakeplane])
            bpy.data.materials.remove(bakemat)


    def bakeLieGroups(self, context, ob, bakeplane, bakemat):
        def findTexImage(tree):
            for node in tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    return node, node.image

        def makeBakeImage(node, img):
            width,height = img.size
            name = stripUuid(node.name)
            bakeimg = bpy.data.images.new(name, width, height)
            bakeimg.colorspace_settings.name = img.colorspace_settings.name
            words = os.path.splitext(img.filepath)
            if len(words) == 2:
                ext = words[1]
            else:
                ext = ".png"
            bakeimg.filepath = os.path.join(self.texpath, "%s%s" % (name, ext))
            return bakeimg

        def makeBakeTree(node, baketree, bakeimg, uvname):
            baketree.nodes.clear()
            uvmap = baketree.nodes.new(type="ShaderNodeUVMap")
            uvmap.location = (0,0)
            uvmap.uv_map = uvname
            uvmap.label = uvname
            lie = baketree.nodes.new(type="ShaderNodeGroup")
            lie.location = (200,0)
            lie.node_tree = node.node_tree
            baketree.links.new(uvmap.outputs["UV"], lie.inputs["Vector"])
            emission = baketree.nodes.new(type="ShaderNodeEmission")
            emission.location = (400, 0)
            baketree.links.new(lie.outputs["Color"], emission.inputs["Color"])
            output = baketree.nodes.new(type="ShaderNodeOutputMaterial")
            output.location = (600, 0)
            baketree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
            tex = baketree.nodes.new(type="ShaderNodeTexImage")
            tex.location = (0, -200)
            tex.image = bakeimg
            tex.interpolation = "Linear"
            tex.projection = 'FLAT'
            tex.extension = 'CLIP'
            baketree.nodes.active = tex

        def bakeMaterial(tree, baketree, uvname):
            lies = []
            for node in tree.nodes:
                if (node.type == 'GROUP' and
                    node.node_tree.name.startswith("LIE")):
                    tex,img = findTexImage(node.node_tree)
                    if img:
                        bakeimg = makeBakeImage(node, img)
                        makeBakeTree(node, baketree, bakeimg, uvname)
                        print('Bake %s %s image\n  "%s"' %
                            (tuple(bakeimg.size), bakeimg.colorspace_settings.name, bakeimg.filepath))
                        width,height = img.size
                        bpy.ops.object.bake(type='EMIT', width=width, height=height)
                        if self.useSaveGenerated:
                            bakeimg.save()
                        else:
                            bakeimg.pack()
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

        uvname = bakeplane.data.uv_layers.active.name
        for mat in ob.data.materials:
            if mat and mat.node_tree:
                bakeMaterial(mat.node_tree, bakemat.node_tree, uvname)

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


