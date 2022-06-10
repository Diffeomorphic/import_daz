# Copyright (c) 2016-2022, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
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
from .error import *
from .utils import *
from .tree import Tree, NodeGroup, XSIZE, YSIZE, addNodeGroup
from .morphing import Selector

VECTOR = 1
VALUE = 2
RGBA = 3
BOOLEAN = 4
INT = 5

# ---------------------------------------------------------------------
#   Geometry nodes, tree
# ---------------------------------------------------------------------

class GeoTree(Tree, NodeGroup):
    def __init__(self):
        Tree.__init__(self, None)
        NodeGroup.__init__(self)
        self.type = 'GEONODES'
        self.nodeTreeType = "GeometryNodeTree"
        self.nodeGroupType = "GeometryNodeGroup"

# ---------------------------------------------------------------------
#   Projection source group
# ---------------------------------------------------------------------

class ProjectionSource(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 4)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketObject", "Target")
        self.group.outputs.new("NodeSocketGeometry", "Geometry")
        self.group.outputs.new("NodeSocketFloat", "Vector")


    def addNodes(self):
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        objinfo.transform_space = 'RELATIVE'
        self.links.new(self.inputs.outputs["Target"], objinfo.inputs[0])
        position = self.addNode("GeometryNodeInputPosition", 1)
        index = self.addNode("GeometryNodeInputIndex", 1)

        transfer = self.addNode("GeometryNodeAttributeTransfer", 2)
        transfer.data_type = 'FLOAT_VECTOR'
        transfer.mapping = 'INDEX'
        transfer.domain = 'POINT'
        self.links.new(objinfo.outputs["Geometry"], transfer.inputs["Source"])
        self.links.new(position.outputs["Position"], transfer.inputs["Attribute"])
        self.links.new(index.outputs["Index"], transfer.inputs["Index"])

        sub = self.addNode("ShaderNodeVectorMath", 3)
        sub.operation = 'SUBTRACT'
        self.links.new(transfer.outputs["Attribute"], sub.inputs[0])
        self.links.new(position.outputs["Position"], sub.inputs[1])

        self.links.new(self.inputs.outputs["Geometry"], self.outputs.inputs["Geometry"])
        self.links.new(sub.outputs["Vector"], self.outputs.inputs["Vector"])


class ProjectionTarget(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 5)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketFloat", "Blending")
        self.group.inputs.new("NodeSocketObject", "Object")
        self.group.inputs.new("NodeSocketVector", "Attribute")
        self.group.outputs.new("NodeSocketGeometry", "Geometry")


    def addNodes(self):
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        objinfo.transform_space = 'RELATIVE'
        self.links.new(self.inputs.outputs["Object"], objinfo.inputs["Object"])

        transfer = self.addNode("GeometryNodeAttributeTransfer", 2)
        transfer.data_type = 'FLOAT_VECTOR'
        transfer.mapping = 'NEAREST_FACE_INTERPOLATED'
        self.links.new(objinfo.outputs["Geometry"], transfer.inputs["Source"])
        self.links.new(self.inputs.outputs["Attribute"], transfer.inputs["Attribute"])

        mult = self.addNode("ShaderNodeVectorMath", 3)
        mult.operation = 'MULTIPLY'
        self.links.new(transfer.outputs["Attribute"], mult.inputs[0])
        self.links.new(self.inputs.outputs["Blending"], mult.inputs[1])

        setpos = self.addNode("GeometryNodeSetPosition", 4)
        self.links.new(self.inputs.outputs["Geometry"], setpos.inputs["Geometry"])
        self.links.new(mult.outputs[0], setpos.inputs["Offset"])
        self.links.new(setpos.outputs["Geometry"], self.outputs.inputs["Geometry"])


class DAZ_OT_AddProjection(DazOperator, Selector, IsMesh):
    bl_idname = "daz.add_projection"
    bl_label = "Add Projection"
    bl_description = "Add shrinkwrap modifiers covering the active mesh.\nOptionally add solidify modifiers"
    bl_options = {'UNDO'}

    columnWidth = 300
    ncols = 4

    def draw(self, context):
        if self.base:
            self.layout.label(text = "Base mesh: %s" % self.base.name)
        else:
            self.layout.label(text = "No base mesh found!")
        self.layout.label(text = "Morphed mesh: %s" % self.morphed.name)
        Selector.draw(self, context)


    def invoke(self, context, event):
        from .finger import getFingerPrint
        self.morphed = context.object
        self.base = None
        finger = getFingerPrint(self.morphed)
        for ob in getSelectedMeshes(context):
            if self.morphed != ob and getFingerPrint(ob) == finger:
                self.base = ob
                break
        self.selection.clear()
        for ob in getVisibleMeshes(context):
            if ob != self.morphed and ob != self.base:
                item = self.selection.add()
                item.name = ob.name
                item.text = ob.name
                item.select = False
        return self.invokeDialog(context)


    def getMeshSelection(self):
        return [bpy.data.objects[item.name] for item in self.getSelectedItems()]


    def run(self, context):
        if self.base is None:
            raise DazError("No base mesh found")
        self.makeSourceModifier(self.base, self.morphed)
        for clo in self.getMeshSelection():
            activateObject(context, clo)
            self.makeTargetModifier(clo, self.base)


    def makeSourceModifier(self, base, morphed):
        mod = base.modifiers.new("Source %s" % morphed.name, 'NODES')
        mod.node_group = addNodeGroup(ProjectionSource, "Projection Source")
        mod["Input_1"] = morphed
        mod["Output_1"] = "Deltas"


    def makeTargetModifier(self, clo, morphed):
        mod = clo.modifiers.new("Target %s" % morphed.name, 'NODES')
        mod.node_group = addNodeGroup(ProjectionTarget, "Projection Target")
        bpy.ops.object.geometry_nodes_input_attribute_toggle(prop_path=propRef("Input_3_use_attribute"), modifier_name=mod.name)
        mod["Input_1"] = 1.0
        mod["Input_2"] = morphed
        mod["Input_3_attribute_name"] = "Deltas"

# ---------------------------------------------------------------------
#   Geograft group
# ---------------------------------------------------------------------

class GeograftGroup(GeoTree):
    def create(self, name):
        NodeGroup.make(self, name, 5)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketFloat", "Geograft Edge")
        self.group.inputs.new("NodeSocketFloat", "Geograft Area")
        self.group.inputs.new("NodeSocketFloat", "Merge Distance")
        self.group.outputs.new("NodeSocketGeometry", "Geometry")
        self.group.outputs.new("NodeSocketInt", "Vertex Table")


    def addNodes(self, anatomies):
        index = self.addNode("GeometryNodeInputIndex", 0)
        captureIndex = self.addNode("GeometryNodeCaptureAttribute", 1)
        captureIndex.data_type = 'INT'
        captureIndex.domain = 'POINT'
        self.links.new(self.inputs.outputs["Geometry"], captureIndex.inputs["Geometry"])
        self.links.new(index.outputs["Index"], captureIndex.inputs[INT])

        captureEdge = self.addNode("GeometryNodeCaptureAttribute", 1)
        captureEdge.data_type = 'FLOAT'
        captureEdge.domain = 'POINT'
        self.links.new(captureIndex.outputs["Geometry"], captureEdge.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Edge"], captureEdge.inputs[VALUE])
        union = captureEdge.outputs[VALUE]

        deleteMask = self.addNode("GeometryNodeDeleteGeometry", 2)
        self.links.new(captureEdge.outputs["Geometry"], deleteMask.inputs["Geometry"])
        self.links.new(self.inputs.outputs["Geograft Area"], deleteMask.inputs["Selection"])

        joinGeo = self.addNode("GeometryNodeJoinGeometry", 3)
        joins = [deleteMask]
        for aob in anatomies:
            objinfo = self.addNode("GeometryNodeObjectInfo", 0)
            objinfo.inputs[0].default_value = aob

            captureAnatomy = self.addNode("GeometryNodeCaptureAttribute", 1)
            captureAnatomy.data_type = 'FLOAT'
            captureAnatomy.domain = 'POINT'
            self.links.new(objinfo.outputs["Geometry"], captureAnatomy.inputs["Geometry"])
            self.links.new(self.inputs.outputs["Geograft Edge"], captureAnatomy.inputs[VALUE])
            joins.append(captureAnatomy)

            node = self.addNode("FunctionNodeBooleanMath", 2)
            node.operation = 'OR'
            self.links.new(union, node.inputs[0])
            self.links.new(captureAnatomy.outputs[VALUE], node.inputs[1])
            union = node.outputs[0]
        joins.reverse()
        for node in joins:
            self.links.new(node.outputs["Geometry"], joinGeo.inputs["Geometry"])

        mergeDist = self.addNode("GeometryNodeMergeByDistance", 4)
        mergeDist.inputs["Distance"].default_value = 1e-4
        self.links.new(self.inputs.outputs["Merge Distance"], mergeDist.inputs["Distance"])
        self.links.new(joinGeo.outputs["Geometry"], mergeDist.inputs["Geometry"])
        self.links.new(union, mergeDist.inputs["Selection"])

        self.links.new(mergeDist.outputs["Geometry"], self.outputs.inputs["Geometry"])
        self.links.new(captureIndex.outputs[INT], self.outputs.inputs["Vertex Table"])

# ---------------------------------------------------------------------
#   Geoshell group
# ---------------------------------------------------------------------

class GeoshellGroup(GeoTree):
    def create(self, name, mnames):
        NodeGroup.make(self, name, 4)
        self.group.inputs.new("NodeSocketGeometry", "Geometry")
        self.group.inputs.new("NodeSocketObject", "Shell Geometry")
        self.group.inputs.new("NodeSocketFloat", "Shell Offset")
        for mname in mnames:
            self.group.inputs.new("NodeSocketMaterial", mname)
        self.group.outputs.new("NodeSocketGeometry", "Geometry")


    def addNodes(self, mnames, mats):
        # Geoshell
        objinfo = self.addNode("GeometryNodeObjectInfo", 1)
        self.links.new(self.inputs.outputs["Shell Geometry"], objinfo.inputs["Object"])
        normal = self.addNode("GeometryNodeInputNormal", 1)

        mult = self.addNode("ShaderNodeVectorMath", 2)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Shell Offset"], mult.inputs[0])
        self.links.new(normal.outputs["Normal"], mult.inputs[1])

        setpos = self.addNode("GeometryNodeSetPosition", 3)
        self.links.new(mult.outputs[0], setpos.inputs["Offset"])
        self.links.new(objinfo.outputs["Geometry"], setpos.inputs["Geometry"])

        # Materials
        for mname,mat in zip(mnames,mats):
            matsel = self.addNode("GeometryNodeMaterialSelection", 2)
            matsel.inputs["Material"].default_value = mat
            setmat = self.addNode("GeometryNodeSetMaterial", 3)
            self.links.new(setpos.outputs["Geometry"], setmat.inputs["Geometry"])
            self.links.new(matsel.outputs["Selection"], setmat.inputs["Selection"])
            self.links.new(self.inputs.outputs[mname], setmat.inputs["Material"])
            setpos = setmat

        #joinGeo = self.addNode("GeometryNodeJoinGeometry", 6)
        #self.links.new(objinfo.outputs["Geometry"], joinGeo.inputs["Geometry"])
        #self.links.new(setpos.outputs["Geometry"], joinGeo.inputs["Geometry"])
        self.links.new(setpos.outputs["Geometry"], self.outputs.inputs["Geometry"])

#----------------------------------------------------------
#   Add shells
#----------------------------------------------------------

def getUvset(scn, context):
    return [(uvset,uvset,uvset) for uvset in theUvSets]


class DAZ_OT_AddShell(DazPropsOperator):
    bl_idname = "daz.add_shell"
    bl_label = "Add Shell"
    bl_description = "Add active shell to selected mesh"
    bl_options = {'UNDO'}

    uvset : EnumProperty(
        items = getUvset,
        name = "UV Set",
        description = "Use this UV set for shell materials")

    offset : FloatProperty(
        name = "Offset Distance (cm)",
        description = "Shell offset (cm)",
        min = 0.0,
        precision = 5,
        default = 0.01)

    asMaterial : BoolProperty(
        name = "As Material",
        description = "Add the shell as a material node group,\nnot as a geometry nodes modifier",
        default = False)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.data.vertices) == 0)

    def draw(self, context):
        self.layout.prop(self, "uvset")
        self.layout.prop(self, "offset")
        self.layout.prop(self, "asMaterial")


    def invoke(self, context, event):
        global theUvSets
        self.object = None
        objects = [ob for ob in getSelectedMeshes(context) if ob.data.vertices]
        if objects:
            self.object = objects[0]
            theUvSets = [uvlayer.name for uvlayer in self.object.data.uv_layers]
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        from .matedit import copyMaterialAttributes, fixMaterialUvs
        shell = context.object
        ob = self.object
        if ob is None:
            raise DazError("No matching mesh selected")
        fixMaterialUvs(shell.data.materials, self.uvset)
        mnames = []
        mats = []
        shmats = []
        for mat in ob.data.materials:
            mname = self.stripName(mat.name)
            for shmat in shell.data.materials:
                shname = self.stripName(shmat.name)
                if mname == shname:
                    mnames.append(mname)
                    mats.append(mat)
                    shmats.append(shmat)
        offset = ob.DazScale * self.offset
        if self.asMaterial:
            for mat,shmat in zip(mats, shmats):
                self.addMaterialShell(mat, shmat)
            ob.DazVisibilityDrivers = True
        else:
            shell.visible_shadow = False
            makeShellModifier(shell, ob, offset, mnames, mats, shmats)
            for src,trg in zip(mats, shmats):
                copyMaterialAttributes(src, trg)


    def stripName(self, mname):
        return mname.rsplit(".", 1)[0].rsplit("-", 1)[0]


    def addMaterialShell(self, mat, shmat):
        def replaceLink(output, node, slot):
            links = output.inputs["Surface"].links
            if links:
                socket = links[0].from_socket
                tree.links.new(socket, node.inputs[slot])
                tree.links.new(node.outputs[slot], output.inputs["Surface"])

        from .cycles import findMaterial, findTexco
        from .tree import findNodes, XSIZE, YSIZE
        dmat = findMaterial(mat)
        shdmat = findMaterial(shmat)
        tree = dmat.tree
        texco = findTexco(tree, 1)
        tree.column = 10
        node = tree.addNode("ShaderNodeGroup")
        node.width = 240
        nname = ("%s_%s" % (shmat.name, mat.name))
        node.name = nname
        node.label = shmat.name
        group = tree.getShellGroup(shdmat, self.offset)
        group.create(node, nname, tree)
        group.addNodes((shdmat, self.uvset))
        node.inputs["Influence"].default_value = 1.0
        tree.links.new(tree.getTexco(self.uvset), node.inputs["UV"])
        outputs = findNodes(tree, 'OUTPUT_MATERIAL')
        for output in outputs:
            x,y = output.location
            node.location = (x, 2*YSIZE)
            output.location = (x+XSIZE, y)
            if output.target == 'EEVEE':
                replaceLink(output, node, "Eevee")
            else:
                replaceLink(output, node, "Cycles")


def makeShellModifier(shell, ob, offset, mnames, mats, shmats):
    mod = shell.modifiers.new(shell.name, 'NODES')
    group = GeoshellGroup()
    group.create(ob.name, mnames)
    group.addNodes(mnames, mats)
    mod.node_group = group.group
    mod["Input_1"] = ob
    mod["Input_2"] = offset
    for n,shmat in enumerate(shmats):
        mod["Input_%d" % (n+3)] = shmat

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddShell,
    DAZ_OT_AddProjection,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
