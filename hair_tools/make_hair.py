# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import sys
import bpy
from mathutils import Vector, Matrix
from ..error import *
from ..utils import *
from ..tree import addGroupInput, addGroupOutput, getGroupInput
from ..material import WHITE, GREY, BLACK, isWhite, isBlack
from ..hair_material import HairTree
from ..transfer import MatchOperator
from .hair_builder import HairBuilder

#-------------------------------------------------------------
#   Separator class
#-------------------------------------------------------------

class Separator:
    useCheckStrips : BoolProperty(
        name = "Check Strips",
        description = "Check that the hair mesh consists of strips in UV space",
        default = True)

    def getMeshHairs(self, context, hair, hum):
        hairs = []
        if self.useSeparateLoose:
            from ..geometry import clearMeshProps
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
        from ..channels import Channels
        self.name = ("Hair_%s" % key)
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
        pset.child_radius = 0.1*btn.childRadius*GS.scale

        if hasattr(ccset, "root_width"):
            ccset.root_width = 0.1*btn.rootRadius
            ccset.tip_width = 0.1*btn.tipRadius
        else:
            ccset.root_radius = 0.1*btn.rootRadius
            ccset.tip_radius = 0.1*btn.tipRadius
        if btn.strandShape == 'SHRINK':
            pset.shape = 0.99
        ccset.radius_scale = GS.scale


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

#-------------------------------------------------------------
#   Tesselator class
#-------------------------------------------------------------

class Tesselator:
    def unTesselateFaces(self, context, hair):
        self.squashFaces(hair)
        self.removeDoubles(context, hair)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair)


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


    def removeDoubles(self, context, hair):
        activateObject(context, hair)
        threshold = 0.001*GS.scale
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')


    def checkTesselation(self, hair):
        # Check that there are only pure lines
        from ..tables import getVertEdges
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


    def mergeRemainingFaces(self, hair):
        for f in hair.data.polygons:
            fverts = [hair.data.vertices[vn] for vn in f.vertices]
            r0 = fverts[0].co
            for v in fverts:
                v.co = r0
                v.select = True
        threshold = 0.001*GS.scale
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
        pgs = dazRna(hair.data).DazPolylineMaterials
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
        box.label(text="Deform")
        if self.output == 'HAIR_CURVES':
            box.prop(self, "deformType")
            if self.deformType == 'NONE':
                box.prop(self, "useHeadParent")
            elif self.deformType == 'CURVES':
                box.prop(self, "onInvalid")
            elif self.deformType == 'PROXY':
                self.drawPoseSim(context, box)
        else:
            box.prop(self, "useHeadParent")


    def invoke(self, context, event):
        ob = context.object
        self.strandType = dazRna(ob.data).DazHairType
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
        from ..merge_rigs import applyTransformToObjects, restoreTransformsToObjects
        hair,hum = getHairAndHuman(context, True)
        applyTransformToObjects(context, [hair])
        wmats = applyTransformToObjects(context, [hum])
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

        from ..apply import applyAllShapekeys
        applyAllShapekeys(hair)
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
                tess.unTesselateFaces(context, hair)
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
            if self.deformType == 'PROXY':
                proxy = self.buildHairProxy(context, hname, strands, hair, hum)
        elif self.output == 'PARTICLES':
            ob = self.buildHairCurves(context, hname, strands, hair, hum, mnames)

        ob.name = "Hair %s" % baseName(hair.name)
        coll.objects.link(ob)
        if self.deformType == 'NONE' or self.output != 'HAIR_CURVES':
            self.parentToHead(ob, hum)
        elif self.deformType == 'CURVES':
            if "rest_position" not in hum.data.attributes.keys():
                hum.data.attributes.new("rest_position", 'FLOAT_VECTOR', 'POINT')
            if activateObject(context, ob):
                setMode('SCULPT_CURVES')
                bpy.ops.curves.snap_curves_to_surface(attach_mode='NEAREST')
                setMode('OBJECT')
        elif self.deformType == 'PROXY':
            proxy.name = "Proxy %s" % baseName(hair.name)
            coll.objects.link(proxy)
            self.addProxyModifiers(context, proxy, hum)
            if duphair:
                from ..transfer import transferVertexGroups
                useEdges = (self.proxyType == 'LINE')
                transferVertexGroups(context, duphair, [proxy], 1e-3, useEdges)
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

        elif self.output == 'HAIR_CURVES':
            from .hair_nodes import addHairNodeGroup
            activateObject(context, ob)
            if self.deformType == 'PROXY':
                self.addFollowProxy(ob, proxy)
            elif self.deformType == 'CURVES':
                self.addDeformCurves(ob, hum)

            def addMod(ob, name):
                group = addHairNodeGroup(ob, name)
                if group:
                    mod = ob.modifiers.new(name, 'NODES')
                    mod.node_group = group
                    return mod

            mod = addMod(ob, "Set Hair Curve Profile")
            if mod:
                socket = ("Input" if "Input_2" in mod.keys() else "Socket")
                mod["%s_3" % socket] = self.hairRadius * 1e-3
                mod["%s_2" % socket] = self.hairShape
            mod = addMod(ob, "Duplicate Hair Curves")
            if mod:
                socket = ("Input" if "Input_2" in mod.keys() else "Socket")
                mod["%s_2" % socket] = self.nRenderChildren
                mod["%s_4" % socket] = self.viewFactor
                mod["%s_5" % socket] = self.childRadius * 1e-3

    def findMeshRects(self, hair):
        from ..tables import getVertFaces, findNeighbors
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
        from ..tables import getVertFaces, findNeighbors, findTexVerts
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
        from ..tables import getVertFaces, findNeighbors
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
        from ..hair_material import buildHairMaterial
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

#-------------------------------------------------------------
#   Hair tree for adding root transparency to existing material
#-------------------------------------------------------------

from ..tree import NodeGroup

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
        node.operation = 'ADD'
        self.links.new(socket1, node.inputs[0])
        self.links.new(socket2, node.inputs[1])
        return node


def addFade(mat, img):
    tree = FadeHairTree(mat, mat.diffuse_color[0:3], img)
    tree.build(mat)


class FadeHairTree(HairTree):

    def build(self, mat):
        from ..tree import findNode, findLinksTo
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
        from ..tree import findNode, YSIZE, NCOLUMNS
        self.tree = mat.node_tree
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.info = findNode(self.tree, 'HAIR_INFO')
        for col in range(NCOLUMNS):
            self.ycoords[col] -= YSIZE


# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    ColorGroup,
    DAZ_OT_MakeHair,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
