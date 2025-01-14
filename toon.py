# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .cycles import CyclesTree
from .material import WHITE, BLACK, isBlack
from .tree import colorOutput
from .utils import *

#------------------------------------------------------------------
#   Toon Tree
#------------------------------------------------------------------

class ToonTree(CyclesTree):
    def __init__(self, cmat):
        CyclesTree.__init__(self, cmat)
        self.type = 'TOON'


    def buildLayer(self, uvname):
        self.buildNormal(uvname)
        self.buildBump(uvname)
        self.column = 4
        self.buildDiffuse()
        self.buildRim()
        self.buildGlossy()
        self.buildLight()
        self.buildEmission()


    def buildBumpMap(self, bumpval, bumptex):
        bump = self.addNode("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bumpval
        self.links.new(colorOutput(bumptex), bump.inputs["Height"])
        bump.inputs["Distance"].default_value = 0.2 * GS.scale * GS.bumpMultiplier
        return bump


    def correctBumpArea(self, geo, me):
        pass


    def buildDiffuse(self):
        from .cgroup import ToonDiffuseGroup
        color,tex = self.getDiffuseColor()
        node = self.addGroup(ToonDiffuseGroup, "DAZ Toon Diffuse")
        self.linkColor(tex, node, color, "Color")
        threshold = self.getValue(["Shadow Threshold"], 0)
        if threshold == -1:
            node.inputs["Ambience"].default_value[0:3] = WHITE
        else:
            amb,ambtex,texslot = self.getColorTex(["Ambient"], "COLOR", WHITE)
            self.linkColor(ambtex, node, amb, "Ambience")
        self.linkBumpNormal(node)
        self.cycles = self.diffuse = node
        LS.usedFeatures["Diffuse"] = True


    def buildShellGroups(self, shells):
        LS.rimtoons.append(self.owner.geometry)


    def buildGlossy(self):
        fac = self.getValue(["Glossy Layered Weight"], 0)
        if fac == 0:
            return
        from .cgroup import ToonGlossyGroup
        node = self.addGroup(ToonGlossyGroup, "DAZ Toon Glossy")
        refl,refltex,texslot = self.getColorTex(["Glossy Reflectivity"], "COLOR", WHITE)
        rough,roughtex,texslot = self.getColorTex(["Glossy Roughness"], "NONE", 0.0)
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.linkColor(refltex, node, refl*fac, "Reflection")
        self.linkScalar(roughtex, node, rough, "Roughness")
        self.linkBumpNormal(node)
        self.cycles = node
        LS.usedFeatures["Glossy"] = True


    def buildRim(self):
        rim = self.getValue(["Rim Amount"], 0)
        if rim == 0:
            return
        from .cgroup import ToonRimGroup
        node = self.addGroup(ToonRimGroup, "DAZ Toon Rim")
        color,tex,texslot = self.getColorTex(["Rim Color"], "COLOR", WHITE)
        rim,rimtex,texslot = self.getColorTex(["Rim Amount"], "NONE", 0)
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.linkScalar(rimtex, node, rim, "Rim")
        self.linkColor(tex, node, color, "Color")
        self.linkBumpNormal(node)
        self.cycles = node
        LS.usedFeatures["Rim"] = True


    def buildLight(self):
        from .cgroup import ToonLightGroup
        node = self.addGroup(ToonLightGroup, "DAZ Toon Light")
        if self.cycles:
            self.links.new(self.cycles.outputs["Output"], node.inputs["Input"])
        self.cycles = node


    def setRenderSettings(self):
        mat = self.owner.rna
        if mat:
            mat.surface_render_method = 'BLENDED'


#------------------------------------------------------------------
#   Add toons to collection
#------------------------------------------------------------------

def addToons(context):
    def addCollection(cname, objects):
        coll = bpy.data.collections.new(cname)
        layer = getLayerCollection(context, coll)
        if layer:
            layer.exclude = True
        for ob in objects:
            coll.objects.link(ob)
        return coll

    toons = set(LS.toons)
    print("Toons: %s" % [ob.name for ob in toons])
    rimtoons = [geonode.rna for geonode in set(LS.rimtoons) if geonode.rna and geonode.rna.type == 'MESH']
    print("Rim: %s" % [ob.name for ob in rimtoons])
    if GS.toonMethod in ['FREESTYLE', 'LINEART']:
        rimcoll = addCollection("DAZ Toon Outline", rimtoons)
        LS.collection.children.link(rimcoll)

    if GS.toonMethod == 'FREESTYLE':
        scn = context.scene
        scn.render.use_freestyle = True
        fset = context.view_layer.freestyle_settings
        lineset = fset.linesets.active
        lineset.collection = rimcoll
        lineset.select_by_collection = True

    elif GS.toonMethod == 'LINEART':
        bpy.ops.object.grease_pencil_add(type='LINEART_OBJECT')
        lineart = context.object
        lineart.name = "%s Line Art" % LS.collection.name
        if lineart.name not in LS.collection.objects.keys():
            LS.collection.objects.link(lineart)
        mat = lineart.data.materials[0]
        mat.grease_pencil.show_fill = True
        mod = lineart.modifiers[0]
        mod.source_type = 'COLLECTION'
        mod.source_collection = rimcoll

    elif GS.toonMethod == 'SOLIDIFY':
        from .material import BLACK
        mat = bpy.data.materials.get("DAZ Toon Outline")
        if mat is None:
            mat = bpy.data.materials.new("DAZ Toon Outline")
        mat.use_nodes = True
        mat.use_backface_culling = True
        mat.diffuse_color[0:3] = BLACK
        tree = mat.node_tree
        tree.nodes.clear()
        rgb = tree.nodes.new("ShaderNodeRGB")
        rgb.location = (0, 0)
        rgb.outputs["Color"].default_value[0:3] = BLACK
        output = tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (200, 0)
        output.target = 'ALL'
        tree.links.new(rgb.outputs["Color"], output.inputs["Surface"])

        shading = context.scene.display.shading
        shading.light = 'MATCAP'
        shading.show_backface_culling = True
        shading.show_object_outline = False
        print("SS", shading, shading.light)

        for ob in rimtoons:
            ob.data.materials.append(mat)
            mod = ob.modifiers.new("Outline", 'SOLIDIFY')
            mod.thickness = -1*GS.scale
            mod.use_flip_normals = True
            mod.use_rim = False
            mod.material_offset = 100


    lname = "DAZ Toon Light"
    if LS.distantLight:
        light = LS.distantLight.rna
    if light is None:
        sun = bpy.data.lights.new(lname, "SUN")
        light = bpy.data.objects.new(lname, sun)
        LS.collection.objects.link(light)
    coll = addCollection(lname, toons)
    light.light_linking.receiver_collection = coll
