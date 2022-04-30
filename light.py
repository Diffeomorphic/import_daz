# Copyright (c) 2016-2022, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import bpy
import math
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
            ("shadow_buffer_clip_start", "<", 1.0*LS.scale),
            ("shadow_buffer_bias", "<", 0.01),
            ("use_contact_shadow", "=", True),
            ("contact_shadow_bias", "<", 0.01),
            ("contact_shadow_distance", "<", 1.0*LS.scale),
            ("contact_shadow_thickness", "<", 10*LS.scale),
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
        lgeo = inst.getValue(["Light Geometry"], -1)
        usePhoto = inst.getValue(["Photometric Mode"], False)
        self.twosided = inst.getValue(["Two Sided"], False)
        height = inst.getValue(["Height"], 0) * LS.scale
        width = inst.getValue(["Width"], 0) * LS.scale

        # [ "Point", "Rectangle", "Disc", "Sphere", "Cylinder" ]
        if lgeo == 1:
            light = bpy.data.lights.new(self.name, "AREA")
            light.shape = 'RECTANGLE'
            light.size = width
            light.size_y = height
        elif lgeo == 2:
            light = bpy.data.lights.new(self.name, "AREA")
            light.shape = 'DISK'
            light.size = height
        elif lgeo > 1:
            light = bpy.data.lights.new(self.name, "POINT")
            light.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'POINT':
            light = bpy.data.lights.new(self.name, "POINT")
            light.shadow_soft_size = 0
            inst.fluxFactor = 3
            self.twosided = False
        elif self.type == 'SPOT':
            light = bpy.data.lights.new(self.name, "SPOT")
            light.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'DIRECTIONAL':
            light = bpy.data.lights.new(self.name, "SUN")
            light.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'light':
            light = bpy.data.lights.new(self.name, "AREA")
        else:
            msg = ("Unknown light type: %s" % self.type)
            reportError(msg, trigger=(1,3))
            light = bpy.data.lights.new(self.name, "SPOT")
            light.shadow_soft_size = height/2
            self.twosided = False

        for attr,op,value in getMinLightSettings():
            if hasattr(light, attr):
                setattr(light, attr, value)
        self.data = inst.material.rna = light
        Node.build(self, context, inst)
        inst.material.build(context)


    def postTransform(self):
        if GS.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2


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

        light.color = self.getValue(["Color"], WHITE)
        flux = self.getValue(["Flux"], 15000)
        light.energy = flux / 15000
        light.shadow_color = self.getValue(["Shadow Color"], BLACK)
        if hasattr(light, "shadow_buffer_soft"):
            light.shadow_buffer_soft = self.getValue(["Shadow Softness"], False)
        #if hasattr(light, "shadow_buffer_bias"):
        #    bias = self.getValue(["Shadow Bias"], None)
        #    if bias:
        #        light.shadow_buffer_bias = bias
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
        emit.inputs["Strength"].default_value = self.owner.instance.fluxFactor * self.getValue(["Intensity"], 1.0)

        output = self.addNode("ShaderNodeOutputLight", 3)
        self.links.new(emit.outputs[0], output.inputs["Surface"])


    def addTexco(self, slot):
        return



