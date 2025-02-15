# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .error import reportError
from .utils import *
from .load_json import JL

#-------------------------------------------------------------
#   Accessor base class
#-------------------------------------------------------------

class Accessor:
    def __init__(self, fileref):
        self.fileref = fileref
        self.caller = None
        self.rna = None


    def getAsset(self, id, strict=False):
        if isinstance(id, Asset):
            return id

        id = normalizeRef(id)
        if "?" in id:
            # Attribute. Return None
            return None
        ref = getRef(id, self.fileref)
        asset = LS.assets.get(ref)
        if asset:
            return asset

        if id[0] == "#":
            if self.caller:
                ref = getRef(id, self.caller.fileref)
                asset = LS.assets.get(ref)
                if asset:
                    return asset
            ref = getRef(id, self.fileref)
            asset = LS.assets.get(ref)
            if asset:
                return asset
            asset = LS.otherAssets.get(ref)
            if asset:
                return asset
            if strict:
                msg = ("Missing local asset:\n  '%s'\n" % ref)
                if self.caller:
                    msg += ("in file:\n  '%s'\n" % self.caller.fileref)
                reportError(msg)
            return None
        else:
            return self.getNewAsset(id, ref)


    def getNewAsset(self, id, ref):
        from .files import parseAssetFile
        fileref = id.split("#")[0]
        filepath = GS.getAbsPath(fileref)
        if filepath:
            struct = JL.load(filepath)
            parseAssetFile(struct, fileref=fileref)
            return LS.assets.get(ref)
        else:
            return None


    def getTypedAsset(self, id, type):
        asset = self.getAsset(id)
        if (asset is None or
            type is None or
            isinstance(asset,type)):
            return asset
        if self.caller and self.caller != self:
            asset = self.caller.getTypedAsset(id, type)
            if asset:
                return asset
        msg = (
            "Asset of type %s not found:\n  %s\n" % (type, id) +
            "File ref:\n  '%s'\n" % self.fileref
        )
        return reportError(msg, trigger=(2,5), warnPaths=True)


    def parseUrlAsset(self, struct, type=None):
        if "url" not in struct.keys():
            msg = ("URL asset failure: No URL.\n" +
                   "Type: %s\n" % type +
                   "File ref:\n  '%s'\n" % self.fileref +
                   "Id: '%s'\n" % struct["id"] +
                   "Keys:\n %s\n" % list(struct.keys()))
            reportError(msg, warnPaths=True)
            return None
        asset = self.getTypedAsset(struct["url"], type)
        if isinstance(asset, Asset):
            asset.caller = self
            asset.update(struct)
            self.saveAsset(struct, asset)
            return asset
        elif asset is not None:
            msg = ("Empty asset:\n  %s   " % struct["url"])
            return reportError(msg, warnPaths=True)
        else:
            asset = self.getAsset(struct["url"])
            msg = ("URL asset failure:\n" +
                   "URL: '%s'\n" % struct["url"] +
                   "Type: %s\n" % type +
                   "File ref:\n  '%s'\n" % self.fileref +
                   "Found asset:\n %s\n" % asset)
            return reportError(msg, warnPaths=True, trigger=(3,5))
        return None


    def saveAsset(self, struct, asset):
        ref = ref2 = normalizeRef(asset.id)
        if self.caller:
            if "id" in struct.keys():
                ref = getId(struct["id"], self.caller.fileref)
            else:
                print("No id", struct.keys())

        asset2 = LS.assets.get(ref)
        if asset2 and asset2 != asset:
            msg = ("Duplicate asset definition\n" +
                   "  Asset 1: %s\n" % asset +
                   "  Asset 2: %s\n" % asset2 +
                   "  Ref 1: %s\n" % ref +
                   "  Ref 2: %s\n" % ref2)
            reportError(msg)
            LS.assets[ref2] = asset
        else:
            LS.assets[ref] = LS.assets[ref2] = asset
        return

        if asset.caller:
            ref2 = "%s#%s" % (asset.caller.id, struct["id"])
            ref2 = normalizeRef(ref2)
            if ref2 in LS.assets.keys():
                asset2 = LS.assets[ref2]
                if asset != asset2 and GS.verbosity > 1:
                    msg = ("Duplicate asset definition\n" +
                           "  Asset 1: %s\n" % asset +
                           "  Asset 2: %s\n" % asset2 +
                           "  Caller: %s\n" % asset.caller +
                           "  Ref 1: %s\n" % ref +
                           "  Ref 2: %s\n" % ref2)
                    return reportError(msg)
            else:
                print("REF2", ref2)
                print("  ", asset)
                LS.assets[ref2] = asset


    def addNewAsset(self, struct):
        asset = self.parseUrlAsset(struct)
        if asset:
            ref = normalizeRef("%s#%s" % (asset.fileref, struct["id"]))
            LS.assets[ref] = asset

#-------------------------------------------------------------
#   Asset base class
#-------------------------------------------------------------

class Asset(Accessor):
    def __init__(self, fileref):
        Accessor.__init__(self, fileref)
        self.id = None
        self.url = None
        self.name = None
        self.oldnames = []
        self.label = None
        self.type = None
        self.visible = True
        self.parent = None
        self.parentRef = None
        self.children = []
        self.source = None
        self.sourcing = None
        self.drivable = True


    def __repr__(self):
        return ("<Asset %s t: %s r: %s>" % (self.id, self.type, self.rna))


    def errorWrite(self, ref, fp):
        fp.write('\n"%s":\n' % ref)
        fp.write("  %s\n" % self)


    def selfref(self):
        return ("#" + self.id.rsplit("#", 2)[-1])


    def getLabel(self, inst=None):
        if inst and inst.label:
            return inst.label
        elif self.label:
            return self.label
        else:
            return self.name


    def getName(self):
        if self.id is None:
            return "None"
        else:
            return unquote(self.id.rsplit("#",1)[-1])


    def copySource(self, asset):
        for key in dir(asset):
            if hasattr(self, key) and key[0] != "_":
                attr = getattr(self, key)
                try:
                    setattr(asset, key, attr)
                except RuntimeError:
                    pass


    def copySourceFile(self, source):
        file = source.rsplit("#", 1)[0]
        asset = self.parseUrlAsset({"url": source})
        if asset is None:
            return None
        old = asset.id.rsplit("#", 1)[0]
        new = self.id.rsplit("#", 1)[0]
        self.copySourceAssets(old, new)
        if old not in LS.sources.keys():
            LS.sources[old] = []
        for other in LS.sources[old]:
            self.copySourceAssets(other, new)
        LS.sources[old].append(new)
        return asset


    def copySourceAssets(self, old, new):
        nold = len(old)
        nnew = len(new)
        adds = []
        assets = []
        for key,asset in LS.assets.items():
            if key[0:nold] == old:
                adds.append((new + key[nold:], asset))
        for key,asset in adds:
            if key not in LS.otherAssets.keys():
                LS.otherAssets[key] = asset
                assets.append(asset)


    def parse(self, struct):
        if "id" in struct.keys():
            self.id = getId(struct["id"], self.fileref)
        else:
            self.id = "?"
            msg = ("Asset without id\nin file \"%s\":\n%s    " % (self.fileref, struct))
            reportError(msg, trigger=(1,5))

        if "url" in struct.keys():
            self.url = struct["url"]
        elif "id" in struct.keys():
            self.url = struct["id"]

        if "type" in struct.keys():
            self.type = struct["type"]

        if "name" in struct.keys():
            self.name = struct["name"]
        elif "id" in struct.keys():
            self.name = struct["id"]
        elif self.url:
            self.name = self.url
        else:
            self.name = "Noname"

        if "label" in struct.keys():
            self.label = struct["label"]

        if "channel" in struct.keys():
            for key,value in struct["channel"].items():
                if key == "visible":
                    self.visible = value
                elif key == "label":
                    self.label = value

        if "parent" in struct.keys() and not LS.useMorphOnly:
            self.parentRef = instRef(struct["parent"])
            self.parent = self.getAsset(struct["parent"])
            if self.parent:
                self.parent.children.append(self)

        if "source" in struct.keys():
            self.parseSource(struct["source"])
        return self


    def parseSource(self, url):
        asset = self.getAsset(url)
        if asset:
            if self.type == asset.type:
                self.source = asset
                asset.sourcing = self
                LS.assets[url] = self
            else:
                msg = ("Source type mismatch:   \n" +
                       "%s != %s\n" % (asset.type, self.type) +
                       "URL: %s           \n" % url +
                       "Asset: %s\n" % self +
                       "Source: %s\n" % asset)
                reportError(msg)


    def update(self, struct):
        for key,value in struct.items():
            if key == "type":
                self.type = value
            elif key == "name":
                if self.name != value:
                    self.oldnames.append(self.name)
                    self.name = value
            elif key == "url":
                self.url = value
            elif key == "label":
                self.label = value
            elif key == "parent" and not LS.useMorphOnly:
                self.parentRef = instRef(struct["parent"])
                if self.parent is None and self.caller:
                    self.parent = self.caller.getAsset(struct["parent"])
            elif key == "channel":
                self.value = getCurrentValue(value)
        if False and self.source:
            self.children = self.source.children
            self.sourceChildren(self.source)
        return self


    def sourceChildren(self, source):
        for srcnode in source.children:
            url = self.fileref + "#" + srcnode.id.rsplit("#",1)[-1]
            print("HHH", url)
            LS.assets[url] = srcnode
            self.sourceChildren(srcnode)


    def build(self, context, inst=None):
        return
        raise NotImplementedError("Cannot build %s yet" % self.type)


    def buildData(self, context, inst, center):
        print("BDATA", self)
        if self.rna is None:
            self.build(context)
        return None, None


    def connect(self, struct):
        pass


def getAssetFromStruct(struct, fileref):
    id = getId(struct["id"], fileref)
    return LS.assets.get(id)


def getExistingFile(fileref):
    ref = normalizeRef(fileref)
    return LS.assets.get(ref)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def storeAsset(asset, url):
    LS.assets[url] = asset


def getAssets():
    return LS.assets


def getId(id0, fileref):
    id = normalizeRef(id0)
    if len(id) == 0:
        print("Asset with no id in %s" % fileref)
        return fileref + "#"
    elif id[0] == "/":
        return id
    else:
        return fileref + "#" + id


def getRef(id, fileref):
    id = normalizeRef(id)
    if id[0] == "#":
        return "%s%s" % (fileref, id)
    else:
        return id


def normalizeRef(id):
    ref = quote(id)
    ref = ref.replace("%23","#").replace("%25","%").replace("%2D", "-").replace("%2E", ".").replace("%2F", "/").replace("%3F", "?")
    ref = ref.replace("%5C", "/").replace("%5F", "_").replace("%7C", "|")
    if len(ref) == 0:
        return ""
    elif ref[0] == "/":
        words = ref.rsplit("#", 1)
        if len(words) == 2:
            ref = "%s#%s" % (words[0].lower(), words[1])
        else:
            ref = ref.lower()
    return canonicalPath(ref)


def normalizeUrl(filepath):
    relpath = GS.getRelativePath(filepath)
    return normalizeRef(relpath)
