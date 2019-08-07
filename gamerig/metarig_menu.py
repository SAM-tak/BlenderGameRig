# ##### BEGIN GPL LICENSE BLOCK #####
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
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import os
from string import capwords

import bpy

from . import utils

class ArmatureMainMenu(bpy.types.Menu):
    bl_idname = 'ARMATURE_MT_GameRig_class'
    bl_label = 'GameRig'
    submenus = []
    operators = []

    def draw(self, context):
        layout = self.layout
        for cl in self.submenus:
            layout.menu(cl.bl_idname, icon='OUTLINER_OB_ARMATURE')
        for op, name, text in self.operators:
            icon='BONE_DATA' if name == 'single_bone' else 'OUTLINER_OB_ARMATURE'
            layout.operator(op, icon=icon, text=text)


def mainmenu_func(self, context):
    self.layout.menu(ArmatureMainMenu.bl_idname, icon='OUTLINER_OB_ARMATURE')


class ArmatureSubMenu(bpy.types.Menu):
    def draw(self, context):
        layout = self.layout
        for op, name, text in self.operators:
            icon='BONE_DATA' if name == 'single_bone' else 'OUTLINER_OB_ARMATURE'
            layout.operator(op, icon=icon, text=text)


def get_metarig_list(path, depth=0):
    """ Searches for metarig modules, and returns a list of the
        imported modules.
    """
    metarigs = []
    metarigs_dict = dict()
    MODULE_DIR = os.path.dirname(__file__)
    METARIG_DIR_ABS = os.path.join(MODULE_DIR, utils.METARIG_DIR)
    SEARCH_DIR_ABS = os.path.join(METARIG_DIR_ABS, path)
    files = os.listdir(SEARCH_DIR_ABS)
    files.sort()

    for f in files:
        # Is it a directory?
        complete_path = os.path.join(SEARCH_DIR_ABS, f)
        if os.path.isdir(complete_path) and depth == 0:
            if f[0] != '_':
                metarigs_dict[f] = get_metarig_list(f, depth=1)
            else:
                continue
        elif not f.endswith(".py"):
            continue
        elif f == "__init__.py":
            continue
        else:
            module_name = f[:-3]
            try:
                if depth == 1:
                    metarigs.append(utils.get_metarig_module(module_name, utils.METARIG_DIR + '.' + path))
                else:
                    metarigs.append(utils.get_metarig_module(module_name, utils.METARIG_DIR))
            except ImportError:
                pass

    if depth == 1:
        return metarigs

    metarigs_dict[utils.METARIG_DIR] = metarigs
    return metarigs_dict


class AddMetarigOperatorBase(bpy.types.Operator):
    @classmethod
    def poll(cls, context):
        return not context.object or context.object.mode == 'OBJECT'


def make_metarig_add_execute(m):
    """ Create an execute method for a metarig creation operator.
    """
    def execute(self, context):
        # Add armature object
        bpy.ops.object.armature_add()
        obj = context.active_object
        obj.name = "metarig"
        obj.data.name = "metarig"

        # Remove default bone
        bpy.ops.object.mode_set(mode='EDIT')
        bones = context.active_object.data.edit_bones
        bones.remove(bones[0])

        # Create metarig
        m.create(obj)

        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
    return execute


# Get the metarig modules
metarigs_dict = get_metarig_list("")

# Create metarig add Operators
metarig_ops = {}
for metarig_class in metarigs_dict:
    metarig_ops[metarig_class] = []
    for m in metarigs_dict[metarig_class]:
        name = '_D_'.join(m.__name__.split('.')[2:]).replace(' ', '_')
        text = ' '.join((i.capitalize() for i in m.__name__.rsplit('.', 1)[-1].split('_'))) + " (Meta Rig)"

        # Dynamically construct an Operator
        T = type("GameRig_Add_" + name + "_Metarig", (AddMetarigOperatorBase,), {})
        T.bl_idname = "gamerig." + name.lower() + "_metarig_add"
        T.bl_label = "Add " + text
        T.bl_options = {'REGISTER', 'UNDO'}
        T.execute = make_metarig_add_execute(m)

        metarig_ops[metarig_class].append((T, name, text))


for mop, name, text in metarig_ops[utils.METARIG_DIR]:
    ArmatureMainMenu.operators.append((mop.bl_idname, name, text))

metarigs_dict.pop(utils.METARIG_DIR)

for submenu_name in sorted(list(metarigs_dict.keys())):
    # Create menu functions
    armature_submenu = type('Class_GameRig_' + submenu_name + '_submenu', (ArmatureSubMenu,), {})
    armature_submenu.bl_label = submenu_name
    idname = '_D_'.join(submenu_name.split('.')[2:]).replace(' ', '_')
    armature_submenu.bl_idname = 'ARMATURE_MT_GameRig_%s_class' % idname
    armature_submenu.operators = [(mop.bl_idname, name, text) for mop, name, text in metarig_ops[submenu_name]]
    ArmatureMainMenu.submenus.append(armature_submenu)

def register():
    for op in metarig_ops:
        for cl, name, text in metarig_ops[op]:
            bpy.utils.register_class(cl)

    for arm_sub in ArmatureMainMenu.submenus:
        bpy.utils.register_class(arm_sub)

    bpy.utils.register_class(ArmatureMainMenu)

    bpy.types.VIEW3D_MT_armature_add.append(mainmenu_func)


def unregister():
    for op in metarig_ops:
        for cl, name, text in metarig_ops[op]:
            bpy.utils.unregister_class(cl)

    for arm_sub in ArmatureMainMenu.submenus:
        bpy.utils.unregister_class(arm_sub)

    bpy.utils.unregister_class(ArmatureMainMenu)

    bpy.types.VIEW3D_MT_armature_add.remove(mainmenu_func)
