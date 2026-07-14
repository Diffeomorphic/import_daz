# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Merge identical materials
#-------------------------------------------------------------

class DAZ_OT_MergeMaterials(DazPropsOperator, IsMesh):
    bl_idname = "daz.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge identical materials of selected meshes"
    bl_options = {'UNDO'}

    useAcrossObjects : BoolProperty(
        name = "Across Objects",
        description = "Combine materials from different objects",
        default = False)

    useAllObjects : BoolProperty(
        name = "All Objects",
        description = "Combine materials for all objects in scene",
        default = False)

    ignoreBump : BoolProperty(
        name = "Ignore Bump Strength",
        description = "Merge materials even if the bump strengths differ",
        default = True)

    debug : BoolProperty(
        name = "Debug",
        description = "Print debug messages in the terminal",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useAcrossObjects")
        self.layout.prop(self, "useAllObjects")
        self.layout.prop(self, "ignoreBump")
        self.layout.prop(self, "debug")


    def run(self, context):
        self.combine(context)
        self.nMerged = 0
        for ob in self.meshes:
            self.mergeSlots(ob)
        if not ES.easy:
            print("Number of material slots merged: %d" % self.nMerged)


    def getMeshes(self, context):
        if self.useAllObjects:
            return getVisibleMeshes(context)
        else:
            return getSelectedMeshes(context)


    def combine(self, context):
        self.setupShells(context)
        self.nCombined = 0
        if self.useAcrossObjects:
            table,diffuse = self.setupTable(self.meshes)
            for ob in self.meshes:
                self.combineMaterials(ob, table, diffuse)
        else:
            for ob in self.meshes:
                table,diffuse = self.setupTable([ob])
                self.combineMaterials(ob, table, diffuse)
        if not ES.easy:
            print("Number of materials combined: %d" % self.nCombined)


    def setupShells(self, context):
        from .geonodes import getModSocket
        shelled = []
        for shell in getVisibleMeshes(context):
            mod = getModifier(shell, 'NODES')
            if mod:
                ob = getModSocket(mod, 1)
                if isinstance(ob, bpy.types.Object):
                    shelled.append(ob)
        self.meshes = []
        for ob in self.getMeshes(context):
            if ob in shelled:
                print("Object with shell: %s" % ob.name)
            else:
                self.meshes.append(ob)


    def setupTable(self, meshes):
        def norm(color):
            r,g,b,a = color
            return max((abs(r-g), abs(r-b), abs(g-b)))

        mats = []
        for ob in meshes:
            for mat in ob.data.materials:
                if mat:
                    mats.append(mat)
        table = {}
        diffuse = {}
        mats2 = []
        for mat in mats:
            taken = False
            for mat2 in mats2:
                if self.areSameMaterial(mat, mat2):
                    table[mat.name] = mat2
                    if norm(mat.diffuse_color) < norm(mat2.diffuse_color):
                        diffuse[mat2.name] = (mat.name, mat.diffuse_color)
                    taken = True
                    if dazRna(mat).DazMaterialType == 'SKIN':
                        dazRna(mat2).DazMaterialType = 'SKIN'
                    break
            if not taken:
                table[mat.name] = mat
                mats2.append(mat)
        return table,diffuse


    def combineMaterials(self, ob, table, diffuse):
        mats = list(ob.data.materials)
        facenums,phairs = clearMaterials(ob)
        mdatas = []
        for mat in mats:
            if mat is None:
                mat2 = None
                mdatas.append(None)
            else:
                mat2 = table[mat.name]
                mdatas.append( diffuse.get(mat.name, (mat.name, mat.diffuse_color)) )
                ob.data.materials.append(mat2)
        for mat,mdata in zip(mats, mdatas):
            if mat:
                mat.name, mat.diffuse_color = mdata
        for f,mn in zip(ob.data.polygons, facenums):
            f.material_index = mn
        for pset,matslot in phairs:
            pset.material_slot = matslot


    def keepMaterial(self, n, mat, ob):
        for mat2 in self.matlist:
            if self.areSameMaterial(mat, mat2):
                m = self.reindex[n] = self.assoc[mat2.name]
                self.newname[mat.name] = mat2.name
                return False
        return True


    def areSameMaterial(self, mat1, mat2):
        mname1 = mat1.name
        mname2 = mat2.name
        deadMatProps = [
            "texture_slots", "node_tree",
            "name", "name_full", "active_texture",
            "diffuse_color"
        ]
        matProps = self.getRelevantProps(mat1, deadMatProps)
        if not self.haveSameAttrs(mat1, mat2, matProps, mname1, mname2):
            return False
        if not BLENDER5 or (mat1.use_nodes and mat2.use_nodes):
            if self.areSameCycles(mat1.node_tree, mat2.node_tree, mname1, mname2):
                if not ES.easy:
                    print("%s = %s" % (mat1.name, mat2.name))
                self.nCombined += 1
                return True
            else:
                return False
        else:
            return False


    def getRelevantProps(self, rna, deadProps):
        props = []
        for prop in dir(rna):
            if (prop[0] != "_" and
                prop not in deadProps):
                props.append(prop)
        return props


    def haveSameAttrs(self, rna1, rna2, props, mname1, mname2):
        for prop in props:
            attr1 = attr2 = None
            if (prop[0] == "_" or
                prop[0:3] == "Daz" or
                prop in ["select", "session_uid", "users"]):
                pass
            elif hasattr(rna1, prop) and hasattr(rna2, prop):
                attr1 = getattr(rna1, prop)
                if prop == "name":
                    attr1 = self.fixKey(attr1, mname1, mname2)
                attr2 = getattr(rna2, prop)
                if not self.checkEqual(attr1, attr2):
                    if self.debug:
                        print("%s != %s, attribute %s: %s != %s" % (mname1, mname2, prop, attr1, attr2))
                    return False
            elif hasattr(rna1, prop):
                if self.debug:
                    print("%s lacks attribute %s" % (mname2, prop))
                return False
            elif hasattr(rna2, prop):
                if self.debug:
                    print("%s lacks attribute %s" % (mname1, prop))
                return False
        return True


    def checkEqual(self, attr1, attr2):
        if isinstance(attr1, (int, float, str)):
            return (attr1 == attr2)
        elif isinstance(attr1, bpy.types.Image):
            return (isinstance(attr2, bpy.types.Image) and (attr1.name == attr2.name))
        elif (isinstance(attr1, set) and isinstance(attr2, set)):
            return True
        elif hasattr(attr1, "__len__") and hasattr(attr2, "__len__"):
            if (len(attr1) != len(attr2)):
                return False
            for n in range(len(attr1)):
                if not self.checkEqual(attr1[n], attr2[n]):
                    return False
        return True


    def areSameCycles(self, tree1, tree2, mname1, mname2):
        def rehash(struct):
            nstruct = {}
            for key,node in struct.items():
                if node.name[0:2] == "T_":
                    nstruct[node.name] = node
                elif node.type == 'GROUP':
                    nstruct[node.node_tree.name] = node
                else:
                    nstruct[key] = node
            return nstruct

        nodes1 = rehash(tree1.nodes)
        nodes2 = rehash(tree2.nodes)
        if not self.haveSameKeys(nodes1, nodes2, mname1, mname2):
            return False
        if not self.haveSameKeys(tree1.links, tree2.links, mname1, mname2):
            return False
        for key1,node1 in nodes1.items():
            key2 = self.fixKey(key1, mname1, mname2)
            node2 = nodes2[key2]
            if not self.areSameNode(node1, node2, mname1, mname2):
                return False
        for link1 in tree1.links:
            hit = False
            for link2 in tree2.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        for link2 in tree2.links:
            hit = False
            for link1 in tree1.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        return True


    def areSameNode(self, node1, node2, mname1, mname2):
        if node1.type != node2.type:
            return False
        if not self.haveSameKeys(node1, node2, mname1, mname2):
            return False
        deadNodeProps = ["dimensions", "location"]
        nodeProps = self.getRelevantProps(node1, deadNodeProps)
        if node1.type == 'GROUP':
            if node1.node_tree != node2.node_tree:
                return False
        elif not self.haveSameAttrs(node1, node2, nodeProps, mname1, mname2):
            return False
        if not self.haveSameInputs(node1, node2):
            return False
        return True


    def areSameLink(self, link1, link2, mname1, mname2):
        fromname1 = self.getNodeName(link1.from_node)
        toname1 = self.getNodeName(link1.to_node)
        fromname2 = self.getNodeName(link2.from_node)
        toname2 = self.getNodeName(link2.to_node)
        fromname1 = self.fixKey(fromname1, mname1, mname2)
        toname1 = self.fixKey(toname1, mname1, mname2)
        return (
            (fromname1 == fromname2) and
            (toname1 == toname2) and
            (link1.from_socket.name == link2.from_socket.name) and
            (link1.to_socket.name == link2.to_socket.name)
        )


    def getNodeName(self, node):
        if node.type == 'GROUP':
            return node.node_tree.name
        else:
            return node.name


    def haveSameInputs(self, node1, node2):
        if len(node1.inputs) != len(node2.inputs):
            return False
        for n,socket1 in enumerate(node1.inputs):
            socket2 = node2.inputs[n]
            if hasattr(socket1, "default_value"):
                if not hasattr(socket2, "default_value"):
                    return False
                val1 = socket1.default_value
                val2 = socket2.default_value
                if (hasattr(val1, "__len__") and
                    hasattr(val2, "__len__")):
                    for m in range(len(val1)):
                        if val1[m] != val2[m]:
                            return False
                elif (val1 != val2 and
                      not (node1.type == "BUMP" and self.ignoreBump)):
                    return False
            elif hasattr(socket2, "default_value"):
                return False
        return True


    def fixKey(self, key, mname1, mname2):
        n = len(key) - len(mname1)
        if key[n:] == mname1:
            return key[:n] + mname2
        else:
            return key


    def haveSameKeys(self, struct1, struct2, mname1, mname2):
        m = len(mname1)
        for key1 in struct1.keys():
            if key1 in ["interface"]:
                continue
            key2 = self.fixKey(key1, mname1, mname2)
            if key2 not in struct2.keys():
                if self.debug:
                    print("%s != %s, key %s" % (mname1, mname2, key2))
                return False
        return True


    def mergeSlots(self, ob):
        assoc = {}
        reindex = {}
        mats = []
        mnum = 0
        reduced = False
        for mn,mat in enumerate(ob.data.materials):
            if mat is None:
                reduced = True
            elif mat.name in assoc.keys():
                reindex[mn] = assoc[mat.name]
                if not ES.easy:
                    print("%s: %d = %d" % (mat.name, mn, assoc[mat.name]))
                self.nMerged += 1
                reduced = True
            else:
                reindex[mn] = mnum
                assoc[mat.name] = mnum
                mats.append(mat)
                mnum += 1

        if reduced:
            facenums,phairs = clearMaterials(ob)
            for mnum,mat in enumerate(mats):
                ob.data.materials.append(mat)
            for f,mn in zip(ob.data.polygons, facenums):
                f.material_index = reindex[mn]
            for pset,matslot in phairs:
                mnum2 = assoc[matslot]
                pset.material_slot = mats[mnum2].name


def clearMaterials(ob):
    facenums = [f.material_index for f in ob.data.polygons]
    phairs = []
    for psys in ob.particle_systems:
        pset = psys.settings
        phairs.append((pset, pset.material_slot))
    ob.data.materials.clear()
    return facenums,phairs

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeMaterials,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
