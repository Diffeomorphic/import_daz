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
from .mhx import *
from .error import *

MhxLayers = [
    ((L_MAIN,       'Root', 'MhxRoot'),
     (L_SPINE ,     'Spine', 'MhxFKSpine')),
    ((L_HEAD,       'Head', 'MhxHead'),
     (L_FACE,       'Face', 'MhxFace')),
    ((L_TWEAK,      'Tweak', 'MhxTweak'),
     (L_CUSTOM,     'Custom', 'MhxCustom')),
    ('Left', 'Right'),
    ((L_LARMIK,     'IK Arm', 'MhxIKArm'),
     (L_RARMIK,     'IK Arm', 'MhxIKArm')),
    ((L_LARMFK,     'FK Arm', 'MhxFKArm'),
     (L_RARMFK,     'FK Arm', 'MhxFKArm')),
    ((L_LLEGIK,     'IK Leg', 'MhxIKLeg'),
     (L_RLEGIK,     'IK Leg', 'MhxIKLeg')),
    ((L_LLEGFK,     'FK Leg', 'MhxFKLeg'),
     (L_RLEGFK,     'FK Leg', 'MhxFKLeg')),
    ((L_LEXTRA,     'Extra', 'MhxExtra'),
     (L_REXTRA,     'Extra', 'MhxExtra')),
    ((L_LHAND,      'Hand', 'MhxHand'),
     (L_RHAND,      'Hand', 'MhxHand')),
    ((L_LFINGER,    'Fingers', 'MhxFingers'),
     (L_RFINGER,    'Fingers', 'MhxFingers')),
    ((L_LTOE,       'Toes', 'MhxToe'),
     (L_RTOE,       'Toes', 'MhxToe')),
]


class DAZ_OT_MhxEnableAllLayers(DazOperator):
    bl_idname = "daz.pose_enable_all_layers"
    bl_label = "Enable all layers"
    bl_options = {'UNDO'}

    def run(self, context):
        from .finger import getRigMeshes
        rig,_meshes = getRigMeshes(context)
        for (left,right) in MhxLayers:
            if type(left) != str:
                for (n, name, prop) in [left,right]:
                    rig.data.layers[n] = True


class DAZ_OT_MhxDisableAllLayers(DazOperator):
    bl_idname = "daz.pose_disable_all_layers"
    bl_label = "Disable all layers"
    bl_options = {'UNDO'}

    def run(self, context):
        from .finger import getRigMeshes
        rig,_meshes = getRigMeshes(context)
        layers = 32*[False]
        pb = context.active_pose_bone
        if pb:
            for n in range(32):
                if pb.bone.layers[n]:
                    layers[n] = True
                    break
        else:
            layers[0] = True
        if rig:
            rig.data.layers = layers

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MhxEnableAllLayers,
    DAZ_OT_MhxDisableAllLayers,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)



