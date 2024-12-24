# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
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
        else:
            self.presentation = struct["presentation"]
            print("Strange light", self)

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
            inst.fluxFactor = 3
            self.twosided = False
        elif self.type == 'DIRECTIONAL':
            light = bpy.data.lights.new(self.name, "SUN")
            light.shadow_soft_size = height/2
            self.twosided = False
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
        if usePhoto:
            inst.material.rna = light
            inst.material.build(context)


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
    def __init__(self, fileref, node, struct):
        Instance.__init__(self, fileref, node, struct)
        self.material = LightMaterial(fileref, self)
        self.fluxFactor = 1


    def buildChannels(self, context):
        Instance.buildChannels(self, context)
        light = self.rna.data
        if self.getValue(["Cast Shadows"], 0):
            light.cycles.cast_shadow = True
        else:
            light.cycles.cast_shadow = False

        from .material import srgbToLinearCorrect
        color = self.getValue(["Color"], WHITE)
        light.color = srgbToLinearCorrect(color)
        light.energy = self.getValue(["Intensity"], 1.0)

        if hasattr(light, "shadow_color"):
            light.shadow_color = self.getValue(["Shadow Color"], BLACK)
        if hasattr(light, "shadow_buffer_soft"):
            light.shadow_buffer_soft = self.getValue(["Shadow Softness"], False)
        if hasattr(light, "falloff_type"):
            value = self.getValue(["Decay"], 2)
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            light.falloff_type = dtypes[value]

#-------------------------------------------------------------
#   Cycles Light Material
#-------------------------------------------------------------

class LightMaterial(CyclesMaterial):
    def __init__(self, fileref, inst):
        CyclesMaterial.__init__(self, fileref)
        self.name = inst.name
        self.channels = inst.channels
        self.instance = inst

    def guessColor(self):
        return

    def build(self, context):
        self.setupBasics()
        if self.dontBuild():
            return False
        self.tree = LightTree(self)
        self.tree.build()


class LightTree(CyclesTree):
    def __init__(self, owner):
        CyclesTree.__init__(self, owner)
        self.type = 'LIGHT'


    def build(self):
        self.makeTree()

        blackbody = self.addNode("ShaderNodeBlackbody", 1)
        blackbody.inputs["Temperature"].default_value = self.getValue(["Temperature"], 6500)

        emit = self.addNode("ShaderNodeEmission", 2)
        self.links.new(blackbody.outputs["Color"], emit.inputs["Color"])
        factor = self.owner.instance.fluxFactor / 15000
        emit.inputs["Strength"].default_value = factor * self.getValue(["Flux"], 15000)

        output = self.addNode("ShaderNodeOutputLight", 3)
        self.links.new(emit.outputs[0], output.inputs["Surface"])


    def addTexco(self, slot):
        return



