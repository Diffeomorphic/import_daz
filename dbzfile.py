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

import bpy
import os
from mathutils import Vector, Quaternion, Matrix
from .error import *
from .utils import *
from .fileutils import MultiFile, DbzFile
from .morphing import PropDrivers, PosableMaker
from .category import addToCategories
from .uilist import updateScrollbars

#------------------------------------------------------------------
#   DBZ fitting
#------------------------------------------------------------------

class DBZInfo:
    def __init__(self, filepath):
        if filepath:
            self.name = os.path.basename(os.path.splitext(filepath)[0])
        else:
            self.name = "None"
        self.objects = {}
        self.hdobjects = {}
        self.hdshells = {}
        self.rigs = {}


    def getEntry(self, attr, key, inst):
        entries = getattr(self, attr)
        struct = entries.get(key, {})
        if inst.label in struct.keys():
            return struct[inst.label]
        elif inst.name in struct.keys():
            return struct[inst.name]
        elif 0 in struct.keys():
            nkeys = len(struct.keys()) - 1
            for n in range(nkeys):
                entry = struct.get(n)
                if entry is not None:
                    struct[n] = None
                    return entry
            return struct.get(nkeys)
        print('No DBZ data: %s "%s" "%s" "%s"' % (attr, key, inst.label, inst.name))


    def addEntry(self, attr, key, label, entry):
        entries = getattr(self, attr)
        if key not in entries.keys():
            entries[key] = {}
        if label is None:
            label = len(entries[key])
        entries[key][label] = entry


    def fitFigure(self, inst, dbzrig):
        from .figure import FigureInstance
        from .bone import BoneInstance
        if dbzrig is None:
            print("Cannot fit %s" % inst)
        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                dbzchild = self.getEntry("rigs", child.node.name, child)
                self.fitFigure(child, dbzchild)
            elif isinstance(child, BoneInstance):
                self.fitBone(child, dbzrig)


    def fitBone(self, inst, dbzrig):
        from .figure import FigureInstance
        from .bone import BoneInstance
        if inst.node.name not in dbzrig.restdata.keys():
            return
        inst.restdata = dbzrig.restdata[inst.node.name]
        #transform = dbzrig.transforms[inst.node.name]
        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                dbzchild = self.getEntry("rigs", child.node.name, child)
                self.fitFigure(child, dbzchild)
            if isinstance(child, BoneInstance):
                self.fitBone(child, dbzrig)


    def tryGetName(self, name):
        replacements = [
            (" ", "_"),
            (" ", "-"),
            (".", "_"),
            (".", "-"),
        ]
        if name in self.objects.keys():
            return name
        else:
            name = name.replace("(","_").replace(")","_")
            for old,new in replacements:
                if name.replace(old, new) in self.objects.keys():
                    return name.replace(old, new)
        return None


    def getAlternatives(self, nname):
        return []
        alts = []
        for oname,data in self.objects.items():
            if nname == oname[:-2]:
                alts.append(data)
        return alts


class DBZObject:
    def __init__(self, name, label, verts, uvs, edges, faces, polylines, matgroups, polymats, props, lod, center):
        self.name = name
        self.label = label
        self.verts = verts
        self.uvs = uvs
        self.edges = edges
        self.faces = faces
        self.polylines = polylines
        self.matgroups = matgroups
        if polymats:
            self.polyline_materials = polymats
        else:
            self.polyline_materials = [0]*len(polylines)
        self.properties = props
        self.lod = lod
        self.center = center

    def __repr__(self):
        return "<DBZ %s l:%s v:%d e:%d f:%d p:%d mg:%d>" % (self.name, self.label, len(self.verts), len(self.edges), len(self.faces), len(self.polylines), len(self.matgroups))


class DBZRig:
    def __init__(self, label, restdata, transforms, center):
        self.label = label
        self.restdata = restdata
        self.transforms = transforms
        self.center = center

    def __repr__(self):
        return "<DRIG %s r:%d t:%d c:%s>" % (self.label, len(self.restdata), len(self.transforms), self.center)


class DBZNode:
    def __init__(self, center):
        self.center = center

    def __repr__(self):
        return "<DBN c:%s>" % self.center

#------------------------------------------------------------------
#   Load DBZ file
#------------------------------------------------------------------

def loadDbzFile(filepath):
    from .load_json import loadJson
    from .geometry import d2bList
    dbz = DBZInfo(filepath)
    struct = loadJson(filepath)
    if ("application" not in struct.keys() or
        struct["application"] not in ["export_basic_data", "export_to_blender", "export_highdef_to_blender"]):
        msg = ("The file\n" +
               filepath + "           \n" +
               "does not contain data exported from DAZ Studio")
        raise DazError(msg)

    for figure in struct["figures"]:
        center = figure.get("center_point")
        if center:
            center = Vector(center)
        else:
            continue
        name = figure["name"]
        label = figure.get("label")
        nverts = figure.get("num verts", 0)
        nhdverts = figure.get("num hd verts", 0)

        verts = []
        if "vertices" in figure.keys():
            verts = d2bList(figure["vertices"])
            edges = faces = polylines = polymats = uvs = matgroups = []
            props = {}
            for key,value in figure.items():
                if key == "edges":
                    edges = value
                elif key == "faces":
                    faces = value
                elif key == "polylines":
                    polylines = value
                elif key == "polyline_materials":
                    polymats = value
                elif key == "uvs":
                    uvs = value
                elif key == "material groups":
                    matgroups = value
                elif key == "node":
                    props = value["properties"]
            dbzobj = DBZObject(name, label, verts, uvs, edges, faces, polylines, matgroups, polymats, props, 0, center)
            dbz.addEntry("objects", name, label, dbzobj)

        if GS.useHighDef and nhdverts > 0:
            LS.useHDObjects = True
            verts = faces = polylines = polymats = uvs = matgroups = []
            lod = 0
            props = {}
            for key,value in figure.items():
                if key == "hd vertices":
                    verts = d2bList(value)
                elif key == "subd level":
                    lod = value
                elif key == "hd uvs":
                    uvs = value
                elif key == "hd polylines":
                    polylines = value
                elif key == "hd polylines":
                    polymats = value
                elif key == "hd faces":
                    faces = value
                elif key == "hd material groups":
                    matgroups = value
            dbzobj = DBZObject(name, label, verts, uvs, [], faces, polylines, matgroups, polymats, props, lod, center)
            if nverts == 0:
                dbz.addEntry("hdshells", nhdverts, label, dbzobj)
            else:
                dbz.addEntry("hdobjects", name, label, dbzobj)

        restdata = {}
        transforms = {}
        addDbzData(figure, "NODE", restdata, transforms)
        for bone in figure.get("bones", []):
            addDbzData(bone, bone["name"], restdata, transforms)
        dbzrig = DBZRig(label, restdata, transforms, center)
        dbz.addEntry("rigs", name, label, dbzrig)
    return dbz


def addDbzData(node, bname, restdata, transforms):
    head = dazhead = Vector(node["center_point"])
    tail = Vector(node["end_point"])
    vec = tail - head
    if "ws_transform" in node.keys():
        ws = node["ws_transform"]
        wsmat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
        head = Vector(ws[9:12])
        tail = head + vec @ wsmat
    elif "ws_pos" in node.keys():
        head = Vector(node["ws_pos"])
        x,y,z,w = node["ws_rot"]
        quat = Quaternion((w,x,y,z))
        rmat = quat.to_matrix().to_3x3()
        ws = node["ws_scale"]
        smat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
        tail = head + vec @ smat @ rmat
        wsmat = smat @ rmat
    else:
        wsmat = Matrix()
    orient = node.get("orientation", Zero)
    xyz = node.get("rotation_order", 'XYZ')
    origin = node.get("origin")
    restdata[bname] = DBZRestData(head, tail, orient, xyz, origin, wsmat, dazhead)
    transforms[bname] = DBZTransform(wsmat, head)


class DBZRestData:
    def __init__(self, head, tail, orient, xyz, origin, wsmat, dazhead):
        self.head = Vector(head)
        self.tail = Vector(tail)
        if (self.tail - self.head).length < 0.1:
            self.tail = self.head + Vector((0,1,0))
        if len(orient) == 4:
            x,y,z,w = orient
            self.orient = Quaternion((-w,x,y,z)).to_euler()
        else:
            self.orient = Euler(orient)
        self.xyz = xyz
        self.origin = origin
        self.wsmat = wsmat
        self.dazhead = dazhead

    def checkBone(self, bname):
        if (self.head - self.tail).length < 1e-5:
            raise RuntimeError("Check bone %s %s %s" % (bname, self.head, self.tail))


class DBZTransform:
    def __init__(self, wsmat, head):
        self.wsrot = wsmat.to_euler()
        wsmat = wsmat.to_4x4()
        wsmat.col[3][0:3] = GS.scale*head
        self.wsmat = wsmat
        self.wsloc = head
        self.wsscale = (1,1,1)

#------------------------------------------------------------------
#
#------------------------------------------------------------------

def getFitFile(filepath):
    filename = os.path.splitext(filepath)[0]
    for ext in [".dbz", ".json"]:
        filepath = filename + ext
        if os.path.exists(filepath):
            return filepath
    msg = ("Mesh fitting set to DBZ (JSON).\n" +
           "Export \"%s.dbz\"            \n" % filename +
           "from Daz Studio to fit to dbz file.\n" +
           "See documentation for more information.")
    raise DazError(msg)


def fitToFile(filepath, nodes):
    from .geometry import Geometry, UnGeometry
    from .figure import FigureInstance
    from .bone import BoneInstance
    from .node import Instance

    def makeMeshFromDbz(base, geonode, verbose):
        geonode.edges = [e[0:2] for e in base.edges]
        geonode.faces = [f[0] for f in base.faces]
        geonode.polylines = base.polylines
        geonode.polyline_materials = base.polyline_materials
        if len(base.polylines) > 0 and len(base.faces) == 0:
            geonode.verts = base.verts
            msg = "Polylines %s" % node.name
        elif len(base.verts) > len(geo.verts) and len(base.faces) == 0:
            geonode.verts = base.verts[0:len(geo.verts)]
            msg = "Hair guides %s: %d => %d" % (node.name, len(base.verts), len(geo.verts))
        else:
            geonode.verts = base.verts
            msg = "Mismatch %s, %s: %d != %d. " % (node.name, geo.name, len(base.verts), len(geo.verts))
        if verbose:
            print(msg)
        geonode.properties = base.properties
        geonode.center = base.center
        geonode.highdef = highdef

    print("Fitting objects with dbz file...")
    filepath = getFitFile(filepath)
    dbz = loadDbzFile(filepath)
    subsurfaced = False

    unfitted = []
    for node,inst in nodes:
        if inst is None:
            print("fitToFile inst is None:\n  ", node)
            continue
        if isinstance(inst, FigureInstance):
            dbzrig = dbz.getEntry("rigs", inst.node.name, inst)
            if dbzrig:
                dbz.fitFigure(inst, dbzrig)
        elif isinstance(inst, BoneInstance):
            continue
        elif not inst.geometries:
            nodeid = inst.getNodeId()
            dbzobj = dbz.getEntry("rigs", nodeid, inst)
            if dbzobj:
                inst.restdata = dbzobj.restdata["NODE"]

        for geonode in inst.geometries:
            geo = geonode.data
            if not isinstance(geo, (Geometry, UnGeometry)):
                continue
            nname = dbz.tryGetName(node.name)
            if (nname is None and
                node.name[0].isdigit()):
                nname = dbz.tryGetName("a"+node.name)

            if nname:
                base = dbz.getEntry("objects", nname, inst)
                highdef = None
                hdshells = {}
                if dbz.hdobjects:
                    highdef = dbz.getEntry("hdobjects", nname, inst)
                    if highdef:
                        hdshells = dbz.hdshells.get(len(highdef.verts), {})
                        print("HD mesh", highdef)
                        print("HD shells", list(hdshells.values()))
                if base is None:
                    print("Cannot fit: %s" % inst)
                    unfitted.append(node)
                elif isinstance(geo, UnGeometry):
                    makeMeshFromDbz(base, geonode, False)
                elif subsurfaced:
                    if len(verts) < len(geo.verts):
                        msg = ("Mismatch %s, %s: %d < %d" % (node.name, geo.name, len(base.verts), len(geo.verts)))
                        print(msg)
                    else:
                        geonode.verts = verts[0:len(geo.verts)]
                        geonode.center = base.center
                        geonode.highdef = highdef
                        geonode.hdshells = hdshells
                else:
                    if len(base.verts) != len(geo.verts):
                        ok = False
                        for base1 in dbz.getAlternatives(nname):
                            if len(base1.verts) == len(geo.verts):
                                geonode.verts = base1.verts
                                geonode.center = base1.center
                                geonode.highdef = highdef
                                ok = True
                                break
                        if not ok:
                            makeMeshFromDbz(base, geonode, True)
                    else:
                        geonode.verts = base.verts
                        geonode.center = base.center
                        geonode.highdef = highdef
                        geonode.hdshells = hdshells
            elif len(geo.verts) == 0:
                if GS.verbosity >= 3:
                    print("Zero verts:", node.name)
                pass
            else:
                unfitted.append(node)

    if unfitted:
        print("The following nodes were not found")
        print("and must be fitted manually:")
        for node in unfitted:
            print('    "%s"' % node.name)
        print("The following nodes were fitted:")
        for oname in dbz.objects.keys():
            print('    "%s"' % oname)

#----------------------------------------------------------
#   Import DBZ as morph
#----------------------------------------------------------

class DAZ_OT_ImportDBZ(CollectionShower, DazOperator, DbzFile, MultiFile, PropDrivers, PosableMaker, IsMeshArmature):
    bl_idname = "daz.import_dbz"
    bl_label = "Import DBZ Morphs"
    bl_description = "Import DBZ or JSON file(s) (*.dbz, *.json) as morphs"
    bl_options = {'UNDO'}

    hasAdjusters = False
    useAdjusters = False

    min : FloatProperty(
        name = "Min",
        description = "Minimum value for DBZ morph",
        default = 0.0)

    max : FloatProperty(
        name = "Max",
        description = "Maximum value for DBZ morph",
        default = 1.0)

    def draw(self, context):
        self.layout.prop(self, "min")
        self.layout.prop(self, "max")
        PropDrivers.draw(self, context)
        PosableMaker.draw(self, context)

    def run(self, context):
        from .driver import setFloatProp, makePropDriver
        rig = getRigFromContext(context)
        if rig.type == 'ARMATURE':
            meshes = getMeshChildren(rig)
        else:
            meshes = getSelectedMeshes(context)
            rig = None
        paths = self.getMultiFiles(["dbz", "json"])
        props = []
        for path in paths:
            dbz = loadDbzFile(path)
            prop = dbz.name
            props.append(prop)
            for ob in meshes:
                self.buildMeshMorph(ob, rig, dbz)
            if self.usePropDrivers and rig:
                setFloatProp(rig, prop, 0.0, self.min, self.max, True)
                final = finalProp(prop)
                setFloatProp(rig.data, final, 0.0, self.min, self.max, False)
                makePropDriver(propRef(prop), rig.data, propRef(final), rig, "x")
                if GS.ercMethod != 'NONE':
                    self.buildRigMorph(context, rig, meshes, dbz)
        if self.usePropDrivers and rig:
            addToCategories(rig, props, None, self.category)
            rig.DazCustomMorphs = True
        elif GS.useShapeCats:
            for ob in meshes:
                addToCategories(ob, props, None, self.category)
                ob.DazMeshMorphs = True
        self.makePosable(context, rig)
        updateScrollbars(context)


    def buildRigMorph(self, context, rig, meshes, dbz):
        from .formula import Expression, ExprTarget
        from .load_morph import LoadMorph
        restdata = {}
        for name,dbzrigs in dbz.rigs.items():
            for dbzrig in dbzrigs.values():
                for key,data in dbzrig.restdata.items():
                    if key not in restdata.keys():
                        restdata[key] = data

        self.builtBones = {}
        lm = LoadMorph()
        lm.rig = rig
        lm.initAll()
        expr = Expression()
        expr.prop = ExprTarget(dbz.name, "value", -1)
        expr.prop.factor = 1
        try:
            lm.createTmp()
            if GS.ercMethod == 'TRANSLATION':
                self.makeErcFormulas(context, rig, meshes, lm, expr, restdata)
            elif GS.ercMethod in ('ARMATURE', 'ALL'):
                self.makeOffsetFormulas(rig, lm, expr, restdata)
                lm.buildSumDrivers()
        finally:
            lm.deleteTmp()


    def makeErcFormulas(self, context, rig, meshes, lm, expr, restdata):
        lm.ercBones = {}
        for pb in rig.pose.bones:
            if (self.builtBones.get(pb.name, False) or
                isDrvBone(pb.name) or
                pb.name not in restdata.keys()):
                continue
            self.builtBones[pb.name] = True
            rdata = restdata[pb.name]
            vec = Vector(rdata.head) - b2d(pb.bone.head_local)
            for idx,comp in enumerate(vec):
                expr.prop.factor = comp
                lm.makeErcFormula(pb.name, idx, expr)
        if lm.ercBones:
            lm.makeErcMorphs()
        lm.buildSumDrivers()
        if lm.ercMorphs and meshes:
            for mesh in meshes:
                lm.mesh = mesh
                lm.applyErcArmature(context, mesh)
                mesh.update_tag()


    def makeOffsetFormulas(self, rig, lm, expr, restdata):
        for pb in rig.pose.bones:
            if (self.builtBones.get(pb.name, False) or
                isDrvBone(pb.name) or
                pb.name not in restdata.keys()):
                continue
            self.builtBones[pb.name] = True
            rdata = restdata[pb.name]
            vec = Vector(rdata.head) - b2d(pb.bone.head_local)
            for idx,comp in enumerate(vec):
                expr.prop.factor = comp
                lm.makeOffsetFormula("HdOffset", pb.name, idx, expr)


    def setDriver(self, fcu, rig, prop, expr):
        from .driver import addDriverVar, removeModifiers
        fcu.driver.type = 'SCRIPTED'
        fcu.driver.expression = expr
        removeModifiers(fcu)
        addDriverVar(fcu, "a", propRef(prop), rig)


    def buildMeshMorph(self, ob, rig, dbz):
        from .modifier import getBasicShape
        basic,skeys,new = getBasicShape(ob)
        sname = dbz.name
        if sname in skeys.key_blocks.keys():
            skey = skeys.key_blocks[sname]
            ob.shape_key_remove(skey)
        if self.makeShape(ob, rig, sname, dbz.objects):
            return
        elif self.makeShape(ob, rig, sname, dbz.hdobjects):
            return
        else:
            print("No matching morph found")


    def makeShape(self, ob, rig, sname, objects):
        def setShape(ob, struct):
            for dbz in struct.values():
                verts = dbz.verts
                if GS.verbosity >= 3:
                    print("Try %s (%d verts)" % (dbz.name, len(verts)))
                if len(verts) == len(ob.data.vertices):
                    skey = ob.shape_key_add(name=sname)
                    for vn,co in enumerate(verts):
                        skey.data[vn].co = co
                    skey.slider_min = self.min
                    skey.slider_max = self.max
                    print("Morph created for %s" % sname)
                    if self.usePropDrivers and rig:
                        fcu = skey.driver_add("value")
                        self.setDriver(fcu, rig, sname, "a")
                    return True

        struct = objects.get(ob.data.name)
        if struct and setShape(ob, struct):
            return True
        else:
            for name in objects.keys():
                struct = objects[name]
                if setShape(ob, struct):
                    return True
        return False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportDBZ,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
