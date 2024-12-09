# SPDX-FileCopyrightText: 2016-2024, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

#----------------------------------------------------------
#   Debugging
#----------------------------------------------------------

from ..debug import DEBUG

if not DEBUG:
    pass
elif "SimulationToolsFeature" in locals():
    print("Reloading Simulation Tools")
    import imp
    imp.reload(simulation)
    imp.reload(deflection)
else:
    print("Loading Simulation Tools")
    from . import simulation
    from . import deflection
    SimulationToolsFeature = True

#----------------------------------------------------------
#   Simulations panel
#----------------------------------------------------------

import bpy
from ..panel import DAZ_PT_SetupTab

class DAZ_PT_Simulation(DAZ_PT_SetupTab, bpy.types.Panel):
    bl_idname = "DAZ_PT_Simulation"
    bl_label = "Simulation"

    def draw(self, context):
        self.layout.operator("daz.add_softbody")
        self.layout.operator("daz.make_deflection")
        self.layout.operator("daz.make_dforce")
        self.layout.separator()
        self.layout.operator("daz.make_collision")
        self.layout.operator("daz.make_cloth")

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    print("Register Simulation Tools")
    bpy.utils.register_class(DAZ_PT_Simulation)
    from . import simulation, deflection
    simulation.register()
    deflection.register()

def unregister():
    bpy.utils.unregister_class(DAZ_PT_Simulation)
    from . import simulation, deflection
    simulation.unregister()
    deflection.unregister()


