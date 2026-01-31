# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from .error import *
from .utils import *
from .selector import Selector
from .morphing import MS

#------------------------------------------------------------------------
#   General Morph selector
#------------------------------------------------------------------------

theMorphEnums = []
theCatEnums = []

def getMorphEnums(scn, context):
    return theMorphEnums

def getCatEnums(scn, context):
    return theCatEnums

class GeneralMorphSelector(Selector):
    morphset : EnumProperty(
        items = getMorphEnums,
        name = "Type")

    category : EnumProperty(
        items = getCatEnums,
        name = "Category")

    def selectCondition(self, item):
        if (self.morphset == "Custom" or
            (self.morphset == "All" and self.category != "All")):
            return (item.name in self.catnames[self.category])
        else:
            return (item.name in self.morphnames[self.morphset])

    def draw(self, context):
        self.layout.prop(self, "morphset")
        if self.morphset in ["All", "Custom"]:
            self.layout.prop(self, "category")
        self.drawMore()
        Selector.draw(self, context)

    def drawMore(self):
        pass

    def getKeys(self, rig, ob):
        if rig is None:
            return []
        from .morphing import getMorphList
        morphs = getMorphList(rig, self.morphset, sets=MS.Standards)
        keys = [(item.name, item.text, "All") for item in morphs]
        for cat in dazRna(rig).DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


    def specialKey(self, key):
        return key.startswith(("Daz", "daz_importer", "Adjust"))


    def invoke(self, context, event):
        global theMorphEnums, theCatEnums
        rig = self.rig = getRigFromContext(context)
        theMorphEnums = [("All", "All", "All")]
        theCatEnums = [("All", "All", "All")]
        self.morphset = "All"
        self.morphnames = {}
        self.morphnames["All"] = []
        for morphset in MS.Standards:
            theMorphEnums.append((morphset, morphset, morphset))
            if rig:
                pgs = getattr(dazRna(rig), "Daz%s" % morphset)
                self.morphnames["All"] += list(pgs.keys())
                self.morphnames[morphset] = pgs.keys()
        theMorphEnums.append(("Custom", "Custom", "Custom"))
        self.catnames = {}
        self.catnames["All"] = []
        if rig:
            for cat in dazRna(rig).DazMorphCats:
                theCatEnums.append((cat.name, cat.name, cat.name))
                self.morphnames["All"] += list(cat.morphs.keys())
                self.catnames["All"] += list(cat.morphs.keys())
                self.catnames[cat.name] = cat.morphs.keys()
        return Selector.invoke(self, context, event)

#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

class DAZ_OT_UpdateSliderLimits(DazOperator, GeneralMorphSelector, IsMeshArmature):
    bl_idname = "daz.update_slider_limits"
    bl_label = "Update Slider Limits"
    bl_description = "Update selected slider min and max values.\nAll slider limits are selected when called from script"
    bl_options = {'UNDO'}

    min : FloatProperty(
        name = "Min",
        description = "Minimum slider value",
        default = 0.0)

    max : FloatProperty(
        name = "Max",
        description = "Maximum slider value",
        default = 1.0)

    useSliders : BoolProperty(
        name = "Sliders",
        description = "Update min and max for slider values",
        default = True)

    useFinal : BoolProperty(
        name = "Final",
        description = "Update min and max for final values",
        default = True)

    useShapekeys : BoolProperty(
        name = "Shapekeys",
        description = "Update min and max for shapekeys",
        default = True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "min")
        row.prop(self, "max")
        row = self.layout.row()
        row.prop(self, "useSliders")
        row.prop(self, "useFinal")
        row.prop(self, "useShapekeys")
        GeneralMorphSelector.draw(self, context)


    def run(self, context):
        from .uilist import updateScrollbars
        ob = context.object
        rig = getRigFromContext(context)
        self.props = [prop.lower() for prop in self.getSelectedValues()]
        if rig:
            if not self.props:
                self.props = [key.lower() for key in rig.keys() if not self.specialKey(key)]
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)
        updateScrollbars(context)


    def updatePropLimits(self, rig, context):
        from .driver import setFloatProp
        if self.useShapekeys:
            for ob in getShapeChildren(rig):
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in self.props:
                        skey.slider_min = self.min
                        skey.slider_max = self.max
                        skey.driver_remove("slider_min")
                        skey.driver_remove("slider_max")
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in self.props and isinstance(rig[raw], float):
                if self.useSliders:
                    setFloatProp(rig, raw, rig[raw], self.min, self.max, True)
                if self.useFinal:
                    final = finalProp(raw)
                    if final in amt.keys():
                        setFloatProp(amt, final, amt[final], self.min, self.max, False)
        updateRigDrivers(context, rig)
        print("Slider limits updated")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_UpdateSliderLimits,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
