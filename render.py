# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.props import BoolProperty
import os
from .asset import Asset
from .channels import Channels
from .material import Material, WHITE, BLACK, isBlack
from .tree import addGroupInput, addGroupOutput, getGroupInput
from .cycles import CyclesMaterial, CyclesTree
from .cgroup import CyclesGroup
from .utils import *
from .error import DazPropsOperator

#-------------------------------------------------------------
#   Render Options
#-------------------------------------------------------------

class RenderOptions(Asset, Channels):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.world = None
        self.background = None
        self.backdrop = None


    def initSettings(self, settings, backdrop):
        if "backdrop_visible" in settings.keys():
            if not settings["backdrop_visible"]:
                return
        if "backdrop_visible_in_render" in settings.keys():
            if not settings["backdrop_visible_in_render"]:
                return
        if backdrop:
            self.backdrop = backdrop
        for key,value in settings.items():
            if key == "background_color":
                self.background = value


    def __repr__(self):
        return ("<RenderOptions %s %s>" % (self.background, self.backdrop))


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)
        if "children" in struct.keys():
            for child in struct["children"]:
                if "channels" in child.keys():
                    for channel in child["channels"]:
                        self.setChannel(channel["channel"])


    def update(self, struct):
        Asset.update(self, struct)
        Channels.update(self, struct)


    def build(self, context):
        if LS.worldMethod != 'NEVER':
            self.world = WorldMaterial(self, self.fileref)
            self.world.build(context)

#-------------------------------------------------------------
#   World Material
#-------------------------------------------------------------

class WorldMaterial(CyclesMaterial):

    def __init__(self, render, fileref):
        CyclesMaterial.__init__(self, fileref)
        self.name = os.path.splitext(os.path.basename(fileref))[0] + " World"
        self.channels = render.channels
        self.background = None
        if render.background:
            from .material import srgbToLinearGamma22
            self.background = srgbToLinearGamma22(render.background)
        self.backdrop = render.backdrop
        self.envmap = None


    def guessColor(self):
        return


    def build(self, context):
        if self.dontBuild():
            self.setupBasics()
            return
        mode = self.getValue(["Environment Mode"], 3)
        # [Dome and Scene, Dome Only, Sun-Skies Only, Scene Only]
        if LS.worldMethod != 'ALWAYS' and mode == 3 and not self.background:
            if GS.verbosity >= 3:
                print("Import scene only")
            return

        scn = context.scene
        self.envmap = self.getChannel(["Environment Map"])
        scn.render.film_transparent = False
        if mode in [0,1] and self.envmap:
            print("Draw environment", mode)
            if not self.getValue(["Draw Dome"], False):
                print("Draw Dome turned off")
                scn.render.film_transparent = True
            elif self.getImageFile(self.envmap) is None:
                print("Don't draw environment. Image file not found")
        else:
            self.envmap = None
            if self.background:
                print("Draw background", mode, self.background)
            else:
                scn.render.film_transparent = True
                self.background = BLACK

        self.refractive = False
        Material.build(self, context)
        self.tree = WorldTree(self)

        world = self.rna = bpy.data.worlds.new(self.name)
        if BLENDER5:
            world.use_nodes = True
        self.tree.build()
        scn.world = world
        if self.envmap is None and self.background is None:
            vis = world.cycles_visibility
            vis.camera = True
            vis.diffuse = False
            vis.glossy = False
            vis.transmission = False
            vis.scatter = False

#-------------------------------------------------------------
#   World Tree
#-------------------------------------------------------------

class WorldTree(CyclesTree):

    def __init__(self, wmat):
        CyclesTree.__init__(self, wmat)
        self.type == "WORLD"


    def build(self):
        from .tree import pruneNodeTree
        backdrop = self.owner.backdrop
        background = self.owner.background
        envmap = self.owner.envmap
        self.texco = self.makeTree()
        self.column = 5
        envnode = bgnode = socket = None
        if envmap:
            envnode,socket = self.buildEnvmap(envmap)
        if background:
            from .tree import hideAllBut
            bgnode,socket = self.buildBackground(background, backdrop)
            self.addColumn()
            lightpath = self.addNode("ShaderNodeLightPath", size=2)
            hideAllBut(lightpath, ["Is Camera Ray"])
            mix = self.addNode("ShaderNodeMixShader")
            self.links.new(lightpath.outputs["Is Camera Ray"], mix.inputs["Fac"])
            self.links.new(bgnode.outputs["Background"], mix.inputs[2])
            socket = mix.outputs[0]
            if envnode:
                self.links.new(envnode.outputs["Background"], mix.inputs[1])

        self.addColumn()
        output = self.addNode("ShaderNodeOutputWorld")
        if socket:
            self.links.new(socket, output.inputs["Surface"])
        if GS.usePruneNodes:
            pruneNodeTree(self, usePruneTexco=False)


    def buildEnvmap(self, envmap):
        from mathutils import Euler

        texco = self.texco.outputs["Generated"]
        rot = self.getValue(["Dome Rotation"], 0)
        orx = self.getValue(["Dome Orientation X"], 0)
        ory = self.getValue(["Dome Orientation Y"], 0)
        orz = self.getValue(["Dome Orientation Z"], 0)

        if rot != 0 or orx != 0 or ory != 0 or orz != 0:
            mat1 = Euler((0,0,-rot*D)).to_matrix()
            mat2 = Euler((0,-orz*D,0)).to_matrix()
            mat3 = Euler((orx*D,0,0)).to_matrix()
            mat4 = Euler((0,0,ory*D)).to_matrix()
            mat = mat1 @ mat2 @ mat3 @ mat4
            scale = (1,1,1)
            texco = self.addMapping(mat.to_euler(), scale, texco, 2)

        value = self.owner.getChannelValue(envmap, 1)
        img = self.getImage(envmap, "LINEAR")
        tex = None
        if img:
            tex = self.addNode("ShaderNodeTexEnvironment", 3)
            if img:
                tex.image = img
                tex.name = img.name
            self.links.new(texco, tex.inputs["Vector"])
        strength = self.getValue(["Environment Intensity"], 1) * value

        envnode = self.addNode("ShaderNodeBackground")
        envnode.inputs["Strength"].default_value = strength
        self.linkColor(tex, envnode, WHITE, "Color")
        socket = envnode.outputs["Background"]
        return envnode, socket


    def buildBackground(self, background, backdrop):
        tex = None
        texco = self.texco.outputs["Window"]
        if backdrop:
            if (backdrop["rotation"] != "NO_ROTATION" or
                backdrop["flip_horizontal"] or
                backdrop["flipped_vertical"]):
                if backdrop["rotation"] == "ROTATE_LEFT_90":
                    zrot = 90*D
                elif backdrop["rotation"] == "ROTATE_RIGHT_90":
                    zrot = -90*D
                elif backdrop["rotation"] == "ROTATE_180":
                    zrot = 180*D
                else:
                    zrot = 0
                scale = [1,1,1]
                if backdrop["flip_horizontal"]:
                    scale[0] = -1
                    zrot *= -1
                if backdrop["flipped_vertical"]:
                    scale[1] = -1
                    zrot *= -1
                texco = self.addMapping([0,0,zrot], scale, texco, 2)
            img = self.getImage(backdrop, "COLOR")
            if img:
                tex = self.addTextureNode(3, img, img.name)
                self.setTexNode(img.name, tex, tex, "COLOR")
                self.linkVector(texco, tex)

        bgnode = self.addNode("ShaderNodeBackground")
        self.linkColor(tex, bgnode, background, "Color")
        bgnode.inputs["Strength"].default_value = 1.0
        socket = bgnode.outputs["Background"]
        return bgnode, socket


    def addMapping(self, rot, scale, texco, col):
        mapping = self.addNode("ShaderNodeMapping", col)
        mapping.vector_type = 'TEXTURE'
        if hasattr(mapping, "rotation"):
            mapping.rotation = rot
            mapping.scale = scale
        else:
            mapping.inputs['Rotation'].default_value = rot
            mapping.inputs['Scale'].default_value = scale
        self.links.new(texco, mapping.inputs["Vector"])
        return mapping.outputs["Vector"]


    def getImage(self, channel, colorSpace):
        assets,maps = self.owner.getTextures(channel)
        if not assets:
            return None
        asset = assets[0]
        img = asset.image
        if img is None:
            img,imgname = asset.buildImage(colorSpace)
        return img

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def parseRenderOptions(renderSettings, sceneSettings, backdrop, fileref):
    if not LS.worldMethod:
        return
    else:
        renderOptions = renderSettings["render_options"]
        if "render_elements" in renderOptions.keys():
            if not LS.render:
                LS.render = RenderOptions(fileref)
            LS.render.initSettings(sceneSettings, backdrop)
            for element in renderOptions["render_elements"]:
                LS.render.parse(element)

#-------------------------------------------------------------
#   Utility for rendering a range of frames.
#-------------------------------------------------------------

class DAZ_OT_RenderFrames(bpy.types.Operator):
    bl_idname = "daz.render_frames"
    bl_label = "Render Frames"
    bl_description = "Render a range of frames as still images.\nTo overcome problems with morphing armatures and rendering"

    useAllArmatures : BoolProperty(
        name = "All Armatures",
        description = "Auto morph all visible armatures instead of just the visible ones",
        default = True)

    useOpenGl : BoolProperty(
        name = "Open GL",
        description = "Open GL rendering",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useOpenGl")
        self.layout.prop(self, "useAllArmatures")


    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


    def execute(self, context):
        scn = context.scene
        self.filepath = scn.render.filepath
        self.frame = scn.frame_current
        scn.frame_current = scn.frame_start
        self.rigs = []
        for ob in context.view_layer.objects:
            if (ob.type == 'ARMATURE' and
                not (ob.hide_get() or ob.hide_viewport)):
                self.rigs.append(ob)
        if self.useAllArmatures:
            for rig in self.rigs:
                rig.select_set(True)
        ob = context.object
        if self.rigs and not (ob and ob.type == 'ARMATURE'):
            context.view_layer.objects.active = self.rigs[0]
        wm = context.window_manager
        self.timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


    def modal(self, context, event):
        scn = context.scene
        wm = context.window_manager
        if event.type in {'ESC'}:
            wm.event_timer_remove(self.timer)
            scn.render.filepath = self.filepath
            print("Rendering cancelled")
            return {'CANCELLED'}
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}
        wm.event_timer_remove(self.timer)
        context.evaluated_depsgraph_get().update()
        scn.render.filepath = "%s%04d" % (self.filepath, scn.frame_current)
        try:
            if self.rigs and GS.ercMethod.startswith("Armature"):
                from .runtime.morph_armature import onFrameChangeDaz
                onFrameChangeDaz(scn)
            if self.useOpenGl:
                bpy.ops.render.opengl(animation=False, write_still=True)
            else:
                bpy.ops.render.render(animation=False, write_still=True, use_viewport=True)
            success = True
        except RuntimeError as err:
            success = False
        scn.frame_current += 1
        if scn.frame_current > scn.frame_end or not success:
            scn.render.filepath = self.filepath
            return {'FINISHED'}
        self.timer = wm.event_timer_add(0.1, window=context.window)
        return {'PASS_THROUGH'}


#-------------------------------------------------------------
#   Register
#-------------------------------------------------------------

classes = [
    DAZ_OT_RenderFrames,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)