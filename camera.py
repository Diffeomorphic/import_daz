# Copyright (c) 2016-2023, Thomas Larsson
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

class Camera(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.perspective = {}
        self.orthographic = {}
        self.aspectRatio = 1.0


    def __repr__(self):
        return ("<Camera %s>" % (self.id))


    def parse(self, struct):
        Node.parse(self, struct)
        if "perspective" in struct.keys():
            self.perspective = struct["perspective"]
        elif "orthographic" in struct.keys():
            self.orthographic = struct["orthographic"]


    def postTransform(self):
        if GS.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2


    def makeInstance(self, fileref, struct):
        return CameraInstance(fileref, self, struct)


    def build(self, context, inst):
        if self.perspective:
            self.data = bpy.data.cameras.new(self.name)
            inst.setCameraProps(self.perspective)
        elif self.orthographic:
            self.data = bpy.data.cameras.new(self.name)
            inst.setCameraProps(self.orthographic)
        else:
            return None
        Node.build(self, context, inst)


class CameraInstance(Instance):

    def setCameraProps(self, props):
        camera = self.node.data
        for key,value in props.items():
            if key == "znear" :
                camera.clip_start = value * LS.scale
            elif key == "zfar" :
                camera.clip_end = value * LS.scale
            elif key == "yfov" :
                pass
            elif key == "focal_length" :
                camera.lens = value
            elif key == "depth_of_field" :
                camera.dof.use_dof = value
            elif key == "focal_distance" :
                camera.dof.focus_distance = value * LS.scale
            elif key == "fstop" :
                camera.dof.aperture_fstop = value
            else:
                print("Unknown camera prop: '%s' %s" % (key, value))


    def buildChannels(self, context):
        from .utils import getCurrentValue, D

        camera = self.rna.data
        camera.sensor_height = 64
        camera.sensor_fit = 'VERTICAL'
        for key,channel in self.channels.items():
            value = channel.get("current_value")
            if value is None:
                continue
            elif key == "Lens Shift X" :
                camera.shift_x = value * LS.scale
            elif key == "Lens Shift Y" :
                camera.shift_y = value * LS.scale
            elif key == "Focal Length":
                camera.lens = value         # in mm
            elif key == "DOF":
                camera.dof.use_dof = value
            elif key == "Depth of Field":
                camera.dof.focus_distance = value * LS.scale
            elif key == "Frame Width":
                # https://bitbucket.org/Diffeomorphic/import-daz/issues/75/better-cameras
                camera.sensor_height = value
            elif key == "Aspect Ratio":
                if value[0] != 0:
                    self.aspectRatio = value[1]/value[0]
            elif key == "Aperture Blades":
                camera.dof.aperture_blades = value
            elif key == "Aperture Blade Rotation":
                camera.dof.aperture_rotation = value*D

            elif key in ["Point At", "Renderable", "Visible", "Selectable", "Perspective",
                        "Render Priority", "Cast Shadows", "Pixel Size",
                        "Lens Stereo Offset", "Lens Radial Bias", "Lens Stereo Offset",
                        "Lens Distortion Type", "Lens Distortion K1", "Lens Distortion K2", "Lens Distortion K3", "Lens Distortion Scale",
                        "DOF", "Aperature", "Disable Transform", "Visible in Simulation",
                        "Lens Thickness", "Local Dimensions", "Dimension Preset", "Constrain Proportions",
                        "HeadlampMode", "Headlamp Intensity", "XHeadlampOffset", "YHeadlamp", "ZHeadlampOffset",
                        "Display Persistence", "Sight Line Opacity",
                        "Focal Point Scale", "FOV Color", "FOV Opacity", "FOV Length",
                        "DOF Plane Visibility", "DOF Plane Color",
                        "Visible in Viewport",
                        "DOF Overlay Color", "DOF Overlay Opacity", "Near DOF Plane Visibility", "Far DOF Plane Visibility",
                        ]:
                #print("Unused", key, value)
                pass
            elif GS.verbosity > 2:
                print("Unknown camera channel '%s' %s" % (key, value))
