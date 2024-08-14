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


import os
import bpy
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Fingerprints
#-------------------------------------------------------------

FingerPrints = {
    "19296-38115-18872" : "Genesis",
    "21556-42599-21098" : ("Genesis2-female", "Genesis2-male"),
    "17418-34326-17000" : "Genesis3-female",
    "17246-33982-16828" : "Genesis3-male",
    "16556-32882-16368" : "Genesis8-female",
    "464-804-352" : ("Lashes8-female", "Lashes8-male"),
    "16384-32538-16196" : "Genesis8-male",
    "1128-1440-438" : ("Lashes81-female", "Lashes81-male"),
    "212-376-164" : ("Tear81-female", "Tear81-male"),

    "25182-50338-25156" : "Genesis9",
    "2120-4224-2112" : "Eyes9",
    "2028-2730-858" : "Lashes9",
    "5079-10079-5000" : "Mouth9",
    "280-500-220" : "Tear9",
}

HomeDirs = {
    "Genesis" : "data/DAZ 3D/Genesis/Base/Morphs",
    "Genesis2-female" : "data/DAZ 3D/Genesis 2/Female/Morphs",
    "Genesis2-male" : "data/DAZ 3D/Genesis 2/Male/Morphs",
    "Genesis3-female" : "data/DAZ 3D/Genesis 3/Female/Morphs",
    "Genesis3-male" : "data/DAZ 3D/Genesis 3/Male/Morphs",
    "Genesis8-female" : "data/DAZ 3D/Genesis 8/Female/Morphs",
    "Genesis8-male" : "data/DAZ 3D/Genesis 8/Male/Morphs",
    "Genesis81-female" : "data/DAZ 3D/Genesis 8/Female 8_1/Morphs",
    "Genesis81-male" : "data/DAZ 3D/Genesis 8/Male 8_1/Morphs",
    "Lashes8-female" : "data/DAZ 3D/Genesis 8/Female Eyelashes/Morphs",
    "Lashes8-male" : "data/DAZ 3D/Genesis 8/Male Eyelashes/Morphs",
    "Lashes81-female" : "data/DAZ 3D/Genesis 8/Female 8_1 Eyelashes/Morphs",
    "Lashes81-male" : "data/DAZ 3D/Genesis 8/Male 8_1 Eyelashes/Morphs",
    "Tear81-female" : "data/DAZ 3D/Genesis 8/Female 8_1 Tear/Morphs",
    "Tear81-male" : "data/DAZ 3D/Genesis 8/Male 8_1 Tear/Morphs",
    "Genesis9" : "data/DAZ 3D/Genesis 9/Base/Morphs",
    "Eyes9" : "data/DAZ 3D/Genesis 9/Genesis 9 Eyes/Morphs",
    "Lashes9" : "data/DAZ 3D/Genesis 9/Genesis 9 Eyelashes/Morphs",
    "Tear9" : "data/DAZ 3D/Genesis 9/Genesis 9 Tear/Morphs",
    "Mouth9" : "data/DAZ 3D/Genesis 9/Genesis 9 Mouth/Morphs",
}

VertexCounts = {
    19296 : "Genesis (male or female)",
    21556 : "Genesis 2 (male or female)",
    17418 : "Genesis 3 female",
    17246 : "Genesis 3 male",
    16556 : "Genesis 8 female",
    16384 : "Genesis 8 male",
    464 : "Genesis 8 eyelashes",
    1128 : "Genesis 8.1 eyelashes",
    212 : "Genesis 8.1 tear",
    25182 : "Genesis 9 (male or female)",
    2120 : "Genesis 9 eyes",
    2028 : "Geneis 9 eyelashes",
    5079 : "Genesis 9 mouth",
    280 : "Genesis 9 tear",
}

FingerPrintsHD = {
    "19296-38115-18872" : ("Genesis", 0),
    "76283-151718-75488" : ("Genesis", 1),
    "303489-605388-301952" : ("Genesis", 2),

    "21556-42599-21098" : ("Genesis2-female", 0),
    "85253-169556-84358" : ("Genesis2-female", 1),
    "339167-676544-337432" : ("Genesis2-female", 2),

    "17418-34326-17000" : ("Genesis3-female", 0),
    "68744-136652-68000" : ("Genesis3-female", 1),
    "273396-545304-272000" : ("Genesis3-female", 2),

    "17246-33982-16828" : ("Genesis3-male", 0),
    "68056-135276-67312" : ("Genesis3-male", 1),
    "270644-539800-269248" : ("Genesis3-male", 2),

    "16556-32882-16368" : ("Genesis8-female", 0),
    "65806-131236-65472" : ("Genesis8-female", 1),
    "262514-524360-261888" : ("Genesis8-female", 2),
    "1048762-2096272-1047552" : ("Genesis8-female", 3),

    "16384-32538-16196" : ("Genesis8-male", 0),
    "65118-129860-64784" : ("Genesis8-male", 1),
    "259762-518856-259136" : ("Genesis8-male", 2),
    "1037754-2074256-1036544" : ("Genesis8-male", 3),

    "25182-50338-25156" : ("Genesis9", 0),

    "536-1056-528" : ("Genesis9-eyes", -1),
    "2120-4224-2112" : ("Genesis9-eyes", 0),
    "8456-16896-8448" : ("Genesis9-eyes", 1),
    "33800-67584-33792" : ("Genesis9-eyes", 2),
    "135176-270336-135168" : ("Genesis9-eyes", 3),
}


def getFingerPrint(ob):
    if ob.type == 'MESH':
        return ("%d-%d-%d" % (len(ob.data.vertices), len(ob.data.edges), len(ob.data.polygons)))


def getFingeredCharacters(ob, useOrig, useGenesis=False, verbose=True):
    def getSingleChar(rig, char):
        if isinstance(char, tuple):
            if rig:
                url = rig.DazUrl.rsplit("#",1)[-1]
                if url.startswith("Genesis"):
                    if "Female" in url:
                        return char[0]
                    elif "Male" in url:
                        return char[1]
            return char[0]
        return char

    meshes = []
    chars = []
    modded = False
    char = None
    if ob is None:
        return None,meshes,chars,False
    elif ob.type == 'MESH':
        finger = getFingerPrint(ob)
        if finger in FingerPrints.keys():
            char = FingerPrints[finger]
        elif useOrig and ob.data.DazFingerPrint in FingerPrints.keys():
            char = FingerPrints[ob.data.DazFingerPrint]
            modded = True
        else:
            if verbose:
                print("Did not find fingerprint", finger)
        char = getSingleChar(ob.parent, char)
        if not useGenesis or (char and char.startswith("Genesis")):
            chars = [char]
            meshes = [ob]
        if ob.parent and ob.parent.type == 'ARMATURE':
            rig = ob.parent
        else:
            rig = None
        return rig,meshes,chars,modded

    elif ob.type == 'ARMATURE':
        def addChar(finger, mesh):
            char = FingerPrints.get(finger)
            if char:
                char = getSingleChar(ob, char)
                if char.startswith("Genesis"):
                    meshes0.append(child)
                    chars0.append(char)
                elif not useGenesis:
                    meshes.append(child)
                    chars.append(char)
            return char

        meshes0 = []
        chars0 = []
        modded = False
        for child in ob.children:
            if child.type == 'MESH':
                finger = getFingerPrint(child)
                if addChar(finger, child):
                    pass
                elif useOrig:
                    addChar(child.data.DazFingerPrint, child)
        meshes = meshes0 + meshes
        chars = chars0 + chars
        return ob,meshes,chars,modded

    elif ob.parent and ob.parent.type == 'ARMATURE':
        return getFingeredCharacters(ob.parent, useOrig)
    return None,[],[],False


def isGenesis(ob):
    chars = getFingeredCharacters(ob, False, verbose=False)[2]
    if chars:
        char = chars[0]
        return (char and char.startswith("Genesis"))
    return False


def getCharacter(ob):
    chars = getFingeredCharacters(ob, False, verbose=False)[2]
    if chars:
        return chars[0]
    return None



def replaceHomeDir(path0, char0, char):
    if char0 and char:
        homedir0 = HomeDirs[char0].lower()
        homedir = HomeDirs[char].lower()
        path0 = normalizePath(path0).lower()
        if homedir0 in path0:
            path = path0.replace(homedir0, homedir)
            if os.path.exists(path):
                return path
    return None


class DAZ_OT_GetFingerPrint(bpy.types.Operator, IsMeshArmature):
    bl_idname = "daz.get_finger_print"
    bl_label = "Get Fingerprint"
    bl_description = "Get fingerprint of active character"

    def draw(self, context):
        for line in self.lines:
            self.layout.label(text=line)

    def execute(self, context):
        return{'FINISHED'}

    def invoke(self, context, event):
        ob = context.object
        self.lines = ["Fingerprint for %s" % ob.name]
        rig,meshes,chars,modded = getFingeredCharacters(ob,False)
        if meshes:
            finger = getFingerPrint(meshes[0])
            mesh = meshes[0].name
            char = chars[0]
        else:
            finger = None
            mesh = None
            char = None
        if rig:
            rig = rig.name
        self.lines += [
            ("  Rig: %s" % rig),
            ("  Mesh: %s" % mesh),
            ("  Character: %s" % char),
            ("  Fingerprint: %s" % finger)]
        for line in self.lines:
            print(line)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


def getRigMeshes(context):
    ob = context.object
    if (ob.type == 'MESH' and
        ob.parent is None):
        return None, [ob]

    rig = None
    for ob in getSelectedObjects(context):
        if ob.type == 'ARMATURE':
            rig = ob
            break
        elif ob.type == 'MESH' and ob.parent and ob.parent.type == 'ARMATURE':
            rig = ob.parent
            break
    if rig:
        return rig, getMeshChildren(rig)
    else:
        return rig, []

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_GetFingerPrint,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
