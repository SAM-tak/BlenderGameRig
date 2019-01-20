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
    importlib.reload(generate)
    importlib.reload(ui)
    importlib.reload(utils)
    importlib.reload(metarig_menu)
    importlib.reload(rig_lists)
else:
    from . import utils, rig_lists, generate, ui, metarig_menu

import bpy
import sys
import os
from bpy.types import AddonPreferences
from bpy.props import (
    BoolProperty,
    IntProperty,
    EnumProperty,
    StringProperty,
    FloatVectorProperty,
    PointerProperty,
    CollectionProperty,
)


class GameRigPreferences(AddonPreferences):
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


class GameRigName(bpy.types.PropertyGroup):
    name : StringProperty()


class GameRigColorSet(bpy.types.PropertyGroup):
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


class GameRigSelectionColors(bpy.types.PropertyGroup):

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


class GameRigParameters(bpy.types.PropertyGroup):
    name : StringProperty()


class GameRigArmatureLayer(bpy.types.PropertyGroup):

    def get_group(self):
        if 'group_prop' in self.keys():
            return self['group_prop']
        else:
            return 0

    def set_group(self, value):
        arm = bpy.context.object.data
        if value > len(arm.gamerig_colors):
            self['group_prop'] = len(arm.gamerig_colors)
        else:
            self['group_prop'] = value

    name : StringProperty(name="Layer Name", default=" ")
    row : IntProperty(name="Layer Row", default=1, min=1, max=32, description='UI row for this layer')
    selset : BoolProperty(name="Selection Set", default=False, description='Add Selection Set for this layer')
    group : IntProperty(
        name="Bone Group", default=0, min=0, max=32,
        get=get_group, set=set_group, description='Assign Bone Group to this layer'
    )

class GameRigRigUITemplateName(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()


##### REGISTER #####

classes = (
    GameRigPreferences,
    GameRigName,
    GameRigParameters,
    GameRigColorSet,
    GameRigSelectionColors,
    GameRigArmatureLayer,
    GameRigRigUITemplateName,
)

def register():
    # Sub-modules.
    ui.register()
    metarig_menu.register()

    # Classes.
    for cl in classes:
        bpy.utils.register_class(cl)

    bpy.types.Armature.gamerig_rig_ui_template = StringProperty(
        name="GameRig Rig UI Template",
        description="Rig UI Template for this armature"
    )
    bpy.types.Armature.gamerig_rig_name = StringProperty(
        name="GameRig Rig Name",
        description="Defines the name of the Rig.",
        default="rig"
    )

    bpy.types.Armature.gamerig_layers = CollectionProperty(type=GameRigArmatureLayer)
    bpy.types.Armature.gamerig_colors = CollectionProperty(type=GameRigColorSet)
    bpy.types.Armature.gamerig_selection_colors = PointerProperty(type=GameRigSelectionColors)
    bpy.types.Armature.gamerig_colors_index = IntProperty(default=-1)
    bpy.types.Armature.gamerig_colors_lock = BoolProperty(default=True)
    bpy.types.Armature.gamerig_theme_to_add = EnumProperty(
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

    bpy.types.PoseBone.gamerig_type = StringProperty(name="GameRig Type", description="Rig type for this bone")
    bpy.types.PoseBone.gamerig_parameters = PointerProperty(type=GameRigParameters)

    IDStore = bpy.types.WindowManager
    IDStore.gamerig_collection = EnumProperty(
        items=rig_lists.col_enum_list, default="All",
        name="GameRig Active Collection",
        description="The selected rig collection"
    )

    IDStore.gamerig_types = CollectionProperty(type=GameRigName)
    IDStore.gamerig_active_type = IntProperty(name="GameRig Active Type", description="The selected rig type")
    IDStore.gamerig_rig_ui_template_list = CollectionProperty(type=GameRigRigUITemplateName)

    IDStore.gamerig_show_layer_names_pane = BoolProperty(default=False)
    IDStore.gamerig_show_bone_groups_pane = BoolProperty(default=False)

    # Add rig parameters
    for rig in rig_lists.rig_list:
        r = utils.get_rig_type(rig)
        try:
            r.add_parameters(GameRigParameters)
        except AttributeError:
            pass


def unregister():
    # Properties.
    del bpy.types.Armature.gamerig_rig_ui_template
    del bpy.types.Armature.gamerig_rig_name
    del bpy.types.Armature.gamerig_layers
    del bpy.types.Armature.gamerig_colors
    del bpy.types.Armature.gamerig_selection_colors
    del bpy.types.Armature.gamerig_colors_index
    del bpy.types.Armature.gamerig_colors_lock
    del bpy.types.Armature.gamerig_theme_to_add

    del bpy.types.PoseBone.gamerig_type
    del bpy.types.PoseBone.gamerig_parameters

    IDStore = bpy.types.WindowManager
    del IDStore.gamerig_collection
    del IDStore.gamerig_types
    del IDStore.gamerig_active_type
    del IDStore.gamerig_rig_ui_template_list
    del IDStore.gamerig_show_layer_names_pane
    del IDStore.gamerig_show_bone_groups_pane

    # Classes.
    for cl in classes:
        bpy.utils.unregister_class(cl)

    # Sub-modules.
    metarig_menu.unregister()
    ui.unregister()
