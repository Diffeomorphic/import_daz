# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from ..error import *
from ..utils import *
from ..fileutils import SingleFile, DF
from ..animation import ActionOptions

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

class DAZ_OT_ImportMoho(DazOperator, ActionOptions, SingleFile, IsMeshArmature):
    bl_idname = "daz.import_moho"
    bl_label = "Import Moho"
    bl_description = "Import Moho (.dat) file"
    bl_options = {'UNDO'}

    filename_ext = ".dat"
    filter_glob : StringProperty(default="*.dat", options={'HIDDEN'})

    morphType : EnumProperty(
        items = [('VISEMES', "Visemes", "Visemes"),
                 ('FACS', "FACS", "FACS")],
        name = "Morph Type",
        description = "Import MOHO animation to these morphs",
        default = 'FACS')

    phonemeSet : EnumProperty(
        items = [("Preston-Blair", "Preston-Blair", "Preston-Blair"),
                 ("Fleming-Dobbs", "Fleming-Dobbs",  "Fleming-Dobbs"),
                 ("Rhubarb", "Rhubarb", "Rhubarb"),
                 ("CMU_39", "CMU_39", "CMU_39")],
        name = "Phoneme Set",
        description = "Phoneme Set",
        default = "Preston-Blair")

    emphasis: FloatProperty(
        name = "Emphasis",
        description = "Speech strength",
        min = 0.2, max = 5.0,
        default = 1.0)

    useUpdateLimits : BoolProperty(
        name = "Update Limits",
        description = "Update limits of open vowels to account for emphasis",
        default = True)

    useRelax : BoolProperty(
        name = "Relax Animation",
        description = "Relax the Moho animation to make it more natural",
        default = True)

    useShapekeys : BoolProperty(
        name = "Load To Shapekeys",
        description = "Load morphs to mesh shapekeys instead of rig properties",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "morphType")
        self.layout.prop(self, "phonemeSet")
        self.layout.prop(self, "useRelax")
        if self.useRelax:
            self.layout.prop(self, "emphasis")
            self.layout.prop(self, "useUpdateLimits")
        self.layout.prop(self, "useShapekeys")
        self.layout.separator()
        self.layout.prop(self, "useNewAction")
        if self.useNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "atFrameOne")


    def storeState(self, context):
        scn = context.scene
        self.auto = scn.tool_settings.use_keyframe_insert_auto
        scn.tool_settings.use_keyframe_insert_auto = True
        DazOperator.storeState(self, context)


    def restoreState(self, context):
        scn = context.scene
        scn.tool_settings.use_keyframe_insert_auto = self.auto
        DazOperator.restoreState(self, context)

    openVowels = ["AI", "E", "O"]
    silentVowels = ["FV", "MBP", "WQ"]

    def run(self, context):
        from ..selector import MorphGroup
        scn = context.scene
        if self.useShapekeys:
            ob = context.object
            if ob.type == 'ARMATURE':
                meshes = getShapeChildren(ob)
                if meshes:
                    ob = meshes[0]
                else:
                    raise DazError("No mesh found")
            skeys = ob.data.shape_keys
            if skeys is None:
                raise DazError("%s has no shapekeys" % ob.name)
            entry = DF.findEntry(skeys.key_blocks.keys(), "moho")
            self.clearAnimation(skeys)
        else:
            rig = getRigFromContext(context)
            if rig is None:
                raise DazError("No armature found")
            entry = DF.loadEntry(self.morphType.lower(), "moho")
            self.clearAnimation(rig)

        self.phonemes = entry[self.phonemeSet]

        if self.useShapekeys:
            self.shapes = dict(
                [(skey.name, skey) for skey in skeys.key_blocks.values()
                 if skey.name in self.phonemes.values()])
            self.visemes = dict([(sname, sname) for sname in self.shapes.keys()])
        else:
            mgrp = MorphGroup()
            if self.morphType == 'VISEMES':
                mgrp.init("Visemes", "", "", "DazVisemes")
                pgs = dazRna(rig).DazVisemes
            else:
                mgrp.init("Facs", "", "", "DazFacs")
                pgs = dazRna(rig).DazFacs
            if len(pgs) == 0:
                msg = ("%s has no morphs of type %s.\n" % (rig.name, self.morphType) +
                       "Import morphs first or choose another morph type." )
                raise DazError(msg)
            self.visemes = dict([(pg.text, pg.name) for pg in pgs.values() if pg.name in rig.keys()])

        if self.atFrameOne and self.useNewAction:
            frame0 = 0
        else:
            frame0 = scn.frame_current-1
        frames = self.readMoho()
        if self.useRelax:
            frames = self.improveMoho(frames)
            if self.useUpdateLimits:
                if self.useShapekeys:
                    self.updateShapeLimits(skeys)
                else:
                    self.updateRigLimits(rig)
        if self.useShapekeys:
            self.setShapes(frames, frame0)
        else:
            self.setProps(frames, rig, mgrp, scn, frame0)
            self.nameAnimation(rig, [self.filepath])
        print("Moho file %s loaded" % self.filepath)


    def updateRigLimits(self, rig):
        from ..driver import getPropMinMax, setPropMinMax
        for moho in self.openVowels:
            prop = self.getMohoKey(moho)
            min,max,default,ovr = getPropMinMax(rig, prop, True)
            if max < self.emphasis:
                setPropMinMax(rig, prop, default, min, self.emphasis, True)
            final = finalProp(prop)
            if final in rig.data.keys():
                min,max,default,ovr = getPropMinMax(rig.data, final, False)
                if max < self.emphasis:
                    setPropMinMax(rig.data, final, default, min, self.emphasis, False)


    def updateShapeLimits(self, skeys):
        for moho in self.openVowels:
            prop = self.getMohoKey(moho)
            skey = self.shapes[prop]
            if skey.slider_max < self.emphasis:
                skey.slider_max = self.emphasis


    def readMoho(self):
        from ..fileutils import safeOpen
        frames = []
        with safeOpen(self.filepath, "r") as fp:
            for n,line in enumerate(fp):
                words= line.split()
                if len(words) >= 2 and words[0].isdigit():
                    frames.append((int(words[0]), n, words[1]))
        frames.sort()
        return [(t,key,1.0) for t,n,key in frames]


    def improveMoho(self, frames):
        first,frames = self.splitBeginning(frames)
        frames.reverse()
        last,frames = self.splitBeginning(frames)
        last.reverse()
        frames.reverse()
        key0 = "etc"
        emp = self.emphasis
        nframes = self.pruneRest(first)
        for n,frame in enumerate(frames[:-1]):
            t,key,y = frame
            t1,key1,y1 = frames[n+1]
            if key == "etc":
                if key0 == key1 and key0 in self.openVowels:
                    nframe = (t, key0, 0.5*emp)
                    nframes.append(nframe)
            elif key in self.openVowels:
                if key0 == key1 and key0 in self.silentVowels:
                    nframe = (t, key, 0.5*emp)
                elif key1 in self.silentVowels and t1-t <= 3:
                    nframe = (t, key, 0.5*emp)
                else:
                    nframe = (t, key, emp)
                nframes.append(nframe)
            else:
                nframes.append(frame)
            key0 = key
        nframes.append(frames[-1])
        last = self.pruneRest(last)
        return nframes + last


    def splitBeginning(self, frames):
        first = []
        for frame in frames:
            if frame[1] in ("rest", "etc"):
                first.append(frame)
            else:
                break
        n = len(first)
        return first, frames[n:]


    def pruneRest(self, frames):
        for frame in frames:
            if frame[1] == "rest":
                return [frame]
        return []


    def getMohoKey(self, moho):
        daz = self.phonemes.get(moho)
        if daz is None:
            msg = ("Missing viseme: %s\n" % moho +
                   "Choose different phoneme set")
            raise DazError(msg)
        prop = self.visemes.get(daz)
        if prop:
            return prop
        raise DazError("Missing viseme: %s (%s)\n" % (daz, moho))


    def setProps(self, frames, rig, mgrp, scn, frame0):
        from ..selector import keyProp
        for frame,moho,value in frames:
            for pho in self.phonemes.keys():
                if pho != "rest":
                    prop = self.getMohoKey(pho)
                    rig[prop] = 0.0
                    keyProp(rig, prop, frame)
            if moho != "rest":
                prop = self.getMohoKey(moho)
                rig[prop] = value
                keyProp(rig, prop, frame)


    def setShapes(self, frames, frame0):
        for frame,moho,value in frames:
            for skey in self.shapes.values():
                skey.value = 0.0
                skey.keyframe_insert("value", frame=frame+frame0)
            if moho != "rest":
                prop = self.getMohoKey(moho)
                skey = self.shapes[prop]
                skey.value = value
                skey.keyframe_insert("value", frame=frame+frame0)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

def register():
    bpy.utils.register_class(DAZ_OT_ImportMoho)

def unregister():
    bpy.utils.unregister_class(DAZ_OT_ImportMoho)
