# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..error import *
from ..utils import *
from ..fix import GizmoUser

#-------------------------------------------------------------
#   Replace left-right prefix with suffix
#-------------------------------------------------------------

class DAZ_OT_ChangePrefixToSuffix(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.change_prefix_to_suffix"
    bl_label = "Change Prefix To Suffix"
    bl_description = "Change l/r prefix to .L/.R suffix,\nto use Blender symmetry tools"
    bl_options = {'UNDO'}

    def run(self, context):
        self.renamedBones = {}
        for rig in getSelectedArmatures(context):
            if dazRna(rig).DazRig.endswith(".suffix"):
                raise DazError("%s already has suffix bones" % rig.name)
            if dazRna(rig).DazRig.startswith(("mhx", "rigify")):
                raise DazError("Cannot change a %s rig to suffix" % dazRna(rig).DazRig)
            self.renameFaceBones(rig)
            dazRna(rig).DazRig = "%s.suffix" % dazRna(rig).DazRig

    def isFaceBone(self, pb, rig):
        return True


class DAZ_OT_ChangeSuffixToPrefix(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.change_suffix_to_prefix"
    bl_label = "Change Suffix To Prefix"
    bl_description = "Change .L/.R suffix to l/r prefix,\nto prepare rig for MHX or Rigify"
    bl_options = {'UNDO'}

    def run(self, context):
        self.renamedBones = {}
        for rig in getSelectedArmatures(context):
            if not dazRna(rig).DazRig.endswith(".suffix"):
                raise DazError("%s does not have suffix bones" % rig.name)
            self.rigtype = dazRna(rig).DazRig = dazRna(rig).DazRig[:-7]
            self.renameFaceBones(rig)

    def isFaceBone(self, pb, rig):
        return True

    def getOtherName(self, bname):
        if len(bname) < 2:
            return bname
        elif bname[-2:] in [".L", "_L"]:
            if self.rigtype == "genesis9":
                return "l_%s" % bname[0:-2]
            else:
                return "l%s%s" % (bname[0].upper(), bname[1:-2])
        elif bname[-2:] in [".R", "_R"]:
            if self.rigtype == "genesis9":
                return "r_%s" % bname[0:-2]
            else:
                return "r%s%s" % (bname[0].upper(), bname[1:-2])
        else:
            return bname

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangePrefixToSuffix,
    DAZ_OT_ChangeSuffixToPrefix,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

