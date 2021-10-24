# Copyright (c) 2016-2021, Thomas Larsson
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
#
# ---------------------------------------------------------------------------
#
# The purpose of this file is to make morphing armatures work even if the
# import_daz add-on is not available. A typical situation might be if you send
# the blend file to an external rendering service.
#
# 1. Open this file (runtime/morph_armature.py) in a text editor window.
# 2. Enable the Text > Register checkbox.
# 3. Run the script (Run Script)
# 4. Save the blend file.
# 5. Reload the blend file.
#
# ---------------------------------------------------------------------------

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector

def getEditBones(rig):
    def d2b90(v):
        return scale*Vector((v[0], -v[2], v[1]))

    def isOutlier(vec):
        return (vec[0] == -1 and vec[1] == -1 and vec[2] == -1)

    scale = rig.DazScale
    heads = {}
    tails = {}
    offsets = {}
    for pb in rig.pose.bones:
        if isOutlier(pb.DazHeadLocal):
            pb.DazHeadLocal = pb.bone.head_local
        if isOutlier(pb.DazTailLocal):
            pb.DazTailLocal = pb.bone.tail_local
        heads[pb.name] = Vector(pb.DazHeadLocal)
        tails[pb.name] = Vector(pb.DazTailLocal)
        offsets[pb.name] = d2b90(pb.HdOffset)
    for pb in rig.pose.bones:
        if pb.name[-5:] == "(drv)":
            bname = pb.name[:-5]
            finname = "%s(fin)" % bname
            heads[bname] = heads[finname] = heads[pb.name]
            tails[bname] = tails[finname] = tails[pb.name]
            offsets[bname] = offsets[finname] = offsets[pb.name]
    for pb in rig.pose.bones:
        if pb.bone.DazExtraBone:
            parent = pb.parent
            while parent and parent.bone.DazExtraBone:
                parent = parent.parent
            if parent:
                offsets[pb.name] += offsets[parent.name]
                if pb.name[-5:] == "(drv)":
                    bname = pb.name[:-5]
                    finname = "%s(fin)" % bname
                    offsets[bname] = offsets[finname] = offsets[pb.name]
    return heads, tails, offsets


def morphArmature(rig, heads, tails, offsets):
    for eb in rig.data.edit_bones:
        head = heads[eb.name] + offsets[eb.name]
        if eb.use_connect and eb.parent:
            eb.parent.tail = head
        eb.head = head
        eb.tail = tails[eb.name] + offsets[eb.name]

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

@persistent
def onFrameChange(scn):
    data = []
    for ob in scn.objects:
        if (ob.type == 'ARMATURE' and
            ob.select_get() and
            not ob.hide_get() and
            not ob.hide_viewport):
            mode = ob.mode
            heads, tails, offsets = getEditBones(ob)
            data.append((ob, heads, tails, offsets))
    if data:
        bpy.ops.object.mode_set(mode='EDIT')
        for ob, heads, tails, offsets in data:
            morphArmature(ob, heads, tails, offsets)
        bpy.ops.object.mode_set(mode=mode)


def register():
    bpy.app.handlers.frame_change_post.append(onFrameChange)

def unregister():
    bpy.app.handlers.frame_change_post.remove(onFrameChange)

if __name__ == "__main__":
    register()