# Copyright (c) 2016-2022, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
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
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, JsonExportFile, AF
from .animation import HideOperator

#-------------------------------------------------------------
#   Save current pose
#-------------------------------------------------------------

class DAZ_OT_SavePoseInternal(DazOperator, JsonExportFile, IsArmature):
    bl_idname = "daz.save_pose_internal"
    bl_label = "Save Pose Internal"
    bl_description = "Save the current pose as a json file"
    bl_options = {'UNDO'}

    useSkeleton : BoolProperty(
        name = "Skeleton",
        description = "Save rotation mode and roll angles",
        default = False)

    usePose : BoolProperty(
        name = "Pose",
        description = "Save the current pose",
        default = True)

    useObjectTransform : BoolProperty(
        name = "Object Transform",
        description = "Save object transform",
        default = True)

    useRotationOnly : BoolProperty(
        name = "Rotation Only",
        description = "Save rotation curves only",
        default = False)

    useSelectedOnly : BoolProperty(
        name = "Selected Only",
        description = "Save pose of selected bones only",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useSkeleton")
        self.layout.prop(self, "usePose")
        if self.usePose:
            self.layout.prop(self, "useRotationOnly")
            self.layout.prop(self, "useObjectTransform")
        self.layout.prop(self, "useSelectedOnly")


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        rig = context.object
        struct = OrderedDict()
        struct["character"] = rig.name
        struct["scale"] = 1.0

        if self.useSkeleton:
            rolls = {}
            setMode('EDIT')
            for eb in rig.data.edit_bones:
                rolls[eb.name] = eb.roll
            setMode('OBJECT')
            skel = {}
            struct["skeleton"] = skel
            for pb in rig.pose.bones:
                skel[pb.name]  = [pb.rotation_mode, rolls[pb.name]]

        if self.useObjectTransform:
            struct["object"] = [list(rig.location),
                                list(rig.rotation_euler),
                                list(rig.scale),
                                rig.rotation_mode]

        if self.usePose:
            pose = {}
            struct["pose"] = pose
            for pb in rig.pose.bones:
                if not self.useSelectedOnly or pb.bone.select:
                    loc,quat,scale = pb.matrix.decompose()
                    euler = quat.to_euler()
                    if (self.useRotationOnly or
                        not (nonzero(pb.location) or nonzero(pb.scale-One))):
                        pose[pb.name] = (list(euler),
                                         list(pb.bone.DazOrient),
                                         pb.DazRotMode)
                    else:
                        pose[pb.name] = (list(euler),
                                         list(pb.location),
                                         list(pb.scale),
                                         list(pb.bone.DazOrient),
                                         pb.DazRotMode)
        from .load_json import saveJson
        saveJson(struct, self.filepath)

#-------------------------------------------------------------
#   Load pose
#-------------------------------------------------------------

def getCharacter(rig):
    if rig.DazMesh:
        char = rig.DazMesh.lower().replace("-","_").replace("genesis", "genesis_")
        if char[-1] == "_":
            char = char[:-1]
        print("Character: %s" % char)
        return char
    else:
        return None


def loadRestPoseEntry(character, table, folder):
    import json
    from .fileutils import safeOpen
    if character in table.keys():
        return
    filepath = os.path.join(folder, character +  ".json")
    print("Load", filepath)
    if not os.path.exists(filepath):
        raise DazError("File %s    \n does not exist" % filepath)
    else:
        with safeOpen(filepath, "r") as fp:
            data = json.load(fp)
    table[character] = data


def getOrientation(character, bname, rig):
    if rig and bname in rig.pose.bones.keys():
        pb = rig.pose.bones[bname]
        return pb.bone.DazOrient, pb.DazRotMode

    loadRestPoseEntry(character, AF.RestPoses, AF.RestPoseFolder)
    poses = AF.RestPoses[character]["pose"]
    if bname in poses.keys():
        orient, xyz = poses[bname][-2:]
        return orient, xyz
    else:
        return None, "XYZ"


def getParentCharacter(character):
    loadRestPoseEntry(character, AF.RestPoses, AF.RestPoseFolder)
    if "parent" in AF.RestPoses[character].keys():
        parent = AF.RestPoses[character]["parent"]
        return parent.lower().replace(" ", "_")
    else:
        return character


def getParent(character, bname):
    parent = getParentCharacter(character)
    loadRestPoseEntry(parent, AF.Parents, AF.ParentsFolder)
    parents = AF.Parents[parent]["parents"]
    if bname in parents.keys() and parents[bname]:
        return parents[bname]
    else:
        return None


def loadPose(context, rig, character, table, modify):

    def getBoneName(bname, bones):
        if bname in bones.keys():
            return bname
        elif isDrvBone(bname):
            bname = baseBone(bname)
            if bname in bones.keys():
                return bname
        elif (bname[-4:] == "Copy" and
              bname[:-4] in bones.keys()):
            return bname[:-4]
        return None


    def modifySkeleton(rig, skel):
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            bname = getBoneName(eb.name, skel)
            if bname in skel.keys():
                eb.roll = skel[bname][1]
        setMode('OBJECT')
        for pb in rig.pose.bones:
            bname = getBoneName(pb.name, skel)
            if bname in skel.keys():
                pb.rotation_mode = skel[bname][0]


    def loadBonePose(context, pb, pose):
        pbname = getBoneName(pb.name, pose)
        if pbname and pb.name[:-4] != "Copy":
            if len(pose[pbname]) == 3:
                rot, pb.bone.DazOrient, pb.DazRotMode = pose[pbname]
                loc = scale = None
            else:
                rot, loc, scale, pb.bone.DazOrient, pb.DazRotMode = pose[pbname]
            euler = Euler(rot)
            mat = euler.to_matrix()
            rmat = pb.bone.matrix_local.to_3x3()
            if pb.parent:
                par = pb.parent
                rmat = par.bone.matrix_local.to_3x3().inverted() @ rmat
                mat = par.matrix.to_3x3().inverted() @ mat
            bmat = rmat.inverted() @ mat
            pb.matrix_basis = bmat.to_4x4()
            if loc:
                pb.location = loc
                pb.scale = scale
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_euler[n] = 0
            updateScene(context)

        if pb.name != "head":
            for child in pb.children:
                loadBonePose(context, child, pose)


    def loadObjectPose(context, rig, pose):
        rig.location, rot, rig.scale, xyz = pose
        euler = Euler(rot, xyz)
        rig.rotation_euler = euler


    root = None
    for pb in rig.pose.bones:
        if pb.parent is None:
            root = pb
            break
    ctable = table[character]
    if "skeleton" in ctable.keys():
        modifySkeleton(rig, ctable["skeleton"])
    if "object" in ctable.keys():
        loadObjectPose(context, rig, ctable["object"])
    else:
        loadObjectPose(context, rig, [Zero, Zero, One, "XYZ"])
    if "pose" in ctable.keys():
        loadBonePose(context, root, ctable["pose"])


class DAZ_OT_LoadPoseInternal(HideOperator, JsonFile, SingleFile, IsArmature):
    bl_idname = "daz.load_pose_internal"
    bl_label = "Load Pose Internal"
    bl_description = "Load pose from a json file"
    bl_options = {'UNDO'}

    def run(self, context):
        folder = os.path.dirname(self.filepath)
        character = os.path.splitext(os.path.basename(self.filepath))[0]
        table = {}
        loadRestPoseEntry(character, table, folder)
        print("Load pose")
        loadPose(context, context.object, character, table, False)
        print("Pose %s loaded" % self.filepath)

#-------------------------------------------------------------
#   Optimize pose for IK
#   Function used by rigify
#-------------------------------------------------------------

class DAZ_OT_OptimizePose(DazPropsOperator, IsArmature):
    bl_idname = "daz.optimize_pose"
    bl_label = "Optimize Pose For IK"
    bl_description = "Optimize pose for IK.\nIncompatible with pose loading and body morphs"
    bl_options = {'UNDO'}

    useApplyRestPose : BoolProperty(
        name = "Apply Rest Pose",
        description = "Apply current pose as rest pose for all armatures",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useApplyRestPose")

    def run(self, context):
        optimizePose(context, self.useApplyRestPose)


def optimizePose(context, useApplyRestPose):
    from .merge import applyRestPoses
    rig = context.object
    char = getCharacter(rig)
    if char is None:
        raise DazError("Did not recognize character")
    loadRestPoseEntry(char, AF.IkPoses, AF.IkPoseFolder)
    loadPose(context, rig, char, AF.IkPoses, False)
    if useApplyRestPose:
        applyRestPoses(context, rig, [])

#-------------------------------------------------------------
#   Convert Rig
#-------------------------------------------------------------

SourceRig = {
    "genesis" : "genesis1",
    "genesis_2_female" : "genesis2",
    "genesis_2_male" : "genesis2",
    "genesis_3_female" : "genesis3",
    "genesis_3_male" : "genesis3",
    "genesis_8_female" : "genesis8",
    "genesis_8_male" : "genesis8",
    "victoria_4" : "genesis3",
    "victoria_7" : "genesis3",
    "victoria_8" : "genesis8",
    "michael_4" : "genesis3",
    "michael_7" : "genesis3",
    "michael_8" : "genesis8",
}

class DAZ_OT_ConvertRigPose(DazPropsOperator):
    bl_idname = "daz.convert_rig"
    bl_label = "Convert DAZ Rig"
    bl_description = "Convert current DAZ rig to other DAZ rig"
    bl_options = {'UNDO'}

    newRig : EnumProperty(
        items = AF.RestPoseItems,
        name = "New Rig",
        description = "Convert active rig to this",
        default = "genesis_3_female")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig[0:7] == "genesis")

    def draw(self, context):
        self.layout.prop(self, "newRig")

    def run(self, context):
        rig = context.object
        scn = context.scene
        loadRestPoseEntry(self.newRig, AF.RestPoses, AF.RestPoseFolder)
        scale = 1.0
        if self.newRig in SourceRig.keys():
            modify = False
            src = SourceRig[self.newRig]
            conv,twists = getConverter(src, rig)
            if conv:
                self.renameBones(rig, conv)
        else:
            modify = True
            src = self.newRig
            table = AF.RestPoses[src]
            if "translate" in table.keys():
                self.renameBones(rig, table["translate"])
            if "scale" in table.keys():
                scale = table["scale"] * rig.DazScale
        loadPose(context, rig, self.newRig, AF.RestPoses, modify)
        rig.DazRig = src
        print("Rig converted to %s" % self.newRig)
        if scale != 1.0:
            raise DazError("Use scale = %.5f when loading BVH files.       " % scale, True)


    def renameBones(self, rig, conv):
        setMode('EDIT')
        for eb in rig.data.edit_bones:
            if eb.name in conv.keys():
                data = conv[eb.name]
                if isinstance(data, list):
                    eb.name = data[0]
                    if data[1] == "reverse":
                        head = tuple(eb.head)
                        tail = tuple(eb.tail)
                        eb.head = (1,2,3)
                        eb.tail = head
                        eb.head = tail
                else:
                    eb.name = data
        setMode('OBJECT')

#-------------------------------------------------------------
#   Bone conversion
#-------------------------------------------------------------

AF.TwistBones["genesis3"] = [
    ("lShldrBend", "lShldrTwist"),
    ("rShldrBend", "rShldrTwist"),
    ("lForearmBend", "lForearmTwist"),
    ("rForearmBend", "rForearmTwist"),
    ("lThighBend", "lThighTwist"),
    ("rThighBend", "rThighTwist"),
]
AF.TwistBones["genesis8"] = AF.TwistBones["genesis3"]


def getConverter(stype, trg):
    if stype == "genesis8":
        stype = "genesis3"
    trgtype = trg.DazRig
    if trgtype == "genesis8":
        trgtype = "genesis3"

    if stype == "" or trgtype == "":
        return {},[]
    if (stype in AF.TwistBones.keys() and
        trgtype not in AF.TwistBones.keys()):
        twists = AF.TwistBones[stype]
    else:
        twists = []

    if stype == trgtype:
        return {},twists
    if trgtype == "mhx":
        cname = stype[:-1] + "-mhx"
    elif trgtype[0:6] == "rigify":
        cname = stype[:-1] + "-" + trgtype
    elif trgtype == "genesis9":
        cname = "genesis1238-genesis9"
    else:
        cname = stype + "-" + trgtype

    conv = getConverterEntry(cname)
    if not conv:
        print("No converter", stype, trg.DazRig)
    return conv, twists


def getConverterEntry(cname):
    import json
    from .fileutils import safeOpen
    if cname in AF.Converters.keys():
        return AF.Converters[cname]
    else:
        folder = os.path.join(os.path.dirname(__file__), "data", "converters")
        filepath = os.path.join(folder, cname + ".json")
        if os.path.exists(filepath):
            with safeOpen(filepath, "r") as fp:
                conv = AF.Converters[cname] = json.load(fp)
            return conv
    return {}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SavePoseInternal,
    DAZ_OT_LoadPoseInternal,
    DAZ_OT_OptimizePose,
    DAZ_OT_ConvertRigPose,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
