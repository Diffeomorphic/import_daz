# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
from mathutils import Vector, Matrix

def getEditBones(rig):
    def d2b90(v):
        return scale*Vector((v[0], -v[2], v[1]))

    def isOutlier(vec):
        return (vec[0] == -1 and vec[1] == -1 and vec[2] == -1)

    def copyTables(bname1, bname2):
        if bname1 in heads.keys():
            heads[bname2] = heads[bname1]
            tails[bname2]= tails[bname1]

    scale = rig.get("DazScale", 0.01)
    heads = {}
    tails = {}
    hdoffsets = {}
    Zero = Vector((0,0,0))
    for pb in rig.pose.bones:
        if isOutlier(pb.DazHeadLocal):
            pb.DazHeadLocal = pb.bone.head_local
        if isOutlier(pb.DazTailLocal):
            pb.DazTailLocal = pb.bone.tail_local
        heads[pb.name] = Vector(pb.DazHeadLocal)
        tails[pb.name] = Vector(pb.DazTailLocal)
        hdoffsets[pb.name] = d2b90(pb.HdOffset)

    for pb in rig.pose.bones:
        if pb.name[-5:] == "(drv)":
            hdoffsets[pb.name[:-5]] = hdoffsets[pb.name]

    return (rig, heads, tails, hdoffsets)


def morphArmature(data):
    rig, heads, tails, hdoffsets = data
    for eb in rig.data.edit_bones:
        head = heads[eb.name] + hdoffsets[eb.name]
        tail = tails[eb.name] + hdoffsets[eb.name]
        if eb.use_connect and eb.parent:
            eb.parent.tail = head
        eb.head = head
        eb.tail = tail

#----------------------------------------------------------
#   Render a sequence of frames, morphing armatures before rendering each frame
#----------------------------------------------------------

def renderFrames(first=None, last=None, useOpenGl=False, useAllArmatures=True):
    scn = bpy.context.scene
    filepath = scn.render.filepath
    if first is None:
        first = scn.frame_start
    if last is None:
        last = scn.frame_end
    vly = bpy.context.view_layer
    rigs = [ob for ob in vly.objects
            if ob.type == 'ARMATURE' and not (ob.hide_get() or ob.hide_viewport)]
    if useAllArmatures:
        for rig in rigs:
            rig.select_set(True)
    ob = bpy.context.object
    if rigs and not (ob and ob.type == 'ARMATURE'):
        vly.objects.active = rigs[0]
    for frame in range(first, last+1):
        scn.frame_current = frame
        bpy.context.evaluated_depsgraph_get().update()
        scn.render.filepath = "%s%04d" % (filepath, frame)
        if rigs:
            onFrameChangeDaz(scn)
        if useOpenGl:
            bpy.ops.render.opengl(animation=False, write_still=True)
        else:
            bpy.ops.render.render(animation=False, write_still=True, use_viewport=True)
    scn.render.filepath = filepath

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

@persistent
def onFrameChangeDaz(scn):
    datas = []
    for ob in scn.objects:
        if (ob.type == 'ARMATURE' and
            ob.select_get() and
            not ob.hide_get() and
            not ob.hide_viewport):
            mode = ob.mode
            data = getEditBones(ob)
            datas.append(data)
    if datas:
        bpy.ops.object.mode_set(mode='EDIT')
        for data in datas:
            morphArmature(data)
        bpy.ops.object.mode_set(mode=mode)


def register():
    bpy.types.PoseBone.DazHeadLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.DazTailLocal = bpy.props.FloatVectorProperty(size=3, default=(-1,-1,-1))
    bpy.types.PoseBone.HdOffset = bpy.props.FloatVectorProperty(size=3, default=(0,0,0))
    unregister()
    bpy.app.handlers.frame_change_post.append(onFrameChangeDaz)

def unregister():
    oldFcns = [fcn for fcn in bpy.app.handlers.frame_change_post if fcn.__name__ == "onFrameChangeDaz"]
    for fcn in oldFcns:
        bpy.app.handlers.frame_change_post.remove(fcn)

#----------------------------------------------------------
#
#----------------------------------------------------------

if __name__ == "__main__":
    register()
    # Enable this to render with armature morphing
    # renderFrames()