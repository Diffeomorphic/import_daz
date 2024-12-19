# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import bpy
import numpy as np
from .error import *
from .utils import *
from .selector import JCMSelector
from .driver import DriverUser
from .morphing import MS, RigidTransfer

#-------------------------------------------------------------
#
#-------------------------------------------------------------

class MatchOperator(DazPropsOperator):
    transferMethod = 'NEAREST'
    useNonConforming = True
    ignoreRigidity = False
    needsTarget = True

    def storeState(self, context):
        DazPropsOperator.storeState(self, context)
        self.mesh = context.object
        self.storeMesh(self.mesh)
        self.rig = getRigFromMesh(self.mesh)
        self.storeRig(self.rig)


    def restoreState(self, context):
        self.restoreRig(self.rig)
        self.restoreMesh(self.mesh)
        DazPropsOperator.restoreState(self, context)


    def prepareBvhTree(self, context, src):
        updateScene(context)
        self.bvhtree = None
        if (self.transferMethod in ['NEAREST', 'SELECTED']):
            from mathutils.bvhtree import BVHTree
            activateObject(context, src)
            setMode('EDIT')
            bpy.ops.mesh.reveal()
            setMode('OBJECT')
            me = src.data
            verts = [tuple(v.co) for v in me.vertices]
            faces1 = [tuple(f.vertices[0:4]) for f in me.polygons]
            tris1 = [f[0:3] for f in faces1]
            faces2 = [f for f in faces1 if len(f) == 4]
            tris2 = [(v0,v2,v3) for v0,v1,v2,v3 in faces2]
            tris = tris1 + tris2
            self.bvhtree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
            self.verts = np.array(verts)
            self.tris = np.array(tris, dtype=np.uint32)
            print("BVH created")


    def getTargets(self, src, context):
        checkObjectTransforms(src)
        objects = []
        for ob in getSelectedMeshes(context):
            if (ob != src and
                len(ob.data.polygons) > 0 and
                (ob.get("DazConforms", True) or self.useNonConforming)):
                objects.append(ob)
                checkObjectTransforms(ob)
                if (ob.parent and
                    ob.parent != src.parent and
                    self.transferMethod != 'BY_NUMBER'):
                    msg = '"%s" parent is not same as\n"%s" parent' % (ob.name, src.name)
                    self.addWarning(msg)
        if not objects and not ES.easy and self.needsTarget:
            msg = ('No good target meshes selected.\nTarget meshes must have faces.\n' +
                   'Also, shapekeys are not transferred to non-conforming meshes\nunless the option "Non-conforming meshes" is enabled')
            raise DazError(msg)
        return objects


    def findMatchNearest(self, bvh, trg):
        if self.projection is None:
            closest = [(v.co, bvh.find_nearest(v.co))
                for v in trg.data.vertices]
        else:
            closest = [(v.co, bvh.find_nearest(v.co + Vector(self.projection[v.index])))
                for v in trg.data.vertices]
        # (position, normal, index, distance)
        cverts = np.array([list(x) for x,data in closest if data[0]])
        offsets = np.array([list(x-data[0]) for x,data in closest if data[0]])
        fnums = [data[2] for x,data in closest if data[0]]
        tris = self.tris[fnums]
        tverts = self.verts[tris]
        A = np.transpose(tverts, axes=(0,2,1))
        B = cverts - offsets
        try:
            w = np.linalg.solve(A, B)
            msg = None
        except np.linalg.LinAlgError:
            msg = "Numerical error when finding match.\nConsider using the Legacy transfer method instead"
        if msg:
            raise DazError(msg)
        self.match = (tris, w, offsets)

#----------------------------------------------------------
#   Vertex group transfer
#----------------------------------------------------------

def transferVertexGroups(context, src, targets, threshold):
    activateObject(context, src)
    targets = [trg for trg in targets if trg.data.polygons]
    if len(targets) == 0:
        return
    for trg in targets:
        trg.select_set(True)
        trg.vertex_groups.clear()
    print("Transfer vertex groups %s => %s" % (src.name, [trg.name for trg in targets]))
    bpy.ops.object.data_transfer(
        data_type = 'VGROUP_WEIGHTS',
        vert_mapping = 'POLYINTERP_NEAREST',
        layers_select_src = 'ALL',
        layers_select_dst = 'NAME')
    if threshold > 0:
        for trg in targets:
            pruneVertexGroups(trg, threshold, [], False)

#----------------------------------------------------------
#   UV layer transfer
#----------------------------------------------------------

def transferUvLayers(context, src, targets):
    activateObject(context, src)
    for trg in targets:
        trg.select_set(True)
    print("Transfer UV layers %s => %s" % (src.name, [trg.name for trg in targets]))
    bpy.ops.object.data_transfer(
        data_type = 'UV',
        loop_mapping = 'NEAREST_POLYNOR',
        layers_select_src = 'ALL',
        layers_select_dst = 'NAME')

#----------------------------------------------------------
#   Morphs transfer
#----------------------------------------------------------

class DAZ_OT_TransferShapekeys(JCMSelector, MatchOperator, DriverUser, RigidTransfer, IsShape):
    bl_idname = "daz.transfer_shapekeys"
    bl_label = "Transfer Shapekeys"
    bl_description = "Transfer shapekeys from active mesh to selected meshes"
    bl_options = {'UNDO'}

    usePropDriver = True
    defaultSelect = True
    needsTarget : BoolProperty(default = True)

    transferMethod : EnumProperty(
        items = [('NEAREST', "Nearest Face", "Transfer shapekeys from nearest source face.\nUse to transfer shapekeys to clothes"),
                 #('SELECTED', "Selected", "One transfer shapekeys from selected vertices"),
                 ('BY_NUMBER', "By Number", "Transfer shapekeys by vertex number.\nBoth meshes must have the same number of vertices"),
                 ('BODY', "Body", "Only transfer vertices as long as they match exactly.\nUse to transfer shapekeys from body to merged mesh"),
                 ('GEOGRAFT', "Geograft", "Transfer shapekeys to nearest target vertex.\nUse to transfer shapekeys from geograft to merged mesh"),
                 ('LEGACY', "Legacy", "Transfer using Blender's data transfer modifier.\nVery slow but works in general")],
        name = "Transfer Method",
        description = "Method used to transfer morphs",
        default = 'NEAREST')

    useDrivers : BoolProperty(
        name = "Transfer Drivers",
        description = "Transfer both shapekeys and drivers",
        default = True)

    useShapeAsDriver : BoolProperty(
        name = "Shapekeys As Drivers",
        description = "Use the main shapekey to drive the other shapekeys",
        default = True)

    useStrength : BoolProperty(
        name = "Strength Multiplier",
        description = "Add a strength multiplier to drivers",
        default = False)

    useVendorMorphs : BoolProperty(
        name = "Use Vendor Morphs",
        description = "Use customized morphs provided by vendor,\notherwise always auto-transfer morphs",
        default = True)

    useOverwrite : BoolProperty(
        name = "Overwrite Existing Shapekeys",
        description = "Overwrite existing shapekeys or create new ones",
        default = True)

    useSelectedOnly : BoolProperty(
        name = "Selected Verts Only",
        description = "Only copy to selected vertices",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "transferMethod", expand=True)
        row = self.layout.row()
        row.prop(self, "useDrivers")
        row.prop(self, "useShapeAsDriver")
        row.prop(self, "useVendorMorphs")
        row.prop(self, "useOverwrite")
        row = self.layout.row()
        row.prop(self, "useStrength")
        row.prop(self, "useSelectedOnly")
        row.prop(self, "useNonConforming")
        row.prop(self, "ignoreRigidity")
        JCMSelector.draw(self, context)


    def run(self, context):
        from .load_morph import newLine
        t1 = perf_counter()
        src = context.object
        if not src.data.shape_keys:
            raise DazError("Cannot transfer because object    \n%s has no shapekeys   " % (src.name))
        self.initTmp()
        self.eps = 0.02*GS.scale    # 0.2 mm
        if not self.useDrivers:
            self.useStrength = False
        targets = self.getTargets(src, context)
        self.prepareBvhTree(context, src)
        self.createTmp()
        try:
            failed = self.transferAllMorphs(context, src, targets)
        finally:
            self.deleteTmp()
        t2 = perf_counter()
        print("Morphs transferred in %.1f seconds" % (t2-t1))
        if failed:
            msg = ("Morph transfer to the following meshes\nfailed due to insufficient memory:")
            for trg in failed:
                msg += ("\n    %s" % trg.name)
            msg += "\nTry the General transfer method instead.       "
            raise DazError(msg)


    def transferAllMorphs(self, context, src, targets):
        from .load_morph import newLine
        failed = []
        hskeys = src.data.shape_keys
        if hskeys is None:
            return failed
        self.driverPaths = {}
        if self.useDrivers and hskeys.animation_data:
            self.driverPaths = dict([(fcu.data_path,fcu) for fcu in hskeys.animation_data.drivers])
        snames = self.getSelectedProps()
        srcboxes = {}
        for sname in snames:
            hskey = hskeys.key_blocks[sname]
            srcboxes[sname] = self.computeShapeBox(src, hskey)
        for trg in targets:
            if not self.transferMorphs(snames, src, trg, srcboxes, context):
                failed.append(trg)
            newLine()
        return failed


    def transferMorphs(self, snames, src, trg, srcboxes, context):
        from .load_morph import printName
        from .morphing import MP
        from .modifier import getBasicShape

        startProgress("Transfer morphs %s => %s" %(src.name, trg.name))
        scn = context.scene
        GS.setRootPaths()
        activateObject(context, src)
        self.projection = MP.getProjection(trg)
        if not self.findMatch(src, trg):
            return False
        hskeys = src.data.shape_keys
        cbasic,cskeys,new = getBasicShape(trg)
        if src.active_shape_key_index < 0:
            src.active_shape_key_index = 0
        trg.active_shape_key_index = 0
        trg.select_set(True)
        trgbox = self.computeObjectBox(trg)

        if "Rigidity" in trg.vertex_groups.keys() and not self.ignoreRigidity:
            if GS.useRigidityAttributes:
                def getVertsFromGroup(ob, gname):
                    attr = ob.data.attributes.get(gname)
                    if attr:
                        return [vn for vn,data in enumerate(attr.data) if data.value]
                    else:
                        return []
            else:
                def getVertsFromGroup(ob, gname):
                    vgrp = ob.vertex_groups.get(gname)
                    if vgrp:
                        idx = vgrp.index
                        obverts = ob.data.vertices
                        verts = [v.index for v in ob.data.vertices for g in v.groups if g.group == idx]
                        return verts
                    else:
                        return []

            rigidity_table = dict([(vgrp.index, {}) for vgrp in trg.vertex_groups])
            for v in trg.data.vertices:
                for g in v.groups:
                    rigidity_table[g.group][v.index] = g.weight
            rigidity_groups = []
            for rgroup in trg.data.DazRigidityGroups:
                refverts = getVertsFromGroup(trg, rgroup.reference_vertices)
                if len(refverts) == 0:
                    continue
                maskverts = getVertsFromGroup(trg, rgroup.mask_vertices)
                rigidity_groups.append((rgroup, refverts, maskverts))
        else:
            rigidity_groups = []
            rigidity_table = None

        nskeys = len(snames)
        for idx,sname in enumerate(snames):
            showProgress(idx, nskeys)
            if sname not in hskeys.key_blocks.keys():
                printName(" ?", sname)
                continue
            hskey = hskeys.key_blocks[sname]

            if self.outsideBox(srcboxes[sname], trgbox):
                printName(" 0", sname)
                continue

            if sname in cskeys.key_blocks.keys():
                if self.useOverwrite:
                    cskey = cskeys.key_blocks[sname]
                    trg.shape_key_remove(cskey)
                else:
                    printName(" X", sname)
                    continue

            cskey = None
            filepath = None
            if self.useVendorMorphs:
                from .fileutils import findPathRecursiveFromObject
                filepath = findPathRecursiveFromObject(sname, trg, ["Morphs/", "Base/Morphs/"])
            if filepath is not None:
                cskey = self.loadMorph(filepath, src, trg, scn)
            if cskey:
                cskey.name = sname
                printName(" *", sname)
            elif self.autoTransfer(src, trg, hskey):
                cskey = cskeys.key_blocks[sname]
                if cskey and rigidity_table:
                    try:
                        rigid = self.correctForRigidity(trg, cskey, rigidity_groups, rigidity_table)
                    except IndexError:
                        rigid = False
                    if rigid:
                        trg.shape_key_remove(cskey)
                        cskey = None
                    else:
                        printName(" +", sname)
                else:
                    printName(" +", sname)

            if cskey:
                from .driver import addGeneralDriver
                cskey.slider_min = hskey.slider_min
                cskey.slider_max = hskey.slider_max
                cskey.value = self.svalues[sname]
                if self.useDrivers:
                    path = 'key_blocks["%s"].value' % hskey.name
                    if self.useShapeAsDriver:
                        addGeneralDriver(cskey, "value", hskeys, path, "x")
                    else:
                        fcu = self.driverPaths.get(path)
                        if fcu:
                            self.copyDriver(fcu, cskeys)
                    path = 'key_blocks["%s"].mute' % hskey.name
                    fcu = self.driverPaths.get(path)
                    if fcu:
                        self.copyDriver(fcu, cskeys)
            else:
                printName(" -", sname)

        if (cbasic and
            len(trg.data.shape_keys.key_blocks) == 1 and
            trg.data.shape_keys.key_blocks[0] == cbasic):
            if not ES.easy:
                print("No shapekeys transferred to %s" % trg.name)
            trg.shape_key_remove(cbasic)
        return True


    def loadMorph(self, filepath, src, trg, scn):
        from .load_json import JL
        from .files import parseAssetFile
        from .modifier import Morph
        from .hd_data import addSkeyToUrls
        LS.forMorphLoad(trg)
        struct = JL.load(filepath)
        asset = parseAssetFile(struct)
        if (not isinstance(asset, Morph) or
            len(trg.data.vertices) != asset.vertex_count):
            return None
        asset.buildMorph(trg, useBuild=True)
        if asset.rna:
            skey,_,_ = asset.rna
            addSkeyToUrls(trg, asset, skey)
            return skey
        else:
            return None


    # Improvements by Suttisak Denduangchai, issue 749, 754
    def correctForRigidity(self, ob, skey, rigidity_groups, rigidity_table):
        from mathutils import Matrix

        for rgroup, refverts, maskverts in rigidity_groups:
            if GS.verbosity >= 3 and not ES.easy:
                print("Rigidity group: %s" % rgroup.id)
            obverts = ob.data.vertices
            base_coords = [obverts[vn].co for vn in refverts]
            skeydata = skey.data
            shapekey_coords = [skeydata[vn].co for vn in refverts]
            base_center_coords = np.average(base_coords, axis=0)
            shapekey_center_coords = np.average(shapekey_coords, axis=0)

            # If the center doesn't move, we can remove the shapekey if the mesh is fully rigid.
            diff = base_center_coords-shapekey_center_coords
            dist = np.sum(np.abs(diff))
            if dist < self.eps and ob.data.get("DazFullyRigid", False):
                return True

            rotmode = rgroup.rotation_mode
            if rotmode != "none":
                msg = ("Not yet implemented: Rigidity rotmode = %s\n" % rotmode +
                       "Object: %s\n" % ob.name +
                       "Shapekey: %s\n" % skey.name)
                reportError(msg, trigger=(3,5))

            scalemodes = rgroup.scale_modes.split(" ")

            # I think Daz3d use Singular Value Decomposition to determine which X,Y,Z scaling between shapekey_coords and base_coords
            # https://www.daz3d.com/forums/discussion/comment/636426/
            # https://gregorygundersen.com/blog/2018/12/10/svd/

            # Transfrom Base Coordinate to be relative to its center
            base_coords_relative_to_base_center_coords = base_coords - base_center_coords
            # Singular value decomposition
            S1= np.linalg.svd(base_coords_relative_to_base_center_coords, compute_uv=False)
            if len(S1) < 3:
                continue

            # Transfrom Shapekey Coordinate to be relative to its center
            shapekey_coords_relative_to_shapekey_center_coords = shapekey_coords - shapekey_center_coords
            # Singular value decomposition
            S2= np.linalg.svd(shapekey_coords_relative_to_shapekey_center_coords, compute_uv=False)
            # U matrix is average coordinates of polygon, S is matrix is how coordinates dilate and reflex. The dilated and reflexed shape (without rotation) is U cross S
            scale_between_shapekey_and_base_averagecoords = S2/S1

            refverts_base_dimension = [["X",S1[0],scale_between_shapekey_and_base_averagecoords[0]],["Y",S1[1],scale_between_shapekey_and_base_averagecoords[1]],["Z",S1[2],scale_between_shapekey_and_base_averagecoords[2]]]
            # Sort from max dimension to min dimension to determine Primary (scaling of max dimension) to Tertiary (scaling of min dimension) scale mode
            # ex. [["Y",10,1.1],["X",5,1.2],["Z",2,1.05]]
            refverts_base_dimension.sort(key=lambda x: -x[1])

            # Determine First - Thrid axis by target object (eg. Geograft) dimensions
            target_dimension= [["X",ob.dimensions.x,1],["Y",ob.dimensions.y,1],["Z",ob.dimensions.z,1]]
            target_dimension.sort(key=lambda x: -x[1])

            for n,smode in enumerate(scalemodes): # Scale mode of First to Third axis which is defined in Rigidity group editor in Daz3d
                if smode == "primary":
                    target_dimension[n][2] = refverts_base_dimension[0][2]
                elif smode == "secondary":
                    target_dimension[n][2] = refverts_base_dimension[1][2]
                elif smode == "tertiary":
                    target_dimension[n][2] = refverts_base_dimension[2][2]
                # No-scale No need to reassign 1 again
            target_dimension.sort(key=lambda x: x[0])
            smat = Matrix.Identity(3)
            base_center_vector = Vector((0,0,0))
            shapekey_center_vector = Vector((0,0,0))
            for n in range(3):
                base_center_vector[n] = base_center_coords[n]
                shapekey_center_vector[n] = shapekey_center_coords[n]
            for n in range(3):
                smat[n][n]= target_dimension[n][2]

            if "Rigidity" in ob.vertex_groups.keys():
                rigidity_map_vertex_group_index = ob.vertex_groups["Rigidity"].index
                for vn in maskverts: # Called Rigidity Participant Vertex in Daz3D
                    v = obverts[vn]
                    for g in v.groups:
                        if g.group == rigidity_map_vertex_group_index:
                            # Max Rigidity (Rigidity=1) coordinate
                            max_rigidity_coordinate = (smat @ (obverts[vn].co - base_center_vector)) + shapekey_center_vector
                            # Min Rigidity (Rigidity=0) coordinate
                            min_rididity_coordinate = skeydata[vn].co
                            # Mix both coordinate using Rigidity Weight Map
                            skeydata[vn].co = (max_rigidity_coordinate * g.weight) + ((1-g.weight)*min_rididity_coordinate)
                # Save DazRigidityScaleFactor to Armature
                parent = ob.parent
                rig = None
                while parent:
                    if(parent.type == "ARMATURE"):
                        rig = parent
                        break
                    parent = parent.parent

                if rig:
                    def affectBoneRigidity(ob, affectedbonename, rigidity_group):
                        newbonename = rigidity_group.affected_bones.add()
                        newbonename.name = affectedbonename
                        affectedbone_vertex_group_index = ob.vertex_groups[affectedbonename].index
                        vertex_group_weight = 0
                        rigidity_map_weight_sum = 0
                        for vn,vertex_enveloping_bone_weight in rigidity_table[affectedbone_vertex_group_index].items():
                            rigidity_weight = rigidity_table[rigidity_map_vertex_group_index].get(vn)
                            if rigidity_weight is not None:
                                rigidity_map_weight_sum += vertex_enveloping_bone_weight*rigidity_weight
                                vertex_group_weight += vertex_enveloping_bone_weight
                        if (vertex_group_weight > 0):
                            newbonename.weight = rigidity_map_weight_sum/vertex_group_weight

                    if ob.name in rig.data.DazRigidityScaleFactors:
                        rigidity_group = rig.data.DazRigidityScaleFactors[ob.name]
                    else:
                        rigidity_group = rig.data.DazRigidityScaleFactors.add()
                        rigidity_group.name = ob.name
                        rigidity_group.base_center_coord = base_center_vector

                    rigidity_group.affected_bones.clear()
                    affectedbones = [vx for vx in ob.vertex_groups.keys() if vx in rig.data.bones]
                    for affectedbonename in affectedbones:
                        affectBoneRigidity(ob, affectedbonename, rigidity_group)

                    if skey.name in rigidity_group.shapekeys:
                        shapekey_scalefactor = rigidity_group.shapekeys[skey.name]
                    else:
                        shapekey_scalefactor = rigidity_group.shapekeys.add()
                        shapekey_scalefactor.name = skey.name

                    shapekey_scalefactor.shapekey_center_coord = shapekey_center_vector
                    shapekey_scalefactor.scale = [smat[j][i] for i in range(len(smat)) for j in range(len(smat))]
        return False


    def computeShapeBox(self, src, hskey):
        eps = self.eps
        verts = src.data.vertices
        hdata = hskey.data
        box = []
        hverts = [v.index for v in verts if (hdata[v.index].co - v.co).length > eps]
        for j in range(3):
            xkey = [verts[vn].co[j] for vn in hverts]
            if xkey:
                minkey = min(xkey)
                maxkey = max(xkey)
            else:
                minkey = maxkey = 0
            box.append((minkey,maxkey))
        return box


    def computeObjectBox(self, ob):
        box = []
        verts = ob.data.vertices
        for j in range(3):
            coords = [v.co[j] for v in verts]
            box.append((min(coords), max(coords)))
        return box


    def outsideBox(self, srcbox, trgbox):
        for srcside,trgside in zip(srcbox, trgbox):
            if srcside[0] > trgside[1] or srcside[1] < trgside[0]:
                return True
        return False


    def findMatch(self, src, trg):
        t1 = perf_counter()
        if self.bvhtree:
            self.findMatchNearest(self.bvhtree, trg)
        elif self.transferMethod == 'LEGACY':
            return True
        elif self.transferMethod == 'BODY':
            self.findMatchExact(src, trg)
        elif self.transferMethod == 'BY_NUMBER':
            self.findMatchByNumber(src, trg)
        elif self.transferMethod == 'GEOGRAFT':
            self.findMatchGeograft(src, trg)
        t2 = perf_counter()
        if not ES.easy:
            print("Matching table created in %.1f seconds" % (t2-t1))
        return True


    def autoTransfer(self, src, trg, hskey):
        if self.transferMethod == 'LEGACY':
            return self.autoTransferSlow(src, trg, hskey)
        elif self.transferMethod in ['BODY', 'BY_NUMBER']:
            return self.autoTransferExact(src, trg, hskey)
        elif self.transferMethod in ['NEAREST', 'SELECTED']:
            return self.autoTransferFace(src, trg, hskey)
        elif self.transferMethod == 'GEOGRAFT':
            return self.autoTransferExact(src, trg, hskey)

    #----------------------------------------------------------
    #   Slow transfer
    #----------------------------------------------------------

    def autoTransferSlow(self, src, trg, hskey):
        hverts = src.data.vertices
        cverts = trg.data.vertices
        facs = {0:1.0, 1:1.0, 2:1.0}
        offsets = {0:0.0, 1:0.0, 2:0.0}
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            coord = [data.co[n] - hverts[j].co[n] for j,data in enumerate(hskey.data)]
            if min(coord) == max(coord):
                fac = 1.0
            else:
                fac = 1.0/(max(coord)-min(coord))
            facs[n] = fac
            offs = offsets[n] = min(coord)
            weights = [fac*(co-offs) for co in coord]

            vgrp = src.vertex_groups.new(name=vgname)
            for vn,w in enumerate(weights):
                vgrp.add([vn], w, 'REPLACE')
            bpy.ops.object.data_transfer(
                data_type = "VGROUP_WEIGHTS",
                vert_mapping = 'POLYINTERP_NEAREST',
                layers_select_src = 'ACTIVE',
                layers_select_dst = 'NAME')
            src.vertex_groups.remove(vgrp)

        coords = []
        isZero = True
        eps = self.eps
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            vgrp = trg.vertex_groups[vgname]
            weights = [[g.weight for g in v.groups if g.group == vgrp.index][0] for v in trg.data.vertices]
            fac = facs[n]
            offs = offsets[n]
            coord = [cverts[j].co[n] + w/fac + offs for j,w in enumerate(weights)]
            coords.append(coord)
            wmax = max(weights)/fac + offs
            wmin = min(weights)/fac + offs
            if abs(wmax) > eps or abs(wmin) > eps:
                isZero = False
            trg.vertex_groups.remove(vgrp)

        if isZero:
            return False

        cskey = trg.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            verts = trg.data.vertices
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    if verts[j].select:
                        cskey.data[j].co[n] = x
        else:
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    cskey.data[j].co[n] = x

        return True

    #----------------------------------------------------------
    #   Exact
    #----------------------------------------------------------

    def findMatchExact(self, src, trg):
        eps = self.eps
        hverts = src.data.vertices
        self.match = []
        nhverts = len(hverts)
        hvn = 0
        for cvn,cv in enumerate(trg.data.vertices):
            hv = hverts[hvn]
            while (hv.co - cv.co).length > eps:
                hvn += 1
                if hvn < nhverts:
                    hv = hverts[hvn]
                else:
                    print("Matched %d vertices" % cvn)
                    return
            self.match.append((cvn, hvn, cv.co - hv.co))


    def autoTransferExact(self, src, trg, hskey):
        cverts = trg.data.vertices
        hverts = src.data.vertices
        cskey = trg.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            for cvn,hvn,offset in self.match:
                if cverts[cvn].select:
                    cskey.data[cvn].co = hskey.data[hvn].co + offset
        else:
            for cvn,hvn,offset in self.match:
                cskey.data[cvn].co = hskey.data[hvn].co + offset
        return True

    #----------------------------------------------------------
    #   By number
    #----------------------------------------------------------

    def findMatchByNumber(self, src, trg):
        if len(src.data.vertices) != len(trg.data.vertices):
            raise DazError("Both meshes must have the same number of vertices\nto use the By Number transfer method")
        tverts = trg.data.vertices
        self.match = [(vn, vn, tverts[vn].co - v.co) for vn,v in enumerate(src.data.vertices)]

    #----------------------------------------------------------
    #   Nearest vertex and face matching
    #----------------------------------------------------------

    def nearestNeighbor(self, hvn, hverts, cverts):
        diff = cverts - hverts[hvn]
        dists = np.sum(np.abs(diff), axis=1)
        cvn = np.argmin(dists, axis=0)
        return cvn, hvn, Vector(cverts[cvn]-hverts[hvn])


    def findMatchGeograft(self, src, trg):
        hverts = np.array([list(v.co) for v in src.data.vertices])
        cverts = np.array([list(v.co) for v in trg.data.vertices])
        nhverts = len(hverts)
        self.match = [self.nearestNeighbor(hvn, hverts, cverts) for hvn in range(nhverts)]


    def autoTransferFace(self, src, trg, hskey):
        if self.transferMethod == 'SELECTED':
            tskey = src.data.shape_keys.key_blocks[hskey.name]
        else:
            tskey = hskey
        hcos = np.array([list(data.co) for data in tskey.data])
        tris, w, offsets = self.match
        tcos = hcos[tris]
        ccos = np.sum(tcos * w[:,:,None], axis=1) + offsets
        cverts = np.array([list(v.co) for v in trg.data.vertices])
        dists = np.sum(np.abs(ccos-cverts), axis=1)
        dmax = np.max(dists)
        if dmax < self.eps:
            return False
        cskey = trg.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            cverts = trg.data.vertices
            for cvn,co in enumerate(ccos):
                if cverts[cvn].select:
                    cskey.data[cvn].co = co
        else:
            for cvn,co in enumerate(ccos):
                cskey.data[cvn].co = co
        return True

#----------------------------------------------------------
#   Apply all shapekeys
#----------------------------------------------------------

def applyAllShapekeys(ob):
    skeys = ob.data.shape_keys
    if skeys:
        nverts = len(ob.data.vertices)
        verts = np.array([v.co for v in ob.data.vertices])
        coords = verts.copy()
        for skey in skeys.key_blocks:
            scoords = np.array([skey.data[n].co for n in range(nverts)])
            coords += skey.value*(scoords - verts)
        blocks = list(skeys.key_blocks)
        blocks.reverse()
        for skey in blocks:
            ob.shape_key_remove(skey)
        for v,co in zip(ob.data.vertices, coords):
            v.co = co

#-------------------------------------------------------------
#   Prune vertex groups
#-------------------------------------------------------------

def pruneVertexGroups(ob, threshold, bnames, verbose):
    def findVertexGroups(ob, bnames):
        nverts = len(ob.data.vertices)
        nvgrps = len(ob.vertex_groups)
        vnames = [vgrp.name for vgrp in ob.vertex_groups if vgrp.name not in bnames]
        weights = dict([(gn, np.zeros(nverts, dtype=float)) for gn in range(nvgrps)])
        for v in ob.data.vertices:
            for g in v.groups:
                weights[g.group][v.index] = g.weight
        return vnames,weights

    vnames,weights = findVertexGroups(ob, bnames)
    for vgrp in list(ob.vertex_groups):
        ob.vertex_groups.remove(vgrp)
    for gn,vname in enumerate(vnames):
        cweights = weights[gn]
        cweights[cweights > 1] = 1
        cweights[cweights < threshold] = 0
        nonzero = np.nonzero(cweights)[0].astype(int)
        if len(nonzero) > 0:
            vgrp = ob.vertex_groups.new(name=vname)
            for vn in nonzero:
                vgrp.add([int(vn)], cweights[vn], 'REPLACE')
            if verbose:
                print("  * %s" % vname)

#----------------------------------------------------------
#   Apply selected shapekeys
#----------------------------------------------------------

class DAZ_OT_ApplyActiveShapekey(DazPropsOperator, IsShape):
    bl_idname = "daz.apply_active_shapekey"
    bl_label = "Apply Active Shapekey"
    bl_description = "Add active shapekey to all other shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[ob.active_shape_key_index]
        self.layout.label(text='Apply shapekey "%s"?' % skey.name)

    def run(self, context):
        t1 = perf_counter()
        ob = context.object
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[ob.active_shape_key_index]
        verts = ob.data.vertices
        data = skey.data
        offsets = [d.co - v.co for v,d in zip(verts, data)]
        skey.driver_remove("value")
        skey.driver_remove("mute")
        skey.driver_remove("slider_min")
        skey.driver_remove("slider_max")
        ob.shape_key_remove(skey)
        for v,offs in zip(verts,offsets):
            v.co += offs
        for skey in skeys.key_blocks:
            print(skey.name)
            data = skey.data
            for d,offs in zip(data,offsets):
                d.co += offs
        t2 = perf_counter()
        print("Shapekey applied in %.1f seconds" % (t2-t1))

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def checkObjectTransforms(ob):
    if (ob.location != Zero or
        Vector(ob.rotation_euler) != Zero or
        ob.scale != One):
        raise DazError("Apply object transformations to %s first" % ob.name)


def removeShapeDriversAndProps(rig, sname):
    if rig and rig.type == 'ARMATURE':
        final = finalProp(sname)
        rig.data.driver_remove(propRef(final))
        if final in rig.data.keys():
            del rig.data[final]
        if sname in rig.keys():
            del rig[sname]
        removeFromAllMorphsets(rig, sname)


def removeFromPropGroup(pgs, prop):
    idxs = []
    for n,item in enumerate(pgs):
        if item.name == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgs.remove(n)


def removeFromAllMorphsets(rig, prop):
    for morphset in MS.Standards:
        pgs = getattr(rig, "Daz" + morphset)
        removeFromPropGroup(pgs, prop)
    for cat in rig.DazMorphCats.values():
        removeFromPropGroup(cat.morphs, prop)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TransferShapekeys,
    DAZ_OT_ApplyActiveShapekey,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
