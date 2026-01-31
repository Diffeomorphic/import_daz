# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from ..utils import *
from ..error import *
from ..matsel import MaterialSelector
from ..fileutils import SingleFile, ImageFile
from ..tree import XSIZE, YSIZE

# ---------------------------------------------------------------------
#   Make Decal
# ---------------------------------------------------------------------

def getEmptyName(scn, context):
    ob = context.object
    enums = [('NONE', "None", "None")]
    for child in ob.children:
        if child.type == 'EMPTY':
            enums.append((child.name, child.name, child.name))
    return enums


class DAZ_OT_MakeDecal(DazOperator, ImageFile, SingleFile, MaterialSelector, IsMesh):
    bl_idname = "daz.make_decal"
    bl_label = "Make Decal"
    bl_description = "Add a decal to the active material"
    bl_options = {'UNDO'}

    channel : EnumProperty(
        items = [("Diffuse", "Diffuse Color", "Diffuse Color"),
                 ("Glossy", "Glossy Color", "Glossy Color"),
                 ("Translucency", "Translucency Color", "Translucency Color"),
                 ("SSS", "Subsurface Color", "Subsurface Color"),
                 ("PBase", "Principled Base Color", "Principled Base Color"),
                 ("PSSS", "Principled Subsurface Color", "Principled Subsurface Color"),
                 ("Bump", "Bump", "Bump"),
                ],
        name = "Channel",
        description = "Add decal to this channel",
        default = "Diffuse")

    slots = {
        "Diffuse" : ('BSDF_DIFFUSE', "Color"),
        "Glossy" : ("DAZ Glossy", "Color"),
        "Translucency" : ("DAZ Translucent", "Color"),
        "SSS" : ("DAZ SSS", "Color"),
        "PBase" : ('BSDF_PRINCIPLED', "Base Color"),
        "PSSS" : ('BSDF_PRINCIPLED', "Subsurface Color"),
        "Bump" : ("BUMP", "Height"),
    }

    reuseEmpty : BoolProperty(
        name = "Reuse Empty",
        description = "Reuse an existing empty instead of creating a new one",
        default = False)

    emptyName : EnumProperty(
        items = getEmptyName,
        name = "Empty",
        description = "Empty to reuse")

    useMask : BoolProperty(
        name = "Use Mask",
        description = "Use a separate texture to mask the decal",
        default = False)

    decalMask : StringProperty(
        name = "Decal Mask",
        description = "Path to decal mask texture",
        default = "")

    blendType : EnumProperty(
        items = [('MIX', "Mix", "Mix"),
                 ('MULTIPLY', "Multiply", "Multiply")],
        name = "Blend Type",
        description = "Type of blending decal with skin",
        default = 'MIX')

    def draw(self, context):
        MaterialSelector.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "channel")
        self.layout.prop(self, "reuseEmpty")
        if self.reuseEmpty:
            self.layout.prop(self, "emptyName")
        self.layout.prop(self, "useMask")
        if self.useMask:
            self.layout.prop(self, "decalMask")
        self.layout.prop(self, "blendType")


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        scn = context.scene
        self.decalMask = dazRna(scn).DazDecalMask
        return SingleFile.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return (ob.active_material == mat)


    def run(self, context):
        from ..material import setColorSpaceSRGB, setColorSpaceNone
        img = bpy.data.images.load(self.filepath)
        if img is None:
            raise DazError("Unable to load file %s" % self.filepath)
        setColorSpaceSRGB(img)

        mask = None
        if self.useMask:
            maskname = os.path.basename(self.decalMask)
            if maskname in bpy.data.images.keys():
                mask = bpy.data.images[maskname]
            else:
                mask = bpy.data.images.load(self.decalMask)
            if mask is None:
                raise DazError("Unable to load mask file %s" % self.decalMask)
            setColorSpaceNone(mask)

        ob = context.object
        dazRna(ob).DazVisibilityDrivers = True
        fname = os.path.splitext(os.path.basename(self.filepath))[0]
        if self.reuseEmpty and self.emptyName != 'NONE':
            empty = bpy.data.objects[self.emptyName]
        else:
            empty = bpy.data.objects.new(fname, None)
            empty.parent = ob
            empty.rotation_euler = (0, 0, 0)
            empty.scale = (1, 0.2, 1)
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 0.25
            coll = getCollection(context, ob)
            coll.objects.link(empty)
        self.force = True
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.loadDecal(mat, img, empty, mask, fname)


    def loadDecal(self, mat, img, empty, mask, fname):
        def getFromToSockets(tree, nodeType, slot):
            from ..tree import findNodes
            for link in tree.links.values():
                node = link.to_node
                if node:
                    if (node.type == nodeType or
                        (node.type == 'GROUP' and node.node_tree.name == nodeType)):
                        if link.to_socket == node.inputs[slot]:
                            return link.from_socket, link.to_socket, node.location
            nodes = findNodes(tree, nodeType)
            if nodes:
                node = nodes[0]
                return None, node.inputs[slot], node.location
            return None, None, None

        from ..cgroup import DecalGroup
        from ..cycles import findTree
        tree = findTree(mat)
        nodeType,slot = self.slots[self.channel]
        fromSocket, toSocket, loc = getFromToSockets(tree, nodeType, slot)
        if toSocket is None:
            raise DazError("Channel %s not found (%s)" % (self.channel, nodeType))
        nname = "%s_%s" % (fname, self.channel)
        node = tree.addGroup(DecalGroup, nname, args=[empty, img, mask, self.blendType], force=self.force)
        node.label = empty.name
        self.force = False
        node.location = (loc[0]-XSIZE, 3*YSIZE)
        node.inputs["Influence"].default_value = 1.0
        if fromSocket:
            tree.links.new(fromSocket, node.inputs["Color"])
        else:
            rgb = tree.addNode("ShaderNodeRGB")
            rgb.location = (loc[0]-2*XSIZE, 3*YSIZE)
            rgb.outputs["Color"].default_value = toSocket.default_value
            tree.links.new(rgb.outputs["Color"], node.inputs["Color"])
        tree.links.new(node.outputs["Combined"], toSocket)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MakeDecal,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
