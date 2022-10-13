# Copyright (c) 2016-2022, Thomas Larsson
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

def clearErrorMessage():
    LS.theMessage = ""
    LS.theErrorLines = []


class ErrorOperator(bpy.types.Operator):
    bl_idname = "daz.error"
    bl_label = "Daz Importer"

    def execute(self, context):
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        LS.theErrorLines = LS.theMessage.split('\n')
        maxlen = len(self.bl_label)
        for line in LS.theErrorLines:
            if len(line) > maxlen:
                maxlen = len(line)
        width = 40+5*maxlen
        height = 20+5*len(LS.theErrorLines)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width)

    def draw(self, context):
        for line in LS.theErrorLines:
            self.layout.label(text=line)


def invokeErrorMessage(value, warning=False):
    if warning:
        LS.theMessage = "WARNING:\n" + value
    else:
        LS.theMessage = "ERROR:\n" + value
    if GS.silentMode:
        print(LS.theMessage)
    else:
        bpy.ops.daz.error('INVOKE_DEFAULT')


class DazError(Exception):

    def __init__(self, value, warning=False):
        invokeErrorMessage(value, warning)

    def __str__(self):
        return repr(LS.theMessage)


def reportError(msg, instances={}, warnPaths=False, trigger=(2,3), force=False):
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
    fp.write(LS.theMessage)

    try:
        if warning:
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
        print(LS.theMessage)
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
    for string in LS.theTrace:
        fp.write("  %s\n" % string)

    fp.write("\nASSETS:")
    refs = list(LS.theAssets.keys())
    refs.sort()
    for ref in refs:
        asset = LS.theAssets[ref]
        asset.errorWrite(ref, fp)

    fp.write("\n\nOTHER ASSETS:\n")
    refs = list(LS.theOtherAssets.keys())
    refs.sort()
    for ref in refs:
        fp.write('"%s"\n    %s\n\n' % (ref, LS.theOtherAssets[ref]))

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
    def execute(self, context):
        self.prequel(context)
        try:
            self.run(context)
        except DazError:
            handleDazError(context)
        except KeyboardInterrupt:
            LS.theMessage = "Keyboard interrupt"
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
        from .utils import getSelectedObjects
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
        from .utils import setActiveObject
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


class DazPropsOperator(DazOperator):
    dialogWidth = 300
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=self.dialogWidth)

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

class IsMeshArmature:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])

