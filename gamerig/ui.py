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

import bpy
from bpy.props import BoolProperty, IntProperty, EnumProperty, StringProperty
from mathutils import Color

from .utils import (
    get_rig_type, MetarigError, write_metarig, write_widget, unique_name, get_keyed_frames,
    bones_in_frame, overwrite_prop_animation, unlink_all_widgets
)
from . import rig_lists, generate


class DATA_PT_gamerig(bpy.types.Panel):
    bl_label = "GameRig"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'\
            and context.active_object.data.get("gamerig_rig_ui_template") is not None

    def draw(self, context):
        C = context
        layout = self.layout
        obj = context.object
        id_store = C.window_manager
        armature = obj.data

        ## Layers
        # Ensure that the layers exist
        box = layout.box()
        show = id_store.gamerig_show_layer_names_pane
        row = box.row()
        row.prop(id_store, "gamerig_show_layer_names_pane", text="", toggle=True, icon='TRIA_DOWN' if show else 'TRIA_RIGHT', emboss=False)
        row.alignment = 'LEFT'
        row.label('Layer Names')
        if 0:
            for i in range(1 + len(armature.gamerig_layers), 29):
                armature.gamerig_layers.add()
        else:
            # Can't add while drawing, just use button
            if len(armature.gamerig_layers) < 29:
                layout.operator("pose.gamerig_layer_init")
                show = False
        if show:
            # UI
            main_row = box.row(align=True).split(0.06)
            col1 = main_row.column()
            col2 = main_row.column()
            col1.label()
            for i in range(31):
                if i == 16 or i == 29:
                    col1.label()
                col1.label(str(i+1))

            for i, gamerig_layer in enumerate(armature.gamerig_layers):
                # note: gamerig_layer == armature.gamerig_layers[i]
                if (i % 16) == 0:
                    col = col2.column()
                    if i == 0:
                        col.label(text="Top Row:")
                    else:
                        col.label(text="Bottom Row:")
                if (i % 8) == 0:
                    col = col2.column()
                if i != 28:
                    row = col.row(align=True)
                    icon = 'RESTRICT_VIEW_OFF' if armature.layers[i] else 'RESTRICT_VIEW_ON'
                    row.prop(armature, "layers", index=i, text="", toggle=True, icon=icon)
                    #row.prop(armature, "layers", index=i, text="Layer %d" % (i + 1), toggle=True, icon=icon)
                    row.prop(gamerig_layer, "name", text="")
                    row.prop(gamerig_layer, "row", text="UI Row")
                    icon = 'RADIOBUT_ON' if gamerig_layer.selset else 'RADIOBUT_OFF'
                    row.prop(gamerig_layer, "selset", text="", toggle=True, icon=icon)
                    row.prop(gamerig_layer, "group", text="Bone Group")
                else:
                    row = col.row(align=True)

                    icon = 'RESTRICT_VIEW_OFF' if armature.layers[i] else 'RESTRICT_VIEW_ON'
                    row.prop(armature, "layers", index=i, text="", toggle=True, icon=icon)
                    # row.prop(armature, "layers", index=i, text="Layer %d" % (i + 1), toggle=True, icon=icon)
                    row1 = row.split(align=True).row(align=True)
                    row1.prop(gamerig_layer, "name", text="")
                    row1.prop(gamerig_layer, "row", text="UI Row")
                    row1.enabled = False
                    icon = 'RADIOBUT_ON' if gamerig_layer.selset else 'RADIOBUT_OFF'
                    row.prop(gamerig_layer, "selset", text="", toggle=True, icon=icon)
                    row.prop(gamerig_layer, "group", text="Bone Group")
                if gamerig_layer.group == 0:
                    row.label(text='None')
                else:
                    row.label(text=armature.gamerig_colors[gamerig_layer.group-1].name)

            # buttons
            col = col2.column()
            col.label(text="Reserved:")
            reserved_names = {30: 'MCH', 31: 'ORG'}
            for i in range(30, 32):
                row = col.row(align=True)
                icon = 'RESTRICT_VIEW_OFF' if armature.layers[i] else 'RESTRICT_VIEW_ON'
                row.prop(armature, "layers", index=i, text="", toggle=True, icon=icon)
                row.label(text=reserved_names[i])

        ## Bone Groups
        box = layout.box()
        show = id_store.gamerig_show_bone_groups_pane
        row = box.row()
        row.prop(id_store, "gamerig_show_bone_groups_pane", text="", toggle=True, icon='TRIA_DOWN' if show else 'TRIA_RIGHT', emboss=False)
        row.alignment = 'LEFT'
        row.label('Bone Groups')
        if show:
            color_sets = obj.data.gamerig_colors
            idx = obj.data.gamerig_colors_index

            row = box.row()
            row.operator("armature.gamerig_use_standard_colors", icon='FILE_REFRESH', text='')
            row = row.row(align=True)
            row.prop(armature.gamerig_selection_colors, 'select', text='')
            row.prop(armature.gamerig_selection_colors, 'active', text='')
            row = box.row(align=True)
            icon = 'LOCKED' if armature.gamerig_colors_lock else 'UNLOCKED'
            row.prop(armature, 'gamerig_colors_lock', text = 'Unified select/active colors', icon=icon)
            row.operator("armature.gamerig_apply_selection_colors", icon='FILE_REFRESH', text='Apply')
            row = box.row()
            row.template_list("DATA_UL_gamerig_bone_groups", "", obj.data, "gamerig_colors", obj.data, "gamerig_colors_index")

            col = row.column(align=True)
            col.operator("armature.gamerig_bone_group_add", icon='ZOOMIN', text="")
            col.operator("armature.gamerig_bone_group_remove", icon='ZOOMOUT', text="").idx = obj.data.gamerig_colors_index
            col.menu("DATA_MT_gamerig_bone_groups_specials", icon='DOWNARROW_HLT', text="")
            row = box.row()
            row.prop(armature, 'gamerig_theme_to_add', text = 'Theme')
            op = row.operator("armature.gamerig_bone_group_add_theme", text="Add From Theme")
            op.theme = armature.gamerig_theme_to_add
            row = box.row()
            row.operator("armature.gamerig_add_bone_groups", text="Add Standard")

        ## Generation
        if obj.mode in {'POSE', 'OBJECT'}:
            rig_id = obj.data.get('gamerig_id')
            target = next((i for i in C.scene.objects if i != obj and 'gamerig_id' in i.data and i.data['gamerig_id'] == rig_id), None) if rig_id else None
            if target:
                layout.row().operator("pose.gamerig_generate", text="Regenerate Rig", icon='POSE_HLT')
                layout.row().box().label(text="Overwrite to '%s'" % target.name, icon='INFO')
            else:
                layout.row().operator("pose.gamerig_generate", text="Generate Rig", icon='POSE_HLT')
                layout.row().prop(obj.data, "gamerig_rig_name", text="Rig Name")

        elif obj.mode == 'EDIT':
            # Build types list
            collection_name = str(id_store.gamerig_collection).replace(" ", "")

            for i in range(0, len(id_store.gamerig_types)):
                id_store.gamerig_types.remove(0)

            for r in rig_lists.rig_list:

                if collection_name == "All":
                    a = id_store.gamerig_types.add()
                    a.name = r
                elif r.startswith(collection_name + '.'):
                    a = id_store.gamerig_types.add()
                    a.name = r
                elif (collection_name == "None") and ("." not in r):
                    a = id_store.gamerig_types.add()
                    a.name = r

            # Rig type list
            layout.row().template_list("UI_UL_list", "gamerig_types", id_store, "gamerig_types", id_store, 'gamerig_active_type')

            props = layout.operator("armature.gamerig_metarig_sample_add", text="Add sample")
            props.metarig_type = id_store.gamerig_types[id_store.gamerig_active_type].name


class DATA_OT_gamerig_add_bone_groups(bpy.types.Operator):
    bl_idname = "armature.gamerig_add_bone_groups"
    bl_label  = "GameRig Add Standard Bone Groups"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'gamerig_colors'):
            return {'FINISHED'}

        groups = ['Root', 'IK', 'Special', 'Tweak', 'FK', 'Extra']

        for g in groups:
            if g in armature.gamerig_colors.keys():
                continue

            armature.gamerig_colors.add()
            armature.gamerig_colors[-1].name = g

            armature.gamerig_colors[g].select = Color((0.3140000104904175, 0.7839999794960022, 1.0))
            armature.gamerig_colors[g].active = Color((0.5490000247955322, 1.0, 1.0))
            armature.gamerig_colors[g].standard_colors_lock = True

            if g == "Root":
                armature.gamerig_colors[g].normal = Color((0.43529415130615234, 0.18431372940540314, 0.41568630933761597))
            if g == "IK":
                armature.gamerig_colors[g].normal = Color((0.6039215922355652, 0.0, 0.0))
            if g== "Special":
                armature.gamerig_colors[g].normal = Color((0.9568628072738647, 0.7882353663444519, 0.0470588281750679))
            if g== "Tweak":
                armature.gamerig_colors[g].normal = Color((0.03921568766236305, 0.21176472306251526, 0.5803921818733215))
            if g== "FK":
                armature.gamerig_colors[g].normal = Color((0.11764706671237946, 0.5686274766921997, 0.03529411926865578))
            if g== "Extra":
                armature.gamerig_colors[g].normal = Color((0.9686275124549866, 0.250980406999588, 0.0941176563501358))

        return {'FINISHED'}


class DATA_OT_gamerig_use_standard_colors(bpy.types.Operator):
    bl_idname = "armature.gamerig_use_standard_colors"
    bl_label  = "GameRig Get active/select colors from current theme"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'gamerig_colors'):
            return {'FINISHED'}

        current_theme = bpy.context.user_preferences.themes.items()[0][0]
        theme = bpy.context.user_preferences.themes[current_theme]

        armature.gamerig_selection_colors.select = theme.view_3d.bone_pose
        armature.gamerig_selection_colors.active = theme.view_3d.bone_pose_active

        # for col in armature.gamerig_colors:
        #     col.select = theme.view_3d.bone_pose
        #     col.active = theme.view_3d.bone_pose_active

        return {'FINISHED'}


class DATA_OT_gamerig_apply_selection_colors(bpy.types.Operator):
    bl_idname = "armature.gamerig_apply_selection_colors"
    bl_label  = "GameRig Apply user defined active/select colors"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'gamerig_colors'):
            return {'FINISHED'}

        #current_theme = bpy.context.user_preferences.themes.items()[0][0]
        #theme = bpy.context.user_preferences.themes[current_theme]

        for col in armature.gamerig_colors:
            col.select = armature.gamerig_selection_colors.select
            col.active = armature.gamerig_selection_colors.active

        return {'FINISHED'}


class DATA_OT_gamerig_bone_group_add(bpy.types.Operator):
    bl_idname = "armature.gamerig_bone_group_add"
    bl_label  = "GameRig Add Bone Group color set"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data

        if hasattr(armature, 'gamerig_colors'):
            armature.gamerig_colors.add()
            armature.gamerig_colors[-1].name = unique_name(armature.gamerig_colors, 'Group')

            current_theme = bpy.context.user_preferences.themes.items()[0][0]
            theme = bpy.context.user_preferences.themes[current_theme]

            armature.gamerig_colors[-1].normal = theme.view_3d.wire
            armature.gamerig_colors[-1].normal.hsv = theme.view_3d.wire.hsv
            armature.gamerig_colors[-1].select = theme.view_3d.bone_pose
            armature.gamerig_colors[-1].select.hsv = theme.view_3d.bone_pose.hsv
            armature.gamerig_colors[-1].active = theme.view_3d.bone_pose_active
            armature.gamerig_colors[-1].active.hsv = theme.view_3d.bone_pose_active.hsv

        return {'FINISHED'}


class DATA_OT_gamerig_bone_group_add_theme(bpy.types.Operator):
    bl_idname  = "armature.gamerig_bone_group_add_theme"
    bl_label   = "GameRig Add Bone Group color set from Theme"
    bl_options = {"REGISTER", "UNDO"}

    theme = EnumProperty(
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
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data

        if hasattr(armature, 'gamerig_colors'):

            if self.theme in armature.gamerig_colors.keys():
                return {'FINISHED'}
            armature.gamerig_colors.add()
            armature.gamerig_colors[-1].name = self.theme

            id = int(self.theme[-2:]) - 1

            theme_color_set = bpy.context.user_preferences.themes[0].bone_color_sets[id]

            armature.gamerig_colors[-1].normal = theme_color_set.normal
            armature.gamerig_colors[-1].select = theme_color_set.select
            armature.gamerig_colors[-1].active = theme_color_set.active

        return {'FINISHED'}


class DATA_OT_gamerig_bone_group_remove(bpy.types.Operator):
    bl_idname = "armature.gamerig_bone_group_remove"
    bl_label  = "GameRig Remove Bone Group color set"

    idx = IntProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        obj.data.gamerig_colors.remove(self.idx)

        # set layers references to 0
        for l in obj.data.gamerig_layers:
            if l.group == self.idx + 1:
                l.group = 0
            elif l.group > self.idx + 1:
                l.group -= 1

        return {'FINISHED'}


class DATA_OT_gamerig_bone_group_remove_all(bpy.types.Operator):
    bl_idname = "armature.gamerig_bone_group_remove_all"
    bl_label  = "GameRig Remove All Bone Groups"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object

        for i, col in enumerate(obj.data.gamerig_colors):
            obj.data.gamerig_colors.remove(0)
            # set layers references to 0
            for l in obj.data.gamerig_layers:
                if l.group == i + 1:
                    l.group = 0

        return {'FINISHED'}


class DATA_UL_gamerig_bone_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row = row.split(percentage=0.1)
        row.label(text=str(index+1))
        row = row.split(percentage=0.7)
        row.prop(item, "name", text='', emboss=False)
        row = row.row(align=True)
        icon = 'LOCKED' if item.standard_colors_lock else 'UNLOCKED'
        #row.prop(item, "standard_colors_lock", text='', icon=icon)
        row.prop(item, "normal", text='')
        row2 = row.row(align=True)
        row2.prop(item, "select", text='')
        row2.prop(item, "active", text='')
        #row2.enabled = not item.standard_colors_lock
        row2.enabled = not bpy.context.object.data.gamerig_colors_lock


class DATA_MT_gamerig_bone_groups_specials(bpy.types.Menu):
    bl_label = 'GameRig Bone Groups Specials'

    def draw(self, context):
        layout = self.layout

        layout.operator('armature.gamerig_bone_group_remove_all')


class BONE_PT_gamerig_type(bpy.types.Panel):
    bl_label       = "GameRig Type"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = "bone"
    #bl_options    = {'DEFAULT_OPEN'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.active_pose_bone\
            and context.active_object.data.get("gamerig_rig_ui_template") is not None

    def draw(self, context):
        C = context
        id_store = C.window_manager
        bone = context.active_pose_bone
        collection_name = str(id_store.gamerig_collection).replace(" ", "")
        rig_name = str(context.active_pose_bone.gamerig_type).replace(" ", "")

        layout = self.layout

        # Build types list
        for i in range(0, len(id_store.gamerig_types)):
            id_store.gamerig_types.remove(0)

        for r in rig_lists.rig_list:
            if r in rig_lists.implementation_rigs:
                continue
            # collection = r.split('.')[0]  # UNUSED
            if collection_name == "All":
                a = id_store.gamerig_types.add()
                a.name = r
            elif r.startswith(collection_name + '.'):
                a = id_store.gamerig_types.add()
                a.name = r
            elif collection_name == "None" and len(r.split('.')) == 1:
                a = id_store.gamerig_types.add()
                a.name = r
        
        # Rig collection field
        row = layout.row()
        row.prop(id_store, 'gamerig_collection', text="Category")

        # Rig type field
        row = layout.row()
        row.prop_search(bone, "gamerig_type", id_store, "gamerig_types", text="Rig type:")

        # Rig type parameters / Rig type non-exist alert
        if rig_name != "":
            try:
                rig = get_rig_type(rig_name)
                rig.Rig
            except (ImportError, AttributeError):
                row = layout.row()
                box = row.box()
                box.label(text="ALERT: type \"%s\" does not exist!" % rig_name)
            else:
                try:
                    rig.parameters_ui
                except AttributeError:
                    col = layout.column()
                    col.label(text="No options")
                else:
                    col = layout.column()
                    col.label(text="Options:")
                    box = layout.box()
                    rig.parameters_ui(box, bone.gamerig_parameters)


class VIEW3D_PT_gamerig_dev_tools(bpy.types.Panel):
    bl_label       = "GameRig Dev Tools"
    bl_category    = 'Tools'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'

    @classmethod
    def poll(cls, context):
        return context.mode in ['EDIT_ARMATURE', 'EDIT_MESH'] and context.user_preferences.addons['gamerig'].preferences.shows_dev_tools

    def draw(self, context):
        obj = context.active_object
        if obj is not None:
            if context.mode == 'EDIT_ARMATURE':
                r = self.layout.row()
                r.operator("armature.gamerig_encode_metarig", text="Encode Metarig to Python")
                r = self.layout.row()
                r.operator("armature.gamerig_encode_metarig_sample", text="Encode Sample to Python")

            if context.mode == 'EDIT_MESH':
                r = self.layout.row()
                r.operator("mesh.gamerig_encode_mesh_widget", text="Encode Mesh Widget to Python")


def gamerig_report_exception(operator, exception):
    import traceback
    import sys
    import os
    # find the module name where the error happened
    # hint, this is the metarig type!
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    fn = traceback.extract_tb(exceptionTraceback)[-1][0]
    fn = os.path.basename(fn)
    fn = os.path.splitext(fn)[0]
    message = []
    if fn.startswith("__"):
        message.append("Incorrect armature...")
    else:
        message.append("Incorrect armature for type '%s'" % fn)
    message.append(exception.message)

    message.reverse()  # XXX - stupid! menu's are upside down!

    operator.report({'INFO'}, '\n'.join(message))


class LayerInit(bpy.types.Operator):
    """Initialize armature gamerig layers"""

    bl_idname  = "pose.gamerig_layer_init"
    bl_label   = "Add GameRig Layers"
    bl_options = {'UNDO'}

    def execute(self, context):
        obj = context.object
        arm = obj.data
        for i in range(1 + len(arm.gamerig_layers), 30):
            arm.gamerig_layers.add()
        arm.gamerig_layers[28].name = 'Root'
        arm.gamerig_layers[28].row = 14
        return {'FINISHED'}


class Generate(bpy.types.Operator):
    """Generates a rig from the active metarig armature"""

    bl_idname      = "pose.gamerig_generate"
    bl_label       = "GameRig Generate Rig"
    bl_options     = {'UNDO'}
    bl_description = 'Generates a rig from the active metarig armature'

    @classmethod
    def poll(cls, context):
        return not context.object.hide and not context.object.hide_select

    def execute(self, context):
        import importlib
        importlib.reload(generate)

        use_global_undo = context.user_preferences.edit.use_global_undo
        context.user_preferences.edit.use_global_undo = False
        try:
            generate.generate_rig(context, context.object)
            unlink_all_widgets()
        except MetarigError as rig_exception:
            gamerig_report_exception(self, rig_exception)
        finally:
            context.user_preferences.edit.use_global_undo = use_global_undo

        return {'FINISHED'}


class ToggleArmatureReference(bpy.types.Operator):
    """Toggle armature reference between metarig and generated rig."""

    bl_idname  = "pose.gamerig_toggle_armature"
    bl_label   = "GameRig Toggle Rig"
    bl_options = {'UNDO'}

    def execute(self, context):
        metarig = context.object
        if 'gamerig_id' in metarig.data:
            rig_id = metarig.data['gamerig_id']
            genrig = next((i for i in context.scene.objects if i and i != metarig and i.data and 'gamerig_id' in i.data and i.data['gamerig_id'] == rig_id), None)
            if genrig is not None:
                for i in context.scene.objects:
                    for j in i.modifiers:
                        if j.type == 'ARMATURE':
                            if j.object == genrig:
                                j.object = metarig
                            elif j.object == metarig:
                                j.object = genrig

        return {'FINISHED'}


class Sample(bpy.types.Operator):
    """Create a sample metarig to be modified before generating """ \
    """the final rig"""

    bl_idname  = "armature.gamerig_metarig_sample_add"
    bl_label   = "Add a sample metarig for a rig type"
    bl_options = {'UNDO'}

    metarig_type = StringProperty(
        name="Type",
        description="Name of the rig type to generate a sample of",
        maxlen=128,
    )

    def execute(self, context):
        if context.mode == 'EDIT_ARMATURE' and self.metarig_type != "":
            use_global_undo = context.user_preferences.edit.use_global_undo
            context.user_preferences.edit.use_global_undo = False
            try:
                rig = get_rig_type(self.metarig_type)
                create_sample = rig.create_sample
            except (ImportError, AttributeError):
                raise Exception("rig type '" + self.metarig_type + "' has no sample.")
            else:
                create_sample(context.active_object)
            finally:
                context.user_preferences.edit.use_global_undo = use_global_undo
                bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarig(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname  = "armature.gamerig_encode_metarig"
    bl_label   = "GameRig Encode Metarig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_ARMATURE'

    def execute(self, context):
        name = "metarig.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_metarig(context.active_object, layers=True, func_name="create", groups=True)
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarigSample(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig
        as a sample.
    """
    bl_idname  = "armature.gamerig_encode_metarig_sample"
    bl_label   = "GameRig Encode Metarig Sample"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_ARMATURE'

    def execute(self, context):
        name = "metarig_sample.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_metarig(context.active_object, layers=False, func_name="create_sample")
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeWidget(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname  = "mesh.gamerig_encode_mesh_widget"
    bl_label   = "GameRig Encode Widget"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        name = "widget.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_widget(context.active_object)
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

### Registering ###

classes = (
    DATA_OT_gamerig_add_bone_groups,
    DATA_OT_gamerig_use_standard_colors,
    DATA_OT_gamerig_apply_selection_colors,
    DATA_OT_gamerig_bone_group_add,
    DATA_OT_gamerig_bone_group_add_theme,
    DATA_OT_gamerig_bone_group_remove,
    DATA_OT_gamerig_bone_group_remove_all,
    DATA_UL_gamerig_bone_groups,
    DATA_MT_gamerig_bone_groups_specials,
    DATA_PT_gamerig,
    BONE_PT_gamerig_type,
    VIEW3D_PT_gamerig_dev_tools,
    LayerInit,
    Generate,
    Sample,
    EncodeMetarig,
    EncodeMetarigSample,
    EncodeWidget,
)


def register():
    # Classes.
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    # Classes.
    for cl in classes:
        bpy.utils.unregister_class(cl)
