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

import math
from mathutils import Vector, Matrix
import os
import bpy
import bmesh
from collections import OrderedDict
from .asset import Asset, normalizeRef
from .channels import Channels
from .utils import *
from .error import *
from .node import Node, Instance, SimNode
from .fileutils import SingleFile, DazFile, DazExporter

#-------------------------------------------------------------
#   Geonode
#-------------------------------------------------------------

class GeoNode(Node, SimNode):
    def __init__(self, figure, geo, ref, etype):
        if figure.caller:
            fileref = figure.caller.fileref
        else:
            fileref = figure.fileref
        Node.__init__(self, fileref)
        self.id = normalizeRef(ref)
        self.etype = etype
        if isinstance(geo, Geometry):
            geo.caller = self
            geo.nodes[self.id] = self
        elif isinstance(geo, UnGeometry):
            if GS.verbosity >= 3:
                print("UnGeometry: %s %s" % (self.id, etype))
        elif geo is None:
            if GS.verbosity >= 3:
                print("Geometry is None: %s %s" % (self.id, etype))
        else:
            msg = ("Not a geometry:\n%s" % geo)
            reportError(msg)
        self.data = geo
        self.figure = figure
        self.figureInst = None
        self.verts = None
        self.edges = []
        self.faces = []
        self.materials = OrderedDict()
        self.hairMaterials = []
        self.isStrandHair = False
        self.properties = {}
        self.polylines = []
        self.polyline_materials = []
        self.highdef = None
        self.hdobject = None
        self.hdType = 'NONE'
        self.index = figure.count
        self.modifiers = {}
        self.morphsValues = {}
        self.isShell = False
        self.shellGeos = []
        self.shellPrefix = ""
        self.push = 0
        self.assigned = False
        SimNode.__init__(self)


    def __repr__(self):
        return ("<GeoNode %s %d M:%d C: %s R: %s>" % (self.id, self.index, len(self.materials), self.center, self.rna))

    def errorWrite(self, ref, fp):
        fp.write('   G: %s\n' % (self))

    def isVisibleMaterial(self, dmat):
        if isinstance(self.data, Geometry):
            return self.data.isVisibleMaterial(dmat)
        return True

    def getRig(self):
        ob = self.rna
        if ob and ob.parent and ob.parent.type == 'ARMATURE':
            return ob.parent
        return None

    def preprocess(self, context, inst):
        if isinstance(self.data, Geometry):
            self.data.preprocess(context, inst)
        elif inst.isStrandHair:
            geo = self.data = Geometry(self.fileref)
            geo.name = inst.name
            geo.isStrandHair = True
            geo.preprocess(context, inst)


    def buildObject(self, context, inst, center):
        Node.buildObject(self, context, inst, center)


    def getObjectName(self, inst):
        from .figure import Figure
        if isinstance(self.figure, Figure):
            return "%s Mesh" % inst.name
        else:
            return inst.name


    def buildShells(self, context):
        if not self.shellGeos:
            return
        from .geonodes import makeShell, makeShellModifier
        ob = self.rna
        activateObject(context, ob)
        mats = [dmat.rna for dmat in self.materials.values()]
        print('Build %d shells for "%s" with prefix "%s"' % (len(self.shellGeos), ob.name, self.shellPrefix))
        for shgeonode,visibles in self.shellGeos:
            mnames = []
            mats = []
            shmats = []
            for mname,dmat in self.materials.items():
                shname = "%s%s" % (self.shellPrefix, mname)
                if shname in shgeonode.materials.keys() and visibles[shname]:
                    mnames.append(mname)
                    mats.append(dmat.rna)
                    shmat = shgeonode.materials[shname]
                    shmats.append(shmat.rna)

            if shgeonode.rna:
                shell = shgeonode.rna
            else:
                shell = makeShell(shgeonode.name, shmats, ob)
                shgeonode.rna = shell
            offset = LS.scale * shgeonode.push
            makeShellModifier(shell, ob, offset, mnames, mats, shmats)


    def addLSMesh(self, ob, inst, rigname):
        if self.assigned:
            return
        elif inst.isStrandHair:
            LS.hairs[rigname].append(ob)
        else:
            LS.meshes[rigname].append(ob)
        self.assigned = True


    def subtractCenter(self, ob, inst, center):
        if not LS.fitFile:
            ob.location = -center
        inst.center = center


    def subdivideObject(self, ob, inst, context):
        if not isinstance(self.data, Geometry):
            return
        if self.highdef:
            from .finger import getFingerPrint
            me = self.buildHDMesh(ob)
            hdob = bpy.data.objects.new(ob.name + "_HD", me)
            self.hdobject = inst.hdobject = hdob
            LS.hdmeshes[LS.rigname].append(hdob)
            hdob.DazVisibilityDrivers = ob.DazVisibilityDrivers
            self.addHDMaterials(ob.data.materials, "")
            center = Vector((0,0,0))
            self.arrangeObject(hdob, inst, context, center)
            if not GS.useMultiUvLayers:
                self.addHDUvs(ob, hdob)
            self.hdType = 'HIGHDEF'
            if GS.useMultires and hdob.data.polygons:
                self.hdType = addMultires(context, ob, hdob, False)
            if self.hdType == 'MULTIRES':
                if GS.useMultiUvLayers:
                    copyUvLayers(ob, hdob)
            elif self.hdType == 'NONE':
                print("HD mesh same as base mesh:", ob.name)
                self.hdobject = inst.hdobject = None
                deleteObjects(context, [hdob])
            elif self.hdType == 'HIGHDEF' and GS.useMultiUvLayers:
                self.addHDUvs(ob, hdob)
        elif LS.useHDObjects:
            self.hdobject = inst.hdobject = ob

        if ob and self.data:
            self.data.buildRigidity(ob)
            if self.hdType == 'MULTIRES':
                self.data.buildRigidity(self.hdobject)

        renderLevel = 0
        subDLevel = 0
        if self.materials:
            subDLevel = max([dmat.getSubDLevel(0) for dmat in self.materials.values()])
            subDLevel = min(subDLevel, GS.maxSubdivs)
        if (self.type == "subdivision_surface" and
            self.data and
            (self.data.SubDIALevel > 0 or self.data.SubDRenderLevel > 0 or subDLevel > 0)):
            mod = ob.modifiers.new("Subsurf", 'SUBSURF')
            renderLevel = max(self.data.SubDIALevel + self.data.SubDRenderLevel, subDLevel)
            renderLevel = min(renderLevel, GS.maxSubdivs)
            mod.render_levels = renderLevel
            mod.levels = min(self.data.SubDIALevel, GS.maxSubdivs)
            if hasattr(mod, "use_limit_surface"):
                mod.use_limit_surface = False
            if self.data.SubDEdgeInterpolateLevel == 1:
                # [ "Soft Corners And Edges", "Sharp Edges and Corners", "Sharp Edges" ]
                try:
                    mod.boundary_smooth = 'PRESERVE_CORNERS'
                except AttributeError:
                    pass
            self.data.creaseEdges(context, ob)
            ob.data.use_auto_smooth = False
        if False and subDLevel > renderLevel:
            mod = ob.modifiers.new("SubD Displacement", 'SUBSURF')
            mod.subdivision_type = 'SIMPLE'
            mod.levels = 0
            mod.render_levels = subDLevel - renderLevel


    def addMappings(self, selmap):
        self.data.mappings = dict([(key,val) for val,key in selmap["mappings"]])


    def buildHDMesh(self, ob):
        verts = self.highdef.verts
        edges = []
        faces = self.stripNegatives([f[0] for f in self.highdef.faces])
        mnums = [f[4] for f in self.highdef.faces]
        nverts = len(verts)
        me = bpy.data.meshes.new(ob.data.name + "_HD")
        print("Build HD mesh for %s: %d verts, %d faces, %d edges" % (ob.name, nverts, len(faces), len(edges)))
        me.from_pydata(verts, edges, faces)
        print("HD mesh %s built" % me.name)
        for f in me.polygons:
            f.material_index = mnums[f.index]
            f.use_smooth = True
        self.data.setHairType(me)
        self.data.validateMesh(me)
        return me


    def addHDUvs(self, ob, hdob):
        uvs = self.highdef.uvs
        if not uvs:
            if hdob.name not in LS.hdUvMissing:
                LS.hdUvMissing.append(hdob.name)
            return
        uvfaces = self.stripNegatives([f[1] for f in self.highdef.faces])
        if len(ob.data.uv_layers) > 0:
            uvname = ob.data.uv_layers[0].name
        else:
            uvname = "UV Layer"
        uvlayer = makeNewUvLayer(hdob.data, uvname, True)
        if len(uvs) > len(uvlayer.data):
            print("%s has too many UVs: %d > %d" % (hdob.name, len(uvs), len(uvlayer.data)))
            LS.hdUvMismatch.append(hdob.name)
            return
        m = 0
        for f in uvfaces:
            for vn in f:
                uvlayer.data[m].uv = uvs[vn]
                m += 1


    def addHDMaterials(self, mats, prefix):
        for mat in mats:
            pg = self.hdobject.data.DazHDMaterials.add()
            pg.name = prefix + mat.name.rsplit("-",1)[0]
            pg.text = mat.name
        if self.data and self.data.vertex_pairs:
            # Geograft
            insts = []
            for inst in self.figure.instances.values():
                if (inst and
                    inst.parent and
                    inst.parent.geometries and
                    inst not in insts):
                    insts.append(inst)
                    par = inst.parent.geometries[0]
                    if par and par.hdobject and par.hdobject != par.rna:
                        par.addHDMaterials(mats, inst.name + "?" + prefix)


    def stripNegatives(self, faces):
        return [(f if f[-1] >= 0 else f[:-1]) for f in faces]


    def finalize(self, context, inst):
        from .material import sortMaterialsByName
        geo = self.data
        ob = self.rna
        if ob is None:
            return
        if self.hairMaterials:
            for dmat in self.hairMaterials:
                if dmat.rna:
                    ob.data.materials.append(dmat.rna)
        hdob = self.hdobject
        if hdob:
            self.finishHD(context, self.rna, hdob, inst)
        if ob.type == 'MESH':
            if GS.usePruneNodes:
                pruneUvMaps(ob)
            for mnum,dmat in enumerate(self.materials.values()):
                if dmat:
                    dmat.correctEmitArea(ob, mnum)
            scaleEyeMoisture(ob)
            if GS.useMaterialsByName:
                sortMaterialsByName(ob)
            if hdob and hdob != ob:
                if GS.usePruneNodes:
                    pruneUvMaps(hdob)
                scaleEyeMoisture(hdob)
                if GS.useMaterialsByName:
                    sortMaterialsByName(hdob)
            if GS.shellMethod == 'GEONODES':
                self.buildShells(context)
        if LS.fitFile and ob.type == 'MESH':
            shiftMesh(ob, inst.worldmat.inverted())
            if hdob and hdob != ob:
                shiftMesh(hdob, inst.worldmat.inverted())
        if hdob and not GS.keepBaseMesh:
            if hdob == ob:
                if hdob.name in LS.collection.objects:
                    LS.collection.objects.unlink(hdob)
                hdob.name = "%s_HD" % ob.name
                LS.hdmeshes[LS.rigname].append(hdob)
            else:
                unlinkAll(ob, True)
            if hdob.parent and hdob.parent.name in LS.collection.objects:
                LS.collection.objects.unlink(hdob.parent)


    def finishHD(self, context, ob, hdob, inst):
        from .finger import getFingerPrint
        if self.hdType in ['HIGHDEF','MULTIRES']:
            self.copyHDMaterials(ob, hdob, context, inst)
        hdob.parent = ob.parent
        hdob.parent_type = ob.parent_type
        hdob.parent_bone = ob.parent_bone
        setWorldMatrix(hdob, ob.matrix_world)
        if LS.hdcollection is None:
            from .main import makeRootCollection
            LS.hdcollection = makeRootCollection(LS.collection.name + "_HD", context)
        if hdob.name in LS.hdcollection.objects:
            print("DUPHD", hdob.name)
            return
        LS.hdcollection.objects.link(hdob)
        if hdob.parent and hdob.parent.name not in LS.hdcollection.objects:
            LS.hdcollection.objects.link(hdob.parent)
        hdob.data.DazFingerPrint = getFingerPrint(hdob)
        if hdob.data.DazFingerPrint == ob.data.DazFingerPrint:
            hdob.DazMesh = ob.DazMesh
        if hdob == ob:
            return
        setWorldMatrix(hdob, ob.matrix_world)
        if hdob.name in inst.collection.objects:
            inst.collection.objects.unlink(hdob)


    def postbuild(self, context, inst):
        ob = self.rna
        hdob = self.hdobject
        if ob:
            self.setHideInfoMesh(ob)
            if hdob and hdob != ob:
                self.setHideInfoMesh(hdob)
            self.addLSMesh(ob, inst, None)
            for extra in self.extra:
                for favo in extra.get("favorites", []):
                    item = ob.data.DazFavorites.add()
                    item.name = favo


    def copyHDMaterials(self, ob, hdob, context, inst):
        def getDataMaterial(mname):
            while True:
                for mat in LS.materials.values():
                    if baseName(mat.name):
                        return mat
                words = mname.split("_",1)
                if len(words) == 1:
                    return None
                mname = words[1]

        def fixHDMaterial(mat, uvmap):
            keep = True
            for node in mat.node_tree.nodes:
                if node.type in ['UVMAP', 'ATTRIBUTE', 'NORMAL_MAP']:
                    keep = False
                    break
            if keep:
                return mat
            else:
                nmat = mat.copy()
                for node in nmat.node_tree.nodes:
                    if node.type in ['UVMAP', 'ATTRIBUTE', 'NORMAL_MAP']:
                        node.uv_map = uvmap
                return nmat

        uvmap = None
        useMulti = (getModifier(hdob, 'MULTIRES') and GS.useMultiUvLayers)
        if not useMulti and len(ob.data.uv_layers) > 1:
            if hdob.data.uv_layers:
                uvmap = hdob.data.uv_layers[0].name
            elif hdob.name not in LS.hdUvMissing:
                LS.hdUvMissing.append(hdob.name)
        matnames = dict([(pg.name,pg.text) for pg in hdob.data.DazHDMaterials])
        for mn,mname in enumerate(self.highdef.matgroups):
            mat = None
            if mname in matnames.keys():
                mname = matnames[mname]
            if mname in LS.materials.keys():
                mat = LS.materials[mname]
            else:
                mat = getDataMaterial(mname)
            if uvmap and mat:
                mat = fixHDMaterial(mat, uvmap)
            hdob.data.materials.append(mat)
        inst.parentObject(context, self.hdobject)


    def setHideInfoMesh(self, ob):
        geo = self.data
        if ob.data is None:
            return
        ob.data.DazVertexCount = geo.vertex_count
        if geo.hidden_polys:
            hgroup = ob.data.DazMaskGroup
            for fn in geo.hidden_polys:
                elt = hgroup.add()
                elt.a = fn
        if geo.vertex_pairs:
            ggroup = ob.data.DazGraftGroup
            for vn,pvn in geo.vertex_pairs:
                pair = ggroup.add()
                pair.a = vn
                pair.b = pvn


    def hideVertexGroups(self, hidden):
        if self.data is None:
            return
        fnums = self.data.getPolyGroup(hidden)
        self.data.hidePolyGroup(self.rna, fnums)
        if self.hdobject and self.hdobject != self.rna:
            self.data.hidePolyGroup(self.hdobject.rna, fnums)


def shiftMesh(ob, mat):
    from .node import isUnitMatrix
    if isUnitMatrix(mat):
        return
    for v in ob.data.vertices:
        v.co = mat @ v.co


def scaleEyeMoisture(ob):
    if GS.useScaleEyeMoisture and ob.DazMesh:
        mdict = {}
        for mn,mat in enumerate(ob.data.materials):
            if mat.name.lower().startswith(("eyemoisture", "eyereflection")):
                for f in ob.data.polygons:
                    if f.material_index == mn:
                        for vn in f.vertices:
                            mdict[vn] = True
                break
        if mdict:
            if "lEye" in ob.vertex_groups.keys():
                lgn = ob.vertex_groups["lEye"].index
            else:
                return
            if "rEye" in ob.vertex_groups.keys():
                rgn = ob.vertex_groups["rEye"].index
            else:
                return
            lmoist = []
            rmoist = []
            for vn in mdict.keys():
                v = ob.data.vertices[vn]
                for g in v.groups:
                    if g.group == lgn:
                        lmoist.append(v)
                    elif g.group == rgn:
                        rmoist.append(v)
            lcenter = sum([v.co for v in lmoist], Vector((0,0,0))) / len(lmoist)
            rcenter = sum([v.co for v in rmoist], Vector((0,0,0))) / len(rmoist)
            print('Scale eye moisture vertices for %s mesh "%s"' % (ob.DazMesh, ob.name))
            print("Centers:", lcenter, rcenter)
            for v in lmoist:
                v.co = lcenter + 1.01*(v.co - lcenter)
            for v in rmoist:
                v.co = rcenter + 1.01*(v.co - rcenter)



def isEmpty(vgrp, ob):
    idx = vgrp.index
    for v in ob.data.vertices:
        for g in v.groups:
            if (g.group == idx and
                abs(g.weight-0.5) > 1e-4):
                return False
    return True

#-------------------------------------------------------------
#   Add multires
#-------------------------------------------------------------

def addMultires(context, ob, hdob, strict):
    from .finger import getFingerPrint
    if bpy.app.version < (2,90,0):
        print("Cannot rebuild subdiv in Blender %d.%d.%d" % bpy.app.version)
        return 'HIGHDEF'
    nverts = len(ob.data.vertices)
    nhdverts = len(hdob.data.vertices)
    if nverts == nhdverts:
        print("Not a HD object: %s" % hdob.name)
        return
    activateObject(context, hdob)
    hdme = hdob.data.copy()
    setMode('EDIT')
    bpy.ops.mesh.delete_loose()
    setMode('OBJECT')

    nmods = len(hdob.modifiers)
    mod = hdob.modifiers.new("Multires", 'MULTIRES')
    for n in range(nmods-1):
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    try:
        bpy.ops.object.multires_rebuild_subdiv(modifier="Multires")
        ok = True
    except RuntimeError:
        ok = False
    if ok:
        finger = getFingerPrint(ob)
        hdfinger = getFingerPrint(hdob)
        if hdfinger == finger:
            print('Rebuilt %d subdiv levels for "%s"' % (mod.levels, hdob.name))
            hdob.DazMultires = True
            mod.levels = mod.sculpt_levels = 0
            return 'MULTIRES'

    nhdverts = len(hdob.data.vertices)
    if nhdverts < nverts:
        hdob.data = hdme.copy()
        nhdverts = len(hdob.data.vertices)
        factor = math.sqrt(nhdverts/nverts)
        levels = int(round(math.log(factor, 2)))
        hdob.modifiers.remove(mod)
        print('Unsubdivide "%s": %f %d %d' % (hdob.name, factor, levels, nhdverts))
        mod = hdob.modifiers.new("Multires", 'MULTIRES')
        for n in range(levels):
            try:
                print("  Step %d" % n)
                bpy.ops.object.multires_unsubdivide(modifier="Multires")
            except RuntimeError:
                pass
        hdfinger = getFingerPrint(hdob)
        if hdfinger == finger:
            print('Rebuilt %d subdiv levels for "%s"' % (mod.render_levels, hdob.name))
            hdob.DazMultires = True
            mod.levels = mod.sculpt_levels = 0
            return 'MULTIRES'

    msg = ('Cannot unsubdivide "%s"' % hdob.name)
    if strict:
        raise DazError(msg)
    reportError(msg)
    hdob.modifiers.remove(mod)
    LS.hdFailures.append(hdob.name)
    return 'HIGHDEF'


class DAZ_OT_MakeMultires(DazOperator, IsMesh):
    bl_idname = "daz.make_multires"
    bl_label = "Make Multires"
    bl_description = "Convert HD mesh into mesh with multires modifier,\nand add vertex groups and extra UV layers"
    bl_options = {'UNDO'}

    def run(self, context):
        from .modifier import makeArmatureModifier, copyVertexGroups
        hdob = None
        baseob = context.object
        for ob in getSelectedMeshes(context):
            if ob != baseob:
                hdob = ob
                break
        if hdob is None:
            raise DazError("Two meshes must be selected, \none subdivided and one at base resolution.")
        print('Base "%s", HD "%s"' % (baseob.name, hdob.name))
        hdtype = addMultires(context, baseob, hdob, True)
        if hdtype == 'MULTIRES':
            copyUvLayers(baseob, hdob)
            copyVertexGroups(baseob, hdob)
        if hdtype != 'NONE':
            rig = baseob.parent
            hdob.parent = rig
            if rig and rig.type == 'ARMATURE' and not getModifier(hdob, 'ARMATURE'):
                makeArmatureModifier(rig.name, context, hdob, rig)


def copyUvLayers(ob, hdob):
    def setupLoopsMapping():
        loopsMapping = {}
        for f in hdob.data.polygons:
            loops = dict([(vn, f.loop_indices[i]) for i,vn in enumerate(f.vertices)])
            fid = tuple( sorted(list(f.vertices)) )
            if fid in loopsMapping:
                raise RuntimeError("duplicated face_id?")
            loopsMapping[fid] = loops
        return loopsMapping

    def copyUvLayer(uvdata, hddata, loopsMapping):
        for f in ob.data.polygons:
            fid = tuple( sorted(list(f.vertices)) )
            if fid not in loopsMapping:
                #print("Bad map", fid)
                continue
            for i,vn in enumerate(f.vertices):
                if vn not in loopsMapping[fid]:
                    print("Bad vert", vn)
                    continue
                hdLoop = loopsMapping[fid][vn]
                loop = f.loop_indices[i]
                hddata[hdLoop].uv = uvdata[loop].uv

    loopsMapping = setupLoopsMapping()
    for uvlayer in ob.data.uv_layers:
        if uvlayer.name in hdob.data.uv_layers.keys():
            print('UV layer "%s" already exists' % uvlayer.name)
            continue
        hdlayer = makeNewUvLayer(hdob.data, uvlayer.name, False)
        copyUvLayer(uvlayer.data, hdlayer.data, loopsMapping)

#-------------------------------------------------------------
#   UnGeometry
#   Where DS wants a geometry and Blender an empty
#-------------------------------------------------------------

class UnGeometry(Asset, Channels):
    def __init__(self, etype, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.etype = etype
        if self.etype == "studio_geometry_channels":
            self.polygon_material_groups = []
        self.uv_sets = {}

    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)
        if self.etype == "studio_geometry_channels":
            self.polygon_material_groups = struct["polygon_material_groups"]["values"]

    def fixMappingNodes(self, inst):
        # Lost the correct location somewhere
        if self.etype == "studio_geometry_channels" and inst.mappingNode:
            mtree = inst.mappingNode
            map1,map2 = [mnode for mnode in mtree.nodes if mnode.type == 'MAPPING']
            if GS.verbosity >= 3:
                print("Fix maps",  map1.inputs["Location"].default_value,  map2.inputs["Location"].default_value)
            map1.inputs["Location"].default_value = (0, 0, 0)
            map1.inputs["Rotation"].default_value = (0, 0, 0)
            map1.inputs["Scale"].default_value = (0.1, 1.0, 0.1)
            map2.inputs["Location"].default_value = (0.5, 0.5, 0)
            map2.inputs["Rotation"].default_value = (-90*D, 0, 0)
            map2.inputs["Scale"].default_value = (2, 2 ,2)

#-------------------------------------------------------------
#   Geometry
#-------------------------------------------------------------

class Geometry(Asset, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.instances = self.nodes = {}

        self.verts = []
        self.faces = []
        self.polylines = []
        self.polyline_materials = []
        self.polygon_indices = []
        self.material_indices = []
        self.polygon_material_groups = []
        self.polygon_groups = []
        self.edge_weights = []
        self.mappings = {}
        self.material_group_vis = {}

        self.material_selection_sets = []
        self.type = None
        self.isStrandHair = False
        self.vertex_count = 0
        self.poly_count = 0
        self.vertex_pairs = []
        self.dmaterials = []
        self.bumpareas = {}

        self.hidden_polys = []
        self.uv_set = None
        self.default_uv_set = None
        self.uv_sets = OrderedDict()
        self.rigidity = []

        self.root_region = None
        self.SubDIALevel = 0
        self.SubDRenderLevel = 0
        self.SubDEdgeInterpolateLevel = 0
        self.isShell = False
        self.shells = {}


    def __repr__(self):
        return ("<Geometry %s %s %s>" % (self.id, self.name, self.rna))


    def getInstance(self, ref, caller=None):
        def getSelfInstance(ref, nodes):
            iref = instRef(ref)
            if iref in nodes.keys():
                return nodes[iref]
            iref = unquote(iref)
            return nodes.get(iref)

        iref = getSelfInstance(ref, self.nodes)
        if iref:
            return iref
        if self.sourcing:
            iref = getSelfInstance(ref, self.sourcing.nodes)
            if iref:
                return iref
        return None


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)

        self.verts = d2bList(struct["vertices"]["values"])
        fdata = struct["polylist"]["values"]
        self.faces = [ f[2:] for f in fdata]
        self.polygon_indices = [f[0] for f in fdata]
        self.polygon_groups = struct["polygon_groups"]["values"]
        self.material_indices = [f[1] for f in fdata]
        self.polygon_material_groups = struct["polygon_material_groups"]["values"]

        for key,data in struct.items():
            if key == "polyline_list":
                self.polylines = data["values"]
            elif key == "edge_weights":
                self.edge_weights = data["values"]
            elif key == "default_uv_set":
                uvset = self.getTypedAsset(data, Uvset)
                if uvset:
                    self.default_uv_set = self.uv_sets[uvset.name] = uvset
            elif key == "uv_set":
                uvset = self.getTypedAsset(data, Uvset)
                if uvset:
                    self.uv_set = self.uv_sets[uvset.name] = uvset
            elif key == "graft":
                for key1,data1 in data.items():
                    if key1 == "vertex_count":
                        self.vertex_count = data1
                    elif key1 == "poly_count":
                        self.poly_count = data1
                    elif key1 == "hidden_polys":
                        self.hidden_polys = data1["values"]
                    elif key1 == "vertex_pairs":
                        self.vertex_pairs = data1["values"]
            elif key == "rigidity":
                self.rigidity = data
            elif key == "groups":
                self.groups.append(data)
            elif key == "root_region":
                self.root_region = data
            elif key == "type":
                self.type = data

        if self.uv_set is None:
            self.uv_set = self.default_uv_set
        return self


    def update(self, struct):
        Asset.update(self, struct)
        Channels.update(self, struct)
        if "polygon_groups" in struct.keys():
            self.polygon_groups = struct["polygon_groups"]["values"]
        if "polygon_material_groups" in struct.keys():
            self.polygon_material_groups = struct["polygon_material_groups"]["values"]
        for key,data in self.channels.items():
            if key == "SubDIALevel":
                self.SubDIALevel = getCurrentValue(data, 0)
            elif key == "SubDRenderLevel":
                self.SubDRenderLevel = getCurrentValue(data, 0)
            elif key == "SubDEdgeInterpolateLevel":
                self.SubDEdgeInterpolateLevel = getCurrentValue(data, 0)
            elif key == "SubDNormalSmoothing":
                self.SubDNormalSmoothing = getCurrentValue(data, 0)
        if self.SubDIALevel == 0 and "current_subdivision_level" in struct.keys():
            self.SubDIALevel = struct["current_subdivision_level"]


    def setExtra(self, extra):
        if extra["type"] == "studio/geometry/shell":
            self.isShell = True
        elif extra["type"] == "material_selection_sets":
            self.material_selection_sets = extra["material_selection_sets"]


    def isVisibleMaterial(self, dmat):
        if not self.material_group_vis.keys():
            return True
        label = dmat.name.rsplit("-", 1)[0]
        if label in self.material_group_vis.keys():
            return self.material_group_vis[label]
        else:
            return True


    def getPolyGroup(self, hidden):
        polyidxs = dict([(pgrp,n) for n,pgrp in enumerate(self.polygon_groups)])
        hideidxs = {}
        for pgrp in hidden:
            if pgrp in polyidxs.keys():
                hideidxs[polyidxs[pgrp]] = True
            elif pgrp in self.mappings.keys():
                alt = self.mappings[pgrp]
                if alt in polyidxs.keys():
                    hideidxs[polyidxs[alt]] = True
        return [fn for fn,idx in enumerate(self.polygon_indices)
                if idx in hideidxs.keys()]


    def hidePolyGroup(self, ob, fnums):
        if not fnums:
            return
        mat = self.getHiddenMaterial()
        mnum = len(ob.data.materials)
        ob.data.materials.append(mat)
        for fn in fnums:
            f = ob.data.polygons[fn]
            f.material_index = mnum


    def getHiddenMaterial(self):
        if LS.hiddenMaterial:
            return LS.hiddenMaterial
        mat = LS.hiddenMaterial = bpy.data.materials.new("HIDDEN")
        mat.diffuse_color[3] = 0
        mat.use_nodes = True
        mat.blend_method = 'CLIP'
        mat.shadow_method = 'NONE'
        tree = mat.node_tree
        tree.nodes.clear()
        node = tree.nodes.new(type = "ShaderNodeBsdfTransparent")
        node.location = (0,0)
        output = tree.nodes.new(type = "ShaderNodeOutputMaterial")
        output.location = (200,0)
        tree.links.new(node.outputs["BSDF"], output.inputs["Surface"])
        return mat


    def preprocess(self, context, inst):
        if self.isShell:
            self.uvs = {}
            for geonode in self.nodes.values():
                self.processShell(geonode, inst)


    def processShell(self, geonode, inst):
        for extra in geonode.extra:
            if "type" not in extra.keys():
                pass
            elif extra["type"] == "studio/node/shell":
                if "material_uvs" in extra.keys():
                    self.uvs = dict(extra["material_uvs"])
        if GS.shellMethod != 'MESH':
            if inst.shellNode:
                missing = self.addShells(inst.shellNode, inst)
                for mname,shmat,uv in missing:
                    msg = ("Missing shell material\n" +
                           "Material: %s\n" % mname +
                           "Node: %s\n" % geonode.name +
                           "Inst: %s\n" % inst.name +
                           "Shell: %s\n" % inst.shellNode.name +
                           "UV set: %s\n" % uv)
                    reportError(msg)


    def addShells(self, inst, shinst):
        if not (inst.geometries and shinst.geometries):
            return []
        missing = []
        geonode = inst.geometries[0]
        geo = geonode.data
        if shinst.isShell:
            shgeonode = shinst.geometries[0]
            shname = shinst.name
            shmats = {}
            visibles = {}
            geomats,shgeomats = self.getGeoMaterials(geonode, shgeonode)
            for mname,shmat in shgeomats.items():
                vis = self.material_group_vis.get(mname)
                if vis is None:
                    print("Warning: no visibility for material %s" % mname)
                    vis = True
                if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
                    shmat.getValue("getChannelOpacity", 1) == 0):
                    vis = False
                shmats[mname] = shmat
                visibles[mname] = vis

            if GS.shellMethod == 'GEONODES':
                for mname in geomats.keys():
                    if mname in shmats.keys() and visibles[mname]:
                        geonode.shellGeos.append((shgeonode,visibles))
                        uv = self.uvs.get(mname)
                        if uv:
                            uvset = self.addNewUvset(uv, geo, inst)
                            for dmat in geomats.values():
                                dmat.uvNodeType = 'ATTRIBUTE'
                            for dmat in shgeomats.values():
                                dmat.uvNodeType = 'ATTRIBUTE'
                                dmat.uv_set = uvset
                        return []
                for child in inst.children.values():
                    if self.addShellGeo(child, shmats, shgeonode, visibles, ""):
                        pass
                        #return []
                return []

            for mname,shmat in shmats.items():
                if not visibles[mname]:
                    continue
                uv = self.uvs.get(mname)
                if uv and mname in geomats.keys():
                    dmat = geomats[mname]
                    if shname not in dmat.shells.keys():
                        dmat.shells[shname] = self.makeShell(shname, shmat, uv)
                    shmat.ignore = True
                    self.addNewUvset(uv, geo, inst)
                else:
                    missing.append((mname,shmat,uv))
        self.matused = []
        for mname,shmat,uv in missing:
            for key,child in inst.children.items():
                self.addMoreShells(child, mname, shname, shmat, uv, "")
        return [miss for miss in missing if miss[0] not in self.matused]


    def getGeoMaterials(self, geonode, shgeonode):
        if GS.useMaterialsByIndex:
            geomats = dict([(skipName(mname),shmat) for mname,shmat in geonode.materials.items()])
            shgeomats = dict([(skipName(mname),shmat) for mname,shmat in shgeonode.materials.items()])
        else:
            geomats = geonode.materials
            shgeomats = shgeonode.materials
        return geomats, shgeomats


    def addShellGeo(self, inst, shmats, shgeonode, visibles, pprefix):
        if not inst.geometries:
            return False
        geonode = inst.geometries[0]
        geo = geonode.data
        geomats,shgeomats = self.getGeoMaterials(geonode, shgeonode)
        prefix = "%s%s_" % (pprefix, inst.node.name)
        for mname in shmats.keys():
            mname1 = self.unprefixName(prefix, inst, mname)
            if mname1 in geomats.keys() and visibles[mname]:
                geonode.shellGeos.append((shgeonode,visibles))
                geonode.shellPrefix = prefix
                uv = self.uvs.get(mname)
                uvset = self.addNewUvset(uv, geo, inst)
                for dmat in geomats.values():
                    dmat.uvNodeType = 'ATTRIBUTE'
                for dmat in shgeomats.values():
                    dmat.uvNodeType = 'ATTRIBUTE'
                    dmat.uv_set = uvset
                return True
        for child in inst.children.values():
            if self.addShellGeo(child, shmats, shgeonode, visibles, prefix):
                return True
        return False


    def addMoreShells(self, inst, mname, shname, shmat, uv, pprefix):
        from .figure import FigureInstance
        if not isinstance(inst, FigureInstance) or not inst.geometries:
            return
        if mname in self.matused:
            return
        geonode = inst.geometries[0]
        geo = geonode.data
        geomats,_shgeomats = self.getGeoMaterials(geonode, geonode)
        prefix = "%s%s_" % (pprefix, inst.node.name)
        mname1 = self.unprefixName(prefix, inst, mname)
        if mname1 and mname1 in geomats.keys():
            dmat = geomats[mname1]
            mshells = dmat.shells
            if shname not in mshells.keys():
                mshells[shname] = self.makeShell(shname, shmat, uv)
            shmat.ignore = True
            self.addNewUvset(uv, geo, inst)
            self.matused.append(mname)
        else:
            for key,child in inst.children.items():
                self.addMoreShells(child, mname, shname, shmat, uv, prefix)


    def unprefixName(self, prefix, inst, mname):
        n = len(prefix)
        if mname[0:n] == prefix:
            return mname[n:]
        else:
            return None


    def addNewUvset(self, uv, geo, inst):
        if uv not in geo.uv_sets.keys():
            uvset = self.findUvSet(uv, inst.node.id)
            if uvset:
                geo.uv_sets[uv] = geo.uv_sets[uvset.name] = uvset
                return uvset
        return geo.default_uv_set


    def findUvSet(self, uv, url):
        from .asset import getRelativeRef
        from .fileutils import findPathRecursive
        relpath = os.path.dirname(url)
        filepath = findPathRecursive(uv, relpath, ["UV Sets/"])
        if filepath:
            url = unquote("%s#%s" % (filepath, uv))
            url = getRelativeRef(url)
            asset = self.getAsset(url)
            if asset:
                if GS.verbosity > 2:
                    print("Found UV set '%s' in '%s'" % (uv, unquote(url)))
                self.uv_sets[uv] = asset
            return asset
        return None


    def buildData(self, context, geonode, inst, center):
        if not isinstance(geonode, GeoNode):
            raise DazError("BUG buildData: Should be Geonode:\n  %s" % geonode)
        if (self.rna and not LS.singleUser):
            return None, None

        if self.sourcing:
            asset = self.sourcing
            if isinstance(asset, Geometry):
                self.polygon_groups = asset.polygon_groups
                self.polygon_material_groups = asset.polygon_material_groups
            else:
                msg = ("BUG: Sourcing:\n%  %s\n  %s" % (self, asset))
                reportError(msg)

        me = self.rna = bpy.data.meshes.new(geonode.getName())

        verts = self.verts
        edges = []
        polymats = guideVerts = guideEdges = guidePolymats = []
        faces = self.faces
        if isinstance(geonode, GeoNode) and geonode.verts:
            if geonode.edges:
                verts = geonode.verts
                edges = geonode.edges
            elif geonode.faces:
                verts = geonode.verts
                faces = geonode.faces
            elif geonode.polylines:
                verts,edges,polymats,guideVerts,guideEdges,guidePolymats = self.getEdges(geonode, faces)
            elif self.polylines:
                verts = geonode.verts
            elif len(geonode.verts) == len(verts):
                verts = geonode.verts

        if not verts:
            return None, None

        if self.polylines and not polymats:
            polymats = [pline[1] for pline in self.polylines]
            for pline in self.polylines:
                edges += [(pline[i-1],pline[i]) for i in range(3,len(pline))]

        if LS.fitFile:
            me.from_pydata(verts, edges, faces)
        else:
            me.from_pydata([Vector(vco)-center for vco in verts], edges, faces)

        if len(faces) != len(me.polygons):
            msg = ("Not all faces were created:\n" +
                   "Geometry: '%s'\n" % self.name +
                   "\# DAZ faces: %d\n" % len(faces) +
                   "\# Blender polygons: %d\n" % len(me.polygons))
            reportError(msg)

        if len(me.polygons) > 0:
            for fn,mn in enumerate(self.material_indices):
                f = me.polygons[fn]
                f.material_index = mn
                f.use_smooth = True

        self.setHairMatNums(me, polymats)
        if self.isStrandHair and not edges:
            me.DazHairType = 'TUBE'

        hasShells = self.addMaterials(me, geonode, context)
        for key,uvset in self.uv_sets.items():
            self.buildUVSet(context, uvset, me, False)
        self.buildUVSet(context, self.uv_set, me, True)
        if self.shells and self.uv_set != self.default_uv_set:
            self.buildUVSet(context, self.default_uv_set, me, False)

        for struct in self.material_selection_sets:
            if "materials" in struct.keys() and "name" in struct.keys():
                if struct["name"][0:8] == "Template":
                    continue
                items = me.DazMaterialSets.add()
                items.name = struct["name"]
                for mname in struct["materials"]:
                    item = items.names.add()
                    item.name = mname

        obname = geonode.getObjectName(inst)
        ob = bpy.data.objects.new(obname, me)
        from .finger import getFingerPrint
        me.DazFingerPrint = getFingerPrint(ob)
        if hasShells:
            ob.DazVisibilityDrivers = True
        self.validateMesh(me)

        if GS.onFaceMaps == 'POLYGON_GROUPS' and me.polygons:
            self.addFaceMaps(ob, self.polygon_groups, self.polygon_indices)
        elif GS.onFaceMaps == 'MATERIALS' and me.polygons:
            self.addFaceMaps(ob, self.polygon_material_groups, self.material_indices)

        guideOb = None
        if guideVerts:
            guideMe = bpy.data.meshes.new("%s_GUIDE" % geonode.getName())
            guideMe.from_pydata(guideVerts, guideEdges, [])
            guideOb = bpy.data.objects.new("%s_GUIDE" % inst.name, guideMe)
            guideMe.DazFingerPrint = getFingerPrint(guideOb)
            self.setHairMatNums(guideMe, guidePolymats)
            for mat in me.materials:
                guideMe.materials.append(mat)
            self.validateMesh(guideMe)

        return ob, guideOb


    def getEdges(self, geonode, faces):
        verts = geonode.verts
        guideEdges = []
        guideVerts = []
        guidePolymats = []
        if self.polylines and GS.useHairGuides:
            gverts = []
            for pline in self.polylines:
                guideEdges += [(pline[i-1],pline[i]) for i in range(3,len(pline))]
                gverts += [(pline[i],True) for i in range(2,len(pline))]
            guideVerts = [verts[vn] for vn in dict(gverts).keys()]
            guidePolymats = [pline[1] for pline in self.polylines]
        edges = []
        for pline in geonode.polylines:
            edges += [(pline[i-1],pline[i]) for i in range(1,len(pline))]
        return verts, edges, geonode.polyline_materials, guideVerts, guideEdges, guidePolymats


    def setHairMatNums(self, me, polymats):
        if self.polylines:
            me.DazPolylineMaterials.clear()
            self.setHairType(me)
            for mnum in polymats:
                item = me.DazPolylineMaterials.add()
                item.a = mnum


    def setHairType(self, me):
        if me.polygons:
            me.DazHairType = 'SHEET'
        else:
            me.DazHairType = 'LINE'


    def addFaceMaps(self, ob, groups, indices):
        facemaps = dict([(mn,[]) for mn in range(len(groups))])
        for fn,mn in enumerate(indices):
            facemaps[mn].append(fn)
        for mn,mname in enumerate(groups):
            facemap = ob.face_maps.new(name = mname)
            facemap.add(facemaps[mn])


    def creaseEdges(self, context, ob):
        if self.edge_weights:
            from .tables import getVertEdges
            vertedges = getVertEdges(ob)
            weights = {}
            for vn1,vn2,w in self.edge_weights:
                for e in vertedges[vn1]:
                    if vn2 in e.vertices:
                        weights[e.index] = w
            activateObject(context, ob)
            setMode('EDIT')
            bm = bmesh.from_edit_mesh(ob.data)
            bm.edges.ensure_lookup_table()
            creaseLayer = bm.edges.layers.crease.verify()
            level = max(1, self.SubDIALevel + self.SubDRenderLevel)
            for en,w in weights.items():
                e = bm.edges[en]
                e[creaseLayer] = min(1.0, w/level)
            bmesh.update_edit_mesh(ob.data)
            setMode('OBJECT')
            self.edge_weights = []


    def addMaterials(self, me, geonode, context):
        hasShells = False
        if GS.useMaterialsByIndex:
            for mnum,dmat in enumerate(geonode.materials.values()):
                self.addMaterial(dmat, mnum, me, geonode)
                if dmat.shells:
                    hasShells = True
            return hasShells

        for mnum,mname in enumerate(self.polygon_material_groups):
            dmat = None
            if mname in geonode.materials.keys():
                dmat = geonode.materials[mname]
            else:
                ref = self.fileref + "#" + mname
                dmat = self.getAsset(ref)
            if dmat:
                self.addMaterial(dmat, mnum, me, geonode)
                if dmat.shells:
                    hasShells = True
            else:
                if GS.verbosity > 3:
                    mats = list(geonode.materials.keys())
                    mats.sort()
                    print("Existing materials:\n  %s" % mats)
                reportError("Material \"%s\" not found in geometry %s" % (mname, geonode.name))
                return False
        return hasShells


    def addMaterial(self, dmat, mnum, me, geonode):
        if dmat.rna is None:
            msg = ("Material without rna:\n  %s\n  %s\n  %s" % (dmat, geonode, self))
            reportError(msg)
        me.materials.append(dmat.rna)
        self.dmaterials.append(dmat)
        dmat.correctBumpArea(self, me)
        if dmat.uv_set and dmat.uv_set.checkSize(me):
            self.uv_set = dmat.uv_set
        if GS.useAutoSmooth:
            me.use_auto_smooth = dmat.getValue(["Smooth On"], False)
            me.auto_smooth_angle = dmat.getValue(["Smooth Angle"], 89.9)*D


    def validateMesh(self, me):
        if me.validate():
            reportError('Invalid mesh "%s". Correcting.' % me.name)
            LS.invalidMeshes.append(me.name)

    def getBumpArea(self, me, bumps):
        bump = list(bumps)[0]
        if bump not in self.bumpareas.keys():
            area = 0.0
            for mn,dmat in enumerate(self.dmaterials):
                use = (bump in dmat.geobump.keys())
                for shell in dmat.shells.values():
                    if bump in shell.material.geobump.keys():
                        use = True
                if use:
                    area += sum([f.area for f in me.polygons if f.material_index == mn])
            self.bumpareas[bump] = area
        return self.bumpareas[bump]


    def buildUVSet(self, context, uv_set, me, setActive):
        if uv_set:
            if uv_set.checkSize(me):
                uv_set.build(context, me, self, setActive)
            else:
                msg = ("Incompatible UV sets:\n  %s\n  %s" % (me.name, uv_set.name))
                reportError(msg)


    def buildRigidity(self, ob):
        from .modifier import buildVertexGroup
        if self.rigidity:
            if "weights" in self.rigidity.keys():
                buildVertexGroup(ob, "Rigidity", self.rigidity["weights"]["values"])
            if "groups" not in self.rigidity.keys():
                return
            for group in self.rigidity["groups"]:
                rgroup = ob.data.DazRigidityGroups.add()
                rgroup.id = group["id"]
                rgroup.rotation_mode = group["rotation_mode"]
                rgroup.scale_modes = " ".join(group["scale_modes"])
                for vn in group["reference_vertices"]["values"]:
                    vert = rgroup.reference_vertices.add()
                    vert.a = vn
                for vn in group["mask_vertices"]["values"]:
                    vert = rgroup.mask_vertices.add()
                    vert.a = vn


    def makeShell(self, shname, shmat, uv):
        first = False
        if shname not in self.shells.keys():
            first = True
            self.shells[shname] = []
        match = None
        for shell in self.shells[shname]:
            if shmat.equalChannels(shell.material):
                if uv == shell.uv:
                    return shell
                else:
                    match = shell
        if not match:
            for shell in self.shells[shname]:
                shell.single = False
        shell = Shell(shname, shmat, uv, self, first, match)
        self.shells[shname].append(shell)
        return shell


def d2bList(verts):
    s = LS.scale
    if GS.zup:
        return [[s*v[0], -s*v[2], s*v[1]] for v in verts]
    else:
        return [[s*v[0], s*v[1], s*v[2]] for v in verts]

#-------------------------------------------------------------
#   Shell
#-------------------------------------------------------------

class Shell:
    def __init__(self, shname, shmat, uv, geo, first, match):
        self.name = shname
        self.material = shmat
        self.uv = uv
        self.geometry = geo
        self.single = first
        self.match = match
        self.tree = None


    def __repr__(self):
        dmat = self.material
        return ("<Shell %s %s S:%s D:%s>" % (self.name, dmat.name, self.single, dmat.getDiffuse()))


    def build(self, me):
        print("BS", self)
        print("ME", me)

#-------------------------------------------------------------
#   UV Asset
#-------------------------------------------------------------

class Uvset(Asset):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.uvs = []
        self.polyverts = []
        self.built = {}


    def __repr__(self):
        return ("<Uvset %s '%s' %d %d>" % (self.id, self.name, len(self.uvs), len(self.polyverts)))


    def parse(self, struct):
        Asset.parse(self, struct)
        self.type = "uv_set"
        self.uvs = struct["uvs"]["values"]
        self.polyverts = struct["polygon_vertex_indices"]
        self.name = self.getLabel()
        return self


    def checkSize(self, me):
        if not self.polyverts:
            return True
        fnums = [pvi[0] for pvi in self.polyverts]
        fnums.sort()
        return (len(me.polygons) >= fnums[-1])


    def checkPolyverts(self, me, polyverts, error):
        uvnums = []
        for fverts in polyverts.values():
            uvnums += fverts
        if uvnums:
            uvmin = min(uvnums)
            uvmax = max(uvnums) + 1
        else:
            uvmin = uvmax = -1
        if (uvmin != 0 or uvmax != len(self.uvs)):
                msg = ("Vertex number mismatch.\n" +
                       "Expected mesh with %d UV vertices        \n" % len(self.uvs) +
                       "but %s has %d UV vertices." % (me.name, uvmax))
                if error:
                    raise DazError(msg)
                else:
                    print(msg)


    def getPolyVerts(self, me):
        polyverts = dict([(f.index, list(f.vertices)) for f in me.polygons])
        if self.polyverts:
            fnums = [fn for fn,vn,uv in self.polyverts]
            if max(fnums) > len(me.polygons):
                msg = "UV set has %d faces but target mesh only has %d faces" % (max(fnums), len(me.polygons))
                print(msg)
                raise DazError(msg)
            for fn,vn,uv in self.polyverts:
                f = me.polygons[fn]
                for n,vn1 in enumerate(f.vertices):
                    if vn1 == vn:
                        polyverts[fn][n] = uv
        return polyverts


    def build(self, context, me, geo, setActive):
        if self.name is None:
            return
        uvlayer = self.built.get(me.name)
        if uvlayer:
            if setActive:
                uvlayer.active = uvlayer.active_render = True
            return
        if len(me.polygons) == 0:
            LS.polyLines[geo.id] = geo
            if GS.verbosity > 2:
                print("NO UVs", me.name, self.name)
            return

        polyverts = self.getPolyVerts(me)
        self.checkPolyverts(me, polyverts, False)
        uvlayer = makeNewUvLayer(me, self.getLabel(), setActive)

        m = 0
        vnmax = len(self.uvs)
        nmats = len(geo.polygon_material_groups)
        ucoords = [[] for n in range(nmats)]
        for fn,f in enumerate(me.polygons):
            mn = geo.material_indices[fn]
            for n in range(len(f.vertices)):
                vn = polyverts[f.index][n]
                if vn < vnmax:
                    uv = self.uvs[vn]
                    uvlayer.data[m].uv = uv
                    ucoords[mn].append(uv[0])
                m += 1

        for mn in range(nmats):
            if len(ucoords[mn]) > 0:
                umin = min(ucoords[mn])
                umax = max(ucoords[mn])
                if umax-umin <= 1:
                    udim = math.floor((umin+umax)/2)
                else:
                    udim = 0
                    if GS.verbosity > 2:
                        print("UV coordinate difference %f - %f > 1" % (umax, umin))
                self.fixUdims(context, mn, udim, geo)
        self.built[me.name] = uvlayer


    def fixUdims(self, context, mn, udim, geo):
        fixed = False
        key = geo.polygon_material_groups[mn]
        for geonode in geo.nodes.values():
            if key in geonode.materials.keys():
                dmat = geonode.materials[key]
                dmat.fixUdim(context, udim)
                fixed = True
        if not (fixed or GS.useMaterialsByIndex):
            print("Material \"%s\" not found" % key)


def makeNewUvLayer(me, name, setActive):
    uvtex = me.uv_layers.new()
    uvtex.name = name
    uvlayer = me.uv_layers[-1]
    uvlayer.active_render = setActive
    if setActive:
        me.uv_layers.active_index = len(me.uv_layers) - 1
    return uvlayer

#-------------------------------------------------------------
#   Prune Uv textures
#-------------------------------------------------------------

def pruneUvMaps(ob):
    if ob.data is None or len(ob.data.uv_layers) <= 1:
        return
    used = {}
    for uvlayer in ob.data.uv_layers:
        used[uvlayer.name] = False
    active = getActiveUvLayer(ob)
    used[active.name] = True
    for mat in ob.data.materials:
        if mat:
            for node in mat.node_tree.nodes:
                if node.type == "ATTRIBUTE":
                    used[node.attribute_name]= True
                elif node.type == "UVMAP":
                    used[node.uv_map] = True
                elif node.type == "NORMAL_MAP":
                    used[node.uv_map] = True
    for uvname in used.keys():
        if not used[uvname]:
            uvlayer = ob.data.uv_layers[uvname]
            print("Remove UV layer %s" % uvname)
            ob.data.uv_layers.remove(uvlayer)


def getActiveUvLayer(ob):
    for uvlayer in ob.data.uv_layers:
        if uvlayer.active_render:
            return uvlayer
    return None


class DAZ_OT_PruneUvMaps(DazOperator, IsMesh):
    bl_idname = "daz.prune_uv_maps"
    bl_label = "Prune UV Maps"
    bl_description = "Remove unused UV maps"
    bl_options = {'UNDO'}

    def run(self, context):
        setMode('OBJECT')
        for ob in getSelectedMeshes(context):
            pruneUvMaps(ob)

#-------------------------------------------------------------
#   Collaps UDims
#-------------------------------------------------------------

def addUdimsToUVs(ob, restore, udim, vdim):
    mat = ob.data.materials[0]
    for uvlayer in ob.data.uv_layers:
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            mat = ob.data.materials[f.material_index]
            if restore:
                ushift = mat.DazUDim
                vshift = mat.DazVDim
            else:
                ushift = udim - mat.DazUDim
                vshift = vdim - mat.DazVDim
            for n in range(len(f.vertices)):
                uvlayer.data[m].uv[0] += ushift
                uvlayer.data[m].uv[1] += vshift
                m += 1


class DAZ_OT_CollapseUDims(DazOperator):
    bl_idname = "daz.collapse_udims"
    bl_label = "Collapse UDIMs"
    bl_description = "Restrict UV coordinates to the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and not ob.DazUDimsCollapsed)

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.collapseUDims(ob)

    def collapseUDims(self, ob):
        from .material import addUdimTree
        if ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = True
        addUdimsToUVs(ob, False, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = True
            addUdimTree(mat.node_tree, -mat.DazUDim, -mat.DazVDim)


class DAZ_OT_RestoreUDims(DazOperator):
    bl_idname = "daz.restore_udims"
    bl_label = "Restore UDIMs"
    bl_description = "Restore original UV coordinates outside the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.DazUDimsCollapsed)

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.restoreUDims(ob)

    def restoreUDims(self, ob):
        from .material import addUdimTree
        if not ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = False
        addUdimsToUVs(ob, True, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if not mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = False
            addUdimTree(mat.node_tree, mat.DazUDim, mat.DazVDim)

#-------------------------------------------------------------
#   Load UVs
#-------------------------------------------------------------

class DAZ_OT_LoadUV(DazOperator, DazFile, SingleFile, IsMesh):
    bl_idname = "daz.load_uv"
    bl_label = "Load UV Set"
    bl_description = "Load a UV set to the active mesh"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        from .fileutils import getFoldersFromObject
        folders = getFoldersFromObject(context.object, ["UV Sets/"])
        if folders:
            self.properties.filepath = folders[0]
        return SingleFile.invoke(self, context, event)


    def run(self, context):
        from .load_json import loadJson
        from .files import parseAssetFile

        ob = context.object
        me = ob.data
        LS.forUV(ob)
        struct = loadJson(self.filepath)
        asset = parseAssetFile(struct)
        if asset is None or len(asset.uvs) == 0:
            raise DazError ("Not an UV asset:\n  '%s'" % self.filepath)

        for uvset in asset.uvs:
            polyverts = uvset.getPolyVerts(me)
            uvset.checkPolyverts(me, polyverts, True)
            uvlayer = makeNewUvLayer(me, uvset.getLabel(), False)
            vnmax = len(uvset.uvs)
            m = 0
            for fn,f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvlayer.data[m].uv = uv
                    m += 1

#-------------------------------------------------------------
#   Save UVs
#-------------------------------------------------------------

class DAZ_OT_SaveUV(DazOperator, DazFile, SingleFile, DazExporter):
    bl_idname = "daz.save_uv"
    bl_label = "Save UV Set"
    bl_description = "Save the active UV set as a duf file"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.uv_layers.active)

    def invoke(self, context, event):
        self.filepath = "%s.duf" % bpy.path.clean_name(context.object.data.uv_layers.active.name)
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        ob = context.object
        uvlayer = ob.data.uv_layers.active
        struct, filepath = self.makeDazStruct("uv_set", self.filepath)
        uvstruct = OrderedDict()
        uvstruct["id"] = uvlayer.name
        uvstruct["name"] = uvlayer.name
        uvstruct["label"] = uvlayer.name
        uvstruct["vertex_count"] = len(ob.data.vertices)
        uvs = OrderedDict()
        uvs["count"] = len(uvlayer.data)
        uvs["values"] = [list(uv.uv) for uv in uvlayer.data]
        uvstruct["uvs"] = uvs
        polys = []
        m = 0
        for f in ob.data.polygons:
            for vn in f.vertices:
                polys.append([f.index, vn, m])
                m += 1
        uvstruct["polygon_vertex_indices"] = polys
        struct["uv_set_library"] = [uvstruct]
        scene = {"uvs": [
            { "id" : "%s-1" % uvlayer.name,
              "url" : "#%s" % normalizeRef(uvlayer.name) }
            ]
        }
        struct["scene"] = scene
        saveJson(struct, filepath, binary=self.useCompress)
        print("UV set %s saved" % filepath)


#----------------------------------------------------------
#   Prune vertex groups
#----------------------------------------------------------

class DAZ_OT_LimitVertexGroups(DazPropsOperator, IsMesh):
    bl_idname = "daz.limit_vertex_groups"
    bl_label = "Limit Vertex Groups"
    bl_description = "Limit the number of vertex groups per vertex"
    bl_options = {'UNDO'}

    limit : IntProperty(
        name = "Limit",
        description = "Max number of vertex group per vertex",
        default = 4,
        min = 1, max = 10
    )

    def draw(self, context):
        self.layout.prop(self, "limit")

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.limitVertexGroups(ob)

    def limitVertexGroups(self, ob):
        deletes = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        weights = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        for v in ob.data.vertices:
            data = [(g.weight, g.group) for g in v.groups]
            if len(data) > self.limit:
                data.sort()
                vnmin = len(data) - self.limit
                for w,gn in data[0:vnmin]:
                    deletes[gn].append(v.index)
                wsum = sum([w for w,gn in data[vnmin:]])
                for w,gn in data[vnmin:]:
                    weights[gn].append((v.index, w/wsum))
        for vgrp in ob.vertex_groups:
            vnums = deletes[vgrp.index]
            if vnums:
                vgrp.remove(vnums)
            for vn,w in weights[vgrp.index]:
                vgrp.add([vn], w, 'REPLACE')

#----------------------------------------------------------
#   Finalize meshes
#----------------------------------------------------------

class DAZ_OT_FinalizeMeshes(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.finalize_meshes"
    bl_label = "Finalize Meshes"
    bl_description = "Remove internal properties from meshes.\nDisables some tools but may improve performance"
    bl_options = {'UNDO'}

    useStoreData : BoolProperty(
        name = "Store Data",
        description = "Store data in a file",
        default = False)

    useOverwrite : BoolProperty(
        name = "Overwrite",
        description = "Overwrite stored data",
        default = False)

    maxSubsurf : IntProperty(
        name = "Maximal Subsurf Level",
        description = "Maximal subsurf level",
        min = 0,
        default = 2)

    def draw(self, context):
        self.layout.prop(self, "maxSubsurf")
        self.layout.prop(self, "useStoreData")
        if self.useStoreData:
            self.layout.prop(self, "useOverwrite")

    def invoke(self, context, event):
        ob = context.object
        if (ob.DazBlendFile and ob.DazBlendFile != bpy.data.filepath):
            self.useStoreData = False
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        from .load_json import saveJson
        ob = context.object
        rig = getRigFromContext(context)
        self.nothing = True
        if self.useStoreData:
            if not bpy.data.filepath:
                raise DazError("Save the blend file first")
            struct = { "filetype" : "mesh_data", "meshes" : [] }
        else:
            struct = None
        if rig:
            for ob1 in getMeshChildren(rig):
                self.finalizeMesh(ob1, struct)
        if ob.type == 'MESH':
            self.finalizeMesh(ob, struct)
        if self.nothing:
            print("Nothing to save.")
        elif self.useStoreData:
            rig.DazBlendFile = bpy.data.filepath
            folder,path = getMeshDataFile(bpy.data.filepath)
            if not os.path.exists(folder):
                os.makedirs(folder)
            if self.useOverwrite or not os.path.exists(path):
                saveJson(struct, path)
                print('Saved "%s"' % path)


    def finalizeMesh(self, ob, struct):
        from .finger import getFingerPrint
        if self.useStoreData:
            ob.DazBlendFile = bpy.data.filepath
            mstruct = {}
            struct["meshes"].append(mstruct)
            mstruct["name"] = ob.name
            mstruct["finger_print"] = getFingerPrint(ob)
            mstruct["orig_finger_print"] = ob.data.DazFingerPrint
            origverts = [(int(item.name),item.a) for item in ob.data.DazOrigVerts]
            origverts.sort()
            mstruct["orig_verts"] = origverts
            if origverts:
                self.nothing = False
        for mod in ob.modifiers:
            if mod.type == 'SUBSURF':
                if mod.levels > self.maxSubsurf:
                    mod.levels = self.maxSubsurf
                if mod.render_levels > self.maxSubsurf:
                    mod.render_levels = self.maxSubsurf
        clearMeshProps(ob.data)


def clearMeshProps(me):
    me.DazRigidityGroups.clear()
    me.DazOrigVerts.clear()
    #me.DazFingerPrint = getFingerPrint(ob)
    me.DazGraftGroup.clear()
    me.DazMaskGroup.clear()
    me.DazPolylineMaterials.clear()
    me.DazMaterialSets.clear()
    me.DazHDMaterials.clear()


def getMeshDataFile(filepath):
    folder = os.path.dirname(filepath)
    folder = os.path.join(folder, "mesh_data")
    fname = os.path.splitext(os.path.basename(filepath))[0]
    path = os.path.join(folder, "%s.json" % fname)
    return folder,path


def restoreOrigVerts(ob, vcount):
    if len(ob.data.DazOrigVerts) > 0:
        return True, False
    elif not ob.DazBlendFile:
        return False, False
    folder,filepath = getMeshDataFile(ob.DazBlendFile)
    if not os.path.exists(filepath):
        print("%s does not exist" % filepath)
        return False, False
    from .load_json import loadJson
    from .finger import getFingerPrint
    finger = getFingerPrint(ob)
    struct = loadJson(filepath)
    for mstruct in struct["meshes"]:
        if mstruct["finger_print"] == finger and mstruct["orig_verts"]:
            nverts = int(mstruct["orig_finger_print"].split("-")[0])
            if nverts == vcount or vcount < 0:
                me = ob.data
                me.DazOrigVerts.clear()
                for m,n in mstruct["orig_verts"]:
                    pg = me.DazOrigVerts.add()
                    pg.name = str(m)
                    pg.a = n
                me.DazFingerPrint = mstruct["orig_finger_print"]
                return True, True
    return False, False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PruneUvMaps,
    DAZ_OT_MakeMultires,
    DAZ_OT_CollapseUDims,
    DAZ_OT_RestoreUDims,
    DAZ_OT_LoadUV,
    DAZ_OT_SaveUV,
    DAZ_OT_LimitVertexGroups,
    DAZ_OT_FinalizeMeshes,
]

def register():
    from .propgroups import DazIntGroup, DazFloatGroup, DazPairGroup, DazRigidityGroup, DazRigidityScaleFactor, DazStringStringGroup, DazTextGroup
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Armature.DazRigidityScaleFactors = bpy.props.CollectionProperty(type=DazRigidityScaleFactor)
    bpy.types.Mesh.DazRigidityGroups = CollectionProperty(type = DazRigidityGroup)
    bpy.types.Mesh.DazOrigVerts = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazFingerPrint = StringProperty(name = "Original Fingerprint", default="")
    bpy.types.Mesh.DazGraftGroup = CollectionProperty(type = DazPairGroup)
    bpy.types.Mesh.DazMaskGroup = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazPolylineMaterials = CollectionProperty(type = DazIntGroup)
    bpy.types.Mesh.DazVertexCount = IntProperty(default=0)
    bpy.types.Mesh.DazMaterialSets = CollectionProperty(type = DazStringStringGroup)
    bpy.types.Mesh.DazHDMaterials = CollectionProperty(type = DazTextGroup)
    bpy.types.Mesh.DazMergedGeografts = CollectionProperty(type = bpy.types.PropertyGroup)
    bpy.types.Object.DazMultires = BoolProperty(default=False)
    bpy.types.Mesh.DazHairType = StringProperty(default = 'SHEET')

    bpy.types.Object.DazBlendFile = StringProperty(
        name = "Blend File",
        description = "Blend file where the object is defined",
        default = "")


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
