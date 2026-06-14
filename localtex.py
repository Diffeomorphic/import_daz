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
    maxTexLevel = 2
    minTexLevel = 0

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and
                ob and ob.type == 'MESH' and
                dazRna(ob.data).DazTexLevel <= self.maxTexLevel and
                dazRna(ob.data).DazTexLevel >= self.minTexLevel)

    useSaveGenerated : BoolProperty(
        name = "Save Generated Images",
        description = "Save generated images to disk.\nPack them in blend file if this option is disabled",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useSaveGenerated")


    def getMeshes(self, context):
        return getSelectedMeshes(context)


    def initLocalImages(self):
        folder = normalizePath(os.path.dirname(bpy.data.filepath))
        self.texpath = "%s%s" % (folder, self.subdir)
        self.basepath = "%s/textures" % folder
        print('Save textures to "%s"' % self.texpath)
        self.loadedImages = {}
        self.copiedImages = {}
        self.deletedImages = {}


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
            if lpath.startswith(self.basepath.lower()):
                for string in ["/textures/original/", "/textures/udim/", "/textures/lie/"]:
                    words = lpath.rsplit(string, 1)
                    if len(words) == 2:
                        return path[-len(words[1]):]
                words = lpath.rsplit("/textures/res", 1)
                if len(words) == 2:
                    return path[-len(words[1]):]
            words = lpath.rsplit("/runtime/textures/", 1)
            if len(words) == 2:
                return path[-len(words[1]):]
            print("NO REL PATH", lpath, self.basepath.lower())

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


    def saveLocalImages(self):
        if self.useSaveGenerated:
            if self.useSaveLoaded:
                images = list(self.loadedImages.items()) + list(self.copiedImages.items())
            else:
                images = self.copiedImages.items()
            for path,img in images:
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
                print("Delete", path)
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
        if src in self.loadedImages.keys():
            del self.loadedImages[src]
        if src in self.copiedImages.keys():
            del self.copiedImages[src]
        self.deletedImages[src] = img
        img.name = os.path.basename(trg)
        img.filepath_raw = trg
        img.update()
        trg,img = self.modifyImage(trg, img)
        print("Copied %s %s" % (tuple(img.size), trg))
        self.copiedImages[trg] = img
        if "Public" in trg:
            msg = "Expected local image: %s" % trg
            print(msg)
            raise DazError(msg)
        return img


    def modifyImage(self, path, img):
        return path, img


    def loadImage(self, path):
        path = normalizePath(path)
        img = self.loadedImages.get(path)
        if img is None:
            img = self.copiedImages.get(path)
        if path in self.deletedImages.keys():
            print("Image was deleted: %s" % path)
        if False and img is None:
            imgname = os.path.splitext(os.path.basename(path))[0]
            img = bpy.data.images.get(imgname)
            self.loadedImages[path] = img
        if img is None:
            img = bpy.data.images.load(path)
            print("RELOAD", path)
            print(img)
            if img is None:
                msg = ("Image not found: %s" % path)
                print(msg)
                raise DazError(msg)
            self.loadedImages[path] = img
        if not img.has_data:
            self.printLocalImages()
        img.update()
        return img


    def changeImage(self, src, trg, img, img2=None, strict=True):
        #if not self.checkImage(src):
        #    return None
        if src != trg and not self.imageExists(trg):
            img = self.copyImage(src, trg)
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
            self.images.append((path, img))
            if isnew:
                self.copiedImages[path] = img
            else:
                self.loadedImages[path] = img


    def isIrrelevant(self, path):
        return False


    def saveLocalTextures(self, context):
        meshes = self.getMeshes(context)
        self.getAllImages(meshes)
        for src,img in self.images:
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

        self.images = []
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

    maxTexLevel = 0
    useSaveLoaded = True
    subdir = "/textures/original"

    def draw(self, context):
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
        if path.startswith(self.basepath):
            print("Already local: %s" % path)
            return True
        return False

# ---------------------------------------------------------------------
#   Restore textures
# ---------------------------------------------------------------------

class DAZ_OT_RestoreOriginalTextures(HiddenTextureUser, LocalTextureUser, DazPropsOperator):
    bl_idname = "daz.restore_original_textures"
    bl_label = "Restore Original Textures"
    bl_description = "Restore the original textures"

    minTexLevel = 1
    subdir = ""

    def draw(self, context):
        HiddenTextureUser.draw(self, context)

    def run(self, context):
        self.initLocalImages()
        meshes = self.getMeshes(context)
        self.getAllImages(meshes)
        for _,img in self.images:
            filepath = img.get("DazFilePath")
            if filepath and os.path.exists(filepath):
                img.filepath = filepath
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 0

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class DAZ_OT_ResizeTextures(DazPropsOperator, HiddenTextureUser, LocalTextureUser):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = "Replace all textures of selected meshes with resized versions"
    bl_options = {'UNDO'}

    resizeAll = True
    maxTexLevel = 1

    steps : IntProperty(
        name = "Steps",
        description = "Resize original images with this number of steps",
        min = 1, max = 8,
        default = 2)

    def draw(self, context):
        LocalTextureUser.draw(self, context)
        HiddenTextureUser.draw(self, context)
        self.layout.prop(self, "steps")


    def run(self, context):
        self.subdir = "/textures/res%d" % self.steps
        meshes = self.getMeshes(context)
        self.initLocalImages()
        self.saveLocalTextures(context)
        self.printLocalImages()
        self.saveLocalImages()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 2


    def modifyImage(self, path, img):
        scale = int(2**self.steps)
        x,y = img.size
        img.scale(int(x/scale), int(y/scale))
        return path, img

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
    DAZ_OT_RestoreOriginalTextures,
    DAZ_OT_ResizeTextures,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

