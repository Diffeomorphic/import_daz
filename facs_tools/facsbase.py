# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from ..utils import *
from ..error import *
from ..fileutils import DF

#------------------------------------------------------------------
#   Utility class BoneHandler
#------------------------------------------------------------------

class BoneHandler:
    def setRotation(self, pb, euler, frame, fraction=None):
        if fraction == 0 or pb is None:
            return
        elif fraction is not None:
            euler = Euler(fraction*Vector(euler))
        mat = euler.to_matrix()
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = mat.to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
        else:
            pb.rotation_euler = mat.to_euler(pb.rotation_mode)
            pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)


    def getBones(self, bnames, rig):
        def getBone(bname, rig):
            if bname not in rig.pose.bones.keys():
                return None
            pb = rig.pose.bones[bname]
            if rig.animation_data and not self.useShapekeys:
                msg = ("Bone %s is driven.\nMake bones posable first" % bname)
                datapath = 'pose.bones["%s"].rotation_euler' % bname
                for fcu in rig.animation_data.drivers:
                    if fcu.data_path == datapath:
                        raise DazError(msg)
            return pb

        for bname in bnames:
            pb = getBone(bname, rig)
            if pb:
                return pb
        print("Did not find bones: %s" % bnames)
        return None

#------------------------------------------------------------------
#   Head User
#------------------------------------------------------------------

class HeadUser:
    useHeadLoc : BoolProperty(
        name = "Head Location",
        description = "Include head location animation",
        default = False)

    useHeadRot : BoolProperty(
        name = "Head Rotation",
        description = "Include head rotation animation",
        default = True)

    headDist : FloatProperty(
        name = "Head",
        description = "Fraction of head rotation that affects head",
        min = 0.0, max = 1.0,
        default = 0.15)

    neckUpperDist : FloatProperty(
        name = "Upper Neck",
        description = "Fraction of head rotation that affects upper neck",
        min = 0.0, max = 1.0,
        default = 0.4)

    neckLowerDist : FloatProperty(
        name = "Lower Neck",
        description = "Fraction of head rotation that affects lower neck",
        min = 0.0, max = 1.0,
        default = 0.4)

    abdomenDist : FloatProperty(
        name = "Abdomen",
        description = "Fraction of head rotation that affects abdomen",
        min = 0.0, max = 1.0,
        default = 0.05)

    def draw(self, context):
        if self.useShapekeys:
            return
        self.layout.prop(self, "useHeadLoc")
        self.layout.prop(self, "useHeadRot")
        if self.useHeadRot:
            box = self.layout.box()
            box.prop(self, "headDist")
            box.prop(self, "neckUpperDist")
            box.prop(self, "neckLowerDist")
            box.prop(self, "abdomenDist")

    def setupHead(self, rig):
        self.head = self.getBones(["head"], rig)
        self.neckUpper = self.getBones(["neckUpper", "neck2", "neck-1"], rig)
        self.neckLower = self.getBones(["neckLower", "neck1", "neck"], rig)
        self.abdomen = self.getBones(["abdomenUpper", "spine2", "spine-1", "spine_fk.002"], rig)
        self.hip = self.getBones(["hip", "torso"], rig)
        if self.head is None:
            self.headDist = 0
        if self.neckUpper is None:
            self.neckUpperDist = 0
        if self.neckLower is None:
            self.neckLowerDist = 0
        if self.abdomen is None:
            self.abdomenDist = 0
        distsum = self.headDist + self.neckUpperDist + self.neckLowerDist + self.abdomenDist
        self.headDist /= distsum
        self.neckUpperDist /= distsum
        self.neckLowerDist /= distsum
        self.abdomenDist /= distsum

#------------------------------------------------------------------
#   Generic FACS importer
#------------------------------------------------------------------

class FACSImporter(BoneHandler, IsMeshArmature):

    useShapekeys : BoolProperty(
        name = "Load To Shapekeys",
        description = "Load morphs to mesh shapekeys instead of rig properties",
        default = False)

    useEyes : BoolProperty(
        name = "Eyes",
        description = "Include eyes animation",
        default = False)

    useTongue : BoolProperty(
        name = "Tongue",
        description = "Include tongue animation",
        default = False)

    filepath : StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        default="")

    makeNewAction : BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName : StringProperty(
        name = "Action Name",
        description = "Name of loaded action.\nUse name of imported file if blank",
        default = "")

    fps : FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in animation file.\nFPS = 0 means one frame per step",
        min = 0,
        default = 0)

    def draw(self, context):
        self.layout.prop(self, "fps")
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "useShapekeys")
        #self.layout.prop(self, "useEyes")
        #self.layout.prop(self, "useTongue")


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        entry = None
        if self.useShapekeys:
            rig = context.object
            if rig.type == 'ARMATURE':
                meshes = getShapeChildren(rig)
                skeys = meshes[0].data.shape_keys
                klist = [list(ob.data.shape_keys.key_blocks.keys()) for ob in meshes]
                keys = set(flatten(klist))
                rig = None
            else:
                ob = rig
                skeys = ob.data.shape_keys
                if skeys is None:
                    raise DazError("Active mesh has no shapekeys")
                meshes = [ob]
                keys = skeys.key_blocks.keys()
                rig = None
            entry = DF.findEntry(skeys.key_blocks.keys(), "facs")
        else:
            rig = getRigFromContext(context)
            if rig:
                meshes = []
                keys = rig.keys()
                rig["MhaGaze_L"] = 0.0
                rig["MhaGaze_R"] = 0.0
                entry = DF.findEntry(rig.keys(), "facs")
        if not entry:
            print("No entry")
            return
        self.getSource(context)
        self.setupFacsTable(entry, keys)
        self.bshapes = []
        self.bskeys = {}
        self.hlockeys = {}
        self.hrotkeys = {}
        self.leyekeys = {}
        self.reyekeys = {}
        self.shapekeys = {}
        for ob in meshes:
            for skey in ob.data.shape_keys.key_blocks:
                self.shapekeys[skey.name] = True
        self.parse(context)
        print("Blendshapes: %d" % len(self.bshapes))
        if self.bskeys:
            first = list(self.bskeys.values())[0]
            print("Keys: %d" % len(first))
        else:
            raise DazError("No FACS animation found")
        if self.makeNewAction:
            def addAction(rna):
                if self.actionName:
                    aname = self.actionName
                else:
                    aname = os.path.splitext(os.path.basename(self.filepath))[0]
                if rna.animation_data is None:
                    rna.animation_data_create()
                act = bpy.data.actions.new(name=aname)
                rna.animation_data.action = act

            if meshes:
                for ob in meshes:
                    addAction(ob.data.shape_keys)
            else:
                addAction(rig)
        self.build(context, rig, meshes)


    def getSource(self, context):
        pass


    def setupFacsTable(self, entry, keys):
        self.facstable = {}
        print("Setting up FACS table for %s" % entry["name"])
        miss = []
        for key,data in entry["facs"].items():
            if isinstance(data[0], str):
                data = [data]
            self.facstable[key.lower()] = dict(data)
            for prop,factor in data:
                if prop not in keys:
                    miss.append(prop)
        print("Missing FACS morphs (%d): %s" % (len(miss), miss))


    def build(self, context, rig, meshes):
        def isMatch(string, bases):
            for base in bases:
                if string in base:
                    return True
            return False

        missing = []
        for bshape in self.bshapes:
            if bshape not in self.facstable.keys():
                missing.append(bshape)
        if rig:
            self.setupBones(rig)
        self.skipped = {}
        missingShapes = {}
        warned = []
        nframes = len(self.bskeys)
        t1 = perf_counter()
        for n,t in enumerate(self.bskeys.keys()):
            prev = {}
            if self.fps == 0:
                frame = n+1
            else:
                frame = self.getFrame(t)
            if rig:
                self.setBoneFrame(t, frame, context)
            for bshape,value in zip(self.bshapes, self.bskeys[t]):
                formulas = self.facstable.get(bshape)
                if formulas is None:
                    if bshape not in warned and bshape not in self.skipped.keys():
                        warned.append(bshape)
                    continue
                for prop,factor in formulas.items():
                    for ob in meshes:
                        if prop in ob.data.shape_keys.key_blocks.keys():
                            skey = ob.data.shape_keys.key_blocks[prop]
                            prev[prop] = skey.value = value*factor + prev.get(prop, 0)
                            skey.keyframe_insert("value", frame=frame)
                        else:
                            if ob.name not in missingShapes.keys():
                                missingShapes[ob.name] = {}
                            missingShapes[ob.name][prop] = True
                    if rig:
                        prev[prop] = rig[prop] = value*factor + prev.get(prop, 0)
                        rig.keyframe_insert(propRef(prop), frame=frame, group="FACS")

        t2 = perf_counter()
        print("%d frames loaded in %g seconds" % (nframes, t2-t1))

        if warned:
            print("WARN", warned)
        if missing:
            msg = "Missing blendshapes:     \n"
            missing.sort()
            for bshape in missing:
                msg += ("  %s\n" % bshape)
            print(msg)
            msg = ("%d blendshapes missing. See terminal window for details." % len(missing))
            self.report({'WARNING'}, msg)

        elif missingShapes:
            msg = "The following objects are missing shapekeys. See terminal window for details."
            for obname in missingShapes.keys():
                msg += "  %s\n" % obname
            self.report({'WARNING'}, msg)


    def setupBones(self, rig):
        self.leye = self.getBones(["lEye", "l_eye", "eye.L"], rig)
        self.reye = self.getBones(["rEye", "r_eye", "eye.R"], rig)
        self.setupHead(rig)


    def setupHead(self, rig):
        pass


    def setBoneFrame(self, t, frame, context):
        if self.useHeadLoc:
            self.hip.location = GS.scale*self.hlockeys[t]
            self.hip.keyframe_insert("location", frame=frame, group="hip")
        if self.useHeadRot:
            self.setRotation(self.head, self.hrotkeys[t], frame, self.headDist)
            self.setRotation(self.neckUpper, self.hrotkeys[t], frame, self.neckUpperDist)
            self.setRotation(self.neckLower, self.hrotkeys[t], frame, self.neckLowerDist)
            self.setRotation(self.abdomen, self.hrotkeys[t], frame, self.abdomenDist)
        if self.useEyes:
            self.setRotation(self.leye, self.leyekeys[t], frame)
            self.setRotation(self.reye, self.reyekeys[t], frame)

#------------------------------------------------------------------
#   Copy FACS animation
#------------------------------------------------------------------

class FACSCopier:
    useHeadLoc = False
    useHeadRot = False

    def getFcurves(self, act):
        fcus = {}
        tmin = 99999
        tmax = -99999
        fcurves = getActionBag(act, 'KEY').fcurves
        for fcu in fcurves:
            sname,channel = getShapeChannel(fcu)
            if sname and channel == "value":
                fcus[sname.lower()] = fcu
                times = [kp.co[0] for kp in fcu.keyframe_points]
                t0 = int(min(times))
                t1 = int(max(times))
                if t0 < tmin:
                    tmin = t0
                if t1 > tmax:
                    tmax = t1
        for t in range(tmin, tmax+1):
            if t not in self.bskeys.keys():
                self.bskeys[t] = []
                self.hlockeys[t] = Vector((0,0,0))
                self.hrotkeys[t] = Euler((0,0,0))
                self.leyekeys[t] = Euler((0,0,0))
                self.reyekeys[t] = Euler((0,0,0))
        for key,fcu in fcus.items():
            if key not in self.bshapes:
                self.bshapes.append(key)
                for t in range(tmin, tmax+1):
                    self.bskeys[t].append(fcu.evaluate(t))
        if tmin > tmax:
            raise DazError("No source F-curves found")

    def getFrame(self, t):
        return t+1


class DAZ_OT_CopyFacsAnimation(DazPropsOperator, FACSImporter, FACSCopier):
    bl_idname = "daz.copy_facs_animation"
    bl_label = "Copy FACS Animation"
    bl_description = "Copy FACS animation from selected mesh to active character"
    bl_options = {'UNDO'}

    def run(self, context):
        FACSImporter.run(self, context)

    def getSource(self, context):
        self.action = None
        for ob in context.view_layer.objects:
            if ob.type == 'MESH' and ob.select_get():
                skeys = ob.data.shape_keys
                if skeys and skeys.animation_data and skeys.animation_data.action:
                    self.action = skeys.animation_data.action
                    return
        raise DazError("No source mesh found")

    def parse(self, context):
        self.getFcurves(self.action)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_CopyFacsAnimation)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_CopyFacsAnimation)
