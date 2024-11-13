#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import bpy
import math
import numpy as np

from mathutils import Vector, Matrix
from .error import *
from .utils import *
from .tree import addGroupInput, addGroupOutput, getGroupInput
from .material import WHITE, GREY, BLACK, isWhite, isBlack
from .cycles import CyclesMaterial, CyclesTree
from .selector import Selector
from .guess import ColorProp
from .fix import GizmoUser
from .transfer import MatchOperator
from .pin import Pinner
from .dforce import Cloth, Collision

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

    image : StringProperty()


class Separator:
    useCheckStrips : BoolProperty(
        name = "Check Strips",
        description = "Check that the hair mesh consists of strips in UV space",
        default = True)

    def getMeshHairs(self, context, hair, hum):
        hairs = []
        if self.useSeparateLoose:
            from .geometry import clearMeshProps
            print("Separate loose parts")
            clearMeshProps(hair)
            bpy.ops.mesh.separate(type='LOOSE')
            print("Loose parts separated")
        setMode('OBJECT')
        hname = baseName(hair.name)
        haircount = 0
        hairs = []
        for hair in getSelectedMeshes(context):
            if baseName(hair.name) == hname and hair != hum:
                if self.checkStrip(context, hair):
                    hairs.append(hair)
        if self.sparsity > 1:
            keeps = []
            deletes = []
            for n,hair in enumerate(hairs):
                if n % self.sparsity == 0:
                    keeps.append(hair)
                else:
                    deletes.append(hair)
            hairs = keeps
            deleteObjects(context, deletes)
        return hairs


    def checkStrip(self, context, hair):
        if (not self.useCheckStrips or
            len(hair.data.polygons) < 50 or
            hair.data.uv_layers.active is None):
            return True
        uvs = hair.data.uv_layers.active.data
        xs = [uv.uv[0] for uv in uvs]
        ys = [uv.uv[1] for uv in uvs]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        isstrip = (dx > 2*dy or dy > 2*dx)
        if not isstrip:
            activateObject(context, hair)
            msg = '"%s" is not a strip.\nDid you separate the scalp from the rest of the hair?\nDisable Check Strips to avoid this error' % hair.name
            print(msg)
            raise DazError(msg)
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

    enums = [('PARTICLES', "Particles", "Particle hair"),
             ('CURVES', "Curves", "Ordinary curves"),
             ('POLYLINES', "Polylines", "Line meshes, one for each strand"),
             ('MESH', "Mesh", "Single line mesh")]
    if not BLENDER3:
        enums = [('HAIR_CURVES', "Hair Curves", "Hair curves")] + enums
    output : EnumProperty(
        items = enums,
        name = "Output",
        description = "")

    useSingleOutput : BoolProperty(
        name = "Single Output",
        description = "Hair output is a single object",
        default = True)

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
        description = (
            "Resize hair so all strands have the same length,\n" +
            "and thus fit into a single particle system.\n" +
            "Known to cause problems for hair dynamics")
    )

    useAutoResize : BoolProperty(
        name = "Auto Resize",
        default = True,
        description = "Resize each material to the length of the longest strand")

    useResizeInBlocks : BoolProperty(
        name = "Resize In Blocks",
        default = False,
        description = "Resize hair in blocks of ten afterwards")

    useSnapRoots : BoolProperty(
        name = "Snap Roots",
        default = True,
        description = "Snap roots to nearest point on mesh")

    # Settings

    nRenderChildren : IntProperty(
        name = "Render Children",
        description = "Number of hair children displayed in renders",
        min = 0,
        default = 10)

    strandShape : EnumProperty(
        items = [('STANDARD', "Standard", "Standard strand shape"),
                 ('ROOTS', "Fading Roots", "Root transparency (standard shape with fading roots)\nCan cause performance problems in scenes with volume effects"),
                 ('SHRINK', "Root And Tip Shrink", "Root and tip shrink.\n(Root and tip radii interchanged)")],
        name = "Strand Shape",
        description = "Strand shape",
        default = 'STANDARD')

    nViewChildren : IntProperty(
        name = "Viewport Children",
        description = "Number of hair children displayed in viewport",
        min = 0,
        default = 5)

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

    hairRadius : FloatProperty(
        name = "Hair radius (mm)",
        description = "Strand diameter",
        min = 0,
        default = 0.1)

    hairShape : FloatProperty(
        name = "Hair Shape",
        description = "Hair shape parameter",
        min = -1, max = 1,
        default = 0)

    hairLength : FloatProperty(
        name = "Hair Length (meters)",
        description = "Hair length during emission",
        min = 0.1, max = 2,
        default = 0.5)

    viewFactor : FloatProperty(
        name = "Viewport Factor",
        description = "The fraction of children displayed in the viewport",
        min = 0, max = 1,
        default = 0.1)

    childRadius : FloatProperty(
        name = "Child radius (mm)",
        description = "Radius of children around parent",
        min = 0,
        default = 10)

    # Materials

    multiMaterials : BoolProperty(
        name = "Multi Materials",
        description = "Create separate particle systems for each material",
        default = False)

    keepMaterial : BoolProperty(
        name = "Keep Material",
        description = "Use existing material",
        default = True)

    useActiveTexture : BoolProperty(
        name = "Use Active Texture",
        description = "Use the active texture of the scalp mesh as hair color",
        default = False)

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
        self.material = ""
        if mnum < len(btn.materials):
            mat = btn.materials[mnum]
            if mat:
                self.material = mat.name


    def setHairSettings(self, psys, ob):
        btn = self.button
        pset = psys.settings
        pset.hair_length = btn.hairLength * GS.scale * 100
        if btn.nViewChildren or btn.nRenderChildren:
            pset.child_type = 'SIMPLE'
        else:
            pset.child_type = 'NONE'
        pset.use_hair_bspline = True
        if hasattr(pset, "display_step"):
            pset.display_step = 3
        else:
            pset.draw_step = 3
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
        if hasattr(pset, "child_nbr"):
            pset.child_nbr = btn.nViewChildren
        else:
            pset.child_percent = btn.nViewChildren
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


    def snapRoots(self, context, hum):
        from mathutils.bvhtree import BVHTree
        deps = context.evaluated_depsgraph_get()
        bvhtree = BVHTree.FromObject(hum, deps)
        nstrands = []
        for strand in self.strands:
            loc = bvhtree.find_nearest(strand[0])[0]
            nstrands.append([loc] + strand[1:])
        self.strands = nstrands


    def build(self, context, ob):
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

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
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

#-------------------------------------------------------------
#   HairBuilder class
#-------------------------------------------------------------

class HairBuilder(Pinner, Cloth, Collision):

    hairPoseSim : EnumProperty(
        items = [('NONE', "None", "Neither posing nor simulation"),
                 ('POSING', "Posing", "Posing"),
                 ('SIMULATION', "Simulation", "Simulation")],
        name = "Hair Posing/Simulation",
        description = "Add a hair proxy mesh for posing or simulation",
        default = 'NONE')

    useVertexGroups : BoolProperty(
        name = "Copy Vertex Groups",
        description = "Copy vertex groups to proxy mesh",
        default = False)

    proxyType : EnumProperty(
        items = [('LINE', "Line", "Line proxy mesh"),
                 ('SHEET', "Sheet", "Sheet proxy mesh"),
                 ('TUBE', "Tube", "Tubular proxy mesh")],
        name = "Proxy Mesh",
        description = "Proxy mesh type",
        default = 'SHEET')

    proxyWidth : FloatProperty(
        name = "Proxy width (mm)",
        description = "Width of the proxy strands",
        min = 0.001,
        max = 10,
        precision = 3,
        default = 1.0)

    usePinGroup : BoolProperty(
        name = "Pinning Group",
        description = "Add a pinning group to the hair proxy",
        default = True)

    useClothSimulation : BoolProperty(
        name = "Cloth Simulation",
        description = "Add a cloth simulation",
        default = True)

    def drawPoseSim(self, context, layout):
        layout.prop(self, "hairPoseSim")
        if self.hairPoseSim == 'POSING':
            layout.prop(self, "proxyType")
            layout.prop(self, "useVertexGroups")
        elif self.hairPoseSim == 'SIMULATION':
            layout.prop(self, "proxyType")
            layout.prop(self, "proxyWidth")
            layout.prop(self, "usePinGroup")
            if self.usePinGroup:
                self.drawMapping(context, layout)
                layout.separator()
            layout.prop(self, "useClothSimulation")
            if self.useClothSimulation:
                self.drawCloth(context, layout)
                self.drawCollision(context, layout)


    def buildMesh(self, context, hname, strands, hair, hum, mnames):
        def getVectors(coords):
            if len(coords) == 1:
                return Vector((1,0,0)), Vector((0,1,0))
            tang = coords[-1] - coords[0]
            norm = tang.cross(Vector((0,0,1)))
            return tang.normalized(), norm.normalized()

        nverts = 0
        verts = []
        edges = []
        faces = []
        for strand in strands:
            verts += strand
        nverts = len(verts)
        dr = self.proxyWidth * 0.1 * GS.scale
        if self.hairPoseSim == 'NONE':
            return
        elif self.hairPoseSim == 'POSING' and self.proxyType == 'LINE':
            m = 0
            for strand in strands:
                nsverts = len(strand)
                edges += [(m+n, m+n+1) for n in range(nsverts-1)]
                m += nsverts
        elif self.proxyType in ['SHEET', 'LINE']:
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*norm
                    verts.append(tuple(v))
            m1 = -1
            for strand in strands:
                if not strand:
                    continue
                m1 += 1
                m2 = m1+nverts
                for s in strand[1:]:
                    faces.append((m1, m1+1, m2+1, m2))
                    m1 += 1
                    m2 += 1
        elif self.proxyType == 'TUBE':
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*norm
                    verts.append(tuple(v))
            for strand in strands:
                if not strand:
                    continue
                coords = [Vector(r) for r in strand]
                tang,norm = getVectors(coords)
                for r in coords:
                    v = r + dr*tang.cross(norm)
                    verts.append(tuple(v))
            m1 = -1
            for strand in strands:
                if not strand:
                    continue
                m1 += 1
                m2 = m1+nverts
                m3 = m1+2*nverts
                faces.append((m1, m2, m3))
                for s in strand[1:]:
                    faces.append((m1, m1+1, m2+1, m2))
                    faces.append((m2, m2+1, m3+1, m3))
                    faces.append((m3, m3+1, m1+1, m1))
                    m1 += 1
                    m2 += 1
                    m3 += 1
                faces.append((m1, m3, m2))

        me = bpy.data.meshes.new(hname)
        me.from_pydata(verts, edges, faces)
        #me.DazHairType = self.proxyType
        ob = self.buildObject(hname, me, hair, hum, mnames)

        def addWeights(vgrp, strands, m):
            for strand in strands:
                nsverts = len(strand)
                for n in range(nsverts):
                    vgrp.add([m+n], n/(nsverts-1), 'REPLACE')
                m += nsverts

        vgrp = ob.vertex_groups.new(name="Root Distance")
        addWeights(vgrp, strands, 0)
        if self.proxyType == 'SHEET':
            addWeights(vgrp, strands, nverts)
            if self.proxyType == 'TUBE':
                addWeights(vgrp, strands, 2*nverts)
        return ob


    def buildHairProxy(self, context, hname, strands, hair, hum):
        mat = bpy.data.materials.get("Hair Proxy")
        if mat is None:
            mat = bpy.data.materials.new("Hair Proxy")
            mat.diffuse_color[0:3] = (1,0,0)
        proxy = self.buildMesh(context, hname, strands, hair, hum, [mat.name])
        proxy.hide_render = True
        if self.hairPoseSim == 'SIMULATION' and self.usePinGroup:
            self.addHairPinning(proxy)
            if self.useClothSimulation:
                self.addCloth(proxy)
        return proxy


    def buildCurves(self, context, hname, strands, hair, hum, mnames):
        cu = bpy.data.curves.new(hname, 'CURVE')
        cu.dimensions = '3D'
        cu.twist_mode = 'TANGENT'
        for strand in strands:
            npoints = len(strand)
            spline = cu.splines.new('POLY')
            spline.points.add(npoints-1)
            for co,point in zip(strand, spline.points):
                point.co[0:3] = co
        return self.buildObject(hname, cu, hair, hum, mnames)


    def buildHairCurves(self, context, hname, strands, hair, hum, mnames):
        from .geometry import getActiveUvLayer
        curves = bpy.data.hair_curves.new(self.name)
        sizes = [len(strand) for strand in strands]
        curves.add_curves(sizes)
        for strand,curve in zip(strands, curves.curves):
            for pos,point in zip(strand, curve.points):
                point.position = pos
        curves.surface = hum
        uvlayer = getActiveUvLayer(hum)
        if uvlayer:
            curves.surface_uv_map = uvlayer.name
        return self.buildObject(hname, curves, hair, hum, mnames)


    def buildObject(self, hname, data, hair, hum, mnames):
        ob = bpy.data.objects.new(hname, data)
        wmat = ob.matrix_world.copy()
        ob.parent = hum
        ob.parent_bone = hair.parent_bone
        ob.parent_type = hair.parent_type
        setWorldMatrix(ob, wmat)
        for mname in mnames:
            mat = bpy.data.materials.get(mname)
            data.materials.append(mat)
        return ob


    def linkHair(self, ob, hum, coll):
        coll.objects.link(ob)
        rig = hum.parent
        if rig and rig.type == 'ARMATURE':
            head = rig.data.bones.get("head")
            wmat = ob.matrix_world.copy()
            ob.parent = rig
            if head:
                ob.parent_type = 'BONE'
                ob.parent_bone = head.name
            setWorldMatrix(ob, wmat)


    def addFollowProxy(self, hair, proxy):
        from .geonodes import FollowProxyGroup
        from .tree import addNodeGroup
        from .dforce import ModStore
        stores = []
        for mod in list(hair.modifiers):
            if not (mod.type == 'NODES' and
                    mod.node_group and
                    mod.node_group.name == "DAZ Follow Proxy"):
                stores.append(ModStore(mod))
            hair.modifiers.remove(mod)
        mod = hair.modifiers.new("Follow %s" % proxy.name, 'NODES')
        mod.node_group = addNodeGroup(FollowProxyGroup, "DAZ Follow Proxy")
        mod["Socket_1"] = proxy
        for store in stores:
            store.restore(hair)

#-------------------------------------------------------------
#   Make Hair Proxy
#-------------------------------------------------------------

class DAZ_OT_MakeHairProxy(DazPropsOperator, HairBuilder, IsCurves):
    bl_idname = "daz.make_hair_proxy"
    bl_label = "Make Hair Proxy"
    bl_description = "Make proxy for hair curves and add cloth simulation to it"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.drawPoseSim(context, self.layout)

    def invoke(self, context, event):
        self.invokePinner()
        self.hairPoseSim = 'SIMULATION'
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        hair = context.object
        hum = hair.parent
        hname = baseName(hair.name).lstrip("Hair ")
        strands = []
        for cu in hair.data.curves:
            strand = [tuple(point.position) for point in cu.points]
            strands.append(strand)
        proxy = self.buildHairProxy(context, hname, strands, hair, hum)
        proxy.name = "Proxy %s" % baseName(hair.name)
        self.linkHair(proxy, hum, context.collection)
        self.addFollowProxy(hair, proxy)

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

class DAZ_OT_MakeHair(MatchOperator, CombineHair, IsMesh, HairOptions, HairBuilder, Separator):
    bl_idname = "daz.make_hair"
    bl_label = "Make Hair"
    bl_description = "Make particle hair from mesh hair"
    bl_options = {'UNDO'}

    dialogWidth = 1000

    def draw(self, context):
        split = self.layout.split(factor=0.7)
        row = split.row()
        col = row.column()
        box = col.box()
        box.label(text="Create")
        box.prop(self, "strandType", expand=True)
        box.label(text="Output")
        box.prop(self, "output", expand=True)
        if self.output in ['MESH', 'CURVES', 'HAIR_CURVES']:
            box.prop(self, "useSingleOutput")
        if self.strandType == 'SHEET':
            box.prop(self, "strandOrientation")
            box.prop(self, "useSeparateLoose")
            box.prop(self, "useCheckStrips")
        box.prop(self, "keepMesh")
        box.prop(self, "removeOldHairs")
        box.prop(self, "useSnapRoots")
        if not self.hasSingleOutput():
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
            box.prop(self, "useActiveTexture")
            if self.useActiveTexture:
                pass
            elif multimat:
                for item in self.colors:
                    row2 = box.row()
                    row2.label(text=item.name)
                    row2.prop(item, "color", text="")
            else:
                box.prop(self, "color")

        col = row.column()
        box = col.box()
        box.label(text="Settings")
        if self.output == 'PARTICLES':
            box.prop(self, "nViewChildren")
            box.prop(self, "nRenderChildren")
            box.prop(self, "hairLength")
            box.prop(self, "childRadius")
            box.prop(self, "rootRadius")
            box.prop(self, "tipRadius")
            box.prop(self, "nViewStep")
            box.prop(self, "nRenderStep")
            box.prop(self, "strandShape")
        elif self.output ==  'HAIR_CURVES':
            box.prop(self, "nRenderChildren")
            box.prop(self, "viewFactor")
            box.prop(self, "childRadius")
            box.prop(self, "hairRadius")
            box.prop(self, "strandShape")

        col = split.column()
        box = col.box()
        box.label(text="Posing/Simulation")
        if self.output ==  'HAIR_CURVES':
            self.drawPoseSim(context, box)


    def invoke(self, context, event):
        ob = context.object
        self.strandType = ob.data.DazHairType
        self.colors.clear()
        for mat in ob.data.materials:
            if mat and mat.node_tree:
                item = self.colors.add()
                item.name = mat.name
                item.color = mat.diffuse_color
                self.color = mat.diffuse_color
                node = mat.node_tree.nodes.active
                if node and node.type == 'TEX_IMAGE' and node.image:
                    item.image = node.image.name
        self.invokePinner()
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        from .merge import applyTransformToObjects, restoreTransformsToObjects
        hair,hum = getHairAndHuman(context, True)
        applyTransformToObjects([hair])
        wmats = applyTransformToObjects([hum])
        try:
            self.makeHair(context, hair, hum)
        finally:
            restoreTransformsToObjects(wmats)


    def makeHair(self, context, hair, hum):
        t1 = perf_counter()
        self.clocks = []
        duphair = None
        if self.keepMesh or self.useVertexGroups:
            activateObject(context, hair)
            bpy.ops.object.duplicate()
            if self.useVertexGroups:
                duphair = getSelectedObjects(context)[-1]

        if self.strandType == 'SHEET':
            if not hair.data.uv_layers.active:
                raise DazError("Hair object has no active UV layer.\nConsider using Line or Tube strand types instead")
        elif self.strandType == 'LINE':
            if hair.data.polygons:
                raise DazError("Cannot use Line strand type for hair mesh with faces")
        elif self.strandType == 'TUBE':
            self.multiMaterials = False

        from .transfer import applyAllShapekeys
        applyAllShapekeys(hair)
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

        if self.hasSingleOutput():
            pass
        elif self.useResizeInBlocks and not self.useAutoResize:
            hsystems = self.blockResize(hsystems, hum)
        elif self.useResizeHair:
            hsystems = self.hairResize(self.size, hsystems, hum)
        t6 = perf_counter()
        self.clocks.append(("Resize", t6-t5))
        if self.useSnapRoots:
            for hsys in hsystems.values():
                hsys.snapRoots(context, hum)
        if self.output == 'PARTICLES' and BLENDER3:
            self.makeParticleHair(context, hsystems, hum)
        else:
            self.makePolylineHair(context, hsystems, hair, hum, duphair)
        for hair in hairs:
            unlinkAll(hair, True)
        #deleteObjects(context, hairs)
        if duphair and not self.keepMesh:
            unlinkAll(duphair, True)
            deleteObjects(context, [duphair])
        t7 = perf_counter()
        self.clocks.append(("Make Hair", t7-t6))
        if self.nonquads:
            print("Ignored %d non-quad faces out of %d faces" % (len(self.nonquads), nhairfaces))
        print("Hair converted in %.2f seconds" % (t7-t1))
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


    def makePolylineHair(self, context, hsystems, hair, hum, duphair):
        print("Make polyline hair")
        coll = getCollection(context, hair)
        if not hsystems:
            print("No hair system found")
        elif self.output in ['MESH', 'CURVES', 'HAIR_CURVES', 'PARTICLES']:
            for hsys in hsystems.values():
                self.buildOutput(context, hsys.name, hsys.strands, hair, hum, [hsys.material], coll, duphair)
        elif self.output == 'POLYLINES':
            subcoll = bpy.data.collections.new(name = "Mesh Hairs")
            coll.children.link(subcoll)
            for hsys in hsystems.values():
                for strand in hsys.strands:
                    ob = self.buildMesh(context, hsys.name, [strand], hair, hum, [hsys.material])
                    subcoll.objects.link(ob)
        print("Done")


    def buildOutput(self, context, hname, strands, hair, hum, mnames, coll, duphair):
        proxy = None
        if self.output == 'MESH':
            ob = self.buildMesh(context, hname, strands, hair, hum, mnames)
        elif self.output == 'CURVES':
            ob = self.buildCurves(context, hname, strands, hair, hum, mnames)
        elif self.output == 'HAIR_CURVES':
            ob = self.buildHairCurves(context, hname, strands, hair, hum, mnames)
            if self.hairPoseSim != 'NONE':
                proxy = self.buildHairProxy(context, hname, strands, hair, hum)
        elif self.output == 'PARTICLES':
            ob = self.buildHairCurves(context, hname, strands, hair, hum, mnames)

        ob.name = "Hair %s" % baseName(hair.name)
        self.linkHair(ob, hum, coll)
        if proxy:
            proxy.name = "Proxy %s" % baseName(hair.name)
            self.linkHair(proxy, hum, coll)
            if duphair:
                from .transfer import transferVertexGroups
                transferVertexGroups(context, duphair, [proxy], 1e-3)
                mod = proxy.modifiers.new("Armature", 'ARMATURE')
                mod.object = duphair.parent
                proxy.parent = duphair.parent
                proxy.parent_type = 'OBJECT'
                proxy.matrix_basis = Matrix()

        if self.output == 'PARTICLES':
            activateObject(context, ob)
            bpy.ops.curves.convert_to_particle_system()
            activateObject(context, hum)
            ob.hide_set(True)
            ob.hide_render = True
            hsys = HairSystem("Dummy", 0, hum, 0, self)
            for psys in hum.particle_systems:
                pset = psys.settings
                hair = psys.particles[0]
                pset.hair_step = len(hair.hair_keys) - 1
                pset.count = len(psys.particles)
                hsys.setHairSettings(psys, hum)
        if self.output == 'HAIR_CURVES':
            def addMod(ob, name):
                group = bpy.data.node_groups.get(name)
                if group:
                    mod = ob.modifiers.new(name, 'NODES')
                    mod.node_group = group
                    return mod

            if proxy:
                self.addFollowProxy(ob, proxy)
            mod = addMod(ob, "Set Hair Curve Profile")
            if mod:
                mod["Input_3"] = self.hairRadius * 1e-3
                mod["Input_2"] = self.hairShape
            mod = addMod(ob, "Duplicate Hair Curves")
            if mod:
                mod["Input_2"] = self.nRenderChildren
                mod["Input_4"] = self.viewFactor
                mod["Input_5"] = self.childRadius * 1e-3


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
        for mfaces,tfaces in trects:
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


    def hasSingleOutput(self):
        return (self.output in ['MESH', 'CURVES', 'HAIR_CURVES'] and self.useSingleOutput)


    def getHairKey(self, n, mnum):
        if self.multiMaterials and mnum < len(self.materials):
            mat = self.materials[mnum]
            if self.hasSingleOutput():
                hname = mat.name
            else:
                hname = "%d_%s" % (n, mat.name)
        else:
            mnum = 0
            if self.hasSingleOutput():
                hname = ""
            else:
                hname = str(n)
        return hname, mnum


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
        nix = (None,None,None,None)
        if len(singlets) > 0:
            if len(singlets) != 2:
                sys.stdout.write("S")
                return nix
            if (types[3] != [] or types[4] != []):
                sys.stdout.write("T")
                return nix
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
                return nix
            if len(doublets) < 4:
                if len(doublets) == 2:
                    sys.stdout.write("2")
                    self.selectFaces(ob, neighbors.keys())
                return nix
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
                    mname = "H%s" % item.name
                    if self.useActiveTexture:
                        img = bpy.data.images.get(item.image)
                    else:
                        img = None
                    mat = buildHairMaterial(mname, item.color, img, context, force=True)
                    if fade:
                        addFade(mat)
                    mats.append(mat)
            for mat in mats:
                if self.output == 'PARTICLES' and BLENDER3:
                    hum.data.materials.append(mat)
                self.materials.append(mat)
        else:
            mname = self.activeMaterial
            mat = hair.data.materials[mname]
            img = None
            if not keepmat:
                node = mat.node_tree.nodes.active
                if self.useActiveTexture and node and node.type == 'TEX_IMAGE':
                    img = node.image
                mat = buildHairMaterial("Hair", self.color, img, context, force=True)
            if fade and img:
                addFade(mat, img)
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
        if psys.cloth:
            csettings = self.getSettings(psys.cloth.settings)
        else:
            csettings = None
        return psettings, hdyn, csettings


    def setAllSettings(self, psys, data):
        psettings, hdyn, csettings = data
        self.setSettings(psys.settings, psettings)
        psys.use_hair_dynamics = hdyn
        if csettings is not None:
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
    bl_description = "Copy settings from active particle system to all other particle systems"
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
                mat = buildHairMaterial(mname, self.color, None, context, force=True)
                if fade:
                    addFade(mat, None)
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

def buildHairMaterial(mname, color, img, context, force=False):
    color = list(color[0:3])
    hmat = HairMaterial(mname, color, img)
    hmat.force = force
    hmat.build(context, color, img)
    return hmat.rna


class HairMaterial(CyclesMaterial):

    def __init__(self, name, color, img):
        CyclesMaterial.__init__(self, name)
        self.name = name
        self.color = color
        self.image = img


    def guessColor(self):
        if self.rna:
            self.rna.diffuse_color = self.color


    def build(self, context, color, img):
        from .material import Material
        if not Material.build(self, context):
            return
        self.tree = getHairTree(self, color, img)
        self.tree.build()
        self.rna.diffuse_color[0:3] = self.color


def getHairTree(dmat, color=BLACK, img=None):
    #print("Creating %s hair material" % LS.hairMaterialMethod)
    if LS.hairMaterialMethod == 'HAIR_PRINCIPLED':
        return HairPBRTree(dmat, color, img)
    elif LS.hairMaterialMethod == 'PRINCIPLED':
        return HairEeveeTree(dmat, color, img)
    else:
        return HairBSDFTree(dmat, color, img)

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat, color, img):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = color
        self.image = img
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
            bump.inputs["Distance"].default_value = 0.1 * GS.scale
            bump.inputs["Height"].default_value = 1
            self.normal = bump


    def linkTangent(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Tangent"])


    def linkBumpNormal(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Normal"])


    def addRamp(self, node, label, root, tip, endpos=1, slot="Color"):
        if self.image:
            root = tip = WHITE
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
        if self.image:
            xyz = self.addNode("ShaderNodeCombineXYZ", col = self.column-3)
            xyz.inputs[0].default_value = 0.5
            xyz.inputs[1].default_value = 0.5
            xyz.inputs[2].default_value = 0.5
            tex = self.addNode("ShaderNodeTexImage", col=self.column-2, size=2)
            tex.image = self.image
            tex.hide = True
            self.links.new(xyz.outputs["Vector"], tex.inputs["Vector"])
            mult,a,b,socket = self.addMixRgbNode('MULTIPLY', self.column-1, size=12)
            mult.inputs[0].default_value = 1
            self.links.new(ramp.outputs["Color"], a)
            self.links.new(tex.outputs["Color"], b)
        else:
            socket = ramp.outputs["Color"]
        return ramp,socket


    def readColor(self, factor):
        root,self.roottex,_ = self.getColorTex(["Hair Root Color"], "COLOR", self.color, useFactor=False)
        tip,self.tiptex,_ = self.getColorTex(["Hair Tip Color"], "COLOR", self.color, useFactor=False)
        self.owner.rna.diffuse_color[0:3] = root
        self.root = factor * Vector(root)
        self.tip = factor * Vector(tip)


    def linkRamp(self, ramp, socket, texs, node, slot):
        out = socket
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
        root,roottex,_ = self.getColorTex(["Root Transmission Color"], "COLOR", self.color, useFactor=False)
        tip,tiptex,_ = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color, useFactor=False)
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 1
        trans.inputs["RoughnessV"].default_value = 1
        ramp,socket = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, socket, [roottex, tiptex], trans, "Color")
        #self.linkTangent(trans)
        self.active = trans
        return trans


    def buildHighlight(self):
        refl = self.addNode('ShaderNodeBsdfHair')
        refl.component = 'Reflection'
        refl.inputs['Offset'].default_value = 0
        refl.inputs["RoughnessU"].default_value = 0.02
        refl.inputs["RoughnessV"].default_value = 1.0
        ramp,socket = self.addRamp(refl, "Reflection", self.root, self.tip)
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], refl, "Color")
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
        HairTree.__init__(self, parent.owner, BLACK, None)
        NodeGroup.create(self, node, name, parent, 4)
        addGroupInput(self.group, "NodeSocketShader", "Shader")
        addGroupInput(self.group, "NodeSocketFloat", "Intercept")
        addGroupInput(self.group, "NodeSocketFloat", "Random")
        addGroupOutput(self.group, "NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        self.column = 3
        self.info = self.inputs
        ramp,socket = self.addRamp(None, "Root Transparency", (1,1,1,0), (1,1,1,1), endpos=0.15)
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


def addFade(mat, img):
    tree = FadeHairTree(mat, mat.diffuse_color[0:3], img)
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
        ramp,socket = self.addRamp(pbr, "Color", self.root, self.tip)
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], pbr, "Color")
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
        pbr = self.active = self.addNode("ShaderNodeBsdfPrincipled")
        ramp,socket = self.addRamp(pbr, "Color", self.root, self.tip, slot="Base Color")
        self.linkRamp(ramp, socket, [self.roottex, self.tiptex], pbr, "Base Color")
        pbr.inputs["Metallic"].default_value = 0.9
        pbr.inputs["Roughness"].default_value = 0.2
        self.buildOutput()

# ---------------------------------------------------------------------
#   Add Hair Rig
# ---------------------------------------------------------------------

class HairBoneInfo:
    def __init__(self, bones, weights, xaxis, hairs):
        self.bones = bones
        self.weights = weights
        self.xaxis = xaxis
        self.hairs = hairs


class DAZ_OT_AddHairRig(DazPropsOperator, Separator, GizmoUser, IsMesh):
    bl_idname = "daz.add_hair_rig"
    bl_label = "Add Hair Rig"
    bl_description = "Add an armature to mesh hair"
    bl_options = {'UNDO'}

    useSeparateLoose = True
    sparsity = 1
    gizmoFile = "knuckle"

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

    keepVertexNumbers : BoolProperty(
        name = "Keep Vertex Numbers",
        description = "Keep vertex numbers.\nThis is necessary for hair proxy meshes",
        default = True)

    controlMethod : EnumProperty(
        items = [('NONE', "None", "Don't add control bones"),
                 ('IK', "IK", "IK controls"),
                 ('BBONE', "Bendy Bones", "Bendy bones"),
                 ('WINDER', "Winder", "Winder")],
        name = "Control Method",
        description = "Method for controlling hair posing",
        default = 'NONE')

    useHideBones : BoolProperty(
        name = "Hide IK Deform Bones",
        description = "Hide the deform bones if using IK",
        default = True)

    useSeparateRig : BoolProperty(
        name = "Separate Hair Rig",
        description = "Make a separate rig parented to the head bone,\ninstead of adding bones to the main rig",
        default = True)

    headName : StringProperty(
        name = "Head",
        description = "Name of the head bone",
        default = "head")

    useVertexGroups : BoolProperty(
        name = "Vertex Groups",
        description = "Create vertex groups based on Z coordinate",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "nSectors")
        self.layout.prop(self, "sectorOffset")
        self.layout.prop(self, "hairLength")
        self.layout.prop(self, "keepVertexNumbers")
        self.layout.prop(self, "useVertexGroups")
        self.layout.prop(self, "controlMethod")
        if self.controlMethod == 'IK':
            self.layout.prop(self, "useHideBones")
        if False and self.controlMethod != 'BBONE':
            self.layout.prop(self, "useSeparateRig")
        self.layout.prop(self, "useCheckStrips")
        self.layout.prop(self, "headName")


    def run(self, context):
        ob = context.object
        hairname = ob.name
        rig = ob.parent
        if rig is None:
            raise DazError("No rig found")
        if rig is None or rig.type != 'ARMATURE':
            raise DazError("Hair must have an armature")
        if self.headName not in rig.data.bones.keys():
            raise DazError('No head bone named "%s"' % self.headName)
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            ob.modifiers.remove(mod)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

        # Remove old vertex groups
        for vgrp in list(ob.vertex_groups):
            if vgrp.name not in ["Root Distance"]:
                ob.vertex_groups.remove(vgrp)

        # Create a separate hair rig
        if self.useSeparateRig or self.controlMethod == 'BBONE':
            rig = self.addSeparateRig(context, hairname, rig)

        # Duplicate mesh and store original vertex number in an attribute
        self.startGizmos(context, rig)
        activateObject(context, ob)
        origMesh = None
        if self.keepVertexNumbers and not BLENDER3:
            bpy.ops.object.duplicate()
            for ob1 in getSelectedMeshes(context):
                if ob1 != ob:
                    origMesh = ob
                    ob = ob1
                    ob.name = "DUPLI"
                    break
            activateObject(context, ob)
        if origMesh:
            self.storeOrigVerts(ob)

        # Divide hair into sectors
        hairs = self.getMeshHairs(context, ob, None)
        sectors = {}
        for hair in hairs:
            data = self.getAngleCoord(hair)
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

        # Build deform bones and compute weights
        setMode('EDIT')
        head = rig.data.edit_bones[self.headName]
        binbones = {}
        for key,sector in sectors.items():
            binbones[key] = self.buildBones(context, key, sector, head, rig)

        # Build control bones
        if self.controlMethod == 'IK':
            for key,bininfo in binbones.items():
                self.addIkBone(key, bininfo, head, rig)
        elif self.controlMethod == 'BBONE':
            for key,bininfo in binbones.items():
                self.addBendyBones(key, bininfo, head, rig)
            rig.data.display_type = 'BBONE'
        #self.addSkull(rig, binbones)

        setMode('OBJECT')
        hairs = []
        for key,bininfo in binbones.items():
            hair = self.mergeObjects(context, bininfo.hairs, "Sector %d" % key)
            bininfo.hairs = [hair]
            hairs.append(hair)
        for key,bininfo in binbones.items():
            self.hideBones(bininfo, rig)

        # Add vertex groups
        if self.useVertexGroups:
            for key,bininfo in binbones.items():
                self.buildVertexGroups(key, bininfo)

        # Add constraints for control bones
        if self.controlMethod == 'IK':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for key,bininfo in binbones.items():
                self.addIkConstraint(key, bininfo, rig, gizmo)
        elif self.controlMethod == 'BBONE':
            for key,bininfo in binbones.items():
                self.addBendyConstraints(key, bininfo, rig)
        elif False and self.controlMethod == 'NONE':
            gizmo = self.makeEmptyGizmo("GZM_Cone", 'CONE')
            for bininfo in binbones.values():
                self.addAutoIk(bininfo, rig, gizmo)
        elif self.controlMethod == 'WINDER':
            from .winder import addWinder
            self.makeGizmos(False, ["GZM_Knuckle"])
            gizmo = self.gizmos["GZM_Knuckle"]
            activateObject(context, rig)
            for key,bininfo in binbones.items():
                bnames = [bone[0] for bone in bininfo.bones]
                windname = "Wind_%s" % bnames[0]
                layers = [T_WIDGETS, T_HIDDEN]
                addWinder(rig, windname, bnames, layers, gizmo=gizmo, useLocation=True, xaxis=bininfo.xaxis)
            activateObject(context, ob)

       # Merge rigs
        ob = self.mergeObjects(context, hairs, hairname)
        if origMesh:
            self.restoreOrigVerts(origMesh, ob)
            deleteObjects(context, [ob])
            ob = origMesh

        self.makeEnvelope(context, ob, rig)
        activateObject(context, ob)
        wmat = ob.matrix_world.copy()
        ob.parent = rig
        ob.parent_type = 'OBJECT'
        if self.useVertexGroups:
            addArmatureModifier(ob, rig, "Armature Hair")
        setWorldMatrix(ob, wmat)
        bpy.ops.object.transform_apply()
        enableRigNumLayer(rig, T_WIDGETS)
        enableRigNumLayer(rig, T_HIDDEN, False)


    def mergeObjects(self, context, hairs, hairname):
        print("Merge %d objects to %s" % (len(hairs), hairs[0].name))
        activateObject(context, hairs[0])
        for hair in hairs:
            hair.select_set(True)
        bpy.ops.object.join()
        ob = context.object
        ob.name = hairname
        bpy.ops.object.shade_smooth()
        return ob


    def storeOrigVerts(self, ob):
        ovi:Attribute = ob.data.attributes.new("orig_vertex", 'INT', 'POINT')
        for v in ob.data.vertices:
            ovi.data[v.index].value = v.index


    def restoreOrigVerts(self, origMesh, ob):
        origMesh.vertex_groups.clear()
        weights = {}
        ngrps = {}
        for gn,vgrp in enumerate(ob.vertex_groups):
            ngrp = origMesh.vertex_groups.new(name = vgrp.name)
            ngrps[gn] = ngrp
        for v in ob.data.vertices:
            weights[v.index] = dict([(g.group, g.weight) for g in v.groups])
        ovi = ob.data.attributes["orig_vertex"]
        for vn,elt in enumerate(ovi.data):
            ovn = elt.value
            for gn,w in weights[vn].items():
                ngrps[gn].add([ovn], w, 'REPLACE')


    def makeEnvelope(self, context, ob, rig):
        for bone in rig.data.bones:
            if bone.name == "Skull":
                bone.envelope_distance = 10*GS.scale
                bone.head_radius = 3*GS.scale
                bone.tail_radius = 3*GS.scale
            elif bone.use_deform:
                bone.envelope_distance = 50*GS.scale/self.nSectors
                bone.head_radius = 20*GS.scale/self.nSectors
                bone.tail_radius = 20*GS.scale/self.nSectors
            else:
                bone.envelope_distance = 0.1*GS.scale
                bone.head_radius = 0.1*GS.scale
                bone.tail_radius = 0.1*GS.scale


    def addSeparateRig(self, context, hairname, rig):
        rigname = "%s Rig" % hairname
        amt = bpy.data.armatures.new(rigname)
        hairrig = bpy.data.objects.new(rigname, amt)
        hairrig.parent = rig
        hairrig.parent_type = 'BONE'
        hairrig.parent_bone = self.headName
        hairrig.show_in_front = True
        for coll in bpy.data.collections:
            if rig.name in coll.objects:
                coll.objects.link(hairrig)
        activateObject(context, rig)
        setMode('EDIT')
        eb = rig.data.edit_bones[self.headName]
        head = eb.head.copy()
        tail = eb.tail.copy()
        roll = eb.roll
        setMode('OBJECT')
        activateObject(context, hairrig)
        setWorldMatrix(hairrig, rig.matrix_world)
        bpy.ops.object.transform_apply()
        setMode('EDIT')
        eb = amt.edit_bones.new(self.headName)
        eb.head = head
        eb.tail = tail
        eb.roll = roll
        setMode('OBJECT')
        hairrig.data.display_type = 'STICK'
        hairrig.lock_location = TTrue
        bone = amt.bones[self.headName]
        enableBoneNumLayer(bone, hairrig, T_HIDDEN)
        return hairrig


    def getAngleCoord(self, hair):
        coord = np.array([list(v.co) for v in hair.data.vertices])
        x,y,z = np.average(coord, axis=0)
        angle = math.atan2(y, x)/D
        if angle < 0:
            angle += 360
        return angle,coord


    def buildBones(self, context, key, sector, head, rig):
        from .bone import setRoll
        hair,data = sector[0]
        coord = data[1]
        hairs = [hair]
        for hair,data in sector[1:]:
            coord = np.append(coord, data[1], axis=0)
            hairs.append(hair)
        z = coord[:,2]
        zmin = np.min(z)
        zmax = np.max(z)
        dz = (zmax - zmin)/self.hairLength
        npoints = self.hairLength+1
        joints = []
        for n in range(npoints):
            c = zmax - n*dz - 0.5*dz
            idxs = np.argwhere(np.abs(z-c) <= dz)
            batch = coord[idxs]
            r = np.average(batch, axis=0)
            r = r.reshape((3,))
            if n == 0:
                r[0] = 0
            else:
                r[2] = zmax - n*dz
            joints.append(r)

        angle = (key*360/self.nSectors + self.sectorOffset)
        x = math.cos(angle*D)
        y = math.sin(angle*D)
        arrow = np.array((x,y,0))
        c = np.array(head.tail)
        dr = coord-c
        dr[:,2] = 0
        norm = np.linalg.norm(dr, axis=1)
        nmin = np.min(norm)
        nmax = np.max(norm)
        rmin = np.array((nmin*x + c[0], nmin*y + c[1], zmax))
        rmax = np.array((nmax*x + c[0], nmax*y + c[1], zmin))
        e1 = rmin - c
        e2 = rmax - c
        xaxis = Vector(np.cross(e1, e2))
        xaxis.normalize()

        weights = np.zeros((coord.shape[0], npoints), dtype=float)
        c = zmax - 0.5*dz
        weights[:,0] = np.clip((z-c)/dz, 0.0, 1.0)
        for n in range(1,npoints):
            c = zmax - n*dz + 0.5*dz
            weights[:,n] = np.clip(1-np.abs(z-c)/dz, 0.0, 1.0)
        idxs = np.argwhere(z < zmin + 0.5*dz)
        weights[idxs,npoints-1] = 1.0
        idxs = np.argwhere(np.dot(coord, arrow) < 0)
        weights[idxs,:] = 0
        weights[idxs,0] = 1.0

        bones = []
        locs = []
        parent = head
        r0 = joints[0]
        for n,r1 in enumerate(joints[1:]):
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
            r0 = r1
            parent = eb

        return HairBoneInfo(bones, weights, xaxis, hairs)


    def getIkName(self, key):
        return "Hair_%d_IK" % key


    def addIkBone(self, key, bininfo, head, rig):
        def normalize(v):
            return v/np.linalg.norm(v)

        lastname,r0,r1 = bininfo.bones[-1]
        eb = rig.data.edit_bones.new(self.getIkName(key))
        eb.head = r1
        eb.tail = r1 + rig.DazScale*normalize(r1-r0)
        eb.parent = head


    def getHandleName(self, key, n):
        return "Handle_%d_%d" % (key, n)


    def addBendyBones(self, key, bininfo, head, rig):
        def addHandle(n):
            handle = rig.data.edit_bones.new(self.getHandleName(key, n))
            handle.head = r0 - eps*dr
            handle.tail = r0 + eps*dr
            handle.use_connect = False
            handle.parent = None
            return handle

        eps = 0.05
        bb = None
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            dr = r1 - r0
            if bb:
                bb.tail = r0 - eps*dr
            bb = rig.data.edit_bones[bname]
            bb.use_connect = False
            handle = addHandle(n)
            bb.parent = handle
            bb.head = r0 + eps*dr
        r0 = r1
        bb.tail = r0 - eps*dr
        handle = addHandle(len(bininfo.bones))


    def addSkull(self, rig, binbones):
        centers = []
        for bininfo in binbones.values():
            centers.append(bininfo.bones[0][1])
        coord = np.array(centers)
        x,y,z = np.average(coord, axis=0)
        head = rig.data.edit_bones.get(self.headName)
        skull = rig.data.edit_bones.new("Skull")
        skull.head = (0, y-5*GS.scale, z-2*GS.scale)
        skull.tail = (0, y+5*GS.scale, z-2*GS.scale)
        skull.parent = head
        enableBoneNumLayer(skull, rig, T_HIDDEN)


    def addAutoIk(self, bininfo, rig, gizmo):
        lname,r0,r1 = bininfo.bones[-1]
        pb = rig.pose.bones[lname]
        pb.custom_shape = gizmo
        setCustomShapeTransform(pb, self.hairLength/25)


    def addIkConstraint(self, key, bininfo, rig, gizmo):
        ikname = self.getIkName(key)
        lastname,r0,r1 = bininfo.bones[-1]
        pb = rig.pose.bones[lastname]
        cns = pb.constraints.new('IK')
        cns.name = "IK %s" % ikname
        cns.target = rig
        cns.subtarget = ikname
        cns.chain_count = len(bininfo.bones)
        cns.use_location = True
        cns.use_rotation = True
        pb = rig.pose.bones[ikname]
        pb.bone.show_wire = True
        pb.custom_shape = gizmo
        pb.bone.use_deform = False
        enableBoneNumLayer(pb.bone, rig, T_WIDGETS)


    def addBendyConstraints(self, key, bininfo, rig):
        def getHandle(n):
            handlename = self.getHandleName(key, n)
            handle = rig.pose.bones[handlename]
            handle.bone.bbone_x = handleSize
            handle.bone.bbone_z = handleSize
            handle.bone.use_deform = False
            return handle

        from .rig_utils import stretchTo
        bboneSize = 0.1*GS.scale
        handleSize = 0.5*GS.scale

        rig.data.display_type = 'BBONE'
        head = rig.data.bones[self.headName]
        head.bbone_x = 1*GS.scale
        head.bbone_z = 1*GS.scale
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            bone = rig.data.bones[bname]
            enableBoneNumLayer(bone, rig, T_WIDGETS)

        handle = getHandle(0)
        enableBoneNumLayer(handle, rig, T_WIDGETS)
        for n,bdata in enumerate(bininfo.bones):
            bname,r0,r1 = bdata
            pb = rig.pose.bones[bname]
            lockAllTransforms(pb)
            pb.bone.bbone_segments = 6
            pb.bone.bbone_x = bboneSize
            pb.bone.bbone_z = bboneSize
            pb.bone.bbone_handle_type_start = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_start = handle.bone
            handle = getHandle(n+1)
            enableBoneNumLayer(handle, rig, T_WIDGETS)
            pb.bone.bbone_handle_type_end = 'ABSOLUTE'
            pb.bone.bbone_custom_handle_end = handle.bone
            stretchTo(pb, handle, rig)
            pb.bone.hide_select = True


    def hideBones(self, bininfo, rig):
        if self.controlMethod == 'IK' and self.useHideBones:
            layer = T_HIDDEN
        else:
            layer = T_WIDGETS
        for bname,r0,r1 in bininfo.bones:
            bone = rig.data.bones[bname]
            enableBoneNumLayer(bone, rig, layer)


    def buildVertexGroups(self, key, bininfo):
        print("Build sector %d weights: %d" % (key, len(bininfo.hairs)))
        for hair in bininfo.hairs:
            hgrp = hair.vertex_groups.new(name=self.headName)
            vgrps = [hgrp]
            for bname,r0,r1 in bininfo.bones:
                vgrp = hair.vertex_groups.new(name=bname)
                vgrps.append(vgrp)
            weights = bininfo.weights
            for gn,vgrp in enumerate(vgrps):
                for vn,w in enumerate(weights[:,gn]):
                    if w > 0.001:
                        vgrp.add([vn], w, 'REPLACE')


def addArmatureModifier(ob, rig, modname):
    from .dforce import addModifierFirst
    mod = getModifier(ob, 'ARMATURE')
    if mod is None:
        mod = addModifierFirst(ob, modname, 'ARMATURE')
        mod.object = rig
    else:
        mod.object = rig
        mod.name = modname

# ---------------------------------------------------------------------
#   Add Hair Rig
# ---------------------------------------------------------------------

class DAZ_OT_SetEnvelopes(DazPropsOperator, IsArmature):
    bl_idname = "daz.set_envelopes"
    bl_label = "Set Envelopes"
    bl_description = "Change the envelopes of all deform bones"
    bl_options = {'UNDO'}

    envelope_distance : FloatProperty(
        name = "Distance",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    head_radius : FloatProperty(
        name = "Head Radius",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    tail_radius : FloatProperty(
        name = "Tail Radius",
        min = 0.0001,
        precision = 4,
        default = 0.01)

    def draw(self, context):
        self.layout.prop(self, "envelope_distance")
        self.layout.prop(self, "head_radius")
        self.layout.prop(self, "tail_radius")

    def invoke(self, context, event):
        rig = context.object
        for bone in rig.data.bones:
            if isHairBone(bone):
                self.envelope_distance = bone.envelope_distance
                self.head_radius = bone.head_radius
                self.tail_radius = bone.tail_radius
                break
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        rig = context.object
        for bone in rig.data.bones:
            if isHairBone(bone):
                bone.envelope_distance = self.envelope_distance
                bone.head_radius = self.head_radius
                bone.tail_radius = self.tail_radius

# ---------------------------------------------------------------------
#   Toggle Hair Locks
# ---------------------------------------------------------------------

class DAZ_OT_ToggleHairLocks(DazOperator, IsArmature):
    bl_idname = "daz.toggle_hair_locks"
    bl_label = "Toggle Hair Locks"
    bl_description = "Disable/enable locking of all deform bones"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        lock = None
        for bone in rig.data.bones:
            if isHairBone(bone):
                if lock is None:
                    lock = (not bone.hide_select)
                bone.hide_select = lock


def isHairBone(bone):
    words = bone.name.split("_")
    return (bone.use_deform and
            len(words) >= 3 and
            words[1].isdigit() and
            words[2].isdigit())

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    ColorGroup,

    DAZ_OT_MakeHair,
    DAZ_OT_MakeHairProxy,
    DAZ_OT_CombineHairs,
    DAZ_OT_UpdateHair,
    DAZ_OT_ColorHair,
    DAZ_OT_ConnectHair,
    DAZ_OT_AddHairRig,
    DAZ_OT_SetEnvelopes,
    DAZ_OT_ToggleHairLocks,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
