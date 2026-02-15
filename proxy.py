# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from mathutils import Vector, Euler, Matrix
from .error import *
from .tables import *
from .utils import *
from .driver import DriverUser

#-------------------------------------------------------------
#   Find polys
#-------------------------------------------------------------

def findPolys(context):

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

#-------------------------------------------------------------
#   Make faithful proxy
#-------------------------------------------------------------

class Proxifier(DriverUser):
    def __init__(self, ob):
        self.initTmp()
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

        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        self.dirty = dict([(f.index, f.hide) for f in ob.data.polygons])
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
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
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
        from .geometry import makeNewUvLayer

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
        uvloop = makeNewUvLayer(me, "Uvloop", True)
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
                    setModernProps(mat)
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
            if mindist > 1e-4*GS.scale:
                pco = pxy.data.vertices[pvn]
                co = hum.data.vertices[vn]
                print("DIST", pvn, vn, pco, co, mindist)
    return humPxy, pxyHum

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

#-------------------------------------------------------------
#   Select parent verts
#-------------------------------------------------------------

class DAZ_OT_SelectParentVerts(DazOperator):
    bl_idname = "daz.select_parent_verts"
    bl_label = "Select Parent Vertices"
    bl_description = "Select parent vertices"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.parent and ob.parent_type.startswith('VERTEX'))

    def run(self, context):
        ob = context.object
        mesh = ob.parent
        if activateObject(context, mesh):
            setMode('EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            setMode('OBJECT')
            for vn in ob.parent_vertices:
                mesh.data.vertices[vn].select = True

    def sequel(self, context):
        setMode('EDIT')

#-------------------------------------------------------------
#   Print statistics
#-------------------------------------------------------------

def printStatistics(ob):
    print(getStatistics(ob))


def getStatistics(ob):
    nskeys = ( len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0)
    return ("Verts: %d, Edges: %d, Faces: %d, Shapekeys: %d, Vgroups: %d" %
            (len(ob.data.vertices), len(ob.data.edges), len(ob.data.polygons), nskeys, len(ob.vertex_groups)))


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

#----------------------------------------------------------
#   Make custom shapes from mesh
#----------------------------------------------------------

class WidgetConverter:
    deleteUnused = True

    def convertWidgets(self, context, rig, ob, wrig):
        from .node import createHiddenCollection
        if rig is None or not rig.type == 'ARMATURE':
            raise DazError("Object has no armature parent")

        coll = context.scene.collection
        hidden = createHiddenCollection(context, rig)
        activateObject(context, ob)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

        vgnames,vgverts,vgfaces = self.getVertexGroupMesh(ob)
        euler = Euler((0,180*D,90*D))
        factor = 1/GS.scale
        mat = factor*euler.to_matrix()
        self.gizmos = []
        for idx,verts in vgverts.items():
            if not verts:
                continue
            bone = rig.data.bones.get(vgnames[idx])
            verts = self.transform(verts, mat, bone)
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
            eb = rig.data.edit_bones.get(bname)
            if eb:
                eb.use_deform = False

        setMode('OBJECT')
        self.drivers = {}
        self.getDrivers(rig)
        self.getDrivers(rig.data)
        self.unused = {}
        for bname,gzm in self.gizmos:
            pb = rig.pose.bones.get(bname)
            if pb:
                pb.custom_shape = gzm
                scale = GS.scale / pb.bone.length
                setCustomShapeTransform(pb, scale)
                pb.bone.show_wire = True
                self.assignLayer(pb, rig)
                if len(pb.children) == 1:
                    self.inheritLimits(pb, pb.children[0], rig)
            coll.objects.unlink(gzm)
        unlinkAll(ob, False)

        enableRigNumLayer(rig, T_WIDGETS)
        enableRigNumLayer(rig, T_HIDDEN, False)
        if self.deleteUnused:
            activateObject(context, rig)
            setMode('EDIT')
            for bname in self.unused.keys():
                eb = rig.data.edit_bones[bname]
                rig.data.edit_bones.remove(eb)
            setMode('OBJECT')
        else:
            for bname in self.unused.keys():
                bone = rig.data.bones[bname]
                bone.use_deform = False
                enableBoneNumLayer(bone, rig, T_HIDDEN)


    def inheritLimits(self, pb, pb2, rig):
        if pb2.name.startswith(pb.name):
            from .store import copyConstraints
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
            if len(grps) < 1:
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


    def transform(self, verts, mat, bone):
        if False and bone:
            center = Vector(bone.head_local)
        else:
            vsum = Vector((0,0,0))
            for co in verts:
                vsum += co
            center = vsum/len(verts)
        verts = [mat@(co-center) for co in verts]
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
            enableBoneNumLayer(pb.bone, rig, T_WIDGETS)
            if not pb.custom_shape:
                self.modifyDriver(pb, rig)
        elif isDrvBone(pb.name) or isFinal(pb.name):
            bname = baseBone(pb.name)
            if bname not in self.drivers.keys():
                self.unused[pb.name] = True
        else:
            enableBoneNumLayer(pb.bone, rig, T_HIDDEN)
            if pb.name not in self.drivers.keys():
                self.unused[pb.name] = True
        for child in pb.children:
            self.assignLayer(child, rig)


    def modifyDriver(self, pb, rig):
        bname = pb.name
        if bname[-2] == "-" and bname[-1].isdigit():
            self.replaceDriverTarget(bname, bname[:-2], rig)
        self.unused[bname] = True
        enableBoneNumLayer(pb.bone, rig, T_HIDDEN)
        if bname not in self.drivers.keys():
            return
        for fcu in self.drivers[bname]:
            bname,channel,cnsname = getBoneChannel(fcu)
            if bname:
                pb1 = rig.pose.bones[bname]
                pb1.driver_remove(channel, fcu.array_index)


    def replaceDriverTarget(self, bname, bname1, rig):
        if bname1 in rig.pose.bones.keys():
            pb1 = rig.pose.bones[bname1]
            enableBoneNumLayer(pb1.bone, rig, T_WIDGETS)
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

    deleteUnused : BoolProperty(
        name = "Delete Unused",
        description = "Delete unused bones.\nIf disabled, unused bones are hidden",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "deleteUnused")

    def run(self, context):
        ob = context.object
        rig = ob.parent
        self.convertWidgets(context, rig, ob, rig)

#------------------------------------------------------------------------
#   Collections
#------------------------------------------------------------------------

def createSubCollection(coll, cname):
    def getSubColl(coll, cname):
        for child in coll.children:
            if child.name == cname:
                return child
        for child in coll.children:
            subcoll = getSubColl(child, cname)
            if subcoll:
                return subcoll
        return None

    subcoll = getSubColl(coll, cname)
    if subcoll:
        return subcoll
    subcoll = bpy.data.collections.new(cname)
    coll.children.link(subcoll)
    return subcoll

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SelectParentVerts,
    DAZ_OT_PrintStatistics,
    DAZ_OT_ConvertWidgets,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)




