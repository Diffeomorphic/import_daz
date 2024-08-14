#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.


import bpy
import math
from .node import Node, Instance
from .utils import *

class Camera(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.perspective = {}
        self.orthographic = {}


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
                camera.clip_start = value * GS.scale
            elif key == "zfar" :
                camera.clip_end = value * GS.scale
            elif key == "yfov" :
                pass
            elif key == "focal_length" :
                camera.lens = value
            elif key == "depth_of_field" :
                camera.dof.use_dof = value
            elif key == "focal_distance" :
                camera.dof.focus_distance = value * GS.scale
            elif key == "fstop" :
                camera.dof.aperture_fstop = value
            else:
                print("Unknown camera prop: '%s' %s" % (key, value))


    def buildChannels(self, context):
        camera = self.rna.data
        camera.sensor_fit = 'VERTICAL'
        for key,channel in self.channels.items():
            value = self.getChannelValue(channel, None)
            if value is None:
                continue
            elif key == "Lens Shift X" :
                camera.shift_x = value * GS.scale
            elif key == "Lens Shift Y" :
                camera.shift_y = value * GS.scale
            elif key == "Focal Length":
                camera.lens = value         # in mm
            elif key == "DOF":
                camera.dof.use_dof = value
            elif key == "Depth of Field":
                camera.dof.focus_distance = value * GS.scale
            elif key == "Frame Width":
                camera.sensor_height = value
            elif key == "Aspect Ratio":
                pass
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
            elif GS.verbosity >= 3:
                print("Unknown camera channel '%s' %s" % (key, value))
