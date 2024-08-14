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

import math
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


    scale = rig.DazScale
    heads = {}
    tails = {}
    hdoffsets = {}
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
            bname = pb.name[:-5]
            if bname in rig.pose.bones.keys():
                hdoffsets[bname] = hdoffsets[pb.name] = hdoffsets[bname] + hdoffsets[pb.name]

    processed_bonenames = []
    '''
    # Disabled because it wreaks havoc to G9 eyes
    skeys = None
    for ob in rig.children:
        if ob.type == 'MESH' and ob.DazMesh:
            skeys = ob.data.shape_keys
            break

    if skeys:
        for rigidity_group in rig.data.DazRigidityScaleFactors:
            base_center_coord = rigidity_group.base_center_coord
            combined_all_used_shapekeys_center_coord = Vector(base_center_coord) # Copy
            combined_all_used_shapekeys_scale_difference_from_baseshape = Matrix(([0,0,0],[0,0,0],[0,0,0]))
            for shapekey_scale_factor in rigidity_group.shapekeys:
                if shapekey_scale_factor.name in skeys.key_blocks.keys():
                    shapekey = skeys.key_blocks[shapekey_scale_factor.name]
                    if shapekey.value != 0:
                        shapekey_center_coord = shapekey_scale_factor.shapekey_center_coord
                        scale = shapekey_scale_factor.scale
                        for n in range(3):
                           combined_all_used_shapekeys_scale_difference_from_baseshape[n][n] =((shapekey.value * scale[n][n] + (1-shapekey.value) * 1)-1) + combined_all_used_shapekeys_scale_difference_from_baseshape[n][n]
                           combined_all_used_shapekeys_center_coord[n] = (shapekey.value * (shapekey_center_coord[n] - base_center_coord[n])) + combined_all_used_shapekeys_center_coord[n]
            combined_all_used_shapekeys_scale_difference_from_baseshape = combined_all_used_shapekeys_scale_difference_from_baseshape + Matrix.Identity(3)

            for bone in rigidity_group.affected_bones:
                parent = rig.pose.bones[bone.name].parent
                while parent and parent.bone.get("DazExtraBone"):
                    parent = parent.parent
                heads[bone.name] = (bone.weight * ((combined_all_used_shapekeys_scale_difference_from_baseshape @ (heads[bone.name]-base_center_coord))+combined_all_used_shapekeys_center_coord)) + ((1-bone.weight)*(heads[bone.name]+ hdoffsets[parent.name]))
                tails[bone.name] = (bone.weight * ((combined_all_used_shapekeys_scale_difference_from_baseshape @ (tails[bone.name]-base_center_coord))+combined_all_used_shapekeys_center_coord)) + ((1-bone.weight)*(tails[bone.name]+ hdoffsets[parent.name]))
                hdoffsets[bone.name] = (bone.weight * combined_all_used_shapekeys_scale_difference_from_baseshape @ hdoffsets[bone.name]) + ((1-bone.weight)*hdoffsets[bone.name])
                copyTables(bone.name, "%s(drv)" % bone.name)
                processed_bonenames.append(bone.name)
    '''

    for pb in rig.pose.bones:
        if pb.bone.get("DazExtraBone") and pb.name not in processed_bonenames :
            parent = pb.parent
            while parent and parent.bone.get("DazExtraBone"):
                parent = parent.parent
            if parent:
                hdoffsets[pb.name] = hdoffsets[pb.name] + hdoffsets[parent.name]
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
    bpy.types.Object.DazScale = bpy.props.FloatProperty(default = 0.01)
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