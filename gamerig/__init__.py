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
    "version": (1, 4, 1),
    "author": "Osamu Takasugi, (Rigify : Nathan Vegdahl, Lucio Rossi, Ivan Cappiello)",
    "blender": (3, 0, 0),
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
from bpy.types import (
    AddonPreferences,
    PropertyGroup
)
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
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


class ColorSet(PropertyGroup):
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


# Parameter update callback

in_update = False

def update_callback(prop_name):
    def callback(params, context):
        global in_update
        # Do not recursively call if the callback updates other parameters
        if not in_update:
            try:
                in_update = True
                bone = context.active_pose_bone

                if bone and bone.gamerig == params:
                    rig_info = rig_lists.rigs.get(utils.get_rig_type(bone), None)
                    if rig_info:
                        rig_cb = getattr(rig_info["module"].Rig, 'on_parameter_update', None)
                        if rig_cb:
                            rig_cb(context, bone, params, prop_name)
            finally:
                in_update = False

    return callback

# Remember the initial property set
PARAMETERS_BASE_DIR = set(dir(PoseBoneProperties))

PARAMETER_TABLE = {'name': ('DEFAULT', StringProperty())}

def clear_parameters():
    for name in list(dir(PoseBoneProperties)):
        if name not in PARAMETERS_BASE_DIR:
            delattr(PoseBoneProperties, name)
            if name in PARAMETER_TABLE:
                del PARAMETER_TABLE[name]


def format_property_spec(spec):
    """Turns the return value of bpy.props.SomeProperty(...) into a readable string."""
    callback, params = spec
    param_str = ["%s=%r" % (k, v) for k, v in params.items()]
    return "%s(%s)" % (callback.__name__, ', '.join(param_str))


class ParameterValidator(object):
    """
    A wrapper around ParameterValidator that verifies properties
    defined from rigs for incompatible redefinitions using a table.

    Relies on the implementation details of bpy.props return values:
    specifically, they just return a tuple containing the real define
    function, and a dictionary with parameters. This allows comparing
    parameters before the property is actually defined.
    """
    __params = None
    __rig_name = ''
    __prop_table = {}

    def __init__(self, params, rig_name, prop_table):
        self.__params = params
        self.__rig_name = rig_name
        self.__prop_table = prop_table

    def __getattr__(self, name):
        return getattr(self.__params, name)

    def __setattr__(self, name, val):
        # allow __init__ to work correctly
        if hasattr(ParameterValidator, name):
            return object.__setattr__(self, name, val)

        original_val = val

        # to support 2.93.0 later
        if isinstance(val, bpy.props._PropertyDeferred):
            val = (val.function, val.keywords)
        
        if not (isinstance(val, tuple) and callable(val[0]) and isinstance(val[1], dict)):
            print("!!! GAMERIG RIG %s: INVALID DEFINITION FOR RIG PARAMETER %s: %r\n" % (self.__rig_name, name, val))
            return

        # actually defining the property modifies the dictionary with new parameters, so copy it now
        new_def = (val[0], val[1].copy())

        if 'poll' in new_def[1]:
            del new_def[1]['poll']
        
        if name in self.__prop_table:
            cur_rig, cur_info = self.__prop_table[name]
            if val != cur_info:
                print("!!! GAMERIG RIG %s: REDEFINING PARAMETER %s AS:\n\n    %s\n" % (self.__rig_name, name, format_property_spec(val)))
                print("!!! PREVIOUS DEFINITION BY %s:\n\n    %s\n" % (cur_rig, format_property_spec(cur_info)))

        # inject a generic update callback that calls the appropriate rig classmethod
        if val[0] != bpy.props.CollectionProperty:
            val[1]['update'] = update_callback(name)

        setattr(self.__params, name, original_val)
        self.__prop_table[name] = (self.__rig_name, new_def)


class GlobalProperties(PropertyGroup):
    category : EnumProperty(
        items=rig_lists.col_enum_list,
        default="All",
        name="GameRig Active Category",
        description="The selected rig category"
    )

    types : CollectionProperty(type=PropertyGroup)
    active_type : IntProperty(name="GameRig Active Rig", description="The selected rig type")

    show_layer_names_pane : BoolProperty(default=False)
    show_bone_groups_pane : BoolProperty(default=False)

    rename_batch_find : StringProperty(name="Find", description="target string for replace")
    rename_batch_replace : StringProperty(name="Replace", description="replace string")
    rename_batch_re : BoolProperty(name="Regular expression", description="Use regular expression")

    # Properties.
    q2e_order_list : EnumProperty(
        items=(
            ('QUATERNION', 'QUATERNION', 'QUATERNION'),
            ('XYZ', 'XYZ', 'XYZ'),
            ('XZY', 'XZY', 'XZY'),
            ('YXZ', 'YXZ', 'YXZ'),
            ('YZX', 'YZX', 'YZX'),
            ('ZXY', 'ZXY', 'ZXY'),
            ('ZYX', 'ZYX', 'ZYX'),
        ),
        name='Convert to',
        description="The target rotation mode", default='QUATERNION'
    )
    q2e_convert_only_selected : BoolProperty(name="Convert Only Selected", description="Convert selected bones only", default=True)

    # a value between [0,100] will show the slider  
    progress_indicator : FloatProperty(
        name="GameRig : Generating",
        subtype='PERCENTAGE',
        default=-1,
        precision=1,
        soft_min=0,
        soft_max=100,
        min=-1,
        max=101,
    )

    @classmethod
    def register(cls):
        bpy.types.WindowManager.gamerig = PointerProperty(type=cls)

        # Sub-modules.
        ui.register()
        metarig_menu.register()

        # Add rig parameters
        for rig in rig_lists.rig_list:
            r = utils.get_rig_type(rig)
            if hasattr(r, 'add_parameters'):
                r.add_parameters(ParameterValidator(PoseBoneProperties, rig, PARAMETER_TABLE))
    
    @classmethod
    def unregister(cls):
        clear_parameters()

        # Sub-modules.
        metarig_menu.unregister()
        ui.unregister()

        del bpy.types.WindowManager.gamerig


##### REGISTER #####

register, unregister = bpy.utils.register_classes_factory((
    ColorSet,
    SelectionColors,
    ArmatureLayer,
    ArmatureProperties,
    PoseBoneProperties,
    Preferences,
    GlobalProperties,
))
