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
from .morphing import MorphLoader
from .utils import *

#------------------------------------------------------------------
#   Import baked morphs
#------------------------------------------------------------------

class BakedMorphLoader(MorphLoader):
    useAdjusters = False
    useMakePosable = False
    useTransferFace = False
    morphset = "Baked"

    def getFingeredRigMeshes(self, context):
        self.chars = []
        self.modded = []

    def finishLoading(self, namepaths, context, t1):
        pass


def postloadMorphs(context, filepath):
    def getPath(asset):
        if asset.url[0] == "#":
            return filepath
        else:
            url = asset.url.rsplit("#")[0]
            return GS.getAbsPath(url)

    from .node import Node
    namepathss = {}
    objects = {}
    props = {}
    parents = {}
    for asset in LS.bakedMorphs.values():
        parent = asset.getMorphParent()
        if parent:
            key = parent.id
            if key not in objects.keys():
                namepathss[key] = []
                objects[key] = parent.rna
                props[key] = {}
                if isinstance(asset.parent, Node) and asset.parent.formulas:
                    parents[key] = parent
            path = getPath(asset)
            namepathss[key].append((asset.name, path, 'BAKED'))
            props[key][asset.name] = (asset.label, asset.value)
    settings = LS.getSettings()
    try:
        importBakedMorphs(context, namepathss, objects, props, parents)
    finally:
        LS.restoreSettings(settings)


def importBakedMorphs(context, namepathss, objects, props, parents):
    from .driver import setProtected
    from .selector import setActivated
    from .node import Instance

    def setupMorphLoader(ob):
        lm = BakedMorphLoader()
        lm.rig = lm.obj = None
        lm.meshes = []
        if ob.type == 'ARMATURE':
            lm.rig = lm.obj = ob
            lm.meshes = getMeshChildren(ob)
        elif ob.type == 'MESH':
            lm.mesh = ob
            lm.meshes = [ob]
            if ob.parent and ob.parent.type == 'ARMATURE':
                lm.obj = lm.rig = ob.parent
        elif ob:
            lm.obj = ob
            lm.meshes = []
        else:
            print("Bad object (importBakedMorphs): %s" % ob)
            return None
        return lm

    def addProps(props, ob, lm, factor):
        for prop,data in props.items():
            label,value = data
            lm.obj[prop] = value*factor
            setProtected(ob, prop, True)
            setActivated(ob, prop, False)
            if prop not in ob.DazBaked.keys():
                item = ob.DazBaked.add()
                item.name = prop
                item.text = label

    def addFormulas(inst, node, ob, lm):
        exprs,rig2 = node.evalFormulas(ob, None, True)
        for driven,expr in exprs.items():
            if driven == "RIG":
                lm.addObjectDrivers(ob, expr)

    for key,namepaths in namepathss.items():
        ob = objects[key]
        print("Load baked morphs to %s" % ob.name)
        if not isinstance(ob, bpy.types.Object):
            continue
        lm = setupMorphLoader(ob)
        if lm is None:
            continue
        lm.getAllMorphs(namepaths, context)
        addProps(props[key], ob, lm, 1)
        taken = []
        if key in parents.keys():
            inst = parents[key]
            if isinstance(inst, Instance):
                taken.append(inst)
                node = inst.node
                addFormulas(inst, node, ob, lm)
                inst2 = inst.instanceTarget
                if inst.instances:
                    insts = inst.instances
                elif inst2:
                    insts = [inst2] + [inst3 for inst3 in inst2.instances if inst3 != inst]
                else:
                    insts = []
                print("LII", insts)
                for inst2 in insts:
                    if inst2 in taken:
                        continue
                    taken.append(inst2)
                    ob2 = inst2.rna
                    lm2 = setupMorphLoader(ob2)
                    if lm2 is not None:
                        lm2.getAllMorphs(namepaths, ob2)
                        addProps(props[key], ob2, lm2, 0)
                        addFormulas(inst2, node, ob2, lm2)
