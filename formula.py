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

import math
from mathutils import *
from .error import DazError, reportError
from .utils import *

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class Formula:

    def __init__(self):
        self.formulas = []
        self.built = False


    def parse(self, struct):
        if (LS.useFormulas and
            "formulas" in struct.keys()):
            self.formulas = struct["formulas"]


    def build(self, context, inst):
        return
        from .modifier import Morph
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if asset is None:
                continue
            if key == "value" and isinstance(asset, Morph):
                asset.build(context, inst, value)


    def buildBakedFormulas(self, context, inst):
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if key == "value":
                buildBakedMorph(inst, ref, value)


    def postbuild(self, context, inst):
        from .modifier import Morph
        from .node import Node
        if not LS.useMorphOnly:
            return
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if isinstance(asset, Morph):
                pass
            elif isinstance(asset, Node):
                inst = asset.getInstance(ref, self.caller)
                if inst:
                    inst.formulate(key, value)


    def computeFormula(self, formula):
        if len(formula["operations"]) != 3:
            return None,None,0
        stack = []
        for struct in formula["operations"]:
            op = struct["op"]
            if op == "push":
                if "url" in struct.keys():
                    ref,key = self.getRefKey(struct["url"])
                    if ref is None or key != "value":
                        return None,None,0
                    asset = self.getAsset(ref)
                    if not hasattr(asset, "value"):
                        return None,None,0
                    stack.append(asset.value)
                elif "val" in struct.keys():
                    data = struct["val"]
                    stack.append(data)
                else:
                    reportError("Cannot push %s" % struct.keys(), trigger=(1,5), force=True)
            elif op == "mult":
                x = stack[-2]*stack[-1]
                stack = stack[:-2]
                stack.append(x)
            else:
                reportError("Unknown formula %s %s" % (op, struct.items()), trigger=(1,5), force=True)

        if len(stack) == 1:
            ref,key = self.getRefKey(formula["output"])
            return ref,key,stack[0]
        else:
            raise DazError("Stack error %s" % stack)
            return None,None,0


    def evalFormulas(self, rig, mesh, force):
        success = False
        exprs = {}
        rig2 = rig
        for formula in self.formulas:
            rig2 = self.evalFormula(formula, exprs, rig, mesh, force)
        if not exprs and GS.verbosity > 3 and self.formulas:
            print("Could not parse formulas", self.formulas)
        return exprs,rig2

    Genesis = [
        "Genesis",
        "Genesis2Female",
        "Genesis2Male",
        "Genesis3Female",
        "Genesis3Male",
        "Genesis8Female",
        "Genesis8Male",
        "Genesis8_1Female",
        "Genesis8_1Male",
        "Genesis9",
    ]

    def evalFormula(self, formula, exprs, rig, mesh, force):
        from .bone import getMappedBone, Bone
        from .modifier import ChannelAsset
        output,channel,fileref,url = self.getPropAndType(formula["output"], rig)
        pb = None
        rig2 = rig
        if channel == "value":
            if mesh is None and rig is None and force:
                if GS.verbosity > 2:
                    print("Cannot drive properties", output)
                    print("  ", unquote(formula["output"]))
                return rig2
        elif output in self.Genesis:
            output = "RIG"
        elif rig:
            output1 = getMappedBone(output, rig, mesh)
            if output1 and output1 in rig.pose.bones.keys():
                output = output1
            elif output1 == "RIG":
                output = "RIG"
            else:
                asset = self.getAsset(url)
                if isinstance(asset, Bone) and asset.instances:
                    inst = list(asset.instances.values())[0]
                    rig2 = inst.figure.rna
                    pb = inst.rna
                    #LS.otherRigBones["%s => %s/%s" % (rig.name, rig2.name, pb.name)] = True
                    reportError("Found bone in other rig: %s/%s (%s)" % (rig2.name, pb.name, output), trigger=(3,5))
                    #return False
                else:
                    reportError("Missing bone (evalFormula): %s" % output)
                    return rig

        path,idx,default = self.parseChannel(channel)
        expr = setFormulaExpr(exprs, output, path, channel, idx, fileref)
        if "stage" in formula.keys():
            self.evalStage(formula, expr, rig, mesh)
        else:
            self.evalOperations(formula, expr, rig, mesh)
        return rig2


    def evalStage(self, formula, expr, rig, mesh):
        from .bone import getMappedBone
        ignore = ["JCMs On",
                  "BaseFlexions",
                  "body_basejointcorrectives",
                  "body_ctrl_FlexionAutoStrength",
                  "facs_ctrl_FACSDetailStrength",]
        if formula["stage"] == "mult":
            opers = formula["operations"]
            key,type,path,comp = self.evalUrl(opers[0], rig)
            if key in ignore:
                pass
            elif type == "value":
                if expr.prop is None:
                    expr.prop = ExprTarget(key, type, comp)
                expr.prop.mults.append(key)
            elif comp >= 0 and rig:
                bname = getMappedBone(key, rig, mesh)
                if bname in rig.pose.bones.keys():
                    if expr.bone is None:
                        expr.bone = ExprTarget(bname, type, comp)
                    expr.bone.mults.append((bname, path, comp))


    def evalOperations(self, formula, expr, rig, mesh):
        from .bone import getMappedBone
        opers = formula["operations"]
        prop,type,path,comp = self.evalUrl(opers[0], rig)
        if type == "value":
            if expr.prop is None:
                target = expr.prop = ExprTarget(prop, type, -1)
            else:
                target = expr.prop2 = ExprTarget(prop, type, -1)
        else:
            bname = getMappedBone(prop, rig, mesh)
            if expr.bone is None:
                target = expr.bone = ExprTarget(bname, type, comp)
            else:
                target = expr.bone2 = ExprTarget(bname, type, comp)
        expr.path = path
        self.evalMainOper(opers, target)


    def evalUrl(self, oper, rig):
        if "url" not in oper.keys():
            print(oper)
            raise RuntimeError("BUG: Operation without URL")
        prop,type,_fileref,_url = self.getPropAndType(oper["url"], rig)
        path,comp,default = self.parseChannel(type)
        return prop,type,path,comp


    def getPropAndType(self, string, rig):
        before,type = string.rsplit("?",1)
        bname,url = before.split(":",1)
        fileref,prop = url.split("#")
        bname = unquote(bname)
        prop = unquote(prop)
        #if type == "value" and rig and bname in rig.data.bones.keys():
        #    prop = "%s:%s" % (bname, prop)
        return prop,type,unquote(fileref),url


    def evalMainOper(self, opers, target):
        if len(opers) == 1:
            target.factor = 1
            return
        oper = opers[-1]
        op = oper["op"]
        if op == "mult":
            target.factor = opers[1]["val"]
        elif op == "spline_tcb":
            target.points = [opers[n]["val"] for n in range(1,len(opers)-2)]
        elif op == "spline_linear":
            target.points = [opers[n]["val"] for n in range(1,len(opers)-2)]
        else:
            reportError("Unknown formula %s" % opers, trigger=(2,6))
            return


    def parseChannel(self, channel):
        if channel == "value":
            return channel, 0, 0.0
        elif channel == "general_scale":
            channel = "scale/general"
        data = channel.split("/")
        if len(data) != 2:
            return channel, 0, 0.0
        attr,comp = data
        idx = getIndex(comp)
        if attr in ["rotation", "translation", "center_point", "end_point"]:
            default = Zero
        elif attr == "scale":
            default = One
        elif attr in ["orientation"]:
            return None, 0, Zero
        else:
            msg = ("Unknown attribute: %s" % attr)
            reportError(msg)
        return attr, idx, default


    def getRefKey(self, string):
        base = string.split(":",1)[-1]
        return base.rsplit("?",1)

#-------------------------------------------------------------
#   Baked morphs
#-------------------------------------------------------------

def buildBakedMorph(inst, ref, value):
    from .driver import removeModifiers, setProtected, addDriverVar
    from .selector import setActivated
    rig = inst.getRig()
    if rig and value != 0:
        value = float(value)
        file,raw = ref.rsplit("#",1)
        file = unquote(file)
        raw = rawProp(unquote(raw))
        rig[raw] = value
        final = finalProp(raw)
        rig.data[final] = value
        if GS.verbosity > 2 and not ES.easy:
            print("Baked morph (%s): %s = %f" % (rig.name, unquote(raw), value))
        setProtected(rig, raw, True)
        setActivated(rig, raw, False)
        item = rig.DazBaked.add()
        item.name = raw
        item.text = raw
        if file not in rig.DazBakedFiles.keys():
            item = rig.DazBakedFiles.add()
            item.name = file
            item.f = value
            if GS.verbosity > 2 and not ES.easy:
                print("Baked morph file (%s): %s" % (rig.name, file))
        fcu = rig.data.driver_add(propRef(final))
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        fcu.driver.expression = "a"
        addDriverVar(fcu, "a",  propRef(raw), rig)

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class ExprTarget:
    def __init__(self, key, type, comp):
        self.key = key
        self.type = type.rsplit("/",1)[0]
        self.comp = comp
        self.factor = 0.0
        self.points = []
        self.mults = []


    def __repr__(self):
        return "<ExprTarget %s %s %d %.3f %s %s>" % (self.key, self.type, self.comp, self.factor, self.points, self.mults)


    def getFactor(self, useSplines):
        if not self.points:
            return self.factor
        elif useSplines and GS.useSplineDrivers:
            return [point[0:2] for point in self.points]
        else:
            x0 = y0 = None
            for n,point in enumerate(self.points):
                x,y = point[0:2]
                if x == 0 and y == 0:
                    x0 = x
                    y0 = y
                    n0 = n
                    break
            if x0 is None:
                return self.factor
            if n0 == 0:
                x1,y1 = self.points[-1][0:2]
            else:
                x1,y1 = self.points[0][0:2]
            factor = (y1-y0)/(x1-x0)
            return factor


class Expression:
    def __init__(self):
        self.prop = None
        self.prop2 = None
        self.bone = None
        self.bone2 = None
        self.path = None

    def __repr__(self):
        return "<Expression\n  %s\n  %s\n  %s\n  %s\n  %s>" % (self.prop, self.prop2, self.bone, self.bone2, self.path)

    def multFactors(self, factor):
        for trg in [self.prop, self.bone]:
            if trg:
                trg.factor *= factor


def setFormulaExpr(exprs, output, path, channel, idx, fileref=""):
    if output not in exprs.keys():
        exprs[output] = {"*fileref" : (fileref, channel)}
    if path not in exprs[output].keys():
        exprs[output][path] = {}
    if idx not in exprs[output][path].keys():
        exprs[output][path][idx] = Expression()
    return exprs[output][path][idx]
