# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from random import random
from .utils import *
from .error import *

def getMaterialType(mat, defaultType='CLOTHES'):
    if dazRna(mat).DazMaterialType:
        return dazRna(mat).DazMaterialType

    SkinMaterials = {
        "eyelash" : 'BLACK',
        "eyelashes" : 'BLACK',
        "eyemoisture" : 'INVIS',
        "lacrimal" : 'INVIS',
        "lacrimals" : 'INVIS',
        "cornea" : 'INVIS',
        "tear" : 'INVIS',
        "eyereflection" : 'INVIS',

        "fingernail" : 'RED',
        "fingernails" : 'RED',
        "toenail" : 'RED',
        "toenails" : 'RED',
        "lip" : 'RED',
        "lips" : 'RED',
        "mouth" : 'MOUTH',
        "tongue" : 'MOUTH',
        "innermouth" : 'MOUTH',
        "gums" : 'MOUTH',
        "teeth" : 'WHITE',
        "pupil" : 'BLACK',
        "pupils" : 'BLACK',
        "sclera" : 'WHITE',
        "iris" : 'BLUE',
        "irises" : 'BLUE',
        "eye_left" : 'BLUE',
        "eye_right" : 'BLUE',
        "highlight" : 'WHITE',
        "shadow" : 'SHADOW',

        "skinface" : 'SKIN',
        "face" : 'SKIN',
        "head" : 'SKIN',
        "ears" : 'SKIN',
        "skinleg" : 'SKIN',
        "legs" : 'SKIN',
        "skintorso" : 'SKIN',
        "torso" : 'SKIN',
        "body" : 'SKIN',
        "skinarm" : 'SKIN',
        "arms" : 'SKIN',
        "feet" : 'SKIN',
        "skinhip" : 'SKIN',
        "hips" : 'SKIN',
        "shoulders" : 'SKIN',
        "skinhand" : 'SKIN',
        "hands" : 'SKIN',
    }

    mname = mat.name.lower().split("-")[0].split(".")[0].split(" ")[0].split("&")[0]
    if mname in SkinMaterials.keys():
        return SkinMaterials[mname]
    mname2 = mname.rsplit("_", 2)[-1]
    if mname2 in SkinMaterials.keys():
        return SkinMaterials[mname2]
    return defaultType


def setDiffuse(mat, color):
    mat.diffuse_color[0:3] = color[0:3]


def guessMaterialColor(mat, choose, enforce, default, defaultType='CLOTHES'):
    if mat is None:
        return
    mtype = getMaterialType(mat, defaultType)
    dazRna(mat).DazMaterialType = mtype
    if not hasDiffuseTexture(mat, enforce):
        return

    elif choose == 'RANDOM':
        from random import random
        color = (random(), random(), random(), 1)
        setDiffuse(mat, color)

    elif choose in ['GUESS', 'GLOBAL']:
        if mat.diffuse_color[3] < 1.0:
            pass
        elif mtype == 'SKIN':
            setDiffuse(mat, default)
        elif mtype == 'RED':
            setDiffuse(mat, (1,0,0,1))
        elif mtype == 'MOUTH':
            setDiffuse(mat, (0.8,0,0,1))
        elif mtype == 'BLUE':
            setDiffuse(mat, (0,0,1,1))
        elif mtype == 'WHITE':
            setDiffuse(mat, (1,1,1,1))
        elif mtype == 'BLACK':
            setDiffuse(mat, (0,0,0,1))
        elif mtype == 'INVIS':
            setDiffuse(mat, (0.5,0.5,0.5,0))
        elif mtype == 'SHADOW':
            mat.diffuse_color = (0.5,0.5,0.5,0.2)
        else:
            setDiffuse(mat, default)


def hasDiffuseTexture(mat, enforce):
    from .material import isWhite
    if mat.node_tree:
        color = (1,1,1,1)
        node = None
        for node1 in mat.node_tree.nodes.values():
            if node1.type == 'BSDF_DIFFUSE':
                node = node1
                name = "Color"
            elif node1.type == 'BSDF_PRINCIPLED':
                node = node1
                name = "Base Color"
            elif node1.type in ['HAIR_INFO', 'BSDF_HAIR', 'BSDF_HAIR_PRINCIPLED']:
                return False
        if node is None:
            return True
        color = node.inputs[name].default_value
        for link in mat.node_tree.links:
            if (link.to_node == node and
                link.to_socket.name == name):
                return True
        setDiffuse(mat, color)
        return False
    else:
        if not isWhite(mat.diffuse_color) and not enforce:
            return False
        for mtex in mat.texture_slots:
            if mtex and mtex.use_map_color_diffuse:
                return True
        return False

#-------------------------------------------------------------
#   Change colors
#-------------------------------------------------------------

class ColorProp:
    color : FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.1, 0.1, 0.5, 1)
    )

    def draw(self, context):
        self.layout.prop(self, "color")


class DAZ_OT_ChangeColors(DazPropsOperator, ColorProp, IsMesh):
    bl_idname = "daz.change_colors"
    bl_label = "Change Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    setDiffuse(mat, self.color)


class DAZ_OT_ChangeSkinColor(DazPropsOperator, ColorProp, IsMesh):
    bl_idname = "daz.change_skin_color"
    bl_label = "Change Skin Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                guessMaterialColor(mat, 'GUESS', True, self.color)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangeColors,
    DAZ_OT_ChangeSkinColor,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


