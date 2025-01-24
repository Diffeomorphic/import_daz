# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..transfer import MatchOperator
from ..pin import Pinner

#----------------------------------------------------------
#   Threshold
#----------------------------------------------------------

class ThresholdFloat:
    threshold : FloatProperty(
        name = "Threshold",
        description = "Minimum vertex weight to keep",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 1e-3)

#----------------------------------------------------------
#   Limit vertex groups
#----------------------------------------------------------

class DAZ_OT_LimitVertexGroups(DazPropsOperator, IsMesh):
    bl_idname = "daz.limit_vertex_groups"
    bl_label = "Limit Vertex Groups"
    bl_description = "Limit the number of vertex groups per vertex"
    bl_options = {'UNDO'}

    limit : IntProperty(
        name = "Limit",
        description = "Max number of vertex group per vertex",
        default = 4,
        min = 1, max = 10
    )

    def draw(self, context):
        self.layout.prop(self, "limit")

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.limitVertexGroups(ob)

    def limitVertexGroups(self, ob):
        deletes = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        weights = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        for v in ob.data.vertices:
            data = [(g.weight, g.group) for g in v.groups]
            if len(data) > self.limit:
                data.sort()
                vnmin = len(data) - self.limit
                for w,gn in data[0:vnmin]:
                    deletes[gn].append(v.index)
                wsum = sum([w for w,gn in data[vnmin:]])
                for w,gn in data[vnmin:]:
                    weights[gn].append((v.index, w/wsum))
        for vgrp in ob.vertex_groups:
            vnums = deletes[vgrp.index]
            if vnums:
                vgrp.remove(vnums)
            for vn,w in weights[vgrp.index]:
                vgrp.add([vn], w, 'REPLACE')

#----------------------------------------------------------
#   Prune vertex groups
#----------------------------------------------------------

class DAZ_OT_PruneVertexGroups(DazPropsOperator, ThresholdFloat, IsMesh):
    bl_idname = "daz.prune_vertex_groups"
    bl_label = "Prune Vertex Groups"
    bl_description = "Remove vertices and groups with weights below threshold"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "threshold")

    def run(self, context):
        from ..transfer import pruneVertexGroups
        for ob in getSelectedMeshes(context):
            pruneVertexGroups(ob, self.threshold, [], True)

#-------------------------------------------------------------
#   Create graft and mask vertex groups
#-------------------------------------------------------------

class DAZ_OT_CreateGraftGroups(DazOperator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and dazRna(ob.data).DazGraftGroup)

    def run(self, context):
        graft = context.object
        objects = []
        for ob in getSelectedMeshes(context):
            if ob != graft:
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        hum = objects[0]
        gname = "%s:Graft" % graft.data.name
        mname = "%s:Mask" % graft.data.name
        avnums = [pair.a for pair in dazRna(graft.data).DazGraftGroup]
        self.createVertexGroup(graft, gname, avnums)
        bvnums = [pair.b for pair in dazRna(graft.data).DazGraftGroup]
        self.createVertexGroup(hum, gname, bvnums)
        mask = {}
        for face in dazRna(graft.data).DazMaskGroup:
            for vn in hum.data.polygons[face.a].vertices:
                if vn not in bvnums:
                    mask[vn] = True
        self.createVertexGroup(hum, mname, mask.keys())


    def createVertexGroup(self, ob, gname, vnums):
        vgrp = ob.vertex_groups.new(name=gname)
        for vn in vnums:
            vgrp.add([vn], 1, 'REPLACE')
        return vgrp


class DAZ_OT_TransferVertexGroups(MatchOperator, IsMesh, ThresholdFloat):
    bl_idname = "daz.transfer_vertex_groups"
    bl_label = "Transfer Vertex Groups"
    bl_description = "Transfer vertex groups from active to selected"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "threshold")

    def run(self, context):
        from ..transfer import transferVertexGroups
        src = context.object
        if not src.vertex_groups:
            raise DazError("Source mesh %s         \nhas no vertex groups" % src.name)
        t1 = perf_counter()
        targets = list(self.getTargets(src, context))
        transferVertexGroups(context, src, targets, self.threshold)
        t2 = perf_counter()
        print("Vertex groups transferred in %.1f seconds" % (t2-t1))

#----------------------------------------------------------
#   UV layer transfer
#----------------------------------------------------------

class DAZ_OT_TransferUvLayers(DazOperator, IsMesh):
    bl_idname = "daz.transfer_uv_layers"
    bl_label = "Transfer UV Layers"
    bl_description = "Transfer UV layers from active to selected"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..transfer import transferUvLayers
        src = context.object
        if not src.data.uv_layers:
            raise DazError("No UV layers found")
        targets = [ob for ob in getSelectedMeshes(context) if ob != src]
        t1 = perf_counter()
        transferUvLayers(context, src, targets)
        t2 = perf_counter()
        print("UV layers transferred in %.1f seconds" % (t2-t1))

#----------------------------------------------------------
#   Copy vertex groups by number
#----------------------------------------------------------

class DAZ_OT_CopyVertexGroupsByNumber(DazOperator, IsMesh):
    bl_idname = "daz.copy_vertex_groups_by_number"
    bl_label = "Copy Vertex Groups By Number"
    bl_description = "Copy vertex groups from active to selected meshes with the same number of vertices"
    bl_options = {'UNDO'}

    def run(self, context):
        from ..finger import getFingerPrint
        from ..modifier import copyVertexGroups
        src = context.object
        if not src.vertex_groups:
            raise DazError("Source mesh %s         \nhas no vertex groups" % src.name)
        for trg in getSelectedMeshes(context):
            if trg != src:
                ok,msg = copyVertexGroups(src, trg)
                if not ok:
                    msg = "Cannot copy vertex groups %s" % msg
                    raise DazError(msg)

# ---------------------------------------------------------------------
#   Modify vertex group
# ---------------------------------------------------------------------

class DAZ_OT_ModifyVertexGroup(Pinner, DazPropsOperator, IsMesh):
    bl_idname = "daz.modify_vertex_group"
    bl_label = "Modify Vertex Group"
    bl_description = "Modify the active vertex group"
    bl_options = {'UNDO'}

    direction : EnumProperty(
        items = [("+X", "+X", "+X"),
                 ("-X", "-X", "-X"),
                 ("+Y", "+Y", "+Y"),
                 ("-Y", "-Y", "-Y"),
                 ("+Z", "+Z", "+Z"),
                 ("-Z", "-Z", "-Z")],
        name = "Direction")


    def draw(self, context):
        Pinner.draw(self, context)
        ob = context.object
        vgrp = ob.vertex_groups.active
        box = self.layout.box()
        box.label(text="Vertex group: %s" % vgrp.name)
        self.layout.prop(self, "direction")


    def run(self, context):
        vectors = {
            "+X" : (1,0,0),
            "-X" : (-1,0,0),
            "+Y" : (0,1,0),
            "-Y" : (0,-1,0),
            "+Z" : (0,0,1),
            "-Z" : (0,0,-1)
        }
        ob = context.object
        vgrp = ob.vertex_groups.active
        self.initMapping()
        ez = Vector(vectors[self.direction])
        zs = [ez.dot(v.co) for v in ob.data.vertices]
        z0 = min(zs)
        z1 = max(zs)
        for v in ob.data.vertices:
            w = (ez.dot(v.co) - z0)/(z1 - z0)
            self.addWeight(vgrp, v.index, w)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_LimitVertexGroups,
    DAZ_OT_PruneVertexGroups,
    DAZ_OT_CreateGraftGroups,
    DAZ_OT_TransferVertexGroups,
    DAZ_OT_TransferUvLayers,
    DAZ_OT_CopyVertexGroupsByNumber,
    DAZ_OT_ModifyVertexGroup,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
