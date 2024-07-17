# Copyright (c) 2016-2024, Thomas Larsson
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


def invokeErrorMessage(value, warning=False):
    from .buildnumber import BUILD
    if warning:
        LS.message = value
    else:
        LS.message = "ERROR (4.2.0.%04d):\n%s" % (BUILD, value)
    if GS.silentMode:
        print(LS.message)
    elif ES.easy:
        ES.message += "%s\n" % LS.message
        LS.message = ""
    else:
        bpy.ops.daz.error('INVOKE_DEFAULT')


class DazError(Exception):

    def __init__(self, value, warning=False):
        invokeErrorMessage(value, warning)

    def __str__(self):
        return repr(LS.message)


def addItem(pgs):
    try:
        return pgs.add()
    except TypeError as err:
        raise DazError("Loading morphs caused a type error:\n%s\nMorphs can not be loaded to linked characters." % err)


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
        msg += ("\nFor details see\n'%s'" % getErrorPath())
        raise DazError(msg)
    return None


def getErrorPath():
    import os
    return os.path.realpath(os.path.expanduser(GS.errorPath))


def handleDazError(context, warning=False, dump=False):
    global theUseDumpErrors

    if not (dump or theUseDumpErrors):
        return
    theUseDumpErrors = False

    filepath = getErrorPath()
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
    filepath = getErrorPath()
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

    fp.write("\nABSOLUTE PATHS:\n")
    for lpath,folders in GS.absPaths.items():
        fp.write('"%s":\n' % lpath)
        for folder in folders:
            fp.write('    "%s"\n' % folder)

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
    def execute(self, context):
        self.prequel(context)
        self.warnings = ""
        try:
            self.run(context)
            if self.warnings:
                print(self.warnings)
                raise DazError(self.warnings, warning=True)
        except DazError:
            handleDazError(context)
        except KeyboardInterrupt:
            LS.message = "Keyboard interrupt"
            bpy.ops.daz.error('INVOKE_DEFAULT')
        finally:
            self.sequel(context)
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
        self.warnings += msg


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
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=self.dialogWidth)

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


