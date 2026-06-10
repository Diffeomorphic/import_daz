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

    @classmethod
    def poll(self, context):
        return (bpy.data.filepath and context.object and context.object.type == 'MESH')

    if useLocals:
        useSaveGenerated : BoolProperty(
            name = "Save Generated Images",
            description = "Save generated images to disk.\nPack them in blend file if this option is disabled",
            default = False)

        def draw(self, context):
            self.layout.prop(self, "useSaveGenerated")
    else:
        useSaveLocalTextures : BoolProperty(
            name = "Save Local Textures",
            description = "Save local textures if not already done",
            default = True)

        def draw(self, context):
            self.layout.prop(self, "useSaveLocalTextures")


    def getMeshes(self, context):
        return getSelectedMeshes(context)


    def checkLocalTextures(self, context, ob):
        self.initLocalImages()
        if self.useLocals:
            self.saveLocalTextures(context)
        elif not dazRna(ob).DazLocalTextures:
            if self.useSaveLocalTextures:
                self.saveLocalTextures(context)
            else:
                raise DazError("Save local textures first")


    def saveLocalTextures(self, context):
        folder = normalizePath(os.path.dirname(bpy.data.filepath))
        if GS.useLowerResFolders:
            self.subdir = "/textures/original"
        else:
            self.subdir = "/textures"
        self.texpath = "%s%s" % (folder, self.subdir)
        self.basepath = "%s/textures" % folder
        print('Save textures to "%s"' % self.texpath)
        self.ensureExists(self.texpath)

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


    def initLocalImages(self):
        self.loadedImages = {}
        self.copiedImages = {}
        self.removedImages = set()


    def printLocalImages(self):
        print("Loaded images")
        for path,img in self.loadedImages.items():
            print("  ", path)
            print("  ", img)
        print("Copied images")
        for path,img in self.copiedImages.items():
            print("  ", path)
            print("  ", img)
        print("Removed images")
        for path in self.removedImages:
            print("  ", path)


    def saveLocalImages(self):
        if not self.useLocals:
            return
        elif self.useSaveGenerated:
            for path,img in self.copiedImages.items():
                if path not in self.removedImages:
                    words = path.lower().rsplit("/textures/", 1)
                    if len(words) == 2:
                        locpath = "%s/%s" % (self.texpath, words[1])
                        print("SAVE", locpath)
                        print("GLOB", path)
                        img.filepath_raw = locpath
                        img.save()
        else:
            for path,img in self.copiedImages.items():
                if path not in self.removedImages:
                    print("PACK", img)
                    #img.pack()


    def checkImage(self, path, strict=False):
        if not self.imageExists(path):
            msg = "Missing texture file:\n%s" % path
            print(msg)
            if strict:
                raise DazError(msg)


    def imageExists(self, path):
        if self.useLocals:
            return (self.loadedImages.get(path) or self.copiedImages.get(path))
        else:
            return os.path.exists(path)


    def ensureExists(self, folder):
        if not self.useLocals:
            if not os.path.exists(folder):
                os.makedirs(folder)


    def copyImage(self, src, trg):
        print("Copy %s\n=> %s" % (src, trg))
        if self.useLocals:
            img = self.loadImage(src)
            img2 = img.copy()
            img2.name = os.path.basename(trg)
            img2.filepath = trg
            #self.loadedImages[trg] = img2
            self.copiedImages[trg] = img2
            self.removedImages.add(src)
        else:
            from shutil import copyfile
            try:
                copyfile(src, trg)
                return True
            except:
                print("Copying failed")
                return False


    def loadImage(self, path):
        img = self.loadedImages.get(path)
        if img is None:
            img = self.copiedImages.get(path)
        if img is None:
            img = bpy.data.images.load(path)
            self.loadedImages[path] = img
            print("LOAD", path)
        return img


    def changeImage(self, src, trg, img, strict=True):
        if not self.checkImage(src):
            return None
        if src != trg and not self.imageExists(trg):
            if not self.copyImage(src, trg):
                return None
        if img is None:
            if trg in bpy.data.images.keys():
                img = bpy.data.images[trg]
            else:
                img = self.loadImage(trg)
            self.copiedImages[trg] = img
            self.removedImages.add(src)
        img.filepath = bpy.path.relpath(trg)
        return img


    def saveImage(self, img, isnew):
        if img:
            path = bpy.path.abspath(img.filepath)
            path = bpy.path.reduce_dirs([path])[0]
            path = normalizePath(path)
            self.images.append((path, img))
            if isnew:
                self.copiedImages[path] = img
            else:
                self.loadedImages[path] = img


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

    def run(self, context):
        self.saveLocalTextures(context)

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class ChangeResolution:
    steps : IntProperty(
        name = "Steps",
        description = "Resize original images with this number of steps",
        min = 0, max = 8,
        default = 2)

    resizeAll = True

    def draw(self, context):
        self.layout.prop(self, "steps")

    def initResolution(self):
        self.filenames = []
        self.typedImages = {}

    def getFileNames(self, paths):
        for path in paths:
            fname = bpy.path.basename(self.getBasePath(path))
            self.filenames.append(fname)


    def getAllTextures(self, context, resolveUDIM):
        paths = set()
        for ob in self.getMeshes(context):
            self.checkLocalTextures(context, ob)
            for mat in ob.data.materials:
                if mat:
                    self.getTreeTextures(mat.node_tree, paths, resolveUDIM)
            for psys in ob.particle_systems:
                self.getSlotTextures(psys.settings, paths)
        return paths


    def getSlotTextures(self, mat, paths):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                paths.add(normPath(mtex.texture.image.filepath))


    def getTreeTextures(self, tree, paths, resolveUDIM):
        if tree is None:
            return
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                if img.source == 'TILED':
                    folder,basename,ext = self.getTiledPath(img.filepath)
                    for file1 in os.listdir(folder):
                        fname1,ext1 = os.path.splitext(file1)
                        if fname1[:-4] == basename and ext1 == ext:
                            if bpy.app.version >= (3,1,0) and resolveUDIM:
                                path = os.path.join(folder, "%s%s%s" % (fname1[:-4], "<UDIM>", ext1))
                            else:
                                path = os.path.join(folder, "%s%s" % (fname1, ext1))
                            paths.add(normPath(path))
                else:
                    paths.add(normPath(img.filepath))
            elif node.type == 'GROUP':
                self.getTreeTextures(node.node_tree, paths, resolveUDIM)


    def getTiledPath(self, filepath):
        path = normPath(filepath)
        folder = os.path.dirname(path)
        fname,ext = os.path.splitext(bpy.path.basename(path))
        if fname[-6:] == "<UDIM>":
            return folder, fname[:-6], ext
        else:
            return folder, fname[:-4], ext


    def replaceTextures(self, context):
        for ob in self.getMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    self.resizeTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.resizeSlots(psys.settings)


    def resizeSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                img = self.replaceImage(mtex.texture.image)
                mtex.texture.image = img


    def resizeTree(self, tree):
        if tree is None:
            return
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                img = self.replaceImage(node.image)
                node.image = img
                if img:
                    node.name = img.name
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)


    def getBasePath(self, path):
        path = self.getBasePathNames(normalizePath(path))
        if GS.useLowerResFolders:
            words = path.split("/textures/res", 1)
            if len(words) == 2:
                path = "%s/textures/original%s" % (words[0], words[1][1:])
        return path


    def getBasePathNames(self, path):
        fname,ext = os.path.splitext(path)
        if fname[-5:] == "-res0":
            return "%s%s" % (fname[:-5], ext)
        elif fname[-5:-1] == "-res" and fname[-1].isdigit():
            return "%s%s" % (fname[:-5], ext)
        elif (fname[-10:-6] == "-res" and
              fname[-6].isdigit() and
              fname[-5] == "_" and
              fname[-4:].isdigit()):
            return "%s%s%s" % (fname[:-10], fname[-5:], ext)
        elif (fname[-12:-8] == "-res" and
              fname[-8].isdigit() and
              fname[-7:] == "_<UDIM>"):
            return "%s%s%s" % (fname[:-12], fname[-7:], ext)
        else:
            return path


    def replaceImage(self, img):
        if img is None:
            return None
        colorSpace = img.colorspace_settings.name
        if colorSpace not in self.typedImages.keys():
            self.typedImages[colorSpace] = {}
        images = self.typedImages[colorSpace]

        path = self.getBasePath(img.filepath)
        filename = bpy.path.basename(path)
        if filename not in self.filenames:
            return img

        newname,newpath = self.getNewPath(path)
        if img.source == 'TILED':
            if newname[-6:] == "<UDIM>":
                newname = newname[:-7]
            else:
                newname = newname[:-5]
        if newpath == img.filepath:
            return img
        elif newpath in images.keys():
            return images[newpath][1]
        oldimg = bpy.data.images.get(newname)
        if oldimg and oldimg.filepath == newpath:
            return oldimg
        try:
            newimg = self.loadNewImage(img, newpath)
        except RuntimeError:
            newimg = None
        if newimg:
            newimg.name = newname
            newimg.name = newname
            newimg.colorspace_settings.name = colorSpace
            newimg.source = img.source
            images[newpath] = (img, newimg)
            return newimg
        else:
            print('"%s" does not exist' % newpath)
            return img


    def loadNewImage(self, img, newpath):
        print('Replace "%s" with "%s"' % (img.filepath, newpath))
        if img.source == 'TILED':
            folder,basename,ext = self.getTiledPath(newpath)
            newimg = None
            print("Tiles:")
            for file1 in os.listdir(folder):
                fname1,ext1 = os.path.splitext(file1)
                if fname1[:-4] == basename and ext1 == ext:
                    path = os.path.join(folder, file1)
                    img = self.loadImage(path)
                    udim = int(fname1[-4:])
                    if newimg is None:
                        newimg = img
                        newimg.source = 'TILED'
                        tile = img.tiles[0]
                        tile.number = udim
                        if bpy.app.version >= (3,1,0):
                            path2,ext2 = os.path.splitext(newimg.filepath)
                            newimg.filepath = "%s%s%s" % (path2[:-4],"<UDIM>",ext2)
                            newimg.name=basename[:-1]
                    else:
                        newimg.tiles.new(tile_number = udim)
                    print('  "%s"' % file1)
            return newimg
        else:
            print("XXX", newpath)
            newimg = self.loadImage(newpath)
            print("YYY", newimg)
            return newimg


    def getNewPathFolders(self, path):
        if self.steps == 0 or not self.useLocals:
            return path
        words = path.split("/textures/original/", 1)
        if len(words) != 2:
            words = path.split("/textures/", 1)
        if len(words) == 2:
            newpath = "%s/textures/res%d/%s" % (words[0], self.steps, words[1])
            folder = getProperPath(os.path.dirname(newpath))
            self.ensureExists(folder)
            return newpath
        else:
            msg = 'Illegal path: %s' % path
            print(msg)
            #raise DazError(msg)
            return path


    def getNewPath(self, path):
        if GS.useLowerResFolders:
            path = self.getNewPathFolders(path)
        base,ext = os.path.splitext(path)
        if self.steps == 0:
            newbase = base
        elif len(base) > 5 and base[-5] == "_" and base[-4:].isdigit():
            newbase = ("%s-res%d%s" % (base[:-5], self.steps, base[-5:]))
        elif len(base) > 7 and base[-7:] == "_<UDIM>":
            newbase = ("%s-res%d%s" % (base[:-7], self.steps, base[-7:]))
        else:
            newbase = ("%s-res%d" % (base, self.steps))
        newname = bpy.path.basename(newbase)
        newpath = "%s%s" % (newbase, ext)
        return newname, newpath


def normPath(path):
    path = bpy.path.abspath(path)
    path = bpy.path.reduce_dirs([path])[0]
    return path


class DAZ_OT_ChangeResolution(DazPropsOperator, HiddenTextureUser, LocalTextureUser, ChangeResolution):
    bl_idname = "daz.change_resolution"
    bl_label = "Change Resolution"
    bl_description = (
        "Change all textures of selected meshes with resized versions.\n" +
        "The resized textures must already exist.")
    bl_options = {'UNDO'}

    useSaveLocalTextures = False

    def draw(self, context):
        HiddenTextureUser.draw(self, context)
        ChangeResolution.draw(self, context)

    def run(self, context):
        self.initResolution()
        self.overwrite = False
        paths = self.getAllTextures(context, True)
        self.getFileNames(paths)
        self.replaceTextures(context)


class DAZ_OT_ResizeTextures(DazPropsOperator, HiddenTextureUser, LocalTextureUser, ChangeResolution):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = "Replace all textures of selected meshes with resized versions"
    bl_options = {'UNDO'}

    def draw(self, context):
        LocalTextureUser.draw(self, context)
        HiddenTextureUser.draw(self, context)
        ChangeResolution.draw(self, context)

    def run(self, context):
        self.initResolution()
        paths = self.getAllTextures(context, False)
        self.printLocalImages()
        self.getFileNames(paths)

        scale = int(2**self.steps)
        for path in paths:
            path = getProperPath(path)
            base = self.getBasePath(path)
            _,newpath = self.getNewPath(base)
            if not self.imageExists(newpath) and self.imageExists(base):
                img = self.loadImage(base)
                if img is None:
                    print("Could not load %s" % base)
                    continue
                x,y = img.size
                img.scale(int(x/scale), int(y/scale))
                img.filepath_raw = newpath
                img.name = os.path.splitext(os.path.basename(newpath))[0]
                print("%s => %s: %s => %s" % (os.path.basename(path), os.path.basename(newpath), (x,y), tuple(img.size)))
                self.saveImage(img, True)
            else:
                print("Skip", newpath)

        self.replaceTextures(context)
        self.printLocalImages()
        self.saveLocalImages()

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def getProperPath(path):
    if path[0:2] == "//":
        return os.path.join(os.path.dirname(bpy.data.filepath), path[2:])
    return path

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SaveLocalTextures,
    DAZ_OT_ChangeResolution,
    DAZ_OT_ResizeTextures,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

