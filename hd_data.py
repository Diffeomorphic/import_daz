# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from collections import OrderedDict

from .error import *
from .utils import *

#-------------------------------------------------------------
#   Copy graft groups
#-------------------------------------------------------------

def copyGraftGroups(context, hdob, baseob, grafts):
    # Create HD graft
    nbasemats = len(baseob.data.materials)
    nhdmats = len(hdob.data.materials)
    if nhdmats == nbasemats:
        print("No extra HD materials")
        return False
    print("Base materials: %d" % nbasemats)
    activateObject(context, hdob)
    setMode('EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    setMode('OBJECT')
    for f in hdob.data.polygons:
        if f.material_index >= nbasemats:
            f.select = True
    setMode('EDIT')
    bpy.ops.mesh.duplicate()
    bpy.ops.mesh.separate(type='SELECTED')
    setMode('OBJECT')
    for ob in getSelectedMeshes(context):
        if ob != hdob:
            hdgraft = ob

    # Copy vertex groups from grafts to HD graft
    from .transfer import transferVertexGroups
    if len(grafts) == 1:
        transferVertexGroups(context, grafts[0], [hdgraft], 1e-3)
    else:
        weights = OrderedDict([(vgrp.name, []) for vgrp in hdgraft.vertex_groups])
        for graft in grafts:
            transferVertexGroups(context, graft, [hdgraft], 1e-3)
            vgroups = {}
            for vgrp in graft.vertex_groups:
                hdvgrp = hdgraft.vertex_groups.get(vgrp.name)
                if hdvgrp:
                    vgroups[hdvgrp.index] = hdvgrp.name
                    if hdvgrp.index not in weights.keys():
                        weights[hdvgrp.name] = []
            vnums = getHDMaterialVertNums(graft.data, hdgraft.data)
            hdverts = hdgraft.data.vertices
            for vn in vnums:
                v = hdverts[vn]
                for g in v.groups:
                    vgname = vgroups[g.group]
                    weights[vgname].append((vn, g.weight))

        hdgraft.vertex_groups.clear()
        for vgname,data in weights.items():
            if data:
                vgrp = hdgraft.vertex_groups.new(name=vgname)
                for vn,w in data:
                    vgrp.add([vn], w, 'REPLACE')

    # Copy vertex groups from HD graft to HD object
    print("Copy vertex groups to HD mesh")
    offset = len(hdob.data.loops) - len(hdgraft.data.loops)
    for vgrp in hdob.vertex_groups:
        for loop in hdob.data.loops[offset:]:
            vgrp.remove([loop.vertex_index])
    grps = dict([(vgrp.index,{}) for vgrp in hdgraft.vertex_groups])
    for v in hdgraft.data.vertices:
        for g in v.groups:
            grps[g.group][v.index] = g.weight
    for vgrp1 in hdgraft.vertex_groups:
        weights = grps[vgrp1.index]
        if vgrp1.name in hdob.vertex_groups:
            vgrp2 = hdob.vertex_groups[vgrp1.name]
        else:
            vgrp2 = hdob.vertex_groups.new(name=vgrp1.name)
        for loop1,loop2 in zip(hdgraft.data.loops, hdob.data.loops[offset:]):
            w = weights.get(loop1.vertex_index)
            if w is not None:
                vgrp2.add([loop2.vertex_index], w, 'REPLACE')

    # Delete HD graft
    deleteObjects(context, [hdgraft])
    return True


def getHDMaterialVertNums(me, hdme):
    mnums = [mn for mn,mat in enumerate(hdme.materials)
             if mat and mat.name in me.materials]
    vnumlists = [list(f.vertices) for f in hdme.polygons
                 if f.material_index in mnums]
    vnums = [vn for fverts in vnumlists for vn in fverts]
    return set(vnums)


def addSkeyToUrls(ob, asset, skey):
    if asset.hd_url:
        pgs = dazRna(ob.data).DazDhdmFiles
        if skey.name not in pgs.keys():
            item = pgs.add()
            item.name = skey.name
            item.s = GS.getAbsPath(asset.hd_url)
            item.b = False

    pgs = dazRna(ob.data).DazMorphFiles
    if skey.name not in pgs.keys():
        item = pgs.add()
        item.name = skey.name
        item.s = GS.getAbsPath(asset.fileref)
        item.b = False
