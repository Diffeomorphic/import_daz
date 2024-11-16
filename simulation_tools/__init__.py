#  DAZ Simulations - Tools for rigging figures imported with the DAZ Importer
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
        self.layout.separator()
        self.layout.operator("daz.make_simulation")
        self.layout.separator()
        self.layout.operator("daz.make_deflection")
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


