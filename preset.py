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
from .fileutils import DazExporter
from .selector import Selector, getRigFromObject

#-------------------------------------------------------------
#   Save morph presets
#-------------------------------------------------------------

class DAZ_OT_SaveMorphPreset(DazOperator, DazExporter, Selector, IsMesh):
    bl_idname = "daz.save_morph_preset"
    bl_label = "Save Morph Preset"
    bl_description = "Save selected shapekeys as a morph preset"

    directory: StringProperty(
        name = "Directory",
        description = "Directory")

    presentation: EnumProperty(
        items = [("Modifier/Pose", "Pose Control", "Pose control"),
                 ("Modifier/Shape", "Shape", "Shape")],
        name = "Presentation",
        description = "Presentation",
        default = "Modifier/Pose")

    def draw(self, context):
        self.layout.prop(self, "directory")
        Selector.draw(self, context)
        #DazExporter.draw(self, context)
        #self.layout.prop(self, "presentation")

    def getKeys(self, rig, ob):
        keys = []
        for skey in ob.data.shape_keys.key_blocks[1:]:
            keys.append((skey.name, skey.name, "All"))
        return keys

    def invoke(self, context, event):
        ob = context.object
        if ob.data.shape_keys is None:
            msg = "Object %s has no shapekeys" % ob.name
            invokeErrorMessage(msg)
            return {'CANCELLED'}
        self.directory = context.scene.DazMorphPath
        return Selector.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        from .asset import normalizeUrl
        ob = context.object
        rig = ob.parent
        parent = None
        if rig:
            parent = normalizeUrl(rig.DazUrl)
        for item in self.getSelectedItems():
            filename = ("%s.duf" % item.name).replace(" ", "_")
            filepath = os.path.join(self.directory, filename)
            struct,filepath = self.makeDazStruct("modifier", filepath)
            modlib = struct["modifier_library"] = []
            skey = ob.data.shape_keys.key_blocks[item.name]
            mstruct = self.addLibModifier(skey, ob, parent)
            modlib.append(mstruct)
            modlist = []
            struct["scene"] = {"modifiers" : modlist}
            mname = item.name.replace(" ", "_")
            mstruct = {"id" : "%s-1" % mname, "url" : normalizeUrl(mname)}
            modlist.append(mstruct)
            saveJson(struct, filepath, binary=self.useCompress)
            print("Morph preset %s saved" % filepath)


    def addLibModifier(self, skey, ob, parent):
        from collections import OrderedDict
        mname = skey.name.replace(" ", "_")
        struct = OrderedDict()
        struct["id"] = mname
        struct["name"] = mname
        if parent:
            struct["parent"] = parent
        struct["presentation"] = {
            "type" : self.presentation,
            "label" : skey.name,
            "description" : "",
            "icon_large" : "",
            "colors" : [ [ 0.1607843, 0.1607843, 0.1607843 ], [ 0.4980392, 0, 0 ] ]
        }
        struct["channel"] = {
            "id" : "value",
            "type" : "float",
            "name" : mname,
            "label" : skey.name,
            "auto_follow" : True,
            "value" : 0,
            "min" : 0,
            "max" : 1,
            "clamped" : True,
            "display_as_percent" : True,
            "step_size" : 0.01
        }
        if self.presentation == "Modifier/Pose":
            struct["group"] = "/Pose Controls"
        elif self.presentation == "Modifier/Shape":
            struct["region"] = "Actor"
            struct["group"] = "/Full Body/People"
        nverts = len(ob.data.vertices)
        mstruct = struct["morph"] = OrderedDict()
        mstruct["vertex_count"] = nverts
        dstruct = mstruct["deltas"] = OrderedDict()
        factor = 1/ob.DazScale
        eps = 0.001 # 0.01 mm
        diffs = [factor*(skey.data[vn].co - v.co) for vn,v in enumerate(ob.data.vertices)]
        deltas = [[vn, delta[0], delta[2], -delta[1]] for vn,delta in enumerate(diffs) if delta.length > eps]
        dstruct["count"] = len(deltas)
        dstruct["values"] = deltas
        return struct

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SaveMorphPreset,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
