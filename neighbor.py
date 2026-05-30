# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from .error import *
from .utils import *

#-------------------------------------------------------------
#  Get neighbor daz file
#-------------------------------------------------------------

def getNeighborDazFile(step, lastpath):
    if not lastpath:
        raise DazError("No pose has been imported yet")
    lastpath = bpy.path.resolve_ncase(lastpath)
    folder = os.path.dirname(lastpath)
    if not os.path.isdir(folder):
        raise DazError("DAZ folder not found:\n%s" % folder)

    dazfiles = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        ext = os.path.splitext(fname)[1].lower()
        if os.path.isfile(path) and ext in [".duf", ".dsf"]:
            dazfiles.append(path)

    if not dazfiles:
        raise DazError("No .duf/.dsf files found in:\n%s" % folder)

    dazfiles.sort(key=lambda path: os.path.basename(path).lower())
    lowerpaths = [path.lower() for path in dazfiles]
    try:
        idx = lowerpaths.index(lastpath.lower())
    except ValueError:
        idx = 0
    return dazfiles[(idx + step) % len(dazfiles)]

#-------------------------------------------------------------
#  Neighbor tools
#-------------------------------------------------------------

class DAZ_OT_ImportNeighborPose(DazOperator, IsObject):
    bl_idname = "daz.import_neighbor_pose"
    bl_label = "Import Neighbor Pose"
    bl_description = "Import the previous or next pose file from the last imported pose folder"
    bl_options = {'UNDO'}

    step : IntProperty(default=1)

    def run(self, context):
        lastpath = dazRna(context.scene).DazLastImportedPose
        filepath = getNeighborDazFile(self.step, lastpath)
        oldSelection = list(LS.selection)
        try:
            LS.selection = [filepath]
            bpy.ops.daz.import_pose('EXEC_DEFAULT', affectMorphs=False)
        finally:
            LS.selection = oldSelection


class DAZ_OT_ImportNeighborExpression(DazOperator, IsObject):
    bl_idname = "daz.import_neighbor_expression"
    bl_label = "Import Neighbor Expression"
    bl_description = "Import the previous or next expression file from the last imported expression folder"
    bl_options = {'UNDO'}

    step : IntProperty(default=1)

    def run(self, context):
        lastpath = dazRna(context.scene).DazLastImportedExpression
        filepath = getNeighborDazFile(self.step, lastpath)
        oldSelection = list(LS.selection)
        try:
            LS.selection = [filepath]
            bpy.ops.daz.import_expression('EXEC_DEFAULT',
                                          affectBones=False,
                                          affectObject=False,
                                          useClearMorphs=True)
        finally:
            LS.selection = oldSelection

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportNeighborPose,
    DAZ_OT_ImportNeighborExpression,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
