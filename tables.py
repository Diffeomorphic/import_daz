# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

def getVertFaces(ob, verts=None, faces=None, faceverts=None):
    if verts is None:
        verts = range(len(ob.data.vertices))
    if faces is None:
        faces = range(len(ob.data.polygons))
    if faceverts is None:
        faceverts = [list(f.vertices) for f in ob.data.polygons]
    vertfaces = dict([(vn,[]) for vn in verts])
    for fn in faces:
        for vn in faceverts[fn]:
            vertfaces[vn].append(fn)
    return faceverts, vertfaces


def getVertEdges(ob):
    nverts = len(ob.data.vertices)
    vertedges = dict([(vn,[]) for vn in range(nverts)])
    for e in ob.data.edges:
        for vn in e.vertices:
            vertedges[vn].append(e)
    return vertedges


def otherEnd(vn, e):
    vn1,vn2 = e.vertices
    if vn == vn1:
        return vn2
    else:
        return vn1


def getEdgeFaces(ob, vertedges):
    nedges = len(ob.data.edges)
    edgefaces = dict([(en,[]) for en in range(nedges)])
    for f in ob.data.polygons:
        for vn1,vn2 in f.edge_keys:
            for e in vertedges[vn1]:
                if vn2 in e.vertices:
                    en = e.index
                    edgefaces[en].append(f.index)
    return edgefaces


def getConnectedVerts(ob):
    nverts = len(ob.data.vertices)
    connected = dict([(vn,[]) for vn in range(nverts)])
    for e in ob.data.edges:
        vn1,vn2 = e.vertices
        connected[vn1].append(vn2)
        connected[vn2].append(vn1)
    return connected


def findNeighbors(faces, faceverts, vertfaces):
    neighbors = dict([(fn,[]) for fn in faces])
    for fn1 in faces:
        for v1n in faceverts[fn1]:
            for fn2 in vertfaces[v1n]:
                if (fn2 == fn1 or
                    fn2 in neighbors[fn1]):
                    continue
                for v2n in faceverts[fn2]:
                    if (v1n != v2n and
                        fn1 in vertfaces[v2n]):
                        if fn2 not in neighbors[fn1]:
                            neighbors[fn1].append(fn2)
                        if fn1 not in neighbors[fn2]:
                            neighbors[fn2].append(fn1)

    return neighbors


def findEdgeNeighbors(ob):
    neighbors = dict([(e.index,[]) for e in ob.data.edges])
    vertEdges = getVertEdges(ob)
    for vn,edges in vertEdges.items():
        if len(edges) == 2:
            e1,e2 = edges
            neighbors[e1.index].append(e2.index)
            neighbors[e2.index].append(e1.index)
    return neighbors

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def findTexVerts(ob, vertfaces):
    nfaces = len(ob.data.polygons)
    touches = dict([(fn,[]) for fn in range(nfaces)])
    for f1 in ob.data.polygons:
        fn1 = f1.index
        for vn in f1.vertices:
            for fn2 in vertfaces[vn]:
                if fn1 != fn2:
                    touches[fn1].append(fn2)

    uvs = ob.data.uv_layers.active.data
    uvindices = {}
    m = 0
    for f in ob.data.polygons:
        nv = len(f.vertices)
        uvindices[f.index] = range(m, m+nv)
        m += nv

    texverts = {}
    texfaces = {}
    vt = 0
    vts = {}
    for fn1 in range(nfaces):
        texfaces[fn1] = texface = []
        touches[fn1].sort()
        for m1 in uvindices[fn1]:
            test = False
            matched = False
            uv1 = uvs[m1].uv
            for fn2 in touches[fn1]:
                if fn2 < fn1:
                    for m2 in uvindices[fn2]:
                        uv2 = uvs[m2].uv
                        if (uv1-uv2).length < 2e-4:
                            if m2 < m1:
                                vts[m1] = vts[m2]
                            else:
                                vts[m2] = vts[m1]
                            matched = True
                            #break
            if not matched:
                vts[m1] = vt
                texverts[vt] = uvs[m1].uv
                vt += 1
            texface.append(vts[m1])
    return texverts, texfaces
