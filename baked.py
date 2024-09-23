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
    from .driver import setProtected
    from .selector import setActivated
    from .node import Node, Instance
    from .modifier import FormulaAsset

    def getPath(asset):
        if asset.url[0] == "#":
            return filepath
        else:
            url = asset.url.rsplit("#")[0]
            return GS.getAbsPath(url)

    def setupMorphLoader(ob):
        lm = BakedMorphLoader()
        lm.rig = lm.obj = None
        lm.meshes = []
        if ob.type == 'ARMATURE':
            lm.rig = lm.obj = ob
            lm.meshes = getMeshChildren(ob)
        elif ob.type == 'MESH':
            lm.obj = lm.mesh = ob
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

    def addProps(props, lm, factor):
        ob = lm.obj
        for prop,data in props.items():
            label,value = data
            ob[prop] = value*factor
            setProtected(ob, prop, True)
            setActivated(ob, prop, False)
            if prop not in ob.DazBaked.keys():
                item = ob.DazBaked.add()
                item.name = prop
                item.text = label

    def addFormFormulas(forms, ob, lm, useMorphed):
        edict = {}
        for form in forms:
            exprss,rig2 = form.evalFormulas(ob, None, True)
            for driven,exprs in exprss.items():
                if driven == "RIG":
                    for channel in ["translation", "rotation", "scale"]:
                        expr = exprs.get(channel)
                        if expr:
                            for idx in expr.keys():
                                key = "%s:%d" % (channel, idx)
                                if key in edict.keys():
                                    props = edict[key][1]
                                    props += expr[idx].props
                                else:
                                    edict[key] = (exprs, expr[idx].props)
        for exprs,props in edict.values():
            lm.addObjectDrivers(ob, exprs, useMorphed)

    def addNodeFormulas(node, ob, lm, useMorphed):
        exprss,rig2 = node.evalFormulas(ob, None, True)
        for driven,exprs in exprss.items():
            if driven == "RIG":
                lm.addObjectDrivers(ob, exprs, useMorphed)

    namepathss = {}
    objects = {}
    props = {}
    forms = {}
    parents = {}
    for asset in LS.bakedMorphs.values():
        parent = asset.getMorphParent()
        if parent:
            key = parent.id
            if key not in objects.keys():
                namepathss[key] = []
                objects[key] = parent.rna
                props[key] = {}
                forms[key] = []
                parents[key] = None
            if isinstance(asset, FormulaAsset):
                forms[key].append(asset)
            elif isinstance(asset.parent, Node) and asset.parent.formulas:
                parents[key] = parent
            path = getPath(asset)
            namepathss[key].append((asset.name, path, 'BAKED'))
            props[key][asset.name] = (asset.label, asset.value)

    useMorphed = (LS.onLoadBaked == 'MORPHED')
    settings = LS.getSettings()
    try:
        for key,namepaths in namepathss.items():
            ob = objects[key]
            print("Load baked morphs to %s" % ob.name)
            if not isinstance(ob, bpy.types.Object):
                continue
            lm = setupMorphLoader(ob)
            if lm is None:
                continue
            if useMorphed:
                lm.getAllMorphs(namepaths, context)
            addProps(props[key], lm, 1.0)
            addFormFormulas(forms[key], ob, lm, useMorphed)

            inst = parents.get(key)
            taken = []
            if isinstance(inst, Instance):
                taken.append(inst)
                node = inst.node
                addNodeFormulas(node, ob, lm, useMorphed)
                inst2 = inst.instanceTarget
                if inst.instances:
                    insts = inst.instances
                elif inst2:
                    insts = [inst2] + [inst3 for inst3 in inst2.instances if inst3 != inst]
                else:
                    insts = []
                for inst2 in insts:
                    if inst2 in taken:
                        continue
                    taken.append(inst2)
                    ob2 = inst2.rna
                    lm2 = setupMorphLoader(ob2)
                    if lm2 is not None:
                        if useMorphed:
                            lm2.getAllMorphs(namepaths, ob2)
                        addProps(props[key], lm2, 0.0)
                    addNodeFormulas(node, ob2, lm2, useMorphed)
    finally:
        LS.restoreSettings(settings)
