# SPDX-FileCopyrightText: 2016-2026, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import gzip
import os
import bpy
from mathutils import Vector, Color
from .error import reportError, DazError

#-------------------------------------------------------------
#   Class for caching
#-------------------------------------------------------------

class JsonLoader:
    useCache = [
        "genesis.dsf",
        "genesis2female.dsf",
        "genesis2male.dsf",
        "genesis3female.dsf",
        "genesis3male.dsf",
        "genesis8female.dsf",
        "genesis8male.dsf",
        "genesis8_1female.dsf",
        "genesis8_1male.dsf",
        "genesis9.dsf",
    ]

    def __init__(self):
        self.cached = {}

    def load(self, filepath, mustOpen=False, silent=False):
        key = os.path.basename(filepath).lower()
        struct = self.cached.get(key)
        if struct:
            return struct
        struct = loadJson(filepath, mustOpen, silent)
        if key in self.useCache:
            self.cached[key] = struct
        return struct


JL = JsonLoader()

#-------------------------------------------------------------
#   Load gzipped json file
#-------------------------------------------------------------

def loadJson(filepath, mustOpen=False, silent=False):
    def loadFromString(string):
        struct = {}
        jsonerr = None
        try:
            struct = json.loads(string)
            msg = None
        except json.decoder.JSONDecodeError as err:
            msg = ('JSON error while reading %s file\n"%s"\n%s' % (filetype, filepath, err))
            jsonerr = str(err)
        except UnicodeDecodeError as err:
            msg = ('Unicode error while reading %s file\n"%s"\n%s' % (filetype, filepath, err))
        return struct, msg, jsonerr

    def smashString(string, jsonerr):
        # Expecting value: line 14472 column 630 (char 619107)
        words = jsonerr.split("(char ")
        if len(words) == 2:
            nstring = words[1].split(")")[0]
            if nstring.isdigit():
                n1 = int(nstring)
                n = n1-1
                if len(string) < n:
                    print("Unknown error: %s" % jsonerr)
                    return None
                while string[n].isspace() and n > 0:
                    n -= 1
                if string[n] == ",":
                    print("Smashing character %d" % n)
                    return "%s %s" % (string[:n], string[n1:])
        return None

    filepath = bpy.path.resolve_ncase(os.path.expanduser(filepath))
    if not os.path.exists(filepath):
        msg = 'File does not exist:\n"%s"' % filepath
        if silent:
            return {}
        elif mustOpen:
            raise DazError(msg)
        else:
            print(msg)
            return {}
    try:
        with gzip.open(filepath, 'rb') as fp:
            bytes = fp.read()
    except IOError:
        bytes = None

    if bytes:
        try:
            string = bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            string = bytes.decode("utf-16")
        filetype = "zipped"
    else:
        def readFile(filepath, encoding):
            try:
                with open(filepath, 'r', encoding=encoding) as fp:
                    string = fp.read()
                return string
            except (IOError, UnicodeError, UnicodeDecodeError) as err:
                print(err)
                return None

        string = readFile(filepath, "utf-8-sig")
        if string is None:
            print('UTF-16 "%s"' % filepath)
            string = readFile(filepath, "utf-16")
        filetype = "ascii"
    if string is None:
        if not silent:
            reportError('Could not open file\n"%s"\n' % (filepath), trigger=(1,5))
        return {}

    struct,msg,jsonerr = loadFromString(string)
    if jsonerr:
        try:
            string = smashString(string, jsonerr)
        except IndexError:
            string = ""
        if string:
            struct,msg,jsonerr = loadFromString(string)
    if msg and not silent:
        reportError(msg, trigger=(1,5))
    return struct

#-------------------------------------------------------------
#   Save Json file
#-------------------------------------------------------------

def saveJson(struct, filepath, binary=False, strict=True):
    folder = os.path.dirname(filepath)
    if not os.path.exists(folder):
        if strict:
            raise DazError('Output directory does not exist.\n"%s"' % folder)
        else:
            print('Creating directory: %s' % folder)
            os.makedirs(folder)
    if binary:
        string = encodeJsonData(struct, "")
        bytes = string.encode("utf-8-sig")
        with gzip.open(filepath, 'wb') as fp:
            fp.write(bytes)
    else:
        import codecs
        string = encodeJsonData(struct, "")
        with codecs.open(filepath, "w", encoding="utf-8-sig") as fp:
            fp.write(string)
            fp.write("\n")


def encodeJsonData(data, pad=""):
    from .error import DazError
    if data is None:
        return "null"
    elif isinstance(data, (bool)):
        if data:
            return "true"
        else:
            return "false"
    elif isinstance(data, (float)):
        if abs(data) < 1e-6:
            return "0.0"
        else:
            return "%.5g" % data
    elif isinstance(data, (int)):
        return str(data)

    elif isinstance(data, (str)):
        return "\"%s\"" % data
    elif isinstance(data, (list, tuple, Vector, Color)):
        if leafList(data):
            string = "["
            string += ",".join([encodeJsonData(elt) for elt in data])
            return string + "]"
        else:
            string = "["
            string += ",".join(
                ["\n    " + pad + encodeJsonData(elt, pad+"    ")
                 for elt in data])
            if string == "[":
                return "[]"
            else:
                return string + "\n%s]" % pad
    elif isinstance(data, dict):
        string = "{"
        string += ",".join(
            ["\n    %s\"%s\" : " % (pad, key) + encodeJsonData(value, pad+"    ")
             for key,value in data.items()])
        if string == "{":
            return "{}"
        else:
            return string + "\n%s}" % pad
    else:
        try:
            string = "["
            string += ",".join([encodeJsonData(elt) for elt in data])
            return string + "]"
        except:
            print(data)
            print("Can't encode: %s" % data)
            return str(data)
            print(data.type)
            raise DazError("Can't encode: %s %s" % (data, data.type))


def leafList(data):
    for elt in data:
        if isinstance(elt, (list,dict)):
            return False
    return True
