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

import sys
import bpy
import math
import numpy as np

from mathutils import Vector
from .error import *
from .utils import *
from .material import WHITE, GREY, BLACK, isWhite, isBlack
from .cycles import CyclesMaterial, CyclesTree
from .morphing import Selector
from .guess import ColorProp
from .fix import GizmoUser

#-------------------------------------------------------------
#   Classes
#-------------------------------------------------------------

def getMaterialEnums(self, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]


class ColorGroup(bpy.types.PropertyGroup):
    color : FloatVectorProperty(
        name = "Hair Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.2, 0.02, 0.01, 1)
    )


class Separator:
    useCheckStrips : BoolProperty(
        name = "Check Strips",
        description = "Check that the hair mesh consists of strips in UV space",
        default = True)

    def getMeshHairs(self, context, hair, hum):
        hairs = []
        if self.useSeparateLoose:
            bpy.ops.mesh.separate(type='LOOSE')
            #bpy.ops.daz.separate_loose_parts()
            print("Loose parts separated")
        setMode('OBJECT')
        hname = baseName(hair.name)
        haircount = 0
        hairs = []
        for hair in getSelectedMeshes(context):
            if baseName(hair.name) == hname and hair != hum:
                if self.checkStrip(hair):
                    hairs.append(hair)
        if self.sparsity > 1:
            hairs = [hair for n,hair in enumerate(hairs) if n % self.sparsity == 0]
        return hairs


    def checkStrip(self, hair):
        if not self.useCheckStrips:
            return True
        uvs = hair.data.uv_layers.active.data
        xs = [uv.uv[0] for uv in uvs]
        ys = [uv.uv[1] for uv in uvs]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        isstrip = (dx > 2*dy or dy > 2*dx)
        if not isstrip:
            raise DazError('"%s" is not a strip.\nDid you separate the scalp from the rest of the hair?' % hair.name)
        return True


class HairOptions:
    strandType : EnumProperty(
        items = [('SHEET', "Sheet", "For transmapped hair (mesh hair)"),
                 ('LINE', "Line", "For polyline hair (dForce guides and line tesselation = 1)"),
                 ('TUBE', "Tube", "For dForce and SBH strands (line tesselation >= 2)")],
        name = "Strand Type",
        description = "Mesh hair strand type",
        default = 'SHEET')

    strandOrientation : EnumProperty(
        items = [('TOP', "Top-Down", "Top-Down"),
                 ('BOTTOM', "Bottom-Up", "Bottom-Up"),
                 ('LEFT', "Left-Right", "Left-Right"),
                 ('RIGHT', "Right-Left", "Right-Left")],
        name = "Strand Orientation",
        default = 'TOP',
        description = "How the strands are oriented in UV space"
    )

    keepMesh : BoolProperty(
        name = "Keep Mesh Hair",
        default = False,
        description = "Keep (reconstruct) mesh hair after making particle hair"
    )

    usePolylineHair : BoolProperty(
        name = "Make Polyline Hair",
        description = "Output the result to a polyline mesh",
        default = False)

    useSinglePolyline : BoolProperty(
        name = "Single Polyline",
        description = "Make a single polyline mesh rather than separate ones for each length",
        default = False)

    removeOldHairs : BoolProperty(
        name = "Remove Particle Hair",
        default = False,
        description = "Remove existing particle systems from this mesh"
    )

    useSeparateLoose : BoolProperty(
        name = "Separate Loose Parts",
        default = True,
        description = ("Separate hair mesh into loose parts before doing the conversion.\n" +
                       "Usually improves performance but can stall for large meshes")
    )

    sparsity : IntProperty(
        name = "Sparsity",
        min = 1,
        max = 50,
        default = 1,
        description = "Only use every n:th hair"
    )

    size : IntProperty(
        name = "Hair Length",
        min = 3,
        max = 100,
        default = 50,
        description = "Length of resized hair. Maximum length if Auto Resize is enabled."
    )

    useResizeHair : BoolProperty(
        name = "Resize Hair",
        default = False,
        description = "Resize hair afterwards"
    )

    useAutoResize : BoolProperty(
        name = "Auto Resize",
        default = True,
        description = "Resize each material to the length of the longest strand")

    useResizeInBlocks : BoolProperty(
        name = "Resize In Blocks",
        default = False,
        description = "Resize hair in blocks of ten afterwards"
    )

    # Settings

    nViewChildren : IntProperty(
        name = "Viewport Children",
        description = "Number of hair children displayed in viewport",
        min = 0,
        default = 0)

    nRenderChildren : IntProperty(
        name = "Render Children",
        description = "Number of hair children displayed in renders",
        min = 0,
        default = 0)

    nViewStep : IntProperty(
        name = "Viewport Steps",
        description = "How many steps paths are drawn with (power of 2)",
        min = 0,
        default = 3)

    nRenderStep : IntProperty(
        name = "Render Steps",
        description = "How many steps paths are rendered with (power of 2)",
        min = 0,
        default = 3)

    strandShape : EnumProperty(
        items = [('STANDARD', "Standard", "Standard strand shape"),
                 ('ROOTS', "Fading Roots", "Root transparency (standard shape with fading roots)\nCan cause performance problems in scenes with volume effects"),
                 ('SHRINK', "Root And Tip Shrink", "Root and tip shrink.\n(Root and tip radii interchanged)")],
        name = "Strand Shape",
        description = "Strand shape",
        default = 'STANDARD')

    rootRadius : FloatProperty(
        name = "Root radius (mm)",
        description = "Strand diameter at the root",
        min = 0,
        default = 0.3)

    tipRadius : FloatProperty(
        name = "Tip radius (mm)",
        description = "Strand diameter at the tip",
        min = 0,
        default = 0.3)

    childRadius : FloatProperty(
        name = "Child radius (mm)",
        description = "Radius of children around parent",
        min = 0,
        default = 10)

    # Materials

    multiMaterials : BoolProperty(
        name = "Multi Materials",
        description = "Create separate particle systems for each material",
        default = True)

    keepMaterial : BoolProperty(
        name = "Keep Material",
        description = "Use existing material",
        default = True)

    activeMaterial : EnumProperty(
        items = getMaterialEnums,
        name = "Material",
        description = "Material to use as hair material")

    color : FloatVectorProperty(
        name = "Hair Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.2, 0.02, 0.01, 1)
    )

    colors : CollectionProperty(type = ColorGroup)

    hairMaterialMethod : EnumProperty(
        items = [('HAIR_BSDF', "Hair BSDF", "Hair BSDF (Cycles)"),
                 ('HAIR_PRINCIPLED', "Hair Principled", "Hair Principled (Cycles)"),
                 ('PRINCIPLED', "Principled", "Principled (Eevee and Cycles)")],
        name = "Hair Material Method",
        description = "Type of hair material node tree",
        default = 'HAIR_BSDF')

#-------------------------------------------------------------
#   Hair system class
#-------------------------------------------------------------

class HairSystem:
    def __init__(self, key, n, hum, mnum, btn):
        from .channels import Channels
        self.name = ("Hair_%s" % key)
        self.scale = hum.DazScale
        self.button = btn
        self.npoints = n
        self.mnum = mnum
        self.strands = []
        self.useEmitter = True
        self.vertexGroup = None
        self.material = btn.materials[mnum].name


    def setHairSettings(self, psys, ob):
        btn = self.button
        pset = psys.settings
        if hasattr(pset, "cycles_curve_settings"):
            ccset = pset.cycles_curve_settings
        elif hasattr(pset, "cycles"):
            ccset = pset.cycles
        else:
            ccset = pset

        if (self.material and
            self.material in ob.data.materials.keys()):
            pset.material_slot = self.material

        pset.rendered_child_count = btn.nRenderChildren
        pset.child_nbr = btn.nViewChildren
        if hasattr(pset, "display_step"):
            pset.display_step = btn.nViewStep
        else:
            pset.draw_step = btn.nViewStep
        pset.render_step = btn.nRenderStep
        pset.child_length = 1
        psys.child_seed = 0
        pset.child_radius = 0.1*btn.childRadius*self.scale

        if hasattr(ccset, "root_width"):
            ccset.root_width = 0.1*btn.rootRadius
            ccset.tip_width = 0.1*btn.tipRadius
        else:
            ccset.root_radius = 0.1*btn.rootRadius
            ccset.tip_radius = 0.1*btn.tipRadius
        if btn.strandShape == 'SHRINK':
            pset.shape = 0.99
        ccset.radius_scale = self.scale


    def addStrand(self, strand):
        self.strands.append(strand[0])


    def resize(self, size):
        nstrands = []
        for strand in self.strands:
            nstrand = self.resizeStrand(strand, size)
            nstrands.append(nstrand)
        return nstrands


    def resizeBlock(self):
        n = 10*((self.npoints+5)//10)
        if n < 10:
            n = 10
        return n, self.resize(n)


    def resizeStrand(self, strand, n):
        m = len(strand)
        if m == n:
            return strand
        step = (m-1)/(n-1)
        nstrand = []
        for i in range(n-1):
            j = math.floor(i*step + 1e-4)
            x = strand[j]
            y = strand[j+1]
            eps = i*step - j
            z = eps*y + (1-eps)*x
            nstrand.append(z)
        nstrand.append(strand[m-1])
        return nstrand


    def build(self, context, ob):
        from time import perf_counter
        t1 = perf_counter()
        if len(self.strands) == 0:
            raise DazError("No strands found")
        btn = self.button

        hlen = int(len(self.strands[0]))
        if hlen < 2:
            return
        elif hlen == 2:
            self.strands = [(v0, (v0+v1)/2, v1) for v0,v1 in self.strands]
            hlen = 3
        bpy.ops.object.particle_system_add()
        psys = ob.particle_systems.active
        psys.name = self.name

        if self.vertexGroup:
            psys.vertex_group_density = self.vertexGroup

        pset = psys.settings
        pset.type = 'HAIR'
        pset.use_strand_primitive = True
        if hasattr(pset, "use_render_emitter"):
            pset.use_render_emitter = self.useEmitter
        elif hasattr(ob, "show_instancer_for_render"):
            ob.show_instancer_for_render = self.useEmitter
        pset.render_type = 'PATH'
        if btn.nViewChildren or btn.nRenderChildren:
            pset.child_type = 'SIMPLE'
        else:
            pset.child_type = 'NONE'

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
        pset.use_hair_bspline = True
        if hasattr(pset, "display_step"):
            pset.display_step = 3
        else:
            pset.draw_step = 3
        self.setHairSettings(psys, ob)

        psys.use_hair_dynamics = False

        t2 = perf_counter()
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)
        psys = updateHair(context, ob, psys)
        t3 = perf_counter()
        self.buildStrands(psys)
        t4 = perf_counter()
        psys = updateHair(context, ob, psys)
        #printPsys(psys)
        t5 = perf_counter()
        self.buildFinish(context, psys, ob)
        t6 = perf_counter()
        setMode('OBJECT')
        #print("Hair %s: %.3f %.3f %.3f %.3f %.3f" % (self.name, t2-t1, t3-t2, t4-t3, t5-t4, t6-t5))


    def buildStrands(self, psys):
        for m,hair in enumerate(psys.particles):
            verts = self.strands[m]
            hair.location = verts[0]
            if len(verts) < len(hair.hair_keys):
                continue
            for n,v in enumerate(hair.hair_keys):
                v.co = verts[n]


    def buildFinish(self, context, psys, hum):
        scn = context.scene
        #activateObject(context, hum)
        setMode('PARTICLE_EDIT')
        pedit = scn.tool_settings.particle_edit
        pedit.use_emitter_deflect = False
        pedit.use_preserve_length = False
        pedit.use_preserve_root = False
        hum.data.use_mirror_x = False
        pedit.select_mode = 'POINT'
        bpy.ops.transform.translate()
        setMode('OBJECT')
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)


    def addHairDynamics(self, psys, hum):
        psys.use_hair_dynamics = True
        cset = psys.cloth.settings
        cset.pin_stiffness = 1.0
        cset.mass = 0.05
        deflector = findDeflector(hum)


    def buildMesh(self, context, hair, mnames):
        verts = []
        edges = []
        m = 0
        for strand in self.strands:
            verts += strand
            edges += [(m+n, m+n+1) for n in range(len(strand)-1)]
            m += len(strand)
        if len(mnames) <= 1:
            name = "Hair %s" % self.material
        else:
            name = "Mesh Hair"
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, edges, [])
        me.DazHairType = 'LINE'
        ob = bpy.data.objects.new(name, me)
        wmat = ob.matrix_world.copy()
        ob.parent = hair.parent
        ob.parent_bone = hair.parent_bone
        ob.parent_type = hair.parent_type
        setWorldMatrix(ob, wmat)
        for mname in mnames:
            mat = bpy.data.materials.get(mname)
            me.materials.append(mat)
        coll = getCollection(context, hair)
        coll.objects.link(ob)

#-------------------------------------------------------------
#   Tesselator class
#-------------------------------------------------------------

class Tesselator:
    def unTesselateFaces(self, context, hair, btn):
        self.squashFaces(hair)
        self.removeDoubles(context, hair, btn)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair, btn)


    def squashFaces(self, hair):
        verts = hair.data.vertices
        for f in hair.data.polygons:
            fverts = [verts[vn] for vn in f.vertices]
            if len(fverts) == 4:
                v1,v2,v3,v4 = fverts
                if (v1.co-v2.co).length < (v2.co-v3.co).length:
                    v2.co = v1.co
                    v4.co = v3.co
                else:
                    v3.co = v2.co
                    v4.co = v1.co


    def removeDoubles(self, context, hair, btn):
        activateObject(context, hair)
        threshold = 0.001*btn.scale
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')


    def checkTesselation(self, hair):
        # Check that there are only pure lines
        from .tables import getVertEdges
        vertedges = getVertEdges(hair)
        nverts = len(hair.data.vertices)
        print("Check hair", hair.name, nverts)
        deletes = []
        for vn,v in enumerate(hair.data.vertices):
            ne = len(vertedges[vn])
            if ne > 2:
                #v.select = True
                deletes.append(vn)
        print("Number of vertices to delete", len(deletes))
        return deletes


    def mergeRemainingFaces(self, hair, btn):
        for f in hair.data.polygons:
            fverts = [hair.data.vertices[vn] for vn in f.vertices]
            r0 = fverts[0].co
            for v in fverts:
                v.co = r0
                v.select = True
        threshold = 0.001*btn.scale
        setMode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        setMode('OBJECT')


    def findStrands(self, hair, strandType):
        def makeStrand(pline, verts):
            return [verts[vn].co for vn in pline]

        if strandType == 'TUBE':
            edges = [(min(e.vertices),max(e.vertices)) for e in hair.data.edges]
            edges.sort()
        else:
            edges = [e.vertices for e in hair.data.edges]
        pline = None
        plines = []
        v0 = -1
        for v1,v2 in edges:
            if v1 == v0:
                pline.append(v2)
            else:
                pline = [v1,v2]
                plines.append(pline)
            v0 = v2
        verts = hair.data.vertices
        pgs = hair.data.DazPolylineMaterials
        if len(pgs) == len(plines):
            strands = [(item.a, makeStrand(pline, verts)) for item,pline in zip(pgs, plines)]
        else:
            strands = [(0, makeStrand(pline, verts)) for pline in plines]
        return strands

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

def getHairAndHuman(context, strict):
    hair = context.object
    hum = None
    for ob in getSelectedMeshes(context):
        if ob != hair:
            hum = ob
            break
    if strict and hum is None:
        raise DazError("Select hair and human")
    return hair,hum

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

class CombineHair:

    def addStrands(self, hum, strands, hsystems, haircount):
        for strand in strands:
            mnum,n,strand = self.getStrand(strand)
            key,mnum = self.getHairKey(n, mnum)
            if key not in hsystems.keys():
                hsystems[key] = HairSystem(key, n, hum, mnum, self)
            hsystems[key].strands.append(strand)
        return len(strands)


    def combineHairSystems(self, hsystems, hsyss):
        for key,hsys in hsyss.items():
            if key in hsystems.keys():
                hsystems[key].strands += hsys.strands
            else:
                hsystems[key] = hsys


    def hairResize(self, maxsize, hsystems, hum):
        if self.useAutoResize:
            sizes = dict([(hsys.material,3) for hsys in hsystems.values()])
            for hsys in hsystems.values():
                length = max([len(strand) for strand in hsys.strands])
                if length > sizes[hsys.material] and length < maxsize:
                    sizes[hsys.material] = length
        else:
            sizes = dict([(hsys.material,maxsize) for hsys in hsystems.values()])

        print("Resize hair:\n%s" % sizes)
        nsystems = {}
        for hsys in hsystems.values():
            size = sizes[hsys.material]
            key,mnum = self.getHairKey(size, hsys.mnum)
            if key not in nsystems.keys():
                nsystems[key] = HairSystem(key, size, hum, hsys.mnum, self)
            nstrands = hsys.resize(size)
            nsystems[key].strands += nstrands
        return nsystems

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

class DAZ_OT_MakeHair(DazPropsOperator, CombineHair, IsMesh, HairOptions, Separator):
    bl_idname = "daz.make_hair"
    bl_label = "Make Hair"
    bl_description = "Make particle hair from mesh hair"
    bl_options = {'UNDO'}

    dialogWidth = 600

    def draw(self, context):
        row = self.layout.row()
        col = row.column()
        box = col.box()
        box.label(text="Create")
        box.prop(self, "strandType", expand=True)
        if self.strandType == 'SHEET':
            box.prop(self, "strandOrientation")
            box.prop(self, "useSeparateLoose")
            box.prop(self, "useCheckStrips")
        box.prop(self, "keepMesh")
        box.prop(self, "usePolylineHair")
        if self.usePolylineHair:
            box.prop(self, "useSinglePolyline")
        box.prop(self, "removeOldHairs")
        box.separator()
        box.prop(self, "useResizeHair")
        if self.useResizeHair:
            box.prop(self, "useAutoResize")
            box.prop(self, "size")
            if not self.useAutoResize:
                box.prop(self, "useResizeInBlocks")
        box.prop(self, "sparsity")

        col = row.column()
        box = col.box()
        box.label(text="Material")
        keepmat = False
        multimat = False
        if self.strandType != 'TUBE':
            box.prop(self, "multiMaterials")
            multimat = self.multiMaterials
        if self.strandType != 'SHEET':
            box.prop(self, "keepMaterial")
            keepmat = self.keepMaterial
        if keepmat:
            if not multimat:
                box.prop(self, "activeMaterial")
        else:
            box.prop(self, "hairMaterialMethod")
            if multimat:
                for item in self.colors:
                    row2 = box.row()
                    row2.label(text=item.name)
                    row2.prop(item, "color", text="")
            else:
                box.prop(self, "color")

        col = row.column()
        box = col.box()
        box.label(text="Settings")
        box.prop(self, "nViewChildren")
        box.prop(self, "nRenderChildren")
        box.prop(self, "nViewStep")
        box.prop(self, "nRenderStep")
        box.prop(self, "childRadius")
        box.prop(self, "strandShape")
        box.prop(self, "rootRadius")
        box.prop(self, "tipRadius")


    def invoke(self, context, event):
        ob = context.object
        self.strandType = ob.data.DazHairType
        self.colors.clear()
        for mat in ob.data.materials:
            if mat:
                item = self.colors.add()
                item.name = mat.name
                item.color = mat.diffuse_color
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        from time import perf_counter
        t1 = perf_counter()
        self.clocks = []
        hair,hum = getHairAndHuman(context, True)
        if hasObjectTransforms(hair):
            raise DazError("Apply object transformations to %s first" % hair.name)
        if hasObjectTransforms(hum):
            raise DazError("Apply object transformations to %s first" % hum.name)

        if self.strandType == 'SHEET':
            if not hair.data.uv_layers.active:
                raise DazError("Hair object has no active UV layer.\nConsider using Line or Tube strand types instead")
        elif self.strandType == 'LINE':
            if hair.data.polygons:
                raise DazError("Cannot use Line strand type for hair mesh with faces")
        elif self.strandType == 'TUBE':
            self.multiMaterials = False

        self.scale = hair.DazScale
        LS.hairMaterialMethod = self.hairMaterialMethod

        self.nonquads = []
        scn = context.scene
        # Build hair material while hair is still active
        self.buildHairMaterials(hum, hair, context)
        activateObject(context, hum)
        if self.removeOldHairs:
            self.clearHair(hum)

        activateObject(context, hair)
        nhairfaces = len(hair.data.polygons)
        setMode('EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')

        t2 = perf_counter()
        self.clocks.append(("Initialize", t2-t1))
        print("Start conversion")
        hsystems = {}
        if self.strandType == 'SHEET':
            hairs = self.getMeshHairs(context, hair, hum)
            count = 0
            haircount = 0
            for hair in hairs:
                count += 1
                hsyss,hcount = self.makeHairSystems(context, hum, hair)
                haircount += hcount
                self.combineHairSystems(hsystems, hsyss)
                if count % 10 == 0:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            t5 = perf_counter()
            self.clocks.append(("Make hair systems", t5-t2))
        else:
            hairs = [hair]
            setMode('OBJECT')
            tess = Tesselator()
            if self.strandType == 'LINE':
                pass
            elif self.strandType == 'TUBE':
                tess.unTesselateFaces(context, hair, self)
            strands = tess.findStrands(hair, self.strandType)
            if self.sparsity > 1:
                strands = [strand for n,strand in enumerate(strands) if n % self.sparsity == 0]
            haircount = self.addStrands(hum, strands, hsystems, -1)
            t5 = perf_counter()
            self.clocks.append(("Make hair systems", t5-t2))
        haircount += 1
        print("\nTotal number of strands: %d" % haircount)
        if haircount == 0:
            raise DazError("Conversion failed.\nNo hair strands created")

        if self.useResizeInBlocks and not self.useAutoResize:
            hsystems = self.blockResize(hsystems, hum)
        elif self.useResizeHair:
            hsystems = self.hairResize(self.size, hsystems, hum)
        t6 = perf_counter()
        self.clocks.append(("Resize", t6-t5))
        if self.usePolylineHair:
            self.makePolylineHair(context, hsystems, hair)
        else:
            self.makeParticleHair(context, hsystems, hum)
        t7 = perf_counter()
        self.clocks.append(("Make Hair", t7-t6))
        if self.keepMesh:
            if self.strandType == 'SHEET':
                activateObject(context, hair)
                selectObjects(context, hairs)
                bpy.ops.object.join()
                activateObject(context, hum)
                t8 = perf_counter()
                self.clocks.append(("Rejoined mesh hairs", t8-t7))
            else:
                t8 = t7
        else:
            for hair in hairs:
                hair.parent = None
                unlinkAll(hair)
            #deleteObjects(context, hairs)
            t8 = perf_counter()
            self.clocks.append(("Deleted mesh hairs", t8-t7))
        if self.nonquads:
            print("Ignored %d non-quad faces out of %d faces" % (len(self.nonquads), nhairfaces))
        print("Hair converted in %.2f seconds" % (t8-t1))
        for hdr,t in self.clocks:
            print("  %s: %2f s" % (hdr, t))


    def makeParticleHair(self, context, hsystems, hum):
        print("Make particle hair")
        activateObject(context, hum)
        for hsys in hsystems.values():
            hsys.useEmitter = True
            hsys.vertexGroup = None
            hsys.build(context, hum)
            sys.stdout.write(".")
            sys.stdout.flush()
        print("Done")


    def makePolylineHair(self, context, hsystems, hair):
        print("Make polyline hair")
        if not hsystems:
            print("No hair system found")
        elif self.useSinglePolyline:
            strands = []
            mnames = []
            for hsys in hsystems.values():
                strands += hsys.strands
                mnames.append(hsys.material)
            hsys = list(hsystems.values())[0]
            hsys.strands = strands
            hsys.buildMesh(context, hair, mnames)
        else:
            for hsys in hsystems.values():
                hsys.buildMesh(context, hair, [hsys.material])
        print("Done")


    def findMeshRects(self, hair):
        from .tables import getVertFaces, findNeighbors
        #print("Find neighbors")
        self.faceverts, self.vertfaces = getVertFaces(hair)
        self.nfaces = len(hair.data.polygons)
        if not self.nfaces:
            return None
            raise DazError("Hair has no faces")
        mneighbors = findNeighbors(range(self.nfaces), self.faceverts, self.vertfaces)
        self.centers, self.uvcenters = self.findCenters(hair)

        #print("Collect rects")
        mfaces = [(f.index,f.vertices) for f in hair.data.polygons]
        mrects,_,_ = self.collectRects(mfaces, mneighbors)
        return mrects


    def findTexRects(self, hair, mrects):
        from .tables import getVertFaces, findNeighbors, findTexVerts
        #print("Find texverts")
        self.texverts, self.texfaces = findTexVerts(hair, self.vertfaces)
        #print("Find tex neighbors", len(self.texverts), self.nfaces, len(self.texfaces))
        # Improve
        _,self.texvertfaces = getVertFaces(hair, self.texverts, None, self.texfaces)
        tneighbors = findNeighbors(range(self.nfaces), self.texfaces, self.texvertfaces)

        rects = []
        #print("Collect texrects")
        for mverts,mfaces in mrects:
            texfaces = [(fn,self.texfaces[fn]) for fn in mfaces]
            nn = [(fn,tneighbors[fn]) for fn in mfaces]
            rects2,clusters,fclusters = self.collectRects(texfaces, tneighbors)
            for rect in rects2:
                rects.append(rect)
        return rects


    def makeHairSystems(self, context, hum, hair):
        from .tables import getVertFaces, findNeighbors
        if len(hair.data.polygons) > 0:
            mnum = hair.data.polygons[0].material_index
        else:
            mnum = 0
        mrects = self.findMeshRects(hair)
        if mrects is None:
            return {}, 0
        trects = self.findTexRects(hair, mrects)
        #print("Sort columns")
        haircount = -1
        setActiveObject(context, hair)
        hsystems = {}
        verts = range(len(hair.data.vertices))
        for _,tfaces in trects:
            if not self.quadsOnly(hair, tfaces):
                continue
            _,vertfaces = getVertFaces(None, verts, tfaces, self.faceverts)
            neighbors = findNeighbors(tfaces, self.faceverts, vertfaces)
            if neighbors is None:
                continue
            first, corner, boundary, bulk = self.findStartingPoint(hair, neighbors, self.uvcenters)
            if first is None:
                continue
            self.selectFaces(hair, tfaces)
            columns = self.sortColumns(first, corner, boundary, bulk, neighbors, self.uvcenters)
            if columns:
                coords = self.getColumnCoords(columns, self.centers)
                strands = [(mnum,strand) for strand in coords]
                haircount = self.addStrands(hum, strands, hsystems, haircount)
        return hsystems, haircount


    def getStrand(self, strand):
        return strand[0], len(strand[1]), strand[1]


    def getHairKey(self, n, mnum):
        if self.multiMaterials and mnum < len(self.materials):
            mat = self.materials[mnum]
            return ("%d_%s" % (n, mat.name)), mnum
        else:
            return str(n),0


    def blockResize(self, hsystems, hum):
        print("Resize hair in blocks of ten")
        nsystems = {}
        for hsys in hsystems.values():
            n,nstrands = hsys.resizeBlock()
            key,mnum = self.getHairKey(n, hsys.mnum)
            if key not in nsystems.keys():
                nsystems[key] = HairSystem(key, n, hum, hsys.mnum, self)
            nsystems[key].strands += nstrands
        return nsystems

    #-------------------------------------------------------------
    #   Collect rectangles
    #-------------------------------------------------------------

    def collectRects(self, faceverts, neighbors):
        #fclusters = dict([(fn,-1) for fn,_ in faceverts])
        fclusters = {}
        for fn,_ in faceverts:
            fclusters[fn] = -1
            for nn in neighbors[fn]:
                fclusters[nn] = -1
        clusters = {-1 : -1}
        nclusters = 0

        for fn,_ in faceverts:
            fncl = [self.deref(nn, fclusters, clusters) for nn in neighbors[fn] if nn < fn]
            if fncl == []:
                cn = clusters[cn] = nclusters
                nclusters += 1
            else:
                cn = min(fncl)
                for cn1 in fncl:
                    clusters[cn1] = cn
            fclusters[fn] = cn

        for fn,_ in faceverts:
            fclusters[fn] = self.deref(fn, fclusters, clusters)

        rects = []
        for cn in clusters.keys():
            if cn == clusters[cn]:
                faces = [fn for fn,_ in faceverts if fclusters[fn] == cn]
                vertsraw = [vs for fn,vs in faceverts if fclusters[fn] == cn]
                vstruct = {}
                for vlist in vertsraw:
                    for vn in vlist:
                        vstruct[vn] = True
                verts = list(vstruct.keys())
                verts.sort()
                rects.append((verts, faces))
                if len(rects) > 1000:
                    print("Too many rects")
                    return rects, clusters, fclusters

        return rects, clusters, fclusters


    def deref(self, fn, fclusters, clusters):
        cn = fclusters[fn]
        updates = []
        while cn != clusters[cn]:
            updates.append(cn)
            cn = clusters[cn]
        for nn in updates:
            clusters[nn] = cn
        fclusters[fn] = cn
        return cn

    #-------------------------------------------------------------
    #   Find centers
    #-------------------------------------------------------------

    def findCenters(self, ob):
        vs = ob.data.vertices
        uvs = ob.data.uv_layers.active.data
        centers = {}
        uvcenters = {}
        m = 0
        for f in ob.data.polygons:
            f.select = True
            fn = f.index
            if len(f.vertices) == 4:
                vn0,vn1,vn2,vn3 = f.vertices
                centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co+vs[vn3].co)/4
                uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv+uvs[m+3].uv)/4
                m += 4
            else:
                vn0,vn1,vn2 = f.vertices
                centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co)/4
                uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv)/4
                m += 3
            f.select = False
        if self.strandOrientation == 'TOP':
            pass
        elif self.strandOrientation == 'BOTTOM':
            uvcenters = dict([(fn,Vector((u[0], -u[1]))) for fn,u in uvcenters.items()])
        elif self.strandOrientation == 'LEFT':
            uvcenters = dict([(fn,Vector((-u[1], -u[0]))) for fn,u in uvcenters.items()])
        elif self.strandOrientation == 'RIGHT':
            uvcenters = dict([(fn,Vector((u[1], u[0]))) for fn,u in uvcenters.items()])
        return centers, uvcenters

    #-------------------------------------------------------------
    #   Find starting point
    #-------------------------------------------------------------

    def findStartingPoint(self, ob, neighbors, uvcenters):
        types = dict([(n,[]) for n in range(1,5)])
        for fn,neighs in neighbors.items():
            nneighs = len(neighs)
            if nneighs == 0:
                return None,None,None,None
            elif nneighs >= 5:
                sys.stdout.write("N")
                return None,None,None,None
            types[nneighs].append(fn)

        singlets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[1]]
        singlets.sort()
        if len(singlets) > 0:
            if len(singlets) != 2:
                sys.stdout.write("S")
                return None,None,None,None
            if (types[3] != [] or types[4] != []):
                sys.stdout.write("T")
                return None,None,None,None
            first = singlets[0][1]
            corner = types[1]
            boundary = types[2]
            bulk = types[3]
        else:
            doublets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[2]]
            doublets.sort()
            if len(doublets) > 4:
                sys.stdout.write(">")
                self.selectFaces(ob, [fn for _,fn in doublets])
                return None,None,None,None
            if len(doublets) < 4:
                if len(doublets) == 2:
                    sys.stdout.write("2")
                    self.selectFaces(ob, neighbors.keys())
                return None,None,None,None
            first = doublets[0][1]
            corner = types[2]
            boundary = types[3]
            bulk = types[4]

        return first, corner, boundary, bulk

    #-------------------------------------------------------------
    #   Sort columns
    #-------------------------------------------------------------

    def sortColumns(self, first, corner, boundary, bulk, neighbors, uvcenters):
        column = self.getDown(first, neighbors, corner, boundary, uvcenters)
        columns = [column]
        if len(corner) <= 2:
            return columns
        fn = first
        n = 0
        while (True):
            n += 1
            horizontal = [(uvcenters[nb][0], nb) for nb in neighbors[fn]]
            horizontal.sort()
            fn = horizontal[-1][1]
            if n > 50:
                return columns
            elif fn in corner:
                column = self.getDown(fn, neighbors, corner, boundary, uvcenters)
                columns.append(column)
                return columns
            elif fn in boundary:
                column = self.getDown(fn, neighbors, boundary, bulk, uvcenters)
                columns.append(column)
            else:
                print("Hair bug", fn)
                return None
                raise DazError("Hair bug")
        print("Sorted")


    def getDown(self, top, neighbors, boundary, bulk, uvcenters):
        column = [top]
        fn = top
        n = 0
        while (True):
            n += 1
            vertical = [(uvcenters[nb][1], nb) for nb in neighbors[fn]]
            vertical.sort()
            fn = vertical[-1][1]
            if fn in boundary or n > 500:
                column.append(fn)
                column.reverse()
                return column
            else:
                column.append(fn)

    #-------------------------------------------------------------
    #   Get column coords
    #-------------------------------------------------------------

    def getColumnCoords(self, columns, centers):
        #print("Get column coords")
        length = len(columns[0])
        hcoords = []
        short = False
        for column in columns:
            if len(column) < length:
                length = len(column)
                short = True
            hcoord = [centers[fn] for fn in column]
            hcoords.append(hcoord)
        if short:
            hcoords = [hcoord[0:length] for hcoord in hcoords]
        return hcoords

    #-------------------------------------------------------------
    #   Clear hair
    #-------------------------------------------------------------

    def clearHair(self, hum):
        nsys = len(hum.particle_systems)
        for n in range(nsys):
            bpy.ops.object.particle_system_remove()


    def buildHairMaterials(self, hum, hair, context):
        self.materials = []
        fade = (self.strandShape == 'ROOTS')
        keepmat = (self.keepMaterial and self.strandType != 'SHEET')
        if self.multiMaterials:
            if keepmat:
                mats = hair.data.materials
            else:
                mats = []
                for item in self.colors:
                    mname = "H" + item.name
                    mat = buildHairMaterial(mname, item.color, context, force=True)
                    if fade:
                        addFade(mat)
                    mats.append(mat)
            for mat in mats:
                hum.data.materials.append(mat)
                self.materials.append(mat)
        else:
            mname = self.activeMaterial
            if keepmat:
                mat = hair.data.materials[mname]
            else:
                mat = buildHairMaterial("Hair", self.color, context, force=True)
            if fade:
                addFade(mat)
            hum.data.materials.append(mat)
            self.materials = [mat]


    def quadsOnly(self, ob, faces):
        for fn in faces:
            f = ob.data.polygons[fn]
            if len(f.vertices) != 4:
                #print("  Face %d has %s corners" % (fn, len(f.vertices)))
                self.nonquads.append(fn)
                return False
        return True


    def selectFaces(self, ob, faces):
        for fn in faces:
            ob.data.polygons[fn].select = True

# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------

def createSkullGroup(hum, skullType):
    if skullType == 'TOP':
        maxheight = -1e4
        for v in hum.data.vertices:
            if v.co[2] > maxheight:
                maxheight = v.co[2]
                top = v.index
        vgrp = hum.vertex_groups.new(name="Skull")
        vgrp.add([top], 1.0, 'REPLACE')
        return vgrp
    elif skullType == 'ALL':
        vgrp = hum.vertex_groups.new(name="Skull")
        for vn in range(len(hum.data.vertices)):
            vgrp.add([vn], 1.0, 'REPLACE')
        return vgrp
    else:
        return None


def updateHair(context, ob, psys):
    dg = context.evaluated_depsgraph_get()
    return ob.evaluated_get(dg).particle_systems.active


def updateHairs(context, ob):
    dg = context.evaluated_depsgraph_get()
    return ob.evaluated_get(dg).particle_systems


def printPsys(psys):
    for m,hair in enumerate(psys.particles):
        print("\n")
        print(hair.location)
        for v in hair.hair_keys:
            print(v.co)

#------------------------------------------------------------------------
#   Deflector
#------------------------------------------------------------------------

def makeDeflector(pair, rig, bnames, cfg):
    _,ob = pair

    shiftToCenter(ob)
    if rig:
        for bname in bnames:
            if bname in cfg.bones.keys():
                bname = cfg.bones[bname]
            if bname in rig.pose.bones.keys():
                ob.parent = rig
                ob.parent_type = 'BONE'
                ob.parent_bone = bname
                pb = rig.pose.bones[bname]
                ob.matrix_basis = pb.matrix.inverted() @ ob.matrix_basis
                ob.matrix_basis.col[3] -= Vector((0,pb.bone.length,0,0))
                break

    ob.draw_type = 'WIRE'
    ob.field.type = 'FORCE'
    ob.field.shape = 'SURFACE'
    ob.field.strength = 240.0
    ob.field.falloff_type = 'SPHERE'
    ob.field.z_direction = 'POSITIVE'
    ob.field.falloff_power = 2.0
    ob.field.use_max_distance = True
    ob.field.distance_max = 0.125*ob.DazScale


def shiftToCenter(ob):
    sum = Vector()
    for v in ob.data.vertices:
        sum += v.co
    offset = sum/len(ob.data.vertices)
    for v in ob.data.vertices:
        v.co -= offset
    ob.location = offset


def findDeflector(human):
    rig = human.parent
    if rig:
        children = rig.children
    else:
        children = human.children
    for ob in children:
        if ob.field.type == 'FORCE':
            return ob
    return None

#------------------------------------------------------------------------
#   Buttons
#------------------------------------------------------------------------

class IsHair:
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.particle_systems.active)

#------------------------------------------------------------------------
#   Hair Update
#------------------------------------------------------------------------

class HairUpdater:

    def getAllSettings(self, psys):
        psettings = self.getSettings(psys.settings)
        hdyn = psys.use_hair_dynamics
        csettings = self.getSettings(psys.cloth.settings)
        return psettings, hdyn, csettings


    def setAllSettings(self, psys, data):
        psettings, hdyn, csettings = data
        self.setSettings(psys.settings, psettings)
        psys.use_hair_dynamics = hdyn
        self.setSettings(psys.cloth.settings, csettings)


    def getSettings(self, pset):
        settings = {}
        for key in dir(pset):
            attr = getattr(pset, key)
            if (key[0] == "_" or
                key in ["count"] or
                (key in ["material", "material_slot"] and
                 not self.affectMaterial)):
                continue
            if (
                isinstance(attr, int) or
                isinstance(attr, bool) or
                isinstance(attr, float) or
                isinstance(attr, str)
                ):
                settings[key] = attr
        return settings


    def setSettings(self, pset, settings):
        for key,value in settings.items():
            if key in ["use_absolute_path_time"]:
                continue
            try:
                setattr(pset, key, value)
            except AttributeError:
                pass


class DAZ_OT_UpdateHair(DazPropsOperator, HairUpdater, IsHair):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Change settings for particle hair"
    bl_options = {'UNDO'}

    affectMaterial : BoolProperty(
        name = "Affect Material",
        description = "Also change materials",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "affectMaterial")

    def run(self, context):
        hum = context.object
        psys0 = hum.particle_systems.active
        idx0 = hum.particle_systems.active_index
        data = self.getAllSettings(psys0)
        for idx,psys in enumerate(hum.particle_systems):
            if idx == idx0:
                continue
            hum.particle_systems.active_index = idx
            self.setAllSettings(psys, data)
        hum.particle_systems.active_index = idx0

#------------------------------------------------------------------------
#   Combine Hairs
#------------------------------------------------------------------------

class DAZ_OT_CombineHairs(DazOperator, CombineHair, HairUpdater, Selector, HairOptions):
    bl_idname = "daz.combine_hairs"
    bl_label = "Combine Hairs"
    bl_description = "Combine several hair particle systems into a single one"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.particle_systems) > 0)

    def draw(self, context):
        self.layout.prop(self, "size")
        Selector.draw(self, context)

    def invoke(self, context, event):
        return Selector.invoke(self, context, event)

    def getKeys(self, rig, ob):
        enums = []
        for n,psys in enumerate(ob.particle_systems):
            if psys.settings.type == 'HAIR':
                text = "(%3d)   %s" % (psys.settings.hair_step+1, psys.name)
                enum = (str(n), text, "All")
                enums.append(enum)
        return enums

    def getStrand(self, strand):
        return 0, len(strand), strand

    def getHairKey(self, n, mnum):
        mat = self.materials[0]
        return ("%d_%s" % (n, mat.name)), 0


    def getStrandsFromPsys(self, psys):
        strands = []
        for hair in psys.particles:
            strand = [v.co.copy() for v in hair.hair_keys]
            strands.append(strand)
        return strands


    def run(self, context):
        scn = context.scene
        ob = context.object
        psystems = []
        hsystems = {}
        haircount = -1
        for item in self.getSelectedItems():
            idx = int(item.name)
            psys = ob.particle_systems[idx]
            psystems.append((idx, psys))
        if len(psystems) == 0:
            raise DazError("No particle system selected")
        idx0, psys0 = psystems[0]
        self.affectMaterial = False
        data = self.getAllSettings(psys0)
        mname = psys0.settings.material_slot
        mat = ob.data.materials[mname]
        self.materials = [mat]

        for idx,psys in psystems:
            ob.particle_systems.active_index = idx
            psys = updateHair(context, ob, psys)
            strands = self.getStrandsFromPsys(psys)
            haircount = self.addStrands(ob, strands, hsystems, haircount)
        psystems.reverse()
        for idx,psys in psystems:
            ob.particle_systems.active_index = idx
            bpy.ops.object.particle_system_remove()
        hsystems = self.hairResize(self.size, hsystems, ob)
        for hsys in hsystems.values():
            hsys.build(context, ob)
        psys = ob.particle_systems.active
        self.setAllSettings(psys, data)

#------------------------------------------------------------------------
#   Color Hair
#------------------------------------------------------------------------

class DAZ_OT_ColorHair(DazPropsOperator, IsHair, ColorProp):
    bl_idname = "daz.color_hair"
    bl_label = "Color Hair"
    bl_description = "Change particle hair color"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        hum = context.object
        fade = False
        mats = {}
        for mat in hum.data.materials:
            mats[mat.name] = (mat, True)
        for psys in hum.particle_systems:
            pset = psys.settings
            mname = pset.material_slot
            if mname in mats.keys() and mats[mname][1]:
                mat = buildHairMaterial(mname, self.color, context, force=True)
                if fade:
                    addFade(mat)
                mats[mname] = (mat, False)

        for _,keep in mats.values():
            if not keep:
                hum.data.materials.pop()
        for mat,keep in mats.values():
            if not keep:
                hum.data.materials.append(mat)

#------------------------------------------------------------------------
#   Connect Hair - seems unused
#------------------------------------------------------------------------

class DAZ_OT_ConnectHair(DazOperator, IsHair):
    bl_idname = "daz.connect_hair"
    bl_label = "Connect Hair"
    bl_description = "(Re)connect hair"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        for mod in hum.modifiers:
            if isinstance(mod, bpy.types.ParticleSystemModifier):
                print(mod)

        nparticles = len(hum.particle_systems)
        for n in range(nparticles):
            hum.particle_systems.active_index = n
            print(hum.particle_systems.active_index, hum.particle_systems.active)
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.disconnect_hair()
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.connect_hair()
            bpy.ops.particle.particle_edit_toggle()

#------------------------------------------------------------------------
#   Materials
#------------------------------------------------------------------------

def buildHairMaterial(mname, color, context, force=False):
    color = list(color[0:3])
    hmat = HairMaterial(mname, color)
    hmat.force = force
    hmat.build(context, color)
    return hmat.rna


class HairMaterial(CyclesMaterial):

    def __init__(self, name, color):
        CyclesMaterial.__init__(self, name)
        self.name = name
        self.color = color


    def guessColor(self):
        if self.rna:
            self.rna.diffuse_color = self.color


    def build(self, context, color):
        from .material import Material
        if not Material.build(self, context):
            return
        self.tree = getHairTree(self, color)
        self.tree.build()
        self.rna.diffuse_color[0:3] = self.color


def getHairTree(dmat, color=BLACK):
    #print("Creating %s hair material" % LS.hairMaterialMethod)
    if LS.hairMaterialMethod == 'HAIR_PRINCIPLED':
        return HairPBRTree(dmat, color)
    elif LS.hairMaterialMethod == 'PRINCIPLED':
        return HairEeveeTree(dmat, color)
    else:
        return HairBSDFTree(dmat, color)

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat, color):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = color
        self.root = Vector(color)
        self.tip = Vector(color)
        self.roottex = None
        self.tiptex = None


    def build(self):
        self.makeTree()
        self.buildLayer("")


    def initLayer(self):
        self.column = 4
        self.active = None
        self.buildBump()


    def addTexco(self, slot):
        CyclesTree.addTexco(self, slot)
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        #self.texco = self.info.outputs["Intercept"]


    def buildOutput(self):
        self.addColumn()
        output = self.addNode('ShaderNodeOutputMaterial')
        self.links.new(self.active.outputs[0], output.inputs['Surface'])


    def buildBump(self):
        strength = self.getValue(["Bump Strength"], 1)
        if False and strength:
            bump = self.addNode("ShaderNodeBump", col=2)
            bump.inputs["Strength"].default_value = strength
            bump.inputs["Distance"].default_value = 0.1 * LS.scale
            bump.inputs["Height"].default_value = 1
            self.normal = bump


    def linkTangent(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Tangent"])


    def linkBumpNormal(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Normal"])


    def addRamp(self, node, label, root, tip, endpos=1, slot="Color"):
        ramp = self.addNode('ShaderNodeValToRGB', col=self.column-2)
        ramp.label = label
        self.links.new(self.info.outputs["Intercept"], ramp.inputs['Fac'])
        ramp.color_ramp.interpolation = 'LINEAR'
        colramp = ramp.color_ramp
        elt = colramp.elements[0]
        elt.position = 0
        if len(root) == 3:
            elt.color = list(root) + [1]
        else:
            elt.color = root
        elt = colramp.elements[1]
        elt.position = endpos
        if len(tip) == 3:
            elt.color = list(tip) + [0]
        else:
            elt.color = tip
        if node:
            node.inputs[slot].default_value[0:3] == root
        return ramp


    def readColor(self, factor):
        root, self.roottex = self.getColorTex(["Hair Root Color"], "COLOR", self.color, useFactor=False)
        tip, self.tiptex = self.getColorTex(["Hair Tip Color"], "COLOR", self.color, useFactor=False)
        self.owner.rna.diffuse_color[0:3] = root
        self.root = factor * Vector(root)
        self.tip = factor * Vector(tip)


    def linkRamp(self, ramp, texs, node, slot):
        out = ramp.outputs[0]
        for tex in texs:
            if tex:
                mix,a,b,out = self.addMixRgbNode('MULTIPLY', col=self.column-1)
                mix.inputs[0].default_value = 1.0
                self.links.new(tex.outputs[0], a)
                self.links.new(ramp.outputs[0], b)
                break
        self.links.new(out, node.inputs[slot])
        return out


    def setRoughness(self, diffuse, rough):
        diffuse.inputs["Roughness"].default_value = rough


    def mixSockets(self, socket1, socket2, weight):
        mix = self.addNode('ShaderNodeMixShader')
        mix.inputs[0].default_value = weight
        self.links.new(socket1, mix.inputs[1])
        self.links.new(socket2, mix.inputs[2])
        return mix


    def mixShaders(self, node1, node2, weight):
        return self.mixSockets(node1.outputs[0], node2.outputs[0], weight)


    def addShaders(self, node1, node2):
        add = self.addNode('ShaderNodeAddShader')
        self.links.new(node1.outputs[0], add.inputs[0])
        self.links.new(node2.outputs[0], add.inputs[1])
        return add

#-------------------------------------------------------------
#   Hair tree BSDF
#-------------------------------------------------------------

class HairBSDFTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.5)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        self.addColumn()
        if trans and refl:
            #weight = self.getValue(["Highlight Weight"], 0.11)
            weight = self.getValue(["Glossy Layer Weight"], 0.5)
            self.active = self.mixShaders(trans, refl, weight)
        #self.buildAnisotropic()
        self.buildCutout()
        self.buildOutput()


    def buildTransmission(self):
        root, roottex = self.getColorTex(["Root Transmission Color"], "COLOR", self.color, useFactor=False)
        tip, tiptex = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color, useFactor=False)
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 1
        trans.inputs["RoughnessV"].default_value = 1
        ramp = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, [roottex, tiptex], trans, "Color")
        #self.linkTangent(trans)
        self.active = trans
        return trans


    def buildHighlight(self):
        refl = self.addNode('ShaderNodeBsdfHair')
        refl.component = 'Reflection'
        refl.inputs['Offset'].default_value = 0
        refl.inputs["RoughnessU"].default_value = 0.02
        refl.inputs["RoughnessV"].default_value = 1.0
        ramp = self.addRamp(refl, "Reflection", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], refl, "Color")
        self.active = refl
        return refl


    def buildAnisotropic(self):
        # Anisotropic
        aniso = self.getValue(["Anisotropy"], 0)
        if aniso:
            if aniso > 0.2:
                aniso = 0.2
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.rootramp.outputs[0], node.inputs["Color"])
            node.inputs["Anisotropy"].default_value = aniso
            arots = self.getValue(["Anisotropy Rotations"], 0)
            node.inputs["Rotation"].default_value = arots
            self.linkTangent(node)
            self.linkBumpNormal(node)
            self.addColumn()
            self.active = self.addShaders(self.active, node)


    def buildCutout(self):
        # Cutout
        alpha = self.getValue(["Cutout Opacity"], 1)
        if alpha < 1:
            transp = self.addNode("ShaderNodeBsdfTransparent")
            transp.inputs["Color"].default_value[0:3] = WHITE
            self.addColumn()
            self.active = self.mixShaders(transp, self.active, alpha)
            self.owner.setTransSettings(False, False, WHITE, alpha)

#-------------------------------------------------------------
#   Hair tree for adding root transparency to existing material
#-------------------------------------------------------------

from .tree import NodeGroup

class FadeGroup(NodeGroup, HairTree):
    def __init__(self):
        NodeGroup.__init__(self)
        self.insockets += ["Shader", "Intercept", "Random"]
        self.outsockets += ["Shader"]


    def create(self, node, name, parent):
        HairTree.__init__(self, parent.material, BLACK)
        NodeGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketFloat", "Intercept")
        self.group.inputs.new("NodeSocketFloat", "Random")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        self.column = 3
        self.info = self.inputs
        ramp = self.addRamp(None, "Root Transparency", (1,1,1,0), (1,1,1,1), endpos=0.15)
        maprange = self.addNode('ShaderNodeMapRange', col=1)
        maprange.inputs["From Min"].default_value = 0
        maprange.inputs["From Max"].default_value = 1
        maprange.inputs["To Min"].default_value = -0.1
        maprange.inputs["To Max"].default_value = 0.4
        self.links.new(self.inputs.outputs["Random"], maprange.inputs["Value"])
        add = self.addSockets(ramp.outputs["Alpha"], maprange.outputs["Result"], col=2)
        transp = self.addNode('ShaderNodeBsdfTransparent', col=2)
        transp.inputs["Color"].default_value[0:3] = WHITE
        mix = self.mixSockets(transp.outputs[0], self.inputs.outputs["Shader"], 1)
        self.links.new(add.outputs[0], mix.inputs[0])
        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])


    def addSockets(self, socket1, socket2, col=None):
        node = self.addNode("ShaderNodeMath", col=col)
        math.operation = 'ADD'
        self.links.new(socket1, node.inputs[0])
        self.links.new(socket2, node.inputs[1])
        return node


def addFade(mat):
    tree = FadeHairTree(mat, mat.diffuse_color[0:3])
    tree.build(mat)


class FadeHairTree(HairTree):

    def build(self, mat):
        from .tree import findNode, findLinksTo
        if mat.node_tree is None:
            print("Material %s has no nodes" % mat.name)
            return
        elif findNode(mat.node_tree, 'TRANSPARENCY'):
            print("Hair material %s already has fading roots" % mat.name)
            return
        self.recoverTree(mat)
        links = findLinksTo(self.tree, 'OUTPUT_MATERIAL')
        if links:
            link = links[0]
            fade = self.addGroup(FadeGroup, "DAZ Fade Roots", col=5)
            self.links.new(link.from_node.outputs[0], fade.inputs["Shader"])
            self.links.new(self.info.outputs["Intercept"], fade.inputs["Intercept"])
            self.links.new(self.info.outputs["Random"], fade.inputs["Random"])
            for link in links:
                self.links.new(fade.outputs["Shader"], link.to_socket)


    def recoverTree(self, mat):
        from .tree import findNode, YSIZE, NCOLUMNS
        self.tree = mat.node_tree
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.info = findNode(self.tree, 'HAIR_INFO')
        for col in range(NCOLUMNS):
            self.ycoords[col] -= YSIZE

#-------------------------------------------------------------
#   Hair tree Principled
#-------------------------------------------------------------

class HairPBRTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfHairPrincipled")
        ramp = self.addRamp(pbr, "Color", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Color")
        pbr.inputs["Roughness"].default_value = 0.2
        pbr.inputs["Radial Roughness"].default_value = 0.8
        pbr.inputs["IOR"].default_value = 1.1
        self.buildOutput()

#-------------------------------------------------------------
#   Hair tree Eevee
#-------------------------------------------------------------

class HairEeveeTree(HairTree):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfPrincipled", size=25)
        ramp = self.addRamp(pbr, "Color", self.root, self.tip, slot="Base Color")
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Base Color")
        pbr.inputs["Metallic"].default_value = 0.9
        pbr.inputs["Roughness"].default_value = 0.2
        self.buildOutput()

# ---------------------------------------------------------------------
#   Pinning
# ---------------------------------------------------------------------

class Pinning:
    def __init__(self):
        self.nodeGroup = None
        self.curveMapping = None

    def getCurveMapping(self):
        if self.nodeGroup is None:
            self.nodeGroup = bpy.data.node_groups.new('DazPinningData', 'ShaderNodeTree')
        if self.curveMapping is None:
            cn = self.nodeGroup.nodes.new('ShaderNodeRGBCurve')
            self.curveMapping = cn.name
        return self.nodeGroup.nodes[self.curveMapping]

    def invoke(self, context, event):
        node = self.getCurveMapping()
        cu = node.mapping.curves[3]
        cu.points[0].location = (0,1)
        cu.points[-1].location = (1,0)
        return DazPropsOperator.invoke(self, context, event)

    def draw(self, context):
        self.layout.template_curve_mapping(self.getCurveMapping(), "mapping")


class DAZ_OT_MeshAddPinning(Pinning, DazPropsOperator, IsMesh):
    bl_idname = "daz.mesh_add_pinning"
    bl_label = "Add Pinning Group"
    bl_description = "Add HairPin group to mesh hair"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        node = self.getCurveMapping()
        cu = node.mapping.curves[3]
        if "HairPinning" in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups["HairPinning"]
            ob.vertex_groups.remove(vgrp)
        vgrp = ob.vertex_groups.new(name="HairPinning")
        uvs = ob.data.uv_layers.active.data
        m = 0
        for f in ob.data.polygons:
            for n,vn in enumerate(f.vertices):
                x = min(1.0, max(0.0, 1-uvs[m+n].uv[1]))
                w = node.mapping.evaluate(cu, x)
                vgrp.add([vn], w, 'REPLACE')
            m += len(f.vertices)

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

class DAZ_OT_AddHairRig(DazPropsOperator, Separator, GizmoUser, IsMesh):
    bl_idname = "daz.add_hair_rig"
    bl_label = "Add Hair Rig"
    bl_description = "Add an armature to mesh hair"
    bl_options = {'UNDO'}

    useSeparateLoose = True
    sparsity = 1

    nSectors : IntProperty(
        name = "Sectors",
        description = "Number of sectors",
        min = 2, max = 36,
        default = 12)

    sectorOffset : IntProperty(
        name = "Sector Offset",
        description = "Angle to beginning of first sector",
        min = 0, max = 90,
        default = 0)

    hairLength : IntProperty(
        name = "Hair Length",
        description = "Number of bones in a hair",
        min = 2, max = 10,
        default = 5)

    boneLayer : IntProperty(
        name = "Bone Layer",
        description = "Bone layer for hair bones",
        min = 1, max = 32,
        default = 4)

    controlMethod : EnumProperty(
        items = [('NONE', "None", "Don't add control bones"),
                 ('IK', "IK", "IK controls"),
                 ('BBONES', "Bendy Bones", "Bendy bones"),
                 ('WINDER', "Winder", "Winder")],
        name = "Control Method",
        description = "Method for controlling hair posing",
        default = 'IK')

    useHideBones : BoolProperty(
        name = "Hide Bones",
        description = "Hide the deform bones if using IK",
        default = True)

    roundness : FloatProperty(
        name = "Roundness",
        description = "Expand the joints radially from the head to make the bones rounder",
        min = 0.0, max = 1.0,
        default = 0.5)

    useSeparateRig : BoolProperty(
        name = "Separate Hair Rig",
        description = "Make a separate rig parented to the head bone,\ninstead of adding bones to the main rig",
        default = False)

    headName : StringProperty(
        name = "Head",
        description = "Name of the head bone",
        default = "head")

    weightingMethod : EnumProperty(
        items = [('REAL', "Real Space", "Use location in real space"),
                 ('UV', "UV Space", "Use location in UV space"),
                 ('AUTO', "Auto", "Use Blender automatic bone weighting")],
        name = "Weighting Method",
        description = "Method for weighting mesh",
        default = 'REAL')

    startHair : FloatProperty(
        name = "Hair Start Location",
        description = "Location in UV space where hair starts",
        min = 0.0, max = 1.0,
        default = 0.1)

    endHead : FloatProperty(
        name = "Head End Location",
        description = "Location in UV space where head ends",
        min = 0.0, max = 1.0,
        default = 0.2)

    def draw(self, context):
        self.layout.prop(self, "nSectors")
        self.layout.prop(self, "sectorOffset")
        self.layout.prop(self, "hairLength")
        self.layout.prop(self, "boneLayer")
        self.layout.prop(self, "weightingMethod")
        self.layout.prop(self, "roundness")
        self.layout.prop(self, "controlMethod")
        if self.controlMethod != 'NONE':
            self.layout.prop(self, "useHideBones")
        if self.controlMethod != 'BBONES':
            self.layout.prop(self, "useSeparateRig")
        self.layout.prop(self, "useCheckStrips")
        self.layout.prop(self, "headName")
        if self.weightingMethod == 'REAL':
            self.layout.prop(self, "startHair")
            self.layout.prop(self, "endHead")


    def invoke(self, context, event):
        ob = context.object
        rig = ob.parent
        if rig and rig.DazRig == "mhx":
            self.boneLayer = 17
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        ob = context.object
        hairname = ob.name
        rig = ob.parent
        if rig is None or rig.type != 'ARMATURE':
            raise DazError("Hair must have an armature")
        if self.headName not in rig.data.bones.keys():
            raise DazError('No head bone named "%s"' % self.headName)
        if self.startHair > self.endHead:
            raise DazError("Hair start location cannot exceed head end location")
        self.boneLayers = (self.boneLayer-1)*[False] + [True] + (32-self.boneLayer)*[False]
        self.hiddenLayers = 30*[False] + [True, False]
        if self.useSeparateRig or self.controlMethod == 'BBONES':
            rig = self.addSeparateRig(context, hairname, rig)
            activateObject(context, ob)
        self.startGizmos(context, rig)

        hairs = self.getMeshHairs(context, ob, None)
        datas = []
        for hair in hairs:
            data = self.getData(hair)
            datas.append(data)
        sectors = {}
        for hair,data in zip(hairs, datas):
            angle = data[0] - self.sectorOffset
            key = int(math.floor(self.nSectors*angle/360 + 0.5))
            if key >= self.nSectors:
                key -= self.nSectors
            elif key < 0:
                key += self.nSectors
            if key not in sectors.keys():
                sectors[key] = []
            sectors[key].append((hair,data))
        activateObject(context, rig)

        setMode('EDIT')
        head = rig.data.edit_bones[self.headName]
        binbones = {}
        for key,sector in sectors.items():
            binbones[key] = self.buildBones(key, sector, head, rig)
        if self.controlMethod == 'IK':
            for key,data in binbones.items():
                self.addIkBone(key, data, head, rig)
        elif self.controlMethod == 'BBONES':
            for key,data in binbones.items():
                self.addBendyBones(key, data, head, rig)

        setMode('OBJECT')
        for key,data in binbones.items():
            self.hideBones(data, rig)
        if self.controlMethod == 'IK':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for key,data in binbones.items():
                self.addIkConstraint(key, data, rig, gizmo)
        elif self.controlMethod == 'BBONES':
            for key,data in binbones.items():
                self.addBendyConstraints(key, data, rig)
        elif self.controlMethod == 'NONE':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for data in binbones.values():
                self.addAutoIk(data, rig, gizmo)
        elif self.controlMethod == 'WINDER':
            from .fix import addWinder
            self.makeGizmos(False, ["GZM_Knuckle"])
            gizmo = self.gizmos["GZM_Knuckle"]
            for key,data in binbones.items():
                bones,locs,xaxis = data
                addWinder(rig, bones[0][0], gizmo, True, self.boneLayers, self.hiddenLayers, xaxis=xaxis)

        if self.weightingMethod != 'AUTO':
            for key,data in binbones.items():
                self.buildVertexGroups(key, sectors[key], data)
        ob = self.mergeObjects(context, hairs, hairname, rig)
        if self.weightingMethod == 'AUTO':
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                ob.modifiers.remove(mod)
            activateObject(context, rig)
            ob.select_set(True)
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        elif self.useSeparateRig:
            ob.parent = rig
            mod = getModifier(ob, 'ARMATURE')
            mod.object = rig
            mod.name = "Armature Hair"
        rig.data.layers[self.boneLayer-1] = True


    def mergeObjects(self, context, hairs, hairname, rig):
        print("Merge %d objects to %s" % (len(hairs), hairs[0].name))
        activateObject(context, hairs[0])
        for hair in hairs:
            hair.select_set(True)
        bpy.ops.object.join()
        ob = context.object
        ob.name = hairname
        bpy.ops.object.shade_smooth()
        return ob


    def addSeparateRig(self, context, hairname, rig):
        rigname = "%s Rig" % hairname
        amt = bpy.data.armatures.new(rigname)
        hairrig = bpy.data.objects.new(rigname, amt)
        hairrig.parent = rig
        hairrig.parent_type = 'BONE'
        hairrig.parent_bone = self.headName
        hairrig.show_in_front = True
        context.collection.objects.link(hairrig)
        activateObject(context, rig)
        setMode('EDIT')
        eb = rig.data.edit_bones[self.headName]
        head = eb.head.copy()
        tail = eb.tail.copy()
        roll = eb.roll
        setMode('OBJECT')
        activateObject(context, hairrig)
        setMode('EDIT')
        eb = amt.edit_bones.new(self.headName)
        eb.head = head
        eb.tail = tail
        eb.roll = roll
        eb.hide_select = True
        setMode('OBJECT')
        setWorldMatrix(hairrig, rig.matrix_world)
        return hairrig


    def getData(self, hair):
        coord = np.array([list(v.co) for v in hair.data.vertices])
        x,y,z = np.average(coord, axis=0)
        angle = math.atan2(y, x)/D
        if angle < 0:
            angle += 360
        return angle,coord


    def buildBones(self, key, sector, head, rig):
        from .bone import setRoll
        hair,data = sector[0]
        coord = data[1]
        for hair,data in sector[1:]:
            coord = np.append(coord, data[1], axis=0)
        zmin = np.min(coord[:,2])
        zmax = np.max(coord[:,2])
        c = np.array(head.tail)
        dr = coord-c
        dr[:,2] = 0
        norm = np.linalg.norm(dr, axis=1)
        nmin = np.min(norm)
        nmax = np.max(norm)
        angle = (key*360/self.nSectors + self.sectorOffset)
        x = math.cos(angle*D)
        y = math.sin(angle*D)
        rmin = np.array((nmin*x + c[0], nmin*y + c[1], zmax))
        rmax = np.array((nmax*x + c[0], nmax*y + c[1], zmin))
        e1 = rmin - c
        e2 = rmax - c
        xaxis = Vector(np.cross(e1, e2))
        xaxis.normalize()
        dmin = np.linalg.norm(e1)
        dmax = np.linalg.norm(e2)
        r0 = rmin
        d0 = dmin
        bones = []
        parent = head
        locs = []
        for n in range(self.hairLength):
            s = (n+1)/self.hairLength
            r1 = (1-s)*rmin + s*rmax
            d1 = (1-s)*dmin + s*dmax
            f = d1/np.linalg.norm(r1-c)
            r1 = (1-self.roundness)*r1 + self.roundness*(c + f*(r1-c))
            bname = "Hair_%d_%d" % (key, n)
            eb = rig.data.edit_bones.new(bname)
            eb.head = r0
            eb.tail = r1
            if self.controlMethod == 'WINDER':
                setRoll(eb, xaxis)
            eb.parent = parent
            if n > 0:
                eb.use_connect = True
            bones.append((bname, r0, r1))
            locs.append((r0+r1)/2)
            r0 = r1
            parent = eb
        return bones, np.array(locs), xaxis


    def getIkName(self, key):
        return "Hair_%d_IK" % key


    def addIkBone(self, key, data, head, rig):
        def normalize(v):
            return v/np.linalg.norm(v)

        bones,locs,xaxis = data
        lastname,r0,r1 = bones[-1]
        eb = rig.data.edit_bones.new(self.getIkName(key))
        eb.head = r1
        eb.tail = r1 + rig.DazScale*normalize(r1-r0)
        eb.parent = head


    def getHandleName(self, key, n):
        return "Handle_%d_%d" % (key, n)


    def addBendyBones(self, key, data, head, rig):
        def addHandle(n):
            handle = rig.data.edit_bones.new(self.getHandleName(key, n))
            handle.head = r0 - eps*dr
            handle.tail = r0 + eps*dr
            handle.use_connect = False
            handle.parent = None
            return handle

        #rig.data.display_type = 'BBONE'
        bones,locs,xaxis = data
        eps = 0.05
        for n,bdata in enumerate(bones):
            bname,r0,r1 = bdata
            dr = r1 - r0
            vec = dr/np.linalg.norm(dr)
            bb = rig.data.edit_bones[bname]
            handle = addHandle(n)
            bb.use_connect = False
            bb.parent = handle
            bb.head = r0 + eps*dr
            bb.tail = r1 - eps*dr
        r0 = r1
        handle = addHandle(len(bones))


    def addAutoIk(self, data, rig, gizmo):
        bones,locs,xaxis = data
        lname,r0,r1 = bones[-1]
        pb = rig.pose.bones[lname]
        pb.custom_shape = gizmo
        s = self.hairLength/25
        if hasattr(pb, "custom_shape_scale_xyz"):
            pb.custom_shape_scale_xyz = (s,s,s)
        else:
            pb.custom_shape_scale = s


    def addIkConstraint(self, key, data, rig, gizmo):
        bones,locs,xaxis = data
        ikname = self.getIkName(key)
        lastname,r0,r1 = bones[-1]
        pb = rig.pose.bones[lastname]
        cns = pb.constraints.new('IK')
        cns.name = "IK %s" % ikname
        cns.target = rig
        cns.subtarget = ikname
        cns.chain_count = len(bones)
        cns.use_location = True
        cns.use_rotation = True
        pb = rig.pose.bones[ikname]
        pb.bone.show_wire = True
        pb.custom_shape = gizmo
        pb.bone.use_deform = False
        pb.bone.layers = self.boneLayers


    def addBendyConstraints(self, key, data, rig):
        def getHandle(n):
            handlename = self.getHandleName(key, n)
            handle = rig.pose.bones[handlename]
            handle.bone.bbone_x = handleSize
            handle.bone.bbone_z = handleSize
            handle.bone.use_deform = False
            return handle

        from .mhx import stretchTo
        bones,locs,xaxis = data
        bboneSize = 0.001
        handleSize = 0.005
        if self.useSeparateRig:
            rig.data.display_type = 'BBONE'
            head = rig.data.bones[self.headName]
            head.bbone_x = handleSize
            head.bbone_z = handleSize
            for n,bdata in enumerate(bones):
                bname,r0,r1 = bdata
                bone = rig.data.bones[bname]
                bone.layers = self.boneLayers

        handle = getHandle(0)
        for n,bdata in enumerate(bones):
            bname,r0,r1 = bdata
            pb = rig.pose.bones[bname]
            lockAllTransforms(pb)
            pb.bone.bbone_segments = 6
            pb.bone.bbone_x = bboneSize
            pb.bone.bbone_z = bboneSize
            pb.bone.bbone_handle_type_start = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_start = handle.bone
            handle = getHandle(n+1)
            pb.bone.bbone_handle_type_end = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_end = handle.bone
            stretchTo(pb, handle, rig)


    def hideBones(self, data, rig):
        bones,locs,xaxis = data
        if self.controlMethod == 'NONE' or not self.useHideBones:
            for bname,r0,r1 in bones:
                bone = rig.data.bones[bname]
                bone.layers = self.boneLayers
        elif self.useHideBones:
            for bname,r0,r1 in bones:
                bone = rig.data.bones[bname]
                bone.layers = self.hiddenLayers
                bone.hide_select = True


    def buildVertexGroups(self, key, sector, data):
        bones,blocs,xaxis = data
        blocs = blocs[None,:,:]
        for hair,data in sector:
            hair.vertex_groups.clear()
            hgrp = hair.vertex_groups.new(name=self.headName)
            vgrps = [hgrp]
            for bname,r0,r1 in bones:
                vgrp = hair.vertex_groups.new(name=bname)
                vgrps.append(vgrp)
            heights = self.getUvHeights(hair)
            if self.weightingMethod == 'REAL':
                weights = self.getWeightsFromLocs(hair, blocs, heights)
            elif self.weightingMethod == 'UV':
                weights = self.getWeightsFromUvs(hair, heights)
            for gn,vgrp in enumerate(vgrps):
                for vn,w in enumerate(weights[:,gn]):
                    if w > 0.001:
                        vgrp.add([vn], w, 'REPLACE')


    def getUvHeights(self, hair):
        uvlayer = hair.data.uv_layers[0]
        heights = dict([(vn, uvlayer.data[f.loop_indices[i]].uv[1])
            for f in hair.data.polygons
            for i,vn in enumerate(f.vertices)
            ])
        ylist = list(heights.values())
        ymin = min(ylist)
        ymax = max(ylist)
        k = 1/(ymax-ymin)
        hlist = list()
        hlist.sort()
        heights = dict([(vn,k*(y-ymin)) for vn,y in heights.items()])
        return heights


    def getWeightsFromLocs(self, hair, blocs, heights):
        vlocs = np.array([v.co for v in hair.data.vertices])
        vecs = np.subtract(vlocs[:,None,:], blocs)
        dists = np.linalg.norm(vecs, axis=2)
        weights = 1.0/(dists + 0.0001)
        norms = np.linalg.norm(weights, axis=1)
        weights = np.divide(weights, norms[:,None])
        nverts = vlocs.shape[0]

        hweights = np.zeros([nverts], dtype=float)
        y1 = 1 - self.startHair
        y2 = 1 - self.endHead
        for vn,y in heights.items():
            if y > y1:
                hweights[vn] = 1.0
                weights[vn,:] = 0
            elif y > y2:
                w = (y-y2)/(y1-y2)
                hweights[vn] = min(w,1)
        weights = np.append(hweights[:,None], weights, axis=1)
        return weights


    def getWeightsFromUvs(self, hair, heights):
        nverts = len(hair.data.vertices)
        k = self.hairLength+1
        weights = np.zeros([nverts, k+1], dtype=float)
        for vn,y in heights.items():
            s = k*(1-y)
            m = int(math.floor(s))
            a = s-m
            if a < 0.5:
                if m > 0:
                    weights[vn,m] = a + 0.5
                    weights[vn,m-1] = 0.5 - a
                else:
                    weights[vn,m] = 1.0
            else:
                if m < k:
                    weights[vn,m] = 1.5 - a
                    weights[vn,m+1] = a - 0.5
                else:
                    weights[vn,m] = 1.0
        return weights

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    ColorGroup,

    DAZ_OT_MakeHair,
    DAZ_OT_CombineHairs,
    DAZ_OT_UpdateHair,
    DAZ_OT_ColorHair,
    DAZ_OT_ConnectHair,
    DAZ_OT_MeshAddPinning,
    DAZ_OT_AddHairRig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
