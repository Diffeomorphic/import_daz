# Copyright (c) 2016-2022, Thomas Larsson
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


import json
import gzip
import os
from mathutils import Vector, Color
from .error import reportError, DazError


def loadJson(filepath, mustOpen=False):
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
                while string[n].isspace() and n > 0:
                    n -= 1
                if string[n] == ",":
                    print("Smashing character %d" % n)
                    return "%s %s" % (string[:n], string[n1:])
        return None

    if not os.path.exists(filepath):
        raise DazError('File does not exist:\n"%s"' % filepath)
    try:
        with gzip.open(filepath, 'rb') as fp:
            bytes = fp.read()
    except IOError:
        bytes = None

    if bytes:
        string = bytes.decode("utf_8_sig")
        filetype = "zipped"
    else:
        try:
            with open(filepath, 'r') as fp:
                string = fp.read()
            filetype = "ascii"
        except IOError:
            string = None
        except UnicodeDecodeError:
            string = None
    if string is None:
        reportError('Could not open file\n"%s"\n' % (filepath), trigger=(1,2))
        return {}

    struct,msg,jsonerr = loadFromString(string)
    if jsonerr:
        string = smashString(string, jsonerr)
        if string:
            struct,msg,jsonerr = loadFromString(string)
    if msg:
        reportError(msg, trigger=(1,2))
    return struct


def saveJson(struct, filepath, binary=False):
    folder = os.path.dirname(filepath)
    if not os.path.exists(folder):
        raise DazError('Output directory does not exist.\n"%s"' % folder)
    if binary:
        string = encodeJsonData(struct, "")
        bytes = string.encode("utf_8_sig")
        with gzip.open(filepath, 'wb') as fp:
            fp.write(bytes)
    else:
        import codecs
        string = encodeJsonData(struct, "")
        with codecs.open(filepath, "w", encoding="utf_8") as fp:
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
            print(data.type)
            raise DazError("Can't encode: %s %s" % (data, data.type))


def leafList(data):
    for elt in data:
        if isinstance(elt, (list,dict)):
            return False
    return True
