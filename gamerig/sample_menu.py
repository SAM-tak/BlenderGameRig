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

import bpy

from . import utils, rig_lists


class GAMERIG_MT_SampleRigs(bpy.types.Menu):
    bl_label = 'GameRig'
    submenus = []
    operators = []

    def draw(self, context):
        layout = self.layout
        for cl in self.submenus:
            layout.menu(cl.bl_idname, icon='BONE_DATA')
        for op, name, text in self.operators:
            layout.operator(op, icon='BONE_DATA', text=text)


def editmenu_func(self, context):
    self.layout.menu("GAMERIG_MT_SampleRigs", icon='BONE_DATA')


class SampleSubMenu(bpy.types.Menu):
    def draw(self, context):
        layout = self.layout
        for op, name, text in self.operators:
            layout.operator(op, icon='BONE_DATA', text=text)


class AddSampleOperatorBase(bpy.types.Operator):
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_ARMATURE'


def make_sample_add_execute(rig_type_name):
    """Create an execute method for a rig sample creation operator."""
    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            rig = utils.get_rig_type(rig_type_name)
            rig.create_sample(context.active_object)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
    return execute


# Collect rigs that expose create_sample, grouped by sub-directory.
# rig_list entries use dot notation for sub-dirs: 'face', 'limbs.arm', etc.
_top_ops = []       # list of (OperatorClass, rig_name, display_text)
_sub_ops  = {}      # dict[subdir_str] -> list of (OperatorClass, rig_name, display_text)

for _rig_name in rig_lists.rig_list:
    _rig_module = utils.get_rig_type(_rig_name)
    if not hasattr(_rig_module, 'create_sample'):
        continue

    _leaf = _rig_name.rsplit('.', 1)[-1]
    _text = ' '.join(i.capitalize() for i in _leaf.split('_')) + " (Sample)"
    _safe  = _rig_name.replace('.', '_D_').replace(' ', '_')

    T = type("GameRig_Add_" + _safe + "_Sample", (AddSampleOperatorBase,), {})
    T.bl_idname     = "gamerig." + _safe.lower() + "_sample_add"
    T.bl_label      = "Add " + _text
    T.bl_description = "Add a sample rig for '%s' to the active armature" % _rig_name
    T.bl_options    = {'REGISTER', 'UNDO'}
    T.execute       = make_sample_add_execute(_rig_name)

    if '.' in _rig_name:
        _subdir = _rig_name.split('.')[0]
        _sub_ops.setdefault(_subdir, []).append((T, _rig_name, _text))
    else:
        _top_ops.append((T, _rig_name, _text))

# Register top-level operators into the main menu
for _op, _name, _text in _top_ops:
    GAMERIG_MT_SampleRigs.operators.append((_op.bl_idname, _name, _text))

# Build sub-menus for each sub-directory
for _subdir_name in sorted(_sub_ops.keys()):
    _submenu = type(
        'Class_GameRig_' + _subdir_name + '_sample_submenu',
        (SampleSubMenu,),
        {}
    )
    _submenu.bl_label    = _subdir_name.capitalize()
    _safe_id             = _subdir_name.replace(' ', '_')
    _submenu.bl_idname   = 'GAMERIG_MT_SampleRigs_%s' % _safe_id
    _submenu.operators   = [(_op.bl_idname, _name, _text) for _op, _name, _text in _sub_ops[_subdir_name]]
    GAMERIG_MT_SampleRigs.submenus.append(_submenu)


def register():
    for op, name, text in _top_ops:
        bpy.utils.register_class(op)
    for ops in _sub_ops.values():
        for op, name, text in ops:
            bpy.utils.register_class(op)
    for arm_sub in GAMERIG_MT_SampleRigs.submenus:
        bpy.utils.register_class(arm_sub)
    bpy.utils.register_class(GAMERIG_MT_SampleRigs)
    bpy.types.TOPBAR_MT_edit_armature_add.append(editmenu_func)


def unregister():
    bpy.types.TOPBAR_MT_edit_armature_add.remove(editmenu_func)
    bpy.utils.unregister_class(GAMERIG_MT_SampleRigs)
    for arm_sub in reversed(GAMERIG_MT_SampleRigs.submenus):
        bpy.utils.unregister_class(arm_sub)
    for ops in _sub_ops.values():
        for op, name, text in ops:
            bpy.utils.unregister_class(op)
    for op, name, text in _top_ops:
        bpy.utils.unregister_class(op)
