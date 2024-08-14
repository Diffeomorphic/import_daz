#  DAZ Importer - Importer for native DAZ files (.duf, .dsf)
#  Copyright (c) 2016-2024, Thomas Larsson
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from .error import reportError
from .utils import *

#-------------------------------------------------------------
#   Channels class
#-------------------------------------------------------------

class Channels:
    def __init__(self):
        self.channels = {}
        self.extra = []
        self.usedChannels = {}


    def parse(self, struct):
        from copy import deepcopy
        if "url" in struct.keys():
            asset = self.getAsset(struct["url"])
            if asset and hasattr(asset, "channels"):
                self.channels = deepcopy(asset.channels)
        for key,data in struct.items():
            if key == "extra":
                if isinstance(data, list):
                    self.extra = data
                else:
                    self.extra = [data]
                for extra in self.extra:
                    self.setExtra(extra)
                    for cstruct in extra.get("channels", {}):
                        if isinstance(cstruct, dict) and "channel" in cstruct.keys():
                            self.setChannel(cstruct["channel"])
            elif isinstance(data, dict) and "channel" in data.keys():
                self.setChannel(data["channel"])


    def setChannel(self, channel):
        self.channels[channel["id"]] = channel


    def update(self, struct):
        for key,data in struct.items():
            if key == "extra":
                if isinstance(data, list):
                    self.extra = data
                else:
                    self.extra = [data]
                for extra in self.extra:
                    self.setExtra(extra)
                    for cstruct in extra.get("channels", {}):
                        if isinstance(cstruct, dict) and "channel" in cstruct.keys():
                            self.replaceChannel(cstruct["channel"])
            elif isinstance(data, dict) and "channel" in data.keys():
                self.replaceChannel(data["channel"])


    def setExtra(self, struct):
        pass


    def replaceChannel(self, channel, key=None):
        from copy import deepcopy
        if key is None:
            key = channel["id"]
        if key in self.channels.keys():
            for name,value in channel.items():
                self.channels[key][name] = value
        else:
            self.channels[key] = deepcopy(channel)


    def getChannel(self, attr, onlyVisible=True):
        if isinstance(attr, str):
            return getattr(self, attr)()
        for key in attr:
            if key in self.channels.keys():
                channel = self.channels[key]
                self.usedChannels[key] = True
                if channel.get("visible", True) or not onlyVisible:
                    return channel
        return None


    def equalChannels(self, other):
        for key,value in self.channels.items():
            if (key not in other.channels.keys() or
                other.channels[key] != value):
                return False
        return True


    def copyChannels(self, channels):
        for key,value in channels.items():
            self.channels[key] = value


    def getValue(self, attr, default, onlyVisible=True):
        return self.getChannelValue(self.getChannel(attr, onlyVisible), default)


    def getValueImage(self, attr, default):
        channel = self.getChannel(attr)
        value = self.getChannelValue(channel, default)
        return value,channel.get("image_file")


    def getChannelValue(self, channel, default, warn=True):
        if channel is None:
            return default
        if (channel.get("invalid_without_map") and
            not self.getImageFile(channel)):
            return default
        for key in ["color", "strength", "current_value", "value"]:
            if key in channel.keys():
                value = channel[key]
                if default is None:
                    return value
                elif isVector(default):
                    if isVector(value):
                        return value
                    else:
                        return Vector((value, value, value))
                else:
                    if isVector(value):
                        return (value[0] + value[1] + value[2])/3
                    else:
                        return value
        if warn and GS.verbosity > 2:
            print("Did not find value for channel %s" % channel["id"])
            print("Keys: %s" % list(channel.keys()))
        return default


    def getImageFile(self, channel):
        return (channel.get("image_file") or channel.get("image"))



