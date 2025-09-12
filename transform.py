# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from mathutils import *
from .utils import *

class Transform:
    def __init__(self, trans=None, rot=None, scale=None, general=None):
        self.trans = trans
        self.rot = rot
        self.scale = scale
        self.general = general

        self.transProp = None
        self.rotProp = None
        self.scaleProp = None
        self.generalProp = None

    def __repr__(self):
        return ("<TFM t:%s\n    r:%s\n    s:%s\n    g:%s\n    %s %s %s %s>" %
                (self.trans, self.rot, self.scale, self.general,
                 self.transProp, self.rotProp, self.scaleProp, self.generalProp))


    def noTrans(self):
        self.trans = None
        self.transProp = None

    def setTrans(self, trans, prop=None, index=None):
        if index is None:
            self.trans = Vector(trans)
        else:
            self.trans = Vector((0,0,0))
            self.trans[index] = trans
        self.transProp = prop

    def noRot(self):
        self.rot = None
        self.rotProp = None

    def setRot(self, rot, prop=None, index=None):
        if index is None:
            self.rot = Vector(rot)
        else:
            self.rot = Vector((0,0,0))
            self.rot[index] = rot
        self.rotProp = prop

    def noScale(self):
        self.scale = None
        self.scaleProp = None

    def setScale(self, scale, addUnit, prop=None, index=None):
        if index is None:
            self.scale = Vector(scale)
        elif index == -1:
            self.scale = Vector((scale,scale,scale))
        else:
            self.scale = Vector((0,0,0))
            self.scale[index] = scale
        if addUnit:
            self.scale += One
        self.scaleProp = prop

    def noGeneral(self):
        self.general = None
        self.generalProp = None

    def setGeneral(self, general, addUnit, prop=None):
        if addUnit:
            self.general = general + 1
        else:
            self.general = general
        self.generalProp = prop


    def evalTrans(self):
        if self.trans is None:
            return Vector((0,0,0))
        else:
            return self.trans

    def evalRot(self):
        if self.rot is None:
            return Vector((0,0,0))
        else:
            return self.rot*D

    def evalScale(self):
        if self.scale is None:
            scale = Vector((1,1,1))
        else:
            scale = self.scale
        if self.general is not None:
            scale *= self.general
        if scale.length == 0:
            raise RuntimeError("Bug evalScale")
        return scale


    def getTransMat(self):
        return Matrix.Translation(d2b00(self.evalTrans()))


    def getRotation(self):
        if self.rot is None:
            return Zero
        elif isinstance(self.rot, Quaternion) or isinstance(self.rot, Matrix):
            return Vector(self.rot.to_euler(dazRna(pb).DazRotMode))/D
        else:
            return Vector(self.rot)


    def getRotMat(self, pb):
        if self.rot is None:
            return Matrix()
        elif isinstance(self.rot, Quaternion):
            return self.rot.to_matrix().to_4x4()
        elif isinstance(self.rot, Matrix):
            return self.rot.to_4x4()
        else:
            return getEulerMatrix(self.rot, dazRna(pb).DazRotMode)


    def getScaleMat(self):
        mat = Matrix()
        scale = self.evalScale()
        for n in range(3):
            mat[n][n] = scale[n]
        return mat


    def hasNoScale(self):
        return ((self.scale is None or (self.scale-One).length == 0.0) and self.general == 1)


    def setObject(self, ob):
        ob.location = d2b(self.evalTrans() + Vector(dazRna(ob).DazCenter))
        rot = d2bu(self.evalRot())
        mid = ord(dazRna(ob).DazRotMode[1]) - ord('X')
        if abs(abs(rot[mid]) - pi/2) < 0.01:
            quat = Euler(rot, 'ZXY').to_quaternion()
            rot = quat.to_euler(ob.rotation_mode)
        ob.rotation_euler = rot
        ob.scale = d2bs(self.evalScale())


    def clearRna(self, rna):
        rna.location = (0,0,0)
        rna.rotation_euler = (0,0,0)
        if hasattr(rna, "rotation_quaternion"):
            rna.rotation_quaternion = (1,0,0,0)
        rna.scale = (1,1,1)


    def insertTranslationKey(self, rig, pb, frame, group, driven):
        if self.trans is None:
            return
        if pb is None:
            rig.keyframe_insert("location", frame=frame, group=group)
            return
        if pb.bone.use_connect or pb.name in driven:
            return
        if not isLocationLocked(pb):
            pb.keyframe_insert("location", frame=frame, group=group)


    def insertRotationKey(self, rig, pb, frame, group, driven):
        if self.rot is None:
            return
        if pb is None:
            rig.keyframe_insert("rotation_euler", frame=frame, group=group)
            return
        if pb.name in driven:
            return
        if pb.rotation_mode == 'QUATERNION':
            channel = "rotation_quaternion"
        else:
            channel = "rotation_euler"
        pb.keyframe_insert(channel, frame=frame, group=group)


    def insertScaleKey(self, rig, pb, frame, group, driven):
        if self.scale is None and self.general is None:
            return
        if pb is None:
            rig.keyframe_insert("scale", frame=frame, group=group)
            return
        if pb.name in driven:
            return
        if (pb.lock_scale[0] == False or
            pb.lock_scale[1] == False or
            pb.lock_scale[2] == False):
            pb.keyframe_insert("scale", frame=frame, group=group)

#-------------------------------------------------------------
#   Rounding
#-------------------------------------------------------------

def roundMatrix(mat, eps):
    for i in range(3):
        for j in range(3):
            if abs(mat[i][j]) < eps:
                mat[i][j] = 0


def roundVector(vec, eps = 1e-4):
    for i in range(3):
        if abs(vec[i]) < eps:
            vec[i] = 0
    return vec


def roundQuat(quat, eps = 1e-4):
    if abs(quat[0]-1) < eps:
        quat[0] = 1
    for i in range(1,4):
        if abs(quat[i]) < eps:
            quat[i] = 0
    return quat


def roundScale(scale, eps = 1e-4):
    for i in range(3):
        if abs(scale[i]-1) < eps:
            scale[i] = 1
    return scale

