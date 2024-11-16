#  DAZ Materials - Tools for editing materials imported with the DAZ Importer
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
from ..utils import *
from ..error import *

# ---------------------------------------------------------------------
#   Launch button
# ---------------------------------------------------------------------

class DAZ_OT_LaunchEditor(MaterialSelector, DazPropsOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}

    shows : CollectionProperty(type = ShowGroup)

    useAllMaterials : BoolProperty(
        name = "All Materials",
        description = "Affect all materials of all selected meshes",
        default = False)

    useChangedOnly : BoolProperty(
        name = "Only Modified Channels",
        description = "Only update channels that have been modified by the material editor",
        default = True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "useAllMaterials")
        row.prop(self, "useChangedOnly")
        if not self.useAllMaterials:
            MaterialSelector.draw(self, context)
        self.drawActive(context)
        group = None
        items = []
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                if group:
                    self.drawGroup(group)
                items = []
                group = (key, items)
            elif key in self.matSlots.keys():
                items.append( (key, self.matSlots[key]) )
        if group:
            self.drawGroup(group)
        self.layout.operator("daz.update_materials")


    def drawGroup(self, group):
        section,items = group
        if not items:
            return
        elif not self.shows[section].show:
            self.layout.prop(self.shows[section], "show", icon="RIGHTARROW", emboss=False, text=section)
            return
        self.layout.prop(self.shows[section], "show", icon="DOWNARROW_HLT", emboss=False, text=section)
        nchars = len(section)
        for key,item in items:
            row = self.layout.row()
            if key[0:nchars] == section:
                text = item.name[nchars+1:]
            else:
                text = item.name
            row.label(text=text)
            if item.ncomps == 4:
                row.prop(item, "color", text="")
            elif item.ncomps == 1:
                row.prop(item, "number", text="")
            elif item.ncomps == 3:
                row.prop(item, "vector", text="")
            else:
                print("WAHT")


    def invoke(self, context, event):
        self.setupMaterialSelector(context)
        self.shows.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                item = self.shows.add()
                item.name = key
                item.show = False
                continue
        self.addSlots(context)
        return DazPropsOperator.invoke(self, context, event)


    def isDefaultActive(self, mat, ob):
        return self.isSkinRedMaterial(mat)


    def run(self, context):
        ob = context.object
        for ob1 in getSelectedMeshes(context):
            for item in self.matSlots:
                self.setEditChannel(ob1, item)


    def setEditChannel(self, ob, item):
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.setChannelCycles(mat, item)
                beautifyNodeTree(mat.node_tree)


    def getObjectSlot(self, mat, key):
        for item in mat.DazSlots:
            if item.name == key:
                return item
        item = mat.DazSlots.add()
        item.name = key
        item.new = True
        return item


    def setOriginal(self, socket, ncomps, mat, key):
        item = self.getObjectSlot(mat, key)
        if item.new:
            value = socket.default_value
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            item.new = False


    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        x,y = node.location
        if item.ncomps == 4 and not isWhite(item.color):
            mix = tree.nodes.new(type = MixRGB.Nodetype)
            mix.location = (x-XSIZE+50,y-12*YSTEP)
            mix.blend_type = 'MULTIPLY'
            if bpy.app.version >= (3,4,0):
                mix.data_type = 'RGBA'
            mix.inputs[0].default_value = 1.0
            mix.inputs[MixRGB.Color1].default_value = item.color
            tree.links.new(fromsocket, mix.inputs[MixRGB.Color2])
            tree.links.new(mix.outputs[MixRGB.ColorOut], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type = "ShaderNodeMath")
            mult.location = (x-XSIZE+50,y-12*YSTEP)
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.links.new(fromsocket, mult.inputs[1])
            tree.links.new(mult.outputs[0], tosocket)
            return mult


class DAZ_OT_UpdateMaterials(bpy.types.Operator):
    bl_idname = "daz.update_materials"
    bl_label = "Update Materials"
    bl_description = "Update Materials"

    def execute(self, context):
        global theMaterialEditor
        theMaterialEditor.run(context)
        return {'PASS_THROUGH'}


# ---------------------------------------------------------------------
#   Reset button
# ---------------------------------------------------------------------

class DAZ_OT_ResetMaterials(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_materials"
    bl_label = "Reset Materials"
    bl_description = "Reset materials to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.resetObject(ob)


    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                for item in mat.DazSlots:
                    self.setChannelCycles(mat, item)
                    item.new = True
                mat.DazSlots.clear()


    def setOriginal(self, socket, ncomps, item, key):
        pass

    def useMaterial(self, mat):
        return True

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        pass

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_LaunchEditor,
    DAZ_OT_UpdateMaterials,
    DAZ_OT_ResetMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
