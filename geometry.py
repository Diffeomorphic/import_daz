# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
        self.hdshells = {}
        self.hdobject = None
        self.hdType = 'NONE'
        self.index = figure.count
        self.matSubDLevel = 0.0
        self.isShell = False
        self.shellGeos = []
        self.shellPrefix = ""
        self.push = 0
        self.assigned = False
        self.conform_target = None
        SimNode.__init__(self)


    def __repr__(self):
        return ("<GeoNode %s %d M:%d C: %s R: %s>" % (self.id, self.index, len(self.materials), self.center, self.rna))

    def errorWrite(self, ref, fp):
        fp.write('   G: %s\n' % (self))

    def isVisibleMaterial(self, dmat):
        if isinstance(self.data, Geometry):
            return self.data.isVisibleMaterial(dmat)
        return True

    def getName(self):
        if self.figureInst:
            return self.figureInst.node.name
        else:
            return Asset.getName(self)

    def getRig(self):
        ob = self.rna
        if ob and ob.parent and ob.parent.type == 'ARMATURE':
            return ob.parent
        return None

    def isGraft(self):
        return (self.data and self.data.vertex_count > 0)

    def getGraftParent(self):
        if self.isGraft() and self.figureInst:
            figpar = self.figureInst.parent
            if figpar and figpar.geometries:
                return figpar.geometries[0]


    def preprocess(self, context, inst):
        if isinstance(self.data, Geometry):
            self.data.preprocess(context, inst)
        elif inst.isStrandHair:
            geo = self.data = Geometry(self.fileref)
            geo.name = inst.name
            geo.isStrandHair = True
            geo.preprocess(context, inst)


    def getObjectName(self, inst):
        from .figure import Figure
        if isinstance(self.figure, Figure):
            return "%s Mesh" % noHDName(inst.name)
        else:
            return noHDName(inst.name)


    def buildShells(self, context):
        if not self.shellGeos:
            return
        from .geonodes import makeShell, linkShell, makeShellModifier
        ob = self.rna
        hdob = self.hdobject
        if hdob and getModifier(hdob, 'MULTIRES'):
            ob = hdob
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
                unlinkAll(shell, False)
                linkShell(shell)
            else:
                shell = makeShell(shgeonode.name, shmats, ob)
                shgeonode.rna = shell
            offset = GS.scale * shgeonode.push
            makeShellModifier(shell, ob, offset, mnames, mats, shmats)


    def addLSMesh(self, ob, inst, rigname):
        if self.assigned:
            return
        elif inst.isStrandHair:
            LS.hairs[rigname].append(ob)
        elif ob and ob.type == 'MESH':
            LS.meshes[rigname].append(ob)
        self.assigned = True


    def subtractCenter(self, ob, inst, center):
        if not LS.fitFile:
            ob.location = -center
        inst.center = center


    def buildHDObject(self, context, ob, inst, me):
        if me == ob.data and not self.isGraft():
            hdob = ob
        else:
            hdob = bpy.data.objects.new(HDName(ob.name), me)
            setModernProps(hdob)
            dazRna(hdob).DazVisibilityDrivers = dazRna(ob).DazVisibilityDrivers
            self.arrangeObject(hdob, inst, context, Zero)
        dazRna(hdob).DazHDMesh = True
        self.hdobject = inst.hdobject = hdob
        LS.hdmeshes[LS.rigname].append(hdob)
        return hdob


    def subdivideObject(self, ob, inst, context):
        if not isinstance(self.data, Geometry):
            return
        if self.highdef:
            me = self.buildHDMesh(ob)
            hdob = self.buildHDObject(context, ob, inst, me)
            self.addHDUvs(ob, hdob)
            self.hdType = 'HIGHDEF'
            if GS.useMultires and hdob.data.polygons:
                self.hdType = addMultires(context, ob, hdob, False, self.data.SubDIALevel, self.data)
            if self.hdType in ['MULTIRES', 'HIGHDEF']:
                if len(ob.data.uv_layers) > len(hdob.data.uv_layers):
                    print("COPY UVS", ob.name, hdob.name)
                    copyUvLayers(context, ob, hdob)
            elif self.hdType == 'NONE':
                print("HD mesh same as base mesh:", ob.name)
        elif LS.useHDObjects:
            def ignoreHDGraft():
                from .finger import getFingerPrint, FingerPrintsHD
                parent = self.getGraftParent()
                if parent and parent.hdobject:
                    fing = getFingerPrint(parent.hdobject)
                    if fing and fing not in FingerPrintsHD.keys():
                        return True

            if ignoreHDGraft():
                print("Ignore HD graft %s" % ob.name)
            else:
                print("No HD object, use base mesh %s" %  ob.name)
                hdob = self.buildHDObject(context, ob, inst, ob.data)
        if ob and self.data:
            if not self.conform_target:
                dazRna(ob).DazConforms = False
            self.data.buildRigidity(ob)
            if self.hdType == 'MULTIRES':
                self.data.buildRigidity(self.hdobject)

        renderLevel = 0
        if self.materials:
            self.matSubDLevel = max([dmat.getSubDLevel(0) for dmat in self.materials.values()])
            if self.matSubDLevel > GS.maxSubdivs:
                for dmat in self.materials.values():
                    mat = dmat.rna
                    if mat:
                        if hasattr(mat, "displacement_method"):
                            if mat.displacement_method == 'DISPLACEMENT':
                                mat.displacement_method = GS.displacementMethod
                        else:
                            if mat.cycles.displacement_method == 'DISPLACEMENT':
                                mat.cycles.displacement_method = GS.displacementMethod

        if self.isSubdivided():
            mod = ob.modifiers.new("Subsurf", 'SUBSURF')
            meshSubDLevel = self.data.SubDIALevel + self.data.SubDRenderLevel
            renderLevel = max(meshSubDLevel, self.matSubDLevel)
            mod.render_levels = min(renderLevel, GS.maxSubdivs)
            mod.levels = min(self.data.SubDIALevel, GS.maxSubdivs)
            if meshSubDLevel == 0:
                mod.subdivision_type = 'SIMPLE'
            if hasattr(mod, "use_limit_surface"):
                mod.use_limit_surface = False
            if self.data.SubDEdgeInterpolateLevel == 1:
                # [ "Soft Corners And Edges", "Sharp Edges and Corners", "Sharp Edges" ]
                try:
                    mod.boundary_smooth = 'PRESERVE_CORNERS'
                except AttributeError:
                    pass
            self.data.creaseEdges(context, ob)
            if hasattr(ob.data, "use_auto_smooth"):
                ob.data.use_auto_smooth = False


    def isSubdivided(self):
        if not self.data:
            return False
        elif self.matSubDLevel > 0:
            return True
        elif (self.type == "subdivision_surface" and
              self.data.SubDIALevel + self.data.SubDRenderLevel > 0):
            return True
        else:
            return False


    def addMappings(self, selmap):
        self.data.mappings = dict([(key,val) for val,key in selmap["mappings"]])


    def buildHDMesh(self, ob):
        if not self.highdef.faces:
            print("HD mesh %s without faces: (%d %d)" % (ob.name, len(ob.data.vertices), len(self.highdef.verts)))
            return ob.data
        verts = self.highdef.verts
        edges = []
        faces = self.stripNegatives([f[0] for f in self.highdef.faces])
        mnums = [f[4] for f in self.highdef.faces]
        nverts = len(verts)
        me = bpy.data.meshes.new(HDName(ob.data.name))
        setModernProps(me)
        if GS.verbosity >= 3:
            print("Build HD mesh for %s: %d verts, %d faces, %d edges" % (ob.name, nverts, len(faces), len(edges)))
        me.from_pydata(verts, edges, faces)
        if GS.verbosity >= 3:
            print("HD mesh %s built" % me.name)
        for f in me.polygons:
            f.material_index = mnums[f.index]
            f.use_smooth = True
        self.data.setHairType(me)
        self.data.validateMesh(me, HDName(ob.name))
        return me


    def addHDUvs(self, ob, hdob):
        if not self.highdef.uvs:
            if hdob.name not in LS.hdUvMissing:
                print("No HD UVs for %s" % hdob.name)
                LS.hdUvMissing.append(hdob.name)
            return

        def addUvLayer(uvname, uvs, faces, setActive):
            if uvname in hdob.data.uv_layers:
                print("HD UV layer %s already exists" % uvname)
                return
            uvfaces = self.stripNegatives([f[1] for f in faces])
            uvlayer = makeNewUvLayer(hdob.data, uvname, setActive)
            if GS.verbosity >= 3:
                print("Add HD UV layer %s to %s" % (uvlayer.name, hdob.name))
            m = 0
            for f in uvfaces:
                for vn in f:
                    uvlayer.data[m].uv = uvs[vn]
                    m += 1

        if len(ob.data.uv_layers) > 0:
            uvname = ob.data.uv_layers[0].name
        else:
            uvname = "UV Layer"
        addUvLayer(uvname, self.highdef.uvs, self.highdef.faces, True)
        for hdshell in self.hdshells.values():
            uvname = LS.shellUvs.get(hdshell.label)
            if uvname is None:
                uvname = LS.shellUvs.get(hdshell.name)
            if uvname is None:
                uvname = hdshell.label
                print("Missing shell UV layer: %s" % uvname)
            addUvLayer(uvname, hdshell.uvs, hdshell.faces, False)


    def addHDMaterials(self, matgroups, inst, mats, prefix):
        def addToTable(mats, prefix):
            for mat in mats:
                if mat:
                    mname = "%s%s" % (prefix, stripName(mat.name))
                    table[mname] = baseName(mat.name)

        if matgroups:
            from .figure import FigureInstance
            table = {}
            addToTable(mats, "")
            for child in inst.children.values():
                if isinstance(child, FigureInstance):
                    for geo in child.geometries:
                        ob = geo.rna
                        if isGeograft(ob):
                            addToTable(ob.data.materials, "%s_" % child.id)
            for mg in matgroups:
                pg = dazRna(self.hdobject.data).DazHDMaterials.add()
                pg.name = mg
                pg.text = table.get(mg, mg)
            return

        for mat in mats:
            pg = dazRna(self.hdobject.data).DazHDMaterials.add()
            pg.name = prefix + stripName(mat.name)
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
                        par.addHDMaterials(matgroups, None, mats, "%s?%s" % (inst.name, prefix))


    def stripNegatives(self, faces):
        return [(f if f[-1] >= 0 else f[:-1]) for f in faces]


    def finalize(self, context, inst):
        from .material import sortMaterialsByName
        from .matsel import driveShellInfluence
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
            smooth = False
            dmats = [(mnum,dmat) for mnum,dmat in enumerate(self.materials.values()) if dmat]
            for mnum,dmat in dmats:
                dmat.correctEmitArea(ob, mnum)
                smooth = (smooth or dmat.getValue(["Smooth On"], False))
                if dmat.shader == 'TOON':
                    LS.toons.append(ob)

            def selectMaterialPolys(me, mnum):
                bpy.ops.mesh.select_mode(type='VERT')
                bpy.ops.mesh.select_all(action='DESELECT')
                setMode('OBJECT')
                for f in me.polygons:
                    f.select = (f.material_index == mnum)
                setMode('EDIT')

            if smooth and GS.useSharpEdges and not self.isSubdivided():
                activateObject(context, ob)
                if hasattr(ob.data, "use_auto_smooth"):
                    setMode('EDIT')
                    bpy.ops.mesh.reveal()
                    bpy.ops.mesh.split_normals()
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.mark_sharp(clear=True)
                    for mnum,dmat in dmats:
                        angle = dmat.getValue(["Smooth Angle"], 89.9)
                        selectMaterialPolys(ob.data, mnum)
                        bpy.ops.mesh.hide(unselected=True)
                        bpy.ops.mesh.select_all(action='DESELECT')
                        bpy.ops.mesh.select_mode(type='EDGE')
                        bpy.ops.mesh.edges_select_sharp(sharpness=angle*D)
                        bpy.ops.mesh.mark_sharp()
                        bpy.ops.mesh.reveal()
                    setMode('OBJECT')
                    try:
                        bpy.ops.object.shade_smooth(use_auto_smooth=True)
                    except TypeError:
                        bpy.ops.object.shade_smooth()
                else:
                    setMode('EDIT')
                    for mnum,dmat in dmats:
                        angle = dmat.getValue(["Smooth Angle"], 89.9)
                        selectMaterialPolys(ob.data, mnum)
                        bpy.ops.mesh.select_mode(type='EDGE')
                        bpy.ops.mesh.set_sharpness_by_angle(angle=angle*D)
                    setMode('OBJECT')

            self.scaleEyeMoisture(context, ob, dazRna(ob).DazMesh)
            if GS.useMaterialsByName:
                sortMaterialsByName(ob)
            if hdob and hdob.data != ob.data:
                uvlayer = getActiveUvLayer(ob)
                if uvlayer:
                    hduvlayer = hdob.data.uv_layers.get(uvlayer.name)
                    if hduvlayer:
                        hduvlayer.active = hduvlayer.active_render = True
                #if GS.usePruneNodes:
                #    pruneUvMaps(hdob)
                self.scaleEyeMoisture(context, hdob, dazRna(ob).DazMesh)
                if GS.useMaterialsByName:
                    sortMaterialsByName(hdob)
                if GS.useShellDrivers:
                    driveShellInfluence(hdob)
            if GS.useShellDrivers:
                driveShellInfluence(ob)
            if GS.shellMethod == 'GEONODES':
                self.buildShells(context)

        def shiftMesh(ob, inst):
            from .node import isUnitMatrix
            if not isUnitMatrix(inst.worldmat):
                mat = inst.worldmat.inverted()
                for v in ob.data.vertices:
                    v.co = mat @ v.co

        if LS.fitFile and ob.type == 'MESH':
            shiftMesh(ob, inst)
            if hdob and hdob.data != ob.data:
                shiftMesh(hdob, inst)


    def scaleEyeMoisture(self, context, ob, meshtype):
        if GS.onScaleEyeMoisture != 'NONE':
            url = self.url.lower().rsplit("#",1)[0]
            if (meshtype in ["Genesis8-female", "Genesis8-male"] and
                url in ["/data/daz%203d/genesis%208/female/genesis8female.dsf",
                        "/data/daz%203d/genesis%208/female/genesis8male.dsf"]):
                verts = []
                for mn,mat in enumerate(ob.data.materials):
                    if mat and mat.name.lower().startswith(("eyemoisture", "eyereflection")):
                        for f in ob.data.polygons:
                            if f.material_index == mn:
                                verts += f.vertices
                        break
                vgrp = ob.vertex_groups.new(name="Displace")
                for vn in set(verts):
                    vgrp.add([vn], 1.0, 'REPLACE')
                strength = 0.01 * GS.scale
            elif (False and meshtype == "Toon9-eye-socket" and
                  url == "/data/daz%203d/g9tooncommon/genesis%209%20toon%20eye%20socket/g9tooneyesocket.dsf"):
                vgrp = None
                strength = 0.1 * GS.scale
            else:
                return

            from .store import addModifierFirst
            mod = addModifierFirst(ob, "Displace", 'DISPLACE')
            mod.strength = strength
            mod.mid_level = 0
            if vgrp:
                mod.vertex_group = vgrp.name
            if GS.onScaleEyeMoisture == 'APPLY':
                context.view_layer.objects.active = ob
                applyModifier(mod.name)
                vgrp = ob.vertex_groups.get("Displace")
                if vgrp:
                    ob.vertex_groups.remove(vgrp)


    def finishHD(self, context, ob, hdob, inst):
        from .finger import getFingerPrint
        if hdob == ob and isGeograft(ob):
            return
        if LS.hdcollection is None:
            LS.hdcollection = bpy.data.collections.new(name = HDName(LS.collection.name))
            context.collection.children.link(LS.hdcollection)
            for ob1 in LS.collection.objects:
                if (ob1.type != 'MESH' and
                    ob1.name not in LS.hdcollection.objects):
                    LS.hdcollection.objects.link(ob1)
        if hdob.name not in LS.hdcollection.objects:
            LS.hdcollection.objects.link(hdob)
        if ob.parent and ob.parent.name not in LS.hdcollection.objects:
            LS.hdcollection.objects.link(ob.parent)
        if hdob == ob:
            return
        if self.hdType in ['HIGHDEF','MULTIRES']:
            self.addHDMaterials(self.highdef.matgroups, inst, ob.data.materials, "")
            self.copyHDMaterials(ob, hdob, context, inst)
        hdob.parent = ob.parent
        hdob.parent_type = ob.parent_type
        hdob.parent_bone = ob.parent_bone
        setWorldMatrix(hdob, ob.matrix_world)
        dazRna(hdob.data).DazFingerPrint = getFingerPrint(hdob)
        if dazRna(hdob.data).DazFingerPrint == dazRna(ob.data).DazFingerPrint:
            dazRna(hdob).DazMesh = dazRna(ob).DazMesh
        setWorldMatrix(hdob, ob.matrix_world)
        if hdob.name in LS.collection.objects:
            LS.collection.objects.unlink(hdob)


    def postbuild(self, context, inst):
        ob = self.rna
        hdob = self.hdobject
        if ob:
            self.setHideInfoMesh(ob)
            if hdob and hdob != ob:
                self.setHideInfoMesh(hdob)
            self.addLSMesh(ob, inst, LS.rigname)
            for extra in self.extra:
                for favo in extra.get("favorites", []):
                    pg = dazRna(ob.data).DazFavorites.add()
                    pg.name = favo


    def copyHDMaterials(self, ob, hdob, context, inst):
        def getDataMaterial(mname):
            while True:
                for mat in LS.materials.values():
                    if baseName(mat.name) == mname:
                        return mat
                words = mname.split("_",1)
                if len(words) == 1:
                    return None
                mname = words[1]

        matnames = dict([(pg.name,pg.text) for pg in dazRna(hdob.data).DazHDMaterials])
        for mn,mname in enumerate(self.highdef.matgroups):
            mat = None
            if mname in matnames.keys():
                mname = matnames[mname]
            mat = LS.materials.get(mname)
            if mat is None:
                mat = getDataMaterial(mname)
            hdob.data.materials.append(mat)
        inst.parentObject(context, self.hdobject)


    def setHideInfoMesh(self, ob):
        geo = self.data
        if ob.data is None:
            return
        dazRna(ob.data).DazVertexCount = geo.vertex_count
        if geo.hidden_polys:
            hgroup = dazRna(ob.data).DazMaskGroup
            for fn in geo.hidden_polys:
                elt = hgroup.add()
                elt.a = fn
        if geo.vertex_pairs:
            ggroup = dazRna(ob.data).DazGraftGroup
            for vn,pvn in geo.vertex_pairs:
                pair = ggroup.add()
                pair.a = vn
                pair.b = pvn


    def hideFaceGroups(self, hidden):
        from .geonodes import addMaskFaceModifier
        if self.data is None:
            return
        ob = self.rna
        pgs = dazRna(ob.data).DazPolygonGroup
        for fgroup in hidden:
            if fgroup not in pgs.keys():
                fgroup = self.data.mappings.get(fgroup)
            addMaskFaceModifier(ob, "DazPolygonGroup", fgroup, True)
        hdob = self.hdobject
        if hdob and hdob != ob:
            pgs = dazRna(hdob.data).DazPolygonGroup
            for fgroup in hidden:
                if fgroup not in pgs.keys():
                    fgroup = self.data.mappings.get(fgroup)
                addMaskFaceModifier(hdob, "DazPolygonGroup", fgroup, True)


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

def addMultires(context, ob, hdob, strict, subdivlevel, geo):
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

    finger = getFingerPrint(ob)
    nmods = len(hdob.modifiers)
    mod = hdob.modifiers.new("Multires", 'MULTIRES')
    for n in range(nmods-1):
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    ok = True
    nlevels = 0
    if subdivlevel is None:
        try:
            bpy.ops.object.multires_rebuild_subdiv(modifier="Multires")
            nlevels = mod.levels
        except RuntimeError:
            ok = False
    else:
        for n in range(subdivlevel):
            try:
                bpy.ops.object.multires_unsubdivide(modifier="Multires")
                nlevels = n+1
            except RuntimeError:
                ok = False
            if not ok:
                print("Failed to unsubdive %d of %d levels" % (n, subdivlevel))
                break
    if ok:
        hdfinger = getFingerPrint(hdob)
        if hdfinger == finger or not strict:
            if GS.verbosity >= 3:
                print('Rebuilt %d subdiv levels for "%s"' % (nlevels, hdob.name))
            mod.levels = mod.sculpt_levels = 0
            if hdfinger == finger:
                if geo:
                    try:
                        geo.addFaceMap(hdob, "DazPolygonGroup", geo.polygon_groups, geo.polygon_indices)
                        geo.addFaceMap(hdob, "DazMaterialGroup", geo.polygon_material_groups, geo.material_indices)
                    except IndexError:
                        LS.hdMismatch.append(hdob.name)
            else:
                LS.hdMismatch.append(hdob.name)
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
            mod.levels = mod.sculpt_levels = 0
            return 'MULTIRES'

    msg = ('Cannot unsubdivide "%s"' % hdob.name)
    if strict:
        raise DazError(msg)
    reportError(msg)
    hdob.modifiers.remove(mod)
    LS.hdFailures.append(hdob.name)
    return 'HIGHDEF'


class DAZ_OT_MakeMultires(DazPropsOperator, IsMesh):
    bl_idname = "daz.make_multires"
    bl_label = "Make Multires"
    bl_description = "Convert HD mesh into mesh with multires modifier,\nand add vertex groups and extra UV layers"
    bl_options = {'UNDO'}

    useNewUvs : BoolProperty(
        name = "New UV Layers",
        description = "Copy UV layers to multires mesh even if it already has UVs",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useNewUvs")

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
        if len(baseob.data.vertices) > len(hdob.data.vertices):
            tmp = baseob
            baseob = hdob
            hdob = tmp
        print('Base "%s", HD "%s"' % (baseob.name, hdob.name))
        hdtype = addMultires(context, baseob, hdob, False, None, None)
        if hdtype == 'MULTIRES':
            if self.useNewUvs or hdob.data.uv_layers is None:
                copyUvLayers(context, baseob, hdob)
            ok,msg = copyVertexGroups(baseob, hdob)
            if not ok:
                print("Cannot copy vertex groups: %s" % msg)
        if hdtype != 'NONE':
            rig = baseob.parent
            hdob.parent = rig
            if rig and rig.type == 'ARMATURE' and not getModifier(hdob, 'ARMATURE'):
                makeArmatureModifier(rig.name, context, hdob, rig)


def copyUvLayers(context, src, trg, selection=None):
    def setupLoopsMapping(me):
        loopsMapping = {}
        for f in me.polygons:
            loops = dict([(vn, f.loop_indices[i]) for i,vn in enumerate(f.vertices)])
            fid = tuple( sorted(list(f.vertices)) )
            if fid in loopsMapping:
                raise RuntimeError("duplicated face_id?")
            loopsMapping[fid] = loops
        return loopsMapping

    def copyLayer(srcdata, trgdata, loopsMapping):
        for f in src.data.polygons:
            fid = tuple( sorted(list(f.vertices)) )
            if fid not in loopsMapping:
                return False
            for i,vn in enumerate(f.vertices):
                if vn not in loopsMapping[fid]:
                    print("Bad vertex", vn)
                    continue
                trgloop = loopsMapping[fid][vn]
                srcloop = f.loop_indices[i]
                trgdata[trgloop].uv = srcdata[srcloop].uv
        return True

    def copyAllLayers(trg):
        loopsMapping = setupLoopsMapping(trg.data)
        for srclayer in list(src.data.uv_layers):
            if selection is None or srclayer.name in selection:
                if srclayer.name in trg.data.uv_layers.keys():
                    print('UV layer "%s" already exists' % srclayer.name)
                    continue
                trglayer = makeNewUvLayer(trg.data, srclayer.name, False)
                ok = copyLayer(srclayer.data, trglayer.data, loopsMapping)
                if not ok:
                    trg.data.uv_layers.remove(trglayer)
                    return False
        return True

    ok = copyAllLayers(trg)
    if not ok:
        print("Cannot copy UV layer to target mesh.")
        from .transfer import transferUvLayers
        transferUvLayers(context, src, [trg])

#-------------------------------------------------------------
#   UnGeometry
#   Where DS wants a geometry and Blender an empty
#-------------------------------------------------------------

class UnGeometry(Asset, Channels):
    def __init__(self, etype, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.verts = []
        self.etype = etype
        if self.etype == "studio_geometry_channels":
            self.polygon_material_groups = []
        self.uv_sets = {}

    def __repr__(self):
        return "<UnGeometry %s>" % (self.id)

    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)
        if self.etype == "studio_geometry_channels":
            self.polygon_material_groups = struct["polygon_material_groups"]["values"]

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
        return ("<Geometry %s %s %s>" % (self.id, self.name, list(self.nodes.keys())))


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
        from .cycles import setRenderMethod, setShadowMethod
        mat = LS.hiddenMaterial = bpy.data.materials.new("HIDDEN")
        setModernProps(mat)
        mat.diffuse_color[3] = 0
        if BLENDER5:
            mat.use_nodes = True
        setRenderMethod(mat, False, True)
        setShadowMethod(mat, False)
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
        if GS.shellMethod in ['MATERIAL', 'GEONODES']:
            if inst.shellNode:
                vis = inst.channels.get("Visible")
                if vis and not vis.get("current_value", True):
                    print("Ignoring hidden shell %s" % inst.name)
                    return
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
        from .asset import normalizeRef
        from .fileutils import findPathRecursive
        folder = os.path.dirname(unquote(url))
        filepath = findPathRecursive(uv, folder, ["UV Sets/"])
        if filepath:
            relpath = GS.getRelativePath(filepath)
            url = normalizeRef("%s#%s" % (relpath, uv))
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
        setModernProps(me)

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
            if not self.isStrandHair:
                self.addAllMaterials(me, geonode)
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
            dazRna(me).DazHairType = 'TUBE'

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
                pgs = dazRna(me).DazMaterialSets.add()
                pgs.name = struct["name"]
                for mname in struct["materials"]:
                    pg = pgs.names.add()
                    pg.name = mname

        obname = geonode.getObjectName(inst)
        ob = bpy.data.objects.new(obname, me)
        setModernProps(ob)
        from .finger import getFingerPrint
        dazRna(me).DazFingerPrint = getFingerPrint(ob)
        if hasShells:
            dazRna(ob).DazVisibilityDrivers = True

        geonodes = list(self.nodes.values())
        if me.vertices and geonodes and self.id:
            pgs = dazRna(ob.data).DazGraftData
            pg = pgs.add()
            pg.name = geonodes[0].getName()
            pg.s = self.id.rsplit("/",1)[0]
            pg.i = len(ob.data.vertices)
            vattr = ob.data.attributes.new("DazVertex", 'INT', 'POINT')
            gattr = ob.data.attributes.new("DazGraft", 'INT', 'POINT')
            for vn in range(len(me.vertices)):
                vattr.data[vn].value = vn
                gattr.data[vn].value = 0
        if me.polygons:
            self.addFaceMap(ob, "DazPolygonGroup", self.polygon_groups, self.polygon_indices)
            self.addFaceMap(ob, "DazMaterialGroup", self.polygon_material_groups, self.material_indices)

        self.validateMesh(me, obname)
        guideOb = None
        if guideVerts:
            guideMe = bpy.data.meshes.new("%s_GUIDE" % geonode.getName())
            setModernProps(guideMe)
            guideMe.from_pydata(guideVerts, guideEdges, [])
            guideOb = bpy.data.objects.new("%s_GUIDE" % inst.name, guideMe)
            setModernProps(guideOb)
            guideMe.DazFingerPrint = getFingerPrint(guideOb)
            self.setHairMatNums(guideMe, guidePolymats)
            for mat in me.materials:
                guideMe.materials.append(mat)
            self.validateMesh(guideMe, guideOb.name)

        return ob, guideOb


    def addFaceMap(self, ob, aname, groups, indices):
        pgs = getattr(dazRna(ob.data), aname)
        for group in groups:
            pg = pgs.add()
            pg.name = group
            pg.a = len(pgs) - 1
        attr = ob.data.attributes.new(aname, 'INT', 'FACE')
        for fn,gn in enumerate(indices):
            attr.data[fn].value = gn


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
            dazRna(me).DazPolylineMaterials.clear()
            self.setHairType(me)
            for mnum in polymats:
                item = dazRna(me).DazPolylineMaterials.add()
                item.a = mnum


    def setHairType(self, me):
        if me.polygons:
            dazRna(me).DazHairType = 'SHEET'
        else:
            dazRna(me).DazHairType = 'LINE'


    def creaseEdges(self, context, ob):
        if self.edge_weights:
            from .tables import getVertEdges
            vertedges = getVertEdges(ob)
            weights = {}
            for vn1,vn2,w in self.edge_weights:
                for e in vertedges[vn1]:
                    if vn2 in e.vertices:
                        weights[e.index] = w
            level = max(1, self.SubDIALevel + self.SubDRenderLevel)
            activateObject(context, ob)
            if not BLENDER3:
                bpy.ops.geometry.attribute_add(name='crease_edge', domain='EDGE')
            setMode('EDIT')
            bm = bmesh.from_edit_mesh(ob.data)
            bm.edges.ensure_lookup_table()
            if BLENDER3:
                crease = bm.edges.layers.crease.verify()
            else:
                crease = bm.edges.layers.float.get('crease_edge')
            for en,w in weights.items():
                e = bm.edges[en]
                e[crease] = min(1.0, w/level)
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
                if GS.verbosity >= 3:
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


    def validateMesh(self, me, name):
        if me.validate():
            reportError('Invalid mesh "%s". Correcting.' % me.name)
            LS.invalidMeshes.append(noMeshName(name))


    def addAllMaterials(self, me, geonode):
        for key, dmat in geonode.materials.items():
            if dmat.rna:
                me.materials.append(dmat.rna)
                self.dmaterials.append(dmat)


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
            def addRigid(prefix, rgroup, key):
                aname = "%s:%s" % (prefix, rgroup.id)
                verts = group[key]["values"]
                if GS.useRigidityAttributes:
                    data = ob.data.attributes.new(aname, 'BOOLEAN', 'POINT').data
                    for vn in verts:
                        data[vn].value = True
                else:
                    weights = [(vn, 1.0) for vn in verts]
                    buildVertexGroup(ob, aname, weights)
                setattr(rgroup, key, aname)

            strange = False
            for group in self.rigidity.get("groups", []):
                rgroup = dazRna(ob.data).DazRigidityGroups.add()
                rgroup.id = group["id"]
                rgroup.rotation_mode = group["rotation_mode"]
                rgroup.scale_modes = " ".join(group["scale_modes"])
                addRigid("Rigid:Ref", rgroup, "reference_vertices")
                addRigid("Rigid:Mask", rgroup, "mask_vertices")
                if group["rotation_mode"] != "none":
                    strange = True
                for mode in group["scale_modes"]:
                    if mode != "none":
                        strange = True

            if "weights" in self.rigidity.keys():
                nverts = len(ob.data.vertices)
                rweights = self.rigidity["weights"]["values"]
                buildVertexGroup(ob, "Rigidity", rweights)
                if strange:
                    return
                wvalues = [w for vn,w in rweights]
                if len(rweights) == nverts and min(wvalues) > 0.9999:
                    dazRna(ob.data).DazFullyRigid = True


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
    s = GS.scale
    if GS.zup:
        return [[s*v[0], -s*v[2], s*v[1]] for v in verts]
    else:
        return [[s*v[0], s*v[1], s*v[2]] for v in verts]


def isGeograft(ob):
    return (dazRna(ob.data).DazVertexCount > 0)

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
        if first:
            LS.shellUvs[self.name] = uv


    def __repr__(self):
        dmat = self.material
        return ("<Shell %s %s S:%s D:%s U:%s>" % (self.name, dmat.name, self.single, dmat.getDiffuse(), self.uv))


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
            return
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
                if vn < vnmax and mn < nmats:
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
    if (ob.data is None or
        len(ob.data.uv_layers) <= 1 or
        GS.shellMethod == 'GEONODES'):
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

#----------------------------------------------------------
#   Finalize meshes
#----------------------------------------------------------

class DAZ_OT_FinalizeMeshes(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.finalize_meshes"
    bl_label = "Finalize Meshes"
    bl_description = "Remove internal properties from meshes.\nDisables some tools but may improve performance"
    bl_options = {'UNDO'}

    maxSubsurf : IntProperty(
        name = "Maximal Subsurf Level",
        description = "Maximal subsurf level",
        min = 0,
        default = 2)

    keepVertex : BoolProperty(
        name = "Keep Original Vertex Numbers",
        description = "Keep information about original vertex numbers.\nNecessary to import morphs to modified meshes",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "maxSubsurf")
        self.layout.prop(self, "keepVertex")


    def run(self, context):
        def finalizeMesh(ob):
            from .finger import getFingerPrint
            for mod in ob.modifiers:
                if mod.type == 'SUBSURF':
                    if mod.levels > self.maxSubsurf:
                        mod.levels = self.maxSubsurf
                    if mod.render_levels > self.maxSubsurf:
                        mod.render_levels = self.maxSubsurf
            clearMeshProps(ob, keepVertex=self.keepVertex)

        ob = context.object
        rig = getRigFromContext(context)
        if rig:
            for ob1 in getMeshChildren(rig):
                finalizeMesh(ob1)
        if ob.type == 'MESH':
            finalizeMesh(ob)


def clearMeshProps(ob, keepVertex=False):
    me = ob.data
    for gname in ["Rigidity"]:
        vgrp = ob.vertex_groups.get(gname)
        if vgrp:
            ob.vertex_groups.remove(vgrp)
    dazRna(me).DazRigidityGroups.clear()
    dazRna(me).DazGraftGroup.clear()
    dazRna(me).DazMaskGroup.clear()
    dazRna(me).DazPolylineMaterials.clear()
    dazRna(me).DazMaterialSets.clear()
    dazRna(me).DazHDMaterials.clear()
    dazRna(ob).DazMorphUrls.clear()
    dazRna(me).DazMaterialGroup.clear()
    dazRna(me).DazPolygonGroup.clear()

    def clearAttribute(key):
        attr = me.attributes.get(key)
        if attr:
            me.attributes.remove(attr)

    clearAttribute("DazMaterialGroup")
    clearAttribute("DazPolygonGroup")
    if not keepVertex:
        clearAttribute("DazVertex")
        clearAttribute("DazGraft")
        dazRna(me).DazGraftData.clear()
    for key in me.attributes.keys():
        if key.startswith("paired_body_vert_"):
            clearAttribute(key)



def getMeshDataFile(filepath):
    folder = os.path.dirname(filepath)
    folder = os.path.join(folder, "mesh_data")
    fname = os.path.splitext(os.path.basename(filepath))[0]
    path = os.path.join(folder, "%s.json" % fname)
    return folder,path

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PruneUvMaps,
    DAZ_OT_MakeMultires,
    DAZ_OT_FinalizeMeshes,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
