#  Shell Editor - Tools for manipulating shells and layered images from DAZ Importer
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
from ..matsel import *
from ..selector import Selector
from ..tree import *
from ..geometry import getActiveUvLayer, copyUvLayers
from ..finger import getFingerPrint
from ..cgroup import ShellGroup, CyclesTree
from ..driver import setFloatProp, addDriver


class UniqueMaterials:
    useUniqueMaterials : BoolProperty(
        name = "Unique Materials",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useUniqueMaterials")

    def ensureUnique(self, mat, idx, ob):
        if self.useUniqueMaterials and mat.users > 1:
            nmat = mat.copy()
            ob.data.materials[idx] = nmat
            return nmat
        return mat

# ---------------------------------------------------------------------
#   Remove shells from materials
# ---------------------------------------------------------------------

class ShellRemover:
    def getShells(self, context):
        self.shells = {}
        #for ob in getSelectedMeshes(context):
        for ob in [context.object]:
            for mat in ob.data.materials:
                if mat:
                    for node in mat.node_tree.nodes:
                        if self.isShellNode(node):
                            self.addShell(mat, node, node.node_tree)


    def isShellNode(self, node):
        return isShellNode(node)


    def addItems(self):
        self.selection.clear()
        for name,nodes in self.shells.items():
            item = self.selection.add()
            item.name = name
            item.text = name
            item.select = False


    def addShell(self, mat, shell, tree):
        data = (mat,shell)
        if tree.name in self.shells.keys():
            struct = self.shells[tree.name]
            if mat.name in struct.keys():
                struct[mat.name].append(data)
            else:
                struct[mat.name] = [data]
        else:
            self.shells[tree.name] = {mat.name : [data]}


    def deleteNodes(self, mat, shell):
        print("Delete shell '%s' from material '%s'" % (shell.name, mat.name))
        linkFrom = {}
        linkTo = {}
        tree = mat.node_tree
        for link in tree.links:
            if link.to_node == shell:
                linkFrom[link.to_socket.name] = link.from_socket
            if link.from_node == shell:
                linkTo[link.from_socket.name] = link.to_socket
        for key in linkFrom.keys():
            if key in linkTo.keys():
                tree.links.new(linkFrom[key], linkTo[key])
        tree.nodes.remove(shell)


class DAZ_OT_RemoveShells(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.remove_shells"
    bl_label = "Remove Shells"
    bl_description = "Remove selected shells from selected objects"
    bl_options = {'UNDO'}

    columnWidth = 350

    def run(self, context):
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat,node in data:
                    self.deleteNodes(mat, node)


    def invoke(self, context, event):
        self.getShells(context)
        self.addItems()
        return self.invokeDialog(context)


class DAZ_OT_ReplaceShells(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.replace_shells"
    bl_label = "Replace Shells"
    bl_description = "Display shell node groups so they can be displaced"
    bl_options = {'UNDO'}

    dialogWidth = 800

    def draw(self, context):
        rows = []
        n = 0
        for tname,struct in self.shells.items():
            for mname,data in struct.items():
                for mat,node in data:
                    rows.append((node.name, n, node))
                    n += 1
        rows.sort()
        for nname,n,node in rows:
            row = self.layout.row()
            row.label(text=nname)
            row.prop(node, "node_tree")


    def run(self, context):
        pass


    def invoke(self, context, event):
        self.getShells(context)
        return DazPropsOperator.invoke(self, context, event)

#-------------------------------------------------------------
#   Copy shells
#-------------------------------------------------------------

class ShellCopy:
    useCopyUvs : BoolProperty(
        name = "Copy Missing UVs",
        description = "Copy missing UV maps",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useCopyUvs")

    def copyShells(self, context, mat, nodes, src, trg):
        tree = mat.node_tree
        output = findNode(tree, 'OUTPUT_MATERIAL')
        if output is None:
            return
        for node in nodes:
            nnode = tree.nodes.new(type="ShaderNodeGroup")
            nnode.label = node.label
            nnode.name = node.name
            nnode.node_tree = node.node_tree
            nnode.location = output.location
            output.location[0] += XSIZE
            for slot,oslot in [("BSDF", "Surface"), ("Displacement", "Displacement")]:
                for link in output.inputs[oslot].links:
                    tree.links.new(link.from_socket, nnode.inputs[slot])
                tree.links.new(nnode.outputs[slot], output.inputs[oslot])
            for link in node.inputs["UV"].links:
                uvnode = link.from_node
                if uvnode.type == 'UVMAP':
                    uvname = uvnode.uv_map
                    if uvname not in trg.data.uv_layers.keys():
                        if self.useCopyUvs:
                            sfinger = getFingerPrint(src)
                            tfinger = getFingerPrint(trg)
                            if sfinger == tfinger:
                                copyUvLayers(context, src, trg, [uvname])
                        else:
                            uvname = getActiveUvLayer(trg).name
                elif uvnode.type == 'TEX_COORD':
                    uvname = getActiveUvLayer(trg).name
                else:
                    print("Unknown UV node type: %s" % uvnode.type)
                    return
                uvmap = tree.nodes.new(type="ShaderNodeUVMap")
                uvmap.uv_map = uvname
                uvmap.label = uvname
                uvmap.hide = True
                uvmap.location = nnode.location - Vector((XSIZE, YSIZE))
                tree.links.new(uvmap.outputs["UV"], nnode.inputs["UV"])


class DAZ_OT_CopyShells(DazPropsOperator, ShellRemover, UniqueMaterials, ShellCopy, Selector, IsMesh):
    bl_idname = "daz.copy_shells"
    bl_label = "Copy Shells"
    bl_description = "Copy selected material shells to selected meshes"
    bl_options = {'UNDO'}

    useActive : BoolProperty(
        name = "From Active Material",
        description = "Copy shells from active material instead of named materials",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useActive")
        if self.useActive:
            box = self.layout.box()
            box.label(text="Active Material: %s" % context.object.active_material.name)
        UniqueMaterials.draw(self, context)
        ShellCopy.draw(self, context)
        Selector.draw(self, context)


    def invoke(self, context, event):
        self.getShells(context)
        self.addItems()
        return self.invokeDialog(context)


    def run(self, context):
        src = context.object
        shells = {}
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat,node in data:
                    mname = stripName(mat.name)
                    if mname not in shells.keys():
                        shells[mname] = {}
                    shells[mname][node.node_tree.name] = node
        if self.useActive:
            mname = stripName(src.active_material.name)
            print("Copy from %s" % mname)
        for trg in getSelectedMeshes(context):
            if trg != src:
                for idx,mat in list(enumerate(trg.data.materials)):
                    if mat is None:
                        continue
                    if not self.useActive:
                        mname = stripName(mat.name)
                    nodes = shells.get(mname, {})
                    if nodes:
                        mat = self.ensureUnique(mat, idx, trg)
                        self.copyShells(context, mat, nodes.values(), src, trg)
                driveShellInfluence(trg)

#----------------------------------------------------------
#   Drive Shell influence
#----------------------------------------------------------

class DAZ_OT_DriveShellInfluence(DazOperator, IsMesh):
    bl_idname = "daz.drive_shell_influence"
    bl_label = "Drive Shell Influence"
    bl_description = "Create drivers for shell and layered image influence"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            driveShellInfluence(ob)

#----------------------------------------------------------
#   Fix shells
#----------------------------------------------------------

class DAZ_OT_FixShells(MaterialSelector, DazPropsOperator):
    bl_idname = "daz.fix_shells"
    bl_label = "Fix Shells"
    bl_description = "Replace shell node groups in selected meshes\nwith the node groups of the active material"
    bl_options = {'UNDO'}

    useSelf : BoolProperty(
        name = "Fix Active Mesh",
        description = "Fix selected materials of the active mesh rather than selected meshes",
        default = False)

    def draw(self, context):
        self.drawActive(context)
        self.layout.prop(self, "useSelf")
        if self.useSelf:
            MaterialSelector.draw(self, context)

    def run(self, context):
        hum = context.object
        mat = hum.active_material
        if mat is None:
            raise DazError("No active material")
        mainShells = {}
        self.getShells(mat, mainShells)
        usedShells = {}
        if self.useSelf:
            for mat in hum.data.materials:
                if mat and self.useMaterial(mat):
                    self.fixMaterial(mat, mainShells, usedShells)
        else:
            for mat in hum.data.materials:
                self.getShells(mat, usedShells)
            for ob in getSelectedMeshes(context):
                if ob != hum:
                    for mat in ob.data.materials:
                        self.fixMaterial(mat, mainShells, usedShells)


    def fixMaterial(self, mat, mainShells, usedShells):
        if mat is None:
            return
        shells = {}
        self.getShells(mat, shells)
        for label,nodes in shells.items():
            if label in mainShells.keys():
                tree = mainShells[label][0].node_tree
                for node in nodes:
                    node.node_tree = tree
            elif label in usedShells.keys():
                for node in nodes:
                    for slot in ["BSDF", "Displacement"]:
                        for inlink in list(node.inputs[slot].links):
                            for outlink in list(node.outputs[slot].links):
                                mat.node_tree.links.new(inlink.from_socket, outlink.to_socket)
                    mat.node_tree.nodes.remove(node)


    def getShells(self, mat, shells):
        if mat:
            for node in mat.node_tree.nodes:
                if isShellNode(node):
                    if node.label not in shells.keys():
                        shells[node.label] = []
                    shells[node.label].append(node)

#-------------------------------------------------------------
#   Sort shells
#-------------------------------------------------------------

class DAZ_OT_SortShells(DazPropsOperator, IsMesh):
    bl_idname = "daz.sort_shells"
    bl_label = "Sort Shells"
    bl_description = "Sort selected material shells"
    bl_options = {'UNDO'}

    from ..propgroups import DazIntGroup
    shellOrder : CollectionProperty(type = DazIntGroup)

    useBeautify : BoolProperty(
        name = "Beautify",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useBeautify")
        for item in self.shellOrder:
            self.layout.prop(item, "a", text=item.name)


    def invoke(self, context, event):
        ob = context.object
        self.shells = {}
        self.shellOrder.clear()
        idx = 0
        for mat in ob.data.materials:
            if mat is None:
                continue
            shells = {}
            self.shells[mat.name] = (mat, shells)
            for node in mat.node_tree.nodes:
                if isShellNode(node):
                    key = node.label
                    shells[key] = node
                    if key not in self.shellOrder.keys():
                        idx += 1
                        item = self.shellOrder.add()
                        item.name = key
                        item.a = idx
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        def isFirst(node):
            for slot in ShellOutputs:
                links = node.inputs[slot].links
                if links and not isShellNode(links[0].from_node):
                    return True

        def isLast(node):
            for slot in ShellOutputs:
                links = node.outputs[slot].links
                if links and not isShellNode(links[0].to_node):
                    return True

        ob = context.object
        names = [(item.a, item.name) for item in self.shellOrder]
        names.sort()
        for mat,shells in self.shells.values():
            tree = mat.node_tree
            first = {}
            last = {}
            for node in shells.values():
                if isFirst(node):
                    for slot in ShellOutputs:
                        links = node.inputs[slot].links
                        if links:
                            first[slot] = links[0].from_socket
                        else:
                            first[slot] = None
                if isLast(node):
                    for slot in ShellOutputs:
                        last[slot] = []
                        for link in node.outputs[slot].links:
                            last[slot].append(link.to_socket)
            if not (first and last):
                continue
            prev = first
            for idx,key in names:
                node = shells.get(key)
                if node:
                    for slot in ShellOutputs:
                        if prev[slot]:
                            tree.links.new(prev[slot], node.inputs[slot])
                        else:
                            links = node.inputs[slot].links
                            if links:
                                tree.links.remove(links[0])
                        prev[slot] = node.outputs[slot]
            for slot in ShellOutputs:
                for socket in last[slot]:
                    tree.links.new(prev[slot], socket)

            if self.useBeautify:
                beautifyNodeTree(tree)

#-------------------------------------------------------------
#   Custom shells
#-------------------------------------------------------------

class ShellCyclesGroup(ShellGroup, CyclesTree):
    GroupSize = 3
    owner = None

    def create(self, node, name):
        CyclesTree.__init__(self, self.owner)
        ShellGroup.create(self, node, name, self)

    def addNodes(self, group):
        node = self.addNode("ShaderNodeGroup", 1)
        node.node_tree = group
        self.links.new(self.inputs.outputs["BSDF"], node.inputs[0])
        mix = self.addNode("ShaderNodeMixShader", 2)
        mix.label = "Mix"
        self.links.new(self.inputs.outputs["Influence"], mix.inputs[0])
        self.links.new(self.inputs.outputs["BSDF"], mix.inputs[1])
        self.links.new(node.outputs[0], mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs["BSDF"])
        self.links.new(self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])


def getNodeGroups(scn, context):
    return [(name,name,name) for name in bpy.data.node_groups.keys() if not name.startswith("DAZ ")]


class DAZ_OT_AddCustomShell(MaterialSelector, DazPropsOperator):
    bl_idname = "daz.add_custom_shell"
    bl_label = "Add Custom Shell"
    bl_description = "Add a nodegroup as a shell to selected materials"
    bl_options = {'UNDO'}

    nodeGroup : EnumProperty(
        items = getNodeGroups,
        name = "Node Group",
        description = "Node group to be converted to a shell.\nMust have Shader input and output sockets")

    def draw(self, context):
        self.layout.prop(self, "nodeGroup")
        MaterialSelector.draw(self, context)

    def run(self, context):
        ob = rig = context.object
        if ob.parent:
            rig = ob.parent
        self.group = None
        uvname = getActiveUvLayer(ob).name
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.addShell(mat, uvname, ob, rig)


    def addShell(self, mat, uvname, ob, rig):
        def makeShellGroup(group):
            if isShellNode(group):
                return group
            shell = ShellCyclesGroup(0.0)
            shell.create(node, shellname)
            shell.addNodes(group)
            return shell.group

        tree = mat.node_tree
        output = findNode(tree, 'OUTPUT_MATERIAL')
        if output is None:
            return
        shellname = "%s Shell" % self.nodeGroup
        node = tree.nodes.new(type="ShaderNodeGroup")
        if self.group is None:
            group = bpy.data.node_groups.get(self.nodeGroup)
            self.group = makeShellGroup(group)

        node.label = node.name = shellname
        node.node_tree = self.group
        x,y = output.location
        node.location = (x,y)
        output.location = (x+XSIZE, y)

        node.inputs["Influence"].default_value = 1.0
        if GS.useShellDrivers:
            prop = "INFLU %s" % shellname
            setFloatProp(rig, prop, 1.0, 0.0, 10.0, True, False)
            addDriver(node.inputs["Influence"], "default_value", rig, propRef(prop), "x")
            ob.DazVisibilityDrivers = rig.DazVisibilityDrivers = True

        uvmap = tree.nodes.new(type="ShaderNodeUVMap")
        uvmap.location = (x, y-YSIZE)
        uvmap.uv_map = uvname
        uvmap.label = uvname
        uvmap.hide = True
        tree.links.new(uvmap.outputs["UV"], node.inputs["UV"])

        for slot,oslot in [("BSDF", "Surface"), ("Displacement", "Displacement")]:
            for link in output.inputs[oslot].links:
                tree.links.new(link.from_socket, node.inputs[slot])
            tree.links.new(node.outputs[slot], output.inputs[oslot])

#----------------------------------------------------------
#   Assign Shell Maps
#----------------------------------------------------------

class DAZ_OT_AssignShellMap(MaterialSelector, DazPropsOperator):
    bl_idname = "daz.assign_shell_map"
    bl_label = "Assign Shell Map"
    bl_description = "Assign shell maps to selected materials"
    bl_options = {'UNDO'}

    def draw(self, context):
        ob = context.object
        uvname = getActiveUvLayer(ob).name
        box = self.layout.box()
        box.label(text = "UV Layer: %s" % uvname)
        MaterialSelector.draw(self, context)

    def run(self, context):
        ob = context.object
        uvname = getActiveUvLayer(ob).name
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                mat["DazShellMap"] = uvname

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_RemoveShells,
    DAZ_OT_ReplaceShells,
    DAZ_OT_CopyShells,
    DAZ_OT_FixShells,
    DAZ_OT_SortShells,
    DAZ_OT_DriveShellInfluence,
    DAZ_OT_AddCustomShell,
    DAZ_OT_AssignShellMap,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
