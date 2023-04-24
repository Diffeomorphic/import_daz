# Copyright (c) 2016-2023, Thomas Larsson
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
import math
from math import pi
from mathutils import *
from .utils import *
from .transform import Transform
from .error import *
from .node import Node, Instance
from .bone_data import BD

#-------------------------------------------------------------
#   Alternative bone names
#-------------------------------------------------------------

def getMappedBone(bname, rig):
    if rig is None or bname is None:
        return None
    bname = unquote(bname)
    pg = rig.data.DazBoneMap.get(bname)
    if pg and pg.s in rig.data.bones.keys():
        return pg.s
    elif bname in rig.pose.bones.keys():
        return bname
    bname1 = BD.BoneMap.get(bname)
    if bname1 and bname1 in rig.data.bones.keys():
        return bname1
    from .fix import getSuffixName
    sufname = getSuffixName(bname)
    if sufname in rig.pose.bones.keys():
        return sufname
    #print("NO BONE FOUND", bname)
    return ""

#-------------------------------------------------------------
#   BoneInstance
#-------------------------------------------------------------

class BoneInstance(Instance):

    def __init__(self, fileref, node, struct):
        from .figure import FigureInstance
        Instance.__init__(self, fileref, node, struct)
        if isinstance(self.parent, FigureInstance):
            self.figure = self.parent
        elif isinstance(self.parent, BoneInstance):
            self.figure = self.parent.figure
        self.id = self.node.id.rsplit("#",1)[-1]
        self.name = self.node.name
        self.roll = 0.0
        self.useRoll = False
        self.axes = [0,1,2]
        self.flipped = [False,False,False]
        self.flopped = [False,False,False]
        self.isPosed = False
        self.isBuilt = False
        self.test = False


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        fname = (self.figure.name if self.figure else None)
        return "<BoneInst %s N: %s F: %s T: %s P: %s R:%s>" % (self.id, self.node.name, fname, self.target, pname, self.rna)


    def parentObject(self, context, ob):
        pass


    def buildExtra(self, context):
        pass


    def finalize(self, context):
        pass


    def getHeadTail(self, center, mayfit=True):
        if mayfit and self.restdata:
            head,tail,orient,xyz,origin,wsmat = self.restdata
            #head = (cp - center)
            #tail = (ep - center)
            if orient:
                x,y,z,w = orient
                orient = Quaternion((-w,x,y,z)).to_euler()
            else:
                orient = Euler(self.attributes["orientation"]*D)
                xyz = self.rotation_order
        else:
            head = (self.attributes["center_point"] - center)
            tail = (self.attributes["end_point"] - center)
            orient = Euler(self.attributes["orientation"]*D)
            xyz = self.rotation_order
            wsmat = self.U3
        if (tail-head).length < 0.1:
            tail = head + Vector((0,1,0))
        return head,tail,orient,xyz,wsmat

    RX = Matrix.Rotation(pi/2, 4, 'X')
    FX = Matrix.Rotation(pi, 4, 'X')
    FZ = Matrix.Rotation(pi, 4, 'Z')

    def buildEdit(self, figure, figinst, rig, parent, center, isFace):
        self.makeNameUnique(rig.data.edit_bones)
        head,tail,orient,xyz,wsmat = self.getHeadTail(center)
        eb = rig.data.edit_bones.new(self.name)
        figure.bones[self.name] = eb.name
        figinst.bones[self.name] = self
        if (head-tail).length < 1e-5:
            raise RuntimeError("BUG: buildEdit %s %s %s" % (self.name, head, tail))
        eb.parent = parent
        eb.head = head = d2b(head)
        eb.tail = tail = d2b(tail)
        length = (head-tail).length
        omat = orient.to_matrix()
        lsmat = self.getLocalMatrix(wsmat, omat)
        if not eulerIsZero(lsmat.to_euler()):
            self.isPosed = True
        omat = omat.to_4x4()
        if GS.zup:
            omat = self.RX @ omat
        flip = self.FX
        if not GS.unflipped:
            omat,flip = self.flipAxes(omat, xyz)

        if self.test:
            print("BB", self.name, orient)

        #  engetudouiti's fix for posed bones
        rmat = wsmat.to_4x4()
        if GS.zup:
            rmat = self.RX @ rmat @ self.RX.inverted()
        if rmat.determinant() > 1e-4:
            omat = rmat.inverted() @ omat

        if GS.unflipped:
            omat.col[3][0:3] = head
            eb.matrix = omat
        else:
            omat = self.flipBone(omat, head, tail, flip)
            self.setFlip()
            if self.test:
                print("FBONE", self.name, self.rotation_order, self.axes, self.flipped)
            omat.col[3][0:3] = head
            eb.matrix = omat
            self.correctRoll(eb, figure)
        self.correctLength(eb, length)

        if self.name in ["upperFaceRig", "lowerFaceRig"]:
            isFace = True
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(figure, figinst, rig, eb, center, isFace)
        self.isBuilt = True


    def makeNameUnique(self, ebones):
        if self.name not in ebones.keys():
            return
        orig = self.name
        if len(self.name) < 2:
            self.name = "%s-1" % self.name
        while self.name in ebones.keys():
            if self.name[-2] == "-" and self.name[-1].isdigit():
                self.name = "%s-%d" % (self.name[:-2], 1+int(self.name[-1]))
            else:
                self.name = "%s-1" % self.name
        print("Bone name made unique: %s => %s" % (orig, self.name))


    def flipAxes(self, omat, xyz):
        if xyz == 'YZX':    #
            # Blender orientation: Y = twist, X = bend
            euler = Euler((0,0,0))
            flip = self.FX
            self.axes = [0,1,2]
            self.flipped = [False,False,False]
            self.flopped = [False,True,True]
        elif xyz == 'YXZ':
            # Apparently not used
            euler = Euler((0, pi/2, 0))
            flip = self.FZ
            self.axes = [2,1,0]
            self.flipped = [False,False,False]
            self.flopped = [False,False,False]
        elif xyz == 'ZYX':  #
            euler = Euler((pi/2, 0, 0))
            flip = self.FX
            self.axes = [0,2,1]
            self.flipped = [False,True,False]
            self.flopped = [False,False,False]
        elif xyz == 'XZY':  #
            euler = Euler((0, 0, pi/2))
            flip = self.FZ
            self.axes = [1,0,2]
            self.flipped = [False,False,False]
            self.flopped = [False,True,False]
        elif xyz == 'ZXY':
            # Eyes and eyelids
            euler = Euler((pi/2, 0, 0))
            flip = self.FZ
            self.axes = [0,2,1]
            self.flipped = [False,True,False]
            self.flopped = [False,False,False]
        elif xyz == 'XYZ':  #
            euler = Euler((pi/2, pi/2, 0))
            flip = self.FZ
            self.axes = [1,2,0]
            self.flipped = [True,True,True]
            self.flopped = [True,True,False]

        if self.test:
            print("\nAXES", self.name, xyz, self.axes)
        rmat = euler.to_matrix().to_4x4()
        omat = omat @ rmat
        return omat, flip


    def flipBone(self, omat, head, tail, flip):
        vec = tail-head
        yaxis = Vector(omat.col[1][0:3])
        if vec.dot(yaxis) < 0:
            if self.test:
                print("FLOP", self.name)
            self.flipped = self.flopped
            return omat @ flip
        else:
            return omat


    def correctRoll(self, eb, figure):
        if eb.name in BD.RollCorrection.keys():
            offset = BD.RollCorrection[eb.name]
        elif (figure.rigtype in ["genesis1", "genesis2"] and
              eb.name in BD.RollCorrectionG12.keys()):
            offset = BD.RollCorrectionG12[eb.name]
        else:
            return

        roll = eb.roll + offset*D
        if roll > pi:
            roll -= 2*pi
        elif roll < -pi:
            roll += 2*pi
        eb.roll = roll

        a = self.axes
        f = self.flipped
        i = a.index(0)
        j = a.index(1)
        k = a.index(2)
        if offset == 90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == -90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == 180:
            f[i] = not f[i]
            f[k] = not f[k]


    def correctLength(self, eb, length):
        vec = (eb.tail - eb.head).normalized()
        eb.tail = eb.head + length*vec


    def buildBoneProps(self, rig, center):
        if self.name not in rig.data.bones.keys():
            return
        bone = rig.data.bones[self.name]
        bone.inherit_scale = GS.defaultInherit()
        bone.DazOrient = self.attributes["orientation"]

        head,tail,orient,xyz,wsmat = self.getHeadTail(center)
        head0,tail0,orient0,xyz0,wsmat0 = self.getHeadTail(center, False)
        bone.DazHead = head
        bone.DazTail = tail
        bone.DazAngle = 0

        vec = d2b00(tail) - d2b00(head)
        vec0 = d2b00(tail0) - d2b00(head0)
        if vec.length > 0 and vec0.length > 0:
            vec /= vec.length
            vec0 /= vec0.length
            sprod = vec.dot(vec0)
            if sprod < -0.99:
                bone.DazAngle = math.pi
                bone.DazNormal = vec.cross(vec0)
            elif sprod < 0.99:
                bone.DazAngle = math.acos(sprod)
                bone.DazNormal = vec.cross(vec0)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)


    def buildFormulas(self, rig, hide):
        from .load_morph import buildBoneFormula
        if (self.node.formulas and
            self.name in rig.pose.bones.keys()):
            pb = rig.pose.bones[self.name]
            pb.rotation_mode = self.getRotationMode(pb, self.isRotMorph(self.node.formulas))
            errors = []
            buildBoneFormula(self.node, rig, self.figure.altmorphs, errors)
        if hide or not self.getValue(["Visible"], True):
            self.figure.hiddenBones[self.name] = True
            bone = rig.data.bones[self.name]
            bone.hide = True
        if self.name.endswith(("twist1", "twist2")):
            bone = rig.data.bones[self.name]
            bone.layers = 31*[False] + [True]
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, hide)


    def isRotMorph(self, formulas):
        for formula in formulas:
            if ("output" in formula.keys() and
                "?rotation" in formula["output"]):
                return True
        return False


    def getRotationMode(self, pb, useEulers):
        if GS.unflipped:
            return self.rotation_order
        elif useEulers:
            return self.getDefaultMode(pb)
        elif GS.useQuaternions and pb.name in BD.SocketBones:
            return 'QUATERNION'
        else:
            return self.getDefaultMode(pb)


    def getDefaultMode(self, pb):
        if pb.name in BD.RotationModes.keys():
            return BD.RotationModes[pb.name]
        else:
            return 'YZX'


    def setFlip(self):
        if self.name.startswith(BD.UnFlips):
            self.flipped[0] = False
        elif self.name.startswith(BD.Flips):
            self.flipped[0] = True


    def buildPose(self, figure, inFace, targets, missing):
        from .driver import isBoneDriven
        node = self.node
        rig = figure.rna
        if node.name not in rig.pose.bones.keys():
            print("NIX", node.name)
            return
        pb = rig.pose.bones[node.name]
        self.rna = pb
        pb.bone.inherit_scale = GS.defaultInherit()
        mapped = self.node.mapped
        if (mapped and
            self.name != mapped and
            mapped not in rig.data.DazBoneMap.keys()):
            pg = rig.data.DazBoneMap.add()
            pg.name = mapped
            pg.s = self.name
        if isBoneDriven(rig, pb):
            pb.rotation_mode = self.getRotationMode(pb, True)
            pb.bone.layers = [False,True] + 30*[False]
        else:
            pb.rotation_mode = self.getRotationMode(pb, False)
        pb.DazRotMode = self.rotation_order
        pb.DazAxes = self.axes
        pb.DazFlips = [(-1 if flip else +1) for flip in self.flipped]
        tchildren = self.targetTransform(pb, node, targets, rig)
        self.setRotationLockDaz(pb, rig)
        self.setLocationLockDaz(pb, rig)
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(figure, inFace, tchildren, missing)


    def targetTransform(self, pb, node, targets, rig):
        from .node import setBoneTransform
        tname = getMappedBone(node.name, rig)
        if tname and tname in targets.keys():
            tinst = targets[tname]
            tfm = Transform(
                trans = tinst.attributes["translation"],
                rot = tinst.attributes["rotation"])
            tchildren = tinst.children
        else:
            tinst = None
            tfm = Transform(
                trans = self.attributes["translation"],
                rot = self.attributes["rotation"])
            tchildren = {}
        if LS.fitFile:
            if nonzero(tfm.rot):
                pb.DazRestRotation = tfm.rot
        else:
            setBoneTransform(tfm, pb, False)
            if nonzero(tfm.trans):
                pb.DazTranslation = tfm.trans
            if nonzero(tfm.rot):
                pb.DazRotation = tfm.rot
        return tchildren


    def formulate(self, key, value):
        from .node import setBoneTransform
        if self.figure is None:
            return
        channel,comp = key.split("/")
        self.attributes[channel][getIndex(comp)] = value
        pb = self.rna
        node = self.node
        tfm = Transform(
            trans=self.attributes["translation"],
            rot=self.attributes["rotation"])
        setBoneTransform(tfm, pb)


    def getLocksLimits(self, pb, structs):
        locks = [False, False, False]
        limits = [None, None, None]
        useLimits = False
        for idx,comp in enumerate(structs):
            if "locked" in comp.keys() and comp["locked"]:
                locks[idx] = True
            elif "clamped"in comp.keys() and comp["clamped"]:
                if comp["min"] == 0 and comp["max"] == 0:
                    locks[idx] = True
                else:
                    limits[idx] = (comp["min"], comp["max"])
                    if comp["min"] != -180 or comp["max"] != 180:
                        useLimits = True
        return locks,limits,useLimits


    IndexComp = { 0 : "x", 1 : "y", 2 : "z" }

    def setRotationLockDaz(self, pb, rig):
        locks,limits,useLimits = self.getLocksLimits(pb, self.node.rotation)
        if pb.rotation_mode == 'QUATERNION':
            return
        # DazRotLocks used to update lock_rotation
        for n,lock in enumerate(locks):
            idx = self.axes[n]
            pb.DazRotLocks[idx] = lock
        if GS.useLockRot:
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_rotation[idx] = lock
        if useLimits and GS.useLimitRot and not self.isPosed:
            from .mhx import limitRotation
            cns = limitRotation(pb, rig)
            for n,limit in enumerate(limits):
                idx = self.axes[n]
                if limit is not None:
                    mind, maxd = limit
                    minr = mind*D
                    if abs(minr) < 1e-4:
                        minr = 0
                    maxr = maxd*D
                    if abs(maxr) < 1e-4:
                        maxr = 0
                    if self.flipped[n]:
                        tmp = minr
                        minr = -maxr
                        maxr = -tmp
                    xyz = self.IndexComp[idx]
                    setattr(cns, "use_limit_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, minr)
                    setattr(cns, "max_%s" % xyz, maxr)
                    if GS.displayLimitRot:
                        setattr(pb, "use_ik_limit_%s" % xyz, True)
                        setattr(pb, "ik_min_%s" % xyz, minr)
                        setattr(pb, "ik_max_%s" % xyz, maxr)


    def setLocationLockDaz(self, pb, rig):
        locks,limits,useLimits = self.getLocksLimits(pb, self.node.translation)
        # DazLocLocks used to update lock_location
        for n,lock in enumerate(locks):
            idx = self.axes[n]
            pb.DazLocLocks[idx] = lock
        if GS.useLockLoc:
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_location[idx] = lock
        if useLimits and GS.useLimitLoc:
            from .mhx import limitLocation
            cns = limitLocation(pb, rig)
            for n,limit in enumerate(limits):
                idx = self.axes[n]
                if limit is not None:
                    mind, maxd = limit
                    if self.flipped[n]:
                        tmp = mind
                        mind = -maxd
                        maxd = -tmp
                    xyz = self.IndexComp[idx]
                    setattr(cns, "use_min_%s" % xyz, True)
                    setattr(cns, "use_max_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, mind*LS.scale)
                    setattr(cns, "max_%s" % xyz, maxd*LS.scale)

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def eulerIsZero(euler):
    vals = [abs(x) for x in euler]
    return (max(vals) < 1e-4)


def setRoll(eb, xaxis):
    yaxis = eb.tail - eb.head
    yaxis.normalize()
    xaxis -= yaxis.dot(xaxis)*yaxis
    xaxis.normalize()
    zaxis = xaxis.cross(yaxis)
    zaxis.normalize()
    mat = Matrix().to_3x3()
    mat.col[0] = xaxis
    mat.col[1] = yaxis
    mat.col[2] = zaxis
    quat = mat.to_quaternion()
    if abs(quat.w) < 1e-4:
        eb.roll = pi
    else:
        eb.roll = 2*math.atan(quat.y/quat.w)

#-------------------------------------------------------------
#   Bone
#-------------------------------------------------------------

class Bone(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.mapped = None


    def __repr__(self):
        return ("<Bone %s %s>" % (self.id, self.instances))


    def getSelfId(self):
        return self.node.name


    def makeInstance(self, fileref, struct):
        return BoneInstance(fileref, self, struct)


    def getInstance(self, ref, caller=None):
        def getSelfInstance(ref, instances):
            iref = instRef(ref)
            if iref in instances.keys():
                return instances[iref]
            iref = unquote(iref)
            if iref in instances.keys():
                return instances[iref]
            elif iref in BD.BoneMap.keys():
                return instances.get(BD.BoneMap[iref])
            else:
                return None

        iref = getSelfInstance(ref, self.instances)
        if iref:
            return iref
        if self.sourcing:
            iref = getSelfInstance(ref, self.sourcing.instances)
            if iref:
                print("Sourced %s" % iref)
                return iref

        trgfig = self.figure.sourcing
        if trgfig:
            iref = instRef(ref)
            struct = {
                "id" : iref,
                "url" : self.url,
                "target" : trgfig,
            }
            print("Creating reference to target figure:\n", trgfig)
            inst = self.makeInstance(self.fileref, struct)
            self.instances[iref] = inst
            print("Target instance:\n", inst)
            return inst
        if (GS.verbosity <= 2 and
            len(self.instances.values()) > 0):
            return list(self.instances.values())[0]
        msg = ("Bone: Did not find instance %s in %s\nSelf = %s\nSourcing = %s" % (iref, list(self.instances.keys()), self, self.sourcing))
        reportError(msg, trigger=(2,3))
        return None


    def parse(self, struct):
        from .figure import Figure
        Node.parse(self, struct)
        for channel,data in struct.items():
            if channel == "rotation":
                self.rotation = data
            elif channel == "translation":
                self.translation = data
            elif channel == "scale":
                self.scale = data
        if isinstance(self.parent, Figure):
            self.figure = self.parent
        elif isinstance(self.parent, Bone):
            self.figure = self.parent.figure


    def update(self, struct):
        Node.update(self, struct)
        if "url" in struct.keys():
            self.mapped = unquote(struct["url"]).rsplit("#")[-1]


    def build(self, context, inst=None):
        pass


    def preprocess(self, context, inst):
        pass


    def poseRig(self, context, inst):
        pass

