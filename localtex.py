# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
from .utils import *
from .error import *
from .material import isSRGBImage, setRightColorSpace

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
    level = 0
    imageSize = 64
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


    def getMeshes(self, context):
        return getSelectedMeshes(context)


    def setResSubdir(self, level):
        if level == 0:
            self.subdir = "/textures/original"
        else:
            self.subdir = "/textures/res%d" % level


    def getResLevel(self, path):
        lpath = normalizePath(path).lower()
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
        self.existImages = {}
        self.existImages[True] = dict([(pathKey(img.filepath), img)
                                        for img in bpy.data.images if isSRGBImage(img)])
        self.existImages[False] = dict([(pathKey(img.filepath), img)
                                        for img in bpy.data.images if not isSRGBImage(img)])
        self.foundImages = []
        self.deletedImages = {}


    def printLocalImages(self):
        print("SRGB images")
        for path,img in self.existImages[True].items():
            if img:
                print("  ", path, img.has_data)
        print("NonColor images")
        for path,img in self.existImages[False].items():
            if img:
                print("  ", path, img.has_data)
        print("Deleted images")
        for path,img in self.deletedImages.items():
            if img:
                print("  ", path, img.has_data)


    def stripPath(self, path):
        lpath = path.lower()
        for string in ["/textures/original/", "/textures/udim/"]:
            words = lpath.rsplit(string, 1)
            if len(words) == 2:
                n = len(words[1])
                return path[-n:]
        words = lpath.rsplit("/textures/res", 1)
        if len(words) == 2:
            n = len(words[1])
            return path[-n+2:]


    def getLocalPath(self, path):
        path = normalizePath(path)
        words = path.split(".jpg")
        if len(words) > 2 or path.endswith("<UDIM>"):
            msg = ("Bad local path: %s" % path)
            print(msg)
            raise DazError(msg)
        relpath = None
        lpath = path.lower()
        if lpath.startswith(self.basepath):
            relpath = self.stripPath(path)
        else:
            words = lpath.rsplit("/runtime/textures/", 1)
            if len(words) == 2:
                n = len(words[1])
                relpath = path[-n:]
        if relpath:
            return "%s/%s" % (self.texpath, relpath)
        else:
            return path


    def getOrigPath(self, img):
        path = img.get("DazFilePath")
        if path:
            return path
        path = self.getLocalPath(img.filepath)
        path = normalizePath(bpy.path.relpath(path))
        if path.startswith("//textures"):
            relpath = self.stripPath(path[1:])
            if relpath:
                path = "/runtime/textures/%s" % relpath
        return GS.getAbsPath(path)


    def copyImage(self, src, trg, srgb, key=None):
        trg = pathKey(trg)
        img = self.existImages[srgb].get(trg)
        if img:
            return img
        elif os.path.exists(trg):
            img = bpy.data.images.load(trg)
            setRightColorSpace(img, srgb)
            self.existImages[srgb][trg] = img
            return img

        src = pathKey(src)
        if not os.path.exists(src):
            print("Image not found: %s" % src)
            return None
        img = bpy.data.images.load(src)
        setRightColorSpace(img, srgb)
        img.update()
        img = self.modifyImage(img)
        img.filepath_raw = trg
        img.name = os.path.basename(trg)
        img.save()
        self.existImages[srgb][trg] = img
        if GS.verbosity >= 3:
            print("Copied %s %s" % (tuple(img.size), trg))
        if "Public" in trg:
            msg = "Expected local image: %s" % trg
            print(msg)
            raise DazError(msg)
        return img


    def modifyImage(self, img):
        return img


    def addImage(self, imgname, trg, srgb, key):
        from .material import setColorSpaceNone
        if key.endswith(("Factor:Value", "Fac")):
            color = (1,1,1,1)
        elif key.startswith("NORMAL_MAP:Color"):
            color = (0.5, 0.5, 1.0, 1)
        elif key.endswith(("Color:A", "Color:B", "Color")):
            color = (1,1,1,1)
        elif key.startswith(("BUMP:Height")):
            color = (0.5, 0.5, 0.5, 1)
        elif key.startswith(("PBR:Base Color", "DAZ Dual Lobe:IOR", "PBR:Specular Tint")):
            color = (1,1,1,1)
        elif "Roughness" in key:
            color = (1,1,1,1)
        else:
            print("Unknown key when adding UDIM image:", key)
            color = (0,0,0,1)

        img = bpy.data.images.new(imgname, self.imageSize, self.imageSize)
        img.generated_color = color
        setRightColorSpace(img, srgb)
        trg = pathKey(trg)
        img.filepath_raw = trg
        self.saveImage(img)
        return img


    def saveImage(self, img):
        img.update()
        img.save()
        path = pathKey(img.filepath)
        srgb = isSRGBImage(img)
        self.existImages[srgb][path] = img


    def saveImageAs(self, img, path):
        img.update()
        srgb = isSRGBImage(img)
        img2 = bpy.data.images.load(img.filepath)
        img2.update()
        img2.filepath_raw = path
        img2.save()
        img2.colorspace_settings.name = img.colorspace_settings.name
        img2.update()
        self.existImages[srgb][path] = img2
        return img2


    def isIrrelevant(self, path):
        return False


    def getAllImages(self, meshes):
        def getNodesInTree(tree):
            for node in tree.nodes.values():
                if node.type == 'TEX_IMAGE':
                    self.foundImages.append((node, node.image))
                elif node.type == 'GROUP':
                    getNodesInTree(node.node_tree)

        def getTextureSlots(mat):
            for mtex in mat.texture_slots:
                if mtex:
                    tex = mtex.texture
                    if hasattr(tex, "image") and tex.image:
                        self.foundImages.append((None, tex.image))

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
    subdir = "/textures/original"

    def run(self, context):
        meshes = self.getMeshes(context)
        self.initLocalImages()
        self.getAllImages(meshes)
        for node,img in self.foundImages:
            src = pathKey(img.filepath)
            trg = self.getLocalPath(src)
            srgb = isSRGBImage(img)
            img2 = self.copyImage(src, trg, srgb)
            node.image = img2
        #freeImages()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 1


    def isIrrelevant(self, path):
        if (path.lower().startswith(self.basepath) and
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
        self.initLocalImages()
        if self.useOriginal:
            self.restoreOriginal(meshes)
        else:
            self.getAllImages(meshes)
            for _,img in self.foundImages:
                filepath = bpy.path.abspath(img.filepath)
                if filepath and os.path.exists(filepath):
                    if img.packed_file:
                        if not self.useUnpack:
                            continue
                        img.unpack()
                    img.filepath_raw = filepath
                    img.update()
        freeImages()


    def restoreOriginal(self, meshes):
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

    force : BoolProperty(
        name = "Force Resize",
        description = "Resize the image even if it means upscaling it",
        default = False)

    def draw(self, context):
        LocalTextureUser.draw(self, context)
        HiddenTextureUser.draw(self, context)
        self.layout.prop(self, "level")
        self.layout.prop(self, "force")


    def run(self, context):
        self.setResSubdir(self.level)
        meshes = self.getMeshes(context)
        self.initLocalImages()
        self.getAllImages(meshes)
        for node,img in self.foundImages:
            src = pathKey(img.filepath)
            trg = self.getLocalPath(src)
            srgb = isSRGBImage(img)
            img2 = self.copyImage(src, trg, srgb)
            node.image = img2
        #freeImages()
        for ob in meshes:
            dazRna(ob.data).DazTexLevel = 2


    def modifyImage(self, img):
        level = self.getResLevel(img.filepath)
        if level < self.level:
            scale = int(2**(self.level-level))
            x,y = img.size
            img.scale(int(x/scale), int(y/scale))
            return img
        elif level > self.level and self.force:
            scale = int(2**(level-self.level))
            x,y = img.size
            img.scale(int(x*scale), int(y*scale))
            return img
        else:
            return img

#----------------------------------------------------------
#   Prune images
#----------------------------------------------------------

class DAZ_OT_PruneImages(DazOperator):
    bl_idname = "daz.prune_images"
    bl_label = "Prune Images"
    bl_description = "Remove all unused images"
    bl_options = {'UNDO'}

    def run(self, context):
        for img in list(bpy.data.images):
            img.buffers_free()
            if img.users == 0:
                print("Remove %s" % img.name)
                bpy.data.images.remove(img)

#----------------------------------------------------------
#   Utility
#----------------------------------------------------------

def freeImages():
    for img in bpy.data.images:
        img.buffers_free()


def pathKey(path, colorspace=None):
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
    DAZ_OT_PruneImages,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

