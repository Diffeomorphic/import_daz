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
from mathutils import Vector, Euler
from .error import *
from .tables import *
from .utils import *
from .fileutils import AF
from .selector import Selector
from .driver import DriverUser

#-------------------------------------------------------------
#   Find polys
#-------------------------------------------------------------

def findHumanAndProxy(context):
    hum = pxy = None
    for ob in getSelectedMeshes(context):
        if hum is None:
            hum = ob
        else:
            pxy = ob
    if len(pxy.data.vertices) > len(hum.data.vertices):
        ob = pxy
        pxy = hum
        hum = ob
    return hum,pxy


def assocPxyHumVerts(hum, pxy):
    pxyHumVerts = {}
    hverts = [(hv.co, hv.index) for hv in hum.data.vertices]
    hverts.sort()
    pverts = [(pv.co, pv.index) for pv in pxy.data.vertices]
    pverts.sort()
    for pco,pvn in pverts:
        hco,hvn = hverts[0]
        while (pco-hco).length > 1e-4:
            hverts = hverts[1:]
            hco,hvn = hverts[0]
        pxyHumVerts[pvn] = hvn
    humPxyVerts = dict([(hvn,None) for hvn in range(len(hum.data.vertices))])
    for pvn,hvn in pxyHumVerts.items():
        humPxyVerts[hvn] = pvn
    return pxyHumVerts, humPxyVerts


def findPolys(context):
    hum,pxy = findHumanAndProxy(context)
    print(hum, pxy)
    humFaceVerts,humVertFaces = getVertFaces(hum)
    pxyFaceVerts,pxyVertFaces = getVertFaces(pxy)
    pxyHumVerts,humPxyVerts = assocPxyHumVerts(hum, pxy)
    print("PxyHumVerts", len(pxyHumVerts), len(humPxyVerts))

    pvn = len(pxy.data.vertices)
    pen = len(pxy.data.edges)
    newHumPxyVerts = {}
    newPxyEdges = []
    for e in hum.data.edges:
        if e.use_seam:
            hvn1,hvn2 = e.vertices
            pvn1 = humPxyVerts[hvn1]
            pvn2 = humPxyVerts[hvn2]
            useAdd = False
            if pvn1 is None or pvn2 is None:
                if hvn1 in newHumPxyVerts.keys():
                    pvn1 = newHumPxyVerts[hvn1]
                else:
                    pvn1 = newHumPxyVerts[hvn1] = pvn
                    pvn += 1
                if hvn2 in newHumPxyVerts.keys():
                    pvn2 = newHumPxyVerts[hvn2]
                else:
                    pvn2 = newHumPxyVerts[hvn2] = pvn
                    pvn += 1
                newPxyEdges.append((pen, pvn1, pvn2))
                pen += 1

    newVerts = [(pvn,hvn) for hvn,pvn in newHumPxyVerts.items()]
    newVerts.sort()

    setActiveObject(context, pxy)
    setMode('EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    setMode('OBJECT')

    print("BEF", len(pxy.data.vertices), len(pxy.data.edges))
    pxy.data.vertices.add(len(newVerts))
    for pvn,hvn in newVerts:
        pv = pxy.data.vertices[pvn]
        pv.co = hum.data.vertices[hvn].co.copy()
        #print(pv.index,pv.co)
    pxy.data.edges.add(len(newPxyEdges))
    for pen,pvn1,pvn2 in newPxyEdges:
        pe = pxy.data.edges[pen]
        pe.vertices = (pvn1,pvn2)
        pe.select = True
        #print(pe.index, list(pe.vertices), pe.use_seam)
    print("AFT", len(pxy.data.vertices), len(pxy.data.edges))
    return

    pxyHumFaces = {}
    for pfn,pfverts in enumerate(pxyFaceVerts):
        cands = []
        for pvn in pfverts:
            hvn = pxyHumVerts[pvn]
            for hfn in humVertFaces[hvn]:
                cands.append(hfn)
        print(pfn, cands)
        if len(cands) == 16:
            vcount = {}
            for hfn in cands:
                for hvn in humFaceVerts[hfn]:
                    if hvn not in vcount.keys():
                        vcount[hvn] = []
                    vcount[hvn].append(hfn)
            vlist = [(len(hfns),hvn,hfns) for hvn,hfns in vcount.items()]
            vlist.sort()
            print(vlist)
            pxyHumFaces[pfn] = vlist[-1]
            print("RES", pfn, pxyHumFaces[pfn])
            for hfn in vlist[-1][2]:
                hf = hum.data.polygons[hfn]
                hf.select = True


class DAZ_OT_FindPolys(DazOperator, IsMeshArmature):
    bl_idname = "daz.find_polys"
    bl_label = "Find Polys"
    bl_options = {'UNDO'}

    def run(self, context):
        findPolys(context)

#-------------------------------------------------------------
#   Make faithful proxy
#-------------------------------------------------------------

class Proxifier(DriverUser):
    def __init__(self, ob):
        DriverUser.__init__(self)
        self.object = ob
        self.nfaces = len(ob.data.polygons)
        self.nverts = len(ob.data.vertices)
        self.faceverts = None
        self.vertfaces = None
        self.neighbors = None
        self.seams = None
        self.faces = []
        self.matOffset = 10
        self.origMnums = {}
        self.colorOnly = False


    def remains(self):
        free = [t for t in self.dirty.values() if not t]
        return len(free)


    def setup(self, ob, context):
        self.faceverts, self.vertfaces, self.neighbors, self.seams = findSeams(ob)
        if self.colorOnly:
            self.createMaterials()
        self.origMnums = {}
        for f in ob.data.polygons:
            self.origMnums[f.index] = f.material_index
            if self.colorOnly:
                f.material_index = 0

        deselectEverything(ob, context)
        self.dirty = dict([(fn,False) for fn in range(self.nfaces)])
        for f in ob.data.polygons:
            if f.hide:
                self.dirty[f.index] = True
        newfaces = [[fn] for fn in range(self.nfaces) if self.dirty[fn]]
        printStatistics(ob)
        return newfaces


    def getConnectedComponents(self):
        self.clusters = dict([(fn,-1) for fn in range(self.nfaces)])
        self.refs = dict([(fn,fn) for fn in range(self.nfaces)])
        cnum = 0
        for fn in range(self.nfaces):
            cnums = []
            for fn2 in self.neighbors[fn]:
                cn = self.clusters[fn2]
                if cn >= 0:
                    cnums.append(self.deref(cn))
            cnums.sort()
            if cnums:
                self.clusters[fn] = cn0 = cnums[0]
                for cn in cnums[1:]:
                    self.refs[cn] = cn0
            else:
                self.clusters[fn] = cn0 = cnum
                cnum += 1

        comps = dict([(cn,[]) for cn in range(cnum)])
        taken = dict([(cn,False) for cn in range(cnum)])
        for fn in range(self.nfaces):
            cn = self.clusters[fn]
            cn = self.deref(cn)
            comps[cn].append(fn)
            self.clusters[fn] = cn
        return comps,taken


    def deref(self, cn):
        cnums = []
        while self.refs[cn] != cn:
            cnums.append(cn)
            cn = self.refs[cn]
        for cn1 in cnums:
            self.refs[cn1] = cn
        return cn


    def getComponents(self, ob, context):
        deselectEverything(ob, context)
        if ob.data.polygons:
            self.faceverts, self.vertfaces = getVertFaces(ob)
            self.neighbors = findNeighbors(range(self.nfaces), self.faceverts, self.vertfaces)
        elif ob.data.edges:
            self.neighbors = findEdgeNeighbors(ob)
            self.nfaces = len(ob.data.edges)
        comps,taken = self.getConnectedComponents()
        return comps


    def selectComp(self, comp, ob):
        if ob.data.polygons:
            faces = ob.data.polygons
        elif ob.data.edges:
            faces = ob.data.edges
        else:
            return
        for fn in comp:
            f = faces[fn]
            if not f.hide:
                f.select = True


    def getNodes(self):
        nodes = []
        comps,taken = self.getConnectedComponents()
        for vn in range(self.nverts):
            fnums = self.vertfaces[vn]
            if len(fnums) not in [0,2,4]:
                for fn in fnums:
                    if not self.dirty[fn]:
                        nodes.append(fn)
                        taken[self.clusters[fn]] = True
        for cn,comp in comps.items():
            if len(comp) > 0 and not taken[cn]:
                nodes.append(comp[0])
        return set(nodes)


    def make(self, ob, context):
        newfaces = self.setup(ob, context)
        remains1 = self.remains()
        print("Step 0 Remains:", remains1)

        nodes = self.getNodes()
        for fn in nodes:
            self.dirty[fn] = True
        for fn in nodes:
            self.mergeFaces(fn, newfaces)

        prevblock = newfaces
        step = 1
        remains2 = self.remains()
        while remains2 and remains2 < remains1 and step < 50:
            print("Step %d Remains:" % step, self.remains())
            block = []
            for newface in prevblock:
                self.mergeNextFaces(newface, block)
            newfaces += block
            prevblock = block
            step += 1
            remains1 = remains2
            remains2 = self.remains()
        print("Step %d Remains:" % step, self.remains())

        if self.colorOnly:
            self.combineFaces(newfaces)
            return
        else:
            self.buildNewMesh(newfaces)
        deleteMidpoints(ob)
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        setMode('OBJECT')
        printStatistics(ob)


    def makeQuads(self, ob, context):
        newfaces = self.setup(ob, context)
        for fn1 in range(self.nfaces):
            if self.dirty[fn1]:
                continue
            if len(self.faceverts[fn1]) == 3:
                for fn2 in self.neighbors[fn1]:
                    if (len(self.faceverts[fn2]) == 3 and
                        not self.dirty[fn2] and
                        fn2 not in self.seams[fn1]):
                        self.dirty[fn1] = True
                        self.dirty[fn2] = True
                        newface = [fn1,fn2]
                        newfaces.append(newface)
                        break
        if self.colorOnly:
            self.combineFaces(newfaces)
            return
        else:
            self.buildNewMesh(newfaces)
        printStatistics(ob)


    def buildNewMesh(self, newfaces):
        from .geometry import makeNewUvloop

        free = [[fn] for fn,t in self.dirty.items() if not t]
        newfaces += free
        ob = self.object
        uvtex,uvloop,uvdata = getUvData(ob)
        self.vertmap = dict([(vn,-1) for vn in range(self.nverts)])
        self.verts = []
        self.lastvert = 0
        faces = []
        uvfaces = []
        mats = list(ob.data.materials)
        mnums = []
        n = 0
        for newface in newfaces:
            taken = self.findTaken(newface)
            n = 0
            fn1 = newface[n]
            fverts = self.faceverts[fn1]
            idx = 0
            vn = fverts[idx]
            while self.changeFace(vn, fn1, newface) >= 0:
                idx += 1
                if idx == len(fverts):
                    n += 1
                    if n == len(newface):
                        for fn in newface:
                            print(fn, self.faceverts[fn])
                        raise RuntimeError("BUG")
                    fn1 = newface[n]
                    fverts = self.faceverts[fn1]
                    idx = 0
                vn = fverts[idx]
            face = [self.getVert(vn)]
            uvface = [uvdata[fn1][idx]]
            mnums.append(self.origMnums[fn1])
            taken[vn] = True
            done = False
            while not done:
                fn2 = self.changeFace(vn, fn1, newface)
                if fn2 >= 0:
                    fn1 = fn2
                    fverts = self.faceverts[fn2]
                    idx = getIndex(vn, fverts)
                idx = (idx+1)%len(fverts)
                vn = fverts[idx]
                if taken[vn]:
                    done = True
                else:
                    face.append(self.getVert(vn))
                    uvface.append(uvdata[fn1][idx])
                    taken[vn] = True
            if len(face) >= 3:
                faces.append(face)
                uvfaces.append(uvface)
            else:
                print("Non-face:", face)

        me = bpy.data.meshes.new("New")
        me.from_pydata(self.verts, [], faces)
        uvloop = makeNewUvloop(me, "Uvloop", True)
        n = 0
        for uvface in uvfaces:
            for uv in uvface:
                uvloop.data[n].uv = uv
                n += 1
        for mat in mats:
            me.materials.append(mat)
        for fn,mn in enumerate(mnums):
            f = me.polygons[fn]
            f.material_index = mn
            f.use_smooth = True

        vgnames = [vgrp.name for vgrp in ob.vertex_groups]
        weights = dict([(vn,{}) for vn in range(self.nverts)])
        for vn,v in enumerate(ob.data.vertices):
            nvn = self.vertmap[vn]
            if nvn >= 0:
                for g in v.groups:
                    weights[nvn][g.group] = g.weight

        skeys = []
        if ob.data.shape_keys:
            for skey in ob.data.shape_keys.key_blocks:
                data = dict([(vn, skey.data[vn].co) for vn in range(self.nverts)])
                skeys.append((skey.name, skey.value, skey.slider_min, skey.slider_max, data))
        drivers = self.getShapekeyDrivers(ob)

        ob.data = me
        ob.vertex_groups.clear()
        vgrps = {}
        for gn,vgname in enumerate(vgnames):
            vgrps[gn] = ob.vertex_groups.new(name=vgname)
        for vn,grp in weights.items():
            for gn,w in grp.items():
                vgrps[gn].add([vn], w, 'REPLACE')

        for (sname, value, min, max, data) in skeys:
            skey = ob.shape_key_add(name=sname)
            skey.slider_min = min
            skey.slider_max = max
            skey.value = value
            for vn,co in data.items():
                nvn = self.vertmap[vn]
                if nvn >= 0:
                    skey.data[nvn].co = co

        if drivers:
            self.copyShapeKeyDrivers(ob, drivers)


    def changeFace(self, vn, fn1, newface):
        for fn2 in newface:
            if (fn2 != fn1 and
                vn in self.faceverts[fn2]):
                return fn2
        return -1


    def getVert(self, vn):
        nvn = self.vertmap[vn]
        if nvn < 0:
            self.verts.append(self.object.data.vertices[vn].co)
            nvn = self.vertmap[vn] = self.lastvert
            self.lastvert += 1
        return nvn


    def findTaken(self, newface):
        taken = dict([vn,False] for fn in newface for vn in self.faceverts[fn])
        hits = dict([vn,0] for fn in newface for vn in self.faceverts[fn])
        for fn in newface:
            for vn in self.faceverts[fn]:
                hits[vn] += 1
                if hits[vn] > 2:
                    taken[vn] = True
        return taken


    def combineFaces(self, newfaces):
        ob = self.object
        maxmnum = self.colorFaces(newfaces)
        print("Max material number:", maxmnum)

        print("Adding faces")
        setMode('EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        count = 0
        for mn in range(maxmnum):
            if count % 25 == 0:
                print("  ", count)
            if mn % self.matOffset == 0:
                continue
            setMode('OBJECT')
            ob.active_material_index = mn
            setMode('EDIT')
            bpy.ops.object.material_slot_select()
            try:
                bpy.ops.mesh.edge_face_add()
            except RuntimeError:
                pass
            bpy.ops.mesh.select_all(action='DESELECT')
            setMode('OBJECT')
            count += 1

        printStatistics(ob)


    def mergeNextFaces(self, face, newfaces):
        me = self.object.data
        if len(face) < 2:
            return
        nextfaces = [face]
        while nextfaces:
            faces = nextfaces
            nextfaces = []
            for face in faces:
                for fn0 in face:
                    mn = self.origMnums[fn0]
                    for fn1 in face:
                        if (fn1 in self.neighbors[fn0] and
                            mn == self.origMnums[fn1]):
                            newface = self.mergeSide(fn0, fn1, newfaces, mn)
                            if newface:
                                if len(newface) == 4:
                                    for fn in newface:
                                        me.polygons[fn].select = True
                                    nextfaces.append(newface)
                                break


    def mergeSide(self, fn0, fn1, newfaces, mn):
        for fn2 in self.neighbors[fn0]:
            if (self.dirty[fn2] or
                fn2 in self.seams[fn0] or
                fn2 in self.seams[fn1]
                ):
                continue
            for fn3 in self.neighbors[fn1]:
                if (fn3 == fn2 or
                    self.dirty[fn3] or
                    fn3 not in self.neighbors[fn2] or
                    fn3 in self.seams[fn0] or
                    fn3 in self.seams[fn1] or
                    fn3 in self.seams[fn2]
                    ):
                    continue
                self.dirty[fn2] = True
                self.dirty[fn3] = True
                newface = self.mergeFacePair([fn2,fn3], newfaces, mn)
                return newface
        return None


    def mergeFaces(self, fn0, newfaces):
        newface = [fn0]
        self.dirty[fn0] = True
        mn = self.origMnums[fn0]
        for fn1 in self.neighbors[fn0]:
            if (fn1 not in self.seams[fn0] and
                not self.dirty[fn1] and
                mn == self.origMnums[fn1]):
                newface.append(fn1)
                self.dirty[fn1] = True
                break
        if len(newface) == 2:
            return self.mergeFacePair(newface, newfaces, mn)
        else:
            newfaces.append(newface)
            return newface


    def mergeFacePair(self, newface, newfaces, mn):
        fn0,fn1 = newface
        for fn2 in self.neighbors[fn0]:
           if (fn2 != fn1 and
                self.sharedVertex(fn1, fn2) and
                fn2 not in self.seams[fn0] and
                not self.dirty[fn2] and
                mn == self.origMnums[fn2]):
                newface.append(fn2)
                self.dirty[fn2] = True
                break

        if len(newface) == 3:
            fn2 = newface[2]
            for fn3 in self.neighbors[fn1]:
                if (fn3 != fn0 and
                    fn3 != fn2 and
                    fn3 in self.neighbors[fn2] and
                    not self.dirty[fn3] and
                    mn == self.origMnums[fn3]):
                    newface.append(fn3)
                    self.dirty[fn3] = True
                    break

        if len(newface) == 3:
            fn0,fn1,fn2 = newface
            self.dirty[fn2] = False
            newface = [fn0,fn1]

        newfaces.append(newface)
        return newface


    def sharedVertex(self, fn1, fn2):
        for vn in self.faceverts[fn1]:
            if vn in self.faceverts[fn2]:
                return True
        return False


    def colorFaces(self, newfaces):
        me = self.object.data
        matnums = dict((fn,0) for fn in range(self.nfaces))
        maxmnum = 0
        for newface in newfaces:
            mnums = []
            for fn in newface:
                mnums += [matnums[fn2] for fn2 in self.neighbors[fn]]
            mn = 1
            while mn in mnums:
                mn += 1
            if mn > maxmnum:
                maxmnum = mn
            for fn in newface:
                f = me.polygons[fn]
                f.material_index = matnums[fn] = mn

        return maxmnum


    def createMaterials(self):
        me = self.object.data
        mats = [mat for mat in me.materials]
        me.materials.clear()
        n = 0
        for r in range(3):
            for g in range(3):
                for b in range(3):
                    mat = bpy.data.materials.new("Mat-%02d" % n)
                    n += 1
                    mat.diffuse_color[0:3] = (r/2, g/2, b/2)
                    me.materials.append(mat)


def getUvData(ob):
    from collections import OrderedDict

    uvtex = ob.data.uv_layers
    uvloop = ob.data.uv_layers[0]
    uvdata = OrderedDict()
    m = 0
    for fn,f in enumerate(ob.data.polygons):
        n = len(f.vertices)
        uvdata[fn] = [uvloop.data[j].uv for j in range(m,m+n)]
        m += n
    return uvtex,uvloop,uvdata


def deleteMidpoints(ob):
    vertedges = getVertEdges(ob)
    faceverts, vertfaces = getVertFaces(ob)
    uvtex,uvloop,uvdata = getUvData(ob)

    for vn,v in enumerate(ob.data.vertices):
        if (len(vertedges[vn]) == 2 and
            len(vertfaces[vn]) <= 2):
            e = vertedges[vn][0]
            vn1,vn2 = e.vertices
            if vn1 == vn:
                v.co = ob.data.vertices[vn2].co
                moveUv(vn, vn2, vertfaces[vn], faceverts, uvdata)
            elif vn2 == vn:
                v.co = ob.data.vertices[vn1].co
                moveUv(vn, vn1, vertfaces[vn], faceverts, uvdata)
            else:
                halt

    m = 0
    for uvs in uvdata.values():
        for j,uv in enumerate(uvs):
            uvloop.data[m+j].uv = uv
        m += len(uvs)


def moveUv(vn1, vn2, fnums, faceverts, uvdata):
    for fn in fnums:
        fverts = faceverts[fn]
        n1 = getIndex(vn1, fverts)
        n2 = getIndex(vn2, fverts)
        uvdata[fn][n1] = uvdata[fn][n2]


def getIndex(vn, verts):
    for n,vn1 in enumerate(verts):
        if vn1 == vn:
            return n


#-------------------------------------------------------------
#   Insert seams
#-------------------------------------------------------------

def insertSeams(hum, pxy):
    for pe in pxy.data.edges:
        pe.use_seam = False
    humPxy,pxyHum = identifyVerts(hum, pxy)

    pvn = pvn0 = len(pxy.data.vertices)
    pen = len(pxy.data.edges)
    newVerts = {}
    newEdges = {}
    seams = [e for e in hum.data.edges if e.use_seam]
    nseams = {}
    for e in seams:
        vn1,vn2 = e.vertices
        old1 = (vn1 in humPxy.keys())
        old2 = (vn2 in humPxy.keys())
        if old1 and old2:
            pvn1 = humPxy[vn1]
            pvn2 = humPxy[vn2]
            if (pvn1 in nseams.keys() and
                pvn2 not in nseams[pvn1]):
                newEdges[pen] = (pvn1, pvn2)
                pen += 1
        elif old1:
            pvn1 = humPxy[vn1]
            pvn2 = pvn
            newVerts[pvn2] = hum.data.vertices[vn2].co
            humPxy[vn2] = pvn2
            pvn += 1
            newEdges[pen] = (pvn1, pvn2)
            pen += 1
        elif old2:
            pvn1 = pvn
            newVerts[pvn1] = hum.data.vertices[vn1].co
            humPxy[vn1] = pvn1
            pvn2 = humPxy[vn2]
            pvn += 1
            newEdges[pen] = (pvn1, pvn2)
            pen += 1
        else:
            pvn1 = pvn
            newVerts[pvn1] = hum.data.vertices[vn1].co
            humPxy[vn1] = pvn1
            pvn2 = pvn+1
            newVerts[pvn2] = hum.data.vertices[vn2].co
            humPxy[vn2] = pvn2
            pvn += 2
            newEdges[pen] = (pvn1, pvn2)
            pen += 1

        if pvn1 not in nseams.keys():
            nseams[pvn1] = [pvn2]
        else:
            nseams[pvn1].append(pvn2)
        if pvn2 not in nseams.keys():
            nseams[pvn2] = [pvn1]
        else:
            nseams[pvn2].append(pvn1)

        if 1367 in [pvn1,pvn2]:
            print("O", vn1, vn2, pvn, pvn1, pvn2, old1, old2)
            print("  ", hum.data.vertices[vn1].co)
            print("  ", hum.data.vertices[vn2].co)
            print("  ", nseams[1367])
            print("  ", pxyHum[1367])


    pvn0 = len(pxy.data.vertices)
    pxy.data.vertices.add(len(newVerts))
    for pvn,co in newVerts.items():
        pxy.data.vertices[pvn].co = co
    #for pvn in range(pvn0, pvn0+3):
    #    print("  ", pvn, pxy.data.vertices[pvn].co)


    pxy.data.edges.add(len(newEdges))
    for pen,pverts in newEdges.items():
        pe = pxy.data.edges[pen]
        pe.vertices = pverts
        pe.select = True
    for pe in pxy.data.edges:
        pvn1,pvn2 = pe.vertices
        if (pvn1 in nseams.keys() and
            pvn2 in nseams[pvn1]):
            pe.use_seam = True


def identifyVerts(hum, pxy):
    '''
    for e in hum.data.edges:
        if e.use_seam:
            vn1,vn2 = e.vertices
            if vn1 < vn2:
                v1 = hum.data.vertices[vn1]
                v2 = hum.data.vertices[vn2]
                verts += [(v1.co, ("E", vn1, vn2, e.index)),
                          (v2.co, ("E", vn2, vn1, e.index))]
    '''
    hverts = [(v.co, ("H", v.index, v.co)) for v in hum.data.vertices]
    pverts = [(v.co, ("P", v.index, v.co)) for v in pxy.data.vertices]
    verts = hverts + pverts
    verts.sort()

    humPxy = {}
    pxyHum = {}
    nverts = len(verts)
    for m,vert in enumerate(verts):
        co1,data1 = vert
        if data1[0] == "P":
            mindist = 1e7
            pvn = data1[1]
            for j in range(-20,20):
                n = min(max(0, m+j), nverts-1)
                co2,data2 = verts[n]
                dist = (co1-co2).length
                if data2[0] == "H" and dist < mindist:
                    mindist = dist
                    vn = data2[1]
            humPxy[vn] = pvn
            pxyHum[pvn] = vn
            if mindist > 1e-7:
                pco = pxy.data.vertices[pvn]
                co = hum.data.vertices[vn]
                print("DIST", pvn, vn, pco, co, mindist)
    return humPxy, pxyHum


def deselectEverything(ob, context):
    for f in ob.data.polygons:
        f.select = False
    for e in ob.data.edges:
        e.select = False
    for v in ob.data.vertices:
        v.select = False

#-------------------------------------------------------------
#   Make Proxy
#-------------------------------------------------------------

class MakeProxy(IsMesh):

    def run(self, context):
        active = context.object
        meshes = getSelectedMeshes(context)
        print("-----")
        errors = []
        for ob in meshes:
            if activateObject(context, ob):
                print("\nMake %s low-poly" % ob.name)
                self.makeProxy(ob, context, errors)
        restoreSelectedObjects(context, meshes, active)
        if errors:
            msg = "Cannot make low-poly version\nof meshes with shapekeys:"
            for ob in errors:
                msg += ("\n  %s" % ob.name)
            raise DazError(msg)


class DAZ_OT_MakeQuickProxy(MakeProxy, DazPropsOperator):
    bl_idname = "daz.make_quick_proxy"
    bl_label = "Make Quick Low-poly"
    bl_description = "Replace all selected meshes by low-poly versions, using a quick algorithm that does not preserve UV seams"
    bl_options = {'UNDO'}

    iterations : IntProperty(
        name = "Iterations",
        description = "Number of iterations when ",
        min = 0, max = 10,
        default = 2)

    def makeProxy(self, ob, context, errors):
        scn = context.scene
        if ob.data.shape_keys:
            errors.append(ob)
            return None
        applyShapeKeys(ob)
        printStatistics(ob)
        mod = ob.modifiers.new("Proxy", 'DECIMATE')
        mod.decimate_type = 'UNSUBDIV'
        mod.iterations = self.iterations
        bpy.ops.object.modifier_apply(modifier=mod.name)
        printStatistics(ob)
        return ob


class DAZ_OT_MakeFaithfulProxy(MakeProxy, DazOperator):
    bl_idname = "daz.make_faithful_proxy"
    bl_label = "Make Faithful Low-poly"
    bl_description = "Replace all selected meshes by low-poly versions, using a experimental algorithm that does preserve UV seams"
    bl_options = {'UNDO'}

    def makeProxy(self, ob, context, _errors):
        return Proxifier(ob).make(ob, context)


#-------------------------------------------------------------
#   Quadify
#-------------------------------------------------------------

class DAZ_OT_Quadify(MakeProxy, DazOperator, IsMesh):
    bl_idname = "daz.quadify"
    bl_label = "Quadify Triangles"
    bl_description = "Join triangles to quads"
    bl_options = {'UNDO'}

    def run(self, context):
        active = context.object
        meshes = getSelectedMeshes(context)
        print("-----")
        errors = []
        for ob in meshes:
            if activateObject(context, ob):
                print("\nQuadify %s" % ob.name)
                printStatistics(ob)
                setMode('EDIT')
                bpy.ops.mesh.select_mode(type='FACE')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.tris_convert_to_quads()
                setMode('OBJECT')
                printStatistics(ob)
        restoreSelectedObjects(context, meshes, active)


def restoreSelectedObjects(context, meshes, active):
    for ob in meshes:
        selectSet(ob, True)
    setActiveObject(context, active)

#-------------------------------------------------------------
#   Split n-gons
#-------------------------------------------------------------

def splitNgons(ob, context):
    if not activateObject(context, ob):
        return
    printStatistics(ob)
    setMode('EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    setMode('OBJECT')
    for f in ob.data.polygons:
        if (len(f.vertices) > 4 and not f.hide):
            f.select = True
    setMode('EDIT')
    bpy.ops.mesh.quads_convert_to_tris(ngon_method='BEAUTY')
    #bpy.ops.mesh.tris_convert_to_quads()
    setMode('OBJECT')
    printStatistics(ob)


class DAZ_OT_SplitNgons(DazOperator, IsMesh):
    bl_idname = "daz.split_ngons"
    bl_label = "Split n-gons"
    bl_description = "Split all polygons with five or more corners into triangles"
    bl_options = {'UNDO'}

    def run(self, context):
        active = context.object
        meshes = getSelectedMeshes(context)
        for ob in meshes:
            print("\nSplit n-gons of %s" % ob.name)
            splitNgons(ob, context)
        restoreSelectedObjects(context, meshes, active)

#-------------------------------------------------------------
#   Find seams
#-------------------------------------------------------------

def findSeams(ob):
    print("Find seams", ob)
    #ob.data.materials.clear()

    faceverts,vertfaces = getVertFaces(ob)
    nfaces = len(faceverts)
    neighbors = findNeighbors(range(nfaces), faceverts, vertfaces)

    texverts,texfaces = findTexVerts(ob, vertfaces)
    _,texvertfaces = getVertFaces(ob, texverts, None, texfaces)
    texneighbors = findNeighbors(range(nfaces), texfaces, texvertfaces)

    seams = dict([(fn,[]) for fn in range(nfaces)])
    for fn1,nn1 in neighbors.items():
        for fn2 in nn1:
            if (fn2 not in texneighbors[fn1]):
                if fn1 in seams.keys():
                    seams[fn1].append(fn2)

    setMode('EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    setMode('OBJECT')

    for e in ob.data.edges:
        vn1,vn2 = e.vertices
        for fn1 in vertfaces[vn1]:
            f1 = ob.data.polygons[fn1]
            for fn2 in vertfaces[vn2]:
                f2 = ob.data.polygons[fn2]
                if (vn2 in f1.vertices and
                    vn1 in f2.vertices and
                    fn1 != fn2):
                    if fn2 in seams[fn1]:
                        e.select = True

    vertedges = getVertEdges(ob)
    edgefaces = getEdgeFaces(ob, vertedges)
    for e in ob.data.edges:
        if len(edgefaces[e.index]) != 2:
            e.select = True

    setMode('EDIT')
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    setMode('OBJECT')

    print("Seams found")
    return  faceverts, vertfaces, neighbors,seams


class DAZ_OT_FindSeams(DazOperator, IsMesh):
    bl_idname = "daz.find_seams"
    bl_label = "Find Seams"
    bl_description = "Create seams based on existing UVs"
    bl_options = {'UNDO'}

    def run(self, context):
        findSeams(context.object)

#-------------------------------------------------------------
#   Select random strands
#-------------------------------------------------------------

class DAZ_OT_SelectRandomStrands(DazPropsOperator, IsMesh):
    bl_idname = "daz.select_random_strands"
    bl_label = "Select Random Strands"
    bl_description = ("Select random subset of strands selected in UV space.\n" +
                      "Useful for reducing the number of strands before making particle hair")
    bl_options = {'UNDO'}

    fraction : FloatProperty(
        name = "Fraction",
        description = "Fraction of strands to select",
        min = 0.0, max = 1.0,
        default = 0.5)

    seed : IntProperty(
        name = "Seed",
        description = "Seed for the random number generator",
        default = 0)

    def draw(self, context):
        self.layout.prop(self, "fraction")
        self.layout.prop(self, "seed")


    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.selectRandom(context, ob)


    def selectRandom(self, context, ob):
        import random
        if not (ob.data.polygons or ob.data.edges):
            return
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, context)
        random.seed(self.seed)
        for comp in comps.values():
            if random.random() < self.fraction:
                prox.selectComp(comp, ob)


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#-------------------------------------------------------------
#   Select strands by width
#-------------------------------------------------------------

class DAZ_OT_SelectStrandsByWidth(DazPropsOperator, IsMesh):
    bl_idname = "daz.select_strands_by_width"
    bl_label = "Select Strands By Width"
    bl_description = "Select strands not wider than threshold"
    bl_options = {'UNDO'}

    width : FloatProperty(
        name = "Width",
        description = "Max allowed width (mm)",
        min = 0.1, max = 10,
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "width")


    def run(self, context):
        ob = context.object
        if not ob.data.polygons:
            raise DazError("Mesh has no polygons")
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, context)
        maxwidth = 0.1 * self.width * ob.DazScale
        verts = ob.data.vertices
        faces = ob.data.polygons
        for comp in comps.values():
            if self.withinWidth(verts, faces, comp, maxwidth):
                prox.selectComp(comp, ob)


    def withinWidth(self, verts, faces, comp, maxwidth):
        for fn in comp:
            sizes = [(verts[vn1].co - verts[vn2].co).length
                      for vn1,vn2 in faces[fn].edge_keys]
            sizes.sort()
            if sizes[-3] > maxwidth:
                return False
        return True


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#-------------------------------------------------------------
#   Select largest strands
#-------------------------------------------------------------

class DAZ_OT_SelectStrandsBySize(DazOperator, IsMesh, Selector):
    bl_idname = "daz.select_strands_by_size"
    bl_label = "Select Strands By Size"
    bl_description = ("Select strands based on the number of faces.\n" +
                      "Useful for reducing the number of strands before making particle hair")
    bl_options = {'UNDO'}

    def draw(self, context):
        Selector.draw(self, context)

    def run(self, context):
        ob = context.object
        if not (ob.data.polygons or ob.data.edges):
            return
        prox = Proxifier(ob)
        for item in self.getSelectedItems():
            for comp in self.groups[int(item.name)]:
                prox.selectComp(comp, ob)


    def getKeys(self, rig, ob):
        prox = Proxifier(ob)
        comps = prox.getComponents(ob, bpy.context)
        self.groups = dict([(len(comp),[]) for comp in comps.values()])
        for comp in comps.values():
            self.groups[len(comp)].append(comp)
        sizes = list(self.groups.keys())
        sizes.sort()
        keys = [(str(size), str(size), "All") for size in sizes]
        return keys


    def invoke(self, context, event):
        return Selector.invoke(self, context, event)


    def sequel(self, context):
        DazPropsOperator.sequel(self, context)
        if context.object:
            setMode('EDIT')

#-------------------------------------------------------------
#  Apply morphs
#-------------------------------------------------------------

def applyShapeKeys(ob):
    from .category import getShapeKeyCoords
    if ob.type != 'MESH':
        return
    if ob.data.shape_keys:
        skeys,coords = getShapeKeyCoords(ob)
        skeys.reverse()
        for skey in skeys:
            ob.shape_key_remove(skey)
        skey = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(skey)
        for v in ob.data.vertices:
            v.co = coords[v.index]


class DAZ_OT_ApplyMorphs(DazOperator, IsMesh):
    bl_idname = "daz.apply_morphs"
    bl_label = "Apply Morphs"
    bl_description = "Apply all shapekeys"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            applyShapeKeys(ob)

#-------------------------------------------------------------
#   Apply subsurf modifier
#-------------------------------------------------------------

class DAZ_OT_ApplySubsurf(DazOperator, IsMesh):
    bl_idname = "daz.apply_subsurf"
    bl_label = "Apply Subsurf"
    bl_description = "Apply subsurf modifier, maintaining shapekeys"
    bl_options = {'UNDO'}

    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False

    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def run(self, context):
        from .driver import Driver
        ob = context.object
        mod = getModifier(ob, 'SUBSURF')
        if not mod:
            raise DazError("Object %s\n has no subsurface modifier.    " % ob.name)
        modname = mod.name

        startProgress("Apply Subsurf Modifier")
        coords = []
        drivers = []
        skeys = ob.data.shape_keys
        if skeys:
            # Store shapekey coordinates
            for skey in skeys.key_blocks:
                coord = [v.co.copy() for v in skey.data]
                coords.append((skey.name, coord))
            if skeys.animation_data:
                for fcu in skeys.animation_data.drivers:
                    drivers.append(Driver(fcu, True))
            # Remove shapekeys
            skeys = list(ob.data.shape_keys.key_blocks)
            skeys.reverse()
            for skey in skeys:
                ob.shape_key_remove(skey)

        # Duplicate object and apply subsurf modifier
        activateObject(context, ob)
        bpy.ops.object.duplicate()
        nob = context.object
        bpy.ops.object.modifier_apply(modifier=modname)
        nskeys = len(coords)

        # For each shapekey, duplicate shapekey and apply subsurf modifier.
        # Then create subsurfed shapekey
        idx = 0
        if coords:
            nob.shape_key_add(name=coords[0][0])
            for sname,coord in coords[1:]:
                idx += 1
                showProgress(idx, nskeys)
                print("Copy shapekey", sname)
                activateObject(context, ob)
                bpy.ops.object.duplicate()
                tob = context.object
                verts = tob.data.vertices
                for vn,co in enumerate(coord):
                    verts[vn].co = co
                bpy.ops.object.modifier_apply(modifier=modname)
                skey = nob.shape_key_add(name=sname)
                for vn,v in enumerate(tob.data.vertices):
                    skey.data[vn].co = v.co.copy()
                activateObject(context, tob)
                bpy.ops.object.delete(use_global=False)

        # Delete original object and activate the subsurfed one
        activateObject(context, ob)
        bpy.ops.object.delete(use_global=False)
        activateObject(context, nob)

        # Restore drivers
        nskeys = nob.data.shape_keys
        if nskeys:
            for driver in drivers:
                words = driver.data_path.split('"')
                if words[0] == "key_blocks[":
                    nskey = nskeys.key_blocks.get(words[1])
                    if nskey:
                        channel = driver.data_path.rsplit(".",1)[-1]
                        fcu = nskey.driver_add(channel)
                        driver.fill(fcu)

#-------------------------------------------------------------
#   Print statistics
#-------------------------------------------------------------

def printStatistics(ob):
    print(getStatistics(ob))


def getStatistics(ob):
    return ("Verts: %d, Edges: %d, Faces: %d" %
            (len(ob.data.vertices), len(ob.data.edges), len(ob.data.polygons)))


class DAZ_OT_PrintStatistics(bpy.types.Operator, IsMesh):
    bl_idname = "daz.print_statistics"
    bl_label = "Print Statistics"
    bl_description = "Display statistics for selected meshes"

    def draw(self, context):
        for line in self.lines:
            self.layout.label(text=line)

    def execute(self, context):
        return{'FINISHED'}

    def invoke(self, context, event):
        self.lines = []
        for ob in getSelectedMeshes(context):
            self.lines.append("Object: %s" % ob.name)
            self.lines.append("  " + getStatistics(ob))
        print("\n--------- Statistics ------------\n")
        for line in self.lines:
            print(line)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=450)

#-------------------------------------------------------------
#   Add mannequin
#   With improvements by ViSlArT, issue 756
#-------------------------------------------------------------

class DAZ_OT_AddMannequin(DazPropsOperator, IsMesh):
    bl_idname = "daz.add_mannequin"
    bl_label = "Add Mannequins"
    bl_description = "Add mannequins to selected meshes. Don't change rig after this."
    bl_options = {'UNDO'}

    headType : EnumProperty(
        items = [('SOLID', "Solid", "Solid head"),
                 ('JAW', "Jaw", "Head with jaws and eyes"),
                 ('FULL', "Full", "Head with all face bones"),
                 ],
        name = "Head Type",
        description = "How to make the mannequin head",
        default = 'JAW')

    useGroup : BoolProperty(
        name = "Add To Collection",
        description = "Add mannequin to collection",
        default = True)

    group : StringProperty(
        name = "Collection",
        description = "Add mannequin to this collection",
        default = "Mannequin")

    useNormals : BoolProperty(
        name = "Transfer Normals",
        description = "Transfer custom normals to mannequin meshes",
        default = False)

    useVertexGroups : BoolProperty(
        name = "Transfer Vertex Groups",
        description = "Transfer vertex groups to mannequin meshes",
        default = False)

    ignoreBoneGroups : BoolProperty(
        name = "Ignore Bone Groups",
        description = "Don't transfer bone vertex groups",
        default = False)

    threshold : FloatProperty(
        name = "Threshold",
        description = "Minimum vertex weight to keep",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 1e-3)

    useVertexColors : BoolProperty(
        name = "Transfer Vertex Colors",
        description = "Transfer vertex colors to mannequin meshes",
        default = False)

    useUvLayers : BoolProperty(
        name = "Transfer UV Layers",
        description = "Transfer UV layers to mannequin meshes",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "headType")
        self.layout.prop(self, "useGroup")
        self.layout.prop(self, "group")
        self.layout.prop(self, "useNormals")
        self.layout.prop(self, "useVertexGroups")
        if self.useVertexGroups:
            self.layout.prop(self, "ignoreBoneGroups")
            self.layout.prop(self, "threshold")
        self.layout.prop(self, "useVertexColors")
        self.layout.prop(self, "useUvLayers")


    def storeState(self, context):
        DazPropsOperator.storeState(self, context)
        self.meshes = []
        for ob in getSelectedMeshes(context):
            mod = getModifier(ob, 'NODES')
            if mod:
                self.meshes.append((ob, mod.show_viewport, mod.show_render))
                mod.show_viewport = mod.show_render = False


    def restoreState(self, context):
        DazPropsOperator.restoreState(self, context)
        for ob,viewport,render in self.meshes:
            mod = getModifier(ob, 'NODES')
            if mod:
                mod.show_viewport = viewport
                mod.show_render = render


    def run(self, context):
        obs,nobs,rig = self.addMannequins(context)
        if self.ignoreBoneGroups:
            bnames = rig.data.bones.keys()
        else:
            bnames = []
        for obname,ob in obs.items():
            self.transferData(context, ob, nobs[obname], bnames)


    def addMannequins(self, context):
        selected = getSelectedObjects(context)
        meshes = getSelectedMeshes(context)
        ob = context.object
        rig = ob.parent
        if not (rig and rig.type == 'ARMATURE'):
            raise DazError("Mesh %s has no armature parent" % ob)
        setActiveObject(context, rig)
        setMode('OBJECT')
        oldlayers = list(rig.data.layers)
        rig.data.layers = 32*[True]
        oldpose = rig.data.pose_position
        rig.data.pose_position = 'REST'

        # Create group/collection
        mangrp = None
        scn = context.scene
        coll = rigcoll = getCollection(context, rig)
        obs = {}
        nobs = {}
        if self.useGroup:
            from .hide import createSubCollection
            coll = createSubCollection(rigcoll, self.group)

        # Add mannequin objects for selected meshes
        for ob in meshes:
            obs[ob.name] = ob
            nobs[ob.name] = self.addMannequin(ob, context, rig, coll, mangrp)

        for ob in getSelectedObjects(context):
            if ob in selected:
                selectSet(ob, True)
            else:
                selectSet(ob, False)
        rig.data.layers = oldlayers
        rig.data.pose_position = oldpose
        return obs, nobs, rig


    def addMannequin(self, ob, context, rig, coll, mangrp):
        faceverts, vertfaces = getVertFaces(ob)
        majors = {}
        skip = []
        for vgrp in ob.vertex_groups:
            bone = rig.data.bones.get(vgrp.name)
            if bone and bone.use_deform:
                majors[vgrp.index] = []
            else:
                skip.append(vgrp.index)
        for v in ob.data.vertices:
            wmax = 1e-3
            vbest = None
            for g in v.groups:
                if g.weight > wmax and g.group not in skip:
                    wmax = g.weight
                    vbest = v
                    gbest = g.group
            if vbest is not None:
                majors[gbest].append(vbest)

        roots = [bone for bone in rig.data.bones if bone.parent is None]
        for bone in roots:
            self.remapBones(bone, ob.vertex_groups, majors, None)

        mob = ob.evaluated_get(context.evaluated_depsgraph_get())

        face_mats = dict()
        if ob.data.materials:
            for rnd in range(3, 8):
                face_mats[rnd] = dict()
                for f in mob.data.polygons:
                    try:
                        mat = ob.material_slots[f.material_index].material
                    except IndexError:
                        continue
                    nn = tuple(round(x, rnd) for x in f.normal)
                    face_mats[rnd][nn] = mat

        obverts = mob.data.vertices
        nobinfos = []
        self.defaultMaterial = None
        for vgrp in ob.vertex_groups:
            if (vgrp.name not in rig.pose.bones.keys() or
                vgrp.index not in majors.keys()):
                continue
            fnums = []
            for v in majors[vgrp.index]:
                for fn in vertfaces[v.index]:
                    fnums.append(fn)
            fnums = list(set(fnums))

            nverts = []
            nfaces = []
            for fn in fnums:
                f = ob.data.polygons[fn]
                nverts += f.vertices
                nfaces.append(f.vertices)
            if not nfaces:
                continue
            nverts = list(set(nverts))
            nverts.sort()

            bone = rig.data.bones[vgrp.name]
            head = bone.head_local
            verts = [obverts[vn].co-head for vn in nverts]
            assoc = dict([(vn,n) for n,vn in enumerate(nverts)])
            faces = []
            for fverts in nfaces:
                faces.append([assoc[vn] for vn in fverts])

            name = "%s_%s" % (ob.name[0:3], vgrp.name)
            me = bpy.data.meshes.new(name)
            me.from_pydata(verts, [], faces)
            nob = bpy.data.objects.new(name, me)
            coll.objects.link(nob)
            nob.location = head
            lockAllTransforms(nob)
            nobinfos.append((nob, rig, bone, me))

            if face_mats:
                for f in me.polygons:
                    for rnd in reversed(range(3, 8)):
                        fmat = face_mats[rnd].get(tuple(round(x, rnd) for x in f.normal))
                        if fmat:
                            break
                    else:
                        fmat = self.getDefaultMaterial(ob)
                    if fmat.name not in me.materials:
                        me.materials.append(fmat)
                    for (i, mat_i) in enumerate(nob.material_slots):
                        if mat_i.material == fmat:
                            f.material_index = i
                            break

        updateScene(context)

        from .node import setParent
        for nob, rig, bone, me in nobinfos:
            setParent(context, nob, rig, bone.name, update=False)
            nob.DazMannequin = True
            if mangrp:
                mangrp.objects.link(nob)
        return [nobinfo[0] for nobinfo in nobinfos]


    def getDefaultMaterial(self, ob):
        from random import random
        from .guess import getMaterialType
        if self.defaultMaterial is None:
            mat = bpy.data.materials.new("%s_Mannequin" % ob.name)
            self.defaultMaterial = mat
            mat.diffuse_color[0:3] = (random(), random(), random())
            for omat in ob.data.materials:
                if omat:
                    mat.diffuse_color = omat.diffuse_color
                    if getMaterialType(omat) == 'SKIN':
                        break
        return self.defaultMaterial


    def remapBones(self, bone, vgrps, majors, remap):
        special = {
            'SOLID' : ["head"],
            'JAW' : ["head", "lowerjaw", "leye", "reye"],
            'FULL' : []
              }
        if bone.name.lower() in special[self.headType]:
            if bone.name in vgrps.keys():
                remap = vgrps[bone.name].index
        elif remap is not None:
            if bone.name in vgrps.keys():
                gn = vgrps[bone.name].index
                if gn in majors.keys():
                    majors[remap] += majors[gn]
                    del majors[gn]
        for child in bone.children:
            self.remapBones(child, vgrps, majors, remap)


    def transferData(self, context, ob, nobs, bnames):
        print("Transfer data from %s to %d meshes" % (ob.name, len(nobs)))
        transfer = bpy.ops.object.data_transfer
        activateObject(context, ob)
        for nob in nobs:
            nob.select_set(True)

        if self.useNormals:
            for face in ob.data.polygons:
                if face.use_smooth:
                    bpy.ops.object.shade_smooth()
                    break
            if ob.data.use_auto_smooth:
                transfer(data_type='CUSTOM_NORMAL')
                for nob in nobs:
                    nob.data.use_auto_smooth = True

        if ob.vertex_groups and self.useVertexGroups:
            from .transfer import pruneVertexGroups
            transfer(data_type='VGROUP_WEIGHTS', layers_select_src='ALL', layers_select_dst='NAME')
            for nob in nobs:
                pruneVertexGroups(nob, self.threshold, bnames, False)
        if ob.data.vertex_colors and self.useVertexColors:
            transfer(data_type='VCOL', layers_select_src='ALL', layers_select_dst='NAME')
        if ob.data.uv_layers and self.useUvLayers:
            transfer(data_type='UV', layers_select_src='ALL', layers_select_dst='NAME')

#-------------------------------------------------------------
#   Add push
#-------------------------------------------------------------

class DAZ_OT_AddPush(DazOperator, IsMesh):
    bl_idname = "daz.add_push"
    bl_label = "Add Push"
    bl_description = "Add a push shapekey"
    bl_options = {'UNDO'}

    def run(self, context):
        hasShapeKeys = []
        for ob in getSelectedMeshes(context):
            #applyShapeKeys(ob)
            if ob.data.shape_keys:
                hasShapeKeys.append(ob)
            else:
                basic = ob.shape_key_add(name="Basic")
            skey = ob.shape_key_add(name="Push")
            scale = ob.DazScale
            for n,v in enumerate(ob.data.vertices):
                skey.data[n].co += v.normal*scale
        if hasShapeKeys:
            msg = ("Push added to meshes with shapekeys:\n  " + "\n  ".join([ob.name for ob in hasShapeKeys]))
            raise DazError(msg, True)

#-------------------------------------------------------------
#   Make deflection
#-------------------------------------------------------------

class DAZ_OT_MakeDeflection(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_deflection"
    bl_label = "Make Deflection"
    bl_description = "Make a low-poly deflection mesh for the active mesh"
    bl_options = {'UNDO'}

    offset : FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 5.0)

    useQuads : BoolProperty(
        name = "Quads",
        description = "Convert the deflector into a majority-quad mesh",
        default = True)

    useSubsurf : BoolProperty(
        name = "Subsurf",
        description = "Smooth the deflection mesh with a subsurf modifier",
        default = True)

    useShrinkwrap : BoolProperty(
        name = "Shrinkwrap",
        description = "Shrinkwrap the deflection mesh to the original mesh",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "offset")
        self.layout.prop(self, "useQuads")
        self.layout.prop(self, "useSubsurf")
        self.layout.prop(self, "useShrinkwrap")

    def storeState(self, context):
        scn = context.scene
        self.simplify = scn.render.use_simplify
        scn.render.use_simplify = False

    def restoreState(self, context):
        context.scene.render.use_simplify = self.simplify


    def run(self, context):
        ob = context.object
        fac = self.offset*0.1*ob.DazScale
        char = ob.DazMesh.lower()
        struct = AF.loadEntry(char, "lowpoly")
        vnums = struct["vertices"]
        verts = ob.data.vertices
        coords = [(verts[vn].co + fac*verts[vn].normal) for vn in vnums]
        #faces = struct["faces"]
        faces = ([(f[0],f[1],f[2]) for f in struct["faces"]] +
                 [(f[0],f[2],f[3]) for f in struct["faces"] if len(f) > 3])
        me = bpy.data.meshes.new(ob.data.name+"Deflect")
        me.from_pydata(coords, [], faces)
        nob = bpy.data.objects.new(ob.name+"Deflect", me)
        ncoll = bpy.data.collections.new(name=ob.name+"Deflect")
        ncoll.objects.link(nob)
        for coll in bpy.data.collections:
            if ob in coll.objects.values():
                coll.children.link(ncoll)
        nob.hide_render = True
        nob.show_wire = True
        nob.show_all_edges = True
        nob.parent = ob.parent

        vgrps = dict([(vgrp.index, vgrp) for vgrp in ob.vertex_groups])
        ngrps = {}
        for vgrp in ob.vertex_groups:
            ngrp = nob.vertex_groups.new(name=vgrp.name)
            ngrps[ngrp.index] = ngrp
        for nv in nob.data.vertices:
            v = ob.data.vertices[vnums[nv.index]]
            for g in v.groups:
                ngrp = ngrps[g.group]
                ngrp.add([nv.index], g.weight, 'REPLACE')

        mod = getModifier(ob, 'ARMATURE')
        if mod:
            nmod = nob.modifiers.new("Armature %s" % mod.name, 'ARMATURE')
            nmod.object = mod.object
            nmod.use_deform_preserve_volume = mod.use_deform_preserve_volume

        setActiveObject(context, nob)
        if self.useQuads:
            setMode('EDIT')
            bpy.ops.mesh.tris_convert_to_quads()
            setMode('OBJECT')
        if self.useSubsurf:
            mod = nob.modifiers.new("Subsurf", 'SUBSURF')
            mod.levels = 1
            bpy.ops.object.modifier_apply(modifier="Subsurf")
        if self.useShrinkwrap:
            mod = nob.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
            mod.wrap_method = 'NEAREST_SURFACEPOINT'
            mod.wrap_mode = 'ON_SURFACE'
            mod.target = ob
            bpy.ops.object.modifier_apply(modifier="Shrinkwrap")

#----------------------------------------------------------
#   Copy modifiers
#----------------------------------------------------------

class DAZ_OT_CopyModifiers(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_modifiers"
    bl_label = "Copy Modifiers"
    bl_description = "Copy modifiers from active mesh to selected"
    bl_options = {'UNDO'}

    offset : FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 5.0)

    useSubsurf : BoolProperty(
        name = "Use Subsurf",
        description = "Also copy subsurf and multires modifiers",
        default = False)

    useRemoveCloth : BoolProperty(
        name = "Remove Cloth",
        description = "Remove cloth modifiers from source mesh",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useSubsurf")
        self.layout.prop(self, "useRemoveCloth")

    def run(self, context):
        from .dforce import ModStore
        src = context.object
        stores = []
        for mod in list(src.modifiers):
            if (self.useSubsurf or
                mod.type not in ['SUBSURF', 'MULTIRES']):
                stores.append(ModStore(mod))
            if (self.useRemoveCloth and
                mod.type in ['COLLISION', 'CLOTH', 'SOFTBODY']):
                src.modifiers.remove(mod)
        for trg in getSelectedMeshes(context):
            if trg != src:
                trg.parent = src.parent
                for store in stores:
                    print("RES", store)
                    store.restore(trg)

#----------------------------------------------------------
#   Make custom shapes from mesh
#----------------------------------------------------------

class WidgetConverter:
    usedLayer = 4
    unusedLayer = 5
    deleteUnused = True

    def convertWidgets(self, context, rig, ob):
        from .node import createHiddenCollection
        if rig is None or not rig.type == 'ARMATURE':
            raise DazError("Object has no armature parent")

        coll = context.scene.collection
        hidden = createHiddenCollection(context, rig)
        rig.data.layers[self.usedLayer-1] = True
        rig.data.layers[self.unusedLayer-1] = False
        self.usedLayers = (self.usedLayer-1)*[False] + [True] + (32-self.usedLayer)*[False]
        self.unusedLayers = (self.unusedLayer-1)*[False] + [True] + (32-self.unusedLayer)*[False]
        activateObject(context, ob)

        vgnames,vgverts,vgfaces = self.getVertexGroupMesh(ob)
        euler = Euler((0,180*D,90*D))
        mat = euler.to_matrix()*(1.0/rig.DazScale)
        self.gizmos = []
        for idx,verts in vgverts.items():
            if not verts:
                continue
            verts = self.transform(verts, mat)
            faces = vgfaces[idx]
            key = vgnames[idx]
            gname = "GZM_"+key
            me = bpy.data.meshes.new(gname)
            me.from_pydata(verts, [], faces)
            gzm = bpy.data.objects.new(gname, me)
            self.gizmos.append((key,gzm))
            coll.objects.link(gzm)
            hidden.objects.link(gzm)
            gzm.select_set(True)

        self.removeInteriors(context)

        activateObject(context, rig)
        setMode('EDIT')
        for bname,gzm in self.gizmos:
            if bname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bname]
                eb.use_deform = False

        setMode('OBJECT')
        self.drivers = {}
        self.getDrivers(rig)
        self.getDrivers(rig.data)
        self.unused = {}
        for bname,gzm in self.gizmos:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                pb.custom_shape = gzm
                pb.bone.show_wire = True
                self.assignLayer(pb, rig)
                if len(pb.children) == 1:
                    self.inheritLimits(pb, pb.children[0], rig)
            coll.objects.unlink(gzm)
        unlinkAll(ob, False)

        if self.deleteUnused:
            activateObject(context, rig)
            setMode('EDIT')
            for bname in self.unused.keys():
                eb = rig.data.edit_bones[bname]
                rig.data.edit_bones.remove(eb)
            setMode('OBJECT')


    def inheritLimits(self, pb, pb2, rig):
        if pb2.name.startswith(pb.name):
            from .fix import copyConstraints
            pb.lock_location = pb2.lock_location
            pb.lock_rotation = pb2.lock_rotation
            if getConstraint(pb2, 'LIMIT_LOCATION'):
                copyConstraints(pb2, pb, rig)


    def getVertexGroupMesh(self, ob):
        vgnames = dict([(vg.index, vg.name) for vg in ob.vertex_groups])
        vgverts = dict([(vg.index, []) for vg in ob.vertex_groups])
        vgfaces = dict([(vg.index, []) for vg in ob.vertex_groups])
        vgroups = {}
        assoc = {}
        for v in ob.data.vertices:
            grps = [(g.weight,g.group) for g in v.groups]
            if len(grps) != 1:
                raise DazError("Not a custom shape mesh")
            grps.sort()
            idx = grps[-1][1]
            assoc[v.index] = len(vgverts[idx])
            vgverts[idx].append(v.co)
            vgroups[v.index] = idx
        for f in ob.data.polygons:
            idx = vgroups[f.vertices[0]]
            nf = [assoc[vn] for vn in f.vertices]
            vgfaces[idx].append(nf)
        return vgnames, vgverts, vgfaces


    def transform(self, verts, mat):
        vsum = Vector((0,0,0))
        for co in verts:
            vsum += co
        ave = vsum/len(verts)
        verts = [mat@(co-ave) for co in verts]
        return verts


    def removeInteriors(self, context):
        from .tables import getVertEdges, getEdgeFaces
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        for _bname,ob in self.gizmos:
            vertedges = getVertEdges(ob)
            edgefaces = getEdgeFaces(ob, vertedges)
            verts = ob.data.vertices
            for v in verts:
                v.select = True
            for e in ob.data.edges:
                if len(edgefaces[e.index]) <= 1:
                    vn1,vn2 = e.vertices
                    verts[vn1].select = False
                    verts[vn2].select = False
        setMode('EDIT')
        bpy.ops.mesh.delete(type='VERT')
        setMode('OBJECT')


    def getDrivers(self, rna):
        if not (rna and rna.animation_data):
            return
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                if var.type == 'TRANSFORMS':
                    for trg in var.targets:
                        bname = baseBone(trg.bone_target)
                        if bname not in self.drivers.keys():
                            self.drivers[bname] = []
                        self.drivers[bname].append(fcu)


    def assignLayer(self, pb, rig):
        if pb.name in self.drivers.keys() or len(pb.children) > 3:
            pb.bone.layers = self.usedLayers
            if not pb.custom_shape:
                self.modifyDriver(pb, rig)
        elif isDrvBone(pb.name) or isFinal(pb.name):
            bname = baseBone(pb.name)
            if bname not in self.drivers.keys():
                self.unused[pb.name] = True
        else:
            pb.bone.layers = self.unusedLayers
            if pb.name not in self.drivers.keys():
                self.unused[pb.name] = True
        for child in pb.children:
            self.assignLayer(child, rig)


    def modifyDriver(self, pb, rig):
        bname = pb.name
        if bname[-2] == "-" and bname[-1].isdigit():
            self.replaceDriverTarget(bname, bname[:-2], rig)
        self.unused[bname] = True
        pb.bone.layers = self.unusedLayers
        if bname not in self.drivers.keys():
            return
        for fcu in self.drivers[bname]:
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[":
                pb1 = rig.pose.bones[words[1]]
                channel = words[-1].rsplit(".",1)[-1]
                pb1.driver_remove(channel, fcu.array_index)


    def replaceDriverTarget(self, bname, bname1, rig):
        if bname1 in rig.pose.bones.keys():
            pb1 = rig.pose.bones[bname1]
            pb1.bone.layers = self.usedLayers
            self.drivers[bname1] = []
            if bname1 in self.unused.keys():
                del self.unused[bname1]
            for fcu in self.drivers[bname]:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        if trg.bone_target == bname:
                            trg.bone_target = bname1


class DAZ_OT_ConvertWidgets(WidgetConverter, DazPropsOperator, IsMesh):
    bl_idname = "daz.convert_widgets"
    bl_label = "Convert To Widgets"
    bl_description = "Convert the active mesh to custom shapes for the parent armature bones"
    bl_options = {'UNDO'}

    usedLayer : IntProperty(
        name = "Used Layer",
        description = "Bone layer for bones with shapekeys",
        min = 1, max = 32,
        default = 4)

    unusedLayer : IntProperty(
        name = "Unused Layer",
        description = "Bone layer for bones without shapekeys",
        min = 1, max = 32,
        default = 5)

    deleteUnused : BoolProperty(
        name = "Delete Unused",
        description = "Delete unused bones",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "usedLayer")
        self.layout.prop(self, "unusedLayer")
        self.layout.prop(self, "deleteUnused")

    def run(self, context):
        ob = context.object
        rig = ob.parent
        self.convertWidgets(context, rig, ob)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_FindPolys,
    DAZ_OT_MakeQuickProxy,
    DAZ_OT_MakeFaithfulProxy,
    DAZ_OT_Quadify,
    DAZ_OT_SplitNgons,
    DAZ_OT_FindSeams,
    DAZ_OT_SelectRandomStrands,
    DAZ_OT_SelectStrandsByWidth,
    DAZ_OT_SelectStrandsBySize,
    DAZ_OT_ApplyMorphs,
    DAZ_OT_ApplySubsurf,
    DAZ_OT_PrintStatistics,
    DAZ_OT_AddMannequin,
    DAZ_OT_AddPush,
    DAZ_OT_MakeDeflection,
    DAZ_OT_CopyModifiers,
    DAZ_OT_ConvertWidgets,
]

def register():
    bpy.types.Object.DazMannequin = BoolProperty(default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)




