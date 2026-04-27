# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .node import Node, Instance
from .utils import *
from .cycles import CyclesMaterial, CyclesTree
from .material import Material, WHITE, BLACK
from .error import reportError

#-------------------------------------------------------------
#   Light base class
#-------------------------------------------------------------

def getMinLightSettings():
    return [("use_shadow", "=", True),
            ("shadow_buffer_clip_start", "<", 1.0*GS.scale),
            ("shadow_buffer_bias", "<", 0.01),
            ("use_contact_shadow", "=", True),
            ("contact_shadow_bias", "<", 0.01),
            ("contact_shadow_distance", "<", 1.0*GS.scale),
            ("contact_shadow_thickness", "<", 10*GS.scale),
           ]


class Light(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.type = None
        self.info = {}
        self.presentation = {}
        self.data = None
        self.twosided = False


    def __repr__(self):
        return ("<Light %s %s>" % (self.id, self.rna))


    def parse(self, struct):
        Node.parse(self, struct)
        if "spot" in struct.keys():
            self.type = 'SPOT'
            self.info = struct["spot"]
        elif "point" in struct.keys():
            self.type = 'POINT'
            self.info = struct["point"]
        elif "directional" in struct.keys():
            self.type = 'DIRECTIONAL'
            self.info = struct["directional"]
        elif "extra" in struct.keys():
            for extra in struct["extra"]:
                if extra.get("type") == "studio/node/light/daz_shader":
                    self.type = extra.get("definition")
        else:
            self.presentation = struct["presentation"]
            print("Strange light", self.name, self.presentation)

    def makeInstance(self, fileref, struct):
        return LightInstance(fileref, self, struct)


    def build(self, context, inst):
        lgeo = inst.getValue(["Light Geometry"], 0)
        self.twosided = inst.getValue(["Two Sided"], False)
        usePhoto = inst.getValue(["Photometric Mode"], False)
        width = inst.getValue(["Width"], 10) * GS.scale
        height = inst.getValue(["Height"], 10) * GS.scale

        # [ "Point", "Rectangle", "Disc", "Sphere", "Cylinder" ]
        if self.type == 'POINT':
            light = bpy.data.lights.new(self.name, "POINT")
            light.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'DIRECTIONAL':
            light = bpy.data.lights.new(self.name, "SUN")
            light.shadow_soft_size = height/2
            self.twosided = False
            if LS.distantLight is None:
                LS.distantLight = self
        elif self.type in [
            "support/DAZ/Uber/shaderDefinitions/light/omUberEnvironment2Def.dse"
            ]:
            worldmat = WorldMaterial(None, inst)
            worldmat.build(context)
            context.scene.world = self.rna = worldmat.rna
            return
        else:
            light = bpy.data.lights.new(self.name, "AREA")
            light.shape = ('RECTANGLE' if lgeo == 1 else 'DISK')
            if lgeo == 0:
                light.size = light.size_y = 0.1*GS.scale
            else:
                light.size = width
                light.size_y = height
            spread = inst.getValue(["Spread Angle"], 60) * D
            beam = inst.getValue(["Beam Exponent"], 1)
            light.spread = spread / (1 + (beam - 1) * 0.05)
            if self.type not in ['light', 'SPOT']:
                msg = ("Unknown light type: %s" % self.type)
                reportError(msg, trigger=(1,5))

        for attr,op,value in getMinLightSettings():
            if hasattr(light, attr):
                setattr(light, attr, value)
        self.data = light
        Node.build(self, context, inst)


    def postTransform(self):
        if GS.zup:
            ob = self.rna
            ob.rotation_euler[0] += pi/2


    def postbuild(self, context, inst):
        Node.postbuild(self, context, inst)
        if self.twosided:
            if inst.rna:
                ob = inst.rna
                activateObject(context, ob)
                bpy.ops.object.duplicate_move()
                nob = getActiveObject(context)
                nob.data = ob.data
                nob.scale = -ob.scale

#-------------------------------------------------------------
#   LightInstance
#-------------------------------------------------------------

class LightInstance(Instance):
    def buildChannels(self, context):
        Instance.buildChannels(self, context)
        light = self.rna.data
        if hasattr(light, "use_shadow"):
            light.use_shadow = self.getValue(["Cast Shadows"], 0)
        else:
            light.cycles.cast_shadow = self.getValue(["Cast Shadows"], 0)

        from .material import srgbToLinearCorrect
        intens = self.getValue(["Intensity"], 1.0)
        flux = self.getValue(["Flux"], 15000)
        factor = (3 if light.type == 'POINT' else 1)
        light.energy = intens * flux/15000 * factor

        color = self.getValue(["Color"], WHITE)
        color = srgbToLinearCorrect(color)
        temp = self.getValue(["Temperature"], 6500)
        if hasattr(light, "temperature"):
            light.color = color
            light.use_temperature  = True
            light.temperature = temp
        else:
            def kelvin_to_rgb(temperature):
                T = temperature / 100
                if T <= 66:
                    red = 255
                else:
                    red = 329.698727446 * (T - 60)**-0.1332047592
                if T <= 66:
                    green = 99.4708025861 * math.log(T) - 161.1195681661
                else:
                    green = 288.1221695283 * (T - 60)**-0.0755148492
                if T >= 66:
                    blue = 255
                elif T <= 19:
                    blue = 0
                else:
                    blue = 138.5177312231 * math.log(T - 10) - 305.0447927307
                return Vector([red, green, blue]) / 255

            rgb = kelvin_to_rgb(temp)
            for n,factor in enumerate(rgb):
                color[n] *= factor
            light.color = color

        if hasattr(light, "shadow_color"):
            light.shadow_color = self.getValue(["Shadow Color"], BLACK)
        if hasattr(light, "shadow_buffer_soft"):
            light.shadow_buffer_soft = self.getValue(["Shadow Softness"], False)
        if hasattr(light, "falloff_type"):
            value = self.getValue(["Decay"], 2)
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            light.falloff_type = dtypes[value]

#-------------------------------------------------------------
#   For animation
#-------------------------------------------------------------

def getBlenderData(light, dazdata, btn, frame):
    def getNode(ntype):
        if not BLENDER5 or light.use_nodes:
            btn.dataRnas.add((light.node_tree, 'NODETREE'))
            for node in light.node_tree.nodes:
                if node.type == ntype:
                    return node
        return None

    def setNode(node, channel, value):
        node.inputs[channel].default_value = value
        if btn.useInsertKeys:
            node.inputs[channel].keyframe_insert("default_value", frame=frame)

    from .material import srgbToLinearCorrect
    bdata = {}
    for key,value in dazdata.items():
        if key == "Color":
            bdata["color"] = srgbToLinearCorrect(value)
        elif key == "Intensity":
            bdata["energy"] = value
        elif key == "Shadow Color":
            bdata["shadow_color"] = value
        elif key == "Shadow Softness":
            bdata["shadow_buffer_soft"] = value
        elif key == "Decay":
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            bdata["falloff_type"] = dtypes[value]
        elif key == "Temperature":
            node = getNode('BLACKBODY')
            if node:
                setNode(node, "Temperature", value)
        elif key == "Flux":
            node = getNode('EMISSION')
            if node:
                factor = (3 if light.type == 'POINT' else 1)
                setNode(node, "Strength", factor*value/15000)
        btn.olddata[key] = value
    return bdata


def getDazKeys():
    return {
        "color" : "Color",
        "energy" : "Intensity",
        "shadow_color" : "Shadow Color",
        "shadow_buffer_soft" : "Shadow Softness",
        "falloff_type" : "Decay",
        'nodes["Emission"].inputs[1].default_value' : "Intensity",
    }

#-------------------------------------------------------------
#   Cycles World Material
#-------------------------------------------------------------

class WorldMaterial(CyclesMaterial):
    def __init__(self, fileref, inst):
        CyclesMaterial.__init__(self, fileref)
        self.name = inst.name
        self.channels = inst.channels
        self.instance = inst
        for key in self.channels.keys():
            print(key, self.getValue([key], None))


    def guessColor(self):
        return


    def build(self, context):
        self.setupBasics()
        if self.dontBuild():
            return False
        world = bpy.data.worlds.new(self.name)
        self.rna = world
        self.tree = WorldTree(self)
        self.tree.build()
        return world


class WorldTree(CyclesTree):
    def __init__(self, owner):
        CyclesTree.__init__(self, owner)
        self.type = 'World'


    def build(self):
        from .tree import pruneNodeTree
        self.makeTree("Generated")

        mapping = self.addNode("ShaderNodeMapping", 1)
        mapping.vector_type = 'TEXTURE'
        mapping.inputs["Location"].default_value = (0,0,-0.5)
        mapping.inputs["Rotation"].default_value = (pi/2,0,0)
        self.linkVector(self.texco, mapping)
        self.texco = mapping.outputs["Vector"]

        color,tex,_ = self.getColorTex(["Color"], "COLOR", WHITE)
        strength = self.getValue(["Strength"], 1.0)
        scale = self.getValue(["Intensity Scale"], 1.0)
        envnode = self.addNode("ShaderNodeBackground")
        envnode.inputs["Strength"].default_value = strength*scale
        self.linkColor(tex, envnode, color, "Color")

        output = self.addNode("ShaderNodeOutputWorld", 3)
        self.links.new(envnode.outputs["Background"], output.inputs["Surface"])

        if GS.usePruneNodes:
            pruneNodeTree(self, usePruneTexco=False)



