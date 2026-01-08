# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from .settings import GS, LS
from .utils import *

def clearErrorMessage():
    LS.message = ""
    LS.errorLines = []


class ErrorOperator(bpy.types.Operator):
    bl_idname = "daz.error"
    bl_label = "Daz Importer"

    def execute(self, context):
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        LS.errorLines = LS.message.split('\n')
        maxlen = len(self.bl_label)
        for line in LS.errorLines:
            if len(line) > maxlen:
                maxlen = len(line)
        width = 40+5*maxlen
        height = 20+5*len(LS.errorLines)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width)

    def draw(self, context):
        for line in LS.errorLines:
            self.layout.label(text=line)


def invokeErrorMessage(value, warning=False, useDialog=False):
    from .buildnumber import BUILD
    LS.message = value
    if not warning:
        LS.error = True
    if GS.silentMode:
        print(LS.message)
    elif ES.easy:
        ES.message += "%s\n" % LS.message
        if not warning:
            ES.error = True
        LS.error = False
        LS.message = ""
    elif not warning:
        LS.message = "ERROR (5.1.0.%04d):\n%s" % (BUILD, LS.message)
        bpy.ops.daz.error('INVOKE_DEFAULT')
    elif useDialog:
        bpy.ops.daz.error('INVOKE_DEFAULT')


class DazError(Exception):
    def __init__(self, value, warning=False, useDialog=False):
        invokeErrorMessage(value, warning, useDialog)

    def __str__(self):
        return repr(LS.message)


def reportError(msg, instances={}, warnPaths=False, trigger=(2,5), force=False):
    global theUseDumpErrors
    trigWarning,trigError = trigger
    if GS.verbosity >= trigWarning or force:
        print(msg)
    if GS.verbosity >= trigError or force:
        theUseDumpErrors = True
        if warnPaths:
            msg += ("\nHave all DAZ library paths been set up correctly?\n" +
                    "See https://diffeomorphic.blogspot.se/p/setting-up-daz-library-paths.html         ")
        msg += ("\nFor details see\n'%s'" % GS.getErrorPath())
        raise DazError(msg)
    return None


def handleDazError(context, warning=False, dump=False):
    global theUseDumpErrors

    if not (dump or theUseDumpErrors):
        return
    theUseDumpErrors = False

    filepath = GS.getErrorPath()
    try:
        fp = open(filepath, "w", encoding="utf-8-sig")
    except:
        print("Could not write to %s" % filepath)
        return
    fp.write(LS.message)

    try:
        if False and warning:
            string = getMissingAssets()
            fp.write(string)
            print(string)
        else:
            printTraceBack(context, fp)
    except:
        pass
    finally:
        fp.write("\n")
        fp.close()
        print(LS.message)
        LS.reset()


def dumpErrors(context):
    filepath = GS.getErrorPath()
    with open(filepath, "w", encoding="utf-8-sig") as fp:
        printTraceBack(context, fp)


def getMissingAssets():
    if not LS.missingAssets:
        return ""
    string = "\nMISSING ASSETS:\n"
    for ref in LS.missingAssets.keys():
        string += ("  %s\n" % ref)
    return string


def printTraceBack(context, fp):
    import sys, traceback
    type,value,tb = sys.exc_info()
    fp.write("\n\nTRACEBACK:\n")
    traceback.print_tb(tb, 30, fp)

    from .node import Node

    fp.write("\n\nFILES VISITED:\n")
    for string in LS.trace:
        fp.write("  %s\n" % string)

    fp.write("\nASSETS:")
    refs = list(LS.assets.keys())
    refs.sort()
    for ref in refs:
        asset = LS.assets[ref]
        asset.errorWrite(ref, fp)

    fp.write("\n\nOTHER ASSETS:\n")
    refs = list(LS.otherAssets.keys())
    refs.sort()
    for ref in refs:
        fp.write('"%s"\n    %s\n\n' % (ref, LS.otherAssets[ref]))

    fp.write("\nDAZ ROOT PATHS:\n")
    for n, path in enumerate(GS.rootPaths):
        fp.write('%d:   "%s"\n' % (n, path))

    string = getMissingAssets()
    fp.write(string)

    fp.write("\nSETTINGS:\n")
    settings = []
    scn = bpy.context.scene
    for attr in dir(scn):
        if attr[0:3] == "Daz" and hasattr(scn, attr):
            value = getattr(scn, attr)
            if (isinstance(value, int) or
                isinstance(value, float) or
                isinstance(value, str) or
                isinstance(value, bool)):
                settings.append((attr, value))
    settings.sort()
    for attr,value in settings:
        if isinstance(value, str):
            value = ('"%s"' % value)
        fp.write('%25s:    %s\n' % (attr, value))


theUseDumpErrors = False

#-------------------------------------------------------------
#   Execute
#-------------------------------------------------------------

class DazOperator(bpy.types.Operator):
    useReport = True
    invoked = False

    def execute(self, context):
        self.prequel(context)
        self.warnings = ""
        try:
            self.run(context)
            if self.useReport:
                self.report({'INFO'}, "%s finished" % self.bl_label)
        except DazError:
            if LS.error:
                msg = "%s failed" % self.bl_label
                self.report({'INFO'}, msg)
                handleDazError(context)
            elif self.warnings and not ES.easy:
                msg = "\n%s finished with warnings.\nSee terminal window for details" % self.bl_label
                self.report({'WARNING'}, msg)
                print(self.warnings)
        except KeyboardInterrupt:
            LS.message = "Keyboard interrupt"
            bpy.ops.daz.error('INVOKE_DEFAULT')
        finally:
            self.sequel(context)
            self.invoked = False
        return{'FINISHED'}


    def prequel(self, context):
        self.storeState(context)
        LS.returnValue = {}
        clearErrorMessage()


    def sequel(self, context):
        wm = bpy.context.window_manager
        wm.progress_update(100)
        wm.progress_end()
        self.restoreState(context)


    def storeState(self, context):
        self.mode = None
        self.activeObject = context.object
        self.selectedObjects = [ob.name for ob in getSelectedObjects(context)]
        if context.object:
            self.mode = context.object.mode
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass


    def restoreState(self, context):
        try:
            if self.activeObject:
                setActiveObject(context, self.activeObject)
            for obname in self.selectedObjects:
                if obname in bpy.data.objects.keys():
                    bpy.data.objects[obname].select_set(True)
            if self.mode:
                bpy.ops.object.mode_set(mode=self.mode)
        except RuntimeError:
            pass


    def storeRig(self, rig):
        self.rvalues = {}
        if rig:
            rig.data.pose_position = 'REST'
            for key,value in rig.items():
                self.rvalues[key] = value
                setTypedPropValue(rig, key, value, 0)


    def restoreRig(self, rig):
        if rig:
            rig.data.pose_position = 'POSE'
            for key,value in self.rvalues.items():
                setTypedPropValue(rig, key, value, value)
            updateDrivers(rig)


    def storeMesh(self, ob):
        self.svalues = {}
        self.mvalues = {}
        for key,value in ob.items():
            self.mvalues[key] = value
            setTypedPropValue(ob, key, value, 0)
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks:
                self.svalues[skey.name] = skey.value
                skey.value = 0.0


    def restoreMesh(self, ob):
        skeys = self.mesh.data.shape_keys
        for key,value in self.mvalues.items():
            setTypedPropValue(ob, key, value, value)
        updateDrivers(ob)
        if skeys:
            for key,value in self.svalues.items():
                skey = skeys.key_blocks[key]
                skey.value = value
            updateDrivers(skeys)


    def addWarning(self, msg):
        if self.warnings:
            self.warnings += "\n"
        else:
            self.warnings = "\n%s finished with warnings.\n" % self.bl_label
        self.warnings += msg


    def raiseWarning(self, msg, useDialog=False):
        if msg:
            self.addWarning(msg)
            raise DazError(msg, warning=True, useDialog=useDialog)


def setTypedPropValue(ob, key, value, newvalue):
    if isinstance(value, float):
        ob[key] = float(newvalue)
    elif isinstance(value, bool):
        ob[key] = bool(newvalue)
    elif isinstance(value, int):
        ob[key] = int(newvalue)


class DazPropsOperator(DazOperator):
    dialogWidth = 300
    def invoke(self, context, event):
        self.invoked = True
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=self.dialogWidth)

#-------------------------------------------------------------
#   CollectionShower
#-------------------------------------------------------------

class CollectionShower:
    def storeState(self, context):
        def showLayerColls(layer):
            for child in layer.children:
                showLayerColls(child)
            self.layerColls.append((layer, layer.exclude))
            layer.exclude = False

        self.layerColls = []
        showLayerColls(context.view_layer.layer_collection)
        self.obhides = []
        for ob in context.view_layer.objects:
            self.obhides.append((ob, ob.hide_get(), ob.hide_viewport))
            ob.hide_set(False)
        DazOperator.storeState(self, context)


    def restoreState(self, context):
        DazOperator.restoreState(self, context)
        for ob,hide,hideview in self.obhides:
            try:
                ob.hide_set(hide)
                ob.hide_viewport = hideview
            except ReferenceError:
                pass
        for layer,exclude in reversed(self.layerColls):
            layer.exclude = exclude

#-------------------------------------------------------------
#
#-------------------------------------------------------------

class IsObject:
    @classmethod
    def poll(self, context):
        return context.object

class IsMesh:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

class IsArmature:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

class IsCurves:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'CURVES')

class IsMeshArmature:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])

class IsShape:
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


