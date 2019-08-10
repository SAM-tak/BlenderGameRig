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
    bones_in_frame, overwrite_prop_animation, get_rig_name
)
from . import rig_lists, generate


class MainPanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_main"
    bl_label = "GameRig"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'\
            and context.active_object.data.get("gamerig_rig_ui_template") is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        gparam = context.window_manager.gamerig
        armature = obj.data

        ## Layers
        # Ensure that the layers exist
        # Can't add while drawing, just use button
        if len(armature.gamerig_layers) < 30:
            layout.operator(InitLayerOperator.bl_idname)
        else:
            box = layout.box()
            show = gparam.show_layer_names_pane
            row = box.row()
            row.prop(gparam, "show_layer_names_pane", text="", toggle=True, icon='TRIA_DOWN' if show else 'TRIA_RIGHT', emboss=False)
            row.alignment = 'LEFT'
            row.label(text='Layer Name Settings')
            
            if show:
                # UI
                main_row = box.row(align=True).split(factor=0.06)
                col1 = main_row.column()
                col2 = main_row.column()
                col1.label()
                for i in range(1, 33):
                    if i == 17 or i == 31:
                        col1.label()
                    col1.label(text=str(i))

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
                    row = col.row(align=True)
                    icon = 'RESTRICT_VIEW_OFF' if armature.layers[i] else 'RESTRICT_VIEW_ON'
                    row.prop(armature, "layers", index=i, text="", toggle=True, icon=icon)
                    row.prop(gamerig_layer, "name", text="")
                    row.prop(gamerig_layer, "row", text="UI Row")
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
        show = gparam.show_bone_groups_pane
        row = box.row()
        row.prop(gparam, "show_bone_groups_pane", text="", toggle=True, icon='TRIA_DOWN' if show else 'TRIA_RIGHT', emboss=False)
        row.alignment = 'LEFT'
        row.label(text='Bone Group Settings')
        if show:
            color_sets = obj.data.gamerig_colors
            idx = obj.data.gamerig_colors_index

            row = box.row()
            row.operator(UseStandardColorsOperator.bl_idname, icon='FILE_REFRESH', text='')
            row = row.row(align=True)
            row.prop(armature.gamerig_selection_colors, 'select', text='')
            row.prop(armature.gamerig_selection_colors, 'active', text='')
            row = box.row(align=True)
            icon = 'LOCKED' if armature.gamerig_colors_lock else 'UNLOCKED'
            row.prop(armature, 'gamerig_colors_lock', text = 'Unified select/active colors', icon=icon)
            row.operator(ApplySelectionColorsOperator.bl_idname, icon='FILE_REFRESH', text='Apply')
            row = box.row()
            row.template_list(BoneGroupsUIList.bl_idname, "", obj.data, "gamerig_colors", obj.data, "gamerig_colors_index")

            col = row.column(align=True)
            col.operator(AddBoneGroupOperator.bl_idname, icon='ZOOM_IN', text="")
            col.operator(RemoveBoneGroupOperator.bl_idname, icon='ZOOM_OUT', text="").idx = obj.data.gamerig_colors_index
            col.menu(BoneGroupsSpecialsMenu.bl_idname, icon='DOWNARROW_HLT', text="")
            row = box.row()
            row.prop(armature, 'gamerig_theme_to_add', text = 'Theme')
            op = row.operator(AddBoneGroupThemeOperator.bl_idname, text="Add From Theme")
            op.theme = armature.gamerig_theme_to_add
            row = box.row()
            row.operator(AddBoneGroupsOperator.bl_idname, text="Add Standard")

        ## Generation
        if obj.mode in {'POSE', 'OBJECT'}:
            layout.row().prop(obj.data, "gamerig_rig_name", text="Rig Name")
            rig_name = get_rig_name(obj)
            target = next((i for i in context.collection.objects if i != obj and i.type == 'ARMATURE' and i.name == rig_name), None)
            if target:
                layout.row().operator(GenerateOperator.bl_idname, text="Regenerate Rig", icon='POSE_HLT')
                layout.row().box().label(text="Overwrite to '%s'" % target.name, icon='INFO')
                if obj.mode == 'OBJECT':
                    layout.row().operator(ToggleArmatureReferenceOperator.bl_idname, text="Toggle armature metarig/generated", icon='POSE_HLT')
            else:
                layout.row().operator(GenerateOperator.bl_idname, text="Generate New Rig", icon='POSE_HLT')
                layout.row().box().label(text="Create new armature '%s'" % rig_name, icon='INFO')

        elif obj.mode == 'EDIT':
            # Build types list
            category_name = str(gparam.category).replace(" ", "")

            for i in range(0, len(gparam.types)):
                gparam.types.remove(0)

            for r in rig_lists.rig_list:

                if category_name == "All":
                    a = gparam.types.add()
                    a.name = r
                elif r.startswith(category_name + '.'):
                    a = gparam.types.add()
                    a.name = r
                elif (category_name == "None") and ("." not in r):
                    a = gparam.types.add()
                    a.name = r

            # Rig type list
            layout.row().template_list("UI_UL_list", "gamerig_types", gparam, "types", gparam, 'active_type')

            props = layout.operator(AddSampleOperator.bl_idname, text="Add sample")
            props.metarig_type = gparam.types[gparam.active_type].name


class AddBoneGroupsOperator(bpy.types.Operator):
    bl_idname = "gamerig.add_bone_groups"
    bl_label = "Add Bone Groups"
    bl_description = "Add Standard Bone Groups"

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


class UseStandardColorsOperator(bpy.types.Operator):
    bl_idname = "gamerig.use_standard_colors"
    bl_label  = "Use standard colors"
    bl_description = "Reset active/select colors from current theme"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'gamerig_colors'):
            return {'FINISHED'}

        current_theme = bpy.context.preferences.themes.items()[0][0]
        theme = bpy.context.preferences.themes[current_theme]

        armature.gamerig_selection_colors.select = theme.view_3d.bone_pose
        armature.gamerig_selection_colors.active = theme.view_3d.bone_pose_active

        # for col in armature.gamerig_colors:
        #     col.select = theme.view_3d.bone_pose
        #     col.active = theme.view_3d.bone_pose_active

        return {'FINISHED'}


class ApplySelectionColorsOperator(bpy.types.Operator):
    bl_idname = "gamerig.apply_selection_colors"
    bl_label = "Apply colors"
    bl_description = "Apply user defined active/select colors"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'gamerig_colors'):
            return {'FINISHED'}

        #current_theme = bpy.context.preferences.themes.items()[0][0]
        #theme = bpy.context.preferences.themes[current_theme]

        for col in armature.gamerig_colors:
            col.select = armature.gamerig_selection_colors.select
            col.active = armature.gamerig_selection_colors.active

        return {'FINISHED'}


class AddBoneGroupOperator(bpy.types.Operator):
    bl_idname = "gamerig.bone_group_add"
    bl_label  = "Add GameRig bone group"
    bl_description = "Add bone group color set"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data

        if hasattr(armature, 'gamerig_colors'):
            armature.gamerig_colors.add()
            armature.gamerig_colors[-1].name = unique_name(armature.gamerig_colors, 'Group')

            current_theme = bpy.context.preferences.themes.items()[0][0]
            theme = bpy.context.preferences.themes[current_theme]

            armature.gamerig_colors[-1].normal = theme.view_3d.wire
            armature.gamerig_colors[-1].normal.hsv = theme.view_3d.wire.hsv
            armature.gamerig_colors[-1].select = theme.view_3d.bone_pose
            armature.gamerig_colors[-1].select.hsv = theme.view_3d.bone_pose.hsv
            armature.gamerig_colors[-1].active = theme.view_3d.bone_pose_active
            armature.gamerig_colors[-1].active.hsv = theme.view_3d.bone_pose_active.hsv

        return {'FINISHED'}


class AddBoneGroupThemeOperator(bpy.types.Operator):
    bl_idname = "gamerig.add_bone_group_theme"
    bl_label = "Add Gamerig bone group"
    bl_description = "Add Bone Group color set from Theme"
    bl_options = {"REGISTER", "UNDO"}

    theme: EnumProperty(
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

            theme_color_set = bpy.context.preferences.themes[0].bone_color_sets[id]

            armature.gamerig_colors[-1].normal = theme_color_set.normal
            armature.gamerig_colors[-1].select = theme_color_set.select
            armature.gamerig_colors[-1].active = theme_color_set.active

        return {'FINISHED'}


class RemoveBoneGroupOperator(bpy.types.Operator):
    bl_idname = "gamerig.remove_bone_group"
    bl_label  = "Remove Color Set"
    bl_description = "Remove a selected bone group color set"
    bl_options = {'UNDO'}

    idx: IntProperty()

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


class RemoveAllBoneGroupOperator(bpy.types.Operator):
    bl_idname = "gamerig.remove_all_bone_group"
    bl_label  = "Remove All Bone Groups"
    bl_description = "Remove all gamerig bone groups settings"
    bl_options = {'UNDO'}

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


class BoneGroupsUIList(bpy.types.UIList):
    bl_idname = "GAMERIG_UL_bone_groups"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row = row.split(factor=0.1)
        row.label(text=str(index+1))
        row = row.split(factor=0.7)
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


class BoneGroupsSpecialsMenu(bpy.types.Menu):
    bl_idname = "GAMERIG_MT_bone_groups_specials"
    bl_label = 'GameRig Bone Groups Specials'

    def draw(self, context):
        layout = self.layout

        layout.operator(RemoveAllBoneGroupOperator.bl_idname)


class RigTypePanel(bpy.types.Panel):
    bl_idname      = "GAMERIG_PT_rig_type"
    bl_label       = "GameRig Rig Type"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = "bone"
    #bl_options    = {'DEFAULT_OPEN'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.active_pose_bone\
            and context.active_object.data.get("gamerig_rig_ui_template") is not None

    def draw(self, context):
        gparam = context.window_manager.gamerig
        bone = context.active_pose_bone
        category_name = str(gparam.category).replace(" ", "")
        rig_name = str(context.active_pose_bone.gamerig_type).replace(" ", "")

        layout = self.layout

        # Build types list
        for i in range(0, len(gparam.types)):
            gparam.types.remove(0)

        for r in rig_lists.rig_list:
            if r in rig_lists.implementation_rigs:
                continue
            # collection = r.split('.')[0]  # UNUSED
            if category_name == "All":
                a = gparam.types.add()
                a.name = r
            elif r.startswith(category_name + '.'):
                a = gparam.types.add()
                a.name = r
            elif category_name == "None" and len(r.split('.')) == 1:
                a = gparam.types.add()
                a.name = r
        
        # Rig category field
        row = layout.row()
        row.prop(gparam, 'category', text="Category")

        # Rig type field
        row = layout.row()
        row.prop_search(bone, "gamerig_type", gparam, "types", text="Rig type:")

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


class DevToolsPanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_dev_tools"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label       = "GameRig Dev Tools"

    @classmethod
    def poll(cls, context):
        return context.mode in ['EDIT_ARMATURE', 'EDIT_MESH']\
         and context.preferences.addons['gamerig'].preferences.shows_dev_tools

    def draw(self, context):
        obj = context.active_object
        if obj is not None:
            if context.mode == 'EDIT_ARMATURE':
                r = self.layout.row()
                r.operator(EncodeMetarigOperator.bl_idname, text="Encode Metarig to Python")
                r = self.layout.row()
                r.operator(EncodeMetarigSampleOperator.bl_idname, text="Encode Sample to Python")

            if context.mode == 'EDIT_MESH':
                r = self.layout.row()
                r.operator(EncodeWidgetOperator.bl_idname, text="Encode Mesh Widget to Python")


class UtilityPanel(bpy.types.Panel):
    bl_idname = "GAMERIG_PT_utility"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = "bone"
    bl_label       = "GameRig Utility"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.active_pose_bone\
          and context.active_object.data.get("gamerig_id") is not None\
          and context.preferences.addons['gamerig'].preferences.shows_dev_tools

    def draw(self, context):
        layout = self.layout
        layout.operator(RevealUnlinkedWidgetOperator.bl_idname)


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


class InitLayerOperator(bpy.types.Operator):
    """Initialize armature gamerig layers"""

    bl_idname = "gamerig.init_layer"
    bl_label = "Add Layer Settings"
    bl_description = "Add GameRig Layers setting by default values"
    bl_options = {'UNDO'}

    def execute(self, context):
        obj = context.object
        arm = obj.data
        for i in range(1 + len(arm.gamerig_layers), 31):
            arm.gamerig_layers.add()
        return {'FINISHED'}


class RevealUnlinkedWidgetOperator(bpy.types.Operator):
    """Reveal unlinked widget in current scene.
    """
    bl_idname = "gamerig.reveal_unlinked_widget"
    bl_label = "Reveal unlinked widget"
    bl_description = "Link unlinked widget to current collection for edit"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene and context.object and context.object.type == 'ARMATURE' and context.active_pose_bone\
         and context.active_pose_bone.custom_shape is not None\
         and not (context.active_pose_bone.custom_shape.name in context.view_layer.objects)

    def execute(self, context):
        context.collection.objects.link(context.active_pose_bone.custom_shape)
        return {'FINISHED'}


class GenerateOperator(bpy.types.Operator):
    """Generates a rig from the active metarig armature"""

    bl_idname      = "gamerig.generate"
    bl_label       = "Generate Rig"
    bl_description = 'Generates a rig from the active metarig armature'
    bl_options     = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return not context.object.hide_viewport and not context.object.hide_select

    def execute(self, context):
        import importlib
        importlib.reload(generate)

        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False
        try:
            generate.generate_rig(context, context.object)
        except MetarigError as rig_exception:
            gamerig_report_exception(self, rig_exception)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo

        return {'FINISHED'}


class ToggleArmatureReferenceOperator(bpy.types.Operator):
    """Toggle armature reference between metarig and generated rig."""

    bl_idname  = "gamerig.toggle_armature"
    bl_label   = "Toggle Rig"
    bl_description = "Toggle armature reference between metarig and generated rig"
    bl_options = {'UNDO'}

    def execute(self, context):
        metarig = context.object
        if metarig.data.get("gamerig_rig_ui_template") is not None:
            rig_name = get_rig_name(metarig)
            genrig = next((i for i in context.collection.objects if i and i != metarig and i.type == 'ARMATURE' and i.name == rig_name), None)
            if genrig is not None:
                for i in context.collection.objects:
                    for j in i.modifiers:
                        if j.type == 'ARMATURE':
                            if j.object == genrig:
                                j.object = metarig
                            elif j.object == metarig:
                                j.object = genrig

        return {'FINISHED'}


class AddSampleOperator(bpy.types.Operator):
    """Create a sample metarig to be modified before generating """ \
    """the final rig"""

    bl_idname  = "gamerig.add_metarig_sample"
    bl_label = "Add sample"
    bl_description = "Add a sample metarig for a rig type"
    bl_options = {'UNDO'}

    metarig_type: StringProperty(
        name="Type",
        description="Name of the rig type to generate a sample of",
        maxlen=128,
    )

    def execute(self, context):
        if context.mode == 'EDIT_ARMATURE' and self.metarig_type != "":
            use_global_undo = context.preferences.edit.use_global_undo
            context.preferences.edit.use_global_undo = False
            try:
                rig = get_rig_type(self.metarig_type)
                create_sample = rig.create_sample
            except (ImportError, AttributeError):
                raise Exception("rig type '" + self.metarig_type + "' has no sample.")
            else:
                create_sample(context.active_object)
            finally:
                context.preferences.edit.use_global_undo = use_global_undo
                bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarigOperator(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname = "gamerig.encode_metarig"
    bl_label = "Encode Metarig"
    bl_description = "Encode whole metarig to script"
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

        text = write_metarig(context.active_object, func_name="create", layers=True, groups=True, template=True)
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarigSampleOperator(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig
        as a sample.
    """
    bl_idname  = "gamerig.encode_metarig_sample"
    bl_label   = "Encode Metarig Sample"
    bl_description = "Encode rig to script as sample rig"
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

        text = write_metarig(context.active_object, func_name="create_sample")
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeWidgetOperator(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname = "gamerig.encode_mesh_widget"
    bl_label = "Encode Widget"
    bl_description = "Encode widget mesh data to script"
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
    AddBoneGroupsOperator,
    UseStandardColorsOperator,
    ApplySelectionColorsOperator,
    AddBoneGroupOperator,
    AddBoneGroupThemeOperator,
    RemoveBoneGroupOperator,
    RemoveAllBoneGroupOperator,
    InitLayerOperator,
    RevealUnlinkedWidgetOperator,
    GenerateOperator,
    AddSampleOperator,
    ToggleArmatureReferenceOperator,
    EncodeMetarigOperator,
    EncodeMetarigSampleOperator,
    EncodeWidgetOperator,
    BoneGroupsUIList,
    BoneGroupsSpecialsMenu,
    MainPanel,
    RigTypePanel,
    UtilityPanel,
    DevToolsPanel,
)


def register():
    # Classes.
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    # Classes.
    for cl in classes:
        bpy.utils.unregister_class(cl)
