#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

# <pep8 compliant>

bl_info = {
    "name": "GameRig",
    "version": (0, 9),
    "author": "Osamu Takasugi, (Rigify : Nathan Vegdahl, Lucio Rossi, Ivan Cappiello)",
    "blender": (2, 80, 0),
    "description": "Character Rigging framework for Game / Realtime content",
    "location": "Armature properties, Bone properties, View3d tools panel, Armature Add menu",
    "support": "COMMUNITY",
    "wiki_url": "https://github.com/SAM-tak/BlenderGameRig",
    "tracker_url": "https://github.com/SAM-tak/BlenderGameRig/issues",
    "category": "Rigging"
}


if "bpy" in locals():
    import importlib
    importlib.reload(utils)
    importlib.reload(rig_lists)
    importlib.reload(generate)
    importlib.reload(ui)
    importlib.reload(metarig_menu)
else:
    from . import utils, rig_lists, generate, ui, metarig_menu

import bpy
import sys
import os
from bpy.types import (
    AddonPreferences,
    PropertyGroup
)
from bpy.props import (
    BoolProperty,
    IntProperty,
    EnumProperty,
    StringProperty,
    FloatVectorProperty,
    PointerProperty,
    CollectionProperty,
)


class Preferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    shows_dev_tools : BoolProperty(
        name='Enable Dev Tools',
        description='Dev Tools appears in Tools tab on edit mode.',
        default=False
    )

    def draw(self, context):
        self.layout.row().prop(self, 'shows_dev_tools')


class RigType(PropertyGroup):
    pass


class ColorSet(PropertyGroup):
    name : StringProperty(name="Color Set", default=" ")
    active : FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )
    normal : FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )
    select : FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )
    standard_colors_lock : BoolProperty(default=True)


class SelectionColors(PropertyGroup):
    select : FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(0.314, 0.784, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )

    active : FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(0.549, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )


class ArmatureLayer(PropertyGroup):
    def get_group(self):
        if 'group_prop' in self.keys():
            return self['group_prop']
        else:
            return 0

    def set_group(self, value):
        arm = bpy.context.object.data
        if value > len(arm.gamerig.colors):
            self['group_prop'] = len(arm.gamerig.colors)
        else:
            self['group_prop'] = value

    name : StringProperty(name="Layer Name", default=" ")
    row : IntProperty(name="Layer Row", default=1, min=1, max=32, description='UI row for this layer')
    selset : BoolProperty(name="Selection Set", default=False, description='Add Selection Set for this layer')
    group : IntProperty(
        name="Bone Group", default=0, min=0, max=32,
        get=get_group, set=set_group, description='Assign Bone Group to this layer'
    )


class ArmatureProperties(PropertyGroup):
    rig_ui_template : StringProperty(
        name="GameRig Rig UI Template",
        description="Rig UI Template for this armature"
    )
    rig_name : StringProperty(
        name="GameRig Rig Name",
        description="Defines the name of the Rig."
    )

    layers : CollectionProperty(type=ArmatureLayer)
    colors : CollectionProperty(type=ColorSet)
    selection_colors : PointerProperty(type=SelectionColors)
    colors_index : IntProperty(default=-1)
    colors_lock : BoolProperty(default=True)
    theme_to_add : EnumProperty(
        items=(
            ('THEME01', 'THEME01', ''),
            ('THEME02', 'THEME02', ''),
            ('THEME03', 'THEME03', ''),
            ('THEME04', 'THEME04', ''),
            ('THEME05', 'THEME05', ''),
            ('THEME06', 'THEME06', ''),
            ('THEME07', 'THEME07', ''),
            ('THEME08', 'THEME08', ''),
            ('THEME09', 'THEME09', ''),
            ('THEME10', 'THEME10', ''),
            ('THEME11', 'THEME11', ''),
            ('THEME12', 'THEME12', ''),
            ('THEME13', 'THEME13', ''),
            ('THEME14', 'THEME14', ''),
            ('THEME15', 'THEME15', ''),
            ('THEME16', 'THEME16', ''),
            ('THEME17', 'THEME17', ''),
            ('THEME18', 'THEME18', ''),
            ('THEME19', 'THEME19', ''),
            ('THEME20', 'THEME20', '')
        ),
        name='Theme'
    )

    @classmethod
    def register(cls):
        bpy.types.Armature.gamerig = PointerProperty(type=cls, name='GameRig Settings')

    @classmethod
    def unregister(cls):
        del bpy.types.Armature.gamerig


class PoseBoneProperties(PropertyGroup):

    @classmethod
    def register(cls):
        bpy.types.PoseBone.gamerig = PointerProperty(type=cls, name='GameRig Bone Attributes')

    @classmethod
    def unregister(cls):
        del bpy.types.PoseBone.gamerig


class GlobalProperties(PropertyGroup):
    category : EnumProperty(
        items=rig_lists.col_enum_list,
        default="All",
        name="GameRig Active Category",
        description="The selected rig category"
    )

    types : CollectionProperty(type=RigType)
    active_type : IntProperty(name="GameRig Active Rig", description="The selected rig type")

    show_layer_names_pane : BoolProperty(default=False)
    show_bone_groups_pane : BoolProperty(default=False)

    @classmethod
    def register(cls):
        # Sub-modules.
        ui.register()
        metarig_menu.register()

        bpy.types.WindowManager.gamerig = PointerProperty(type=cls)

        # Add rig parameters
        for rig in rig_lists.rig_list:
            r = utils.get_rig_type(rig)
            if hasattr(r, 'add_parameters'):
                r.add_parameters(PoseBoneProperties)
    
    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.gamerig

        # Sub-modules.
        metarig_menu.unregister()
        ui.unregister()
    
##### REGISTER #####

register, unregister = bpy.utils.register_classes_factory((
    RigType,
    ColorSet,
    SelectionColors,
    ArmatureLayer,
    ArmatureProperties,
    PoseBoneProperties,
    Preferences,
    GlobalProperties,
))
