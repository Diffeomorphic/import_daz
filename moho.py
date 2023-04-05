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

import os
import bpy

from .error import *
from .utils import *
from .selector import getRigFromObject
from .fileutils import SingleFile, DatFile
from .animation import ActionOptions

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

class DAZ_OT_LoadMoho(DazOperator, DatFile, ActionOptions, SingleFile, IsMeshArmature):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

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

    def draw(self, context):
        self.layout.prop(self, "phonemeSet")
        self.layout.prop(self, "useRelax")
        if self.useRelax:
            self.layout.prop(self, "emphasis")
            self.layout.prop(self, "useUpdateLimits")
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
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

    phonemeConverters = {
        "Preston-Blair" : {
            "AI": "AA",
            "E": "EH",
            "etc": "K",
            "FV": "F",
            "L": "L",
            "MBP": "M",
            "O": "OW",
            "rest": "Rest",
            "U": "UW",
            "WQ": "W"
        },
        "Fleming-Dobbs" : {
            "AA": "AA",
            "EHSZ": "W",
            "FV": "F",
            "GK": "W",
            "IY": "OW",
            "MBP": "K",
            "NLTDR": "EH",
            "O": "Rest",
            "rest": "L",
            "SH": "F",
            "TH": "EH"
        },
        "Rhubarb" : {
            "A": "K",
            "B": "OW",
            "C": "W",
            "D": "AA",
            "E": "W",
            "F": "Rest",
            "G": "F",
            "H": "EH",
            "rest": "L"
        },
        "CMU_39" : {
            "AA": "AA",
            "AE": "AA",
            "AH": "EH",
            "AO": "OW",
            "AW": "M",
            "AY": "AA",
            "B": "K",
            "CH": "F",
            "D": "W",
            "DH": "EH",
            "EH": "W",
            "ER": "M",
            "EY": "W",
            "F": "F",
            "G": "W",
            "H": "W",
            "HH": "W",
            "IH": "W",
            "IY": "W",
            "JH": "M",
            "K": "W",
            "L": "EH",
            "M": "K",
            "N": "K",
            "NG": "W",
            "OW": "Rest",
            "OY": "Rest",
            "P": "K",
            "R": "EH",
            "rest": "L",
            "S": "F",
            "SH": "W",
            "T": "AA",
            "TH": "W",
            "UH": "UW",
            "UW": "UW",
            "V": "F",
            "W": "M",
            "Y": "W",
            "Z": "OW",
            "ZH": "OW"
        },
    }


    def run(self, context):
        from .selector import MorphGroup, setMorphs, pinProp
        scn = context.scene
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No armature found")
        self.phonemes = self.phonemeConverters[self.phonemeSet]
        self.clearAnimation(rig)
        if self.atFrameOne:
            frame0 = 0
        else:
            frame0 = scn.frame_current-1
        frames = self.readMoho()
        if self.useRelax:
            frames = self.improveMoho(frames)
            if self.useUpdateLimits:
                self.updateLimits(rig)
        mgrp = MorphGroup()
        mgrp.init("Visemes", "", "", "DazVisemes")
        for frame,moho,value in frames:
            if moho == "rest":
                setMorphs(0.0, rig, mgrp, scn, frame, True)
            else:
                prop = self.getMohoKey(moho, rig)
                pinProp(rig, scn, prop, mgrp, frame+frame0, value=value)
        self.nameAnimation(rig)
        print("Moho file %s loaded" % self.filepath)


    def updateLimits(self, rig):
        from .driver import getPropMinMax, setPropMinMax
        for moho in self.openVowels:
            prop = self.getMohoKey(moho, rig)
            min,max,default,ovr = getPropMinMax(rig, prop, True)
            if max < self.emphasis:
                setPropMinMax(rig, prop, default, min, self.emphasis, True)
            final = finalProp(prop)
            if final in rig.data.keys():
                min,max,default,ovr = getPropMinMax(rig.data, final, False)
                if max < self.emphasis:
                    setPropMinMax(rig.data, final, default, min, self.emphasis, False)


    def readMoho(self):
        from .fileutils import safeOpen
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


    def getMohoKey(self, moho, rig):
        if moho in self.phonemes.keys():
            daz = self.phonemes[moho]
            for item in rig.DazVisemes:
                if item.text == daz:
                    prop = item.name
                    if prop in rig.keys():
                        return prop
            msg = "Missing viseme: %s (%s)\n" % (daz, moho)
        else:
            msg = ("Missing viseme: %s\n" % moho +
                   "Choose different phoneme set")
        raise DazError(msg)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_LoadMoho,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
