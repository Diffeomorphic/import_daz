# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ..utils import *

class RigifyData:
    def __init__(self, meta):
        def deleteChildren(eb, meta):
            for child in eb.children:
                deleteChildren(child, meta)
                meta.data.edit_bones.remove(child)

        self.hips = "spine"
        spine = "spine.001"
        spine1 = "spine.002"
        chest = "spine.003"
        chest1 = "spine.004"
        neck = "spine.005"
        if meta.get("DazUseSplitNeck"):
            neck1= "spine.006"
            self.head = "spine.007"
        else:
            self.head = "spine.006"
        meta.DazRigifyType = "rigify2"



        self.RigifyParams = {
            ("spine", "neck_pos", 6),
            ("spine", "pivot_pos", 1),
        }

        self.MetaDisconnect = [self.hips, neck]

        self.MetaParents = {
            "shoulder.L" : chest1,
            "shoulder.R" : chest1,
        }

        self.Genesis9Removes = ["l_upperarm", "r_upperarm"]

        self.ExtraParents = {
            "lPectoral" : "DEF-spine.004",
            "rPectoral" : "DEF-spine.004",
            "l_pectoral" : "DEF-spine.004",
            "r_pectoral" : "DEF-spine.004",
        }
        self.ExtraParents = {}

