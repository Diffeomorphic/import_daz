# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from ..selector import Selector
from .preset import *

#-------------------------------------------------------------
#   Save morph presets
#-------------------------------------------------------------

class MorphPreset(Preset):
    extension = ".dsf"

    presentation : EnumProperty(
        items = [('Shape', "Shape", "Shape"),
                 ('Pose', "Pose", "Pose"),
                 ('Corrective', "Corrective", "Corrective")],
        name = "Presentation",
        default = 'Shape')

    region : StringProperty(
        name = "Region",
        default = "Actor")

    def drawPresentation(self):
        self.layout.prop(self, "presentation")
        self.layout.prop(self, "region")

    def saveFile(self, context, filepath, ob, skey, mname, first):
        struct,filepath = self.makeDazStruct("modifier", filepath)
        modlib = struct["modifier_library"] = []
        mstruct = self.addLibModifier(ob, skey, mname, first)
        modlib.append(mstruct)
        modlist = []
        struct["scene"] = {"modifiers" : modlist}
        mstruct = {
            "id" : "%s-1" % mname,
            "url" : "#%s" % normalizeUrl(mname)}
        modlist.append(mstruct)
        saveJson(struct, filepath, binary=self.useCompress, strict=False)
        print("Morph preset %s saved" % filepath)


    def addLibModifier(self, ob, skey, mname, first):
        struct = OrderedDict()
        struct["id"] = mname
        struct["name"] = mname
        if ob.parent:
            struct["parent"] = normalizeUrl(ob.parent.DazUrl)
        struct["presentation"] = {
            "type" : "Modifier/%s" % self.presentation,
            "label" : mname,
            "description" : "",
            "icon_large" : "",
            "colors" : [ [ 0.1607843, 0.1607843, 0.1607843 ], [ 0.4980392, 0, 0 ] ]
        }
        struct["channel"] = {
            "id" : "value",
            "type" : "float",
            "name" : mname,
            "label" : mname,
            "auto_follow" : True,
            "value" : 0,
            "min" : 0,
            "max" : 1,
            "clamped" : True,
            "display_as_percent" : True,
            "step_size" : 0.01
        }
        self.addGroup(struct)
        if first:
            self.addFormulas(ob, skey, mname, struct)
        nverts = len(ob.data.vertices)
        mstruct = struct["morph"] = OrderedDict()
        mstruct["vertex_count"] = nverts
        dstruct = mstruct["deltas"] = OrderedDict()
        deltas = self.getDeltas(ob, skey)
        dstruct["count"] = len(deltas)
        dstruct["values"] = deltas
        return struct


    def addGroup(self, struct):
        if self.presentation == "Pose":
            struct["group"] = "/Pose Controls"
        elif self.presentation == "Shape":
            if self.region:
                struct["region"] = self.region
            struct["group"] = GS.author

#-------------------------------------------------------------
#   Save morph preset
#-------------------------------------------------------------

class DAZ_OT_SaveMorphPresets(DazOperator, MorphPreset, Selector, IsMesh):
    bl_idname = "daz.save_morph_presets"
    bl_label = "Save Morph Presets"
    bl_description = "Save selected shapekeys as a morph preset"

    subdir = "Morphs"

    def draw(self, context):
        self.drawFiles(context)
        self.drawPresentation()
        self.layout.prop(self, "useCompress")
        Selector.draw(self, context)


    def addFormulas(self, ob, skey, mname, struct):
        pass


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
        self.reldir = self.getDefaultDirectory(ob)
        return Selector.invoke(self, context, event)


    def run(self, context):
        ob = context.object
        folder = self.getFullDirectory(context.scene)
        for item in self.getSelectedItems():
            filepath = "%s/%s.duf" % (folder, item.name)
            skey = ob.data.shape_keys.key_blocks[item.name]
            mname = bpy.path.clean_name(item.name)
            self.saveFile(context, filepath, ob, skey, mname, True)


    def getDeltas(self, ob, skey):
        factor = 1/GS.scale
        eps = 0.001 # 0.01 mm
        diffs = [factor*(skey.data[vn].co - v.co) for vn,v in enumerate(ob.data.vertices)]
        return [[vn, delta[0], delta[2], -delta[1]] for vn,delta in enumerate(diffs) if delta.length > eps]

#-------------------------------------------------------------
#   Save figure preset
#-------------------------------------------------------------

class DAZ_OT_SaveDazFigure(DazPropsOperator, MorphPreset, DufFile, IsMeshArmature):
    bl_idname = "daz.save_daz_figure"
    bl_label = "Save DAZ Figure"
    bl_description = "Save active mesh as a DAZ figure relative to the other mesh"

    subdir = "Morphs"
    dialogWidth = 600

    morphname : StringProperty(
        name = "Morph Name",
        description = "Name of the morph")

    def draw(self, context):
        self.layout.prop(self, "morphname")
        self.layout.separator()
        self.layout.prop(context.scene, "DazPreferredRoot")
        self.layout.prop(self, "reldir")
        self.layout.prop(self, "useCompress")


    def invoke(self, context, event):
        ob = context.object
        self.morphname = ob.name
        self.setDefaultFilepath(ob, context.scene, ob.name)
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        trg = getRigFromContext(context, strict=False)
        self.rootpath = context.scene.DazPreferredRoot
        self.filename = "%s%s" % (self.morphname, self.extension)
        self.saveFiles(context, trg, context.view_layer.objects, 2)


    def getObjectPath(self, ob):
        folder = self.getDefaultDirectory(ob)
        return canonicalPath("%s/%s/%s" % (self.rootpath, folder, self.filename))


    def saveFiles(self, context, trg, objects, first):
        ref = self.getMatchingObject(objects, trg)
        if ref is None:
            return
        elif trg.type == 'ARMATURE':
            first = max(0,first-1)
            urls = []
            for child in trg.children:
                self.saveFiles(context, child, ref.children, first)
                urls.append(child.DazUrl)
            if first:
                rigs = [ob for ob in ref.children if ob.type == 'ARMATURE' and ob.DazUrl not in urls]
                meshes = [ob for ob in trg.children if ob.type == 'MESH']
                for rig in rigs:
                    for ob in rig.children:
                        trg = self.getMatchingObject(meshes, ob)
                        if trg:
                            filepath = self.getObjectPath(trg)
                            self.saveFile(context, filepath, ob, trg, self.morphname, False)
        elif trg.type == 'MESH':
            filepath = self.getObjectPath(trg)
            self.saveFile(context, filepath, ref, trg, self.morphname, first)


    def getMatchingObject(self, objects, trg):
        for ob in objects:
            if ob != trg and ob.DazUrl == trg.DazUrl:
                return ob
        return None


    def getDeltas(self, ob, trg):
        factor = 1/GS.scale
        eps = 0.001 # 0.01 mm
        diffs = [factor*(tv.co - v.co) for tv,v in zip(trg.data.vertices, ob.data.vertices)]
        return [[vn, delta[0], delta[2], -delta[1]] for vn,delta in enumerate(diffs) if delta.length > eps]


    def addFormulas(self, ob, trg, mname, struct):
        rig = trg.parent
        rig0 = ob.parent
        if rig is None or rig0 is None:
            print("Lacking rig")
            return
        elif rig == rig0:
            print("Same armature")
            return

        def addFormula(bname, path, char, channel, comp, mname, offs):
            if abs(offs) < 1e-3:
                return None
            return {
                "output" : "%s:%s#%s?%s/%s" % (bname, path, bname, channel, comp),
                "operations" : [
                    { "op" : "push", "url" : "%s:#%s?value" % (char, mname) },
                    { "op" : "push", "val" : offs },
                    { "op" : "mult" }
                ]
            }

        path,char = rig.DazUrl.split("#")
        path = quote(path)
        char = quote(char)
        formulas = []
        for bone0 in rig0.data.bones:
            bone = rig.data.bones.get(bone0.name)
            if bone is None:
                continue
            offset = b2d(bone.head_local - bone0.head_local)
            for n,comp in enumerate(["x", "y", "z"]):
                formula = addFormula(bone.name, path, char, "center_point", comp, mname, offset[n])
                if formula:
                    formulas.append(formula)
            offset = b2d(bone.tail_local - bone0.tail_local)
            for n,comp in enumerate(["x", "y", "z"]):
                formula = addFormula(bone.name, path, char, "end_point", comp, mname, offset[n])
                if formula:
                    formulas.append(formula)
        if formulas:
            struct["formulas"] = formulas

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_SaveMorphPresets,
    DAZ_OT_SaveDazFigure,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
