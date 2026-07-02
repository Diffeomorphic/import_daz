# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Use hidden textures
#-------------------------------------------------------------

class HiddenTextureUser:
    useAllMeshes : BoolProperty(
        name = "All Meshes",
        description = "Affect textures from all meshes in scene, including hidden ones",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useAllMeshes")

    def getMeshes(self, context):
        if self.useAllMeshes:
            return [ob for ob in bpy.data.objects if ob.type == 'MESH']
        else:
            return getSelectedMeshes(context)

#-------------------------------------------------------------
#   Save local textures
#-------------------------------------------------------------

class LocalTextureUser:
    useSaveLoaded = False
    useSaveGenerated = False
    reuseExisting = True
    maxTexLevel = 2
    minTexLevel = 0
    level = 0
    subdir = "/textures/original"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and
                ob and ob.type == 'MESH' and
                dazRna(ob.data).DazTexLevel <= self.maxTexLevel and
                dazRna(ob.data).DazTexLevel >= self.minTexLevel)

    def draw(self, context):
        pass
        #self.layout.prop(self, "useSaveGenerated")
        #self.layout.prop(self, "reuseExisting")


    def getMeshes(self, context):
        return getSelectedMeshes(context)


    def setResSubdir(self, level):
        if level == 0:
            self.subdir = "/textures/original"
        else:
            self.subdir = "/textures/res%d" % level


    def getResLevel(self, path):
        lpath = path.lower()
        if lpath.startswith(self.basepath):
            lpath = lpath[len(self.basepath):]
            for string in ["/res", "/udim/res", "/lie/res"]:
                if lpath.startswith(string):
                    n = int(len(string))
                    return int(lpath[n])
            for string in ["/original", "/udim", "/lie"]:
                return 0
        return 0


    def initLocalImages(self):
        folder = normalizePath(os.path.dirname(bpy.data.filepath))
        self.texpath = "%s%s" % (folder, self.subdir)
        self.basepath = ("%s/textures" % folder).lower()
        print('Save textures to "%s"' % self.texpath)
        self.foundImages = []
        self.loadedImages = {}
        self.copiedImages = {}
        self.deletedImages = {}
        self.ignoredImages = set()
        self.origPaths = {}


    def printLocalImages(self):
        return
        print("Loaded images")
        for path,img in self.loadedImages.items():
            if img:
                print("  ", path, img.has_data)
        print("Copied images")
        for path,img in self.copiedImages.items():
            if img:
                print("  ", path, img.has_data,)
        print("Deleted images")
        for path,img in self.deletedImages.items():
            if img:
                print("  ", path, img.has_data)


    def getLocalPath(self, path):
        def getRelPath(path, lpath):
            if lpath.startswith(self.basepath):
                for string in ["/textures/original/", "/textures/udim/", "/textures/lie/"]:
                    words = lpath.rsplit(string, 1)
                    if len(words) == 2:
                        n = len(words[1])
                        return path[-n:]
                words = lpath.rsplit("/textures/res", 1)
                if len(words) == 2:
                    n = len(words[1])
                    return path[-n+2:]
            words = lpath.rsplit("/runtime/textures/", 1)
            if len(words) == 2:
                n = len(words[1])
                return path[-n:]
            print("NO REL PATH", lpath, self.basepath)

        path = normalizePath(path)
        words = path.split(".jpg")
        if len(words) > 2 or path.endswith("<UDIM>"):
            msg = ("Bad local path: %s" % path)
            print(msg)
            raise DazError(msg)
        relpath = getRelPath(path, path.lower())
        if relpath:
            return "%s/%s" % (self.texpath, relpath)
        else:
            return path


    def getOrigPath(self, img):
        path = img.get("DazFilePath")
        if path:
            return path
        path = self.getLocalPath(img.filepath)
        path = "/runtime/textures/%s" % path[nstrip:]
        return GS.getAbsPath(path)


    def saveLocalImages(self):
        if self.useSaveGenerated:
            if self.useSaveLoaded:
                images = list(self.loadedImages.items()) + list(self.copiedImages.items())
            else:
                images = self.copiedImages.items()
            for path,img in images:
                if path in self.ignoredImages:
                    continue
                if self.reuseExisting and os.path.exists(path):
                    continue
                locpath = self.getLocalPath(path)
                if locpath:
                    img.filepath_raw = locpath
                    if not img.has_data:
                        img.update()
                    if img.has_data:
                        img.save()
                    else:
                        print("Failed to update image:", img.filepath)
        else:
            for path,img in self.copiedImages.items():
                if path in self.ignoredImages:
                    print("IGNO", path)
                    continue
                try:
                    img.pack()
                except RuntimeError as err:
                    print(err)
                    #print("FAIL", img.filepath, img.has_data)


    def deleteCopiedImages(self):
        for img in self.copiedImages.values():
            path = img.filepath_raw
            if (path.startswith(self.texpath) and
                os.path.exists(path)):
                if GS.verbosity >= 3:
                    print("Delete %s" % path)
                os.remove(path)


    def checkImage(self, path, strict=False):
        if not self.imageExists(path):
            msg = "Missing texture file:\n%s" % path
            print(msg)
            if strict:
                raise DazError(msg)


    def imageExists(self, path):
        return (self.loadedImages.get(path) or self.copiedImages.get(path))


    def copyImage(self, src, trg):
        src = normalizePath(src)
        trg = normalizePath(trg)
        img = self.loadImage(src)
        if self.reuseExisting and os.path.exists(trg):
            mod,img = self.modifyImage(img, True)
            img.filepath_raw = trg
            img.update()
        else:
            mod,img = self.modifyImage(img, False)
            if not mod:
                self.ignoredImages.add(trg)
                return False, img
            img.filepath_raw = trg
            img.update()
        img.name = os.path.basename(trg)
        if src in self.loadedImages.keys():
            del self.loadedImages[src]
        if src in self.copiedImages.keys():
            del self.copiedImages[src]
        if GS.verbosity >= 3:
            print("Copied %s %s" % (tuple(img.size), trg))
        self.copiedImages[trg] = img
        self.deletedImages[src] = img
        if "Public" in trg:
            msg = "Expected local image: %s" % trg
            print(msg)
            raise DazError(msg)
        return True, img


    def modifyImage(self, img, force):
        return True, img


    def loadImage(self, path):
        path = normalizePath(path)
        img = self.loadedImages.get(path)
        if img is None:
            img = self.copiedImages.get(path)
        if path in self.deletedImages.keys():
            print("Image was deleted: %s" % path)
            path1 = self.origPaths.get(path)
            if path1 is None and img:
                path1 = self.getOrigPath(img)
            if path1:
                img = None
                self.origPaths[path] = path1
                path = path1
        if img is None:
            if os.path.exists(path):
                print("Reload image: %s" % path)
                img = bpy.data.images.load(path)
                self.loadedImages[path] = img
            else:
                msg = ("Image not found: %s" % path)
                print(msg)
                raise DazError(msg)
        if not img.has_data:
            self.printLocalImages()
        img.update()
        return img


    def changeImage(self, src, trg, img, img2=None, strict=True):
        #if not self.checkImage(src):
        #    return None
        if src != trg and not self.imageExists(trg):
            mod,img = self.copyImage(src, trg)
            if not mod:
                return img
        if img is None:
            img = img2.copy()
            img.update()
            img.colorspace_settings.name = img2.colorspace_settings.name
            self.copiedImages[trg] = img
        img.filepath_raw = trg
        return img


    def saveImage(self, img, isnew):
        if img:
            if not img.has_data:
                img.update()
            path = bpy.path.abspath(img.filepath)
            path = bpy.path.reduce_dirs([path])[0]
            path = normalizePath(path)
            self.foundImages.append((path, img))
            if isnew:
                self.copiedImages[path] = img
            else:
                self.loadedImages[path] = img


    def isIrrelevant(self, path):
        return False


    def saveLocalTextures(self, context):
        meshes = self.getMeshes(context)
        self.getAllImages(meshes)
        for src,img in self.foundImages:
            if self.isIrrelevant(src):
                continue
            trg = self.getLocalPath(src)
            self.changeImage(src, trg, img)


    def getAllImages(self, meshes):
        def getNodesInTree(tree):
            for node in tree.nodes.values():
                if node.type == 'TEX_IMAGE':
                    self.saveImage(node.image, False)
                elif node.type == 'GROUP':
                    getNodesInTree(node.node_tree)

        def getTextureSlots(mat):
            for mtex in mat.texture_slots:
                if mtex:
                    tex = mtex.texture
                    if hasattr(tex, "image") and tex.image:
                        self.saveImage(tex.image, False)

        self.foundImages = []
        for ob in meshes:
            for mat in ob.data.materials:
                if mat:
                    if not BLENDER5 or mat.use_nodes:
                        getNodesInTree(mat.node_tree)
            for psys in ob.particle_systems:
                getTextureSlots(psys.settings)

# ---------------------------------------------------------------------
#   Save local textures
# ---------------------------------------------------------------------

class DAZ_OT_SaveLocalTextures(HiddenTextureUser, LocalTextureUser, DazPropsOperator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Local Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"
    bl_options = {'UNDO'}

    maxTexLevel = 0
    useSaveLoaded = True
    subdir = "/textures/original"

    reuseExisting : BoolProperty(
        name = "Reuse Existing Images",
        description = "Reuse existing local textures instead of regenerating them",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "reuseExisting")
        HiddenTextureUser.draw(self, context)

    def run(self, context):
        meshes = self.getMeshes(context)
        self.useSaveGenerated = True
        self.initLocalImages()
        self.saveLocalTextures(context)
        self.printLocalImages()
        self.saveLocalImages()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 1


    def isIrrelevant(self, path):
        if (path.lower().startswith(self.basepath) and
            self.reuseExisting and
            os.path.exists(path)):
            print("Already local: %s" % path)
            return True
        return False

# ---------------------------------------------------------------------
#   Restore textures
# ---------------------------------------------------------------------

class DAZ_OT_ReloadTextures(HiddenTextureUser, LocalTextureUser, DazPropsOperator):
    bl_idname = "daz.reload_textures"
    bl_label = "Reload Textures"
    bl_description = "Reload textures from disk, optionally restore original textures"
    bl_options = {'UNDO'}

    useOriginal : BoolProperty(
        name = "Restore Original Textures",
        description = "Restore original textures instead of reloading current textures",
        default = False)

    useUnpack : BoolProperty(
        name = "Unpack Images",
        description = "Unpack packed images before reloading",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useOriginal")
        if not self.useOriginal:
            self.layout.prop(self, "useUnpack")
        HiddenTextureUser.draw(self, context)

    def run(self, context):
        ob = context.object
        meshes = self.getMeshes(context)
        if self.useOriginal:
            self.restoreOriginal(meshes)
        else:
            self.initLocalImages()
            self.getAllImages(meshes)
            for _,img in self.foundImages:
                filepath = bpy.path.abspath(img.filepath)
                if filepath and os.path.exists(filepath):
                    if img.packed_file:
                        if not self.useUnpack:
                            continue
                        img.unpack()
                    img.filepath = filepath
                    img.update()


    def restoreOriginal(self, meshes):
        self.initLocalImages()
        nstrip = len(self.texpath)
        self.getAllImages(meshes)
        for _,img in self.foundImages:
            filepath = self.getOrigPath(img)
            if filepath and os.path.exists(filepath):
                if img.packed_file:
                    img.unpack()
                img.filepath = filepath
                img.reload()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 0

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class DAZ_OT_SetResolution(DazPropsOperator, HiddenTextureUser, LocalTextureUser):
    bl_idname = "daz.set_resolution"
    bl_label = "Set Resolution"
    bl_description = "Replace all textures of selected meshes with resized versions"
    bl_options = {'UNDO'}

    resizeAll = True

    level : IntProperty(
        name = "Resolution Level",
        description = "Resize images to this resolution level",
        min = 0, max = 8,
        default = 2)

    def draw(self, context):
        LocalTextureUser.draw(self, context)
        HiddenTextureUser.draw(self, context)
        self.layout.prop(self, "level")


    def run(self, context):
        self.setResSubdir(self.level)
        meshes = self.getMeshes(context)
        self.initLocalImages()
        self.saveLocalTextures(context)
        self.printLocalImages()
        self.saveLocalImages()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 2


    def modifyImage(self, img, force):
        level = self.getResLevel(img.filepath)
        if level < self.level:
            scale = int(2**(self.level-level))
            x,y = img.size
            img.scale(int(x/scale), int(y/scale))
            return True, img
        elif force:
            scale = int(2**(level-self.level))
            x,y = img.size
            img.scale(int(x*scale), int(y*scale))
            return True, img
        else:
            return False, img

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def getProperPath(path):
    if path[0:2] == "//":
        return os.path.join(os.path.dirname(bpy.data.filepath), path[2:])
    return path


def normPath(path):
    path = bpy.path.abspath(path)
    path = bpy.path.reduce_dirs([path])[0]
    return normalizePath(path)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SaveLocalTextures,
    DAZ_OT_ReloadTextures,
    DAZ_OT_SetResolution,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

