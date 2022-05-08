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

import math
from mathutils import Vector, Matrix
import os
import bpy
import bmesh
from collections import OrderedDict
from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .node import Node, Instance, SimNode
from .fileutils import SingleFile, DazFile

#-------------------------------------------------------------
#   Geonode
#-------------------------------------------------------------

class GeoNode(Node, SimNode):
    def __init__(self, figure, geo, ref, etype):
        from .asset import normalizeRef
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
            print("UnGeometry: %s" % etype)
        else:
            msg = ("Not a geometry:\n%s" % geo)
            reportError(msg, trigger=(2,3))
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
        self.polylines = None
        self.highdef = None
        self.hdobject = None
        self.index = figure.count
        self.modifiers = {}
        self.morphsValues = {}
        self.shstruct = {}
        self.shellGeos = []
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


    def buildShells(self, context):
        if not self.shellGeos:
            return
        from .geonodes import GeoshellGroup
        ob = self.rna
        activateObject(context, ob)
        print("SHELL", self.rna, bpy.context.object)
        mats = [dmat.rna for dmat in self.materials.values()]
        for shgeo in self.shellGeos:
            print(shgeo)
            print("MM", shgeo.materials)
            shmats = [dmat.rna for dmat in shgeo.materials.values()]

            mod = ob.modifiers.new(shgeo.name, 'NODES')
            nmods = len(ob.modifiers)
            for n in range(nmods-1):
                bpy.ops.object.modifier_move_up(modifier=mod.name)

            group = GeoshellGroup()
            group.create(shgeo.name, mats)
            group.addNodes(mats)
            mod.node_group = group.group
            #mod["Input_1"] = ob
            mod["Input_2"] = 0.1 * ob.DazScale
            shmat = shmats[0]
            for n,mat in enumerate(mats):
                mod["Input_%d" % (n+3)] = shmat


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
        if isinstance(self.data, UnGeometry):
            return
        if self.highdef:
            me = self.buildHDMesh(ob)
            hdob = bpy.data.objects.new(ob.name + "_HD", me)
            self.hdobject = inst.hdobject = hdob
            LS.hdmeshes[LS.rigname].append(hdob)
            hdob.DazVisibilityDrivers = ob.DazVisibilityDrivers
            self.addHDMaterials(ob.data.materials, "")
            center = Vector((0,0,0))
            self.arrangeObject(hdob, inst, context, center)
            multi = False
            if not (GS.useMultires and GS.useMultiUvLayers):
                self.addHDUvs(ob, hdob)
            if GS.useMultires and hdob.data.polygons:
                multi = addMultires(context, ob, hdob, False)
            if multi:
                if GS.useMultiUvLayers:
                    copyUvLayers(ob, hdob)
            elif (len(hdob.data.vertices) == len(ob.data.vertices) and
                  len(hdob.data.edges) == len(ob.data.edges) and
                  len(hdob.data.polygons) == len(ob.data.polygons)):
                print("HD mesh same as base mesh:", ob.name)
                self.hdobject = inst.hdobject = None
                deleteObjects(context, [hdob])
            elif GS.useMultires:
                self.addHDUvs(ob, hdob)
        elif LS.useHDObjects:
            self.hdobject = inst.hdobject = ob

        if ob and self.data:
            self.data.buildRigidity(ob)
            hdob = self.hdobject
            if hdob and hdob != ob:
                self.data.buildRigidity(hdob)

        renderLevel = 0
        subDLevel = 0
        if self.materials:
            subDLevel = max([dmat.getSubDLevel(0) for dmat in self.materials.values()])
            subDLevel = min(subDLevel, GS.maxSubdivs)
        if (self.type == "subdivision_surface" and
            self.data and
            (self.data.SubDIALevel > 0 or self.data.SubDRenderLevel > 0)):
            mod = ob.modifiers.new("Subsurf", 'SUBSURF')
            renderLevel = self.data.SubDIALevel + self.data.SubDRenderLevel
            renderLevel = min(renderLevel, GS.maxSubdivs)
            mod.render_levels = renderLevel
            mod.levels = min(self.data.SubDIALevel, GS.maxSubdivs)
            if hasattr(mod, "use_limit_surface"):
                mod.use_limit_surface = False
            self.data.creaseEdges(context, ob)
        if subDLevel > renderLevel:
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
        if not self.highdef.uvs:
            if hdob.name not in LS.hdUvMissing:
                LS.hdUvMissing.append(hdob.name)
            return
        uvfaces = self.stripNegatives([f[1] for f in self.highdef.faces])
        if len(ob.data.uv_layers) > 0:
            uvname = ob.data.uv_layers[0].name
        else:
            uvname = "UV Layer"
        addUvs(hdob.data, uvname, self.highdef.uvs, uvfaces)


    def addHDMaterials(self, mats, prefix):
        for mat in mats:
            pg = self.hdobject.data.DazHDMaterials.add()
            pg.name = prefix + mat.name.rsplit("-",1)[0]
            pg.text = mat.name
        if self.data and self.data.vertex_pairs:
            # Geograft
            insts = []
            for inst in self.figure.instances.values():
                if inst and inst.parent and inst not in insts:
                    insts.append(inst)
                    par = inst.parent.geometries[0]
                    if par and par.hdobject and par.hdobject != par.rna:
                        par.addHDMaterials(mats, inst.name + "?" + prefix)


    def stripNegatives(self, faces):
        return [(f if f[-1] >= 0 else f[:-1]) for f in faces]


    def finalize(self, context, inst):
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
            scaleEyeMoisture(ob)
            if hdob and hdob != ob:
                scaleEyeMoisture(hdob)
        if LS.fitFile and ob.type == 'MESH':
            shiftMesh(ob, inst.worldmat.inverted())
            if hdob and hdob != ob:
                shiftMesh(hdob, inst.worldmat.inverted())


    def finishHD(self, context, ob, hdob, inst):
        from .finger import getFingerPrint
        if hdob != ob:
            self.copyHDMaterials(ob, hdob, context, inst)
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
        hdob.parent = ob.parent
        hdob.parent_type = ob.parent_type
        hdob.parent_bone = ob.parent_bone
        setWorldMatrix(hdob, ob.matrix_world)
        if hdob.name in inst.collection.objects:
            inst.collection.objects.unlink(hdob)


    def postbuild(self, context, inst):
        ob = self.rna
        if ob:
            pruneUvMaps(ob)
            self.addLSMesh(ob, inst, None)
            if GS.shellMethod == 'GEONODES':
                self.buildShells(context)


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
                if node.type in ['UVMAP', 'NORMAL_MAP']:
                    keep = False
                    break
            if keep:
                return mat
            else:
                nmat = mat.copy()
                for node in nmat.node_tree.nodes:
                    if node.type in ['UVMAP', 'NORMAL_MAP']:
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


    def setHideInfo(self):
        if self.data is None:
            return
        self.setHideInfoMesh(self.rna)
        if self.hdobject and self.hdobject != self.rna:
            self.setHideInfoMesh(self.hdobject)


    def setHideInfoMesh(self, ob):
        if ob.data is None:
            return
        ob.data.DazVertexCount = self.data.vertex_count
        if self.data.hidden_polys:
            hgroup = ob.data.DazMaskGroup
            for fn in self.data.hidden_polys:
                elt = hgroup.add()
                elt.a = fn
        if self.data.vertex_pairs:
            ggroup = ob.data.DazGraftGroup
            for vn,pvn in self.data.vertex_pairs:
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
        return False
    activateObject(context, hdob)
    hdme = hdob.data.copy()
    setMode('EDIT')
    bpy.ops.mesh.delete_loose()
    setMode('OBJECT')
    mod = hdob.modifiers.new("Multires", 'MULTIRES')
    try:
        bpy.ops.object.multires_rebuild_subdiv(modifier="Multires")
        finger = getFingerPrint(hdob)
        if finger != ob.data.DazFingerPrint:
            msg = ('Multires mesh "%s" does not match "%s"' % (hdob.name, ob.name))
            failtype = "Finger"
        else:
            failtype = None
    except RuntimeError:
        msg = ('Cannot rebuild subdivisions for "%s"' % hdob.name)
        failtype = "Runtime"
    if failtype is None:
        hdob.DazMultires = True
        return True
    elif strict:
        raise DazError(msg)
    else:
        reportError(msg, trigger=(2,4))
        hdob.modifiers.remove(mod)
        LS.hdFailures.append(hdob.name)
        if failtype == "Finger":
            hdob.data = hdme
        return False


class DAZ_OT_MakeMultires(DazOperator, IsMesh):
    bl_idname = "daz.make_multires"
    bl_label = "Make Multires"
    bl_description = "Convert HD mesh into mesh with multires modifier,\nand add vertex groups and extra UV layers"
    bl_options = {'UNDO'}

    def run(self, context):
        from .modifier import makeArmatureModifier, copyVertexGroups
        meshes = getSelectedMeshes(context)
        if len(meshes) != 2:
            raise DazError("Two meshes must be selected, \none subdivided and one at base resolution.")
        hdob = context.object
        baseob = None
        for ob in meshes:
            if ob != hdob:
                if len(hdob.data.vertices) > len(ob.data.vertices):
                    baseob = ob
                else:
                    hdob = ob
                    baseob = context.object
                break
        addMultires(context, baseob, hdob, True)
        copyUvLayers(baseob, hdob)
        rig = baseob.parent
        if not (rig and rig.type == 'ARMATURE'):
            return
        hdob.parent = rig
        makeArmatureModifier(rig.name, context, hdob, rig)
        copyVertexGroups(baseob, hdob)


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

    for uvlayer in list(hdob.data.uv_layers):
        hdob.data.uv_layers.remove(uvlayer)
    loopsMapping = setupLoopsMapping()
    for uvlayer in ob.data.uv_layers:
        hdlayer = makeNewUvloop(hdob.data, uvlayer.name, False)
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
        self.shstruct = {}
        self.shells = {}


    def __repr__(self):
        return ("<Geometry %s %s %s>" % (self.id, self.name, self.rna))


    def getInstance(self, ref, caller=None):
        iref = instRef(ref)
        if iref in self.nodes.keys():
            return self.nodes[iref]
        iref = unquote(iref)
        if iref in self.nodes.keys():
            return self.nodes[iref]
        else:
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
        if "SubDIALevel" in self.channels.keys():
            self.SubDIALevel = getCurrentValue(self.channels["SubDIALevel"], 0)
        if "SubDRenderLevel" in self.channels.keys():
            self.SubDRenderLevel = getCurrentValue(self.channels["SubDRenderLevel"], 0)
        if self.SubDIALevel == 0 and "current_subdivision_level" in struct.keys():
            self.SubDIALevel = struct["current_subdivision_level"]


    def setExtra(self, extra):
        if extra["type"] == "studio/geometry/shell":
            self.shstruct = extra
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
        if self.shstruct:
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
                missing = self.addShells(inst.shellNode, inst, self.material_group_vis)
                for mname,shmat,uv in missing:
                    msg = ("Missing shell material\n" +
                           "Material: %s\n" % mname +
                           "Node: %s\n" % geonode.name +
                           "Inst: %s\n" % inst.name +
                           "Shell: %s\n" % inst.shellNode.name +
                           "UV set: %s\n" % uv)
                    reportError(msg, trigger=(2,4))


    def addShells(self, inst, shinst, vis):
        missing = []
        geonode = inst.geometries[0]
        geo = geonode.data
        if shinst.shstruct:
            shgeonode = shinst.geometries[0]
            shname = shinst.name
            if GS.shellMethod == 'GEONODES':
                geonode.shellGeos.append(shgeonode)
                return []
            for mname,shmat in shgeonode.materials.items():
                if mname in vis.keys():
                    if not vis[mname]:
                        continue
                else:
                    print("Warning: no visibility for material %s" % mname)
                if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
                    shmat.getValue("getChannelOpacity", 1) == 0):
                    continue
                uv = self.uvs.get(mname)
                if uv and mname in geonode.materials.keys():
                    dmat = geonode.materials[mname]
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


    def addMoreShells(self, inst, mname, shname, shmat, uv, pprefix):
        from .figure import FigureInstance
        if not isinstance(inst, FigureInstance):
            return
        if mname in self.matused:
            return
        geonode = inst.geometries[0]
        geo = geonode.data
        prefix = pprefix + inst.node.name + "_"
        n = len(prefix)
        if mname[0:n] == prefix:
            mname1 = mname[n:]
        else:
            mname1 = None
        if mname1 and mname1 in geonode.materials.keys():
            dmat = geonode.materials[mname1]
            mshells = dmat.shells
            if shname not in mshells.keys():
                mshells[shname] = self.makeShell(shname, shmat, uv)
            shmat.ignore = True
            self.addNewUvset(uv, geo, inst)
            self.matused.append(mname)
        else:
            for key,child in inst.children.items():
                self.addMoreShells(child, mname, shname, shmat, uv, prefix)


    def addNewUvset(self, uv, geo, inst):
        if uv not in geo.uv_sets.keys():
            uvset = self.findUvSet(uv, inst.node.id)
            if uvset:
                geo.uv_sets[uv] = geo.uv_sets[uvset.name] = uvset


    def findUvSet(self, uv, url):
        from .asset import getDazPath, getRelativeRef
        from .transfer import findFileRecursive
        path = os.path.dirname(url)
        folder = getDazPath("%s/UV Sets" % path, strict=False)
        if not folder:
            folder = getDazPath(path)
        file = ("%s.dsf" % uv)
        if folder:
            file = findFileRecursive(folder, file)
            if file:
                url = unquote("%s#%s" % (file, uv))
                url = getRelativeRef(url)
                asset = self.getAsset(url)
                if asset:
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
                reportError(msg, trigger=(2,3))

        me = self.rna = bpy.data.meshes.new(geonode.getName())

        verts = self.verts
        edges = []
        guideVerts = guideEdges = []
        faces = self.faces
        if isinstance(geonode, GeoNode) and geonode.verts:
            if geonode.edges:
                verts = geonode.verts
                edges = geonode.edges
            elif geonode.faces:
                verts = geonode.verts
                faces = geonode.faces
            elif geonode.polylines:
                verts,edges,guideVerts,guideEdges = self.getEdges(geonode.verts, geonode.polylines, faces)
            elif self.polylines:
                verts = geonode.verts
            elif len(geonode.verts) == len(verts):
                verts = geonode.verts

        if not verts:
            self.addAllMaterials(me, geonode)
            return None, None

        if self.polylines and not guideVerts:
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
            reportError(msg, trigger=(2,3))

        if len(me.polygons) > 0:
            for fn,mn in enumerate(self.material_indices):
                f = me.polygons[fn]
                f.material_index = mn
                f.use_smooth = True

        self.setHairMatNums(me)
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

        ob = bpy.data.objects.new(inst.name, me)
        from .finger import getFingerPrint
        me.DazFingerPrint = getFingerPrint(ob)
        if hasShells:
            ob.DazVisibilityDrivers = True
        self.validateMesh(me)

        guideOb = None
        if guideVerts:
            guideMe = bpy.data.meshes.new("%s_GUIDE" % geonode.getName())
            guideMe.from_pydata(guideVerts, guideEdges, [])
            guideOb = bpy.data.objects.new("%s_GUIDE" % inst.name, guideMe)
            guideMe.DazFingerPrint = getFingerPrint(guideOb)
            self.setHairMatNums(guideMe)
            for mat in me.materials:
                guideMe.materials.append(mat)
            self.validateMesh(guideMe)

        return ob, guideOb


    def getEdges(self, verts, polylines, faces):
        edges = []
        guideEdges = []
        guideVerts = []
        if self.polylines and GS.useHairGuides:
            for pline in self.polylines:
                guideEdges += [(pline[i-1],pline[i]) for i in range(3,len(pline))]
        if polylines and not faces:
            vnmin = min([min(pline) for pline in polylines])
            if vnmin > 0:
                if GS.useHairGuides:
                    guideVerts = verts[:vnmin]
                verts = verts[vnmin:]
                polylines = [[vn-vnmin for vn in pline] for pline in polylines]
        for pline in polylines:
            edges += [(pline[i-1],pline[i]) for i in range(1,len(pline))]
        return verts, edges, guideVerts, guideEdges


    def setHairMatNums(self, me):
        if self.polylines:
            me.DazMatNums.clear()
            self.setHairType(me)
            for pline in self.polylines:
                mnum = pline[1]
                for n in range(len(pline)-3):
                    item = me.DazMatNums.add()
                    item.a = mnum


    def setHairType(self, me):
        if me.polygons:
            me.DazHairType = 'SHEET'
        else:
            me.DazHairType = 'LINE'


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
        if GS.materialsByIndex:
            for dmat in geonode.materials.values():
                self.addMaterial(dmat, me, geonode)
                if dmat.shells:
                    hasShells = True
            return hasShells

        for mn,mname in enumerate(self.polygon_material_groups):
            dmat = None
            if mname in geonode.materials.keys():
                dmat = geonode.materials[mname]
            else:
                ref = self.fileref + "#" + mname
                dmat = self.getAsset(ref)
            if dmat:
                self.addMaterial(dmat, me, geonode)
                if dmat.shells:
                    hasShells = True
            else:
                if GS.verbosity > 3:
                    mats = list(geonode.materials.keys())
                    mats.sort()
                    print("Existing materials:\n  %s" % mats)
                reportError("Material \"%s\" not found in geometry %s" % (mname, geonode.name), trigger=(2,4))
                return False
        return hasShells


    def addMaterial(self, dmat, me, geonode):
        if dmat.rna is None:
            msg = ("Material without rna:\n  %s\n  %s\n  %s" % (dmat, geonode, self))
            reportError(msg, trigger=(2,3))
        me.materials.append(dmat.rna)
        self.dmaterials.append(dmat)
        if dmat.uv_set and dmat.uv_set.checkSize(me):
            self.uv_set = dmat.uv_set
        if GS.useAutoSmooth:
            me.use_auto_smooth = dmat.getValue(["Smooth On"], False)
            me.auto_smooth_angle = dmat.getValue(["Smooth Angle"], 89.9)*D


    def addAllMaterials(self, me, geonode):
        for key, dmat in geonode.materials.items():
            if dmat.rna:
                me.materials.append(dmat.rna)
                self.dmaterials.append(dmat)


    def validateMesh(self, me):
        if me.validate():
            reportError('Invalid mesh "%s". Correcting.' % me.name, trigger=(2,5))
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
                reportError(msg, trigger=(2,3))


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
        self.material = None
        self.built = []


    def __repr__(self):
        return ("<Uvset %s '%s' %d %d %s>" % (self.id, self.name, len(self.uvs), len(self.polyverts), self.material))


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
            for fn,vn,uv in self.polyverts:
                f = me.polygons[fn]
                for n,vn1 in enumerate(f.vertices):
                    if vn1 == vn:
                        polyverts[fn][n] = uv
        return polyverts


    def build(self, context, me, geo, setActive):
        if self.name is None or me in self.built:
            return
        if len(me.polygons) == 0:
            print("NO UVs", me.name, self.name)
            return

        polyverts = self.getPolyVerts(me)
        self.checkPolyverts(me, polyverts, False)
        uvloop = makeNewUvloop(me, self.getLabel(), setActive)

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
                    uvloop.data[m].uv = uv
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
        self.built.append(me)


    def fixUdims(self, context, mn, udim, geo):
        fixed = False
        key = geo.polygon_material_groups[mn]
        for geonode in geo.nodes.values():
            if key in geonode.materials.keys():
                dmat = geonode.materials[key]
                dmat.fixUdim(context, udim)
                fixed = True
        if not (fixed or GS.materialsByIndex):
            print("Material \"%s\" not found" % key)


def makeNewUvloop(me, name, setActive):
    uvtex = me.uv_layers.new()
    uvtex.name = name
    uvloop = me.uv_layers[-1]
    uvloop.active_render = setActive
    if setActive:
        me.uv_layers.active_index = len(me.uv_layers) - 1
    return uvloop


def addUvs(me, name, uvs, uvfaces):
    if not uvs:
        return
    uvloop = makeNewUvloop(me, name, True)
    m = 0
    for f in uvfaces:
        for vn in f:
            uvloop.data[m].uv = uvs[vn]
            m += 1

#-------------------------------------------------------------
#   Prune Uv textures
#-------------------------------------------------------------

def pruneUvMaps(ob):
    if ob.data is None or len(ob.data.uv_layers) <= 1:
        return
    print("Pruning UV maps")
    uvtexs = {}
    for uvtex in ob.data.uv_layers:
        uvtexs[uvtex.name] = [uvtex, uvtex.active_render]
    for mat in ob.data.materials:
        if mat:
            for node in mat.node_tree.nodes:
                if (node.type == "ATTRIBUTE" and
                    node.attribute_name in uvtexs.keys()):
                    uvtexs[node.attribute_name][1] = True
                elif (node.type == "UVMAP" and
                    node.uv_map in uvtexs.keys()):
                    uvtexs[node.uv_map][1] = True
    for uvtex,used in uvtexs.values():
        if not used:
            ob.data.uv_layers.remove(uvtex)


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
    for uvloop in ob.data.uv_layers:
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
                uvloop.data[m].uv[0] += ushift
                uvloop.data[m].uv[1] += vshift
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
        from .material import addUdim
        if ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = True
        addUdimsToUVs(ob, False, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = True
            addUdim(mat, -mat.DazUDim, -mat.DazVDim)


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
        from .material import addUdim
        if not ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = False
        addUdimsToUVs(ob, True, 0, 0)
        for mn,mat in enumerate(ob.data.materials):
            if not mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = False
            addUdim(mat, mat.DazUDim, mat.DazVDim)


class DAZ_OT_UDimsFromTextures(DazOperator, IsMesh):
    bl_idname = "daz.udims_from_textures"
    bl_label = "UDIMs From Textures"
    bl_description = "Restore UV coordinates based on texture names"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.udimsFromTextures(ob)

    def udimsFromTextures(self, ob):
        dims = {}
        print("Shift materials:")
        for mn,mat in enumerate(ob.data.materials):
            udim = vdim = 0
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if (node.type == 'TEX_IMAGE' and
                        node.image):
                        tile = node.image.name.rsplit("_", 1)[-1]
                        if len(tile) == 4 and tile.isdigit():
                            udim = (int(tile) - 1001) % 10
                            vdim = (int(tile) - 1001) // 10
            dims[mn] = (udim, vdim)
            print("  ", mat.name, udim, vdim)

        for uvloop in ob.data.uv_layers:
            m = 0
            for fn,f in enumerate(ob.data.polygons):
                udim,vdim = dims[f.material_index]
                for _ in f.vertices:
                    uvs = uvloop.data[m].uv
                    uvs[0] += udim - int(uvs[0])
                    uvs[1] += vdim - int(uvs[1])
                    m += 1

#-------------------------------------------------------------
#   Load UVs
#-------------------------------------------------------------

class DAZ_OT_LoadUV(DazOperator, DazFile, SingleFile, IsMesh):
    bl_idname = "daz.load_uv"
    bl_label = "Load UV Set"
    bl_description = "Load a UV set to the active mesh"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        from .fileutils import getFolders
        folders = getFolders(context.object, ["UV Sets/", ""])
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
            uvloop = makeNewUvloop(me, uvset.getLabel(), False)
            vnmax = len(uvset.uvs)
            m = 0
            for fn,f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvloop.data[m].uv = uv
                    m += 1

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

    storeData : BoolProperty(
        name = "Store Data",
        description = "Store data in a file",
        default = True)

    overwrite : BoolProperty(
        name = "Overwrite",
        description = "Overwrite stored data",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "storeData")
        self.layout.prop(self, "overwrite")

    def invoke(self, context, event):
        ob = context.object
        if (ob.DazBlendFile and ob.DazBlendFile != bpy.data.filepath):
            self.storeData = False
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        from .morphing import getRigFromObject
        from .load_json import saveJson
        ob = context.object
        rig = getRigFromObject(ob)
        self.nothing = True
        if self.storeData:
            if not bpy.data.filepath:
                raise DazError("Save the blend file first")
            struct = { "filetype" : "mesh_data", "meshes" : [] }
        else:
            struct = None
        for ob1 in rig.children:
            if ob1.type == 'MESH':
                self.finalizeMesh(ob1, struct)
        if ob.type == 'MESH' and ob not in rig.children:
            self.finalizeMesh(ob, struct)
        if self.nothing:
            print("Nothing to save.")
        elif self.storeData:
            rig.DazBlendFile = bpy.data.filepath
            folder,path = getMeshDataFile(bpy.data.filepath)
            if not os.path.exists(folder):
                os.makedirs(folder)
            if self.overwrite or not os.path.exists(path):
                saveJson(struct, path)
                print('Saved "%s"' % path)


    def finalizeMesh(self, ob, struct):
        from .finger import getFingerPrint
        if self.storeData:
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
        clearMeshProps(ob.data)


def clearMeshProps(me):
    me.DazRigidityGroups.clear()
    me.DazOrigVerts.clear()
    #me.DazFingerPrint = getFingerPrint(ob)
    me.DazGraftGroup.clear()
    me.DazMaskGroup.clear()
    me.DazMatNums.clear()
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
    DAZ_OT_UDimsFromTextures,
    DAZ_OT_LoadUV,
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
    bpy.types.Mesh.DazMatNums = CollectionProperty(type = DazIntGroup)
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
