# Copyright (c) 2016-2023, Thomas Larsson
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


import os
import json
import gzip
import copy
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
        asset = LS.theAssets.get(ref)
        if asset:
            return asset

        if id[0] == "#":
            if self.caller:
                ref = getRef(id, self.caller.fileref)
                asset = LS.theAssets.get(ref)
                if asset:
                    return asset
            ref = getRef(id, self.fileref)
            asset = LS.theAssets.get(ref)
            if asset:
                return asset
            asset = LS.theOtherAssets.get(ref)
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
            return LS.theAssets.get(ref)
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

        asset2 = LS.theAssets.get(ref)
        if asset2 and asset2 != asset:
            msg = ("Duplicate asset definition\n" +
                   "  Asset 1: %s\n" % asset +
                   "  Asset 2: %s\n" % asset2 +
                   "  Ref 1: %s\n" % ref +
                   "  Ref 2: %s\n" % ref2)
            reportError(msg)
            LS.theAssets[ref2] = asset
        else:
            LS.theAssets[ref] = LS.theAssets[ref2] = asset
        return

        if asset.caller:
            ref2 = "%s#%s" % (asset.caller.id, struct["id"])
            ref2 = normalizeRef(ref2)
            if ref2 in LS.theAssets.keys():
                asset2 = LS.theAssets[ref2]
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
                LS.theAssets[ref2] = asset

#-------------------------------------------------------------
#   Asset base class
#-------------------------------------------------------------

class Asset(Accessor):
    def __init__(self, fileref):
        Accessor.__init__(self, fileref)
        self.id = None
        self.url = None
        self.name = None
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
        if old not in LS.theSources.keys():
            LS.theSources[old] = []
        for other in LS.theSources[old]:
            self.copySourceAssets(other, new)
        LS.theSources[old].append(new)
        return asset


    def copySourceAssets(self, old, new):
        nold = len(old)
        nnew = len(new)
        adds = []
        assets = []
        for key,asset in LS.theAssets.items():
            if key[0:nold] == old:
                adds.append((new + key[nold:], asset))
        for key,asset in adds:
            if key not in LS.theOtherAssets.keys():
                LS.theOtherAssets[key] = asset
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
                LS.theAssets[url] = self
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
            LS.theAssets[url] = srcnode
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
    return LS.theAssets.get(id)


def getExistingFile(fileref):
    ref = normalizeRef(fileref)
    return LS.theAssets.get(ref)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def storeAsset(asset, url):
    LS.theAssets[url] = asset


def getAssets():
    return LS.theAssets


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
    return ref.replace("//", "/")


def normalizeUrl(filepath):
    relpath = GS.getRelativePath(filepath)
    return normalizeRef(relpath)
