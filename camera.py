# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
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
            ob.rotation_euler[0] += pi/2


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


    def buildChannels(self, ob):
        camera = ob.data
        camera.sensor_fit = 'VERTICAL'
        persp = None
        length = None
        dist = None
        for key,channel in self.channels.items():
            value = self.getChannelValue(channel, None)
            if value is None:
                continue
            elif key == "Lens Shift X" :
                camera.shift_x = value * GS.scale
            elif key == "Lens Shift Y" :
                camera.shift_y = value * GS.scale
            elif key == "Focal Length":
                length = value
                camera.lens = value
            elif key == "DOF":
                camera.dof.use_dof = value
            elif key == "Depth of Field":
                dist = value
                camera.dof.focus_distance = value * GS.scale
            elif key == "Frame Width":
                camera.sensor_height = value
            elif key == "Aspect Ratio":
                pass
            elif key == "Aperture Blades":
                camera.dof.aperture_blades = value
            elif key == "Aperture Blade Rotation":
                camera.dof.aperture_rotation = value*D
            elif key == "Perspective":
                persp = value

            elif key in ["Point At", "Renderable", "Visible", "Selectable",
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

        if not persp:
            camera.type = 'ORTHO'
            if dist and length:
                camera.ortho_scale = dist/length * 0.34

#-------------------------------------------------------------
#   For animation
#-------------------------------------------------------------

def getBlenderData(camera, dazdata, btn, frame):
    bdata = {}
    if camera.type == 'ORTHO':
        length = dazdata.get("Focal Length")
        if length is None:
            length = btn.olddata.get("Focal Length")
        dist = dazdata.get("Depth of Field")
        if dist is None:
            dist = btn.olddata.get("Depth of Field")
        if dist and length:
            bdata["ortho_scale"] = dist/length * 0.34
    for key,value in dazdata.items():
        if key == "Lens Shift X" :
            bdata["shift_x"] = value * GS.scale
        elif key == "Lens Shift Y" :
            bdata["shift_y"] = value * GS.scale
        elif key == "Focal Length":
            bdata["lens"] = value
        elif key == "DOF":
            bdata["dof.use_dof"] = value
        elif key == "Depth of Field":
            bdata["dof.focus_distance"] = value * GS.scale
        elif key == "Frame Width":
            bdata["sensor_height"] = value
        elif key == "Aperture Blades":
            bdata["dof.aperture_blades"] = value
        elif key == "Aperture Blade Rotation":
            bdata["dof.aperture_rotation"] = value*D
        btn.olddata[key] = value
    return bdata

def getDazKeys():
    return {
        "ortho_scale" : "Focal Length",
        "shift_x" : "Lens Shift X",
        "shift_y" : "Lens Shift Y",
        "lens" : "Focal Length",
        "dof.use_dof" : "DOF",
        "dof.focus_distance" : "Depth of Field",
        "sensor_height" : "Frame Width",
        "dof.aperture_blades" : "Aperture Blades",
        "dof.aperture_rotation" : "Aperture Blade Rotation",
    }
