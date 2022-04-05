# Copyright (c) 2016-2021, Thomas Larsson
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


import bpy
import os
from mathutils import Vector, Quaternion, Matrix
from .error import *
from .utils import *
from .fileutils import MultiFile, DbzFile

#------------------------------------------------------------------
#   DBZ fitting
#------------------------------------------------------------------

class DBZInfo:
    def __init__(self):
        self.objects = {}
        self.hdobjects = {}
        self.rigs = {}


    def fitFigure(self, inst, takenfigs):
        from .figure import FigureInstance
        from .bone import BoneInstance
        name = inst.node.name
        if name in self.rigs.keys():
            if inst.id in takenfigs[name]:
                return
            elif inst.index < len(self.rigs[name]):
                restdata,transforms,center = self.rigs[name][inst.index]
                takenfigs[name].append(inst.id)
            else:
                print("Cannot fit %s" % name, inst.index, len(self.rigs[name]))
                return
        else:
            print("No fitting info for figure %s" % name)
            for key in self.rigs.keys():
                print("  ", key)
            return

        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                self.fitFigure(child, takenfigs)
            elif isinstance(child, BoneInstance):
                self.fitBone(child, restdata, transforms, takenfigs)


    def fitBone(self, inst, restdata, transforms, takenfigs):
        from .figure import FigureInstance
        from .bone import BoneInstance
        if inst.node.name not in restdata.keys():
            return
        inst.restdata = restdata[inst.node.name]
        rmat,wsloc,wsrot,wsscale = transforms[inst.node.name]

        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                self.fitFigure(child, takenfigs)
            if isinstance(child, BoneInstance):
                self.fitBone(child, restdata, transforms, takenfigs)


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
    def __init__(self, verts, uvs, edges, faces, polylines, matgroups, props, lod, center):
        self.verts = verts
        self.uvs = uvs
        self.edges = edges
        self.faces = faces
        self.polylines = polylines
        self.matgroups = matgroups
        self.properties = props
        self.lod = lod
        self.center = center

    def __repr__(self):
        return "<DBZ v:%d f:%d p:%d>" % (len(self.verts), len(self.faces), len(self.polylines))

#------------------------------------------------------------------
#   Load DBZ file
#------------------------------------------------------------------

def loadDbzFile(filepath):
    from .load_json import loadJson
    from .geometry import d2bList
    dbz = DBZInfo()
    struct = loadJson(filepath)
    if ("application" not in struct.keys() or
        struct["application"] not in ["export_basic_data", "export_to_blender", "export_highdef_to_blender"]):
        msg = ("The file\n" +
               filepath + "           \n" +
               "does not contain data exported from DAZ Studio")
        raise DazError(msg)

    for figure in struct["figures"]:
        if "num verts" in figure.keys() and figure["num verts"] == 0:
            continue

        if "center_point" in figure.keys():
            center = Vector(figure["center_point"])
        else:
            center = None

        name = figure["name"]
        if name not in dbz.objects.keys():
            dbz.objects[name] = []

        if "vertices" in figure.keys():
            verts = d2bList(figure["vertices"])
            edges = faces = polylines = uvs = matgroups = []
            props = {}
            for key,value in figure.items():
                if key == "edges":
                    edges = value
                elif key == "faces":
                    faces = value
                elif key == "polylines":
                    polylines = value
                elif key == "uvs":
                    uvs = value
                elif key == "material groups":
                    matgroups = value
                elif key == "node":
                    props = value["properties"]
            dbz.objects[name].append(DBZObject(verts, uvs, edges, faces, polylines, matgroups, props, 0, center))

        if GS.useHighDef and "hd vertices" in figure.keys():
            LS.useHDObjects = True
            if name not in dbz.hdobjects.keys():
                dbz.hdobjects[name] = []
            verts = []
            polylines = []
            faces = []
            lod = 0
            uvs = []
            matgroups = []
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
                elif key == "hd faces":
                    faces = value
                elif key == "material groups":
                    matgroups = value
            dbz.hdobjects[name].append(DBZObject(verts, uvs, [], faces, polylines, matgroups, props, lod, center))

        if "bones" not in figure.keys():
            continue

        restdata = {}
        transforms = {}
        if name not in dbz.rigs.keys():
            dbz.rigs[name] = []
        dbz.rigs[name].append((restdata, transforms, center))
        for bone in figure["bones"]:
            head = Vector(bone["center_point"])
            tail = Vector(bone["end_point"])
            vec = tail - head
            if "ws_transform" in bone.keys():
                ws = bone["ws_transform"]
                wsmat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                head = Vector(ws[9:12])
                tail = head + vec @ wsmat
            else:
                head = Vector(bone["ws_pos"])
                x,y,z,w = bone["ws_rot"]
                quat = Quaternion((w,x,y,z))
                rmat = quat.to_matrix().to_3x3()
                ws = bone["ws_scale"]
                smat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                tail = head + vec @ smat @ rmat
                wsmat = smat @ rmat
            if "orientation" in bone.keys():
                orient = bone["orientation"]
                xyz = bone["rotation_order"]
                origin = bone["origin"]
            else:
                orient = xyz = origin = None
            bname = bone["name"]
            rmat = wsmat.to_4x4()
            rmat.col[3][0:3] = LS.scale*head
            restdata[bname] = (head, tail, orient, xyz, origin, wsmat)
            transforms[bname] = (rmat, head, rmat.to_euler(), (1,1,1))

    return dbz

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
    from .geometry import Geometry
    from .figure import FigureInstance
    from .bone import BoneInstance
    from .node import Instance

    print("Fitting objects with dbz file...")
    filepath = getFitFile(filepath)
    dbz = loadDbzFile(filepath)
    subsurfaced = False

    taken = dict([(name,0) for name in dbz.objects.keys()])
    takenfigs = dict([(name,[]) for name in dbz.rigs.keys()])
    unfitted = []
    for node,inst in nodes:
        if inst is None:
            print("fitToFile inst is None:\n  ", node)
            continue
        if isinstance(inst, FigureInstance):
            if inst.node.name in dbz.rigs.keys():
                dbz.fitFigure(inst, takenfigs)

        for geonode in inst.geometries:
            geo = geonode.data
            if not isinstance(geo, Geometry):
                continue
            nname = dbz.tryGetName(node.name)
            if (nname is None and
                node.name[0].isdigit()):
                nname = dbz.tryGetName("a"+node.name)

            if nname:
                idx = taken[nname]
                if idx >= len(dbz.objects[nname]):
                    msg = ("Too many instances of object %s: %d" % (nname, idx))
                    ok = False
                else:
                    base = dbz.objects[nname][idx]
                    highdef = None
                    if dbz.hdobjects:
                        try:
                            highdef = dbz.hdobjects[nname][idx]
                            print("Highdef", nname, highdef.lod, len(highdef.verts))
                        except KeyError:
                            pass
                    taken[nname] += 1
                    ok = True
                if not ok:
                    print(msg)
                    unfitted.append(node)
                elif subsurfaced:
                    if len(verts) < len(geo.verts):
                        msg = ("Mismatch %s, %s: %d < %d" % (node.name, geo.name, len(base.verts), len(geo.verts)))
                        print(msg)
                    else:
                        geonode.verts = verts[0:len(geo.verts)]
                        geonode.center = base.center
                        geonode.highdef = highdef
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
                            geonode.edges = [e[0:2] for e in base.edges]
                            geonode.faces = [f[0] for f in base.faces]
                            geonode.polylines = base.polylines
                            if len(base.polylines) > 0:
                                geonode.verts = base.verts
                                msg = "Polylines %s" % node.name
                            elif len(base.verts) > len(geo.verts) and len(base.faces) == 0:
                                geonode.verts = base.verts[0:len(geo.verts)]
                                msg = "Corrected vertex number for %s: %d => %d" % (node.name, len(base.verts), len(geo.verts))
                            else:
                                geonode.verts = base.verts
                                msg = "Mismatch %s, %s: %d != %d. " % (node.name, geo.name, len(base.verts), len(geo.verts))
                            print(msg)
                            geonode.properties = base.properties
                            geonode.center = base.center
                            geonode.highdef = highdef
                    else:
                        geonode.verts = base.verts
                        geonode.center = base.center
                        geonode.highdef = highdef
            elif len(geo.verts) == 0:
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
#   Initialize
#----------------------------------------------------------

class DAZ_OT_ImportDBZ(DazOperator, DbzFile, MultiFile, IsMesh):
    bl_idname = "daz.import_dbz"
    bl_label = "Import DBZ Morphs"
    bl_description = "Import DBZ or JSON file(s) (*.dbz, *.json) as morphs"
    bl_options = {'UNDO'}

    def run(self, context):
        objects = getSelectedMeshes(context)
        if not objects:
            return
        LS.scale = objects[0].DazScale
        paths = self.getMultiFiles(["dbz", "json"])
        for path in paths:
            for ob in objects:
                self.buildDBZMorph(ob, path)


    def buildDBZMorph(self, ob, filepath):
        dbz = loadDbzFile(filepath)
        if not ob.data.shape_keys:
            basic = ob.shape_key_add(name="Basic")
        else:
            basic = ob.data.shape_keys.key_blocks[0]
        sname = os.path.basename(os.path.splitext(filepath)[0])
        if sname in ob.data.shape_keys.key_blocks.keys():
            skey = ob.data.shape_keys.key_blocks[sname]
            ob.shape_key_remove(skey)
        if self.makeShape(ob, sname, dbz.objects):
            return
        elif self.makeShape(ob, sname, dbz.hdobjects):
            return
        else:
            print("No matching morph found")


    def makeShape(self, ob, sname, objects):
        for name in objects.keys():
            verts = objects[name][0].verts
            print("Try %s (%d verts)" % (name, len(verts)))
            if len(verts) == len(ob.data.vertices):
                skey = ob.shape_key_add(name=sname)
                for vn,co in enumerate(verts):
                    skey.data[vn].co = co
                print("Morph %s created" % sname)
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
