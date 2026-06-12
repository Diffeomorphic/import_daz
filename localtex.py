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
    useHiddenMeshes : BoolProperty(
        name = "Also Hidden Meshes",
        description = "Also save textures from hidden meshes",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useHiddenMeshes")

    def getMeshes(self, context):
        if self.useHiddenMeshes:
            return [ob for ob in bpy.data.objects if ob.type == 'MESH']
        else:
            return getVisibleMeshes(context)

#-------------------------------------------------------------
#   Save local textures
#-------------------------------------------------------------

class LocalTextureUser:
    useLocals = True
    useSaveLoaded = False

    @classmethod
    def poll(self, context):
        return (bpy.data.filepath and context.object and context.object.type == 'MESH')

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
        self.ensureExists(self.texpath)
        self.loadedImages = {}
        self.copiedImages = {}
        self.deletedImages = {}


    def printLocalImages(self):
        print("Loaded images")
        for path,img in self.loadedImages.items():
            if img:
                print("  ", path, img.has_data)
        print("Copied images")
        for path,img in self.copiedImages.items():
            if img:
                print("  ", path, img.has_data)
        print("Removed images")
        for path,img in self.deletedImages.items():
            if img:
                print("  ", path, img.has_data)


    def getLocalPath(self, path):
        def getRelPath(lpath):
            words = path.rsplit("/runtime/textures/res", 1)
            if len(words) == 2:
                return words[1][2:]
            words = path.rsplit("/runtime/textures/", 1)
            if len(words) == 2:
                return words[1]
            words = path.rsplit("/textures/original/", 1)
            if len(words) == 2:
                return words[1]
            words = path.rsplit("/textures/res", 1)
            if len(words) == 2:
                return words[1][2:]

        path = normalizePath(path)
        if path.endswith("<UDIM>"):
            print("UDD", path)
            halt
        relpath = getRelPath(path.lower())
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
                except RuntimeError:
                    print("FAIL", img.filepath, img.has_data)


    def checkImage(self, path, strict=False):
        if not self.imageExists(path):
            msg = "Missing texture file:\n%s" % path
            print(msg)
            if strict:
                raise DazError(msg)


    def imageExists(self, path):
        return (self.loadedImages.get(path) or self.copiedImages.get(path))


    def ensureExists(self, folder):
        if not self.useLocals:
            if not os.path.exists(folder):
                os.makedirs(folder)


    def copyImage(self, src, trg):
        src = normalizePath(src)
        trg = normalizePath(trg)
        print("Copy %s\n=> %s" % (src, trg))
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
        self.copiedImages[trg] = img
        if "Public" in trg:
            halt
        return img


    def modifyImage(self, path, img):
        return path, img


    def loadImage(self, path):
        path = normalizePath(path)
        img = self.loadedImages.get(path)
        if img is None:
            img = self.copiedImages.get(path)
        if img is None:
            img = self.deletedImages.get(path)
            if img:
                print("DELETED", path)
                halt
        if img is None:
            imgname = os.path.splitext(os.path.basename(path))[0]
            img = bpy.data.images.get(imgname)
            self.loadedImages[path] = img
        if img is None:
            print("BBII", bpy.data.images.keys())
            print("UUU", path)
            halt
            img = bpy.data.images.load(path)
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


    def saveLocalTextures(self, context):
        self.images = []
        for ob in self.getMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    if not BLENDER5 or mat.use_nodes:
                        self.saveNodesInTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.saveTextureSlots(psys.settings)
            dazRna(ob).DazLocalTextures = True

        for src,img in self.images:
            if src.startswith(self.basepath):
                print("Already local: %s" % src)
                continue
            file = bpy.path.basename(src)
            srclower = normalizePath(src).lower()
            if ("/textures/" in srclower and
                "/textures/original/" not in srclower):
                subpath = os.path.dirname(srclower.rsplit("/textures/",1)[1])
                folder = "%s/%s" % (self.texpath, subpath)
                self.ensureExists(folder)
                trg = "%s/%s" % (folder, file)
            else:
                trg = "%s/%s" % (self.texpath, file)
            self.changeImage(src, trg, img)


    def saveNodesInTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                self.saveImage(node.image, False)
            elif node.type == 'GROUP':
                self.saveNodesInTree(node.node_tree)


    def saveTextureSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex:
                tex = mtex.texture
                if hasattr(tex, "image") and tex.image:
                    self.saveImage(tex.image, False)


class DAZ_OT_SaveLocalTextures(HiddenTextureUser, LocalTextureUser, DazPropsOperator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Local Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"

    useSaveLoaded = True
    subdir = "/textures/original"

    def draw(self, context):
        HiddenTextureUser.draw(self, context)

    def run(self, context):
        self.useSaveGenerated = True
        self.initLocalImages()
        self.saveLocalTextures(context)
        self.printLocalImages()
        self.saveLocalImages()

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class DAZ_OT_ResizeTextures(DazPropsOperator, HiddenTextureUser, LocalTextureUser):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = "Replace all textures of selected meshes with resized versions"
    bl_options = {'UNDO'}

    resizeAll = True

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
        self.initLocalImages()
        self.saveLocalTextures(context)
        self.printLocalImages()
        self.saveLocalImages()


    def modifyImage(self, path, img):
        scale = int(2**self.steps)
        x,y = img.size
        img.scale(int(x/scale), int(y/scale))
        print("Scale %s: %s => %s" % (path, (x,y), tuple(img.size)))
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
    DAZ_OT_ResizeTextures,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

